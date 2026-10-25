"""Real queued filesystem refresh, using only disposable game files."""
from pathlib import Path
import sys,tempfile,time,uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtWidgets import QApplication

app=QApplication([])
def wait(predicate):
    until=time.monotonic()+5
    while not predicate() and time.monotonic()<until:app.processEvents();time.sleep(.005)
    assert predicate(),'Filesystem refresh timed out'
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    root=Path(folder);store=Store(root/'data','fixture');store.settings.update(playnite='',library='',watch=False,recommendations_enabled=False)
    ident=str(uuid.uuid4());game=root/'Game';game.mkdir();exe=game/'Game.exe';exe.write_bytes(b'fixture')
    saves=root/'saves';saves.mkdir();(saves/'slot.sav').write_text('keep')
    store.games=[{'id':ident,'name':'Game','cover':'','import_source':'playnite'}]
    store.local[ident]={'install_dir':str(game),'save_dir':str(saves),'installed':True,'launch_mode':'playnite'}
    raw={'_id':{'$guid':ident},'InstallDirectory':str(game),'IsInstalled':False,'GameActions':[{'IsPlayAction':True,'Type':0,'Path':'{InstallDir}/Game.exe'}]}
    with patch.object(store,'read_playnite',return_value=[raw]) as read:
        bridge=Bridge(store)
        try:
            bridge.refreshInstallations();wait(lambda:not bridge._installation_pending)
            assert store.local[ident]['launch_mode']=='direct' and bridge.games[0]['installed']
            exe.unlink();game.rmdir();bridge._installation_last=0;bridge.refreshInstallations();wait(lambda:not bridge._installation_pending)
            assert not bridge.games[0]['installed'] and (saves/'slot.sav').read_text()=='keep'
            game.mkdir();exe.write_bytes(b'fixture');bridge._installation_last=0;bridge.refreshInstallations();wait(lambda:not bridge._installation_pending)
            assert bridge.games[0]['installed'] and read.call_count==1
            before=dict(store.local[ident]);store.save_game(ident,{'arguments':'--edited'})
            bridge.receiveInstallations({ident:{'before':before,'values':{'arguments':'--stale','installed':False}}})
            assert store.local[ident]['arguments']=='--edited' and bridge.games[0]['installed']
        finally:bridge.shutdownWatch();bridge.pool.shutdown(wait=True);bridge._installation_pool.shutdown(wait=True)
print('PASS queued installation refresh, direct Playnite action migration, removed/reinstalled game, save retention and manual edit race')
