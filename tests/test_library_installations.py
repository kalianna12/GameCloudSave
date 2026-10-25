from pathlib import Path
import sys,tempfile,unittest,uuid,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from library_installations import launch_fields,installation,probe

class Installations(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
        self.folder=self.root/'Game';self.folder.mkdir();self.exe=self.folder/'Game.exe';self.exe.write_bytes(b'fixture')
        self.ident=str(uuid.uuid4())
        self.raw={'_id':{'$guid':self.ident},'Name':'Game','InstallDirectory':str(self.folder),'IsInstalled':True,
                  'GameActions':[{'Type':0,'IsPlayAction':True,'Path':'{InstallDir}/Game.exe','Arguments':'--language zh','WorkingDir':'{InstallDir}'}]}
    def tearDown(self):self.temp.cleanup()
    def test_numeric_action_direct_launch_arguments_and_working_directory(self):
        fields=launch_fields(self.raw)
        self.assertEqual(Path(fields['exe']),self.exe);self.assertEqual(fields['arguments'],'--language zh')
        store=Store(self.root/'data','fixture');store.local[self.ident]={'launch_mode':'playnite','install_dir':str(self.folder),'save_dir':'keep'}
        with patch.object(store,'read_playnite',return_value=[self.raw]),patch('services.subprocess.Popen') as popen:
            popen.return_value.pid=42;self.assertEqual(store.launch(self.ident),42)
            self.assertEqual(popen.call_args.kwargs['cwd'],str(self.folder))
            self.assertNotIn('Playnite',popen.call_args.args[0]);self.assertIn('--language zh',popen.call_args.args[0])
        self.assertEqual(store.local[self.ident]['save_dir'],'keep')
    def test_deleted_game_still_has_save_but_is_not_installed(self):
        local={**launch_fields(self.raw),'install_dir':str(self.folder),'save_dir':str(self.root/'saves')}
        Path(local['save_dir']).mkdir();(Path(local['save_dir'])/'slot.sav').write_text('progress')
        self.exe.unlink();self.folder.rmdir()
        self.assertFalse(installation(local))
        result=probe([{'id':self.ident}],{self.ident:{**local,'installed':True}},[self.raw])
        self.assertFalse(result[self.ident]['values']['installed']);self.assertNotIn('save_dir',result[self.ident]['values'])
        store=Store(self.root/'data','fixture');store.local[self.ident]=local
        with patch('services.subprocess.Popen') as popen,self.assertRaisesRegex(ValueError,'存档和资料已保留'):store.launch(self.ident)
        popen.assert_not_called();self.assertTrue((Path(local['save_dir'])/'slot.sav').is_file())
    def test_actual_file_overrides_playnite_flag_and_manual_launch_is_retained(self):
        raw={**self.raw,'IsInstalled':False}
        self.assertTrue(installation({**launch_fields(raw),'install_dir':str(self.folder)}))
        changed=probe([{'id':self.ident}],{self.ident:{'exe':str(self.exe),'launch_mode':'direct','arguments':'--manual','launch_origin':'manual','installed':False}},[raw])
        self.assertTrue(changed[self.ident]['values']['installed']);self.assertNotIn('arguments',changed[self.ident]['values'])
    def test_ambiguous_scripts_and_emulators_keep_original_launcher(self):
        self.assertFalse(launch_fields({**self.raw,'PreScript':'prepare'}))
        self.assertFalse(launch_fields({**self.raw,'GameActions':[{'Type':2,'IsPlayAction':True,'Path':str(self.exe)}]}))
        other=self.folder/'Other.exe';other.write_bytes(b'fixture')
        self.assertFalse(launch_fields({**self.raw,'GameActions':[*self.raw['GameActions'],{'Type':'File','IsPlayAction':True,'Path':str(other)}]}))
    def test_missing_executable_in_existing_folder_and_empty_directory(self):
        self.exe.unlink();self.assertFalse(installation({'exe':str(self.exe),'install_dir':str(self.folder)}))
        self.assertFalse(installation({'install_dir':str(self.folder),'installed':True}))
        self.assertFalse(installation({'save_dir':str(self.root),'installed':True}))
    def test_relative_working_directory_and_batch_action(self):
        (self.folder/'bin').mkdir();batch=self.folder/'run.cmd';batch.write_text('exit /b')
        raw={**self.raw,'GameActions':[{'Type':'File','IsPlayAction':True,'Path':'run.cmd','WorkingDir':'bin'}]}
        fields=launch_fields(raw);self.assertEqual(Path(fields['exe']),batch);self.assertEqual(Path(fields['working_dir']),self.folder/'bin')
    def test_unresolved_relative_path_and_batch_arguments_need_original_launcher(self):
        self.assertFalse(launch_fields({**self.raw,'InstallDirectory':'','GameActions':[{'Type':0,'IsPlayAction':True,'Path':'Game.exe'}]}))
        self.assertFalse(launch_fields({**self.raw,'GameActions':[{'Type':0,'IsPlayAction':True,'Path':'run.cmd','Arguments':'--extra'}]}))

if __name__=='__main__':unittest.main(verbosity=2)
