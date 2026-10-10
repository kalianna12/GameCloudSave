"""Preview has no library writes; application fills only still-missing fields."""
from pathlib import Path
import sys,tempfile,threading,unittest
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from library_enrichment import preview,apply

class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'enrichment')
        self.store.root.joinpath('covers').mkdir()
        self.existing=self.store.root/'covers/existing.jpg';self.existing.write_bytes(b'existing-image')
        self.store.games=[{'id':'known','name':'Existing','release_date':'2000-01-01','category':'视觉小说','tags':['悬疑'],'series':'Existing series','cover':str(self.existing)},
                          {'id':'missing','name':'Missing','category':'其他','tags':[],'cover':''}]
        write_json(self.store.root/'library.json',self.store.games)
        self.data={'release_date':'2020-02-03','release_date_source':'Steam','tags':['角色扮演'],'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/1/'}
        self.cover={'id':'steam:1','appid':'1','name':'Missing','image':'https://shared.fastly.steamstatic.com/example.jpg','provider':'steam','score':1}
    def tearDown(self):self.temp.cleanup()
    def download(self,store,record):
        path=store.root/'covers/candidate.jpg';path.write_bytes(b'candidate-image');return str(path)
    def query(self,**options):
        with patch('library_metadata.lookup',return_value=self.data),patch('cover_sources.search',return_value=[self.cover]),patch('cover_sources.download',side_effect=self.download):
            return preview(self.store,options=options)
    def test_preview_does_not_change_games_or_library_file(self):
        original=deepcopy(self.store.games);disk=(self.store.root/'library.json').read_bytes()
        result=self.query(dates=True,tags=True,covers=True,use_ai=False)
        self.assertEqual(self.store.games,original);self.assertEqual((self.store.root/'library.json').read_bytes(),disk)
        rows={row['id']:row for row in result['rows']}
        self.assertEqual(rows['known']['fields'],{})
        self.assertEqual(rows['missing']['fields']['release_date'],'2020-02-03');self.assertIn('cover',rows['missing']['fields'])
    def test_apply_keeps_every_existing_field_and_cover(self):
        result=self.query(dates=True,tags=True,covers=True,use_ai=False);original=deepcopy(self.store.games[0])
        with patch.object(self.store,'prepare_thumbnails'):apply(self.store,result['rows'],['known','missing'])
        self.assertEqual(self.store.games[0],original);self.assertEqual(self.existing.read_bytes(),b'existing-image')
        self.assertEqual(self.store.games[1]['release_date'],'2020-02-03');self.assertEqual(self.store.games[1]['tags'],['角色扮演'])
        self.assertEqual(Store(self.temp.name,'enrichment').games[1]['category'],'角色扮演')
    def test_user_filling_fields_after_preview_wins(self):
        result=self.query(dates=True,tags=True,covers=True,use_ai=False)
        self.store.games[1].update(release_date='1999-09-09',tags=['手动标签'],series='Manual',cover=str(self.existing),category='动作冒险')
        before=deepcopy(self.store.games[1]);apply(self.store,result['rows'],['missing'])
        self.assertEqual(self.store.games[1],before)
    def test_only_selected_rows_are_applied(self):
        result=self.query(dates=True,tags=True,covers=True,use_ai=False)
        apply(self.store,result['rows'],['known']);self.assertNotIn('release_date',self.store.games[1])
        with self.assertRaises(ValueError):apply(self.store,result['rows'],['invalid'])
    def test_options_disable_queries_and_never_replace_existing_tags(self):
        with patch('library_metadata.lookup') as lookup,patch('cover_sources.search') as covers:
            result=preview(self.store,options={'dates':False,'tags':False,'covers':False})
        self.assertFalse(lookup.called);self.assertFalse(covers.called);self.assertTrue(all(not row['fields'] for row in result['rows']))
    def test_ai_is_supplemental_and_previewed(self):
        proposed=[{'id':'known','category':'射击竞技','tags':['射击'],'series':'Wrong'}, {'id':'missing','category':'解谜休闲','tags':['解谜','悬疑'],'series':'Pair','tags_source':'DeepSeek 补缺'}]
        with patch('library_metadata.lookup',return_value={}),patch('library_organizer.suggestions',return_value=proposed):
            result=preview(self.store,options={'dates':False,'tags':True,'covers':False,'use_ai':True})
        rows={row['id']:row for row in result['rows']}
        self.assertEqual(rows['known']['fields'],{});self.assertEqual(rows['missing']['fields']['tags'],['解谜','悬疑'])
        self.assertEqual(self.store.games[1]['tags'],[])
    def test_cancel_has_no_library_side_effect(self):
        cancel=threading.Event();cancel.set();original=deepcopy(self.store.games)
        with patch('library_metadata.lookup') as lookup,patch('cover_sources.search') as covers:
            result=preview(self.store,cancel=cancel)
        self.assertTrue(result['cancelled']);self.assertFalse(lookup.called);self.assertFalse(covers.called)
        self.assertEqual(self.store.games,original)
    def test_failed_sources_do_not_invent_values(self):
        with patch('library_metadata.lookup',side_effect=TimeoutError),patch('cover_sources.search',side_effect=TimeoutError):
            result=preview(self.store,options={'tags':False,'dates':True,'covers':True})
        row=next(row for row in result['rows'] if row['id']=='missing');self.assertEqual(row['fields'],{});self.assertTrue(row['notes'])

if __name__=='__main__':unittest.main(verbosity=2)
