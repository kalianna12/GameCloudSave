"""Read Steam Auto-Cloud rules from local appinfo (v39-v41) and SteamDB UFS."""
from pathlib import Path
from functools import lru_cache
from html.parser import HTMLParser
from urllib.request import Request,urlopen
import mmap,struct,re,time,json,os

ROOTS={'WinAppDataLocal':'local','WinAppDataLocalLow':'locallow','WinAppDataRoaming':'roaming','WinMyDocuments':'documents','WinSavedGames':'savedgames','gameinstall':'install'}

@lru_cache(maxsize=1)
def app_index(path,modified,size):
    if size>512*1024*1024:raise ValueError('Steam appinfo 超过读取上限')
    with open(path,'rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        magic,universe=struct.unpack_from('<II',data);version=magic&255
        if magic not in (0x07564427,0x07564428,0x07564429):raise ValueError('Steam appinfo 版本暂不支持')
        offset=16 if version==41 else 8;strings=[];entries={}
        if version==41:
            pointer=struct.unpack_from('<Q',data,8)[0];count=struct.unpack_from('<I',data,pointer)[0];pointer+=4
            if count>1000000:raise ValueError('Steam 字符串表过大')
            for _ in range(count):
                end=data.find(b'\0',pointer)
                if end<0:raise ValueError('Steam appinfo 尚未写入完整')
                strings.append(data[pointer:end].decode('utf-8',errors='replace'));pointer=end+1
        for _ in range(200000):
            appid=struct.unpack_from('<I',data,offset)[0]
            if not appid:break
            length=struct.unpack_from('<I',data,offset+4)[0];header=60 if version>=40 else 40
            if length<header or offset+8+length>size:raise ValueError('Steam appinfo 记录不完整')
            entries[appid]=(offset+8+header,length-header);offset+=8+length
        return entries,strings

def local_rules(file,appid):
    file=Path(file);stamp=file.stat();entries,strings=app_index(str(file),stamp.st_mtime_ns,stamp.st_size)
    if int(appid) not in entries:return []
    offset,size=entries[int(appid)]
    with file.open('rb') as f:f.seek(offset);data=f.read(size)
    position=0;nodes=0
    def take(n):
        nonlocal position
        if position+n>len(data):raise ValueError('Steam appinfo 记录不完整')
        value=data[position:position+n];position+=n;return value
    def text():
        nonlocal position
        end=data.find(b'\0',position)
        if end<0:raise ValueError('Steam appinfo 字段不完整')
        value=data[position:end].decode('utf-8',errors='replace');position=end+1;return value
    def tree(depth=0):
        nonlocal nodes
        if depth>48:raise ValueError('Steam appinfo 嵌套过深')
        result={}
        while position<len(data):
            kind=take(1)[0]
            if kind in (8,11):break
            key=strings[struct.unpack('<I',take(4))[0]] if strings else text();nodes+=1
            if nodes>100000:raise ValueError('Steam appinfo 条目过多')
            if kind==0:value=tree(depth+1)
            elif kind==1:value=text()
            elif kind in (2,4,6):value=struct.unpack('<i',take(4))[0]
            elif kind==3:value=struct.unpack('<f',take(4))[0]
            elif kind in (7,9):value=struct.unpack('<Q',take(8))[0]
            elif kind==10:value=0
            else:raise ValueError('Steam appinfo 字段类型暂不支持')
            result[key]=value
        return result
    def collect(node):
        found=[]
        if isinstance(node,dict):
            if node.get('root') in ROOTS and 'path' in node:found.append({k:node[k] for k in ('root','path','pattern') if k in node})
            for value in node.values():found.extend(collect(value))
        return found
    # Parse only the selected application's bounded record, not the entire cache.
    parsed=tree();app=parsed.get('appinfo',parsed)
    return collect(app.get('ufs',{}))

def page_rules(html):
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_data(self,text):self.parts.append(text)
    parser=Text();parser.feed(html);text=' '.join(' '.join(parser.parts).split())
    rules=[]
    for match in re.finditer(r'\broot\s+(WinAppDataLocalLow|WinAppDataLocal|WinAppDataRoaming|WinMyDocuments|WinSavedGames|gameinstall)\s+path\s+(.*?)\s+pattern\s+([^\s]+)',text,re.I):
        key=next(k for k in ROOTS if k.casefold()==match[1].casefold())
        rules.append({'root':key,'path':match[2],'pattern':match[3]})
    return rules[:64]

def hints(rules,local,source):
    result=[]
    for row in rules:
        root=ROOTS.get(row.get('root'));relative=str(row.get('path','')).replace('\\','/').strip('/')
        if not root or '..' in relative.split('/') or ':' in relative or len(relative)>500:continue
        # A user's Steam ID is not a directory we can guess. Wildcards are
        # expanded only below a known root and capped by matching.scan.
        relative=re.sub(r'\{64BitSteamID\}|\{Steam3AccountID\}|\{SteamID\}', '*',relative,flags=re.I)
        if '{' in relative or '}' in relative:continue
        value={'root':root,'relative':relative or '.','pattern':str(row.get('pattern','*')),'reason':'Steam 云存档配置','source_url':source,'verified_rule':True}
        if value not in result:result.append(value)
    return result

def lookup(store,item,local,cancel):
    appid=str(item.get('steam_appid') or item.get('metadata_steam_appid') or (item.get('external_id') if item.get('platform')=='steam' else '') or '')
    if not appid.isdigit():return {}
    from achievement_steam import steam_roots
    found=[];source='https://steamdb.info/app/'+appid+'/ufs/'
    for root in steam_roots():
        try:found.extend(local_rules(root/'appcache/appinfo.vdf',appid))
        except (OSError,ValueError,IndexError,struct.error):pass
    if not found and not cancel.is_set():
        cache=store.profile/'steam-cloud-rules.json'
        from services import read_json,write_json
        with store.match_lock:records=read_json(cache,{});saved=records.get(appid,{})
        if time.time()-saved.get('time',0)<86400:found=saved.get('rules',[])
        else:
            request=Request(source,headers={'User-Agent':'GameCloudSave/2.7 (save location lookup)'})
            try:
                with urlopen(request,timeout=7) as response:body=response.read(2*1024*1024+1)
                if len(body)<=2*1024*1024:found=page_rules(body.decode('utf-8',errors='replace'))
            except OSError:pass
            with store.match_lock:
                records=read_json(cache,{});records[appid]={'time':time.time(),'rules':found};write_json(cache,records)
    return {'hints':hints(found,local,source),'sources':[{'title':'Steam 云存档配置','url':source}]} if found else {}
