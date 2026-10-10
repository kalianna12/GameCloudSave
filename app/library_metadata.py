"""Best-effort source metadata. Dates never come from model guesses."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import json,re,time,unicodedata

from library_sources import release_date
from tag_catalog import normalize_tags,vocabulary,MAX_TAGS

def fetch(url,body=None):
    request=Request(url,data=json.dumps(body).encode() if body is not None else None,
                    headers={'User-Agent':'GameCloudSave/2.3','Accept':'application/json','Content-Type':'application/json'})
    with urlopen(request,timeout=8) as response:data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024:raise ValueError('资料响应过大')
    return json.loads(data)

def steam_date(value):
    if not isinstance(value,dict) or value.get('coming_soon'):return ''
    text=value.get('date','')
    parsed=release_date(text)
    if parsed:return parsed
    # Steam appdetails with l=english returns an English month, independent of OS locale.
    months={name:index for index,name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1)}
    match=re.fullmatch(r'(\d{1,2}) ([A-Za-z]{3}),? (\d{4})',text)
    if not match:
        alternate=re.fullmatch(r'([A-Za-z]{3}) (\d{1,2}),? (\d{4})',text)
        if alternate:match=(None,alternate[2],alternate[1],alternate[3])
    if not match or match[2] not in months:return ''
    try:return datetime(int(match[3]),months[match[2]],int(match[1])).date().isoformat()
    except ValueError:return ''

def title_key(value):return re.sub(r'[\W_]','',unicodedata.normalize('NFKC',value).casefold())

def lookup(game):
    appid=str(game.get('steam_appid') or game.get('metadata_steam_appid') or '')
    result={}
    if re.fullmatch(r'\d{1,12}',appid):
        data=fetch('https://store.steampowered.com/api/appdetails?'+urlencode({'appids':appid,'l':'english'})).get(appid,{})
        if data.get('success') and data.get('data',{}).get('type','game')=='game':
            raw=data['data'];date=steam_date(raw.get('release_date'))
            tags=normalize_tags([row.get('description','') for row in raw.get('genres',[])],vocabulary([]))[:MAX_TAGS]
            result={'release_date':date,'release_date_source':'Steam','tags':tags,'tags_source':'Steam','metadata_url':'https://store.steampowered.com/app/'+appid+'/'}
        return result
    # Unknown platform games use visual-novel matching only when the library supplies a VN cue.
    tags=normalize_tags(game.get('source_tags') or game.get('tags',[]),vocabulary([]))
    if game.get('category')!='视觉小说' and '视觉小说' not in tags:return {}
    data=fetch('https://api.vndb.org/kana/vn',{'filters':['search','=',game['name'][:150]],
        'fields':'title,alttitle,titles.title,titles.latin,aliases,released','results':5,'sort':'searchrank'})
    scored=[];name=title_key(game['name'])
    for row in data.get('results',[]):
        titles=[row.get('title'),row.get('alttitle'),*row.get('aliases',[])]
        for item in row.get('titles',[]):titles.extend([item.get('title'),item.get('latin')])
        score=max((SequenceMatcher(None,name,title_key(title)).ratio() for title in titles if isinstance(title,str) and title),default=0)
        scored.append((score,row))
    scored.sort(key=lambda pair:-pair[0])
    if not scored or scored[0][0]<.96 or len(scored)>1 and scored[0][0]-scored[1][0]<.08:return {}
    row=scored[0][1];date=release_date(row.get('released'))
    return {'release_date':date,'release_date_source':'VNDB（首次发行）','metadata_url':'https://vndb.org/'+row['id']}

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
        key=json.dumps(['metadata-v1',game['id'],game['name'],game.get('steam_appid'),game.get('metadata_steam_appid'),game.get('category'),effective_tags(game)],ensure_ascii=False)
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
