"""Archive the existing portable build without user data or another program directory."""
from pathlib import Path
import argparse,hashlib,re,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--version',default='2.7.0');args=parser.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise ValueError('Invalid release version')
program=ROOT/'dist/GameCloudSave';installer=ROOT/('dist/installers/GameCloudSave-Setup-V'+args.version+'.exe')
for file in (program/'GameCloudSave.exe',program/'Uninstall.exe',program/'source.zip',program/'使用说明.txt',installer):
    if not file.is_file():raise ValueError('Missing release input: '+file.name)
output=ROOT/'dist/releases';output.mkdir(exist_ok=True)
portable=output/('GameCloudSave-V'+args.version+'-Portable.zip')
allowed={'GameCloudSave.exe','Uninstall.exe','source.zip','LICENSE','THIRD_PARTY_NOTICES.md','使用说明.txt','更新说明.md'}
files=[file for file in program.rglob('*') if file.is_file() and (file.relative_to(program).parts[0] in ('_internal','licenses') or file.relative_to(program).as_posix() in allowed)]
if any(file.suffix.lower()=='.dpapi' for file in files):raise ValueError('Credential file in build')
with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for file in sorted(files):archive.write(file,'GameCloudSave-Portable/'+file.relative_to(program).as_posix())
source=output/('GameCloudSave-V'+args.version+'-Source.zip');shutil.copy2(program/'source.zip',source)
for file in (portable,source):
    with zipfile.ZipFile(file) as archive:
        if archive.testzip():raise ValueError('Corrupt archive: '+file.name)
        names=archive.namelist()
        if any(name.endswith('.dpapi') or any(part in ('data','test-data','machines','.venv','.git') for part in Path(name).parts) for name in names):raise ValueError('Private data in archive')
report=output/('GameCloudSave-V'+args.version+'-Report.md')
shutil.copy2(ROOT/('docs/V'+args.version+'完整优化报告.md'),report)
assets=(installer,portable,source,report)
checks=[]
for file in assets:
    with file.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
    checks.append(checksum+'  '+file.name)
(output/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='utf-8')
for file in (*assets,output/'SHA256SUMS.txt'):print(file.name+': '+str(file.stat().st_size)+' bytes')
