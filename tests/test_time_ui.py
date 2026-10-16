"""Render actual local/cloud history using isolated fixtures, without backups or network."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import Store, ROOT
from main import Bridge
from PySide6.QtCore import QObject, QUrl, QMetaObject, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material')
app = QApplication([])
messages = []
qInstallMessageHandler(lambda kind, context, message: messages.append(message))


def spin():
    end = time.monotonic() + .4
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.005)


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as directory:
    store = Store(directory, 'local-time-ui')
    store.settings.update(setup_completed=True, guide_dismissed=True, watch=False, close_to_tray=False)
    backend = Bridge(store)
    local = [{'id':1, 'created_at':'2026-10-16T12:53:17+00:00', 'event':'manual', 'uploaded':1, 'note':'Local fixture'}]
    cloud = [{'created_at':'2026-10-16T23:53:17.123456789Z', 'computer':'Other device', 'note':'Cloud fixture', 'remote':'fixture'}]
    originals = deepcopy((local, cloud))
    backend._history = local
    backend._cloud_history = cloud
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml')))
    assert engine.rootObjects(), messages
    root = engine.rootObjects()[0]
    dialog = root.findChild(QObject, 'historyDialog')
    QMetaObject.invokeMethod(dialog, 'open')
    spin()
    tabs = root.findChild(QObject, 'historyTabs')
    for index, rows in enumerate((local, cloud)):
        tabs.setProperty('currentIndex', index)
        spin()
        labels = [item for item in walk(root.contentItem()) if item.objectName() == 'snapshotTime' and item.isVisible()]
        expected = datetime.fromisoformat(rows[0]['created_at'].replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
        assert len(labels) == 1 and labels[0].property('text') == expected, (index, expected, messages)
        if index == 0:
            output = ROOT / 'test-data/time-review'
            output.mkdir(exist_ok=True)
            root.grabWindow().save(str(output / 'history-local.png'))
    assert (local, cloud) == originals
    errors = [message for message in messages if any(word in message for word in ('TypeError', 'ReferenceError', 'Cannot assign', 'Unable to assign'))]
    assert not errors, errors
    backend.shutdownWatch()
    backend.pool.shutdown(wait=True)
    shiboken6.delete(engine)
print('PASS: local/cloud history uses computer timezone, midnight rollover, stored timestamps unchanged, isolated QML render')
