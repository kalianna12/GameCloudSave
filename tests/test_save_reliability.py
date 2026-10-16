"""Two independent computers, account mapping, partial slots and staged restore failures."""
from pathlib import Path
import gc
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from matching import scan
from save_workflow import select_candidate,evidence
from ai_match import identify_game
from save_web import search,supported_hint
from local_index import clear


class SaveReliability(unittest.TestCase):
    def setUp(self):
        clear();self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
    def tearDown(self):
        clear();gc.collect();self.temp.cleanup()
    def file(self,folder,name,content='progress'):
        path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content);return path
    def store(self,name,ident='game',title='Khazan',platform='steam',external='2680010'):
        store=Store(self.root/name,name);store.settings.update(watch=False,computer=name,cloud_folder='games')
        store.games=[{'id':ident,'name':title,'platform':platform,'external_id':external,'cover':''}]
        saves=self.root/name/'SaveGames';saves.mkdir()
        store.save_game(ident,{'save_dir':str(saves)})
        from tests.test_sources_and_sync import Features
        Features.configure_cloud(self,store)
        return store,saves
    def test_both_khazan_locations_are_discovered_and_ambiguity_is_retained(self):
        root=self.root/'Local'
        for path in ('BBQ','The First Berserker Khazan'):
            self.file(root/path/'Saved/SaveGames/76561198000000001','SaveGame01_Player.sav')
        candidates,_=scan('第一狂战士：卡赞',{},root_override={'local':root})
        paths={Path(candidate['path']) for candidate in candidates}
        self.assertIn((root/'BBQ/Saved/SaveGames').resolve(),paths)
        self.assertIn((root/'The First Berserker Khazan/Saved/SaveGames').resolve(),paths)
        self.assertIsNone(select_candidate({'candidates':candidates}))
    def test_configuration_sav_and_empty_save_are_not_progress(self):
        path=self.root/'BBQ/Saved/SaveGames'
        self.file(path,'ProfileSettings.sav');self.file(path,'slot.sav','')
        self.assertFalse(evidence({'path':str(path),'files':['ProfileSettings.sav','slot.sav']}))
    def test_partial_directory_slot_retains_other_slots_and_settings(self):
        store,saves=self.store('A')
        for name in ('save1','save2','ChallengeSave'):self.file(saves/name,'GameData.json',name)
        self.file(saves,'settings.json','current settings')
        store.backup('game');snapshot=store.history('game')[0]['id']
        self.file(saves/'save1','GameData.json','new1');self.file(saves/'save2','GameData.json','new2')
        store.restore('game',snapshot,{'slot':'save1'})
        self.assertEqual((saves/'save1/GameData.json').read_text(),'save1')
        self.assertEqual((saves/'save2/GameData.json').read_text(),'new2')
        self.assertEqual((saves/'settings.json').read_text(),'current settings')
    def test_file_slot_restores_all_companions_but_preserves_another_slot(self):
        store,saves=self.store('A')
        for name in ('SaveGame01_Player.sav','SaveGame01_Slot.sav','SaveGame01_Player_bak0.sav','SaveGame01-Progress.sav','SaveGame01 Settings.sav','SaveGame010_Player.sav','SaveGame02_Player.sav'):self.file(saves,name,name)
        store.backup('game');snapshot=store.history('game')[0]['id']
        for path in saves.iterdir():path.write_text('new')
        store.restore('game',snapshot,{'slot':'SaveGame01'})
        self.assertEqual((saves/'SaveGame01_Player_bak0.sav').read_text(),'SaveGame01_Player_bak0.sav')
        self.assertEqual((saves/'SaveGame01-Progress.sav').read_text(),'SaveGame01-Progress.sav')
        self.assertEqual((saves/'SaveGame01 Settings.sav').read_text(),'SaveGame01 Settings.sav')
        self.assertEqual((saves/'SaveGame010_Player.sav').read_text(),'new')
        self.assertEqual((saves/'SaveGame02_Player.sav').read_text(),'new')
    def test_renamed_independent_imports_find_same_platform_game(self):
        a,save_a=self.store('A','source-id','The First Berserker: Khazan')
        b,save_b=self.store('B','different-id','第一狂战士：卡赞')
        self.file(save_a,'progress.sav','from A');self.file(save_b,'progress.sav','from B')
        a.upload('source-id',a.backup('source-id'))
        records=b.cloud_history('different-id');self.assertEqual(len(records),1)
        snapshot=b.receive_cloud_snapshot('different-id',records[0])
        self.assertEqual((save_b/'progress.sav').read_text(),'from B')
        b.restore('different-id',snapshot)
        self.assertEqual((save_b/'progress.sav').read_text(),'from A')
    def test_different_accounts_require_mapping_and_preserve_unselected_account(self):
        a,save_a=self.store('A','source');b,save_b=self.store('B','target')
        source='76561198000000001';target='76561198000000002';other='76561198000000003'
        self.file(save_a/source,'SaveGame01_Player.sav','source progress')
        self.file(save_b/target,'SaveGame01_Player.sav','target progress');self.file(save_b/other,'progress.sav','other progress')
        a.upload('source',a.backup('source'));records=b.cloud_history('target')
        snapshot=b.receive_cloud_snapshot('target',records[0])
        preview=b.restore_preview('target',snapshot);self.assertTrue(preview['needs_mapping'])
        with self.assertRaisesRegex(ValueError,'账号'):b.restore('target',snapshot)
        self.assertEqual((save_b/target/'SaveGame01_Player.sav').read_text(),'target progress')
        b.restore('target',snapshot,{'source_account':source,'target_account':target})
        self.assertFalse((save_b/source).exists())
        self.assertEqual((save_b/target/'SaveGame01_Player.sav').read_text(),'source progress')
        self.assertEqual((save_b/other/'progress.sav').read_text(),'other progress')
    def test_different_platform_same_name_cannot_restore(self):
        a,save_a=self.store('A');b,save_b=self.store('B',platform='epic',external='another-version')
        self.file(save_a,'progress.sav');self.file(save_b,'progress.sav','B')
        a.upload('game',a.backup('game'));record=a.cloud_history('game')[0]
        self.assertEqual(b.cloud_history('game'),[])
        with self.assertRaisesRegex(ValueError,'平台'):b.receive_cloud_snapshot('game',record)
        self.assertEqual((save_b/'progress.sav').read_text(),'B')
    def test_tampered_local_archive_does_not_touch_saves(self):
        store,saves=self.store('A');self.file(saves,'progress.sav','keep')
        archive=store.backup('game');archive.write_bytes(archive.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'校验'):store.restore('game',store.history('game')[0]['id'])
        self.assertEqual((saves/'progress.sav').read_text(),'keep')
    def test_failed_commit_rolls_back_current_folder(self):
        store,saves=self.store('A');self.file(saves,'progress.sav','old');store.backup('game')
        self.file(saves,'progress.sav','new');original=Path.rename
        def rename(path,target):
            if path.name=='prepared':raise OSError('fixture commit failure')
            return original(path,target)
        with patch.object(Path,'rename',rename):
            with self.assertRaises(OSError):store.restore('game',store.history('game')[0]['id'])
        self.assertEqual((saves/'progress.sav').read_text(),'new')
        self.assertEqual(len(list(saves.parent.glob('SaveGames.before-restore.*'))),1)
    def test_real_search_endpoint_and_bounded_results(self):
        payload={'results':[{'title':'Game save','url':'https://example.com/game','content':'%LOCALAPPDATA%/BBQ/Saved/SaveGames'}]}
        with patch('save_web.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as call:
            sources=search('Game','fixture-key')
        self.assertEqual(call.call_args.args[0].full_url,'https://api.deepseek.com/v1/tools/search')
        self.assertTrue(json.loads(call.call_args.args[0].data)['need_content'])
        hint={'source_url':sources[0]['url'],'relative':'BBQ/Saved/SaveGames'}
        self.assertTrue(supported_hint(hint,sources))
        self.assertFalse(supported_hint({**hint,'relative':'OtherGame/Saves'},sources))
        self.assertFalse(supported_hint({**hint,'source_url':'https://unprovided.example'},sources))
    def test_model_web_hint_requires_citable_path_and_no_invented_path(self):
        source={'title':'Game','url':'https://example.com/game','text':'%LOCALAPPDATA%/BBQ/Saved/SaveGames'}
        value={'english_name':'Game','aliases':[],'hints':[{'root':'local','relative':'BBQ/Saved/SaveGames','source_url':source['url']},
                                                            {'root':'local','relative':'Invented/Saves','source_url':source['url']}]}
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
        with patch('ai_match.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            result=identify_game('Game','','fixture-key','fixture-model',web_sources=[source])
        self.assertEqual(len(result['hints']),1)
    def test_cancelled_search_never_sends_request(self):
        cancel=threading.Event();cancel.set()
        with patch('save_web.urlopen') as request:self.assertEqual(search('Game','fixture-key',cancel),[])
        request.assert_not_called()
    def test_literal_internal_path_is_retained_when_model_omits_it(self):
        from save_web import extract_paths
        source={'title':'Game alternate save','url':'https://example.com/game','text':'Game uses AppData\\Local\\BBQ\\Saved\\SaveGames, not the other folder.'}
        hints=extract_paths([source],'Game')
        self.assertEqual(hints[0]['relative'],'BBQ/Saved/SaveGames')
        self.assertEqual(extract_paths([source],'Unrelated Game'),[])
    def test_steam_appid_remote_is_found_without_matching_folder_name(self):
        remote=self.root/'Steam/userdata/12345678/2680010/remote'
        self.file(remote,'progress.sav');self.file(remote.parent.parent/'999/remote','other.sav')
        with patch('matching.roots_for',return_value={'local':self.root/'empty'}),patch('library_sources.steam_roots',return_value=[self.root/'Steam']):
            candidates,_=scan('Entirely Different Name',{'_steam_appid':'2680010'})
        self.assertEqual(select_candidate({'candidates':candidates})['path'],str(remote))
        self.assertFalse(any('/999/' in Path(row['path']).as_posix() for row in candidates))
    def test_progress_after_many_settings_is_not_truncated_out(self):
        from matching import inspect_directory
        path=self.root/'Game'
        for index in range(35):self.file(path,'settings_'+str(index)+'.json','{}')
        self.file(path,'zzz.sav')
        files=inspect_directory(path)
        self.assertIn('zzz.sav',files);self.assertLessEqual(len(files),30)
        self.assertTrue(evidence({'path':str(path),'files':files}))
    def test_reliable_local_match_does_not_pay_for_web_search(self):
        from match_engine import match
        store,saves=self.store('A');self.file(saves,'progress.sav')
        store.settings.update(ai_enabled=True,match_network=True)
        candidate={'path':str(saves),'confidence':.95,'files':['progress.sav']}
        with patch('matching.scan',return_value=([candidate],[])),patch('match_engine.cached_ai',return_value={}),patch('match_engine.cached_network',return_value={}),patch('match_engine.cached_web') as web:
            match(store,'game')
        web.assert_not_called()
    def test_web_second_pass_only_when_first_path_is_unavailable(self):
        from match_engine import match
        store,_=self.store('A',title='Game');store.settings.update(ai_enabled=True,match_network=True,match_ai_review=False)
        local=self.root/'local';self.file(local/'Coded/Saved/SaveGames','progress.sav')
        resources=self.root/'resources/ui';resources.mkdir(parents=True);(resources/'save-rules.json').write_text('{"rules":[]}')
        def identity(path):return {'english_name':'Game','hints':[{'root':'local','relative':path,'reason':'web'}]}
        with patch('matching.roots_for',return_value={'local':local}),patch('library_sources.steam_roots',return_value=[]),patch('services.RESOURCES',resources.parent),patch('match_engine.cached_ai',return_value={}),patch('match_engine.cached_network',return_value={}),patch('match_engine.cached_web',side_effect=[identity('Missing/Saves'),identity('Coded/Saved/SaveGames')]) as web:
            result=match(store,'game')
        self.assertEqual(web.call_count,2);self.assertTrue(web.call_args.args[-1])
        self.assertTrue(select_candidate(result))
    def test_web_cache_reuses_evidence_without_saving_key(self):
        from match_engine import cached_web
        store,_=self.store('A');store.save_settings({'ai_key':'fixture-web-key'})
        source={'title':'Khazan','url':'https://example.com/game','text':'Khazan %LOCALAPPDATA%/BBQ/Saved/SaveGames'}
        identity={'english_name':'Khazan','hints':[{'root':'local','relative':'BBQ/Saved/SaveGames','source_url':source['url']}]}
        with patch('save_web.search',return_value=[source]) as query,patch('ai_match.identify_game',return_value=identity):
            first=cached_web(store,store.games[0],{},identity,threading.Event())
            second=cached_web(store,store.games[0],{},identity,threading.Event())
        self.assertEqual(first,second);self.assertEqual(query.call_count,1)
        self.assertNotIn('fixture-web-key',(store.profile/'save-web-cache.json').read_text(encoding='utf-8'))
    def test_cancellation_returns_while_web_request_is_still_finishing(self):
        from match_engine import match
        from concurrent.futures import ThreadPoolExecutor
        store,_=self.store('A');store.settings.update(ai_enabled=True,match_network=True)
        started=threading.Event();gate=threading.Event();cancel=threading.Event()
        def web(*args):started.set();gate.wait(3);return {}
        with patch('matching.scan',return_value=([],[])),patch('match_engine.cached_ai',return_value={}),patch('match_engine.cached_network',return_value={}),patch('match_engine.cached_web',side_effect=web):
            with ThreadPoolExecutor(max_workers=1) as worker:
                future=worker.submit(match,store,'game',None,cancel)
                try:
                    self.assertTrue(started.wait(2));cancel.set();result=future.result(timeout=1)
                    self.assertIn('停止',result['message'])
                finally:gate.set()
    def test_overlapping_parent_and_child_games_are_not_automatically_applied(self):
        from save_workflow import run_workflow
        store,_=self.store('A');store.local={}
        store.games=[{'id':'one','name':'Game one'},{'id':'two','name':'Game two'}]
        parent=self.root/'shared';child=parent/'subgame'
        self.file(parent,'progress.sav');self.file(child,'progress.sav')
        store.match_report=[{'id':ident,'name':ident,'candidates':[{'path':str(path),'confidence':.95,'files':['progress.sav']}]} for ident,path in [('one',parent),('two',child)]]
        result=run_workflow(store,['one','two'],lambda row:None,threading.Event(),upload=False,recheck=False)
        self.assertEqual(result['review'],2);self.assertEqual(store.local,{})
    def test_more_than_200_cloud_versions_remain_browsable_without_deletion(self):
        store,_=self.store('A');remote=self.root/'remote'/store.settings['cloud_folder']/'Khazan/SaveGames';remote.mkdir(parents=True)
        for index in range(205):(remote/(str(index)+'.zip')).write_bytes(b'listing fixture')
        records=store.cloud_history('game')
        self.assertEqual(len(records),200)
        self.assertEqual(len(list(remote.glob('*.zip'))),205)
    def test_legacy_archive_without_sidecar_is_listed_and_can_be_received(self):
        store,saves=self.store('A');self.file(saves,'progress.sav')
        archive=store.backup('game');remote=self.root/'remote'/store.settings['cloud_folder']/'Khazan/SaveGames';remote.mkdir(parents=True)
        shutil.copy2(archive,remote/archive.name)
        records=store.cloud_history('game');self.assertEqual(len(records),1);self.assertFalse(records[0]['verified'])
        self.assertTrue(store.receive_cloud_snapshot('game',records[0]))
    def test_malformed_sidecar_does_not_hide_the_archive(self):
        store,_=self.store('A');remote=self.root/'remote'/store.settings['cloud_folder']/'Khazan/SaveGames';remote.mkdir(parents=True)
        (remote/'fixture.zip').write_bytes(b'fixture');(remote/'fixture.zip.json').write_text('[]')
        records=store.cloud_history('game');self.assertEqual(len(records),1);self.assertFalse(records[0]['verified'])
    def test_roman_sequel_does_not_take_first_game_progress(self):
        self.file(self.root/'Code Vein/Saved/SaveGames','progress.sav')
        candidates,_=scan('CODE VEIN II',{},root_override={'local':self.root})
        self.assertEqual(candidates,[])
    def test_roman_title_can_find_the_matching_arabic_directory(self):
        self.file(self.root/'My Quest 2/Saved/SaveGames','progress.sav')
        candidates,_=scan('My Quest II',{},root_override={'local':self.root})
        self.assertTrue(select_candidate({'candidates':candidates}))
    def test_chinese_number_without_space_does_not_take_previous_sequel(self):
        self.file(self.root/'纪念碑谷2/Saves','progress.sav')
        candidates,_=scan('纪念碑谷3',{},root_override={'local':self.root})
        self.assertEqual(candidates,[])


if __name__=='__main__':unittest.main(verbosity=2)
