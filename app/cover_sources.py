"""Catalog search and bounded artwork downloads; public web-search entry points."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode,urlparse
from urllib.request import Request,urlopen
from library_sources import key
from catalog_match import titles,score

HOSTS={'shared.fastly.steamstatic.com','cdn.akamai.steamstatic.com','cdn.cloudflare.steamstatic.com','s.vndb.org','t.vndb.org'}
PROVIDERS=[{'id':'steam','label':'Steam Store','kind':'api'},{'id':'vndb','label':'VNDB','kind':'api'},
 {'id':'google','label':'Google 图片','kind':'scrape','url':'https://www.google.com/search?tbm=isch&q={query}'},
 {'id':'bing','label':'Bing 图片','kind':'scrape','url':'https://www.bing.com/images/search?q={query}'},
 {'id':'ign','label':'IGN','kind':'scrape','url':'https://www.ign.com/search?q={query}'},
 {'id':'steamgriddb','label':'SteamGridDB','kind':'scrape','url':'https://www.steamgriddb.com/search/grids?term={query}'},
 {'id':'gog','label':'GOG 商店','kind':'scrape','url':'https://www.gog.com/en/games?query={query}'},
 {'id':'epic','label':'Epic 商店','kind':'scrape','url':'https://store.epicgames.com/en-US/browse?q={query}'},
 {'id':'custom','label':'自定义 JSON 来源','kind':'api'}]
def fetch_json(url,data=None,headers=None):
    request=Request(url,data=data,headers={'User-Agent':'GameCloudSave/2.2',**(headers or {})})
    try:
        with urlopen(request,timeout=18) as response:
            payload=response.read(4*1024*1024+1)
            if len(payload)>4*1024*1024:raise ValueError('封面搜索响应过大')
            return json.loads(payload)
    except ValueError:raise
    except Exception:raise ValueError('封面来源暂不可用，请重试或更换来源') from None
def search(store,query,provider='steam',use_ai=False,cancel=None):
    query=query.strip()[:160]
    if not query:raise ValueError('请输入游戏名称')
    original=query
    if cancel and cancel.is_set():return []
    if use_ai:
        token=store.profile/'ai-key.dpapi'
        if token.is_file():
            from services import protect
            from ai_match import identify_game
            identified=identify_game(query,'',protect(token.read_bytes(),True).decode(),store.settings['ai_model'],cancel=cancel)
            query=identified.get('english_name') or query
    from services import read_json,write_json,protect
    cache=read_json(store.profile/'cover-search.json',{})
    cache_key='titles-v3-artwork:'+provider+':'+key(query)
    if cancel and cancel.is_set():return []
    if provider=='custom':cache_key+=':'+hashlib.sha256(store.settings.get('custom_cover_url','').encode()).hexdigest()[:16]
    cached=cache.get(cache_key)
    if cached and time.time()-cached['time']<86400:return cached['rows']
    rows=[]
    if provider=='steam':
        data=fetch_json('https://store.steampowered.com/search/results/?'+urlencode({'term':query,'json':1,'count':20,'start':0,'l':'schinese'}))
        for item in data.get('items',[]):
            match=re.search(r'/apps/(\d+)/',item.get('logo',''))
            if not match:continue
            appid=match.group(1);name=item.get('name','')
            if any(word in name.casefold() for word in ('soundtrack','song pack')) or re.search(r'\b(?:ost|dlc)\b',name,re.I):continue
            rows.append({'id':'steam:'+appid,'name':name,'provider':'steam','appid':appid,
                         'image':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/'+appid+'/library_600x900.jpg',
                         'fallback':item['logo'],'page':'https://store.steampowered.com/app/'+appid+'/'})
        if not data.get('items') and data.get('results_html'):
            from html.parser import HTMLParser
            class Parser(HTMLParser):
                def __init__(self):super().__init__();self.row=None;self.title=False;self.results=[]
                def handle_starttag(self,tag,attrs):
                    values=dict(attrs)
                    if tag=='a' and values.get('data-ds-appid','').isdigit():self.row={'appid':values['data-ds-appid'],'name':''}
                    if tag=='span' and values.get('class')=='title':self.title=True
                def handle_data(self,value):
                    if self.title and self.row:self.row['name']+=value
                def handle_endtag(self,tag):
                    if tag=='span':self.title=False
                    if tag=='a' and self.row:self.results.append(self.row);self.row=None
            parser=Parser();parser.feed(data['results_html'])
            for item in parser.results:
                appid=item['appid'];rows.append({'id':'steam:'+appid,'name':item['name'],'provider':'steam','appid':appid,'image':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/'+appid+'/library_600x900.jpg','fallback':'','page':'https://store.steampowered.com/app/'+appid+'/'})
    elif provider=='vndb':
        data=fetch_json('https://api.vndb.org/kana/vn',json.dumps({'filters':['search','=',query],'fields':'title,alttitle,titles.title,titles.latin,aliases,released,image.url,image.thumbnail,screenshots.url','results':20,'sort':'searchrank'}).encode(),{'Content-Type':'application/json'})
        for item in data.get('results',[]):
            image=item.get('image') or {}
            rows.append({'id':'vndb:'+item['id'],'name':item['title'],'aliases':titles(item),'released':item.get('released',''),
                         'provider':'vndb','image':image.get('url',''),'fallback':image.get('thumbnail',''),'page':'https://vndb.org/'+item['id'],
                         'background_url':next((s.get('url') for s in item.get('screenshots',[]) if s.get('url')),'')})
    elif provider=='custom':
        from urllib.parse import quote
        endpoint=store.settings.get('custom_cover_url','')
        if '{query}' not in endpoint or urlparse(endpoint).scheme not in ('http','https'):raise ValueError('请配置包含 {query} 的自定义 JSON 搜索地址')
        data=fetch_json(endpoint.replace('{query}',quote(query)))
        for index,item in enumerate(data.get('items',[])[:30]):
            if not isinstance(item,dict) or not isinstance(item.get('name'),str) or urlparse(item.get('image','')).scheme not in ('http','https'):continue
            rows.append({'id':'custom:'+str(item.get('id',index)),'name':item['name'],'provider':'custom','image':item['image'],'fallback':'','page':item.get('page',''),'user_authorized':True})
    elif any(source['id']==provider and source['kind']=='scrape' for source in PROVIDERS):
        from image_search import search as scrape
        rows=scrape(store,query,provider,'cover',cancel)
    else:raise ValueError('未知封面来源')
    for row in rows:
        row['score']=round(score([query,original],row),3)
    rows=sorted({row['id']:row for row in rows}.values(),key=lambda row:-row['score'])[:20]
    with store.match_lock:
        cache=read_json(store.profile/'cover-search.json',{})
        cache[cache_key]={'time':time.time(),'rows':rows};write_json(store.profile/'cover-search.json',dict(list(cache.items())[-200:]))
    return rows
def download(store,record):
    directory=store.root/'covers';directory.mkdir(exist_ok=True)
    target=directory/('catalog-'+hashlib.sha256(record['id'].encode()).hexdigest()[:20]+'.jpg')
    if target.is_file():return str(target)
    for url in (record['image'],record.get('fallback','')):
        if not url:continue
        if urlparse(url).scheme not in ('http','https') or not record.get('user_authorized') and urlparse(url).hostname not in HOSTS:raise ValueError('封面地址不受支持')
        try:
            with urlopen(Request(url,headers={'User-Agent':'GameCloudSave/2.2'}),timeout=18) as response:
                if urlparse(response.geturl()).scheme not in ('http','https') or not record.get('user_authorized') and urlparse(response.geturl()).hostname not in HOSTS:raise ValueError('封面跳转地址不受支持')
                content=response.read(12*1024*1024+1)
            if len(content)>12*1024*1024:raise ValueError('封面文件过大')
            temporary=target.with_suffix('.tmp');temporary.write_bytes(content)
            from PySide6.QtGui import QImageReader
            reader=QImageReader(str(temporary));size=reader.size()
            del reader
            if not size.isValid() or size.width()>8192 or size.height()>8192:temporary.unlink(missing_ok=True);continue
            temporary.replace(target);return str(target)
        except ValueError:raise
        except Exception:continue
    raise ValueError('该游戏封面暂不可下载，请选择其他结果或本地图片')
