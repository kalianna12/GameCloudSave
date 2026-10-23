"""Local achievements: serialized background file I/O and foreground-safe toasts."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time
import threading
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
from PySide6.QtWidgets import QFileDialog
from achievement_files import (discover, identify, merge_progress, namespace,
                               normalize_schema, parse_state, read_text, steam_schema,canonical_states)


class Repository:
    """Accessed only on the single achievements worker, independent of Store writes."""
    def __init__(self, profile):
        self.root = Path(profile) / 'achievements'; self.configs = None; self.records = None

    def load(self):
        if self.configs is not None: return
        from services import read_json
        configs = read_json(self.root / 'config.json', {})
        records = read_json(self.root / 'progress.json', {})
        if not isinstance(configs, dict) or not isinstance(records, dict): raise ValueError('成就缓存格式错误，请保留文件以便修复')
        self.configs = configs; self.records = records

    def save(self):
        from services import write_json
        write_json(self.root / 'config.json', self.configs)
        write_json(self.root / 'progress.json', self.records)

    def config(self, ident):
        self.load(); return self.configs.setdefault(ident, {'enabled': True, 'notifications': True, 'appid': '', 'source': '', 'schema': [], 'sources': []})

    def record(self, ident, config):
        key = ident + ':' + namespace(config.get('appid', ''), config.get('source', ''))
        return self.records.setdefault(key, {})

    def setup(self, game, local, refresh=False, baseline=True):
        config = self.config(game['id'])
        config['platform']=game.get('platform') or 'local'
        if config['platform']=='steam':config['notifications']=False
        appid = identify(game, local, config.get('appid', ''))
        scan_local=dict(local,achievement_roots=config.get('roots',[]))
        found = discover(game, scan_local, appid)
        config['appid'] = appid; config['sources'] = found['sources']
        config['checked']=found.get('checked',[]);config['rejected']=found.get('rejected',[])
        if not config.get('source') and len(found['sources']) == 1:
            config['source'] = found['sources'][0]
            if not baseline: self.record(game['id'], config)['initialized'] = True
        if found['schemas'] and (not config.get('schema') or refresh):
            config['schema_source'] = found['schemas'][0][0]; config['schema'] = found['schemas'][0][1]
        if config.get('source') and baseline:
            try: states = parse_state(config['source'])
            except FileNotFoundError:
                self.record(game['id'], config)['initialized'] = True; states = None
            except (OSError, ValueError): states = None
            if states is not None: merge_progress(self.record(game['id'], config), canonical_states(states,config.get('schema',[])))
        self.save(); return config

    def view(self, ident, message=''):
        config = self.config(ident); record = self.record(ident, config)
        schema = {row['id']: row for row in config.get('schema', [])}
        states = record.get('progress', {}); unlocks = record.get('unlocks', {})
        rows = []
        for key in dict.fromkeys([*schema, *states, *unlocks]):
            row = dict(schema.get(key) or {'id': key, 'name': key, 'description': '尚未匹配成就说明', 'icon': '', 'hidden': False, 'max': 0})
            row.update(unlocked=key in unlocks, unlocked_at=time.strftime('%Y-%m-%d %H:%M', time.localtime(unlocks[key])) if unlocks.get(key,0)>0 else '时间未知' if key in unlocks else '', progress=states.get(key, {}).get('progress', 0))
            row.update(secret_name=row['name'],secret_description=row['description'],unlocked_time=unlocks.get(key,0))
            if row['hidden'] and not row['unlocked']: row.update(name='隐藏成就', description='解锁后显示详情')
            icon = self.icon_path(row)
            row['iconUrl'] = QUrl.fromLocalFile(icon).toString() if icon else ''
            rows.append(row)
        rows.sort(key=lambda row: (not row['unlocked'], row['name']))
        if not message:
            if config.get('last_error'):
                message='上次匹配未完成：'+config['last_error']+('；已缓存定义保留' if schema else '')
            elif not config.get('source'):
                message = '找到多个记录，请选择本次游玩的账号／目录' if len(config.get('sources', [])) > 1 else '尚未找到可读取的成就记录；可选择记录文件，游戏首次解锁后也可能才生成文件'
            elif not Path(config['source']).is_file(): message = '记录文件尚未生成；游玩时会等待它出现'
            else: message = '本地记录已同步；启动游戏后监听新解锁' if config.get('schema') else '已读取进度；请匹配成就定义以显示名称与图标'
        valid=set(schema) or {row['id'] for row in rows}
        return {**{k: v for k, v in config.items() if k != 'schema'}, 'ident': ident, 'rows': rows,
                'total': len(valid), 'has_schema': bool(schema), 'unlocked': len(valid&set(unlocks)), 'message': message, 'busy': False,
                'icons_done':sum(bool(self.icon_path(row)) for row in schema.values()),'icons_total':sum(bool(row.get('icon')) for row in schema.values())}

    def summary(self,ident):
        config=self.config(ident);record=self.record(ident,config);schema=config.get('schema',[])
        keys={row['id'] for row in schema} or set(record.get('progress',{}))|set(record.get('unlocks',{}))
        return {'total':len(keys),'unlocked':len(keys&set(record.get('unlocks',{}))),
                'has_schema':bool(schema),'has_record':bool(config.get('source')) and Path(config['source']).is_file(),
                'source':config.get('source',''),'appid':config.get('appid',''),'provider':config.get('schema_source',''),
                'enabled':config.get('enabled',True),'ambiguous':len(config.get('sources',[]))>1 and not config.get('source'),
                'icons_cached':sum(bool(self.icon_path(row)) for row in schema),'icons_total':sum(bool(row.get('icon')) for row in schema)}

    def icon_path(self, row):
        value = row.get('icon', '')
        if not value: return ''
        if Path(value).is_absolute() or not urlsplit(value).scheme: return value if Path(value).is_file() else ''
        path = self.root / 'icons' / (hashlib.sha256(value.encode()).hexdigest() + '.img')
        return str(path) if path.is_file() else ''

    def cache_icons(self, schema):
        for row in schema:
            url = row.get('icon', '')
            if self.icon_path(row) or not url: continue
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname not in ('cdn.cloudflare.steamstatic.com', 'cdn.akamai.steamstatic.com', 'shared.fastly.steamstatic.com', 'steamcdn-a.akamaihd.net'): continue
            try:
                with urlopen(Request(url, headers={'User-Agent': 'GameCloudSave/2.5'}), timeout=3) as response: data = response.read(1024*1024 + 1)
                if not data or len(data) > 1024*1024: continue
                path = self.root / 'icons' / (hashlib.sha256(url.encode()).hexdigest() + '.img')
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.tmp'); temporary.write_bytes(data); temporary.replace(path)
            except OSError: continue


class Achievements(QObject):
    changed = Signal()
    completed = Signal(int, str, object, str)
    polled = Signal(object)
    schemaReady = Signal(str, str, object, str)
    iconsReady = Signal(str)
    searchReady = Signal(int, str, object, str)
    catalogChanged=Signal()
    catalogReady=Signal(object)
    batchChanged=Signal()
    batchReady=Signal(object)
    iconProgress=Signal(str,int,int,int)

    def __init__(self, store, parent=None):
        super().__init__(parent); self.store = store; self.repository = Repository(store.profile)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievements')
        self.network = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievement-metadata')
        self.icons = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievement-icons')
        self.batch_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='achievement-batch')
        self._batch_cancel=threading.Event();self._batch={'running':False,'done':0,'total':0,'message':'选择游戏后开始批量匹配'}
        self._summaries={};self._overview=[];self._recent=[];self._catalog_revision=0;self._icon_jobs=set();self._providers={}
        self._icon_wanted={}
        self._fetching = set();self._auto_attempted=set()
        self._wanted = {}
        self._fetch_serial = {}
        self._state = {'busy': False, 'ident': '', 'message': '选择一款本地游戏以匹配成就', 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0}
        self._serial = 0; self.closed = False; self.sessions = {}; self.polling = False
        from achievement_overlay import AchievementOverlay
        self.overlay = AchievementOverlay(self)
        self.completed.connect(self.receive); self.polled.connect(self.receivePoll)
        self.schemaReady.connect(self.receiveSchema); self.iconsReady.connect(self.refreshView)
        self.searchReady.connect(self.receiveSearch)
        self.catalogReady.connect(self.receiveCatalog);self.batchReady.connect(self.receiveBatch);self.iconProgress.connect(self.receiveIcons)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.poll)
        QTimer.singleShot(0,self.refreshCatalog)

    @Property('QVariantMap', notify=changed)
    def state(self): return self._state

    @Property(int,notify=catalogChanged)
    def summaryRevision(self):return self._catalog_revision

    @Property('QVariantList',notify=catalogChanged)
    def overview(self):return self._overview

    @Property('QVariantList',notify=catalogChanged)
    def recent(self):return self._recent

    @Property('QVariantMap',notify=batchChanged)
    def batchState(self):return self._batch

    @Property('QVariantList',constant=True)
    def providers(self):
        from achievement_sources import PROVIDERS
        return PROVIDERS

    @Slot(str,result='QVariantMap')
    def summary(self,ident):return self._summaries.get(ident,{})

    def publish(self):
        summaries={};rows=[];recent=[]
        for game in list(self.store.games):
            ident=game['id'];config=self.repository.config(ident)
            value=self.repository.summary(ident)
            definitions={r['id']:r for r in config.get('schema',[])}
            for key,stamp in self.repository.record(ident,config).get('unlocks',{}).items():
                if stamp>0 and key in definitions:
                    recent.append({'game':game['name'],'name':definitions[key]['name'],'time':time.strftime('%Y-%m-%d %H:%M',time.localtime(stamp)),'stamp':stamp})
            if value['total']:summaries[ident]=value
            rows.append(dict(value,id=ident,name=game['name'],platform=game.get('platform') or 'local',
                             supported=game.get('platform') in ('local','steam','',None),
                             error=config.get('last_error',''),status='已就绪' if value['has_schema'] and value['has_record'] else '待选择记录' if value['ambiguous'] else '已匹配 · 尚无记录' if value['has_schema'] else '匹配失败' if config.get('last_error') else '待匹配'))
        if not self.closed:self.catalogReady.emit({'summaries':summaries,'rows':rows,'recent':sorted(recent,key=lambda r:-r['stamp'])[:200]})

    @Slot()
    def refreshCatalog(self):
        if self.closed:return
        def work():
            try:self.publish()
            except Exception:pass
        self.pool.submit(work)

    @Slot(object)
    def receiveCatalog(self,result):
        if self.closed:return
        if result['summaries']==self._summaries and result['rows']==self._overview and result['recent']==self._recent:return
        self._summaries=result['summaries'];self._overview=result['rows'];self._recent=result['recent'];self._catalog_revision+=1;self.catalogChanged.emit()

    @Slot('QVariantList',str,bool)
    def batch(self,ids,provider='auto',force=False):
        if self.closed or self._batch['running']:return
        wanted=set(ids);games=[deepcopy(g) for g in self.store.games if (not wanted or g['id'] in wanted) and g.get('platform') in ('local','steam','',None)]
        local=deepcopy(self.store.local);self._batch_cancel.clear()
        self._batch={'running':True,'done':0,'total':len(games),'message':'正在检测成就记录与匹配定义','errors':[]};self.batchChanged.emit()
        def run():
            done=0;errors=[]
            try:
                for game in games:
                    if self.closed or self._batch_cancel.is_set():break
                    ident=game['id'];message=''
                    try:
                        config=deepcopy(self.pool.submit(self.repository.setup,game,local.get(ident,{}),False,ident not in self.sessions).result())
                        appid=config.get('appid','')
                        if not appid and provider!='local':
                            from network_metadata import lookup
                            identity=lookup(game['name'],Path(local.get(ident,{}).get('install_dir','')).name,cancel=self._batch_cancel)
                            appid=identity.get('steam_appid','')
                        # Normal refresh reuses cached definitions; full refresh is explicit.
                        if force or not config.get('schema'):
                            if not appid and not config.get('schema'):raise ValueError('没有可靠的 App ID；请在单游戏页搜索并确认版本')
                            from achievement_sources import resolve
                            rows,label,failures=resolve(appid,provider,config.get('schema'),steam_fetch=steam_schema)
                            def apply():
                                current=self.repository.config(ident)
                                if current.get('appid')!=appid:current.update(source='',sources=[])
                                current.update(appid=appid,schema=rows,schema_source=label,provider=provider,last_error='')
                                self.repository.setup(game,local.get(ident,{}),baseline=ident not in self.sessions)
                                if failures:current['source_notes']=failures
                                self.repository.save();return deepcopy(current)
                            config=self.pool.submit(apply).result()
                        if not self.closed:self.cacheAll(ident,config.get('schema',[]))
                    except Exception as exc:
                        message=str(exc)[:240];errors.append({'id':ident,'name':game['name'],'message':message})
                        def remember_error():
                            self.repository.config(ident)['last_error']=message;self.repository.save()
                        self.pool.submit(remember_error).result()
                    done+=1
                    self.pool.submit(self.publish).result()
                    if not self.closed:self.batchReady.emit({'running':True,'done':done,'total':len(games),'message':game['name']+('：'+message if message else '：定义与记录检测完成'),'errors':list(errors)})
            finally:
                if not self.closed:self.batchReady.emit({'running':False,'done':done,'total':len(games),'message':'已停止，已完成内容保留' if self._batch_cancel.is_set() else '批量检测完成；图标继续后台缓存，缺失项可在单游戏页处理','errors':errors})
        self.batch_pool.submit(run)

    @Slot(object)
    def receiveBatch(self,result):
        if self.closed:return
        self._batch=result;self.batchChanged.emit()
        if not result['running'] and self._state.get('ident'):self.refreshView(self._state['ident'])

    @Slot()
    def cancelBatch(self):self._batch_cancel.set()

    def game(self, ident):
        return next((deepcopy(g) for g in self.store.games if g['id'] == ident), None)

    def submit(self, ident, work):
        if self.closed or self._state.get('busy'): return
        self._serial += 1; serial = self._serial
        self._state.update(ident=ident, busy=True, message='正在读取成就资料'); self.changed.emit()
        def run():
            try: result = work(); error = ''
            except Exception as exc: result = None; error = str(exc)[:220]
            if not self.closed: self.completed.emit(serial, ident, result, error)
        self.pool.submit(run)

    @Slot(int, str, object, str)
    def receive(self, serial, ident, result, error):
        if self.closed or serial != self._serial or ident != self._state.get('ident'): return
        if error: self._state.update(busy=False, message='成就：'+error)
        else: self._state = result
        self.changed.emit()
        self.refreshCatalog()
        if not error and (result.get('enabled') is False or result.get('notifications') is False): self.overlay.discard(ident)
        needs_schema=not error and (not result.get('has_schema') or result.get('platform')=='steam' and result.get('provider','auto')=='auto' and not result.get('schema_source','').startswith('Steam 公开'))
        if needs_schema and result.get('appid') and not result.get('candidates') and (ident,result['appid']) not in self._auto_attempted:
            self._auto_attempted.add((ident,result['appid']));self.fetchSchema(ident, result['appid'])

    @Slot(str)
    def openFor(self, ident):
        game = self.game(ident)
        if not game: return
        if game.get('platform') not in ('local','steam', '', None):
            self._serial += 1
            self._state = {'ident': ident, 'busy': False, 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0, 'message': '此平台暂不支持自动读取；可使用本地游戏条目和对应记录'}; self.changed.emit(); return
        # A newly selected game invalidates old results without cancelling its disk write.
        self._serial += 1; self._state = {'ident': ident, 'busy': False, 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0}
        local = deepcopy(self.store.local.get(ident, {}))
        def work():
            config=self.repository.setup(game, local, baseline=ident not in self.sessions)
            self.cacheAll(ident,config.get('schema',[]))
            return self.repository.view(ident)
        self.submit(ident, work)

    @Slot(str, str)
    def search(self, ident, query):
        # Use the existing bounded Steam catalog and show candidates for explicit selection.
        if self.closed or self._state.get('busy'): return
        self._serial += 1; serial = self._serial
        self._state.update(ident=ident, busy=True, message='正在搜索对应游戏'); self.changed.emit()
        def find():
            try:
                from cover_sources import search
                rows = search(self.store, query, 'steam', False)[:16]; error = ''
            except Exception as exc: rows = []; error = str(exc)[:180]
            if not self.closed: self.searchReady.emit(serial, ident, rows, error)
        self.network.submit(find)

    @Slot(int, str, object, str)
    def receiveSearch(self, serial, ident, rows, error):
        if self.closed or serial != self._serial or ident != self._state.get('ident'): return
        def work():
            view = dict(self.repository.view(ident), candidates=[{'appid': r['appid'], 'name': r['name']} for r in rows], message='请选择对应版本，再匹配成就' if rows else '未找到游戏，可输入 Steam App ID 或导入定义')
            if not self.closed: self.completed.emit(serial, ident, view, error)
        self.pool.submit(work)

    @Slot(str, str)
    def match(self, ident, appid):
        if not self.game(ident) or self._state.get('busy'): return
        self._serial += 1
        self._state.update(message='正在匹配成就定义，游戏监听保持运行'); self.changed.emit()
        self.fetchSchema(ident, appid)

    @Slot(str,str,str)
    def matchSource(self,ident,appid,provider):
        self._providers[ident]=provider;self.match(ident,appid)

    def fetchSchema(self, ident, appid):
        if self.closed: return
        self._wanted[ident] = appid
        self._fetch_serial[(ident, appid)] = self._serial
        if (ident, appid) in self._fetching: return
        self._fetching.add((ident, appid))
        def run():
            try:
                from achievement_sources import resolve
                config=self.pool.submit(lambda:deepcopy(self.repository.config(ident))).result()
                local_rows=config.get('schema',[]) if config.get('appid') in ('',appid) else []
                rows,label,failures=resolve(appid,self._providers.get(ident,config.get('provider','auto')),local_rows,steam_fetch=steam_schema)
                for row in rows:row['_definition_source']=label
                error = ''
            except Exception as exc: rows = []; error = str(exc)[:180]
            if not self.closed: self.schemaReady.emit(ident, appid, rows, error)
        self.network.submit(run)

    @Slot(str, str, object, str)
    def receiveSchema(self, ident, appid, rows, error):
        self._fetching.discard((ident, appid))
        serial = self._fetch_serial.pop((ident, appid), -1)
        if self.closed or self._wanted.get(ident) != appid: return
        if error:
            if self._state.get('ident') == ident: self._state.update(message='联网匹配暂不可用，已有成就保留；可重试或导入定义。'+error); self.changed.emit()
            return
        game = self.game(ident)
        if not game: return
        local = deepcopy(self.store.local.get(ident, {}))
        def write():
            try:
                config = self.repository.config(ident)
                changed_identity = config.get('appid') != appid
                if changed_identity: config.update(source='', schema=[], sources=[])
                config.update(appid=appid, schema=rows, schema_source=rows[0].get('_definition_source','Steam 公开成就资料'),provider=self._providers.get(ident,'auto'),last_error='')
                self.repository.setup(game, local, baseline=ident not in self.sessions or changed_identity); self.repository.save()
                view = self.repository.view(ident)
                if not self.closed: self.completed.emit(serial, ident, view, '')
                self.publish()
            except Exception as exc:
                if not self.closed: self.completed.emit(serial, ident, None, str(exc)[:180])
        self.pool.submit(write)
        self.cacheAll(ident,rows)

    def cacheAll(self,ident,rows):
        if self.closed:return
        self._icon_wanted[ident]=rows
        if ident in self._icon_jobs:return
        self._icon_jobs.add(ident)
        def run():
            assets=[row for row in rows if row.get('icon')];failed=0
            try:
                for index,row in enumerate(assets):
                    if self.closed:break
                    self.repository.cache_icons([row])
                    if not self.repository.icon_path(row):failed+=1
                    if index%8==0 or index==len(assets)-1:self.iconProgress.emit(ident,index+1,len(assets),failed)
            finally:
                self._icon_jobs.discard(ident)
                if not self.closed:self.iconsReady.emit(ident)
                latest=self._icon_wanted.get(ident)
                if not self.closed and latest is not rows:self.cacheAll(ident,latest)
        self.icons.submit(run)

    @Slot(str,int,int,int)
    def receiveIcons(self,ident,done,total,failed):
        if self.closed:return
        if self._state.get('ident')==ident:
            self._state.update(icons_done=done,icons_total=total,icons_failed=failed);self.changed.emit()
        if done==total:self.refreshCatalog()

    @Slot(str)
    def refreshView(self, ident):
        if self.closed or ident != self._state.get('ident') or self._state.get('busy'): return
        serial = self._serial
        def work():
            if not self.closed: self.completed.emit(serial, ident, self.repository.view(ident), '')
        self.pool.submit(work)

    @Slot(str, 'QVariantMap')
    def save(self, ident, values):
        def work():
            config = deepcopy(self.repository.config(ident))
            for key in ('enabled', 'notifications'):
                if key in values:
                    if type(values[key]) is not bool: raise ValueError('成就开关无效')
                    config[key] = values[key]
            if (self.game(ident) or {}).get('platform')=='steam':config['notifications']=False
            if 'provider' in values:
                from achievement_sources import PROVIDERS
                if values['provider'] not in {p['id'] for p in PROVIDERS}:raise ValueError('成就来源不存在')
                config['provider']=values['provider']
            source = str(values.get('source', config.get('source', ''))).strip()
            if source:
                if Path(source).suffix.casefold() not in ('.json', '.ini','.bin'): raise ValueError('请选择 JSON、INI 或 Steam BIN 成就记录')
                if Path(source).is_file():
                    parsed = parse_state(source)
                    if not parsed and Path(source).suffix.casefold() == '.json' and normalize_schema(json.loads(read_text(source))):
                        raise ValueError('这是成就定义，请用“导入定义”；记录文件需要包含 earned / achieved / unlocked 等进度字段')
            if source != config.get('source'): config['source'] = source
            if source and Path(source).is_file(): merge_progress(self.repository.record(ident, config), canonical_states(parse_state(source),config.get('schema',[])))
            self.repository.configs[ident] = config
            self.repository.save(); return self.repository.view(ident, '方案已保存；已有进度已导入，不重复弹出')
        self.submit(ident, work)

    @Slot(str)
    def pickSource(self, ident):
        path, _ = QFileDialog.getOpenFileName(None, '选择游戏生成的成就记录', '', '成就记录 (*.json *.ini *.bin)')
        if path: self.save(ident, {'source': path})

    @Slot(str)
    def importSchema(self, ident):
        path, _ = QFileDialog.getOpenFileName(None, '导入成就定义（包含名称和内部编号）', '', '成就定义 (*.json)')
        if not path: return
        def work():
            rows = normalize_schema(json.loads(read_text(path)), Path(path).parent)
            if not rows: raise ValueError('该文件只有进度或没有 displayName，不能作为成就定义')
            self.repository.config(ident).update(schema=rows, schema_source=path)
            self.repository.save(); return self.repository.view(ident)
        self.submit(ident, work)

    @Slot(str)
    def addRoot(self,ident):
        root=QFileDialog.getExistingDirectory(None,'选择成就记录可能所在的目录')
        if not root:return
        game=self.game(ident);local=deepcopy(self.store.local.get(ident,{}))
        def work():
            config=self.repository.config(ident);config['roots']=list(dict.fromkeys(config.get('roots',[])+[root]))[-10:]
            self.repository.setup(game,local,baseline=ident not in self.sessions)
            return self.repository.view(ident)
        self.submit(ident,work)

    @Slot()
    def preview(self):
        self.overlay.enqueue({'name': '新的冒险', 'description': '弹窗不会抢走游戏焦点，也不会拦截鼠标。'}, {}, True)

    def begin(self, ident):
        """Called before launch; baseline reads on the same serial worker as polling."""
        game = self.game(ident)
        if self.closed or not game or game.get('platform') not in ('local','steam', '', None): return
        session = {'ident': ident, 'game': game, 'local': deepcopy(self.store.local.get(ident, {})), 'target': {}, 'created': time.monotonic(), 'primed': False, 'signature': None, 'discovery': 0}
        if game.get('platform')=='steam':
            # Steam may launch through an already-running client, without a
            # detectable child window. Silent cache statistics can still sync.
            import psutil
            session['target']={'pid':os.getpid(),'hwnd':0,'created':psutil.Process().create_time(),'cache_only':True}
        self.sessions[ident] = session
        def prime():
            try:
                self.repository.setup(game, session['local'])
                session['primed'] = True
                config = self.repository.config(ident)
                self.cacheAll(ident,config.get('schema',[]))
                if config.get('enabled', True) and config.get('appid') and not config.get('schema'):
                    # Signal to GUI; network work never holds the monitoring worker.
                    if not self.closed:self.polled.emit({'events': [], 'ended': [], 'view': None, 'fetch': (ident, config['appid'])})
            except Exception: session['primed'] = True
        baseline = self.pool.submit(prime); self.timer.start(); return baseline

    def attach(self, ident, pid, hwnd):
        if ident not in self.sessions: self.begin(ident)
        if ident in self.sessions:
            target = {'pid': pid, 'hwnd': hwnd}
            try:
                import psutil
                target['created'] = psutil.Process(pid).create_time()
            except Exception: pass
            self.sessions[ident]['target'] = target

    def poll(self):
        if self.closed or self.polling: return
        self.polling = True; sessions = list(self.sessions.values()); selected = self._state.get('ident', '')
        def run():
            events = []; ended = []; changed = False;any_changed=False
            for session in sessions:
                target = dict(session['target']); ident = session['ident']
                if not target:
                    if time.monotonic()-session['created'] > 360: ended.append((ident, session['created']))
                    continue
                try:
                    import psutil
                    try:
                        process = psutil.Process(target['pid'])
                        if process.create_time() != target.get('created', process.create_time()): ended.append((ident, session['created'])); continue
                    except psutil.NoSuchProcess:
                        # Read once more after exit: some games flush the final
                        # achievement immediately before their process terminates.
                        ended.append((ident, session['created']))
                    config = self.repository.config(ident)
                    if not config.get('enabled', True): continue
                    source = config.get('source', '')
                    if not source and time.monotonic()-session['discovery'] > 8:
                        # Discovery never baselines a newly generated file during a game.
                        found = discover(session['game'], dict(session['local'],achievement_roots=config.get('roots',[])), config.get('appid', ''))
                        session['discovery'] = time.monotonic(); config['sources'] = found['sources']
                        if len(found['sources']) == 1:
                            source = config['source'] = found['sources'][0]
                            self.repository.record(ident, config)['initialized'] = True
                            self.repository.save()
                    if not source: continue
                    path = Path(source); stat = path.stat(); signature = (config.get('appid'), source, stat.st_mtime_ns, stat.st_size)
                    if signature == session['signature']: continue
                    states = canonical_states(parse_state(path),config.get('schema',[]))
                    # Empty/partial transient writes do not erase remembered progress.
                    if not states and stat.st_size == 0: continue
                    record = self.repository.record(ident, config)
                    keys, dirty = merge_progress(record, states, notify=True)
                    session['signature'] = signature
                    if dirty: self.repository.save(); changed = changed or ident == selected;any_changed=True
                    schema = {r['id']: r for r in config.get('schema', [])}
                    if config.get('notifications', True) and session['game'].get('platform')!='steam':
                        for key in keys:
                            row = dict(schema.get(key) or {'id': key, 'name': key, 'description': ''})
                            row.update(game_id=ident, game_name=session['game']['name'], icon_path=self.repository.icon_path(row))
                            events.append((row, target))
                except psutil.NoSuchProcess: ended.append((ident, session['created']))
                except Exception: continue  # Writing/atomic replace/file missing: retry, preserve history.
            view = self.repository.view(selected) if changed else None
            if not self.closed: self.polled.emit({'events': events, 'ended': ended, 'view': view})
            if any_changed:self.publish()
        self.pool.submit(run)

    @Slot(object)
    def receivePoll(self, result):
        self.polling = False
        if self.closed: return
        for ident, created in result['ended']:
            if ident in self.sessions and self.sessions[ident]['created'] == created: self.sessions.pop(ident)
        for row, target in result['events']:
            # Bound to the exact owned scaler and its source, never any Magpie window.
            graphics = getattr(self.parent(), '_graphics', None)
            if graphics and graphics.engine.target and graphics.engine.target[0] == target['pid']:
                try:
                    from graphics_enhancement import SCALING_CLASS
                    from ctypes import wintypes as W
                    import ctypes
                    user = ctypes.windll.user32; user.FindWindowW.argtypes = [W.LPCWSTR, W.LPCWSTR]; user.FindWindowW.restype = W.HWND
                    target['scaler'] = int(user.FindWindowW(SCALING_CLASS, None) or 0)
                except Exception: pass
            self.overlay.enqueue(row, target)
        if result.get('fetch') and tuple(result['fetch']) not in self._auto_attempted:
            self._auto_attempted.add(tuple(result['fetch']));self.fetchSchema(*result['fetch'])
        if result['view'] and result['view']['ident'] == self._state.get('ident') and not self._state.get('busy'):
            self._state = result['view']; self.changed.emit()
        if not self.sessions: self.timer.stop()

    def shutdown(self):
        self.closed = True; self.timer.stop(); self.overlay.shutdown()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.network.shutdown(wait=False, cancel_futures=True)
        self.icons.shutdown(wait=False, cancel_futures=True)
        self._batch_cancel.set();self.batch_pool.shutdown(wait=False,cancel_futures=True)
