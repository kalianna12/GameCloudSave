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
def install(payload,target,desktop=None,start_menu=None,version='2.2.1',registry=True,progress=lambda value:None):
    target=Path(target).resolve()
    if target==Path(target.anchor) or target==Path.home().resolve():raise ValueError('请选择软件专用安装文件夹')
    previous={}
    if target.exists() and any(target.iterdir()):
        try:previous=json.loads((target/MARKER).read_text(encoding='utf-8'))
        except (OSError,ValueError):raise ValueError('该目录已有其他文件，请选择空目录或现有 GameCloudSave 安装目录') from None
        if previous.get('product')!=PRODUCT:raise ValueError('安装目录不属于 GameCloudSave')
    if running(target):raise ValueError('请先退出 GameCloudSave，包括托盘中的程序')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent,prefix='gamecloud-stage-') as temporary:
        stage=Path(temporary)/'new';journal=Path(temporary)/'old';stage.mkdir();journal.mkdir()
        with zipfile.ZipFile(payload) as zipped:
            for info in zipped.infolist():checked(stage,info.filename)
            if zipped.testzip():raise ValueError('安装包损坏')
            zipped.extractall(stage)
        files=[file.relative_to(stage).as_posix() for file in stage.rglob('*') if file.is_file()]
        exes=[name for name in files if '/' not in name and name.startswith('GameCloudSave-V') and name.endswith('.exe')]
        if len(exes)!=1 or 'Uninstall.exe' not in files:raise ValueError('安装包缺少主程序或卸载程序')
        if any(name.startswith(('data/','machines/')) for name in files):raise ValueError('安装包不应包含用户数据')
        target.mkdir(exist_ok=True);changed=[];new=[]
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
                    link=Path(directory)/'GameCloudSave.lnk';shortcut(link,exe);links.append(str(link))
            record={'product':PRODUCT,'version':version,'exe':exes[0],'files':sorted(set(files+previous.get('files',[]))),'links':list(set(links+previous.get('links',[]))),'registered':registry}
            (target/MARKER).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            if registry:register(target,exe,version)
            progress(100);return exe
        except Exception:
            for name in new:checked(target,name).unlink(missing_ok=True)
            for name in changed:shutil.copy2(checked(journal,name),checked(target,name))
            raise
def uninstall(target,progress=lambda value:None):
    target=Path(target).resolve()
    record=json.loads((target/MARKER).read_text(encoding='utf-8'))
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
