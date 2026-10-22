"""One focus across recycled shelves, animated navigation, cursor ownership and sound."""
from pathlib import Path
import sys, tempfile, time, math
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import Store, ROOT, RESOURCES
from main import Bridge
from gamepad import dispatch
from input_feedback import InputFeedback
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, Q_RETURN_ARG, QEvent, Qt, QPointF, qInstallMessageHandler
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material')
app = QApplication([])
messages = []
qInstallMessageHandler(lambda kind, context, message: messages.append(message))

def spin(ms=250):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents(); time.sleep(.005)

def invoke(obj, name, *values):
    return QMetaObject.invokeMethod(obj, name, Q_RETURN_ARG('QVariant'), *(Q_ARG('QVariant', v) for v in values))

def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as directory:
    store = Store(directory, 'input')
    store.settings.update(setup_completed=True, guide_dismissed=True, watch=False)
    categories = ['视觉小说', '角色扮演', '动作冒险', '射击竞技', '策略模拟']
    for i in range(80):
        store.games.append({'id': str(i), 'name': f'Game {i:02}', 'category': categories[i % 5],
                            'tags': [categories[i % 5]], 'series': f'Pair {i % 3}',
                            'last_played': f'2026-10-09T12:{i % 60:02}:00Z', 'cover': ''})
        store.local[str(i)] = {'installed': True}
    backend = Bridge(store)
    feedback = InputFeedback(app, backend, RESOURCES); backend.input_feedback = feedback
    engine = QQmlApplicationEngine(); engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'ui/Main.qml'))); assert engine.rootObjects()
    root = engine.rootObjects()[0]; root.requestActivate(); spin()
    home = root.findChild(QObject, 'libraryHome'); view = root.findChild(QObject, 'libraryHomeList')
    home.forceActiveFocus()

    def rings():
        return [item for item in walk(root.contentItem()) if item.objectName() == 'tileFocusRing' and item.isVisible() and item.property('focusWidth') > 2.5]

    with patch.object(feedback.audio,'play') as audio:
        dispatch(app, root, backend, 'right'); spin()
        assert backend.controllerMode and feedback.hidden and app.overrideCursor().shape() == Qt.BlankCursor
        assert len(rings()) == 1, len(rings())
        # Visit multiple rows in both directions; bindings must remain live after reuse.
        samples = []
        root.frameSwapped.connect(lambda: samples.append(view.property('contentY')))
        for command in ['down', 'down', 'down', 'down', 'up', 'up', 'up', 'up']:
            dispatch(app, root, backend, command); spin()
            assert len(rings()) == 1, (command, home.property('focusedSection'), len(rings()))
        assert len({round(y, 1) for y in samples if y > 1}) > 10, 'Vertical navigation must render intermediate positions'
        assert audio.call_count >= 9, audio.call_count
        backend.store.settings['navigation_sounds'] = False
        count = audio.call_count; dispatch(app, root, backend, 'right'); spin()
        assert audio.call_count == count
        # Stationary or synthesized mouse input cannot take ownership.
        root.requestActivate(); spin(80); backend.setControllerMode(True)
        anchor = QPointF(feedback.pointer)
        app.sendEvent(root, QMouseEvent(QEvent.MouseMove, QPointF(20,20), anchor, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert backend.controllerMode and feedback.hidden
        moved = anchor + QPointF(15, 0)
        app.sendEvent(root, QMouseEvent(QEvent.MouseMove, QPointF(35,20), moved, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert not backend.controllerMode and not feedback.hidden and app.overrideCursor() is None
        home.forceActiveFocus(); dispatch(app, root, backend, 'right'); spin()
        feedback.application_state(Qt.ApplicationInactive)
        assert not feedback.hidden and not backend.controllerMode
        root.requestActivate(); invoke(root, 'navigate', 'all', ''); spin()
        grid = root.findChild(QObject, 'gameGrid'); grid.forceActiveFocus()
        samples.clear(); root.frameSwapped.connect(lambda: samples.append(grid.property('contentY')))
        for _ in range(4): dispatch(app, root, backend, 'down'); spin()
        assert grid.property('contentY') > 0 and len({round(y, 1) for y in samples if y > 1}) > 8
        store.settings['animations'] = False; backend.settingsChanged.emit(); spin()
        dispatch(app, root, backend, 'up'); spin(25)
        assert math.isfinite(grid.property('contentY'))
    # Cross-region recovery after mouse focus, sorting and popup dismissal.
    from library_sources import release_date, playnite_metadata
    assert release_date({'Year':2020,'Month':2,'Day':29}) == '2020-02-29'
    assert release_date({'$date':'2021-07-03T00:00:00Z'}) == '2021-07-03'
    for unknown in (None, '2020', '2021-02-29', {'Year':2020}, 'Coming soon'):
        assert release_date(unknown) == ''
    assert playnite_metadata({'ReleaseDate':{'Year':1999,'Month':9,'Day':9}})['release_date']=='1999-09-09'
    grid.setProperty('currentIndex',0);grid.forceActiveFocus()
    dispatch(app,root,backend,'left');spin()
    assert root.activeFocusItem().objectName()=='navAll'
    for name in ['navRecent','navFavorites','navSeries']:
        dispatch(app,root,backend,'down');spin(30)
        assert root.activeFocusItem().objectName()==name
    dispatch(app,root,backend,'activate');spin()
    assert root.property('libraryMode')=='series'
    grid.setProperty('currentIndex',0);grid.forceActiveFocus()
    dispatch(app,root,backend,'up');spin()
    item=root.activeFocusItem();toolbar_names={'installedFilter','platformFilter','sourceFilter','seriesFilter','librarySort','homeMappingProfile','layoutControl','personalControl','fullscreenControl'}
    while item and item.objectName() not in toolbar_names:item=item.parentItem() if hasattr(item,'parentItem') else item.parent()
    assert item is not None,'Up from the grid must enter the nearest visible toolbar row'
    root.findChild(QObject,'installedFilter').forceActiveFocus()
    dispatch(app,root,backend,'right');spin()
    assert root.activeFocusItem().objectName()=='platformFilter'
    dispatch(app,root,backend,'search');spin()
    assert root.activeFocusItem().objectName()=='search'
    dispatch(app,root,backend,'activate');spin()
    keyboard=root.findChild(QObject,'controllerKeyboard');assert keyboard.property('visible')
    dispatch(app,root,backend,'activate');spin(40)
    assert keyboard.property('value')=='1'
    dispatch(app,root,backend,'favorite');spin(40);assert keyboard.property('value')==''
    dispatch(app,root,backend,'history');spin(40);assert keyboard.property('value')==' '
    keyboard.setProperty('value','Game 00')
    dispatch(app,root,backend,'menu');spin()
    assert not keyboard.property('visible') and root.property('searchQuery')=='game 00'
    invoke(root,'navigate','all','');spin()
    search=root.findChild(QObject,'search');search.forceActiveFocus()
    dispatch(app,root,backend,'right');spin()
    watch=root.findChild(QObject,'watchControl');assert watch.hasActiveFocus()
    assert root.findChild(QObject,'watchFocusRing').isVisible()
    dispatch(app,root,backend,'right');spin();assert watch.hasActiveFocus(), 'Unsupported import button must not receive controller focus'
    dispatch(app,root,backend,'activate');spin()
    while backend.busy:spin(25)
    assert store.settings['watch']
    store.settings['watch']=False;backend.timer.stop();backend.settingsChanged.emit()
    # Mouse-click a top control, then resume navigation into the content.
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPoint
    search=root.findChild(QObject,'search');point=search.mapToScene(QPointF(search.width()/2,search.height()/2))
    QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,QPoint(int(point.x()),int(point.y())));spin()
    dispatch(app,root,backend,'down');spin()
    assert not invoke(root,'libraryFocus'),'Down from search enters the toolbar at the current column'
    for _ in range(3):
        if grid.hasActiveFocus():break
        dispatch(app,root,backend,'down');spin()
    assert grid.hasActiveFocus()
    invoke(root,'navigate','all','');spin()
    store.games[0]['release_date']='2020-02-29';store.games[1]['release_date']='1999-09-09'
    backend._games_cache=None;backend.gamesChanged.emit();spin()
    def records():
        value=root.property('shownGames');return value.toVariant() if hasattr(value,'toVariant') else value
    root.setProperty('librarySort','release_asc');spin()
    assert [g['id'] for g in records()[:2]]==['1','0']
    root.setProperty('librarySort','release_desc');spin()
    assert [g['id'] for g in records()[:2]]==['0','1']
    assert all(not g.get('release_date') for g in records()[2:])
    # Real combo activation changes sorting even in the recent page.
    invoke(root,'navigate','recent','');spin()
    sort=root.findChild(QObject,'librarySort');sort.forceActiveFocus()
    dispatch(app,root,backend,'activate');spin()
    for _ in range(2):dispatch(app,root,backend,'down');spin(30)
    dispatch(app,root,backend,'activate');spin()
    assert root.property('librarySort')=='release_asc' and [g['id'] for g in records()[:2]]==['1','0']
    assert sort.width()>=200
    grid.setProperty('currentIndex',0);grid.forceActiveFocus();spin()
    rings=[item for item in walk(root.contentItem()) if item.objectName()=='cardFocusRing' and item.isVisible()]
    assert len(rings)==1 and rings[0].z()>0
    ring=rings[0];assert ring.width()==ring.parentItem().width() and ring.height()==ring.parentItem().height()
    dispatch(app,root,backend,'menu');spin();assert backend.popupActive()
    before=grid.property('currentIndex');dispatch(app,root,backend,'right');spin()
    assert grid.property('currentIndex')==before
    dispatch(app,root,backend,'back');spin();assert not backend.popupActive()
    dispatch(app,root,backend,'right');spin();assert grid.property('currentIndex')==1
    # A mouse-only child window must not accept arbitrary gamepad Tab/Space input.
    invoke(root,'openBatch');spin();child=root.findChild(QObject,'batchWindow')
    focused=child.activeFocusItem()
    with patch.object(backend,'applyMatches') as apply:
        for command in ['up','right','activate','launch']:dispatch(app,root,backend,command);spin(30)
        assert child.activeFocusItem()==focused and not apply.called
    dispatch(app,root,backend,'back');spin();assert not child.property('visible')
    assert not any(term in message for message in messages for term in ['TypeError', 'ReferenceError', 'Binding loop', 'Cannot assign']), messages
    feedback.release_cursor(); app.removeEventFilter(feedback)
    backend.timer.stop(); backend.pool.shutdown(wait=True); shiboken6.delete(engine)
print('PASS: release sorting and unknown dates, sidebar/toolbar navigation, mouse recovery, whole-card ring, popup guard, input regressions')

