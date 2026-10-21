"""Home spatial navigation, right-aligned tools, stick tilt and A/Menu actions; isolated."""
from pathlib import Path
import sys,tempfile,time,statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch,Mapper,Pad
from PySide6.QtCore import QObject,QUrl,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Slot,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=50):
    until=time.perf_counter()+ms/1000
    while time.perf_counter()<until:app.processEvents();time.sleep(.002)
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
class SafeBridge(Bridge):
    calls=[]
    @Slot(str)
    def launch(self,ident):self.calls.append(ident)
    @Slot(QObject)
    def beginLaunchPresentation(self,window):pass

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'spatial-home');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,animations=True,theme='light')
    store.games=[{'id':str(i),'name':f'Game {i:02}','cover':'','tags':['Adventure'],'category':'Action','last_played':'2026-10-10T10:00:00Z','series':'Series'} for i in range(30)]
    store.settings['navigation_volume']=0
    backend=SafeBridge(store)
    from input_feedback import InputFeedback
    backend.input_feedback=InputFeedback(app,backend,ROOT)
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.resize(1920,1050);root.requestActivate();spin(250)
    home=root.findChild(QObject,'libraryHome');view=root.findChild(QObject,'libraryHomeList')
    records=[dict(game,coverUrl='',coverHighUrl='') for game in backend.games]
    sections=[{'id':'recent','kind':'recent','title':'Recent','items':records},
              {'id':'store:test','kind':'store','title':'New','items':[dict(game,category='new',platformLabel='Steam') for game in records]},
              {'id':'games','kind':'games','title':'Collection','items':records}]
    home.setProperty('sections',sections);spin(150)
    def shelf():return invoke(home,'currentShelf')
    def pad(command,delay=45):dispatch(app,root,backend,command);spin(delay)
    try:
        assert backend.input_feedback.audio.ready and len(backend.input_feedback.audio.sounds)==36
        # Actual outer content edges, rather than the centre of a stretched grid cell.
        full=root.findChild(QObject,'fullscreenControl');installed=root.findChild(QObject,'installedFilter')
        for width in (1440,1920,2560):
            root.resize(width,1050);spin(70)
            right=full.mapToScene(QPointF(full.width(),0)).x()
            ancestors=[];parent=full
            while parent is not None:
                ancestors.append((parent.metaObject().className(),round(parent.x()),round(parent.width())));parent=parent.parentItem()
            assert abs(right-home.mapToScene(QPointF(home.width(),0)).x())<2,(width,right,home.mapToScene(QPointF(home.width(),0)).x(),ancestors)
            assert abs(installed.mapToScene(QPointF()).x()-home.mapToScene(QPointF()).x())<4
        root.resize(1920,1050);spin(80);invoke(home,'focusFirst');backend.setControllerMode(True)
        for _ in range(4):pad('right',10)
        x=invoke(shelf(),'selectionSceneX');pad('down',180)
        new=shelf();assert home.property('focusedSection')==1
        assert abs(invoke(new,'selectionSceneX')-x)<(new.property('tileWidth')+new.property('cardGap'))/2+1
        # Leave a deliberately wrong old position, then enter at a different X.
        for _ in range(6):pad('right',10)
        pad('up',180)
        for _ in range(3):pad('left',20)
        x=invoke(shelf(),'selectionSceneX');pad('down',180)
        new=shelf();assert abs(invoke(new,'selectionSceneX')-x)<(new.property('tileWidth')+new.property('cardGap'))/2+1,(x,invoke(new,'selectionSceneX'))
        # Tilt follows both axes only on the selected cover and resets by mode/focus.
        backend.setControllerTilt(.8,-.6);spin(80)
        effects=[item for item in walk(root.contentItem()) if item.objectName()=='coverEffects' and item.isVisible() and item.property('controllerFocused')]
        assert len(effects)==1,len(effects)
        effect=effects[0];assert effect.property('yaw')>10 and effect.property('pitch')<0
        backend.setControllerMode(False);spin(40);assert effect.property('yaw')==0 and backend.controllerTilt==[0.,0.]
        backend.setControllerMode(True);backend.setControllerTilt(.7,.6);store.settings['controller_tilt']=False;backend.settingsChanged.emit();spin(400)
        assert effect.property('yaw')==0
        store.settings['controller_tilt']=True;backend.settingsChanged.emit();backend.setControllerTilt(0.,0.)
        output=ROOT/'test-data/home-input-review';output.mkdir(exist_ok=True);root.grabWindow().save(str(output/'home-aligned-light.png'))
        # Every game layout uses A to launch and Menu to open the options dialog.
        menu=root.findChild(QObject,'controllerGameMenu');transition=root.findChild(QObject,'launchTransition')
        for design in ('classic','shelf','cinema','atlas'):
            store.settings['library_design']=design;backend.settingsChanged.emit();spin(180)
            if design=='classic':invoke(home,'focusFirst')
            else:invoke(root,'focusFirstContent')
            backend.setControllerMode(True);pad('menu',100)
            assert menu.property('visible') and not transition.property('running'),design
            QMetaObject.invokeMethod(menu,'close');spin(220)
            invoke(root,'focusFirstContent');pad('history',60)
            history=root.findChild(QObject,'historyDialog');assert history.property('visible') and not menu.property('visible'),(design,root.activeFocusItem().objectName(),home.property('focusedSection'),invoke(home,'selectedGame'),messages[-5:])
            QMetaObject.invokeMethod(history,'close');spin(220)
            while backend.busy:spin(20)
            invoke(root,'focusFirstContent');pad('activate',160)
            assert transition.property('running') and not menu.property('visible'),(design,backend.calls)
            invoke(transition,'cancel');spin(80)
        # Time navigation with warmed delegates; no sound file load or image I/O.
        store.settings['library_design']='classic';backend.settingsChanged.emit();spin(100);invoke(home,'focusFirst')
        timings=[]
        for _ in range(12):
            begin=time.perf_counter();dispatch(app,root,backend,'right');timings.append((time.perf_counter()-begin)*1000);spin(20)
        assert statistics.median(timings)<25,timings
        pad_state=Pad();mapper=Mapper();pad_state.buttons=0x10
        assert mapper.read(pad_state,1)==['menu']
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Cannot assign','Unable to assign','Binding loop','recursive rearrange'))]
        assert not errors,errors[:12]
        print('PASS: current-X home navigation, outer-edge toolbar alignment, stick tilt/reset/disable, A/Menu/Y across four layouts, 36 preloaded sound events; median dispatch %.2fms; no real game launch'%statistics.median(timings))
    finally:
        backend.input_feedback.release_cursor();backend.input_feedback.audio.shutdown();app.removeEventFilter(backend.input_feedback)
        backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
