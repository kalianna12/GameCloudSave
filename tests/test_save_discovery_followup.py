"""Regional dates, fresh on-disk progress evidence, scoped searches and new imports."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from unittest.mock import patch
import io,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from matching import inspect_directory,scan
from save_workflow import evidence,select_candidate
from match_engine import score_reviews
from library_metadata import lookup,fetch,steam_date
from library_catalog import recently_added,sections
from library_sources import import_rows
from save_search import targets,searched

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
        self.store=Store(self.root/'data','discovery')
    def tearDown(self):self.temp.cleanup()

    def test_cn_region_retry_and_local_timezone_cookie(self):
        raw={'1329410':{'success':True,'data':{'name':'Mahjong Soul','release_date':{'date':'15 Jul, 2020'},'genres':[]}}}
        def query(url,*args):return raw if 'cc=us' in url else {'1329410':{'success':False}}
        with patch('library_metadata.fetch',side_effect=query) as request:
            self.assertEqual(lookup({'name':'Mahjong Soul','steam_appid':'1329410'})['release_date'],'2020-07-15')
            self.assertIn('cc=cn',request.call_args_list[0].args[0]);self.assertIn('cc=us',request.call_args_list[1].args[0])
        with patch('library_metadata.local_utc_offset',return_value=28800),patch('library_metadata.urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as request:
            fetch('https://store.steampowered.com/api/appdetails?appids=1329410')
            self.assertEqual(request.call_args.args[0].get_header('Cookie'),'timezoneOffset=28800,0')
        self.assertEqual(steam_date({'date':'2020 年 7 月 15 日'}),'2020-07-15')
        self.assertEqual(steam_date({'date':'2020 年 2 月 30 日'}),'')
        self.assertEqual(steam_date({'date':None}),'')

    def test_ori_progress_file_beats_settings_only_and_ai_guess(self):
        local=self.root/'Local';saves=local/'Ori and the Will of The Wisps';saves.mkdir(parents=True)
        config=local/'Moon Studios/OriAndTheWillOfTheWisps';config.mkdir(parents=True)
        (saves/'settings.bin').write_bytes(b'settings')
        (saves/'saveFile0.uberstate').write_bytes(b'fixture-progress')
        (saves/'saveFile0_bkup0.uberstate').write_bytes(b'fixture-backup')
        (config/'wwiseOutputOverride.json').write_text('{"audio":true}')
        candidates,_=scan('Ori and the Will of the Wisps',{},root_override={'local':local})
        real=next(c for c in candidates if Path(c['path'])==saves)
        self.assertIn('saveFile0.uberstate',real['files'][:2]);self.assertTrue(evidence(real))
        score_reviews(candidates,{i:{'confidence':.1,'reason':'unfamiliar extension'} for i in range(len(candidates))},.75)
        self.assertEqual(Path(candidates[0]['path']),saves);self.assertGreaterEqual(candidates[0]['confidence'],.85)
        self.assertIn('本机',candidates[0]['score_note'])
        self.assertEqual(Path(select_candidate({'candidates':candidates})['path']),saves)
        # Files are probed again: deleting progress must invalidate the strong evidence.
        (saves/'saveFile0.uberstate').unlink();(saves/'saveFile0_bkup0.uberstate').unlink()
        self.assertFalse(evidence(real))
        changed,_=scan('Ori and the Will of the Wisps',{},root_override={'local':local})
        self.assertFalse(next(c for c in changed if Path(c['path'])==saves)['has_save_evidence'])

    def test_priority_scopes_preserve_confirmations_and_unsearched_first(self):
        self.store.games=[{'id':name,'name':name,'added_at':added} for name,added in [('old','2020'),('new','2026'),('confirmed','2025'),('offline','2026'),('cancelled','2025')]]
        self.store.local={g['id']:{'installed':g['id']!='offline'} for g in self.store.games}
        self.store.local['confirmed']['save_dir']='confirmed-device-folder'
        self.store.match_report=[{'id':'old','status':'review','checked_at':'2025'}, {'id':'confirmed','status':'applied'}, {'id':'cancelled','status':'review','completed':False}]
        self.assertEqual(targets(self.store),['new','cancelled','old'])
        self.assertEqual(targets(self.store,'unsearched'),['new','cancelled'])
        self.assertEqual(set(targets(self.store,'all',False)),{g['id'] for g in self.store.games})
        self.assertEqual(targets(self.store,'pending',False,['new','confirmed']),['new'])
        self.assertFalse(searched({'status':'running'}));self.assertFalse(searched({'status':'review','completed':False}))

    def test_new_marker_window_and_section_do_not_invent_old_timestamps(self):
        now=datetime.now(timezone.utc)
        fresh={'id':'fresh','name':'Fresh','added_at':now.isoformat()}
        old={'id':'old','name':'Old','added_at':(now-timedelta(days=4)).isoformat()}
        self.assertTrue(recently_added(fresh,now));self.assertFalse(recently_added(old,now))
        self.assertFalse(recently_added({'id':'legacy','name':'Legacy'},now))
        row=next(r for r in sections([fresh,old]) if r['id']=='new')
        self.assertEqual([g['id'] for g in row['items']],['fresh']);self.assertEqual(row['target'],'new')
        install=self.root/'game';install.mkdir()
        self.store.games=[{'id':'steam:1','name':'Old','steam_appid':'1','platform':'steam','external_id':'1','cover':''}]
        self.store.local['steam:1']={'install_dir':str(install)}
        import_rows(self.store,[{'id':'x','name':'Old','platform':'steam','external_id':'1','install_dir':str(install),'installed':True}])
        self.assertNotIn('added_at',self.store.games[0])

if __name__=='__main__':unittest.main(verbosity=2)
