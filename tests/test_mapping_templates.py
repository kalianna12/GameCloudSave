"""Genre presets, independent imports, persistence and real input-math behavior; isolated data."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from mapping_templates import make_template,template_catalog
from mapping_model import PAD_BUTTONS,Forward,validate
from input_mapping import MappingController
from services import Store,ROOT
app=QCoreApplication.instance() or QCoreApplication([])


def state(**values):return {'buttons':[],'LS':[0.,0.],'RS':[0.,0.]}|values


class GenreTemplatesTests(unittest.TestCase):
    def test_eight_complete_offline_profiles_and_single_confirmation_events(self):
        catalog=template_catalog();self.assertEqual(len(catalog),8);self.assertEqual(len({r['id'] for r in catalog}),8)
        for entry in catalog:
            profile=make_template(entry['id']);self.assertEqual(validate(profile),profile)
            self.assertEqual(profile['mode'],'pad_to_keys');self.assertEqual(len(entry['bindings']),len(PAD_BUTTONS)+2)
            self.assertEqual(set(profile['forward']['buttons']),set(PAD_BUTTONS))
            self.assertTrue(all(len(keys)==1 for keys in profile['forward']['buttons'].values()))
            self.assertTrue(all(r['action'] and r['output'] for r in entry['bindings']))
        with self.assertRaises(ValueError):make_template('unknown')
    def test_factories_and_previews_never_share_mutable_bindings(self):
        first=make_template('vn');first['forward']['buttons']['A'].append('K:65')
        self.assertEqual(make_template('vn')['forward']['buttons']['A'],['K:13'])
        catalog=template_catalog();catalog[0]['bindings'][0]['action']='edited'
        self.assertNotEqual(template_catalog()[0]['bindings'][0]['action'],'edited')
    def test_rpgmaker_uses_arrows_and_distinct_confirm_alternatives(self):
        profile=make_template('rpgmaker');engine=Forward()
        self.assertEqual(engine.frame(profile,state(LS=[0,.5]),.01)[0],{'K:38'})
        self.assertEqual(engine.frame(profile,state(LS=[0,.95]),.01)[0],{'K:38','K:160'})
        self.assertEqual(engine.frame(profile,state(buttons=['A']),.01)[0],{'K:90'})
        self.assertEqual(engine.frame(profile,state(buttons=['RT']),.01)[0],{'K:13'})
        self.assertNotIn('K:87',profile['forward']['sticks']['LS']['light']['N'])
    def test_sprint_is_opt_in_by_genre_and_all_templates_release(self):
        for entry in template_catalog():
            profile=make_template(entry['id']);engine=Forward();desired,_=engine.frame(profile,state(LS=[0,.95]),.01)
            if profile['forward']['sticks']['LS']['mode']=='keys':
                self.assertEqual('K:160' in desired,entry['id'] in ('shooter','survival','rpgmaker'))
            self.assertEqual(engine.frame(profile,state(),.01),(set(),[0,0]));self.assertFalse(engine.wheel_steps)
    def test_vn_mouse_confirmation_and_management_zoom_are_functional(self):
        profile=make_template('vn');engine=Forward()
        self.assertEqual(engine.frame(profile,state(buttons=['A']),.01)[0],{'K:13'})
        self.assertEqual(engine.frame(profile,state(buttons=['RT']),.01)[0],{'M:left'})
        self.assertLess(profile['forward']['sticks']['RS']['speed'],profile['forward']['sticks']['LS']['speed'])
        self.assertGreater(engine.frame(profile,state(RS=[1,0]),.03)[1][0],0)
        profile=make_template('management');engine=Forward();engine.frame(profile,state(RS=[0,1]),.01)
        self.assertEqual(engine.wheel_steps,['wheelup']);self.assertGreater(engine.frame(profile,state(LS=[1,0]),.03)[1][0],0)


class TemplateImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'template-unit');self.c=MappingController(self.store)
    def tearDown(self):self.c.shutdown();app.processEvents();self.temp.cleanup()
    def test_add_all_preserves_unsaved_draft_and_saved_original_without_enabling(self):
        c=self.c;c.rename('saved original');c.save();ident=c.profileId;saved=copy.deepcopy(c.profile)
        c.rename('unsaved draft');c.selectTarget('A');c.setChord(['K:70']);draft=copy.deepcopy(c.profile)
        self.assertTrue(c.addAllTemplates());self.assertEqual(len(c.profiles),9);self.assertEqual(c.profile,draft)
        self.assertEqual(c.profileId,ident);self.assertTrue(c.state['dirty']);self.assertFalse(c.state['enabled'])
        persisted=json.loads(c.file.read_text(encoding='utf-8'));self.assertEqual(persisted['profiles'][ident],saved)
        self.assertEqual(len(c.profileOptions),10)
        other=MappingController(self.store)
        try:self.assertEqual(len(other.profiles),9);self.assertEqual(other.profile,saved)
        finally:other.shutdown()
    def test_existing_customized_template_is_not_replaced_or_duplicated(self):
        c=self.c;c.setModel('ps');c.setSlot(2);self.assertTrue(c.addTemplate('vn'));ident=c.profileId
        self.assertEqual(c.padModel,'ps');self.assertEqual(c.profile['slot'],2);self.assertFalse(c.state['enabled'])
        c.rename('my VN');c.selectTarget('A');c.setChord(['K:74']);c.save();custom=copy.deepcopy(c.profile)
        self.assertTrue(c.addAllTemplates());self.assertEqual(c.profile,custom);self.assertTrue(c.addAllTemplates());self.assertEqual(len(c.profiles),9)
        self.assertTrue(c.addTemplate('vn'));self.assertEqual(c.profileId,ident);self.assertEqual(c.profile,custom)
        c.rename('unsaved VN');draft=copy.deepcopy(c.profile);self.assertTrue(c.addTemplate('vn'));self.assertEqual(c.profile,draft);self.assertTrue(c.state['dirty'])
    def test_reset_restores_genre_bindings_and_keeps_device_and_custom_name(self):
        c=self.c;c.setModel('joycon');c.setSlot(1);c.addTemplate('rpgmaker');c.rename('custom RPG');c.selectTarget('A');c.setChord(['K:65'])
        c.reset();self.assertEqual(c.currentChord,['K:90']);self.assertEqual(c.profile['templateId'],'rpgmaker');self.assertEqual(c.padModel,'joycon')
        self.assertEqual(c.profile['name'],'custom RPG');self.assertEqual(c.profile['slot'],1);self.assertTrue(c.state['dirty'])
        self.assertEqual(c.profile['forward']['sticks']['LS']['light']['N'],['K:38'])
    def test_capacity_invalid_id_and_write_failure_are_atomic(self):
        c=self.c;c.save();before=c.file.read_bytes();original=copy.deepcopy(c._profiles)
        self.assertFalse(c.addTemplate('unknown'));self.assertEqual(c._profiles,original);self.assertEqual(c.file.read_bytes(),before)
        with patch.object(Path,'replace',side_effect=OSError('fixture denied')):self.assertFalse(c.addAllTemplates())
        self.assertEqual(c._profiles,original);self.assertEqual(c.file.read_bytes(),before)
        for index in range(35):c._profiles['fixture-'+str(index)]=copy.deepcopy(c.profile)
        count=len(c.profiles);self.assertFalse(c.addAllTemplates());self.assertEqual(len(c.profiles),count);self.assertEqual(c.file.read_bytes(),before)
    def test_bulk_import_does_not_restart_or_switch_running_mapping(self):
        c=self.c;c.save();c._enabled=True;revision=c._revision;profile=copy.deepcopy(c._runtime_profile);ident=c.profileId
        self.assertTrue(c.addAllTemplates());self.assertTrue(c.state['enabled']);self.assertEqual(c.activeProfile,ident)
        self.assertEqual(c._revision,revision);self.assertEqual(c._runtime_profile,profile)


if __name__=='__main__':unittest.main(verbosity=2)
