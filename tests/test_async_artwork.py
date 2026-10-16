"""Slow metadata cannot block catalog previews, unrelated work or a newer search."""
from pathlib import Path
import sys,tempfile,time,threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app=QApplication([])
def spin(ms=30):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def until(condition):
    end=time.monotonic()+3
    while not condition() and time.monotonic()<end:spin(10)
    assert condition()
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'async-art');store.settings['watch']=False;backend=Bridge(store)
    release=threading.Event();started=threading.Event();lock=threading.Lock();active=[0,0];ticks=[]
    timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
    def catalog(store,query,*args):
        return [{'id':query+str(i),'appid':query+str(i),'provider':'steam','name':query+str(i),'image':'https://images.example/'+str(i)} for i in range(4)]
    def lookup(store,game):
        if game['name'].startswith('old') and not game['name'].endswith('0'):
            with lock:
                active[0]+=1;active[1]=max(active);started.set()
            release.wait(3)
            with lock:active[0]-=1
        return {'background_url':'https://images.example/'+game['name']+'.jpg','release_date':'2020-01-01'}
    try:
        with patch('cover_sources.search',side_effect=catalog),patch('library_enrichment.cached_lookup',side_effect=lookup):
            backend.searchTargetArtwork('game','a','old','steam','cover',False)
            until(lambda:len(backend.coverResults)==4 and started.is_set())
            assert backend.artworkSearching and not backend.busy
            until(lambda:backend.coverResults[0]['background_state']=='available')
            assert any(row['background_state']=='loading' for row in backend.coverResults)
            until(lambda:active[1]>=2)
            backend.saveSettings({'animations':False});until(lambda:not backend.busy)
            assert store.settings['animations'] is False and backend.artworkSearching
            spin(60);assert len(ticks)>5,'Qt event loop blocked while metadata waited'
            backend.searchTargetArtwork('game','b','new','steam','background',False)
            until(lambda:not backend.artworkSearching)
            assert backend.coverSearchTarget=='game:b' and all(r['name'].startswith('new') for r in backend.coverResults)
            release.set();spin(120)
            assert all(r['name'].startswith('new') for r in backend.coverResults),'Stale search replaced newer results'
            backend.searchTargetArtwork('game','a','old','steam','cover',False);backend.clearCoverSearch();spin(80)
            assert not backend.artworkSearching and not backend.coverResults
            assert backend.status=='图片搜索已停止'
        with patch('cover_sources.search',side_effect=ValueError('Fixture unavailable')):
            backend.searchTargetArtwork('game','b','bad','steam','cover',False);until(lambda:not backend.artworkSearching)
            assert backend.status=='Fixture unavailable' and not backend.busy
    finally:
        release.set();timer.stop();backend.shutdownWatch();backend._artwork_pool.shutdown(wait=True);backend.pool.shutdown(wait=True)
print('PASS: immediate catalog preview, four parallel detail workers, partial metadata, responsive event loop, independent settings, newer-search priority, cancellation and failure cleanup')
