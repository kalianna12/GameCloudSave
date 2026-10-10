"""Source precedence, compact tags, trustworthy dates and failure preservation."""
from pathlib import Path
import sys,tempfile,json,io,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from library_metadata import complete,lookup,steam_date
from library_sources import playnite_metadata,merge_metadata,import_rows,candidate
from library_organizer import suggestions
from library_catalog import prepare_game,sections
from tag_catalog import effective_tags,vocabulary

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'metadata')
    def tearDown(self):self.temp.cleanup()
    def test_precise_dates_and_english_months(self):
        for text in ['29 Feb, 2020','Feb 29, 2020','2020-02-29']:
            self.assertEqual(steam_date({'date':text}),'2020-02-29')
        for text in ['2020','Feb 2020','29 Feb, 2021','Coming Soon','Q3 2026']:
            self.assertEqual(steam_date({'date':text}),'')
        self.assertEqual(steam_date({'date':'29 Feb, 2020','coming_soon':True}),'')
    def test_source_tags_are_canonical_and_bounded(self):
        raw={'ResolvedGenres':['Visual Novel'],'ResolvedTags':['Mystery','Dating Sim','Story Rich','Cute','Magic','FPS','Indie','Fantasy','Music','Multiple Endings']}
        fields=playnite_metadata(raw)
        self.assertEqual(fields['tags'][:4],['视觉小说','悬疑','恋爱','剧情']);self.assertLessEqual(len(fields['tags']),6)
        self.assertIn('Cute',fields['source_tags']);self.assertNotIn('Cute',vocabulary([{'tags':['Cute','Magic']}]))
        old={'id':'a','name':'A','tags':['Music','Visual Novel','Mystery','Cute','Magic','Dating Sim']}
        self.assertNotIn('Cute',prepare_game(old)['tags']);self.assertIn('悬疑',prepare_game(old)['tags'])
    def test_refresh_preserves_manual_edits_and_known_dates(self):
        game={'tags':['我的标签'],'tags_manual':True,'release_date':'2000-01-01','release_date_manual':True}
        merge_metadata(game,playnite_metadata({'ReleaseDate':{'Year':2002,'Month':1,'Day':1},'ResolvedTags':['RPG']}))
        self.assertEqual(game['tags'],['我的标签']);self.assertEqual(game['release_date'],'2000-01-01')
        other={'release_date':'2000-01-01'};merge_metadata(other,playnite_metadata({}))
        self.assertEqual(other['release_date'],'2000-01-01')
        steam={'tags':['角色扮演'],'source_tags':['RPG'],'tags_source':'Steam'};merge_metadata(steam,playnite_metadata({}))
        self.assertEqual(effective_tags(steam),['角色扮演']);self.assertEqual(steam['tags_source'],'Steam')
    def test_model_only_supplements_missing_tags(self):
        self.store.games=[{'id':'a','name':'VN','source_tags':['Visual Novel','Mystery'],'tags':['Visual Novel','Music']}, {'id':'b','name':'Missing','tags':[]}]
        self.store.save_settings({'ai_key':'fixture'})
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':[
            {'id':'a','category':'射击竞技','tags':['射击','音乐节奏'],'series':''},
            {'id':'b','category':'解谜休闲','tags':['Puzzle','Mystery','Invented'],'series':''}]})}}]}
        with patch('library_organizer.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            rows={row['id']:row for row in suggestions(self.store,True,['a','b'],True)}
        self.assertEqual(rows['a']['tags'],['视觉小说','悬疑']);self.assertEqual(rows['a']['category'],'视觉小说')
        self.assertEqual(rows['b']['tags'],['解谜','悬疑']);self.assertEqual(self.store.games[1]['tags'],[])
    def test_completion_keeps_known_and_manual_metadata_and_caches(self):
        self.store.games=[{'id':'a','name':'Game','tags':[]}, {'id':'b','name':'Manual','tags':['自己选择'],'tags_manual':True,'release_date':'1999-09-09','release_date_manual':True}]
        fields={'release_date':'2020-02-29','release_date_source':'Steam','tags':['角色扮演'],'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/1/'}
        with patch('library_metadata.lookup',return_value=fields) as query:
            result=complete(self.store);self.assertEqual(result['dated'],1);self.assertEqual(query.call_count,1)
            complete(self.store);self.assertEqual(query.call_count,1)
        self.assertEqual(self.store.games[1]['tags'],['自己选择']);self.assertEqual(self.store.games[1]['release_date'],'1999-09-09')
        self.assertEqual(Store(self.temp.name,'metadata').games[0]['release_date'],'2020-02-29')
    def test_failed_or_ambiguous_query_does_not_invent_date(self):
        self.store.games=[{'id':'a','name':'VN','tags':['视觉小说']}]
        with patch('library_metadata.lookup',side_effect=TimeoutError):self.assertEqual(complete(self.store)['failed'],1)
        self.assertNotIn('release_date',self.store.games[0])
        with patch('library_metadata.fetch',return_value={'results':[{'id':'v1','title':'VN','released':'2000-01-01'},{'id':'v2','title':'VN','released':'2001-01-01'}]}):
            self.assertEqual(lookup(self.store.games[0]),{})
        with patch('library_metadata.fetch',return_value={'results':[{'id':'v1','title':'VN','released':'2000-01'}]}):
            self.assertEqual(lookup(self.store.games[0])['release_date'],'')
    def test_manual_metadata_validation_is_atomic(self):
        self.store.games=[{'id':'a','name':'Game','tags':[]}]
        self.store.update_library([{'id':'a','tags':['悬疑','解谜'],'release_date':'2001-02-03'}])
        self.assertTrue(self.store.games[0]['tags_manual']);self.assertTrue(self.store.games[0]['release_date_manual'])
        with self.assertRaises(ValueError):self.store.update_library([{'id':'a','tags':['改动'],'release_date':'2001-02-30'}])
        self.assertEqual(self.store.games[0]['tags'],['悬疑','解谜'])
        with self.assertRaises(ValueError):self.store.update_library([{'id':'a','tags':['标签'+str(i) for i in range(7)]}])
    def test_every_effective_tag_is_browsable(self):
        games=[{'id':str(i),'name':str(i),'tags':['Mystery','Puzzle','Dating Sim']} for i in range(3)]
        rows=sections(games);tiles=next(row for row in rows if row['id']=='tags')['items']
        self.assertEqual({item['name'] for item in tiles},{'悬疑','解谜','恋爱'})
        self.assertEqual({item['count'] for item in tiles},{3})
    def test_import_metadata_pipeline_has_source_dates_and_tags(self):
        install=Path(self.temp.name)/'game';install.mkdir()
        row=candidate('VN','local','vn',install)
        row.update(playnite=True,raw={'ReleaseDate':{'Year':2010,'Month':2,'Day':3},'ResolvedGenres':['Visual Novel'],'ResolvedTags':['Mystery']})
        self.assertEqual(import_rows(self.store,[row]),1)
        self.assertEqual(self.store.games[0]['release_date'],'2010-02-03');self.assertEqual(self.store.games[0]['tags'],['视觉小说','悬疑'])

if __name__=='__main__':unittest.main(verbosity=2)
