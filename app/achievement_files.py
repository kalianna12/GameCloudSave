"""Read-only local achievement adapters. Never changes a game's files or DLLs."""
from __future__ import annotations
import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

LIMIT = 8 * 1024 * 1024
FILENAMES = ('achievements.json', 'achievements.ini', 'user_stats.ini')
FLAGS = ('earned', 'achieved', 'unlocked', 'achievedstate', 'haveachieved', 'bachieved')
TIMES = ('earned_time', 'unlocktime', 'unlock_time', 'timestamp', 'time')


def read_text(path):
    path = Path(path)
    if path.stat().st_size > LIMIT: raise ValueError('成就文件超过 8 MB，未读取')
    data = path.read_bytes()
    if len(data) > LIMIT: raise ValueError('成就文件过大')
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):return data.decode('utf-16')
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:return data.decode('gb18030')


def number(value):
    try:
        result = float(int(value, 16)) if isinstance(value, str) and value.lower().startswith('0x') else float(value)
        return result if math.isfinite(result) else 0
    except (TypeError, ValueError): return 0


def truth(value):
    return value is True or str(value).strip().casefold() in ('true', '1', 'yes', 'unlocked', 'achieved')


def state_entry(value):
    if not isinstance(value, dict): return None
    fields = {str(k).casefold(): v for k, v in value.items()}
    flag = next((fields[k] for k in FLAGS if k in fields), None)
    stamp = max((number(fields.get(k)) for k in TIMES), default=0)
    if flag is None and not stamp and not any(k in fields for k in ('progress', 'cur_progress', 'current')): return None
    return {'unlocked': truth(flag) if flag is not None else stamp > 0,
            'time': max(0, min(stamp, 32503680000)),
            'progress': max(0, number(fields.get('progress', fields.get('cur_progress', fields.get('current', 0)))))}


def parse_state(path):
    """JSON schema lists are not progress. Numeric stats alone never unlock achievements."""
    if Path(path).suffix.casefold()=='.bin':
        from achievement_steam import progress_file
        return progress_file(path)
    text = read_text(path)
    entries = {}
    if Path(path).suffix.casefold() == '.json':
        data = json.loads(text)
        if isinstance(data, dict): data = data.get('achievements', data)
        if isinstance(data, list):
            pairs = ((row.get('name') or row.get('apiName') or row.get('id'), row) for row in data if isinstance(row, dict))
        elif isinstance(data, dict): pairs = data.items()
        else: raise ValueError('不支持的成就 JSON 结构')
        for index,(key, value) in enumerate(pairs):
            if index>=5000:break
            state = state_entry(value)
            if key and state is not None: entries[str(key)] = state
    else:
        parser = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';', '#'))
        parser.optionxform = str
        parser.read_string(text)
        for section in parser.sections()[:5000]:
            fields = dict(parser.items(section))
            if section.casefold() in ('achievements', 'achievement', 'userstats'):
                for key, value in fields.items():
                    if re.fullmatch(r'(?:true|false|[01])', value.strip(), re.I):
                        entries[key] = {'unlocked': truth(value), 'time': 0, 'progress': 0}
                    elif value.startswith('{'):
                        try: row = state_entry(json.loads(value))
                        except ValueError: row = None
                        if row: entries[key] = row
            else:
                row = state_entry(fields)
                if row: entries[re.sub(r'^ACHIEVEMENTS\.', '', section, flags=re.I)] = row
            # Flat achievement suffix fields, e.g. ACH_FIRST.earned=1.
            grouped={}
            for key,value in fields.items():
                match=re.fullmatch(r'(.+)[._](earned|achieved|unlocked|earned_time|unlocktime|progress)',key,re.I)
                if match:grouped.setdefault(match[1],{})[match[2]]=value
            for key,fields in grouped.items():
                row=state_entry(fields)
                if row is not None:entries[key]=row
    return entries


def localized(value):
    if isinstance(value, dict): return str(value.get('schinese') or value.get('simplified_chinese') or value.get('english') or next(iter(value.values()), ''))[:2000]
    return str(value or '')[:2000]


