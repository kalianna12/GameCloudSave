"""Batch page, cover badges, Steam silent progress and complete offline assets."""
from pathlib import Path
import json,os,sys,tempfile,time,threading
from datetime import datetime,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_achievement_sources import steam_fixture
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
from services import Store,ROOT
from main import Bridge

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=70):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def until(condition,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(25)
    assert condition(),messages[-15:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',value) for value in args))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)


with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievement-library-') as temp:
    root=Path(temp);store=Store(root/'data','isolated');output=ROOT/'build/achievement-library-review';output.mkdir(exist_ok=True)
    store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,achievement_badges='always')
    schema=[{'name':f'ACH_{i}','displayName':f'冒险纪念 {i:02}','description':'探索并记录新的旅程','hidden':i==94} for i in range(96)]
    for folder in ('game/steam_settings','game/profile','ambiguous/steam_settings','ambiguous/one','ambiguous/two'):(root/folder).mkdir(parents=True)
    (root/'game/steam_settings/achievements.json').write_text(json.dumps(schema),encoding='utf-8')
    record=root/'game/profile/achievements.json';record.write_text(json.dumps({f'ACH_{i}':{'earned':i<33} for i in range(96)}),encoding='utf-8')
    (root/'ambiguous/steam_settings/achievements.json').write_text(json.dumps(schema[:2]),encoding='utf-8')
    for account in ('one','two'):(root/f'ambiguous/{account}/achievements.ini').write_text('[FIRST]\nachieved=1',encoding='utf-8')
    steam,definition=steam_fixture(root/'steam')
    image=QImage(360,500,QImage.Format_RGB32);image.fill(QColor('#3b5878'));cover=store.root/'covers/cover.jpg';cover.parent.mkdir();image.save(str(cover))
    store.games=[{'id':'local','name':'本地冒险','platform':'local','metadata_steam_appid':'42','cover':str(cover),'tags':[],'category':'冒险','isNew':True},
                 {'id':'steam','name':'Steam 冒险','platform':'steam','steam_appid':'43','cover':str(cover),'tags':[],'category':'冒险'},
                 {'id':'ambiguous','name':'双账号记录','platform':'local','metadata_steam_appid':'44','cover':str(cover),'tags':[],'category':'冒险'},
                 {'id':'missing','name':'尚无成就记录','platform':'local','cover':str(cover),'tags':[],'category':'冒险'}]
    store.local={'local':{'installed':True,'install_dir':str(root/'game')},'steam':{'installed':True},'ambiguous':{'installed':True,'install_dir':str(root/'ambiguous')}}
    store.games[0]['added_at']=datetime.now(timezone.utc).isoformat()
    backend=None;qml=None
    with patch('achievement_steam.steam_roots',return_value=[root/'steam']),patch('achievements.steam_schema',side_effect=AssertionError('Unexpected network')):
        try:
            backend=Bridge(store);manager=backend.achievements;qml=QQmlApplicationEngine();qml.rootContext().setContextProperty('backend',backend)
            qml.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert qml.rootObjects(),messages
            window=qml.rootObjects()[0];window.resize(1440,900);window.show();spin(250)
            manager.batch([],'local',False);until(lambda:not manager.batchState['running'])
            until(lambda:manager.summary('local').get('total')==96)
            assert manager.summary('local')['unlocked']==33
            assert manager.summary('steam')['unlocked']==1
            assert manager.repository.configs['steam']['notifications'] is False
            assert not manager.repository.configs['ambiguous']['source']
            assert any(r['id']=='missing' for r in manager.batchState['errors'])
            for design in ('classic','shelf','cinema','atlas'):
                store.settings['library_design']=design;backend.settingsChanged.emit();spin(300)
                if design=='classic':
                    invoke(window,'navigate','all','');spin(180)
                    shown=window.property('shownGames');shown=shown.toVariant() if hasattr(shown,'toVariant') else shown
                    invoke(window.findChild(QObject,'gameGrid'),'navigateFocus',next(i for i,g in enumerate(shown) if g['id']=='local'));spin(250)
                badges=[item for item in walk(window.contentItem()) if item.objectName()=='achievementBadge' and item.isVisible()]
                assert badges,(design,messages[-8:])
                if not any(b.property('total')==96 and b.property('completed')==33 for b in badges):
                    window.grabWindow().save(str(output/'failure.png'))
                    print('ALL BADGES',[(b.property('gameId'),b.property('total'),b.isVisible()) for b in walk(window.contentItem()) if b.objectName()=='achievementBadge'],flush=True)
                    print('MODEL',[(g['id'],g['name']) for g in backend.games],messages[-15:],flush=True)
                assert any(b.property('total')==96 and b.property('completed')==33 for b in badges),(design,[(b.property('gameId'),b.property('total'),b.property('completed')) for b in badges],manager.summary('local'))
                for badge in badges:
                    if badge.property('gameId')=='local':
                        new=next((s for s in badge.parentItem().childItems() if s.objectName()=='newGameBadge' and s.isVisible()),None)
                        if new:assert badge.y()>=new.y()+new.height(),(design,new.y(),badge.y(),badge.height())
                        # Hover/focus mode and global hiding never move the new-game marker.
                        original_y=new.y() if new else None
                        store.settings['achievement_badges']='hidden';backend.settingsChanged.emit();spin(30)
                        assert not badge.isVisible()
                        store.settings['achievement_badges']='hover';backend.settingsChanged.emit();badge.setProperty('revealed',False);spin(30)
                        assert not badge.isVisible()
                        badge.setProperty('revealed',True);spin(30);assert badge.isVisible()
                        if new:assert new.y()==original_y
                        store.settings['achievement_badges']='always';backend.settingsChanged.emit();spin(30)
                window.grabWindow().save(str(output/f'badges-{design}.png'))
            store.settings['library_design']='classic';backend.settingsChanged.emit();invoke(window,'navigate','home','');spin(250)
            window.grabWindow().save(str(output/'home.png'))
            nav=window.findChild(QObject,'achievementsNav');QMetaObject.invokeMethod(nav,'clicked');spin(150)
            library=window.findChild(QObject,'achievementsWindow');assert library and library.property('visible')
            invoke(library,'selectGame',0);until(lambda:not manager.state['busy']);spin(120)
            library.grabWindow().save(str(output/'page.png'))
            search=library.findChild(QObject,'achievementListSearch');search.setProperty('text','95');spin(70)
            assert library.findChild(QObject,'achievementList').property('count')==1
            search.setProperty('text','');filter=library.findChild(QObject,'achievementListFilter');filter.setProperty('currentIndex',2);spin(70)
            assert library.findChild(QObject,'achievementList').property('count')==33
            filter.setProperty('currentIndex',0);spin(50)
            library.resize(900,650);spin(140);library.grabWindow().save(str(output/'page-900.png'))
            pages=library.findChild(QObject,'achievementPages');pages.setProperty('currentIndex',1);spin(120)
            library.grabWindow().save(str(output/'sources.png'));pages.setProperty('currentIndex',2);spin(70)
            assert library.findChild(QObject,'achievementRecentList').property('count')>=1
            pages.setProperty('currentIndex',0);spin(50)
            # Counters update in the library without rebuilding the game's model.
            before=backend.libraryRevision;calls=[];manager.overlay.enqueue=lambda *args:calls.append(args)
            manager.begin('steam').result(timeout=3);manager.sessions['steam']['target']={'pid':os.getpid(),'hwnd':0}
            from test_achievement_sources import kv
            steam.write_bytes(kv({'cache':{'7':{'data':3},'8':{'data':10},'9':{'data':4}}}))
            manager.poll();until(lambda:manager.summary('steam').get('unlocked')==2)
            assert not calls and backend.libraryRevision==before
            # Entire requested asset set is visited, rather than a 30-second prefix.
            rows=[{'id':str(i),'icon':'https://cdn.cloudflare.steamstatic.com/'+str(i)} for i in range(60)]
            visited=[]
            with patch.object(manager.repository,'cache_icons',side_effect=lambda group:visited.extend(r['id'] for r in group)),patch.object(manager.repository,'icon_path',return_value='cached'):
                manager.cacheAll('asset-fixture',rows);until(lambda:'asset-fixture' not in manager._icon_jobs)
            assert len(visited)==60
            errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))]
            assert not errors,errors[:20]
            print('PASS: batch local/Steam/cache/ambiguous/missing, 33/96 badges on all layouts, complete page and filters, silent Steam live counters, all 60 assets cached')
        finally:
            if backend:
                backend.shutdownWatch()
                for pool in (backend.achievements.batch_pool,backend.achievements.network,backend.achievements.icons,backend.achievements.pool,backend.pool):pool.shutdown(wait=True)
            if qml:shiboken6.delete(qml)
