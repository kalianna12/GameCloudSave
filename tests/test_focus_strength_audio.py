"""Native focus coverage, top-to-cover audio and per-game strength round trips."""
from pathlib import Path
import sys,tempfile,time,json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler,QPointF
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
from services import ROOT,RESOURCES,Store
from main import Bridge
from input_feedback import InputFeedback

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(seconds=.06):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
def until(condition,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if condition():return
        spin(.02)
    assert condition(),messages[-12:]
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='focus-strength-') as temp:
    store=Store(Path(temp)/'data','isolated');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=80,theme='midnight',animations=False)
    store.games=[dict(id=str(i),name=f'Game {i:02}',platform='local',category='视觉小说',tags=[],cover='') for i in range(12)]
    store.local={};backend=Bridge(store);feedback=InputFeedback(app,backend,RESOURCES,audio_muted=True);backend.input_feedback=feedback
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    output=ROOT/'build/focus-strength-review';output.mkdir(exist_ok=True)
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];root.resize(1440,1000);root.show();root.requestActivate();until(lambda:app.focusWindow()==root);spin(.12)
        controlFocus=root.findChild(QObject,'controlFocus');frame=controlFocus.findChild(QObject,'controlFocusFrame')
        report={}
        with patch.object(feedback.audio,'play') as audio:
            for design in ('classic','shelf','cinema','atlas'):
                store.settings['library_design']=design;backend.settingsChanged.emit();invoke(root,'navigate','home','');spin(.18)
                toolbar=root.findChild(QObject,'platformFilter');toolbar.forceActiveFocus();spin(.1);audio.reset_mock()
                invoke(root,'controllerInput','down');spin(.03)
                assert invoke(root,'libraryFocus') and audio.call_count==1,(design,audio.call_args_list)
                report[design+'_top_sound']=True
                # Entering a secondary layout's own grouping bar is a separate
                # focus transition with exactly one movement cue as well.
                if design!='classic':
                    group=root.findChild(QObject,'experienceGrouping');group.forceActiveFocus();spin(.1);audio.reset_mock();invoke(root,'controllerInput','down');spin(.03)
                    assert audio.call_count==1,(design,audio.call_args_list)
        store.settings['library_design']='classic';backend.settingsChanged.emit();spin(.1)
        dialog=root.findChild(QObject,'gameDialog');invoke(dialog,'openFor','0',3);spin(.12)
        pane=dialog.findChild(QObject,'graphicsSettingsPane');enabled=pane.findChild(QObject,'graphicsEnabled');enabled.setProperty('checked',True)
        def check_focus(control):
            control.forceActiveFocus();spin(.025)
            assert controlFocus.property('targetControl')==control,(control.objectName(),controlFocus.property('targetControl'))
            assert frame.isVisible() and frame.parentItem()==control
            point=frame.mapToItem(control,QPointF());assert abs(point.x()+2)<.1 and abs(point.y()+2)<.1
        check_focus(enabled)
        tabs=dialog.findChild(QObject,'gameSettingsTabs');invoke(dialog,'controllerInput','next');spin(.04)
        check_focus(tabs.property('currentItem'));invoke(dialog,'controllerInput','previous');spin(.04)
        # Form navigation reveals every control before it gets its focus frame.
        quick=pane.findChild(QObject,'graphicsQuickProfile');quick.forceActiveFocus()
        seen=set()
        for _ in range(16):
            invoke(pane,'controllerInput','down');spin(.015)
            target=controlFocus.property('targetControl')
            if target is not None:
                assert frame.isVisible() and frame.parentItem()==target
                seen.add(target.objectName())
        assert {'graphicsEnabled','graphicsSharpness'}<=seen,seen
        fps=pane.findChild(QObject,'graphicsFps')
        # SpinBox's editable child must still highlight the entire number field.
        assert fps is not None
        check_focus(fps);fps.property('contentItem').forceActiveFocus();spin(.02);assert controlFocus.property('targetControl')==fps
        for theme in ('midnight','light'):
            store.settings['theme']=theme;backend.settingsChanged.emit();enabled.forceActiveFocus();pane.property('contentItem').setProperty('contentY',0);spin(.06)
            root.grabWindow().save(str(output/f'switch-{theme}.png'));assert frame.isVisible()
        # Levels change only algorithm/sharpness; the user's output options survive.
        display=pane.findChild(QObject,'graphicsDisplay');display.setProperty('currentIndex',1)
        fps.setProperty('value',120)
        for level,algorithm,value in [('low',0,35),('medium',1,70),('high',1,100)]:
            invoke(pane,'applyIntensity',level)
            assert pane.findChild(QObject,'graphicsAlgorithm').property('currentIndex')==algorithm
            assert pane.findChild(QObject,'graphicsSharpness').property('value')==value
            assert display.property('currentIndex')==1 and fps.property('value')==120
        pane.findChild(QObject,'graphicsIntensityHigh').forceActiveFocus();pane.property('contentItem').setProperty('contentY',0);spin(.05);root.grabWindow().save(str(output/'strength-high.png'))
        invoke(pane,'save');until(lambda:not backend.graphics.state['busy'])
        invoke(pane,'loadFor','0');assert pane.property('intensity')=='high'
        assert store.local['0']['graphics']['sharpness']==100
        pane.findChild(QObject,'graphicsSharpness').setProperty('value',87);assert pane.property('intensity')=='custom'
        invoke(pane,'save');until(lambda:not backend.graphics.state['busy']);invoke(pane,'loadFor','0')
        assert pane.property('intensity')=='custom' and pane.findChild(QObject,'graphicsSharpness').property('value')==87
        invoke(pane,'loadFor','1');assert pane.findChild(QObject,'graphicsSharpness').property('value')==20
        dialog.close();spin(.06)
        achievements=root.findChild(QObject,'achievementsWindow');invoke(achievements,'openFor',[]);achievements.requestActivate();until(lambda:app.focusWindow()==achievements)
        until(lambda:not backend.achievements.state['busy']);spin(.1)
        otherFocus=achievements.findChild(QObject,'controlFocus');otherFrame=otherFocus.findChild(QObject,'controlFocusFrame')
        switch=achievements.findChild(QObject,'achievementEnabled');switch.forceActiveFocus();spin(.03)
        assert otherFocus.property('targetControl')==switch and otherFrame.isVisible() and not frame.isVisible()
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))];assert not errors,errors[:15]
        report.update(focus_controls=sorted(seen),standalone_focus=True,themes=['midnight','light'],strength_roundtrip=True,custom_preserved=True)
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('PASS: native focus frames, top-to-cover sound in four layouts, strength/custom per-game persistence')
    finally:
        feedback.audio.shutdown();backend.shutdownWatch()
        for pool in (backend.pool,backend.graphics.pool,backend.achievements.pool,backend.achievements.network,backend.achievements.icons,backend.achievements.batch_pool):pool.shutdown(wait=True)
        shiboken6.delete(engine)
