"""Decode a tiny generated local clip, then release it on focus loss and launch."""
from pathlib import Path
import struct,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QByteArray,QBuffer,QIODevice,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtMultimedia import QMediaPlayer
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def chunk(tag,data):return tag+struct.pack('<I',len(data))+data+(b'\0' if len(data)%2 else b'')
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    # Uncompressed headers + MJPEG frames avoid a new encoder dependency.
    image=QImage(160,90,QImage.Format_RGB32);image.fill(QColor('#345689'));buffer=QByteArray();device=QBuffer(buffer);device.open(QIODevice.WriteOnly);image.save(device,'JPEG');jpeg=bytes(buffer)
    n=40;avih=struct.pack('<14I',100000,len(jpeg)*10,0,0,n,0,1,len(jpeg),160,90,0,0,0,0)
    strh=struct.pack('<4s4sIHH8I4h',b'vids',b'MJPG',0,0,0,0,1,10,0,n,len(jpeg),0xffffffff,0,0,0,160,90)
    strf=struct.pack('<IiiHH4sIiiII',40,160,90,1,24,b'MJPG',160*90*3,0,0,0,0)
    header=chunk(b'LIST',b'hdrl'+chunk(b'avih',avih)+chunk(b'LIST',b'strl'+chunk(b'strh',strh)+chunk(b'strf',strf)))
    clip=Path(directory)/'clip.avi';clip.write_bytes(chunk(b'RIFF',b'AVI '+header+chunk(b'LIST',b'movi'+chunk(b'00dc',jpeg)*n)))
    store=Store(Path(directory)/'data','video');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library_design='cinema',library='')
    store.games=[{'id':'a','name':'Local video fixture','cover':''}]
    backend=Bridge(store);backend._media_loaded=True;backend._media_source=('','');backend._library_media={'a':{'videoUrl':QUrl.fromLocalFile(str(clip)).toString()}}
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(180)
    cinema=next(item for item in walk(root.contentItem()) if item.objectName()=='cinemaExperience')
    assert not cinema.property('playing') and not root.findChild(QObject,'cinemaPlayer')
    cinema.setProperty('playing',True);spin(800)
    player=root.findChild(QObject,'cinemaPlayer');assert player and player.property('playbackState')==QMediaPlayer.PlayingState,messages
    output=root.findChild(QObject,'cinemaOutput');assert output.property('videoSink').videoFrame().isValid(),messages
    assert cinema.property('muted') is True
    root.hide();spin(100)
    assert not cinema.property('playing') and not cinema.findChild(QObject,'cinemaVideoLoader').property('active'),messages
    if shiboken6.isValid(player):assert player.property('playbackState')==QMediaPlayer.StoppedState and not player.property('source').toString()
    root.show();root.requestActivate();spin(100);cinema.setProperty('playing',True);spin(250)
    assert cinema.findChild(QObject,'cinemaVideoLoader').property('active')
    cinema.setProperty('launching',True);spin(80);assert not cinema.property('playing') and not cinema.findChild(QObject,'cinemaVideoLoader').property('active')
    assert not cinema.property('videoFailed'),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: actual local video frame decoded, muted default, no autoplay, decoder stopped/released on focus loss and launch')
