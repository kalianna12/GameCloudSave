"""Real one-second timer, passive sync, pending windows and live metadata changes.

All writes target disposable fixtures; no real game/library is opened.
"""
from pathlib import Path
import json, os, struct, sys, tempfile, threading, time, zlib
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtWidgets import QApplication
from achievements import Achievements
from achievement_monitor import check
from services import ROOT, Store

app = QApplication([])
def until(condition, timeout=5):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if condition(): return
        time.sleep(.004)
    assert condition(), 'Timed out'

with tempfile.TemporaryDirectory(dir=ROOT/'test-data', prefix='achievement-realtime-') as temp:
    root=Path(temp); store=Store(root/'data', 'isolated')
    store.games=[dict(id='game', name='Isolated', platform='local')]
    store.local={}; manager=Achievements(store); events=[]; gate=threading.Event()
    manager.overlay.enqueue=lambda row,target,preview=False: events.append(row)
    source=root/'achievements.json'
    source.write_text('{"FIRST":{"earned":false,"progress":0}}', encoding='utf-8')
    report={}
    try:
        manager.openFor('game'); until(lambda:not manager.state['busy'])
        manager.save('game',dict(source=str(source))); until(lambda:not manager.state['busy'])
        # No begin/attach/poll call: an external game writes a known record.
        start=time.monotonic(); source.write_text('{"FIRST":{"earned":true,"progress":1}}', encoding='utf-8')
        until(lambda:manager.state['unlocked']==1 and manager.summary('game').get('unlocked')==1)
        report['passive_timer_ms']=round((time.monotonic()-start)*1000)
        assert not events
        until(lambda:not manager.polling)
        with patch('achievement_monitor.parse_state',side_effect=AssertionError('Unchanged files must not be parsed')) as parse, patch('achievement_monitor.discover',side_effect=AssertionError('Idle library scan')):
            manager.poll(); until(lambda:not manager.polling)
            assert not parse.called
        # Pending launcher/window detection must not suspend record synchronization.
        manager.begin('game').result(timeout=3)
        source.write_text('{"FIRST":{"earned":true},"SECOND":{"earned":true}}',encoding='utf-8')
        until(lambda:manager.state['unlocked']==2)
        assert not events and not manager.sessions['game']['target']
        manager.attach('game',os.getpid(),0)
        # With metadata search blocked, the timer still updates the actual page
        # and catalog rather than dropping the only dirty-file notification.
        with patch('cover_sources.search', side_effect=lambda *args:(gate.wait(8),[dict(appid='42',name='Fixture')])[1]):
            manager.search('game','Fixture')
            source.write_text('{"FIRST":{"earned":true},"SECOND":{"earned":true},"THIRD":{"earned":true}}',encoding='utf-8')
            until(lambda:manager.state['unlocked']==3 and manager.summary('game').get('unlocked')==3)
            assert manager.state['busy'] and [r['id'] for r in events]==['THIRD']
            gate.set(); until(lambda:not manager.state['busy'])
        assert manager.state['candidates'][0]['appid']=='42'
        # Atomic replacement and partial writes preserve history and retry.
        source.write_text('{',encoding='utf-8')
        until(lambda:'自动重试' in manager.state.get('monitor_status',''))
        assert manager.state['unlocked']==3
        replacement=root/'complete.tmp';replacement.write_text('{"FOURTH":{"earned":true}}',encoding='utf-8');replacement.replace(source)
        until(lambda:manager.state['unlocked']==4)
        assert [r['id'] for r in events]==['THIRD','FOURTH']
        assert manager.state['candidates'][0]['appid']=='42'
        # Late CRC mapping must reparse the same unchanged SSE file.
        sse=root/'stats.bin';sse.write_bytes(struct.pack('<I',1)+struct.pack('<IIIIii',zlib.crc32(b'LATE'),0,1700000000,0,0,1))
        def late_schema():
            config=manager.repository.config('crc');config.update(source=str(sse),schema=[])
            session=dict(ident='crc',game=dict(id='crc',name='CRC'),local={},target={'pid':os.getpid(),'hwnd':0},primed=True,created=time.monotonic(),signature=None,discovery=0)
            check(manager.repository,session)
            assert not manager.repository.record('crc',config)['unlocks']
            config['schema']=[dict(id='LATE',name='Late',icon='',hidden=False)]
            _,rows,_=check(manager.repository,session)
            assert set(manager.repository.record('crc',config)['unlocks'])=={'LATE'}
            assert not rows, 'Late metadata must not replay the initial CRC baseline'
            # Definitions still absent at launch: retain OLD as baseline, but
            # notify NEW if the game wrote it while metadata was downloading.
            config=manager.repository.config('late-launch');config.update(source=str(sse),schema=[])
            manager.repository.setup(dict(id='late-launch',name='Late launch',platform='local'),{})
            sse.write_bytes(struct.pack('<I',2)+struct.pack('<IIIIii',zlib.crc32(b'LATE'),0,1700000000,0,0,1)+struct.pack('<IIIIii',zlib.crc32(b'NEW'),0,1700000001,0,0,1))
            config['schema']=[dict(id=k,name=k,icon='',hidden=False) for k in ('LATE','NEW')]
            session=dict(session,ident='late-launch',game=dict(id='late-launch',name='Launch'),signature=None)
            _,rows,_=check(manager.repository,session)
            assert [row['id'] for row,target in rows]==['NEW']
        manager.pool.submit(late_schema).result(timeout=3)
        # A per-tick unexpected exception releases polling, allowing recovery.
        until(lambda:not manager.polling)
        with patch.object(manager.repository,'load',side_effect=OSError('fixture transient')):
            manager.poll(); until(lambda:not manager.polling)
        source.write_text('{"FIFTH":{"earned":true}}',encoding='utf-8')
        until(lambda:manager.state['unlocked']==5)
        manager.save('game',dict(enabled=False));until(lambda:not manager.state['busy'])
        assert manager.state['monitor_status']=='监听已关闭'
        source.write_text('{"SIXTH":{"earned":true}}',encoding='utf-8')
        until(lambda:not manager.polling);manager.poll();until(lambda:not manager.polling)
        assert manager.state['unlocked']==5
        report.update(pending_window=True,busy_page_live=True,atomic_retry=True,late_crc=True,no_duplicate_toasts=True,guard_recovers=True,disabled=True)
        output=ROOT/'build/achievement-realtime-review';output.mkdir(exist_ok=True)
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('PASS',json.dumps(report))
    finally:
        gate.set();manager.shutdown()
        for pool in (manager.pool,manager.network,manager.icons,manager.batch_pool):pool.shutdown(wait=True)
