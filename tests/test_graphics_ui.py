"""Actual themed settings pane, save/reopen and small-window layout; no game launch."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:app.processEvents();time.sleep(.004)
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
    store=Store(temp,'graphics-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,close_to_tray=False)
    store.games=[{'id':'fixture','name':'画质增强测试游戏','cover':'','tags':[],'category':'其他'}]
    store.local={'fixture':{'installed':True,'exe':r'D:\fixture.exe'}}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];root.setWidth(1400);root.setHeight(1050);root.show();spin(300)
        dialog=root.findChild(QObject,'gameDialog');invoke(dialog,'openFor','fixture',3);spin(220)
        pane=dialog.findChild(QObject,'graphicsSettingsPane');assert pane.property('visible')
        enabled=pane.findChild(QObject,'graphicsEnabled');algorithm=pane.findChild(QObject,'graphicsAlgorithm')
        enabled.setProperty('checked',True);algorithm.setProperty('currentIndex',2)
        pane.findChild(QObject,'graphicsSharpness').setProperty('value',56)
        invoke(pane,'save')
        until=time.monotonic()+5
        while backend.graphics.state['busy'] and time.monotonic()<until:spin(10)
        assert store.local['fixture']['graphics']['preset']=='fsr'
        assert store.local['fixture']['graphics']['sharpness']==56
        invoke(pane,'loadFor','fixture');assert algorithm.property('currentIndex')==2
        assert not pane.property('dirty') and not backend.graphics.state['installed']
        output=ROOT/'build/graphics-review';output.mkdir(exist_ok=True)
        root.grabWindow().save(str(output/'dark.png'))
        store.settings['theme']='light';backend.settingsChanged.emit();spin(150)
        root.grabWindow().save(str(output/'light.png'))
        root.setWidth(900);root.setHeight(680);spin(160);root.grabWindow().save(str(output/'small.png'))
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Cannot assign','Unable to assign','Binding loop','recursive rearrange'))]
        assert not errors,errors
        assert backend.graphics.engine.process is None
        print('PASS: four-tab themed settings, isolated save/reopen, light/dark/small layouts, no core/game launched')
    finally:
        backend.shutdownWatch();backend.graphics.pool.shutdown(wait=True);backend.pool.shutdown(wait=True);shiboken6.delete(engine)
