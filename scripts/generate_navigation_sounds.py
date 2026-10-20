"""Generate original short UI feedback tones. No console/game audio samples used."""
from pathlib import Path
import math,struct,wave

folder=Path(__file__).resolve().parents[1]/'ui/sounds'
folder.mkdir(exist_ok=True)
for style,base in (('clear',860),('soft',520),('arcade',1080)):
    for kind,notes,duration in (('move',[1],.045),('confirm',[1,1.5],.11),('back',[1,.75],.095),('open',[1,1.25,1.5],.14)):
        samples=[];rate=44100
        for frame in range(round(rate*duration)):
            t=frame/rate;index=min(len(notes)-1,int(t/duration*len(notes)))
            note_t=t-index*duration/len(notes);span=duration/len(notes)
            envelope=min(1,note_t/.0025)*math.exp(-note_t/(span*.32))*min(1,max(0,(span-note_t)/.004))
            frequency=base*notes[index];phase=2*math.pi*frequency*t
            tone=math.sin(phase)+(.2 if style=='arcade' else .08)*math.sin(phase*2)
            samples.append(struct.pack('<h',round(max(-1,min(1,tone*envelope*.8))*32767)))
        with wave.open(str(folder/(style+'-'+kind+'.wav')),'wb') as output:
            output.setparams((1,2,rate,0,'NONE','not compressed'));output.writeframes(b''.join(samples))
print('Generated 12 original navigation sounds')
