"""Isolated result filters, hidden selections and explicit account/slot restore preview."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):
    value=QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
    return value.toVariant() if hasattr(value,'toVariant') else value
def idle():
    end=time.monotonic()+8
    while backend.busy and time.monotonic()<end:spin(20)
    assert not backend.busy,backend.status
    spin(100)
def data(obj,key):
    value=obj.property(key);return value.toVariant() if hasattr(value,'toVariant') else value
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    root_path=Path(directory);store=Store(root_path/'data','save-ui')
    store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,playnite='',library='')
    store.games=[{'id':ident,'name':name,'cover':'','category':'其他','tags':[]} for ident,name in [('A','Configured'),('B','Missing'),('C','Review'),('D','Failed')]]
    for game in store.games:store.local[game['id']]={'installed':True}
    saves=root_path/'SaveGames';source='76561198000000001';target='76561198000000002'
    (saves/source).mkdir(parents=True)
    for number in ('01','02'):(saves/source/('SaveGame'+number+'_Player.sav')).write_text('source'+number)
    store.save_game('A',{'save_dir':str(saves)});store.backup('A');snapshot=store.history('A')[0]['id']
    (saves/source).rename(saves/target)
    for number in ('01','02'):(saves/target/('SaveGame'+number+'_Player.sav')).write_text('target'+number)
    candidate=root_path/'review';candidate.mkdir();(candidate/'slot.sav').write_text('candidate')
    row={'path':str(candidate),'confidence':.94,'files':['slot.sav'],'fileSummary':'slot.sav','has_save_evidence':True}
    store.match_report=[{'id':ident,'name':name,'status':status,'candidates':candidates} for ident,name,status,candidates in [('A','Configured','applied',[row]),('B','Missing','notfound',[]),('C','Review','review',[row]),('D','Failed','failed',[])]]
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];spin(200)
    invoke(root,'openMatch','B');spin(200)
    matcher=root.findChild(QObject,'matchWindow');query=matcher.findChild(QObject,'matchResultQuery');filter=matcher.findChild(QObject,'matchResultFilter');list_view=matcher.findChild(QObject,'matchResultList')
    assert list_view.property('count')==4
    filter.setProperty('currentIndex',2);spin();assert list_view.property('count')==2
    query.setProperty('text','Missing');spin();assert list_view.property('count')==1
    query.setProperty('text','');filter.setProperty('currentIndex',4);spin();assert list_view.property('count')==1
    matcher.hide();invoke(root,'openBatch');spin(200)
    batch=root.findChild(QObject,'batchWindow');filter=batch.findChild(QObject,'batchResultFilter');query=batch.findChild(QObject,'batchResultQuery')
    filter.setProperty('currentIndex',3);spin();assert [row['id'] for row in data(batch,'rows')]==['C']
    invoke(batch,'selectAll');assert invoke(batch,'ids')==['C']
    query.setProperty('text','Missing');spin();assert invoke(batch,'ids')==[],'Hidden selections must not be acted upon'
    query.setProperty('text','');spin();assert invoke(batch,'ids')==['C']
    batch.hide();root.requestActivate();spin()
    dialog=root.findChild(QObject,'restoreDialog');invoke(dialog,'begin','A',snapshot,{});idle()
    assert data(dialog,'preview')['needs_mapping']
    confirm=dialog.findChild(QObject,'confirmRestore');assert not confirm.property('enabled')
    dialog.findChild(QObject,'restoreSourceAccount').setProperty('currentIndex',1)
    dialog.findChild(QObject,'restoreTargetAccount').setProperty('currentIndex',1)
    slot=dialog.findChild(QObject,'restoreSlotChoice');slot.setProperty('currentIndex',1);spin()
    assert confirm.property('enabled')
    assert (saves/target/'SaveGame01_Player.sav').read_text()=='target01','Preview must not restore'
    output=ROOT/'test-data/save-reliability';root.grabWindow().save(str(output/'restore-preview.png'))
    QMetaObject.invokeMethod(confirm,'click');idle()
    assert (saves/target/'SaveGame01_Player.sav').read_text()=='source01',backend.status
    assert (saves/target/'SaveGame02_Player.sav').read_text()=='target02'
    errors=[message for message in messages if any(word in message for word in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))]
    assert not errors,errors
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: result status/name filters, hidden selections, asynchronous preview, explicit account mapping and one-slot restore')
