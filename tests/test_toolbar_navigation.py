"""Single-row tools, viewport reveal and controller/keyboard focus at every width."""
from pathlib import Path
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QPointF,QPoint,QMetaObject,Q_ARG,Q_RETURN_ARG,Qt,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))

def spin(ms=35):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def pad(command):dispatch(app,root,backend,command);spin()
def center(item):return item.mapToScene(QPointF(item.width()/2,item.height()/2))

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'toolbar-navigation');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,animations=False,recommendations_enabled=False,theme='light')
    store.games=[{'id':str(i),'name':f'Game {i:02}','cover':'','tags':['冒险'],'series':'Example','category':'动作冒险','last_played':'2026-10-10T12:00:00Z'} for i in range(30)]
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(200);backend.setControllerMode(True)
    names=['libraryBack','search','watchControl','installedFilter','platformFilter','sourceFilter','libraryFilterControl','clearLibraryFilters','homeRandomGame','librarySort','homeMappingProfile','layoutControl','personalControl','fullscreenControl']
    controls={name:root.findChild(QObject,name) for name in names};assert all(controls.values())
    def focus_name():
        item=root.activeFocusItem()
        while item:
            if item.objectName() in controls:return item.objectName()
            item=item.parentItem() if hasattr(item,'parentItem') else item.parent()
        return ''
    def focus(name):controls[name].forceActiveFocus();spin(15)
    def expect(name):assert focus_name()==name,(name,focus_name(),[(n,round(center(c).x()),round(center(c).y())) for n,c in controls.items() if c.isVisible()])
    def content():assert invoke(root,'libraryFocus'),(root.activeFocusItem().objectName(),focus_name())
    try:
        strip=root.findChild(QObject,'libraryToolbarStrip')
        def visible_focus():
            control=controls[focus_name()];p=control.mapToItem(strip,QPointF())
            assert p.x()>=-1 and p.x()+control.width()<=strip.width()+1,(focus_name(),p.x(),control.width(),strip.width())
        root.resize(1100,800);spin(80)
        focus('sourceFilter');pad('right');expect('libraryFilterControl');visible_focus()
        pad('right');expect('homeRandomGame');pad('right');expect('homeMappingProfile');visible_focus()
        pad('left');expect('homeRandomGame');pad('left');expect('libraryFilterControl');pad('activate')
        assert root.findChild(QObject,'libraryFilterDialog').property('visible')
        pad('back');spin(60);expect('libraryFilterControl')
        focus('homeMappingProfile');pad('right');expect('layoutControl');pad('right');expect('personalControl');pad('right');expect('fullscreenControl')
        for _ in range(6):pad('right');expect('fullscreenControl')
        visible_focus()
        pad('left');expect('personalControl');pad('left');expect('layoutControl');pad('left');expect('homeMappingProfile')
        focus('platformFilter');visible_focus()
        p=center(controls['platformFilter']);QTest.mouseClick(root,Qt.LeftButton,pos=QPoint(round(p.x()),round(p.y())));spin(50)
        pad('back');spin(50);pad('down');content();pad('up');expect('platformFilter')
        focus('homeMappingProfile');pad('activate');spin(70);pad('down')
        assert not root.property('fullScreenMode') and not backend.mapping.state['enabled']
        pad('back');spin(70);expect('homeMappingProfile')
        output=ROOT/'build/toolbar-single-row';output.mkdir(exist_ok=True)
        for width in (900,1100,1440,1920):
            root.resize(width,850);spin(70)
            for mode in ('home','all','series'):
                invoke(root,'navigate',mode,'');spin(50)
                filter_names=[n for n in names if n not in ('libraryBack','search','watchControl') and controls[n].isVisible()]
                ys=[center(controls[n]).y() for n in filter_names]
                assert max(ys)-min(ys)<3,(width,mode,ys)
                for name,control in controls.items():
                    if not control.isVisible() or not control.isEnabled():continue
                    focus(name);origin=center(control);pad('right');right=focus_name()
                    assert right and abs(center(controls[right]).y()-origin.y())<20,(width,mode,name,right,'horizontal wrapped',root.isActive(),root.activeFocusItem().objectName() if root.activeFocusItem() else None,[(w.objectName(),w.isVisible(),w.isActive()) for w in app.topLevelWindows()],messages[-6:])
                    if right not in ('libraryBack','search','watchControl'):visible_focus()
                    focus(name);pad('up');above=focus_name()
                    assert above,(width,mode,name,'lost focus')
                    if above!=name:
                        assert center(controls[above]).y()<origin.y()-15,(width,mode,name,above)
                        pad('down');expect(name)
                invoke(root,'focusFirstContent');pad('up');assert focus_name() in controls
                for _ in range(5):
                    if invoke(root,'libraryFocus'):break
                    pad('down')
                content()
            focus('installedFilter');root.grabWindow().save(str(output/f'window-{width}.png'))
        invoke(root,'toggleFullScreen');spin(180)
        ys=[center(controls[n]).y() for n in filter_names];assert max(ys)-min(ys)<3
        root.grabWindow().save(str(output/'fullscreen.png'));invoke(root,'toggleFullScreen');spin(80)
        errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))]
        assert not errors,errors
    finally:
        backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: single tool row at 900/1100/1440/1920px and fullscreen, scroll-to-focus, mouse and controller recovery')
