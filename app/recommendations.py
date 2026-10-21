"""Independent catalog and artwork pools with incremental Qt updates and local caches."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import logging
import os
import threading
import time

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, Qt, QTimer
from PySide6.QtGui import QDesktopServices, QImage
import recommendation_sources as sources

TTL = 3600
MAX_AGE = 7 * 86400
RETRY_SECONDS = 60


class Recommendations(QObject):
    changed = Signal()
    received = Signal(str, object, int)
    artwork = Signal(str, str, str, int, str, int)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='store-feed')
        self._images = ThreadPoolExecutor(max_workers=4, thread_name_prefix='store-art')
        self._cancel = threading.Event()
        self._token = 0
        self._closed = False
        self._started = False
        self._providers = ()
        self._rows = {}
        self._errors = {}
        self._notices = {}
        self._pending = set()
        self._image_locks = {}
        self._requests = {}
        self._section_pending = set()
        self._request_serial = 0
        self._revisions = {category:0 for category in sources.SECTIONS}
        self.received.connect(self.receive)
        self.artwork.connect(self.receive_art)
        self._timer=QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_refresh)

    def enabled_providers(self):
        if not self.store.settings.get('recommendations_enabled', True):
            return ()
        return tuple(p for p in ('steam', 'xbox') if self.store.settings.get('recommendations_' + p, True))

    @Property(bool, notify=changed)
    def loading(self):
        return bool(self._pending or self._section_pending)

    @Property(str, notify=changed)
    def status(self):
        if self.loading:
            return '正在读取商店…'
        return '；'.join(dict.fromkeys(self._errors.values()))

    @Property('QVariantList', notify=changed)
    def sections(self):
        if not self.enabled_providers():
            return []
        result = []
        for category, (title, page) in sources.SECTIONS.items():
            provider='xbox' if category=='xbox' else 'steam'
            if provider not in self._providers:continue
            items = [row for row in self._rows.get(provider, []) if row['category'] == category]
            loading=self._section_loading(category)
            message=('正在刷新，保留现有推荐' if items else '正在读取商店…') if loading else self._errors.get(category) or self._notices.get(category,'')
            if not loading and not message and any(row.get('stale') for row in items):message='离线缓存 · 价格待刷新'
            if not loading and not message and not items:message='该栏目暂时没有推荐，点击刷新重试'
            result.append({'id': 'store:' + category, 'kind': 'store', 'title': title, 'items': items,
                           'page': page, 'message': message, 'refresh': True,
                           'revision':self._revisions[category], 'loading':loading})
        if not result:
            result.append({'id': 'store:status', 'kind': 'store', 'title': '游戏推荐', 'items': [],
                           'message': self.status or '刷新以查看商店游戏', 'refresh': True, 'loading':self.loading})
        return result

    def _section_loading(self,category):
        provider='xbox' if category=='xbox' else 'steam'
        return provider in self._pending or category in self._section_pending

    @Slot(str)
    def refreshSection(self,ident):
        if ident=='store:status':
            self.refresh();return
        category=ident.removeprefix('store:')
        provider='xbox' if category=='xbox' else 'steam'
        if (self._closed or category not in sources.SECTIONS or provider not in self.enabled_providers()
                or self._section_loading(category)):
            return
        previous=self._requests.get(category)
        if previous:previous[1].set()
        self._request_serial+=1
        cancel=threading.Event();request=self._request_serial
        self._requests[category]=(request,cancel)
        self._section_pending.add(category)
        self.changed.emit()
        self._pool.submit(self._load,provider,True,self._token,cancel,category,request)

    @Slot()
    def start(self):
        providers = self.enabled_providers()
        if self._closed or self._started and providers == self._providers:
            return
        self._started = True
        self._begin(providers, False)

    @Slot()
    def refresh(self):
        if self._closed or self.loading:
            return
        self._started = True
        self._begin(self.enabled_providers(), True)

    def _auto_refresh(self):
        if self._closed or not self.enabled_providers():return
        if self.loading:self._timer.start(1000)
        else:self.refresh()

    def _schedule_refresh(self):
        if not self._closed and self.enabled_providers() and not self.loading:
            self._timer.start((RETRY_SECONDS if self._errors else TTL)*1000)

    def sync(self):
        if self._started:
            self.start()

    def _begin(self, providers, force):
        self._cancel.set()
        for request,cancel in self._requests.values():cancel.set()
        self._requests.clear();self._section_pending.clear()
        self._cancel = threading.Event()
        self._token += 1
        token = self._token
        self._providers = providers
        self._rows = {p: self._rows.get(p, []) for p in providers}
        self._errors = {}
        self._notices = {}
        self._pending = set(providers)
        self._timer.stop()
        self.changed.emit()
        for provider in providers:
            self._pool.submit(self._load, provider, force, token, self._cancel)

    def _load(self, provider, force, token, cancel, scope='', request=0):
        folder = self.store.profile / 'recommendations'
        file = folder / (provider + '.json')
        cached = []
        try:
            data = json.loads(file.read_text(encoding='utf-8'))
            age = time.time() - data['time']
            if data.get('version') == 1 and 0 <= age < MAX_AGE and isinstance(data.get('rows'), list):
                cached = self._cached_rows(data['rows'], age)
                if not cached:raise ValueError('No usable storefront cache')
                if not cancel.is_set() and not force:
                    self.received.emit(provider, {'rows': cached, 'done': age < TTL,'cached':True,'at':data['time']}, token)
                if not force and age < TTL:
                    self._artwork(provider, cached, token, cancel)
                    return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if cancel.is_set():
            return
        try:
            rows = sources.fetch(provider)
            if cancel.is_set():
                return
            fetched=time.time()
            # Cache persistence must never suppress successfully fetched recommendations.
            try:
                folder.mkdir(parents=True, exist_ok=True)
                temporary = file.with_suffix('.'+str(token)+'.'+str(request)+'.tmp')
                temporary.write_text(json.dumps({'version': 1, 'time': fetched, 'rows': rows}, ensure_ascii=False), encoding='utf-8')
                if cancel.is_set():temporary.unlink(missing_ok=True);return
                temporary.replace(file)
                self._prune_images(folder/'images')
            except OSError:
                logging.getLogger(__name__).warning('Store cache write failed: provider=%s',provider)
            self.received.emit(provider, {'rows': rows, 'done': True,'scope':scope,'request':request,'at':fetched}, token)
            self._artwork(provider, [row for row in rows if not scope or row['category']==scope], token, cancel, scope, request)
        except Exception as error:
            if not cancel.is_set():
                logging.getLogger(__name__).warning('Store feed failed: provider=%s kind=%s',provider,type(error).__name__)
                self.received.emit(provider, {'rows': cached, 'done': True,'scope':scope,'request':request, 'error': self._error_message(provider,error)}, token)
                self._artwork(provider, [row for row in cached if not scope or row['category']==scope], token, cancel, scope, request)

    @staticmethod
    def _error_message(provider,error):
        from urllib.error import HTTPError,URLError
        name='Steam' if provider=='steam' else 'Xbox'
        if isinstance(error,HTTPError):
            detail='请求过于频繁' if error.code==429 else '暂时拒绝访问' if error.code in (401,403) else '商店服务异常'
        elif isinstance(error,(TimeoutError,URLError,OSError)):detail='连接超时或网络不可用'
        else:detail='暂未取得有效推荐'
        return name+' '+detail+'，点击刷新重试'

    def _cached_rows(self, rows, age):
        result = []
        for row in rows[:40]:
            if (not isinstance(row, dict) or row.get('category') not in sources.SECTIONS
                    or not all(isinstance(row.get(field),str) for field in ('id','name','page','provider'))
                    or not sources.valid_page(row['page']) or not isinstance(row.get('images'),list)):
                continue
            if row.get('category') == 'sale' and sources.amount(row.get('expires')) and row['expires'] and row['expires'] <= time.time():
                continue
            row = {**row, 'images': [url for url in row.get('images', [])[:2] if sources.image_url(url)]}
            if age >= TTL:
                row.update(stale=True, price='价格待刷新', originalPrice='', discount=0)
            result.append(row)
        return result

    @Slot(str, object, int)
    def receive(self, provider, result, token):
        if self._closed or token != self._token or provider not in self.enabled_providers():
            return
        scope=result.get('scope','')
        if scope and (scope not in self._requests or self._requests[scope][0]!=result.get('request')):return
        old=self._rows.get(provider,[])
        artwork={(row['id'],row['category']):row['coverUrl'] for row in old if row.get('coverUrl')}
        states={(row['id'],row['category']):{key:row[key] for key in ('artworkFailed','artworkLoading') if key in row} for row in old}
        incoming=[]
        for row in result['rows']:
            if scope and row['category']!=scope:continue
            cover=artwork.get((row['id'],row['category']))
            incoming.append({**row,**({'coverUrl':cover} if cover else {}),**states.get((row['id'],row['category']),{})})
        if result.get('error') and old and not incoming:
            # A failed refresh keeps the currently displayed cards, including artwork.
            incoming=[row for row in old if not scope or row['category']==scope]
        updated=[row for row in old if row['category']!=scope]+incoming if scope else incoming
        categories=[scope] if scope else [category for category in sources.SECTIONS if (category=='xbox')==(provider=='xbox')]
        if result.get('done'):
            for category in categories:
                if result.get('error'):
                    self._errors[category]=result['error']+(' · 保留已有推荐' if any(row['category']==category for row in updated) else '')
                else:
                    self._errors.pop(category,None)
                    label='缓存' if result.get('cached') else '已更新'
                    stamp=time.strftime('%H:%M:%S',time.localtime(result.get('at',time.time())))
                    # Server catalogs often legitimately return the same featured games.
                    before=[r for r in old if r['category']==category]
                    after=[r for r in updated if r['category']==category]
                    unchanged=before and before==after and not result.get('cached')
                    self._notices[category]=label+' '+stamp+(' · 暂无新推荐' if unchanged else '' if after else ' · 该栏目暂时没有推荐')
        if updated!=old:
            categories={row['category'] for row in old+updated}
            for category in categories:
                if [r for r in old if r['category']==category]!=[r for r in updated if r['category']==category]:self._revisions[category]+=1
            self._rows[provider]=updated
        if result.get('done'):
            if scope:self._section_pending.discard(scope)
            else:self._pending.discard(provider)
        self._schedule_refresh()
        self.changed.emit()

    def _artwork(self, provider, rows, token, cancel, scope='', request=0):
        seen = set()
        for row in rows:
            if cancel.is_set():
                return
            if row['id'] in seen:
                continue
            seen.add(row['id'])
            self._images.submit(self._picture, provider, row, token, cancel, scope, request)

    @Slot(str, str)
    def retryArtwork(self, ident, category):
        provider='xbox' if category=='xbox' else 'steam'
        if self._closed or provider not in self.enabled_providers():return
        row=next((r for r in self._rows.get(provider,[]) if r['id']==ident and r['category']==category),None)
        if not row or row.get('artworkLoading'):return
        serial,cancel=self._requests.get(category,(0,self._cancel))
        self._rows[provider]=[{**r,'artworkFailed':False,'artworkLoading':True} if r is row else r for r in self._rows[provider]]
        self._revisions[category]+=1;self.changed.emit()
        self._images.submit(self._picture,provider,row,self._token,cancel,category if serial else '',serial,time.monotonic_ns())

    def _picture(self, provider, row, token, cancel, scope='', request=0, reload=0):
        directory = self.store.profile / 'recommendations' / 'images'
        for url in row.get('images', [])[:2]:
            if cancel.is_set():return
            if not sources.image_url(url):continue
            file = directory / (hashlib.sha256(url.encode()).hexdigest() + '.jpg')
            try:
                # Different editions can share artwork; download/write it only once.
                with self._image_locks.setdefault(url,threading.Lock()):
                    if cancel.is_set():
                        return
                    if not file.is_file() or QImage(str(file)).isNull():
                        image = QImage.fromData(sources.request(url, 3 * 1024 * 1024))
                        if cancel.is_set():
                            return
                        if image.isNull() or image.width() * image.height() > 32000000:
                            continue
                        directory.mkdir(parents=True, exist_ok=True)
                        image = image.scaled(640, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        temporary = file.with_suffix('.'+str(token)+'.'+str(threading.get_ident())+'.tmp')
                        if not image.save(str(temporary), 'JPEG', 88):
                            continue
                        temporary.replace(file)
                    if not cancel.is_set():
                        stat=file.stat()
                        # Keep content identity stable on a cache hit, but change it after repair.
                        # Qt caches failed image loads too, so the bare filename cannot recover.
                        try:os.utime(file,ns=(time.time_ns(),stat.st_mtime_ns))
                        except OSError:pass # A read-only cached image can still be displayed.
                        local=QUrl.fromLocalFile(str(file))
                        local.setQuery('v='+str(stat.st_mtime_ns)+'-'+str(stat.st_size)+('-'+str(reload) if reload else ''))
                        self.artwork.emit(provider, row['id'], local.toString(), token,scope,request)
                return
            except Exception:
                continue
        if not cancel.is_set():self.artwork.emit(provider,row['id'],'',token,scope,request)

    def _prune_images(self,directory):
        # This is a regenerable storefront cache, not game artwork or backup data.
        try:
            protected=set()
            for cache in directory.parent.glob('*.json'):
                try:
                    for row in json.loads(cache.read_text(encoding='utf-8')).get('rows',[]):
                        protected.update(hashlib.sha256(url.encode()).hexdigest() for url in row.get('images',[]) if isinstance(url,str))
                except (OSError,ValueError,TypeError,AttributeError):pass
            entries=sorted(((max(file.stat().st_atime,file.stat().st_mtime),file) for file in directory.glob('*.jpg') if len(file.stem)==64),reverse=True)
            for stamp,file in entries[160:]:
                if file.stem not in protected and time.time()-stamp>86400:file.unlink(missing_ok=True)
        except OSError:pass

    @Slot(str, str, str, int, str, int)
    def receive_art(self, provider, ident, url, token, scope='', request=0):
        if self._closed or token != self._token or provider not in self.enabled_providers():
            return
        if scope and (scope not in self._requests or self._requests[scope][0]!=request):return
        old=self._rows.get(provider,[])
        changed={row['category'] for row in old if row['id']==ident and (row['category']==scope if scope else row['category'] not in self._requests) and (row.get('coverUrl','')!=url or row.get('artworkLoading') or bool(row.get('artworkFailed'))!=bool(not url))}
        if not changed:return
        self._rows[provider] = [{**row, **({'coverUrl':url} if url else {}),'artworkFailed':not bool(url),'artworkLoading':False} if row['id']==ident and row['category'] in changed else row for row in old]
        for category in changed:self._revisions[category]+=1
        self.changed.emit()

    @Slot(str, result=bool)
    def open(self, ident):
        pages = {section['id']: section.get('page', '') for section in self.sections}
        pages.update({row['id']: row['page'] for section in self.sections for row in section['items']})
        page = pages.get(ident, '')
        return bool(page and sources.valid_page(page) and QDesktopServices.openUrl(QUrl(page)))

    def shutdown(self):
        self._closed = True
        self._cancel.set()
        for request,cancel in self._requests.values():cancel.set()
        self._timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._images.shutdown(wait=False, cancel_futures=True)
