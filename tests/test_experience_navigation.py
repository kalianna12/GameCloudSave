"""Controller-only paths across film categories, top controls and design selection."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=60):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.004)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def pad(command):dispatch(app,root,backend,command);spin()
def idle():
    end=time.monotonic()+3
    while backend.busy and time.monotonic()<end:spin(20)
    assert not backend.busy;spin(100)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def category_focus():
    item=root.activeFocusItem()
    while item:
        if item.objectName()=='cinemaCategories':return True
        item=item.parentItem() if hasattr(item,'parentItem') else item.parent()
    return False
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'pad-designs');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='')
    (store.root/'covers').mkdir();art=store.root/'covers/fixture.png';image=QImage(300,450,QImage.Format_RGB32);image.fill(QColor('#806c92'));image.save(str(art))
    store.games=[{'id':str(i),'name':f'Game {i:02}','cover':str(art),'series':f'Series {i//3}','category':['动作冒险','视觉小说','角色扮演'][i%3],'tags':['冒险']} for i in range(30)]
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(200);backend.setControllerMode(True)
    output=ROOT/'test-data/navigation-search-review';output.mkdir(exist_ok=True)
    designs=['classic','shelf','cinema','atlas']
    for source in designs:
        root.setProperty('filterFocusIndex',0);root.setProperty('headerFocusIndex',0)
        backend.saveSettings({'library_design':source,'experience_group':'series'});idle();root.requestActivate();invoke(root,'navigate','home','');spin(120)
        if source!='classic':
            experience=next(item for item in walk(root.contentItem()) if item.objectName()=='libraryExperience');invoke(experience,'focusFirst');spin()
        if source=='cinema':
            pad('up');assert category_focus(),(root.activeFocusItem().objectName(),messages)
            categories=experience.findChild(QObject,'cinemaCategories');pad('right');assert categories.property('currentIndex')==1
            assert len([item for item in walk(categories) if item.objectName()=='cinemaCategoryFocusRing' and item.isVisible()])==1
            root.grabWindow().save(str(output/'cinema-categories-focus.png'))
            pad('back');assert root.activeFocusItem().objectName()=='libraryExperience'
            pad('up');pad('right')
            pad('activate');assert experience.property('groupValue')=='Series 0'
            pad('up');pad('up');assert root.activeFocusItem().objectName()=='experience-action-play'
            pad('right');assert root.activeFocusItem().objectName()=='experience-action-settings'
            pad('activate');assert backend.popupActive();pad('back');spin(200)
            invoke(experience,'focusFirst');pad('up');pad('down');assert root.activeFocusItem().objectName()=='libraryExperience'
            invoke(experience,'focusFirst');pad('up');pad('up');pad('up');assert root.activeFocusItem().objectName()=='experienceGrouping'
            # The real film model scrolls to categories beyond the viewport.
            root.setWidth(900);root.setHeight(650);spin(100)
            invoke(experience,'focusFirst');pad('up')
            for _ in range(10):pad('right')
            assert categories.property('currentIndex')==10 and categories.property('contentX')>0
            pad('activate');assert experience.property('groupValue')=='Series 9'
            experience.setProperty('groupValue','');root.setWidth(1440);root.setHeight(940);spin()
        # Reach top tools from each layout through its own boundaries.
        invoke(root,'focusFirstContent');spin()
        for _ in range(80):
            if root.activeFocusItem().objectName()=='installedFilter':break
            pad('up')
        assert root.activeFocusItem().objectName()=='installedFilter',(source,root.activeFocusItem().objectName())
        for _ in range(12):
            if root.activeFocusItem().objectName()=='personalControl':break
            pad('right')
        assert root.activeFocusItem().objectName()=='personalControl',source
        pad('activate');spin(150);personal=root.findChild(QObject,'personalization')
        assert app.focusWindow()==personal and personal.activeFocusItem().objectName()=='design-'+source,(source,messages)
        target=designs[(designs.index(source)+1)%4];current=designs.index(source);destination=designs.index(target)
        if current//2!=destination//2:pad('down' if destination//2>current//2 else 'up')
        if current%2!=destination%2:pad('right' if destination%2>current%2 else 'left')
        assert personal.activeFocusItem().objectName()=='design-'+target,(source,target,personal.activeFocusItem().objectName())
        pad('activate');idle();assert root.property('libraryDesign')==target
        personal.grabWindow().save(str(output/(source+'-to-'+target+'.png')))
        pad('back');spin(180);assert app.focusWindow()==root and root.activeFocusItem().objectName()=='personalControl'
    # Narrow personalization becomes one column; D-pad scrolling keeps selection visible.
    personal.setWidth(540);personal.setHeight(480);invoke(personal,'openPersonalization');spin(100)
    for _ in range(3):pad('down')
    view=personal.findChild(QObject,'personalizationScroll').property('contentItem');assert view.property('contentY')>0
    focus=personal.activeFocusItem()
    point=focus.mapToItem(view,QPointF(0,0))
    assert view.property('width')<personal.width() and point.y()>=-1 and point.y()+focus.height()<=view.property('height')+1,(focus.objectName(),point,view.property('height'),focus.height())
    personal.grabWindow().save(str(output/'personal-small-scroll.png'))
    pad('down');assert personal.activeFocusItem().objectName()=='colorThemesToggle'
    pad('activate');assert personal.findChild(QObject,'themeGrid').isVisible()
    pad('down');assert personal.activeFocusItem().objectName().startswith('theme-')
    theme=personal.activeFocusItem().objectName().removeprefix('theme-');pad('activate');idle();assert backend.settings['theme']==theme
    pad('back')
    errors=[m for m in messages if any(term in m for term in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','not a function','is not defined'])]
    assert not errors,errors
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: cinema category focus/scroll/filter/actions, all four layouts reach top tools, controller-only personalization/design changes, return focus and narrow-window scrolling')
