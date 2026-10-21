"""Windows XAudio2: complete PCM buffers, no Python/Qt realtime callbacks.

ABI follows Microsoft's xaudio2.h (packed structures, XAudio2 2.9 vtables).
Only our mastering voice is muted; system/other applications' volume is untouched.
"""
import ctypes as C
from ctypes import wintypes as W
import threading

VOICE_COUNT=8
MASTER_GAIN=.44 # 8 voices * asset peak .28 * .44 < 1, including at volume 100.


class Format(C.Structure):
    _pack_=1
    _fields_=[('tag',W.WORD),('channels',W.WORD),('rate',W.DWORD),('average',W.DWORD),('align',W.WORD),('bits',W.WORD),('extra',W.WORD)]

class Buffer(C.Structure):
    _pack_=1
    _fields_=[('flags',C.c_uint32),('size',C.c_uint32),('data',C.c_void_p),('begin',C.c_uint32),('length',C.c_uint32),
              ('loop_begin',C.c_uint32),('loop_length',C.c_uint32),('loops',C.c_uint32),('context',C.c_void_p)]

class State(C.Structure):
    _pack_=1
    _fields_=[('context',C.c_void_p),('queued',C.c_uint32),('samples',C.c_uint64)]

def method(pointer,index,result,*arguments):
    vtable=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result,C.c_void_p,*arguments)(vtable[index])

def check(result):
    if result<0:raise OSError('XAudio2 error 0x%08x'%(result&0xffffffff))

class Clip:
    def __init__(self,pcm,loop=False):
        self.pcm=C.create_string_buffer(pcm)
        self.buffer=Buffer(flags=0x40,size=len(pcm),data=C.addressof(self.pcm),loops=255 if loop else 0)

class Voice:
    def __init__(self,engine):
        self.pointer=C.c_void_p()
        create=method(engine,5,C.c_int32,C.POINTER(C.c_void_p),C.POINTER(Format),C.c_uint32,C.c_float,C.c_void_p,C.c_void_p,C.c_void_p)
        format=Format(1,1,44100,88200,2,16,0)
        check(create(engine,C.byref(self.pointer),C.byref(format),0,2.,None,None,None))
        self.submit=method(self.pointer,21,C.c_int32,C.POINTER(Buffer),C.c_void_p)
        self.start=method(self.pointer,19,C.c_int32,C.c_uint32,C.c_uint32)
        self.stop=method(self.pointer,20,C.c_int32,C.c_uint32,C.c_uint32)
        self.flush=method(self.pointer,22,C.c_int32)
        self.volume=method(self.pointer,12,C.c_int32,C.c_float,C.c_uint32)
        self.get_state=method(self.pointer,25,None,C.POINTER(State),C.c_uint32)
        self.clip=None

    def state(self):
        result=State();self.get_state(self.pointer,C.byref(result),0);return result

    def play(self,clip,gain):
        self.clip=clip # Own the sample memory until XAudio2 has consumed the buffer.
        check(self.volume(self.pointer,gain,0))
        check(self.submit(self.pointer,C.byref(clip.buffer),None))
        check(self.start(self.pointer,0,0))

    def reset(self):
        check(self.stop(self.pointer,0,0));check(self.flush(self.pointer));self.clip=None

    def close(self):
        if self.pointer:
            method(self.pointer,18,None)(self.pointer);self.pointer=None;self.clip=None

class NativeAudio:
    def __init__(self,muted=False):
        self.lock=threading.RLock();self.pointer=C.c_void_p();self.master=C.c_void_p();self.voices=[];self.warm=None
        self.enabled=False;self.closed=False
        self.com=C.WinDLL('ole32');self.owner=threading.get_ident()
        self.com.CoInitializeEx.argtypes=[C.c_void_p,C.c_uint32];self.com.CoInitializeEx.restype=C.c_int32
        result=self.com.CoInitializeEx(None,0);self.com_owned=result>=0
        if result<0 and result!=-2147417850:check(result) # Reuse an existing STA apartment.
        try:
            self.dll=C.WinDLL('xaudio2_9.dll')
            create=self.dll.XAudio2Create;create.argtypes=[C.POINTER(C.c_void_p),C.c_uint32,C.c_uint32];create.restype=C.c_int32
            check(create(C.byref(self.pointer),0,1))
            master=method(self.pointer,7,C.c_int32,C.POINTER(C.c_void_p),C.c_uint32,C.c_uint32,C.c_uint32,C.c_wchar_p,C.c_void_p,C.c_int)
            check(master(self.pointer,C.byref(self.master),0,0,0,None,None,6))
            check(method(self.master,12,C.c_int32,C.c_float,C.c_uint32)(self.master,0. if muted else MASTER_GAIN,0))
            for _ in range(VOICE_COUNT):self.voices.append(Voice(self.pointer))
            self.warm=Voice(self.pointer);self.silence=Clip(bytes(4410),loop=True)
            self.start=method(self.pointer,8,C.c_int32);self.stop=method(self.pointer,9,None)
            self.performance=method(self.pointer,11,None,C.c_void_p)
            self.stop(self.pointer)
        except Exception:self.close();raise

    def set_enabled(self,enabled):
        with self.lock:
            if self.closed or self.enabled==bool(enabled):return
            self.enabled=bool(enabled)
            if enabled:
                check(self.start(self.pointer));self.warm.play(self.silence,0.)
            else:
                self.stop(self.pointer)
                for voice in self.voices+[self.warm]:voice.reset()

    def play(self,clip,volume):
        with self.lock:
            if not self.enabled or self.closed:return False
            for voice in self.voices:
                if not voice.state().queued:
                    voice.play(clip,volume/100);return True
            return False # Never truncate another voice's tail just to admit a new sound.

    def inspect(self):
        with self.lock:
            if self.closed:return {'available':False,'enabled':False}
            states=[v.state() for v in self.voices]
            data=(C.c_ubyte*256)();self.performance(self.pointer,C.byref(data))
            raw=bytes(data)
            return {'available':True,'enabled':self.enabled,'state':'ActiveState' if self.enabled else 'StoppedState','error':'NoError',
                'processed':round(self.warm.state().samples*1000000/44100),'voices':sum(s.queued>0 for s in states),
                'samples':[s.samples for s in states],'underruns':int.from_bytes(raw[32:36],'little'),
                'latency_samples':int.from_bytes(raw[28:32],'little'),'backend':'XAudio2 / native PCM buffers'}

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
            for voice in self.voices:voice.close()
            if self.warm:self.warm.close()
            if self.master:method(self.master,18,None)(self.master);self.master=None
            if self.pointer:method(self.pointer,2,C.c_uint32)(self.pointer);self.pointer=None
            if self.com_owned and threading.get_ident()==self.owner:self.com.CoUninitialize();self.com_owned=False
