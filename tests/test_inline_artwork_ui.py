"""Rendered in-page search/capture with a local public-page fixture, never external browsing."""
from pathlib import Path
import sys,tempfile,time,threading,json
from http.server import HTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QPointF,QMetaObject,Q_ARG,Q_RETURN_ARG,qInstallMessageHandler
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
import shiboken6
QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda kind,context,message:messages.append(message))
def spin(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def invoke(obj,name,*values):return QMetaObject.invokeMethod(obj,name,Q_RETURN_ARG('QVariant'),*(Q_ARG('QVariant',v) for v in values))
def idle():
    end=time.monotonic()+12
    while (backend.busy or backend.artworkSearching) and time.monotonic()<end:spin(25)
    assert not backend.busy and not backend.artworkSearching,backend.status
def variant(value):return value.toVariant() if hasattr(value,'toVariant') else value
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    folder=Path(directory)
    for name,size,color in [('cover',(360,540),'#8068aa'),('banner',(1280,720),'#447d82')]:
        image=QImage(*size,QImage.Format_RGB32);image.fill(QColor(color));image.save(str(folder/(name+'.png')))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path.startswith('/cover.png'):content=(folder/'cover.png').read_bytes();mime='image/png'
            elif self.path.startswith('/banner.png'):content=(folder/'banner.png').read_bytes();mime='image/png'
            else:content=b'<html><title>Image search fixture</title><body><img src="/cover.png" alt="cover" width="360" height="540"><img src="/banner.png" alt="banner" width="1280" height="720"></body></html>';mime='text/html'
            self.send_response(200);self.send_header('Content-Type',mime);self.end_headers();self.wfile.write(content)
    server=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_port)
    store=Store(folder/'data','inline');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,library='',playnite='')
    store.games=[{'id':'g','name':'Fixture','cover':'','tags':[],'category':'其他'},{'id':'m','name':'Missing','cover':'','tags':[],'category':'其他'}]
    write_json(store.root/'library.json',store.games)
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.load(QUrl.fromLocalFile(str(ROOT/'ui/Main.qml')));assert engine.rootObjects(),messages
    root=engine.rootObjects()[0];root.setWidth(1440);root.setHeight(940);root.requestActivate();spin(250)
    invoke(root,'openGame',backend.games[0]);spin(100)
    dialog=root.findChild(QObject,'gameDialog');dialog.findChild(QObject,'gameSettingsTabs').setProperty('currentIndex',1);spin(150)
    picker=dialog.findChild(QObject,'gameCoverPicker');provider=picker.findChild(QObject,'gameCoverProvider');tabs=picker.findChild(QObject,'artworkTabs')
    provider.setProperty('currentIndex',next(i for i,p in enumerate(backend.coverProviders) if p['id']=='google'))
    output=ROOT/'test-data/image-search-review';output.mkdir(exist_ok=True)
    def web_search(pane,retry=False):
        with patch.object(backend,'artworkBrowserUrl',return_value=url+'/page') as endpoint:
            invoke(pane,'search')
            if retry:
                spin(100);assert pane.property('browserOpen')
                old=pane.property('browserToken');endpoint.return_value=url+'/page?retry=1';invoke(pane,'search');spin(50)
                browser=pane.findChild(QObject,'inlineImageBrowser')
                assert browser.property('token')!=old and browser.property('searchUrl').toString().endswith('retry=1')
            end=time.monotonic()+18
            while pane.property('browserOpen') and time.monotonic()<end:spin(50)
        assert not pane.property('browserOpen'),(backend.status,messages)
        assert len(backend.coverResults)==1,(backend.coverResults,backend.status,messages)
        spin(250)
    def choose_visible():
        grid=picker.findChild(QObject,'gameCoverResults')
        button=next(item for item in walk(grid) if item.objectName()=='chooseArtwork' and item.isVisible())
        point=button.mapToItem(grid,QPointF(0,button.height()))
        assert point.y()<=grid.height()+1,('Artwork button clipped',point.y(),grid.height())
    web_search(picker,retry=True)
    choose_visible()
    assert backend.coverResults[0]['provider']=='google' and backend.coverResults[0]['width']==360
    root.grabWindow().save(str(output/'inline-cover.png'))
    backend.applyCover('game','g',backend.coverResults[0]['id']);idle();assert store.games[0]['cover']
    tabs.setProperty('currentIndex',1);web_search(picker)
    result=backend.coverResults[0];assert result['background_url'] and result['width']==1280
    root.grabWindow().save(str(output/'inline-banner.png'))
    backend.applyBackground('g',result['id']);idle();assert Path(store.games[0]['background']).is_file()
    assert variant(picker.property('record'))['backgroundUrl'].startswith('file:')
    # Catalog candidates expose the banner before selection; switching preview
    # type reuses the paired assets, without another request or changing files.
    provider.setProperty('currentIndex',0)
    records=[{'id':'steam:1','appid':'1','name':'Has banner','image':url+'/cover.png','background_url':url+'/banner.png','background_state':'available','provider':'steam','user_authorized':True},
             {'id':'steam:2','name':'No banner','image':url+'/cover.png','background_url':'','background_state':'none','provider':'steam'}]
    with patch('artwork_search.search',return_value=records):invoke(picker,'search');idle();spin(150)
    badges=[i.property('text') for i in walk(picker) if i.objectName()=='candidateBannerStatus' and i.isVisible()]
    assert '有横幅' in badges and '无横幅' in badges,badges
    choose_visible()
    first=next(item for item in walk(picker) if item.objectName()=='chooseArtwork' and item.isVisible())
    backend.receiveArtwork(backend._image_token,[dict(r,background_state='unknown') for r in records],False,'');spin(80)
    assert shiboken6.isValid(first) and first.isVisible(),'A progressive result recreated the existing image card'
    backend.receiveArtwork(backend._image_token,records,True,'');spin(80)
    root.grabWindow().save(str(output/'catalog-banners.png'));dialog.setProperty('visible',False)
    # Completion uses the same embedded search and keeps the selected image in
    # a preview on this page until explicit Apply.
    from enrichment_manual import base
    invoke(root,'openEnrichment',[],{},False);spin(100);window=root.findChild(QObject,'enrichmentWindow')
    window.setProperty('ownsQuery',True);window.setProperty('hasQuery',True)
    backend.receiveEnrichment(base(store,'m')[1],1,1,'Fixture');invoke(window,'sync')
    invoke(window,'openManual',backend.enrichmentResults[-1]);spin(100)
    manual=window.findChild(QObject,'manualEnrichmentPane');manual.findChild(QObject,'manualProvider').setProperty('currentIndex',2)
    manual.findChild(QObject,'manualImageKind').setProperty('currentIndex',1);web_search(manual)
    before=(store.root/'library.json').read_bytes()
    backend.previewEnrichmentArtwork('m',backend.coverResults[0]['id'],'background');idle();spin(150)
    assert window.property('manualId')=='m' and manual.isVisible()
    assert backend.enrichmentResults[-1]['fields']['background'] and (store.root/'library.json').read_bytes()==before
    window.grabWindow().save(str(output/'manual-banner-selected.png'))
    # Series alone never makes a complete game appear in the missing filter.
    store.games[0].update(release_date='2020-01-01',category='动作冒险',tags=['动作'])
    backend.receiveEnrichment(base(store,'g')[1],2,2,'Fixture');window.setProperty('manualId','')
    missing=window.findChild(QObject,'enrichOnlyMissing');missing.setProperty('checked',True);invoke(window,'sync');spin(100)
    listing=window.findChild(QObject,'enrichmentPreview');assert listing.property('count')==1
    stale=backend._image_token;backend.clearCoverSearch()
    assert backend.receiveInlineImages(stale,'google',[{'image':url+'/cover.png'}])==0
    window.hide();spin(100)
    errors=[m for m in messages if any(s in m for s in ('TypeError','ReferenceError','Binding loop','Cannot assign','Unable to assign','is not defined','is not a type'))]
    assert not errors,errors
    backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine);server.shutdown();server.server_close()
print('PASS: embedded Chromium page capture, portrait/banner results, catalog banner availability, settings apply, same-page completion preview, series excluded and stale capture rejection')
