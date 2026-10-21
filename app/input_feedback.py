"""Switch input ownership on real input, without polling the mouse or audio."""
import time
from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtGui import QCursor


class InputFeedback(QObject):
    def __init__(self, app, bridge, resources, *, audio_muted=False):
        super().__init__(app)
        self.app, self.bridge = app, bridge
        self.pointer = QCursor.pos()
        self.hidden = False
        self.last_sound = {}
        from navigation_audio import NavigationAudio
        self.audio=NavigationAudio(resources,self,muted=audio_muted)
        bridge.settingsChanged.connect(self.sync_audio)
        bridge.inputModeChanged.connect(self.sync_cursor)
        app.applicationStateChanged.connect(self.application_state)
        app.aboutToQuit.connect(self.release_cursor)
        app.aboutToQuit.connect(self.audio.shutdown)
        app.installEventFilter(self)
        self.sync_audio()

    def sync_audio(self):
        settings=self.bridge.store.settings
        self.audio.set_enabled(self.app.applicationState()==Qt.ApplicationActive and settings.get('navigation_sounds',True) and settings.get('navigation_volume',80)>0)

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
        self.sync_audio()

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

    def play(self,kind='move',style=None,volume=None,design=None):
        if not self.bridge.store.settings.get('navigation_sounds', True):
            return
        now = time.monotonic()
        if kind=='move' and now-max(self.last_sound.get('switch',0),self.last_sound.get('group',0))<.09:return
        if now - self.last_sound.get(kind,0) < (.055 if kind=='move' else .08 if kind in ('switch','group') else .025):
            return
        self.last_sound[kind] = now
        style=style or self.bridge.store.settings.get('navigation_sound_style','clear')
        design=design or self.bridge.store.settings.get('library_design','classic')
        bank=design if design in ('shelf','cinema','atlas') else 'classic-'+style
        level=self.bridge.store.settings.get('navigation_volume',80) if volume is None else volume
        if level<=0:return
        # A settings preview can be audible even while the saved volume is muted.
        if volume is not None and self.app.applicationState()==Qt.ApplicationActive:
            self.audio.set_enabled(True);QTimer.singleShot(300,self.sync_audio)
        self.audio.play(kind,bank,max(0,min(100,level)))
