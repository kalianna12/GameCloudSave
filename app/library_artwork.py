"""Bounded, validated local landscape artwork used by enrichment previews."""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
import hashlib,shutil,uuid
from PySide6.QtGui import QImageReader,QImage

HOSTS={'shared.fastly.steamstatic.com','shared.akamai.steamstatic.com','cdn.akamai.steamstatic.com','cdn.cloudflare.steamstatic.com','shared.steamstatic.com','s.vndb.org','t.vndb.org'}

def existing(store,game):
    value=game.get('background') or ''
    if not value or value.startswith(('http://','https://')):return ''
    for path in (Path(value),store.root/'backgrounds'/Path(value).name):
        if path.is_file():return str(path.resolve())
    return ''

def landscape(path):
    reader=QImageReader(str(path));size=reader.size();del reader
    return size.isValid() and 1.2<=size.width()/size.height()<=4 and size.width()<=8192 and size.height()<=8192

def prepare(store,value,cancel=None,user_authorized=False):
    if cancel and cancel.is_set():return ''
    folder=store.root/'backgrounds';folder.mkdir(exist_ok=True)
    target=folder/('preview-'+hashlib.sha256(str(value).encode()).hexdigest()[:24]+'.jpg')
    if target.is_file() and landscape(target):return str(target)
    temporary=target.with_name(target.stem+'-'+uuid.uuid4().hex+'.part')
    try:
        if str(value).startswith(('http://','https://')):
            parsed=urlsplit(value)
            if not user_authorized and parsed.hostname not in HOSTS:raise ValueError('横幅来源不受支持')
            with urlopen(Request(value,headers={'User-Agent':'GameCloudSave/2.4'}),timeout=12) as response:
                redirected=urlsplit(response.geturl())
                if redirected.scheme not in ('http','https') or not user_authorized and redirected.hostname not in HOSTS:raise ValueError('横幅跳转不受支持')
                payload=response.read(12*1024*1024+1)
            if len(payload)>12*1024*1024:raise ValueError('横幅图片过大')
            temporary.write_bytes(payload)
        else:
            original=Path(value)
            if not original.is_file() or original.stat().st_size>12*1024*1024:raise ValueError('请选择小于 12 MB 的横向图片')
            shutil.copyfile(original,temporary)
        if cancel and cancel.is_set():return ''
        if not landscape(temporary):raise ValueError('没有可用的横向图片')
        # Decode once on the worker, so the cinema uses a small, fixed-size JPEG.
        image=QImage(str(temporary));image=image.scaledToWidth(min(1280,image.width()))
        if image.isNull() or not image.save(str(target),'JPEG',88):raise ValueError('横幅缓存失败')
        return str(target)
    finally:temporary.unlink(missing_ok=True)
