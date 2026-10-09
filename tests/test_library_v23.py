"""Platform ownership, taxonomy migration, series thresholds and home recommendations."""
from pathlib import Path
import sys,tempfile,unittest,uuid,json,io
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from library_sources import platform_for,playnite_metadata,candidate,import_rows,annotate_duplicates
from library_catalog import sections,prepare_game,valid_series,primary
from library_organizer import suggestions
STEAM={'$guid':'cb91dfc9-b977-43bf-8e70-55f46e410fab'}
EMPTY={'$guid':'00000000-0000-0000-0000-000000000000'}

class LibraryV23(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_steam_artwork_is_not_platform_ownership(self):
        raw={'PluginId':EMPTY,'GameId':str(uuid.uuid4()),'InstallDirectory':'SteamLibrary/Game','Links':[{'Url':'https://store.steampowered.com/app/2531310/'}]}
        self.assertEqual(platform_for(raw),'local')
        fields=playnite_metadata(raw);self.assertEqual(fields['metadata_steam_appid'],'2531310');self.assertNotIn('steam_appid',fields)
        self.assertEqual(platform_for({**raw,'PluginId':STEAM,'GameId':'2531310'}),'steam')
        store=Store(self.root/'data','test');install=self.root/'Manual';install.mkdir()
        row=candidate('Manual game','local','manual',install);row['metadata_steam_appid']='2531310';import_rows(store,[row])
        self.assertEqual(store.games[0]['platform'],'local');self.assertEqual(store.games[0]['metadata_steam_appid'],'2531310');self.assertNotIn('steam_appid',store.games[0])
    def test_old_schema_migrates_groups_to_tags_with_backup_and_stable_paths(self):
        game={'id':'old','name':'Manual','platform':'steam','external_id':str(uuid.uuid4()),'source':'Playnite','steam_appid':'bad-id','groups':['动作角色扮演','魂类','开放世界'],'favorite':True,'cover':''}
        write_json(self.root/'library.json',[game]);write_json(self.root/'groups.json',game['groups'])
        store=Store(self.root,'test');self.assertEqual(store.games[0]['platform'],'local');self.assertEqual(store.games[0]['category'],'角色扮演')
        self.assertEqual(store.games[0]['tags'],game['groups']);self.assertTrue(store.games[0]['favorite'])
        self.assertEqual(json.loads((self.root/'migrations/v23/library.json').read_text(encoding='utf-8')),[game])
        self.assertEqual(Store(self.root,'test').games,store.games)
    def test_refresh_repairs_existing_playnite_platform_and_real_last_activity(self):
        store=Store(self.root,'test');store.games=[{'id':'native','name':'Steam game','cover':''},{'id':'manual','name':'Manual','cover':''}]
        store.local={'native':{'save_dir':'keep native'},'manual':{'save_dir':'keep manual'}}
        rows=[{'_id':{'$guid':'native'},'PluginId':STEAM,'GameId':'123','LastActivity':{'$date':'2026-09-01T00:00:00Z'},'ResolvedTags':['合作'],'ResolvedGenres':['射击']},
              {'_id':{'$guid':'manual'},'PluginId':EMPTY,'GameId':'uuid','RecentActivity':{'$date':'2026-10-01T00:00:00Z'},'Links':[{'Url':'https://store.steampowered.com/app/123/'}]}]
        self.assertEqual(store.sync_playnite_metadata(rows),2)
        self.assertEqual(store.games[0]['platform'],'steam');self.assertEqual(store.games[1]['platform'],'local')
        self.assertEqual(store.games[0]['category'],'射击竞技');self.assertNotIn('last_played',store.games[1]);self.assertEqual(store.local['native']['save_dir'],'keep native')
    def test_series_requires_multiple_distinct_games_and_tags_remain_searchable(self):
        games=[{'id':'a','name':'9-nine A','series':'9-nine-','tags':['视觉小说','恋爱']},{'id':'b','name':'9-nine B','series':'9-nine','tags':['视觉小说']},{'id':'c','name':'Solo RPG','series':'Solo','tags':['RPG','开放世界']}]
        self.assertEqual(list(valid_series(games)),['9-nine'])
        home=sections(games);series=next(row for row in home if row['id']=='series')
        self.assertEqual(series['items'][0]['count'],2);self.assertEqual(len(series['items']),1)
        self.assertIn('恋爱',prepare_game(games[0])['searchText']);self.assertEqual(primary(['动作','第一人称射击']),'射击竞技')
        self.assertEqual(primary(['Action','Adventure']),'动作冒险');self.assertEqual(primary(['Indie','Strategy','Simulation']),'策略模拟')
    def test_recommendations_use_recent_tags_and_do_not_recommend_the_recent_game(self):
        games=[{'id':'recent','name':'Recent','tags':['RPG','魂类'],'last_played':'2026-10-09T01:00:00Z'}, {'id':'similar','name':'Similar','tags':['RPG','魂类']}, {'id':'other','name':'Shooter','tags':['射击']}]
        home=sections(games);row=next(row for row in home if row['id']=='recommend')
        self.assertEqual(row['items'][0]['id'],'similar');self.assertNotIn('recent',[game['id'] for game in row['items']])
    def test_ai_classifies_into_one_category_with_rich_tags_and_prunes_singletons(self):
        store=Store(self.root,'test');store.games=[{'id':'a','name':'Solo RPG','tags':['开放世界']}];store.save_settings({'ai_key':'dummy'})
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':[{'id':'a','category':'角色扮演','tags':['动作','魂类'],'series':'Solo'}]})}}]}
        with patch('library_organizer.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):rows=suggestions(store,True)
        self.assertEqual(rows[0]['groups'],['角色扮演']);self.assertEqual(rows[0]['series'],'');self.assertIn('开放世界',rows[0]['tags']);self.assertNotIn('category',store.games[0])
    def test_real_litedb_export_resolves_genre_and_tag_ids(self):
        from services import run_process
        base=Path(Store().settings['playnite']);dll=base/'LiteDB.dll'
        if not dll.is_file():dll=base/'Playnite/LiteDB.dll'
        if not dll.is_file():self.skipTest('Playnite LiteDB not installed')
        script=self.root/'create-fixture.ps1'
        script.write_text('''param([string]$Dll,[string]$Folder)
Add-Type -Path $Dll
$taskGenre="11111111-1111-1111-1111-111111111111"
$taskTag="22222222-2222-2222-2222-222222222222"
foreach($taskKind in @('games','genres','tags')) {
    $taskDb=[LiteDB.LiteDatabase]::new((Join-Path $Folder ($taskKind+'.db')))
    try {
        if($taskKind -eq 'games') {$taskCollection='Game';$taskJson='{"_id":{"$guid":"33333333-3333-3333-3333-333333333333"},"Name":"Fixture","PluginId":{"$guid":"cb91dfc9-b977-43bf-8e70-55f46e410fab"},"GenreIds":[{"$guid":"11111111-1111-1111-1111-111111111111"}],"TagIds":[{"$guid":"22222222-2222-2222-2222-222222222222"}]}'}
        elseif($taskKind -eq 'genres') {$taskCollection='Genre';$taskJson='{"_id":{"$guid":"11111111-1111-1111-1111-111111111111"},"Name":"RPG"}'}
        else {$taskCollection='Tag';$taskJson='{"_id":{"$guid":"22222222-2222-2222-2222-222222222222"},"Name":"Co-op"}'}
        $taskDb.GetCollection($taskCollection).Insert([LiteDB.JsonSerializer]::Deserialize($taskJson)) | Out-Null
    } finally {$taskDb.Dispose()}
}
''',encoding='utf-8-sig')
        made=run_process(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Dll',str(dll),'-Folder',str(self.root)],timeout=20)
        self.assertEqual(made.returncode,0,made.stderr)
        output=self.root/'export.json'
        exported=run_process(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/export_playnite.ps1'),'-AssemblyPath',str(dll),'-DatabasePath',str(self.root/'games.db'),'-OutputPath',str(output)],timeout=20)
        self.assertEqual(exported.returncode,0,exported.stderr)
        row=json.loads(output.read_text(encoding='utf-8'))[0];self.assertEqual(row['ResolvedGenres'],['RPG']);self.assertEqual(row['ResolvedTags'],['Co-op'])
if __name__=='__main__':unittest.main(verbosity=2)
