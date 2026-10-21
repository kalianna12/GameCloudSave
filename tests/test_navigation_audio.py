"""PCM quality and seamless mixing checks, without playing sound on the user's speakers."""
from array import array
from pathlib import Path
import math,sys,time,unittest,wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from navigation_audio import VoiceMixer
ROOT=Path(__file__).resolve().parents[1]

def samples(style='clear',kind='move'):
    with wave.open(str(ROOT/'ui/sounds'/f'{style}-{kind}.wav'),'rb') as file:
        return [v/32768 for v in array('h',file.readframes(file.getnframes()))]

class AudioTests(unittest.TestCase):
    def test_assets_have_soft_edges_low_peaks_and_no_dc(self):
        for style in ('clear','soft','arcade'):
            for kind in ('move','confirm','back','open'):
                data=samples(style,kind)
                self.assertLess(max(abs(x) for x in data),.31)
                self.assertEqual(data[0],0);self.assertEqual(data[-1],0)
                self.assertLess(abs(sum(data)/len(data)),.001)
                self.assertLess(max(abs(a-b) for a,b in zip(data,data[1:])),.03)
                # The first/last 3ms must fade rather than start/stop at full amplitude.
                self.assertLess(max(abs(x) for x in data[:132]),.06)
                self.assertLess(max(abs(x) for x in data[-132:]),.02)

    def test_mix_is_identical_across_arbitrary_backend_chunks(self):
        left=VoiceMixer();right=VoiceMixer()
        for mixer in (left,right):mixer.add(samples('soft','open'),.8)
        expected=left.render(9000)
        actual=b''.join(right.render(count) for count in (1,17,300,5000,3682))
        self.assertEqual(actual,expected)
        self.assertEqual(right.render(2048),bytes(4096))

    def test_repeated_movement_overlaps_without_cutting_previous_tail(self):
        mixer=VoiceMixer();tone=samples()
        mixer.add(tone,.8);mixer.render(1323) # 30ms repeat
        offset=mixer.voices[0][1];mixer.add(tone,.8)
        self.assertEqual(len(mixer.voices),2)
        first=array('h',mixer.render(1))[0]/32767
        self.assertAlmostEqual(first,.85*math.tanh(tone[offset]*.8),places=4)
        for _ in range(100):
            mixer.add(tone,1);pcm=array('h',mixer.render(1323))
            self.assertLess(max(abs(x) for x in pcm),28000)
        mixer.render(9000);self.assertFalse(mixer.voices)

    def test_overlap_admission_never_truncates_a_voice_or_clips(self):
        mixer=VoiceMixer(channels=2);tone=samples('arcade','open')
        for _ in range(8):self.assertTrue(mixer.add(tone,1))
        self.assertFalse(mixer.add(tone,1));self.assertEqual(len(mixer.voices),8)
        pcm=array('h',mixer.render(8000));self.assertLess(max(abs(x) for x in pcm),28000)
        self.assertEqual(pcm[::2],pcm[1::2]);self.assertFalse(mixer.voices)

    def test_silent_idle_and_mixing_cost_are_bounded(self):
        mixer=VoiceMixer();started=time.perf_counter()
        for _ in range(10000):self.assertEqual(mixer.render(1411),bytes(2822))
        self.assertLess(time.perf_counter()-started,1)
        started=time.perf_counter()
        for _ in range(200):mixer.add(samples(),.8);mixer.render(1411)
        self.assertLess(time.perf_counter()-started,3)

if __name__=='__main__':unittest.main(verbosity=2)
