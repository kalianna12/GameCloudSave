"""Mouse editing of individual chord members; isolated data, no native output."""
from pathlib import Path
import sys,tempfile,time,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from input_mapping import MappingController
from qml_bootstrap import install_incubator
from PySide6.QtCore import QObject,QUrl,QPointF,QMetaObject,QEvent,Qt,qInstallMessageHandler
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=60):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def point(item):return item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
class Preview:
    def sample(self,*args):return {'buttons':[],'LS':[0,0],'RS':[0,0]},0
    def foreground(self):return 1,os.getpid()
    def held(self,*args):return False
    def key(self,*args):raise AssertionError('No native output permitted')
    move=key;wheel=key

out=ROOT/'test-data/chord-editor';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'chord-editor');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    backend=Bridge(store);c=backend.mapping;c._transport_factory=Preview
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];window=root.findChild(QObject,'inputMappingWindow');QMetaObject.invokeMethod(window,'openMapping')
    deadline=time.perf_counter()+5
    while not window.property('editorReady') and time.perf_counter()<deadline:spin(20)
    assert window.property('editorReady'),messages
    scroll=window.findChild(QObject,'mappingScroll');flick=scroll.property('contentItem')
    def find(name):
        item=window.findChild(QObject,name)
        if item is not None:return item
        return next((item for item in walk(window.contentItem()) if item.objectName()==name),None)
    def click(name,reveal=True):
        item=find(name);assert item is not None,(name,messages[:10])
        if reveal:
            flick.setProperty('contentY',max(0,min(flick.property('contentHeight')-flick.property('height'),flick.property('contentY')+point(item).y()-window.height()*.52)));spin(50)
        QTest.mouseClick(window,Qt.LeftButton,pos=point(item));spin(80)
    def replace(editor,old,new):
        click(editor+'-edit-'+old)
        assert find(editor+'-picker').property('visible'),messages
        entry=find(editor+'-filter');QTest.mouseClick(window,Qt.LeftButton,pos=point(entry))
        for char in new:
            app.sendEvent(window,QKeyEvent(QEvent.KeyPress,ord(char.upper()),Qt.NoModifier,char))
            app.sendEvent(window,QKeyEvent(QEvent.KeyRelease,ord(char.upper()),Qt.NoModifier,char))
        spin(80)
        click(editor+'-option-'+new,False)
        assert not find(editor+'-picker').property('visible')
    try:
        c.selectTarget('A');c.setChord(['K:162','K:89','K:88']);spin()
        click('mappingChord-remove-K:88');assert c.currentChord==['K:162','K:89'] and c.target=='A'
        replace('mappingChord','K:89','K:135');assert c.currentChord==['K:162','K:135']
        click('mappingChord-edit-K:162');spin();window.grabWindow().save(str(out/'replace-key.png'))
        click('mappingChord-delete',False);assert c.currentChord==['K:135']
        click('mappingChord-remove-K:135');assert c.currentChord==[]
        assert find('mappingChord').property('text')=='\u672a\u7ed1\u5b9a'
        c.setChord(['K:65','M:left','M:wheelup']);spin()
        replace('mappingChord','M:left','M:right');assert c.currentChord==['K:65','M:right','M:wheelup']
        click('mappingChordClear');assert c.currentChord==[]
        c.selectTarget('LS.hard.NE');c.setChord(['K:160','K:87','K:68']);spin()
        click('mappingStickChord-remove-K:68');assert c.currentChord==['K:160','K:87']
        replace('mappingStickChord','K:87','K:38');assert c.currentChord==['K:160','K:38']
        c.setMode('keys_to_pad');c.selectSource(['K:162','K:89','K:88']);c.setChord(['P:A','P:Y','P:X']);route=c.target;spin()
        click('mappingChord-remove-P:X');assert c.currentChord==['P:A','P:Y'] and c.target==route
        replace('mappingChord','P:Y','P:RB');assert c.currentChord==['P:A','P:RB']
        click('mappingSourceChord-remove-K:88');assert c.sourceChord==['K:162','K:89'] and c.target==route
        replace('mappingSourceChord','K:89','M:right');assert c.sourceChord==['K:162','M:right'] and c.currentChord==['P:A','P:RB']
        # Clicking an old popup must not edit the newly selected binding.
        click('mappingChord-edit-P:RB');assert find('mappingChord-picker').property('visible')
        c.selectSource(['K:70']);spin();assert not find('mappingChord-picker').property('visible') and c.currentChord==[]
        # Maximum-size chords wrap; both panels grow together, without overlap.
        c.selectSource(['K:'+str(v) for v in range(112,124)]);c.setChord(['P:'+v for v in ('A','B','X','Y','LB','RB','LT','RT','Back','Start','LS','RS')]);spin()
        for theme in ('dark','light'):
            backend.saveSettings({'theme':theme});window.resize(1040,700);spin(150)
            for name in ('mappingSourceChord','mappingChord'):
                editor=find(name);editors=[item for item in walk(editor) if '-edit-' in item.objectName()]
                assert len(editors)==12
                for item in editors:
                    p=item.mapToItem(editor,QPointF())
                    assert p.x()>=-.1 and p.x()+item.width()<=editor.width()+.1,(name,p,editor.width())
                    assert p.y()>=-.1 and p.y()+item.height()<=editor.height()+.1,(name,p,editor.height())
            left=find('mappingControllerPanel');right=find('mappingPreviewPanel')
            assert abs(left.height()-right.height())<.1
            record=find('mappingRecord');events=find('mappingEventList');chord=find('mappingChord')
            assert point(record).y()>point(chord).y() and events.height()>=70
            click('mappingChord-edit-P:X');window.grabWindow().save(str(out/('reverse-12-'+theme+'.png')))
            assert find('mappingChord-picker').property('visible');click('mappingChord-delete',False);assert 'P:X' not in c.currentChord
            c.setChord(['P:'+v for v in ('A','B','X','Y','LB','RB','LT','RT','Back','Start','LS','RS')]);spin()
        assert c.save();other=MappingController(store)
        try:assert other.profile==c.profile
        finally:other.shutdown()
        errors=[m for m in messages if any(t in m for t in ('Error','Cannot','Unable','Binding loop','recursive rearrange'))]
        assert not errors,errors[:20]
    finally:
        window.close();backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: individual remove/replace, keyboard/mouse/pad/stick/source chords, stale popup dismissal, 12-member wrapping, equal panels, small light/dark screenshots and persistence; no native output')
