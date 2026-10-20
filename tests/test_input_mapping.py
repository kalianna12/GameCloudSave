"""Pure stick math, ownership, editing and a non-injecting runtime fixture."""
from pathlib import Path
import sys,tempfile,math,copy,time,os
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from mapping_model import default_profile,validate,Forward,Reverse,chord,direction_keys,DIRECTIONS
from mapping_native import KeyOutput
from input_mapping import MappingController
from services import Store,ROOT
app=QCoreApplication.instance() or QCoreApplication([])


def neutral():return {'buttons':[],'LS':[0.,0.],'RS':[0.,0.]}


class FakeInput:
    def __init__(self):self.state=neutral();self.physical=set();self.injected=set();self.events=[];self.owner=(100,999999)
    def sample(self,*args):return self.state,0 if self.state else -1
    def foreground(self):return self.owner
    def held(self,token):
        if token=='K:17':return bool(self.physical&{'K:162','K:163'})
        if token=='K:18':return bool(self.physical&{'K:164','K:165'})
        return token in self.physical|self.injected
    def key(self,token,down):
        self.events.append((token,down));self.injected.add(token) if down else self.injected.discard(token)
    def move(self,*args):
        if any(args):self.events.append(('move',args))
    def wheel(self,direction):self.events.append(('wheel',direction))


