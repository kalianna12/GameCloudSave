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
    assert root.grabWindow().pixelColor(320,180).red()>100,'Old image cleared before the next one loaded'
    spin(240);assert backdrop.property('ready') and root.grabWindow().pixelColor(320,180).blue()>100
    backdrop.setProperty('source',urls[0]);spin(240);assert backdrop.property('ready')
    assert root.grabWindow().pixelColor(320,180).red()>100,'Cached return selected the wrong buffer'
    for i in range(8):backdrop.setProperty('source',urls[i%2]);spin(12)
    spin(240);assert backdrop.property('ready') and root.grabWindow().pixelColor(320,180).blue()>100
    frames=[];root.frameSwapped.connect(lambda:frames.append(1));spin(250);assert len(frames)<=5,len(frames)
    assert not any('ReferenceError' in m or 'TypeError' in m for m in messages),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: local banners, old buffer retained, correct cached return, rapid-switch coalescing and idle rendering')
