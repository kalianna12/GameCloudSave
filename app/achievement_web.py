"""Public schema pages. Exact API names win; title-only sources stay explicit."""
from html.parser import HTMLParser
import json,re
from urllib.request import Request,urlopen
from achievement_files import LIMIT,normalize_schema


class Node:
    def __init__(self,tag='',attrs=(),parent=None):self.tag=tag;self.attrs=dict(attrs);self.children=[];self.parent=parent
    def all(self,tag=None):
        for child in self.children:
            if isinstance(child,Node):
                if tag is None or child.tag==tag:yield child
                yield from child.all(tag)
    def text(self):return ' '.join(c.text() if isinstance(c,Node) else c for c in self.children).strip()


class Document(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.root=Node();self.current=self.root;self.nodes=0;self.feed(text)
    def handle_starttag(self,tag,attrs):
        self.nodes+=1
        if self.nodes>80000:raise ValueError('成就页面过大')
        node=Node(tag,attrs,self.current);self.current.children.append(node)
        if tag not in ('img','br','hr','input','meta','link','source','area','wbr'):self.current=node
    def handle_endtag(self,tag):
        node=self.current
        while node.parent:
            if node.tag==tag:self.current=node.parent;return
            node=node.parent
    def handle_data(self,text):self.current.children.append(text)


def fetch_page(url):
    with urlopen(Request(url,headers={'User-Agent':'GameCloudSave/2.5 (achievement metadata)'}),timeout=10) as response:data=response.read(LIMIT+1)
    if len(data)>LIMIT:raise ValueError('成就页面超过读取上限')
    return data.decode('utf-8',errors='replace')


def community_schema(appid):
    if not re.fullmatch(r'[1-9]\d{0,11}',str(appid)):raise ValueError('App ID 无效')
    document=Document(fetch_page(f'https://steamcommunity.com/stats/{appid}/achievements/?l=schinese'))
    for script in document.root.all('script'):
        if script.attrs.get('id')!='valve-ssr-data':continue
        stack=[json.loads(script.text())];visited=0
        while stack and visited<30000:
            value=stack.pop();visited+=1
            if isinstance(value,str) and value.lstrip().startswith(('{','[')):
                try:stack.append(json.loads(value))
                except ValueError:pass
            elif isinstance(value,list):stack.extend(value)
            elif isinstance(value,dict):
                key=value.get('queryKey',[])
                if key==['achievements',int(appid),'schema']:
                    payload=value.get('state',{}).get('data',{});groups=payload.get('groups',[])
                    entries=payload.get('achievements',[])
                    for group in groups:entries.extend(group.get('achievements',[]))
                    rows=[dict(r,internal_name=r.get('api_name'),localized_name=r.get('name'),icon=r.get('icon_achieved','')) for r in entries if r.get('api_name')]
                    result=normalize_schema(rows,appid=str(appid))
                    if result:return result
                stack.extend(value.values())
    raise ValueError('Steam Community 未返回带内部 ID 的成就定义')


def completionist_schema(appid,existing=()):
    if not re.fullmatch(r'[1-9]\d{0,11}',str(appid)):raise ValueError('App ID 无效')
    document=Document(fetch_page(f'https://completionist.me/steam/app/{appid}/achievements'))
    result=[];seen=set()
    for row in document.root.all('tr'):
        cells=[c for c in row.children if isinstance(c,Node) and c.tag=='td']
        if len(cells)<5:continue
        image=next(row.all('img'),None)
        if not image:continue
        # Only Steam CDN icons are accepted by the downstream asset cache.
        icon=image.attrs.get('src','')
        title_node=next((n for n in cells[1].all() if n.tag in ('a','strong','h3','h4')),None)
        if not title_node:continue
        title=title_node.text().strip();text=cells[1].text();description=text[len(title):].strip() if text.startswith(title) else ''
        if not title or title.casefold() in seen:continue
        seen.add(title.casefold());match=[r for r in existing if r.get('name','').casefold()==title.casefold() or icon and r.get('icon','').rsplit('/',1)[-1]==icon.rsplit('/',1)[-1]]
        api_name=match[0]['id'] if len(match)==1 else 'title:'+title
        percent=re.search(r'(\d+(?:\.\d+)?)\s*%',cells[3].text())
        result.append(dict(id=api_name,name=title,description=description[:2000],icon=icon,hidden='hidden' in cells[2].text().casefold(),max=0,rarity=float(percent[1]) if percent else 0,rarity_known=bool(percent),match_mode='api' if len(match)==1 else 'title'))
    if not result:raise ValueError('Completionist.me 未返回可识别的成就列表')
    return result[:5000]
