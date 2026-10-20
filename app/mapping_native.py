"""Windows input transport. Imported without starting hooks or creating virtual devices."""
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import os
import threading

from PySide6.QtCore import QAbstractNativeEventFilter
from mapping_model import MODIFIERS,pad_state

ULONG_PTR=C.c_size_t
class KEYBDINPUT(C.Structure):_fields_=[('wVk',W.WORD),('wScan',W.WORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',ULONG_PTR)]
class MOUSEINPUT(C.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',ULONG_PTR)]
class HARDWAREINPUT(C.Structure):_fields_=[('uMsg',W.DWORD),('wParamL',W.WORD),('wParamH',W.WORD)]
class UNION(C.Union):_fields_=[('ki',KEYBDINPUT),('mi',MOUSEINPUT),('hi',HARDWAREINPUT)]
class INPUT(C.Structure):_anonymous_=('data',);_fields_=[('type',W.DWORD),('data',UNION)]
MARKER=0x4743534D


class WindowsInput:
    def __init__(self):
        self.user=C.WinDLL('user32',use_last_error=True)
        self.user.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int];self.user.SendInput.restype=W.UINT
        self.user.GetForegroundWindow.restype=W.HWND
        self.user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        self.user.GetAsyncKeyState.argtypes=[C.c_int];self.user.GetAsyncKeyState.restype=C.c_short
        self.user.GetKeyboardLayout.restype=W.HKL
        self.user.MapVirtualKeyExW.argtypes=[W.UINT,W.UINT,W.HKL];self.user.MapVirtualKeyExW.restype=W.UINT
        self.reader=None
        self._sample_cache={}
        for library in ('xinput1_4.dll','xinput9_1_0.dll'):
            try:
                from gamepad import State
                dll=C.WinDLL(library);self.reader=dll.XInputGetState;self.reader.argtypes=[W.DWORD,C.POINTER(State)];self.reader.restype=W.DWORD;break
            except OSError:pass

    def held(self,token):
        mouse={'left':1,'right':2,'middle':4,'x1':5,'x2':6}
        vk=int(token[2:]) if token.startswith('K:') else mouse.get(token[2:],0)
        return bool(vk and self.user.GetAsyncKeyState(vk)&0x8000)

    def foreground(self):
        hwnd=self.user.GetForegroundWindow();pid=W.DWORD()
        if hwnd:self.user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        return int(hwnd or 0),pid.value

    def pointer(self):
        point=W.POINT();self.user.GetCursorPos(C.byref(point));return [point.x,point.y]

    def sample(self,slot=-1,exclude=-1):
        if self.reader is None:return None,-1
        from gamepad import State
        for index in range(4) if slot<0 else [slot]:
            if index==exclude:continue
            state=State()
            if self.reader(index,C.byref(state))==0:
                signature=(state.packet,bytes(state.pad));cached=self._sample_cache.get(index)
                if cached is None or cached[0]!=signature:cached=(signature,pad_state(state.pad));self._sample_cache[index]=cached
                return cached[1],index
            self._sample_cache.pop(index,None)
        return None,-1

    def _send(self,event):
        if self.user.SendInput(1,C.byref(event),C.sizeof(INPUT))!=1:
            raise OSError('系统未接收模拟输入；请确认游戏与本程序权限一致')

    def key(self,token,down):
        event=INPUT()
        if token.startswith('K:'):
            vk=int(token[2:]);scan=self.user.MapVirtualKeyExW(vk,4,self.user.GetKeyboardLayout(0))
            if scan and vk!=19:event.type=1;event.ki=KEYBDINPUT(0,scan&255,8|(1 if scan&0xff00==0xe000 else 0)|(0 if down else 2),0,MARKER)
            else:event.type=1;event.ki=KEYBDINPUT(vk,0,0 if down else 2,0,MARKER)
        else:
            name=token[2:];flags={'left':(2,4),'right':(8,16),'middle':(32,64),'x1':(128,256),'x2':(128,256)}
            event.type=0;event.mi=MOUSEINPUT(0,0,1 if name=='x1' else 2 if name=='x2' else 0,flags[name][0 if down else 1],0,MARKER)
        self._send(event)

    def move(self,x,y):
        if x or y:
            event=INPUT();event.type=0;event.mi=MOUSEINPUT(x,y,0,1,0,MARKER);self._send(event)

    def wheel(self,direction):
        event=INPUT();event.type=0;event.mi=MOUSEINPUT(0,0,120 if direction=='wheelup' else (-120)&0xffffffff,0x800,0,MARKER);self._send(event)


class KeyOutput:
    """Reference-union ownership: two mappings sharing Shift cannot release each other."""
    def __init__(self,transport):self.transport=transport;self.owned=set();self.wheels={}
    def update(self,desired,move,now):
        wheels={token for token in desired if token in ('M:wheelup','M:wheeldown')};held=desired-wheels
        modifier=lambda token:token.startswith('K:') and int(token[2:]) in MODIFIERS
        for token in sorted(self.owned-held,key=lambda token:(modifier(token),token)):
            self.transport.key(token,False);self.owned.remove(token)
        for token in sorted(held-self.owned,key=lambda token:(not modifier(token),token)):
            if not self.transport.held(token):self.transport.key(token,True);self.owned.add(token)
        for token in wheels:
            if now>=self.wheels.get(token,0):self.transport.wheel(token[2:]);self.wheels[token]=now+.4
        self.wheels={token:time for token,time in self.wheels.items() if token in wheels}
        self.transport.move(*move)
    def release(self):
        errors=[]
        for token in sorted(self.owned,key=lambda token:token.startswith('K:') and int(token[2:]) in MODIFIERS):
            try:self.transport.key(token,False)
            except OSError:errors.append(token)
        self.owned=set(errors);self.wheels.clear()


def virtual_available():
    if os.name!='nt' or not importlib.util.find_spec('vgamepad'):return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Services\ViGEmBus'):return True
    except OSError:return False


class VirtualPad:
    def __init__(self):
        if not virtual_available():raise OSError('键鼠→手柄需要 vgamepad 与 ViGEmBus；请查看映射帮助')
        import vgamepad as vg
        self.pad=vg.VX360Gamepad();self.index=-1
        from vgamepad.win.vigem_client import vigem_target_x360_get_user_index
        index=W.DWORD()
        if vigem_target_x360_get_user_index(self.pad._busp,self.pad._devicep,C.byref(index))==0x20000000:self.index=index.value
        if not 0<=self.index<=3:
            self.close();raise OSError('无法确定虚拟手柄编号，请检查系统手柄数量与驱动状态')
    def update(self,report):
        pad=self.pad
        pad.report.wButtons=report['buttons'];pad.report.bLeftTrigger=report['LT'];pad.report.bRightTrigger=report['RT']
        for field,key in [('sThumbLX','LX'),('sThumbLY','LY'),('sThumbRX','RX'),('sThumbRY','RY')]:setattr(pad.report,field,report[key])
        pad.update()
    def release(self):
        if self.pad:self.pad.reset();self.pad.update()
    def close(self):
        if self.pad:
            try:self.release()
            finally:pad=self.pad;self.pad=None;del pad


class RAWDEVICE(C.Structure):_fields_=[('page',W.USHORT),('usage',W.USHORT),('flags',W.DWORD),('hwnd',W.HWND)]
class RAWHEADER(C.Structure):_fields_=[('kind',W.DWORD),('size',W.DWORD),('device',W.HANDLE),('wparam',W.WPARAM)]
class RAWMOUSE(C.Structure):_fields_=[('flags',W.USHORT),('buttons',W.ULONG),('rawButtons',W.ULONG),('x',W.LONG),('y',W.LONG),('extra',W.ULONG)]


class RawMouse(QAbstractNativeEventFilter):
    def __init__(self):
        super().__init__();self.user=C.WinDLL('user32',use_last_error=True);self.lock=threading.Lock();self.delta=[0,0];self.pulses=set();self.enabled=False
        self.user.RegisterRawInputDevices.argtypes=[C.POINTER(RAWDEVICE),W.UINT,W.UINT];self.user.RegisterRawInputDevices.restype=W.BOOL
        self.user.GetRawInputData.argtypes=[W.HANDLE,W.UINT,C.c_void_p,C.POINTER(W.UINT),W.UINT];self.user.GetRawInputData.restype=W.UINT
    def start(self,hwnd):
        device=RAWDEVICE(1,2,0x100,hwnd)
        if not self.user.RegisterRawInputDevices(C.byref(device),1,C.sizeof(device)):raise OSError('无法读取原始鼠标移动')
        self.enabled=True
    def stop(self):
        if self.enabled:
            device=RAWDEVICE(1,2,1,None);self.user.RegisterRawInputDevices(C.byref(device),1,C.sizeof(device));self.enabled=False
        self.take()
    def take(self):
        with self.lock:delta=self.delta;buttons=self.pulses;self.delta=[0,0];self.pulses=set();return delta,buttons
    def nativeEventFilter(self,event_type,message):
        if not self.enabled:return False,0
        msg=W.MSG.from_address(int(message))
        if msg.message!=0xff:return False,0
        size=W.UINT()
        if self.user.GetRawInputData(msg.lParam,0x10000003,None,C.byref(size),C.sizeof(RAWHEADER))==0xffffffff or not C.sizeof(RAWHEADER)<=size.value<=4096:return False,0
        buffer=C.create_string_buffer(size.value)
        if self.user.GetRawInputData(msg.lParam,0x10000003,buffer,C.byref(size),C.sizeof(RAWHEADER))==0xffffffff:return False,0
        if size.value<C.sizeof(RAWHEADER):return False,0
        header=RAWHEADER.from_buffer(buffer)
        if header.kind==0 and size.value>=C.sizeof(RAWHEADER)+C.sizeof(RAWMOUSE):
            mouse=RAWMOUSE.from_buffer(buffer,C.sizeof(RAWHEADER))
            if mouse.extra!=MARKER:
                with self.lock:
                    if not mouse.flags&1:self.delta[0]+=mouse.x;self.delta[1]+=mouse.y
                    if mouse.buttons&0x400:
                        value=C.c_short(mouse.buttons>>16).value;self.pulses.add('M:wheelup' if value>0 else 'M:wheeldown')
        return False,0
