"""Isolated navigation round trips, native-editable search, saves and GPU presets."""
from pathlib import Path
import sys,tempfile,time,threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QPointF,Slot,qInstallMessageHandler
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=60):
    until=time.perf_counter()+ms/1000
    while time.perf_counter()<until:app.processEvents();time.sleep(.003)
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))
def variant(value):return value.toVariant() if hasattr(value,'toVariant') else value
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
class SafeBridge(Bridge):
    actions=[]
    @Slot(str)
    def history(self,ident):
        self._history_ident=ident;self._history=[{'id':n,'created_at':'2026-10-20T00:00:00Z','note':'Fixture','uploaded':False} for n in range(1,7)];self.changed.emit()
    @Slot(str)
    def refreshCloudHistory(self,ident):self.actions.append(('cloud-history',ident));self._cloud_history=[{'remote':'fixture.zip','created_at':'2026-10-20T00:00:00Z'}];self.changed.emit()
    @Slot(str)
    def localSave(self,ident):self.actions.append(('local',ident))
    @Slot(str)
    def cloudSave(self,ident):self.actions.append(('upload',ident))
    @Slot(str,int,'QVariantMap')
    def restoreWithOptions(self,ident,snapshot,options):self.actions.append(('restore',ident,snapshot,options))

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='controller-flow-') as temp:
    store=Store(temp,'workflow');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,cloud_folder='fixture',animations=True)
    store.games=[{'id':str(i),'name':f'Game {i:03}','cover':'','tags':[],'category':f'Group {i//10:02}','last_played':''} for i in range(160)]
    store.games[0]['name']='沙耶之歌';store.local={str(i):{'installed':True,'save_dir':temp} for i in range(160)}
    backend=SafeBridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    gate=threading.Event()
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];root.resize(1440,900);root.requestActivate();spin(350)
        home=root.findChild(QObject,'libraryHome');view=root.findChild(QObject,'libraryHomeList');search=root.findChild(QObject,'search');grid=root.findChild(QObject,'gameGrid')
        def pad(command,ms=50):dispatch(app,root,backend,command);spin(ms)
        def shelf():return invoke(home,'currentShelf')
        def selected():return variant(invoke(home,'selectedGame'))
        invoke(home,'focusFirst');backend.setControllerMode(True)
        for _ in range(7):pad('down',50)
        spin(200);section=home.property('focusedSection');assert section>=6
        for _ in range(14):pad('left',15)
        assert root.activeFocusItem().objectName()=='navHome'
        before=(home.property('focusedSection'),selected()['id'],view.property('contentY'))
        pad('right',180)
        assert (home.property('focusedSection'),selected()['id'])==before[:2]
        assert abs(view.property('contentY')-before[2])<2
        pad('search');assert root.activeFocusItem().objectName()=='search'
        pad('right');pad('down');pad('search',150)
        assert home.hasActiveFocus() and (home.property('focusedSection'),selected()['id'])==before[:2]
        pad('left');assert root.activeFocusItem().objectName()=='navHome'
        pad('search');pad('search');assert root.activeFocusItem().objectName()=='navHome'
        pad('right',150)
        for _ in range(14):pad('right',25)
        spin(180)
        row=shelf();assert row,(home.property('focusedSection'),view.property('contentY'),[(i.objectName(),i.property('active'),i.y(),i.property('item') is not None) for i in walk(root.contentItem()) if i.objectName().startswith('section-loader-')],messages[-15:])
        horizontal=next(item for item in walk(root.contentItem()) if item.objectName()=='shelf-'+variant(row.property('section'))['id'])
        spin(150)
        assert horizontal.property('contentX')>=horizontal.property('originX')-.5
        assert horizontal.property('contentX')<=horizontal.property('originX')+max(0,horizontal.property('contentWidth')-horizontal.width())+.5
        ident=selected()['id'];index=invoke(home,'selectionIndex');position=horizontal.property('contentX')-horizontal.property('originX')
        # A slow serial disk queue must not turn favourite into a global busy operation.
        backend.pool.submit(lambda:gate.wait(3));start=time.perf_counter()
        if '--profile' in sys.argv:
            import cProfile,pstats
            profile=cProfile.Profile();profile.enable();backend.toggleFavorite(ident);profile.disable();pstats.Stats(profile).sort_stats('cumulative').print_stats(22)
        else:backend.toggleFavorite(ident)
        elapsed=time.perf_counter()-start;print('Favourite GUI dispatch ms',round(elapsed*1000,2),flush=True)
        assert not backend.busy and backend.libraryGame(ident)['favorite'];assert '--profile' in sys.argv or elapsed<.25
        spin(150);assert selected()['id']==ident and invoke(home,'selectionIndex')==index
        assert abs(horizontal.property('contentX')-horizontal.property('originX')-position)<2
        gate.set();spin(150)
        for _ in range(8):pad('left',45)
        spin(120)
        row=shelf();y=row.mapToScene(QPointF()).y();assert y>=home.mapToScene(QPointF()).y()-2
        assert y+row.height()<=home.mapToScene(QPointF(0,home.height())).y()+2,(y,row.height(),home.mapToScene(QPointF(0,home.height())).y(),view.property('contentY'),view.property('originY'),home.property('focusedSection'))
        invoke(home,'scrollBy',100000);spin(160)
        assert view.property('contentY')<=view.property('originY')+max(0,view.property('contentHeight')-view.height())+1
        invoke(home,'resumeFocus');spin(150)
        # Both initial letters and complete pinyin find Chinese names.
        for query in ('syzg','shayezhige','沙耶'):
            search.setProperty('text',query);spin(200);assert grid.property('count')==1,(query,grid.property('count'))
        search.setProperty('text','');spin(180);search.forceActiveFocus()
        preedit=QInputMethodEvent('sha',[]);app.sendEvent(search,preedit);spin(30)
        assert search.property('inputMethodComposing') and search.property('text')==''
        commit=QInputMethodEvent();commit.setCommitString('沙耶');app.sendEvent(search,commit);spin(200)
        assert grid.property('count')==1 and root.property('searchQuery')=='沙耶'
        keyboard=root.findChild(QObject,'controllerKeyboard');invoke(keyboard,'start','');spin(100)
        pad('activate');assert keyboard.property('value')=='1';pad('favorite');assert keyboard.property('value')==''
        pad('history');assert keyboard.property('value')==' '
        # Every key is a visible cell in the provided 11-column reference layout.
        keys={item.objectName():item for item in walk(keyboard.property('contentItem'))}
        delete=keys['keyboardKey-40'];done=keys['keyboardKey-41'];cancel=keys['keyboardKey-42'];space=keys['keyboardKey-44']
        assert abs(delete.x()-done.x())<1 and abs(done.x()-cancel.x())<1 and space.width()>5*delete.width()
        invoke(keyboard,'selectKey',29);pad('right');assert keyboard.property('selectedKey')==41
        pad('left');assert keyboard.property('selectedKey')==29
        invoke(keyboard,'selectKey',40);pad('right');assert keyboard.property('selectedKey')==40
        pad('case');assert keyboard.property('upper');pad('zoom-out');assert keyboard.property('upper');pad('case');assert not keyboard.property('upper')
        for size in [(900,650),(1440,900)]:
            root.resize(*size);spin(150)
            top=keyboard.property('y');height=keyboard.property('height')
            assert top>=0 and top+height<=root.height()+1,(size,top,height)
            assert all(key.width()>25 and key.height()>25 for name,key in keys.items() if name.startswith('keyboardKey-'))
        invoke(keyboard,'selectKey',0)
        output=ROOT/'build/controller-workflow';output.mkdir(exist_ok=True);root.grabWindow().save(str(output/'keyboard.png'))
        if '--native-ime' in sys.argv:
            import ctypes as C
            from ctypes import wintypes as W
            from launch_ready import foreground
            user=C.windll.user32;user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)];user.GetWindowThreadProcessId.restype=W.DWORD;user.SetForegroundWindow.argtypes=[W.HWND]
            own=C.windll.kernel32.GetCurrentThreadId();other=user.GetWindowThreadProcessId(foreground()[0],None)
            attached=bool(user.AttachThreadInput(own,other,True))
            try:user.SetForegroundWindow(int(root.winId()))
            finally:
                if attached:user.AttachThreadInput(own,other,False)
            root.requestActivate();spin(120)
            keyboard.setProperty('value','');invoke(keyboard,'toggleChinese');spin(120)
            assert keyboard.property('chinese'),keyboard.property('inputNotice')
            for char in 'nihao':assert backend.searchIme.key(char);spin(70)
            editor=keyboard.findChild(QObject,'keyboardValue')
            assert keyboard.property('composing'),(editor.property('text'),editor.property('preeditText'))
            assert backend.searchIme.key('space');spin(180)
            committed=keyboard.property('value');assert any('\u4e00'<=c<='\u9fff' for c in committed),committed
            root.grabWindow().save(str(output/'native-ime.png'));print('Native Windows IME committed:',committed,flush=True)
            keyboard.setProperty('value','')
            for char in 'nihao':assert backend.searchIme.key(char);spin(60)
            pad('menu',180)
            assert not keyboard.property('visible') and '你' in root.property('searchQuery'),root.property('searchQuery')
            invoke(keyboard,'start','');spin(100)
        pad('back');assert not keyboard.property('visible')
        search.setProperty('text','');spin(200);invoke(home,'resumeFocus');spin(150)
        ident=selected()['id'];pad('history');history=root.findChild(QObject,'historyDialog');assert history.property('visible')
        pad('activate');assert backend.actions[-1]==('local',ident)
        pad('right');pad('activate');assert backend.actions[-1]==('upload',ident)
        pad('down');pad('down');assert history.property('controllerZone')=='records',(history.property('controllerZone'),root.findChild(QObject,'historyList').property('count'),root.findChild(QObject,'historyTabs').property('currentIndex'),messages[-12:])
        def preview(game,snapshot,record):
            backend._restore_preview={'ident':game,'snapshot':snapshot,'target':temp,'file_count':2,'slots':[]};backend.restorePreviewChanged.emit()
        with patch.object(backend,'previewRestore',side_effect=preview):pad('activate')
        restore=root.findChild(QObject,'restoreDialog');assert restore.property('visible')
        pad('down');pad('right')
        assert root.activeFocusItem().objectName()=='confirmRestore',(root.activeFocusItem().objectName(),restore.property('preview'),messages[-10:])
        pad('activate')
        assert backend.actions[-1][0:2]==('restore',ident),(backend.actions[-1],backend.active_popup().objectName(),restore.findChild(QObject,'confirmRestore').property('enabled'),variant(restore.property('preview')),messages[-10:])
        assert history.property('visible') and not restore.property('visible')
        with patch.object(backend,'previewRestore',side_effect=preview):pad('activate')
        pad('back');assert history.property('visible') and not restore.property('visible')
        pad('next');assert root.findChild(QObject,'historyTabs').property('currentIndex')==1
        pad('activate')
        with patch.object(backend,'previewRestore',side_effect=preview) as cloud_preview:pad('activate')
        assert cloud_preview.call_args.args[2]['remote']=='fixture.zip'
        pad('back');pad('previous')
        root.grabWindow().save(str(output/'history.png'));pad('back');spin(150)
        dialog=root.findChild(QObject,'gameDialog');invoke(dialog,'openFor',ident,3);spin(100)
        pane=root.findChild(QObject,'graphicsSettingsPane');invoke(pane,'controllerInput','down')
        invoke(pane,'controllerInput','right');invoke(pane,'controllerInput','right');invoke(pane,'controllerInput','down');invoke(pane,'controllerInput','activate')
        invoke(dialog,'controllerInput','menu');spin(180)
        assert store.local[ident]['graphics']['preset']=='fsr' and store.local[ident]['graphics']['game_3d']
        assert '×' in pane.findChild(QObject,'graphicsOutputResolution').property('text')
        root.grabWindow().save(str(output/'graphics.png'));invoke(dialog,'controllerInput','back')
        # A loading/error shelf cannot trap focus, including when a populated
        # recommendation row becomes empty during a refresh.
        record=backend.libraryGame(ident)
        rows=[{'id':'test-a','kind':'games','title':'A','items':[record]},{'id':'test-empty','kind':'store','title':'Loading','items':[]},{'id':'test-b','kind':'games','title':'B','items':[record]}]
        home.setProperty('sections',rows);spin(120);invoke(home,'focusFirst');pad('down',120)
        assert home.property('focusedSection')==2
        rows[2]['items']=[];home.setProperty('sections',rows);spin(120)
        assert home.property('focusedSection')==0
        errors=[m for m in messages if any(v in m for v in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))]
        assert not errors,errors[:15]
        print('PASS: sidebar/View round trips, bounded shelves, instant favourite, initials/pinyin/IME composition, reference keyboard, Y backup/restore preview, controller GPU presets')
    finally:
        gate.set();backend.shutdownWatch();backend.graphics.pool.shutdown(wait=True);backend.pool.shutdown(wait=True);shiboken6.delete(engine)
