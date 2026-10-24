"""Isolated first-toast work, background decoding and compositor-call regression.

--compare reads the previous source revision for a before/after measurement.
No actual game is opened and all fixture images live in a temporary directory.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json, subprocess, sys, tempfile, threading, time, types
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from services import ROOT
import achievement_overlay as overlay

app=QApplication([]);app.setQuitOnLastWindowClosed(False)

def spin(seconds):
    end=time.perf_counter()+seconds
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)

def measure(module,row,prepared):
    manager=module.AchievementOverlay();calls=[];created=[]
    toast_init=module.Toast.__init__;keep_above=module.Toast.keep_above
    def construct(self):created.append(time.perf_counter());toast_init(self)
    def above(self):calls.append(time.perf_counter());keep_above(self)
    try:
        with patch.object(module.Toast,'__init__',construct),patch.object(module.Toast,'keep_above',above):
            if prepared:
                manager.prepare();assert manager.toast is not None and not manager.toast.isVisible()
            created.clear()
            clock=time.monotonic()
            manager.current=(row,{},clock,True);manager.remaining=5;manager.last=clock
            start=time.perf_counter();manager.tick();first=(time.perf_counter()-start)*1000
            spin(.03)
            for i in range(1,31):
                with patch.object(module.time,'monotonic',return_value=clock+i*.15):manager.tick()
            assert manager.toast.isVisible()
            result=dict(first_unlock_gui_ms=round(first,3),native_windows_created_at_unlock=len(created),
                        z_order_calls_while_visible=len(calls))
            manager.toast.grab().save(str(output/('prepared-toast.png' if prepared else 'baseline-toast.png')))
            return result
    finally:manager.shutdown();app.processEvents()

output=ROOT/'build/achievement-overlay-review';output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='toast-latency-') as temp:
    path=Path(temp)/'icon.png'
    image=QImage(2048,1024,QImage.Format_ARGB32);image.fill(QColor('#54b68a'));assert image.save(str(path))
    row=dict(name='冒险纪念',description='首次探索新的世界',icon_path=str(path),game_id='fixture')
    report={}
    if '--compare' in sys.argv:
        old=types.ModuleType('achievement_overlay_baseline')
        source=subprocess.check_output(['git','show','96861f7:app/achievement_overlay.py'],cwd=ROOT).decode('utf-8')
        exec(compile(source,'achievement_overlay@96861f7','exec'),old.__dict__)
        report['before']=measure(old,row,False)
        assert report['before']['z_order_calls_while_visible']>=30

    # A slow decoder must never execute on or block the Qt application thread.
    gate=threading.Event();started=threading.Event();threads=[];beats=[]
    decode=overlay._decode_icon
    def slow_decode(*args):
        threads.append(threading.get_ident());started.set();assert gate.wait(3)
        return decode(*args)
    timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:beats.append(time.perf_counter()));timer.start()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with patch.object(overlay,'_decode_icon',side_effect=slow_decode):
                future=pool.submit(overlay.read_toast_icon,str(path));assert started.wait(1)
                spin(.10);assert len(beats)>=5,'Image decoding blocked the GUI'
                gate.set();prepared_icon=future.result(timeout=3)
        finally:gate.set();timer.stop()
    assert threads[0]!=threading.get_ident()
    assert (prepared_icon.width(),prepared_icon.height())==(120,60)
    hits=decode.cache_info().hits
    overlay.read_toast_icon(str(path));assert decode.cache_info().hits==hits+1
    # Replacing an icon at the same path invalidates the bounded decode cache.
    image=QImage(32,32,QImage.Format_ARGB32);image.fill(QColor('#bf6cdb'));assert image.save(str(path))
    replacement=overlay.read_toast_icon(str(path));assert replacement.pixelColor(0,0)==QColor('#bf6cdb')
    assert overlay.read_toast_icon(str(Path(temp)/'missing.png')).isNull()
    assert decode.cache_info().maxsize==64
    row['_toast_icon']=prepared_icon
    # No filesystem reader or native window construction is permitted at unlock.
    with patch.object(overlay,'QImageReader',side_effect=AssertionError('GUI decoded an image')):
        report['after']=measure(overlay,row,True)
    assert report['after']['native_windows_created_at_unlock']==0
    assert report['after']['z_order_calls_while_visible']==1

    # Foreground changes hide/resume without decoding or recreating the window.
    manager=overlay.AchievementOverlay();manager.prepare();toast=manager.toast
    try:
        target={'hwnd':1,'pid':1};clock=time.monotonic()
        manager.current=(row,target,clock,False);manager.remaining=5;manager.last=clock
        with patch.object(overlay,'valid_target',return_value=True),patch.object(overlay,'game_foreground',return_value=True),patch.object(overlay.Toast,'keep_above') as above:
            manager.tick();assert toast.isVisible() and above.call_count==1
            with patch.object(overlay,'game_foreground',return_value=False):manager.tick();assert not toast.isVisible()
            manager.tick();assert toast.isVisible() and manager.toast is toast and above.call_count==2
            manager.discard('fixture');assert not toast.isVisible() and manager.current is None
        manager.enqueue(row,{},True);manager.shutdown();spin(.02)
        assert manager.closed and not manager.queue and not manager.timer.isActive()
    finally:manager.shutdown()
    report.update(background_icon_decode=True,decoded_size=[120,60],heartbeat_during_slow_decode=len(beats),
                  bounded_icon_cache=64,foreground_resume=True,discard_shutdown=True)
    (output/'latency.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('PASS',json.dumps(report))
