"""Bounded background image scraping; every source returns the same candidate grid."""
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlencode,urljoin,urlsplit,parse_qs,quote
from urllib.request import Request,urlopen
from pathlib import Path
import json,re,os,time,tempfile,subprocess

AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
LIMIT=5*1024*1024

def parse(html,base):
    records=[]
    def add(image,name='',page='',thumbnail='',width=0,height=0):
        if not image or len(records)>=200:return
        try:
            image=urljoin(base,unescape(str(image)))
            parsed=urlsplit(image)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:return
        except ValueError:return
        if re.search(r'(?:logo|favicon|sprite|avatar|placeholder)',urlsplit(image).path,re.I):return
        try:width=int(width or 0);height=int(height or 0)
        except (ValueError,TypeError):width=height=0
        if width and height and (width<140 or height<140):return
        if any(row['image']==image for row in records):return
        def joined(value):
            try:return urljoin(base,str(value))
            except ValueError:return ''
        records.append(dict(image=image,name=unescape(str(name))[:200],page=joined(page),thumbnail=joined(thumbnail) if thumbnail else image,width=width,height=height))
    class Page(HTMLParser):
        link=''
        def handle_starttag(self,tag,attrs):
            props=dict(attrs)
            if tag=='a':
                self.link=props.get('href','')
                try:query=parse_qs(urlsplit(self.link).query)
                except ValueError:query={};self.link=''
                if query.get('imgurl'):add(query['imgurl'][0],props.get('title',''),query.get('imgrefurl',[''])[0],width=query.get('w',[0])[0],height=query.get('h',[0])[0])
                if props.get('m'):
                    try:
                        meta=json.loads(props['m']);add(meta.get('murl',''),meta.get('t','') or meta.get('desc',''),meta.get('purl',''),meta.get('turl',''),meta.get('w',0),meta.get('h',0))
                    except (ValueError,TypeError):pass
            if tag=='img':
                source=props.get('data-original') or props.get('data-src') or props.get('src','')
                if not source or source.startswith('data:') or source.split('?',1)[0].lower().endswith('.svg'):return
                if self.link and parse_qs(urlsplit(self.link).query).get('imgurl'):return
                add(source,props.get('alt',''),self.link,width=props.get('width',0),height=props.get('height',0))
        def handle_endtag(self,tag):
            if tag=='a':self.link=''
    pair=r'\["(https?[^"\r\n]+)",\s*(\d{2,5}),\s*(\d{2,5})\],\s*\["(https?[^"\r\n]+)",\s*(\d{2,5}),\s*(\d{2,5})\]'
    for match in re.finditer(pair,html):
        if 'gstatic.com' not in match[1]:continue
        try:add(json.loads('"'+match[4]+'"'),thumbnail=json.loads('"'+match[1]+'"'),width=match[6],height=match[5])
        except ValueError:pass
    # Original-image triples embedded in Google's rendered image result data.
    for match in re.finditer(r'\["(https?[^"\r\n]+)",\s*(\d{2,5}),\s*(\d{2,5})\]',html):
        try:image=json.loads('"'+match[1]+'"')
        except ValueError:continue
        if 'gstatic.com' not in image:add(image,width=match[3],height=match[2])
    for match in re.finditer(r'"(?:original|image_url|imageUrl|fullUrl|image|thumbnailUrl)"\s*:\s*"(https?[^"\r\n]+)"',html):
        try:add(json.loads('"'+match[1]+'"'))
        except ValueError:pass
    Page().feed(html)
    originals=[row for row in records if 'gstatic.com' not in urlsplit(row['image']).netloc]
    return (originals or records)[:80]

def fetch(url,cancel):
    if cancel and cancel.is_set():return ''
    request=Request(url,headers={'User-Agent':AGENT,'Accept-Language':'en-US,en;q=0.9','Accept':'text/html'})
    try:
        with urlopen(request,timeout=12) as response:raw=response.read(LIMIT+1)
    except OSError:raise ValueError('该图片来源暂时无法连接，请重试或更换来源') from None
    if len(raw)>LIMIT:raise ValueError('搜索页过大，请缩短关键词')
    return raw.decode('utf-8',errors='replace')

def rendered(url,profile,cancel):
    """Optional on-demand system Edge, hidden and disposable; never installed/bundled."""
    candidates=[Path(os.environ.get(key,''))/'Microsoft/Edge/Application/msedge.exe' for key in ('PROGRAMFILES(X86)','PROGRAMFILES','LOCALAPPDATA')]
    edge=next((p for p in candidates if p.is_file()),None)
    if edge is None:return ''
    import psutil
    parent=Path(profile)/'image-search';parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent,ignore_cleanup_errors=True) as temp:
        process=subprocess.Popen([str(edge),'--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking','--user-data-dir='+temp,'--dump-dom','--timeout=10000','--virtual-time-budget=3000',url],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        children={};deadline=time.monotonic()+15
        try:
            while time.monotonic()<deadline and not (cancel and cancel.is_set()):
                try:
                    data,_=process.communicate(timeout=.12)
                    return data[:LIMIT].decode('utf-8',errors='replace')
                except subprocess.TimeoutExpired:
                    try:
                        for child in psutil.Process(process.pid).children(recursive=True):children[child.pid]=(child,child.create_time())
                    except psutil.Error:pass
            return ''
        finally:
            for child,created in reversed(list(children.values())):
                try:
                    if child.create_time()==created:child.terminate()
                except psutil.Error:pass
            if process.poll() is None:process.terminate()
            try:process.communicate(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.communicate()

def search(store,query,provider,kind,cancel=None):
    from cover_sources import PROVIDERS
    from artwork_search import web_rows
    terms=query+(' game cover' if kind=='cover' else ' game wallpaper') if provider in ('google','bing') else query
    source=next((p for p in PROVIDERS if p['id']==provider and p.get('url')),None)
    if source is None:raise ValueError('图片来源不存在')
    url=source['url'].replace('{query}',quote(terms))
    if provider=='google':url='https://www.google.com/search?'+urlencode({'q':terms,'udm':'2'})
    elif provider=='bing':url='https://www.bing.com/images/async?'+urlencode({'q':terms,'first':1,'count':35,'mmasync':1})
    try:html=fetch(url,cancel)
    except ValueError:html=''
    rows=web_rows(parse(html,url),provider,kind)
    if len(rows)<4 and not (cancel and cancel.is_set()):
        html=rendered(url,store.profile,cancel);rendered_rows=web_rows(parse(html,url),provider,kind)
        if rendered_rows:rows=rendered_rows
    if cancel and cancel.is_set():return []
    if not rows:raise ValueError('该来源未返回可用图片，可能需要验证；请重试或换一个来源')
    for row in rows:
        if not row.get('name') or row['name']=='搜索图片':row['name']=query
    return rows
