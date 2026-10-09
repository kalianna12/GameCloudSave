from pathlib import Path
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from library_sources import scan,installed,import_rows,platform_for

class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
    def tearDown(self):
        import gc
        gc.collect();self.temp.cleanup()
    def test_scan_nested_batch_and_exclude_installers(self):
        root=self.root/'games';game=root/'Example';(game/'Binaries/Win64').mkdir(parents=True)
        for file in (game/'Binaries/Win64/Example.exe',game/'Start.bat',game/'unins000.exe',game/'setup.exe'):file.write_text('do not execute')
        rows=scan(root)['rows']
        self.assertEqual({Path(row['exe']).name for row in rows},{'Example.exe','Start.bat'})
        self.assertTrue(all(row['name']=='Example' for row in rows))
        store=Store(self.root/'data','A');import_rows(store,[rows[0]]);import_rows(store,[rows[0]])
        self.assertEqual(len(store.games),1)
        self.assertEqual(store.local[store.games[0]['id']]['launch_mode'],'direct')
    def test_native_steam_and_cross_source_dedup(self):
        base=self.root/'Steam';game=base/'steamapps/common/Example';game.mkdir(parents=True)
        (base/'steamapps/appmanifest_123.acf').write_text('"AppState" { "appid" "123" "name" "Example" "installdir" "Example" }')
        rows=installed(['steam'],[base]);self.assertEqual(len(rows),1)
        store=Store(self.root/'data','A');game_id=str(uuid.uuid4())
        store.games=[{'id':game_id,'name':'Example','cover':'','steam_appid':'123'}]
        import_rows(store,rows);self.assertEqual(store.games[0]['id'],game_id)
        self.assertEqual(store.local[game_id]['launch_uri'],'steam://rungameid/123')
    def test_plugin_classification(self):
        self.assertEqual(platform_for({'PluginId':{'$guid':'CB91DFC9-B977-43BF-8E70-55F46E410FAB'}}),'steam')
        self.assertEqual(platform_for({'PluginId':{'$guid':'00000002-DBD1-46C6-B5D0-B1BA559D10E4'}}),'epic')
        self.assertEqual(platform_for({'PluginId':{'$guid':'C2F038E5-8B92-4877-91F1-DA9094155FC5'}}),'ubisoft')
    def test_playnite_platform_filter_preserves_local_save_settings(self):
        from types import SimpleNamespace
        base=self.root/'Playnite';library=self.root/'library';base.mkdir();library.mkdir()
        (base/'LiteDB.dll').write_bytes(b'fixture');(library/'games.db').write_bytes(b'fixture')
        game_id=str(uuid.uuid4());other=str(uuid.uuid4())
        rows=[{'_id':{'$guid':game_id},'PluginId':{'$guid':'CB91DFC9-B977-43BF-8E70-55F46E410FAB'},'GameId':'123','Name':'Steam game'},
              {'_id':{'$guid':other},'PluginId':{'$guid':'00000002-DBD1-46C6-B5D0-B1BA559D10E4'},'GameId':'abc','Name':'Epic game'}]
        def export(command,**kwargs):
            Path(command[command.index('-OutputPath')+1]).write_text(json.dumps(rows),encoding='utf-8')
            return SimpleNamespace(returncode=0)
        store=Store(self.root/'data','A');store.settings.update(playnite=str(base),library=str(library))
        store.local[game_id]={'save_dir':'original'}
        with patch('services.run_process',side_effect=export):self.assertEqual(store.import_playnite(['steam']),1)
        self.assertEqual([g['id'] for g in store.games],[game_id]);self.assertEqual(store.local[game_id]['save_dir'],'original')
    def test_epic_and_ubisoft_native_adapters(self):
        import os
        from types import SimpleNamespace
        programdata=self.root/'ProgramData';base=programdata/'Epic/EpicGamesLauncher/Data/Manifests';base.mkdir(parents=True)
        install=self.root/'EpicGame';install.mkdir();(install/'Game.exe').write_bytes(b'fixture')
        (base/'game.item').write_text(json.dumps({'InstallLocation':str(install),'LaunchExecutable':'Game.exe','AppName':'epic-id','DisplayName':'Epic game'}))
        class Key:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.dict(os.environ,{'PROGRAMDATA':str(programdata)}),patch('winreg.OpenKey',return_value=Key()),patch('winreg.QueryInfoKey',return_value=(1,0,0)),patch('winreg.EnumKey',return_value='99'),patch('winreg.QueryValueEx',return_value=(str(install),1)):
            rows=installed(['epic','ubisoft'])
        self.assertEqual({row['platform'] for row in rows},{'epic','ubisoft'})
    def configure_cloud(self,store):
        remote=self.root/'remote';remote.mkdir(exist_ok=True)
        def remote_path(text):
            path=(remote/text.removeprefix('gamecloud:')).resolve()
            assert path.is_relative_to(remote.resolve());return path
        def rclone(command,*args,**kwargs):
            operation=command[0]
            if operation=='copyto':
                source=remote_path(command[1]) if command[1].startswith('gamecloud:') else Path(command[1])
                target=remote_path(command[2]) if command[2].startswith('gamecloud:') else Path(command[2])
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);return ''
            if operation=='lsjson':
                base=remote_path(command[1]);return json.dumps([{'Name':file.name,'Path':file.relative_to(base).as_posix(),'IsDir':False,'Size':file.stat().st_size,'ModTime':'2026-10-09T00:00:00Z'} for file in base.rglob('*') if file.is_file()])
            if operation=='copy':
                base=remote_path(command[1]);target=Path(command[2])
                for file in base.rglob('*.zip.json'):
                    output=target/file.relative_to(base);output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,output)
                return ''
            if operation=='cat':return remote_path(command[1]).read_text(encoding='utf-8')
            raise AssertionError(command)
        store.rclone=rclone;store.settings['cloud_folder']='game-saves';return remote
    def make_store(self,computer,game_id):
        store=Store(self.root/computer,computer);store.settings['computer']=computer
        store.games=[{'id':game_id,'name':'Example','cover':'','platform':'steam','external_id':'123'}]
        saves=self.root/computer/'Release';saves.mkdir(parents=True);(saves/'slot1.sav').write_text(computer)
        store.save_game(game_id,{'save_dir':str(saves)});self.configure_cloud(store);return store,saves
    def test_cross_device_notes_and_restore(self):
        a_id=str(uuid.uuid4());b_id=str(uuid.uuid4())
        a,a_saves=self.make_store('PC-A',a_id);b,b_saves=self.make_store('PC-B',b_id)
        archive=a.backup(a_id);snapshot=a.history(a_id)[0]['id'];a.set_snapshot_note(a_id,snapshot,'Chapter three')
        a.upload(a_id,archive)
        records=b.cloud_history(b_id);self.assertEqual(len(records),1)
        self.assertEqual(records[0]['note'],'Chapter three');self.assertEqual(records[0]['computer'],'PC-A')
        imported=b.receive_cloud_snapshot(b_id,records[0]);self.assertEqual((b_saves/'slot1.sav').read_text(),'PC-B')
        b.restore(b_id,imported);self.assertEqual((b_saves/'slot1.sav').read_text(),'PC-A')
        self.assertTrue(list(b_saves.parent.glob('Release.before-restore.*')))
        b.set_snapshot_note(b_id,imported,'Continue here')
        self.assertEqual(a.cloud_history(a_id)[0]['note'],'Continue here')
        self.assertEqual(a.cloud_history(a_id)[0]['computer'],'PC-A')
    def test_corrupt_hash_rejected_without_save_changes(self):
        game_id=str(uuid.uuid4());a,_=self.make_store('PC-A',game_id);b,saves=self.make_store('PC-B',game_id)
        archive=a.backup(game_id);a.upload(game_id,archive);record=b.cloud_history(game_id)[0]
        record['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'校验'):b.receive_cloud_snapshot(game_id,record)
        self.assertEqual((saves/'slot1.sav').read_text(),'PC-B')
    def test_launch_batch_is_explicit_and_hidden(self):
        store=Store(self.root/'data','A');game_id=str(uuid.uuid4());file=self.root/'Start.bat';file.write_text('exit /b')
        store.local[game_id]={'exe':str(file),'launch_mode':'direct'}
        with patch('services.subprocess.Popen') as launch:
            store.launch(game_id)
            self.assertIn('/d',launch.call_args.args[0]);self.assertEqual(launch.call_args.kwargs['creationflags'],0x08000000)

if __name__=='__main__':unittest.main(verbosity=2)
