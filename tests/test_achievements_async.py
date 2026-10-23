"""Out-of-order metadata, failed matches, monitoring during network I/O and first files."""
from pathlib import Path
import json
import os
import sys
import tempfile
import threading
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtWidgets import QApplication
from services import ROOT, Store
from achievements import Achievements

app=QApplication([])

def spin(seconds=.05):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.003)

def until(condition,seconds=5):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if condition():return
        spin(.02)
    assert condition(),'Timed out'

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievements-async-') as temp:
    root=Path(temp);store=Store(root/'data','isolated')
    store.games=[{'id':'a','name':'A','platform':'local'},{'id':'b','name':'B','platform':'local'}]
    store.local={};manager=Achievements(store);gate=threading.Event();events=[]
    manager.overlay.enqueue=lambda row,target,preview=False:events.append(row)
    def idle():return not manager.state['busy']
    source=root/'game/achievements.json';source.parent.mkdir()
    source.write_text('{"OLD":{"earned":true}}',encoding='utf-8')
    try:
        manager.openFor('a');until(idle);manager.save('a',{'source':str(source)});until(idle)
        # Late responses persist for their own game but cannot replace another page.
        schema=[{'id':key,'name':key,'description':'Explore','hidden':False,'icon':'','max':0} for key in ('FIRST','NEXT')]
        with patch('achievements.steam_schema',side_effect=lambda _: (gate.wait(3),schema)[1]):
            manager.match('a','42');manager.openFor('b');until(idle);gate.set()
            until(lambda:not manager._fetching);spin(.1)
        assert manager.state['ident']=='b' and not manager.state['rows']
        manager.openFor('a');until(idle);assert manager.state['appid']=='42'
        # Explicitly select source after changing identity (separate history namespace).
        manager.save('a',{'source':str(source)});until(idle)
        before=manager.state['total']
        with patch('achievements.steam_schema',side_effect=OSError('offline')),patch('achievement_sources.hunters_schema',side_effect=OSError('offline')),patch('achievement_web.fetch_page',side_effect=OSError('offline')):
            manager.match('a','99');until(lambda:'offline' in manager.state.get('message',''))
        assert manager.state['appid']=='42' and manager.state['total']==before
        # Invalid source doesn't partially apply its accompanying toggle.
        manager.save('a',{'enabled':False,'source':str(root/'invalid.txt')});until(idle)
        assert manager.repository.configs['a']['enabled'] is True
        # File does not yet exist. Reading a baseline now must allow FIRST to pop
        # when the game creates it, rather than silently import the first unlock.
        source=root/'new/achievements.json'
        manager.save('a',{'source':str(source)});until(idle)
        baseline=manager.begin('a');baseline.result(timeout=3)
        manager.sessions['a']['target']={'pid':os.getpid(),'hwnd':0}
        source.parent.mkdir();source.write_text('{"FIRST":{"earned":true}}',encoding='utf-8')
        # Searching online must not block the separate file-monitor worker.
        gate.clear()
        with patch('cover_sources.search',side_effect=lambda *args:(gate.wait(3),[])[1]):
            manager.search('a','A');manager.poll()
            until(lambda:events)
            assert events[0]['id']=='FIRST' and manager.state['busy']
            gate.set();until(idle)
        # Corrupted/part-written progress is retried without losing or replaying.
        source.write_text('{',encoding='utf-8');manager.poll();spin(.2)
        source.write_text('{"FIRST":{"earned":true},"NEXT":{"earned":true}}',encoding='utf-8')
        manager.poll();until(lambda:len(events)==2)
        manager.poll();spin(.1);assert len(events)==2
        manager.openFor('a');until(idle);assert manager.state['unlocked']==2
        # The AI switch only affects catalog identification, not local unlocks.
        with patch('cover_sources.search',return_value=[]) as search:
            manager.search('a','A',True);until(idle);assert search.call_args.args[3] is True
        # An existing RUNE Count=0 container must emit the first real unlock.
        rune=root/'rune/achievements.ini';rune.parent.mkdir();rune.write_text('[SteamAchievements]\nCount=0',encoding='utf-8')
        manager.save('a',{'source':str(rune)});until(idle)
        baseline=manager.begin('a');baseline.result(timeout=3);manager.sessions['a']['target']={'pid':os.getpid(),'hwnd':0}
        rune.write_text('[FIRST]\nAchieved=1\nUnlockTime=1700000000',encoding='utf-8');manager.poll();until(lambda:len(events)==3)
        assert events[-1]['id']=='FIRST'
        print('PASS: late metadata isolation, offline cache, transactional settings, first-file unlock, live monitoring during search, partial-write retry')
    finally:
        gate.set();manager.shutdown();manager.pool.shutdown(wait=True);manager.network.shutdown(wait=True);manager.icons.shutdown(wait=True)
