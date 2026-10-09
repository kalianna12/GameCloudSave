"""Switch input ownership on real input, without polling the mouse or audio."""
import time
from pathlib import Path
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QCursor


class InputFeedback(QObject):
    def __init__(self, app, bridge, resources):
        super().__init__(app)
        self.app, self.bridge = app, bridge
        self.pointer = QCursor.pos()
        self.hidden = False
        self.last_sound = 0.0
        self.sound = str(Path(resources) / 'ui/sounds/navigation.wav')
        bridge.inputModeChanged.connect(self.sync_cursor)
        app.applicationStateChanged.connect(self.application_state)
        app.aboutToQuit.connect(self.release_cursor)
        app.installEventFilter(self)

    def sync_cursor(self):
        if self.bridge.controllerMode and self.app.applicationState() == Qt.ApplicationActive:
            if not self.hidden:
                self.pointer = QCursor.pos()
                self.app.setOverrideCursor(QCursor(Qt.BlankCursor))
                self.hidden = True
        else:
            self.release_cursor()

    def release_cursor(self):
        if self.hidden:
            self.app.restoreOverrideCursor()
            self.hidden = False

    def application_state(self, state):
        if state != Qt.ApplicationActive:
            self.bridge.setControllerMode(False)
        self.sync_cursor()

    def eventFilter(self, watched, event):
        if not self.bridge.controllerMode:
            return False
        kind = event.type()
        if kind in (QEvent.HoverEnter, QEvent.HoverMove, QEvent.HoverLeave):
            return True
        if kind in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            if event.source() != Qt.MouseEventNotSynthesized:
                return True
            position = event.globalPosition().toPoint()
            if kind == QEvent.MouseMove and (position - self.pointer).manhattanLength() < 3:
                return True
            self.pointer = position
            self.bridge.setControllerMode(False)
        elif kind in (QEvent.Wheel, QEvent.TouchBegin):
            self.bridge.setControllerMode(False)
        return False

    def play(self):
        if not self.bridge.store.settings.get('navigation_sounds', True):
            return
        now = time.monotonic()
        if now - self.last_sound < .075:
            return
        self.last_sound = now
        try:
            import winsound
            winsound.PlaySound(self.sound, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except (ImportError, OSError, RuntimeError):
            pass
