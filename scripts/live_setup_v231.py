"""Read-only live connection and matching checks, using an isolated profile."""
from pathlib import Path
import sys,shutil,tempfile,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl,QObject,QMetaObject
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([])
source=Store();report={}
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'live-setup');store.settings={**source.settings,'watch':False,'setup_completed':True,'snapshots':str(store.profile/'snapshots')}
    for name in ('credential.dpapi','ai-key.dpapi'):
        if (source.profile/name).exists():shutil.copy2(source.profile/name,store.profile/name)
    selected=[game for game in source.games if 'last of us' in game['name'].casefold() or 'rubinite' in game['name'].casefold()][:2]
    if not selected:selected=source.games[:1]
    store.games=[dict(game) for game in selected];store.local={game['id']:dict(source.local.get(game['id'],{})) for game in selected}
    (store.root/'covers').mkdir()
    for game in selected:
        file=source.root/'covers'/Path(game.get('cover') or '').name
        if file.is_file():shutil.copy2(file,store.root/'covers'/file.name)
    bridge=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',bridge);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects();root=engine.rootObjects()[0];QMetaObject.invokeMethod(root,'openSetup')
    wizard=root.findChild(QObject,'setupWizard');wizard.setProperty('step',3)
    def wait(timeout=90):
        start=time.monotonic()
        while bridge.busy and time.monotonic()-start<timeout:app.processEvents();time.sleep(.01)
        assert not bridge.busy,'Timed out: '+bridge.status
        app.processEvents();return round(time.monotonic()-start,2)
    bridge.browseCloud(store.settings['cloud_folder'],{})
    report['dav_seconds']=wait();report['dav_items']=len(bridge.directories)
    assert bridge.status.startswith('DAV'),bridge.status
    wizard.setProperty('browsingCloud',True);wizard.setProperty('cloudBrowseValid',True);app.processEvents()
    output=ROOT/'test-data/v231';output.mkdir(exist_ok=True);wizard.grabWindow().save(str(output/'wizard-dav-live.png'))
    wizard.setProperty('step',4);bridge.testAi({'ai_enabled':True})
    report['ai_test_seconds']=wait();report['ai_connected']=bridge.aiConnection.startswith('DeepSeek 连接成功');assert report['ai_connected'],bridge.status
    wizard.setProperty('step',1);bridge.testPlaynite(store.settings['playnite'],store.settings['library']);wait()
    report['playnite']=bridge.playniteConnection
    # If the live Playnite database is locked, verify the same read-only exporter on the existing copied fixture.
    if not bridge.playniteConnection.startswith('Playnite 已连接'):
        assert '关闭 Playnite' in bridge.playniteConnection,bridge.playniteConnection
        fixture=Path(directory)/'playnite';fixture.mkdir();shutil.copy2(ROOT/'test-data/playnite-games.db',fixture/'games.db')
        bridge.testPlaynite(store.settings['playnite'],str(fixture));wait();report['playnite_fixture']=bridge.playniteConnection
        assert bridge.playniteConnection.startswith('Playnite 已连接')
    wizard.hide();matcher=root.findChild(QObject,'matchWindow');matcher.setProperty('showConnection',False);QMetaObject.invokeMethod(matcher,'openMatcher',__import__('PySide6.QtCore',fromlist=['Q_ARG']).Q_ARG('QVariant',selected[0]['id']))
    # Fresh caches exercise real local + network + DeepSeek; no saves are configured, backed up or uploaded.
    bridge.matchGames([game['id'] for game in selected])
    start=time.monotonic();ticks=[];changed=False
    while bridge.busy and time.monotonic()-start<100:
        app.processEvents();ticks.append(time.monotonic());time.sleep(.01)
        if not changed and time.monotonic()-start>.2:
            root.findChild(QObject,'search').setProperty('text',selected[0]['name'][:4]);changed=True
    assert not bridge.busy,'Live matching timed out'
    report['match_seconds']=round(time.monotonic()-start,2)
    report['heartbeat_max_ms']=round(max(b-a for a,b in zip(ticks,ticks[1:]))*1000,1)
    report['matches']=[{'game':row['name'],'status':row['status'],'candidates':len(row['candidates']),'ai_reviewed':any('ai_confidence' in candidate for candidate in row['candidates'])} for row in bridge.matchResults]
    matcher.grabWindow().save(str(output/'match-live.png'))
    assert report['heartbeat_max_ms']<500,report
    report['passed']=True
    (output/'live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False))
    bridge.timer.stop();bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
