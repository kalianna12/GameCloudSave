"""Isolated achievement browsing, detail, filters, themes and controller UX.

Optional cached real definitions/artwork are read only. All progress is synthetic.
"""
from pathlib import Path
import hashlib,json,shutil,sys,tempfile,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler,QPointF,Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQml import QQmlApplicationEngine
from gamepad import dispatch
import shiboken6
from services import ROOT,Store
from achievements import Repository
from main import Bridge

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(seconds=.08):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def until(condition,timeout=6):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.02)
    assert condition(),messages[-12:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))

output=ROOT/'build/achievement-design-review';output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievement-design-') as temp:
    root=Path(temp);store=Store(root/'data','isolated')
    store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,theme='violet')
    real=ROOT/'test-data/source-preview';library=json.loads((real/'library.json').read_text(encoding='utf-8')) if (real/'library.json').is_file() else []
    assets=Repository(ROOT/'build/achievement-game-review/isolated-assets')
    store.games=[];store.local={};definitions={};sources={}
    for number,(appid,name) in enumerate([('2680010','The First Berserker: Khazan'),('2947440','SILENT HILL f'),('2531310','The Last of Us Part II Remastered')]):
        ident='design-'+appid;path=ROOT/f'build/achievement-schema-{appid}.json'
        rows=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else [dict(id='ACH_'+str(i),name='冒险纪念 '+str(i),description='探索世界并完成新的挑战',hidden=False,icon='',max=0) for i in range(57)]
        for row in rows:row['icon']=assets.icon_path(row)
        # A long entry verifies actual scrolling rather than truncating details.
        rows[0]['description']='完成一次探索并开启新的旅程。'+('这是一段用于检查长说明滚动与小窗口排版的隔离测试文字。'*40)
        rows[-1].update(hidden=True,name='隐藏挑战',description='隐藏说明，仅在用户允许后展示。')
        rows[0].update(rarity_known=True,rarity=.8);rows[1].update(rarity_known=True,rarity=6.3)
        game=dict(id=ident,name=name,platform='steam' if number==1 else 'local',metadata_steam_appid=appid,steam_appid=appid if number==1 else '',cover='',tags=[],category='其他')
        original=next((g for g in library if str(g.get('metadata_steam_appid') or g.get('steam_appid') or '')==appid),{})
        cover=Path(original.get('cover') or '.')
        if not cover.is_absolute():cover=real/cover
        target=store.root/'covers'/f'{ident}.jpg';target.parent.mkdir(exist_ok=True)
        if cover.is_file():shutil.copyfile(cover,target)
        else:
            img=QImage(360,500,QImage.Format_RGB32);img.fill(QColor(['#41596d','#576346','#774d47'][number]));img.save(str(target))
        game['cover']=str(target);store.games.append(game)
        source=root/ident/'achievements.json';source.parent.mkdir();sources[ident]=source
        source.write_text(json.dumps({r['id']:dict(earned=i<19-number*5,earned_time=time.time()-i*86400 if i<19-number*5 else 0) for i,r in enumerate(rows)}),encoding='utf-8')
        definitions[ident]=rows
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    manager=backend.achievements
    try:
        def prepare():
            for game in store.games:
                config=manager.repository.config(game['id']);config.update(appid=game['metadata_steam_appid'],schema=definitions[game['id']],schema_source='Steam 公开资料（隔离测试缓存）',source=str(sources[game['id']]),platform=game['platform'])
                manager.repository.setup(game,{})
            manager.publish()
        with patch('achievement_steam.steam_roots',return_value=[]):manager.pool.submit(prepare).result()
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        host=engine.rootObjects()[0];host.show();spin(.15)
        window=host.findChild(QObject,'achievementsWindow');invoke(window,'openFor',[])
        until(lambda:manager.state.get('has_schema') and not manager.state['busy']);spin(.15)
        assert manager.state['has_record']
        pane=window.findChild(QObject,'achievementsLibraryDetail');games=window.findChild(QObject,'achievementsGameList');entries=pane.findChild(QObject,'achievementList');pages=window.findChild(QObject,'achievementPages')
        for width,height in [(1440,1000),(1280,880),(900,650)]:
            window.resize(width,height);spin(.35)
            assert entries.height()>=150,(width,entries.height())
            for name in ('achievementListSearch','achievementListFilter','achievementListSort','achievementRevealHidden'):
                item=pane.findChild(QObject,name);pos=item.mapToItem(pane,QPointF())
                assert pos.x()>=0 and pos.x()+item.width()<=pane.width()+2,(width,name,pos.x(),item.width(),pane.width())
            window.grabWindow().save(str(output/f'games-{width}.png'))
            if width==900:
                pages.setProperty('currentIndex',3);spin(.18)
                ranking=window.findChild(QObject,'achievementStatisticsGames');pos=ranking.mapToItem(window.contentItem(),QPointF())
                assert ranking.height()>=60 and pos.y()+ranking.height()<=window.height()-25,(ranking.height(),pos.y(),window.height())
                window.grabWindow().save(str(output/'statistics-900.png'));pages.setProperty('currentIndex',0);spin(.08)
        # A gamepad enters the achievement list directly and opens full details.
        games.forceActiveFocus();invoke(window,'controllerInput','right');spin(.06);assert entries.hasActiveFocus()
        model=entries.property('model');model=model.toVariant() if hasattr(model,'toVariant') else model
        entries.setProperty('currentIndex',next(i for i,row in enumerate(model) if row['id']==definitions['design-2680010'][0]['id']))
        invoke(window,'controllerInput','activate');spin(.12)
        dialog=pane.findChild(QObject,'achievementEntryDialog');assert dialog.property('visible')
        assert len(pane.findChild(QObject,'achievementEntryDescription').property('text'))>800
        window.grabWindow().save(str(output/'detail-900.png'))
        window.requestActivate();until(lambda:app.focusWindow()==window)
        dispatch(app,host,backend,'down')
        scroll=pane.findChild(QObject,'achievementDescriptionScroll');assert scroll.property('contentItem').property('contentY')>0
        dispatch(app,host,backend,'back')
        until(lambda:not dialog.property('visible') and entries.hasActiveFocus());assert window.isVisible()
        QTest.keyClick(window,Qt.Key_Return);until(lambda:dialog.property('visible'))
        QTest.keyClick(window,Qt.Key_Escape);until(lambda:not dialog.property('visible') and entries.hasActiveFocus())
        QTest.keyClick(window,Qt.Key_F,Qt.ControlModifier);spin(.05);assert window.findChild(QObject,'achievementsLibrarySearch').hasActiveFocus()
        invoke(pane,'focusEntries')
        # Preserve the focused achievement through background progress updates.
        for _ in range(23):invoke(window,'controllerInput','down')
        anchor=entries.property('navigationId');assert anchor
        source=sources['design-2680010'];data=json.loads(source.read_text());data[definitions['design-2680010'][30]['id']]=dict(earned=True,earned_time=time.time());source.write_text(json.dumps(data))
        until(lambda:manager.summary('design-2680010').get('unlocked')==20);spin(.1)
        assert entries.property('navigationId')==anchor
        model=entries.property('model');model=model.toVariant() if hasattr(model,'toVariant') else model
        assert model[entries.property('currentIndex')]['id']==anchor
        invoke(window,'controllerInput','left');assert games.hasActiveFocus()
        # Empty results distinguish an actual unmatched game from a filter.
        field=pane.findChild(QObject,'achievementListSearch');field.setProperty('text','no-match-fixture');spin(.05);assert entries.property('count')==0
        QMetaObject.invokeMethod(pane.findChild(QObject,'achievementResetFilters'),'clicked');spin(.05);assert entries.property('count')==57
        # Hidden title/description stay hidden unless the user opts in.
        field.setProperty('text','隐藏成就');spin(.04)
        invoke(pane,'focusEntries');invoke(pane,'controllerInput','activate');spin(.06)
        assert pane.findChild(QObject,'achievementEntryTitle').property('text')=='隐藏成就'
        invoke(pane,'controllerInput','back');until(lambda:not dialog.property('visible'));field.setProperty('text','');spin(.04)
        # Batch selection has visible counts and can be cleared directly.
        games.forceActiveFocus();invoke(window,'controllerInput','favorite');spin(.06);assert window.property('selectedCount')==1
        QMetaObject.invokeMethod(window.findChild(QObject,'achievementClearSelection'),'clicked');assert window.property('selectedCount')==0
        window.findChild(QObject,'achievementBatchToggle').setProperty('checked',False)
        for theme in ('light','amber'):
            store.settings.update(theme=theme,animations=False);backend.settingsChanged.emit();window.resize(1440,1000);spin(.25)
            window.grabWindow().save(str(output/f'games-{theme}.png'))
            pages.setProperty('currentIndex',3);spin(.25);window.grabWindow().save(str(output/f'statistics-{theme}.png'));pages.setProperty('currentIndex',0)
        # Recent/statistics are controller-accessible paths back to the game.
        pages.setProperty('currentIndex',2);spin(.06);recent=window.findChild(QObject,'achievementRecentList');recent.forceActiveFocus();recent.setProperty('currentIndex',0)
        invoke(window,'controllerInput','activate');spin(.1);assert pages.property('currentIndex')==0
        assert pane.property('gameId')=='design-2680010'
        pages.setProperty('currentIndex',3);spin(.06);ranking=window.findChild(QObject,'achievementStatisticsGames');ranking.forceActiveFocus();ranking.setProperty('currentIndex',0);invoke(window,'controllerInput','activate');spin(.1);assert pages.property('currentIndex')==0
        # The embedded game settings page uses the same details and B closes only it.
        window.close();gameDialog=host.findChild(QObject,'gameDialog');invoke(gameDialog,'openFor','design-2680010',4);until(lambda:not manager.state['busy']);spin(.12)
        embedded=host.findChild(QObject,'achievementsPane');invoke(embedded,'focusEntries');invoke(gameDialog,'controllerInput','activate');spin(.08)
        assert embedded.property('entryOpen');invoke(gameDialog,'controllerInput','back');until(lambda:not embedded.property('entryOpen'));assert gameDialog.property('visible')
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))];assert not errors,errors[:15]
        (output/'report.json').write_text(json.dumps(dict(layouts=[900,1280,1440],themes=['violet','light','amber'],details=True,controller_return=True,real_dispatch=True,keyboard=True,live_focus_preserved=True,filters=True,hidden_protected=True,batch=True,recent_navigation=True,embedded=True),indent=2),encoding='utf-8')
        print('PASS: real-icon design review, responsive filters, long details, controller return, live focus, themes, hidden protection, batch and recent navigation')
    finally:
        backend.shutdownWatch()
        for pool in (manager.batch_pool,manager.network,manager.icons,manager.pool,backend.pool):pool.shutdown(wait=True)
        shiboken6.delete(engine)
