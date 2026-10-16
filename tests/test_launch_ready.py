import sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from launch_ready import wait,Probe
class Clock:
    def __init__(self):self.time=0;self.cancelled=False
    def is_set(self):return self.cancelled
    def wait(self,seconds):self.time+=seconds
class Readiness(unittest.TestCase):
    def test_visible_window_must_remain_stable_before_handoff(self):
        clock=Clock();probe=MagicMock();probe.matches.return_value=True
        result=wait(probe,clock,sample=lambda:[{'hwnd':7,'pid':33,'size':(1280,720)}],clock=lambda:clock.time)
        self.assertEqual(result['phase'],'ready');self.assertGreaterEqual(clock.time,.7)
    def test_process_alone_or_foreign_window_is_not_ready(self):
        clock=Clock();probe=MagicMock();probe.matches.return_value=False
        result=wait(probe,clock,timeout=1,sample=lambda:[{'hwnd':7,'pid':33,'size':(1280,720)}],clock=lambda:clock.time)
        self.assertEqual(result['phase'],'timeout')
    def test_disappearing_or_resizing_window_restarts_stability(self):
        clock=Clock();probe=MagicMock();probe.matches.return_value=True
        result=wait(probe,clock,sample=lambda:[] if clock.time<.5 else [{'hwnd':7,'pid':33,'size':(640,480) if clock.time<1 else (1280,720)}],clock=lambda:clock.time)
        self.assertEqual(result['phase'],'ready');self.assertGreaterEqual(clock.time,1.7)
        clock.cancelled=True;self.assertEqual(wait(probe,clock)['phase'],'cancelled')
    def test_match_exact_path_install_root_or_child_never_platform_client(self):
        probe=Probe({'exe':r'D:\Games\Title\game.exe','install_dir':r'D:\Games\Title'},100)
        process=MagicMock();process.name.return_value='shipping.exe';process.exe.return_value=r'D:\Games\Title\Binaries\shipping.exe';process.parents.return_value=[]
        with patch('psutil.Process',return_value=process):self.assertTrue(probe.matches(555))
        probe.cache.clear();process.exe.return_value=r'D:\Games\TitleOther\other.exe'
        with patch('psutil.Process',return_value=process):self.assertFalse(probe.matches(555))
        process.name.return_value='steam.exe'
        with patch('psutil.Process',return_value=process):self.assertFalse(probe.matches(100))
if __name__=='__main__':unittest.main()
