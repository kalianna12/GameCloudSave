"""SSE correlation, empty RUNE containers, stats safety, sources and chart math."""
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import json,struct,sys,tempfile,unittest,zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from achievement_files import parse_state,discover,canonical_states
from achievement_statistics import statistics,game_snapshot
from achievement_web import community_schema,completionist_schema
from achievements import Repository


class Extended(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_user_stats_are_not_achievements_and_empty_rune_is_valid(self):
        stats=self.root/'stats.ini';stats.write_text('[UserStats]\n69f02429fca38baa=1\ncoins=0\ncount=26',encoding='utf-8')
        achievement=self.root/'achievements.ini';achievement.write_text('[SteamAchievements]\nCount=0',encoding='utf-8')
        self.assertEqual(parse_state(stats),{});self.assertEqual(parse_state(achievement),{})
        with patch('achievement_steam.steam_roots',return_value=[]):found=discover({},dict(install_dir=str(self.root)),'')
        self.assertEqual(found['sources'],[str(achievement)]);self.assertTrue(found['rejected'])
        repository=Repository(self.root/'profile');config=repository.config('one');config.update(source=str(stats),schema=[dict(id='coins',name='Coins')])
        with patch('achievement_steam.steam_roots',return_value=[]):repository.setup(dict(id='one'),dict(install_dir=str(self.root)))
        self.assertEqual(config['source'],str(achievement));self.assertEqual(repository.summary('one')['unlocked'],0)
    def test_sse_maps_only_unique_schema_crc(self):
        def entry(name,value):return struct.pack('<IIIIii',zlib.crc32(name.encode()),0,1700000000,0,0,value)
        source=self.root/'stats.bin';source.write_bytes(struct.pack('<I',3)+entry('FIRST',1)+entry('COINS',1)+entry('LAST',5))
        rows=parse_state(source);self.assertEqual(len(rows),2)
        mapped=canonical_states(rows,[dict(id='FIRST')]);self.assertEqual(set(mapped),{'FIRST'});self.assertTrue(mapped['FIRST']['unlocked'])
        self.assertFalse(canonical_states(rows,[]))
        source.write_bytes(source.read_bytes()[:-1])
        with self.assertRaises(ValueError):parse_state(source)
        source.write_bytes(struct.pack('<I',0))
        with patch('achievement_steam.steam_roots',return_value=[]):found=discover({},dict(install_dir=str(self.root)),'')
        self.assertEqual(found['sources'],[str(source)])
    def test_deep_engine_schema(self):
        path=self.root/'Engine/Binaries/ThirdParty/Steamworks/Steamv157/Win64/steam_settings/achievements.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps([dict(name='FIRST',displayName='First')]),encoding='utf-8')
        with patch('achievement_steam.steam_roots',return_value=[]):found=discover({},dict(install_dir=str(self.root)),'')
        self.assertEqual(len(found['schemas']),1);self.assertFalse(found['sources'])
    def test_community_ssr_exact_ids(self):
        payload=dict(queries=[dict(queryKey=['achievements',42,'schema'],state=dict(data=dict(groups=[dict(achievements=[dict(api_name='API_FIRST',name='First',description='Begin',icon_achieved='https://shared.fastly.steamstatic.com/apps/icon.jpg')])])))] )
        text='<script id="valve-ssr-data" type="application/json">'+json.dumps(dict(loaderData=json.dumps(payload)))+'</script>'
        with patch('achievement_web.fetch_page',return_value=text):
            row=community_schema('42')[0];self.assertEqual(row['id'],'API_FIRST');self.assertEqual(row['name'],'First');self.assertTrue(row['icon'])
            with self.assertRaises(ValueError):community_schema('43')
    def test_completionist_never_maps_by_position(self):
        text='<table><tr><td><img src="https://shared.fastly.steamstatic.com/first.jpg"></td><td><strong>First</strong> Begin the story</td><td>visible</td><td>12.5%</td><td>12</td></tr></table>'
        with patch('achievement_web.fetch_page',return_value=text):
            row=completionist_schema('42')[0];self.assertEqual(row['id'],'title:First');self.assertEqual(row['rarity'],12.5)
            row=completionist_schema('42',[dict(id='A',name='First',icon='')])[0];self.assertEqual(row['id'],'A')
    def test_statistics_unknown_dates_and_rarity(self):
        now=datetime(2026,10,23,12);schema=[dict(id='A',rarity=.5,rarity_known=True),dict(id='B',rarity=0,rarity_known=False),dict(id='C',rarity=15,rarity_known=True)]
        snap=game_snapshot(dict(id='one',name='One'),dict(total=3,unlocked=2),schema,dict(unlocks=dict(A=datetime(2026,10,22,12).timestamp(),B=0,UNRELATED=1700000000)))
        value=statistics([snap],'one',7,now);self.assertEqual(value['unlocked'],2);self.assertEqual(value['dated_unlocks'],1);self.assertEqual(value['unknown_dates'],1)
        self.assertEqual(value['rarity'],[1,0,0,0,1]);self.assertEqual(value['cumulative'][-1],1);self.assertEqual(len(value['daily']),7)
        self.assertEqual(statistics([],period=30,now=now)['percent'],0)
    def test_export_does_not_use_api_ids_as_paths(self):
        from achievement_export import export_definitions
        icon=self.root/'source.png';icon.write_bytes(b'fixture');before=icon.read_bytes()
        schema=[dict(id='../FIRST',name='First',icon='https://shared.fastly.steamstatic.com/first.png')]
        result=export_definitions(schema,'42',self.root/'exports',lambda _:str(icon))
        path=Path(result['path']);data=json.loads((path/'steam_settings/achievements.json').read_text(encoding='utf-8'))
        self.assertEqual(data[0]['name'],'../FIRST');self.assertNotIn('..',data[0]['icon']);self.assertEqual(result['icons'],1);self.assertEqual(icon.read_bytes(),before)
        self.assertTrue((path/'steam_settings'/data[0]['icon']).is_file())
        with self.assertRaises(ValueError):export_definitions([dict(schema[0],match_mode='title')],'42',self.root/'exports',lambda _:'')


if __name__=='__main__':unittest.main()
