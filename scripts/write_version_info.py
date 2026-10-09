"""Windows file properties; preserve timestamps when the version is unchanged."""
from pathlib import Path
import sys,re
version=sys.argv[1]
if not re.fullmatch(r'\d+(\.\d+){0,2}',version):raise ValueError('Invalid version')
numbers=tuple(int(n) for n in version.split('.'))
numbers+=tuple(0 for _ in range(4-len(numbers)))
content=f'''VSVersionInfo(
 ffi=FixedFileInfo(filevers={numbers},prodvers={numbers},mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),
 kids=[StringFileInfo([StringTable('040904B0',[
 StringStruct('CompanyName','GameCloudSave contributors'),
 StringStruct('FileDescription','GameCloudSave'),
 StringStruct('FileVersion','{version}'),
 StringStruct('InternalName','GameCloudSave'),
 StringStruct('OriginalFilename','GameCloudSave.exe'),
 StringStruct('ProductName','GameCloudSave'),
 StringStruct('ProductVersion','{version}')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
'''
target=Path(__file__).resolve().parents[1]/'build/version_info.txt';target.parent.mkdir(exist_ok=True)
if not target.exists() or target.read_text('utf-8')!=content:target.write_text(content,'utf-8')
