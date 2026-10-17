"""Independent catalog and artwork pools with incremental Qt updates and local caches."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import threading
import time

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, Qt, QTimer
from PySide6.QtGui import QDesktopServices, QImage
import recommendation_sources as sources

TTL = 3600
MAX_AGE = 7 * 86400


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
        self._pending = set()
        self._last_start = 0
        self._image_locks = {}
        self._requests = {}
        self._section_pending = set()
        self._request_serial = 0
        self._revisions = {category:0 for category in sources.SECTIONS}
        self.received.connect(self.receive)
        self.artwork.connect(self.receive_art)
        self._timer=QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)

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
        return '；'.join(self._errors.values())

    @Property('QVariantList', notify=changed)
    def sections(self):
        if not self.enabled_providers():
            return []
        result = []
        for category, (title, page) in sources.SECTIONS.items():
            items = [row for provider in self._providers for row in self._rows.get(provider, []) if row['category'] == category]
            if items:
                stale = any(row.get('stale') for row in items)
                result.append({'id': 'store:' + category, 'kind': 'store', 'title': title, 'items': items,
                               'page': page, 'message': '离线缓存 · 价格待刷新' if stale else '', 'refresh': True,
                               'revision':self._revisions[category], 'loading':self._section_loading(category)})
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
        if self._closed or self.loading or time.monotonic() - self._last_start < 5:
            return
        self._started = True
        self._begin(self.enabled_providers(), True)

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
        self._pending = set(providers)
        self._last_start = time.monotonic()
        if providers:self._timer.start(TTL*1000)
        else:self._timer.stop()
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
                if not cancel.is_set() and not force:
                    self.received.emit(provider, {'rows': cached, 'done': not force and age < TTL}, token)
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
            folder.mkdir(parents=True, exist_ok=True)
            temporary = file.with_suffix('.'+str(token)+'.'+str(request)+'.tmp')
            temporary.write_text(json.dumps({'version': 1, 'time': time.time(), 'rows': rows}, ensure_ascii=False), encoding='utf-8')
            temporary.replace(file)
            self._prune_images(folder/'images')
            self.received.emit(provider, {'rows': rows, 'done': True,'scope':scope,'request':request}, token)
            self._artwork(provider, [row for row in rows if not scope or row['category']==scope], token, cancel, scope, request)
        except Exception:
            if not cancel.is_set():
                self.received.emit(provider, {'rows': cached, 'done': True,'scope':scope,'request':request, 'error': ('Steam' if provider == 'steam' else 'Xbox') + ' 暂不可用，稍后刷新'}, token)
                self._artwork(provider, [row for row in cached if not scope or row['category']==scope], token, cancel, scope, request)

    def _cached_rows(self, rows, age):
        result = []
        for row in rows[:40]:
            if (not isinstance(row, dict) or row.get('category') not in sources.SECTIONS
                    or not all(isinstance(row.get(field),str) for field in ('id','name','page','provider'))
                    or not sources.valid_page(row['page']) or not isinstance(row.get('images'),list)):
                continue
            if row.get('category') == 'sale' and row.get('expires', 0) and row['expires'] <= time.time():
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
        incoming=[]
        for row in result['rows']:
            if scope and row['category']!=scope:continue
            cover=artwork.get((row['id'],row['category']))
            incoming.append({**row,**({'coverUrl':cover} if cover else {})})
        if result.get('error') and old and not incoming:
            # A failed refresh keeps the currently displayed cards, including artwork.
            incoming=[row for row in old if not scope or row['category']==scope]
        updated=[row for row in old if row['category']!=scope]+incoming if scope else incoming
        if updated!=old:
            categories={row['category'] for row in old+updated}
            for category in categories:
                if [r for r in old if r['category']==category]!=[r for r in updated if r['category']==category]:self._revisions[category]+=1
            self._rows[provider]=updated
        if result.get('done'):
            if scope:self._section_pending.discard(scope)
            else:self._pending.discard(provider)
        if result.get('error'):
            self._errors[provider] = result['error']
        elif result.get('done'):self._errors.pop(provider,None)
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

    def _picture(self, provider, row, token, cancel, scope='', request=0):
        directory = self.store.profile / 'recommendations' / 'images'
        for url in row.get('images', [])[:2]:
            if cancel.is_set() or not sources.image_url(url):
                return
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
                        file.touch()
                        self.artwork.emit(provider, row['id'], QUrl.fromLocalFile(str(file)).toString(), token,scope,request)
                return
            except Exception:
                continue

    def _prune_images(self,directory):
        # This is a regenerable storefront cache, not game artwork or backup data.
        try:
            entries=sorted(((file.stat().st_mtime,file) for file in directory.glob('*.jpg') if len(file.stem)==64),reverse=True)
            for stamp,file in entries[160:]:
                if time.time()-stamp>86400:file.unlink(missing_ok=True)
        except OSError:pass

    @Slot(str, str, str, int, str, int)
    def receive_art(self, provider, ident, url, token, scope='', request=0):
        if self._closed or token != self._token or provider not in self.enabled_providers():
            return
        if scope and (scope not in self._requests or self._requests[scope][0]!=request):return
        old=self._rows.get(provider,[])
        changed={row['category'] for row in old if row['id']==ident and (row['category']==scope if scope else row['category'] not in self._requests) and row.get('coverUrl')!=url}
        if not changed:return
        self._rows[provider] = [{**row, 'coverUrl': url} if row['id']==ident and row['category'] in changed else row for row in old]
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
