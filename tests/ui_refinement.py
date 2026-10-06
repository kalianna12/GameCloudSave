"""Exercise desktop/4K layouts, cache reuse, search and scrolling without network I/O."""
from pathlib import Path
import json
import statistics
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,QPoint,Qt,qInstallMessageHandler
from PySide6.QtGui import QImage,QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QSignalSpy
import shiboken6
from main import Bridge
from services import Store,ROOT

messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
app=QApplication([]);QQuickStyle.setStyle('Material')
# HD cache retains source detail, never upscales, and performs no decode/write on cache hits.
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    fixture=Store(Path(temporary),'thumbnail-test')
    covers=fixture.root/'covers';covers.mkdir()
    for ident,size in [('large',(1800,2500)),('small',(200,280))]:
        image=QImage(*size,QImage.Format_RGB32);image.fill('#556677');image.save(str(covers/(ident+'.png')))
        fixture.games.append({'id':ident,'name':ident,'cover':str(covers/(ident+'.png'))})
    fixture.prepare_thumbnails()
    assert QImage(str(fixture.root/'thumbnails'/fixture.high_thumbnails['large'])).width()==1080
    assert QImage(str(fixture.root/'thumbnails'/fixture.high_thumbnails['small'])).width()==200
    stamps={p:p.stat().st_mtime_ns for p in fixture.root.glob('thumbnail*-index.json')}
    with patch('PySide6.QtGui.QImageReader',side_effect=AssertionError('Cache hit decoded again')):
        fixture.prepare_thumbnails()
    assert all(p.stat().st_mtime_ns==stamp for p,stamp in stamps.items())
store=Store();start=time.perf_counter();store.prepare_thumbnails();cache_ms=(time.perf_counter()-start)*1000
bridge=Bridge(store);bridge.timer.stop()
engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',bridge)
engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
assert engine.rootObjects(),messages
window=engine.rootObjects()[0];QCursor.setPos(0,0)
def settle(seconds=.25):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:app.processEvents();time.sleep(.002)
def items(item):
    yield item
    for child in item.childItems():yield from items(child)
settle(1)
grid=window.findChild(QObject,'gameGrid');search=window.findChild(QObject,'search')
spy=QSignalSpy(bridge.gamesChanged)
window.setProperty('columnCount',0);window.setProperty('coverSize',210)
settle()
assert grid.property('count')==len(bridge.games)
search.setProperty('text','Celeste');settle()
assert grid.property('count')==1
search.setProperty('text','没有这个游戏');settle()
assert grid.property('count')==0
search.setProperty('text','');settle()
window.setProperty('width',900);window.setProperty('height',680);settle()
window.grabWindow().save(str(ROOT/'test-data/library-v13-small.png'))
window.setProperty('width',1440);window.setProperty('height',940);settle()
window.grabWindow().save(str(ROOT/'test-data/library-v13.png'))
ratio=window.devicePixelRatio()
original_flags=window.flags()
window.setFlags(original_flags | Qt.FramelessWindowHint);window.show()
window.setProperty('width',round(3840/ratio));window.setProperty('height',round(2160/ratio))
window.setProperty('coverSize',360);settle(1)
image=window.grabWindow();assert abs(image.width()-3840)<=2 and abs(image.height()-2160)<=2,(image.width(),image.height())
image.save(str(ROOT/'test-data/library-v13-4k.png'))
images=[item for item in items(window.contentItem()) if item.objectName()=='coverImage']
assert images and all(item.property('sourceSize').width()>=360*ratio for item in images)
frames=[]
window.frameSwapped.connect(lambda:frames.append(time.monotonic()))
for velocity in (-2500.,2500.,-2500.,2500.):
    assert QMetaObject.invokeMethod(grid,'flick',Q_ARG('qreal',0.),Q_ARG('qreal',velocity))
    settle(1)
intervals=[(b-a)*1000 for a,b in zip(frames,frames[1:]) if 0<b-a<.15]
assert intervals
assert spy.count()==0
metrics={'physical_resolution':[image.width(),image.height()],'device_pixel_ratio':ratio,'cached_thumbnail_prepare_ms':round(cache_ms,2),
         'scroll_frames':len(frames),'median_frame_ms':round(statistics.median(intervals),2),
         'p95_frame_ms':round(sorted(intervals)[int(len(intervals)*.95)],2),'game_model_resets':spy.count()}
assert metrics['p95_frame_ms']<100,metrics
window.hide();window.resize(1400,900)
window.setFlags(original_flags);window.show()
assert QMetaObject.invokeMethod(window,'openMatch',Q_ARG('QVariant',bridge.games[0]['id']))
matcher=window.findChild(QObject,'matchWindow');settle()
matcher.grabWindow().save(str(ROOT/'test-data/matching-v13.png'))
matcher.setProperty('currentResult',{'candidates':[{'path':r'C:\Users\kalianna\AppData\Roaming\EldenRing','confidence':0.9,'reason':'测试候选','fileSummary':'ER0000.sl2'}]})
expression=QQmlExpression(engine.rootContext(),matcher,'manualStartDirectory()')
assert expression.evaluate()[0]==r'C:\Users\kalianna\AppData\Roaming\EldenRing'
matcher.setProperty('visible',False)
# Load DAV form without calling openBrowser(), which would access the live server.
cloud=window.findChild(QObject,'cloudWindow');cloud.setProperty('visible',True);settle()
cloud.grabWindow().save(str(ROOT/'test-data/cloud-v13.png'));cloud.setProperty('visible',False)
assert QMetaObject.invokeMethod(window,'openSettings');settle()
window.grabWindow().save(str(ROOT/'test-data/settings-v13.png'))
bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
assert not messages,'\n'.join(messages)
(ROOT/'test-data/ui-v13-metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
print('PASS: thumbnail cache/no upscale, search, narrow/desktop/4K layouts, scrolling, manual picker, settings/DAV/matching; zero QML warnings')
print(json.dumps(metrics))
