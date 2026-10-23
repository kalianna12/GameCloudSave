"""Bounded read-only Steam binary KeyValues cache adapter, no client injection.

Python adaptation of the cache-group/bit mapping in PlayniteAchievements'
SteamLocalStatsReader and binary reader. Copyright (c) 2026 Justin Delano.
MIT notice: ui/assets/third-party/PlayniteAchievements-LICENSE.txt.
Reference commit: 002eaa8b2cdcc5df4c6f4bf2d886c5fbbc2390b2.
"""
import os
from pathlib import Path
import re
import struct
from functools import lru_cache


def read_kv(path):
    path=Path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Steam 成就缓存超过读取上限')
    with path.open('rb') as source:data=source.read(32*1024*1024+1)
    if len(data)>32*1024*1024:raise ValueError('Steam 成就缓存超过读取上限')
    offset=0;nodes=0
    def take(length):
        nonlocal offset
        if offset+length>len(data):raise ValueError('Steam 缓存尚未写入完整')
        value=data[offset:offset+length];offset+=length;return value
    def string():
        nonlocal offset
        end=data.find(b'\0',offset,min(len(data),offset+65536))
        if end<0:raise ValueError('Steam 缓存字符串未结束')
        value=data[offset:end].decode('utf-8',errors='replace');offset=end+1;return value
    def children(depth=0,required=False):
        nonlocal nodes
        if depth>48:raise ValueError('Steam 缓存嵌套过深')
        result={}
        while offset<len(data):
            kind=take(1)[0]
            if kind in (8,11):return result
            name=string();nodes+=1
            if nodes>200000:raise ValueError('Steam 缓存条目过多')
            if kind==0:value=children(depth+1,True)
            elif kind==1:value=string()
            elif kind in (2,4,6):value=struct.unpack('<i',take(4))[0]
            elif kind==3:value=struct.unpack('<f',take(4))[0]
            elif kind==5:value=take(struct.unpack('<H',take(2))[0]*2).decode('utf-16-le').rstrip('\0')
            elif kind in (7,9):value=struct.unpack('<q',take(8))[0]
            elif kind==10:value=0
            else:raise ValueError('不支持的 Steam 缓存类型')
            result[name]=value
        if required:raise ValueError('Steam 缓存对象尚未结束')
        return result
    return children()


def descendant(tree,key):
    if not isinstance(tree,dict):return None
    for name,value in tree.items():
        if name.casefold()==key.casefold():return value
    for value in tree.values():
        found=descendant(value,key)
        if found is not None:return found
    return None


@lru_cache(maxsize=32)
def schema_cached(path,stamp,size):
    from achievement_files import localized,number
    stats=descendant(read_kv(path),'stats') or {};rows=[]
    for group,value in stats.items():
        if not isinstance(value,dict):continue
        for bit,entry in (value.get('bits') or {}).items():
            if not isinstance(entry,dict) or not entry.get('name'):continue
            display=entry.get('display') or {};progress=entry.get('progress') or {}
            icon=str(display.get('icon') or '')
            appid=re.search(r'Schema_(\d+)\.bin$',str(path),re.I)
            if icon and not icon.startswith(('http://','https://')) and appid:
                icon=f'https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{appid[1]}/{icon}'
            rows.append({'id':str(entry['name']),'name':localized(display.get('name')) or str(entry['name']),
                         'description':localized(display.get('desc')),'hidden':str(display.get('hidden','0'))=='1',
                         'icon':icon,'max':max(0,number(progress.get('max_val'))-number(progress.get('min_val'))),
                         '_group':str(group),'_bit':int(bit),'_stat':(progress.get('value') or {}).get('operand1',''),
                         '_min':number(progress.get('min_val'))})
    return rows[:5000],stats


def schema_file(path):
    path=Path(path);stat=path.stat();return schema_cached(str(path),stat.st_mtime_ns,stat.st_size)[0]


def progress_schema_path(path):
    path=Path(path);match=re.fullmatch(r'UserGameStats_(?:\d+_)?(\d+)\.bin',path.name,re.I)
    if not match:raise ValueError('请选择 UserGameStats_<账号>_<AppID>.bin，不是定义缓存')
    return path.parent/('UserGameStatsSchema_'+match[1]+'.bin')


def progress_file(path):
    path=Path(path);schema=progress_schema_path(path)
    info=schema.stat();rows,definitions=schema_cached(str(schema),info.st_mtime_ns,info.st_size)
    if not rows:raise ValueError('对应的 Steam 定义缓存没有可读成就')
    tree=read_kv(path);cache=descendant(tree,'cache');result={}
    if isinstance(cache,dict):
        stat_ids={str(v.get('name')):str(k) for k,v in definitions.items() if isinstance(v,dict) and str(v.get('type'))=='1'}
        for row in rows:
            group=cache.get(row['_group'],{});mask=int(group.get('data',0));bit=row['_bit']
            value=(cache.get(stat_ids.get(row['_stat'],''),{}) or {}).get('data',0)
            result[row['id']]={'unlocked':bool(mask&(1<<bit)),'time':max(0,int((group.get('AchievementTimes') or {}).get(str(bit),0))),
                               'progress':max(0,min(row['max'],float(value)-row['_min'])) if row['_stat'] else 0}
        return result
    # Older caches store named achieved flags rather than bitmask groups.
    achievements=descendant(tree,'achievements')
    if isinstance(achievements,dict):
        from achievement_files import state_entry
        for name,entry in achievements.items():
            row=state_entry(entry)
            if row is not None:result[name]=row
        return result
    raise ValueError('此 Steam 缓存没有支持的成就进度结构')


def steam_roots():
    roots=[]
    if os.name=='nt':
        import winreg
        for hive,key,field in [(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Valve\Steam','InstallPath')]:
            try:
                with winreg.OpenKey(hive,key) as handle:roots.append(Path(winreg.QueryValueEx(handle,field)[0]))
            except OSError:pass
    return list(dict.fromkeys(roots))


def cache_paths(appid,roots=None):
    sources=[];schemas=[]
    for root in steam_roots() if roots is None else roots:
        directory=Path(root)/'appcache/stats'
        schema=directory/f'UserGameStatsSchema_{appid}.bin'
        if schema.is_file():schemas.append(schema)
        try:
            for path in directory.glob(f'UserGameStats_*_{appid}.bin'):
                if re.fullmatch(r'UserGameStats_\d+_'+re.escape(str(appid))+r'\.bin',path.name,re.I):sources.append(path)
        except OSError:pass
    return sources[:30],schemas[:8]
