import gc,io,json,sys,tempfile,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from save_workflow import run_workflow,select_candidate
from ai_match import identify_game

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data'); self.store=Store(Path(self.temp.name),'workflow-test')
        self.ident=str(uuid.uuid4()); self.store.games=[{'id':self.ident,'name':'自动备份测试','cover':'','installed':True}]
        self.save=Path(self.temp.name)/'ActualGame/Saves'; self.save.mkdir(parents=True)
        (self.save/'slot.sav').write_bytes(b'actual fixture')
        self.result={'id':self.ident,'name':'自动备份测试','status':'review','candidates':[{'path':str(self.save),'confidence':.9,'files':['slot.sav']}],'checked':[],'aliases':[]}
        self.store.save_settings({'cloud_folder':'电脑/GameCloudSave'})
    def tearDown(self): gc.collect(); self.temp.cleanup()
    def test_complete_without_manual_game_configuration(self):
        stages=[]
        with patch.object(self.store,'match_game',return_value=self.result),patch.object(self.store,'rclone',return_value=''):
            result=run_workflow(self.store,[self.ident],lambda r:stages.append(r['status']),threading.Event())
        self.assertEqual(result['uploaded'],1)
        self.assertEqual(stages,['running','ready','saving','uploading','uploaded'])
        self.assertEqual(self.store.local[self.ident]['save_dir'],str(self.save))
        self.assertTrue(self.store.history(self.ident)[0]['uploaded'])
    def test_network_failure_preserves_local_archive(self):
        with patch.object(self.store,'match_game',return_value=self.result),patch.object(self.store,'upload',side_effect=ValueError('offline')):
            result=run_workflow(self.store,[self.ident],lambda r:None,threading.Event())
        self.assertEqual(result['local_only'],1)
        self.assertTrue(Path(self.store.history(self.ident)[0]['archive_path']).is_file())
    def test_ambiguous_and_empty_directories_not_applied(self):
        empty=Path(self.temp.name)/'EmptyGame';empty.mkdir()
        self.assertIsNone(select_candidate({'candidates':[{'path':str(empty),'confidence':.99,'files':[]}]}))
        other=Path(self.temp.name)/'OtherGame';other.mkdir();(other/'slot.sav').write_bytes(b'fixture')
        self.assertIsNone(select_candidate({'candidates':self.result['candidates']+[{'path':str(other),'confidence':.9,'files':['slot.sav']}]}))
    def test_shared_path_not_applied_to_second_game(self):
        self.store.save_game('other-game',{'save_dir':str(self.save)})
        with patch.object(self.store,'match_game',return_value=self.result):
            result=run_workflow(self.store,[self.ident],lambda r:None,threading.Event())
        self.assertEqual(result['review'],1);self.assertNotIn(self.ident,self.store.local)
    def test_two_unconfigured_games_sharing_path_are_both_skipped(self):
        other=str(uuid.uuid4());self.store.games.append({'id':other,'name':'第二游戏','cover':'','installed':True})
        with patch.object(self.store,'match_game',side_effect=[self.result,{**self.result,'id':other,'name':'第二游戏'}]),patch.object(self.store,'backup') as backup:
            totals=run_workflow(self.store,[self.ident,other],lambda r:None,threading.Event())
        self.assertEqual(totals['review'],2);backup.assert_not_called()
    def test_prefixed_kirikiri_save_directory_is_discovered(self):
        from matching import scan
        install=Path(self.temp.name)/'Fate';install.mkdir()
        saves=install/'fate_savedata';saves.mkdir();(saves/'data0.ksd').write_text('fixture')
        candidates,_=scan('Fate/stay night',{'install_dir':str(install)},root_override={'install':install})
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str(saves.resolve()))
    def test_truncated_json_retried_with_thinking_disabled(self):
        truncated={'choices':[{'finish_reason':'length','message':{'content':''}}]}
        valid={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'english_name':'Game','aliases':[],'hints':[]})}}]}
        responses=[io.BytesIO(json.dumps(truncated).encode()),io.BytesIO(json.dumps(valid).encode())]
        with patch('ai_match.urlopen',side_effect=responses) as call:
            self.assertEqual(identify_game('游戏','Game','dummy','test')['english_name'],'Game')
        self.assertEqual(call.call_count,2)
        payload=json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['thinking']['type'],'disabled');self.assertEqual(payload['max_tokens'],8192)
    def test_dav_write_probe_is_cleaned_before_settings_saved(self):
        with patch.object(self.store,'rclone',return_value=[]) as call:
            self.store.configure_cloud({'cloud_folder':'电脑/GameCloudSave'})
        self.assertEqual(call.call_args_list[1].args[0][0],'copyto')
        self.assertEqual(call.call_args_list[2].args[0][0],'deletefile')

if __name__=='__main__': unittest.main(verbosity=2)
