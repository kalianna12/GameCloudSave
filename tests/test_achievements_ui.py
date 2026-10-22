"""Isolated actual QML/controller and live-file/normal/Anime4K overlay verification.

--gpu additionally installs the cached official engine into the disposable fixture.
Never opens or writes an actual game, library or source-preview directory.
"""
from pathlib import Path
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, Q_RETURN_ARG, QPointF, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
from services import ROOT, Store
from main import Bridge
from launch_ready import Probe, windows, activate, foreground
from graphics_enhancement import Engine, SCALING_CLASS

QQuickStyle.setStyle('Material'); app=QApplication([]); app.setQuitOnLastWindowClosed(False)
messages=[]; qInstallMessageHandler(lambda k,c,m:messages.append(m))
user=ctypes.windll.user32
user.GetWindow.argtypes=[W.HWND,W.UINT];user.GetWindow.restype=W.HWND
user.FindWindowW.argtypes=[W.LPCWSTR,W.LPCWSTR];user.FindWindowW.restype=W.HWND
user.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
user.SetWindowDisplayAffinity.argtypes=[W.HWND,W.DWORD]
user.GetWindowDisplayAffinity.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]

def spin(seconds=.1):
    until=time.monotonic()+seconds
    while time.monotonic()<until: app.processEvents();time.sleep(.005)

def until(condition, timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if condition():return
        spin(.025)
    assert condition(),('Timed out',messages[-10:])

def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))

def focus(hwnd,pid):
    activate(hwnd,pid)
    if foreground()[0]==hwnd:return
    # Only the isolated test's windows may be brought forward by this helper.
    current=ctypes.windll.kernel32.GetCurrentThreadId();other=user.GetWindowThreadProcessId(foreground()[0],None)
    attached=bool(user.AttachThreadInput(current,other,True))
    try:activate(hwnd,pid)
    finally:
        if attached:user.AttachThreadInput(current,other,False)


