"""Actual hover, controller selection, ring colors, persistent hide and click-through."""
from pathlib import Path
import json,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QPoint,qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
from services import ROOT,Store
from main import Bridge

QQuickStyle.setStyle('Material');app=QApplication([]);app.setQuitOnLastWindowClosed(False);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=70):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def badge(item):return item.findChild(QObject,'achievementBadge')
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='badge-') as temp:
    root=Path(temp);store=Store(root/'data','fixture')
    store.settings.update(setup_completed=True,watch=False,recommendations_enabled=False,navigation_volume=0,animations=False)
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    source=b'''
import QtQuick
import QtQuick.Controls
ApplicationWindow {
    id: host
    width: 900;height: 500;visible: true;color: Theme.background
    property bool chosen: false
    property var sample: ({id:"fixture",name:"Local achievement test",coverUrl:"",isNew:true})
    GameCard { objectName:"card";x:20;y:20;width:160;height:320;game:host.sample;selected:host.chosen }
    GameTile { objectName:"tile";x:220;y:20;width:160;height:280;game:host.sample;selected:host.chosen }
    BookCover { objectName:"book";x:420;y:20;width:180;height:340;game:host.sample;selected:host.chosen }
    Row { x:20;y:385;spacing:30
        Repeater { model:["0","25","50","75","100"]
            Column { required property string modelData;spacing:5
                AchievementBadge { gameId:parent.modelData;revealed:true }
                Label { text:parent.modelData+"%";color:Theme.text }
            }
        }
    }
}
'''
    fixture=root/'badge-test.qml';fixture.write_bytes(('import "'+QUrl.fromLocalFile(str(ROOT/'ui')).toString()+'"\n').encode()+source)
    engine.load(QUrl.fromLocalFile(str(fixture)));assert engine.rootObjects(),messages
    window=engine.rootObjects()[0]
    try:
        spin(150);manager=backend.achievements
        summaries={str(i):dict(total=100,unlocked=i) for i in (0,25,50,75,100)};summaries['fixture']=dict(total=96,unlocked=33)
        manager.receiveCatalog(dict(summaries=summaries,rows=[],recent=[]));spin()
        window.requestActivate();QTest.mouseMove(window,QPoint(850,350));spin()
        items=[window.findChild(QObject,name) for name in ('card','tile','book')]
        assert all(not badge(item).isVisible() for item in items)
        markers=[item.findChild(QObject,'newGameBadge') for item in items];positions=[m.y() for m in markers]
        for item,point in zip(items,((80,90),(280,90),(490,140))):
            QTest.mouseMove(window,QPoint(*point));spin()
            assert badge(item).isVisible(),(item.objectName(),messages)
            QTest.mouseMove(window,QPoint(850,350));spin();assert not badge(item).isVisible()
        backend.setControllerMode(True);window.setProperty('chosen',True);spin()
        assert all(badge(item).isVisible() for item in items)
        store.settings['achievement_badges']='hidden';backend.settingsChanged.emit();spin()
        assert all(not badge(item).isVisible() for item in items)
        assert [m.y() for m in markers]==positions
        window.setProperty('chosen',False);store.settings['achievement_badges']='always';backend.settingsChanged.emit();spin()
        assert all(badge(item).isVisible() for item in items)
        badges=[item for item in walk(window.contentItem()) if item.objectName()=='achievementBadge']
        colors={b.property('gameId'):b.property('ringColor').name() for b in badges if b.property('gameId') in summaries and b.property('gameId')!='fixture'}
        assert len(set(colors.values()))==5,colors
        output=ROOT/'build/achievement-badge-review';output.mkdir(exist_ok=True)
        window.grabWindow().save(str(output/'colors-and-covers.png'))
        # Badge remains purely visual; clicking its area still reaches the game cover.
        from PySide6.QtCore import Qt
        events=[];items[0].settingsRequested.connect(lambda:events.append('settings'))
        backend.setControllerMode(False);QTest.mouseClick(window,Qt.LeftButton,pos=QPoint(40,70));spin()
        assert events==['settings'],events
        assert not [m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign'))],messages
        (output/'report.json').write_text(json.dumps(dict(colors=colors,mouse_hover=True,controller_focus=True,hidden=True,click_through=True),indent=2),encoding='utf-8')
        print('PASS: actual mouse hover with animations off, controller selection, always/hidden, stable new markers, five ring colors, click-through')
    finally:
        window.close();backend.shutdownWatch()
        for pool in (backend.achievements.batch_pool,backend.achievements.network,backend.achievements.icons,backend.achievements.pool,backend.pool):pool.shutdown(wait=True)
        shiboken6.delete(engine)
