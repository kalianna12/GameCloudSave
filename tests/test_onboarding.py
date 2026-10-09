"""Exercise real QML onboarding, settings pages and cancelled layout changes."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from PySide6.QtCore import QObject, QMetaObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from services import Store, ROOT
from main import Bridge
import shiboken6

QQuickStyle.setStyle('Material')
app = QApplication([])
with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as directory:
    store = Store(directory, 'onboarding-test')
    backend = Bridge(store)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml')))
    assert engine.rootObjects(), 'QML did not load'
    window = engine.rootObjects()[0]
    guide = window.findChild(QObject, 'guideDialog')
    settings = window.findChild(QObject, 'settingsDialog')
    tabs = window.findChild(QObject, 'settingsTabs')
    app.processEvents()
    assert guide.property('visible'), 'First-run guide missing'
    QMetaObject.invokeMethod(window, 'openSettings')
    QTest.qWait(350)
    assert not guide.property('visible') and settings.property('visible')
    for index in range(4):
        tabs.setProperty('currentIndex', index)
        app.processEvents()
        assert tabs.property('currentIndex') == index
    window.setProperty('coverSize', 320)
    QMetaObject.invokeMethod(settings, 'reject')
    app.processEvents()
    assert window.property('coverSize') == store.settings['cover_size'], 'Cancel kept preview'
    backend.saveSettings({'guide_dismissed': True, 'watch_upload': False})
    reload = Store(directory, 'onboarding-test')
    assert reload.settings['guide_dismissed'] and not reload.settings['watch_upload']
    QMetaObject.invokeMethod(guide, 'open')
    app.processEvents()
    assert guide.property('visible'), 'Guide cannot reopen'
    window.setWidth(900)
    window.setHeight(650)
    app.processEvents()
    assert guide.property('height') <= 590
    backend.timer.stop()
    backend.pool.shutdown(wait=True)
    shiboken6.delete(engine)
print('PASS: first-run guide, four settings pages, cancel rollback, persistence, guide reopening, small window')
