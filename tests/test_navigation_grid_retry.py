"""Use rendered grid columns and focused card, preview sidebar without A."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'nav-grid');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=False)
    for index in range(50):
        ident=str(index);store.games.append({'id':ident,'name':f'Game {index:02}','category':'视觉小说','tags':['视觉小说'],
            'series':'Example','favorite':index%3==0,'last_played':'2026-10-09T12:00:00Z','cover':''})
        store.local[ident]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects()
    root=engine.rootObjects()[0];root.requestActivate();spin(300)
    grid=root.findChild(QObject,'gameGrid');home=root.findChild(QObject,'libraryHome')
    invoke(root,'navigate','all','');spin()
    # The old layout cap claimed fewer columns than Qt actually drew for small covers.
    cases=[(1440,140,0),(900,140,0),(1440,200,0),(1919,200,0),(1440,320,0),(1440,200,3),(1919,200,7)]
    for width,size,fixed in cases:
        root.setWidth(width);root.setProperty('coverSize',size);root.setProperty('columnCount',fixed);spin(150)
        columns=grid.property('effectiveColumns');invoke(grid,'navigateFocus',0);spin()
        first_y=grid.property('currentItem').y()
        invoke(grid,'navigateFocus',columns-1);spin();assert abs(grid.property('currentItem').y()-first_y)<1,(width,size,fixed,columns)
        invoke(grid,'navigateFocus',columns+1);spin();assert grid.property('currentItem').y()>first_y
        dispatch(app,root,backend,'up');spin()
        assert grid.property('currentIndex')==1 and root.activeFocusItem().objectName()=='gameGrid',(width,size,fixed,columns,root.activeFocusItem().objectName())
        dispatch(app,root,backend,'down');spin();assert grid.property('currentIndex')==columns+1
    # Mouse-focused actions belong to their card, even when currentIndex was stale.
    invoke(grid,'navigateFocus',8);spin();delegate=grid.property('currentItem')
    action=next(item for item in walk(delegate) if item.objectName()=='action-settings');grid.setProperty('currentIndex',0);action.forceActiveFocus()
    columns=grid.property('effectiveColumns');dispatch(app,root,backend,'up');spin()
    assert grid.property('currentIndex')==8-columns and root.activeFocusItem().objectName()=='gameGrid',(grid.property('currentIndex'),columns,root.activeFocusItem().objectName())
    invoke(grid,'navigateFocus',0);spin();dispatch(app,root,backend,'left');spin()
    assert root.activeFocusItem().objectName()=='navAll' and root.property('libraryMode')=='all'
    for name,mode in [('navRecent','recent'),('navFavorites','favorites'),('navSeries','series')]:
        dispatch(app,root,backend,'down');spin()
        assert root.activeFocusItem().objectName()==name and root.property('libraryMode')==mode
    dispatch(app,root,backend,'right');spin()
    assert grid.property('currentIndex')==0 and root.activeFocusItem().objectName()=='gameGrid'
    # Re-enter after a moved cursor: right always enters the first game.
    invoke(grid,'navigateFocus',12);spin();grid.setProperty('currentIndex',0);grid.forceActiveFocus()
    dispatch(app,root,backend,'left');spin();grid.setProperty('currentIndex',12)
    dispatch(app,root,backend,'right');spin();assert grid.property('currentIndex')==0
    # Home also starts at its first shelf and first tile.
    dispatch(app,root,backend,'left');spin()
    for _ in range(4):dispatch(app,root,backend,'up');spin(50)
    assert root.property('libraryMode')=='home' and root.activeFocusItem().objectName()=='navHome'
    dispatch(app,root,backend,'right');spin();assert home.property('focusedSection')==0
    shelf=invoke(home,'currentShelf');assert shelf.property('selectionIndex')==0
    dispatch(app,root,backend,'down');spin();dispatch(app,root,backend,'right');spin()
    home.setProperty('focusedSection',0);home.forceActiveFocus();shelf=invoke(home,'currentShelf');invoke(shelf,'selectFirst')
    dispatch(app,root,backend,'left');spin();dispatch(app,root,backend,'right');spin()
    assert home.property('focusedSection')==0 and invoke(home,'currentShelf').property('selectionIndex')==0
    assert not any(word in message for message in messages for word in ['TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign']),messages
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: rendered columns, correct game above, action-focus recovery, sidebar selection previews and first-game entry')
