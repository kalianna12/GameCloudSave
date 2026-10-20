from pathlib import Path
import sys,io,json,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from tag_catalog import vocabulary,normalize_tags,classified,ALIASES,effective_tags
from library_organizer import suggestions
from gamepad import Mapper,Pad

class Taxonomy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'taxonomy')
        self.store.games=[{'id':'old','name':'Existing','category':'视觉小说','tags':['恋爱','剧情','多人合作'],'series':'keep'}, {'id':'new','name':'New game','cover':'','tags':[]}]
        self.store.save_settings({'ai_key':'fixture'})
    def tearDown(self):self.temp.cleanup()
    def answer(self,items):return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':items})}}]}).encode())
    def test_vocabulary_is_fixed_and_normalizes_synonyms(self):
        terms=vocabulary(self.store.games)
        self.assertEqual(terms,list(ALIASES))
        self.assertEqual(normalize_tags(['romance','故事丰富','coop','多人合作','编造标签'],terms),['恋爱','剧情','合作'])
        self.assertEqual(vocabulary(list(reversed(self.store.games))),terms)
    def test_default_sends_only_unclassified_and_caches_the_same_vocabulary(self):
        item={'id':'new','category':'视觉小说','tags':['romance','story-rich','co-op'],'series':''}
        with patch('library_organizer.urlopen',return_value=self.answer([item])) as request:
            rows=suggestions(self.store,True)
            body=json.loads(request.call_args.args[0].data);sent=json.loads(body['messages'][1]['content'])
            self.assertEqual([game['id'] for game in sent],['new']);self.assertEqual(body['temperature'],0)
            self.assertIn('合作',body['messages'][0]['content'])
        old=next(row for row in rows if row['id']=='old');self.assertEqual(old['category'],'视觉小说');self.assertEqual(old['series'],'keep')
        new=next(row for row in rows if row['id']=='new');self.assertEqual(new['tags'],['恋爱','剧情','合作'])
        with patch('library_organizer.urlopen',side_effect=AssertionError('Cache must be reused')):self.assertEqual(suggestions(self.store,True),rows)
        self.assertNotIn('category',self.store.games[1])
    def test_no_model_request_when_every_game_is_classified(self):
        self.store.games=self.store.games[:1]
        original=json.dumps(self.store.games)
        with patch('library_organizer.urlopen',side_effect=AssertionError('Protected game must be skipped')):self.assertEqual(suggestions(self.store,True)[0]['tags'],effective_tags(self.store.games[0]))
        self.assertEqual(json.dumps(self.store.games),original)
    def test_protected_batch_rejected_before_any_modification(self):
        updates=[{'id':'new','category':'角色扮演','tags':['魂类']},{'id':'old','category':'射击竞技','tags':['射击']}]
        original=json.dumps(self.store.games)
        with self.assertRaises(ValueError):self.store.apply_classification(updates)
        self.assertEqual(json.dumps(self.store.games),original)
        self.store.apply_classification(updates,True);self.assertTrue(classified(self.store.games[1]))
    def test_gamepad_deadzone_debounce_and_repeat(self):
        mapper=Mapper();pad=Pad()
        self.assertEqual(mapper.read(pad,0),[])
        pad.lx=7000;self.assertEqual(mapper.read(pad,.01),[])
        pad.lx=16000;self.assertEqual(mapper.read(pad,.02),['right'])
        self.assertEqual(mapper.read(pad,.1),[]);self.assertEqual(mapper.read(pad,.38),['right'])
        pad.lx=0;pad.buttons=0x1000;self.assertEqual(mapper.read(pad,.5),['activate']);self.assertEqual(mapper.read(pad,.6),[])
        pad.buttons=0x2000;self.assertEqual(mapper.read(pad,.7),['back'])
if __name__=='__main__':unittest.main(verbosity=2)
