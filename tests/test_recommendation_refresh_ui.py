"""Refreshing one shelf must not reload artwork or disturb other shelves and navigation."""
from pathlib import Path
import sys,tempfile,threading,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def wait(condition,reason):
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.005)
        if condition():return
    raise AssertionError(reason)
def data(obj,name):
    value=obj.property(name);return value.toVariant() if hasattr(value,'toVariant') else value
def invoke(obj,name,*args):
    return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'refresh-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='')
    cover=store.root/'covers/fixture.png';cover.parent.mkdir(exist_ok=True)
    image=QImage(400,240,QImage.Format_RGB32);image.fill(QColor('#476286'));image.save(str(cover))
    for number in range(8):
        store.games.append({'id':str(number),'name':'Local '+str(number),'cover':cover.name,'last_played':str(20-number),'category':'Other','tags':[]})
    backend=Bridge(store);feed=backend.recommendations;feed._started=True;feed._providers=('steam','xbox')
    feed._rows={'steam':[],'xbox':[]}
    for category in ('new','sale','popular','xbox'):
        provider='xbox' if category=='xbox' else 'steam'
        for number in range(10):
            feed._rows[provider].append({'id':'store:'+provider+':'+str(number),'provider':provider,'category':category,'name':category+' '+str(number),
                'images':[],'coverUrl':QUrl.fromLocalFile(str(cover)).toString(),'price':'¥10','platformLabel':provider,
                'page':'https://store.steampowered.com/app/'+str(number)+'/' if provider=='steam' else 'https://www.xbox.com/zh-HK/games/store/-/ABCDEF123456'})
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];window.resize(1440,1040);QTest.qWait(200)
    home=window.findChild(QObject,'libraryHome');view=window.findChild(QObject,'libraryHomeList')
    def find(name):return next(item for item in walk(window.contentItem()) if item.objectName()==name)
    recent=find('shelf-recent');recent.setProperty('currentIndex',2);recent.setProperty('contentX',140)
    home.setProperty('focusedSection',1);home.forceActiveFocus();view.setProperty('contentY',120);QTest.qWait(60)
    new=find('shelf-store:new');new.setProperty('currentIndex',6);new.setProperty('contentX',600)
    QTest.qWait(80);position=view.property('contentY');horizontal=new.property('contentX')
    changes=[];hero=find('recentHero');hero.gameChanged.connect(lambda:changes.append('hero reset'))
    local_section=recent.parent();local_section.sectionChanged.connect(lambda:changes.append('local section reset'))
    visible_tiles=[item for item in walk(window.contentItem()) if item.inherits('QQuickAbstractButton') and (data(item,'record') or {}).get('category')=='new']
    artwork_changes=[]
    for tile in visible_tiles:
        for item in walk(tile):
            if item.inherits('QQuickImage'):item.sourceChanged.connect(lambda:artwork_changes.append('image reloaded'))
    before={section['id']:section for section in feed.sections}
    entered=threading.Event();gate=threading.Event()
    def fetch(provider):
        assert provider=='steam';entered.set();assert gate.wait(6)
        return [{**row,'price':'¥9' if row['category']=='new' else '¥999'} for row in feed._rows['steam']]
    try:
        with patch('recommendation_sources.fetch',side_effect=fetch) as called:
            QMetaObject.invokeMethod(find('refresh-store:new'),'click')
            wait(entered.is_set,'Refresh button did not start its source')
            states={s['id']:s for s in feed.sections}
            assert states['store:new']['loading']
            assert all(not states[name]['loading'] for name in ('store:sale','store:popular','store:xbox'))
            assert abs(view.property('contentY')-position)<1
            gate.set();wait(lambda:not feed.loading,'Scoped refresh did not finish');QTest.qWait(100)
            called.assert_called_once_with('steam')
        after={section['id']:section for section in feed.sections}
        for name in ('store:sale','store:popular','store:xbox'):assert after[name]==before[name],name
        assert all(row['price']=='¥9' and row.get('coverUrl') for row in after['store:new']['items'])
        assert not changes,changes
        assert not artwork_changes,artwork_changes
        assert home.property('focusedSection')==1 and new.property('currentIndex')==6
        assert abs(new.property('contentX')-horizontal)<1 and abs(view.property('contentY')-position)<1
        assert recent.property('currentIndex')==2 and abs(recent.property('contentX')-140)<1
        errors=[m for m in messages if any(word in m for word in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))]
        assert not errors,errors
    finally:
        gate.set();backend.shutdownWatch();feed._pool.shutdown(wait=True);feed._images.shutdown(wait=True);backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: clicking one shelf refreshes only it; other sections, covers, selected games and both scroll axes remain stable')
