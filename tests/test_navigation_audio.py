"""Validate the actual licensed sample bank and native playback, with output muted."""
from array import array
from pathlib import Path
import ctypes,hashlib,json,sys,time,unittest,wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from native_audio import NativeAudio,Clip,Buffer,State,MASTER_GAIN,VOICE_COUNT
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'ui/sounds/library'
MANIFEST=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))

def pcm(name):
    with wave.open(str(FOLDER/name),'rb') as file:return file.readframes(file.getnframes())

class AudioTests(unittest.TestCase):
    def test_all_layouts_have_complete_distinct_event_banks(self):
        banks={entry['bank'] for entry in MANIFEST['sounds']}
        self.assertEqual(banks,{'classic-clear','classic-soft','classic-arcade','shelf','cinema','atlas','felt','wood','water','launch-warm','launch-projector','launch-orbit'})
        for bank in banks:
            self.assertEqual({e['kind'] for e in MANIFEST['sounds'] if e['bank']==bank},{'launch'} if bank.startswith('launch-') else {'move','confirm','back','open','group','switch'})
        for kind in ('move','confirm','group','switch'):
            audio={pcm(e['files'][0]) for e in MANIFEST['sounds'] if e['kind']==kind and e['bank'] in ('classic-clear','shelf','cinema','atlas')}
            self.assertEqual(len(audio),4)

    def test_samples_have_fades_headroom_short_duration_and_valid_provenance(self):
        for entry in MANIFEST['sounds']:
            for name,origin in zip(entry['files'],entry['origins']):
                with wave.open(str(FOLDER/name),'rb') as file:
                    self.assertEqual((file.getnchannels(),file.getsampwidth(),file.getframerate()),(1,2,44100))
                    self.assertGreater(file.getnframes(),441);self.assertLessEqual(file.getnframes(),44100*(1.8 if entry['kind']=='launch' else .6))
                    if entry['kind']=='launch':self.assertGreater(file.getnframes(),44100*1.2)
                data=[v/32768 for v in array('h',pcm(name))]
                self.assertEqual(data[0],0);self.assertEqual(data[-1],0)
                self.assertLess(max(abs(v) for v in data),.281)
                self.assertLess(max(abs(v) for v in data)*VOICE_COUNT*MASTER_GAIN,1)
                self.assertLess(abs(sum(data)/len(data)),.005)
                source=ROOT/'ui/sounds/sources'/origin['source']
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),origin['sha256'])
                for layer in origin.get('layers',[]):
                    self.assertEqual(hashlib.sha256((ROOT/'ui/sounds/sources'/layer['source']).read_bytes()).hexdigest(),layer['sha256'])

    def test_real_book_and_projector_recordings_are_used(self):
        sources={e['bank']:{o['source'] for item in MANIFEST['sounds'] if item['bank']==e['bank'] for o in item['origins']} for e in MANIFEST['sounds']}
        self.assertIn('rpg/bookOpen.ogg',sources['shelf'])
        self.assertIn('book/book_flip.4.ogg',sources['shelf'])
        self.assertIn('projector/projector.mp3',sources['cinema'])
        self.assertEqual(MANIFEST['license'],'mixed')
        for entry in MANIFEST['sounds']:
            self.assertEqual(entry['license'],'Nintendo-copyright' if entry['bank']=='classic-clear' else 'CC0-1.0')

    def test_default_switch_samples_preserve_provenance_and_louder_safe_levels(self):
        expected={'move':'SeGameIconFocus.wav','confirm':'SeBtnDecide.wav',
            'back':'SeFooterDecideBack.wav','open':'SeDialogOpen.wav',
            'group':'SeSelectFocus.wav','switch':'SeDialogOpen_Accent.wav'}
        # Measured RMS of the previous default bank, before the Switch replacement.
        previous={'move':.040,'confirm':.0494,'back':.0437,'open':.055,'group':.039,'switch':.055}
        for entry in MANIFEST['sounds']:
            if entry['bank']!='classic-clear':continue
            kind=entry['kind']
            self.assertEqual(entry['origins'][0]['source'],'nintendo-switch/'+expected[kind])
            samples=[v/32768 for v in array('h',pcm(entry['files'][0]))]
            rms=(sum(v*v for v in samples)/len(samples))**.5
            self.assertGreater(rms,previous[kind]*1.12,(kind,rms))
            # Even eight simultaneous, full-volume copies cannot clip the mixer.
            self.assertLess(max(abs(v) for v in samples)*VOICE_COUNT*MASTER_GAIN,1)
        notice=(ROOT/'ui/sounds/sources/nintendo-switch/NOTICE.md').read_text(encoding='utf-8')
        self.assertIn('70614a3e0b912068476ed54d9836d08e8d6878b0',notice)
        self.assertIn('Nintendo',notice)

    def test_windows_packed_abi_and_full_pcm_buffer_lifetime(self):
        self.assertEqual(ctypes.sizeof(Buffer),28+2*ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(ctypes.sizeof(State),12+ctypes.sizeof(ctypes.c_void_p))
        data=pcm('atlas-switch-1.wav');clip=Clip(data)
        self.assertEqual(ctypes.string_at(clip.buffer.data,clip.buffer.size),data)
        self.assertEqual(clip.buffer.flags,0x40)

    def test_native_overlap_admission_preserves_sounding_voices(self):
        player=NativeAudio(muted=True)
        try:
            player.set_enabled(True);clip=Clip(pcm('atlas-switch-1.wav'))
            for _ in range(VOICE_COUNT):self.assertTrue(player.play(clip,100))
            self.assertFalse(player.play(clip,100))
            self.assertTrue(all(v.clip is clip for v in player.voices))
            time.sleep(.12);state=player.inspect()
            self.assertEqual(state['voices'],VOICE_COUNT);self.assertTrue(all(s>1000 for s in state['samples']))
            time.sleep(.55);self.assertEqual(player.inspect()['voices'],0)
        finally:player.close();player.close()

    def test_muting_stops_all_native_voices_and_reenable_works(self):
        player=NativeAudio(muted=True)
        try:
            self.assertFalse(player.play(Clip(pcm('cinema-switch-1.wav')),80))
            player.set_enabled(True);self.assertTrue(player.play(Clip(pcm('cinema-switch-1.wav')),80))
            player.set_enabled(False);self.assertEqual(player.inspect()['voices'],0)
            self.assertFalse(player.inspect()['enabled'])
            player.set_enabled(True);self.assertTrue(player.play(Clip(pcm('shelf-open-1.wav')),80))
        finally:player.close()

    def test_cancel_launch_preserves_other_navigation_tails(self):
        player=NativeAudio(muted=True)
        try:
            player.set_enabled(True)
            navigation=Clip(pcm('atlas-switch-1.wav'));launch=Clip(pcm('launch-orbit-launch-1.wav'))
            self.assertTrue(player.play(navigation,80));self.assertTrue(player.play(launch,80))
            player.stop_clips({launch})
            self.assertIs(player.voices[0].clip,navigation)
            self.assertEqual(player.voices[0].state().queued,1)
            self.assertIsNone(player.voices[1].clip)
            deadline=time.monotonic()+.15
            while player.voices[1].state().queued and time.monotonic()<deadline:time.sleep(.002)
            self.assertEqual(player.voices[1].state().queued,0)
            self.assertFalse(player.voices[1].retired)
        finally:player.close()

if __name__=='__main__':unittest.main(verbosity=2)
