"""Isolated combined facets, visible home shelves, random bag and reference keyboard."""
from pathlib import Path
import sys,tempfile,time,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,QPointF,Qt,Slot,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,ctx,text:messages.append(text))
def spin(ms=100):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.003)
def invoke(obj,name,*args):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in args))
def variant(value):return value.toVariant() if hasattr(value,'toVariant') else value
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
class SafeBridge(Bridge):
    launches=[]
    @Slot(str)
    def launch(self,ident):self.launches.append(ident)
    @Slot(QObject)
    def beginLaunchPresentation(self,window):pass

with tempfile.TemporaryDirectory(dir=ROOT/'test-data',prefix='facets-reference-') as folder:
    store=Store(folder,'facets');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False,navigation_volume=0,accent_color='#b6a0df',animations=False)
    (store.root/'covers').mkdir(exist_ok=True)
    sources=list((ROOT/'data/covers').glob('*.jpg'))[:4]
    for i,source in enumerate(sources):shutil.copy2(source,store.root/'covers'/f'{i}.jpg')
    store.games=[{'id':str(i),'name':('Fate 测试游戏 ' if i%2==0 else 'Flowers 测试游戏 ')+str(i),'cover':f'{i%len(sources)}.jpg' if sources else '',
        'series':'Fate' if i%2==0 else 'Flowers','category':'视觉小说','tags':['视觉小说','悬疑' if i%3==0 else '剧情'],'tags_manual':True,
        'release_date':'' if i%5==0 else '2020-07-15' if i%3==0 else '2021-10-12','last_played':'2026-10-22T10:00:00Z'} for i in range(40)]
    store.local={str(i):{'installed':i%2==0} for i in range(40)}
    backend=SafeBridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    try:
        engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
        root=engine.rootObjects()[0];root.resize(1440,900);root.requestActivate();spin(350)
        home=root.findChild(QObject,'libraryHome');keyboard=root.findChild(QObject,'controllerKeyboard');dialog=root.findChild(QObject,'libraryFilterDialog');random=root.findChild(QObject,'randomGameDialog')
        filter_button=root.findChild(QObject,'libraryFilterControl');dice=root.findChild(QObject,'homeRandomGame')
        def pad(command,ms=65):dispatch(app,root,backend,command);spin(ms)
        def shown():return variant(root.property('shownGames'))
        def check(criteria):
            expected=[g for g in backend.games if (not criteria.get('series') or g['series']==criteria['series']) and (not criteria.get('tags') or set(g['tags'])&set(criteria['tags'])) and (not criteria.get('year') or (not g['release_date'] if criteria['year']=='unknown' else g['release_date'].startswith(criteria['year'])))]
            assert {g['id'] for g in shown()}=={g['id'] for g in expected},(criteria,len(shown()),len(expected))
            for section in variant(root.property('localHomeRows')):
                if section['kind']!='tiles':assert {g['id'] for g in section['items']}<={g['id'] for g in expected}
            return expected
        output=ROOT/'build/facets-reference';output.mkdir(parents=True,exist_ok=True)
        root.grabWindow().save(str(output/'home.png'))
        # Drafts are transactional; apply combined series/tag/year to actual home sections.
        filter_button.forceActiveFocus();pad('activate');assert dialog.property('visible')
        tag=next(item for item in walk(dialog.property('contentItem')) if item.objectName()=='facetTag-悬疑');tag.forceActiveFocus();pad('activate');assert variant(dialog.property('draftTags'))==['悬疑']
        pad('activate');assert not variant(dialog.property('draftTags'))
        dialog.findChild(QObject,'facetSeriesChoice').forceActiveFocus()
        pad('down');assert root.activeFocusItem().objectName()=='facetYearChoice'
        pad('right');assert dialog.property('draftYear')=='unknown'
        pad('back');assert root.property('activeFacetCount')==0
        criteria={'series':'Fate','tags':['悬疑'],'year':'2020'}
        invoke(dialog,'begin',{});spin();dialog.setProperty('draftSeries','Fate');dialog.setProperty('draftTags',['悬疑']);dialog.setProperty('draftYear','2020');spin()
        expected=[g for g in backend.games if g['series']=='Fate' and '悬疑' in g['tags'] and g['release_date'].startswith('2020')]
        assert dialog.property('resultCount')==len(expected)
        assert dialog.findChild(QObject,'facetYearChoice').property('currentText')=='2020'
        root.grabWindow().save(str(output/'filters.png'));pad('menu');assert not dialog.property('visible')
        check(criteria);assert root.property('activeFacetCount')==3 and home.isVisible()
        root.grabWindow().save(str(output/'filtered-home.png'))
        # Same facets on an inner page and on all alternative layouts.
        invoke(root,'navigate','all','');spin();check(criteria)
        for design in ('shelf','cinema','atlas','classic'):
            store.settings['library_design']=design;backend.settingsChanged.emit();spin(140)
            check(criteria)
        criteria={'tags':['悬疑','剧情'],'year':'unknown'}
        invoke(root,'setFacets',criteria);spin();check(criteria)
        # Empty matches are a real empty state with a usable reset, rather than store ads.
        invoke(root,'setFacets',{'year':'1998'});spin();assert not shown() and not dice.isEnabled()
        invoke(root,'navigate','home','');spin();assert not home.isVisible() and root.findChild(QObject,'gameGrid').isVisible()
        criteria={'series':'Fate','tags':['悬疑'],'year':'2020'}
        invoke(root,'setFacets',criteria);spin();pool={g['id'] for g in check(criteria)}
        # Draw every candidate once, stay within active filters, and never auto launch.
        drawn=[]
        for _ in range(len(pool)):
            invoke(root,'randomGame');spin(80);assert random.property('visible')
            drawn.append(variant(random.property('game'))['id'])
        assert set(drawn)==pool and len(set(drawn))==len(drawn) and not backend.launches
        previous=drawn[-1];pad('history');assert variant(random.property('game'))['id']!=previous or len(pool)==1
        root.grabWindow().save(str(output/'random.png'));pad('back');assert not random.property('visible')
        invoke(root,'randomGame');spin(120);pad('activate',120)
        assert len(backend.launches)==1 and backend.launches[0] in pool
        invoke(root.findChild(QObject,'launchTransition'),'cancel');spin(100)
        # Toolbar controls remain inside actual page edges at each responsive width.
        for width in (900,1100,1440,1920,2560):
            root.resize(width,900);spin(100)
            for obj in ('installedFilter','platformFilter','sourceFilter','libraryFilterControl','clearLibraryFilters','homeRandomGame','fullscreenControl'):
                item=root.findChild(QObject,obj);p=item.mapToScene(QPointF())
                assert p.x()>=home.mapToScene(QPointF()).x()-4 and p.x()+item.width()<=width-28,(width,obj,p.x(),item.width())
        root.resize(1440,900);invoke(root,'setFacets',{});spin(120);invoke(home,'focusFirst')
        invoke(keyboard,'start','');spin(180)
        for size in ((1440,900),(900,650)):
            root.resize(*size);spin(120)
            cells={i.objectName():i for i in walk(keyboard.property('contentItem')) if i.objectName().startswith('keyboardKey-')}
            for index in range(9):assert abs(cells[f'keyboardKey-{index}'].x()+cells[f'keyboardKey-{index}'].width()-cells[f'keyboardKey-{index+1}'].x())<1
            assert abs(cells['keyboardKey-0'].height()-keyboard.property('keyHeight'))<1
            root.grabWindow().save(str(output/f'keyboard-{size[0]}.png'))
            assert abs(cells['keyboardKey-41'].height()-2*cells['keyboardKey-0'].height())<2,(size,[(i,cells[f'keyboardKey-{i}'].height(),cells[f'keyboardKey-{i}'].y()) for i in (0,10,20,30,41,42,43)])
            assert keyboard.property('y')>=0 and keyboard.property('y')+keyboard.property('height')<=root.height()+1
            root.grabWindow().save(str(output/f'keyboard-{size[0]}.png'))
        pad('back')
        # Long custom-tag lists stay operable without focus escaping the scroll area.
        dialog.setProperty('games',[]);invoke(dialog,'begin',{'series':'Missing Series','tags':['Missing Tag'],'year':'1999'});spin(120)
        assert dialog.findChild(QObject,'facetSeriesChoice').property('currentText')=='Missing Series'
        assert dialog.findChild(QObject,'facetYearChoice').property('currentText')=='1999' and dialog.property('resultCount')==0
        pad('back')
        dialog.setProperty('games',[{'id':'tags-fixture','name':'Tag fixture','tags':[f'Tag {i:02}' for i in range(48)]}])
        invoke(dialog,'begin',{});spin(120)
        for _ in range(25):pad('down',8)
        focused=root.activeFocusItem();p=focused.mapToScene(QPointF())
        assert p.y()>=dialog.property('y') and p.y()+focused.height()<=dialog.property('y')+dialog.property('height')+1,(focused.objectName(),p.y(),focused.height(),dialog.property('y'),dialog.property('height'))
        pad('back')
        store.settings['theme']='light';backend.settingsChanged.emit();spin();root.grabWindow().save(str(output/'home-light-compact.png'))
        errors=[m for m in messages if any(word in m for word in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','recursive rearrange'))]
        assert not errors,errors[:20]
        print('PASS: combined facets on home/inner/four layouts, unknown years, transactional drafts, random without replacement/explicit confirmation, responsive tools, exact reference grid and glyphs; no real game launch')
    finally:
        backend.shutdownWatch();backend.pool.shutdown(wait=True);backend.graphics.pool.shutdown(wait=True);shiboken6.delete(engine)
