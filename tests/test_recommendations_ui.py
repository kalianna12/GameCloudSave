"""Slow catalogs do not block Qt; store cards navigate safely, close and theme correctly."""
from pathlib import Path
import sys,tempfile,threading,time,json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from recommendation_sources import steam_rows
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QTimer,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression,qmlContext
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication.instance() or QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(condition,reason):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.005)
        if condition():return
    raise AssertionError(reason+': '+repr(backend.recommendations.sections)+'; '+repr(messages))
def invoke(obj,name,*args):
    result=QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
    return result.toVariant() if hasattr(result,'toVariant') else result
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def value(obj,name):
    result=obj.property(name);return result.toVariant() if hasattr(result,'toVariant') else result

def image_status(obj):return QQmlExpression(qmlContext(obj),obj,'Number(status)').evaluate()[0]
def rows(provider):
    if provider=='steam':
        item={'id':1,'type':0,'name':'Store fixture','windows_available':True,'final_price':990,'currency':'CNY','discount_percent':50,'header_image':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1/header.jpg'}
        return steam_rows({'new_releases':{'items':[{**item,'id':3}]},'specials':{'items':[item]},'top_sellers':{'items':[{**item,'id':2}]}})
    return [{'id':'store:xbox:ABCDEF123456','name':'Xbox fixture','provider':'xbox','category':'xbox','images':[],
             'platformLabel':'Xbox 港区','page':'https://www.xbox.com/zh-HK/games/store/-/ABCDEF123456','price':'HK$10','discount':0}]

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'recommend-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='')
    # No library entries: a new user must still be able to browse recommendations.
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];home=window.findChild(QObject,'libraryHome');view=window.findChild(QObject,'libraryHomeList')
    gate=threading.Event();entered=threading.Event();ticks=[];threads=[];image_requests=[]
    timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    picture=Path(directory)/'fixture.png';image=QImage(240,360,QImage.Format_RGB32);image.fill(QColor('#5c7196'));image.save(str(picture));raw=picture.read_bytes()
    def fetch(provider):
        threads.append(threading.get_ident())
        if provider=='xbox':entered.set();assert gate.wait(8)
        return rows(provider)
    def request(*args):threads.append(threading.get_ident());image_requests.append(args[0]);return raw
    try:
        with patch('recommendation_sources.fetch',side_effect=fetch),patch('recommendation_sources.request',side_effect=request):
            backend.recommendations.start()
            spin(lambda:entered.is_set() and any(s['id']=='store:sale' for s in backend.recommendations.sections),'Fast provider blocked')
            spin(lambda:len(ticks)>5,'Qt heartbeat stalled');assert backend.recommendations.loading
            assert home.property('visible') and not backend.busy
            gate.set();spin(lambda:not backend.recommendations.loading,'Catalog did not finish')
            spin(lambda:all(row.get('coverUrl') for s in backend.recommendations.sections for row in s['items'] if row['provider']=='steam'),'Images not delivered')
            assert len(image_requests)==1,'Shared artwork must download only once'
            assert all(ident!=threading.get_ident() for ident in threads)
            assert len(backend.recommendations.sections)==4
            window.requestActivate();spin(lambda:window.isActive(),'Fixture window not active')
            backend.setControllerMode(True);invoke(home,'focusFirst');QTest.qWait(100)
            with patch('recommendations.QDesktopServices.openUrl',return_value=True) as opened:
                result=invoke(window,'controllerInput','activate');assert opened.call_count==1,(result,home.property('focusedSection'),invoke(home,'selectedGame'),window.property('homeVisible'),window.property('active'),backend.popupActive(),messages)
                invoke(window,'controllerInput','favorite');invoke(window,'controllerInput','history');invoke(window,'controllerInput','launch')
                assert store.games==[] and not backend.busy,'Store cards must not trigger local game actions'
                tile=next(item for item in walk(window.contentItem()) if (value(item,'record') or {}).get('id')=='store:steam:1' and item.inherits('QQuickAbstractButton'))
                QMetaObject.invokeMethod(tile,'click');assert opened.call_count==2
                # A filename that Qt has already failed to read must recover in-place.
                feed=backend.recommendations
                row=next(r for r in feed._rows['steam'] if r['id']=='store:steam:1')
                art=tile.findChild(QObject,'storeArtwork')
                spin(lambda:image_status(art)==1,'Async catalog/artwork update did not reach the actual image')
                cached=Path(QUrl(row['coverUrl']).toLocalFile());cached.unlink()
                broken=QUrl.fromLocalFile(str(cached));broken.setQuery('v=missing')
                feed._rows['steam']=[{**r,'coverUrl':broken.toString()} if r is row else r for r in feed._rows['steam']]
                feed._revisions['sale']+=1;feed.changed.emit()
                spin(lambda:image_status(art)==3,'Missing file did not enter Image.Error')
                retry=tile.findChild(QObject,'retryStoreArtwork');assert retry.property('visible')
                QMetaObject.invokeMethod(retry,'click')
                spin(lambda:image_status(art)==1,'Repaired artwork did not become Image.Ready')
                assert cached.exists() and len(image_requests)==2 and opened.call_count==2
                assert not retry.property('visible')
            output=ROOT/'test-data/recommendations';output.mkdir(exist_ok=True)
            window.grabWindow().save(str(output/'fixture-dark.png'))
            backend.saveSettings({'theme':'light'});spin(lambda:not backend.busy,'Theme save stalled')
            window.resize(900,650);QTest.qWait(100);window.grabWindow().save(str(output/'fixture-light-small.png'))
            backend.saveSettings({'library_design':'cinema'});spin(lambda:not backend.busy,'Layout save stalled');QTest.qWait(150)
            button=window.findChild(QObject,'recommendationsControl');assert button.property('visible')
            QMetaObject.invokeMethod(button,'click');QTest.qWait(150)
            dialog=window.findChild(QObject,'recommendationDialog');assert dialog.property('visible')
            with patch('recommendations.QDesktopServices.openUrl',return_value=True) as opened:
                invoke(dialog,'controllerInput','activate');assert opened.call_count==1
            invoke(dialog,'controllerInput','back');spin(lambda:not dialog.property('visible'),'Dialog did not close')
            backend.saveSettings({'recommendations_enabled':False});spin(lambda:not backend.busy,'Disable save stalled')
            QTest.qWait(100);assert backend.recommendations.sections==[] and not button.property('visible')
            assert not any(s['kind']=='store' for s in value(window,'homeRows'))
        errors=[message for message in messages if any(word in message for word in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))]
        assert not errors,errors
    finally:
        gate.set();timer.stop();backend.shutdownWatch();backend.recommendations._pool.shutdown(wait=True);backend.recommendations._images.shutdown(wait=True);backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: concurrent catalogs/images, Qt heartbeat, empty library, safe mouse/controller links, alternate-layout dialog, theme/900px and disable')
