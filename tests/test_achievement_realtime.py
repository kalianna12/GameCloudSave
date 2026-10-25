"""File-driven counters, atomic replacements and no in-game notification runtime."""
from pathlib import Path
import json,sys,tempfile,time,threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtWidgets import QApplication
from achievements import Achievements
from services import Store,ROOT
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
def spin(seconds=.04):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def until(condition,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.01)
    assert condition()
with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='quiet-achievements-') as temp:
    root=Path(temp);store=Store(root/'data','isolated');store.games=[dict(id='a',name='Fixture',platform='local')]
    source=root/'achievements.json';source.write_text('{"A":{"earned":false},"B":{"earned":false}}')
    manager=Achievements(store);manager.cacheAll=lambda *args:None;gate=threading.Event()
    try:
        def prepare():
            config=manager.repository.config('a');config.update(source=str(source),schema=[dict(id=k,name=k,description='',icon='',hidden=False) for k in ('A','B')]);manager.repository.save();manager.publish()
        manager.pool.submit(prepare).result();until(lambda:str(source) in manager.watcher.files())
        assert not hasattr(manager,'overlay') and not hasattr(manager,'begin') and not hasattr(manager,'sessions')
        assert 'achievement_overlay' not in sys.modules and not (ROOT/'app/achievement_overlay.py').exists()
        initial=len(app.topLevelWindows());manager.poll();until(lambda:not manager.polling)
        start=time.monotonic();source.write_text('{"A":{"earned":true},"B":{"earned":false}}')
        until(lambda:manager.summary('a').get('unlocked')==1);latency=round((time.monotonic()-start)*1000)
        assert latency<2000 and len(app.topLevelWindows())==initial
        # Monitoring remains independent of an in-flight metadata search.
        with patch('cover_sources.search',side_effect=lambda *a:(gate.wait(3),[])[1]):
            manager.search('a','Fixture');until(lambda:manager.state['busy'])
            replacement=root/'new.json';replacement.write_text('{"A":{"earned":true},"B":{"earned":true}}');replacement.replace(source)
            until(lambda:manager.summary('a').get('unlocked')==2)
            assert manager.state['busy'];gate.set();until(lambda:not manager.state['busy'])
        # Truncated writes are retried, preserving the last valid counters.
        source.write_text('{');manager.poll();until(lambda:not manager.polling)
        assert manager.summary('a')['unlocked']==2
        source.write_text('{"A":{"earned":true},"B":{"earned":true}}');until(lambda:str(source) in manager.watcher.files())
        manager.setEnabled(False);assert not manager.timer.isActive() and not manager.watcher.files() and not manager.watcher.directories()
        manager.setEnabled(True);until(lambda:str(source) in manager.watcher.files())
        manager.controls.submit(lambda:None).result();spin()
        assert len(app.topLevelWindows())==initial
        manager.shutdown();manager.receivePoll({'view':None});assert manager.closed and not manager.timer.isActive()
        print('PASS: file watcher -> counters',latency,'ms; busy search, atomic replace, partial writes, master switch; zero notification windows')
    finally:
        gate.set();manager.shutdown()
        for pool in (manager.pool,manager.network,manager.icons,manager.batch_pool,manager.controls):pool.shutdown(wait=True)
