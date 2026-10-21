"""Live audio controls, modal guards and game-only startup cues; isolated/muted."""
from pathlib import Path
import json,sys,tempfile,time,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from input_feedback import InputFeedback
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,Slot,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=60):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def wait(condition):
    end=time.monotonic()+8
    while time.monotonic()<end:
        spin(10)
        if condition():return
    raise AssertionError(messages[-15:])
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
class SafeBridge(Bridge):
    calls=[]
    @Slot(str)
    def launch(self,ident):self.calls.append(ident)
    @Slot(QObject)
    def beginLaunchPresentation(self,window):pass

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'audio-controls');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,library='',playnite='')
    store.games=[{'id':str(i),'name':f'Fixture {i}','cover':'','last_played':str(100-i)} for i in range(40)]
    backend=SafeBridge(store);feedback=InputFeedback(app,backend,ROOT,audio_muted=True);backend.input_feedback=feedback
    played=[];global_changes=[];feedback.audio.played.connect(lambda kind,bank:played.append((kind,bank)))
    backend.settingsChanged.connect(lambda:global_changes.append(1))
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.resize(1440,1000);root.requestActivate()
    gate=threading.Event()
    try:
        wait(lambda:feedback.audio.ready and root.isActive())
        assert not played,'Opening software must not play the game launch cue'
        personal=root.findChild(QObject,'personalization');QMetaObject.invokeMethod(personal,'openPersonalization')
        wait(lambda:personal.isActive());personal.resize(600,720);spin(120)
        controls={item.objectName():item for item in walk(personal.contentItem()) if item.objectName() in ('navigationSounds','navigationVolume','navigationSoundStyle','launchSound','previewLaunchSound')}
        assert len(controls)==5,controls.keys()
        def focus(name):invoke(personal,'focusChoice',controls[name]);spin(60)
        def pad(command):dispatch(app,root,backend,command);spin(65)
        focus('navigationSoundStyle');pad('activate');assert backend.popupActive()
        for _ in range(7):pad('down')
        pad('activate');wait(lambda:not backend.popupActive())
        assert store.settings['navigation_sound_pack']=='felt' and ('confirm','felt') in played,played[-5:]
        # Pending disk IO never blocks the controls or triggers whole-page refresh.
        backend.pool.submit(lambda:gate.wait(3))
        focus('navigationVolume');before=store.settings['navigation_volume'];pad('left')
        assert store.settings['navigation_volume']==before-5 and feedback.audio.backend.level==before-5,(before,store.settings['navigation_volume'],feedback.audio.backend.level,personal.activeFocusItem().objectName(),controls['navigationVolume'].property('value'),backend.active_popup())
        assert not backend.busy and not global_changes
        pad('down');assert personal.activeFocusItem() is not controls['navigationVolume']
        focus('navigationSounds');pad('activate')
        assert not store.settings['navigation_sounds'] and not feedback.audio.backend.inspect()['enabled']
        count=len(played);feedback.play_launch();feedback.play('move');assert len(played)==count
        pad('activate');assert feedback.audio.backend.inspect()['enabled']
        backend.saveAudioSettings({'navigation_volume':0});assert not feedback.audio.backend.inspect()['enabled']
        backend.saveAudioSettings({'navigation_volume':65,'launch_sound':'orbit'});assert feedback.audio.backend.inspect()['enabled']
        assert controls['navigationVolume'].property('value')==65
        QMetaObject.invokeMethod(controls['previewLaunchSound'],'click');assert played[-1]==('launch','launch-orbit')
        feedback.audio.stop_launch();assert feedback.audio.backend.inspect()['voices']<8
        gate.set();backend.flushAudioSettings();backend.pool.submit(lambda:None).result(timeout=4)
        saved=json.loads((store.profile/'settings.json').read_text(encoding='utf-8'))
        assert saved['navigation_volume']==65 and saved['navigation_sound_pack']=='felt' and saved['launch_sound']=='orbit'
        backend.saveAudioSettings({'navigation_volume':45});backend.saveSettings({'accent_color':'#72b7ec'})
        wait(lambda:not backend.busy);backend.flushAudioSettings();backend.pool.submit(lambda:None).result(timeout=4)
        assert store.settings['navigation_volume']==45
        assert controls['navigationVolume'].property('value')==45
        saved=json.loads((store.profile/'settings.json').read_text(encoding='utf-8'));assert saved['navigation_volume']==45 and saved['accent_color']=='#72b7ec'
        # All nine packs route their own events without rebuilding the library.
        for pack in ('classic-clear','classic-soft','classic-arcade','shelf','cinema','atlas','felt','wood','water'):
            backend.saveAudioSettings({'navigation_sound_pack':pack});spin(90);feedback.play('group');assert played[-1]==('group',pack)
        output=ROOT/'test-data/audio-controls-review';output.mkdir(exist_ok=True)
        focus('launchSound');personal.grabWindow().save(str(output/'audio-controls-600.png'))
        personal.hide();root.requestActivate();wait(root.isActive)
        # A popup created after a cached scan must guard underlying game launch.
        backend.active_popup()
        component=QQmlComponent(engine);component.setData(b'import QtQuick; import QtQuick.Controls; Popup { width: 160; height: 100; modal: true; focus: true }',QUrl())
        popup=component.create();assert popup,component.errors();popup.setParent(root);popup.setProperty('parent',root.contentItem())
        QMetaObject.invokeMethod(popup,'open');spin(100);assert backend.active_popup() is popup
        count=len(backend.calls);pad('activate');assert len(backend.calls)==count
        QMetaObject.invokeMethod(popup,'close');spin(130);shiboken6.delete(popup);assert backend.active_popup() is None
        # Begin once, don't extend/couple the presentation to the audio duration.
        transition=root.findChild(QObject,'launchTransition');backend.saveAudioSettings({'launch_sound':'orbit'})
        before=len(played);started=time.monotonic();invoke(transition,'begin',backend.games[0],'classic');invoke(transition,'begin',backend.games[0],'classic')
        wait(lambda:bool(backend.calls));assert time.monotonic()-started<.7
        assert played[before:].count(('launch','launch-orbit'))==1
        assert backend.calls==[store.games[0]['id']],backend.calls
        invoke(transition,'cancel');assert not transition.property('running')
        clips=set(feedback.audio.clips['launch-orbit','launch']);assert not any(v.clip in clips for v in feedback.audio.backend.voices)
        backend.saveAudioSettings({'launch_sound':'off'});count=len(played);backend.playLaunchSound();assert len(played)==count
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','different thread'))]
        assert not errors,errors
        print('PASS: live mute/volume without global refresh, tool-window gamepad combos/slider, nine packs, persistence/merge, dynamic popup guard, one game launch cue and cancel; muted output')
    finally:
        gate.set();feedback.audio.shutdown();feedback.release_cursor();app.removeEventFilter(feedback)
        backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
