"""Three settings pages, scoped cover results, import choices and responsive fill preview."""
from pathlib import Path
import sys,tempfile,time,shutil,hashlib
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QTimer,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def idle():
    end=time.monotonic()+15
    while (backend.busy or backend.artworkSearching) and time.monotonic()<end:spin(20)
    assert not backend.busy and not backend.artworkSearching,backend.status

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'ui-enrichment');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='',ai_enabled=False)
    covers=store.root/'covers';covers.mkdir()
    art=covers/'fixture.jpg'
    originals=list((ROOT/'data/covers').glob('*.jpg'))
    if originals:shutil.copy2(originals[0],art)
    else:
        picture=QImage(300,450,QImage.Format_RGB32);picture.fill(QColor('#354450'));picture.save(str(art))
    for i in range(10):
        store.games.append({'id':str(i),'name':f'测试游戏 {i}','tags':['悬疑'] if i==0 else [],'category':'视觉小说' if i==0 else '其他','series':'已有系列' if i==0 else '', 'cover':str(art) if i==0 else '', 'release_date':'2000-01-01' if i==0 else ''})
        store.local[str(i)]={'installed':True,'arguments':'--windowed'}
    write_json(store.root/'library.json',store.games)
    original=(store.root/'library.json').read_bytes();backend=Bridge(store)
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.setWidth(1440);root.setHeight(940);root.requestActivate();spin(350)
    output=ROOT/'test-data/enrichment-ui';output.mkdir(exist_ok=True)
    invoke(root,'openGame',backend.games[0]);spin(300)
    dialog=root.findChild(QObject,'gameDialog');tabs=dialog.findChild(QObject,'gameSettingsTabs')
    assert dialog.property('visible') and tabs.property('count')==4
    root.grabWindow().save(str(output/'game-save.png'))
    tabs.setProperty('currentIndex',1);spin(300);root.grabWindow().save(str(output/'game-cover.png'))
    tabs.setProperty('currentIndex',2);spin(300);root.grabWindow().save(str(output/'game-metadata.png'))
    root.setWidth(900);root.setHeight(650);spin(300);root.grabWindow().save(str(output/'settings-small.png'));dialog.setProperty('visible',False)
    root.setWidth(1440);root.setHeight(940);spin()
    # Cover queries run on the worker; changing game/page cannot reuse the wrong result set.
    with patch('cover_sources.search',side_effect=lambda *args: (time.sleep(.15) or [{'id':'cover','name':'First game','image':QUrl.fromLocalFile(str(art)).toString()}])):
        invoke(root,'openGame',backend.games[1]);backend.searchGameCovers('1','one','steam',False)
        invoke(root,'openGame',backend.games[2]);tabs.setProperty('currentIndex',1);idle();spin()
        assert dialog.findChild(QObject,'gameCoverResults').property('count')==0
    with patch('cover_sources.search',return_value=[{'id':'cover-choice','name':'Chosen cover','image':QUrl.fromLocalFile(str(art)).toString()}]):
        backend.searchGameCovers('2','two','steam',False);idle();spin(300)
    assert dialog.findChild(QObject,'gameCoverResults').property('count')==1
    chosen=covers/'chosen.jpg';shutil.copy2(art,chosen)
    with patch('cover_sources.download',return_value=str(chosen)):
        backend.applyCover('game','2','cover-choice');idle();spin(300)
    value=dialog.findChild(QObject,'gameCoverPicker').property('record')
    record=value.toVariant() if hasattr(value,'toVariant') else value
    assert record['cover']==str(chosen),'Current cover must update when the saved game changes'
    root.grabWindow().save(str(output/'game-cover-results.png'))
    original=(store.root/'library.json').read_bytes()
    dialog.setProperty('visible',False)
    assert root.findChild(QObject,'enrichmentNav')
    invoke(root,'openEnrichment',[],{'use_ai':False},False);spin()
    window=root.findChild(QObject,'enrichmentWindow');assert window.property('visible')
    close=window.findChild(QObject,'enrichmentClose');assert close.x()>window.width()/2
    aiSettings=window.findChild(QObject,'enrichmentAiSettings');invoke(aiSettings,'openSettings');spin(300)
    assert aiSettings.property('visible') and aiSettings.property('width')>0
    keyField=aiSettings.findChild(QObject,'enrichmentAiKey');keyField.setProperty('text','fixture-only')
    aiSettings.setProperty('visible',False);spin(300);assert keyField.property('text')==''
    window.grabWindow().save(str(output/'fill-empty.png'))
    ticks=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start()
    def lookup(game):
        time.sleep(.06)
        return {'release_date':'2020-02-03','release_date_source':'Steam','tags':['角色扮演'],'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/1/'}
    def search(store,query,provider,*values):
        time.sleep(.025)
        return [{'id':'test:'+hashlib.sha256(query.encode()).hexdigest()[:8],'appid':'999999','name':query,'provider':'steam','score':1,'image':QUrl.fromLocalFile(str(art)).toString()}]
    def download(store,record):
        path=store.root/'covers'/(record['id'].replace(':','-')+'.jpg');shutil.copy2(art,path);return str(path)
    with patch('library_metadata.lookup',side_effect=lookup),patch('cover_sources.search',side_effect=search),patch('cover_sources.download',side_effect=download):
        invoke(window,'startQuery');spin(100)
        assert backend.busy and backend.enrichmentProgress['running']
        window.setWidth(920);spin();window.grabWindow().save(str(output/'fill-running.png'));idle();spin()
        assert len(ticks)>=10,'Qt event loop must remain responsive during lookup'
        assert (store.root/'library.json').read_bytes()==original
        assert len(backend.enrichmentResults)==10 and any(row['fields'].get('cover') for row in backend.enrichmentResults)
        window.setWidth(1160);spin();window.grabWindow().save(str(output/'fill-preview.png'))
        invoke(root,'openGame',backend.libraryMetadata('1'));tabs.setProperty('currentIndex',2)
        dialog.findChild(QObject,'metadataTags').setProperty('text','未保存标签');invoke(dialog,'mark','tags')
        dialog.findChild(QObject,'gameSavePath').setProperty('text','D:/DraftSave')
        backend.applyEnrichment(['1']);idle();spin()
        assert store.games[0]['release_date']=='2000-01-01' and store.games[0]['cover']==str(art)
        assert store.games[1]['release_date']=='2020-02-03' and store.games[2]['release_date']==''
        assert dialog.findChild(QObject,'metadataTags').property('text')=='未保存标签'
        assert dialog.findChild(QObject,'metadataDate').property('text')=='2020-02-03'
        assert dialog.findChild(QObject,'gameSavePath').property('text')=='D:/DraftSave'
        dialog.setProperty('visible',False)
        assert any(row['id']=='1' and row['applied'] for row in backend.enrichmentResults)
        # Stopping a new query leaves the saved library intact.
        current=(store.root/'library.json').read_bytes();invoke(window,'startQuery');spin(20);backend.cancelEnrichment();idle()
        assert (store.root/'library.json').read_bytes()==current
    # The additional pass also runs off the UI thread and still produces a preview only.
    store.games.append({'id':'retry-ui','name':'Custom edit','source_name':'Original candidate','category':'其他','tags':[],'cover':''})
    backend._games_cache=None;backend.gamesChanged.emit()
    before=(store.root/'library.json').read_bytes();ticks_before=len(ticks)
    phases=[]
    def delayed_search(store,query,provider,*values):
        time.sleep(.08)
        if query=='Original candidate' and provider=='steam':
            return [{'id':'steam:456','appid':'456','name':'Original candidate','provider':'steam','score':1,'image':''}]
        return []
    def retry_metadata(game):
        if game.get('metadata_steam_appid')=='456':return {'release_date':'2002-03-04','release_date_source':'Steam'}
        return {}
    backend.enrichmentChanged.connect(lambda:phases.append(backend.enrichmentProgress['phase']))
    with patch('library_metadata.lookup',side_effect=retry_metadata),patch('cover_sources.search',side_effect=delayed_search):
        invoke(root,'openEnrichment',['retry-ui'],{'dates':True,'tags':False,'covers':False,'use_ai':False},True);spin(80);idle();spin()
    assert len(ticks)-ticks_before>=10 and any('二次查询' in phase for phase in phases)
    assert backend.enrichmentResults[0]['second_pass'] and backend.enrichmentResults[0]['fields']['release_date']=='2002-03-04'
    assert (store.root/'library.json').read_bytes()==before and not store.games[-1].get('release_date')
    store.games.pop();backend._games_cache=None;backend.gamesChanged.emit()
    # A failed title stays in this window: search a chosen catalog, stage a
    # verified match, or type missing fields. Neither action saves until Apply.
    from enrichment_manual import base
    store.games.append({'id':'manual','name':'Edited title','category':'其他','tags':[],'cover':''})
    backend._games_cache=None;backend.gamesChanged.emit()
    _,manual_row,_=base(store,'manual');backend.receiveEnrichment(manual_row,1,1,'Finished')
    window.setProperty('ownsQuery',True);invoke(window,'sync');invoke(window,'openManual',backend.enrichmentResults[-1]);spin(200)
    pane=window.findChild(QObject,'manualEnrichmentPane');assert pane.isVisible()
    assert pane.findChild(QObject,'manualQuery').property('text')=='Edited title'
    for provider in ('google','bing','ign','steamgriddb','gog','epic'):
        assert backend.enrichmentBrowserUrl('Title & name',provider).startswith('https://')
    before=(store.root/'library.json').read_bytes();tick_count=len(ticks)
    with patch('cover_sources.search',side_effect=lambda *args:(time.sleep(.18) or [{'id':'vndb:v1','provider':'vndb','name':'Original title','released':'1999-02-03','image':''}])):
        invoke(pane,'search');idle();spin()
    assert pane.findChild(QObject,'manualCandidates').property('count')==1 and len(ticks)>tick_count
    backend.previewEnrichmentCandidate('manual','vndb:v1');idle();spin(100)
    assert not window.property('manualId') and backend.enrichmentResults[-1]['fields']['release_date']=='1999-02-03'
    assert (store.root/'library.json').read_bytes()==before
    invoke(window,'openManual',backend.enrichmentResults[-1]);spin(100)
    pane.findChild(QObject,'manualDate').setProperty('text','2001-03-04')
    pane.findChild(QObject,'manualSeries').setProperty('text','Manually checked series')
    pane.findChild(QObject,'manualCover').setProperty('text',str(art))
    window.setWidth(920);spin(150);window.grabWindow().save(str(output/'manual-small.png'))
    invoke(pane,'stage');idle();spin(100)
    assert (store.root/'library.json').read_bytes()==before
    proposal=backend.enrichmentResults[-1];assert proposal['fields']['release_date']=='2001-03-04' and proposal['fields']['cover']
    assert proposal['sources']['release_date']=='手动' and window.property('selected').toVariant()['manual']
    backend.applyEnrichment(['manual']);idle();assert store.games[-1]['release_date']=='2001-03-04'
    store.games.pop();backend._games_cache=None;backend.gamesChanged.emit()
    timer.stop();window.hide();root.requestActivate();spin()
    # Import explicitly offers preview enrichment and a plain import without network work.
    invoke(root,'openImport');spin();importer=root.findChild(QObject,'importWindow')
    install=store.root/'installed';install.mkdir()
    backend._imports=[{'id':'candidate','name':'New import','platform':'local','external_id':'new','install_dir':str(install),'score':1}];backend.changed.emit()
    importer.setProperty('selectedIds',{'candidate':True});invoke(importer,'confirmImport');spin()
    options=importer.findChild(QObject,'importEnrichmentOptions');assert options.property('visible')
    importer.grabWindow().save(str(output/'import-choice.png'));options.setProperty('visible',False)
    with patch('library_metadata.lookup') as network:
        backend.importSelected(['candidate'],{'preview':False});idle()
        assert not network.called
    assert any(game['name']=='New import' for game in backend.games)
    # Import-and-query opens a preview scoped to the newly imported game, without applying it.
    another=store.root/'another-installed';another.mkdir()
    backend._imports=[{'id':'next','name':'Another import','platform':'local','external_id':'next','install_dir':str(another),'score':1}]
    with patch('library_metadata.lookup',side_effect=lookup):
        backend.importSelected(['next'],{'preview':True,'dates':True,'tags':True,'covers':False,'use_ai':False});idle();spin(150);idle();spin()
    imported=next(game for game in store.games if game['name']=='Another import')
    assert not imported.get('release_date')
    assert len(backend.enrichmentResults)==1 and backend.enrichmentResults[0]['id']==imported['id']
    assert window.property('visible') and backend.enrichmentResults[0]['fields']['release_date']=='2020-02-03'
    assert not any(word in message for message in messages for word in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign']),messages
    backend.timer.stop();backend.cancelEnrichment();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: three intuitive pages, inline scoped covers, explicit import choices, live progress/preview, selective fill, no overwrite, cancellation and responsive Qt event loop')
