"""Cover shine/tilt responds to input once and becomes idle or honors reduced motion."""
from pathlib import Path
import sys,tempfile,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler,Qt
from PySide6.QtGui import QImage,QColor,QPainter,QLinearGradient,QFont
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    deadline=time.monotonic()+ms/1000
    while time.monotonic()<deadline:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'cover-motion');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=True,accent_color='#80c942')
    cover=store.root/'covers/fixture.png';cover.parent.mkdir()
    image=QImage(480,680,QImage.Format_RGB32);paint=QPainter(image)
    gradient=QLinearGradient(0,0,480,680);gradient.setColorAt(0,QColor('#174c76'));gradient.setColorAt(1,QColor('#122034'));paint.fillRect(image.rect(),gradient)
    paint.setPen(QColor('#90c7e0'));paint.drawRect(20,20,439,639);paint.setPen(QColor('#80c942'));paint.drawEllipse(75,155,330,330)
    paint.setPen(QColor('white'));paint.setFont(QFont('Segoe UI',26,QFont.Bold));paint.drawText(48,110,'GAME CLOUD');paint.drawText(138,345,'SAVE');paint.end();image.save(str(cover))
    for index in range(8):
        ident=str(index);store.games.append({'id':ident,'name':f'Cover motion {index}','category':'视觉小说','tags':['悬疑'],'cover':str(cover)})
        store.local[ident]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.setWidth(1440);root.requestActivate();spin(200)
    invoke(root,'navigate','all','');spin(300);grid=root.findChild(QObject,'gameGrid');grid.forceActiveFocus()
    backend.setControllerMode(True);spin(80)
    effects=[item for item in walk(root.contentItem()) if item.objectName()=='coverEffects' and item.isVisible()]
    assert any(item.property('hot') for item in effects),(root.isActive(),root.activeFocusItem().objectName(),grid.property('currentIndex'),[(item.property('available'),item.property('controllerFocused'),item.property('suspended')) for item in effects],messages)
    effect=next(item for item in effects if item.property('hot'))
    assert sum(bool(item.property('hot')) for item in effects)==1
    shine=effect.findChild(QObject,'coverShine');assert shine.isVisible() and effect.property('yaw')!=0
    output=ROOT/'test-data/cover-motion';output.mkdir(exist_ok=True);root.grabWindow().save(str(output/'controller-shine.png'))
    spin(1800);assert not shine.isVisible(),'Shine must finish, not loop on selection'
    frames=[];root.frameSwapped.connect(lambda:frames.append(time.monotonic()));spin(300)
    assert len(frames)<=6,('Selected cover continues rendering while idle',len(frames))
    idle_frames=len(frames)
    # Mouse position controls the tilt; it never changes library selection or launches a game.
    backend.setControllerMode(False);point=effect.mapToScene(QPointF(effect.width()*.82,effect.height()*.22))
    QTest.mouseMove(root,QPoint(round(point.x()),round(point.y())));spin(100)
    assert effect.property('hot') and effect.property('yaw')>0 and effect.property('pitch')>0
    spin(450);root.grabWindow().save(str(output/'mouse-tilt.png'))
    store.settings['animations']=False;backend.settingsChanged.emit();spin(100)
    assert not effect.property('hot') and effect.property('yaw')==0 and effect.property('pitch')==0 and not shine.isVisible()
    store.settings['animations']=True;backend.settingsChanged.emit();spin(50)
    # Directly suspending the effect models the scrolling guard without synthesizing a flick.
    effect.setProperty('suspended',True);spin();assert not effect.property('hot') and not shine.isVisible()
    # The star keeps its own click; the rest of the cover opens the same three-tab settings.
    card=effect.parentItem().parentItem();clicked=[]
    card.settingsRequested.connect(lambda:clicked.append('settings'))
    card.favoriteRequested.connect(lambda:clicked.append('favorite'))
    favorite=next(item for item in effect.parentItem().childItems() if item.property('iconName')=='star')
    point=favorite.mapToScene(QPointF(favorite.width()/2,favorite.height()/2))
    QTest.mouseClick(root,Qt.LeftButton,pos=QPoint(round(point.x()),round(point.y())));spin(300)
    assert clicked==['favorite'] and not root.findChild(QObject,'gameDialog').property('visible'),clicked
    point=effect.mapToScene(QPointF(effect.width()/2,effect.height()/2))
    QTest.mouseClick(root,Qt.LeftButton,pos=QPoint(round(point.x()),round(point.y())));spin(250)
    assert clicked==['favorite','settings'] and root.findChild(QObject,'gameDialog').property('visible'),clicked
    assert root.findChild(QObject,'gameSettingsTabs').property('count')==3
    report={'one_shot_shine':True,'mouse_tilt':True,'reduced_motion':True,'scroll_guard':True,'cover_settings_click':True,'favorite_click_isolated':True,'idle_frames_in_300ms':idle_frames}
    (output/'report.json').write_text(json.dumps(report),encoding='utf-8')
    assert not any(term in message for message in messages for term in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign')),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: one-shot shine, pointer tilt, no idle rendering, reduced motion and scroll guard')
