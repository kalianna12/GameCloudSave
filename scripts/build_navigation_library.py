"""Build the bundled CC0 navigation library from preserved source recordings.

Development only: pip install soundfile (includes numpy). No runtime dependency.
"""
from pathlib import Path
import hashlib,json,io
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'ui/sounds/sources'
OUTPUT=ROOT/'ui/sounds/library'
RATE=44100

def read(pack,name,speed=1,offset=0):
    audio,rate=sf.read(SOURCE/pack/name,always_2d=True)
    audio=audio.mean(axis=1)
    if offset:audio=audio[round(offset*rate):]
    else:
        audible=np.flatnonzero(np.abs(audio)>max(1e-6,np.max(np.abs(audio))*.018))
        if len(audible):audio=audio[max(0,audible[0]-round(rate*.002)):audible[-1]+1]
    audio=np.interp(np.arange(round(len(audio)*RATE/rate/speed))*rate*speed/RATE,np.arange(len(audio)),audio)
    return audio

def prepare(audio,duration,cutoff,target,echo=False):
    audio=audio[:round(duration*RATE)]
    audio=audio-np.mean(audio)
    frequencies=np.fft.rfftfreq(len(audio),1/RATE)
    audio=np.fft.irfft(np.fft.rfft(audio)/(1+(frequencies/cutoff)**8)**.5,n=len(audio))
    if echo:
        dry=audio.copy()
        for delay,gain in ((.037,.18),(.071,.10)):
            shift=round(delay*RATE)
            if shift<len(audio):audio[shift:]+=dry[:-shift]*gain
    edge=min(round(RATE*.008),len(audio)//3);tail=min(round(RATE*.028),len(audio)//3)
    audio[:edge]*=np.sin(np.linspace(0,np.pi/2,edge))**2
    audio[-tail:]*=np.sin(np.linspace(np.pi/2,0,tail))**2
    rms=float(np.sqrt(np.mean(audio**2)));peak=float(np.max(np.abs(audio)))
    audio*=min(target/max(rms,1e-9),.28/max(peak,1e-9))
    audio[0]=audio[-1]=0
    return audio

def build():
    OUTPUT.mkdir(parents=True,exist_ok=True);entries=[]
    def cue(bank,kind,pack,names,duration,speed=1,cutoff=3500,echo=False,offset=0):
        files=[];origins=[]
        for index,name in enumerate(names.split('|')):
            raw=read(pack,name,speed,offset)
            audio=prepare(raw,duration,cutoff,.040 if kind=='move' else .055,echo)
            filename=f'{bank}-{kind}-{index+1}.wav'
            sf.write(OUTPUT/filename,audio,RATE,subtype='PCM_16')
            files.append(filename)
            origins.append({'source':f'{pack}/{name}','sha256':hashlib.sha256((SOURCE/pack/name).read_bytes()).hexdigest(),
                'speed':speed,'maximum_seconds':duration,'offset_seconds':offset,'lowpass_hz':cutoff,'short_echo':echo})
        entries.append({'bank':bank,'kind':kind,'files':files,'origins':origins})
    for style,move,confirm,speed,cutoff in (
        ('clear','rollover2.wav','click2.wav',1,3200),
        ('soft','rollover6.wav','click1.wav',.9,2200),
        ('arcade','rollover5.wav','click3.wav',1.08,4000)):
        bank='classic-'+style
        cue(bank,'move','ui',move,.14,speed,cutoff)
        cue(bank,'confirm','ui',confirm,.13,speed,cutoff)
        cue(bank,'back','interface','back_002.wav',.15,.9,cutoff)
        cue(bank,'open','interface','select_002.wav',.11,.9,cutoff)
        cue(bank,'group','interface','switch_006.wav',.24,.95,cutoff)
        cue(bank,'switch','interface','confirmation_001.wav',.34,.92,cutoff)
    cue('shelf','move','rpg','bookFlip3.ogg|bookFlip2.ogg',.21,1,4600)
    cue('shelf','confirm','rpg','bookPlace2.ogg',.29,1,3400)
    cue('shelf','back','rpg','bookClose.ogg',.26,1,3500)
    cue('shelf','open','rpg','bookOpen.ogg',.20,.95,4400)
    cue('shelf','group','book','book_flip.4.ogg|book_flip.8.ogg',.40,1,4600)
    cue('shelf','switch','rpg','bookOpen.ogg',.27,.7,3800)
    cue('cinema','move','projector','projector.mp3',.11,1,3000,offset=1.0)
    cue('cinema','confirm','ui','switch30.wav',.24,1,3400)
    cue('cinema','back','interface','back_004.wav',.15,.85,2400)
    cue('cinema','open','ui','switch27.wav',.24,.9,3400)
    cue('cinema','group','projector','projector.mp3',.24,1,3400,offset=2.1)
    cue('cinema','switch','projector','projector.mp3',.48,1,3000,offset=.7)
    cue('atlas','move','interface','glass_002.wav|glass_006.wav',.19,.8,3000,True)
    cue('atlas','confirm','interface','glass_001.wav',.40,.78,3300,True)
    cue('atlas','back','interface','back_004.wav',.18,.7,2400,True)
    cue('atlas','open','interface','select_005.wav',.40,.85,2800,True)
    cue('atlas','group','interface','glass_003.wav',.23,.7,2800,True)
    cue('atlas','switch','interface','confirmation_004.wav',.58,.8,2400,True)
    for bank,pack,move,confirm,speed,cutoff in (
        ('felt','ui','rollover6.wav','click1.wav',.65,1500),
        ('wood','rpg','bookPlace2.ogg','bookClose.ogg',1.2,2600),
        ('water','interface','glass_006.wav','glass_003.wav',.65,1900)):
        cue(bank,'move',pack,move,.16,speed,cutoff)
        cue(bank,'confirm',pack,confirm,.28,speed,cutoff)
        cue(bank,'back','interface','back_002.wav',.19,speed,cutoff)
        cue(bank,'open',pack,move,.23,speed*.85,cutoff)
        cue(bank,'group',pack,confirm,.32,speed*.9,cutoff)
        cue(bank,'switch','interface','confirmation_004.wav',.48,speed,cutoff,True)

    def launch(name,duration,layers,cutoff):
        audio=np.zeros(round(duration*RATE));origins=[]
        for pack,source,speed,offset,delay,gain in layers:
            raw=read(pack,source,speed,offset)
            raw=prepare(raw,min(duration-delay,len(raw)/RATE),cutoff,.055,True)
            start=round(delay*RATE);count=min(len(raw),len(audio)-start)
            audio[start:start+count]+=raw[:count]*gain
            origins.append({'source':f'{pack}/{source}','sha256':hashlib.sha256((SOURCE/pack/source).read_bytes()).hexdigest(),
                'speed':speed,'offset_seconds':offset,'delay_seconds':delay,'gain':gain})
        audio=prepare(audio,duration,cutoff,.055)
        attack=round(RATE*.035);release=round(RATE*.16)
        audio[:attack]*=np.sin(np.linspace(0,np.pi/2,attack))**2
        audio[-release:]*=np.sin(np.linspace(np.pi/2,0,release))**2
        filename=f'launch-{name}-launch-1.wav';sf.write(OUTPUT/filename,audio,RATE,subtype='PCM_16')
        entries.append({'bank':'launch-'+name,'kind':'launch','files':[filename],
            'origins':[{**origins[0],'layers':origins,'maximum_seconds':duration,'lowpass_hz':cutoff}]})
    launch('warm',1.4,[('interface','confirmation_004.wav',.65,0,0,1),('interface','glass_001.wav',.72,0,.45,.48),('interface','glass_003.wav',.82,0,1.15,.25)],1900)
    launch('projector',1.7,[('projector','projector.mp3',1,1,0,.65),('interface','confirmation_001.wav',.75,0,.15,.6)],2600)
    launch('orbit',1.8,[('interface','glass_001.wav',.55,0,0,.8),('interface','glass_003.wav',.68,0,.32,.55),('interface','confirmation_004.wav',.62,0,.62,.65),('interface','glass_001.wav',.65,0,1.32,.18)],2300)
    (OUTPUT/'manifest.json').write_text(json.dumps({'version':1,'license':'CC0-1.0','sounds':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Built {len(entries)} event banks / {sum(len(e["files"]) for e in entries)} PCM recordings')

if __name__=='__main__':build()
