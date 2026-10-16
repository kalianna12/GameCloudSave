from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from gamepad import Mapper,Pad
class Preferences(unittest.TestCase):
    def test_right_stick_zoom_is_independent_and_bounded(self):
        mapper=Mapper();pad=Pad();pad.ry=9000;self.assertEqual(mapper.read(pad,0),[])
        pad.ry=20000;pad.lx=16000;self.assertEqual(mapper.read(pad,.01),['right','zoom-in'])
        self.assertEqual(mapper.read(pad,.04),[]);self.assertEqual(mapper.read(pad,.10),['zoom-in'])
        pad.ry=8000;self.assertEqual(mapper.read(pad,.20),['zoom-in'])
        pad.ry=6000;pad.lx=0;self.assertEqual(mapper.read(pad,.21),[])
        pad.ry=-20000;self.assertEqual(mapper.read(pad,.22),['zoom-out'])
        mapper.reset();pad.ry=0;self.assertEqual(mapper.read(pad,.23),[])
    def test_wood_preferences_are_validated_and_persisted(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
            store=Store(directory,'wood')
            for species in ('oak','walnut','cherry'):
                store.save_settings({'shelf_wood':species,'shelf_sunlight':False})
                restored=Store(directory,'wood');self.assertEqual(restored.settings['shelf_wood'],species);self.assertFalse(restored.settings['shelf_sunlight'])
            before=(store.profile/'settings.json').read_bytes()
            for value in ({'shelf_wood':'unknown'},{'shelf_sunlight':'yes'}):
                with self.assertRaises(ValueError):store.save_settings(value)
                self.assertEqual((store.profile/'settings.json').read_bytes(),before)
if __name__=='__main__':unittest.main()
