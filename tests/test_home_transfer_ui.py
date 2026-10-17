"""Exit backup states reach both recent-game tiles and their shared hero, without real games or DAV."""
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import ROOT, Store
from main import Bridge
from PySide6.QtCore import QObject, QPoint, QUrl, qInstallMessageHandler
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material')
app = QApplication([])
messages = []
qInstallMessageHandler(lambda kind, context, message: messages.append(message))


def spin_until(predicate, message):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError(message)


def value(obj, name):
    result = obj.property(name)
    return result.toVariant() if hasattr(result, 'toVariant') else result


def visual(item):
    yield item
    for child in item.childItems():
        yield from visual(child)


with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as directory:
    store = Store(directory, 'home-transfer')
    store.settings.update(setup_completed=True, guide_dismissed=True, watch=False, library='',
                          playnite='', tray_notifications=False, home_recent_preview=True)
    for ident, name, color in [('a', 'Exit upload fixture', '#564688'), ('b', 'Other game fixture', '#326779')]:
        cover = store.root / 'covers' / (ident + '.png')
        cover.parent.mkdir(exist_ok=True)
        image = QImage(300, 450, QImage.Format_RGB32)
        image.fill(QColor(color))
        assert image.save(str(cover))
        store.games.append({'id': ident, 'name': name, 'cover': cover.name,
                            'last_played': '2026-10-17T00:00:00Z', 'category': 'Other', 'tags': []})
        saves = Path(directory) / ident / 'SaveGames'
        saves.mkdir(parents=True)
        (saves / 'progress.sav').write_text('isolated progress')
        store.save_game(ident, {'save_dir': str(saves), 'installed': True})
    backend = Bridge(store)
    backend.timer.stop()
    backend._sessions.delay = 0
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml')))
    assert engine.rootObjects(), messages
    window = engine.rootObjects()[0]
    window.resize(1440, 900)
    window.requestActivate()
    QTest.mouseMove(window, QPoint(5, 5))
    QTest.qWait(200)

    def tiles(ident):
        return [item for item in visual(window.contentItem())
                if item.property('libraryTile') and (value(item, 'game') or {}).get('id') == ident]

    def check(ident, state):
        matches = tiles(ident)
        assert matches, ident
        for tile in matches:
            assert tile.property('transferState') == state
            action = tile.findChild(QObject, 'tileCloudAction')
            assert action.property('transferState') == state
            assert action.property('loading') == (state in ('saving', 'uploading'))
            badge = tile.findChild(QObject, 'tileTransferBadge')
            assert badge.property('visible') == (not tile.property('featured') and state != 'idle')
        return matches

    store.settings['watch'] = True
    gate = threading.Event()
    entered = threading.Event()
    original_backup = store.backup

    def backup(*args, **kwargs):
        entered.set()
        assert gate.wait(8), 'Backup gate timed out'
        return original_backup(*args, **kwargs)

    uploading = threading.Event()
    upload_gate = threading.Event()

    def upload(*args):
        uploading.set()
        assert upload_gate.wait(8), 'Upload gate timed out'

    try:
        with patch.object(store, 'backup', side_effect=backup), patch.object(store, 'upload', side_effect=upload):
            backend.receiveWatch({'a': True})
            backend.receiveWatch({'a': False})
            backend.receiveWatch({'a': False})
            spin_until(lambda: entered.is_set() and backend.transferStates.get('a') == 'saving', 'Saving state missing')
            matches = check('a', 'saving')
            assert any(tile.property('featured') for tile in matches)
            assert any(not tile.property('featured') for tile in matches)
            check('b', 'idle')
            gate.set()
            spin_until(lambda: uploading.is_set() and backend.transferStates.get('a') == 'uploading', 'Upload state missing')
            check('a', 'uploading')
            recent = next(item for item in visual(window.contentItem()) if item.objectName() == 'shelf-recent')
            recent.setProperty('currentIndex', 1)
            QTest.qWait(60)
            check('b', 'idle')
            assert next(tile for tile in tiles('b') if tile.property('featured')).property('transferState') == 'idle'
            recent.setProperty('currentIndex', 0)
            QTest.qWait(60)
            check('a', 'uploading')
            output = ROOT / 'test-data/home-transfer'
            output.mkdir(exist_ok=True)
            assert window.grabWindow().save(str(output / 'uploading.png'))
            upload_gate.set()
            spin_until(lambda: not backend._auto_active and backend.transferStates.get('a') == 'success', 'Success state missing')
            QTest.qWait(80)
            check('a', 'success')
            check('b', 'idle')

        with patch.object(store, 'upload', side_effect=ValueError('isolated offline fixture')):
            backend.receiveWatch({'a': False, 'b': True})
            backend.receiveWatch({'a': False, 'b': False})
            backend.receiveWatch({'a': False, 'b': False})
            spin_until(lambda: not backend._auto_active and backend.transferStates.get('b') == 'failed', 'Failure state missing')
            check('b', 'failed')
            check('a', 'success')
            assert len(store.history('b')) == 1
        with patch.object(store, 'upload') as retry:
            backend.retryAutoBackups()
            spin_until(lambda: not backend._auto_active and backend.transferStates.get('b') == 'success', 'Retry state missing')
            check('b', 'success')
            assert retry.call_count == 1 and len(store.history('b')) == 1

        errors = [message for message in messages if any(word in message for word in
                  ('TypeError', 'ReferenceError', 'Binding loop', 'Cannot assign', 'Unable to assign'))]
        assert not errors, errors
    finally:
        gate.set()
        upload_gate.set()
        backend.shutdownWatch()
        backend._watch_pool.shutdown(wait=True)
        backend.pool.shutdown(wait=True)
        shiboken6.delete(engine)

print('PASS: real exit-backup signals update hero and home cards through saving/upload/success/failure/retry; game selection stays isolated')
