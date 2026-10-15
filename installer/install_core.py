"""Per-user install/uninstall with tracked files and preserved application data."""
from pathlib import Path,PurePosixPath
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

PRODUCT='GameCloudSave'
MARKER='gamecloud-install.json'
REGISTRY_KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\GameCloudSave'

def registry_state():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REGISTRY_KEY) as entry:
            return [winreg.EnumValue(entry,index) for index in range(winreg.QueryInfoKey(entry)[1])]
    except FileNotFoundError:return None

def restore_registry(values):
    import winreg
    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,REGISTRY_KEY)
    except FileNotFoundError:pass
    if values is not None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,REGISTRY_KEY) as entry:
            for name,value,kind in values:winreg.SetValueEx(entry,name,0,kind,value)

def installed_directory():
    values={name:value for name,value,_ in registry_state() or []}
    return values.get('InstallLocation','')

def owned_path(root,name):
    path=checked(root,name);parts=PurePosixPath(str(name).replace('\\','/')).parts
    if not parts or any(part.casefold() in ('data','machines','test-data','snapshots') for part in parts) or path.suffix.casefold()=='.dpapi' or str(name).casefold()==MARKER:
        raise ValueError('安装清单包含个人数据或无效文件，已停止操作')
    return path

def read_record(target):
    try:record=json.loads((target/MARKER).read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('此目录不是有效安装目录；便携版请保留 data 后自行移除程序文件') from None
    if not isinstance(record,dict) or record.get('product')!=PRODUCT or not isinstance(record.get('files'),list) or not record['files']:
        raise ValueError('安装清单无效，已停止操作')
    for name in record['files']:
        if not isinstance(name,str):raise ValueError('安装清单无效')
        owned_path(target,name)
    if record.get('exe') not in record['files'] or 'Uninstall.exe' not in record['files']:raise ValueError('安装清单缺少程序记录')
    return record
def checked(root,relative):
    relative=str(relative).replace('\\','/')
    if PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts or ':' in relative:raise ValueError('安装包路径无效')
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('安装文件越界')
    return path
def running(root):
    import psutil
    own_exe=Path(sys.executable).resolve()
    parents={process.pid for process in psutil.Process().parents()} if getattr(sys,'frozen',False) else set()
    for process in psutil.process_iter(['exe','pid']):
        if process.info['pid']==os.getpid() or not process.info.get('exe'):continue
        try:
            if process.info['pid'] in parents and Path(process.info['exe']).resolve()==own_exe:continue
            if Path(process.info['exe']).resolve().is_relative_to(root.resolve()):return True
        except OSError:pass
    return False
def shortcut(link,exe,remove=False):
    link=Path(link);exe=Path(exe)
    script="""param([string]$Link,[string]$Exe,[string]$Remove)
$taskShell=New-Object -ComObject WScript.Shell
if($Remove -eq 'yes') {
  if(Test-Path -LiteralPath $Link) {
    $taskExisting=$taskShell.CreateShortcut($Link)
    if($taskExisting.TargetPath -eq $Exe) { Remove-Item -LiteralPath $Link }
  }
} else {
  $taskShortcut=$taskShell.CreateShortcut($Link)
  $taskShortcut.TargetPath=$Exe
  $taskShortcut.WorkingDirectory=Split-Path -Parent $Exe
  $taskShortcut.IconLocation=$Exe+',0'
  $taskShortcut.Save()
}
"""
    if not remove:link.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        file=Path(temporary)/'shortcut.ps1';file.write_text(script,encoding='utf-8-sig')
        result=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(file),'-Link',str(link),'-Exe',str(exe),'-Remove','yes' if remove else 'no'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise ValueError('桌面或开始菜单快捷方式创建失败')
def register(root,exe,version):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\GameCloudSave') as registry:
        for name,value in {'DisplayName':PRODUCT,'DisplayVersion':version,'InstallLocation':str(root),'DisplayIcon':str(exe),'UninstallString':'"'+str(root/'Uninstall.exe')+'"','Publisher':'GameCloudSave contributors'}.items():winreg.SetValueEx(registry,name,0,winreg.REG_SZ,value)
        winreg.SetValueEx(registry,'QuietUninstallString',0,winreg.REG_SZ,'"'+str(root/'Uninstall.exe')+'" --silent')
        for name in ('NoModify','NoRepair'):winreg.SetValueEx(registry,name,0,winreg.REG_DWORD,1)
def install(payload,target,desktop=None,start_menu=None,version='2.3',registry=True,progress=lambda value:None):
    target=Path(target).resolve()
    if target==Path(target.anchor) or target==Path.home().resolve():raise ValueError('请选择软件专用安装文件夹')
    previous={}
    if target.exists() and any(target.iterdir()):
        try:previous=json.loads((target/MARKER).read_text(encoding='utf-8'))
        except (OSError,ValueError):raise ValueError('该目录已有其他文件，请选择空目录或现有 GameCloudSave 安装目录') from None
        if not isinstance(previous,dict) or previous.get('product')!=PRODUCT:raise ValueError('安装目录不属于 GameCloudSave')
        previous=read_record(target)
    original_registry=registry_state() if registry else None
    location=next((value for name,value,_ in original_registry or [] if name=='InstallLocation'),'')
    if location and Path(location).resolve()!=target and (Path(location)/MARKER).is_file():
        raise ValueError('已有安装位于 '+location+'，请选择原目录升级，或先卸载原安装')
    if running(target):raise ValueError('请先退出 GameCloudSave，包括托盘中的程序')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent,prefix='gamecloud-stage-') as temporary:
        stage=Path(temporary)/'new';journal=Path(temporary)/'old';stage.mkdir();journal.mkdir()
        with zipfile.ZipFile(payload) as zipped:
            for info in zipped.infolist():
                owned_path(stage,info.filename)
            if zipped.testzip():raise ValueError('安装包损坏')
            zipped.extractall(stage)
        files=[file.relative_to(stage).as_posix() for file in stage.rglob('*') if file.is_file()]
        exes=[name for name in files if name=='GameCloudSave.exe' or '/' not in name and name.startswith('GameCloudSave-V') and name.endswith('.exe')]
        if len(exes)!=1 or 'Uninstall.exe' not in files:raise ValueError('安装包缺少主程序或卸载程序')
        if any(name.startswith(('data/','machines/')) for name in files):raise ValueError('安装包不应包含用户数据')
        target.mkdir(exist_ok=True);changed=[];new=[];link_journal={}
        marker_before=(target/MARKER).read_bytes() if (target/MARKER).exists() else None
        try:
            for index,name in enumerate(files):
                destination=checked(target,name);source=checked(stage,name)
                if destination.exists():
                    saved=checked(journal,name);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved);changed.append(name)
                else:new.append(name)
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
                progress(int(85*(index+1)/max(1,len(files))))
            exe=target/exes[0];links=[]
            for directory in (desktop,start_menu):
                if directory:
                    link=Path(directory)/'GameCloudSave.lnk'
                    link_journal[link]=link.read_bytes() if link.is_file() else None
                    shortcut(link,exe);links.append(str(link))
            for name in set(previous.get('files',[]))-set(files):
                obsolete=owned_path(target,name)
                if obsolete.is_file():
                    saved=checked(journal,name);saved.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(obsolete,saved);changed.append(name);obsolete.unlink()
            record={'product':PRODUCT,'version':version,'exe':exes[0],'files':sorted(files),'links':list(set(links+previous.get('links',[]))),'registered':registry}
            (target/MARKER).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            if registry:register(target,exe,version)
            progress(100);return exe
        except Exception:
            for name in new:checked(target,name).unlink(missing_ok=True)
            for name in changed:
                destination=checked(target,name);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(checked(journal,name),destination)
            for link,content in link_journal.items():
                if content is None:link.unlink(missing_ok=True)
                else:link.write_bytes(content)
            if marker_before is None:(target/MARKER).unlink(missing_ok=True)
            else:(target/MARKER).write_bytes(marker_before)
            if registry:restore_registry(original_registry)
            raise
