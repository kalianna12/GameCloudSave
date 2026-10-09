from pathlib import Path
import sys,json,tempfile,unittest,io,base64
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
from services import Store,ROOT
from library_sources import candidate,annotate_duplicates,import_rows
from cover_sources import search,download,PROVIDERS
from install_core import install,uninstall,running

class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name);self.store=Store(self.root/'data','test')
    def tearDown(self):
        import gc;gc.collect();self.temp.cleanup()
    def test_playnite_reference_blocks_not_yet_imported_game(self):
        folder=self.root/'Game';folder.mkdir()
        row=candidate('Celeste','steam','504230',folder)
        reference={'id':'playnite-id','name':'Celeste','platform':'steam','external_id':'504230','playnite':True,'install_dir':'other'}
        result=annotate_duplicates(self.store,[row],[reference])[0]
        self.assertEqual(result['duplicate_id'],'playnite-id')
        self.assertIn('Playnite',result['duplicate_reason'])
    def test_alternative_launcher_remains_selectable_and_same_batch_copies_skipped(self):
        folder=self.root/'Game';folder.mkdir()
        rows=[candidate('Game','local','game',folder,folder/'Game.exe'),candidate('Game','local','game',folder,folder/'Start.bat')]
        rows[0]['id']='first';rows[1]['id']='second'
        annotated=annotate_duplicates(self.store,rows)
        self.assertTrue(annotated[1]['alternative_launcher']);self.assertNotIn('duplicate_id',annotated[1])
        copy=self.root/'copy';copy.mkdir();third=candidate('Game','local','game',copy)
        self.assertEqual(import_rows(self.store,[rows[0],third],skip_duplicates=True),1)
    def test_ai_hint_requires_review_and_does_not_invent_directory(self):
        folder=self.root/'Game';folder.mkdir()
        row=candidate('Unknown','local','unknown',folder);row['ai_duplicate_hint']='Known game'
        value=annotate_duplicates(self.store,[row])[0]
        self.assertEqual(value['possible_duplicate'],'Known game');self.assertNotIn('duplicate_id',value)
    def test_sequel_not_fuzzy_merged(self):
        self.store.games=[{'id':'one','name':'Monument Valley 2'}]
        row=candidate('Monument Valley 3','local','three',self.root)
        self.assertNotIn('duplicate_id',annotate_duplicates(self.store,[row])[0])
        self.assertNotIn('possible_duplicate',annotate_duplicates(self.store,[row])[0])
    def test_steam_search_keeps_frostpunk_and_igdb_is_removed(self):
        payload={'items':[{'name':'Frostpunk','logo':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/323190/capsule.jpg'},{'name':'Frostpunk Soundtrack','logo':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/123/capsule.jpg'}]}
        with patch('cover_sources.fetch_json',return_value=payload):
            rows=search(self.store,'Frostpunk');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['score'],1)
        self.assertNotIn('igdb',[provider['id'] for provider in PROVIDERS])
    def test_download_releases_reader_before_atomic_replace(self):
        from PySide6.QtGui import QImage
        fixture=self.root/'fixture.png';QImage(10,15,QImage.Format_RGB32).save(str(fixture))
        class Response(io.BytesIO):
            def geturl(self):return 'https://shared.fastly.steamstatic.com/cover.png'
        row={'id':'steam:1','image':'https://shared.fastly.steamstatic.com/cover.png','fallback':''}
        with patch('cover_sources.urlopen',return_value=Response(fixture.read_bytes())):file=download(self.store,row)
        self.assertTrue(Path(file).is_file())
    def test_install_uninstall_shortcuts_preserve_untracked_data(self):
        import zipfile
        payload=self.root/'payload.zip'
        with zipfile.ZipFile(payload,'w') as zipped:zipped.writestr('GameCloudSave-V2.1.exe',b'fixture');zipped.writestr('Uninstall.exe',b'fixture');zipped.writestr('_internal/library.txt','fixture')
        target=self.root/'installed';desktop=self.root/'desktop';menu=self.root/'menu'
        install(payload,target,desktop,menu,registry=False)
        self.assertTrue((desktop/'GameCloudSave.lnk').is_file())
        (target/'user-note.txt').write_text('keep')
        uninstall(target)
        self.assertFalse((desktop/'GameCloudSave.lnk').exists());self.assertFalse((menu/'GameCloudSave.lnk').exists())
        self.assertEqual((target/'user-note.txt').read_text(),'keep')
    def test_installer_rejects_unrelated_and_traversal(self):
        import zipfile
        target=self.root/'unrelated';target.mkdir();(target/'note.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError,'其他文件'):install(self.root/'none.zip',target,registry=False)
        payload=self.root/'bad.zip'
        with zipfile.ZipFile(payload,'w') as zipped:zipped.writestr('../escape','bad')
        with self.assertRaises(ValueError):install(payload,self.root/'new',registry=False)
        self.assertFalse((self.root/'escape').exists())
    def test_uninstaller_bootloader_parent_does_not_block_cleanup(self):
        from types import SimpleNamespace
        own=self.root/'Uninstall.exe'
        parent=SimpleNamespace(info={'exe':str(own),'pid':999})
        game=SimpleNamespace(info={'exe':str(self.root/'GameCloudSave.exe'),'pid':1000})
        with patch('install_core.sys.frozen',True,create=True),patch('install_core.sys.executable',str(own)),patch('psutil.Process',return_value=SimpleNamespace(parents=lambda:[SimpleNamespace(pid=999)])):
            with patch('psutil.process_iter',return_value=[parent]):self.assertFalse(running(self.root))
            with patch('psutil.process_iter',return_value=[parent,game]):self.assertTrue(running(self.root))
if __name__=='__main__':unittest.main(verbosity=2)
