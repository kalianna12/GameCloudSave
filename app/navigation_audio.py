"""Preload on a worker; submit whole clips to native, callback-free XAudio2 playback."""
import atexit,json,logging,wave
from pathlib import Path
from PySide6.QtCore import QObject,QThread,Signal,Slot,Qt,QMetaObject
from PySide6.QtMultimedia import QMediaDevices
from native_audio import NativeAudio,Clip


class AudioLoader(QObject):
    loaded=Signal(object)
    inspected=Signal(object)

    def __init__(self,resources,muted):
        super().__init__();self.resources=Path(resources);self.muted=muted;self.backend=None

    @Slot()
    def initialize(self):
        self.devices=QMediaDevices(self);self.devices.audioOutputsChanged.connect(self.reload)
        self.reload()

    @Slot()
    def reload(self):
        if self.backend:self.backend.close()
        self.backend=None
        try:
            backend=NativeAudio(self.muted);self.backend=backend
            folder=self.resources/'ui/sounds/library'
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            sounds={}
            for entry in manifest['sounds']:
                variants=[]
                for name in entry['files']:
                    with wave.open(str(folder/name),'rb') as file:
                        if (file.getnchannels(),file.getsampwidth(),file.getframerate())!=(1,2,44100):
                            raise ValueError('Invalid navigation PCM format')
                        variants.append(Clip(file.readframes(file.getnframes())))
                sounds[entry['bank'],entry['kind']]=tuple(variants)
            self.loaded.emit((backend,sounds))
        except (OSError,ValueError,KeyError,wave.Error) as error:
            if self.backend:self.backend.close()
            self.backend=None;self.loaded.emit((None,{}))
            logging.getLogger(__name__).warning('Navigation audio unavailable: %s',error)

    @Slot()
    def inspect(self):
        self.inspected.emit(self.backend.inspect() if self.backend else {'available':False,'enabled':False})

    @Slot()
    def shutdown(self):
        if self.backend:self.backend.close();self.backend=None


class NavigationAudio(QObject):
    """All disk/device initialisation is asynchronous. Playback submits native buffers.

    No Python timer, readData or audio callback participates in realtime playback;
    Qt layout rebuilds and a held Python GIL cannot starve an already submitted clip.
    """
    inspectRequested=Signal()
    readyChanged=Signal()
    inspected=Signal(object)
    played=Signal(str,str)

    def __init__(self,resources,parent=None,*,muted=False):
        super().__init__(parent)
        self.enabled=False;self.ready=False;self.sounds={};self.clips={};self.backend=None
        self.closed=False;self.variants={}
        self.workerThread=QThread(self);self.workerThread.setObjectName('navigation-audio-loader')
        self.worker=AudioLoader(resources,muted);self.worker.moveToThread(self.workerThread)
        self.workerThread.started.connect(self.worker.initialize)
        self.workerThread.finished.connect(self.worker.deleteLater)
        self.inspectRequested.connect(self.worker.inspect)
        self.worker.loaded.connect(self.loaded);self.worker.inspected.connect(self.inspected)
        self.workerThread.start();atexit.register(self.shutdown)

    @Slot(object)
    def loaded(self,result):
        self.backend,self.clips=result;self.sounds={key:len(clips) for key,clips in self.clips.items()}
        self.ready=self.backend is not None
        if self.backend and not self.closed:self.set_enabled(self.enabled)
        self.readyChanged.emit()

    def set_enabled(self,enabled):
        if self.closed:return
        self.enabled=bool(enabled)
        if self.backend:
            try:self.backend.set_enabled(self.enabled)
            except OSError as error:logging.getLogger(__name__).warning('Navigation output changed: %s',error)

    def play(self,kind,bank,volume):
        if self.closed or not self.enabled or not self.backend:return False
        key=(bank,kind);variants=self.clips.get(key,self.clips.get(('classic-soft',kind)))
        if not variants:return False
        index=self.variants.get(key,0)%len(variants)
        try:
            if self.backend.play(variants[index],volume):
                self.variants[key]=index+1;self.played.emit(kind,bank);return True
        except OSError as error:
            logging.getLogger(__name__).warning('Navigation output changed: %s',error)
        return False

    def shutdown(self):
        if self.closed:return
        self.closed=True;self.enabled=False
        if self.workerThread.isRunning():
            QMetaObject.invokeMethod(self.worker,'shutdown',Qt.BlockingQueuedConnection)
            self.workerThread.quit();self.workerThread.wait()
        self.backend=None;self.clips={};atexit.unregister(self.shutdown)
