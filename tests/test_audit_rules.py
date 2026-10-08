from pathlib import Path
import tempfile,sys,gc,unittest,json
from contextlib import closing
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from matching import scan
from local_index import clear
from save_workflow import select_candidate
from save_groups import complete_directory
from services import Store,ROOT

class AuditRules(unittest.TestCase):
    def setUp(self):
        clear();self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
    def tearDown(self):clear();gc.collect();self.temp.cleanup()
    def file(self,relative,data=b'fixture'):
        file=self.root/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data);return file
    def test_djmax_nson_is_found(self):
        self.file('Neowiz/DJMAX RESPECT V/Saves/GameSave001.nson')
        candidates,_=scan('DJMAX RESPECT V',{},root_override={'locallow':self.root})
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str((self.root/'Neowiz/DJMAX RESPECT V/Saves').resolve()))
    def test_shf_rule_without_existing_installation(self):
        self.file('SHf/Saved/SaveGames/76561197960271872/SaveSlot1.sav')
        candidates,_=scan('Silent Hill f',{},root_override={'local':self.root})
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str((self.root/'SHf/Saved/SaveGames').resolve()))
    def test_executable_short_code_is_used(self):
        exe=self.file('install/Abc.exe');self.file('Abc/Saved/SaveGames/slot.sav')
        candidates,_=scan('Different Game Title',{'install_dir':str(exe.parent)},root_override={'local':self.root})
        self.assertTrue(select_candidate({'candidates':candidates})['path'].endswith('Abc\\Saved\\SaveGames'))
    def test_generic_game_and_release_do_not_match_unrelated_games(self):
        self.file('Cup Dog Games/Rubinite/Release/slot.sav')
        exe=self.file('install/Game/long-title-win64-release.exe')
        candidates,_=scan('Different Title',{'install_dir':str(exe.parent)},root_override={'locallow':self.root})
        self.assertFalse(candidates)
    def test_short_game_code_with_language_suffix_is_detected(self):
        self.file('Nitroplus/saya_ch/1.00/system.dat')
        exe=self.file('install/saya/Saya.exe')
        candidates,_=scan('沙耶之歌',{'install_dir':str(exe.parent)},root_override={'roaming':self.root})
        self.assertTrue(any('saya_ch' in c['path'] for c in candidates))
        self.assertIsNone(select_candidate({'candidates':candidates}))
    def test_numbered_sequels_do_not_cross_match(self):
        self.file('ustwo games/Monument Valley 2/progress.sav')
        identity={'english_name':'Monument Valley 3','aliases':['Monument Valley'],'hints':[]}
        candidates,_=scan('Monument Valley 3',{},identity,{'locallow':self.root})
        self.assertFalse(candidates)
    def test_bundled_full_cg_save_does_not_displace_actual_save(self):
        self.file('install/savedata/slot.ksd');self.file('install/补丁/全CG存档/slot.ksd')
        candidates,_=scan('My Game',{'install_dir':str(self.root/'install')},root_override={'install':self.root/'install'})
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str((self.root/'install/savedata').resolve()))
        self.assertTrue(any(c['sample_backup'] for c in candidates))
    def test_steam_accounts_are_kept_together_but_not_global_userdata(self):
        self.file('Roaming/MyGame/steam/76561198183415972/profile.save')
        account=self.root/'Roaming/MyGame/steam/76561198183415972'
        self.assertEqual(complete_directory(account),account.parent)
        global_account=self.root/'userdata/76561198183415972';global_account.mkdir(parents=True)
        self.assertEqual(complete_directory(global_account),global_account)
    def test_old_account_restore_preserves_other_accounts(self):
        one=self.file('Roaming/MyGame/steam/76561198183415972/profile.save',b'old-one')
        two=self.file('Roaming/MyGame/steam/76561197960271872/profile.save',b'other-account')
        store=Store(self.root/'data','audit-rule');store.games=[{'id':'game','name':'MyGame','cover':''}]
        store.save_game('game',{'save_dir':str(one.parent)})
        core=store.core();game=replace(store.game('game'),save_dir=str(one.parent))
        with closing(core.connect_db()) as connection:core.snapshot_game(connection,game,'manual','legacy account')
        one.write_bytes(b'new-one');store.restore('game',store.history('game')[0]['id'])
        self.assertEqual(one.read_bytes(),b'old-one');self.assertEqual(two.read_bytes(),b'other-account')

if __name__=='__main__':unittest.main(verbosity=2)
