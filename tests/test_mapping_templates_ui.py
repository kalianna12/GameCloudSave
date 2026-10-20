"""Actual template browsing/import/editing at desktop and small sizes; no input injection."""
from pathlib import Path
import os,sys,tempfile,time
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
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))

def spin(ms=80):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.003)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def point(item):
    p=item.mapToScene(QPointF(item.width()/2,item.height()/2));return QPoint(round(p.x()),round(p.y()))
class Preview:
    def sample(self,*args):return {'buttons':[],'LS':[0,0],'RS':[0,0]},0
    def foreground(self):return 1,os.getpid()
    def held(self,*args):return False
    def key(self,*args):raise AssertionError('No injection')
    def move(self,*args):raise AssertionError('No injection')
    def wheel(self,*args):raise AssertionError('No injection')

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'templates-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    bridge=Bridge(store);c=bridge.mapping;c._transport_factory=Preview
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',bridge);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];window=root.findChild(QObject,'inputMappingWindow')
    QMetaObject.invokeMethod(window,'openMapping');spin(200)
    deadline=time.perf_counter()+4
    while not window.property('editorReady') and time.perf_counter()<deadline:spin(20)
    assert window.property('editorReady'),messages
    def find(name):return next(item for item in walk(window.contentItem()) if item.objectName()==name)
    def click(name):QTest.mouseClick(window,Qt.LeftButton,pos=point(find(name)));spin(130)
    dialog=window.findChild(QObject,'mappingTemplatesDialog');output=ROOT/'test-data/input-mapping';output.mkdir(exist_ok=True)
    try:
        click('mappingTemplates');assert dialog.property('visible');assert find('mappingTemplateList').property('count')==8
        window.grabWindow().save(str(output/'templates-vn-dark.png'))
        for index,ident in enumerate(('vn','platform','topdown','shooter','tactics','management','survival','rpgmaker')):
            click('mappingTemplate-'+ident);assert dialog.property('selection')==index
            assert find('mappingTemplateBindings').property('count')==18
        click('mappingTemplate-management');window.grabWindow().save(str(output/'templates-management-dark.png'))
        bridge.saveSettings({'theme':'light'})
        while bridge.busy:spin(20)
        window.resize(1040,700);spin(150);click('mappingTemplate-rpgmaker')
        assert point(find('mappingAddTemplate')).y()<window.height()-10
        assert not find('mappingAddTemplate').property('contentItem').property('truncated')
        window.grabWindow().save(str(output/'templates-rpg-small-light.png'))
        bindings=find('mappingTemplateBindings');bindings.setProperty('contentY',bindings.property('contentHeight')-bindings.height());spin(50)
        last=find('mappingTemplateBinding-17');assert point(last).y()<point(bindings).y()+bindings.height()/2
        window.grabWindow().save(str(output/'templates-rpg-small-light-bottom.png'))
        click('mappingAddTemplate');assert not dialog.property('visible')
        assert c.profile['templateId']=='rpgmaker' and c.currentChord==['K:90'] and not c.state['enabled']
        ident=c.profileId;assert ident in [p['id'] for p in c.profileOptions]
        c.rename('My RPG');c.save();click('mappingTemplates');click('mappingAddAllTemplates')
        assert len(c.profiles)==9 and c.profile['name']=='My RPG' and c.profileId==ident
        assert len(c.addedTemplates)==8 and len(c.profileOptions)==10 and not c.state['enabled']
        c.selectTarget('A');c.setChord(['K:70']);click('mappingTemplates')
        assert find('mappingAddTemplate').property('text')=='打开配置'
        click('mappingAddTemplate');assert c.currentChord==['K:70'] and c.state['dirty']
        click('mappingTemplates');find('mappingTemplate-vn').forceActiveFocus();spin(20)
        QMetaObject.invokeMethod(window,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant','down'));spin(40)
        assert dialog.property('selection')==0,dialog.property('selection')
        QMetaObject.invokeMethod(window,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant','back'));spin(120)
        assert dialog.property('visible') and window.isVisible()
        QMetaObject.invokeMethod(dialog,'close');spin(120)
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Cannot assign','Unable to assign','Binding loop','recursive rearrange'))]
        assert not errors,errors
    finally:
        window.close();spin(100);bridge.shutdownWatch();bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: eight full previews, small/light layout, single and batch import, saved home availability, customized/unsaved preservation and gamepad-inert editor; isolated data, no injection')
