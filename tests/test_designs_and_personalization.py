"""Full library designs, paging versus selection, tooltip scope and scrollable preferences."""
from pathlib import Path
import json,shutil,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from themes import PALETTES
from PySide6.QtCore import QObject,QUrl,QPoint,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlEngine,QQmlProperty
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
    point=item.mapToScene(QPointF(item.width()/2,item.height()/2))
    QTest.mouseClick(window,Qt.LeftButton,pos=QPoint(round(point.x()),round(point.y())));spin(80)
def settle(bridge):
    deadline=time.monotonic()+8
    while bridge.busy and time.monotonic()<deadline:spin(25)
    assert not bridge.busy

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'design-review');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=True)
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8'))
    fixtures=[game for game in originals if game.get('cover') and (ROOT/'data/covers'/Path(game['cover']).name).is_file()][:24]
    assert fixtures
    (store.root/'covers').mkdir()
    for index in range(40):
        original=fixtures[index%len(fixtures)];cover=Path(original['cover']).name
        shutil.copy2(ROOT/'data/covers'/cover,store.root/'covers'/cover)
        store.games.append({'id':str(index),'name':original['name']+(f' {index}' if index>=len(fixtures) else ''),'cover':cover,'category':'视觉小说' if index<24 else '角色扮演','tags':['悬疑'] if index<24 else ['冒险'],'last_played':f'2026-10-16T09:{index:02}:00Z' if index<16 else '', 'favorite':index%5==0})
        store.local[str(index)]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.setWidth(1440);root.setHeight(940);root.requestActivate();spin(350)
    output=ROOT/'test-data/design-review';output.mkdir(exist_ok=True)
    assert not any(item.property('text')=='批量确认' for item in walk(root.contentItem()) if item.isVisible())
    personal=root.findChild(QObject,'personalization');invoke(personal,'openPersonalization');spin(250)
    scroll=personal.findChild(QObject,'personalizationScroll');flick=scroll.property('contentItem')
    for width,height in [(540,480),(820,720),(1100,900)]:
        personal.setWidth(width);personal.setHeight(height);spin(180)
        personal.findChild(QObject,'colorThemesToggle').setProperty('checked',True)
        personal.findChild(QObject,'customCoverToggle').setProperty('checked',True);spin(150)
        assert personal.findChild(QObject,'personalizationBar').property('visible')
        flick.setProperty('contentY',max(0,flick.property('contentHeight')-flick.height()));spin(100)
        save=personal.findChild(QObject,'saveCoverSource');point=save.mapToScene(QPointF(0,save.height()))
        assert 60<point.y()<height-25,(width,height,point.y(),flick.property('contentHeight'))
        personal.grabWindow().save(str(output/f'personalization-{width}.png'))
    personal.setWidth(820);personal.setHeight(720);flick.setProperty('contentY',0);spin(150)
    personal.findChild(QObject,'colorThemesToggle').setProperty('checked',False)
    personal.findChild(QObject,'customCoverToggle').setProperty('checked',False);spin(150)
    personal.grabWindow().save(str(output/'design-picker.png'))
    personal.hide();root.requestActivate();spin(150)
    assert store.settings['library_design']=='classic'
    invoke(root,'navigate','home','');root.setWidth(900);spin(180)
    view=next(item for item in walk(root.contentItem()) if item.objectName()=='shelf-recent')
    shelf=view.parentItem();selected=view.property('currentIndex')
    next_button=next(item for item in walk(shelf) if item.objectName()=='shelfNext')
    assert next_button.property('enabled')
    click(root,next_button);spin(220)
    assert view.property('currentIndex')==selected and view.property('contentX')>100
    root.setWidth(1440)
    # Cover hover never shows the title tooltip; only its own text area does.
    backend.saveSettings({'library_design':'classic','theme':'paper'});settle(backend);spin(150)
    invoke(root,'navigate','all','');spin(200)
    effect=next(item for item in walk(root.contentItem()) if item.objectName()=='coverEffects' and item.isVisible())
    card=effect.parentItem().parentItem();title=card.findChild(QObject,'gameTitle')
    point=effect.mapToScene(QPointF(effect.width()*.5,effect.height()*.3))
    QTest.mouseMove(root,QPoint(round(point.x()),round(point.y())));spin(900)
    assert title.property('tooltipVisible') is False,(title.property('tooltipVisible'),point.x(),point.y(),title.mapToScene(QPointF(0,0)),root.property('libraryDesign'),backend.controllerMode)
    point=title.mapToScene(QPointF(title.width()/2,10));QTest.mouseMove(root,QPoint(round(point.x()),round(point.y())));spin(800)
    assert title.property('tooltipVisible') is True
    backend.setControllerMode(True);spin(300)
    assert title.property('tooltipVisible') is False,(backend.controllerMode,title.property('text'),messages[-8:])
    backend.setControllerMode(False)
    invoke(root,'openSettingsPage',2);spin(150)
    home_spin=root.findChild(QObject,'homeCoverSize');home_spin.forceActiveFocus()
    original_home=root.property('homeCoverSize');QTest.keyClick(root,Qt.Key_Up);spin(80)
    assert root.property('homeCoverSize')==original_home+8
    QMetaObject.invokeMethod(root.findChild(QObject,'settingsDialog'),'reject');spin(100)
    assert root.property('homeCoverSize')==original_home
    # Home preferences survive a reload and change shelf geometry independently of the grid.
    old_size=root.property('coverSize');root.setProperty('homeCoverSize',224);root.setProperty('homeGap',22);root.setProperty('homeRecentPreview',False)
    invoke(root,'saveLayout');spin(400)
    restored=Store(directory,'design-review')
    assert restored.settings['home_cover_size']==224 and restored.settings['home_gap']==22 and not restored.settings['home_recent_preview']
    assert restored.settings['cover_size']==old_size
    invoke(root,'navigate','home','');spin(150)
    shelf=next(item for item in walk(root.contentItem()) if item.objectName()=='shelf-recent').parentItem()
    assert shelf.property('tileWidth')==round(224*.9) and not shelf.property('showPreview')
    for values in [{'home_cover_size':0},{'home_gap':99},{'library_design':'invalid'}]:
        try:store.save_settings(values)
        except ValueError:pass
        else:raise AssertionError(values)
    assert len(backend.themePresets)==8
    assert not any(term in message for message in messages for term in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','Detected anchors']),messages
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: classic layout, retained colors, paging/selection, scoped tooltips, scrolling preferences and independent persisted home size')
