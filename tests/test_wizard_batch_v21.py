"""Real QML wizard skipping and all-row batch confirmation/backup."""
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
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
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'wizard-test');store.settings['library']=''
    for i in range(18):
        game_id=str(i);save=Path(directory)/('Game'+game_id)/'Save';save.mkdir(parents=True);(save/'slot1.sav').write_text('fixture')
        store.games.append({'id':game_id,'name':'Game '+game_id,'cover':''})
        store.local[game_id]={'installed':True}
        store.match_report.append({'id':game_id,'name':'Game '+game_id,'status':'review','candidates':[{'path':str(save),'confidence':.95,'files':['slot1.sav']}],'checked':[]})
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects()
    root=engine.rootObjects()[0];wizard=root.findChild(QObject,'setupWizard');QTest.qWait(100)
    assert wizard.property('visible') and wizard.property('step')==0
    QMetaObject.invokeMethod(wizard,'advance',Q_ARG('QVariant',False))
    for _ in range(6):QMetaObject.invokeMethod(wizard,'advance',Q_ARG('QVariant',True))
    assert wizard.property('step')==7
    values=wizard.property('skipped').toVariant() if hasattr(wizard.property('skipped'),'toVariant') else wizard.property('skipped')
    assert all(values.get(str(i),values.get(i)) for i in range(1,7))
    backend.saveSetup({'setup_completed':True,'guide_dismissed':True})
    for _ in range(600):
        QTest.qWait(25)
        if not backend.busy:break
    assert store.settings['setup_completed']
    QMetaObject.invokeMethod(wizard,'hide');QMetaObject.invokeMethod(root,'openBatch');QTest.qWait(200)
    batch=root.findChild(QObject,'batchWindow');QMetaObject.invokeMethod(batch,'selectAll')
    selections=[{'id':row['id'],'path':row['candidates'][0]['path']} for row in store.match_report]
    view=batch.findChild(QObject,'batchGameList');view.setProperty('contentY',550);batch.setProperty('savedY',550)
    backend.applyMatches(selections)
    for _ in range(600):
        QTest.qWait(25)
        if not backend.busy:break
    assert all(store.local[item['id']].get('save_dir')==item['path'] for item in selections), backend.status
    assert abs(view.property('contentY')-550)<2
    with patch.object(store,'match_game',side_effect=AssertionError('Confirmed backup must not rematch')):
        backend.backupConfigured(['0','1'],False)
        for _ in range(600):
            QTest.qWait(25)
            if not backend.busy:break
    assert len(store.history('0'))==1 and len(store.history('1'))==1
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
    import gc;gc.collect()
print('PASS: all wizard steps/skip/summary/save, all-row batch confirmation retains scroll, backup skips rematching')
