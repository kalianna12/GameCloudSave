"""Install/run/uninstall the real EXEs under an isolated workspace test folder."""
from pathlib import Path
import os,json,subprocess,time,sys,zipfile,uuid,argparse
parser=argparse.ArgumentParser();parser.add_argument('--version',default='2.5.0');version=parser.parse_args().version
ROOT=Path(__file__).resolve().parents[1]
test=ROOT/'test-data'/('installer-v'+version+'-'+uuid.uuid4().hex[:8]);test.mkdir()
target=test/'installed';desktop=test/'desktop';menu=test/'menu';profile=test/'localappdata';profile.mkdir()
setup=ROOT/('dist/installers/GameCloudSave-Setup-V'+version+'.exe')
def run(args,env=None,timeout=120):
    started=time.monotonic()
    result=subprocess.run([str(arg) for arg in args],env=env,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,(args[0],result.returncode,result.stderr.decode('utf-8',errors='replace'))
    return round(time.monotonic()-started,3)
report={'version':version,'test_directory':str(test)}
report['install_seconds']=run([setup,'--silent','--target',target,'--desktop',desktop,'--start-menu',menu,'--no-register'])
marker=json.loads((target/'gamecloud-install.json').read_text(encoding='utf-8'));assert marker['version']==version
assert (desktop/'GameCloudSave.lnk').is_file() and (menu/'GameCloudSave.lnk').is_file()
exe=target/marker['exe'];environment=os.environ.copy();environment.pop('GAMECLOUD_DATA',None);environment['LOCALAPPDATA']=str(profile)
report['selftest_seconds']=run([exe,'--self-test',test/'selftest.txt'],env=environment)
assert (test/'selftest.txt').read_text(encoding='utf-8').startswith('PASS')
report['first_launch_seconds']=run([exe,'--show','setup','--quit-after','4500','--screenshot',test/'wizard.png','--startup-report',test/'startup.txt'],env=environment)
assert (test/'wizard.png').is_file();report['qml_startup_seconds']=float((test/'startup.txt').read_text())
data=profile/'GameCloudSave/data';assert data.exists(),'Installed app did not use external user data'
(data/'retain-test.txt').write_text('keep');(target/'user-note.txt').write_text('keep')
with zipfile.ZipFile(target/'source.zip') as zipped:
    names=zipped.namelist();assert 'app/themes.py' in names and 'installer/setup.py' in names and 'docs/theme.schema.json' in names
    assert zipped.read('ui/sounds/navigation.wav') == (ROOT/'ui/sounds/navigation.wav').read_bytes()
    assert zipped.read('app/input_feedback.py') == (ROOT/'app/input_feedback.py').read_bytes()
    for name in ('app/library_enrichment.py','app/catalog_match.py','app/time_display.py','app/game_watcher.py','ui/GameSettingsDialog.qml','ui/EnrichmentWindow.qml','ui/ControllerKeyboard.qml','ui/Main.qml','ui/ExperienceData.js','ui/WoodMaterials.js','ui/InlineImageBrowser.qml','ui/CinemaVideo.qml'):
        assert zipped.read(name)==(ROOT/name).read_bytes(),name+' is stale in the source archive'
    assert not any(name.startswith(('data/','test-data/','.venv/','dist/','build/')) or name.endswith('.dpapi') for name in names)
report['uninstall_seconds']=run([target/'Uninstall.exe','--silent','--report',test/'uninstall.json'])
assert json.loads((test/'uninstall.json').read_text(encoding='utf-8'))['passed']
deadline=time.monotonic()+15
while (target/'Uninstall.exe').exists() and time.monotonic()<deadline:time.sleep(.1)
assert not exe.exists() and not (target/'Uninstall.exe').exists()
assert not (desktop/'GameCloudSave.lnk').exists() and not (menu/'GameCloudSave.lnk').exists()
assert (data/'retain-test.txt').read_text()=='keep' and (target/'user-note.txt').read_text()=='keep'
report['passed']=True
(ROOT/('test-data/v'+version+'-installer-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: real installer, shortcuts, packaged self-test, first-run wizard, external data, source archive, self-uninstall and retained user files')
print(json.dumps(report,ensure_ascii=False))
