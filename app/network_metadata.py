"""Best-effort title/developer lookup on Steam's own store service."""
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from difflib import SequenceMatcher
import json,re,threading

_limit=threading.Semaphore(2)
def normalize(value):return re.sub(r'[^\w]','',value.casefold())
def get(url):
    request=Request(url,headers={'User-Agent':'GameCloudSave/1.6','Accept':'application/json'})
    with urlopen(request,timeout=8) as response:
        data=response.read(1024*1024+1)
    if len(data)>1024*1024:raise ValueError('网络资料响应过大')
    return json.loads(data)

def lookup(title,installation='',appid='',cancel=None):
    if cancel and cancel.is_set():return {}
    with _limit:
        if not str(appid).isdigit():
            query=title
            data=get('https://store.steampowered.com/api/storesearch/?'+urlencode({'term':query,'l':'schinese','cc':'us'}))
            items=data.get('items',[])
            keys=[normalize(title),normalize(installation)]
            scored=sorted(((max(SequenceMatcher(None,normalize(str(item.get('name',''))),key).ratio() for key in keys if key),item) for item in items if isinstance(item,dict)),key=lambda pair:-pair[0])
            if not scored or scored[0][0]<.86 or len(scored)>1 and scored[0][0]-scored[1][0]<.08:return {}
            appid=str(scored[0][1]['id'])
        if cancel and cancel.is_set():return {}
        if not re.fullmatch(r'\d{1,12}',str(appid)):return {}
        data=get('https://store.steampowered.com/api/appdetails?'+urlencode({'appids':appid,'l':'english'})).get(str(appid),{})
        if not data.get('success'):return {}
        game=data.get('data',{})
        if game.get('type','game')!='game':return {}
        def names(field):return [s[:150] for s in game.get(field,[])[:10] if isinstance(s,str)]
        return {'english_name':str(game.get('name',''))[:150],'aliases':[title],'developers':names('developers'),
                'publishers':names('publishers'),'hints':[],'note':'','steam_appid':str(appid),
                'sources':[{'title':'Steam 游戏资料','url':'https://store.steampowered.com/app/'+str(appid)+'/'}]}
