"""Read-only local/plugin media discovery with malformed-cache fallbacks."""
from pathlib import Path
import json,sys,tempfile,unittest,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from playnite_media import discover,PLUGIN
from services import Store,ROOT

class MediaDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
        self.ident=str(uuid.uuid4());self.cache=self.root/'ExtensionsData'/PLUGIN;self.cache.mkdir(parents=True)
        self.settings={'library':str(self.root/'library')};self.game={'id':self.ident,'steam_appid':'123'}
    def tearDown(self):self.temp.cleanup()
    def cache_data(self,data):
        path=self.cache/(self.ident+'_SteamAppDetails.json');path.write_text(json.dumps({'123':{'success':True,'data':data}}),encoding='utf-8');return path
    def test_hls_from_existing_cache_and_no_cache_writes(self):
        path=self.cache_data({'background_raw':'https://cdn.example/bg.jpg','movies':[{'highlight':True,'hls_h264':'https://cdn.example/video.m3u8'}]})
        before=path.read_bytes();result=discover(self.settings,[self.game])[self.ident]
        self.assertEqual(result['videoUrl'],'https://cdn.example/video.m3u8');self.assertTrue(result['videoRemote']);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(discover(self.settings,[{'id':'imported','metadata_steam_appid':'123'}])['imported']['videoUrl'],result['videoUrl'])
    def test_local_video_and_background_preferred(self):
        self.cache_data({'background':'https://cdn.example/bg.jpg','movies':[{'mp4':{'480':'https://cdn.example/trailer.mp4'}}]})
        local=self.root/'ExtraMetadata/games'/self.ident;local.mkdir(parents=True);(local/'VideoTrailer.mp4').write_bytes(b'fixture')
        background=self.root/'local.jpg';background.write_bytes(b'fixture')
        result=discover(self.settings,[{**self.game,'background':str(background)}])[self.ident]
        self.assertTrue(result['videoUrl'].startswith('file:'));self.assertFalse(result['videoRemote']);self.assertTrue(result['backgroundUrl'].startswith('file:'))
        (local/'VideoTrailer.mp4').unlink();(local/'VideoMicrotrailer.mp4').write_bytes(b'micro')
        self.assertIn('VideoMicrotrailer',discover(self.settings,[self.game])[self.ident]['videoUrl'])
    def test_invalid_cache_and_schemes_do_not_break_other_entries(self):
        path=self.cache_data({'movies':None,'background':'https://[invalid'})
        self.assertEqual(discover(self.settings,[self.game]),{})
        for value in [{'movies':[{'mp4':{'480':'file:///not-a-video'}}]}, {'movies':[None,{'hls_h264':'https://user:secret@example.com/video'}]}, {'movies':99}]:
            self.cache_data(value);self.assertEqual(discover(self.settings,[self.game]),{})
        path.write_text('{broken',encoding='utf-8');self.assertEqual(discover(self.settings,[self.game]),{})
    def test_playnite_relative_background_is_contained(self):
        files=self.root/'library/files';files.mkdir(parents=True);(files/'background.jpg').write_bytes(b'fixture')
        game={**self.game,'playnite_background':'background.jpg'}
        self.assertTrue(discover(self.settings,[game])[self.ident]['backgroundUrl'].startswith('file:'))
        (self.root/'secret.jpg').write_bytes(b'fixture')
        self.assertEqual(discover(self.settings,[{**self.game,'playnite_background':'../../secret.jpg'}]),{})
        self.assertEqual(discover(self.settings,[{**self.game,'playnite_background':'https://cdn.example/banner.jpg'}])[self.ident]['backgroundUrl'],'https://cdn.example/banner.jpg')
    def test_classic_default_and_validated_local_preferences(self):
        store=Store(self.root/'source-data','media-test');self.assertEqual(store.settings['library_design'],'classic')
        for design in ('classic','shelf','cinema','atlas'):store.save_settings({'library_design':design})
        for invalid in [{'library_design':'gallery'},{'experience_group':'anything'},{'shelf_arrangement':'other'}]:
            with self.assertRaises(ValueError):store.save_settings(invalid)

if __name__=='__main__':unittest.main()
