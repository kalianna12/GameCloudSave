from pathlib import Path
import gc
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from PySide6.QtCore import QCoreApplication
from services import Store, ROOT
from main import Bridge
app = QCoreApplication([])
with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as temporary:
    store = Store(Path(temporary), 'watch-test')
    ident = str(uuid.uuid4())
    store.games = [{'id':ident,'name':'监听测试','cover':'','installed':True}]
    save = Path(temporary) / 'save'
    save.mkdir()
    (save / 'save.json').write_text('{}')
    store.save_game(ident, {'save_dir':str(save), 'exe':str(Path(temporary) / 'FixtureGame.exe')})
    store.save_settings({'watch':True})
    bridge = Bridge(store)
    notifications=[]
    bridge.notificationReady.connect(lambda title,message,error:notifications.append((title,message,error)))
    bridge.timer.stop()
    def poll(processes):
        with patch('psutil.process_iter', return_value=processes):
            bridge.poll()
            deadline = time.monotonic() + 5
            while (bridge.busy or bridge._watch_pending) and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            assert not bridge.busy, 'Worker did not complete'
    poll([SimpleNamespace(info={'name':'FixtureGame.exe'})])
    poll([SimpleNamespace(info={'name':'FixtureGame.exe'})])
    poll([])
    rows = store.history(ident)
    assert [r['event'] for r in rows] == ['game_stop','game_start']
    assert all(Path(row['archive_path']).exists() for row in rows)
    assert len(notifications)==4 and sum('完成' in title for title,_,_ in notifications)==2
    assert all(error for title,_,error in notifications if '完成' in title), 'Offline uploads should report local retention'
    assert store.games[0]['play_count']==1
    store.settings['tray_notifications']=False
    poll([SimpleNamespace(info={'name':'FixtureGame.exe'})]);assert len(notifications)==4
    bridge.pool.shutdown(wait=True)
    gc.collect()
print('PASS: background watcher start/stop, no duplicate while running, offline local retention')