def uninstall(target,progress=lambda value:None):
    target=Path(target).resolve()
    record=read_record(target)
    if record.get('product')!=PRODUCT or target==Path(target.anchor):raise ValueError('卸载目录无效')
    if running(target):raise ValueError('请先退出 GameCloudSave，包括托盘中的程序')
    files=[checked(target,name) for name in record['files']]
    exe=checked(target,record['exe'])
    for link in record.get('links',[]):
        if Path(link).name=='GameCloudSave.lnk':shortcut(link,exe,remove=True)
    own=Path(sys.executable).resolve() if getattr(sys,'frozen',False) else None
    for index,file in enumerate(files):
        if file!=own:file.unlink(missing_ok=True)
        progress(int(90*(index+1)/max(1,len(files))))
    if record.get('registered'):
        import winreg
        key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\GameCloudSave'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as entry:location=winreg.QueryValueEx(entry,'InstallLocation')[0]
            if Path(location).resolve()==target:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
        except FileNotFoundError:pass
    (target/MARKER).unlink()
    directories=set()
    for file in files:
        parent=file.parent
        while parent!=target and parent.is_relative_to(target):directories.add(parent);parent=parent.parent
    for directory in sorted(directories,key=lambda p:len(p.parts),reverse=True):
        try:directory.rmdir()
        except OSError:pass
    if own and own.parent==target and own.name=='Uninstall.exe':
        helper=Path(tempfile.gettempdir())/('gamecloud-cleanup-'+str(os.getpid())+'.ps1')
        helper.write_text("""param([int]$WaitPid,[string]$File,[string]$Parent)
$taskResolved=[System.IO.Path]::GetFullPath($File)
$taskParent=[System.IO.Path]::GetFullPath($Parent)
if((Split-Path -Leaf $taskResolved) -ne 'Uninstall.exe' -or (Split-Path -Parent $taskResolved) -ne $taskParent) { exit 1 }
Wait-Process -Id $WaitPid -ErrorAction SilentlyContinue
for($taskAttempt=0; $taskAttempt -lt 60; $taskAttempt++) {
  Remove-Item -LiteralPath $taskResolved -ErrorAction SilentlyContinue
  if(-not (Test-Path -LiteralPath $taskResolved)) { break }
  Start-Sleep -Milliseconds 200
}
if((Test-Path -LiteralPath $taskParent) -and @(Get-ChildItem -LiteralPath $taskParent -Force).Count -eq 0) { Remove-Item -LiteralPath $taskParent }
Remove-Item -LiteralPath $PSCommandPath -ErrorAction SilentlyContinue
""",encoding='utf-8-sig')
        subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper),'-WaitPid',str(os.getpid()),'-File',str(own),'-Parent',str(target)],creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:target.rmdir()
        except OSError:pass
    progress(100)
