"""Best-effort source metadata. Dates never come from model guesses."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
import json,re,time

from library_sources import release_date
from tag_catalog import normalize_tags,vocabulary,MAX_TAGS
from catalog_match import title_key,best_match

def local_utc_offset():return int(datetime.now().astimezone().utcoffset().total_seconds())

def fetch(url,body=None):
    headers={'User-Agent':'GameCloudSave/2.3','Accept':'application/json','Content-Type':'application/json'}
    if urlsplit(url).hostname=='store.steampowered.com':
        headers['Cookie']='timezoneOffset='+str(local_utc_offset())+',0'
    request=Request(url,data=json.dumps(body).encode() if body is not None else None,
                    headers=headers)
    with urlopen(request,timeout=8) as response:data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024:raise ValueError('资料响应过大')
    return json.loads(data)

def steam_date(value):
    if not isinstance(value,dict) or value.get('coming_soon'):return ''
    text=value.get('date','')
    if not isinstance(text,str):return ''
    parsed=release_date(text)
    if parsed:return parsed
    chinese=re.fullmatch(r'\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*',text)
    if chinese:
        try:return datetime(*map(int,chinese.groups())).date().isoformat()
        except ValueError:return ''
    # Steam appdetails with l=english returns an English month, independent of OS locale.
    months={name:index for index,name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1)}
    match=re.fullmatch(r'(\d{1,2}) ([A-Za-z]{3}),? (\d{4})',text)
    if not match:
        alternate=re.fullmatch(r'([A-Za-z]{3}) (\d{1,2}),? (\d{4})',text)
        if alternate:match=(None,alternate[2],alternate[1],alternate[3])
    if not match or match[2] not in months:return ''
    try:return datetime(int(match[3]),months[match[2]],int(match[1])).date().isoformat()
    except ValueError:return ''

def vndb_fields(row):
    return {'release_date':release_date(row.get('released')),'release_date_source':'VNDB（首次发行）',
            'metadata_url':'https://vndb.org/'+row['id'],'matched_name':row.get('title',''),
            'background_url':next((s.get('url') for s in row.get('screenshots',[]) if s.get('url')),''),'background_source':'VNDB 截图'}

def lookup(game):
    appid=str(game.get('steam_appid') or game.get('metadata_steam_appid') or '')
    result={}
    if re.fullmatch(r'\d{1,12}',appid):
        data={};last_error=None
        for region in ('cn','us'):
            try:
                data=fetch('https://store.steampowered.com/api/appdetails?'+urlencode({'appids':appid,'l':'english','cc':region})).get(appid,{})
                if data.get('success'):break
            except (OSError,ValueError) as error:last_error=error
        if not data and last_error:raise last_error
        if data.get('success') and data.get('data',{}).get('type','game')=='game':
            raw=data['data'];date=steam_date(raw.get('release_date'))
            tags=normalize_tags([row.get('description','') for row in raw.get('genres',[])],vocabulary([]))[:MAX_TAGS]
            result={'release_date':date,'release_date_source':'Steam','tags':tags,'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/'+appid+'/',
                    'matched_name':raw.get('name') or game['name'],'background_url':raw.get('background_raw') or raw.get('background') or raw.get('header_image',''),'background_source':'Steam'}
        if result.get('release_date'):return result
    # The fast pass uses VNDB for known visual novels, including unreleased Steam entries.
    tags=normalize_tags(game.get('source_tags') or game.get('tags',[]),vocabulary([]))
    if game.get('category')!='视觉小说' and '视觉小说' not in tags:return result
    try:
        data=fetch('https://api.vndb.org/kana/vn',{'filters':['search','=',game['name'][:150]],
            'fields':'title,alttitle,titles.title,titles.latin,aliases,released,screenshots.url','results':5,'sort':'searchrank'})
    except Exception:
        if result:return result
        raise
    row=best_match(data.get('results',[]),[game['name']],threshold=.96)
    if not row:return result
    fields=vndb_fields(row)
    if not fields.get('background_url'):
        fields.pop('background_url',None);fields.pop('background_source',None)
    return {**result,**fields}

def complete(store,idents=None):
    """Fill missing dates/tags, cache read-only requests, persist once after all workers."""
    from services import read_json,write_json
    from tag_catalog import effective_tags
    known={game['id']:game for game in store.games}
    if idents is not None and any(ident not in known for ident in idents):raise ValueError('游戏条目已不存在')
    targets=[dict(game) for game in store.games if (idents is None or game['id'] in idents) and
             (not release_date(game.get('release_date')) and not game.get('release_date_manual') or not effective_tags(game) and not game.get('tags_manual'))]
    cache=read_json(store.root/'metadata-cache.json',{});now=time.time()
    def query(game):
        key=json.dumps(['metadata-v2-region-timezone',local_utc_offset(),game['id'],game['name'],game.get('steam_appid'),game.get('metadata_steam_appid'),game.get('category'),effective_tags(game)],ensure_ascii=False)
        entry=cache.get(key)
        if entry and now-entry['time']<86400:return game['id'],key,entry['fields'],False
        try:return game['id'],key,lookup(game),False
        except Exception:return game['id'],key,{},True
    changed=0;failed=0;dated=0
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(query,targets))
    for ident,key,fields,error in responses:
        if error:failed+=1;continue
        cache[key]={'time':now,'fields':fields}
        game=known[ident];before=dict(game)
        if fields.get('release_date') and not release_date(game.get('release_date')) and not game.get('release_date_manual'):
            game.update(release_date=fields['release_date'],release_date_source=fields['release_date_source'],metadata_url=fields['metadata_url']);dated+=1
        if fields.get('tags') and not effective_tags(game) and not game.get('tags_manual'):
            game.update(tags=fields['tags'],source_tags=fields['tags'],tags_source=fields['tags_source'])
            from library_catalog import primary
            if not game.get('category_manual'):game['category']=primary(fields['tags'])
        if game!=before:changed+=1
    write_json(store.root/'metadata-cache.json',dict(list(cache.items())[-4000:]))
    if changed:write_json(store.root/'library.json',store.games)
    remaining=sum(not release_date(game.get('release_date')) for game in store.games if idents is None or game['id'] in idents)
    return {'changed':changed,'dated':dated,'unknown':remaining,'failed':failed}
