"""Image-filled, rapid vertical navigation; isolated data and muted audio."""
from pathlib import Path
import argparse,cProfile,json,statistics,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from gamepad import dispatch,Gamepad
from input_feedback import InputFeedback
from qml_bootstrap import install_incubator
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_RETURN_ARG,Q_ARG,Qt,Property,qInstallMessageHandler
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');parser.add_argument('--profile',action='store_true');args=parser.parse_args()
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.001)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def percentile(values,fraction):return round(sorted(values)[min(len(values)-1,int(len(values)*fraction))],2) if values else 0

class MeasuredBridge(Bridge):
    games_reads=0
    @Property('QVariantList',notify=Bridge.gamesChanged)
    def games(self):
        self.games_reads+=1
        return Bridge.games.fget(self)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'vertical-performance');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0)
    (store.root/'covers').mkdir(exist_ok=True)
    for i in range(12):
        image=QImage(800,1120,QImage.Format_RGB32);image.fill(QColor.fromHsv(i*29,145,160))
        painter=QPainter(image);painter.setPen(Qt.white);painter.drawText(100,150,f'ISOLATED COVER {i}');painter.end();image.save(str(store.root/'covers'/f'{i}.png'))
    store.games=[{'id':str(i),'name':f'Game {i:03}','cover':f'{i%12}.png','category':f'Category {i%12}','tags':['Adventure'],'last_played':str(900-i)} for i in range(480)]
    backend=MeasuredBridge(store);feedback=InputFeedback(app,backend,ROOT,audio_muted=True);backend.input_feedback=feedback
    engine=QQmlApplicationEngine();install_incubator(engine);engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];window.resize(1920,1080);window.requestActivate();spin(500)
    home=window.findChild(QObject,'libraryHome');view=window.findChild(QObject,'libraryHomeList')
    sections=[{'id':f'benchmark:{i}','kind':'games','title':f'Section {i}','items':backend.games[i*20:(i+1)*20]} for i in range(24)]
    home.setProperty('sections',sections);spin(200);backend.setControllerMode(True);invoke(home,'focusFirst');spin(200)
    # Keep Python off the render thread: a direct Python callback adds a GIL
    # rendezvous to every swap and can itself distort the navigation under test.
    frames=[];window.frameSwapped.connect(lambda:frames.append(time.perf_counter()),Qt.QueuedConnection)
    command_active=[False];writes=[]
    view.contentYChanged.connect(lambda:writes.append(view.property('contentY')) if command_active[0] else None)
    times=[];backend._popup_scans=0;start=time.perf_counter()
    profiler=cProfile.Profile() if args.profile else None
    try:
        if profiler:profiler.enable()
        # 20ms taps are substantially faster than 85ms held-repeat navigation.
        for direction in ['down']*18+['up']*18+['down']*12+['up']*12:
            command_active[0]=True;before=time.perf_counter();dispatch(app,window,backend,direction)
            times.append((time.perf_counter()-before)*1000);command_active[0]=False;spin(20)
        spin(250)
        if profiler:profiler.disable()
        gaps=[(b-a)*1000 for a,b in zip(frames,frames[1:])]
        report={'input_count':len(times),'dispatch_median_ms':round(statistics.median(times),2),'dispatch_p95_ms':percentile(times,.95),
                'renderer':str(window.rendererInterface().graphicsApi()),
                'frame_p95_ms':percentile(gaps,.95),'frame_max_ms':round(max(gaps,default=0),2),'frames_over_50ms':sum(g>50 for g in gaps),
                'frames':len(frames),'popup_tree_scans':backend._popup_scans,'synchronous_scroll_writes':len(writes),
                'elapsed_seconds':round(time.perf_counter()-start,2),'final_section':home.property('focusedSection')}
        out=ROOT/'build/vertical-navigation';out.mkdir(parents=True,exist_ok=True)
        if profiler:profiler.dump_stats(str(out/'navigation.pstats'))
        if not args.baseline:
            # Logical selection must work before offscreen rows/cards exist.
            for _ in range(18):dispatch(app,window,backend,'down')
            for _ in range(3):dispatch(app,window,backend,'right')
            chosen=invoke(home,'selectedGame')
            if hasattr(chosen,'toVariant'):chosen=chosen.toVariant()
            assert home.property('focusedSection')==18 and chosen['id']=='363',(home.property('focusedSection'),chosen)
            report['burst_selection_id']=chosen['id']
            invoke(home,'resetSelection');home.forceActiveFocus();spin(200)
            invoke(window,'navigate','all','');spin(250)
            grid=window.findChild(QObject,'gameGrid');grid.forceActiveFocus();spin(80)
            grid_writes=[];grid_times=[];frames.clear()
            grid.contentYChanged.connect(lambda:grid_writes.append(grid.property('contentY')) if command_active[0] else None)
            for direction in ['down']*24+['up']*24:
                command_active[0]=True;before=time.perf_counter();dispatch(app,window,backend,direction)
                grid_times.append((time.perf_counter()-before)*1000);command_active[0]=False;spin(20)
            spin(200)
            grid_gaps=[(b-a)*1000 for a,b in zip(frames,frames[1:])]
            report['grid']={'input_count':len(grid_times),'dispatch_p95_ms':percentile(grid_times,.95),
                'frame_p95_ms':percentile(grid_gaps,.95),'synchronous_scroll_writes':len(grid_writes),'final_index':grid.property('currentIndex')}
            assert not grid_writes,report
            assert grid.property('currentIndex')==0,report
            if not args.profile:assert percentile(grid_times,.95)<20,report
            sidebar_times=[];window.findChild(QObject,'navAll').forceActiveFocus()
            reads_before_sidebar=backend.games_reads
            sidebar_profile=cProfile.Profile() if args.profile else None
            if sidebar_profile:sidebar_profile.enable()
            for direction in ['down','up']*(2 if args.profile else 8):
                before=time.perf_counter();dispatch(app,window,backend,direction)
                sidebar_times.append((time.perf_counter()-before)*1000);spin(20)
            if sidebar_profile:
                sidebar_profile.disable();sidebar_profile.dump_stats(str(out/'sidebar.pstats'))
            report['sidebar_dispatch_p95_ms']=percentile(sidebar_times,.95)
            report['sidebar_game_property_reads']=backend.games_reads-reads_before_sidebar
            assert report['sidebar_game_property_reads']<=4,report
            report['sidebar_popup_tree_scans']=backend._popup_scans
            assert window.property('libraryMode')=='all' and grid.property('currentIndex')==0,report
            if not args.profile:assert percentile(sidebar_times,.95)<20,report
            # Run the production background sampler + queued dispatch, including
            # the actual 280ms initial hold and 85ms repeat logic, without hardware.
            invoke(window,'navigate','home','');spin(160);invoke(home,'focusFirst');spin(100)
            held=[0];held_commands=[]
            def query(index,state):
                if index:return 1167
                state._obj.pad.buttons=held[0];return 0
            driver=Gamepad(app,query=query)
            driver.command.connect(lambda command:(held_commands.append(command),dispatch(app,window,backend,command)))
            try:
                spin(35);held[0]=2;spin(1000);held[0]=0;spin(45)
                stopped=home.property('focusedSection');spin(180)
                assert home.property('focusedSection')==stopped,('Navigation continued after release',report)
                assert 6<=len(held_commands)<=14 and set(held_commands)=={'down'},held_commands
                report['held_repeat_commands']=len(held_commands)
                report['held_release_stable']=True
            finally:driver.shutdown()
            invoke(home,'resetSelection')
        (out/('before.json' if args.baseline else 'after.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        (out/'scenegraph.txt').write_text('\n'.join(m for m in messages if 'scenegraph' in m.lower() or 'render loop' in m.lower() or 'Graphics' in m),encoding='utf-8')
        print(json.dumps(report),flush=True)
        if not args.baseline:
            assert not writes,('Navigation must not jump the viewport while computing an animation target',report)
            if not args.profile:assert report['dispatch_p95_ms']<20,report
            assert report['popup_tree_scans']<=5,report
            assert home.property('focusedSection')==0,report
        assert not [m for m in messages if any(word in m for word in ('TypeError','ReferenceError','Binding loop','Cannot assign'))],messages[-10:]
    finally:
        feedback.audio.shutdown();feedback.release_cursor();app.removeEventFilter(feedback);backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
