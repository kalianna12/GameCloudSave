"""Opt-in anonymous storefront/cover smoke test using an isolated empty library."""
from pathlib import Path
import sys,tempfile,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression,qmlContext
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

def wait_for_images(window):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.008)
        images=[item for item in walk(window.contentItem()) if item.objectName()=='storeArtwork' and item.property('source').toString()]
        statuses=[QQmlExpression(qmlContext(item),item,'Number(status)').evaluate()[0] for item in images]
        if statuses and all(status==1 for status in statuses):return len(statuses)
    raise AssertionError(('Actual recommendation images not ready',statuses,messages))

def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'live-recommendations');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='')
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];window.resize(1440,1040);started=time.monotonic();first=None
    try:
        backend.recommendations.start();deadline=time.monotonic()+65
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.008)
            sections=backend.recommendations.sections
            rows=[row for section in sections for row in section['items']]
            if rows and first is None:first=round(time.monotonic()-started,2);print('First catalog visible: '+str(first)+'s',flush=True)
            if rows and not backend.recommendations.loading and all(row.get('coverUrl') for row in rows):break
        rows=[row for section in backend.recommendations.sections for row in section['items']]
        QTest.qWait(150)
        home=window.findChild(QObject,'libraryHome');backend.setControllerMode(True);invoke(home,'focusFirst')
        ready=[]
        for i in range(len(backend.recommendations.sections)):
            if i:invoke(home,'navigateFocus','down')
            assert home.property('focusedSection')==i
            QTest.qWait(150);ready.append(wait_for_images(window))
        before={s['id']:s for s in backend.recommendations.sections}
        backend.recommendations.refreshSection('store:new')
        until=time.monotonic()+35
        while backend.recommendations.loading and time.monotonic()<until:app.processEvents();time.sleep(.008)
        assert not backend.recommendations.loading
        after={s['id']:s for s in backend.recommendations.sections}
        for key in ('store:sale','store:popular','store:xbox'):assert before[key]==after[key],key
        invoke(home,'focusFirst');QTest.qWait(150);ready.append(wait_for_images(window))
        report={'first_catalog_seconds':first,'elapsed':round(time.monotonic()-started,2),
                'sections':[{ 'title':s['title'],'count':len(s['items']),'covers':sum(bool(row.get('coverUrl')) for row in s['items'])} for s in backend.recommendations.sections],
                'status':backend.recommendations.status,'actual_images_ready_per_scroll':ready,'scoped_refresh_kept_other_sections':True,'library_unchanged':store.games==[]}
        output=ROOT/'test-data/recommendations';output.mkdir(exist_ok=True)
        (output/'live-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        QTest.qWait(250);window.grabWindow().save(str(output/'live-dark.png'))
        backend.saveSettings({'theme':'light'})
        while backend.busy:app.processEvents();time.sleep(.005)
        window.resize(900,700);QTest.qWait(250);window.grabWindow().save(str(output/'live-light-small.png'))
        print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
        assert {row['provider'] for row in rows}=={'steam','xbox'},'Both real storefronts must return games'
        assert all(s['items'] for s in backend.recommendations.sections)
        assert sum(bool(row.get('coverUrl')) for row in rows)>=len(rows)*.8,'Too many covers failed'
        assert not any(any(word in msg for word in ('TypeError','ReferenceError','Binding loop')) for msg in messages),messages
    finally:
        backend.shutdownWatch();backend.recommendations._pool.shutdown(wait=True);backend.recommendations._images.shutdown(wait=True);backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: live Steam/Xbox recommendations and cached covers; isolated data only, no browser navigation')
