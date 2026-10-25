"""V2.7 batch save application, cloud provider form and notification removal."""
from pathlib import Path
import json,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QPointF,Qt,qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from services import ROOT,Store
from main import Bridge
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(seconds=.05):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def until(condition,timeout=6):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.01)
    assert condition(),messages[-10:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',a) for a in args))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='release-v27-ui-') as temp:
    base=Path(temp);store=Store(base/'data','isolated')
    store.settings.update(setup_completed=True,guide_dismissed=True,recommendations_enabled=False,watch=False,animations=False,navigation_volume=0)
    store.games=[dict(id=k,name='Fixture '+k,platform='local',tags=[],category='其他',cover='') for k in ('a','b','ambiguous','reserved','conflict1','conflict2')]
    store.local={g['id']:{'installed':True} for g in store.games}
    reports=[]
    def candidate(name,confidence=.92):
        path=base/name;path.mkdir(exist_ok=True);(path/'SaveGame01.sav').write_bytes(b'fixture-progress')
        return dict(path=str(path),confidence=confidence,has_save_evidence=True,files=['SaveGame01.sav'],fileSummary='SaveGame01.sav',reason='Fixture')
    for key in ('a','b'):reports.append(dict(id=key,name='Fixture '+key,status='review',candidates=[candidate(key)],checked=[]))
    reports.append(dict(id='ambiguous',name='Ambiguous',status='review',candidates=[candidate('c'),candidate('d')],checked=[]))
    known=candidate('known');store.local['known']={'save_dir':known['path']}
    reports.append(dict(id='reserved',name='Reserved',status='review',candidates=[known],checked=[]))
    for key in ('conflict1','conflict2'):reports.append(dict(id=key,name=key,status='review',candidates=[candidate('shared')],checked=[]))
    backend=Bridge(store);backend._matches=reports;backend._matches_cache=None
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];invoke(root,'openMatch','a');spin(.15)
        match=root.findChild(QObject,'matchWindow');button=match.findChild(QObject,'applyRecommendedSaves')
        assert button.isVisible() and button.property('enabled')
        QTest.mouseClick(match,Qt.LeftButton,pos=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
        until(lambda:not backend.busy);spin(.05)
        assert store.local['a']['save_dir']==str(base/'a') and store.local['b']['save_dir']==str(base/'b')
        assert not store.local['ambiguous'].get('save_dir') and not store.local['reserved'].get('save_dir')
        assert not store.local['conflict1'].get('save_dir') and not store.local['conflict2'].get('save_dir')
        persisted=json.loads((store.profile/'games.json').read_text(encoding='utf-8'));assert persisted['a']['save_dir']==str(base/'a')
        match.hide()
        cloud=root.findChild(QObject,'cloudWindow')
        invoke(cloud,'openBrowserDraft',{'cloud_provider':'github','github_repo':'fixture/saves','github_branch':'backup','github_token':'fixture-token'},False);spin(.1)
        provider=cloud.findChild(QObject,'cloudProvider');assert provider.property('currentIndex')==1
        values=invoke(cloud,'values');values=values.toVariant() if hasattr(values,'toVariant') else values
        assert values['github_repo']=='fixture/saves' and values['github_branch']=='backup' and values['cloud_provider']=='github'
        assert not cloud.findChild(QObject,'davServer').isVisible()
        assert cloud.findChild(QObject,'githubRepository').isVisible()
        cloud.grabWindow().save(str(ROOT/'build/release-2.7.0/github-settings.png'))
        assert not hasattr(backend.achievements,'overlay') and not hasattr(backend.achievements,'preview')
        errors=[m for m in messages if any(w in m for w in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))];assert not errors,errors
        print('PASS: one-click reliable save paths, ambiguity/conflict skipped, persisted; GitHub form in-page; no achievement overlay runtime')
    finally:
        backend.shutdownWatch()
        for pool in (backend.pool,backend.achievements.pool,backend.achievements.network,backend.achievements.icons,backend.achievements.batch_pool,backend.achievements.controls):pool.shutdown(wait=True)
        shiboken6.delete(engine)
