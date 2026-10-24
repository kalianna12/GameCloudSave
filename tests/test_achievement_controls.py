"""Immediate switches, late polling, game exit and application shutdown; isolated."""
from pathlib import Path
import json,os,sys,tempfile,threading,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,QPointF,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
from services import ROOT,Store
from main import Bridge

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(seconds=.04):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def until(condition,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.01)
    assert condition(),messages[-10:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))
def click(window,item):
    QTest.mouseClick(window,Qt.LeftButton,pos=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint());spin()

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievement-controls-') as temp:
    store=Store(Path(temp)/'data','isolated');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,animations=False)
    store.games=[dict(id='a',name='Fixture',platform='local',tags=[],cover='',category='其他')];store.local={}
    backend=Bridge(store);manager=backend.achievements;manager.timer.stop();manager.cacheAll=lambda *a:None
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    gate=threading.Event()
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];window=root.findChild(QObject,'achievementsWindow')
        invoke(window,'openFor',[]);until(lambda:not manager.state['busy'] and manager.state.get('ident')=='a')
        toggle=window.findChild(QObject,'achievementSystemEnabled');assert toggle is not None
        for width in (900,1280):
            window.resize(width,880);spin()
            assert toggle.mapToScene(QPointF(toggle.width(),0)).x()<width
        row=dict(game_id='a',name='Fixture',description='Isolated notification');target={'hwnd':1,'pid':1}
        def result(events=None,ended=None,epoch=None):
            return dict(events=events or [],ended=ended or [],view=None,epoch=manager._poll_epoch if epoch is None else epoch)
        with patch('achievement_overlay.valid_target',return_value=True),patch('achievement_overlay.game_foreground',return_value=True):
            manager.overlay.enqueue(row,{},True);manager.overlay.tick();assert manager.overlay.toast.isVisible()
            # A mouse click is effective before the background writer completes.
            previous=manager._poll_epoch;click(window,toggle)
            assert not manager.enabled and not manager.timer.isActive() and not manager.overlay.queue and not manager.overlay.current
            assert not manager.overlay.toast.isVisible()
            manager.receivePoll(result([(row,target)],epoch=previous));manager.preview();manager.overlay.tick()
            assert not manager.overlay.queue and not manager.overlay.current
            until(lambda:json.loads((store.profile/'settings.json').read_text(encoding='utf-8')).get('achievements_enabled') is False if (store.profile/'settings.json').exists() else False)
            # Rapid toggles are serialized and preserve the final persisted value.
            manager.setEnabled(True);manager.setEnabled(False);manager.setEnabled(True)
            until(lambda:store.settings['achievements_enabled'] is True);manager.controls.submit(lambda:None).result();spin()
            assert manager.enabled and toggle.property('checked')
            manager.timer.stop()
            # Controls are not delayed by the page's busy state or Save button.
            switches=window.findChild(QObject,'achievementNotifications');assert switches.property('enabled')
            manager._state['busy']=True;manager.changed.emit();click(window,switches)
            assert manager._policies['a']['notifications'] is False
            manager.receivePoll(result([(row,target)]));assert not manager.overlay.queue and not manager.overlay.current
            until(lambda:not manager._policy_pending)
            assert manager.repository.configs['a']['notifications'] is False
            manager._state['busy']=False;manager.changed.emit()
            listen=window.findChild(QObject,'achievementEnabled');click(window,listen)
            until(lambda:not manager._policy_pending);assert manager.repository.configs['a']['enabled'] is False
            old_policies=dict(manager._policy_versions)
            manager.setSwitches('a',{'enabled':True,'notifications':True});until(lambda:not manager._policy_pending)
            late=result([(row,target)]);late['policies']=old_policies
            manager.receivePoll(late);assert not manager.overlay.queue and not manager.overlay.current
            # Real record changes while disabled become a silent baseline when
            # resuming the same game; only subsequent unlocks may notify.
            source=Path(temp)/'achievements.json';source.write_text('{"A":{"earned":false},"B":{"earned":false}}')
            manager.save('a',{'source':str(source)});until(lambda:not manager.state['busy'])
            manager.begin('a').result();manager.attach('a',os.getpid(),1);manager.timer.stop()
            manager.setEnabled(False);source.write_text('{"A":{"earned":true},"B":{"earned":false}}')
            manager.setEnabled(True);until(lambda:manager.sessions.get('a',{}).get('primed'));manager.timer.stop()
            assert not manager.overlay.queue and not manager.overlay.current
            source.write_text('{"A":{"earned":true},"B":{"earned":true}}');manager.poll()
            until(lambda:manager.overlay.current is not None)
            assert manager.overlay.current[0]['id']=='B' and '_toast_icon' in manager.overlay.current[0]
            manager.overlay.clear()
            # A completion from a previous disabled interval must not replay.
            stale=manager._poll_epoch;manager.setEnabled(False);manager.setEnabled(True);manager.timer.stop()
            manager.receivePoll(result([(row,target)],epoch=stale));assert not manager.overlay.queue and not manager.overlay.current
            # The master switch and debounced audio settings share one settings
            # file, so their worker writes must never overlap or lose values.
            import services
            write=services.write_json;writing=[0];maximum=[0];lock=threading.Lock()
            def slow_write(path,value):
                if Path(path).name!='settings.json':return write(path,value)
                with lock:writing[0]+=1;maximum[0]=max(maximum[0],writing[0])
                try:time.sleep(.02);return write(path,value)
                finally:
                    with lock:writing[0]-=1
            with patch('services.write_json',side_effect=slow_write):
                manager.setEnabled(False);manager.setEnabled(True)
                backend.saveAudioSettings({'navigation_volume':37});backend.flushAudioSettings()
                manager.controls.submit(lambda:None).result();backend.pool.submit(lambda:None).result();spin(.08)
            assert maximum[0]==1
            saved=json.loads((store.profile/'settings.json').read_text(encoding='utf-8'))
            assert saved['achievements_enabled'] is True and saved['navigation_volume']==37
            manager.timer.stop()
            # Final file flush at process exit still updates statistics but cannot
            # leave queued notifications alive or deliver exit-time events.
            manager.sessions['a']={'created':123}
            manager.overlay.enqueue(row,{},True);manager.overlay.tick();assert manager.overlay.toast.isVisible()
            manager.receivePoll(result([(row,target)],[('a',123)]))
            assert 'a' not in manager.sessions and not manager.overlay.queue and not manager.overlay.current and not manager.overlay.toast.isVisible()
            # A polled result can already be in Qt's queue when Quit begins.
            gate.clear();entered=threading.Event()
            def pending():entered.set();assert gate.wait(3)
            task=manager.pool.submit(pending);assert entered.wait(1)
            manager.overlay.enqueue(row,{},True);manager.overlay.tick()
            with patch.object(backend._mapping,'shutdown',side_effect=RuntimeError('isolated cleanup failure')):
                try:backend.shutdownWatch()
                except RuntimeError:pass
            assert manager.closed and manager.overlay.closed and manager.overlay.toast is None
            gate.set();task.result();manager.receivePoll(result([(row,target)]));manager.overlay.tick();manager.shutdown()
            assert not manager.timer.isActive() and not manager.overlay.timer.isActive() and not manager.overlay.queue
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))];assert not errors,errors
        print('PASS: actual QML immediate master/game switches, rapid persistence, busy page, stale poll, game exit, shutdown before other cleanup and late delivery')
    finally:
        gate.set();backend.shutdownWatch()
        for pool in (backend.pool,manager.pool,manager.network,manager.icons,manager.batch_pool,manager.controls,backend.graphics.pool):pool.shutdown(wait=True)
        shiboken6.delete(engine)
