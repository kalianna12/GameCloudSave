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
                    'ai_enabled': False, 'ai_model': 'deepseek-flash',
                    'cloud_separate_computer':False,'cloud_retries':1,'cloud_timeout':20,'watch_upload':True}
        self.settings = {**defaults, **read_json(self.profile / 'settings.json', {})}
        self.games = read_json(self.root / 'library.json', [])
        self.local = read_json(self.profile / 'games.json', {})
        self.match_report = read_json(self.profile / 'match-report.json', [])
        self.thumbnails = read_json(self.root/'thumbnail-index.json',{})
        self.high_thumbnails = read_json(self.root/'thumbnail-hd-index.json',{})
        self.identities = read_json(self.profile/'ai-identities.json',{})

    def save_settings(self, values):
        values = dict(values)
        password = values.pop('password', '')
        ai_key = values.pop('ai_key', '')
        if ai_key:
            (self.profile / 'ai-key.dpapi').write_bytes(protect(ai_key.encode('utf-8')))
        if password:
            (self.profile / 'credential.dpapi').write_bytes(protect(password.encode('utf-8')))
        self.settings.update(read_json(self.profile/'settings.json',{}))
        self.settings.update(values)
        write_json(self.profile / 'settings.json', self.settings)

    def password(self):
        path = self.profile / 'credential.dpapi'
        return protect(path.read_bytes(), True).decode('utf-8') if path.exists() else ''

    def save_game(self, ident, values):
        values=dict(values)
        if values.get('save_dir'):
            from save_groups import complete_directory
            values['save_dir']=str(complete_directory(values['save_dir']))
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
            try: shutil.copy2(library / 'games.db', temporary / 'games.db')
            except PermissionError: raise ValueError('Playnite 正在占用游戏库；请关闭 Playnite 后再导入。现有游戏列表仍可使用。') from None
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
            self.update_launch_actions(row,ident)
            count += 1
        self.games = sorted(existing.values(), key=lambda g: (not g['installed'], g['name'].casefold()))
        write_json(self.root / 'library.json', self.games)
        write_json(self.profile / 'games.json', self.local)
        self.prepare_thumbnails()
        return count

    def update_launch_actions(self,row,ident):
        direct=[]
        installation=row.get('InstallDirectory') or ''
        for action in row.get('GameActions') or []:
            if not action.get('IsPlayAction',False) or action.get('Type','File')!='File': continue
            path=(action.get('Path') or '').replace('{InstallDir}',installation)
            arguments=(action.get('Arguments') or '').replace('{InstallDir}',installation)
            if '{' in path or '{' in arguments: continue
            if path and not Path(path).is_absolute() and installation: path=str(Path(installation)/path)
            if path.lower().endswith('.exe') and Path(path).is_file():
                direct.append({'exe':path,'arguments':arguments,
                               'working_dir':(action.get('WorkingDir') or installation).replace('{InstallDir}',installation)})
        if len(direct)==1 and not any(row.get(field) for field in ('PreScript','PostScript','GameStartedScript')):
            self.local.setdefault(ident,{})
            for field,value in direct[0].items(): self.local[ident].setdefault(field,value)
            self.local[ident].setdefault('launch_mode','direct')

    def prepare_thumbnails(self):
        from PySide6.QtGui import QImageReader
        from PySide6.QtCore import QSize
        directory=self.root/'thumbnails'
        directory.mkdir(parents=True,exist_ok=True)
        old_index=dict(self.thumbnails)
        old_high_index=dict(self.high_thumbnails)
        for game in self.games:
            if not game.get('cover'): continue
            source=self.root/'covers'/Path(game['cover']).name
            if not source.exists(): continue
            fingerprint=hashlib.sha256((source.name+str(source.stat().st_size)+str(source.stat().st_mtime_ns)).encode()).hexdigest()[:12]
            for limit,index,suffix in ((360,self.thumbnails,''),(1080,self.high_thumbnails,'-hd')):
                target=directory/(game['id']+'-'+fingerprint+suffix+'.jpg')
                if not target.exists():
                    reader=QImageReader(str(source)); reader.setAutoTransform(True); size=reader.size()
                    if size.width()<=0: continue
                    width=min(limit,size.width())
                    reader.setScaledSize(QSize(width,max(1,round(size.height()*width/size.width()))))
                    image=reader.read()
                    if image.isNull() or not image.save(str(target),'JPEG',92): continue
                index[game['id']]=target.name
        if self.thumbnails!=old_index: write_json(self.root/'thumbnail-index.json',self.thumbnails)
        if self.high_thumbnails!=old_high_index: write_json(self.root/'thumbnail-hd-index.json',self.high_thumbnails)

    def rclone(self, command, folder='', values=None):
        if command=='list' and '..' in folder.replace('\\','/').split('/'):
            raise ValueError('浏览路径不能包含上级跳转符号')
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
        retries=max(1,min(3,int(settings.get('cloud_retries',1))))
        timeout=max(10,min(120,int(settings.get('cloud_timeout',20))))
        args = [settings['rclone'], '--config', str(empty_config), '--contimeout', '6s', '--timeout', str(timeout)+'s', '--retries', str(retries)]
        if command == 'list':
            args += ['lsjson', 'gamecloud:' + folder.strip('/')]
        else:
            args += command
        result = run_process(args, env=environment, timeout=timeout*retries+30)
        if result.returncode:
            # Do not surface raw subprocess output containing server/account details.
            detail=result.stderr.casefold()
            if '401' in detail or 'unauthorized' in detail:
                raise ValueError('DAV 登录失败：请在连接设置中检查用户名和密码')
            if '403' in detail or 'forbidden' in detail:
                raise ValueError('DAV 没有读写权限：请选择可写的挂载文件夹')
            if 'timed out' in detail or 'timeout' in detail:
                raise ValueError('DAV 连接超时：请检查网络，或在传输选项中增加超时和尝试次数')
            if '404' in detail or 'not found' in detail:
                raise ValueError('DAV 目录或文件暂不可用：请刷新目录后重试')
            raise ValueError('DAV 操作失败：检查地址、账号密码、网络及目录读写权限')
        return sorted(json.loads(result.stdout),key=lambda row:(not row['IsDir'],row['Name'].casefold())) if command == 'list' else result.stdout

    def preview_cloud(self,folder,entry,values=None):
        name=entry['Name']
        if '/' in name or '\\' in name or name in ('.','..'): raise ValueError('无效文件名')
        target='gamecloud:'+ '/'.join(part for part in (folder.strip('/'),name) if part)
        suffix=Path(name).suffix.casefold()
        result={'name':name,'size':entry.get('Size',0),'modified':entry.get('ModTime',''),
                'mime':entry.get('MimeType',''),'path':target,'text':'','image':''}
        if entry.get('IsDir'):
            result['text']='双击该文件夹进入，查看里面的目录与文件。'
        elif suffix in ('.json','.txt','.log','.ini','.md','.yaml','.yml','.xml','.csv'):
            result['text']=self.rclone(['cat',target,'--head','32768'],values=values)[:32768]
        elif suffix in ('.jpg','.jpeg','.png','.webp') and 0<=entry.get('Size',0)<=4*1024*1024:
            preview=self.profile/'previews'/(hashlib.sha256(target.encode()).hexdigest()+suffix)
            preview.parent.mkdir(parents=True,exist_ok=True)
            self.rclone(['copyto',target,str(preview)],values=values)
            result['image']=str(preview)
        else: result['text']='此类型提供文件信息预览；快照 ZIP 不会自动解压。'
        return result

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
        if cfg.get('snapshot_root')!=self.settings['snapshots']:
            cfg['snapshot_root'] = self.settings['snapshots']
            self._core.save_config(cfg)
        return self._core

    def game(self, ident):
        item = next(g for g in self.games if g['id'] == ident)
        local = self.local.get(ident, {})
        save = Path(local.get('save_dir', ''))
        if not local.get('save_dir') or not save.is_dir():
            raise ValueError('先在该游戏的本机设置中选择存档目录')
        from save_groups import complete_directory
        complete=complete_directory(save)
        if complete!=save:
            self.save_game(ident,{'save_dir':str(complete)})
            save=complete
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
        if not self.settings['cloud_folder'].strip():
            raise ValueError('本地备份已完成；请先在系统设置选择云端根目录')
        archive=Path(archive)
        save_dir=self.local.get(ident,{}).get('save_dir','')
        # Retried archives retain the save folder they backed up, even if local settings changed.
        import zipfile
        with zipfile.ZipFile(archive) as zipped:
            try:
                info=zipped.getinfo('_snapshot_meta.json')
                if info.file_size>65536: raise ValueError('备份元数据过大')
                metadata=json.loads(zipped.read(info))
                if metadata.get('game')!=ident: raise ValueError('备份不属于所选游戏')
                save_dir=metadata.get('save_dir') or save_dir
            except KeyError: pass
        if not save_dir: raise ValueError('备份中缺少存档目录信息')
        target = 'gamecloud:' + self.cloud_directory(ident,save_dir) + '/' + archive.name
        self.rclone(['copyto', str(archive), target, '--transfers', '1', '--checkers', '2'])
        core = self.core()
        with closing(core.connect_db()) as conn:
            conn.execute('UPDATE snapshots SET uploaded=1,cloud_ref=? WHERE archive_path=?', (target, str(archive)))
            conn.commit()

    def cloud_directory(self,ident,save_dir=None,values=None):
        from cloud_paths import directory
        return directory(self.games,ident,save_dir or self.local.get(ident,{}).get('save_dir',''),{**self.settings,**(values or {})})

    def create_cloud_folder(self,parent,name,values=None):
        from cloud_paths import folder_path
        name=str(name).strip()
        if not name or '/' in name or '\\' in name or name in ('.','..'):
            raise ValueError('请输入一个文件夹名，不能包含路径分隔符')
        target='/'.join(p for p in (folder_path(parent),name) if p)
        self.rclone(['mkdir','gamecloud:'+target],values=values)
        return {'path':folder_path(parent),'entries':self.rclone('list',parent,values)}

    def download_cloud(self,folder,entry,destination,values=None):
        from cloud_paths import folder_path
        name=entry['Name']
        if entry.get('IsDir') or '/' in name or '\\' in name or name in ('.','..'):
            raise ValueError('请选择一个文件')
        remote='gamecloud:'+'/'.join(p for p in (folder_path(folder),name) if p)
        self.rclone(['copyto',remote,str(destination)],values=values)
        return '文件已下载：'+str(destination)

    def organize_cloud(self,ident,old_folder,values=None):
        from cloud_management import organize
        return organize(self,ident,old_folder,values)

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
            metadata={}
            if '_snapshot_meta.json' in archive.namelist():
                info=archive.getinfo('_snapshot_meta.json')
                if info.file_size>65536: raise ValueError('备份元数据过大')
                metadata=json.loads(archive.read(info))
        # Historical single-slot archives must not replace the newly configured parent folder.
        from pathlib import PureWindowsPath
        from save_groups import slot_name
        current=Path(self.local[ident]['save_dir'])
        original=PureWindowsPath(metadata.get('save_dir',''))
        target=current
        if slot_name(original.name) and not slot_name(current.name):
            if original.parent.name.casefold()!=current.name.casefold():
                raise ValueError('这是旧版单存档备份，请选择对应存档槽目录后恢复')
            target=current/original.name
            if not target.resolve().is_relative_to(current.resolve()):
                raise ValueError('存档槽目录不在当前游戏存档目录中')
        from argparse import Namespace
        core=self.core()
        try:
            if target!=current:
                with closing(core.connect_db()) as conn:
                    conn.execute('UPDATE games SET save_dir=? WHERE name=?',(str(target),ident)); conn.commit()
            core.cmd_restore(Namespace(snapshot_id=snapshot))
        finally:
            if target!=current: self.game(ident)

    def retry(self, ident):
        count = 0
        for row in self.history(ident):
            if not row['uploaded'] and Path(row['archive_path']).is_file():
                self.upload(ident, Path(row['archive_path']))
                count += 1
        return count

    def launch(self, ident):
        local = self.local.get(ident, {})
        mode=local.get('launch_mode','direct' if local.get('exe') else 'playnite')
        if mode=='direct':
            if not local.get('exe'): raise ValueError('直接启动需要在游戏设置中选择 EXE')
            exe = Path(local['exe'])
            if not exe.is_file():
                raise ValueError('本机启动文件不存在，请重新设置')
            arguments=local.get('arguments','').strip()
            command=subprocess.list2cmdline([str(exe)])+(' '+arguments if arguments else '')
            subprocess.Popen(command,cwd=local.get('working_dir') or exe.parent)
        else:
            base = Path(self.settings['playnite'])
            if not (base / 'Playnite.DesktopApp.exe').exists():
                base /= 'Playnite'
            exe = base / 'Playnite.DesktopApp.exe'
            if not exe.is_file():
                raise ValueError('本机 Playnite 路径不存在，请重新设置')
            subprocess.Popen([str(exe), '--start', str(uuid.UUID(ident))], cwd=base)

    def match_game(self,ident):
        from matching import scan
        from ai_match import identify_game
        import time
        item=next(g for g in self.games if g['id']==ident)
        local=dict(self.local.get(ident,{}))
        if not local.get('install_dir') and local.get('exe'):local['install_dir']=str(Path(local['exe']).parent)
        started=time.monotonic()
        identity={'english_name':'','aliases':[],'hints':[],'note':''}
        ai_error=''
        key_path=self.profile/'ai-key.dpapi'
        if self.settings.get('ai_enabled'):
            if key_path.exists():
                try:
                    cache_key=hashlib.sha256((item['name']+local.get('install_dir','')+self.settings['ai_model']+'v2').encode()).hexdigest()
                    if cache_key in self.identities: identity=self.identities[cache_key]
                    else:
                        identity=identify_game(item['name'],Path(local.get('install_dir','')).name,protect(key_path.read_bytes(),True).decode(),self.settings['ai_model'])
                        self.identities[cache_key]=identity; write_json(self.profile/'ai-identities.json',self.identities)
                except ValueError as error: ai_error=str(error)
            else: ai_error='未配置 DeepSeek API Key，已使用本地规则'
        candidates,checked=scan(item['name'],local,identity)
        status='review' if candidates else 'failed' if ai_error else 'notfound'
        message=(f'找到 {len(candidates)} 个本地候选；'+('AI 暂不可用，仍可按本地证据自动处理' if ai_error else '可批量自动配置并备份')) if candidates else ai_error or '未找到可确认的存档目录'
        return {'id':ident,'name':item['name'],'status':status,'message':message,'candidates':candidates,'checked':checked,
                'english_name':identity['english_name'],'aliases':identity['aliases'],'note':identity['note'],
                'ai_warning':ai_error,
                'elapsed':round(time.monotonic()-started,2),'model':self.settings['ai_model'] if self.settings.get('ai_enabled') else '本地规则'}

    def save_match_report(self,results):
        self.match_report=results
        write_json(self.profile/'match-report.json',results)

    def configure_cloud(self,values):
        values=dict(values)
        folder=values.get('cloud_folder','').strip('/')
        if not values.get('cloud_folder','').strip(): raise ValueError('请选择右侧浏览中的存储文件夹')
        self.rclone('list',folder,values)
        name='.gamecloud-write-check-'+str(uuid.uuid4())+'.txt'
        target='gamecloud:'+ '/'.join(p for p in (folder,name) if p)
        with tempfile.TemporaryDirectory(dir=self.profile) as temporary:
            probe=Path(temporary)/name; probe.write_text('GameCloudSave write verification',encoding='utf-8')
            try: self.rclone(['copyto',str(probe),target],values=values)
            except ValueError: raise ValueError('该目录可浏览但不能上传；请进入可写的挂载文件夹，再验证保存') from None
            self.rclone(['deletefile',target],values=values)
        self.save_settings(values)
        return '已验证目录读写权限并保存；所有游戏共用此位置'

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
