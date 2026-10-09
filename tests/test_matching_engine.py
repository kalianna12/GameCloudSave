from pathlib import Path
import sys,tempfile,gc,unittest,threading,json,io,time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from matching import scan
from local_index import directories,clear
from save_workflow import select_candidate,evidence
from ai_match import review_directories,identify_game
from match_engine import match,score_reviews,ai_weight

class MatchingEngine(unittest.TestCase):
    def setUp(self):
        clear();self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
        self.store=Store(Path(self.temp.name),'match-engine')
        self.store.games=[{'id':'game','name':'Rubinite','cover':''}]
        self.store.settings.update({'match_network':False,'ai_enabled':False})
        self.root=Path(self.temp.name)/'LocalLow'
        self.release=self.root/'Cup Dog Games/Rubinite/Release'
        for name in ('save1','save3','ChallengeSave'):
            directory=self.release/name;directory.mkdir(parents=True)
            (directory/'GameData.json').write_text('ENC1:fixture-encrypted-save')
            (directory/'Flags.json').write_text('ENC1:fixture-encrypted-flags')
        self.identity={'english_name':'Rubinite','aliases':[],'developers':['Cup Dog Games'],'publishers':[],'hints':[]}
    def tearDown(self):clear();gc.collect();self.temp.cleanup()
    def test_unknown_developer_structure_found_without_path_hint(self):
        candidates,_=scan('红眼露比',{},self.identity,{'locallow':self.root})
        selected=select_candidate({'candidates':candidates})
        self.assertEqual(selected['path'],str(self.release.resolve()))
        self.assertTrue(selected['score_details']['developer_match'])
        self.assertTrue(evidence(selected))
    def test_fuzzy_game_directory_is_reported_but_not_trusted_automatically(self):
        (self.root/'Another Studio/Rubin ite Deluxe').mkdir(parents=True)
        candidates,_=scan('Rubinite',{},root_override={'locallow':self.root})
        self.assertTrue(any('Rubin ite Deluxe' in candidate['path'] for candidate in candidates))
    def test_installation_runtime_and_unity_analytics_excluded(self):
        analytics=self.root/'Cup Dog Games/Rubinite/Unity/ShaderVariantAnalytics';analytics.mkdir(parents=True)
        (analytics/'ShaderRuntimeInfoEvent.json').write_text('{"chapter":1}')
        runtime=self.root/'Rubinite_Data/Managed';runtime.mkdir(parents=True)
        candidates,_=scan('Rubinite',{},self.identity,{'locallow':self.root,'install':self.root})
        self.assertFalse(any('/Unity' in Path(c['path']).as_posix() or 'Rubinite_Data' in c['path'] for c in candidates))
    def test_index_caches_and_bounds_results(self):
        rows=directories(self.root,budget=2)
        self.assertLessEqual(len(rows),2)
        with patch('local_index.os.scandir',side_effect=AssertionError('cache miss')):
            self.assertEqual(directories(self.root,budget=2),rows)
    def test_index_cancellation(self):
        cancelled=threading.Event();cancelled.set()
        self.assertFalse(directories(self.root,cancel=cancelled))
    def test_three_modes_start_concurrently_and_local_results_stream_first(self):
        self.store.settings.update({'match_network':True,'ai_enabled':True})
        barrier=threading.Barrier(3);gate=threading.Event();shown=threading.Event();rows=[]
        candidate={'path':str(self.release),'confidence':.92,'files':['save3/GameData.json']}
        def local(*args,**kwargs):
            if len(args)>=3 and args[2] is None:barrier.wait(timeout=2)
            return [candidate],[]
        def provider(*args,**kwargs):barrier.wait(timeout=2);gate.wait(timeout=3);return self.identity
        def progress(row):
            rows.append(row)
            if row['candidates']:shown.set()
        with patch('matching.scan',side_effect=local),patch('match_engine.cached_network',side_effect=provider),patch('match_engine.cached_ai',side_effect=provider):
            with ThreadPoolExecutor(max_workers=1) as runner:
                future=runner.submit(match,self.store,'game',progress)
                self.assertTrue(shown.wait(timeout=2));self.assertFalse(future.done())
                gate.set();result=future.result(timeout=3)
        self.assertEqual(result['developers'],['Cup Dog Games'])
        self.assertEqual(len(result['scan_modes']),3)
    def test_network_failure_does_not_discard_local_results(self):
        self.store.settings['match_network']=True
        with patch('matching.roots_for',return_value={'locallow':self.root}),patch('match_engine.cached_network',side_effect=ValueError('offline')):
            result=match(self.store,'game')
        self.assertTrue(result['candidates']);self.assertEqual(result['network_warning'],'offline')
    def test_cancel_returns_without_waiting_for_network_completion(self):
        self.store.settings['match_network']=True;started=threading.Event();gate=threading.Event();cancel=threading.Event()
        def provider(*args):started.set();gate.wait(timeout=3);return {}
        with patch('match_engine.cached_network',side_effect=provider),patch('matching.roots_for',return_value={'locallow':self.root}):
            with ThreadPoolExecutor(max_workers=1) as runner:
                future=runner.submit(match,self.store,'game',None,cancel)
                self.assertTrue(started.wait(timeout=2));cancel.set()
                try:result=future.result(timeout=1)
                finally:gate.set()
        self.assertIn('停止',result['message'])
    def test_ai_score_does_not_replace_missing_local_evidence(self):
        self.store.save_settings({'ai_enabled':True,'ai_key':'dummy','match_network':False})
        empty=self.root/'RubiniteCache';empty.mkdir()
        candidates=[{'path':str(empty),'confidence':.8,'files':[]},{'path':str(empty/'missing'),'confidence':.8,'files':[]}]
        with patch('matching.scan',return_value=(candidates,[])),patch('match_engine.cached_ai',return_value=self.identity),patch('ai_match.review_directories',return_value={0:{'confidence':1,'reason':'guess'}}):
            result=match(self.store,'game')
        self.assertIsNone(select_candidate(result));self.assertEqual(result['candidates'][0]['confidence'],.8)
    def test_ai_downranks_configuration_and_promotes_params_save_directory(self):
        config=self.root/'Roaming/Naughty Dog/The Last of Us Part II/crs';config.mkdir(parents=True)
        (config/'settings.dat').write_text('settings fixture')
        save=self.root/'Documents/The Last of Us Part II/76561197960271872/savedata';(save/'SAVEFILE0A').mkdir(parents=True)
        (save/'SAVEFILE0A/params.json').write_text('{"title":"slot"}')
        candidates=[{'path':str(config),'confidence':.87,'files':['settings.dat']},{'path':str(save),'confidence':.85,'files':['SAVEFILE0A/params.json']}]
        verdicts={0:{'confidence':.25,'reason':'配置目录'},1:{'confidence':.95,'reason':'存档容器'}}
        score_reviews(candidates,verdicts,ai_weight({}))
        self.assertEqual(candidates[0]['path'],str(save));self.assertEqual(candidates[0]['confidence'],.93)
        self.assertEqual(candidates[1]['confidence'],.41);self.assertEqual(candidates[0]['local_confidence'],.85)
        self.assertIsNone(select_candidate({'candidates':candidates}), 'Ranking alone should not auto-confirm unsupported save evidence')
    def test_ai_reviews_even_single_rule_candidate_and_reuses_scores_with_new_weight(self):
        self.store.save_settings({'ai_enabled':True,'ai_key':'dummy','match_network':False})
        candidate={'path':str(self.release),'confidence':.92,'files':['save3/GameData.json','save3/Flags.json']}
        with patch('matching.scan',side_effect=lambda *args,**kwargs:([dict(candidate)],[])),patch('match_engine.cached_ai',return_value=self.identity),patch('ai_match.review_directories',return_value={0:{'confidence':.2,'reason':'not save'}}) as review:
            result=match(self.store,'game');self.assertEqual(result['candidates'][0]['confidence'],.38)
            self.store.settings['match_ai_weight']=90
            second=match(self.store,'game');self.assertEqual(second['candidates'][0]['confidence'],.27)
            self.assertEqual(review.call_count,1)
            self.assertIsNone(select_candidate(second))
    def test_high_ai_score_does_not_auto_confirm_bundled_save_or_escaped_file(self):
        folder=self.root/'patch';folder.mkdir();(folder/'slot.sav').write_bytes(b'fixture')
        sample={'path':str(folder),'confidence':.55,'files':['slot.sav'],'sample_backup':True}
        score_reviews([sample],{0:{'confidence':1,'reason':'guess'}},.75);self.assertEqual(sample['confidence'],.55)
        escaped={'path':str(folder),'confidence':.8,'files':['../patch/slot.sav','../../outside.sav']}
        # ../patch/slot.sav resolves inside the root; use only the outside path for this check.
        escaped['files']=['../Cup Dog Games/Rubinite/Release/save3/GameData.json']
        score_reviews([escaped],{0:{'confidence':1,'reason':'guess'}},.75);self.assertEqual(escaped['confidence'],.8)
    def test_weight_defaults_and_invalid_values_are_bounded(self):
        self.assertEqual(ai_weight({}),.75)
        for value in ('bad',float('nan'),None):self.assertEqual(ai_weight({'match_ai_weight':value}),.75)
        self.assertEqual(ai_weight({'match_ai_weight':1000}),.95)
    def test_existing_reviews_are_reweighted_once_without_changing_manual_directory(self):
        candidate={'path':str(self.release),'confidence':.92,'local_confidence':.92,'ai_confidence':.3,'files':['save3/GameData.json'],'ai_reason':'low'}
        self.store.save_match_report([{'id':'game','status':'applied','applied_path':str(self.release),'candidates':[candidate]}])
        self.store.save_game('game',{'save_dir':str(self.release)})
        self.assertTrue(self.store.reweight_matches());self.assertFalse(self.store.reweight_matches())
        self.assertEqual(self.store.match_report[0]['candidates'][0]['confidence'],.46)
        self.store.save_settings({'match_ai_weight':90})
        self.assertEqual(self.store.match_report[0]['candidates'][0]['confidence'],.36)
        self.assertEqual(self.store.local['game']['save_dir'],str(self.release))
    def test_steam_lookup_uses_official_metadata(self):
        from network_metadata import lookup
        responses=[{'items':[{'id':1845250,'name':'Rubinite'},{'id':9,'name':'Rubinite Soundtrack'}]},
                   {'1845250':{'success':True,'data':{'name':'Rubinite','type':'game','developers':['Cup Dog Games'],'publishers':[]}}}]
        with patch('network_metadata.get',side_effect=responses):result=lookup('Rubinite')
        self.assertEqual(result['developers'],['Cup Dog Games']);self.assertIn('store.steampowered.com',result['sources'][0]['url'])
    def test_ai_unknown_candidate_rejected(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'matches':[{'id':999,'confidence':1}]})}}]}
        with patch('ai_match.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaises(ValueError):review_directories('Rubinite',[{'path':str(self.release),'files':[]}],'dummy','test')
    def test_ai_candidate_payload_does_not_send_user_path_or_contents(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':'{"matches":[]}'}}]}
        with patch('ai_match.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            review_directories('Rubinite',[{'path':str(self.release),'files':['save3/GameData.json']}],'dummy','test')
        content=json.loads(call.call_args.args[0].data)['messages'][1]['content']
        self.assertNotIn(str(self.temp.name),content);self.assertNotIn('ENC1:',content)

if __name__=='__main__':unittest.main(verbosity=2)
