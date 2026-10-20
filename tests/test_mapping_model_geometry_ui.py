"""Full silhouettes and real QML hit regions: three skins, two sizes/directions.

Uses an isolated store and no native input transport. Raster masks come from the
actual SVG shell paths, rather than duplicating the expected shell coordinates.
"""
from pathlib import Path
import sys,tempfile,time,math,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import ROOT,Store
from main import Bridge
from PySide6.QtCore import QObject,QUrl,QByteArray,QRectF,QPointF,Qt,qInstallMessageHandler
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
import shiboken6

QQuickStyle.setStyle('Material');app=QApplication([]);messages=[]
qInstallMessageHandler(lambda k,c,m:messages.append(m))
def spin(ms=80):
    end=time.perf_counter()+ms/1000
    while time.perf_counter()<end:app.processEvents();time.sleep(.002)
def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)
def mask(model,ids):
    svg=ET.parse(ROOT/'ui/assets'/('mapping-'+model+'.svg')).getroot()
    paths=[p.attrib['d'] for p in svg.iter() if p.attrib.get('id') in ids]
    assert len(paths)==len(ids)
    data='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 650">'+''.join('<path fill="white" d="'+d+'"/>' for d in paths)+'</svg>'
    image=QImage(820,650,QImage.Format_ARGB32);image.fill(Qt.transparent)
    painter=QPainter(image);QSvgRenderer(QByteArray(data.encode())).render(painter,QRectF(0,0,820,650));painter.end()
    return image
def covered(image,x,y):
    return 0<=x<820 and 0<=y<650 and image.pixelColor(int(x),int(y)).alpha()>240
def inside(image,rect,label):
    # Entire hit rectangle, including corners, must lie within its front shell.
    for xi in range(11):
        for yi in range(11):
            x=rect.left()+rect.width()*xi/10;y=rect.top()+rect.height()*yi/10
            assert covered(image,x,y),(label,'outside shell',x,y)
def circle(image,x,y,r,label):
    for a in range(360):
        t=math.radians(a);assert covered(image,x+r*math.cos(t),y+r*math.sin(t)),(label,a)

out=ROOT/'test-data/model-review';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    store=Store(directory,'model-review');store.settings.update(setup_completed=True,guide_dismissed=True,watch=False,recommendations_enabled=False)
    backend=Bridge(store);engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',backend)
    engine.loadData(b'''import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true;width: 860;height: 690;color: "#23282f"
    MappingGamepad { objectName: "reviewPad";anchors.fill: parent;anchors.margins: 20 }
}''',QUrl.fromLocalFile(str(ROOT/'ui/ModelReview.qml')))
    assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];pad=window.findChild(QObject,'reviewPad')
    try:
        deadline=time.perf_counter()+4
        while not pad.property('artworkReady') and time.perf_counter()<deadline:spin(20)
        assert pad.property('artworkReady'),messages
        clicked=[];pad.chosen.connect(clicked.append)
        for model in ('xbox','ps','joycon'):
            pad.setProperty('modelType',model);spin()
            positions=pad.property('placements').toVariant();front=mask(model,('left','right') if model=='joycon' else ('body',))
            left=mask(model,('left',)) if model=='joycon' else front
            right=mask(model,('right',)) if model=='joycon' else front
            rects={}
            for p in positions:
                r=QRectF(p['x']-p['w']/2,p['y']-p['h']/2,p['w'],p['h']);rects[p['id']]=r
                if p['kind'] in ('trigger','shoulder'):
                    # Include shadow and at least eight units of free space.
                    for x in range(int(r.left()-8),int(r.right()+10)):
                        for y in range(int(r.top()-8),int(r.bottom()+13)):
                            assert not covered(front,x,y),(model,p['id'],'rear overlaps body')
                else:
                    shell=(left if p['x']<410 else right)
                    inside(shell,r,(model,p['id']))
                for other,previous in rects.items():
                    if other!=p['id']:assert not r.intersects(previous),(model,p['id'],other,'hit regions overlap')
            if model=='xbox':
                for x,y,r in ((236,263,57),(500,370,57),(321,375,59)):circle(front,x,y,r,model)
            elif model=='ps':
                for x in (293,527):circle(front,x,340,57,model)
            else:
                circle(left,253,267,44,model);circle(right,568,391,44,model)
            for width,height in ((860,690),(520,452)):
                window.resize(width,height);spin()
                mode_sizes=[]
                for reverse in (False,True):
                    pad.setProperty('reverse',reverse);spin()
                    art=pad.findChild(QObject,'mappingPadArtwork');s=art.width()/820
                    mode_sizes.append((art.width(),art.height()))
                    assert len([k for k in walk(art) if str(k.property('token') or '').startswith('P:')])==16
                    items={item.objectName():item for item in walk(art)}
                    for p in positions:
                        key=items['mapping-key-P:'+p['id']]
                        assert abs(key.width()-p['w']*s)<.02
                        point=key.mapToScene(QPointF(key.width()/2,key.height()/2))
                        QTest.mouseClick(window,Qt.LeftButton,pos=point.toPoint());spin(1)
                        assert clicked[-1]=='P:'+p['id'],(model,p['id'],clicked[-1])
                    # Joystick tops stay within their base even diagonally.
                    for axis in ((1,1),(1,-1),(-1,1),(-1,-1),(0,1),(1,0),(-1,0),(0,-1)):
                        pad.setProperty('sample',{'LS':list(axis),'RS':list(axis),'buttons':[]});spin(1)
                        for stick in ('LS','RS'):
                            key=items['mapping-key-P:'+stick]
                            v=key.property('capVector')
                            assert math.hypot(v.x(),v.y())<=1.00001,(stick,v)
                            top=items['mappingStickTop-'+stick]
                            assert top.width()/2+key.width()*.08<=key.width()/2-1*s
                    pad.setProperty('sample',{'LS':[0,0],'RS':[0,0],'buttons':[]});spin()
                    assert window.grabWindow().save(str(out/(model+('-reverse' if reverse else '')+('-small' if width==520 else '')+'.png')))
                assert mode_sizes[0]==mode_sizes[1]
        errors=[m for m in messages if any(t in m for t in ('Error','Cannot','Unable','Binding loop'))]
        assert not errors,errors
    finally:
        window.close();backend.shutdownWatch();backend.pool.shutdown(wait=True);shiboken6.delete(engine)
print('PASS: full SVG shell masks, rear clearance, disjoint hit regions, stick travel, 192 clicks and 12 full-model screenshots; no native input')
