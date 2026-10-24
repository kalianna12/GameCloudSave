"""Per-game GPU scaling through an isolated, pinned Magpie installation.

No capture, frame copies, shader compilation or rendering happens in the Qt process.
Magpie's v0.13.0 portable JSON contract is intentionally version-pinned.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QDesktopServices

VERSION = '0.13.0'
PROJECT = 'https://github.com/Blinue/Magpie'
PACKAGES = {
    'x64': 'a3f774dce9d2e050fb0934c362d51d8db459a2e79e6f937bdb86852312899a9e',
    'ARM64': '3f1d4f8fade6da13402ac4ea739867d60f0dee50e4c4fa56aab508eab0109551',
}
PRESETS = [
    {'id': 'anime-fast', 'name': 'Anime4K 轻量', 'description': '动漫、Galgame；优先响应速度。'},
    {'id': 'anime-quality', 'name': 'Anime4K 精细', 'description': '动漫、Galgame；细化线条，GPU 开销较高。'},
    {'id': 'fsr', 'name': 'FSR 通用', 'description': '3D 游戏和混合画面；空间超分辨率。'},
    {'id': 'lanczos', 'name': 'Lanczos 清晰', 'description': '通用画面；保留原有风格，可叠加锐化。'},
    {'id': 'nearest', 'name': '像素放大', 'description': '像素游戏；使用最近邻，建议整数倍放大。'},
]
DEFAULT = {'enabled': False, 'auto_start': True, 'preset': 'anime-fast',
           'sharpness': 20, 'display': 'fullscreen', 'fit': 'fit',
           'window_scale': 2.0, 'capture': 0, 'fps': 60, 'game_3d': False}
QUICK_PROFILES = [
    {'name':'Galgame 全屏 · 中','values':{'enabled':True,'preset':'anime-quality','sharpness':70}},
    {'name':'动漫精细 · 高','values':{'enabled':True,'preset':'anime-quality','sharpness':100}},
    {'name':'3D 游戏全屏','values':{'enabled':True,'preset':'fsr','sharpness':65,'game_3d':True}},
    {'name':'通用清晰','values':{'enabled':True,'preset':'lanczos','sharpness':60}},
    {'name':'像素 2 倍窗口','values':{'enabled':True,'preset':'nearest','sharpness':0,'display':'windowed','window_scale':2.0}},
    {'name':'关闭增强','values':{'enabled':False}},
]
REQUIRED = ('Magpie.exe', 'Microsoft.UI.Xaml.dll', 'resources.pri',
            'effects/Lanczos.hlsl', 'effects/Nearest.hlsl', 'effects/CAS/CAS.hlsl',
            'effects/FSR/FSR_EASU.hlsl', 'effects/FSR/FSR_RCAS.hlsl',
            'effects/Anime4K/Anime4K_Upscale_Denoise_S.hlsl',
            'effects/Anime4K/Anime4K_Upscale_Denoise_L.hlsl')
SCALING_CLASS = 'Window_Magpie_967EB565-6F73-4E94-AE53-00CC42592A22'


def intensity_profile(preset, level):
    if preset not in {p['id'] for p in PRESETS} or level not in ('low','medium','high'):
        raise ValueError('增强强度选项无效')
    if preset.startswith('anime-'):preset='anime-fast' if level=='low' else 'anime-quality'
    return {'preset':preset,'sharpness':0 if preset=='nearest' else {'low':35,'medium':70,'high':100}[level]}


def architecture():
    native = os.environ.get('PROCESSOR_ARCHITEW6432') or platform.machine()
    return 'ARM64' if native.lower() in ('arm64', 'aarch64') else 'x64'


def supported():
    return os.name == 'nt' and sys.getwindowsversion().build >= 18362


def normalize(values):
    result = dict(DEFAULT)
    if not isinstance(values, dict): return result
    for key in ('enabled', 'auto_start', 'game_3d'):
        if key in values:
            if type(values[key]) is not bool: raise ValueError('画质选项开关无效')
            result[key] = values[key]
    for key, choices in (('preset', {p['id'] for p in PRESETS}),
                         ('display', {'fullscreen', 'windowed'}), ('fit', {'fit', 'stretch'})):
        if key in values:
            if values[key] not in choices: raise ValueError('画质方案选项无效')
            result[key] = values[key]
    for key, low, high in (('sharpness', 0, 100), ('fps', 30, 240), ('window_scale', 1.25, 4)):
        if key in values:
            v = values[key]
            if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('画质方案数值超出范围')
            result[key] = float(v) if key == 'window_scale' else int(v)
    if 'capture' in values:
        if type(values['capture']) is not int or values['capture'] not in (0, 3):
            raise ValueError('不支持此捕获方式')
        result['capture'] = values['capture']
    if result['display'] == 'windowed': result['game_3d'] = False
    return result


def window_class_rule(name):
    # Match the normalizations in Magpie v0.13.0 ProfileService.cpp.
    if re.fullmatch(r'Chrome_WidgetWin_\d+', name): return 'Chrome_WidgetWin_1'
    if re.fullmatch(r'XWindow_\d+', name): return 'XWindow_0'
    match = re.fullmatch(r'HwndWrapper\[(.*);;[0-9a-fA-F-]{36}\]', name)
    return match[1] if match else name


def make_config(options, exe, class_name, name):
    p = normalize(options)
    scale = {'scalingType': 3 if p['fit'] == 'stretch' and p['display'] == 'fullscreen' else 1,
             'scale': {'x': 1.0, 'y': 1.0}}
    effects = []
    if p['preset'].startswith('anime-'):
        size = 'S' if p['preset'] == 'anime-fast' else 'L'
        effects.append({'name': 'Anime4K\\Anime4K_Upscale_Denoise_' + size})
        effects.append({'name': 'Lanczos', **scale})
    elif p['preset'] == 'fsr':
        effects.append({'name': 'FSR\\FSR_EASU', **scale})
    else:
        effects.append({'name': 'Nearest' if p['preset'] == 'nearest' else 'Lanczos', **scale})
    if p['sharpness'] and p['preset'] != 'nearest':
        effects.append({'name': 'FSR\\FSR_RCAS' if p['preset'] == 'fsr' else 'CAS\\CAS',
                        'parameters': {'sharpness': p['sharpness'] / 100.0}})
    base = {'scalingMode': 0, 'captureMethod': p['capture'], 'multiMonitorUsage': 0,
            'initialWindowedScaleFactor': 6, 'customInitialWindowedScaleFactor': p['window_scale'],
            'frameRateLimiterEnabled': True, 'maxFrameRate': p['fps'],
            '3DGameMode': p['game_3d'], 'captureTitleBar': False, 'adjustCursorSpeed': True,
            'cursorScaling': 2, 'fullscreenInitialToolbarState': 2, 'windowedInitialToolbarState': 2}
    return {'language': 'zh-cn', 'autoCheckForUpdates': False, 'showNotifyIcon': True,
            'allowScalingMaximized': False, 'simulateExclusiveFullscreen': False,
            'alwaysRunAsAdmin': False,
            # Ctrl+Alt+F11 toggles scaling. No synthetic keyboard shortcuts are sent.
            'shortcuts': {'scale': 0x200 | 0x400 | 0x7A},
            'scalingModes': [{'name': next(v['name'] for v in PRESETS if v['id'] == p['preset']),
                              'effects': effects}],
            'profiles': [{**base, 'scalingMode': -1}, {**base, 'name': name, 'packaged': False,
                               'pathRule': exe, 'classNameRule': window_class_rule(class_name),
                               'autoScale': 1 if p['display'] == 'fullscreen' else 2}]}


def write_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def extract_verified(archive, destination, arch):
    archive = Path(archive)
    if archive.stat().st_size > 64 * 1024 * 1024: raise ValueError('内核压缩包过大')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PACKAGES[arch]:
        raise ValueError(f'校验失败，请选择官方 Magpie v{VERSION} {arch} ZIP 原包')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage on the same volume; a failed download/extraction never marks a core ready.
    with tempfile.TemporaryDirectory(prefix='magpie-install-', dir=destination.parent) as temp:
        stage = Path(temp) / 'core'
        stage.mkdir()
        with zipfile.ZipFile(archive) as package:
            if sum(i.file_size for i in package.infolist()) > 256 * 1024 * 1024:
                raise ValueError('内核解压体积异常')
            for item in package.infolist():
                relative = PurePosixPath(item.filename.replace('\\', '/'))
                if relative.is_absolute() or '..' in relative.parts or ':' in item.filename or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('内核压缩包路径无效')
            package.extractall(stage)
        if not all((stage / item).is_file() for item in REQUIRED): raise ValueError('内核文件不完整')
        write_atomic(stage / 'config/config.json', {'profiles': [{'scalingMode': -1}]})
        write_atomic(stage / 'gamecloud-core.json', {'version': VERSION, 'arch': arch, 'sha256': PACKAGES[arch],
                                                   'source': PROJECT + '/tree/v' + VERSION})
        (stage / 'SOURCE-NOTICE.txt').write_text(
            f'Magpie v{VERSION} by Blinue and contributors, GPL-3.0.\n'
            f'Unmodified official binaries: {PROJECT}/releases/tag/v{VERSION}\n'
            f'Corresponding source and license: {PROJECT}/tree/v{VERSION}\n'
            'Anime4K and other effect authors/licenses are retained in effects/*.hlsl.\n', encoding='utf-8')
        if destination.is_symlink(): raise ValueError('内核目录不能是符号链接')
        previous = Path(temp) / 'previous'
        if destination.exists(): destination.rename(previous)
        try: stage.rename(destination)
        except OSError:
            if previous.exists(): previous.rename(destination)
            raise


def target_identity(hwnd, pid):
    import psutil
    user = ctypes.windll.user32
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    current = W.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(current))
    if current.value != pid or pid == os.getpid(): raise ValueError('游戏窗口已变化，请重试')
    process = psutil.Process(pid)
    name = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, name, 256)
    if not name.value: raise ValueError('无法读取游戏窗口类型')
    return process.exe(), name.value, process.create_time()


def scaling_visible(pid):
    user = ctypes.windll.user32
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [W.HWND]
    result = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def visit(hwnd, _):
        current = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(current))
        if current.value == pid and user.IsWindowVisible(hwnd):
            name = ctypes.create_unicode_buffer(256)
            user.GetClassNameW(hwnd, name, 256)
            if name.value == SCALING_CLASS: result.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    return bool(result)


class Engine:
    def __init__(self, root):
        self.arch = architecture()
        self.directory = Path(root).resolve() / 'engines' / f'magpie-{VERSION}-{self.arch}'
        self.process = None
        self.target = None

    def installed(self):
        try:
            manifest = json.loads((self.directory / 'gamecloud-core.json').read_text(encoding='utf-8'))
            return manifest.get('version') == VERSION and manifest.get('arch') == self.arch and manifest.get('sha256') == PACKAGES[self.arch] and all((self.directory / p).is_file() for p in REQUIRED)
        except (OSError, ValueError): return False

    def install(self, cancel, progress, archive=''):
        if self.installed(): return
        self.stop()
        if archive:
            if cancel.is_set(): raise InterruptedError('已取消安装')
            extract_verified(archive, self.directory, self.arch)
            return
        url = f'{PROJECT}/releases/download/v{VERSION}/Magpie-v{VERSION}-{self.arch}.zip'
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='magpie-download-', dir=self.directory.parent) as temp:
            path = Path(temp) / 'core.zip'
            request = urllib.request.Request(url, headers={'User-Agent': 'GameCloudSave-Source'})
            with urllib.request.urlopen(request, timeout=20) as response, path.open('wb') as output:
                total = int(response.headers.get('Content-Length', 0)); received = 0; last = -1
                while chunk := response.read(128 * 1024):
                    if cancel.is_set(): raise InterruptedError('已取消下载')
                    received += len(chunk)
                    if received > 64 * 1024 * 1024: raise ValueError('内核下载体积异常')
                    output.write(chunk)
                    percentage = min(99, received * 100 // total) if total else 0
                    if percentage != last: progress(f'正在下载内核 {percentage}%'); last = percentage
            if cancel.is_set(): raise InterruptedError('已取消下载')
            extract_verified(path, self.directory, self.arch)

    def stop(self):
        process = self.process
        if process and process.poll() is None:
            import psutil
            try:
                user = ctypes.windll.user32
                message = user.RegisterWindowMessageW('WM_MAGPIE_QUIT')
                # Only our process receives the quit message; never broadcast to other copies.
                for thread in psutil.Process(process.pid).threads(): user.PostThreadMessageW(thread.id, message, 0, 0)
                process.wait(timeout=3)
            except (OSError, psutil.Error, subprocess.TimeoutExpired):
                if process.poll() is None: process.terminate(); process.wait(timeout=3)
        self.process = None
        self.target = None

    def start(self, options, hwnd, pid, name, cancel):
        if not supported(): raise ValueError('需要 Windows 10 1903 或更新系统及 DirectX 11 显卡')
        if not self.installed(): raise ValueError('请先下载或导入画质增强内核')
        import psutil
        self.stop()
        for process in psutil.process_iter(['pid', 'name']):
            if (process.info['name'] or '').casefold() == 'magpie.exe':
                raise ValueError('请先退出正在运行的 Magpie，再启用本游戏方案')
        exe, class_name, created = target_identity(hwnd, pid)
        config = make_config(options, exe, class_name, name)
        if cancel.is_set(): raise InterruptedError('已取消画质增强')
        write_atomic(self.directory / 'config/config.json', config)
        self.process = subprocess.Popen([str(self.directory / 'Magpie.exe'), '-t'], cwd=self.directory,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
        self.target = (pid, created)
        # Popen success only means the engine was submitted, not that scaling succeeded.
        if cancel.wait(.8): self.stop(); raise InterruptedError('已取消画质增强')
        if self.process.poll() is not None: raise ValueError('内核启动失败，请查看内核日志')

    def poll(self):
        import psutil
        if not self.process: return 'idle'
        if self.process.poll() is not None:
            self.process = None; self.target = None
            return 'exited'
        try:
            game = psutil.Process(self.target[0])
            alive = game.create_time() == self.target[1] and game.is_running()
        except psutil.Error: alive = False
        if not alive: self.stop(); return 'game-exited'
        return 'active' if scaling_visible(self.process.pid) else 'ready'


class GraphicsEnhancement(QObject):
    changed = Signal()
    completed = Signal(int, object)
    progress = Signal(int, str)
    saved = Signal(str)
    failed = Signal(str)
    pollReady = Signal(int, object)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.persistence = getattr(parent, 'pool', None)
        self.engine = Engine(store.root)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='graphics-core')
        self._cancel = threading.Event(); self._serial = 0; self._closed = False; self._busy = False; self._checking = False; self._pending = None
        self._state = {'phase': 'idle', 'message': '尚未启用画质增强', 'game': '', 'installed': self.engine.installed()}
        self.completed.connect(self.receive); self.progress.connect(self.receiveProgress)
        self.pollReady.connect(self.receivePoll)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.check)

    @Property('QVariantList', constant=True)
    def presets(self): return PRESETS

    @Property('QVariantList', constant=True)
    def quickProfiles(self): return QUICK_PROFILES

    @Slot(int,result='QVariantMap')
    def quickProfile(self,index):return normalize(QUICK_PROFILES[index]['values']) if 0<=index<len(QUICK_PROFILES) else dict(DEFAULT)

    @Slot(str,str,result='QVariantMap')
    def intensityProfile(self,preset,level):return intensity_profile(preset,level)

    @Property('QVariantMap', notify=changed)
    def state(self): return {**self._state, 'busy': self._busy, 'supported': supported(), 'version': VERSION}

    @Slot(str, result='QVariantMap')
    def profile(self, ident):
        try: return normalize(self.store.local.get(ident, {}).get('graphics', {}))
        except ValueError: return dict(DEFAULT)

    @Slot(str, 'QVariantMap')
    def save(self, ident, values):
        if not any(g['id'] == ident for g in self.store.games) or self._busy: return
        try: options = normalize(values)
        except ValueError as error:
            self._state.update(phase='error',message=str(error)); self.changed.emit(); return
        active_game = self._state.get('game')
        def work():
            def persist():
                if not any(g['id'] == ident for g in self.store.games): raise ValueError('游戏已移除')
                self.store.save_game(ident, {'graphics': options})
            # Share Bridge's existing serial persistence queue with imports/settings.
            if self.persistence: self.persistence.submit(persist).result()
            else: persist()
            if not options['enabled'] and active_game == ident: self.engine.stop()
            return {'message': '画质方案已保存，下次启动时使用', 'saved': ident,
                    **({'phase': 'idle', 'game': ''} if not self.engine.process else {'phase':'ready'})}
        self.submit('saving', '正在保存画质方案', work)

    def submit(self, phase, message, work):
        if self._busy or self._closed: return False
        self._busy = True; self._serial += 1; serial = self._serial
        self._cancel = threading.Event()
        self._state.update(phase=phase, message=message); self.changed.emit()
        def run():
            try: result = work()
            except InterruptedError as error: result = {'phase': 'idle', 'message': str(error)}
            except Exception as error:
                result = {'phase': 'error', 'message': str(error) if isinstance(error, ValueError) else '操作失败：'+str(error)}
            result['installed'] = self.engine.installed()
            if not self._closed: self.completed.emit(serial, result)
        self.pool.submit(run)
        return True

    @Slot(int, object)
    def receive(self, serial, result):
        if serial != self._serial or self._closed: return
        self._busy = False
        self._state.update({k:v for k,v in result.items() if k != 'saved'})
        self.changed.emit()
        if result.get('saved'): self.saved.emit(result['saved'])
        if result.get('phase') == 'error': self.failed.emit(result['message'])
        if self.engine.process: self.timer.start()
        else: self.timer.stop()
        pending = self._pending; self._pending = None
        if pending and result.get('phase') != 'error':
            QTimer.singleShot(0, lambda:self.startForGame(*pending, automatic=True))

    @Slot(int, str)
    def receiveProgress(self, serial, message):
        if serial == self._serial and not self._closed:
            self._state['message'] = message; self.changed.emit()

    @Slot()
    def install(self): self.installArchive('')

    def installArchive(self, archive):
        if self._busy: return
        if not supported(): self._state['message'] = '需要 Windows 10 1903 或更新系统'; self.changed.emit(); return
        def work():
            self.engine.install(self._cancel, lambda m:self.progress.emit(self._serial, m), archive)
            return {'phase': 'idle', 'message': '画质增强内核已安装'}
        self.submit('installing', '正在校验并安装内核', work)

    @Slot()
    def importArchive(self):
        if self._busy: return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, f'选择官方 Magpie v{VERSION} {self.engine.arch} ZIP', '', 'ZIP (*.zip)')
        if path: self.installArchive(path)

    @Slot()
    def openDownload(self): QDesktopServices.openUrl(QUrl(PROJECT + '/releases/tag/v' + VERSION))

    @Slot()
    def openLogs(self):
        path = self.engine.directory / 'logs'
        if path.is_dir(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def cancel(self): self._pending = None; self._cancel.set()

    @Slot()
    def stop(self):
        self._pending = None
        if self._busy: self._cancel.set(); return
        def work():
            self.engine.stop()
            return {'phase': 'idle', 'message': '画质增强已停止', 'game': ''}
        self.submit('stopping', '正在停止画质增强', work)

    @Slot(str)
    def apply(self, ident): self.startForGame(ident)

    def startForGame(self, ident, pid=None, window=None, automatic=False):
        if self._closed: return
        if self._busy:
            if automatic: self._pending = (ident, pid, window)
            return
        options = self.profile(ident)
        if not options['enabled'] or automatic and not options['auto_start']: return
        game = next((g for g in self.store.games if g['id'] == ident), None)
        if not game: return
        local = dict(self.store.local.get(ident, {})); name = game['name']
        def work():
            if not self.engine.installed(): raise ValueError('请在游戏设置的画质增强页安装内核')
            if window: target = {'hwnd': window, 'pid': pid}
            else:
                from launch_ready import Probe, wait
                if not (local.get('monitor_exe') or local.get('exe') or local.get('install_dir')):
                    raise ValueError('请在启动与监听设置中选择实际游戏 EXE，以识别游戏窗口')
                target = wait(Probe(local, pid), self._cancel, timeout=15)
                if self._cancel.is_set(): raise InterruptedError('已取消画质增强')
                if target['phase'] != 'ready': raise ValueError('未找到游戏窗口，请先启动游戏并设为窗口模式')
            self.engine.start(options, target['hwnd'], target['pid'], name, self._cancel)
            return {'phase': 'ready', 'message': '内核已就绪，切回游戏后自动生效；Ctrl+Alt+F11 可切换', 'game': ident}
        self.submit('starting', '正在等待游戏窗口并准备画质增强', work)

    @Slot()
    def check(self):
        if self._busy or self._checking or not self.engine.process: return
        # Poll runs off the GUI thread; don't flash busy indicators every second.
        self._checking = True; serial = self._serial
        def work():
            try:
                phase = self.engine.poll()
                messages = {'active':'画质增强运行中 · Ctrl+Alt+F11 切换',
                            'ready':'内核已就绪，切回游戏后自动生效；Ctrl+Alt+F11 可切换',
                            'game-exited':'游戏已退出，画质增强已停止', 'exited':'内核已退出，可重新应用方案', 'idle':'尚未启用画质增强'}
                result = {'phase': phase, 'message': messages[phase]}
                if phase not in ('active', 'ready'): result['game'] = ''
            except Exception: result = {'phase':'error', 'message':'无法读取内核状态，请停止后重试'}
            if not self._closed: self.pollReady.emit(serial, result)
        self.pool.submit(work)

    @Slot(int, object)
    def receivePoll(self, serial, result):
        self._checking = False
        if self._closed or self._busy or serial != self._serial: return
        if any(self._state.get(k) != v for k,v in result.items()):
            self._state.update(result); self.changed.emit()
        if not self.engine.process: self.timer.stop()

    def shutdown(self):
        if self._closed: return
        self._closed = True; self._cancel.set(); self.timer.stop()
        self.pool.submit(self.engine.stop)
        self.pool.shutdown(wait=False, cancel_futures=False)
