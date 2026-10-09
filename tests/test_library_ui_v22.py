"""Real QML themes, filtering, source dropdown, sorting and stable library scroll."""
from pathlib import Path
import sys,tempfile,json,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from services import Store,ROOT
from main import Bridge
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([])
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    store=Store(temporary,'ui-v22');store.settings.update(setup_completed=True,guide_dismissed=True,library='')
    # Existing covers are read only; the test changes only its temporary library.
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8')) if (ROOT/'data/library.json').exists() else []
    covers=[game.get('cover','') for game in originals if game.get('cover')]
    destination=store.root/'covers';destination.mkdir()
    for cover in covers:
        source=ROOT/'data/covers'/Path(cover).name
        if source.is_file():shutil.copy2(source,destination/source.name)
    for i in range(30):
        store.games.append({'id':str(i),'name':f'Game {i:02}','installed':True,'cover':covers[i%len(covers)] if covers else '', 'favorite':i<3,'series':'Series' if i<2 else '', 'groups':['RPG'] if i<5 else [],'last_played':'2026-10-09T00:00:00+00:00' if i<4 else ''})
        store.local[str(i)]={'installed':True}
    store.groups=['RPG'];backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects()
    root=engine.rootObjects()[0];QTest.qWait(400)
    grid=root.findChild(QObject,'gameGrid');assert grid.property('count')==30
    grid.setProperty('contentY',600);QTest.qWait(50)
    def idle():
        for _ in range(600):
            QTest.qWait(25)
            if not backend.busy:break
        assert not backend.busy,backend.status
    backend.toggleFavorite('20');idle();assert abs(grid.property('contentY')-600)<2
    root.setProperty('libraryMode','favorites');QTest.qWait(80);assert grid.property('count')==4
    root.setProperty('libraryMode','recent');QTest.qWait(80);assert grid.property('count')==4
    root.setProperty('libraryMode','series');QTest.qWait(80);assert grid.property('count')==2
    root.setProperty('groupFilter','RPG');root.setProperty('libraryMode','group');QTest.qWait(80);assert grid.property('count')==5
    root.setProperty('libraryMode','all');QTest.qWait(80)
    screenshot=ROOT/'test-data/v22-preview';screenshot.mkdir(exist_ok=True)
    root.grabWindow().save(str(screenshot/'library-dark.png'))
    backend.saveSettings({'theme':'light'});idle();QTest.qWait(100)
    assert root.property('color').name()=='#f1f3f5';root.grabWindow().save(str(screenshot/'library-light.png'))
    for name in ('midnight','violet','dark'):backend.saveSettings({'theme':name});idle()
    QMetaObject.invokeMethod(root,'openImport');QTest.qWait(100)
    importer=root.findChild(QObject,'importWindow');tabs=importer.findChild(QObject,'importTabs');tabs.setProperty('currentIndex',2);QTest.qWait(60)
    source=importer.findChild(QObject,'coverSource');assert source.property('currentText')=='Steam Store' and source.property('width')>=190
    backend._imports=[{'id':'duplicate','name':'A duplicate','platform':'local','score':1,'duplicate_id':'old','duplicate_reason':'already imported','exe':'old.exe'}, {'id':'fresh','name':'Z new','platform':'local','score':.9,'exe':'new.exe'}];backend.changed.emit();QTest.qWait(100)
    rows=importer.property('orderedCandidates').toVariant();assert rows[0]['id']=='fresh'
    importer.grabWindow().save(str(screenshot/'import.png'));QMetaObject.invokeMethod(importer,'hide')
    manager=root.findChild(QObject,'libraryManager');QMetaObject.invokeMethod(manager,'openManager');idle()
    assert len(backend.organizerResults)==30;manager.grabWindow().save(str(screenshot/'groups.png'));QMetaObject.invokeMethod(manager,'hide')
    personal=root.findChild(QObject,'personalization');QMetaObject.invokeMethod(personal,'openPersonalization');QTest.qWait(100);personal.grabWindow().save(str(screenshot/'themes.png'))
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: library filters, favorite keeps scroll, four live themes, full source names, new imports first, category preview')
