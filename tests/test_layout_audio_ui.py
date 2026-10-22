"""Actual layout/series controls route distinct sounds; only temporary library data."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from input_feedback import InputFeedback
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:app.processEvents();time.sleep(.002)
def wait(condition):
    until=time.monotonic()+8
    while time.monotonic()<until:
        spin(10)
        if condition():return
    raise AssertionError(('Layout/audio timeout',messages))
def activate(combo,index):
    spin(110);combo.setProperty('currentIndex',index)
    assert QMetaObject.invokeMethod(combo,'activated',Q_ARG(int,index))
    spin(120)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'layout-audio')
    store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,
                          navigation_sounds=True,navigation_volume=80,library='',playnite='')
    store.games=[{'id':str(i),'name':'Fixture '+str(i),'cover':'','series':'Series '+str(i%4),'category':'Action','tags':['Tag']} for i in range(140)]
    backend=Bridge(store);feedback=InputFeedback(app,backend,ROOT,audio_muted=True);backend.input_feedback=feedback
    played=[];feedback.audio.played.connect(lambda kind,bank:played.append((kind,bank)))
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.resize(1440,1000);root.requestActivate()
    try:
        wait(lambda:feedback.audio.ready and root.isActive());backend.setControllerMode(True)
        root.setProperty('libraryMode','series');spin(160)
        filters=root.findChild(QObject,'libraryFilterDialog');QMetaObject.invokeMethod(filters,'begin',Q_ARG('QVariant',{}));spin(120)
        series=root.findChild(QObject,'facetSeriesChoice');assert series.property('visible')
        activate(series,1);assert ('group','classic-clear') in played
        QMetaObject.invokeMethod(filters,'close');spin(150)
        for design in ('shelf','cinema','atlas','classic'):
            spin(110);before=len(played)
            backend.saveSettings({'library_design':design,'experience_group':'category'})
            assert played[before:]==[('switch',design if design!='classic' else 'classic-clear')]
            wait(lambda:not backend.busy and root.property('libraryDesign')==design);spin(180)
            if design=='classic':continue
            experience=root.findChild(QObject,'libraryExperience')
            if experience is None:
                experience=next(item for item in walk(root.contentItem()) if item.objectName()=='libraryExperience')
            grouping=experience.findChild(QObject,'experienceGrouping');activate(grouping,1)
            wait(lambda:not backend.busy);assert experience.property('groupMode')=='series'
            choice=experience.findChild(QObject,'experienceGroupChoice');activate(choice,1)
            assert experience.property('groupValue')==choice.property('currentText')
            assert ('group',design) in played
            # Themed combo owns open/selection sounds; dispatch must not add confirm.
            spin(120);choice.forceActiveFocus();before=len(played)
            dispatch(app,root,backend,'activate');spin(120)
            dispatch(app,root,backend,'down');spin(120)
            dispatch(app,root,backend,'activate');spin(120)
            assert ('group',design) in played[before:] and ('confirm',design) not in played[before:],played[before:]
            if design=='shelf':
                activate(experience.findChild(QObject,'shelfArrangement'),1)
                wait(lambda:not backend.busy);assert played[-1]==('switch','shelf')
        personal=root.findChild(QObject,'personalization');QMetaObject.invokeMethod(personal,'openPersonalization')
        wait(lambda:personal.property('visible'));personal.resize(600,720);spin(180)
        for design in ('classic','shelf','cinema','atlas'):
            button=next(item for item in walk(personal.contentItem()) if item.objectName()=='previewSound-'+design)
            QMetaObject.invokeMethod(personal,'focusChoice',Q_ARG('QVariant',button));spin(130)
            QMetaObject.invokeMethod(button,'click')
            assert played[-1]==('switch',design if design!='classic' else 'classic-clear')
        output=ROOT/'test-data/audio-layout-review';output.mkdir(exist_ok=True)
        personal.grabWindow().save(str(output/'personal-audio.png'));personal.hide();root.requestActivate();spin(80)
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','different thread','Timers cannot'))]
        assert not errors,errors
        print('PASS: 140-game isolated library, all four layouts, actual series/group/arrangement controls, native sound routing and no double confirm; muted output')
    finally:
        feedback.audio.shutdown();feedback.release_cursor();app.removeEventFilter(feedback)
        backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
