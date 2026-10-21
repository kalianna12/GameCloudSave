"""Capture, legacy menu-pointer compatibility and output separation without native injection."""
from pathlib import Path
import copy,json,math,sys,tempfile,time,unittest,wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from services import ROOT,Store
from mapping_model import Forward,validate,default_profile
from mapping_templates import make_template
from mapping_native import KeyOutput,WindowsInput
from input_mapping import MappingController
app=QCoreApplication.instance() or QCoreApplication([])

class InputLogic(unittest.TestCase):
    def test_vn_mouse_stick_never_emits_keyboard_in_any_direction_or_strength(self):
        profile=make_template('vn')
        self.assertEqual(profile['forward']['mouseMode'],'absolute')
        for magnitude in (.4,1.):
            for index in range(8):
                forward=Forward();angle=index*math.pi/4;motion=False
                for _ in range(20):
                    desired,move=forward.frame(profile,{'buttons':[],'LS':[math.sin(angle)*magnitude,math.cos(angle)*magnitude],'RS':[0,0]},.008)
                    self.assertFalse(desired,(magnitude,index,desired))
                    self.assertFalse(forward.wheel_steps)
                    motion=motion or any(move)
                self.assertTrue(motion,(magnitude,index,move))
    def test_absolute_pointer_ignores_game_warps_and_resyncs_real_mouse_and_focus(self):
        class Transport:
            pos=[100,100]
            moves=[]
            def held(self,t):return False
            def pointer(self):return list(self.pos)
            def moveAbsolute(self,x,y):self.moves.append([x,y]);return [x,y]
            def move(self,x,y):self.moves.append(('relative',x,y))
        transport=Transport();output=KeyOutput(transport)
        output.update(set(),[10,5],1,mouse_mode='absolute')
        transport.pos=[900,800]  # Legacy engine snaps its OS cursor to another menu item.
        output.update(set(),[10,5],2,mouse_mode='absolute')
        self.assertEqual(transport.moves,[[110,105],[120,110]])
        output.update(set(),[2,-1],3,mouse_mode='absolute',physical_motion=True)
        self.assertEqual(transport.moves[-1],[902,799])
        output.release();transport.pos=[400,300];output.update(set(),[1,2],4,mouse_mode='absolute')
        self.assertEqual(transport.moves[-1],[401,302])
        output.update(set(),[3,4],5);self.assertEqual(transport.moves[-1],('relative',3,4))
    def test_absolute_coordinates_cover_negative_origin_multimonitor_desktop(self):
        class User:
            def GetSystemMetrics(self,index):return {76:-1920,77:-100,78:3840,79:1180}[index]
        transport=WindowsInput.__new__(WindowsInput);transport.user=User();events=[]
        transport._send=lambda event:events.append((event.mi.dx,event.mi.dy,event.mi.dwFlags))
        self.assertEqual(transport.moveAbsolute(-3000,-400),[-1920,-100]);self.assertEqual(events[-1],(0,0,0xc001))
        self.assertEqual(transport.moveAbsolute(3000,3000),[1919,1079]);self.assertEqual(events[-1],(65535,65535,0xc001))
    def test_migration_adds_vn_mode_without_overriding_explicit_user_choice(self):
        profile=make_template('vn');profile['forward'].pop('mouseMode')
        self.assertEqual(validate(profile)['forward']['mouseMode'],'absolute')
        profile['forward']['mouseMode']='relative';self.assertEqual(validate(profile)['forward']['mouseMode'],'relative')
        plain=default_profile();plain['forward'].pop('mouseMode');self.assertEqual(validate(plain)['forward']['mouseMode'],'relative')
        profile['forward']['mouseMode']='unknown'
        with self.assertRaises(ValueError):validate(profile)
    def test_short_pad_chord_keeps_b_back_menu_and_all_buffered_edges(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
            c=MappingController(Store(folder,'capture-logic'));c._editor=True;c.setMode('keys_to_pad');c.setAutoSelect(False)
            try:
                source=list(c.sourceChord);c.record()
                edges=[{'token':'P:'+b,'down':True,'at':time.time()} for b in ('B','Back','Start','LT','RS')]
                edges +=[dict(row,down=False) for row in edges]
                c.receiveSample({'buttons':[],'LS':[0,0],'RS':[0,0],'keys':[],'_edges':edges})
                self.assertFalse(c.state['recording']);self.assertEqual(c.sourceChord,source)
                self.assertEqual(set(c.currentChord),{'P:B','P:Back','P:Start','P:LT','P:RS'})
            finally:c.shutdown()
    def test_sound_assets_are_distinct_short_pcm_and_settings_are_validated(self):
        frames=set()
        manifest=json.loads((ROOT/'ui/sounds/library/manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['sounds']:
            for filename in entry['files']:
                with wave.open(str(ROOT/'ui/sounds/library'/filename),'rb') as audio:
                    self.assertEqual(audio.getnchannels(),1);self.assertEqual(audio.getsampwidth(),2)
                    self.assertLess(audio.getnframes()/audio.getframerate(),1.81 if entry['kind']=='launch' else .61);frames.add(audio.readframes(audio.getnframes()))
        self.assertGreaterEqual(len(frames),36)
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
            store=Store(folder,'sound-validation')
            for values in ({'navigation_volume':101},{'navigation_volume':True},{'navigation_sound_style':'bad'},{'controller_tilt':1}):
                with self.assertRaises(ValueError):store.save_settings(values)
            store.save_settings({'navigation_volume':0,'navigation_sound_style':'soft','controller_tilt':False})
            self.assertEqual(store.settings['navigation_volume'],0)

if __name__=='__main__':unittest.main(verbosity=2)
