"""Title hints and conservative matching shared by catalog retries and artwork search."""
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import PureWindowsPath
import ctypes,os,re,unicodedata

@lru_cache(maxsize=2048)
def simplified(value):
    if os.name=='nt':
        function=ctypes.windll.kernel32.LCMapStringW
        function.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.c_int,ctypes.c_wchar_p,ctypes.c_int]
        function.restype=ctypes.c_int
        length=function(0x0804,0x02000000,value,-1,None,0)
        if length:
            buffer=ctypes.create_unicode_buffer(length)
            if function(0x0804,0x02000000,value,-1,buffer,length):return buffer.value
    return value

@lru_cache(maxsize=2048)
def traditional(value):
    if os.name=='nt':
        function=ctypes.windll.kernel32.LCMapStringW
        function.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.c_int,ctypes.c_wchar_p,ctypes.c_int]
        function.restype=ctypes.c_int
        length=function(0x0404,0x04000000,value,-1,None,0)
        if length:
            buffer=ctypes.create_unicode_buffer(length)
            if function(0x0404,0x04000000,value,-1,buffer,length):return buffer.value
    return value

def title_key(value):
    value=simplified(unicodedata.normalize('NFKC',value).casefold())
    # Standalone Roman installment numbers are equivalent to Arabic numbers.
    numerals={'ii':'2','iii':'3','iv':'4','v':'5','vi':'6','vii':'7','viii':'8','ix':'9','x':'10'}
    value=re.sub(r'\b(?:viii|vii|iii|vi|iv|ii|ix|v|x)\b',lambda match:numerals[match[0]],value)
    return re.sub(r'[\W_]','',value)

def titles(row):
    values=[row.get('name'),row.get('title'),row.get('alttitle'),*row.get('aliases',[])]
    for item in row.get('titles',[]):values.extend([item.get('title'),item.get('latin')])
    return [value for value in values if isinstance(value,str) and value.strip()]

def score(names,row,deep=False):
    best=0
    for name in names:
        query=title_key(name)
        if not query:continue
        for value in titles(row):
            candidate=title_key(value)
            if not candidate:continue
            rating=SequenceMatcher(None,query,candidate).ratio()
            # Do not confuse sequels, remasters, remakes or different numbered episodes.
            if re.findall(r'\d+(?:\.\d+)?',query)!=re.findall(r'\d+(?:\.\d+)?',candidate):rating=min(rating,.5)
            editions=('remastered','remaster','remake','重制','重制版')
            if any((edition in query)!=(edition in candidate) for edition in editions):rating=min(rating,.5)
            if deep and min(len(query),len(candidate))<6 and rating<.99:rating=min(rating,.5)
            best=max(best,rating)
    return best

def best_match(rows,names,deep=False,threshold=None):
    ranked=sorted(((score(names,row,deep),row) for row in rows),key=lambda pair:-pair[0])
    cutoff=threshold if threshold is not None else .87 if deep else .93
    if not ranked or ranked[0][0]<cutoff or len(ranked)>1 and ranked[0][0]-ranked[1][0]<.08:return None
    return {**ranked[0][1],'score':ranked[0][0]}

def query_hints(store,game,raw=None):
    identity=getattr(store,'identities',{}).get(game['id'],{})
    local=store.local.get(game['id'],{})
    values=[game['name'],(raw or {}).get('Name'),game.get('source_name'),game.get('original_name'),identity.get('english_name'),
            *identity.get('aliases',[]),*game.get('aliases',[])]
    if local.get('install_dir'):values.append(PureWindowsPath(local['install_dir']).name)
    if local.get('exe'):
        stem=PureWindowsPath(local['exe']).stem
        if stem.casefold() not in ('game','start','launcher','launch','main','setup','uninstall','adv','siglusengine'):values.append(stem)
    result=[];seen=set()
    def add(value):
        if not isinstance(value,str):return
        value=value.strip()[:150];key=title_key(value)
        if len(key)>=3 and key not in seen:result.append(value);seen.add(key)
    for value in values:
        add(value)
        if isinstance(value,str):
            clean=re.sub(r'[\[【(（](?:[^\]】)）]*(?:汉化|中文|免安装|硬盘版|整合版|补丁|安装版|portable|repack|v\d)[^\]】)）]*)[\]】)）]','',value,flags=re.I)
            clean=re.sub(r'(?:[ _-]+(?:v\d+(?:\.\d+)+|汉化版|中文版|免安装版|绿色版))+$','',clean,flags=re.I)
            add(clean)
    return result[:5]

def search_queries(names):
    # Full names first. Broader prefixes discover candidates; confidence always uses full hints.
    result=list(names[:4])
    if names:
        name=names[0]
        tokens=re.split(r'\s+[-–—:]\s*|\s+',name)
        fragment=tokens[0] if len(tokens)>1 and len(title_key(tokens[0]))>=6 else ''
        cjk=re.match(r'[\u3400-\u9fff]{8,}',name)
        if cjk:fragment=cjk[0][:6]
        if fragment and fragment not in result:result.append(fragment)
    # Keep script variants for querying: normalization used for *matching* must
    # not deduplicate 愛/爱 before a database has had a chance to search them.
    for name in names[:2]:
        for variant in (traditional(name),simplified(name)):
            if variant and variant not in result:result.append(variant)
    return result[:8]
