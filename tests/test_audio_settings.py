"""Audio settings validation, old-profile migration and independent volume control."""
from pathlib import Path
import ctypes,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from audio_settings import DEFAULTS,validate
from services import Store,write_json,read_json,ROOT
from native_audio import NativeAudio,method,MASTER_GAIN

class AudioSettingsTests(unittest.TestCase):
    def test_qml_integral_numbers_are_normalized_without_accepting_bad_values(self):
        self.assertEqual(validate({'navigation_volume':75.0}),{'navigation_volume':75})
        self.assertIs(type(validate({'navigation_volume':75.0})['navigation_volume']),int)
        for value in (True,-1,101,7.5,'80',float('inf'),float('nan')):
            with self.assertRaises(ValueError):validate({'navigation_volume':value})
        for fields in ({'navigation_sounds':1},{'launch_sound':'unknown'},{'navigation_sound_pack':'unknown'},{'watch':False}):
            with self.assertRaises(ValueError):validate(fields)

    def test_old_profile_and_other_settings_preserve_latest_live_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
            store=Store(directory,'audio-settings');store.save_settings({'navigation_sound_style':'soft'})
            for key in DEFAULTS:self.assertIn(key,store.settings)
            self.assertEqual(store.settings['navigation_sound_pack'],'auto')
            path=store.profile/'settings.json';saved=read_json(path,{})
            saved['navigation_volume']=80;write_json(path,saved)
            store.settings['navigation_volume']=35
            store.save_settings({'theme':'light'})
            self.assertEqual(read_json(path,{})['navigation_volume'],35)
            store.save_settings({'navigation_volume':50.0,'launch_sound':'orbit'})
            other=Store(directory,'audio-settings')
            self.assertEqual(other.settings['navigation_volume'],50)
            self.assertEqual(other.settings['launch_sound'],'orbit')

    def test_master_volume_changes_our_voice_without_stopping_engine(self):
        player=NativeAudio(muted=True)
        try:
            # Read the actual native mastering voice, with no audible sample queued.
            get_volume=method(player.master,13,None,ctypes.POINTER(ctypes.c_float))
            player.muted=False;player.set_enabled(True);player.set_volume(37)
            gain=ctypes.c_float();get_volume(player.master,ctypes.byref(gain))
            self.assertAlmostEqual(gain.value,MASTER_GAIN*.37,places=6)
            self.assertTrue(player.inspect()['enabled'])
            player.set_volume(0);get_volume(player.master,ctypes.byref(gain));self.assertEqual(gain.value,0)
        finally:player.close()

if __name__=='__main__':unittest.main(verbosity=2)
