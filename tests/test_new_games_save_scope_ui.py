"""New games across layouts, scoped searches, enrichment follow-up, stable grid updates."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from input_feedback import InputFeedback
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=80):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.002)
def wait(condition):
    end=time.monotonic()+10
    while time.monotonic()<end:
        spin(10)
        if condition():return
    raise AssertionError(messages[-15:])
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',arg) for arg in args))
def value(obj,name):
    result=obj.property(name);return result.toVariant() if hasattr(result,'toVariant') else result
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as folder:
    store=Store(folder,'new-save-ui');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,match_workers=1,library='',playnite='')
    now=datetime.now(timezone.utc)
    store.games=[{'id':str(i),'name':f'Game {i:02}','cover':'','tags':['动作'],'category':'动作冒险','added_at':(now-timedelta(days=5 if i<54 else 0)).isoformat()} for i in range(60)]
    store.local={g['id']:{'installed':True} for g in store.games};store.local['0']['save_dir']=str(Path(folder)/'confirmed')
    store.match_report=[{'id':'0','name':'Game 00','status':'applied','candidates':[],'applied_path':store.local['0']['save_dir']}]
    backend=Bridge(store);feedback=InputFeedback(app,backend,ROOT,audio_muted=True);backend.input_feedback=feedback
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages;root=engine.rootObjects()[0];root.resize(1440,1000);root.requestActivate();spin(350)
    called=[]
    def match(ident,*args):
        called.append(ident)
        return {'id':ident,'name':'Game '+ident,'status':'notfound','message':'Fixture','candidates':[],'checked':[],'aliases':[],'scan_version':4}
    try:
        rows=value(root,'localHomeRows');new=next(row for row in rows if row['id']=='new')
        assert len(new['items'])==6 and all(g['isNew'] for g in new['items'])
        assert sum(g['isNew'] for g in backend.games)==6
        # Home post-import action scopes itself to the six new games.
        button=next(item for item in walk(root.contentItem()) if item.objectName()=='newGamesSaveSearch' and item.isVisible())
        QMetaObject.invokeMethod(button,'click');spin(150)
        matcher=root.findChild(QObject,'matchWindow');assert matcher and matcher.isVisible(),messages
        assert set(value(matcher,'scopeTargets'))=={str(i) for i in range(54,60)}
        with patch.object(store,'match_game',side_effect=match):
            QMetaObject.invokeMethod(matcher.findChild(QObject,'findScopedSaves'),'click');wait(lambda:not backend.busy);spin(120)
            assert set(called)=={str(i) for i in range(54,60)},called
            assert all(row.get('completed') for row in store.match_report if row['id']!='0')
            scope=matcher.findChild(QObject,'saveSearchScope');scope.setProperty('currentIndex',1);spin(40)
            assert not set(value(matcher,'scopeTargets')).intersection(called)
            called.clear();QMetaObject.invokeMethod(matcher.findChild(QObject,'findAllSaves'),'click');wait(lambda:not backend.busy);spin(120)
            assert len(called)==60 and '0' in called
        assert store.local['0']['save_dir']==str(Path(folder)/'confirmed')
        matcher.hide();root.requestActivate();spin(100)
        # Applying metadata offers a targeted next step rather than a whole-library scan.
        window=root.findChild(QObject,'enrichmentWindow')
        invoke(window,'openFor',['54'],{'dates':True,'tags':False,'covers':False,'backgrounds':False,'use_ai':False},False)
        with patch('library_enrichment.cached_lookup',return_value={'release_date':'2020-07-15','release_date_source':'Steam'}):
            invoke(window,'startQuery');wait(lambda:not backend.busy);spin(80)
        backend.applyEnrichment(['54']);wait(lambda:not backend.busy);spin(80)
        followup=window.findChild(QObject,'enrichmentFindSaves');assert followup.isVisible()
        QMetaObject.invokeMethod(followup,'click');spin(100)
        assert value(matcher,'followupIds')==['54'] and value(matcher,'scopeTargets')==['54']
        matcher.hide();root.requestActivate();spin(100)
        # Visual sidebar order and controller order match; all layouts share new filtering.
        backend.setControllerMode(True);root.findChild(QObject,'navSeries').forceActiveFocus()
        dispatch(app,root,backend,'down');spin(90)
        assert root.activeFocusItem().objectName()=='navNew' and root.property('libraryMode')=='new'
        dispatch(app,root,backend,'right');spin(100)
        for design in ('classic','shelf','cinema','atlas'):
            backend.saveSettings({'library_design':design});wait(lambda:not backend.busy);spin(200)
            assert len(value(root,'shownGames'))==6 and all(g['isNew'] for g in value(root,'shownGames'))
            assert any(i.objectName()=='newGameBadge' and i.isVisible() for i in walk(root.contentItem())),design
        backend.saveSettings({'library_design':'classic'});wait(lambda:not backend.busy);invoke(root,'navigate','all','');spin(150)
        model=root.findChild(QObject,'gameLibraryRecords');updates=[];model.dataChanged.connect(lambda *args:updates.append(1))
        backend._games_cache=None;backend.gamesChanged.emit();spin(80);assert not updates
        grid=root.findChild(QObject,'gameGrid');selected=value(root,'shownGames')[grid.property('currentIndex')]['id']
        store.games[10]['name']='Changed Game';backend._games_cache=None;backend.gamesChanged.emit();spin(80);assert len(updates)==1,updates
        assert value(root,'shownGames')[grid.property('currentIndex')]['id']==selected
        output=ROOT/'test-data/new-games-review';output.mkdir(exist_ok=True)
        invoke(root,'navigate','new','');spin(100);root.grabWindow().save(str(output/'new-games.png'))
        invoke(matcher,'openForGames',['54','55']);spin(100);matcher.grabWindow().save(str(output/'search-scope.png'))
        errors=[m for m in messages if any(t in m for t in ('TypeError','ReferenceError','Binding loop','Cannot assign','different thread'))]
        assert not errors,errors
        print('PASS: six new badges/four layouts, sidebar positions, targeted home/enrichment search, all/never-searched scopes, preserved confirmed path, zero unchanged grid writes and one changed record; isolated')
    finally:
        feedback.audio.shutdown();feedback.release_cursor();app.removeEventFilter(feedback);backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
