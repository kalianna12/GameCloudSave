"""Opt-in dependency repair, pinned official driver download and interactive UAC setup."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from PySide6.QtCore import QObject,Property,Signal,Slot

DRIVER_URL='https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe'
# Microsoft winget-pkgs: manifests/v/ViGEm/ViGEmBus/1.22.0/ViGEm.ViGEmBus.installer.yaml
DRIVER_SHA256='89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a'


def inspect_components():
    package=bool(importlib.util.find_spec('vgamepad'));driver=False
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Services\ViGEmBus'):driver=True
        except OSError:pass
    return {'package':package,'driver':driver,'ready':package and driver,'supported':os.name=='nt'}


def download_driver(folder,cancel,progress):
    from urllib.request import Request,urlopen
    folder.mkdir(parents=True,exist_ok=True);target=folder/'ViGEmBus_1.22.0.exe';temporary=target.with_suffix('.part')
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==DRIVER_SHA256:return target
    try:
        digest=hashlib.sha256();total=0;started=time.monotonic();last=-1
        with urlopen(Request(DRIVER_URL,headers={'User-Agent':'GameCloudSave mapping setup'}),timeout=20) as response:
            length=int(response.headers.get('Content-Length',0))
            with temporary.open('wb') as output:
                while True:
                    block=response.read(131072)
                    if not block:break
                    if cancel.is_set():raise InterruptedError('已取消下载')
                    if time.monotonic()-started>180:raise TimeoutError('驱动下载超时，请重试')
                    total+=len(block)
                    if total>64*1024*1024:raise ValueError('驱动下载超出预期大小')
                    digest.update(block);output.write(block)
                    percent=min(99,int(total/length*100)) if length else 0
                    if percent!=last:progress('正在下载官方驱动 '+str(percent)+'%');last=percent
        if digest.hexdigest()!=DRIVER_SHA256:raise ValueError('驱动完整性校验失败，未运行安装程序')
        temporary.replace(target);return target
    finally:temporary.unlink(missing_ok=True)


def verify_signature(path):
    environment=dict(os.environ,GCS_MAPPING_INSTALLER=str(path))
    command="$s=Get-AuthenticodeSignature -LiteralPath $env:GCS_MAPPING_INSTALLER; @{status=[string]$s.Status;subject=$s.SignerCertificate.Subject}|ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=30,env=environment)
    info=json.loads(result.stdout)
    if info.get('status')!='Valid' or 'Nefarius Software Solutions' not in info.get('subject',''):raise ValueError('驱动签名校验失败，未运行安装程序')


def run_installer(path,cancel):
    class EXECUTE(C.Structure):
        _fields_=[('size',W.DWORD),('mask',W.ULONG),('hwnd',W.HWND),('verb',W.LPCWSTR),('file',W.LPCWSTR),('parameters',W.LPCWSTR),('directory',W.LPCWSTR),('show',C.c_int),('instance',W.HINSTANCE),('idlist',C.c_void_p),('className',W.LPCWSTR),('classKey',W.HKEY),('hotKey',W.DWORD),('icon',W.HANDLE),('process',W.HANDLE)]
    shell=C.WinDLL('shell32',use_last_error=True);shell.ShellExecuteExW.argtypes=[C.POINTER(EXECUTE)];shell.ShellExecuteExW.restype=W.BOOL
    kernel=C.WinDLL('kernel32',use_last_error=True);kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)];kernel.CloseHandle.argtypes=[W.HANDLE]
    request=EXECUTE();request.size=C.sizeof(request);request.mask=0x40|0x100;request.verb='runas';request.file=str(path);request.parameters='/norestart';request.show=1
    if not shell.ShellExecuteExW(C.byref(request)):
        if C.get_last_error()==1223:raise InterruptedError('已取消驱动安装')
        raise C.WinError(C.get_last_error())
    try:
        while True:
            result=kernel.WaitForSingleObject(request.process,250)
            if result==0:break
            if result!=0x102:raise C.WinError(C.get_last_error())
            if cancel.is_set():return None  # The system installer remains under user control.
        code=W.DWORD()
        if not kernel.GetExitCodeProcess(request.process,C.byref(code)):raise C.WinError(C.get_last_error())
        return code.value
    finally:kernel.CloseHandle(request.process)


class MappingSetup(QObject):
    changed=Signal()
    arrived=Signal(object,str)
    progress=Signal(str)
    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self._state=inspect_components();self._busy=False;self._message='';self._cancel=threading.Event();self._closed=False
        self.arrived.connect(self.receive);self.progress.connect(self.report)
    @Property('QVariantMap',notify=changed)
    def state(self):return {**self._state,'busy':self._busy,'message':self._message}
    @Slot(str)
    def report(self,message):
        if not self._closed:self._message=message;self.changed.emit()
    @Slot(object,str)
    def receive(self,state,message):
        if self._closed:return
        self._state=state;self._busy=False;self._message=message;self.changed.emit()
    @Slot()
    def detect(self):self.start(False)
    @Slot()
    def install(self):self.start(True)
    def start(self,repair):
        if self._closed or self._busy:return
        self._busy=True;self._message='正在检测组件';self.changed.emit()
        def work():
            try:
                state=inspect_components();needs_restart=False;message='组件已就绪' if state['ready'] else '手柄→键鼠可直接使用；反向映射需要补齐组件'
                if repair and not state['ready']:
                    if not state['supported']:raise ValueError('此功能需要 Windows')
                    if not state['package']:
                        if getattr(sys,'frozen',False):raise ValueError('当前发行包缺少映射模块，请使用带映射模块的版本')
                        self.progress.emit('正在安装键鼠→手柄模块')
                        environment=dict(os.environ,VGAMEPAD_SKIP_VIGEMBUS_INSTALL='true',PIP_DISABLE_PIP_VERSION_CHECK='1')
                        result=subprocess.run([sys.executable,'-m','pip','install','vgamepad==0.1.0','--retries','1','--timeout','20'],env=environment,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
                        if result.returncode:raise RuntimeError('映射模块安装失败，请检查网络后重试')
                        importlib.invalidate_caches()
                    if not state['driver'] and not self._cancel.is_set():
                        path=download_driver(self.store.profile/'mapping-setup',self._cancel,self.progress.emit);self.progress.emit('正在校验驱动签名');verify_signature(path)
                        if not self._cancel.is_set():
                            self.progress.emit('请在 Windows 安装窗口中完成驱动安装');code=run_installer(path,self._cancel)
                            if code not in (None,0,1641,3010):raise RuntimeError('驱动安装未完成（'+str(code)+'），可重新检测后重试')
                            needs_restart=code in (1641,3010)
                            message='驱动安装完成，请重新检测；若提示重启，请先保存工作再重启电脑'
                    state=inspect_components()
                    state['restart']=needs_restart
                    if state['ready']:message='组件已安装，需要重启电脑后生效；请先保存工作' if needs_restart else '组件已就绪，可以启用键鼠→手柄'
                if not self._closed:self.arrived.emit(state,message)
            except Exception as error:
                if not self._closed:self.arrived.emit(inspect_components(),str(error)[:200])
        threading.Thread(target=work,name='mapping-setup',daemon=True).start()
    def shutdown(self):self._closed=True;self._cancel.set()
