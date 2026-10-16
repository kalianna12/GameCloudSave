from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from enrichment_manual import values,candidate
from library_enrichment import apply
from PySide6.QtGui import QImage,QColor

class Manual(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'manual')
        self.store.games=[{'id':'g','name':'Edited name','cover':'','tags':[],'category':'其他'}]
        write_json(self.store.root/'library.json',self.store.games);self.before=(self.store.root/'library.json').read_bytes()
        self.art=self.store.root/'chosen.png';image=QImage(300,450,QImage.Format_RGB32);image.fill(QColor('blue'));image.save(str(self.art))
    def tearDown(self):self.temp.cleanup()
    def test_manual_fields_and_local_art_stage_then_apply(self):
        row=values(self.store,'g',{'release_date':'2001-02-03','tags':['解谜'],'series':'Series','cover':str(self.art)})
        self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
        self.assertTrue(Path(row['fields']['cover']).is_relative_to(self.store.root/'covers'))
        apply(self.store,[row],['g']);self.assertEqual(self.store.games[0]['release_date'],'2001-02-03')
        self.assertTrue(self.store.games[0]['release_date_manual']);self.assertTrue(self.store.games[0]['tags_manual'])
    def test_candidate_is_explicit_choice_and_preserves_other_proposals(self):
        previous=values(self.store,'g',{'series':'Manual series'})
        row=candidate(self.store,'g',{'id':'vndb:v1','provider':'vndb','name':'Original title','released':'1999-01-02','page':'https://vndb.org/v1'},previous)
        self.assertEqual(row['fields']['release_date'],'1999-01-02');self.assertEqual(row['fields']['series'],'Manual series')
        self.assertEqual(row['matched_name'],'Original title');self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
    def test_existing_and_newly_set_data_always_win(self):
        self.store.games[0].update(release_date='1980-01-01',cover=str(self.art),tags=['解谜'])
        row=values(self.store,'g',{'release_date':'2000-01-01','cover':str(self.art),'tags':['射击']})
        self.assertEqual(row['fields'],{})
        self.store.games[0].pop('release_date');row=values(self.store,'g',{'release_date':'2000-01-01'})
        self.store.games[0]['release_date']='1980-01-01';apply(self.store,[row],['g'])
        self.assertEqual(self.store.games[0]['release_date'],'1980-01-01')
    def test_explicit_steam_choice_uses_database_tags_and_date(self):
        with patch('enrichment_manual.cached_lookup',return_value={'release_date':'2020-01-02','release_date_source':'Steam','tags':['角色扮演'],'tags_source':'Steam'}):
            row=candidate(self.store,'g',{'id':'steam:123','appid':'123','provider':'steam','name':'Original title'})
        self.assertEqual(row['fields']['category'],'角色扮演');self.assertEqual(row['metadata_steam_appid'],'123')
        self.assertEqual(row['sources']['release_date'],'Steam');self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
    def test_invalid_values_cannot_enter_preview(self):
        with self.assertRaises(ValueError):values(self.store,'g',{'release_date':'2000-02-31'})
        with self.assertRaises(ValueError):values(self.store,'gone',{'release_date':'2000-01-01'})
        self.assertEqual(values(self.store,'g',{'exe':'malicious','category':'made up'})['fields'],{})
        self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
if __name__=='__main__':unittest.main()
