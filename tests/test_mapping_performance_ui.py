"""Frame-paced motion, stable delegates, cached reopen and independent input capture; no injection."""
from pathlib import Path
import sys,tempfile,time,math,os,json,statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from qml_bootstrap import install_incubator
from PySide6.QtCore import QObject,QUrl,QMetaObject,qInstallMessageHandler,QEventLoop,QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms):
    loop=QEventLoop();QTimer.singleShot(int(ms),loop.quit);loop.exec()
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
class Motion:
    def sample(self,*args):
        now=time.perf_counter();return {'buttons':['A'] if int(now/.03)%2 else [],'LS':[math.sin(now*5)*.9,math.cos(now*5)*.9],'RS':[0,0]},0
    def foreground(self):return 1,os.getpid()
    def held(self,*args):return False
    def key(self,*args):raise AssertionError('Performance fixture never enables output')
    def move(self,*args):raise AssertionError('No injection')
    def wheel(self,*args):raise AssertionError('No injection')
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'mapping-performance');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    bridge=Bridge(store);bridge.mapping._transport_factory=Motion
    if os.environ.get('MAPPING_PREVIEW_MS'):bridge.mapping._preview_timer.setInterval(int(os.environ['MAPPING_PREVIEW_MS']))
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',bridge);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    root=engine.rootObjects()[0];root.requestActivate();window=root.findChild(QObject,'inputMappingWindow');result={}
    try:
        spin(1800);assert window.property('editorReady'),'Idle preload must complete without opening a hidden window';frames=[];window.frameSwapped.connect(lambda:frames.append(time.perf_counter()))
        started=time.perf_counter();QMetaObject.invokeMethod(window,'openMapping')
        while not frames and time.perf_counter()-started<3:spin(2)
        assert frames;result['first_open_frame_ms']=round((frames[-1]-started)*1000,1);spin(100)
        def keys():return {item.property('token'):shiboken6.getCppPointer(item)[0] for item in walk(window.contentItem()) if (item.property('token') or '').startswith('P:')}
        original=keys();assert len(original)>=16
        pad=window.findChild(QObject,'mappingPadModel');deadline=time.perf_counter()+2
        while not pad.property('artworkReady') and time.perf_counter()<deadline:spin(2)
        assert pad.property('artworkReady'),messages
        switches=[]
        for model in ('ps','joycon','xbox','ps','xbox'):
            before=len(frames);started=time.perf_counter();bridge.mapping.setModel(model)
            while len(frames)==before and time.perf_counter()-started<2:spin(2)
            assert len(frames)>before,(model,messages)
            switches.append((frames[-1]-started)*1000);assert keys()==original,'Switching must reposition keys without destroying them'
        result['model_paint_ms']=[round(v,1) for v in switches]
        changes=[];state_updates=[];profile_updates=[];ages=[]
        bridge.mapping.previewChanged.connect(lambda:(changes.append(time.perf_counter()),ages.append(bridge.mapping._last_capture_age)))
        bridge.mapping.stateChanged.connect(lambda:state_updates.append(1));bridge.mapping.changed.connect(lambda:profile_updates.append(1))
        before=bridge.mapping._capture_count;before_frames=len(frames);started=time.perf_counter();cpu=time.process_time();spin(1000);elapsed=time.perf_counter()-started
        result['capture_hz']=round((bridge.mapping._capture_count-before)/elapsed,1);result['preview_hz']=round(len(changes)/elapsed,1)
        result['window_frame_hz']=round((len(frames)-before_frames)/elapsed,1)
        result['preview_age_p95_ms']=round(sorted(ages)[int(len(ages)*.95)]*1000,1)
        result['motion_cpu_seconds']=round(time.process_time()-cpu,3)
        assert result['capture_hz']>100 and result['preview_hz']>30,result
        assert max(switches)<500,result
        assert not profile_updates and len(state_updates)<5,(profile_updates,state_updates)
        window.close();spin(80);frames.clear();started=time.perf_counter();QMetaObject.invokeMethod(window,'openMapping')
        while not frames and time.perf_counter()-started<2:spin(2)
        assert frames;result['cached_reopen_frame_ms']=round((frames[-1]-started)*1000,1);assert keys()==original
        errors=[m for m in messages if any(w in m for w in ('TypeError','ReferenceError','Binding loop','Cannot assign'))];assert not errors,errors
    finally:
        window.close();spin(50);bridge.shutdownWatch();bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
folder=ROOT/'test-data/input-mapping';folder.mkdir(exist_ok=True);(folder/'performance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS: '+json.dumps(result))
