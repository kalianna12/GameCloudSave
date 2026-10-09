"""Upgrading a versioned executable keeps one program and preserves user files."""
from pathlib import Path
import sys,tempfile,json,zipfile,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
from install_core import install,MARKER,PRODUCT
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'test-data') as directory:
    directory=Path(directory);target=directory/'installed';target.mkdir()
    old='GameCloudSave-V2.2.exe';(target/old).write_bytes(b'old fixture')
    (target/'Uninstall.exe').write_bytes(b'old uninstall fixture')
    (target/'user-note.txt').write_text('keep')
    (target/MARKER).write_text(json.dumps({'product':PRODUCT,'version':'2.2','exe':old,'files':[old,'Uninstall.exe'],'links':[],'registered':False}))
    payload=directory/'payload.zip'
    with zipfile.ZipFile(payload,'w') as zipped:
        zipped.writestr('GameCloudSave.exe',b'new fixture');zipped.writestr('Uninstall.exe',b'new uninstall fixture')
    installed=install(payload,target,version='2.3.1',registry=False)
    assert installed.name=='GameCloudSave.exe' and installed.is_file()
    assert not (target/old).exists() and (target/'user-note.txt').read_text()=='keep'
    assert json.loads((target/MARKER).read_text())['exe']=='GameCloudSave.exe'
    assert json.loads((target/MARKER).read_text())['version']=='2.3.1'
print('PASS: upgrade replaces the old main executable and preserves user files')
