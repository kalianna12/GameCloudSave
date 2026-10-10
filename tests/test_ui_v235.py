"""Actual QML long-path wrapping, metadata editing and controller keyboard layout."""
from pathlib import Path
import sys,tempfile,time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from main import Bridge
from gamepad import dispatch
from PySide6.QtCore import QObject,QUrl,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=150):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'ui-v235');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',accent_color='#80c942')
    longpath='G:\\SteamLibrary\\steamapps\\common\\Flowers - Le volume sur automne-秋\\非常长的存档目录名称\\另一个长目录\\save-data\\user-0001'
    for i in range(8):
        store.games.append({'id':str(i),'name':f'视觉小说测试 {i}','tags':['Visual Novel','Mystery'],'cover':'','release_date':f'200{i}-01-02','platform':'local'})
        store.local[str(i)]={'installed':True}
    backend=Bridge(store);backend._matches=[{'id':'0','name':store.games[0]['name'],'candidates':[{'path':longpath,'confidence':92}]}]
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend);engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.requestActivate();spin(300)
    output=ROOT/'test-data/v235-ui';output.mkdir(exist_ok=True)
    root.setProperty('libraryMode','all');root.setProperty('librarySort','release_asc');root.setWidth(1800);spin()
    root.findChild(QObject,'watchControl').setProperty('checked',True);root.findChild(QObject,'watchControl').forceActiveFocus();spin()
    root.grabWindow().save(str(output/'library-green-focus.png'))
    for item in walk(root.contentItem()):
        if item.objectName()=='gameReleaseDate' and item.isVisible():assert not item.property('truncated')
    search=root.findChild(QObject,'search');search.forceActiveFocus();dispatch(app,root,backend,'activate');spin()
    keyboard=root.findChild(QObject,'controllerKeyboard');assert keyboard.property('visible')
    root.grabWindow().save(str(output/'keyboard-letters.png'))
    dispatch(app,root,backend,'history');spin();root.grabWindow().save(str(output/'keyboard-chinese.png'))
    dispatch(app,root,backend,'back');spin()
    root.setWidth(900);root.setHeight(650);spin()
    sort=root.findChild(QObject,'librarySort');assert sort.width()>=200
    root.grabWindow().save(str(output/'library-small.png'))
    invoke(root,'openBatch');spin();batch=root.findChild(QObject,'batchWindow');batch.setWidth(980);invoke(batch,'choose','0',longpath);spin()
    label=next(item for item in walk(batch.contentItem()) if item.objectName()=='batchPathDetails' and item.property('text')==longpath)
    assert not label.property('truncated') and label.height()>24
    picker=next(item for item in walk(batch.contentItem()) if item.objectName()=='batchPathPicker')
    invoke(picker,'controllerInput','activate');spin()
    options=[item for item in walk(batch.contentItem()) if item.inherits('QQuickText') and item.property('text')==longpath]
    assert options and any(not item.property('truncated') for item in options)
    batch.grabWindow().save(str(output/'batch-long-path.png'));invoke(picker,'controllerInput','back');batch.hide();root.requestActivate();spin()
    root.setProperty('activeId','0');root.setProperty('activeName',store.games[0]['name']);invoke(root,'editMetadata');spin()
    metadata=root.findChild(QObject,'metadataDialog');assert metadata.property('visible')
    root.findChild(QObject,'metadataTags').setProperty('text','悬疑, 解谜')
    root.findChild(QObject,'metadataDate').setProperty('text','1999-09-09')
    backend.updateLibrary([{'id':'0','tags':['悬疑','解谜'],'release_date':'1999-09-09'}])
    while backend.busy:spin(25)
    spin();assert backend.libraryMetadata('0')['release_date']=='1999-09-09'
    assert root.findChild(QObject,'metadataDate').property('text')=='1999-09-09'
    root.grabWindow().save(str(output/'metadata-small.png'));metadata.setProperty('visible',False)
    store.games[1]['release_date']='';backend._games_cache=None;backend.gamesChanged.emit()
    with patch('library_metadata.lookup',return_value={'release_date':'2011-02-03','release_date_source':'Steam','metadata_url':'https://store.steampowered.com/app/1/'}):
        backend.completeMetadata(['1'])
        while backend.busy:spin(25)
    assert backend.libraryMetadata('1')['release_date']=='2011-02-03' and '新增日期 1 款' in backend.status
    install=Path(directory)/'fixture-import';install.mkdir()
    backend._imports=[{'id':'candidate','name':'Imported game','platform':'steam','external_id':'999999','install_dir':str(install),'score':1}]
    backend._import_reference=[]
    with patch('library_metadata.lookup',return_value={'release_date':'2022-01-02','release_date_source':'Steam','tags':['角色扮演'],'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/999999/'}):
        backend.importSelected(['candidate'])
        while backend.busy:spin(25)
    imported=next(game for game in backend.games if game['name']=='Imported game')
    assert imported['release_date']=='2022-01-02' and imported['tags']==['角色扮演']
    assert not any(word in message for message in messages for word in ['TypeError','ReferenceError','Binding loop','Cannot assign']),messages
    backend.timer.stop();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: full long-path options and details, compact date labels, 900px sorting, green focus, keyboard pages, single-game metadata editing; QML clean')
