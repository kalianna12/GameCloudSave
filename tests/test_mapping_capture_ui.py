"""Owned Quick window: capture must bind input without operating the editor."""
from pathlib import Path
import os,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from qml_bootstrap import install_incubator
from PySide6.QtCore import QObject,QEvent,QUrl,QPoint,QPointF,Qt,QMetaObject,qInstallMessageHandler
from PySide6.QtGui import QWheelEvent,QKeyEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=80):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)
def point(item):
    p=item.mapToScene(QPointF(item.width()/2,item.height()/2));return QPoint(round(p.x()),round(p.y()))
class Preview:
    def sample(self,*args):return {'buttons':[],'LS':[0,0],'RS':[0,0]},0
    def foreground(self):return 1,os.getpid()
    def held(self,*args):return False
    def key(self,*args):raise AssertionError('No injection permitted')
    move=key;wheel=key

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'mapping-capture');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    backend=Bridge(store);c=backend.mapping;c._transport_factory=Preview
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0]
    window=root.findChild(QObject,'inputMappingWindow');QMetaObject.invokeMethod(window,'openMapping')
    end=time.perf_counter()+5
    while not window.property('editorReady') and time.perf_counter()<end:spin(20)
    assert window.property('editorReady'),messages
    spin(150)
    try:
        # The mode's extra controls must never resize the model. Both use the
        # previously larger panel at normal and small window sizes, for all skins.
        for width,height in ((1360,980),(1040,700)):
            window.resize(width,height);spin(100)
            for skin in ('xbox','ps','joycon'):
                c.setModel(skin);sizes=[]
                for mode in ('pad_to_keys','keys_to_pad','pad_to_keys'):
                    c.setMode(mode);spin(100)
                    art=window.findChild(QObject,'mappingPadArtwork');panel=window.findChild(QObject,'mappingControllerPanel')
                    sizes.append((round(art.width(),2),round(art.height(),2),round(panel.height(),2)))
                assert sizes[0]==sizes[1]==sizes[2],(width,skin,sizes)
                assert sizes[0][2]>=544,sizes
        window.resize(1360,980);c.setModel('xbox');c.setMode('pad_to_keys');spin(100)
        scroll=window.findChild(QObject,'mappingScroll');flick=scroll.property('contentItem')
        record=window.findChild(QObject,'mappingRecord');cancel=window.findChild(QObject,'mappingCaptureCancel')
        activations=[];cancel.clicked.connect(lambda:activations.append('cancel'))
        def arm():
            c.selectTarget('A');flick.setProperty('contentY',max(0,flick.property('contentY')+point(record).y()-500));spin(30)
            QTest.mouseClick(window,Qt.LeftButton,pos=point(record));spin(60)
            assert c.state['recording'] and window.findChild(QObject,'mappingCapturePrompt').property('visible'),(point(record),c.state,messages[:5])
        def wheel(delta):
            p=QPointF(500,400)
            QTest.mouseMove(window,p.toPoint());spin(10)
            app.sendEvent(window,QWheelEvent(p,QPointF(window.mapToGlobal(p.toPoint())),QPoint(),QPoint(0,delta),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False))
        def unchanged(y):
            assert window.isVisible() and not root.property('fullScreenMode')
            assert c.target=='A' and flick.property('contentY')==y
            assert not activations,activations
        for key,vk in ((Qt.Key_Return,13),(Qt.Key_Enter,13),(Qt.Key_Up,38),(Qt.Key_Down,40),(Qt.Key_Left,37),(Qt.Key_Right,39),(Qt.Key_Tab,9),(Qt.Key_Escape,27),(Qt.Key_Space,32),(Qt.Key_F11,122)):
            arm();y=flick.property('contentY');QTest.keyPress(window,key);spin(20)
            for _ in range(3):app.sendEvent(window,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier,'',True))
            QTest.keyRelease(window,key);spin(160)
            assert not c.state['recording'] and c.currentChord==['K:'+str(vk)],(key,c.currentChord)
            unchanged(y)
        for delta,token in ((120,'M:wheelup'),(-120,'M:wheeldown')):
            arm();y=flick.property('contentY');wheel(delta);spin(20)
            assert c.currentChord==[token] and not c.state['recording']
            for _ in range(4):wheel(delta);spin(20)
            unchanged(y);spin(220)
        arm();y=flick.property('contentY');QTest.keyPress(window,Qt.Key_Control);wheel(120);spin(40)
        assert c.state['recording']
        QTest.keyRelease(window,Qt.Key_Control);spin(180)
        assert c.currentChord==['K:162','M:wheelup'];unchanged(y)
        for button,token in ((Qt.LeftButton,'M:left'),(Qt.RightButton,'M:right'),(Qt.MiddleButton,'M:middle'),(Qt.BackButton,'M:x1'),(Qt.ForwardButton,'M:x2')):
            arm();y=flick.property('contentY');QTest.mouseClick(window,button,pos=QPoint(500,400));spin(180)
            assert not c.state['recording'] and c.currentChord==[token],(button,c.currentChord)
            unchanged(y)
        # B cancels only recording; directions/A cannot navigate the popup.
        arm();window.setProperty('navigateWithPad',True);window.requestActivate();spin(100)
        for command in ('up','down','left','right','activate'):
            dispatch(app,root,backend,command);assert c.state['recording']
        dispatch(app,root,backend,'back');spin(180)
        assert not c.state['recording'] and window.isVisible() and not activations
        arm();before=list(c.currentChord);QTest.mouseClick(window,Qt.LeftButton,pos=point(cancel));spin(180)
        assert not c.state['recording'] and c.currentChord==before and activations==['cancel']
        # Cancel while a key is held: its repeats/release must not reach controls.
        activations.clear();arm();QTest.keyPress(window,Qt.Key_Return);c.cancelCapture()
        app.sendEvent(window,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier,'',True))
        QTest.keyRelease(window,Qt.Key_Return);spin(180)
        assert not activations and not c._capture_draining
        arm();QTest.keyPress(window,Qt.Key_Control);app.sendEvent(window,QEvent(QEvent.WindowDeactivate));spin(180)
        assert not c.state['recording'] and not c._capture_held
        QTest.keyRelease(window,Qt.Key_Control)
        # Reverse recording changes only the selected source, preserving its pad output.
        c.setMode('keys_to_pad');c.selectSource(['K:70']);c.setChord(['P:A']);spin(100)
        flick.setProperty('contentY',max(0,flick.property('contentY')+point(record).y()-500));spin(30)
        QTest.mouseClick(window,Qt.LeftButton,pos=point(record));spin(60);QTest.keyClick(window,Qt.Key_Return);spin(180)
        assert c.sourceChord==['K:13'] and c.currentChord==['P:A'] and not activations
        # Normal wheel events reach preview again; clicks operate controls again.
        c.setWheelTarget('M:wheeldown','P:RY-');spin(220);wheel(-120);spin(40)
        assert c.live.get('virtualAxes',[0,0,0,0])[3]<0,c.live
        model=window.findChild(QObject,'mappingModel1');QTest.mouseClick(window,Qt.LeftButton,pos=point(model));spin(100)
        assert c.padModel=='ps'
        errors=[m for m in messages if any(t in m for t in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))]
        assert not errors,errors[:10]
    finally:
        window.close();spin(100);backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: same large artwork in both directions/three skins/two sizes; Enter, arrows, shortcuts, wheel, mouse and pad capture isolation, cancel, focus loss and restored preview/controls; no real input injection')
