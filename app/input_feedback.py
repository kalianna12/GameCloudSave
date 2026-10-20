"""Switch input ownership on real input, without polling the mouse or audio."""
import time
from pathlib import Path
from PySide6.QtCore import QObject, QEvent, Qt, QUrl
from PySide6.QtGui import QCursor


class InputFeedback(QObject):
    def __init__(self, app, bridge, resources):
        super().__init__(app)
        self.app, self.bridge = app, bridge
        self.pointer = QCursor.pos()
        self.hidden = False
        self.last_sound = 0.0
        from PySide6.QtMultimedia import QSoundEffect
        self.sounds={}
        for style in ('clear','soft','arcade'):
            for kind in ('move','confirm','back','open'):
                effect=QSoundEffect(self);effect.setSource(QUrl.fromLocalFile(str(Path(resources)/'ui/sounds'/(style+'-'+kind+'.wav'))));self.sounds[style,kind]=effect
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

    def play(self,kind='move',style=None,volume=None):
        if not self.bridge.store.settings.get('navigation_sounds', True):
            return
        now = time.monotonic()
        if now - self.last_sound < (.045 if kind=='move' else .025):
            return
        self.last_sound = now
        style=style or self.bridge.store.settings.get('navigation_sound_style','clear')
        effect=self.sounds.get((style,kind),self.sounds['clear','move'])
        level=self.bridge.store.settings.get('navigation_volume',80) if volume is None else volume
        effect.setVolume(max(0,min(100,level))/100);effect.play()
