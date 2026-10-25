from pathlib import Path
import html,json,sys,tempfile,threading,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from image_search import parse,search
from artwork_search import web_rows
from services import Store

class Images(unittest.TestCase):
    def test_google_original_dimensions_and_thumbnail(self):
        page='["https://encrypted-tbn0.gstatic.com/images?q=tbn:x",320,220],["https://images.example/cover.jpg?a=1\\u0026b=2",1600,1100]'
        row=parse(page,'https://google.com/search')[0]
        self.assertEqual((row['width'],row['height']),(1100,1600))
        self.assertIn('&b=2',row['image']);self.assertIn('gstatic',row['thumbnail'])
        self.assertEqual(len(web_rows([row],'google','cover')),1)
    def test_bing_metadata_and_google_links(self):
        data={'murl':'https://images.example/landscape.jpg','turl':'https://images.example/thumb.jpg','purl':'https://example.org/game','t':'Game','w':1920,'h':1080}
        page='<a class="iusc" m="'+html.escape(json.dumps(data))+'"></a>'
        row=parse(page,'https://bing.com')[0]
        self.assertEqual(row['image'],data['murl']);self.assertEqual(row['page'],data['purl'])
        page='<a href="/imgres?imgurl=https%3A%2F%2Fexample.org%2Fc.jpg&amp;w=400&amp;h=600"><img src="https://example.org/t.jpg"></a>'
        self.assertEqual(parse(page,'https://google.com')[0]['image'],'https://example.org/c.jpg')
    def test_all_scraped_sources_use_same_pipeline(self):
        page=''.join(f'<img width="400" height="600" src="https://images.example/{i}.jpg" alt="Fixture">' for i in range(6))
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp,'isolated')
            for source in ('google','bing','ign','steamgriddb','gog','epic'):
                with patch('image_search.fetch',return_value=page),patch('image_search.rendered') as rendered:
                    rows=search(store,'Fixture',source,'cover')
                self.assertEqual(len(rows),6);self.assertEqual(rows[0]['provider'],source);rendered.assert_not_called()
    def test_restricted_source_and_cancellation_remain_in_page(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp,'isolated');cancel=threading.Event();cancel.set()
            with patch('image_search.fetch',return_value=''),patch('image_search.rendered') as rendered:
                self.assertEqual(search(store,'Fixture','google','cover',cancel),[]);rendered.assert_not_called()
            with patch('image_search.fetch',return_value=''),patch('image_search.rendered',return_value=''):
                with self.assertRaises(ValueError):search(store,'Fixture','bing','cover')
            with patch('image_search.fetch',side_effect=ValueError('restricted')),patch('image_search.rendered',return_value='<img src="https://images.example/a.jpg" width="400" height="600">'):
                self.assertEqual(len(search(store,'Fixture','epic','cover')),1)
    def test_malformed_images_do_not_drop_other_results(self):
        page='<img src="http://[broken"><img src="https://images.example/a.jpg" width="400" height="600"><img src="file:///private"><img src="https://images.example/logo.png">'
        self.assertEqual(len(parse(page,'https://example.org')),1)

if __name__=='__main__':unittest.main()
