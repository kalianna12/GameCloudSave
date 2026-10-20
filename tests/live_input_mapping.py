"""Opt-in real SendInput to this test's own window and real neutralized ViGEm device."""
from pathlib import Path
import sys,time,os,json,ctypes,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from input_mapping import MappingController
from mapping_native import WindowsInput,KeyOutput,VirtualPad,RawMouse
from mapping_model import default_profile,Forward,Reverse
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest

app=QApplication([])
temporary=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
recorder=MappingController(Store(temporary.name,'native-recording'))
class Target(QWidget):
    def __init__(self):
        super().__init__();self.events=[];self.setMouseTracking(True);self.setWindowTitle('GameCloudSave isolated input verification');self.resize(640,400)
    def keyPressEvent(self,event):self.events.append(('down',event.key()))
    def keyReleaseEvent(self,event):self.events.append(('up',event.key()))
    def mousePressEvent(self,event):self.events.append(('mouse-down',event.button().value))
    def mouseReleaseEvent(self,event):self.events.append(('mouse-up',event.button().value))
    def wheelEvent(self,event):self.events.append(('wheel',event.angleDelta().y()))
window=Target();window.show();window.activateWindow();window.raise_();QTest.qWait(200)
recorder.bindWindow(window)
transport=WindowsInput();output=KeyOutput(transport);virtual=None;old=QCursor.pos();raw=RawMouse()
report={}
try:
    # Only activate this test's own window; never inject into an unrelated app.
    from ctypes import wintypes as W
    user=ctypes.windll.user32;kernel=ctypes.windll.kernel32
    user.GetForegroundWindow.restype=W.HWND
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    user.SetForegroundWindow.argtypes=[W.HWND]
    user.SetActiveWindow.argtypes=[W.HWND]
    user.SetFocus.argtypes=[W.HWND]
    user.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
    foreground=user.GetForegroundWindow();thread=user.GetWindowThreadProcessId(foreground,None);own=kernel.GetCurrentThreadId()
    attached=bool(thread and thread!=own and user.AttachThreadInput(own,thread,True))
    try:
        user.SetWindowPos(int(window.winId()),-1,0,0,0,0,0x43)
        user.SetForegroundWindow(int(window.winId()));user.SetActiveWindow(int(window.winId()));user.SetFocus(int(window.winId()))
    finally:
        if attached:user.AttachThreadInput(own,thread,False)
    QTest.qWait(150)
    assert window.isActiveWindow() and transport.foreground()[1]==os.getpid(),'Test target did not acquire focus; no inputs sent'
    raw.start(int(window.winId()));raw.stop();report['raw_input_registration']=True
    initial={token:transport.held(token) for token in ('K:162','K:160','K:128')}
    assert not any(initial.values()),'Real keys are already held; test refused'
    output.update({'K:162','K:160','K:128'},[0,0],time.perf_counter());QTest.qWait(200);owned=set(output.owned);output.release();QTest.qWait(250)
    assert ('down',Qt.Key_F17) in window.events and ('up',Qt.Key_F17) in window.events,(window.events,owned,output.owned,transport.foreground(),window.isActiveWindow())
    report['native_combo_and_keyup']=True
    assert transport.foreground()[1]==os.getpid(),'Target focus changed; capture test refused'
    recorder.record();output.update({'K:161','K:163','K:128'},[0,0],time.perf_counter());QTest.qWait(100);output.release();QTest.qWait(150)
    assert set(recorder.currentChord)=={'K:161','K:163','K:128'},recorder.currentChord
    report['native_right_modifier_recording']=True
    recorder.bindWindow(window)
    QCursor.setPos(window.mapToGlobal(window.rect().center()));QTest.qWait(30)
    for token in ('K:13','K:38','K:40','K:37','K:39','M:left','M:right','M:middle','M:x1','M:x2'):
        assert transport.foreground()[1]==os.getpid(),'Capture target lost focus; no inputs sent'
        before=len(window.events);recorder.record()
        output.update({token},[0,0],time.perf_counter());QTest.qWait(40);output.release();QTest.qWait(50)
        assert recorder.currentChord==[token] and not recorder.state['recording'],(token,recorder.currentChord)
        assert len(window.events)==before,window.events[before:]
    for direction in ('wheelup','wheeldown'):
        assert transport.foreground()[1]==os.getpid(),'Wheel capture target lost focus; no inputs sent'
        before=len(window.events);recorder.record()
        output.update({'K:162'},[0,0],time.perf_counter());QTest.qWait(30)
        output.update({'K:162'},[0,0],time.perf_counter(),[direction]);QTest.qWait(30)
        assert recorder.state['recording']
        output.release();QTest.qWait(60)
        assert recorder.currentChord==['K:162','M:'+direction] and not recorder.state['recording'],recorder.currentChord
        assert len(window.events)==before,window.events[before:]
    report['native_recording_enter_arrows_mouse_wheel_no_ui_leak']=True
    QTest.qWait(220)  # Let the captured wheel gesture's tail expire.
    if '--capture-only' in sys.argv:
        print('PASS: owned-window native keyboard/mouse/wheel capture without UI leakage: '+json.dumps(report),flush=True)
        raise SystemExit(0)
    assert transport.foreground()[1]==os.getpid(),'Target focus changed; mouse test refused'
    QCursor.setPos(window.mapToGlobal(window.rect().center()));QTest.qWait(30);start=QCursor.pos()
    output.update(set(),[12,6],time.perf_counter());QTest.qWait(60)
    assert QCursor.pos()!=start;report['native_relative_mouse']=True
    assert transport.foreground()[1]==os.getpid(),'Target focus changed; wheel test refused'
    profile=default_profile();profile['forward']['sticks']['LS']['mode']='wheel';forward=Forward()
    desired,move=forward.frame(profile,{'buttons':[],'LS':[0,.5],'RS':[0,0]},.008)
    output.update(desired,move,time.perf_counter(),forward.wheel_steps);QTest.qWait(40)
    assert ('wheel',120) in window.events,window.events
    forward.frame(profile,{'buttons':[],'LS':[0,0],'RS':[0,0]},.008);assert not forward.wheel_steps
    report['native_stick_to_wheel_and_neutral']=True
    virtual=VirtualPad();slot=virtual.index;virtual.update({'buttons':0x1100,'LT':128,'RT':0,'LX':12000,'LY':20000,'RX':0,'RY':0});QTest.qWait(80)
    state,index=transport.sample(slot)
    assert index==slot and {'A','LB','LT'}.issubset(state['buttons']) and abs(state['LS'][0]-12000/32767)<.01
    virtual.release();QTest.qWait(40);state,index=transport.sample(slot);assert not state['buttons'] and state['LS']==[0.,0.]
    profile['reverse'].update(mouse='disabled',ramp=0,routes=[{'id':'wheel','source':['M:wheelup'],'targets':['P:RY+']}]);reverse=Reverse()
    virtual.update(reverse.frame(profile,{'M:wheelup'},[0,0],.008));QTest.qWait(30)
    assert transport.sample(slot)[0]['RS'][1]>.99
    virtual.update(reverse.frame(profile,set(),[0,0],.008));QTest.qWait(30)
    assert transport.sample(slot)[0]['RS']==[0.,0.];report['wheel_to_virtual_stick_xinput_and_neutral']=True
    # Real XInput 30 ms presses, with a deliberate GUI stall. No SendInput is enabled.
    import threading
    from mapping_clock import PollClock
    def pump(ms):
        end=time.perf_counter()+ms/1000
        while time.perf_counter()<end:app.processEvents();time.sleep(.002)
    recorder.setSlot(slot);recorder.setAutoSelect(False);recorder.setEditorVisible(True);pump(60);recorder.clearEvents()
    failures=[];count=20;hold=.03
    def pulse():
        clock=PollClock();wake=threading.Event()
        try:
            for _ in range(count):
                if transport.foreground()[1]!=os.getpid():raise RuntimeError('Own test window lost foreground; pulse test stopped')
                virtual.update({'buttons':0x1000,'LT':0,'RT':0,'LX':0,'LY':0,'RX':0,'RY':0});clock.wait(hold,wake)
                virtual.release();clock.wait(hold,wake)
        except Exception as error:failures.append(str(error))
        finally:virtual.release();clock.close()
    before=recorder._capture_count;started=time.perf_counter();producer=threading.Thread(target=pulse);producer.start()
    time.sleep(.18)  # Capture must keep both edges while Qt cannot render.
    while producer.is_alive():pump(5)
    producer.join();pump(80);elapsed=time.perf_counter()-started
    assert not failures,failures
    assert recorder.history.pressCounts.get('P:A',0)==count,(recorder.history.pressCounts,recorder._capture_count-before,elapsed)
    assert sum(row['key']=='A' and not row['down'] for row in recorder.history.rows)==count,recorder.history.rows
    rate=round((recorder._capture_count-before)/elapsed,1)
    assert rate>100,rate
    report['30ms_presses_captured_during_gui_stall']=count
    hold=.015;recorder.clearEvents();producer=threading.Thread(target=pulse);producer.start();time.sleep(.18)
    while producer.is_alive():pump(5)
    producer.join();pump(80);assert not failures,failures
    assert recorder.history.pressCounts.get('P:A',0)==count,recorder.history.pressCounts
    assert sum(row['key']=='A' and not row['down'] for row in recorder.history.rows)==count,recorder.history.rows
    report['30ms_full_cycle_presses_captured_during_gui_stall']=count
    recorder.setEditorVisible(False)
    report['editor_capture_hz']=rate
    virtual.close();virtual=None;QTest.qWait(40);assert transport.sample(slot)[0] is None
    report['virtual_xinput_buttons_triggers_axes_reset_detach']=True
finally:
    output.release();raw.stop()
    if virtual:virtual.close()
    if transport.foreground()[1]==os.getpid():QCursor.setPos(old)
    window.close()
    recorder.shutdown();temporary.cleanup()
folder=ROOT/'test-data/input-mapping';folder.mkdir(exist_ok=True)
(folder/'native-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS: '+json.dumps(report))
