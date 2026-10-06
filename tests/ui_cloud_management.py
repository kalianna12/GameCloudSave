"""Offline UI checks with a simulated DAV, including writable folder settings."""
from pathlib import Path
import sys,tempfile,time,gc
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QObject,QUrl,QMetaObject,qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
from services import Store,ROOT
from main import Bridge
messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
app=QApplication([]);QQuickStyle.setStyle('Material')
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    store=Store(Path(temporary),'cloud-ui')
    store.games=[{'id':'one','name':'Fate/stay night','cover':'','installed':True}]
    store.save_game('one',{'save_dir':r'C:\Users\test\AppData\Roaming\save-data'})
    store.settings.update({'cloud_folder':'测试云端','computer':'test-host','cloud_separate_computer':False})
    rows=[{'Name':'z-folder','IsDir':True,'Size':-1,'ModTime':'2026-01-01'},
          {'Name':'large.zip','IsDir':False,'Size':200,'ModTime':'2026-01-03'},
          {'Name':'small.json','IsDir':False,'Size':20,'ModTime':'2026-01-04'},
          {'Name':'.hidden','IsDir':False,'Size':3,'ModTime':'2026-01-05'}]
    bridge=Bridge(store);bridge.timer.stop()
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',bridge)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')))
    assert engine.rootObjects(),messages
    main=engine.rootObjects()[0];cloud=main.findChild(QObject,'cloudWindow')
    def settle(seconds=.2):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:app.processEvents();time.sleep(.002)
    def wait():
        while bridge.busy:settle(.02)
        settle()
    def entries():
        value=cloud.property('visibleEntries')
        return value.toVariant() if hasattr(value,'toVariant') else value
    with patch.object(store,'rclone',return_value=rows) as calls:
        assert QMetaObject.invokeMethod(main,'openCloud');wait()
        assert [e['Name'] for e in entries()]==['z-folder','large.zip','small.json']
        preview=cloud.findChild(QObject,'cloudLayoutPreview')
        assert '测试云端/Fate／stay night/save-data/' in preview.property('text'),preview.property('text')
        cloud.findChild(QObject,'cloudSeparateComputer').setProperty('checked',True);settle()
        assert '/save-data/test-host/' in preview.property('text')
        hidden=cloud.findChild(QObject,'cloudShowHidden');hidden.setProperty('checked',True);settle()
        assert len(entries())==4
        search=cloud.findChild(QObject,'cloudFileSearch');search.setProperty('text','.zip');settle()
        assert [e['Name'] for e in entries()]==['large.zip']
        search.setProperty('text','');hidden.setProperty('checked',False)
        sort=cloud.findChild(QObject,'cloudFileSort');sort.setProperty('currentIndex',1);settle()
        assert [e['Name'] for e in entries()]==['z-folder','small.json','large.zip']
        cloud.findChild(QObject,'cloudFoldersOnly').setProperty('checked',True);settle()
        assert [e['Name'] for e in entries()]==['z-folder']
        tabs=cloud.findChild(QObject,'cloudConfigTabs')
        for index in (0,1,2):tabs.setProperty('currentIndex',index);settle()
        bridge.createCloudFolder('测试云端','新的文件夹',{});wait()
        assert any(call.args[0]==['mkdir','gamecloud:测试云端/新的文件夹'] for call in calls.call_args_list)
        cloud.findChild(QObject,'cloudFoldersOnly').setProperty('checked',False)
        tabs.setProperty('currentIndex',0);settle()
        cloud.grabWindow().save(str(ROOT/'test-data/cloud-management-ui.png'))
    bridge.pool.shutdown(wait=True);shiboken6.delete(engine);gc.collect()
assert not messages,'\n'.join(messages)
print('PASS: readable layout preview, computer grouping, hidden files, text filter, folder filter, sort, config tabs, mkdir; zero QML warnings')
