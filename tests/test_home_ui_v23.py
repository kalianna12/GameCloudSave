"""Real discovery shelves, tag search, platform/source filters and scroll preservation."""
from pathlib import Path
import sys,tempfile,json,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[];qInstallMessageHandler(lambda kind,context,message:messages.append(message))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'home-test');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',theme='dark')
    originals=json.loads((ROOT/'data/library.json').read_text(encoding='utf-8'));covers=[game['cover'] for game in originals if game.get('cover')]
    (store.root/'covers').mkdir()
    for cover in covers:
        source=ROOT/'data/covers'/Path(cover).name
        if source.is_file():shutil.copy2(source,store.root/'covers'/source.name)
    for i in range(32):
        tags=['视觉小说','恋爱'] if i<16 else ['射击','合作']
        store.games.append({'id':str(i),'name':f'Game {i:02}','cover':covers[i%len(covers)],'platform':'steam' if i%2==0 else 'local','import_source':'playnite' if i<25 else 'folder','tags':tags,'series':'Pair' if i<2 else 'Singleton' if i==2 else '', 'last_played':'2026-10-09T00:00:00Z' if i<3 else ''})
        store.local[str(i)]={'installed':True}
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];QTest.qWait(450);home=root.findChild(QObject,'libraryHome');view=root.findChild(QObject,'libraryHomeList');grid=root.findChild(QObject,'gameGrid');search=root.findChild(QObject,'search')
    assert home.property('visible') and view.property('count')>=6
    def visual(item,name):
        if item.objectName()==name:return item
        for child in item.childItems():
            found=visual(child,name)
            if found:return found
    shelf=visual(root.contentItem(),'shelf-recent');assert shelf is not None;shelf.setProperty('contentX',160);QTest.qWait(50)
    QMetaObject.invokeMethod(home,'scrollBy',Q_ARG('QVariant',550));QTest.qWait(150);before=view.property('contentY');assert before>400
    backend.toggleFavorite('8')
    for _ in range(400):
        QTest.qWait(25)
        if not backend.busy:break
    assert abs(view.property('contentY')-before)<2
    assert abs(shelf.property('contentX')-160)<2
    series=root.property('seriesNames').toVariant();assert series==['Pair'],series
    search.setProperty('text','#恋爱');QTest.qWait(180);assert grid.property('visible') and grid.property('count')==16
    root.setProperty('platformFilter','steam');QTest.qWait(80);assert grid.property('count')==8
    search.setProperty('text','');QTest.qWait(180);assert home.property('visible')
    root.setProperty('libraryMode','all');root.setProperty('importSourceFilter','folder');QTest.qWait(100);assert grid.property('count')==3
    root.setProperty('platformFilter','all');root.setProperty('importSourceFilter','all');root.setProperty('libraryMode','series');QTest.qWait(100);assert grid.property('count')==2
    root.setProperty('libraryMode','home');QTest.qWait(100);view.setProperty('contentY',0)
    output=ROOT/'test-data/v23-ui';output.mkdir(exist_ok=True);root.grabWindow().save(str(output/'home-dark.png'));view.setProperty('contentY',700);QTest.qWait(100);root.grabWindow().save(str(output/'home-lower.png'))
    root.setWidth(900);root.setHeight(650);QTest.qWait(100);root.grabWindow().save(str(output/'home-small.png'))
    backend.saveSettings({'theme':'light'})
    for _ in range(400):
        QTest.qWait(25)
        if not backend.busy:break
    root.setWidth(1440);root.setHeight(940);QTest.qWait(120);root.grabWindow().save(str(output/'home-light.png'))
    assert not any('TypeError' in message or 'ReferenceError' in message or 'Binding loop' in message for message in messages),messages
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: home shelves, stable vertical position, tag and platform/source filters, no singleton series, 900px/light theme, QML clean')
