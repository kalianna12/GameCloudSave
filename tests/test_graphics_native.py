"""Opt-in native GPU smoke: official engine and a disposable animated test window.

Run with --run. Never launches a library game or accesses source-preview data.
"""
from pathlib import Path
import json,sys,tempfile,time,threading,subprocess,ctypes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from graphics_enhancement import Engine,SCALING_CLASS
from launch_ready import windows,activate,Probe,foreground
from services import ROOT


def main():
    if '--run' not in sys.argv: print('Native GPU test skipped; pass --run');return
    archive=ROOT/'build/Magpie-v0.13.0-x64.zip'
    assert archive.is_file(),'Cache the pinned official ZIP first'
    from PySide6.QtWidgets import QApplication
    app=QApplication([])
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.processEvents();time.sleep(.02)
    def focus_fixture(target):
        activate(target['hwnd'],target['pid'])
        if foreground()[0]==target['hwnd']:return
        # Automated hosts have no foreground window. Temporarily attach only for
        # this opt-in test; production never steals foreground from another app.
        user=ctypes.windll.user32;current=ctypes.windll.kernel32.GetCurrentThreadId()
        other=user.GetWindowThreadProcessId(foreground()[0],None)
        attached=bool(user.AttachThreadInput(current,other,True))
        try:activate(target['hwnd'],target['pid'])
        finally:
            if attached:user.AttachThreadInput(current,other,False)
    with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='graphics-native-') as temp:
        root=Path(temp);engine=Engine(root);engine.install(threading.Event(),lambda _:None,archive)
        fixture=root/'fixture.py'
        fixture.write_text('''from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtGui import QPainter,QColor,QFont
from PySide6.QtCore import QTimer
app=QApplication([])
class Window(QWidget):
 def __init__(self):
  super().__init__();self.n=0;self.resize(800,450);self.setWindowTitle("GameCloudSave GPU scaling fixture")
 def paintEvent(self,event):
  p=QPainter(self);p.fillRect(self.rect(),QColor("#172c42"));p.setPen(QColor("#aaddff"));p.setFont(QFont("Arial",20))
  p.drawText(32,55,"GPU SCALING FIXTURE - NO GAME DATA")
  for x in range(30,760,24):p.drawLine(x,90,x+130,340)
  p.setBrush(QColor("#80c942"));p.drawEllipse(50+self.n%550,350,40,40)
 def step(self):self.n+=2;self.update()
w=Window();w.show();t=QTimer();t.timeout.connect(w.step);t.start(33)
QTimer.singleShot(180000,app.quit);app.exec()
''',encoding='utf-8')
        report=[];output=ROOT/'build/graphics-review';output.mkdir(exist_ok=True)
        fixture_log=(output/'fixture-native.log').open('wb')
        child=subprocess.Popen([sys.executable,str(fixture)],cwd=root,stdout=fixture_log,stderr=fixture_log,creationflags=subprocess.CREATE_NO_WINDOW)
        import psutil
        probe=Probe({},child.pid)
        def terminate_fixture():
            try: descendants=psutil.Process(child.pid).children(recursive=True)
            except psutil.Error:descendants=[]
            for process in reversed(descendants):
                try:process.terminate();process.wait(timeout=3)
                except psutil.Error:pass
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)
        try:
            until=time.monotonic()+8;target=None
            while time.monotonic()<until:
                target=next((w for w in windows() if probe.matches(w['pid'])),None)
                if target:break
                spin(.1)
            assert target,('Fixture window did not appear',child.poll(),(output/'fixture-native.log').read_text(encoding='utf-8',errors='replace'))
            for preset,display in [('anime-fast','fullscreen'),('anime-quality','fullscreen'),('fsr','fullscreen'),('lanczos','fullscreen'),('nearest','fullscreen'),('anime-fast','windowed')]:
                focus_fixture(target)
                print('fixture focus',target,foreground(),flush=True)
                begin=time.monotonic();engine.start({'enabled':True,'preset':preset,'display':display},target['hwnd'],target['pid'],'GPU Fixture',threading.Event())
                until=time.monotonic()+18;phase=''
                while time.monotonic()<until:
                    phase=engine.poll()
                    if phase in ('active','exited'):break
                    focus_fixture(target)
                    spin(.1)
                spin(.25)
                record={'preset':preset,'display':display,'phase':phase,'startup_s':round(time.monotonic()-begin,2),'foreground':foreground()};report.append(record)
                app.primaryScreen().grabWindow(0).save(str(output/('native-'+preset+'-'+display+'.png')))
                log=engine.directory/'logs/magpie.log'
                if log.is_file():(output/'magpie-native.log').write_bytes(log.read_bytes())
                assert phase=='active',record
                engine.stop();assert engine.process is None
                spin(.25)
            # Owned engine stops as soon as the target process ends.
            focus_fixture(target);engine.start({'preset':'fsr'},target['hwnd'],target['pid'],'Exit Fixture',threading.Event())
            terminate_fixture();spin(.2)
            assert engine.poll()=='game-exited' and engine.process is None
            (output/'native-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report));print('PASS: real GPU scaling, six shader/display cases, owned stop and game-exit cleanup')
        finally:
            log=engine.directory/'logs/magpie.log'
            config=engine.directory/'config/config.json'
            if config.is_file():(output/'native-config.json').write_bytes(config.read_bytes())
            engine.stop()
            if log.is_file():(output/'magpie-native.log').write_bytes(log.read_bytes())
            terminate_fixture()
            fixture_log.close()

if __name__=='__main__':main()
