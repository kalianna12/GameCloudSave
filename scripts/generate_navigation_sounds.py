"""Legacy tone generator. Active audio now comes from build_navigation_library.py."""
from pathlib import Path
import math,struct,wave

folder=Path(__file__).resolve().parents[1]/'ui/sounds'
folder.mkdir(exist_ok=True)
for style,base in (('clear',480),('soft',330),('arcade',610)):
    for kind,notes,duration in (('move',[1],.068),('confirm',[1,1.25],.125),('back',[1,.8],.115),('open',[1,1.25,1.5],.15)):
        samples=[];rate=44100
        phases=[0.0]*len(notes)
        for frame in range(round(rate*duration)):
            t=frame/rate;tone=0.0
            # Overlapping, phase-continuous rounded notes: no hard segment edges.
            for index,note in enumerate(notes):
                start=index*duration*.22;span=duration-start
                note_t=t-start
                if note_t<0:continue
                phases[index]+=2*math.pi*base*note/rate
                attack=math.sin(min(1,note_t/.010)*math.pi/2)**2
                release=math.sin(min(1,max(0,(span-note_t)/.022))*math.pi/2)**2
                envelope=attack*release*math.exp(-note_t/(span*.45))
                tone+=math.sin(phases[index])*envelope
            samples.append(struct.pack('<h',round(tone*.30/len(notes)*32767)))
        with wave.open(str(folder/(style+'-'+kind+'.wav')),'wb') as output:
            output.setparams((1,2,rate,0,'NONE','not compressed'));output.writeframes(b''.join(samples))
print('Generated 12 original navigation sounds')
