"""Exercise import preview, idle watcher and close-to-tray in real QML."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QMetaObject,QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from services import Store,ROOT
from main import Bridge
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    store=Store(temporary,'UI-test');store.settings['guide_dismissed']=True
    backend=Bridge(store)
    assert not backend.timer.isActive(), 'Idle watcher should not wake up'
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects()
    window=engine.rootObjects()[0];QMetaObject.invokeMethod(window,'openImport');QTest.qWait(200)
    importer=window.findChild(QObject,'importWindow');assert importer.property('visible')
    folder=Path(temporary)/'games/Example';folder.mkdir(parents=True);(folder/'Example.exe').write_bytes(b'fixture')
    backend.scanImports(str(folder.parent),6)
    for _ in range(100):
        QTest.qWait(25)
        if not backend.busy:break
    assert len(backend.importCandidates)==1
    backend.importSelected([backend.importCandidates[0]['id']])
    for _ in range(100):
        QTest.qWait(25)
        if not backend.busy:break
    assert len(backend.games)==1 and backend.games[0]['platform']=='local'
    backend.poll();assert not backend.busy and not backend._watch_pending
    with patch('main.QSystemTrayIcon.isSystemTrayAvailable',return_value=True):
        QMetaObject.invokeMethod(window,'close');QTest.qWait(200)
        assert not window.property('visible') and not importer.property('visible')
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: real QML import preview/selection, idle listener does no polling, closing hides all windows for tray')
