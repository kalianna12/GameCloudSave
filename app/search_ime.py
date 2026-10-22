"""Native Windows IME keys restricted to our focused search field."""
import ctypes as C
from ctypes import wintypes as W
import os
from PySide6.QtCore import QObject,Slot,Signal,Property
from PySide6.QtGui import QGuiApplication

class SearchIme(QObject):
    pendingChanged=Signal()
    def __init__(self,parent=None):super().__init__(parent);self.original=None;self._pending=False;self._mode=None;self._hwnd=0
    @Property(bool,notify=pendingChanged)
    def pending(self):return self._pending
    def markPending(self,value):
        if self._pending!=value:self._pending=value;self.pendingChanged.emit()
    @Slot()
    def committed(self):self.markPending(False)
    def window(self):
        if os.name!='nt':return None
        app=QGuiApplication.instance();window=app.focusWindow() if app else None
        if not window or not hasattr(window,'activeFocusItem'):return None
        focus=window.activeFocusItem()
        if not focus or focus.objectName()!='keyboardValue':return None
        from launch_ready import foreground
        if foreground()[1]!=os.getpid():return None
        return int(window.winId())
    @Slot(bool,result=bool)
    def setChinese(self,chinese):
        hwnd=self.window()
        if not hwnd:return False
        user=C.windll.user32
        user.GetKeyboardLayout.argtypes=[W.DWORD];user.GetKeyboardLayout.restype=W.HKL
        user.ActivateKeyboardLayout.argtypes=[W.HKL,W.UINT];user.ActivateKeyboardLayout.restype=W.HKL
        if not chinese:self.end();return True
        count=user.GetKeyboardLayoutList(0,None);layouts=(W.HKL*count)()
        user.GetKeyboardLayoutList.argtypes=[C.c_int,C.POINTER(W.HKL)];user.GetKeyboardLayoutList(count,layouts)
        # Chinese language + US keyboard (0409:0804) is a Latin-only layout,
        # despite its Chinese LANGID. Prefer the active actual Chinese IME.
        choices=[value for value in layouts if value and value&0xffff in (0x0804,0x0404,0x0c04) and (value>>16)&0xffff!=0x0409]
        current=user.GetKeyboardLayout(0)
        layout=current if current in choices else next(iter(choices),None)
        if not layout:return False
        if self.original is None:self.original=current;self._hwnd=hwnd
        user.ActivateKeyboardLayout(layout,0)
        imm=C.windll.imm32
        imm.ImmGetContext.argtypes=[W.HWND];imm.ImmGetContext.restype=W.HANDLE
        imm.ImmReleaseContext.argtypes=[W.HWND,W.HANDLE]
        imm.ImmSetOpenStatus.argtypes=[W.HANDLE,W.BOOL]
        imm.ImmSetConversionStatus.argtypes=[W.HANDLE,W.DWORD,W.DWORD]
        imm.ImmGetOpenStatus.argtypes=[W.HANDLE];imm.ImmGetOpenStatus.restype=W.BOOL
        imm.ImmGetConversionStatus.argtypes=[W.HANDLE,C.POINTER(W.DWORD),C.POINTER(W.DWORD)]
        context=imm.ImmGetContext(hwnd)
        if context:
            conversion=W.DWORD();sentence=W.DWORD()
            imm.ImmGetConversionStatus(context,C.byref(conversion),C.byref(sentence))
            if self._mode is None:self._mode=(imm.ImmGetOpenStatus(context),conversion.value,sentence.value)
            imm.ImmSetOpenStatus(context,True);imm.ImmSetConversionStatus(context,conversion.value|1,sentence.value);imm.ImmReleaseContext(hwnd,context)
        return True
    @Slot(str,result=bool)
    def key(self,key):
        if not self.window():return False
        controls={'space':32,'backspace':8,'escape':27,'left':37,'up':38,'right':39,'down':40,'pageup':33,'pagedown':34}
        vk=controls.get(key,ord(key.upper()) if len(key)==1 and key.isascii() and key.isalnum() else 0)
        if not vk:return False
        from mapping_native import INPUT,KEYBDINPUT,MARKER
        events=(INPUT*2)()
        for index in range(2):events[index].type=1;events[index].ki=KEYBDINPUT(vk,0,2 if index else 0,0,MARKER)
        user=C.windll.user32;user.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int];user.SendInput.restype=W.UINT
        sent=user.SendInput(2,events,C.sizeof(INPUT))==2
        if sent:
            # Some third-party TSF IMEs own their preedit/candidate windows and
            # deliver only committed text to Qt. Track our virtual composition
            # until that actual text edit arrives; letters are still processed
            # entirely by the installed native IME.
            if len(key)==1 and key.isalpha():self.markPending(True)
            elif key=='escape':self.markPending(False)
        return sent
    @Slot()
    def end(self):
        if self.original is not None and os.name=='nt':
            user=C.windll.user32;user.ActivateKeyboardLayout.argtypes=[W.HKL,W.UINT];user.ActivateKeyboardLayout.restype=W.HKL
            user.ActivateKeyboardLayout(self.original,0)
            user.IsWindow.argtypes=[W.HWND]
            if self._mode and self._hwnd and user.IsWindow(self._hwnd):
                imm=C.windll.imm32;context=imm.ImmGetContext(self._hwnd)
                if context:
                    opened,conversion,sentence=self._mode
                    imm.ImmSetOpenStatus(context,opened);imm.ImmSetConversionStatus(context,conversion,sentence);imm.ImmReleaseContext(self._hwnd,context)
        self.original=None;self._mode=None;self._hwnd=0;self.markPending(False)
