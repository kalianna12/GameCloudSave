"""Render library at desktop/compact sizes; visible actions fit the shortened cards."""
from pathlib import Path
import json,shutil,sys,tempfile,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QPoint,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=120):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'library-refresh');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=True,theme='dark',accent_color='#80c942')
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8'))
    fixtures=[game for game in originals if game.get('cover') and (ROOT/'data/covers'/Path(game['cover']).name).is_file()][:24]
    assert fixtures,'Existing cover art is needed for this local visual review'
    (store.root/'covers').mkdir()
    for index,game in enumerate(fixtures):
        cover=Path(game['cover']).name;shutil.copy2(ROOT/'data/covers'/cover,store.root/'covers'/cover)
        store.games.append({'id':str(index),'name':game['name'],'cover':cover,'category':game.get('category','视觉小说'),'tags':game.get('tags',[]),'series':game.get('series',''),'last_played':'2026-10-16T09:00:00Z' if index<3 else '', 'release_date':'2021-04-23','platform':'local','import_source':'playnite'})
        store.local[str(index)]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.setWidth(1440);root.setHeight(940);root.requestActivate();spin(450)
    output=ROOT/'test-data/library-refresh';output.mkdir(exist_ok=True)
    QTest.mouseMove(root,QPoint(220,15));spin(800);root.grabWindow().save(str(output/'home-dark.png'))
    hero=next(item for item in walk(root.contentItem()) if item.objectName()=='recentHero' and item.isVisible())
    play=next(item for item in walk(hero) if item.property('iconName')=='play')
    point=play.mapToScene(play.boundingRect().center())
    with patch.object(store,'launch') as launch:
        QTest.mouseClick(root,Qt.LeftButton,pos=QPoint(round(point.x()),round(point.y())));spin(100)
        while backend.busy:spin(25)
        assert launch.call_count==1,'The hero launch action must only launch once'
        assert not root.findChild(QObject,'gameDialog').property('visible'),'The launch click also opened game settings'
    QTest.mouseMove(root,QPoint(220,15));spin(100)
    invoke(root,'navigate','all','');spin(350)
    grid=root.findChild(QObject,'gameGrid')
    assert backend.libraryMetadata('0')['release_date']=='2021-04-23','Hidden metadata must remain editable'
    for width,height,suffix in [(1440,940,'desktop'),(900,650,'compact'),(1920,1080,'wide')]:
        root.setWidth(width);root.setHeight(height);spin(250)
        checked_cards=0;grid_top=grid.mapToScene(QPoint(0,0)).y()
        for item in walk(root.contentItem()):
            if item.objectName()=='gameActions' and item.isVisible():
                card=item.parentItem().parentItem()
                card_top=card.mapToScene(card.boundingRect().topLeft()).y()
                card_bottom=card.mapToScene(card.boundingRect().bottomRight()).y()
                if card_top<grid_top-1 or card_bottom>grid_top+grid.height()+1:continue
                checked_cards+=1
                assert abs(card.height()-card.width()*1.38-90)<1,(width,card.width(),card.height(),grid.property('cellHeight'))
                assert item.y()+item.height()<=item.parentItem().height()+1,(width,item.y(),item.height(),item.parentItem().metaObject().className(),item.parentItem().height(),card.width(),card.height())
                assert item.mapToScene(item.boundingRect().bottomRight()).y()<=card.mapToScene(card.boundingRect().bottomRight()).y()+1
                assert not any('发行：' in str(child.property('text') or '') or ' / 已安装' in str(child.property('text') or '') for child in walk(card))
        assert checked_cards>0,'No complete visible action cards were checked'
        # Header controls remain on screen, and the reduced card footer has no empty metadata rows.
        for name in ['search','watchControl','platformFilter','librarySort']:
            item=root.findChild(QObject,name);point=item.mapToScene(item.boundingRect().topLeft())
            assert point.x()>=200 and point.x()+item.width()<=width+1,(width,name,point.x(),item.width())
        root.grabWindow().save(str(output/f'grid-{suffix}.png'))
    backend.saveSettings({'theme':'light'});
    while backend.busy:spin(25)
    root.setWidth(1440);root.setHeight(940);spin(300);root.grabWindow().save(str(output/'grid-light.png'))
    invoke(root,'navigate','home','');spin(300);root.grabWindow().save(str(output/'home-light.png'))
    assert not any(term in message for message in messages for term in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign']),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: shorter action cards, no metadata rows, desktop/900px/wide layouts and light theme; QML clean')
