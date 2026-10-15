"""Retry only unresolved items; renamed titles and VNDB dates remain reviewable."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys,tempfile,threading,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from library_metadata import lookup
from library_enrichment import preview
from catalog_match import best_match,title_key,query_hints,search_queries
from cover_sources import search

class CatalogRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'retry')
        self.store.games=[{'id':'g','name':'Renamed title','tags':[],'category':'其他','cover':''}]
        self.store.local={'g':{}}
        self.data={'release_date':'2001-02-03','release_date_source':'Steam','tags':[]}
        self.steam={'id':'steam:123','appid':'123','name':'Original Game','provider':'steam','score':1,'image':''}
    def tearDown(self):self.temp.cleanup()
    def run_preview(self,**options):return preview(self.store,options={'dates':True,'tags':False,'covers':False,**options})
    def test_successful_first_pass_is_not_searched_again(self):
        with patch('library_metadata.lookup',return_value=self.data) as metadata,patch('cover_sources.search') as query:
            result=self.run_preview()
        self.assertEqual(metadata.call_count,1);self.assertFalse(query.called)
        self.assertNotIn('second_pass',result['rows'][0]);self.assertEqual(result['rows'][0]['fields']['release_date'],'2001-02-03')
    def test_playnite_original_name_recovers_renamed_game(self):
        self.store.games[0]['import_source']='playnite'
        raw={'_id':'g','Name':'Original Game'}
        write_json(self.store.root/'library.json',self.store.games);before=(self.store.root/'library.json').read_bytes()
        def metadata(game):return self.data if game.get('metadata_steam_appid')=='123' else {}
        def query(store,name,provider,*args):return [self.steam] if name=='Original Game' and provider=='steam' else []
        with patch.object(self.store,'read_playnite',return_value=[raw]),patch('library_metadata.lookup',side_effect=metadata),patch('cover_sources.search',side_effect=query):
            result=self.run_preview()
        row=result['rows'][0];self.assertTrue(row['second_pass']);self.assertEqual(row['matched_name'],'Original Game')
        self.assertEqual(row['fields']['release_date'],'2001-02-03');self.assertEqual(self.store.games[0]['name'],'Renamed title')
        self.assertEqual((self.store.root/'library.json').read_bytes(),before)
    def test_install_folder_and_known_aliases_are_retry_hints(self):
        self.store.local['g']['install_dir']=r'F:\Games\Original Game [中文版]'
        self.store.identities={'g':{'english_name':'Original Game','aliases':['Original Game II']}}
        hints=query_hints(self.store,self.store.games[0]);self.assertIn('Original Game',hints)
        with patch('library_metadata.lookup',side_effect=lambda game:self.data if game.get('metadata_steam_appid') else {}),patch('cover_sources.search',side_effect=lambda store,name,provider,*args:[self.steam] if name=='Original Game' and provider=='steam' else []):
            self.assertEqual(self.run_preview()['rows'][0]['fields']['release_date'],'2001-02-03')
    def test_steam_original_title_is_used_for_renamed_unreleased_game(self):
        self.store.games[0]['steam_appid']='123'
        candidate={'id':'vndb:v1','name':'Original Game','released':'2001-02-03','provider':'vndb','score':1,'image':'','page':'https://vndb.org/v1'}
        steam_fields={'release_date':'','tags':[],'matched_name':'Original Game','metadata_url':'https://store.steampowered.com/app/123/'}
        def query(store,name,provider,*args):return [candidate] if name=='Original Game' and provider=='vndb' else []
        with patch('library_metadata.lookup',return_value=steam_fields),patch('cover_sources.search',side_effect=query):row=self.run_preview()['rows'][0]
        self.assertEqual(row['fields']['release_date'],'2001-02-03');self.assertEqual(row['metadata_url'],'https://vndb.org/v1')
    def test_vndb_date_when_steam_has_not_released(self):
        game={'name':'美少女万华镜异闻 雪女','steam_appid':'123','category':'视觉小说','tags':[]}
        steam={'123':{'success':True,'data':{'release_date':{'coming_soon':True,'date':'Coming Soon'},'genres':[{'description':'Adventure'}]}}}
        vn={'results':[{'id':'v44184','title':'Bishoujo Mangekyou Ibun - Yuki Onna','aliases':['美少女萬華鏡異聞 雪女'],'released':'2024-04-26'}]}
        with patch('library_metadata.fetch',side_effect=[steam,vn]) as fetch:
            result=lookup(game)
        self.assertEqual(fetch.call_count,2);self.assertEqual(result['release_date'],'2024-04-26')
        self.assertEqual(result['release_date_source'],'VNDB（首次发行）');self.assertEqual(result['metadata_url'],'https://vndb.org/v44184')
        self.assertTrue(result['tags'])
    def test_vndb_failure_keeps_successful_steam_fields(self):
        game={'name':'Visual novel','steam_appid':'123','category':'视觉小说'}
        steam={'123':{'success':True,'data':{'name':'Original Game','release_date':{'coming_soon':True},'genres':[{'description':'Adventure'}]}}}
        with patch('library_metadata.fetch',side_effect=[steam,TimeoutError]):result=lookup(game)
        self.assertTrue(result['tags']);self.assertEqual(result['matched_name'],'Original Game');self.assertEqual(result['release_date'],'')
    def test_shortened_snow_title_fuzzy_retry_and_non_vn_category(self):
        self.store.games[0].update(name='美少女万华镜雪女',steam_appid='123')
        candidate={'id':'vndb:v44184','name':'Bishoujo Mangekyou Ibun - Yuki Onna','aliases':['美少女萬華鏡異聞 雪女'],
                   'released':'2024-04-26','provider':'vndb','score':0,'image':'','page':'https://vndb.org/v44184'}
        def query(store,name,provider,*args):return [candidate] if provider=='vndb' else [{**self.steam,'name':self.store.games[0]['name']}]
        with patch('library_metadata.lookup',return_value={}),patch('cover_sources.search',side_effect=query):row=self.run_preview()['rows'][0]
        self.assertEqual(row['fields']['release_date'],'2024-04-26');self.assertTrue(row['second_pass'])
        self.assertEqual(row['sources']['release_date'],'VNDB（首次发行）')
    def test_broad_discovery_is_rescored_against_full_title(self):
        self.assertIn('美少女万华镜',search_queries(['美少女万华镜雪女']))
        candidate={'id':'v1','name':'美少女万华镜雪女'}
        wrong={'id':'v2','name':'美少女万华镜罪与罚的少女'}
        self.assertEqual(best_match([wrong,candidate],['美少女万华镜雪女'],True)['id'],'v1')
        self.assertIsNone(best_match([wrong],['美少女万华镜雪女'],True))
    def test_numbered_sequels_editions_and_ambiguity_are_rejected(self):
        self.assertEqual(title_key('Original Game Ⅳ'),title_key('Original Game 4'))
        for wrong in ['Original Game 3','Original Game Remastered']:
            self.assertIsNone(best_match([{'id':'x','name':wrong}],['Original Game II'],True))
        self.assertIsNone(best_match([{'id':'a','name':'Original Game'},{'id':'b','name':'Original Games'}],['Original Game'],True))
    def test_cover_search_scores_multilingual_vndb_titles(self):
        data={'results':[{'id':'v44184','title':'Bishoujo Mangekyou Ibun - Yuki Onna','titles':[{'title':'美少女万华镜异闻 雪女','latin':None}],
                          'aliases':['美少女萬華鏡異聞 雪女'],'released':'2024-04-26','image':None}]}
        with patch('cover_sources.fetch_json',return_value=data):rows=search(self.store,'美少女万华镜异闻 雪女','vndb')
        self.assertEqual(rows[0]['score'],1);self.assertEqual(rows[0]['released'],'2024-04-26')
        self.assertEqual(rows[0]['image'],'') # A missing image must not hide available metadata.
    def test_japanese_title_with_simplified_character_gets_script_retry(self):
        self.store.games[0].update(name='真爱の百合は赤く染まる',category='视觉小说',tags=['视觉小说'])
        record={'id':'vndb:v26232','name':'Manakashi no Yuri wa Akaku Somaru','aliases':['真愛の百合は赤く染まる'],'released':'2019-11-08','provider':'vndb','score':0,'image':'','page':'https://vndb.org/v26232'}
        queries=[]
        def search(store,name,provider,*args):
            queries.append((name,provider));return [record] if name=='真愛の百合は赤く染まる' and provider=='vndb' else []
        with patch('library_metadata.lookup',return_value={}),patch('cover_sources.search',side_effect=search):row=self.run_preview()['rows'][0]
        self.assertIn(('真愛の百合は赤く染まる','vndb'),queries)
        self.assertEqual(row['fields']['release_date'],'2019-11-08')
        self.assertEqual(self.store.games[0]['name'],'真爱の百合は赤く染まる')
    def test_cancelling_first_pass_does_not_start_retry(self):
        cancel=threading.Event()
        def metadata(game):cancel.set();return {}
        with patch('library_metadata.lookup',side_effect=metadata),patch('cover_sources.search') as query:
            result=preview(self.store,options={'dates':True,'tags':False,'covers':False},cancel=cancel)
        self.assertTrue(result['cancelled']);self.assertFalse(query.called)
    def test_ambiguous_retry_keeps_missing_date(self):
        self.store.games[0]['source_name']='Original Game'
        candidates=[self.steam,{**self.steam,'id':'steam:124','appid':'124','name':'Original Games'}]
        with patch('library_metadata.lookup',return_value={}),patch('cover_sources.search',return_value=candidates):row=self.run_preview()['rows'][0]
        self.assertTrue(row['second_pass']);self.assertNotIn('release_date',row['fields'])

if __name__=='__main__':unittest.main(verbosity=2)
