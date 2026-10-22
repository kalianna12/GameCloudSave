"""Local achievements: serialized background file I/O and foreground-safe toasts."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
from PySide6.QtWidgets import QFileDialog
from achievement_files import (discover, identify, merge_progress, namespace,
                               normalize_schema, parse_state, read_text, steam_schema)


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
        appid = identify(game, local, config.get('appid', ''))
        found = discover(game, local, appid)
        config['appid'] = appid; config['sources'] = found['sources']
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
            if states is not None: merge_progress(self.record(game['id'], config), states)
        self.save(); return config

    def view(self, ident, message=''):
        config = self.config(ident); record = self.record(ident, config)
        schema = {row['id']: row for row in config.get('schema', [])}
        states = record.get('progress', {}); unlocks = record.get('unlocks', {})
        rows = []
        for key in dict.fromkeys([*schema, *states, *unlocks]):
            row = dict(schema.get(key) or {'id': key, 'name': key, 'description': '尚未匹配成就说明', 'icon': '', 'hidden': False, 'max': 0})
            row.update(unlocked=key in unlocks, unlocked_at=time.strftime('%Y-%m-%d %H:%M', time.localtime(unlocks[key])) if key in unlocks else '', progress=states.get(key, {}).get('progress', 0))
            if row['hidden'] and not row['unlocked']: row.update(name='隐藏成就', description='解锁后显示详情')
            icon = self.icon_path(row)
            row['iconUrl'] = QUrl.fromLocalFile(icon).toString() if icon else ''
            rows.append(row)
        rows.sort(key=lambda row: (not row['unlocked'], row['name']))
        if not message:
            if not config.get('source'):
                message = '找到多个记录，请选择本次游玩的账号／目录' if len(config.get('sources', [])) > 1 else '尚未找到可读取的成就记录；可选择记录文件，游戏首次解锁后也可能才生成文件'
            elif not Path(config['source']).is_file(): message = '记录文件尚未生成；游玩时会等待它出现'
            else: message = '本地记录已同步；启动游戏后监听新解锁' if config.get('schema') else '已读取进度；请匹配成就定义以显示名称与图标'
        return {**{k: v for k, v in config.items() if k != 'schema'}, 'ident': ident, 'rows': rows,
                'total': len(rows), 'has_schema': bool(schema), 'unlocked': sum(row['unlocked'] for row in rows), 'message': message, 'busy': False}

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

    def __init__(self, store, parent=None):
        super().__init__(parent); self.store = store; self.repository = Repository(store.profile)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievements')
        self.network = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievement-metadata')
        self.icons = ThreadPoolExecutor(max_workers=1, thread_name_prefix='achievement-icons')
        self._fetching = set()
        self._wanted = {}
        self._fetch_serial = {}
        self._state = {'busy': False, 'ident': '', 'message': '选择一款本地游戏以匹配成就', 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0}
        self._serial = 0; self.closed = False; self.sessions = {}; self.polling = False
        from achievement_overlay import AchievementOverlay
        self.overlay = AchievementOverlay(self)
        self.completed.connect(self.receive); self.polled.connect(self.receivePoll)
        self.schemaReady.connect(self.receiveSchema); self.iconsReady.connect(self.refreshView)
        self.searchReady.connect(self.receiveSearch)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.poll)

    @Property('QVariantMap', notify=changed)
    def state(self): return self._state

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
        if not error and (result.get('enabled') is False or result.get('notifications') is False): self.overlay.discard(ident)
        if not error and result.get('appid') and not result.get('has_schema') and not result.get('candidates'):
            self.fetchSchema(ident, result['appid'])

    @Slot(str)
    def openFor(self, ident):
        game = self.game(ident)
        if not game: return
        if game.get('platform') not in ('local', '', None):
            self._serial += 1
            self._state = {'ident': ident, 'busy': False, 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0, 'message': '此页用于本地游戏；平台游戏请使用平台自身成就'}; self.changed.emit(); return
        # A newly selected game invalidates old results without cancelling its disk write.
        self._serial += 1; self._state = {'ident': ident, 'busy': False, 'rows': [], 'sources': [], 'total': 0, 'unlocked': 0}
        local = deepcopy(self.store.local.get(ident, {}))
        def work():
            self.repository.setup(game, local, baseline=ident not in self.sessions)
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

    def fetchSchema(self, ident, appid):
        if self.closed: return
        self._wanted[ident] = appid
        self._fetch_serial[(ident, appid)] = self._serial
        if (ident, appid) in self._fetching: return
        self._fetching.add((ident, appid))
        def run():
            try: rows = steam_schema(appid); error = ''
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
                config.update(appid=appid, schema=rows, schema_source='Steam 公开成就资料')
                self.repository.setup(game, local, baseline=ident not in self.sessions or changed_identity); self.repository.save()
                view = self.repository.view(ident)
                if not self.closed: self.completed.emit(serial, ident, view, '')
            except Exception as exc:
                if not self.closed: self.completed.emit(serial, ident, None, str(exc)[:180])
        self.pool.submit(write)
        def icons():
            deadline = time.monotonic()+30
            for row in rows:
                if self.closed or time.monotonic()>deadline: break
                self.repository.cache_icons([row])
            if not self.closed: self.iconsReady.emit(ident)
        self.icons.submit(icons)

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
            source = str(values.get('source', config.get('source', ''))).strip()
            if source:
                if Path(source).suffix.casefold() not in ('.json', '.ini'): raise ValueError('请选择 JSON 或 INI 成就记录')
                if Path(source).is_file():
                    parsed = parse_state(source)
                    if not parsed and Path(source).suffix.casefold() == '.json' and normalize_schema(json.loads(read_text(source))):
                        raise ValueError('这是成就定义，请用“导入定义”；记录文件需要包含 earned / achieved / unlocked 等进度字段')
            if source != config.get('source'): config['source'] = source
            if source and Path(source).is_file(): merge_progress(self.repository.record(ident, config), parse_state(source))
            self.repository.configs[ident] = config
            self.repository.save(); return self.repository.view(ident, '方案已保存；已有进度已导入，不重复弹出')
        self.submit(ident, work)

    @Slot(str)
    def pickSource(self, ident):
        path, _ = QFileDialog.getOpenFileName(None, '选择游戏生成的成就记录', '', '成就记录 (*.json *.ini)')
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

    @Slot()
    def preview(self):
        self.overlay.enqueue({'name': '新的冒险', 'description': '弹窗不会抢走游戏焦点，也不会拦截鼠标。'}, {}, True)

    def begin(self, ident):
        """Called before launch; baseline reads on the same serial worker as polling."""
        game = self.game(ident)
        if self.closed or not game or game.get('platform') not in ('local', '', None): return
        session = {'ident': ident, 'game': game, 'local': deepcopy(self.store.local.get(ident, {})), 'target': {}, 'created': time.monotonic(), 'primed': False, 'signature': None, 'discovery': 0}
        self.sessions[ident] = session
        def prime():
            try:
                self.repository.setup(game, session['local'])
                session['primed'] = True
                config = self.repository.config(ident)
                if config.get('enabled', True) and config.get('appid') and not config.get('schema'):
                    # Signal to GUI; network work never holds the monitoring worker.
                    self.polled.emit({'events': [], 'ended': [], 'view': None, 'fetch': (ident, config['appid'])})
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
            events = []; ended = []; changed = False
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
                        found = discover(session['game'], session['local'], config.get('appid', ''))
                        session['discovery'] = time.monotonic(); config['sources'] = found['sources']
                        if len(found['sources']) == 1:
                            source = config['source'] = found['sources'][0]
                            self.repository.record(ident, config)['initialized'] = True
                            self.repository.save()
                    if not source: continue
                    path = Path(source); stat = path.stat(); signature = (config.get('appid'), source, stat.st_mtime_ns, stat.st_size)
                    if signature == session['signature']: continue
                    states = parse_state(path)
                    # Empty/partial transient writes do not erase remembered progress.
                    if not states and stat.st_size == 0: continue
                    record = self.repository.record(ident, config)
                    keys, dirty = merge_progress(record, states, notify=True)
                    session['signature'] = signature
                    if dirty: self.repository.save(); changed = changed or ident == selected
                    schema = {r['id']: r for r in config.get('schema', [])}
                    if config.get('notifications', True):
                        for key in keys:
                            row = dict(schema.get(key) or {'id': key, 'name': key, 'description': ''})
                            row.update(game_id=ident, game_name=session['game']['name'], icon_path=self.repository.icon_path(row))
                            events.append((row, target))
                except psutil.NoSuchProcess: ended.append((ident, session['created']))
                except Exception: continue  # Writing/atomic replace/file missing: retry, preserve history.
            view = self.repository.view(selected) if changed else None
            if not self.closed: self.polled.emit({'events': events, 'ended': ended, 'view': view})
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
        if result.get('fetch'): self.fetchSchema(*result['fetch'])
        if result['view'] and result['view']['ident'] == self._state.get('ident') and not self._state.get('busy'):
            self._state = result['view']; self.changed.emit()
        if not self.sessions: self.timer.stop()

    def shutdown(self):
        self.closed = True; self.timer.stop(); self.overlay.shutdown()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.network.shutdown(wait=False, cancel_futures=True)
        self.icons.shutdown(wait=False, cancel_futures=True)
