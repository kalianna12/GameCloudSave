"""Only changed records update cards, even during bursts of recommendation replies."""
from pathlib import Path
import copy,json,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QSignalSpy
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=60):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)
def invoke(item,name,*args):return QMetaObject.invokeMethod(item,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',a) for a in args))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'shelf-incremental');store.settings.update(watch=False,recommendations_enabled=False,setup_completed=True,guide_dismissed=True)
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.loadData(b'''import QtQuick
import QtQuick.Controls
ApplicationWindow { visible: true;width:1280;height:760
LibraryHome { objectName: "home";anchors.fill: parent }
}''',QUrl.fromLocalFile(str(ROOT/'ui/ShelfIncrementalReview.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];home=root.findChild(QObject,'home')
    rows=[{'id':str(i),'name':'Game '+str(i),'coverUrl':'','price':'10','platformLabel':'Steam','page':'','category':'new'} for i in range(80)]
    section={'id':'store:new','kind':'store','title':'New','revision':0,'loading':False,'items':rows}
    try:
        home.setProperty('sections',[section]);spin(100)
        shelf=invoke(home,'currentShelf');assert shelf is not None
        model=shelf.findChild(QObject,'shelfRecords');changes=QSignalSpy(model.dataChanged);resets=QSignalSpy(model.modelReset)
        invoke(shelf,'moveSelection',2);spin();selected=shelf.property('selectedId')
        started=time.perf_counter()
        for revision in range(1,13):
            home.setProperty('sections',[dict(copy.deepcopy(section),revision=revision,loading=bool(revision%2))]);spin(5)
        assert changes.count()==0,(changes.count(),messages)
        section=copy.deepcopy(section);section['revision']=13;section['items'][2]['price']='9'
        home.setProperty('sections',[section]);spin()
        assert changes.count()==1,changes.count()
        assert shelf.property('selectedId')==selected
        # Reorder without rewriting every record; preserve selection by ID.
        section=copy.deepcopy(section);section['revision']=14;section['items']=list(reversed(section['items']))
        home.setProperty('sections',[section]);spin()
        assert changes.count()==1 and shelf.property('selectedId')==selected
        # A burst applies the final state once per event-loop turn.
        for revision in range(15,35):
            section=copy.deepcopy(section);section['revision']=revision;section['items'][0]['price']=str(revision)
            home.setProperty('sections',[section])
        spin();assert changes.count()==2 and resets.count()==0,(changes.count(),resets.count())
        home.setProperty('sections',[dict(section,revision=35,items=[])]);spin()
        assert shelf.property('selectedId')=='' and model.rowCount()==0
        errors=[m for m in messages if any(w in m for w in ('Error','Cannot assign','Unable to assign','Binding loop'))]
        assert not errors,errors
        report={'unchanged_record_updates':0,'single_record_updates':1,'burst_record_updates':1,'model_resets':resets.count(),'elapsed_ms':round((time.perf_counter()-started)*1000,1)}
        out=ROOT/'test-data/shelf-incremental';out.mkdir(exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2))
        print('PASS:',json.dumps(report))
    finally:
        root.close();backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
