"""Check actual foreground bounds against each button, including sidebar icons."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QUrl,QPointF
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from main import Bridge
from services import Store,ROOT
import shiboken6
app=QApplication([]);QQuickStyle.setStyle('Material')
bridge=Bridge(Store());bridge.timer.stop()
engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',bridge)
engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
window=engine.rootObjects()[0];QCursor.setPos(0,0)
end=time.monotonic()+2
while time.monotonic()<end: app.processEvents();time.sleep(.005)
image=window.grabWindow();ratio=image.width()/window.width()
def walk(item):
    yield item
    for child in item.childItems(): yield from walk(child)
checked=[]
for item in walk(window.contentItem()):
    if item.metaObject().indexOfProperty('iconName')<0:continue
    if item.metaObject().indexOfProperty('selected')>=0:continue
    point=item.mapToScene(QPointF(item.width()/2,item.height()/2));cx=point.x()*ratio;cy=point.y()*ratio
    if cy>image.height()-100 or cy<0:continue
    bg=item.property('background').property('color')
    if bg.alpha()==0:
        bg=image.pixelColor(round(cx-12*ratio),round(cy-12*ratio))
    pixels=[]
    for y in range(round(cy-11*ratio),round(cy+11*ratio)):
        for x in range(round(cx-11*ratio),round(cx+11*ratio)):
            if not 0<=x<image.width() or not 0<=y<image.height():continue
            color=image.pixelColor(x,y)
            if sum(abs(a-b) for a,b in zip(color.getRgb()[:3],bg.getRgb()[:3]))>95:pixels.append((x,y))
    if not pixels:continue
    actualx=(min(p[0] for p in pixels)+max(p[0] for p in pixels)+1)/2
    actualy=(min(p[1] for p in pixels)+max(p[1] for p in pixels)+1)/2
    assert abs(actualx-cx)<=1.5 and abs(actualy-cy)<=1.5,(item.property('iconName'),actualx-cx,actualy-cy)
    checked.append(item.property('iconName'))
assert len(checked)>=12,checked
image.save(str(ROOT/'test-data/icons-v12.png'))
from PySide6.QtCore import QObject
window.findChild(QObject,'search').setProperty('text','Celeste')
end=time.monotonic()+.5
while time.monotonic()<end:app.processEvents();time.sleep(.005)
window.grabWindow().save(str(ROOT/'test-data/celeste-icons-v12.png'))
bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: actual rendered icon foreground is centered; checked',len(checked),'buttons; DPR',ratio)
