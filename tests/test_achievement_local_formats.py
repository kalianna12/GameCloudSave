"""Independent local-file fixtures based on documented formats, never game saves."""
from pathlib import Path
import json,os,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from achievement_files import parse_state,discover
from achievements import Repository
from services import Store


class LocalFormats(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def write(self,path,value):
        path=self.root/path;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8');return path
    def test_codex_aliases_and_explicit_false(self):
        record=self.write('achievements.ini','[FIRST]\nHaveAchieved=1\nHaveAchievedTime=1700000000\nCurProgress=4\nMaxProgress=10\n[SECOND]\nState=0\nUnlockTime=1700000001\nCurProgress=10\nMaxProgress=10')
        rows=parse_state(record)
        self.assertEqual(rows['FIRST'],dict(unlocked=True,time=1700000000,progress=4,max=10))
        self.assertFalse(rows['SECOND']['unlocked'])
        self.assertEqual(rows['SECOND']['progress'],10)
        record.write_text('[ACHIEVE_DATA]\nFIRST=1\nSECOND=0',encoding='utf-8')
        self.assertTrue(parse_state(record)['FIRST']['unlocked'])
        self.assertFalse(parse_state(record)['SECOND']['unlocked'])
    def test_json_lowercase_ids_and_goldberg(self):
        record=self.write('achievements.json',json.dumps([dict(apiname='FIRST',State=1,CurProgress=3),dict(name='SECOND',earned=False,earned_time=1700000000)]))
        rows=parse_state(record);self.assertTrue(rows['FIRST']['unlocked']);self.assertEqual(rows['FIRST']['progress'],3)
        self.assertFalse(rows['SECOND']['unlocked'])
    def test_textual_alternative_names_and_separate_times(self):
        for filename in ('achiev.ini','stats.ini','CreamAPI.Achievements.cfg','Achievements.Bin','achieve.dat'):
            path=self.write('game/'+filename,'[Achievements]\nFIRST=1\nSECOND=0\n[AchievementsUnlockTimes]\nFIRST=1700000000\nSECOND=1700000001')
            rows=parse_state(path);self.assertEqual(rows['FIRST']['time'],1700000000);self.assertFalse(rows['SECOND']['unlocked'])
        with patch('achievement_steam.steam_roots',return_value=[]):
            result=discover({},dict(install_dir=str(self.root/'game')),'')
        self.assertEqual(len(result['sources']),5)
    def test_new_roots_stay_scoped_to_appid(self):
        paths=('roaming/EMPRESS/42/achievements.ini','roaming/Steam/CODEX/42/achievements.ini','roaming/CreamAPI/42/stats/CreamAPI.Achievements.cfg','program/Steam/player/42/achiev.ini','documents/SKIDROW/42/achieve.dat')
        for path in paths:self.write(path,'[FIRST]\nAchieved=1')
        self.write('roaming/EMPRESS/420/achievements.ini','[OTHER]\nAchieved=1')
        env={name:str(self.root/sub) for name,sub in [('APPDATA','roaming'),('LOCALAPPDATA','local'),('PUBLIC','public'),('PROGRAMDATA','program')]}
        with patch.dict(os.environ,env),patch('achievement_files.documents_dir',return_value=self.root/'documents'),patch('achievement_steam.steam_roots',return_value=[]):
            result=discover({}, {},'42')
        self.assertEqual(len(result['sources']),5);self.assertFalse(any('/420/' in p.replace('\\','/') for p in result['sources']))
        self.assertFalse(result['rejected'])
    def test_record_mismatch_and_unreadable_diagnostics(self):
        record=self.write('game/achievements.ini','[WRONG_VERSION]\nAchieved=1')
        self.write('game/stats.ini','[Settings]\nVolume=90')
        repository=Repository(self.root/'profile');config=repository.config('fixture')
        config.update(source=str(record),schema=[dict(id='FIRST',name='First',description='',icon='',hidden=False,max=0)])
        with patch('achievement_steam.steam_roots',return_value=[]):repository.setup(dict(id='fixture'),dict(install_dir=str(self.root/'game')))
        view=repository.view('fixture');self.assertEqual(view['record_matched'],0);self.assertIn('不匹配',view['record_status'])
        self.assertEqual(view['unlocked'],0);self.assertTrue(config['rejected'])
        self.assertFalse(repository.summary('fixture')['record_ready'])
    def test_badge_preference_persistence_and_validation(self):
        store=Store(self.root/'isolated','fixture');self.assertEqual(store.settings['achievement_badges'],'hover')
        for value in ('hidden','always','hover'):
            store.save_settings(dict(achievement_badges=value))
            self.assertEqual(Store(self.root/'isolated','fixture').settings['achievement_badges'],value)
        with self.assertRaises(ValueError):store.save_settings(dict(achievement_badges='invalid'))


if __name__=='__main__':unittest.main()
