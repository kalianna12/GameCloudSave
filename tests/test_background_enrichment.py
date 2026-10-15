"""Banner preview/apply is local, bounded, opt-in and never overwrites art."""
from pathlib import Path
from unittest.mock import patch
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from library_enrichment import preview,apply
from library_artwork import prepare
from PySide6.QtGui import QImage,QColor
class BackgroundEnrichment(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'backgrounds')
        self.store.games=[{'id':'a','name':'A','cover':'','tags':[]}];write_json(self.store.root/'library.json',self.store.games)
        self.banner=self.store.root/'landscape.png';image=QImage(1920,1080,QImage.Format_RGB32);image.fill(QColor('#45796b'));image.save(str(self.banner))
        self.options={'dates':False,'tags':False,'covers':False,'backgrounds':True,'use_ai':False}
    def tearDown(self):self.temp.cleanup()
    def test_banner_preview_and_apply_preserve_library_until_selected(self):
        disk=(self.store.root/'library.json').read_bytes()
        with patch('library_metadata.lookup',return_value={'background_url':str(self.banner),'background_source':'Steam'}):result=preview(self.store,options=self.options)
        row=result['rows'][0];self.assertIn('background',row['fields']);self.assertEqual((self.store.root/'library.json').read_bytes(),disk)
        image=QImage(row['fields']['background']);self.assertEqual((image.width(),image.height()),(1280,720))
        apply(self.store,result['rows'],['a']);self.assertTrue(Path(self.store.games[0]['background']).is_file())
        self.assertEqual(self.store.games[0]['background_source'],'Steam')
    def test_existing_or_newly_selected_art_is_not_replaced(self):
        with patch('library_metadata.lookup',return_value={'background_url':str(self.banner)}):result=preview(self.store,options=self.options)
        self.store.games[0]['background']=str(self.banner);apply(self.store,result['rows'],['a'])
        self.assertEqual(self.store.games[0]['background'],str(self.banner))
        with patch('library_metadata.lookup') as fetch:result=preview(self.store,options=self.options)
        self.assertFalse(fetch.called);self.assertEqual(result['rows'][0]['fields'],{})
    def test_portrait_cannot_be_silently_used_as_banner(self):
        portrait=self.store.root/'portrait.png';image=QImage(600,900,QImage.Format_RGB32);image.fill(QColor('red'));image.save(str(portrait))
        with self.assertRaises(ValueError):prepare(self.store,str(portrait))
        self.assertFalse(list((self.store.root/'backgrounds').glob('*.part')))
    def test_unsupported_host_is_rejected_before_download(self):
        with patch('library_artwork.urlopen') as network:
            with self.assertRaises(ValueError):prepare(self.store,'https://untrusted.example/image.jpg')
        self.assertFalse(network.called)
if __name__=='__main__':unittest.main()
