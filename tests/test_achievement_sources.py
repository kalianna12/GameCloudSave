"""Upstream Steam cache format, source fallback and file location regressions."""
from pathlib import Path
import json,struct,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from achievement_files import discover,parse_state,identify
from achievement_steam import schema_file,read_kv,cache_paths
from achievement_sources import resolve,hunters_schema


def kv(value):
    result=b''
    for key,item in value.items():
        name=str(key).encode()+b'\0'
        if isinstance(item,dict):result+=b'\0'+name+kv(item)+b'\x08'
        elif isinstance(item,int):result+=b'\x02'+name+struct.pack('<i',item)
        else:result+=b'\x01'+name+str(item).encode()+b'\0'
    return result


def steam_fixture(root,appid='43',mask=1):
    directory=Path(root)/'appcache/stats';directory.mkdir(parents=True,exist_ok=True)
    schema={'game':{'stats':{'7':{'type':'4','bits':{'0':{'name':'FIRST','display':{'name':{'schinese':'第一步'},'desc':{'schinese':'开始冒险'}}},'31':{'name':'LAST','display':{'name':{'english':'Last'}}}}},
                            '8':{'type':'1','name':'KILLS'},'9':{'type':'4','bits':{'2':{'name':'TEN','display':{'name':{'english':'Ten'}},'progress':{'min_val':'5','max_val':'15','value':{'operation':'statvalue','operand1':'KILLS'}}}}}}}}
    definition=directory/f'UserGameStatsSchema_{appid}.bin';definition.write_bytes(kv(schema))
    state=directory/f'UserGameStats_1234_{appid}.bin'
    state.write_bytes(kv({'cache':{'7':{'data':mask,'AchievementTimes':{'0':1700000000}},'8':{'data':8},'9':{'data':0}}}))
    return state,definition


class Sources(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_steam_bitmask_and_progress(self):
        source,schema=steam_fixture(self.root,mask=-2147483647)
        rows=parse_state(source)
        self.assertTrue(rows['FIRST']['unlocked']);self.assertTrue(rows['LAST']['unlocked'])
        self.assertFalse(rows['TEN']['unlocked']);self.assertEqual(rows['TEN']['progress'],3)
        self.assertEqual(schema_file(schema)[2]['max'],10)
        self.assertEqual(rows['FIRST']['time'],1700000000)
    def test_missing_schema_and_truncated_binary(self):
        source,schema=steam_fixture(self.root);schema.unlink()
        with self.assertRaises(OSError):parse_state(source)
        source.write_bytes(b'\0unfinished')
        with self.assertRaises(ValueError):read_kv(source)
    def test_live_steam_definition_dependency(self):
        from achievements import Repository
        from achievement_monitor import check
        source,definition=steam_fixture(self.root,mask=-2147483647)
        full=definition.read_bytes();schema=read_kv(definition)
        schema['game']['stats']['7']['bits'].pop('31');definition.write_bytes(kv(schema))
        repository=Repository(self.root/'profile');config=repository.config('ori')
        config.update(appid='43',source=str(source),platform='steam',schema=[dict(id=key,name=key,hidden=False,icon='') for key in ('FIRST','LAST','TEN')])
        session=dict(ident='ori',game=dict(id='ori',name='Ori',platform='steam'),local={},target={},passive=True,signature=None,discovery=0)
        check(repository,session)
        self.assertEqual(repository.summary('ori')['unlocked'],1)
        before=source.stat().st_mtime_ns
        definition.write_bytes(full)
        updated=check(repository,session)
        self.assertTrue(updated)
        self.assertEqual(source.stat().st_mtime_ns,before)
        self.assertEqual(repository.summary('ori')['unlocked'],2)
    def test_find_exact_appid_and_multiple_accounts(self):
        source,schema=steam_fixture(self.root);other=source.with_name('UserGameStats_4567_43.bin');other.write_bytes(source.read_bytes())
        with patch('achievement_steam.steam_roots',return_value=[self.root]):
            found=discover({}, {},'43')
            self.assertEqual(len(found['sources']),2);self.assertEqual(len(found['schemas']),1)
            self.assertFalse(cache_paths('430')[0])
    def test_config_appid_and_alternate_ini_names(self):
        game=self.root/'game';game.mkdir();(game/'steam_emu.ini').write_text('[Steam]\nAppId=42',encoding='utf-8')
        record=game/'achievements_progress.ini';record.write_text('[Achievements]\nFIRST.achieved=1\nFIRST.unlocktime=1700000000',encoding='utf-8')
        self.assertEqual(identify({}, {'install_dir':str(game)}),'42')
        self.assertTrue(parse_state(record)['FIRST']['unlocked'])
        self.assertEqual(set(parse_state(record)),{'FIRST'})
        with patch('achievement_steam.steam_roots',return_value=[]):self.assertEqual(len(discover({}, {'install_dir':str(game)},'42')['sources']),1)
    def test_steam_identity_uses_platform_id(self):
        self.assertEqual(identify({'platform':'steam','steam_appid':'43','metadata_steam_appid':'42'},{}),'43')
    def test_provider_priority_cache_and_explicit_failure(self):
        rows=[{'id':'FIRST','name':'First'}]
        with patch('achievement_sources.hunters_schema',return_value=rows) as hunters:
            value,label,_=resolve('43','auto',[],steam_fetch=lambda _:rows)
            self.assertIn('Steam ',label);hunters.assert_not_called()
            value,label,failures=resolve('43','auto',rows,steam_fetch=lambda _:(_ for _ in ()).throw(OSError('offline')))
            self.assertIn('本地',label);self.assertTrue(failures);hunters.assert_not_called()
            value,label,_=resolve('43','auto',[],steam_fetch=lambda _:(_ for _ in ()).throw(OSError('offline')))
            self.assertEqual(label,'SteamHunters')
        with patch('achievement_sources.fetch_json',return_value=[{'apiName':'FIRST','name':'第一步','description':'开始','icon':'hash.jpg'}]):
            row=hunters_schema('43')[0];self.assertEqual(row['id'],'FIRST');self.assertEqual(row['name'],'第一步')


if __name__=='__main__':unittest.main()
