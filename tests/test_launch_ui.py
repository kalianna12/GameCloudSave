"""Isolated launcher windows, real Win32 readiness, minimum animation and fullscreen."""
from pathlib import Path
import sys,tempfile,time,subprocess,shutil
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtGui import QColor,QWindow
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def idle():
    until=time.monotonic()+8
    while backend.busy and time.monotonic()<until:spin(20)
    assert not backend.busy
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'launch-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,close_to_tray=False)
    art=next((ROOT/'data/covers').glob('*.jpg'));(store.root/'covers').mkdir();shutil.copy2(art,store.root/'covers'/'cover.jpg')
    store.games=[{'id':'fixture','name':'Startup fixture','cover':'cover.jpg','tags':[],'category':'其他'}]
    store.local['fixture']={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(300)
    output=ROOT/'test-data/launch-review';output.mkdir(exist_ok=True)
    # Fullscreen can be entered with the button/controller method, toggled with
    # F11, persisted, and restored to the prior maximized/windowed state.
    invoke(root,'toggleFullScreen');spin(400)
    assert root.visibility()==QWindow.FullScreen and store.settings['fullscreen']
    root.grabWindow().save(str(output/'fullscreen.png'))
    QTest.keyClick(root,Qt.Key_F11);spin(400);assert root.visibility()!=QWindow.FullScreen and not store.settings['fullscreen']
    root.showMaximized();spin(150);invoke(root,'toggleFullScreen');spin(150);invoke(root,'toggleFullScreen');spin(350)
    assert root.visibility()==QWindow.Maximized
    root.showNormal();root.setWidth(1440);root.setHeight(940);spin(150)
    # Matching highlight frames sit above artwork, use the accent and clear
    # when navigation leaves the content, including the filmstrip.
    for design,name in [('shelf','bookFocusRing'),('cinema','cinemaFocusRing'),('atlas','atlasFocusRing')]:
        backend.saveSettings({'library_design':design,'accent_color':'#80c942'});idle();spin(200)
        experience=next(i for i in walk(root.contentItem()) if i.objectName()=='libraryExperience')
        invoke(experience,'focusFirst');backend.setControllerMode(True);spin(150)
        frames=[i for i in walk(experience) if i.objectName()==name and i.isVisible()]
        assert len(frames)==1,(design,len(frames),messages)
        frame=frames[0];assert QQmlExpression(engine.rootContext(),frame,'border.color').evaluate()[0]==QColor('#80c942')
        assert frame.z()>=100
        root.grabWindow().save(str(output/(design+'-focus.png')))
        root.findChild(QObject,'navHome').forceActiveFocus();spin(100);assert not frame.isVisible(),design
    backend.setControllerMode(False)
    # Cancel before submission performs no launch.
    transition=root.findChild(QObject,'launchTransition');game=backend.games[0]
    with patch.object(store,'launch') as launch:
        invoke(root,'launchGame',game);invoke(transition,'cancel');spin(200);assert not launch.called
    # A window which is ready early still waits for the complete intro.
    with patch.object(store,'launch',return_value=None) as launch,patch('launch_ready.wait',return_value={'phase':'ready','hwnd':0,'message':'Fixture ready'}):
        started=time.monotonic();invoke(root,'launchGame',game);invoke(root,'launchGame',game);spin(300)
        assert transition.property('running') and not transition.property('animationDone')
        spin(900);assert not transition.property('running') and launch.call_count==1
        assert time.monotonic()-started>=1
    # The animation finishes but its curtain stays until a real child window
    # is visible and stable. The helper is isolated and never starts a game.
    helper=store.root/'visible_fixture.py'
    helper.write_text('from PySide6.QtWidgets import QApplication,QWidget,QLabel\nfrom PySide6.QtCore import QTimer\napp=QApplication([])\nw=QWidget();w.setWindowTitle("GameCloudSave readiness fixture");w.resize(720,480);w.setStyleSheet("background:#284a65;color:white")\nQLabel("Rendered test window",w).move(80,80)\nQTimer.singleShot(1900,w.show)\nQTimer.singleShot(7000,app.quit)\napp.exec()\n',encoding='utf-8')
    store.local['fixture'].update(launch_mode='direct',exe=str(Path(sys.executable).with_name('pythonw.exe')),arguments=subprocess.list2cmdline([str(helper)]))
    children=[];real_start=subprocess.Popen
    def capture(*args,**kwargs):
        child=real_start(*args,**kwargs);children.append(child);return child
    phases=[];backend.launchChanged.connect(lambda:phases.append(backend.launchState['phase']))
    try:
        with patch('services.subprocess.Popen',side_effect=capture):
            invoke(root,'launchGame',game);spin(1250)
            assert transition.property('animationDone') and transition.property('running') and backend.launchState['phase']=='waiting'
            root.grabWindow().save(str(output/'waiting.png'))
            until=time.monotonic()+10
            while transition.property('running') and time.monotonic()<until:spin(30)
            assert not transition.property('running') and 'ready' in phases,(phases,backend.launchState,messages)
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)
    root.requestActivate();spin(150)
    # Timeout/resume never sends a second launch. Stale callbacks after return
    # cannot reactivate a game or restart its overlay.
    with patch.object(store,'launch',return_value=None) as launch,patch('launch_ready.wait',return_value={'phase':'timeout','message':'Fixture timeout'}):
        invoke(root,'launchGame',game);spin(1200);assert transition.property('running') and backend.launchState['phase']=='timeout'
        invoke(root,'controllerInput','activate');spin(200);assert launch.call_count==1
        token=backend._launch_token;invoke(transition,'cancel')
        backend.receiveLaunchReady(token,{'phase':'ready','hwnd':0});assert backend.launchState['phase']=='cancelled'
    with patch.object(store,'launch',side_effect=ValueError('Fixture missing executable')):
        invoke(root,'launchGame',game);spin(1200);assert backend.launchState['phase']=='error' and transition.property('running')
        invoke(transition,'cancel')
    def until_cancelled(probe,cancel):
        cancel.wait(3);return {'phase':'cancelled'}
    with patch.object(store,'launch',return_value=None),patch('launch_ready.wait',side_effect=until_cancelled):
        invoke(root,'launchGame',game);spin(250);root.hide();spin(100)
        assert not transition.property('running') and backend._launch_cancel.is_set()
        root.show();root.requestActivate();spin(200)
    backend.saveSettings({'animations':False});idle()
    def delayed_ready(*args):time.sleep(.35);return {'phase':'ready','hwnd':0,'message':'Fixture ready'}
    with patch.object(store,'launch',return_value=None),patch('launch_ready.wait',side_effect=delayed_ready):
        invoke(root,'launchGame',game);spin(80)
        assert transition.property('animationDone') and transition.property('running')
        spin(550);assert not transition.property('running')
    errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','is not defined'))]
    assert not errors,errors
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: accent focus frames, fullscreen restore/persist/F11, full intro, real visible child handoff, cancel, failure, timeout/resume and stale callbacks')
