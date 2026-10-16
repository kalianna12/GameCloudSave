"""Bounded startup-only window detection. No hooks, capture or game injection."""
import ctypes,os,ntpath,time
from ctypes import wintypes as W
from pathlib import Path

IGNORED=('steam.exe','steamwebhelper.exe','playnite.desktopapp.exe','playnite.fullscreenapp.exe','epicgameslauncher.exe','cmd.exe','conhost.exe','explorer.exe')
def windows():
    if os.name!='nt':return []
    user=ctypes.windll.user32;dwm=ctypes.windll.dwmapi
    user.GetWindow.argtypes=[W.HWND,W.UINT];user.GetWindow.restype=W.HWND
    user.GetWindowLongW.argtypes=[W.HWND,ctypes.c_int];user.GetWindowLongW.restype=ctypes.c_long
    user.IsWindowVisible.argtypes=[W.HWND];user.IsIconic.argtypes=[W.HWND];user.IsHungAppWindow.argtypes=[W.HWND]
    user.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    dwm.DwmGetWindowAttribute.argtypes=[W.HWND,W.DWORD,ctypes.c_void_p,W.DWORD]
    rows=[]
    @ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    def collect(hwnd,_):
        if not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd) or user.IsHungAppWindow(hwnd):return True
        if user.GetWindowLongW(hwnd,-20)&0x80:return True  # tool/splash windows
        cloaked=W.DWORD()
        if not dwm.DwmGetWindowAttribute(hwnd,14,ctypes.byref(cloaked),ctypes.sizeof(cloaked)) and cloaked.value:return True
        rect=W.RECT();user.GetClientRect(hwnd,ctypes.byref(rect));width=rect.right-rect.left;height=rect.bottom-rect.top
        if width<320 or height<180:return True
        title=ctypes.create_unicode_buffer(512);user.GetWindowTextW(hwnd,title,512)
        if any(s in title.value.casefold() for s in ('launcher','updater','splash','启动器','更新程序')):return True
        pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        rows.append({'hwnd':int(hwnd),'pid':pid.value,'size':(width,height)})
        return True
    user.EnumWindows(collect,0)
    return rows

class Probe:
    def __init__(self,local,pid=None):
        self.local=dict(local);self.pid=pid if type(pid)==int else None;self.cache={}
        self.exe=ntpath.normcase(ntpath.normpath(local.get('monitor_exe') or local.get('exe') or ''))
        root=local.get('install_dir') or (str(Path(self.exe).parent) if self.exe and local.get('launch_mode')=='direct' else '')
        self.root=ntpath.normcase(ntpath.normpath(root)) if root and len(Path(root).parts)>=3 else ''
    def matches(self,pid):
        import psutil
        if pid==os.getpid():return False
        try:
            p=psutil.Process(pid);name=p.name().casefold()
            if name in IGNORED or any(t in name for t in ('crash','unins','redist','anticheat','launcher','updater','setup')):return False
            created=p.create_time();key=(pid,created)
            if key in self.cache:return self.cache[key]
            exe=ntpath.normcase(ntpath.normpath(p.exe()))
            same=bool(self.exe and exe==self.exe)
            rooted=bool(self.root and exe.startswith(self.root.rstrip('\\')+'\\'))
            child=bool(self.pid and (pid==self.pid or any(parent.pid==self.pid for parent in p.parents())))
            matched=same or rooted or child
            self.cache[key]=matched;return matched
        except (psutil.Error,OSError):return False

def wait(probe,cancel,timeout=60,sample=None,clock=time.monotonic):
    sample=sample or windows;started=clock();stable=None;since=started
    while not cancel.is_set():
        now=clock();eligible=[w for w in sample() if probe.matches(w['pid'])]
        chosen=max(eligible,key=lambda w:w['size'][0]*w['size'][1],default=None)
        key=(chosen['hwnd'],chosen['pid'],chosen['size']) if chosen else None
        if key!=stable:stable=key;since=now
        if key and now-since>=.7:return {'phase':'ready','hwnd':chosen['hwnd'],'pid':chosen['pid'],'message':'游戏窗口已就绪'}
        if now-started>=timeout:return {'phase':'timeout','message':'尚未检测到游戏窗口，可继续等待或返回游戏库'}
        cancel.wait(.25)
    return {'phase':'cancelled','message':'已返回游戏库，游戏启动请求仍有效'}

def pin(hwnd,enabled):
    if os.name!='nt' or not hwnd:return
    user=ctypes.windll.user32;user.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
    user.SetWindowPos(hwnd,-1 if enabled else -2,0,0,0,0,0x13)  # no resize/move/activate

def foreground():
    if os.name!='nt':return (0,0)
    user=ctypes.windll.user32;user.GetForegroundWindow.restype=W.HWND
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    hwnd=user.GetForegroundWindow();pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    return int(hwnd or 0),pid.value

def activate(hwnd,pid=None):
    if os.name!='nt' or not hwnd:return
    user=ctypes.windll.user32;user.IsWindow.argtypes=[W.HWND];user.IsIconic.argtypes=[W.HWND]
    user.SetForegroundWindow.argtypes=[W.HWND];user.ShowWindow.argtypes=[W.HWND,ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    if user.IsWindow(hwnd):
        current=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(current))
        if pid and current.value!=pid:return
        if user.IsIconic(hwnd):user.ShowWindow(hwnd,9)
        user.SetForegroundWindow(hwnd)
