from __future__ import annotations
import base64
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import closing

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
RESOURCES = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else ROOT
DATA = Path(os.environ.get('GAMECLOUD_DATA', str(ROOT / 'data')))

def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def machine_id():
    # MachineGuid distinguishes machines even when they use the same computer name.
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography') as key:
        guid = winreg.QueryValueEx(key, 'MachineGuid')[0]
    return hashlib.sha256((guid + os.environ.get('USERNAME', '')).encode()).hexdigest()[:16]

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def protect(value: bytes, decrypt=False):
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)

def run_process(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)

def safe_child(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('路径不在所选目录内')
    return path

class Store:
    def __init__(self, data=None, identity=None):
        self.root = Path(data or DATA)
        self.identity = identity or machine_id()
        self.profile = self.root / 'machines' / self.identity
        self.profile.mkdir(parents=True, exist_ok=True)
        defaults = {'computer': platform.node(), 'playnite': r'D:\GAMES\PLAYNITE',
                    'library': str(Path(os.environ['APPDATA']) / 'Playnite/library'),
                    'snapshots': str(self.profile / 'snapshots'), 'rclone': str(RESOURCES / 'tools/rclone.exe') if (RESOURCES / 'tools/rclone.exe').exists() else shutil.which('rclone') or 'rclone',
                    'dav_url': 'http://10.208.190.125:5244/dav/', 'dav_user': 'admin', 'cloud_folder': '',
                    'cover_size': 210, 'columns': 0, 'gap': 22, 'installed_only': False, 'watch': False,
                    'ai_enabled': False, 'ai_model': 'deepseek-flash'}
        self.settings = {**defaults, **read_json(self.profile / 'settings.json', {})}
        self.games = read_json(self.root / 'library.json', [])
        self.local = read_json(self.profile / 'games.json', {})

    def save_settings(self, values):
        values = dict(values)
        password = values.pop('password', '')
        ai_key = values.pop('ai_key', '')
        if ai_key:
            (self.profile / 'ai-key.dpapi').write_bytes(protect(ai_key.encode('utf-8')))
        if password:
            (self.profile / 'credential.dpapi').write_bytes(protect(password.encode('utf-8')))
        self.settings.update(values)
        write_json(self.profile / 'settings.json', self.settings)

    def password(self):
        path = self.profile / 'credential.dpapi'
        return protect(path.read_bytes(), True).decode('utf-8') if path.exists() else ''

    def save_game(self, ident, values):
        self.local[ident] = {**self.local.get(ident, {}), **values}
        write_json(self.profile / 'games.json', self.local)

    def remove(self, ident):
        self.games = [g for g in self.games if g['id'] != ident]
        write_json(self.root / 'library.json', self.games)

    def import_playnite(self):
        base = Path(self.settings['playnite'])
        if not (base / 'LiteDB.dll').exists():
            base = base / 'Playnite'
        dll = base / 'LiteDB.dll'
        library = Path(self.settings['library'])
        if not dll.is_file() or not (library / 'games.db').is_file():
            raise ValueError('请在系统设置中分别选择 Playnite 程序目录和 library 数据目录')
        with tempfile.TemporaryDirectory(dir=self.profile) as temporary:
            temporary = Path(temporary)
            shutil.copy2(library / 'games.db', temporary / 'games.db')
            result = run_process(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                  str(RESOURCES / 'scripts/export_playnite.ps1'), '-AssemblyPath', str(dll),
                                  '-DatabasePath', str(temporary / 'games.db'), '-OutputPath', str(temporary / 'games.json')], timeout=60)
            if result.returncode:
                raise ValueError('Playnite 只读导出失败；请关闭 Playnite 后重试，或检查程序与库版本')
            rows = read_json(temporary / 'games.json', [])
        existing = {g['id']: g for g in self.games}
        covers = self.root / 'covers'
        covers.mkdir(parents=True, exist_ok=True)
        count = 0
        for row in rows:
            ident = str(uuid.UUID(row['_id']['$guid']))
            cover = ''
            relative = row.get('CoverImage') or ''
            if relative:
                source = safe_child(library / 'files', relative.replace('\\', '/'))
                if source.is_file():
                    target = covers / (ident + source.suffix.lower())
                    shutil.copy2(source, target)
                    cover = str(target)
            existing[ident] = {**existing.get(ident, {}), 'id': ident, 'name': row.get('Name', '未命名'),
                               'cover': cover, 'installed': bool(row.get('IsInstalled')), 'source': 'Playnite'}
            # Installation paths are specific to the importing computer.
            self.local[ident] = {**self.local.get(ident, {}), 'install_dir': row.get('InstallDirectory') or '', 'installed':bool(row.get('IsInstalled'))}
            count += 1
        self.games = sorted(existing.values(), key=lambda g: (not g['installed'], g['name'].casefold()))
        write_json(self.root / 'library.json', self.games)
        write_json(self.profile / 'games.json', self.local)
        return count

    def rclone(self, command, folder='', values=None):
        settings = {**self.settings, **(values or {})}
        password = settings.pop('password', '') or self.password()
        if not password:
            raise ValueError('请填写 DAV 密码并保存本机设置')
        url = settings['dav_url'].strip()
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise ValueError('DAV 地址须为 http/https 地址，账号请单独填写')
        obscured = run_process([settings['rclone'], 'obscure', '-'], input=password, timeout=10)
        if obscured.returncode:
            raise ValueError('rclone 密码处理失败')
        environment = os.environ.copy()
        environment.update({'RCLONE_CONFIG_GAMECLOUD_TYPE': 'webdav', 'RCLONE_CONFIG_GAMECLOUD_URL': url,
                            'RCLONE_CONFIG_GAMECLOUD_VENDOR': 'other', 'RCLONE_CONFIG_GAMECLOUD_USER': settings['dav_user'],
                            'RCLONE_CONFIG_GAMECLOUD_PASS': obscured.stdout.strip()})
        empty_config = self.profile / 'rclone-empty.conf'
        empty_config.touch(exist_ok=True)
        args = [settings['rclone'], '--config', str(empty_config), '--contimeout', '6s', '--timeout', '20s', '--retries', '1']
        if command == 'list':
            args += ['lsjson', 'gamecloud:' + folder.strip('/'), '--dirs-only']
        else:
            args += command
        result = run_process(args, env=environment, timeout=50)
        if result.returncode:
            # Do not surface raw subprocess output containing server/account details.
            raise ValueError('DAV 操作失败：检查地址、账号密码、网络及目录读写权限')
        return json.loads(result.stdout) if command == 'list' else result.stdout

    def core(self):
        if not hasattr(self, '_core'):
            spec = importlib.util.spec_from_file_location('gamecloud_v1_core', RESOURCES / 'legacy/gamecloud.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            module.APP_ROOT = self.profile / 'core'
            module.DB_PATH = module.APP_ROOT / 'state.db'
            module.CONFIG_PATH = module.APP_ROOT / 'config.json'
            import datetime
            module.now_file_ts = lambda: datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            # Stable suffix prevents collisions between Chinese names in the legacy slugifier.
            module.slugify = lambda name: 'game-' + hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]
            self._core = module
            module.init_db()
        cfg = self._core.load_config()
        cfg['snapshot_root'] = self.settings['snapshots']
        self._core.save_config(cfg)
        return self._core

    def game(self, ident):
        item = next(g for g in self.games if g['id'] == ident)
        local = self.local.get(ident, {})
        save = Path(local.get('save_dir', ''))
        if not local.get('save_dir') or not save.is_dir():
            raise ValueError('先在该游戏的本机设置中选择存档目录')
        core = self.core()
        with closing(core.connect_db()) as conn:
            # Core uses name as key; stable Playnite IDs preserve history across renames.
            conn.execute('INSERT OR IGNORE INTO games (name,exe_path,exe_name,save_dir,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                         (ident, local.get('exe', ''), Path(local.get('exe', '')).name, str(save), core.now_iso(), core.now_iso()))
            conn.execute('UPDATE games SET save_dir=?,exe_path=?,exe_name=? WHERE name=?',
                         (str(save), local.get('exe', ''), Path(local.get('exe', '')).name, ident))
            conn.commit()
            return core.get_game(conn, ident)

    def backup(self, ident, event='manual'):
        game = self.game(ident)
        core = self.core()
        with closing(core.connect_db()) as conn:
            archive = core.snapshot_game(conn, game, event, '新版手动备份' if event == 'manual' else '自动备份')
        if not archive:
            raise ValueError('本地快照创建失败')
        return archive

    def upload(self, ident, archive):
        folder = self.settings['cloud_folder'].strip('/')
        if not self.settings['cloud_folder'].strip():
            raise ValueError('本地备份已完成；请先在系统设置选择云端根目录')
        target = 'gamecloud:' + '/'.join(part for part in (folder, ident, archive.name) if part)
        self.rclone(['copyto', str(archive), target, '--transfers', '1', '--checkers', '2'])
        core = self.core()
        with closing(core.connect_db()) as conn:
            conn.execute('UPDATE snapshots SET uploaded=1,cloud_ref=? WHERE archive_path=?', (target, str(archive)))
            conn.commit()

    def history(self, ident):
        core = self.core()
        with closing(core.connect_db()) as conn:
            rows = conn.execute('SELECT s.* FROM snapshots s JOIN games g ON s.game_id=g.id WHERE g.name=? ORDER BY s.id DESC', (ident,)).fetchall()
        return [dict(row) for row in rows]

    def restore(self, ident, snapshot):
        self.game(ident)  # Refresh this computer's save path.
        if snapshot not in [row['id'] for row in self.history(ident)]:
            raise ValueError('快照不属于当前游戏')
        import zipfile
        row = next(row for row in self.history(ident) if row['id'] == snapshot)
        path = Path(row['archive_path'])
        if not path.is_file():
            raise ValueError('本地快照文件不存在')
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() or not any(name.startswith('save/') for name in archive.namelist()):
                raise ValueError('快照损坏或格式不正确')
            from pathlib import PurePosixPath
            if any('..' in PurePosixPath(name.replace('\\', '/')).parts or name.startswith(('/', '\\')) or ':' in name for name in archive.namelist()):
                raise ValueError('快照包含无效路径')
        from argparse import Namespace
        self.core().cmd_restore(Namespace(snapshot_id=snapshot))

    def retry(self, ident):
        count = 0
        for row in self.history(ident):
            if not row['uploaded'] and Path(row['archive_path']).is_file():
                self.upload(ident, Path(row['archive_path']))
                count += 1
        return count

    def launch(self, ident):
        local = self.local.get(ident, {})
        if local.get('exe'):
            exe = Path(local['exe'])
            if not exe.is_file():
                raise ValueError('本机启动文件不存在，请重新设置')
            subprocess.Popen([str(exe)], cwd=exe.parent)
        else:
            base = Path(self.settings['playnite'])
            if not (base / 'Playnite.DesktopApp.exe').exists():
                base /= 'Playnite'
            exe = base / 'Playnite.DesktopApp.exe'
            if not exe.is_file():
                raise ValueError('本机 Playnite 路径不存在，请重新设置')
            subprocess.Popen([str(exe), '--start', str(uuid.UUID(ident))], cwd=base)

    def candidates(self, ident):
        import re
        item = next(g for g in self.games if g['id'] == ident)
        words = [w.casefold() for w in re.split(r'[^\w]+', item['name']) if len(w) > 2]
        local = self.local.get(ident, {})
        roots = [Path(os.environ['LOCALAPPDATA']), Path(os.environ['APPDATA']),
                 Path.home() / 'AppData/LocalLow', Path.home() / 'Documents/My Games', Path.home() / 'Saved Games']
        found = []
        for root in roots:
            if not root.is_dir():
                continue
            for path in list(root.iterdir())[:1500]:
                if path.is_dir() and any(word in path.name.casefold() for word in words):
                    found.append(str(path))
                elif path.is_dir():
                    try:
                        for child in list(path.iterdir())[:60]:
                            if child.is_dir() and any(word in child.name.casefold() for word in words):
                                found.append(str(child))
                    except OSError:
                        pass
        installation = local.get('install_dir', '')
        if installation:
            for name in ('save', 'saves', 'SaveData', 'Saved', 'userdata'):
                candidate = Path(installation) / name
                if candidate.is_dir():
                    found.append(str(candidate))
        found = list(dict.fromkeys(found))[:30]
        key_path = self.profile / 'ai-key.dpapi'
        if self.settings.get('ai_enabled') and key_path.exists() and found:
            from ai_match import rank_candidates
            return rank_candidates(item['name'], found, protect(key_path.read_bytes(), True).decode(), self.settings['ai_model'])
        return found
