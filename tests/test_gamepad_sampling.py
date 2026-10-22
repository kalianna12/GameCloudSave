"""Sampling is independent of GUI stalls; queues and held repeats stay bounded."""
from pathlib import Path
import sys,threading,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from gamepad_sampling import GamepadSampler

class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.clock=[10.];self.gate=threading.Event();self.wakes=[]
        def query(index,state):self.gate.wait(2);return 1167
        self.sampler=GamepadSampler(query,lambda:self.wakes.append(1),clock=lambda:self.clock[0])
        self.sampler.configure(True);self.epoch=self.sampler.epoch
    def tearDown(self):self.gate.set();self.sampler.close()
    def offer(self,command,repeat=False):self.sampler.publish(self.epoch,0,(0.,0.),[(self.clock[0],command,repeat)])
    def test_hold_repeat_has_one_wake_and_one_pending_repeat(self):
        self.offer('down')
        for _ in range(50):self.offer('down',True)
        self.assertEqual(len(self.wakes),1)
        self.assertEqual(self.sampler.take()[2],['down','down'])
    def test_fresh_taps_are_ordered_and_reversal_removes_obsolete_repeat(self):
        self.offer('down');self.offer('down',True);self.offer('up');self.offer('activate')
        self.assertEqual(self.sampler.take()[2],['down','up','activate'])
    def test_release_discards_queued_hold_repeat_but_preserves_a_real_tap(self):
        self.offer('down');self.offer('down',True)
        self.sampler.publish(self.epoch,0,(0.,0.),[],('',''))
        self.assertEqual(self.sampler.take()[2],['down'])
    def test_stale_input_and_disabled_epoch_cannot_reach_ui(self):
        self.offer('activate');self.clock[0]+=.2
        self.assertEqual(self.sampler.take()[2],[])
        self.sampler.configure(False);self.offer('activate')
        self.assertEqual(self.sampler.take()[2],[])
    def test_excess_input_is_bounded_and_latest_tilt_wins(self):
        for i in range(100):self.offer('activate');self.sampler.publish(self.epoch,0,(i/100,0.),[])
        slot,tilt,commands,ready=self.sampler.take()
        self.assertEqual(len(commands),32);self.assertEqual(tilt,(.99,0.))
    def test_queued_wake_without_a_new_sample_cannot_look_like_a_disconnect(self):
        self.offer('down');self.sampler.configure(True)
        self.assertFalse(self.sampler.take()[3])
        self.offer('activate')  # Old sampling epoch must remain ignored.
        self.assertEqual(self.sampler.take()[2],[])

class SamplingTests(unittest.TestCase):
    def test_virtual_exclusion_changes_wake_sampling_and_reprime_held_buttons(self):
        def query(index,state):
            state._obj.pad.buttons=0x1000
            return 0 if index in (0,1) else 1167
        sampler=GamepadSampler(query,lambda:None)
        try:
            sampler.configure(True,0);time.sleep(.025)
            first=sampler.take();self.assertTrue(first[3]);self.assertEqual(first[0],1);self.assertEqual(first[2],[])
            sampler.configure(True,1);time.sleep(.025)
            second=sampler.take();self.assertTrue(second[3]);self.assertEqual(second[0],0);self.assertEqual(second[2],[])
        finally:sampler.close()
    def test_native_queries_run_on_worker_and_short_presses_survive_gui_idle(self):
        lock=threading.Lock();buttons=[0x1000];threads=[];wakes=[]
        def query(index,state):
            threads.append(threading.get_ident())
            if index:return 1167
            with lock:state._obj.pad.buttons=buttons[0]
            return 0
        sampler=GamepadSampler(query,lambda:wakes.append(1))
        try:
            sampler.configure(True)
            time.sleep(.025)
            self.assertEqual(sampler.take()[2],[],'Held A must be primed on connection')
            with lock:buttons[0]=0
            time.sleep(.025)
            with lock:buttons[0]=0x1000
            time.sleep(.03)
            with lock:buttons[0]=0
            time.sleep(.025)
            self.assertEqual(sampler.take()[2],['activate'])
            self.assertTrue(threads);self.assertNotIn(threading.get_ident(),threads)
            self.assertTrue(sampler.thread.is_alive())
            sampler.configure(False);count=len(threads);time.sleep(.025)
            self.assertLessEqual(len(threads),count+1)
        finally:sampler.close()
        self.assertFalse(sampler.thread.is_alive())

    def test_queued_delivery_is_on_gui_thread_and_gui_pause_does_not_stop_sampling(self):
        from PySide6.QtWidgets import QApplication,QWidget
        from gamepad import Gamepad
        app=QApplication.instance() or QApplication([])
        window=QWidget();window.resize(320,160);window.show();window.activateWindow()
        def spin(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:app.processEvents();time.sleep(.002)
        spin(.06)
        held=[0];queries=[];delivered=[];enabled=[True]
        def query(index,state):
            queries.append(threading.get_ident())
            if index:return 1167
            state._obj.pad.buttons=held[0]
            return 0
        driver=Gamepad(app,lambda:enabled[0],query=query)
        driver.command.connect(lambda command:delivered.append((command,threading.get_ident())))
        try:
            spin(.05);held[0]=2
            time.sleep(.4)  # Simulate a busy GUI, while the sampling thread runs.
            before=len(queries);self.assertGreater(before,20)
            spin(.025)
            self.assertLessEqual(len(delivered),1,'Held navigation must not catch up after a GUI stall')
            held[0]=0;spin(.025);delivered.clear()
            held[0]=0x1000;spin(.03);held[0]=0;spin(.03)
            self.assertEqual([command for command,thread in delivered],['activate'])
            self.assertTrue(all(thread==threading.get_ident() for command,thread in delivered))
            self.assertNotIn(threading.get_ident(),queries)
            enabled[0]=False;driver.sync();count=len(queries);spin(.03)
            self.assertLessEqual(len(queries),count+1)
            delivered.clear();held[0]=0x1000;enabled[0]=True;driver.sync();spin(.03)
            self.assertFalse(delivered,'Held A on foreground/configuration resume must not activate')
        finally:driver.shutdown();window.close()

if __name__=='__main__':unittest.main(verbosity=2)
