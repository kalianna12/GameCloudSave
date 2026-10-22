"""QML hero selection, controller focus, back position and classification warning."""
from pathlib import Path
import sys,tempfile,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import Gamepad,dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:app.processEvents();time.sleep(.005)
def invoke(obj,name,*values):
    return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',value) for value in values))
def variant(value):return value.toVariant() if hasattr(value,'toVariant') else value
def visual(item,name):
    if item.objectName()==name:return item
    for child in item.childItems():
        found=visual(child,name)
        if found:return found
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'navigation');store.settings.update(setup_completed=True,watch=False,guide_dismissed=True,recommendations_enabled=False)
    for i in range(30):
        store.games.append({'id':str(i),'name':f'Game {i:02}','cover':'','last_played':f'2026-10-{min(i+1,9):02}T00:00:00Z' if i<8 else '', 'tags':['恋爱'] if i<20 else [], 'category':'视觉小说' if i<20 else '其他'})
        store.local[str(i)]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(250)
    home=root.findChild(QObject,'libraryHome');view=root.findChild(QObject,'libraryHomeList')
    recent=visual(root.contentItem(),'shelf-recent');assert recent
    shelf=recent.parentItem();hero=visual(root.contentItem(),'recentHero');original=variant(hero.property('game'))['id']
    invoke(shelf,'moveSelection',1);spin(180);assert variant(hero.property('game'))['id']!=original
    selected=variant(hero.property('game'))['id']
    home.forceActiveFocus();dispatch(app,root,backend,'right');spin(180)
    assert variant(hero.property('game'))['id']!=selected
    selected=variant(hero.property('game'))['id']
    backend.toggleFavorite('25')
    while backend.busy:spin(20)
    assert variant(hero.property('game'))['id']==selected
    invoke(home,'navigateFocus','down');spin(180);saved=view.property('contentY')
    invoke(root,'navigate','category','视觉小说');spin(150)
    assert root.findChild(QObject,'libraryBack').property('visible') and root.property('libraryMode')=='category'
    combo=root.findChild(QObject,'platformFilter');combo.forceActiveFocus();dispatch(app,root,backend,'activate');spin(180)
    popup=next(item for item in combo.findChildren(QObject) if item.inherits('QQuickPopup'))
    assert popup.property('visible') and backend.popupActive()
    dispatch(app,root,backend,'back');spin(400)
    assert not popup.property('visible') and root.property('libraryMode')=='category', (popup.property('visible'),root.property('libraryMode'))
    combo.forceActiveFocus();dispatch(app,root,backend,'activate');spin(150)
    dispatch(app,root,backend,'down');spin(40);dispatch(app,root,backend,'activate');spin(150)
    assert combo.property('currentIndex')==1 and not popup.property('visible'),(combo.property('currentIndex'),popup.property('visible'))
    combo.setProperty('currentIndex',0);root.setProperty('platformFilter','all');spin(80)
    root.findChild(QObject,'libraryBack').forceActiveFocus();dispatch(app,root,backend,'activate');spin(150)
    assert root.property('libraryMode')=='home' and abs(view.property('contentY')-saved)<2, (root.property('libraryMode'),view.property('contentY'),saved)
    invoke(home,'focusFirst');invoke(home,'navigateFocus','down');spin(100)
    assert home.property('focusedSection')==1
    invoke(home,'activateSelected');spin(100);assert root.property('libraryMode')=='category'
    invoke(root,'goBack');spin(100)
    invoke(root,'openGame',backend.games[0]);spin(80);assert backend.popupActive()
    assert not variant(invoke(root,'controllerInput','launch')),'Controller must not launch through a modal popup'
    root.findChild(QObject,'gameDialog').setProperty('visible',False);spin(80)
    invoke(root,'openManager') if root.metaObject().indexOfMethod('openManager()')>=0 else QMetaObject.invokeMethod(root.findChild(QObject,'libraryManager'),'openManager')
    while backend.busy:spin(20)
    manager=root.findChild(QObject,'libraryManager');chosen=variant(manager.property('selected'))
    assert set(chosen)=={str(i) for i in range(20,30)},chosen
    row=next(row for row in backend.organizerResults if row['id']=='0');invoke(manager,'choose',row,True);spin(60)
    warning=manager.findChild(QObject,'classificationWarning');assert warning.property('visible') and '0' not in variant(manager.property('selected'))
    guarded=backend.popupActive();dispatch(app,root,backend,'back');spin(250)
    assert not warning.property('visible') and manager.property('visible') and '0' not in variant(manager.property('selected')), (guarded,warning.property('visible'),manager.property('visible'),root.property('libraryMode'))
    invoke(manager,'choose',row,True);QMetaObject.invokeMethod(warning,'accept');spin(60);assert '0' in variant(manager.property('selected'))
    manager.hide();root.requestActivate();spin(60)
    enabled=[True];driver=Gamepad(app,lambda:enabled[0],threaded=False);buttons=[0];commands=[]
    def query(index,state):state._obj.pad.buttons=buttons[0];return 0 if index==0 else 1167
    driver.query=query;driver.command.connect(commands.append);driver.poll()
    buttons[0]=0x1000;driver.poll();driver.poll();assert commands==['activate']
    driver.sync();driver.poll();assert commands==['activate'],'Held A must not fire on resume'
    enabled[0]=False;driver.sync();assert not driver.timer.isActive()
    driver.timer.stop()
    output=ROOT/'test-data/v232';output.mkdir(exist_ok=True);manager.grabWindow().save(str(output/'classification.png'));manager.hide();root.grabWindow().save(str(output/'home.png'))
    errors=[m for m in messages if any(s in m for s in ['TypeError','ReferenceError','Binding loop','is not a type','Cannot assign'])];assert not errors,errors
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: dynamic hero, stable selection, back position, controller category selection, modal guard, unclassified-only defaults and warning')
