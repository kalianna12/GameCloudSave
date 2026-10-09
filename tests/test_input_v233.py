"""One focus across recycled shelves, animated navigation, cursor ownership and sound."""
from pathlib import Path
import sys, tempfile, time, math
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import Store, ROOT, RESOURCES
from main import Bridge
from gamepad import dispatch
from input_feedback import InputFeedback
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, Q_RETURN_ARG, QEvent, Qt, QPointF, qInstallMessageHandler
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material')
app = QApplication([])
messages = []
qInstallMessageHandler(lambda kind, context, message: messages.append(message))

def spin(ms=250):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents(); time.sleep(.005)

def invoke(obj, name, *values):
    return QMetaObject.invokeMethod(obj, name, Q_RETURN_ARG('QVariant'), *(Q_ARG('QVariant', v) for v in values))

def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as directory:
    store = Store(directory, 'input')
    store.settings.update(setup_completed=True, guide_dismissed=True, watch=False)
    categories = ['视觉小说', '角色扮演', '动作冒险', '射击竞技', '策略模拟']
    for i in range(80):
        store.games.append({'id': str(i), 'name': f'Game {i:02}', 'category': categories[i % 5],
                            'tags': [categories[i % 5]], 'series': f'Pair {i % 3}',
                            'last_played': f'2026-10-09T12:{i % 60:02}:00Z', 'cover': ''})
        store.local[str(i)] = {'installed': True}
    backend = Bridge(store)
    feedback = InputFeedback(app, backend, RESOURCES); backend.input_feedback = feedback
    engine = QQmlApplicationEngine(); engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml'))); assert engine.rootObjects()
    root = engine.rootObjects()[0]; root.requestActivate(); spin()
    home = root.findChild(QObject, 'libraryHome'); view = root.findChild(QObject, 'libraryHomeList')
    home.forceActiveFocus()

    def rings():
        return [item for item in walk(root.contentItem()) if item.objectName() == 'tileFocusRing' and item.isVisible() and item.property('focusWidth') > 2.5]

    with patch('winsound.PlaySound') as audio:
        dispatch(app, root, backend, 'right'); spin()
        assert backend.controllerMode and feedback.hidden and app.overrideCursor().shape() == Qt.BlankCursor
        assert len(rings()) == 1, len(rings())
        # Visit multiple rows in both directions; bindings must remain live after reuse.
        samples = []
        root.frameSwapped.connect(lambda: samples.append(view.property('contentY')))
        for command in ['down', 'down', 'down', 'down', 'up', 'up', 'up', 'up']:
            dispatch(app, root, backend, command); spin()
            assert len(rings()) == 1, (command, home.property('focusedSection'), len(rings()))
        assert len({round(y, 1) for y in samples if y > 1}) > 10, 'Vertical navigation must render intermediate positions'
        assert audio.call_count >= 9, audio.call_count
        backend.store.settings['navigation_sounds'] = False
        count = audio.call_count; dispatch(app, root, backend, 'right'); spin()
        assert audio.call_count == count
        # Stationary or synthesized mouse input cannot take ownership.
        root.requestActivate(); spin(80); backend.setControllerMode(True)
        anchor = QPointF(feedback.pointer)
        app.sendEvent(root, QMouseEvent(QEvent.MouseMove, QPointF(20,20), anchor, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert backend.controllerMode and feedback.hidden
        moved = anchor + QPointF(15, 0)
        app.sendEvent(root, QMouseEvent(QEvent.MouseMove, QPointF(35,20), moved, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert not backend.controllerMode and not feedback.hidden and app.overrideCursor() is None
        home.forceActiveFocus(); dispatch(app, root, backend, 'right'); spin()
        feedback.application_state(Qt.ApplicationInactive)
        assert not feedback.hidden and not backend.controllerMode
        root.requestActivate(); invoke(root, 'navigate', 'all', ''); spin()
        grid = root.findChild(QObject, 'gameGrid'); grid.forceActiveFocus()
        samples.clear(); root.frameSwapped.connect(lambda: samples.append(grid.property('contentY')))
        for _ in range(4): dispatch(app, root, backend, 'down'); spin()
        assert grid.property('contentY') > 0 and len({round(y, 1) for y in samples if y > 1}) > 8
        store.settings['animations'] = False; backend.settingsChanged.emit(); spin()
        dispatch(app, root, backend, 'up'); spin(25)
        assert math.isfinite(grid.property('contentY'))
    assert not any(term in message for message in messages for term in ['TypeError', 'ReferenceError', 'Binding loop', 'Cannot assign']), messages
    feedback.release_cursor(); app.removeEventFilter(feedback)
    backend.timer.stop(); backend.pool.shutdown(wait=True); shiboken6.delete(engine)
print('PASS: exclusive focus, home/grid intermediate frames, sound toggle, stationary mouse guard, real movement restore and deactivation')
