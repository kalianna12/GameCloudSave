"""Actual source entry point exits with an active toast and a queued toast."""
from pathlib import Path
import os,subprocess,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if '--child' in sys.argv:
    from PySide6.QtCore import QTimer
    from achievements import Achievements
    import main as application
    managers=[];shown=[];original=Achievements.__init__
    def init(self,*args,**kwargs):
        original(self,*args,**kwargs);managers.append(self)
        def show():
            self.preview();self.overlay.tick();self.preview()
            shown.append(bool(self.overlay.toast and self.overlay.toast.isVisible() and self.overlay.queue))
        QTimer.singleShot(350,show)
    Achievements.__init__=init
    sys.argv=['source-exit-fixture','--quit-after','1000']
    assert application.main()==0
    assert shown==[True]
    assert managers[0].closed and managers[0].overlay.closed and managers[0].overlay.toast is None
    assert not managers[0].overlay.queue and managers[0].overlay.current is None
    print('PASS: real source entry Quit closes visible and queued achievement toasts')
else:
    from services import ROOT,Store
    with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievement-exit-') as temp:
        store=Store(temp)
        store.save_settings(dict(setup_completed=True,guide_dismissed=True,recommendations_enabled=False,navigation_volume=0,watch=False))
        env=dict(os.environ,GAMECLOUD_DATA=temp,PYTHONIOENCODING='utf-8')
        result=subprocess.run([sys.executable,__file__,'--child'],env=env,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
        print(result.stdout.strip())
