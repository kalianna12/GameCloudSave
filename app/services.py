from __future__ import annotations
import base64
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
import re
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
PORTABLE_WORKSPACE=ROOT.parents[1] if ROOT.parent.name=='dist' and ROOT.name=='GameCloudSave' else ROOT
DEFAULT_DATA=Path(os.environ['LOCALAPPDATA'])/'GameCloudSave/data' if (ROOT/'gamecloud-install.json').exists() else PORTABLE_WORKSPACE/'data'
DATA = Path(os.environ.get('GAMECLOUD_DATA', str(DEFAULT_DATA)))

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
        detected_playnite=Path(os.environ['LOCALAPPDATA'])/'Playnite'
        detected_library=Path(os.environ['APPDATA'])/'Playnite/library'
        defaults = {'computer': platform.node(), 'playnite': str(detected_playnite) if (detected_playnite/'LiteDB.dll').is_file() else '',
                    'library': str(detected_library) if (detected_library/'games.db').is_file() else '',
                    'snapshots': str(self.profile / 'snapshots'), 'rclone': str(RESOURCES / 'tools/rclone.exe') if (RESOURCES / 'tools/rclone.exe').exists() else shutil.which('rclone') or 'rclone',
                    'dav_url': '', 'dav_user': '', 'cloud_folder': '',
                    'cover_size': 210, 'columns': 0, 'gap': 22, 'installed_only': False, 'watch': False,
                    'ai_enabled': False, 'ai_model': 'deepseek-flash',
                    'cloud_separate_computer':False,'cloud_retries':1,'cloud_timeout':20,'watch_upload':True,
                    'match_network':True,'match_web_search':True,'match_workers':2,'match_ai_review':True,'match_ai_weight':75,'guide_dismissed':False,
                    'close_to_tray':True,'watch_interval':5,'auto_snapshot_keep':5}
        defaults.update({'setup_completed':False,'cover_source':'steam','custom_cover_url':'','theme':'dark','accent_color':'','animations':True,'tray_notifications':True,'gamepad_enabled':True,'navigation_sounds':True,'fullscreen':False})
        defaults.update(home_cover_size=176,home_gap=14,home_recent_preview=True,library_design='classic',experience_group='category',shelf_arrangement='covers',shelf_wood='walnut',shelf_sunlight=True,atlas_order='release_asc')
        self.settings = {**defaults, **read_json(self.profile / 'settings.json', {})}
        if self.settings.get('library_design') not in ('classic','shelf','cinema','atlas'):self.settings['library_design']='classic'
        if self.settings.get('cover_source')=='igdb':self.settings['cover_source']='steam'
        self.games = read_json(self.root / 'library.json', [])
        self.groups=read_json(self.root/'groups.json',[])
        self.local = read_json(self.profile / 'games.json', {})
        self.migrate_library()
        self.match_report = read_json(self.profile / 'match-report.json', [])
        self.thumbnails = read_json(self.root/'thumbnail-index.json',{})
        self.high_thumbnails = read_json(self.root/'thumbnail-hd-index.json',{})
        self.identities = read_json(self.profile/'ai-identities.json',{})
        self.network_cache=read_json(self.root/'network-identities.json',{})
        import threading
        self.match_lock=threading.RLock()

    def save_settings(self, values):
        values = dict(values)
        if 'fullscreen' in values and type(values['fullscreen'])!=bool:raise ValueError('全屏设置无效')
        if 'auto_snapshot_keep' in values and (type(values['auto_snapshot_keep'])!=int or not 1<=values['auto_snapshot_keep']<=100):
            raise ValueError('自动存档保留份数须为 1 到 100，手动存档不受限制')
        for key,low,high in [('home_cover_size',120,280),('home_gap',8,32)]:
            if key in values and (type(values[key])!=int or not low<=values[key]<=high):raise ValueError('首页布局数值超出范围')
        if 'home_recent_preview' in values and type(values['home_recent_preview'])!=bool:raise ValueError('首页预览设置无效')
        if 'library_design' in values and values['library_design'] not in ('classic','shelf','cinema','atlas'):raise ValueError('游戏库设计不存在')
        if 'experience_group' in values and values['experience_group'] not in ('all','category','series','tags','year'):raise ValueError('分组方式不存在')
        if 'atlas_order' in values and values['atlas_order'] not in ('release_asc','release_desc','name'):raise ValueError('星图排序不存在')
        if 'shelf_arrangement' in values and values['shelf_arrangement'] not in ('covers','books'):raise ValueError('书柜排列方式不存在')
        if 'shelf_wood' in values and values['shelf_wood'] not in ('oak','walnut','cherry'):raise ValueError('木材样式不存在')
        if 'shelf_sunlight' in values and type(values['shelf_sunlight'])!=bool:raise ValueError('日光设置无效')
        password = values.pop('password', '')
        ai_key = values.pop('ai_key', '')
        values.pop('igdb_secret',None)
        if ai_key:
            (self.profile / 'ai-key.dpapi').write_bytes(protect(ai_key.encode('utf-8')))
        if password:
            (self.profile / 'credential.dpapi').write_bytes(protect(password.encode('utf-8')))
        self.settings.update(read_json(self.profile/'settings.json',{}))
        self.settings.update(values)
        write_json(self.profile / 'settings.json', self.settings)
        if 'match_ai_weight' in values:self.reweight_matches()

    def password(self):
        path = self.profile / 'credential.dpapi'
        return protect(path.read_bytes(), True).decode('utf-8') if path.exists() else ''

    def reweight_matches(self):
        from match_engine import score_reviews,ai_weight
        import copy
        weight=ai_weight(self.settings);reports=copy.deepcopy(self.match_report);changed=False
        for report in reports:
            candidates=report.get('candidates',[])
            scores={index:{'confidence':candidate['ai_confidence'],'reason':candidate.get('ai_reason','')} for index,candidate in enumerate(candidates[:30]) if type(candidate.get('ai_confidence')) in (int,float) and 0<=candidate['ai_confidence']<=1}
            if not scores or all(candidates[index].get('ai_weight')==weight for index in scores):continue
            score_reviews(candidates,scores,weight);changed=True
        if changed:self.save_match_report(reports)
        return changed

    def save_game(self, ident, values):
        values=dict(values)
        if values.get('save_dir'):
            from save_groups import complete_directory
            values['save_dir']=str(complete_directory(values['save_dir']))
        self.local[ident] = {**self.local.get(ident, {}), **values}
        write_json(self.profile / 'games.json', self.local)

    def update_library(self,updates):
        known={game['id']:dict(game) for game in self.games}
        group_names=set(self.groups)
        for item in updates:
            if item['id'] not in known:raise ValueError('游戏条目已不存在')
            game=known[item['id']]
            if 'category' in item:
                category=item['category']
                if not isinstance(category,str) or not 0<len(category.strip())<=32:raise ValueError('主分类名称最多 32 字')
                game.update(category=category.strip(),category_manual=True,groups=[category.strip()]);group_names.add(category.strip())
            if 'tags' in item:
                tags=item['tags']
                if not isinstance(tags,list) or len(tags)>6 or not all(isinstance(tag,str) and 0<len(tag.strip())<=32 for tag in tags):raise ValueError('每款游戏最多 6 个标签，每个最多 32 字')
                game['tags']=list(dict.fromkeys(tag.strip() for tag in tags));game['tags_manual']=bool(item.get('tags_manual',True))
                if item.get('tags_source'):game['tags_source']=item['tags_source']
                elif game['tags_manual']:game['tags_source']='手动'
            if 'favorite' in item:game['favorite']=bool(item['favorite'])
            if 'release_date' in item:
                from library_sources import release_date
                value=item['release_date']
                if not isinstance(value,str) or value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or value and not release_date(value):raise ValueError('发行日期须为 YYYY-MM-DD，留空表示未知')
                game.update(release_date=release_date(value),release_date_manual=bool(value),release_date_source='手动' if value else '')
            if 'series' in item:
                value=item['series']
                if not isinstance(value,str) or len(value)>80:raise ValueError('系列名最多 80 字')
                game['series']=value.strip()
            if 'groups' in item:
                groups=item['groups']
                if not isinstance(groups,list) or len(groups)>20 or not all(isinstance(value,str) and 0<len(value.strip())<=32 for value in groups):raise ValueError('分类名称最多 32 字，每款游戏最多 20 个分类')
                game['groups']=list(dict.fromkeys(value.strip() for value in groups));group_names.update(game['groups'])
        new_games=[known[game['id']] for game in self.games]
        write_json(self.root/'library.json',new_games);self.games=new_games
        self.groups=sorted(group_names);write_json(self.root/'groups.json',self.groups)

    def apply_classification(self,updates,allow_existing=False):
        from tag_catalog import classified
        known={game['id']:game for game in self.games}
        for item in updates:
            if item.get('id') not in known:raise ValueError('游戏条目已不存在')
            if classified(known[item['id']]) and not allow_existing:
                raise ValueError('所选游戏已有分类或标签，请确认后再重新分类')
        self.update_library([{key:item[key] for key in ('id','category','tags','series','tags_manual','tags_source') if key in item} for item in updates])

    def migrate_library(self):
        if read_json(self.root/'library-schema.json',{}).get('version',0)>=3:return
        if not self.games:write_json(self.root/'library-schema.json',{'version':3});return
        from library_catalog import primary,unique
        backup=self.root/'migrations/v23';backup.mkdir(parents=True,exist_ok=True)
        for name in ('library.json','groups.json'):
            if (self.root/name).is_file() and not (backup/name).exists():shutil.copy2(self.root/name,backup/name)
        for game in self.games:
            tags=unique([*game.get('tags',[]),*game.get('groups',[])]);game['tags']=tags
            if not game.get('category_manual'):game['category']=primary(tags)
            game['groups']=[game.get('category','其他')]
            game.setdefault('import_source','playnite' if game.get('source')=='Playnite' else 'folder' if game.get('source','local')=='local' else 'platform')
            if game.get('platform')=='steam' and game.get('external_id') and not str(game['external_id']).isdigit():game['platform']='local';game.pop('steam_appid',None)
            game.setdefault('platform','local')
        self.groups=sorted({game['category'] for game in self.games})
        write_json(self.root/'library.json',self.games);write_json(self.root/'groups.json',self.groups);write_json(self.root/'library-schema.json',{'version':3})

    def sync_playnite_metadata(self,rows):
        from library_sources import playnite_metadata,guid,merge_metadata
        from library_catalog import primary,unique
        raw_by_id={guid(raw.get('_id')):raw for raw in rows};count=0
        for game in self.games:
            raw=raw_by_id.get(game['id'])
            if raw is None:continue
            fields=playnite_metadata(raw)
            last=max(game.get('last_played') or '',fields.get('last_played') or '')
            merge_metadata(game,fields)
            if last:game['last_played']=last
            if fields['platform']!='steam':game.pop('steam_appid',None)
            if not game.get('category_manual'):game['category']=primary(game.get('tags',[]));game['groups']=[game['category']]
            relative=raw.get('BackgroundImage') or ''
            if relative:
                source=safe_child(Path(self.settings['library'])/'files',relative.replace('\\','/'))
                if source.is_file():
                    target=self.root/'backgrounds'/(game['id']+source.suffix.lower());target.parent.mkdir(exist_ok=True)
                    if not target.is_file():shutil.copy2(source,target)
                    game['background']=str(target)
            count+=1
        if count:
            self.groups=sorted(set(self.groups)|{game.get('category','其他') for game in self.games})
            write_json(self.root/'library.json',self.games);write_json(self.root/'groups.json',self.groups)
        return count

    def edit_group(self,old,new):
        new=new.strip()
        if len(new)>32:raise ValueError('分类名称最多 32 字')
        if old and old not in self.groups:raise ValueError('分类已不存在')
        if new and new!=old and new in self.groups:raise ValueError('已有同名分类')
        names=[name for name in self.groups if name!=old]
        if new:names.append(new)
        for game in self.games:
            if old in game.get('groups',[]):game['groups']=[new if name==old else name for name in game['groups'] if name!=old or new]
            if game.get('category')==old:game['category']=new or '其他'
        write_json(self.root/'library.json',self.games);self.groups=sorted(names);write_json(self.root/'groups.json',self.groups)

    def mark_played(self,ident):
        from datetime import datetime,timezone
        game=next((game for game in self.games if game['id']==ident),None)
        if game is None:return
        game['last_played']=datetime.now(timezone.utc).isoformat(timespec='seconds');game['play_count']=game.get('play_count',0)+1
        write_json(self.root/'library.json',self.games)

    def remove(self, ident):
        self.games = [g for g in self.games if g['id'] != ident]
        write_json(self.root / 'library.json', self.games)

    def read_playnite(self):
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
            for name in ('sources.db','genres.db','tags.db'):
                try:
                    if (library/name).is_file():shutil.copy2(library/name,temporary/name)
                except OSError:pass
            result = run_process(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                  str(RESOURCES / 'scripts/export_playnite.ps1'), '-AssemblyPath', str(dll),
                                  '-DatabasePath', str(temporary / 'games.db'), '-OutputPath', str(temporary / 'games.json')], timeout=60)
            if result.returncode:
                raise ValueError('Playnite 只读导出失败；请关闭 Playnite 后重试，或检查程序与库版本')
            rows = read_json(temporary / 'games.json', [])
        return rows

    def playnite_candidates(self):
        from library_sources import platform_for,candidate,playnite_metadata
        rows=[]
        library=Path(self.settings['library'])
        for raw in self.read_playnite():
            platform=platform_for(raw); external=str(raw.get('GameId',''))
            row=candidate(raw.get('Name','未命名'),platform,external,raw.get('InstallDirectory') or '')
            row.update(playnite_metadata(raw))
            row.update(id=str(uuid.UUID(raw['_id']['$guid'])),playnite=True,installed=bool(raw.get('IsInstalled')),raw=raw)
            relative=raw.get('CoverImage') or ''
            if relative:
                cover=safe_child(library/'files',relative.replace('\\','/'))
                if cover.is_file():row['cover']=str(cover)
            rows.append(row)
        write_json(self.profile/'playnite-reference.json',[{key:value for key,value in row.items() if key not in ('raw','cover')} for row in rows])
        return rows

    def import_playnite(self,platforms=None):
        rows=self.read_playnite()
        library=Path(self.settings['library'])
        existing = {g['id']: g for g in self.games}
        covers = self.root / 'covers'
        covers.mkdir(parents=True, exist_ok=True)
        count = 0
        for row in rows:
            from library_sources import platform_for,playnite_metadata,merge_metadata
            platform=platform_for(row)
            if platforms is not None and platform not in platforms:continue
            ident = str(uuid.UUID(row['_id']['$guid']))
            cover = ''
            relative = row.get('CoverImage') or ''
            if relative:
                source = safe_child(library / 'files', relative.replace('\\', '/'))
                if source.is_file():
                    target = covers / (ident + source.suffix.lower())
                    if not target.exists() or target.stat().st_mtime_ns!=source.stat().st_mtime_ns or target.stat().st_size!=source.stat().st_size:
                        shutil.copy2(source, target)
                    cover = str(target)
            existing[ident] = {**existing.get(ident, {}), 'id': ident, 'name': row.get('Name', '未命名'),
                               'cover': cover, 'installed': bool(row.get('IsInstalled')), 'source': 'Playnite',
                               'platform':platform,'external_id':str(row.get('GameId',''))}
            if platform=='steam' and str(row.get('GameId','')).isdigit():existing[ident]['steam_appid']=str(row['GameId'])
            fields=playnite_metadata(row)
            merge_metadata(existing[ident],fields)
            if platform!='steam':existing[ident].pop('steam_appid',None)
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
            module.now_file_ts = lambda: datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+self.identity[:8]
            module.now_iso = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
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

    def backup(self, ident, event='manual', session_key=''):
        game = self.game(ident)
        core = self.core()
        with closing(core.connect_db()) as conn:
            from cloud_identity import identity
            archive = core.snapshot_game(conn, game, event, '新版手动备份' if event == 'manual' else '自动备份',
                                         auto_keep=max(1,min(100,int(self.settings.get('auto_snapshot_keep',5)))),session_key=session_key,
                                         game_identity=identity(next(item for item in self.games if item['id']==ident)))
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
        self.rclone(['copyto', str(archive), target, '--transfers', '1', '--checkers', '2','--immutable'])
        from cloud_history import publish
        publish(self,ident,archive,target)
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
            rows = conn.execute('SELECT s.* FROM snapshots s JOIN games g ON s.game_id=g.id WHERE g.name=?', (ident,)).fetchall()
        from datetime import datetime
        def timestamp(row):
            try:return datetime.fromisoformat(row['created_at'].replace('Z','+00:00')).timestamp()
            except ValueError:return 0
        return sorted([dict(row) for row in rows],key=lambda row:(timestamp(row),row['id']),reverse=True)

    def set_snapshot_note(self,ident,snapshot,note):
        if len(note)>1000:raise ValueError('备注最多 1000 字')
        row=next((row for row in self.history(ident) if row['id']==snapshot),None)
        if row is None:raise ValueError('备份不属于所选游戏')
        with closing(self.core().connect_db()) as connection:
            connection.execute('UPDATE snapshots SET note=? WHERE id=?',(note,snapshot));connection.commit()
        if row['uploaded'] and row['cloud_ref']:
            from cloud_history import publish
            try:publish(self,ident,Path(row['archive_path']),row['cloud_ref'])
            except Exception:raise ValueError('备注已保存在本机，云端备注更新失败，请重试') from None

    def cloud_history(self,ident):
        from cloud_history import listing
        return listing(self,ident)

    def receive_cloud_snapshot(self,ident,record):
        from cloud_history import receive
        return receive(self,ident,record)

    def restore_preview(self,ident,snapshot):
        from save_restore import inspect
        return inspect(self,ident,snapshot)

    def restore(self, ident, snapshot, options=None):
        from save_restore import restore
        return restore(self,ident,snapshot,options)

    def retry(self, ident):
        count = 0
        for row in self.history(ident):
            if not row['uploaded'] and Path(row['archive_path']).is_file():
                self.upload(ident, Path(row['archive_path']))
                count += 1
        return count

    def launch(self, ident):
        local = self.local.get(ident, {})
        process=None
        mode=local.get('launch_mode','direct' if local.get('exe') else 'playnite')
        if mode=='platform':
            uri=local.get('launch_uri','')
            if not uri.startswith(('steam://rungameid/','com.epicgames.launcher://apps/','uplay://launch/')):
                raise ValueError('平台启动地址无效，请重新导入')
            os.startfile(uri)
        elif mode=='direct':
            if not local.get('exe'): raise ValueError('直接启动需要在游戏设置中选择 EXE')
            exe = Path(local['exe'])
            if not exe.is_file():
                raise ValueError('本机启动文件不存在，请重新设置')
            arguments=local.get('arguments','').strip()
            command=subprocess.list2cmdline([str(exe)])+(' '+arguments if arguments else '')
            if exe.suffix.casefold() in ('.bat','.cmd'):
                if arguments:raise ValueError('批处理启动暂不支持额外参数，请在 BAT 中设置')
                process=subprocess.Popen([os.environ.get('COMSPEC',r'C:\Windows\System32\cmd.exe'),'/d','/c',str(exe)],cwd=local.get('working_dir') or exe.parent,creationflags=subprocess.CREATE_NO_WINDOW)
            else:process=subprocess.Popen(command,cwd=local.get('working_dir') or exe.parent)
        else:
            base = Path(self.settings['playnite'])
            if not (base / 'Playnite.DesktopApp.exe').exists():
                base /= 'Playnite'
            exe = base / 'Playnite.DesktopApp.exe'
            if not exe.is_file():
                raise ValueError('本机 Playnite 路径不存在，请重新设置')
            process=subprocess.Popen([str(exe), '--start', str(uuid.UUID(ident))], cwd=base)
        self.mark_played(ident)
        return process.pid if process else None

    def match_game(self,ident,progress=None,cancel=None):
        from match_engine import match
        return match(self,ident,progress,cancel)

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
        return '云端目录已验证，设置已保存'

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
