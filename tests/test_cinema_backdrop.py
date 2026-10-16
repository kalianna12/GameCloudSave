"""A cached return never toggles back to the old buffer or flashes empty."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'backdrop');store.settings['watch']=False;backend=Bridge(store)
    urls=[]
    for name,color in [('red','#cc3020'),('blue','#2040cc')]:
        file=Path(directory)/(name+'.jpg');image=QImage(1280,720,QImage.Format_RGB32);image.fill(QColor(color));image.save(str(file));urls.append(QUrl.fromLocalFile(str(file)))
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.loadData(b'import QtQuick\nimport QtQuick.Window\nWindow { visible: true; width: 640; height: 360; color: "black"; CinemaBackdrop { objectName: "testBackdrop"; anchors.fill: parent } }',QUrl.fromLocalFile(str(ROOT/'ui/BackdropTest.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();backdrop=root.findChild(QObject,'testBackdrop')
    backdrop.setProperty('source',urls[0]);spin(260);assert backdrop.property('ready'),messages
    red=root.grabWindow().pixelColor(320,180);assert red.red()>red.blue()
    backdrop.setProperty('source',urls[1]);spin(8)
    assert backdrop.property('hasFrame') and not backdrop.property('failed'),'Pending banner must retain its previous frame'
    assert root.grabWindow().pixelColor(320,180).red()>100,'Old image cleared before the next one loaded'
    spin(240);assert backdrop.property('ready') and root.grabWindow().pixelColor(320,180).blue()>100
    backdrop.setProperty('source',urls[0]);spin(240);assert backdrop.property('ready')
    assert root.grabWindow().pixelColor(320,180).red()>100,'Cached return selected the wrong buffer'
    for i in range(8):backdrop.setProperty('source',urls[i%2]);spin(12)
    spin(240);assert backdrop.property('ready') and root.grabWindow().pixelColor(320,180).blue()>100
    frames=[];root.frameSwapped.connect(lambda:frames.append(1));spin(250);assert len(frames)<=5,len(frames)
    shiboken6.delete(engine)
    # Exercise the actual cinema fallback, not just the two image buffers.
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.loadData(b'import QtQuick\nimport QtQuick.Window\nWindow { visible: true; width: 900; height: 600; CinemaView { objectName: "testCinema"; anchors.fill: parent } }',QUrl.fromLocalFile(str(ROOT/'ui/CinemaTest.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];cinema=root.findChild(QObject,'testCinema');poster=cinema.findChild(QObject,'cinemaFallbackPoster');backdrop=cinema.findChild(QObject,'cinemaBackdrop')
    def select(ident,banner):cinema.setProperty('game',{'id':ident,'name':'Fixture','coverUrl':urls[0].toString(),'backgroundUrl':banner})
    select('red',urls[0].toString());assert not poster.isVisible(),'Poster flashed during initial banner request'
    spin(260);assert backdrop.property('ready') and not poster.isVisible()
    select('blue',urls[1].toString())
    assert backdrop.property('hasFrame') and not poster.isVisible(),'Poster flashed between banner selections'
    spin(8);assert not poster.isVisible()
    spin(260);assert backdrop.property('ready') and not poster.isVisible()
    select('none','');spin(60);assert poster.isVisible() and not backdrop.property('hasFrame')
    select('bad',QUrl.fromLocalFile(str(Path(directory)/'missing.jpg')).toString());assert not poster.isVisible()
    spin(260);assert backdrop.property('failed') and poster.isVisible(),'A genuinely failed banner should fall back to the poster'
    assert not any('ReferenceError' in m or 'TypeError' in m for m in messages),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: old banner retained, cached return, rapid switching, idle rendering, no portrait flash, real missing/error fallback')
