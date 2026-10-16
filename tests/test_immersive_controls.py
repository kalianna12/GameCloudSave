"""Real Qt mouse/controller input, native window returns and bounded theme motion."""
from pathlib import Path
import json,shutil,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,RESOURCES
from main import Bridge
from gamepad import dispatch,Mapper,Pad
from input_feedback import InputFeedback
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=80):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def pad(command):dispatch(app,root,backend,command);spin()
def idle():
    end=time.monotonic()+4
    while backend.busy and time.monotonic()<end:spin(20)
    assert not backend.busy,backend.status
    spin(130)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def click(window,item):
    p=item.mapToScene(QPointF(item.width()/2,item.height()/2));QTest.mouseClick(window,Qt.LeftButton,pos=QPoint(round(p.x()),round(p.y())));spin(160)
def scene(design):
    backend.saveSettings({'library_design':design,'theme':{'cinema':'violet','shelf':'amber','atlas':'midnight'}[design]});idle()
    invoke(root,'navigate','home','');spin(160)
    experience=next(i for i in walk(root.contentItem()) if i.objectName()=='libraryExperience');invoke(experience,'focusFirst');spin(160)
    return experience,experience.findChild(QObject,design+'Experience')
def frames():return [i for i in walk(root.contentItem()) if i.objectName() in ('cinemaCategoryFocusRing','cinemaFocusRing') and i.isVisible()]
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'immersive');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='',navigation_sounds=False,experience_group='series')
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8'))
    fixtures=[g for g in originals if g.get('cover') and (ROOT/'data/covers'/Path(g['cover']).name).is_file()][:28]
    assert fixtures
    (store.root/'covers').mkdir()
    for i,g in enumerate(fixtures):
        name=Path(g['cover']).name;shutil.copy2(ROOT/'data/covers'/name,store.root/'covers'/name)
        store.games.append({**g,'id':str(i),'cover':name,'series':f'Series {i//4}'})
    backend=Bridge(store);feedback=InputFeedback(app,backend,RESOURCES);backend.input_feedback=feedback
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(250)
    output=ROOT/'test-data/immersive-review';output.mkdir(exist_ok=True)
    experience,cinema=scene('cinema');backend.setControllerMode(True);pad('up');assert len(frames())==1
    # Mouse click a non-current category after controller focus. Old code drew
    # both the list's currentIndex and the clicked delegate's focus rectangle.
    for index in [2,0,1,0]:
        button=next((i for i in walk(cinema) if i.objectName()=='cinemaCategory-'+str(index)),None);assert button,(index,messages)
        click(root,button);assert not backend.controllerMode and len(frames())<=1,(index,len(frames()),messages)
        pad('up');assert len(frames())==1,(index,len(frames()),messages)
    pad('down');assert len(frames())==1
    posters=[i for i in walk(cinema) if i.objectName()=='cinemaPoster' and i.isVisible()]
    assert posters and posters[0].height()>=145,(cinema.height(),posters[0].height())
    assert len([i for i in walk(cinema) if i.objectName()=='cinemaFocusHalo' and i.isVisible()])==1
    root.grabWindow().save(str(output/'cinema-large-focus.png'))
    for width,height in [(900,650),(1920,1080)]:
        root.setWidth(width);root.setHeight(height);spin(160)
        info=cinema.findChild(QObject,'cinemaInformation');band=cinema.findChild(QObject,'cinemaFilmBand')
        assert info.y()+info.height()<=band.y()+1,(width,info.y(),info.height(),band.y())
        assert min(i.height() for i in walk(cinema) if i.objectName()=='cinemaPoster' and i.isVisible())>32
    root.setWidth(1440);root.setHeight(940);spin(160)
    window_size=(root.width(),root.height());invoke(root,'toggleFullScreen');spin(280);assert root.visibility()==QWindow.FullScreen
    personal=root.findChild(QObject,'personalization')
    for close in ('button','native','back'):
        invoke(personal,'openPersonalization');spin(180)
        pad('favorite');assert personal.isVisible() and store.settings['fullscreen']
        if close=='button':click(personal,personal.findChild(QObject,'personalClose'))
        elif close=='native':personal.close();spin(180)
        else:pad('back')
        spin(180);assert root.visibility()==QWindow.FullScreen and root.property('fullScreenMode') and store.settings['fullscreen'],(close,root.visibility())
        invoke(root,'focusFirstContent');pad('back');spin(120);assert root.visibility()==QWindow.FullScreen
        invoke(root,'focusFirstContent');pad('favorite');idle();assert root.visibility()==QWindow.FullScreen
    child=QQuickWindow();child.setTitle('Isolated controller return');child.resize(400,260);child.show();child.requestActivate();spin(180)
    pad('back');assert not child.isVisible() and root.visibility()==QWindow.FullScreen
    root.hide();spin(80);invoke(root,'restoreLibraryWindow');spin(180);assert root.visibility()==QWindow.FullScreen
    QTest.keyClick(root,Qt.Key_F11);spin(350);assert root.visibility()!=QWindow.FullScreen and not store.settings['fullscreen'],(root.visibility(),root.property('fullScreenMode'),store.settings['fullscreen'],root.isActive(),app.focusWindow(),messages)
    assert (root.width(),root.height())==window_size,('Fullscreen return changed window size',window_size,root.width(),root.height())
    root.setWidth(1440);root.setHeight(940)
    experience,atlas=scene('atlas');mapper=Mapper();state=Pad();before=atlas.property('zoom');ident=experience.property('selectedId')
    state.ry=22000
    for command in mapper.read(state,0):pad(command)
    assert atlas.property('zoom')>before and experience.property('selectedId')==ident
    before=atlas.property('zoom');state.ry=-22000
    for command in mapper.read(state,.1):pad(command)
    assert atlas.property('zoom')<before
    root.findChild(QObject,'search').forceActiveFocus();before=atlas.property('zoom');pad('zoom-in');assert atlas.property('zoom')==before
    invoke(experience,'focusContent');spin(160)
    sky=atlas.findChild(QObject,'atlasSky');star=next(i for i in walk(sky) if i.objectName()=='atlasDriftingStar-3');phase=sky.property('phase');x=star.x();paint_count=sky.property('texturePaints')
    root.grabWindow().save(str(output/'atlas-moving-before.png'));spin(900)
    assert sky.property('phase')>phase and abs(star.x()-x)>1
    assert sky.property('texturePaints')==paint_count,'Sky repainted cached textures for animation'
    root.grabWindow().save(str(output/'atlas-moving-after.png'))
    for pause in ('game','hidden','reduced','launch'):
        if pause=='game':backend._sessions.active['fixture']={};backend.watchStateChanged.emit()
        elif pause=='hidden':root.hide()
        elif pause=='reduced':backend.saveSettings({'animations':False});idle()
        else:atlas.setProperty('launching',True)
        spin(90);phase=sky.property('phase');spin(200);assert sky.property('phase')==phase,pause
        if pause=='game':backend._sessions.active.clear();backend.watchStateChanged.emit()
        elif pause=='hidden':invoke(root,'restoreLibraryWindow')
        elif pause=='reduced':backend.saveSettings({'animations':True});idle()
        else:atlas.setProperty('launching',False)
        spin(100)
    experience,cabinet=scene('shelf')
    for material in ('oak','walnut','cherry'):
        backend.saveSettings({'shelf_wood':material,'shelf_sunlight':True});idle();spin(180)
        assert cabinet.property('species')==material
        assert any(i.isVisible() for i in walk(cabinet) if i.objectName()=='shelfSunlight')
        root.grabWindow().save(str(output/('shelf-'+material+'.png')))
    assert Store(directory,'immersive').settings['shelf_wood']=='cherry'
    light=experience.findChild(QObject,'shelfSunlightToggle');light.forceActiveFocus();pad('activate');idle();assert not cabinet.property('sunlight')
    assert not any(i.isVisible() for i in walk(cabinet) if i.objectName()=='shelfSunlight')
    backend.setControllerMode(False);QTest.mouseMove(root,QPoint(220,15));spin(800)
    frames_idle=[];root.frameSwapped.connect(lambda:frames_idle.append(1));spin(250);assert len(frames_idle)<=5,len(frames_idle)
    errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','not a function','is not defined'))]
    assert not errors,errors
    feedback.release_cursor();app.removeEventFilter(feedback);backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: single mouse/category focus, larger filmstrip, fullscreen B/X/native/tray returns, real right-stick mapping, live cached sky/pause rules, three persisted woods, sunlight toggle and idle shelf')
