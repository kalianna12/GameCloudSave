"""Exercise interaction during delayed matching, cancellation and inline setup."""
from pathlib import Path
import sys,tempfile,time,json,threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from single_instance import SingleInstance
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,QTimer,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'responsive');store.settings.update(setup_completed=True,watch=False,guide_dismissed=True,ai_enabled=True)
    for index in range(52):
        store.games.append({'id':str(index),'name':f'Game {index:02}','cover':'','tags':['合作']})
        store.local[str(index)]={'installed':True}
    bridge=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',bridge)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];QTest.qWait(250)
    matcher=root.findChild(QObject,'matchWindow');QMetaObject.invokeMethod(matcher,'openMatcher',Q_ARG('QVariant','0'))
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(20)
    def slow_match(ident,progress,cancel):
        for _ in range(15):
            if cancel.wait(.08):break
            progress({'id':ident,'name':'Game '+ident,'status':'running','phase':'DeepSeek · 比较目录','candidates':[],'checked':[]})
        return {'id':ident,'name':'Game '+ident,'status':'notfound','candidates':[],'checked':[]}
    with patch.object(store,'match_game',side_effect=slow_match):
        bridge.matchGames([str(i) for i in range(52)])
        QTest.qWait(300)
        assert bridge.matching and bridge.matchProgress['total']==52
        selector=matcher.findChild(QObject,'matchGameSelector');selector.setProperty('currentIndex',20)
        matcher.setProperty('selectedId','20');assert matcher.property('selectedId')=='20'
        root.findChild(QObject,'search').setProperty('text','#合作');QTest.qWait(180)
        assert root.findChild(QObject,'gameGrid').property('count')==52
        assert matcher.findChild(QObject,'matchProgressBar').property('visible')
        assert matcher.findChild(QObject,'stopMatching').property('enabled')
        for _ in range(100):QTest.qWait(20)
        assert bridge.matchProgress['done']>0,bridge.matchProgress
        start=time.monotonic();bridge.cancelMatching()
        assert bridge.matchProgress['cancelled']
        while bridge.busy and time.monotonic()-start<3:QTest.qWait(25)
        assert not bridge.busy and time.monotonic()-start<3
        assert len(ticks)>30 and max(b-a for a,b in zip(ticks,ticks[1:]))<.35
    timer.stop();matcher.hide()
    QMetaObject.invokeMethod(root,'openSetup');wizard=root.findChild(QObject,'setupWizard');wizard.setProperty('step',3)
    # A fake directory response exercises the real inline browser without network dependence.
    bridge.complete('list',{'path':'Drive','entries':[{'Name':'Saves','IsDir':True,'Size':-1}]},'')
    wizard.setProperty('browsingCloud',True);QTest.qWait(100)
    assert wizard.findChild(QObject,'wizardCloudFolders').property('count')==1
    assert len([w for w in app.topLevelWindows() if w.isVisible() and w.title()=='云端存储'])==0
    root.findChild(QObject,'platformFilter').setProperty('currentIndex',1)
    assert root.findChild(QObject,'platformFilter').property('height')==38
    output=ROOT/'test-data/v231';output.mkdir(exist_ok=True)
    wizard.grabWindow().save(str(output/'wizard-cloud.png'));wizard.hide();root.findChild(QObject,'search').setProperty('text','');QTest.qWait(180)
    root.grabWindow().save(str(output/'home.png'))
    instance=SingleInstance(directory);assert instance.acquire()
    activated=[];instance.activated.connect(lambda:activated.append(True))
    duplicate=SingleInstance(directory);assert not duplicate.acquire();QTest.qWait(100);assert activated
    instance.release();assert duplicate.acquire();duplicate.release()
    bridge.timer.stop();bridge.pool.shutdown(wait=True);shiboken6.delete(engine)
    errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','is not a type'))]
    assert not errors,errors
    report={'passed':True,'library_count':52,'heartbeat_max_ms':round(max(b-a for a,b in zip(ticks,ticks[1:]))*1000,1),'cancelled':True,'inline_cloud':True,'single_instance':True}
    (output/'responsive.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))
