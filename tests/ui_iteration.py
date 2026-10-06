"""V1.1 render, continuous zoom, navigation and scroll checks."""
import json
from pathlib import Path
import statistics
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,QPoint,qInstallMessageHandler
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QSignalSpy
import shiboken6
from main import Bridge
from services import Store,ROOT

messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
app=QApplication([]); QQuickStyle.setStyle('Material')
store=Store(); store.prepare_thumbnails()
bridge=Bridge(store); bridge.timer.stop()
engine=QQmlApplicationEngine(); engine.rootContext().setContextProperty('backend',bridge)
engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
assert engine.rootObjects(),messages
window=engine.rootObjects()[0]
QCursor.setPos(window.position()+QPoint(20,20))
def settle(seconds=.25):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents(); time.sleep(.002)
def wait_job():
    deadline=time.monotonic()+55
    while bridge.busy and time.monotonic()<deadline: settle(.03)
    assert not bridge.busy,'Job did not finish'
def capture(target,name):
    settle(.1)
    assert target.grabWindow().save(str(ROOT/'test-data'/name))
def all_items(item):
    yield item
    if hasattr(item,'childItems'):
        for child in item.childItems(): yield from all_items(child)
settle(2)
grid=window.findChild(QObject,'gameGrid')
slider=window.findChild(QObject,'coverSlider')
spy=QSignalSpy(bridge.gamesChanged)
window.setProperty('columnCount',6)
slider.setProperty('value',251)
assert QMetaObject.invokeMethod(slider,'moved')
settle()
assert window.property('columnCount')==0
assert abs(grid.property('cardWidth')-251)<.01
slider.setProperty('value',252)
QMetaObject.invokeMethod(slider,'moved'); settle()
assert abs(grid.property('cardWidth')-252)<.01
assert spy.count()==0
images=[i for i in all_items(window.contentItem()) if i.objectName()=='coverImage']
assert images and all(i.property('sourceSize').width()>=251*window.devicePixelRatio() for i in images)
buttons=[i for i in all_items(window.contentItem()) if i.objectName().startswith('action-')]
assert buttons
assert all(abs(button.x()+button.width()/2-button.parentItem().width()/2)<.6 for button in buttons)
window.setProperty('coverSize',210)
window.setProperty('gridGap',22)
window.setProperty('columnCount',0)
settle()
capture(window,'library-v11.png')
ident=bridge.games[0]['id']
for state in ('uploading','success','failed'):
    bridge.setTransfer(ident,state); settle(.4)
    capture(window,'upload-'+state+'.png')
bridge.setTransfer(ident,'idle')
frames=[]
window.frameSwapped.connect(lambda:frames.append(time.monotonic()))
for velocity in (-2500.0,2500.0,-2500.0,2500.0):
    assert QMetaObject.invokeMethod(grid,'flick',Q_ARG('qreal',0.0),Q_ARG('qreal',velocity))
    settle(1.2)
intervals=[(b-a)*1000 for a,b in zip(frames,frames[1:]) if 0<(b-a)<.15]
metrics={'rendered_frames':len(frames),'median_ms':round(statistics.median(intervals),2) if intervals else 0,
         'p95_ms':round(sorted(intervals)[int(len(intervals)*.95)],2) if intervals else 0,
         'game_model_resets':spy.count()}
assert grid.property('count')==51 and spy.count()==0
assert intervals and metrics['p95_ms']<100
grid.setProperty('contentY',0); settle()
window.setProperty('width',900); window.setProperty('height',680); settle()
capture(window,'library-v11-small.png')
window.setProperty('width',1440); window.setProperty('height',940)
assert QMetaObject.invokeMethod(window,'openCloud')
cloud=window.findChild(QObject,'cloudWindow')
settle(); wait_job(); settle()
assert cloud.isVisible()
capture(cloud,'dav-v11.png')

fixture=ROOT/'test-data/ui-preview.json'
fixture.write_text(json.dumps({'说明':'云端预览测试','进度':42},ensure_ascii=False),encoding='utf-8')
folder='电脑/GameCloudSave/_ui-preview-'+str(uuid.uuid4())
remote='gamecloud:'+folder+'/preview.json'
uploaded=False
try:
    store.rclone(['copyto',str(fixture),remote]); uploaded=True
    bridge.browseCloud(folder,{}); wait_job(); settle()
    entry=next(row for row in bridge.directories if row['Name']=='preview.json')
    bridge.previewCloud(folder,entry,{}); wait_job(); settle()
    assert '进度' in bridge.cloudPreview['text']
    capture(cloud,'dav-preview-v11.png')
finally:
    if uploaded:
        store.rclone(['deletefile',remote]); store.rclone(['rmdir','gamecloud:'+folder])
cloud.close()
matched=next(row for row in bridge.matchResults if row['name']=='ELDEN RING')
assert QMetaObject.invokeMethod(window,'openMatch',Q_ARG('QVariant',matched['id']))
matcher=window.findChild(QObject,'matchWindow')
settle()
assert matcher.isVisible()
capture(matcher,'ai-results-v11.png')
original=dict(matched)
bridge.receiveMatch({**matched,'status':'failed','message':'模拟失败状态：请求超时，保留本地扫描候选'})
settle(); capture(matcher,'ai-failed-v11.png')
bridge.receiveMatch(original)
matcher.close()
bridge.flushLayout(); bridge.pool.shutdown(wait=True)
shiboken6.delete(engine)
assert not messages,'\n'.join(messages)
(ROOT/'test-data/scroll-metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
print('PASS: pixel zoom, centered icons, stable model, 4 native flicks, transfer states, DAV content preview, real AI results and failure view; zero QML warnings')
print(json.dumps(metrics))