class MappingTests(unittest.TestCase):
    def setUp(self):self.profile=default_profile()
    def test_default_profile_and_unbounded_real_keyboard_vk_range(self):
        self.assertEqual(validate(self.profile),self.profile)
        self.assertEqual(chord(['K:175','K:226','K:135','K:65','K:65']),['K:175','K:226','K:135','K:65'])
    def test_corrupt_and_executable_profiles_rejected(self):
        for change in [('forward',None),('reverse',None),('mode','shell')]:
            with self.subTest(change=change):
                profile=copy.deepcopy(self.profile);profile[change[0]]=change[1]
                with self.assertRaises(ValueError):validate(profile)
        with self.assertRaises(ValueError):chord(['powershell:bad'])
        self.profile['forward']['sticks']['LS']['deadzone']=float('nan')
        with self.assertRaises(ValueError):validate(self.profile)
    def test_eight_directions_and_neutral_release(self):
        vectors=[(0,.5),(.4,.4),(.5,0),(.4,-.4),(0,-.5),(-.4,-.4),(-.5,0),(-.4,.4)]
        for direction,vector in zip(DIRECTIONS,vectors):
            engine=Forward();state=neutral();state['LS']=vector
            desired,move=engine.frame(self.profile,state,.016)
            self.assertEqual(desired,set(self.profile['forward']['sticks']['LS']['light'][direction]))
            self.assertEqual(engine.frame(self.profile,neutral(),.016),(set(),[0,0]))
    def test_light_and_hard_combinations_can_be_reversed(self):
        cfg=self.profile['forward']['sticks']['LS'];cfg['lightExtra']=['K:160'];cfg['hardExtra']=[]
        cfg['hard']['N']=['K:162','K:87']
        state=neutral();state['LS']=[0,.5];engine=Forward()
        self.assertEqual(engine.frame(self.profile,state,.01)[0],{'K:87','K:160'})
        state['LS']=[0,.9];self.assertEqual(engine.frame(self.profile,state,.01)[0],{'K:87','K:162'})
    def test_heavy_and_deadzone_hysteresis_prevent_chatter(self):
        engine=Forward();state=neutral();state['LS']=[0,.8]
        self.assertIn('K:160',engine.frame(self.profile,state,.01)[0])
        for magnitude in (.73,.71,.72):state['LS']=[0,magnitude];self.assertIn('K:160',engine.frame(self.profile,state,.01)[0])
        state['LS']=[0,.67];self.assertNotIn('K:160',engine.frame(self.profile,state,.01)[0])
        state['LS']=[0,.17];self.assertTrue(engine.frame(self.profile,state,.01)[0])
        state['LS']=[0,.12];self.assertFalse(engine.frame(self.profile,state,.01)[0])
    def test_direction_boundary_has_hysteresis(self):
        engine=Forward();state=neutral();state['LS']=[0,.5];engine.frame(self.profile,state,.01)
        angle=math.radians(23);state['LS']=[.5*math.sin(angle),.5*math.cos(angle)]
        self.assertEqual(engine.frame(self.profile,state,.01)[0],{'K:87'})
    def test_mouse_speed_independent_of_frame_rate_and_fractional_motion(self):
        self.profile['forward']['sticks']['RS'].update(speed=1000,smoothing=0,curve=1)
        totals=[]
        for rate in (25,125):
            engine=Forward();state=neutral();state['RS']=[1,0];total=0
            for _ in range(rate):total+=engine.frame(self.profile,state,1/rate)[1][0]
            totals.append(total)
        self.assertLessEqual(abs(totals[0]-totals[1]),1)
        self.assertAlmostEqual(totals[0],1000,delta=1)
        engine=Forward();state['RS']=[.181,0]
        total=sum(engine.frame(self.profile,state,.01)[1][0] for _ in range(1000))
        self.assertGreater(total,0)
    def test_mouse_stop_and_reset_do_not_leave_residual_motion(self):
        state=neutral();state['RS']=[.5,.5];engine=Forward()
        engine.frame(self.profile,state,.02);self.assertEqual(engine.frame(self.profile,neutral(),.02)[1],[0,0])
        engine.reset();self.assertEqual(engine.residual,[0.,0.])
    def test_arrow_preset_diagonals_and_old_profile_defaults(self):
        cfg=self.profile['forward']['sticks']['LS'];cfg['light']=direction_keys('arrows');cfg['hard']=direction_keys('arrows')
        for direction,vector in zip(DIRECTIONS,((0,.5),(.4,.4),(.5,0),(.4,-.4),(0,-.5),(-.4,-.4),(-.5,0),(-.4,.4))):
            state=neutral();state['LS']=vector
            self.assertEqual(Forward().frame(self.profile,state,.016)[0],set(cfg['light'][direction]))
        self.assertEqual(cfg['light']['NW'],['K:38','K:37'])
        self.profile['reverse'].update(mouse='disabled',ramp=0)
        report=Reverse().frame(self.profile,{'K:38','K:39'},[0,0],.01)
        self.assertAlmostEqual(report['LX']/32767,math.sqrt(.5),delta=.001);self.assertEqual(report['LX'],report['LY'])
        for stick in self.profile['forward']['sticks'].values():
            for field in ('wheelLight','wheelHard','wheelInvert'):stick.pop(field)
        self.profile['reverse'].pop('wheelPulse')
        old=validate(self.profile);self.assertEqual(old['reverse']['wheelPulse'],100)
        self.assertEqual(old['forward']['sticks']['LS']['wheelHard'],12)
    def test_stick_wheel_rates_light_heavy_reverse_neutral_and_ownership(self):
        cfg=self.profile['forward']['sticks']['LS'];cfg.update(mode='wheel',wheelLight=3,wheelHard=12)
        totals=[]
        for rate in (25,125):
            engine=Forward();state=neutral();state['LS']=[0,.5];events=[]
            transport=FakeInput();output=KeyOutput(transport)
            for frame in range(rate):
                desired,move=engine.frame(self.profile,state,1/rate);output.update(desired,move,frame/rate,engine.wheel_steps);events.extend(engine.wheel_steps)
            self.assertFalse(transport.injected);self.assertTrue(all(t=='wheelup' for t in events));totals.append(len(events))
            self.assertEqual(len(transport.events),len(events))
            engine.frame(self.profile,neutral(),.01);self.assertFalse(engine.wheel_steps)
            state['LS']=[0,-.9];engine.frame(self.profile,state,.01);self.assertEqual(engine.wheel_steps,['wheeldown'])
            cfg['wheelInvert']=True;engine.reset();engine.frame(self.profile,state,.01);self.assertEqual(engine.wheel_steps,['wheelup']);cfg['wheelInvert']=False
        self.assertLessEqual(abs(totals[0]-totals[1]),1)
        state=neutral();state['LS']=[0,1];engine=Forward();count=0
        for _ in range(125):engine.frame(self.profile,state,.008);count+=len(engine.wheel_steps)
        self.assertAlmostEqual(count,13,delta=1)
    def test_wheel_to_stick_releases_and_rejects_out_of_range_settings(self):
        cfg=self.profile['reverse'];cfg.update(mouse='disabled',ramp=0)
        cfg['routes']=[{'id':'wheel-up','source':['M:wheelup'],'targets':['P:RY+']},{'id':'wheel-down','source':['M:wheeldown'],'targets':['P:RY-']}]
        engine=Reverse();self.assertEqual(engine.frame(self.profile,{'M:wheelup'},[0,0],.01)['RY'],32767)
        self.assertEqual(engine.frame(self.profile,{'M:wheeldown'},[0,0],.01)['RY'],-32767)
        self.assertEqual(engine.frame(self.profile,set(),[0,0],.01)['RY'],0)
        cfg['wheelPulse']=10000
        with self.assertRaises(ValueError):validate(self.profile)
    def test_shared_modifier_and_owned_key_release_order(self):
        transport=FakeInput();output=KeyOutput(transport)
        output.update({'K:160','K:83','K:65'},[0,0],0)
        self.assertEqual(transport.events[0],('K:160',True))
        output.update({'K:160','K:65'},[0,0],.1);self.assertIn('K:160',transport.injected)
        output.release();self.assertEqual(transport.events[-1],('K:160',False));self.assertFalse(transport.injected)
    def test_does_not_release_physically_owned_keys(self):
        transport=FakeInput();transport.physical={'K:32'};output=KeyOutput(transport)
        output.update({'K:32'},[0,0],0);output.release();self.assertEqual(transport.events,[])
    def test_wheel_pulses_are_bounded_and_modifiers_precede_them(self):
        transport=FakeInput();output=KeyOutput(transport)
        for stamp in (0,.01,.1,.39,.4):output.update({'K:162','M:wheelup'},[0,0],stamp)
        self.assertEqual(transport.events.count(('wheel','wheelup')),2)
        self.assertEqual(transport.events[0],('K:162',True))
    def test_reverse_combo_and_diagonal_normalization(self):
        self.profile['reverse'].update(ramp=0,mouse='disabled');engine=Reverse()
        report=engine.frame(self.profile,{'K:87','K:68','K:32'},[0,0],.01)
        self.assertEqual(report['buttons'],0x1000)
        self.assertAlmostEqual(math.hypot(report['LX'],report['LY']),32767,delta=1)
        self.assertEqual(engine.frame(self.profile,set(),[0,0],.01)['LY'],0)
    def test_reverse_light_modifier_and_opposed_keys(self):
        self.profile['reverse'].update(ramp=0,mouse='disabled');engine=Reverse()
        report=engine.frame(self.profile,{'K:87','K:160'},[0,0],.01);self.assertAlmostEqual(report['LY'],32767*.45,delta=1)
        report=engine.frame(self.profile,{'K:87','K:83'},[0,0],.01);self.assertEqual(report['LY'],0)
    def test_reverse_one_key_multiple_buttons_and_mouse_axes(self):
        cfg=self.profile['reverse'];cfg.update(smoothing=0,ramp=0,mouseSpeed=1000)
        cfg['routes']=[{'id':'combo','source':['K:162','K:65'],'targets':['P:A','P:LB','P:LT']}]
        report=Reverse().frame(self.profile,{'K:162','K:65'},[10,-10],.01)
        self.assertEqual(report['buttons'],0x1100);self.assertEqual(report['LT'],255)
        self.assertEqual((report['RX'],report['RY']),(32767,32767))

    def test_raw_mouse_packet_accumulation_feedback_filter_and_malformed_packets(self):
        import ctypes as C
        from ctypes import wintypes as W
        from mapping_native import RawMouse,RAWHEADER,RAWMOUSE,MARKER
        raw=RawMouse();raw.enabled=True
        class Reader:
            packet=b''
            def GetRawInputData(self,handle,command,buffer,size,header_size):
                C.cast(size,C.POINTER(W.UINT)).contents.value=len(self.packet)
                if buffer:C.memmove(buffer,self.packet,len(self.packet))
                return len(self.packet) if buffer else 0
        reader=Reader();raw.user=reader
        def packet(extra=0,flags=0,wheel=120):
            header=RAWHEADER();header.kind=0;header.size=C.sizeof(RAWHEADER)+C.sizeof(RAWMOUSE)
            mouse=RAWMOUSE();mouse.x=12;mouse.y=-6;mouse.buttons=((wheel&0xffff)<<16)|0x400;mouse.extra=extra;mouse.flags=flags
            return bytes(header)+bytes(mouse)
        message=W.MSG();message.message=0xff;message.lParam=42
        reader.packet=packet();raw.nativeEventFilter(b'windows_generic_MSG',C.addressof(message))
        raw.nativeEventFilter(b'windows_generic_MSG',C.addressof(message))
        self.assertEqual(raw.take(),([24,-12],{'M:wheelup'}))
        reader.packet=packet(extra=MARKER);raw.nativeEventFilter(b'windows_generic_MSG',C.addressof(message))
        self.assertEqual(raw.take(),([0,0],set()))
        reader.packet=packet(flags=1,wheel=-120);raw.nativeEventFilter(b'windows_generic_MSG',C.addressof(message))
        self.assertEqual(raw.take(),([0,0],{'M:wheeldown'}))
        for bad in (b'',b'bad',bytes(RAWHEADER())):
            reader.packet=bad;self.assertEqual(raw.nativeEventFilter(b'windows_generic_MSG',C.addressof(message)),(False,0))

    def test_native_sampler_excludes_virtual_slot(self):
        import ctypes as C
        from mapping_native import WindowsInput
        from gamepad import State
        transport=WindowsInput();queried=[]
        def read(index,pointer):
            queried.append(index)
            if index!=2:return 1167
            C.cast(pointer,C.POINTER(State)).contents.pad.buttons=0x1000
            return 0
        transport.reader=read
        state,slot=transport.sample(-1,1)
        self.assertEqual(queried,[0,2]);self.assertEqual(slot,2);self.assertIn('A',state['buttons'])


class EditorRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'mapping-tests');self.transport=FakeInput()
        self.controller=MappingController(self.store,transport_factory=lambda:self.transport)
    def tearDown(self):self.controller.shutdown();app.processEvents();self.temp.cleanup()
    def wait(self,condition):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.004)
            if condition():return
        self.fail('Mapping condition not reached: '+self.controller._message)
    def test_drag_both_directions_combo_and_persistence(self):
        c=self.controller;c.dropBinding('K:162','P:A',False);c.dropBinding('K:83','P:A',True)
        self.assertEqual(c.currentChord,['K:162','K:83'])
        c.dropBinding('M:left','P:LS.hard.NE',False);self.assertEqual(c.currentChord,['M:left'])
        c.setMode('keys_to_pad');c.dropBinding('P:A','K:70',False);c.dropBinding('P:LB','K:70',True)
        self.assertEqual(c.currentChord,['P:A','P:LB']);self.assertEqual(c.sourceChord,['K:70'])
        self.assertTrue(c.save());other=MappingController(self.store)
        try:self.assertEqual(other.profile,c.profile)
        finally:other.shutdown()
    def test_profiles_duplicate_and_bad_options_do_not_overwrite(self):
        c=self.controller;c.duplicate();c.rename('Fixture profile');self.assertTrue(c.save())
        self.assertEqual(len(c.profiles),2);original=c.profile['forward']['sticks']['RS']['speed']
        c.setOption('RS','speed',-5);self.assertEqual(c.profile['forward']['sticks']['RS']['speed'],original)
    def test_edit_individual_chord_members_preserves_binding_and_route(self):
        c=self.controller;c.selectTarget('A');c.setChord(['K:162','K:89','K:88'])
        self.assertTrue(c.editChordToken('K:88','',False));self.assertEqual(c.currentChord,['K:162','K:89'])
        self.assertTrue(c.editChordToken('K:89','M:wheelup',False));self.assertEqual(c.currentChord,['K:162','M:wheelup'])
        self.assertFalse(c.editChordToken('K:162','P:X',False));self.assertEqual(c.currentChord,['K:162','M:wheelup'])
        self.assertFalse(c.editChordToken('K:88','K:70',False))
        c.selectTarget('LS.hard.NE');c.setChord(['K:160','K:87','K:68'])
        self.assertTrue(c.editChordToken('K:87','K:38',False));self.assertEqual(c.currentChord,['K:160','K:38','K:68'])
        c.selectTarget('A');self.assertEqual(c.currentChord,['K:162','M:wheelup'])
        c.setMode('keys_to_pad');c.selectSource(['K:162','K:89','K:88']);c.setChord(['P:A','P:Y','P:X']);route=c.target
        self.assertTrue(c.editChordToken('P:X','',False));self.assertEqual(c.currentChord,['P:A','P:Y'])
        self.assertTrue(c.editChordToken('P:Y','P:RB',False));self.assertEqual(c.currentChord,['P:A','P:RB'])
        self.assertTrue(c.editChordToken('K:88','',True));self.assertEqual(c.sourceChord,['K:162','K:89']);self.assertEqual(c.target,route)
        self.assertTrue(c.editChordToken('K:89','M:right',True));self.assertEqual(c.sourceChord,['K:162','M:right'])
        self.assertFalse(c.editChordToken('K:162','P:A',True));self.assertEqual(c.sourceChord,['K:162','M:right'])
        self.assertTrue(c.editChordToken('P:RB','P:A',False));self.assertEqual(c.currentChord,['P:A'])
        self.assertTrue(c.editChordToken('K:162','',True));self.assertTrue(c.editChordToken('M:right','',True));self.assertEqual(c.sourceChord,[])
        c.chooseKey('K:70');self.assertEqual(c.target,route);self.assertEqual(c.sourceChord,['K:70']);self.assertEqual(c.currentChord,['P:A'])
        c.record();self.assertFalse(c.editChordToken('P:A','',False));c.cancelCapture()
        self.assertTrue(c.editChordToken('P:A','',False));self.assertEqual(c.currentChord,[])
        self.assertTrue(c.save());other=MappingController(self.store)
        try:self.assertEqual(other.profile,c.profile)
        finally:other.shutdown()
        self.assertTrue(all(row['token'].startswith('P:') for row in c.chordOptions(False)))
        self.assertIn('M:wheelup',[row['token'] for row in c.chordOptions(True)])
    def test_presets_keep_extras_and_other_zone_and_persist_wheel_routes(self):
        c=self.controller;cfg=c.profile['forward']['sticks']['LS'];c.selectTarget('LS.lightExtra');c.setChord(['K:162'])
        c.applyStickPreset('LS','light','arrows')
        self.assertEqual(cfg['light']['NE'],['K:38','K:39']);self.assertEqual(cfg['hard']['NE'],['K:87','K:68'])
        self.assertEqual(cfg['lightExtra'],['K:162']);self.assertEqual(cfg['hardExtra'],['K:160'])
        c.applyStickPreset('LS','both','arrows');self.assertEqual(cfg['light'],cfg['hard'])
        c.setMode('keys_to_pad');c.setWheelTarget('M:wheelup','P:RY+');c.setWheelTarget('M:wheeldown','P:RY-')
        c.selectSource(['K:162','M:wheelup']);c.setChord(['P:A']);c.setWheelTarget('M:wheelup','P:LY+')
        self.assertEqual(c.wheelTarget('M:wheelup'),'P:LY+')
        self.assertEqual(len([r for r in c.profile['reverse']['routes'] if 'M:wheelup' in r['source']]),2)
        c.setWheelTarget('M:wheelup','');self.assertEqual(c.wheelTarget('M:wheelup'),'')
        c.selectSource(['M:wheeldown']);c.setChord(['P:A','P:RB']);self.assertEqual(c.wheelTarget('M:wheeldown'),'custom')
        c.setOption('reverse','wheelPulse',180);self.assertTrue(c.save());other=MappingController(self.store)
        try:self.assertEqual(other.profile,c.profile)
        finally:other.shutdown()
    def test_raw_wheel_preview_without_output_preserves_pulse_then_returns_to_neutral(self):
        class Raw:
            def __init__(self):self.pulses=set()
            def take(self):p=self.pulses;self.pulses=set();return [0,0],p
            def stop(self):pass
        c=self.controller;raw=Raw();c._raw=raw;c.setMode('keys_to_pad');c.setWheelTarget('M:wheelup','P:LY+');c.setWheelTarget('M:wheeldown','P:LY-')
        c.setOption('reverse','mouse','disabled');c.setOption('reverse','ramp',0);c.save();c._editor=True;c.ensure_worker()
        raw.pulses={'M:wheelup'}
        self.wait(lambda:(c.publishPreview() or c.live.get('virtualAxes',[0,0,0,0])[1]>0))
        self.assertIn('M:wheelup',c.keyboardPreview)
        raw.pulses={'M:wheeldown'}
        self.wait(lambda:(c.publishPreview() or c.live.get('virtualAxes',[0,0,0,0])[1]<0))
        self.wait(lambda:(c.publishPreview() or c.live.get('virtualAxes',[0,0,0,0])[1]==0))
        self.assertFalse(self.transport.events);c._raw=None
    def test_adding_wheel_binding_while_running_registers_mouse_on_save(self):
        from unittest.mock import patch
        from PySide6.QtCore import QAbstractNativeEventFilter
        class Raw(QAbstractNativeEventFilter):
            def __init__(self):super().__init__();self.started=[];self.enabled=False
            def start(self,hwnd):self.started.append(hwnd);self.enabled=True
            def stop(self):self.enabled=False
            def take(self):return [0,0],set()
        class Host:
            def winId(self):return 100
        class Virtual:
            index=3
            def update(self,report):pass
            def release(self):pass
            def close(self):pass
        c=self.controller;c.bindRuntimeWindow(Host());c._virtual_factory=Virtual;c.setMode('keys_to_pad');c.setOption('reverse','mouse','disabled')
        with patch('mapping_native.virtual_available',return_value=True),patch('mapping_native.RawMouse',Raw):
            c.setEnabled(True);self.assertTrue(c.state['enabled']);self.assertIsNone(c._raw)
            c.setWheelTarget('M:wheelup','P:RY+');self.assertTrue(c.save());self.assertEqual(c._raw.started,[100])
            c.setWheelTarget('M:wheelup','');self.assertTrue(c.save());self.assertFalse(c._raw.enabled)
        c.setEnabled(False)

    def test_model_profiles_create_select_delete_and_old_schema_fallback(self):
        import json
        c=self.controller;original=c.profileId
        c.createProfile();c.rename('PS fixture');c.setModel('ps');self.assertTrue(c.save());ps=c.profileId
        c.createProfile();c.setModel('joycon');self.assertTrue(c.save())
        c.selectProfile(ps);self.assertEqual(c.profile['padModel'],'ps')
        c.deleteProfile();self.assertNotIn(ps,[row['id'] for row in c.profiles]);self.assertEqual(len(c.profiles),2)
        c.selectProfile(original);self.assertEqual(c.profile['padModel'],'xbox')
        old=default_profile();old.pop('padModel');self.assertEqual(validate(old)['padModel'],'xbox')
        c.file.write_text(json.dumps([]),encoding='utf-8');c.load();self.assertEqual(c.profile['padModel'],'xbox')

    def test_editor_preview_history_is_bounded_and_cleared_when_hidden(self):
        c=self.controller;c._editor=True
        for index in range(70):c.receiveSample({**neutral(),'keys':['K:65'] if index%2 else []})
        self.assertEqual(len(c.state['events']),48)
        self.assertEqual(c.state['events'][0]['key'],'A')
        c.setEditorVisible(False);c.receiveSample({**neutral(),'keys':['K:66']})
        self.assertFalse(c.state['events'])

    def test_coalesced_preview_keeps_every_edge_without_resetting_model(self):
        c=self.controller;c._editor=True;resets=[];c.history.modelReset.connect(lambda:resets.append(1))
        for index in range(20):
            c.queuePreview({**neutral(),'buttons':['A'] if index%2==0 else [],'keys':[]},[{'token':'P:A','down':index%2==0,'at':time.time()}])
        c.publishPreview();self.assertEqual(c.history.pressCounts['P:A'],10)
        self.assertEqual(c.history.rowCount(),20);self.assertFalse(resets)

    def test_preview_does_not_notify_entire_state_or_profile(self):
        c=self.controller;c._editor=True;profiles=[];states=[];c.changed.connect(lambda:profiles.append(1));c.stateChanged.connect(lambda:states.append(1))
        for _ in range(8):c.receiveSample({**neutral(),'buttons':['A'],'keys':[]})
        self.assertFalse(profiles);self.assertFalse(states)

    def test_saved_home_options_activate_without_opening_editor_and_none_stops(self):
        c=self.controller;c.rename('配置1');c.save();first=c.profileId
        c.createProfile();new=c.profileId;self.assertNotIn(new,[p['id'] for p in c.profileOptions]);c.rename('配置2');c.setMode('keys_to_pad');c.save()
        self.assertEqual(c.profileOptions[0]['id'],'');self.assertEqual(len(c.profileOptions),3)
        self.assertTrue(c.profileOptions[1]['label'].startswith('🎮'));self.assertTrue(c.profileOptions[2]['label'].startswith('⌨'))
        c.activateProfile(first);self.assertEqual(c.activeProfile,first);self.assertFalse(c._editor)
        c.activateProfile('');self.assertFalse(c.state['enabled']);self.assertEqual(c.activeProfile,'')
    def test_runtime_waits_for_neutral_releases_on_own_focus_disconnect_and_stop(self):
        c=self.controller;t=self.transport;t.state['buttons']=['A'];c.setEnabled(True)
        self.wait(lambda:'等待' in c._message);self.assertFalse(t.events)
        t.state=neutral();self.wait(lambda:c._message=='映射运行中');t.state['buttons']=['A']
        self.wait(lambda:'K:32' in t.injected)
        t.owner=(101,os.getpid());self.wait(lambda:not t.injected)
        t.owner=(102,999999);self.wait(lambda:'等待' in c._message);self.assertFalse(t.injected)
        t.state=neutral();self.wait(lambda:c._message=='映射运行中');t.state['buttons']=['A'];self.wait(lambda:'K:32' in t.injected)
        t.state=None;self.wait(lambda:not t.injected)
        c.setEnabled(False);self.wait(lambda:not c._enabled)
    def test_emergency_stop_accepts_right_modifiers(self):
        c=self.controller;t=self.transport;c.setEnabled(True);self.wait(lambda:c._message=='映射运行中')
        t.state['buttons']=['A'];self.wait(lambda:'K:32' in t.injected)
        t.physical={'K:163','K:165','K:123'};self.wait(lambda:not c._enabled);self.assertFalse(t.injected)

    def test_emergency_stop_also_works_inside_library(self):
        c=self.controller;t=self.transport;t.owner=(102,os.getpid());c.setEnabled(True)
        self.wait(lambda:'游戏库内暂停' in c._message)
        t.physical={'K:163','K:165','K:123'};self.wait(lambda:not c._enabled)
        self.assertFalse(t.injected)

    def test_mouse_runtime_uses_high_resolution_elapsed_time(self):
        from unittest.mock import patch
        c=self.controller;t=self.transport;c.setEnabled(True);self.wait(lambda:c._message=='映射运行中')
        # Python 3.11 GetTickCount64 can stay unchanged for several 4/8 ms frames.
        with patch('time.monotonic',return_value=123):
            t.state['RS']=[1.,0.];end=time.perf_counter()+.12
            while time.perf_counter()<end:app.processEvents();time.sleep(.002)
        self.assertGreaterEqual(sum(event[0]=='move' for event in t.events),3)

    def test_delayed_running_status_does_not_replace_stopped_message(self):
        c=self.controller;c.setEnabled(False);message=c._message
        c.receiveRuntimeMessage('映射运行中',False);self.assertEqual(c._message,message)

    def test_recording_preserves_native_right_modifiers(self):
        from PySide6.QtCore import QEvent,Qt
        from PySide6.QtGui import QKeyEvent
        c=self.controller;c.record()
        for kind in (QEvent.KeyPress,QEvent.KeyRelease):
            for key,scan,vk in ((Qt.Key_Shift,0x36,16),(Qt.Key_Control,0x11d,17),(Qt.Key_Alt,0x138,18)):
                c.eventFilter(None,QKeyEvent(kind,key,Qt.NoModifier,scan,vk,0))
        self.assertEqual(c.currentChord,['K:161','K:163','K:165'])

    def test_reverse_runtime_neutral_arming_focus_reset_and_device_detach(self):
        from unittest.mock import patch
        class Virtual:
            index=3
            def __init__(self):self.report={'buttons':0};self.closed=False
            def update(self,report):self.report=dict(report)
            def release(self):self.report={'buttons':0}
            def close(self):self.release();self.closed=True
        virtual=Virtual();c=self.controller;t=self.transport;c._virtual_factory=lambda:virtual
        c.setMode('keys_to_pad');c.setOption('reverse','mouse','disabled');c.setOption('reverse','ramp',0)
        c.dropBinding('P:A','K:70',False);c.dropBinding('P:LB','K:70',True);t.physical={'K:70'}
        with patch('mapping_native.virtual_available',return_value=True):c.setEnabled(True)
        self.wait(lambda:'松开' in c._message);self.assertEqual(virtual.report['buttons'],0)
        t.physical=set();self.wait(lambda:c._virtual_index==3)
        t.physical={'K:70'};self.wait(lambda:virtual.report['buttons']==0x1100)
        t.owner=(102,os.getpid());self.wait(lambda:virtual.report['buttons']==0)
        c.setEnabled(False);self.wait(lambda:virtual.closed and c._virtual_index==-1)


if __name__=='__main__':unittest.main(verbosity=2)
