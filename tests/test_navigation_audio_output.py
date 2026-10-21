"""Real Qt output on its own thread, muted; GUI stalls must not interrupt PCM."""
from pathlib import Path
from types import SimpleNamespace
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
from input_feedback import InputFeedback

class Bridge(QObject):
    inputModeChanged=Signal();settingsChanged=Signal();audioSettingsChanged=Signal()
    controllerMode=False
    store=SimpleNamespace(settings={'navigation_sounds':True,'navigation_volume':80,'navigation_sound_style':'clear','library_design':'classic'})
    def setControllerMode(self,value):self.controllerMode=value;self.inputModeChanged.emit()

app=QApplication([]);bridge=Bridge()
feedback=InputFeedback(app,bridge,Path(__file__).resolve().parents[1],audio_muted=True)
audio=feedback.audio;states=[];played=[]
audio.inspected.connect(states.append);audio.played.connect(lambda kind,bank:played.append((kind,bank)))
window=QWidget();window.resize(340,150)
def wait(condition):
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.002)
        if condition():return
    raise AssertionError(('Audio deadline',states[-2:]))
def snapshot():
    count=len(states);audio.inspectRequested.emit();wait(lambda:len(states)>count);return states[-1]
try:
    window.show();window.activateWindow();window.raise_()
    wait(lambda:audio.ready and app.applicationState()==Qt.ApplicationActive)
    assert len(audio.sounds)==57
    before=snapshot();assert before['available'] and before['enabled']
    QTest.qWait(3200);after=snapshot()
    assert after['state']=='ActiveState' and after['processed']>before['processed']+2500000,(before,after)
    # A layout rebuild monopolises the GUI event loop, but the audio worker must run.
    feedback.play('switch',design='classic');QTest.qWait(40)
    before=snapshot();time.sleep(.35);after=snapshot()
    assert after['backend'].startswith('XAudio2')
    assert after['processed']>before['processed']+250000,(before,after)
    assert sum(after['samples'])>sum(before['samples'])+10000,(before,after)
    assert after['underruns']==before['underruns'],(before,after)
    for design in ('classic','shelf','cinema','atlas'):
        bridge.store.settings['library_design']=design
        for _ in range(8):feedback.play();QTest.qWait(60)
        feedback.play('group');QTest.qWait(100);feedback.play('confirm');QTest.qWait(100)
    QTest.qWait(650);assert snapshot()['voices']==0
    for bank in ('classic-clear','shelf','cinema','atlas'):
        assert ('move',bank) in played and ('group',bank) in played and ('confirm',bank) in played,played
    bridge.store.settings['navigation_sounds']=False;bridge.settingsChanged.emit()
    wait(lambda:not snapshot()['enabled']);assert snapshot()['state']=='StoppedState'
    bridge.store.settings['navigation_sounds']=True;bridge.settingsChanged.emit()
    wait(lambda:snapshot()['state']=='ActiveState')
    window.hide();wait(lambda:not snapshot()['enabled'])
    assert snapshot()['voices']==0
    print('PASS: 57 event banks; 350ms GUI freeze without PCM starvation; four layout voices, rapid movement, idle, settings/focus release; output muted')
finally:audio.shutdown();window.close()
