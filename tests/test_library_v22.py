"""Library edits, data-only themes and catalog contracts without personal data."""
from pathlib import Path
import sys,tempfile,unittest,json,io
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from themes import PALETTES,validate,resolve
from library_organizer import suggestions
from cover_sources import search,PROVIDERS

class LibraryFeatures(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'library')
        self.store.games=[{'id':'a','name':'9-nine-春色春恋春熙风'},{'id':'b','name':'9-nine-雪色雪花雪之痕'},{'id':'c','name':'Celeste'}]
    def tearDown(self):self.temp.cleanup()
    def test_categories_series_favorites_recent_persist_and_rename(self):
        self.store.update_library([{'id':'a','groups':['视觉小说'],'series':'9-nine','favorite':True}])
        self.store.mark_played('a');self.store.edit_group('视觉小说','Galgame')
        reload=Store(self.temp.name,'library')
        self.assertEqual(reload.groups,['Galgame']);self.assertEqual(reload.games[0]['groups'],['Galgame'])
        self.assertTrue(reload.games[0]['favorite']);self.assertIn('+00:00',reload.games[0]['last_played'])
        self.store.edit_group('Galgame','');self.assertEqual(len(self.store.games),3);self.assertEqual(self.store.games[0]['groups'],[])
    def test_invalid_batch_is_atomic(self):
        with self.assertRaises(ValueError):self.store.update_library([{'id':'a','favorite':True},{'id':'bad','groups':['x']}])
        self.assertNotIn('favorite',self.store.games[0])
        self.assertFalse((self.store.root/'library.json').exists())
    def test_rule_suggestions_leave_library_unchanged(self):
        before=json.dumps(self.store.games);rows=suggestions(self.store)
        self.assertEqual([row['series'] for row in rows],['9-nine','9-nine',''])
        self.assertEqual(before,json.dumps(self.store.games))
    def test_ai_groups_validate_ids_and_preview_only(self):
        self.store.save_settings({'ai_key':'dummy'})
        result={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':[{'id':game['id'],'category':'视觉小说','tags':[],'series':'9-nine' if game['id'] in ('a','b') else ''} for game in self.store.games]})}}]}
        with patch('library_organizer.urlopen',side_effect=lambda *args,**kwargs:io.BytesIO(json.dumps(result).encode())):
            rows=suggestions(self.store,True);self.assertEqual(rows[0]['groups'],['视觉小说']);self.assertNotIn('groups',self.store.games[0])
        result['choices'][0]['message']['content']=json.dumps({'items':[{'id':'unknown','groups':[]}]})
        self.store.settings['ai_model']='uncached-fixture'
        with patch('library_organizer.urlopen',side_effect=lambda *args,**kwargs:io.BytesIO(json.dumps(result).encode())):
            with self.assertRaises(ValueError):suggestions(self.store,True)
    def test_builtin_and_custom_themes_reject_code_and_low_contrast(self):
        for name,palette in PALETTES.items():
            self.assertEqual(resolve({'theme':name})['background'],palette['background'])
            validate({'schemaVersion':1,'name':palette['name'],'dark':palette['dark'],'colors':palette})
        data={'schemaVersion':1,'name':'Custom','colors':{'background':'#101a22','text':'#f4f7ff','accent':'#72b7ec'},'qml':'unsafe code'}
        self.assertNotIn('qml',validate(data))
        with self.assertRaises(ValueError):validate({'schemaVersion':1,'colors':{'text':'#181a1c'}})
        with self.assertRaises(ValueError):validate({'schemaVersion':2})
        self.assertEqual(resolve({'theme':'light','animations':False})['motion'],False)
    def test_vndb_contract_and_custom_endpoint_cache_isolation(self):
        with patch('cover_sources.fetch_json',return_value={'results':[{'id':'v11','title':'Fate/stay night','image':{'url':'https://s.vndb.org/cv/11.jpg','thumbnail':'https://t.vndb.org/cv/11.jpg'}}]}):
            rows=search(self.store,'Fate/stay night','vndb');self.assertEqual(rows[0]['id'],'vndb:v11');self.assertEqual(rows[0]['score'],1)
        self.store.settings['custom_cover_url']='https://one.example/?q={query}'
        with patch('cover_sources.fetch_json',return_value={'items':[{'id':1,'name':'Celeste','image':'https://one.example/cover.jpg'}]}) as fetch:
            self.assertEqual(search(self.store,'Celeste','custom')[0]['image'],'https://one.example/cover.jpg');self.assertEqual(fetch.call_count,1)
        self.store.settings['custom_cover_url']='https://two.example/?q={query}'
        with patch('cover_sources.fetch_json',return_value={'items':[{'id':2,'name':'Celeste','image':'https://two.example/cover.jpg'}]}) as fetch:
            self.assertEqual(search(self.store,'Celeste','custom')[0]['id'],'custom:2');self.assertEqual(fetch.call_count,1)
        self.assertTrue(all('{query}' in row['url'] for row in PROVIDERS if row['kind']=='browser'))
if __name__=='__main__':unittest.main(verbosity=2)
