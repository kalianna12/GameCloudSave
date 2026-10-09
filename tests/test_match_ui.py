"""Regression for match list position and explicit batch confirmation."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QMetaObject,QUrl,Q_ARG,Q_RETURN_ARG
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from services import Store,ROOT
from main import Bridge
import shiboken6

QQuickStyle.setStyle('Material')
app=QApplication([])
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'match-ui-test')
    store.settings['guide_dismissed']=True
    store.settings['setup_completed']=True
    for i in range(30):
        ident=str(i); path=Path(directory)/('Game'+ident)/'savedata'; path.mkdir(parents=True)
        (path/'slot1.sav').write_bytes(b'test')
        store.games.append({'id':ident,'name':'Game '+ident,'cover':''})
        store.match_report.append({'id':ident,'name':'Game '+ident,'status':'review','candidates':[{'path':str(path),'confidence':.9,'fileSummary':'slot1.sav','files':['slot1.sav']}],'checked':[]})
    backend=Bridge(store)
    engine=QQmlApplicationEngine(); engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects()
    root=engine.rootObjects()[0]; window=root.findChild(QObject,'matchWindow')
    QMetaObject.invokeMethod(window,'openMatcher',Q_ARG('QVariant','20'))
    QTest.qWait(350)
    weight=window.findChild(QObject,'matchAiWeight');assert weight.property('value')==75
    weight.setProperty('value',90)
    returned=QMetaObject.invokeMethod(window,'aiValues',Q_RETURN_ARG('QVariant'))
    assert returned.toVariant()['match_ai_weight']==90
    view=window.findChild(QObject,'matchResultList')
    view.setProperty('contentY',850); QTest.qWait(100)
    before=view.property('contentY')
    path=store.match_report[20]['candidates'][0]['path']
    backend.applyMatch('20',path)
    for _ in range(60):
        QTest.qWait(50)
        if not backend.busy:break
    assert store.local['20']['save_dir']==path
    assert abs(view.property('contentY')-before)<2,(before,view.property('contentY'))
    assert window.property('selectedId')=='20'
    selections=[{'id':str(i),'path':store.match_report[i]['candidates'][0]['path']} for i in (21,22)]
    backend.applyMatches(selections)
    for _ in range(60):
        QTest.qWait(50)
        if not backend.busy:break
    assert all(store.local[item['id']]['save_dir']==item['path'] for item in selections)
    assert abs(view.property('contentY')-before)<2
    # Reject all before modifying any selection when one candidate has disappeared.
    valid=store.match_report[23]['candidates'][0]['path']
    backend.applyMatches([{'id':'23','path':valid},{'id':'24','path':str(Path(directory)/'unverified')}])
    for _ in range(60):
        QTest.qWait(50)
        if not backend.busy:break
    assert '23' not in store.local and '24' not in store.local
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: single and batch confirmation retain scroll/selection; invalid batch does not apply valid subset')
