"""Use isolated real artwork copies; never launch games or modify the real library."""
from pathlib import Path
import json,shutil,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def click(window,item):
    p=item.mapToScene(QPointF(item.width()/2,item.height()/2));QTest.mouseClick(window,Qt.LeftButton,pos=QPoint(round(p.x()),round(p.y())));spin(100)
def save(backend,values):
    backend.saveSettings(values);deadline=time.monotonic()+6
    while backend.busy and time.monotonic()<deadline:spin(30)
    assert not backend.busy;spin(120)
def data(obj,key):
    v=obj.property(key);return v.toVariant() if hasattr(v,'toVariant') else v

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'experiences');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=True,library=str(Path(directory)/'playnite/library'))
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8'))
    fixtures=[g for g in originals if g.get('cover') and (ROOT/'data/covers'/Path(g['cover']).name).is_file()]
    (store.root/'covers').mkdir()
    for i,original in enumerate(fixtures[:36]):
        cover=Path(original['cover']).name;shutil.copy2(ROOT/'data/covers'/cover,store.root/'covers'/cover)
        store.games.append({**original,'id':str(i),'cover':cover,'category':original.get('category') or ['视觉小说','角色扮演','动作冒险'][i%3], 'series':original.get('series') or ('测试系列' if i<3 else ''),'tags':original.get('tags') or ['冒险'],'favorite':i%5==0})
        store.local[str(i)]={'installed':i%3!=0}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(250)
    output=ROOT/'test-data/experience-review';output.mkdir(exist_ok=True)
    assert root.property('libraryDesign')=='classic'
    root.grabWindow().save(str(output/'classic-home.png'))
    for design,theme in [('shelf','amber'),('cinema','violet'),('atlas','midnight')]:
        save(backend,{'library_design':design,'theme':theme,'experience_group':'category'});spin(250)
        experience=next(item for item in walk(root.contentItem()) if item.objectName()=='libraryExperience')
        scene=next(item for item in walk(experience) if item.objectName()==design+'Experience')
        assert scene.isVisible() and scene.width()>500 and scene.height()>200,(design,scene.width(),scene.height(),messages)
        invoke(root,'navigate','home','');spin(120)
        invoke(experience,'focusFirst');backend.setControllerMode(True);spin(60)
        if design!='atlas':
            dispatch(app,root,backend,'left');spin(80);assert root.activeFocusItem().objectName()=='navHome',(design,root.property('libraryMode'),root.activeFocusItem().objectName(),messages)
            dispatch(app,root,backend,'down');spin(80);assert root.property('libraryMode')=='all'
            dispatch(app,root,backend,'right');spin(80);assert experience.property('selectedId')==data(experience,'filteredGames')[0]['id']
            dispatch(app,root,backend,'up');spin(80);assert root.activeFocusItem().objectName()=='experienceGrouping'
            dispatch(app,root,backend,'activate');spin(80);assert backend.popupActive()
            dispatch(app,root,backend,'down');dispatch(app,root,backend,'activate');spin(300)
            assert experience.property('groupMode')=='series' and not backend.popupActive(),(design,experience.property('groupMode'),backend.popupActive(),messages)
            experience.setProperty('groupMode','category');invoke(experience,'focusFirst');spin(60)
        before=experience.property('selectedId');dispatch(app,root,backend,'right');spin(150)
        assert experience.property('selectedId')!=before,(design,before,root.activeFocusItem(),messages)
        dispatch(app,root,backend,'activate');spin(100);assert backend.popupActive(),design
        dispatch(app,root,backend,'back');spin(450);assert not backend.popupActive(),design
        backend.setControllerMode(False);QTest.mouseMove(root,QPoint(220,15));spin(800)
        frames=[]
        def frame():frames.append(time.monotonic())
        root.frameSwapped.connect(frame);spin(250);root.frameSwapped.disconnect(frame)
        if len(frames)>5:
            def ancestry(item):
                values=[]
                for _ in range(6):
                    if not item:break
                    values.append((item.metaObject().className(),item.objectName(),item.property('visible'),item.property('opacity')));item=item.parent()
                return values
            animations=[(ancestry(item),item.property('duration'),item.property('loops'),item.property('from'),item.property('to')) for item in root.findChildren(QObject) if item.property('running') is True]
            raise AssertionError((design,'idle frames',len(frames),animations,messages))
        root.grabWindow().save(str(output/f'{design}-home.png'))
        for width,height in [(900,650),(1920,1080)]:
            root.setWidth(width);root.setHeight(height);spin(180)
            assert scene.height()>140 and scene.width()>500
            if design=='cinema':
                information=scene.findChild(QObject,'cinemaInformation');band=scene.findChild(QObject,'cinemaFilmBand')
                assert information.y()+information.height()<=band.y()+1,(width,information.y(),information.height(),band.y())
            root.grabWindow().save(str(output/f'{design}-{width}.png'))
        root.setWidth(1440);root.setHeight(940);spin(180)
        if design=='shelf':
            plank=next(item for item in walk(scene) if item.objectName()=='shelfPlank' and item.isVisible())
            title=next(item for item in walk(scene) if item.objectName()=='bookTitle' and item.isVisible())
            pt=title.mapToScene(QPointF(0,0));pb=plank.mapToScene(QPointF(0,0))
            assert pb.y()<=pt.y() and pt.y()+title.height()<=pb.y()+plank.height(),(pt,pb,title.height(),plank.height())
            book=next(item for item in walk(scene) if item.metaObject().className().startswith('BookCover') and item.isVisible())
            p=book.mapToScene(QPointF(30,60));QTest.mouseMove(root,QPoint(round(p.x()),round(p.y())));spin(300)
            assert book.property('raised') and book.property('lift')==22
            root.grabWindow().save(str(output/'shelf-hover.png'))
            backend.setControllerMode(True);invoke(experience,'focusFirst');dispatch(app,root,backend,'right');spin(400)
            assert not book.property('raised'),'Old book retained its pointer lift'
            backend.setControllerMode(False);QTest.mouseMove(root,QPoint(220,15));save(backend,{'shelf_arrangement':'books'})
            volume=book.findChild(QObject,'bookVolume');assert not volume.isVisible(),'A closed spine must not expose an edge-on cover'
            for local in [QPointF(55,90),QPointF(25,36),QPointF(25,book.height()-10)]:
                point=book.mapToScene(local);QTest.mouseMove(root,QPoint(round(point.x()),round(point.y())));spin(100)
                assert not book.property('raised'),('Empty space picked up a book',local)
            point=book.mapToScene(QPointF(25,90));QTest.mouseMove(root,QPoint(round(point.x()),round(point.y())));spin(300)
            assert book.property('raised') and volume.isVisible(),'Only the real spine should pick up the cover'
            point=volume.mapToScene(QPointF(0,0));bounds=scene.mapToScene(QPointF(0,0));assert point.y()>=bounds.y(),'Raised cover was clipped at the shelf top'
            QTest.mouseMove(root,QPoint(220,15));spin(300);assert not volume.isVisible()
            jacket=book.findChild(QObject,'bookJacket');left=jacket.mapToScene(QPointF(0,0));right=jacket.mapToScene(QPointF(jacket.width(),0))
            assert abs(right.y()-left.y())<jacket.height()*.2,('Closed book has a diagonal roll',left,right,jacket.height())
            root.grabWindow().save(str(output/'shelf-spines.png'))
        if design=='atlas':
            sky=scene.findChild(QObject,'atlasSky');phase=sky.property('phase');spin(180);assert sky.property('phase')>phase
            save(backend,{'animations':False});phase=sky.property('phase');spin(180);assert sky.property('phase')==phase
            save(backend,{'animations':True})
            backend._sessions.active['fixture']={};backend.watchStateChanged.emit();spin(40)
            phase=sky.property('phase');spin(180);assert sky.property('phase')==phase,'Sky must pause while a game is running'
            backend._sessions.active.clear();backend.watchStateChanged.emit()
            root.hide();spin(40);phase=sky.property('phase');spin(180);assert sky.property('phase')==phase,'Hidden sky kept animating'
            root.show();root.requestActivate();spin(120)
            graph=data(scene,'graph');assert len(graph['nodes'])==len(store.games) and len({n['game']['id'] for n in graph['nodes']})==len(store.games)
            for edge in graph['edges']:assert edge['a']['game']['category']==edge['b']['game']['category']==edge['label']
            map_item=scene.findChild(QObject,'atlasMap');before=(scene.property('panX'),scene.property('panY'))
            p=map_item.mapToScene(QPointF(30,100));p=QPoint(round(p.x()),round(p.y()))
            QTest.mousePress(root,Qt.LeftButton,pos=p);QTest.mouseMove(root,p+QPoint(70,50),100);QTest.mouseMove(root,p+QPoint(110,80),100);QTest.mouseRelease(root,Qt.LeftButton,pos=p+QPoint(110,80));spin(100)
            assert before!=(scene.property('panX'),scene.property('panY')),(before,scene.property('panX'),scene.property('panY'),messages)
            zoom=scene.property('zoom');click(root,scene.findChild(QObject,'atlasZoomIn'));assert scene.property('zoom')>zoom
            # A wheel step zooms around the pointer, not just the +/- controls.
            from PySide6.QtGui import QWheelEvent
            p=map_item.mapToScene(QPointF(map_item.width()/2,map_item.height()/2));zoom=scene.property('zoom')
            event=QWheelEvent(p,root.mapToGlobal(QPoint(round(p.x()),round(p.y()))),QPoint(0,0),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
            app.sendEvent(root,event);spin(80);assert scene.property('zoom')>zoom
            import math
            assert math.isfinite(scene.property('panX')) and math.isfinite(scene.property('panY'))
            invoke(scene,'celebrate');spin(150);assert scene.property('lucky')
            root.grabWindow().save(str(output/'atlas-lucky.png'));spin(650);assert not scene.property('lucky')
            experience.setProperty('groupMode','series');spin(200)
            for group in data(scene,'graph')['labels']:
                dated=[n['game'].get('release_date','') for n in data(scene,'graph')['nodes'] if n['group']==group['name'] and n['game'].get('release_date')]
                assert dated==sorted(dated),dated
            root.grabWindow().save(str(output/'atlas-series.png'))
            experience.setProperty('groupMode','year');spin(200);root.grabWindow().save(str(output/'atlas-year.png'))
            experience.setProperty('groupMode','category');spin(150)
        if design=='cinema':
            ribbon=scene.findChild(QObject,'cinemaCategories');chip=next(item for item in walk(ribbon) if item.inherits('QQuickAbstractButton') and item.isVisible() and item.property('modelData') is not None and data(item,'modelData').get('value'))
            value=data(chip,'modelData')['value'];click(root,chip);assert experience.property('groupValue')==value
            experience.setProperty('groupValue','');spin(150)
        # Dice samples the filtered group without repeats and never launches a game.
        experience.setProperty('groupMode','series');spin(80)
        groups=data(experience,'groups');group=next(g for g in groups if len(g['items'])>=2)
        experience.setProperty('groupValue',group['name']);spin(100)
        allowed={g['id'] for g in group['items']};seen=[]
        for _ in range(len(allowed)):
            invoke(experience,'randomGame');spin(30);seen.append(experience.property('selectedId'))
        assert set(seen)==allowed and len(seen)==len(set(seen)),(design,seen,allowed)
        experience.setProperty('groupValue','');experience.setProperty('groupMode','category');spin(100)
    personal=root.findChild(QObject,'personalization');invoke(personal,'openPersonalization');spin(250)
    personal.grabWindow().save(str(output/'design-picker.png'));personal.hide();root.requestActivate();spin(100)
    # A launch transition commits once even after a rapid duplicate request.
    calls=[];backend.launch=lambda ident:calls.append(ident)
    game=backend.games[0];invoke(root,'launchGame',game);dispatch(app,root,backend,'back');spin(300);assert not calls
    invoke(root,'launchGame',game);invoke(root,'launchGame',game);spin(400)
    assert calls==[game['id']],calls
    save(backend,{'animations':False});invoke(root,'launchGame',game);spin(50);assert calls==[game['id']]*2
    # The classic scene remains the default and restores the original aspect ratio.
    save(backend,{'library_design':'classic'});invoke(root,'navigate','all','');spin(200)
    grid=root.findChild(QObject,'gameGrid');assert grid.isVisible()
    assert abs(grid.property('cellHeight')-grid.property('cardWidth')*1.38-90-root.property('gridGap'))<1
    errors=[m for m in messages if any(term in m for term in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','not a function','is not defined'])]
    assert not errors,errors
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: classic default, book pickup/spines, cinema navigation, atlas relations/pan/zoom, scoped dice, responsive layouts, launch once and reduced motion')
