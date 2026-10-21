"""Measure rapid input and stick binding fan-out in an isolated populated library."""
from pathlib import Path
import argparse,json,math,statistics,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from input_feedback import InputFeedback
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QPointF,Property
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
QQuickStyle.setStyle('Material');app=QApplication([])
def spin(ms):
    until=time.perf_counter()+ms/1000
    while time.perf_counter()<until:app.processEvents();time.sleep(.002)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'navigation-latency');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0)
    store.games=[{'id':str(i),'name':f'Game {i:03}','cover':'','category':f'Category {i%12}','tags':[f'Tag {i%8}'],'series':f'Series {i%10}','last_played':str(400-i)} for i in range(240)]
    backend=Bridge(store);feedback=InputFeedback(app,backend,ROOT,audio_muted=True);backend.input_feedback=feedback
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects();window=engine.rootObjects()[0];window.resize(1920,1080);window.requestActivate();spin(400)
    frames=[];window.frameSwapped.connect(lambda:frames.append(time.perf_counter()))
    try:
        backend.setControllerMode(True)
        home=window.findChild(QObject,'libraryHome')
        from PySide6.QtCore import QMetaObject,Q_RETURN_ARG
        QMetaObject.invokeMethod(home,'focusFirst',Q_RETURN_ARG('QVariant'));spin(150)
        effects=[i for i in walk(window.contentItem()) if i.objectName()=='coverEffects']
        updates=[]
        for effect in effects:effect.stickChanged.connect(lambda:updates.append(1))
        for i in range(90):
            backend.setControllerTilt(math.sin(i*.14)*.9,math.cos(i*.14)*.9);spin(8)
        reads=len(updates)
        backend.setControllerTilt(0,0);spin(60)
        times=[];backend._popup_scans=0
        for i in range(36):
            start=time.perf_counter();dispatch(app,window,backend,'right' if i%12<6 else 'left')
            times.append((time.perf_counter()-start)*1000);spin(12)
        report={'effects':len(effects),'stick_samples':90,'stick_property_reads':reads,'navigation_tree_scans':backend._popup_scans,
            'dispatch_median_ms':round(statistics.median(times),2),'dispatch_p95_ms':round(sorted(times)[int(len(times)*.95)],2)}
        output=ROOT/'test-data/navigation-latency';output.mkdir(exist_ok=True)
        (output/('before.json' if args.baseline else 'after.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
        if not args.baseline:
            assert reads<=180,report
            assert backend._popup_scans<=5,report
            assert statistics.median(times)<12,report
    finally:
        feedback.audio.shutdown();feedback.release_cursor();app.removeEventFilter(feedback);backend.shutdownWatch();backend.pool.shutdown(wait=True)
        import shiboken6;shiboken6.delete(engine)
