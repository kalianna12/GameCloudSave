"""Manual artwork search: paired catalog assets and bounded in-page captures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from urllib.parse import urlsplit
import hashlib

def search(store,query,provider,kind='cover',use_ai=False,cancel=None):
    from cover_sources import search as catalog
    from library_enrichment import cached_lookup
    rows=catalog(store,query,provider,use_ai,cancel)[:16]
    def enrich(original):
        row=dict(original)
        if row.get('provider')=='steam' and row.get('appid'):
            try:
                if cancel and cancel.is_set():return row
                fields=cached_lookup(store,{'name':row['name'],'steam_appid':row['appid'],'category':'','tags':[]})
                row.update(metadata_fields=fields,background_url=fields.get('background_url',''),background_state='available' if fields.get('background_url') else 'none')
            except Exception:row['background_state']='unknown'
        else:row['background_state']='available' if row.get('background_url') else 'none'
        row['artwork_kind']=kind
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(enrich,rows))

def web_rows(records,provider,kind):
    if kind not in ('cover','background'):raise ValueError('图片类型无效')
    def remote(value):
        if not isinstance(value,str) or len(value)>8192:return ''
        value=value.strip()
        try:
            parsed=urlsplit(value)
            return value if parsed.scheme in ('https','http') and parsed.hostname and not parsed.username else ''
        except ValueError:return ''
    result=[];seen=set()
    for record in records[:80]:
        if not isinstance(record,dict):continue
        url=remote(record.get('image'))
        if not url or url in seen:continue
        seen.add(url)
        thumb=record.get('thumbnail','')
        if not (isinstance(thumb,str) and len(thumb)<350000 and thumb.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,'))):thumb=remote(thumb)
        width=record.get('width',0);height=record.get('height',0)
        width=width if type(width)==int and 0<=width<=16384 else 0;height=height if type(height)==int and 0<=height<=16384 else 0
        if width and height:
            ratio=width/height
            if kind=='background' and not 1.2<=ratio<=4:continue
            if kind=='cover' and not .4<=ratio<=1.15:continue
        result.append({'id':'web:'+hashlib.sha256((provider+url).encode()).hexdigest()[:24],'name':str(record.get('name') or '搜索图片')[:200],
                       'image':url,'thumbnail':thumb or url,'page':remote(record.get('page')),'provider':provider,'user_authorized':True,
                       'width':width,'height':height,'artwork_kind':kind,'background_url':url if kind=='background' else '',
                       'background_state':'available' if kind=='background' else 'not_searched'})
    return result[:48]

def stage(store,ident,record,kind,previous=None):
    from enrichment_manual import base,candidate
    from cover_sources import download
    from library_artwork import prepare
    if kind=='metadata':
        return candidate(store,ident,record,previous,include_artwork=False)
    game,row,needs=base(store,ident,previous)
    if kind not in ('cover','background'):raise ValueError('图片类型无效')
    if not needs[kind]:raise ValueError('该项已有图片；如需更换，请进入游戏设置')
    if kind=='cover':value=download(store,record)
    else:
        url=record.get('background_url','')
        if not url:raise ValueError('该结果没有横幅，请切换横幅搜索')
        value=prepare(store,url,user_authorized=record.get('user_authorized',False))
    row['fields'][kind]=value;row['sources'][kind]=record.get('provider','手动');row['notes']=['已选择图片，应用所选补全后保存']
    if kind=='cover':row['cover_name']=record['name']
    return row

def set_background(store,ident,source,origin='手动',authorized=False):
    from library_artwork import prepare
    from services import write_json
    path=prepare(store,source,user_authorized=authorized)
    games=deepcopy(store.games);game=next((g for g in games if g['id']==ident),None)
    if game is None:raise ValueError('游戏已不存在')
    game.update(background=path,background_source=origin)
    write_json(store.root/'library.json',games);store.games=games
    return {'scope':'game','kind':'background'}
