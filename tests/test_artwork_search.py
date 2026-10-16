"""Search pairing, bounded page captures and explicit artwork preview/apply."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from artwork_search import search,web_rows,stage,set_background
from enrichment_manual import values
from PySide6.QtGui import QImage,QColor

class Artwork(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'artwork')
        self.store.games=[{'id':'g','name':'Edited title','cover':'','tags':[],'category':'其他'}]
        write_json(self.store.root/'library.json',self.store.games);self.before=(self.store.root/'library.json').read_bytes()
        self.landscape=self.store.root/'landscape.png';self.portrait=self.store.root/'portrait.png'
        for file,size in [(self.landscape,(960,540)),(self.portrait,(360,540))]:
            image=QImage(*size,QImage.Format_RGB32);image.fill(QColor('blue'));image.save(str(file))
    def tearDown(self):self.temp.cleanup()
    def test_catalog_pairs_banner_with_each_result_and_distinguishes_failure(self):
        rows=[{'id':str(i),'appid':str(i),'provider':'steam','name':str(i)} for i in range(3)]
        def lookup(store,game):
            if game['steam_appid']=='2':raise ValueError('unavailable')
            return {'release_date':'2020-01-01','background_url':'https://shared.fastly.steamstatic.com/banner.jpg' if game['steam_appid']=='0' else ''}
        with patch('cover_sources.search',return_value=rows),patch('library_enrichment.cached_lookup',side_effect=lookup):
            result=search(self.store,'Title','steam','background')
        self.assertEqual([r['background_state'] for r in result],['available','none','unknown'])
        self.assertEqual(result[0]['metadata_fields']['release_date'],'2020-01-01')
        self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
    def test_page_capture_deduplicates_filters_and_bounds_untrusted_fields(self):
        rows=[{'image':'https://images.example/cover.png','width':360,'height':540,'name':'x'*400,'page':'javascript:alert(1)'},
              {'image':'https://images.example/cover.png'},{'image':'https://images.example/banner.png','width':1280,'height':720},
              {'image':'http://[broken'},{'image':'file:///secret'},{'image':'https://user:password@images.example/private'},None]
        covers=web_rows(rows,'google','cover');banners=web_rows(rows,'google','background')
        self.assertEqual(len(covers),1);self.assertEqual(len(banners),1)
        self.assertEqual(covers[0]['name'],'x'*200);self.assertEqual(covers[0]['page'],'')
        self.assertEqual(banners[0]['background_state'],'available')
        self.assertEqual(web_rows(rows,'google','cover')[0]['id'],covers[0]['id'])
        self.assertEqual(len(web_rows([{'image':f'https://images.example/{i}'} for i in range(1000)],'bing','cover')),48)
    def test_selected_artwork_merges_preview_without_persisting_or_overwriting(self):
        previous=values(self.store,'g',{'series':'My series'})
        cover={'id':'web:cover','name':'Chosen','image':'https://images.example/c.jpg','provider':'google','user_authorized':True}
        with patch('cover_sources.download',return_value=str(self.portrait)):
            row=stage(self.store,'g',cover,'cover',previous)
        row=stage(self.store,'g',{'background_url':str(self.landscape),'provider':'manual'},'background',row)
        self.assertEqual(set(row['fields']),{'series','cover','background'})
        self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
        self.store.games[0]['cover']=str(self.portrait)
        with self.assertRaises(ValueError):stage(self.store,'g',cover,'cover',row)
    def test_metadata_selection_does_not_download_or_change_selected_images(self):
        previous=values(self.store,'g',{'cover':str(self.portrait)})
        record={'id':'steam:1','appid':'1','name':'Correct title','provider':'steam','image':'https://images.example/c.jpg',
                'metadata_fields':{'release_date':'2001-01-01','tags':['解谜'],'background_url':str(self.landscape)}}
        with patch('cover_sources.download') as download,patch('library_artwork.prepare') as prepare:
            row=stage(self.store,'g',record,'metadata',previous)
        download.assert_not_called();prepare.assert_not_called()
        self.assertEqual(row['fields']['cover'],previous['fields']['cover']);self.assertNotIn('background',row['fields'])
        self.assertEqual(row['fields']['release_date'],'2001-01-01')
    def test_settings_background_replacement_validates_before_persisting(self):
        with self.assertRaises(ValueError):set_background(self.store,'g',str(self.portrait))
        self.assertEqual((self.store.root/'library.json').read_bytes(),self.before)
        result=set_background(self.store,'g',str(self.landscape),'local')
        self.assertEqual(result['kind'],'background');self.assertTrue(Path(self.store.games[0]['background']).is_file())
        before=(self.store.root/'library.json').read_bytes()
        with self.assertRaises(ValueError):set_background(self.store,'deleted',str(self.landscape))
        self.assertEqual((self.store.root/'library.json').read_bytes(),before)

if __name__=='__main__':unittest.main()