def main():
    output=ROOT/'build/achievement-review';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='achievements-ui-') as temp:
        root=Path(temp);store=Store(root/'data','isolated')
        store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0)
        schema=[{'name':f'ACH_{n}', 'displayName':f'冒险纪念 {n:02}', 'description':'完成一次探索，发现新的风景', 'hidden':n==2} for n in range(80)]
        schema_path=root/'game/steam_settings/achievements.json';schema_path.parent.mkdir(parents=True);schema_path.write_text(json.dumps(schema,ensure_ascii=False),encoding='utf-8')
        source=root/'game/profile/achievements.json';source.parent.mkdir();states={'ACH_0':{'earned':True,'earned_time':1700000000},'ACH_1':{'earned':False}}
        def write():source.write_text(json.dumps(states),encoding='utf-8')
        write();original_schema=hashlib.sha256(schema_path.read_bytes()).hexdigest()
        store.games=[{'id':'local-fixture','name':'本地成就测试','platform':'local','cover':'','tags':[],'category':'其他'}, {'id':'platform-fixture','name':'平台测试','platform':'steam','cover':'','tags':[],'category':'其他'}]
        store.local={'local-fixture':{'installed':True,'install_dir':str(root/'game')}}
        backend=Bridge(store);qml=QQmlApplicationEngine();qml.rootContext().setContextProperty('backend',backend)
        child=None;core=None
        try:
            qml.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert qml.rootObjects(),messages
            window=qml.rootObjects()[0];window.resize(1440,900);window.show();spin(.4)
            dialog=window.findChild(QObject,'gameDialog');invoke(dialog,'openFor','local-fixture',4)
            manager=backend.achievements
            until(lambda:not manager.state['busy'] and manager.state.get('total')==80)
            assert manager.state['unlocked']==1 and not manager.overlay.queue
            assert manager.state['source']==str(source)
            assert next(r for r in manager.state['rows'] if r['id']=='ACH_2')['name']=='隐藏成就'
            pane=window.findChild(QObject,'achievementsPane');preview=pane.findChild(QObject,'achievementPreview')
            for size in ((1440,900),(900,650)):
                window.resize(*size);spin(.15);window.grabWindow().save(str(output/f'page-{size[0]}.png'))
                listview=pane.findChild(QObject,'achievementList');assert listview.height()>45,(size,listview.height())
            window.resize(1440,900);spin(.1)
            preview.forceActiveFocus();invoke(dialog,'controllerInput','down');spin()
            listview=pane.findChild(QObject,'achievementList');assert listview.hasActiveFocus()
            for _ in range(75):invoke(dialog,'controllerInput','down')
            assert listview.property('currentIndex')==75;assert listview.property('contentY')>1000
            invoke(dialog,'controllerInput','menu');until(lambda:not manager.state['busy'])
            assert json.loads((store.profile/'achievements/config.json').read_text(encoding='utf-8'))['local-fixture']['enabled']
            with patch('cover_sources.search',return_value=[{'appid':'42','name':'Explicit version'}]):
                manager.search('local-fixture','fixture');until(lambda:not manager.state['busy'])
            assert manager.state['candidates'][0]['appid']=='42'
            pane.findChild(QObject,'achievementSetup').setProperty('checked',True)
            manager._state['sources']=[str(source),str(source.parent/'other-account/achievements.json')];manager.changed.emit()
            window.resize(900,650);spin(.15)
            pane.findChild(QObject,'achievementEnabled').forceActiveFocus()
            for _ in range(22):
                invoke(dialog,'controllerInput','down');spin(.02)
                focused=window.activeFocusItem()
                if focused and focused.objectName() in ('achievementSearch','achievementAppId','achievementSource','achievementSourceChoice','achievementPreview','achievementList'):
                    position=focused.mapToItem(pane,QPointF())
                    assert position.y()>=-1 and position.y()+focused.height()<=pane.height()+1,(focused.objectName(),position.y(),focused.height(),pane.height())
            window.grabWindow().save(str(output/'expanded-900.png'))
            window.resize(1440,900);spin(.1)
            # Old asynchronous result cannot replace a different selected game's page.
            manager.openFor('platform-fixture');assert not manager.state['rows']
            manager.openFor('local-fixture');until(lambda:not manager.state['busy'])
            invoke(dialog,'controllerInput','back');spin(.1)
            fixture=root/'fixture.py';fixture.write_text('''from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtGui import QPainter,QColor
from PySide6.QtCore import QTimer
app=QApplication([])
class Window(QWidget):
 def __init__(self):
  super().__init__();self.n=0;self.resize(800,450);self.setWindowTitle('Achievement GPU fixture - no game data')
 def paintEvent(self,event):
  p=QPainter(self);p.fillRect(self.rect(),QColor('#172c42'));p.setPen(QColor('#aaddff'));p.drawText(25,40,'ACHIEVEMENT TEST - DISPOSABLE WINDOW');p.setBrush(QColor('#80c942'));p.drawEllipse(50+self.n%550,350,40,40)
 def step(self):self.n+=2;self.update()
w=Window();w.show();t=QTimer();t.timeout.connect(w.step);t.start(33);QTimer.singleShot(180000,app.quit);app.exec()
''',encoding='utf-8')
            child=subprocess.Popen([sys.executable,str(fixture)],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
            probe=Probe({},child.pid)
            target={}
            def ready():
                nonlocal target
                target=next((r for r in windows() if probe.matches(r['pid'])),{})
                return bool(target)
            until(ready);focus(target['hwnd'],target['pid']);spin(.2)
            manager.begin('local-fixture');manager.attach('local-fixture',target['pid'],target['hwnd']);spin(.25)
            states['ACH_1']={'earned':True,'earned_time':time.time()};write()
            until(lambda:manager.overlay.toast is not None and manager.overlay.toast.isVisible())
            toast=manager.overlay.toast;assert foreground()[1]==target['pid'],'Toast stole foreground'
            assert manager.state['unlocked']==2
            toast.grab().save(str(output/'normal-toast.png'))
            flags=user.GetWindowLongW(int(toast.winId()),-20)
            assert flags&0x08000000 and flags&0x20,hex(flags) # NOACTIVATE + TRANSPARENT
            affinity=W.DWORD();assert user.GetWindowDisplayAffinity(int(toast.winId()),ctypes.byref(affinity)) and affinity.value==0x11
            focus(int(window.winId()),os.getpid());spin(.25);assert not toast.isVisible(),'Toast leaked over another application'
            focus(target['hwnd'],target['pid']);until(lambda:toast.isVisible());assert foreground()[1]==target['pid']
            manager.overlay.current=None;manager.overlay.queue.clear();toast.hide();manager.overlay.timer.stop()
            states['ACH_1']['earned']=False;write();manager.poll();spin(1.2)
            states['ACH_1']['earned']=True;write();manager.poll();spin(1.2)
            assert not manager.overlay.queue and manager.overlay.current is None,'Relock replayed'
            report={'ordinary_popup':True,'no_focus_steal':True,'alt_tab_hides':True,'capture_excluded':True,'relock_replay':False,'qml_rows':80}
            if '--gpu' in sys.argv:
                core=Engine(root/'gpu');core.install(threading.Event(),lambda _:None,ROOT/'build/Magpie-v0.13.0-x64.zip')
                focus(target['hwnd'],target['pid']);core.start({'preset':'anime-fast'},target['hwnd'],target['pid'],'Achievements fixture',threading.Event())
                def active():
                    if core.poll()=='active':return True
                    focus(target['hwnd'],target['pid']);return False
                until(active,20);spin(.25)
                states['ACH_2']={'earned':True,'earned_time':time.time()};write()
                until(lambda:toast.isVisible());assert foreground()[1]==target['pid']
                scaler=user.FindWindowW(SCALING_CLASS,None);assert scaler
                previous=user.GetWindow(scaler,3);above=False
                while previous:
                    if int(previous)==int(toast.winId()):above=True;break
                    previous=user.GetWindow(previous,3)
                assert above,'Toast is below Anime4K surface'
                # Temporarily include overlay in a test screenshot, then restore
                # production capture exclusion. Does not change game input/rendering.
                user.SetWindowDisplayAffinity(int(toast.winId()),0);spin(.1)
                frame=app.primaryScreen().grabWindow(0).toImage();frame.save(str(output/'anime4k-popup.png'))
                rect=W.RECT();user.GetWindowRect(int(toast.winId()),ctypes.byref(rect))
                color=frame.pixelColor(rect.left+110,rect.top+8)
                assert abs(color.red()-36)<8 and abs(color.blue()-45)<8,('Toast not composited',color.name())
                user.SetWindowDisplayAffinity(int(toast.winId()),0x11)
                assert core.poll()=='active';report['anime4k_popup_above_scaler']=True
                core.stop()
            assert original_schema==hashlib.sha256(schema_path.read_bytes()).hexdigest()
            assert not [m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))],messages[-25:]
            (output/('report-gpu.json' if '--gpu' in sys.argv else 'report.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
            print('PASS',json.dumps(report))
        finally:
            if core:core.stop()
            backend.shutdownWatch();backend.achievements.pool.shutdown(wait=True);backend.achievements.network.shutdown(wait=True);backend.achievements.icons.shutdown(wait=True);backend.pool.shutdown(wait=True)
            if child:
                import psutil
                try:descendants=psutil.Process(child.pid).children(recursive=True)
                except psutil.Error:descendants=[]
                for process in reversed(descendants):
                    try:process.terminate();process.wait(timeout=3)
                    except psutil.Error:pass
                if child.poll() is None:child.terminate();child.wait(timeout=5)
            shiboken6.delete(qml)

if __name__=='__main__':main()
