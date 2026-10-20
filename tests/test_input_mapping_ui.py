"""Visual models, actual internal drag/drop, keyboard chord recording and responsive editor."""
from pathlib import Path
import sys,tempfile,time,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from qml_bootstrap import install_incubator
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
def log(kind,context,message):
    messages.append(message)
    if len(messages)<20:print(message,flush=True)
qInstallMessageHandler(log)
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def point(item):
    p=item.mapToScene(QPointF(item.width()/2,item.height()/2));return QPoint(round(p.x()),round(p.y()))
def drag(window,source,target):
    a=point(source);b=point(target);hits=[];item=window.contentItem()
    while item:
        hits.append((item.metaObject().className(),item.objectName(),item.property('token')));p=item.mapFromScene(QPointF(a));item=item.childAt(p.x(),p.y())
    QTest.mouseMove(window,a);spin(20);QTest.mousePress(window,Qt.LeftButton,pos=a);spin(20)
    for step in range(1,16):QTest.mouseMove(window,a+(b-a)*step/15);spin(12)
    spin(30)
    assert controller.dropTarget==target.property('token'),(controller.dropHint,target.property('token'),a,b,window.height(),source.property('dragging'),point(target),hits)
    assert source.property('label') in controller.dropHint and controller.dropHint.startswith('松开绑定：'),controller.dropHint
    QTest.mouseRelease(window,Qt.LeftButton,pos=b);spin(120);assert not controller.dropHint
