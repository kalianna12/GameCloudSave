"""Foreground-only Windows XInput navigation with bounded repeat and hot-plug polling."""
import ctypes,time
from PySide6.QtCore import QObject,QTimer,Qt,Signal,Slot,QMetaObject,Q_ARG,Q_RETURN_ARG

def dispatch(app,root,bridge,command):
    window=app.focusWindow()
    if window is None:return
    mapping=getattr(bridge,'mapping',None)
    if mapping is not None and window is mapping._host:return
    bridge.setControllerMode(True)
    popup=bridge.active_popup()
    target=popup.parent() if popup is not None else window.activeFocusItem() if hasattr(window,'activeFocusItem') else None
    themed_combo=False
    while target is not None and not target.inherits('QQuickWindow'):
        if target.inherits('QQuickComboBox') and target.property('soundEvent'):themed_combo=True;break
        target=target.parent()
    if bridge.input_feedback and command in ('activate','menu','back') and not (command=='activate' and themed_combo):
        bridge.input_feedback.play('back' if command=='back' else 'open' if command=='menu' else 'confirm')
    if popup is not None and popup.metaObject().indexOfMethod('controllerInput(QVariant)')>=0:
        if QMetaObject.invokeMethod(popup,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant',command)):return
    target=popup.parent() if popup is not None else window.activeFocusItem() if hasattr(window,'activeFocusItem') else None
    while target is not None and not target.inherits('QQuickWindow'):
        if target.inherits('QQuickComboBox') and target.metaObject().indexOfMethod('controllerInput(QVariant)')>=0:
            if QMetaObject.invokeMethod(target,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant',command)):return
        target=target.parent()
    # Only explicit controller windows/popups, the library and combo lists are supported.
    # Never synthesize Tab/Space into native file pickers or mouse-only editors.
    if window!=root:
        if popup is None and window.metaObject().indexOfMethod('controllerInput(QVariant)')>=0:
            if QMetaObject.invokeMethod(window,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant',command)):return
        if command=='back':
            if popup is not None:QMetaObject.invokeMethod(popup,'close')
            else:
                window.close()
                QMetaObject.invokeMethod(root,'returnFromTool')
        return
    if command=='back':
        if popup is not None:
            method='reject' if popup.metaObject().indexOfMethod('reject()')>=0 else 'close'
            QMetaObject.invokeMethod(popup,method);return
    if popup is not None:return
    QMetaObject.invokeMethod(root,'controllerInput',Q_RETURN_ARG('QVariant'),Q_ARG('QVariant',command))

class Pad(ctypes.Structure):
    _fields_=[('buttons',ctypes.c_uint16),('left_trigger',ctypes.c_uint8),('right_trigger',ctypes.c_uint8),
              ('lx',ctypes.c_int16),('ly',ctypes.c_int16),('rx',ctypes.c_int16),('ry',ctypes.c_int16)]
class State(ctypes.Structure):
    _fields_=[('packet',ctypes.c_uint32),('pad',Pad)]

class Mapper:
    BUTTONS={0x1000:'activate',0x2000:'back',0x4000:'favorite',0x8000:'history',0x100:'previous',0x200:'next',0x10:'menu',0x20:'search',0x80:'case'}
    def __init__(self):self.reset()
    def reset(self):self.buttons=0;self.direction='';self.repeat_at=0;self.zoom_direction='';self.zoom_repeat_at=0
    def read(self,pad,now):
        pressed=pad.buttons&~self.buttons;self.buttons=pad.buttons
        commands=[command for mask,command in self.BUTTONS.items() if pressed&mask]
        direction=''
        if pad.buttons&1 and not pad.buttons&2:direction='up'
        elif pad.buttons&2 and not pad.buttons&1:direction='down'
        elif pad.buttons&4 and not pad.buttons&8:direction='left'
        elif pad.buttons&8 and not pad.buttons&4:direction='right'
        elif max(abs(pad.lx),abs(pad.ly))>7849:
            direction=('right' if pad.lx>0 else 'left') if abs(pad.lx)>=abs(pad.ly) else ('up' if pad.ly>0 else 'down')
        if direction!=self.direction:
            self.direction=direction;self.repeat_at=now+.28
            if direction:commands.append(direction)
        elif direction and now>=self.repeat_at:
            commands.append(direction);self.repeat_at=now+.085
        # Independent from left-stick/D-pad navigation; hysteresis prevents
        # tiny stick drift from repeatedly starting or reversing zoom.
        zoom='zoom-in' if pad.ry>10000 else 'zoom-out' if pad.ry< -10000 else ''
        if not zoom and abs(pad.ry)>6500 and self.zoom_direction:
            if (pad.ry>0)==(self.zoom_direction=='zoom-in'):zoom=self.zoom_direction
        if zoom!=self.zoom_direction:
            self.zoom_direction=zoom;self.zoom_repeat_at=now+.08
            if zoom:commands.append(zoom)
        elif zoom and now>=self.zoom_repeat_at:
            commands.append(zoom);self.zoom_repeat_at=now+.08
        return commands

class Gamepad(QObject):
    command=Signal(str)
    tilt=Signal(float,float)
    connectedChanged=Signal(bool)
    sampleReady=Signal()
    def __init__(self,app,enabled=lambda:True,exclude=lambda:-1,*,threaded=True,query=None):
        super().__init__(app);self.app=app;self.enabled=enabled;self.exclude=exclude;self.slot=None;self.mapper=Mapper();self.query=None;self.primed=False
        self._tilt=(0.,0.)
        self.query=query
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer);self.timer.timeout.connect(self.poll)
        for library in ('xinput1_4.dll','xinput9_1_0.dll'):
            if self.query:break
            try:
                function=ctypes.WinDLL(library).XInputGetState
                function.argtypes=[ctypes.c_uint32,ctypes.POINTER(State)];function.restype=ctypes.c_uint32
                self.query=function;break
            except (OSError,AttributeError):pass
        self.sampler=None;self._closed=False
        if threaded and self.query:
            from gamepad_sampling import GamepadSampler
            self.sampleReady.connect(self.poll,Qt.QueuedConnection)
            self.sampler=GamepadSampler(self.query,self.sampleReady.emit)
        app.applicationStateChanged.connect(self.sync)
        app.aboutToQuit.connect(self.shutdown)
        if self.query:self.sync()
    def sync(self,*args):
        self.mapper.reset();self.primed=False
        self._excluded=self.exclude()
        if self._tilt!=(0.,0.):self._tilt=(0.,0.);self.tilt.emit(0.,0.)
        if self.sampler:
            active=not self._closed and self.enabled() and self.app.applicationState()==Qt.ApplicationActive
            self.sampler.configure(active,self._excluded)
            if not self.enabled() and self.slot is not None:self.slot=None;self.connectedChanged.emit(False)
            return
        if self.query and self.enabled() and self.app.applicationState()==Qt.ApplicationActive:
            self.timer.start(16 if self.slot is not None else 500)
        else:
            self.timer.stop()
            if not self.enabled() and self.slot is not None:self.slot=None;self.connectedChanged.emit(False)
    @Slot()
    def poll(self):
        if self._closed:return
        if not self.enabled() or self.app.applicationState()!=Qt.ApplicationActive:
            self.sync();return
        if self.sampler:
            slot,tilt,commands,ready=self.sampler.take()
            if not ready:return
            if slot is not None and slot==self.exclude():self.sync();return
            if (slot is not None)!=(self.slot is not None):self.connectedChanged.emit(slot is not None)
            self.slot=slot
            if tilt!=self._tilt:self._tilt=tilt;self.tilt.emit(*tilt)
            for command in commands:
                if self._closed or not self.enabled() or self.app.applicationState()!=Qt.ApplicationActive:break
                self.command.emit(command)
            return
        indices=[self.slot] if self.slot is not None else range(4)
        for index in indices:
            if index==self.exclude():continue
            state=State()
            if self.query(index,ctypes.byref(state))==0:
                if self.slot is None:
                    self.slot=index;self.mapper.reset();self.mapper.buttons=state.pad.buttons
                    self.timer.start(16);self.connectedChanged.emit(True)
                if not self.primed:self.mapper.buttons=state.pad.buttons;self.primed=True
                def axis(value):return round((1 if value>0 else -1)*max(0,(abs(value)/32767-.12)/.88),3)
                tilt=(axis(state.pad.rx),axis(state.pad.ry))
                if tilt!=self._tilt:self._tilt=tilt;self.tilt.emit(*tilt)
                for command in self.mapper.read(state.pad,time.monotonic()):self.command.emit(command)
                return
        if self.slot is not None:self.connectedChanged.emit(False)
        self.slot=None;self.mapper.reset();self.timer.start(500)
        if self._tilt!=(0.,0.):self._tilt=(0.,0.);self.tilt.emit(0.,0.)

    def shutdown(self):
        self._closed=True;self.timer.stop()
        if self.sampler:self.sampler.close()

    @Slot()
    def refreshExclusion(self):
        if not self._closed and self.exclude()!=getattr(self,'_excluded',-1):self.sync()
