"""No auto-repeat toggling, desktop/minimize restoration loops or repeated activation."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,QEvent,Qt,qInstallMessageHandler
from PySide6.QtGui import QWindow,QKeyEvent
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.003)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'fullscreen-lifecycle');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(150);events=[];root.visibilityChanged.connect(lambda v:events.append(v))
    shortcut=root.findChild(QObject,'fullscreenShortcut');assert shortcut.property('autoRepeat') is False
    try:
        for _ in range(3):
            QMetaObject.invokeMethod(root,'toggleFullScreen');spin(120);assert root.visibility()==QWindow.FullScreen
            root.requestActivate();spin(40)
            for _ in range(12):app.sendEvent(root,QKeyEvent(QEvent.KeyPress,Qt.Key_F11,Qt.NoModifier,'',True,1))
            spin(100);assert root.property('fullScreenMode')
            root.showMinimized();spin(100);before=len(events)
            for _ in range(10):QMetaObject.invokeMethod(root,'returnFromTool')
            spin(160);assert root.visibility()==QWindow.Minimized and len(events)==before,events
            for _ in range(10):QMetaObject.invokeMethod(root,'restoreLibraryWindow')
            spin(220);assert root.visibility()==QWindow.FullScreen,(root.visibility(),root.property('fullScreenMode'),root.isActive(),events,messages)
            assert len(events)-before<=2,events
            QMetaObject.invokeMethod(root,'toggleFullScreen');spin(160);assert root.visibility()==QWindow.Windowed
        root.showMaximized();spin(100);QMetaObject.invokeMethod(root,'toggleFullScreen');spin(130)
        QMetaObject.invokeMethod(root,'toggleFullScreen');spin(170);assert root.visibility()==QWindow.Maximized
        errors=[m for m in messages if any(word in m for word in ('TypeError','ReferenceError','Binding loop'))]
        assert not errors,errors
    finally:backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: repeated fullscreen/minimize/explicit restore, F11 auto-repeat rejection, bounded visibility changes and maximized restoration')