class Preview:
    def sample(self,*args):return {'buttons':[],'LS':[0,0],'RS':[0,0]},0
    def foreground(self):return 1,os.getpid()
    def held(self,*args):return False
    def key(self,*args):raise AssertionError('Editor tests must never inject input')
    def move(self,*args):raise AssertionError('Editor tests must never inject input')
    def wheel(self,*args):raise AssertionError('Editor tests must never inject input')

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'mapping-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    backend=Bridge(store);backend.mapping._transport_factory=Preview
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];window=root.findChild(QObject,'inputMappingWindow');controller=backend.mapping
    QMetaObject.invokeMethod(root.findChild(QObject,'mappingNav'),'click');spin(50);assert window.isVisible()
    deadline=time.monotonic()+4
    while not window.property('editorReady') and time.monotonic()<deadline:spin(30)
    assert window.property('editorReady'),'Asynchronous editor did not become ready'
    spin(80)
    try:
        controller.selectTarget('A');controller.record('binding')
        for key in (Qt.Key_Control,Qt.Key_Shift,Qt.Key_S):QTest.keyPress(window,key)
        for key in (Qt.Key_S,Qt.Key_Shift,Qt.Key_Control):QTest.keyRelease(window,key)
        spin();assert controller.currentChord==['K:162','K:160','K:83'],controller.currentChord
        controller.record('binding');QTest.keyClick(window,Qt.Key_F11);spin()
        assert controller.currentChord==['K:122'] and not root.property('fullScreenMode')
        def key(token):return next(item for item in walk(window.contentItem()) if item.property('token')==token and item.isVisible())
        drag(window,key('K:65'),key('P:B'))
        assert controller.profile['forward']['buttons']['B']==['K:65'],controller.profile['forward']['buttons']['B']
        window.setProperty('appendCombo',True);drag(window,key('K:160'),key('P:B'))
        assert controller.currentChord==['K:65','K:160'],controller.currentChord
        controller.selectTarget('LS.lightExtra');controller.setChord(['K:160']);controller.selectTarget('LS.hardExtra');controller.setChord([])
        controller.setOption('RS','speed',2200);assert controller.save()
        output=ROOT/'test-data/input-mapping';output.mkdir(exist_ok=True)
        window.grabWindow().save(str(output/'forward-dark.png'))
        keyboard=window.findChild(QObject,'mappingKeyboardModel');panel=window.findChild(QObject,'mappingControllerPanel');preview=window.findChild(QObject,'mappingPreviewPanel')
        assert keyboard.mapToScene(QPointF()).y()<panel.mapToScene(QPointF()).y()
        assert panel.mapToScene(QPointF()).x()<preview.mapToScene(QPointF()).x()
        for index,model in ((1,'ps'),(2,'joycon'),(0,'xbox')):
            control=window.findChild(QObject,'mappingModel'+str(index));QTest.mouseClick(window,Qt.LeftButton,pos=point(control));spin(150)
            assert controller.profile['padModel']==model
            assert window.findChild(QObject,'mappingPadModel').property('modelType')==model
            if index:window.grabWindow().save(str(output/(model+'-dark.png')))
        controller.setEditorVisible(True);controller.receiveSample({'buttons':['A'],'LS':[.3,.5],'RS':[0,0],'keys':['K:65'],'connected':True,'slot':0})
        assert any(event['down'] for event in controller.state['events']) and controller.state['sample']['outputs']
        controller.clearEvents();assert not controller.state['events']
        scroll=window.findChild(QObject,'mappingScroll');flick=scroll.property('contentItem')
        source=point(key('K:65'));edge=QPoint(window.width()-110,window.height()-50)
        QTest.mousePress(window,Qt.LeftButton,pos=source);QTest.mouseMove(window,source+QPoint(20,20));spin(30)
        QTest.mouseMove(window,edge);spin(300)
        assert flick.property('contentY')>40,'Dragging near the bottom must scroll to off-screen binding targets'
        QTest.mouseRelease(window,Qt.LeftButton,pos=edge);flick.setProperty('contentY',0);spin(100)
        QMetaObject.invokeMethod(window.findChild(QObject,'mappingDrivers'),'click');spin(160)
        assert window.findChild(QObject,'mappingDriverDialog').property('visible')
        assert window.findChild(QObject,'mappingInstall').property('enabled') is (not controller.setup.state['ready'])
        window.grabWindow().save(str(output/'drivers.png'))
        QMetaObject.invokeMethod(window.findChild(QObject,'mappingDriverDialog'),'close');spin(80)
        controller.setMode('keys_to_pad');spin(150)
        window.setProperty('appendCombo',False);drag(window,key('P:A'),key('K:70'))
        window.setProperty('appendCombo',True);drag(window,key('P:LB'),key('K:70'))
        assert controller.sourceChord==['K:70'] and controller.currentChord==['P:A','P:LB'],(controller.sourceChord,controller.currentChord)
        controller.record('binding')
        QTest.keyPress(window,Qt.Key_Control);QTest.keyClick(window,Qt.Key_K);QTest.keyRelease(window,Qt.Key_Control);spin()
        assert controller.sourceChord==['K:162','K:75']
        controller.receiveSample({'buttons':[],'LS':[0,0],'RS':[0,0],'keys':['K:87'],'mouseDelta':[0,0],'connected':False,'slot':-1})
        assert controller.state['sample']['virtualAxes'][1]>0
        assert controller.save();window.grabWindow().save(str(output/'reverse-dark.png'))
        backend.saveSettings({'theme':'light'})
        while backend.busy:spin(20)
        window.resize(1040,700);spin(180);window.grabWindow().save(str(output/'light-small.png'))
        assert window.findChild(QObject,'mappingScroll').property('contentHeight')>window.findChild(QObject,'mappingScroll').height()
        assert not controller.state['enabled']
        QMetaObject.invokeMethod(window.findChild(QObject,'mappingHelp'),'click');spin(100)
        assert window.findChild(QObject,'mappingHelpDialog').property('visible')
        QMetaObject.invokeMethod(window.findChild(QObject,'mappingHelpDialog'),'close');spin(80)
        window.showMinimized();spin(80);assert not controller.state['editor']
        window.showNormal();window.requestActivate();spin(100);assert controller.state['editor']
        window.close();spin(100)
        # A saved profile can be selected in the library without reopening the editor.
        picker=root.findChild(QObject,'homeMappingProfile');assert picker is not None
        options=controller.profileOptions;ident=controller.profileId;index=next(i for i,p in enumerate(options) if p['id']==ident)
        picker.setProperty('currentIndex',index);QMetaObject.invokeMethod(picker,'activated',Q_ARG(int,index));spin(80)
        assert controller.activeProfile==ident and not window.isVisible(),(controller.activeProfile,ident,controller.state['message'])
        picker.setProperty('currentIndex',0);QMetaObject.invokeMethod(picker,'activated',Q_ARG(int,0));spin(80);assert not controller.state['enabled']
        nav=root.findChild(QObject,'mappingNav');nav.forceActiveFocus()
        for command in ('right','left','up','down','right'):
            QMetaObject.invokeMethod(root,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant',command));spin(25)
            assert not window.isVisible(),'Stick navigation must not reopen the mapping tool'
        errors=[m for m in messages if any(word in m for word in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))]
        assert not errors,errors[:15]
    finally:
        window.close();spin(150);backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: three cached models, two-way drag/drop target highlight/hints, recording, live preview, saved home profile/none selection, no stick reopening, driver detection and small/light scrolling; no injection or driver installation')