def normalize_schema(data, base=None, appid=''):
    if isinstance(data, dict):
        data = data.get('response', data.get('game', data))
        if isinstance(data, dict): data = data.get('availableGameStats', data)
        if isinstance(data, dict): data = data.get('achievements', [])
    if not isinstance(data, list): raise ValueError('成就定义需要包含 achievements 列表')
    result = {}; base = Path(base) if base else None
    for row in data[:5000]:
        if not isinstance(row, dict) or row.get('archived'): continue
        key = str(row.get('internal_name') or row.get('name') or row.get('apiName') or '').strip()[:240]
        title = localized(row.get('localized_name') or row.get('displayName') or row.get('display_name'))
        if not key or not title: continue  # Progress-only JSON is not a schema.
        icon = str(row.get('icon') or '')
        if icon and not urlsplit(icon).scheme:
            if base:
                path = (base / icon).resolve()
                icon = str(path) if path.is_relative_to(base.resolve()) and path.is_file() and path.stat().st_size <= 1024*1024 else ''
            elif appid and re.fullmatch(r'[A-Za-z0-9_.-]+', icon):
                icon = f'https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{appid}/{icon}'
            else: icon = ''
        result[key] = {'id': key, 'name': title[:300], 'description': localized(row.get('localized_desc') or row.get('description')),
                       'hidden': truth(row.get('hidden')), 'icon': icon,
                       'rarity':number(row.get('player_percent_unlocked',row.get('steamPercentage',0))),
                       'max': max(0, number(row.get('max_progress_int', row.get('max_progress_float', row.get('max_progress', 0)))))}
    return list(result.values())


def fetch_json(url):
    request = Request(url, headers={'User-Agent': 'GameCloudSave/2.5 (local achievements)', 'Accept': 'application/json'})
    with urlopen(request, timeout=10) as response: data = response.read(LIMIT + 1)
    if len(data) > LIMIT: raise ValueError('成就资料响应过大')
    return json.loads(data)


def steam_schema(appid):
    if not re.fullmatch(r'[1-9]\d{0,11}', str(appid)): raise ValueError('请输入正确的 Steam App ID')
    url = 'https://api.steampowered.com/IPlayerService/GetGameAchievements/v1/?' + urlencode({'appid': appid, 'language': 'schinese'})
    result = normalize_schema(fetch_json(url), appid=appid)
    if not result: raise ValueError('此游戏没有公开成就定义；可导入本地定义文件')
    return result


def identify(game, local, override=''):
    value = str(override or (game.get('steam_appid') or game.get('external_id') if game.get('platform')=='steam' else '') or game.get('metadata_steam_appid') or '')
    if value.isdigit(): return value
    root = Path(local.get('install_dir') or Path(local.get('exe') or '.').parent)
    files=[root / 'steam_appid.txt',root/'steam_settings/steam_appid.txt',root/'steam_settings/appid.txt']
    for sub in ('','Binaries/Win64','Engine/Binaries/ThirdParty/Steamworks/Steamv153/Win64','steam_settings'):
        files.extend(root/sub/name for name in ('steam_emu.ini','steam_api.ini','steam_api64.ini','SmartSteamEmu.ini','configs.app.ini'))
    for file in files:
        try:
            value = read_text(file).strip()
            if re.fullmatch(r'[1-9]\d{0,11}', value): return value
            matches=re.findall(r'^\s*(?:AppId|SteamAppId|SteamAppID)\s*=\s*([1-9]\d{0,11})\s*(?:;.*)?$',value,re.I|re.M)
            if len(set(matches))==1:return matches[0]
        except (OSError, ValueError): pass
    return ''


def walk_files(root, depth=6, budget=700):
    """Bounded scan of a game/known AppID folder; no disk-wide scans or links."""
    root = Path(root)
    if not root.is_dir(): return []
    found = []; pending = [(root, 0)]; seen = 0
    while pending and seen < budget:
        directory, level = pending.pop(); seen += 1
        try:
            with os.scandir(directory) as iterator:
                for index, entry in enumerate(iterator):
                    if index > 1500: break
                    if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400: continue
                    if entry.is_file(follow_symlinks=False) and (entry.name.casefold() in FILENAMES or re.fullmatch(r'(?:achievements?|user_stats).*\.(?:json|ini)',entry.name,re.I) or re.fullmatch(r'UserGameStats(?:Schema)?_[\d_]+\.bin',entry.name,re.I)):
                        found.append(Path(entry.path))
                    elif level < depth and entry.is_dir(follow_symlinks=False) and entry.name.casefold() not in ('node_modules', '.git', 'video', 'movies'):
                        pending.append((Path(entry.path), level + 1))
        except OSError: continue
    return found


