"""Pure search/tag/preset regressions and asynchronous favourite persistence."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from tag_catalog import ALIASES,normalize_tags,key,normalized
from library_search import search_keys
from graphics_enhancement import QUICK_PROFILES,normalize
from gamepad import Mapper,Pad

class ControllerModels(unittest.TestCase):
    def test_tag_cache_preserves_all_existing_aliases(self):
        for name,aliases in ALIASES.items():
            for alias in [name,*aliases]:self.assertEqual(key(alias),normalized(name))
        self.assertEqual(normalize_tags(['RPG','role-playing','unknown','puzzle',None],['角色扮演','解谜']),['角色扮演','解谜'])
        self.assertEqual(normalize_tags(['Galgame','rpg'],['视觉小说']),['视觉小说'])
    def test_search_name_aliases_and_initials(self):
        values=search_keys({'name':'沙耶之歌','aliases':['The Song of Saya'],'tags':[]})
        text=values
        for query in ('syzg','shayezhige','thesongofsaya'):self.assertIn(query,text)
    def test_view_is_distinct_from_menu(self):
        pad=Pad();mapper=Mapper();pad.buttons=0x20;self.assertEqual(mapper.read(pad,1),['search'])
        mapper.read(Pad(),1.2);pad.buttons=0x10;self.assertEqual(mapper.read(pad,1.4),['menu'])
        mapper.read(Pad(),1.6);pad.buttons=0x80;self.assertEqual(mapper.read(pad,1.8),['case']);self.assertEqual(mapper.read(pad,2.),[])
    def test_quick_presets_are_complete_and_disable_clears_enabled(self):
        for profile in QUICK_PROFILES:
            value=normalize(profile['values'])
            self.assertIn(value['preset'],('anime-fast','anime-quality','fsr','lanczos','nearest'))
            self.assertIn('window_scale',value)
        self.assertFalse(normalize(QUICK_PROFILES[-1]['values'])['enabled'])
    def test_favourites_coalesce_and_persist_without_global_busy(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
            store=Store(folder,'favourite-model');store.settings.update(watch=False,recommendations_enabled=False)
            store.games=[{'id':'a','name':'A','cover':'','favorite':False}]
            backend=Bridge(store)
            try:
                backend.toggleFavorite('a');backend.toggleFavorite('a');backend.toggleFavorite('a')
                self.assertFalse(backend.busy);self.assertTrue(backend.libraryGame('a')['favorite'])
                backend.favoriteTimer.stop();backend.flushFavorites();backend.pool.submit(lambda:None).result(timeout=5)
                self.assertTrue(store.games[0]['favorite']);self.assertTrue(backend.libraryGame('a')['favorite'])
            finally:backend.shutdownWatch();backend.pool.shutdown(wait=True);backend.graphics.pool.shutdown(wait=True)

if __name__=='__main__':
    from PySide6.QtWidgets import QApplication
    app=QApplication([]);unittest.main()
