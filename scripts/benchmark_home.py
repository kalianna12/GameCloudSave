"""Read-only artwork, isolated 520-game stress library and timed scrolling."""
from pathlib import Path
import sys,os,time,tempfile,shutil,json,statistics,argparse
parser=argparse.ArgumentParser();parser.add_argument('--4k',action='store_true');args=parser.parse_args()
if args.__dict__['4k']:os.environ['QT_SCALE_FACTOR']='1.3333333333'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl,QMetaObject,Q_ARG,QObject
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([])
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    source=Store();store=Store(temporary,'home-benchmark');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,theme=source.settings['theme'])
    for directory in ('covers','backgrounds'):
        if (source.root/directory).exists():shutil.copytree(source.root/directory,store.root/directory)
    for index in range(10):
        for game in source.games:
            ident=str(index)+'-'+game['id'];store.games.append({**game,'id':ident});store.local[ident]={'installed':True}
    started=time.perf_counter();backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects()
    root=engine.rootObjects()[0]
    if args.__dict__['4k']:root.showFullScreen()
    app.processEvents();startup=time.perf_counter()-started;QTest.qWait(700)
    home=root.findChild(QObject,'libraryHome');view=root.findChild(QObject,'libraryHomeList');times=[];root.frameSwapped.connect(lambda:times.append(time.perf_counter()))
    for index in range(160):
        QMetaObject.invokeMethod(home,'scrollBy',Q_ARG('QVariant',88 if (index//60)%2==0 else -88));QTest.qWait(16)
    intervals=[1000*(b-a) for a,b in zip(times,times[1:])]
    assert intervals
    report={'games':len(store.games),'sections':len(backend.librarySections),'qml_startup_seconds':round(startup,3),'frames':len(times),'median_frame_ms':round(statistics.median(intervals),2),'p95_frame_ms':round(sorted(intervals)[int(.95*(len(intervals)-1))],2)}
    view.setProperty('contentY',0);QTest.qWait(160);image=root.grabWindow();report['render_pixels']=[image.width(),image.height()]
    output=ROOT/'test-data/v23-benchmark';output.mkdir(exist_ok=True);image.save(str(output/('home-4k.png' if args.__dict__['4k'] else 'home.png')))
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
