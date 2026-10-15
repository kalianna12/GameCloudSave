"""Exit detection survives busy UI; automatic snapshots are bounded, manual ones retained."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import sys,tempfile,time,unittest,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from game_watcher import ProcessSampler,Sessions,ExitQueue
from main import Bridge
from PySide6.QtCore import QCoreApplication
app=QCoreApplication.instance() or QCoreApplication([])

class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data');self.store=Store(self.temp.name,'watch-v241')
        self.save=Path(self.temp.name)/'save';self.save.mkdir();(self.save/'progress.dat').write_bytes(b'progress')
        self.exe=Path(self.temp.name)/'ExampleGame.exe';self.exe.write_bytes(b'fixture')
        self.store.games=[{'id':'a','name':'Example Game','cover':''}]
        self.store.save_game('a',{'save_dir':str(self.save),'exe':str(self.exe)})
        self.bridge=None
    def tearDown(self):
        if self.bridge:
            self.bridge.shutdownWatch();self.bridge._watch_pool.shutdown(wait=True);self.bridge.pool.shutdown(wait=True)
            app.processEvents()
        self.temp.cleanup()
    def bridge_for_test(self):
        self.store.settings.update(watch=False,watch_upload=True)
        self.bridge=Bridge(self.store);self.store.settings['watch']=True;self.bridge._sessions.delay=0
        return self.bridge
    def idle(self):
        end=time.monotonic()+5
        while time.monotonic()<end:
            app.processEvents();time.sleep(.005)
            if not self.bridge._auto_active and not self.bridge._watch_pending and not self.bridge.busy:
                app.processEvents()
                if not self.bridge._auto_active:return
        self.fail('Watcher worker did not finish')
    def exit_game(self):
        self.bridge.receiveWatch({'a':True});self.bridge.receiveWatch({'a':False});self.bridge.receiveWatch({'a':False});self.idle()
    def test_only_end_uploads_once_and_no_busy_lock(self):
        bridge=self.bridge_for_test()
        with patch.object(self.store,'upload') as upload:
            bridge.receiveWatch({'a':True});self.assertEqual(self.store.history('a'),[])
            self.exit_game();self.assertEqual(upload.call_count,1)
            bridge.receiveWatch({'a':False});self.idle();self.assertEqual(upload.call_count,1)
        self.assertEqual([row['event'] for row in self.store.history('a')],['game_stop'])
        self.assertEqual(self.store.games[0]['play_count'],1)
        self.assertFalse(bridge.busy)
    def test_busy_task_does_not_lose_exit(self):
        bridge=self.bridge_for_test();bridge._busy=True
        with patch.object(self.store,'upload') as upload:
            bridge.receiveWatch({'a':True});bridge.receiveWatch({'a':False});bridge.receiveWatch({'a':False})
            self.assertEqual(bridge.watchInfo['queued'],1);self.assertFalse(upload.called)
            bridge._busy=False;bridge.drainAutoBackups();self.idle();self.assertEqual(upload.call_count,1)
    def test_upload_failure_retains_one_archive_and_retry_reuses_it(self):
        bridge=self.bridge_for_test();notices=[];bridge.notificationReady.connect(lambda *args:notices.append(args))
        with patch.object(self.store,'upload',side_effect=ValueError('Offline')) as upload:
            self.exit_game();self.assertEqual(upload.call_count,1)
            for _ in range(4):bridge.receiveWatch({'a':False});self.idle()
            self.assertEqual(upload.call_count,1)
        self.assertEqual(bridge.watchInfo['failed'],1);self.assertTrue(notices[-1][2])
        archive=self.store.history('a')[0]['archive_path']
        with patch.object(self.store,'upload') as upload:
            bridge.retryAutoBackups();self.idle();self.assertEqual(str(upload.call_args.args[1]),archive)
        self.assertEqual(len(self.store.history('a')),1);self.assertEqual(bridge.watchInfo['failed'],0)
    def test_queue_survives_restart(self):
        bridge=self.bridge_for_test();queue=bridge._exit_queue
        queue.add({'ident':'a','token':'persistent'},False)
        restored=ExitQueue(queue.path);self.assertEqual(restored.next()['token'],'persistent')
        with patch.object(self.store,'upload') as upload:
            bridge.receiveWatch({'a':False});self.idle();self.assertEqual(upload.call_count,1)
    def test_session_key_reuses_snapshot_even_after_queue_interruption(self):
        first=self.store.backup('a','game_stop',session_key='same-session')
        second=self.store.backup('a','game_stop',session_key='same-session')
        self.assertEqual(first,second);self.assertEqual(len(self.store.history('a')),1)
    def test_local_default_five_manual_unlimited_cloud_not_deleted(self):
        for _ in range(7):self.store.backup('a')
        with patch.object(self.store,'rclone') as cloud:
            for _ in range(8):self.store.backup('a','game_stop')
        rows=self.store.history('a');self.assertEqual(sum(r['event']=='manual' for r in rows),7)
        self.assertEqual(sum(r['event']=='game_stop' for r in rows),5);self.assertFalse(cloud.called)
        self.assertTrue(all(Path(row['archive_path']).is_file() for row in rows))
        self.store.save_settings({'auto_snapshot_keep':2});self.store.backup('a','game_stop')
        self.assertEqual(sum(row['event']=='game_stop' for row in self.store.history('a')),2)
        self.assertEqual(sum(row['event']=='manual' for row in self.store.history('a')),7)
    def test_retention_validation(self):
        for value in (0,-1,101,True,'5'):
            with self.assertRaises(ValueError):self.store.save_settings({'auto_snapshot_keep':value})
    def test_retention_drops_only_pruned_upload_retries(self):
        bridge=self.bridge_for_test()
        with patch.object(self.store,'upload',side_effect=ValueError('Offline')):
            for _ in range(6):self.exit_game()
        self.assertEqual(len(self.store.history('a')),5);self.assertEqual(bridge.watchInfo['failed'],5)
        with patch.object(self.store,'upload') as upload:
            bridge.retryAutoBackups();self.idle();self.assertEqual(upload.call_count,5)
        self.assertEqual(bridge.watchInfo['failed'],0);self.assertEqual(len(self.store.history('a')),5)
    def test_debounce_and_unknown_status_do_not_end_running_game(self):
        sessions=Sessions(delay=3)
        self.assertEqual(sessions.update({'a':True},0)[0],['a'])
        sessions.update({'a':False},1);self.assertFalse(sessions.update({'a':None},5)[1])
        sessions.update({'a':True},6);sessions.update({'a':False},7)
        self.assertFalse(sessions.update({'a':False},9)[1]);self.assertEqual(len(sessions.update({'a':False},10)[1]),1)
    def test_no_compress_or_upload_while_another_game_is_running(self):
        bridge=self.bridge_for_test()
        bridge.receiveWatch({'a':True,'b':True});bridge.receiveWatch({'a':False,'b':True});bridge.receiveWatch({'a':False,'b':True})
        self.assertEqual(bridge.watchInfo['queued'],1);self.assertEqual(self.store.history('a'),[])
        bridge.receiveWatch({'a':False,'b':False});bridge.receiveWatch({'a':False,'b':False})
        self.idle() # b is not configured; its failure must not discard a's snapshot.
        self.assertEqual(len(self.store.history('a')),1)
    def test_sampler_only_reads_matching_process_paths_and_caches_them(self):
        sampler=ProcessSampler();targets=sampler.targets(self.store.games,self.store.local)
        unrelated=SimpleNamespace(info={'pid':1,'name':'Other.exe'},exe=Mock(side_effect=AssertionError('Unrelated path queried')))
        matching=SimpleNamespace(info={'pid':2,'name':self.exe.name},exe=Mock(return_value=str(self.exe)),create_time=Mock(return_value=3))
        with patch('psutil.process_iter',return_value=[unrelated,matching]) as processes:
            self.assertTrue(sampler.sample(targets)['a']);self.assertTrue(sampler.sample(targets)['a'])
        processes.assert_called_with(['pid','name']);self.assertEqual(matching.exe.call_count,1);self.assertFalse(unrelated.exe.called)
    def test_platform_only_import_discovers_shipping_exe_once(self):
        folder=Path(self.temp.name)/'Game/Binaries/Win64';folder.mkdir(parents=True)
        (folder/'Example-Win64-Shipping.exe').write_bytes(b'fixture')
        local={'a':{'save_dir':str(self.save),'install_dir':str(Path(self.temp.name)/'Game')}}
        sampler=ProcessSampler();targets=sampler.targets(self.store.games,local)
        self.assertIn('example-win64-shipping.exe',targets['a']['names'])
        with patch.object(Path,'glob',side_effect=AssertionError('Configuration rediscovered every tick')):
            sampler.targets(self.store.games,local)

if __name__=='__main__':unittest.main(verbosity=2)