def discover(game, local, appid):
    roots = []
    for value in (local.get('install_dir'), str(Path(local['exe']).parent) if local.get('exe') else '', local.get('save_dir')):
        if value and Path(value).is_dir() and len(Path(value).resolve().parts) >= 3: roots.append(Path(value))
    if appid:
        for env, names in [('APPDATA', ('GSE Saves', 'Goldberg SteamEmu Saves', 'SmartSteamEmu')), ('LOCALAPPDATA', ('GSE Saves', 'Goldberg SteamEmu Saves', 'SKIDROW', 'EMPRESS', 'Steam/CODEX')), ('PUBLIC', ('Documents/Steam/CODEX', 'Documents/Steam/RUNE', 'Documents/Steam', 'Documents/OnlineFix'))]:
            if os.environ.get(env): roots.extend(Path(os.environ[env]) / name / appid for name in names)
        # Account-first and portable Steam-compatible layouts, still scoped to AppID.
        for env,name in [('APPDATA','SmartSteamEmu'),('LOCALAPPDATA','Steam'),('PUBLIC','Documents/Steam')]:
            base=Path(os.environ[env])/name if os.environ.get(env) else None
            if base and base.is_dir():
                try:
                    for parent in list(base.iterdir())[:80]:
                        if parent.is_dir() and not parent.is_symlink():roots.append(parent/appid)
                except OSError:pass
    roots.extend(Path(value) for value in local.get('achievement_roots',[])[:10] if value)
    sources = []; schemas = []; seen = set();rejected=[]
    for root in dict.fromkeys(roots):
        for path in walk_files(root):
            key = str(path.resolve()).casefold()
            if key in seen: continue
            seen.add(key)
            try:
                if path.suffix.casefold()=='.bin':
                    if not appid or not re.search(r'_'+re.escape(str(appid))+r'\.bin$',path.name,re.I):continue
                    if 'schema_' in path.name.casefold():
                        from achievement_steam import schema_file
                        rows=schema_file(path)
                        if rows:schemas.append((str(path),rows))
                        continue
                if path.suffix.casefold() == '.json':
                    schema = normalize_schema(json.loads(read_text(path)), path.parent)
                    if schema: schemas.append((str(path), schema))
                states = parse_state(path)
                # Empty state files outside steam_settings are valid pre-first-unlock records.
                if states or path.suffix.casefold() == '.json' and json.loads(read_text(path)) == {} and 'steam_settings' not in path.parts:
                    sources.append(str(path))
            except (OSError, ValueError, configparser.Error) as exc:rejected.append({'path':str(path),'reason':str(exc)[:150]})
    if appid:
        from achievement_steam import cache_paths,schema_file,steam_roots
        roots.extend(root/'appcache/stats' for root in steam_roots())
        stats,definitions=cache_paths(appid)
        for path in definitions:
            try:
                rows=schema_file(path)
                if rows:schemas.append((str(path),rows))
            except (OSError,ValueError) as exc:rejected.append({'path':str(path),'reason':str(exc)[:150]})
        for path in stats:
            try:
                parse_state(path);sources.append(str(path))
            except (OSError,ValueError) as exc:rejected.append({'path':str(path),'reason':str(exc)[:150]})
    return {'appid': appid, 'sources': list(dict.fromkeys(sources))[:40], 'schemas': schemas[:10],
            'checked':list(dict.fromkeys(map(str,roots)))[:60], 'rejected':rejected[:20]}


def namespace(appid, source):
    return hashlib.sha256((str(appid) + ':' + os.path.normcase(os.path.abspath(source)) if source else str(appid) + ':none').encode()).hexdigest()[:24]


def merge_progress(record, states, notify=False):
    """Monotonic history: missing/truncated/relocked files never erase or replay unlocks."""
    known = record.setdefault('unlocks', {}); updates = []; dirty = False
    initialized = record.get('initialized', False)
    for key, row in states.items():
        if row['unlocked'] and key not in known:
            known[key] = row['time'] or (time.time() if initialized and notify else 0); dirty = True
            if initialized and notify: updates.append(key)
    if not initialized: record['initialized'] = True; dirty = True
    if record.get('progress') != states: record['progress'] = states; dirty = True
    return updates, dirty


def canonical_states(states,schema):
    names={row['id'].casefold():row['id'] for row in schema}
    return {names.get(key.casefold(),key):value for key,value in states.items()}
