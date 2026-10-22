"""Read-only adapters, source/account isolation, baseline and replay protection."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from achievement_files import parse_state, normalize_schema, merge_progress, discover, identify, steam_schema
from achievements import Repository


class LocalAchievements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.game = {'id': 'fixture', 'name': 'Achievement fixture', 'platform': 'local'}

    def tearDown(self): self.temp.cleanup()

    def file(self, name, value):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding='utf-8')
        return path

    def test_json_false_and_counters_do_not_unlock(self):
        path = self.file('achievements.json', {'FIRST': {'earned': 'false', 'earned_time': 100, 'progress': 3}, 'WIN': {'earned': True, 'earned_time': 10}, 'STAT': 99})
        state = parse_state(path)
        self.assertFalse(state['FIRST']['unlocked']); self.assertEqual(state['FIRST']['progress'], 3)
        self.assertTrue(state['WIN']['unlocked']); self.assertNotIn('STAT', state)

    def test_ini_and_utf16(self):
        path = self.file('achievements.ini', '[ACH_ONE]\nAchieved=1\nUnlockTime=0x6553f100\n[ACH_TWO]\nearned=false\nprogress=4\n')
        expected = parse_state(path); self.assertEqual(expected['ACH_ONE']['time'], 1700000000)
        self.assertFalse(expected['ACH_TWO']['unlocked'])
        path.write_text(path.read_text(encoding='utf-8'), encoding='utf-16')
        self.assertEqual(parse_state(path), expected)

    def test_ini_flat_and_prefixed(self):
        path = self.file('user_stats.ini', '[Achievements]\nA=1\nB=0\n[ACHIEVEMENTS.C]\nunlocked=true\n[Stats]\ncoins=900\n')
        rows = parse_state(path)
        self.assertEqual(set(rows), {'A', 'B', 'C'}); self.assertTrue(rows['C']['unlocked'])

    def test_schema_is_not_progress(self):
        schema = [{'name': 'A', 'displayName': {'schinese': '初次冒险', 'english': 'First'}, 'description': 'Begin', 'hidden': '0'}]
        path = self.file('steam_settings/achievements.json', schema)
        self.assertFalse(parse_state(path)); self.assertEqual(normalize_schema(schema)[0]['name'], '初次冒险')
        self.assertFalse(normalize_schema({'A': {'earned': True}}))

    def test_baseline_and_relock_never_replay(self):
        record = {}; yes = {'unlocked': True, 'time': 100, 'progress': 0}; no = {'unlocked': False, 'time': 0, 'progress': 0}
        self.assertEqual(merge_progress(record, {'A': yes}, True)[0], [])
        self.assertEqual(merge_progress(record, {'A': yes, 'B': yes}, True)[0], ['B'])
        merge_progress(record, {'A': no}, True); merge_progress(record, {}, True)
        self.assertEqual(merge_progress(record, {'A': yes, 'B': yes}, True)[0], [])
        self.assertEqual(set(record['unlocks']), {'A', 'B'})

    def test_discovery_separates_schema_and_accounts(self):
        self.file('game/steam_settings/achievements.json', [{'name': 'A', 'displayName': 'First'}])
        self.file('game/user1/achievements.json', {'A': {'earned': False}})
        self.file('game/user2/achievements.json', {'A': {'earned': True}})
        result = discover(self.game, {'install_dir': str(self.root/'game')}, '')
        self.assertEqual(len(result['sources']), 2); self.assertEqual(len(result['schemas']), 1)
        repository = Repository(self.root/'profile'); config = repository.setup(self.game, {'install_dir': str(self.root/'game')})
        self.assertFalse(config['source'])  # Never silently combine account 1 and 2.

    def test_namespace_history_and_reopen(self):
        one = self.file('one/achievements.json', {'A': {'earned': True}})
        two = self.file('two/achievements.json', {'B': {'earned': True}})
        repository = Repository(self.root/'profile'); config = repository.config('fixture')
        config.update(source=str(one), appid='42'); repository.setup(self.game, {})
        self.assertEqual(repository.view('fixture')['unlocked'], 1)
        config['source'] = str(two); self.assertFalse(repository.record('fixture', config))
        repository.setup(self.game, {}); self.assertEqual(set(repository.record('fixture', config)['unlocks']), {'B'})
        config['source'] = str(one); repository.save()
        reopened = Repository(self.root/'profile'); self.assertEqual(reopened.view('fixture')['rows'][0]['id'], 'A')

    def test_missing_source_baseline_allows_first_unlock(self):
        repository = Repository(self.root/'profile'); config = repository.config('fixture')
        config['source'] = str(self.root/'not-created/achievements.json')
        repository.setup(self.game, {})
        record = repository.record('fixture', config)
        self.assertEqual(merge_progress(record, {'FIRST': {'unlocked': True, 'time': 0, 'progress': 0}}, True)[0], ['FIRST'])

    def test_partial_write_preserves_repository_and_game_bytes(self):
        path = self.file('game/achievements.json', {'A': {'earned': True}}); original = path.read_bytes()
        repository = Repository(self.root/'profile'); repository.config('fixture')['source'] = str(path)
        repository.setup(self.game, {}); self.assertEqual(original, path.read_bytes())
        path.write_text('{"A":', encoding='utf-8')
        with self.assertRaises(ValueError): parse_state(path)
        self.assertEqual(repository.view('fixture')['unlocked'], 1)

    def test_matching_uses_exact_internal_ids_and_localization(self):
        payload = {'response': {'achievements': [{'internal_name': 'FIRST', 'localized_name': '初来乍到', 'localized_desc': '进入游戏', 'icon': 'abc.jpg', 'hidden': False}]}}
        with patch('achievement_files.fetch_json', return_value=payload): rows = steam_schema('42')
        self.assertEqual(rows[0]['id'], 'FIRST'); self.assertEqual(rows[0]['name'], '初来乍到')
        self.assertIn('/42/abc.jpg', rows[0]['icon'])
        with self.assertRaises(ValueError): steam_schema('../bad')
        self.file('game/steam_appid.txt', '42')
        self.assertEqual(identify(self.game, {'install_dir': str(self.root/'game')}), '42')


if __name__ == '__main__': unittest.main()
