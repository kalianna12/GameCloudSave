"""Installer rollback is complete; uninstall never trusts data paths in a manifest."""
from pathlib import Path
import json,sys,tempfile,zipfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
from install_core import install,uninstall,MARKER,PRODUCT
ROOT=Path(__file__).resolve().parents[1]

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.root=Path(self.temp.name)
        self.target=self.root/'installed';self.payload=self.root/'payload.zip'
        with zipfile.ZipFile(self.payload,'w') as z:
            z.writestr('GameCloudSave.exe',b'new');z.writestr('Uninstall.exe',b'new uninstall');z.writestr('_internal/current.dll',b'new dependency')
    def tearDown(self):self.temp.cleanup()
    def old_install(self):
        self.target.mkdir();(self.target/'GameCloudSave.exe').write_bytes(b'old');(self.target/'Uninstall.exe').write_bytes(b'old uninstall')
        (self.target/'obsolete.dll').write_bytes(b'old dependency');(self.target/'user-note.txt').write_text('keep')
        record={'product':PRODUCT,'version':'2.4.0','exe':'GameCloudSave.exe','files':['GameCloudSave.exe','Uninstall.exe','obsolete.dll'],'links':[],'registered':False}
        (self.target/MARKER).write_text(json.dumps(record));return (self.target/MARKER).read_bytes()
    def test_upgrade_removes_only_obsolete_tracked_files(self):
        self.old_install();install(self.payload,self.target,registry=False)
        self.assertFalse((self.target/'obsolete.dll').exists());self.assertEqual((self.target/'user-note.txt').read_text(),'keep')
        self.assertNotIn('obsolete.dll',json.loads((self.target/MARKER).read_text())['files'])
    def test_registration_failure_restores_files_manifest_links_and_registry(self):
        before=self.old_install();desktop=self.root/'desktop';desktop.mkdir();link=desktop/'GameCloudSave.lnk';link.write_bytes(b'old link')
        def shortcut(path,exe,**kwargs):Path(path).write_bytes(b'new link')
        with patch('install_core.registry_state',return_value=[('DisplayName','Before',1)]),patch('install_core.restore_registry') as restore,patch('install_core.register',side_effect=OSError('fixture registry failure')),patch('install_core.shortcut',side_effect=shortcut):
            with self.assertRaises(OSError):install(self.payload,self.target,desktop,registry=True)
        restore.assert_called_once_with([('DisplayName','Before',1)])
        self.assertEqual((self.target/MARKER).read_bytes(),before);self.assertEqual(link.read_bytes(),b'old link')
        self.assertEqual((self.target/'GameCloudSave.exe').read_bytes(),b'old');self.assertTrue((self.target/'obsolete.dll').exists())
        self.assertFalse((self.target/'_internal/current.dll').exists())
    def test_new_install_failure_leaves_no_marker_or_new_shortcuts(self):
        desktop=self.root/'desktop'
        with patch('install_core.registry_state',return_value=None),patch('install_core.restore_registry'),patch('install_core.register',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):install(self.payload,self.target,desktop,registry=True)
        self.assertFalse((self.target/MARKER).exists());self.assertFalse((desktop/'GameCloudSave.lnk').exists())
        self.assertFalse((self.target/'GameCloudSave.exe').exists())
    def test_malicious_uninstall_data_entry_aborts_before_deleting_program(self):
        self.old_install();data=self.target/'data';data.mkdir();(data/'save.zip').write_bytes(b'keep')
        marker=json.loads((self.target/MARKER).read_text());marker['files'].append('data/save.zip');(self.target/MARKER).write_text(json.dumps(marker))
        with self.assertRaises(ValueError):uninstall(self.target)
        self.assertTrue((self.target/'GameCloudSave.exe').exists());self.assertEqual((data/'save.zip').read_bytes(),b'keep')
    def test_payload_with_credentials_is_rejected(self):
        with zipfile.ZipFile(self.payload,'a') as z:z.writestr('credential.dpapi',b'fixture')
        with self.assertRaises(ValueError):install(self.payload,self.target,registry=False)
        self.assertFalse((self.target/'GameCloudSave.exe').exists())
    def test_second_registered_directory_is_rejected(self):
        self.old_install()
        with patch('install_core.registry_state',return_value=[('InstallLocation',str(self.target),1)]):
            with self.assertRaisesRegex(ValueError,'原目录'):install(self.payload,self.root/'another',registry=True)
        self.assertFalse((self.root/'another').exists())
    def test_portable_uninstall_gives_clear_message(self):
        with self.assertRaisesRegex(ValueError,'便携版'):uninstall(self.root)
    def test_invalid_marker_is_rejected_before_copying(self):
        self.target.mkdir();(self.target/MARKER).write_text('[]')
        with self.assertRaises(ValueError):install(self.payload,self.target,registry=False)
        self.assertFalse((self.target/'GameCloudSave.exe').exists())

if __name__=='__main__':unittest.main(verbosity=2)
