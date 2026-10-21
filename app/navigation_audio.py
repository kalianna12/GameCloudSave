"""One warm PCM stream with overlapping, preloaded UI voices (no retrigger cuts)."""
from array import array
import math
from pathlib import Path
import wave

from PySide6.QtCore import QObject, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QtAudio


class VoiceMixer:
    def __init__(self, rate=44100, channels=1, floating=False):
        self.rate,self.channels,self.floating=rate,channels,floating
        self.voices=[]

    def add(self, samples, gain):
        # Admission control never cuts a sounding voice at an arbitrary sample.
        if len(self.voices)>=8:return False
        self.voices.append([samples,0,gain]);return True

    def render(self, count):
        if not self.voices:return bytes(count*self.channels*(4 if self.floating else 2))
        mixed=[0.0]*count;remaining=[]
        for samples,offset,gain in self.voices:
            length=min(count,len(samples)-offset)
            for i in range(length):mixed[i]+=samples[offset+i]*gain
            offset+=length
            if offset<len(samples):remaining.append([samples,offset,gain])
        self.voices=remaining
        output=array('f' if self.floating else 'h')
        for sample in mixed:
            # Smooth saturation leaves headroom even during simultaneous UI events.
            sample=.85*math.tanh(sample)
            value=sample if self.floating else round(sample*32767)
            output.extend([value]*self.channels)
        return output.tobytes()


class AudioStream(QIODevice):
    def __init__(self,mixer,parent=None):
        super().__init__(parent);self.mixer=mixer
        self.frame_bytes=mixer.channels*(4 if mixer.floating else 2)
        self.open(QIODevice.ReadOnly|QIODevice.Unbuffered)

    def isSequential(self):return True
    def bytesAvailable(self):return self.mixer.rate*self.frame_bytes//25+super().bytesAvailable()
    def readData(self,size):return self.mixer.render(size//self.frame_bytes)
    def writeData(self,data):return -1


class NavigationAudio(QObject):
    def __init__(self,resources,parent=None):
        super().__init__(parent)
        self.resources=Path(resources);self.sounds={};self.sink=None;self.stream=None
        self.devices=QMediaDevices(self);self.devices.audioOutputsChanged.connect(self.reset_device)
        self.enabled=False
        self.reset_device()

    def reset_device(self):
        if self.sink:
            self.sink.stop();self.sink.deleteLater();self.stream.close();self.stream.deleteLater()
        self.sink=None;self.stream=None;self.sounds={}
        device=QMediaDevices.defaultAudioOutput()
        if device.isNull():return
        format=device.preferredFormat()
        if format.sampleFormat() not in (QAudioFormat.Int16,QAudioFormat.Float):return
        mixer=VoiceMixer(format.sampleRate(),format.channelCount(),format.sampleFormat()==QAudioFormat.Float)
        for style in ('clear','soft','arcade'):
            for kind in ('move','confirm','back','open'):
                try:
                    with wave.open(str(self.resources/'ui/sounds'/f'{style}-{kind}.wav'),'rb') as file:
                        if file.getsampwidth()!=2 or file.getnchannels()!=1:continue
                        rate=file.getframerate();pcm=array('h',file.readframes(file.getnframes()))
                    count=round(len(pcm)*mixer.rate/rate)
                    samples=[]
                    for i in range(count):
                        pos=i*rate/mixer.rate;left=min(int(pos),len(pcm)-1);right=min(left+1,len(pcm)-1)
                        samples.append((pcm[left]+(pcm[right]-pcm[left])*(pos-left))/32768)
                    self.sounds[style,kind]=samples
                except (OSError,EOFError,wave.Error):continue
        self.stream=AudioStream(mixer,self);self.sink=QAudioSink(device,format,self)
        self.sink.setBufferSize(round(mixer.rate*.032)*self.stream.frame_bytes)
        if self.enabled:self.sink.start(self.stream)

    def set_enabled(self,enabled):
        enabled=bool(enabled)
        if enabled==self.enabled:return
        self.enabled=enabled
        if not self.sink:return
        if enabled:self.sink.start(self.stream)
        else:
            self.sink.stop();self.stream.mixer.voices.clear()

    def play(self,kind,style,volume):
        if not self.enabled or not self.sink:return False
        samples=self.sounds.get((style,kind),self.sounds.get(('soft','move')))
        if not samples:return False
        if self.sink.state()==QtAudio.StoppedState:
            if self.sink.error()!=QtAudio.NoError:return False
            self.sink.start(self.stream)
        return self.stream.mixer.add(samples,volume/100)

    def shutdown(self):self.set_enabled(False)
