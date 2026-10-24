"""Many games, live updates and actual mouse-held scrollbar regressions."""
from copy import deepcopy
from pathlib import Path
import json,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QPointF,QPoint,Qt,qInstallMessageHandler
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
from services import Store,ROOT
from main import Bridge
from achievement_files import parse_state,merge_progress

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(seconds=.05):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def until(condition,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.015)
    assert condition(),messages[-15:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))
def scrollbar(view):
    return next(b for b in view.findChildren(QObject) if b.inherits('QQuickScrollBar') and b.property('orientation')==Qt.Vertical and b.property('visible'))

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievement-scroll-') as temp:
    root=Path(temp);store=Store(root/'data','isolated')
    store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,animations=False,theme='amber')
    store.games=[dict(id=f'g{i:02}',name=f'游戏 {i:02}',platform='local',cover='',tags=[],category='其他') for i in range(64)]
    store.local={};source=root/'achievements.json';source.write_text('{"A000":{"earned":true,"earned_time":1700000000}}')
    schema=[dict(id=f'A{i:03}',name=f'成就 {i:03}',description='用于验证滚动条与刷新互不干扰',hidden=False,icon='',max=0) for i in range(220)]
    backend=Bridge(store);manager=backend.achievements;manager.timer.stop();manager.cacheAll=lambda *args:None
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    try:
        def prepare():
            states=parse_state(source)
            for game in store.games:
                config=manager.repository.config(game['id']);config.update(schema=schema,source=str(source));merge_progress(manager.repository.record(game['id'],config),states)
            manager.repository.save();manager.publish()
        manager.pool.submit(prepare).result()
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        host=engine.rootObjects()[0];host.show();spin(.1)
        window=host.findChild(QObject,'achievementsWindow');invoke(window,'openFor',[]);window.resize(1280,880);window.requestActivate()
        until(lambda:manager.state.get('has_schema') and not manager.state['busy']);spin(.1)
        games=window.findChild(QObject,'achievementsGameList');pane=window.findChild(QObject,'achievementsLibraryDetail');entries=pane.findChild(QObject,'achievementList')
        invoke(window,'selectGame',32);until(lambda:manager.state.get('ident')=='g32' and not manager.state['busy']);spin(.1)
        report={};issues=[]
        def catalog_tick(n):
            rows=deepcopy(manager._overview);rows[0]['icons_cached']=n
            manager.receiveCatalog(dict(summaries=manager._summaries,rows=rows,recent=manager._recent,analytics=manager._analytics))
        def entry_tick(n):
            rows=deepcopy(manager._state['rows']);rows[0]['progress']=n
            manager._state=dict(manager._state,rows=rows,icons_done=n);manager.changed.emit()
        # Browsing elsewhere must not force the selected game's row back into view.
        games.setProperty('contentY',337);spin(.04);before=games.property('contentY')
        for n in range(1,8):catalog_tick(n);spin(.025)
        report['game_scroll_drift']=round(games.property('contentY')-before,2)
        if abs(report['game_scroll_drift'])>2:issues.append('game list jumps on background updates')
        def drag(view,tick,label,direction=1,bar=None):
            bar=bar if bar is not None else scrollbar(view);handle=bar.property('contentItem')
            initial=view.property('contentY')
            start=handle.mapToScene(QPointF(handle.width()/2,handle.height()/2)).toPoint()
            destination=max(bar.mapToScene(QPointF(0,8)).y(),min(bar.mapToScene(QPointF(0,bar.height()-8)).y(),start.y()+direction*100))
            QTest.mousePress(window,Qt.LeftButton,pos=start);spin(.02)
            grabbed=bar.property('pressed')
            for step in range(1,9):
                QTest.mouseMove(window,start+type(start)(0,round((destination-start.y())*step/8)),delay=12)
                tick(step+20);spin(.015)
                grabbed=grabbed and bar.property('pressed')
            QTest.mouseRelease(window,Qt.LeftButton,pos=start+type(start)(0,round(destination-start.y())));spin(.08)
            final=view.property('contentY');tick(99);spin(.1)
            report[label]=dict(held=bool(grabbed),distance=round(final-initial,2),after_refresh_drift=round(view.property('contentY')-final,2))
            if not grabbed or abs(final-initial)<40 or abs(view.property('contentY')-final)>2:issues.append(label+' cannot retain a scrollbar drag')
        games.setProperty('contentY',337);spin(.03);drag(games,catalog_tick,'game_drag')
        drag(games,catalog_tick,'game_drag_up',-1)
        invoke(pane,'focusEntries')
        for _ in range(18):invoke(pane,'controllerInput','down')
        entries.setProperty('contentY',260);spin(.04);before=entries.property('contentY')
        for n in range(1,8):entry_tick(n);spin(.025)
        report['entry_scroll_drift']=round(entries.property('contentY')-before,2)
        if abs(report['entry_scroll_drift'])>2:issues.append('achievement list snaps back to focus on refresh')
        entries.setProperty('contentY',260);spin(.04);drag(entries,entry_tick,'entry_drag')
        drag(entries,entry_tick,'entry_drag_up',-1)
        # The outer settings scroller must not consume the inner list's wheel.
        before=entries.property('contentY');outer_before=pane.property('contentItem').property('contentY')
        point=entries.mapToScene(QPointF(entries.width()/2,entries.height()/2))
        event=QWheelEvent(point,QPointF(window.mapToGlobal(point.toPoint())),QPoint(),QPoint(0,-120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        app.sendEvent(window,event);spin(.15)
        report['entry_wheel']=dict(distance=round(entries.property('contentY')-before,2),outer_drift=round(pane.property('contentItem').property('contentY')-outer_before,2))
        if report['entry_wheel']['distance']<=0 or abs(report['entry_wheel']['outer_drift'])>2:issues.append('outer scroller steals list wheel input')
        pane.findChild(QObject,'achievementSetup').setProperty('checked',True);spin(.1)
        outer=pane.property('contentItem');outer.setProperty('contentY',0);spin(.04)
        drag(outer,entry_tick,'settings_drag',bar=pane.findChild(QObject,'achievementPaneScrollBar'))
        drag(outer,entry_tick,'settings_drag_up',-1,pane.findChild(QObject,'achievementPaneScrollBar'))
        pages=window.findChild(QObject,'achievementPages');pages.setProperty('currentIndex',3);window.setProperty('chartGame','');spin(.1)
        ranking=window.findChild(QObject,'achievementStatisticsGames');ranking.setProperty('contentY',240);spin(.04)
        drag(ranking,catalog_tick,'statistics_drag');drag(ranking,catalog_tick,'statistics_drag_up',-1)
        pages.setProperty('currentIndex',2);spin(.1)
        recent=window.findChild(QObject,'achievementRecentList');recent.setProperty('contentY',240);spin(.04)
        drag(recent,catalog_tick,'recent_drag');drag(recent,catalog_tick,'recent_drag_up',-1)
        pages.setProperty('currentIndex',0);pane.findChild(QObject,'achievementSetup').setProperty('checked',False);spin(.06)
        for width,height in [(900,650),(1920,1080)]:
            window.resize(width,height);spin(.1)
            games.setProperty('contentY',337);spin(.025);drag(games,catalog_tick,f'games_{width}')
            invoke(pane,'focusEntries');entries.setProperty('contentY',260);spin(.025);drag(entries,entry_tick,f'entries_{width}')
        output=ROOT/'build/achievement-scroll-review';output.mkdir(exist_ok=True)
        window.grabWindow().save(str(output/'many-games.png'))
        (output/'report.json').write_text(json.dumps(dict(report,issues=issues),indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
        assert not issues,issues
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))];assert not errors,errors[:12]
        print('PASS: 64 games, 220 achievements, no refresh jumps, real held mouse drags during live updates')
    finally:
        backend.shutdownWatch()
        for pool in (manager.batch_pool,manager.network,manager.icons,manager.pool,backend.pool):pool.shutdown(wait=True)
        shiboken6.delete(engine)
