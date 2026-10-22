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
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')


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
    text = read_text(path)
    entries = {}
    if Path(path).suffix.casefold() == '.json':
        data = json.loads(text)
        if isinstance(data, dict): data = data.get('achievements', data)
        if isinstance(data, list):
            pairs = ((row.get('name') or row.get('apiName') or row.get('id'), row) for row in data if isinstance(row, dict))
        elif isinstance(data, dict): pairs = data.items()
        else: raise ValueError('不支持的成就 JSON 结构')
        for key, value in pairs:
            state = state_entry(value)
            if key and state is not None: entries[str(key)] = state
    else:
        parser = configparser.ConfigParser(interpolation=None, strict=False, inline_comment_prefixes=(';', '#'))
        parser.optionxform = str
        parser.read_string(text)
        for section in parser.sections():
            fields = dict(parser.items(section))
            if section.casefold() in ('achievements', 'achievement'):
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
    value = str(override or game.get('metadata_steam_appid') or game.get('steam_appid') or '')
    if value.isdigit(): return value
    root = Path(local.get('install_dir') or Path(local.get('exe') or '.').parent)
    for file in (root / 'steam_appid.txt', root / 'steam_settings/steam_appid.txt', root / 'steam_settings/appid.txt'):
        try:
            value = read_text(file).strip()
            if re.fullmatch(r'[1-9]\d{0,11}', value): return value
        except (OSError, ValueError): pass
    return ''


def walk_files(root, depth=4, budget=700):
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
                    if entry.is_file(follow_symlinks=False) and entry.name.casefold() in FILENAMES:
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
    sources = []; schemas = []; seen = set()
    for root in dict.fromkeys(roots):
        for path in walk_files(root):
            key = str(path.resolve()).casefold()
            if key in seen: continue
            seen.add(key)
            try:
                if path.suffix.casefold() == '.json':
                    schema = normalize_schema(json.loads(read_text(path)), path.parent)
                    if schema: schemas.append((str(path), schema))
                states = parse_state(path)
                # Empty state files outside steam_settings are valid pre-first-unlock records.
                if states or path.suffix.casefold() == '.json' and json.loads(read_text(path)) == {} and 'steam_settings' not in path.parts:
                    sources.append(str(path))
            except (OSError, ValueError, configparser.Error): continue
    return {'appid': appid, 'sources': sources[:40], 'schemas': schemas[:10]}


def namespace(appid, source):
    return hashlib.sha256((str(appid) + ':' + os.path.normcase(os.path.abspath(source)) if source else str(appid) + ':none').encode()).hexdigest()[:24]


def merge_progress(record, states, notify=False):
    """Monotonic history: missing/truncated/relocked files never erase or replay unlocks."""
    known = record.setdefault('unlocks', {}); updates = []; dirty = False
    initialized = record.get('initialized', False)
    for key, row in states.items():
        if row['unlocked'] and key not in known:
            known[key] = row['time'] or time.time(); dirty = True
            if initialized and notify: updates.append(key)
    if not initialized: record['initialized'] = True; dirty = True
    if record.get('progress') != states: record['progress'] = states; dirty = True
    return updates, dirty
