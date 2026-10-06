import gc
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import Store, ROOT, write_json
from ai_match import rank_candidates

class Regression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'test-data')
        self.store = Store(Path(self.temp.name), 'test-computer-A')
        self.ident = str(uuid.uuid4())
        self.store.games = [{'id': self.ident, 'name': '中文游戏存档测试', 'cover':'', 'installed':True}]
        write_json(self.store.root / 'library.json', self.store.games)
        self.save = Path(self.temp.name) / '游戏自带存档'
        self.save.mkdir()
        self.file = self.save / 'save.json'
        self.file.write_text('{"章节":42}', encoding='utf-8')
        self.store.save_game(self.ident, {'save_dir':str(self.save)})

    def tearDown(self):
        gc.collect()
        self.temp.cleanup()

    def test_chinese_snapshot_restore_and_history(self):
        first = self.store.backup(self.ident)
        second = self.store.backup(self.ident)
        self.assertNotEqual(first, second)
        rows = self.store.history(self.ident)
        self.assertEqual(len(rows), 2)
        self.file.write_text('changed', encoding='utf-8')
        self.store.restore(self.ident, rows[-1]['id'])
        self.assertEqual(json.loads(self.file.read_text(encoding='utf-8')), {'章节':42})
        self.assertTrue(list(self.save.parent.glob(self.save.name + '.before-restore.*')))

    def test_upload_failure_keeps_snapshot(self):
        archive = self.store.backup(self.ident)
        self.store.save_settings({'cloud_folder':'电脑/GameCloudSave'})
        with patch.object(self.store, 'rclone', side_effect=ValueError('offline')):
            with self.assertRaises(ValueError): self.store.upload(self.ident, archive)
        self.assertTrue(archive.exists())
        self.assertFalse(self.store.history(self.ident)[0]['uploaded'])

    def test_retry_marks_uploaded(self):
        self.store.backup(self.ident)
        self.store.save_settings({'cloud_folder':'/'})
        with patch.object(self.store, 'rclone', return_value='') as rclone:
            self.assertEqual(self.store.retry(self.ident), 1)
            args = rclone.call_args.args[0]
            self.assertTrue(args[2].startswith('gamecloud:' + self.ident + '/'))
        self.assertTrue(self.store.history(self.ident)[0]['uploaded'])

    def test_machine_paths_and_credentials_isolated(self):
        self.store.save_settings({'password':'dummy-test-password','cloud_folder':'电脑/GameCloudSave','cover_size':280})
        other = Store(self.store.root, 'test-computer-B')
        self.assertEqual(len(other.games), 1)
        self.assertFalse(other.local)
        self.assertEqual(other.password(), '')
        self.assertEqual(other.settings['cloud_folder'], '')
        self.assertEqual(self.store.password(), 'dummy-test-password')
        self.assertNotIn('dummy-test-password', (self.store.profile / 'settings.json').read_text())
        self.assertEqual(Store(self.store.root,'test-computer-A').settings['cover_size'],280)

    def test_delete_preserves_save_and_history(self):
        archive = self.store.backup(self.ident)
        self.store.remove(self.ident)
        self.assertFalse(self.store.games)
        self.assertTrue(self.file.exists())
        self.assertTrue(archive.exists())
        self.assertEqual(len(self.store.history(self.ident)), 1)

    def test_launch_uses_playnite_id(self):
        with patch('services.subprocess.Popen') as start:
            self.store.launch(self.ident)
        self.assertEqual(start.call_args.args[0][-2:], ['--start', self.ident])

    def test_restore_wrong_game_rejected(self):
        self.store.backup(self.ident)
        with self.assertRaises(ValueError): self.store.restore(self.ident, 9999)

    def test_ai_cannot_introduce_paths(self):
        def response(matches):
            return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'matches':matches})}}]}).encode())
        with patch('ai_match.urlopen', return_value=response([{'id':1,'confidence':0.9}])):
            self.assertEqual(rank_candidates('中文名', ['path/a','path/b'], 'dummy', 'test'), ['path/b','path/a'])
        with patch('ai_match.urlopen', return_value=response([{'id':99,'confidence':1}])):
            with self.assertRaises(ValueError): rank_candidates('中文名', ['path/a'], 'dummy', 'test')

if __name__ == '__main__': unittest.main(verbosity=2)
