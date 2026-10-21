"""Exercise the real Qt output silently, including idle, rapid events and settings."""
from pathlib import Path
from types import SimpleNamespace
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtMultimedia import QtAudio
from PySide6.QtTest import QTest
from input_feedback import InputFeedback

class Bridge(QObject):
    inputModeChanged=Signal();settingsChanged=Signal()
    controllerMode=False
    store=SimpleNamespace(settings={'navigation_sounds':True,'navigation_volume':80,'navigation_sound_style':'soft'})
    def setControllerMode(self,value):self.controllerMode=value;self.inputModeChanged.emit()

app=QApplication([]);bridge=Bridge();feedback=InputFeedback(app,bridge,Path(__file__).resolve().parents[1])
assert feedback.audio.sink is not None,'This hardware test requires an audio output'
# Mute the sink before opening a window. Still render all voices through the real backend.
feedback.audio.sink.setVolume(0)
window=QWidget();window.resize(340,150);window.show();window.activateWindow();window.raise_();QTest.qWait(250)
assert app.applicationState()==Qt.ApplicationActive
audio=feedback.audio;assert audio.enabled and len(audio.sounds)==12
sink=audio.sink;before=sink.processedUSecs();QTest.qWait(3200)
assert sink.state()==QtAudio.ActiveState and sink.processedUSecs()>before+2500000,(sink.state(),sink.error())
for _ in range(50):feedback.play();QTest.qWait(30)
feedback.play('confirm');assert len(audio.stream.mixer.voices)>=1
QTest.qWait(250);assert not audio.stream.mixer.voices
assert sink is audio.sink and sink.state()==QtAudio.ActiveState
bridge.store.settings['navigation_sounds']=False;bridge.settingsChanged.emit()
assert not audio.enabled and sink.state()==QtAudio.StoppedState
feedback.play();assert not audio.stream.mixer.voices
bridge.store.settings['navigation_sounds']=True;bridge.settingsChanged.emit();QTest.qWait(80)
assert audio.enabled and sink.state()==QtAudio.ActiveState
window.hide();QTest.qWait(150)
assert app.applicationState()!=Qt.ApplicationActive
assert not audio.enabled and not audio.stream.mixer.voices
audio.shutdown();window.close()
print('PASS: real Qt sink stays warm after idle; 50 rapid moves and confirm drain smoothly; mute/focus release; speakers muted')
