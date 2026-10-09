from pathlib import Path
import gc
import sys,tempfile,unittest,json,zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from cloud_paths import component,folder_path

class CloudPaths(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
        self.store=Store(Path(self.temp.name),'cloud-paths')
        self.ident='12345678-1234-1234-1234-123456789abc'
        self.store.games=[{'id':self.ident,'name':'艾尔登法环 ELDEN RING','cover':''}]
        self.save=Path(self.temp.name)/'EldenRing';self.save.mkdir()
        (self.save/'data.json').write_text('{"chapter":4}')
        self.store.save_game(self.ident,{'save_dir':str(self.save)})
        self.store.settings['cloud_folder']='百度网盘/game-saves'
    def tearDown(self):
        gc.collect()
        self.temp.cleanup()
    def test_upload_uses_playnite_name_and_original_save_folder(self):
        archive=self.store.backup(self.ident)
        self.store.save_game(self.ident,{'save_dir':str(self.save/'another-folder')})
        with patch.object(self.store,'rclone',return_value='') as call:self.store.upload(self.ident,archive)
        copies=[entry.args[0] for entry in call.call_args_list if entry.args[0][0]=='copyto']
        target=next(args[2] for args in copies if args[1]==str(archive))
        self.assertEqual(target,'gamecloud:百度网盘/game-saves/艾尔登法环 ELDEN RING/EldenRing/'+archive.name)
        self.assertTrue(any(args[2]==target+'.json' for args in copies))
        self.assertEqual(self.store.history(self.ident)[0]['cloud_ref'],target)
    def test_special_characters_preserve_readable_name_without_nested_paths(self):
        self.store.games[0]['name']='Fate/stay night: 中文?'
        self.assertIn('/Fate／stay night： 中文？/EldenRing',self.store.cloud_directory(self.ident))
        self.assertEqual(component('CON'),'CON_')
        self.assertEqual(component('名字. '),'名字')
        self.assertEqual(component('../x'),'..／x')
    def test_duplicate_names_do_not_share_folders(self):
        other='87654321-1234-1234-1234-123456789abc'
        self.store.games.append({'id':other,'name':self.store.games[0]['name'],'cover':''})
        self.assertIn(' [12345678]/',self.store.cloud_directory(self.ident))
        self.assertNotEqual(self.store.cloud_directory(self.ident),self.store.cloud_directory(other))
    def test_computer_layer_optional(self):
        self.assertTrue(self.store.cloud_directory(self.ident).endswith('/EldenRing'))
        self.assertTrue(self.store.cloud_directory(self.ident,values={'cloud_separate_computer':True,'computer':'电脑甲'}).endswith('/EldenRing/电脑甲'))
    def test_traversal_rejected(self):
        for value in ('../saves','root/../x','root/./x'):
            with self.assertRaises(ValueError):folder_path(value)
        with patch.object(self.store,'rclone') as call:
            with self.assertRaises(ValueError):self.store.create_cloud_folder('root','../x')
            call.assert_not_called()
    def test_wrong_game_archive_not_uploaded(self):
        archive=self.store.backup(self.ident)
        metadata={'game':'another-game','save_dir':str(self.save)}
        fake=Path(self.temp.name)/'other.zip'
        with zipfile.ZipFile(fake,'w') as zipped:zipped.writestr('_snapshot_meta.json',json.dumps(metadata))
        with patch.object(self.store,'rclone') as call:
            with self.assertRaises(ValueError):self.store.upload(self.ident,fake)
            call.assert_not_called()
    def test_organize_verifies_copy_and_preserves_original(self):
        archive=self.store.backup(self.ident);remote={'gamecloud:root/old/'+archive.name:archive.read_bytes()}
        def rclone(command,folder='',values=None):
            if command=='list':return [{'Name':archive.name,'IsDir':False,'Size':archive.stat().st_size}] if folder=='root/old' else []
            operation,source,target=command[:3]
            self.assertEqual(operation,'copyto')
            if source.startswith('gamecloud:'):Path(target).write_bytes(remote[source])
            else:remote[target]=Path(source).read_bytes()
            return ''
        with patch.object(self.store,'rclone',side_effect=rclone):
            message=self.store.organize_cloud(self.ident,'root/old')
        self.assertIn('1',message)
        self.assertIn('gamecloud:root/old/'+archive.name,remote)
        target='gamecloud:'+self.store.cloud_directory(self.ident)+'/'+archive.name
        self.assertEqual(remote[target],archive.read_bytes())
    def test_organize_mismatch_keeps_history_reference(self):
        archive=self.store.backup(self.ident)
        self.store.upload=lambda *args:None
        def rclone(command,folder='',values=None):
            if command=='list':return [{'Name':archive.name,'IsDir':False}] if folder=='root/old' else []
            if command[0]=='copyto' and command[1].startswith('gamecloud:'):
                Path(command[2]).write_bytes(archive.read_bytes() if 'root/old' in command[1] else b'broken')
            return ''
        with patch.object(self.store,'rclone',side_effect=rclone):
            with self.assertRaises(ValueError):self.store.organize_cloud(self.ident,'root/old')
        self.assertFalse(self.store.history(self.ident)[0]['cloud_ref'])

    def test_organize_retries_temporarily_unavailable_download(self):
        archive=self.store.backup(self.ident);downloads=0
        def rclone(command,folder='',values=None):
            nonlocal downloads
            if command=='list':return [{'Name':archive.name,'IsDir':False}] if folder=='root/old' else []
            if command[0]=='copyto' and command[1].startswith('gamecloud:'):
                if 'root/old' not in command[1]:
                    downloads+=1
                    if downloads==1:raise ValueError('404 temporarily unavailable')
                Path(command[2]).write_bytes(archive.read_bytes())
            return ''
        with patch.object(self.store,'rclone',side_effect=rclone),patch('cloud_management.time.sleep'):
            self.store.organize_cloud(self.ident,'root/old')
        self.assertEqual(downloads,2)

    def test_organize_existing_destination_is_verified_without_overwrite(self):
        archive=self.store.backup(self.ident)
        def rclone(command,folder='',values=None):
            if command=='list':return [{'Name':archive.name,'IsDir':False}]
            self.assertTrue(command[1].startswith('gamecloud:'),'Existing destination must not be overwritten')
            Path(command[2]).write_bytes(archive.read_bytes())
            return ''
        with patch.object(self.store,'rclone',side_effect=rclone):
            self.store.organize_cloud(self.ident,'root/old')

    def test_organize_existing_different_destination_is_not_overwritten(self):
        archive=self.store.backup(self.ident)
        def rclone(command,folder='',values=None):
            if command=='list':return [{'Name':archive.name,'IsDir':False}]
            self.assertTrue(command[1].startswith('gamecloud:'),'Conflicting destination must not be overwritten')
            Path(command[2]).write_bytes(archive.read_bytes() if 'root/old' in command[1] else b'other-data')
            return ''
        with patch.object(self.store,'rclone',side_effect=rclone):
            with self.assertRaises(ValueError):self.store.organize_cloud(self.ident,'root/old')

if __name__=='__main__':unittest.main(verbosity=2)
