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
    def graph(self,games,mode,order='release_asc'):
        result=self.engine.evaluate('atlas('+json.dumps(games)+','+json.dumps(mode)+','+json.dumps(order)+')')
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
    def test_cover_and_two_line_label_bounds_never_overlap(self):
        games=[{'id':str(i),'name':'很长的游戏名称 '+str(i),'category':['视觉小说','角色扮演','解谜休闲'][i%3]} for i in range(95)]
        graph=self.graph(games,'category');nodes=graph['nodes']
        self.assertEqual(len({g['color'] for g in graph['labels']}),3)
        for i,a in enumerate(nodes):
            for b in nodes[i+1:]:
                self.assertTrue(abs(a['x']-b['x'])>=(a['width']+b['width'])/2 or abs(a['y']-b['y'])>=(a['height']+b['height'])/2,(a,b))
        for a in nodes:
            group=next(g for g in graph['labels'] if g['name']==a['group'])
            self.assertGreaterEqual(a['y']-86,group['y']+54)
            self.assertLessEqual(a['y']+88,group['y']+group['height'])
    def test_series_order_and_unknown_dates_last(self):
        games=[{'id':'later','name':'A','series':'Series','release_date':'2020-01-01'},{'id':'early','name':'Z','series':'Series','release_date':'2010-01-01'},{'id':'unknown','name':'B','series':'Series'}]
        self.assertEqual([n['game']['id'] for n in self.graph(games,'series')['nodes']],['early','later','unknown'])
        self.assertEqual([n['game']['id'] for n in self.graph(games,'series','release_desc')['nodes']],['later','early','unknown'])
        year=self.graph(games,'year');self.assertEqual([g['name'] for g in year['labels']],['2010年','2020年','日期未知'])
    def test_constellations_have_stable_varied_silhouettes(self):
        games=[{'id':str(i),'name':str(i),'series':['Orion','Lyra','Swan'][i//7]} for i in range(21)]
        graph=self.graph(games,'series');self.assertEqual(graph,self.graph(games,'series'))
        shapes=[]
        for group in graph['labels']:
            nodes=[n for n in graph['nodes'] if n['group']==group['name']]
            shapes.append([(round(n['x']-group['x']),round(n['y']-group['y'])) for n in nodes])
            self.assertGreater(len({round(n['y']) for n in nodes}),4)
        self.assertEqual(len({str(shape) for shape in shapes}),3)
if __name__=='__main__':unittest.main()
