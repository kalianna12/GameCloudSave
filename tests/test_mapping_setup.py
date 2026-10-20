"""No system installation: verify repair ordering, skip rules, cancellation and pinned download."""
from pathlib import Path
import sys,tempfile,time,threading,hashlib,unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from services import Store,ROOT
import mapping_setup as setup
app=QCoreApplication.instance() or QCoreApplication([])
def state(package=True,driver=True):return {'package':package,'driver':driver,'ready':package and driver,'supported':True}

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.folder.name,'setup');self.helper=None
    def tearDown(self):
        if self.helper:self.helper.shutdown()
        app.processEvents();self.folder.cleanup()
    def wait(self):
        deadline=time.monotonic()+3
        while self.helper.state['busy'] and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        self.assertFalse(self.helper.state['busy'])
    def test_installed_components_never_reinstalled(self):
        with patch.object(setup,'inspect_components',return_value=state()),patch.object(setup,'download_driver') as download,patch.object(setup.subprocess,'run') as process:
            self.helper=setup.MappingSetup(self.store);self.helper.install();self.wait()
            download.assert_not_called();process.assert_not_called();self.assertTrue(self.helper.state['ready'])
    def test_missing_components_installed_in_order_with_embedded_driver_skipped(self):
        order=[];path=Path(self.folder.name)/'verified.exe'
        with patch.object(setup,'inspect_components',side_effect=[state(False,False),state(False,False),state()]),patch.object(setup.subprocess,'run',side_effect=lambda *a,**k:(order.append(('module',a,k)) or Mock(returncode=0))),patch.object(setup,'download_driver',side_effect=lambda *a:(order.append(('download',)) or path)),patch.object(setup,'verify_signature',side_effect=lambda p:order.append(('signature',p))),patch.object(setup,'run_installer',side_effect=lambda p,c:(order.append(('installer',p)) or 0)):
            self.helper=setup.MappingSetup(self.store);self.helper.install();self.wait()
            self.assertEqual([row[0] for row in order],['module','download','signature','installer'])
            self.assertEqual(order[0][2]['env']['VGAMEPAD_SKIP_VIGEMBUS_INSTALL'],'true')
            self.assertTrue(self.helper.state['ready'])
    def test_signature_failure_never_launches_installer_and_can_retry(self):
        with patch.object(setup,'inspect_components',return_value=state(True,False)),patch.object(setup,'download_driver',return_value=Path('driver.exe')),patch.object(setup,'verify_signature',side_effect=ValueError('bad signature')),patch.object(setup,'run_installer') as launch:
            self.helper=setup.MappingSetup(self.store);self.helper.install();self.wait();launch.assert_not_called()
            self.assertIn('bad signature',self.helper.state['message']);self.assertFalse(self.helper.state['ready'])
    def test_download_hash_rejects_tampered_executable(self):
        from io import BytesIO
        class Response(BytesIO):headers={'Content-Length':'7'}
        folder=Path(self.folder.name)/'download'
        with patch('urllib.request.urlopen',return_value=Response(b'tampered')):
            with self.assertRaises(ValueError):setup.download_driver(folder,threading.Event(),lambda m:None)
        self.assertEqual(list(folder.iterdir()),[])
    def test_valid_cached_driver_is_reused_without_network(self):
        folder=Path(self.folder.name);target=folder/'ViGEmBus_1.22.0.exe';target.write_bytes(b'verified fixture')
        with patch.object(setup,'DRIVER_SHA256',hashlib.sha256(target.read_bytes()).hexdigest()),patch('urllib.request.urlopen') as network:
            self.assertEqual(setup.download_driver(folder,threading.Event(),lambda m:None),target);network.assert_not_called()
    def test_uac_cancel_is_visible_without_claiming_success(self):
        with patch.object(setup,'inspect_components',return_value=state(True,False)),patch.object(setup,'download_driver',return_value=Path('driver.exe')),patch.object(setup,'verify_signature'),patch.object(setup,'run_installer',side_effect=InterruptedError('cancelled by user')):
            self.helper=setup.MappingSetup(self.store);self.helper.install();self.wait()
            self.assertFalse(self.helper.state['ready']);self.assertIn('cancelled',self.helper.state['message'])

if __name__=='__main__':unittest.main(verbosity=2)
