"""Metadata relations are exact, deduplicated, and linear in group membership."""
from pathlib import Path
import json,sys,time,unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
app=QCoreApplication([])
ROOT=Path(__file__).resolve().parents[1]
class Relations(unittest.TestCase):
    def setUp(self):
        self.engine=QJSEngine();result=self.engine.evaluate((ROOT/'ui/ExperienceData.js').read_text(encoding='utf-8').replace('.pragma library',''))
        self.assertFalse(result.isError())
    def graph(self,games,mode):
        result=self.engine.evaluate('atlas('+json.dumps(games)+','+json.dumps(mode)+')')
        self.assertFalse(result.isError(),result.toString());return result.toVariant()
    def test_multiple_tags_never_duplicate_nodes_or_invent_relations(self):
        games=[{'id':'a','tags':['悬疑','解谜']},{'id':'b','tags':['悬疑']},{'id':'c','tags':['解谜']},{'id':'d','tags':[]}]
        graph=self.graph(games,'tags');self.assertEqual(len(graph['nodes']),4);self.assertEqual(len(graph['edges']),2)
        for edge in graph['edges']:
            self.assertIn(edge['label'],edge['a']['game']['tags']);self.assertIn(edge['label'],edge['b']['game']['tags'])
        self.assertEqual(self.graph(games,'series')['edges'],[]);self.assertEqual(self.graph(games,'all')['edges'],[])
    def test_group_names_and_ids_cannot_collide_with_object_prototype(self):
        games=[{'id':'__proto__','category':'__proto__'},{'id':'constructor','category':'constructor'},{'id':'a','category':'__proto__'}]
        graph=self.graph(games,'category');self.assertEqual(len(graph['nodes']),3);self.assertEqual(len(graph['edges']),1)
    def test_large_library_has_bounded_edges(self):
        games=[{'id':str(i),'category':'RPG','tags':['A','B','C','D']} for i in range(2000)]
        started=time.perf_counter();graph=self.graph(games,'tags');elapsed=time.perf_counter()-started
        self.assertEqual(len(graph['nodes']),2000);self.assertEqual(len(graph['edges']),4*1999)
        self.assertLess(elapsed,4)
        print(f'2000 games / 4 tags: {len(graph["edges"])} edges in {elapsed:.3f}s')
if __name__=='__main__':unittest.main()
