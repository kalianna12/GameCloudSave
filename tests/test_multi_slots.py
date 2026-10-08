from pathlib import Path
import sys,tempfile,gc,unittest,json,zipfile
from contextlib import closing
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from save_groups import complete_directory
from save_workflow import select_candidate
from matching import scan

class MultipleSlots(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
        self.store=Store(Path(self.temp.name),'slots-test')
        self.ident='rubinite-test';self.store.games=[{'id':self.ident,'name':'Rubinite','cover':''}]
        self.root=Path(self.temp.name)/'Cup Dog Games/Rubinite/Release'
        for name in ('save1','save3','ChallengeSave','backup_save3','backup_ChallengeSave'):
            folder=self.root/name;folder.mkdir(parents=True)
            if name!='save1':(folder/'GameData.json').write_text('{"chapter":3}')
        (self.root/'SettingData.json').write_text('{"volume":0.5}')
    def tearDown(self):gc.collect();self.temp.cleanup()
    def test_manual_single_slot_becomes_complete_parent(self):
        self.store.save_game(self.ident,{'save_dir':str(self.root/'save3')})
        self.assertEqual(self.store.local[self.ident]['save_dir'],str(self.root))
    def test_existing_single_slot_setting_upgrades_before_backup(self):
        self.store.local[self.ident]={'save_dir':str(self.root/'save3')}
        self.store.backup(self.ident)
        self.assertEqual(self.store.local[self.ident]['save_dir'],str(self.root))
    def test_archive_includes_slots_backups_empty_slot_and_settings(self):
        self.store.save_game(self.ident,{'save_dir':str(self.root/'save3')})
        archive=self.store.backup(self.ident)
        with zipfile.ZipFile(archive) as zipped:
            names=zipped.namelist()
            for name in ('save3','ChallengeSave','backup_save3','backup_ChallengeSave'):
                self.assertIn('save/'+name+'/GameData.json',names)
            self.assertIn('save/save1/',names)
            self.assertIn('save/SettingData.json',names)
            self.assertEqual(json.loads(zipped.read('_snapshot_meta.json'))['save_dir'],str(self.root))
    def test_match_parent_selected_over_child(self):
        candidates=[{'path':str(self.root),'confidence':.9,'files':['save3/GameData.json']},
                    {'path':str(self.root/'save3'),'confidence':.95,'files':['GameData.json']}]
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str(self.root))
    def test_hint_to_single_slot_returns_complete_directory(self):
        identity={'english_name':'Rubinite','aliases':[],'hints':[{'root':'locallow','relative':'Cup Dog Games/Rubinite/Release/save3','reason':'save slot'}]}
        candidates,_=scan('Rubinite',{},identity,{'locallow':Path(self.temp.name)})
        self.assertEqual(candidates[0]['path'],str(self.root.resolve()))
        self.assertIn('ChallengeSave/GameData.json',candidates[0]['files'])
    def test_shared_system_root_is_not_promoted(self):
        shared=Path(self.temp.name)/'LocalLow'
        for name in ('save1','save3'):
            folder=shared/name;folder.mkdir(parents=True);(folder/'game.sav').write_text('data')
        self.assertEqual(complete_directory(shared/'save3'),shared/'save3')
    def test_unrelated_sibling_game_is_not_included(self):
        alone=Path(self.temp.name)/'Publisher/GameA/save3';alone.mkdir(parents=True)
        (alone/'game.sav').write_text('data')
        (alone.parent/'OtherGame').mkdir()
        self.assertEqual(complete_directory(alone),alone)
    def test_upload_uses_parent_save_directory(self):
        self.store.save_game(self.ident,{'save_dir':str(self.root/'save3')})
        archive=self.store.backup(self.ident);self.store.settings['cloud_folder']='root'
        with patch.object(self.store,'rclone',return_value='') as calls:self.store.upload(self.ident,archive)
        self.assertTrue(calls.call_args.args[0][2].startswith('gamecloud:root/Rubinite/Release/'))
    def test_full_restore_restores_all_slots(self):
        self.store.save_game(self.ident,{'save_dir':str(self.root)})
        self.store.backup(self.ident);snapshot=self.store.history(self.ident)[0]['id']
        for name in ('save3','ChallengeSave'):(self.root/name/'GameData.json').write_text('changed')
        self.store.restore(self.ident,snapshot)
        for name in ('save3','ChallengeSave'):
            self.assertEqual(json.loads((self.root/name/'GameData.json').read_text())['chapter'],3)
    def test_old_single_slot_restore_preserves_other_slots(self):
        self.store.save_game(self.ident,{'save_dir':str(self.root)})
        game=replace(self.store.game(self.ident),save_dir=str(self.root/'save3'))
        core=self.store.core()
        with closing(core.connect_db()) as connection:core.snapshot_game(connection,game,'manual','old single-slot fixture')
        snapshot=self.store.history(self.ident)[0]['id']
        (self.root/'save3/GameData.json').write_text('changed')
        (self.root/'ChallengeSave/GameData.json').write_text('{"chapter":99}')
        self.store.restore(self.ident,snapshot)
        self.assertEqual(json.loads((self.root/'save3/GameData.json').read_text())['chapter'],3)
        self.assertEqual(json.loads((self.root/'ChallengeSave/GameData.json').read_text())['chapter'],99)
        self.assertTrue((self.root/'SettingData.json').exists())
        self.assertEqual(self.store.game(self.ident).save_dir,str(self.root))

if __name__=='__main__':unittest.main(verbosity=2)
