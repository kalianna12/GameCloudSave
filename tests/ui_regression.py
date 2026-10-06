"""Render real imported covers and exercise QML search, layout and settings."""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, qInstallMessageHandler, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication
import shiboken6
from main import Bridge
from services import Store, ROOT

warnings = []
qInstallMessageHandler(lambda kind, context, message: warnings.append(message))
app = QApplication([])
QQuickStyle.setStyle('Material')
bridge = Bridge(Store())
bridge.timer.stop()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty('backend', bridge)
engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml')))
assert engine.rootObjects(), warnings
window = engine.rootObjects()[0]
QCursor.setPos(window.position() + QPoint(20,20))
def settle(seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
def capture(name):
    assert window.grabWindow().save(str(ROOT / 'test-data' / name))

settle(2)
grid = window.findChild(QObject, 'gameGrid')
search = window.findChild(QObject, 'search')
assert grid.property('count') == 51
capture('library-v1.png')
search.setProperty('text', '9-nine')
settle()
assert grid.property('count') == 5
search.setProperty('text', '无法匹配的中文测试名称')
settle()
assert grid.property('count') == 0
search.setProperty('text', '')
window.setProperty('width', 900)
window.setProperty('height', 680)
window.setProperty('columnCount', 10)
window.setProperty('gridGap', 48)
settle()
assert grid.property('cardWidth') >= 196
capture('library-small.png')
window.setProperty('width', 1440)
window.setProperty('height', 940)
window.setProperty('columnCount', 0)
window.setProperty('gridGap', 22)
assert QMetaObject.invokeMethod(window, 'openSettings')
settle()
assert window.findChild(QObject, 'settingsDialog').property('visible')
capture('settings-v1.png')
QMetaObject.invokeMethod(window.findChild(QObject, 'settingsDialog'), 'close')
assert QMetaObject.invokeMethod(window, 'openGame', Q_ARG('QVariant', bridge.games[0]))
settle()
assert window.findChild(QObject, 'gameDialog').property('visible')
capture('game-settings-v1.png')
QMetaObject.invokeMethod(window.findChild(QObject, 'gameDialog'), 'close')
QMetaObject.invokeMethod(window.findChild(QObject, 'historyDialog'), 'open')
settle()
capture('cloud-v1.png')
bridge.pool.shutdown(wait=True)
shiboken6.delete(engine)
assert not warnings, '\n'.join(warnings)
print('PASS: QML load, 51 covers, search, empty search, narrow resize, dense layout, system/game/cloud dialogs; zero Qt warnings')
