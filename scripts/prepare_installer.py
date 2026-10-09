"""Prepare a self-contained payload, source archive and dependency notices."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
import zipfile
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--version',default='2.3.1');args=parser.parse_args()
import re
if not re.fullmatch(r'\d+(\.\d+){0,2}',args.version):raise ValueError('Invalid version')
release=ROOT/'dist/GameCloudSave';output=ROOT/'build/installer-payload';output.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'dist/installer-tools/Uninstall.exe',release/'Uninstall.exe')
for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(ROOT/name,release/name)
licenses=release/'licenses';licenses.mkdir(exist_ok=True)
versions={}
for package in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','psutil','Pillow','PyInstaller'):
    try:distribution=metadata.distribution(package)
    except metadata.PackageNotFoundError:
        if package=='Pillow':continue
        raise
    versions[package]=distribution.version
    for relative in distribution.files or []:
        if 'license' not in str(relative).casefold() and 'copying' not in str(relative).casefold():continue
        source=Path(distribution.locate_file(relative))
        if source.is_file():
            target=licenses/package/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def license_download(item):
    name,urls=item;target=licenses/name
    if target.is_file() and target.stat().st_size>1000:return
    for url in urls:
        try:
            with urlopen(url,timeout=12) as response:content=response.read()
            if len(content)<1000:continue
            target.write_bytes(content);return
        except Exception:continue
    raise ValueError('Unable to obtain license: '+name)
license_urls={
 'LGPL-3.0.txt':['https://raw.githubusercontent.com/spdx/license-list-data/main/text/LGPL-3.0-only.txt','https://www.gnu.org/licenses/lgpl-3.0.txt'],
 'GPL-3.0.txt':['https://raw.githubusercontent.com/spdx/license-list-data/main/text/GPL-3.0-only.txt','https://www.gnu.org/licenses/gpl-3.0.txt'],
 'GPL-2.0.txt':['https://raw.githubusercontent.com/spdx/license-list-data/main/text/GPL-2.0-only.txt','https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt']}
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(license_download,license_urls.items()))
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.is_file():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
rclone=shutil.which('rclone')
license_output=subprocess.run([rclone,'version'],capture_output=True,text=True,encoding='utf-8').stdout
(licenses/'rclone-version.txt').write_text(license_output,encoding='utf-8')
rclone_tag=license_output.splitlines()[0].split()[-1]
license_download(('rclone-LICENSE.txt',['https://raw.githubusercontent.com/rclone/rclone/'+rclone_tag+'/COPYING','https://raw.githubusercontent.com/rclone/rclone/master/COPYING']))
(licenses/'versions.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
source_paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode('utf-8').split('\0')
with zipfile.ZipFile(release/'source.zip','w',zipfile.ZIP_DEFLATED) as zipped:
    for name in sorted(set(source_paths)):
        if not name or name.startswith(('data/','test-data/','dist/','build/','.venv/','.git/','.codex/')):continue
        source=(ROOT/name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():continue
        if source.suffix.lower() not in ('.py','.qml','.svg','.json','.md','.ps1','.bat','.txt','.toml','.yaml','.ico') and source.name not in ('LICENSE','.gitignore'):continue
        zipped.write(source,name)
with zipfile.ZipFile(output/'payload.zip','w',zipfile.ZIP_STORED) as zipped:
    for file in release.rglob('*'):
        relative=file.relative_to(release)
        if relative.parts[0] in ('data','test-data'):continue
        if file.is_file():zipped.write(file,relative.as_posix())
with (output/'payload.zip').open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
(output/'payload.json').write_text(json.dumps({'version':args.version,'sha256':sha}),encoding='utf-8')
print('Prepared installer payload and source archive')
