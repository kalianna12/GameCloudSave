"""Local achievements: serialized background file I/O and background progress synchronization."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import configparser
import hashlib
import json
import os
from pathlib import Path
import time
import threading
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, QFileSystemWatcher
from PySide6.QtWidgets import QFileDialog
from achievement_files import (discover, identify, merge_progress, namespace,
                               normalize_schema, parse_state, read_text, steam_schema,canonical_states)


class Repository:
    """Accessed only on the single achievements worker, independent of Store writes."""
    def __init__(self, profile):
        self.root = Path(profile) / 'achievements'; self.configs = None; self.records = None
        self.health = {}

    def load(self):
        if self.configs is not None: return
        from services import read_json
        configs = read_json(self.root / 'config.json', {})
        records = read_json(self.root / 'progress.json', {})
        if not isinstance(configs, dict) or not isinstance(records, dict): raise ValueError('成就缓存格式错误，请保留文件以便修复')
        for config in configs.values():config.pop('notifications',None)
        self.configs = configs; self.records = records

    def save(self):
        from services import write_json
        write_json(self.root / 'config.json', self.configs)
        write_json(self.root / 'progress.json', self.records)

    def config(self, ident):
        self.load(); return self.configs.setdefault(ident, {'enabled': True, 'appid': '', 'source': '', 'schema': [], 'sources': []})

    def record(self, ident, config):
        key = ident + ':' + namespace(config.get('appid', ''), config.get('source', ''))
        return self.records.setdefault(key, {})

    def setup(self, game, local, refresh=False, baseline=True):
        config = self.config(game['id'])
        config['platform']=game.get('platform') or 'local'
        appid = identify(game, local, config.get('appid', ''))
        scan_local=dict(local,achievement_roots=config.get('roots',[]))
        found = discover(game, scan_local, appid)
        previous=config.get('source','')
        if previous and Path(previous).name.casefold() in ('stats.ini','user_stats.ini') and Path(previous).is_file():
            from achievement_files import empty_record
            try:
                if not parse_state(previous) and not empty_record(previous):
                    config['source']='';config['record_note']='旧记录为普通统计，已改用成就记录；原文件未修改'
            except (OSError,ValueError,configparser.Error):pass
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
            except (OSError, ValueError,configparser.Error): states = None
            if states is not None:
                from achievement_files import empty_record
                config['record_empty']=not states and empty_record(config['source'])
                record=self.record(game['id'], config)
                # SSE CRCs cannot be named before definitions arrive. Keep the
                # initial raw baseline so later matching doesn't replay history.
                if not record.get('initialized') and any(k.startswith('crc32:') for k in states): record['pending_baseline']=states
                merge_progress(record, canonical_states(states,config.get('schema',[])))
        self.save(); return config

    def view(self, ident, message=''):
        config = self.config(ident); record = self.record(ident, config)
        schema = {row['id']: row for row in config.get('schema', [])}
        states = record.get('progress', {}); unlocks = record.get('unlocks', {})
        rows = []
        for key in dict.fromkeys([*schema, *states, *unlocks]):
            row = dict(schema.get(key) or {'id': key, 'name': key, 'description': '尚未匹配成就说明', 'icon': '', 'hidden': False, 'max': 0})
            row.update(unlocked=key in unlocks, unlocked_at=time.strftime('%Y-%m-%d %H:%M', time.localtime(unlocks[key])) if unlocks.get(key,0)>0 else '时间未知' if key in unlocks else '', progress=states.get(key, {}).get('progress', 0))
            if not row.get('max'):row['max']=states.get(key,{}).get('max',0)
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
        matched=len(set(states)&set(schema))
        if not config.get('source'):record_status='待选择记录' if len(config.get('sources',[]))>1 else '尚未找到记录'
        elif not Path(config['source']).is_file():record_status='等待记录生成'
        elif not schema:record_status='已读取记录 · 待匹配定义'
        elif not states:record_status='等待首次解锁（成就文件已存在）' if config.get('record_empty') else '记录中暂无可读条目'
        elif not matched:record_status='记录与成就 ID 不匹配 · 请检查游戏版本'
        else:record_status=f'已读取 {len(states)} 项 · 对应定义 {matched} 项'
        return {**{k: v for k, v in config.items() if k != 'schema'}, 'ident': ident, 'rows': rows,
                'monitor_status': '监听已关闭' if config.get('enabled') is False else self.health.get(ident, '后台同步记录（约每秒）；游戏写入后更新' if config.get('source') else '等待可读取的成就记录'),
                'record_status':record_status,'record_entries':len(states),'record_matched':matched,
                'total': len(valid), 'has_schema': bool(schema), 'has_record':bool(config.get('source')) and Path(config['source']).is_file(), 'unlocked': len(valid&set(unlocks)), 'message': message, 'busy': False,
                'icons_done':sum(bool(self.icon_path(row)) for row in schema.values()),'icons_total':sum(bool(row.get('icon')) for row in schema.values())}

    def summary(self,ident):
        config=self.config(ident);record=self.record(ident,config);schema=config.get('schema',[])
        keys={row['id'] for row in schema} or set(record.get('progress',{}))|set(record.get('unlocks',{}))
        return {'total':len(keys),'unlocked':len(keys&set(record.get('unlocks',{}))),
                'record_ready':bool(keys&set(record.get('progress',{}))),
                'record_empty':config.get('record_empty',False),
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
    enabledChanged = Signal()
    enableSaved = Signal(int, str)
    switchesSaved = Signal(str, int, object, str)
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
        self._summaries={};self._overview=[];self._recent=[];self._analytics=[];self._statistics_cache={};self._catalog_revision=0;self._icon_jobs=set();self._providers={}
        self._icon_wanted={}
        self._fetching = set();self._auto_attempted=set()
        self._wanted = {}
        self._fetch_serial = {}
        self._state = {'busy': False, 'ident': '', 'message': '选择一款本地游戏以匹配成就', 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0}
        self._serial = 0; self.closed = False; self.polling = False
        self._enabled = bool(store.settings.get('achievements_enabled', True));self._enable_serial=0
        self._policies={};self._policy_pending={};self._policy_versions={};self._policy_serial=0;self._poll_epoch=0
        self.controls = ThreadPoolExecutor(max_workers=1,thread_name_prefix='achievement-controls')
        self._passive = {}
        self.enableSaved.connect(self.receiveEnabled);self.switchesSaved.connect(self.receiveSwitches)
        self.completed.connect(self.receive); self.polled.connect(self.receivePoll)
        self.schemaReady.connect(self.receiveSchema); self.iconsReady.connect(self.refreshView)
        self.searchReady.connect(self.receiveSearch)
        self.catalogReady.connect(self.receiveCatalog);self.batchReady.connect(self.receiveBatch);self.iconProgress.connect(self.receiveIcons)
        self.timer = QTimer(self); self.timer.setInterval(10000); self.timer.timeout.connect(self.poll)
        self.watcher=QFileSystemWatcher(self)
        self.fileDelay=QTimer(self);self.fileDelay.setSingleShot(True);self.fileDelay.setInterval(80);self.fileDelay.timeout.connect(self.poll)
        self._poll_pending=False
        self.watcher.fileChanged.connect(self.schedulePoll)
        self.watcher.directoryChanged.connect(self.directoryChanged)
        QTimer.singleShot(0,self.refreshCatalog)

    @Property('QVariantMap', notify=changed)
    def state(self): return self._state

    @Property(bool, notify=enabledChanged)
    def enabled(self):return self._enabled and not self.closed

    @Slot(bool)
    def setEnabled(self, enabled):
        if self.closed or enabled==self._enabled:return
        self._applyEnabled(enabled);self._enable_serial+=1;serial=self._enable_serial
        def persist():
            error=''
            try:self.store.save_settings({'achievements_enabled':enabled})
            except Exception as exc:error=str(exc)[:180]
            if not self.closed:self.enableSaved.emit(serial,error)
        self.controls.submit(persist)

    def _applyEnabled(self, enabled):
        self._enabled=enabled;self._poll_epoch+=1
        if enabled:
            self.syncWatches()
            if self.polling:self._poll_pending=True
            else:self.poll()
        else:
            self.timer.stop();self.fileDelay.stop();self._poll_pending=False;self._passive.clear();self._batch_cancel.set()
            paths=self.watcher.files()+self.watcher.directories()
            if paths:self.watcher.removePaths(paths)
        self.enabledChanged.emit()

    def syncWatches(self):
        if not self.enabled:return
        wanted=set()
        for row in self._overview:
            if not row.get('source') or row.get('enabled') is False:continue
            path=Path(row['source'])
            if path.is_file():wanted.add(str(path))
            if path.parent.is_dir():wanted.add(str(path.parent))
            if path.suffix.casefold()=='.bin' and path.name.startswith('UserGameStats_'):
                from achievement_steam import progress_schema_path
                schema=progress_schema_path(path)
                if schema.is_file():wanted.add(str(schema))
        current=set(self.watcher.files()+self.watcher.directories())
        if current-wanted:self.watcher.removePaths(list(current-wanted))
        if wanted-current:self.watcher.addPaths(list(wanted-current))
        if wanted:self.timer.start()
        else:self.timer.stop()

    def schedulePoll(self, path=''):
        if not self.enabled:return
        if self.polling:self._poll_pending=True
        elif not self.fileDelay.isActive():self.fileDelay.start()

    def directoryChanged(self, path):
        watched=set(self.watcher.files())
        if any(row.get('source') and str(Path(row['source'])) not in watched for row in self._overview):self.schedulePoll()

    @Slot(int,str)
    def receiveEnabled(self, serial, error):
        if self.closed or serial!=self._enable_serial:return
        if error:
            self._applyEnabled(bool(self.store.settings.get('achievements_enabled',True)))
            self._state['message']='成就总开关保存失败：'+error;self.changed.emit()
        owner=self.parent()
        if owner and hasattr(owner,'settingsChanged'):owner.settingsChanged.emit()

    @Slot(str,'QVariantMap')
    def setSwitches(self, ident, values):
        game=self.game(ident)
        if self.closed or not game:return
        values={k:v for k,v in values.items() if k=='enabled'}
        if not values or any(type(v)!=bool for v in values.values()):return
        resuming=values.get('enabled') is True and self._policies.get(ident,{}).get('enabled') is False
        local=deepcopy(self.store.local.get(ident,{}))
        self._policy_serial+=1;serial=self._policy_serial;self._policy_pending[ident]=serial
        self._policy_versions[ident]=serial
        self._policies.setdefault(ident,{}).update(values)
        def persist():
            error=''
            try:
                self.repository.config(ident).update(values)
                if resuming:self.repository.setup(game,local)
                self.repository.save()
            except Exception as exc:error=str(exc)[:180]
            flags={k:self.repository.config(ident).get(k,True) for k in ('enabled',)}
            if not self.closed:self.switchesSaved.emit(ident,serial,flags,error)
        self.pool.submit(persist)

    @Slot(str,int,object,str)
    def receiveSwitches(self, ident, serial, flags, error):
        if self.closed or self._policy_pending.get(ident)!=serial:return
        self._policy_pending.pop(ident,None);self._policies[ident]=flags
        if self._state.get('ident')==ident:
            self._state.update(flags)
            if error:self._state['message']='成就开关保存失败：'+error
            self.changed.emit()
        self.refreshCatalog()

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

    @Slot(str,int,result='QVariantMap')
    def statistics(self,ident,period):
        from achievement_statistics import statistics
        key=(ident,period,time.strftime('%Y-%m-%d'))
        if key not in self._statistics_cache:self._statistics_cache[key]=statistics(self._analytics,ident,period if period in (0,7,30,90,365) else 30)
        return self._statistics_cache[key]

    def publish(self):
        summaries={};rows=[];recent=[];analytics=[]
        from achievement_statistics import game_snapshot
        covers={}
        owner=self.parent()
        if owner and hasattr(owner,'_games_cache'):
            covers={g['id']:g.get('coverUrl','') for g in owner._games_cache or []}
        for game in list(self.store.games):
            ident=game['id'];config=self.repository.config(ident)
            value=self.repository.summary(ident)
            analytics.append(game_snapshot(game,value,config.get('schema',[]),self.repository.record(ident,config)))
            definitions={r['id']:r for r in config.get('schema',[])}
            for key,stamp in self.repository.record(ident,config).get('unlocks',{}).items():
                if stamp>0 and key in definitions:
                    recent.append({'game_id':ident,'achievement_id':key,'game':game['name'],'name':definitions[key]['name'],'time':time.strftime('%Y-%m-%d %H:%M',time.localtime(stamp)),'stamp':stamp,'iconUrl':QUrl.fromLocalFile(self.repository.icon_path(definitions[key])).toString() if self.repository.icon_path(definitions[key]) else ''})
            if value['total']:summaries[ident]=value
            rows.append(dict(value,id=ident,name=game['name'],coverUrl=covers.get(ident,''),platform=game.get('platform') or 'local',
                             supported=game.get('platform') in ('local','steam','',None),
                             error=config.get('last_error',''),status='已就绪' if value['has_schema'] and value['has_record'] and value['record_ready'] else '待选择记录' if value['ambiguous'] else '等待首次解锁' if value['has_schema'] and value['has_record'] and value['record_empty'] else '记录待验证' if value['has_schema'] and value['has_record'] else '已匹配 · 尚无记录' if value['has_schema'] else '匹配失败' if config.get('last_error') else '待匹配'))
        if not self.closed:self.catalogReady.emit({'summaries':summaries,'rows':rows,'recent':sorted(recent,key=lambda r:-r['stamp'])[:200],'analytics':analytics})

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
        if result['summaries']==self._summaries and result['rows']==self._overview and result['recent']==self._recent and result.get('analytics',[])==self._analytics:return
        if result.get('analytics',[])!=self._analytics:self._statistics_cache.clear()
        self._summaries=result['summaries'];self._overview=result['rows'];self._recent=result['recent'];self._analytics=result.get('analytics',[]);self._catalog_revision+=1;self.catalogChanged.emit()
        self.syncWatches()

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
                        config=deepcopy(self.pool.submit(self.repository.setup,game,local.get(ident,{}),False,True).result())
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
                                self.repository.setup(game,local.get(ident,{}),baseline=True)
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
        if not self.closed and not error and result and ident not in self._policy_pending:
            self._policies[ident]={k:result.get(k,True) for k in ('enabled',)}
        if self.closed or serial != self._serial or ident != self._state.get('ident'): return
        if error: self._state.update(busy=False, message='成就：'+error)
        else: self._state = result
        self.changed.emit()
        self.refreshCatalog()
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
            config=self.repository.setup(game, local, baseline=True)
            self.cacheAll(ident,config.get('schema',[]))
            return self.repository.view(ident)
        self.submit(ident, work)

    @Slot(str, str)
    @Slot(str, str, bool)
    def search(self, ident, query, use_ai=False):
        # Use the existing bounded Steam catalog and show candidates for explicit selection.
        if self.closed or self._state.get('busy'): return
        self._serial += 1; serial = self._serial
        self._state.update(ident=ident, busy=True, message='正在搜索对应游戏'); self.changed.emit()
        def find():
            try:
                from cover_sources import search
                rows = search(self.store, query, 'steam', use_ai)[:16]; error = ''
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
                self.repository.setup(game, local, baseline=True); self.repository.save()
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
            for key in ('enabled',):
                if key in values:
                    if type(values[key]) is not bool: raise ValueError('成就开关无效')
                    config[key] = values[key]
            if 'provider' in values:
                from achievement_sources import PROVIDERS
                if values['provider'] not in {p['id'] for p in PROVIDERS}:raise ValueError('成就来源不存在')
                config['provider']=values['provider']
            source = str(values.get('source', config.get('source', ''))).strip()
            if source:
                if Path(source).suffix.casefold() not in ('.json', '.ini','.bin','.cfg','.dat'): raise ValueError('请选择 JSON、INI、兼容的 CFG / DAT 或 Steam BIN 成就记录')
                if Path(source).is_file():
                    parsed = parse_state(source)
                    if not parsed and Path(source).suffix.casefold() == '.json' and normalize_schema(json.loads(read_text(source))):
                        raise ValueError('这是成就定义，请用“导入定义”；记录文件需要包含 earned / achieved / unlocked 等进度字段')
                    from achievement_files import empty_record
                    if not parsed and not empty_record(source):raise ValueError('未识别到成就记录；普通 UserStats 数值不代表解锁，请选择 achievements.ini / JSON 或兼容记录')
            if source != config.get('source'): config['source'] = source
            if source and Path(source).is_file(): merge_progress(self.repository.record(ident, config), canonical_states(parse_state(source),config.get('schema',[])))
            self.repository.configs[ident] = config
            self.repository.save(); return self.repository.view(ident, '成就方案已保存，进度已同步')
        self.submit(ident, work)

    @Slot(str)
    def pickSource(self, ident):
        path, _ = QFileDialog.getOpenFileName(None, '选择游戏生成的成就记录', '', '成就记录 (*.json *.ini *.bin *.cfg *.dat)')
        if path: self.save(ident, {'source': path})

    @Slot(str)
    def exportDefinitions(self,ident):
        def work():
            from achievement_export import export_definitions
            config=self.repository.config(ident)
            result=export_definitions(config.get('schema',[]),config.get('appid',''),self.repository.root/'exports',self.repository.icon_path)
            return self.repository.view(ident,f"已导出 {result['count']} 项定义、{result['icons']} 个图标：{result['path']}。仅导出定义包，未修改游戏文件。")
        self.submit(ident,work)

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
            self.repository.setup(game,local,baseline=True)
            return self.repository.view(ident)
        self.submit(ident,work)

    def poll(self):
        if not self.enabled or self.polling: return
        epoch=self._poll_epoch;blocked={ident for ident,p in self._policies.items() if p.get('enabled') is False}
        self.polling = True; checks = []; selected = self._state.get('ident', '')
        games = {g['id']: deepcopy(g) for g in self.store.games}
        local = deepcopy(self.store.local)
        def run():
            changed = False;any_changed=False
            view = None
            try:
                from achievement_monitor import check
                self.repository.load()
                for ident, config in list(self.repository.configs.items()):
                    if ident in blocked or ident not in games or config.get('enabled') is False: continue
                    # Only selected unmatched games scan. Idle games merely stat
                    # their configured record; never rescan the entire library.
                    if not config.get('source') and ident != selected: continue
                    state = self._passive.setdefault(ident, {'signature': None, 'discovery': 0})
                    checks.append(dict(state, ident=ident, game=games[ident], local=local.get(ident, {}), _state=state))
                for session in checks:
                    if self.closed or not self._enabled or epoch!=self._poll_epoch:break
                    updated = check(self.repository, session)
                    session['_state'].update(signature=session.get('signature'), discovery=session.get('discovery', 0))
                    changed = changed or updated and session['ident'] == selected
                    any_changed = any_changed or updated
                if changed and selected: view = self.repository.view(selected)
                if any_changed:self.publish()
            finally:
                # A failed check must never wedge the in-flight guard forever.
                if not self.closed: self.polled.emit({'view': view,'epoch':epoch})
        self.pool.submit(run)

    @Slot(object)
    def receivePoll(self, result):
        self.polling = False
        if self._poll_pending:self._poll_pending=False;self.schedulePoll()
        if not self.enabled or result.get('epoch',self._poll_epoch)!=self._poll_epoch: return
        self.syncWatches()
        if result.get('fetch') and tuple(result['fetch']) not in self._auto_attempted:
            self._auto_attempted.add(tuple(result['fetch']));self.fetchSchema(*result['fetch'])
        if result['view'] and result['view']['ident'] == self._state.get('ident'):
            # A search may still be running. Update progress without clearing
            # its busy flag, candidates or message, and never drop the refresh.
            self._state.update({k:v for k,v in result['view'].items() if k not in ('busy','message','candidates')})
            self._state.update(self._policies.get(self._state.get('ident'),{}))
            if not self._state.get('busy') and not self._state.get('candidates'): self._state['message'] = result['view']['message']
            self.changed.emit()

    def shutdown(self):
        if self.closed:return
        self.closed=True;self.timer.stop();self.fileDelay.stop()
        paths=self.watcher.files()+self.watcher.directories()
        if paths:self.watcher.removePaths(paths)
        self._passive.clear();self.polling=False;self._poll_epoch+=1
        self.controls.shutdown(wait=False,cancel_futures=False)
        # Already-queued switch writes must persist even on an immediate Quit.
        self.pool.shutdown(wait=False, cancel_futures=False)
        self.network.shutdown(wait=False, cancel_futures=True)
        self.icons.shutdown(wait=False, cancel_futures=True)
        self._batch_cancel.set();self.batch_pool.shutdown(wait=False,cancel_futures=True)
