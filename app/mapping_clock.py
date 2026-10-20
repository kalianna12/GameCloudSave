"""Per-worker high resolution waits, without changing the system-wide timer period."""
import ctypes as C
from ctypes import wintypes as W
import os

class PollClock:
    def __init__(self):
        self.handle=None
        if os.name=='nt':
            try:
                self.kernel=C.WinDLL('kernel32',use_last_error=True)
                create=self.kernel.CreateWaitableTimerExW;create.argtypes=[C.c_void_p,W.LPCWSTR,W.DWORD,W.DWORD];create.restype=W.HANDLE
                self.kernel.SetWaitableTimer.argtypes=[W.HANDLE,C.POINTER(C.c_longlong),W.LONG,C.c_void_p,C.c_void_p,W.BOOL]
                self.kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];self.kernel.CloseHandle.argtypes=[W.HANDLE]
                self.handle=create(None,None,2,0x1f0003)
            except (OSError,AttributeError):pass
    def wait(self,seconds,wake):
        if wake.is_set():wake.clear();return
        if self.handle:
            due=C.c_longlong(-max(1,int(seconds*10_000_000)))
            if self.kernel.SetWaitableTimer(self.handle,C.byref(due),0,None,None,False):self.kernel.WaitForSingleObject(self.handle,max(20,int(seconds*1000)+20));return
        wake.wait(seconds);wake.clear()
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
