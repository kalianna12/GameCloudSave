"""Small streaming WebDAV/GitHub transports behind the existing cloud operations."""
from pathlib import Path
import base64,hashlib,json,posixpath,re,shutil,tempfile
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlsplit,unquote,urljoin
import xml.etree.ElementTree as ET
from cloud_paths import folder_path

class SameOrigin(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl)[:2]!=urlsplit(req.full_url)[:2]:raise ValueError('云端重定向到了其他服务器')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class FileJSON:
    """Stream base64 JSON rather than keeping several copies of a snapshot in RAM."""
    def __init__(self,metadata,source):
        self.source=Path(source) if source else None
        self.prefix=(json.dumps(metadata)[:-1]+',"content":"').encode()
        size=self.source.stat().st_size if self.source else 0
        self.length=len(self.prefix)+4*((size+2)//3)+2
    def __iter__(self):
        yield self.prefix
        if self.source:
            with self.source.open('rb') as stream:
                while chunk:=stream.read(3*256*1024):yield base64.b64encode(chunk)
        yield b'"}'

class WebDAV:
    def __init__(self,settings,secret):
        self.base=settings.get('dav_url','').strip().rstrip('/')+'/'
        parsed=urlsplit(self.base)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:raise ValueError('请填写有效的 WebDAV 地址')
        if not secret:raise ValueError('请填写 WebDAV 密码')
        self.timeout=max(10,min(120,int(settings.get('cloud_timeout',20))))
        self.headers={'Authorization':'Basic '+base64.b64encode((settings.get('dav_user','')+':'+secret).encode()).decode()}
        self.opener=build_opener(SameOrigin())
    def request(self,method,path='',data=None,headers=None):
        url=self.base+quote(folder_path(path),safe='/')
        if method in ('PROPFIND','MKCOL') and not url.endswith('/'):url+='/'
        try:return self.opener.open(Request(url,data=data,method=method,headers={**self.headers,**(headers or {}),'User-Agent':'GameCloudSave/2.7'}),timeout=self.timeout)
        except HTTPError as e:
            if e.code in (404,405,409,412):raise
            raise ValueError({401:'云端登录失败',403:'云端没有读写权限',429:'云端请求频率受限'}.get(e.code,'云端请求失败：HTTP '+str(e.code))) from None
        except (URLError,TimeoutError):raise ValueError('云端连接失败或超时') from None
    def list(self,path):
        body=b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:getcontentlength/><d:getlastmodified/></d:prop></d:propfind>'
        with self.request('PROPFIND',path,body,{'Depth':'1','Content-Type':'application/xml'}) as r:
            raw=r.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise ValueError('目录结果过大，请进入子目录')
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('云端目录格式无效')
        root=ET.fromstring(raw);rows=[]
        parent=unquote(urlsplit(self.base+quote(folder_path(path),safe='/')).path).rstrip('/')
        for response in root.findall('{DAV:}response'):
            href=response.findtext('{DAV:}href','');location=unquote(urlsplit(urljoin(self.base,href)).path).rstrip('/')
            if location==parent or posixpath.dirname(location)!=parent:continue
            props=next((p.find('{DAV:}prop') for p in response.findall('{DAV:}propstat') if ' 200 ' in p.findtext('{DAV:}status','')),None)
            if props is None:continue
            name=posixpath.basename(location)
            if not name or name in ('.','..'):continue
            rows.append(dict(Name=name,Path=name,IsDir=props.find('{DAV:}resourcetype/{DAV:}collection') is not None,
                             Size=int(props.findtext('{DAV:}getcontentlength','0') or 0),ModTime=props.findtext('{DAV:}getlastmodified','')))
        return rows
    def mkdir(self,path):
        current=''
        for part in folder_path(path).split('/'):
            if not part:continue
            current=posixpath.join(current,part)
            try:
                with self.request('MKCOL',current):pass
            except HTTPError as e:
                if e.code!=405:raise
    def get(self,path,destination=None,head=None):
        with self.request('GET',path) as r:
            if destination:
                with Path(destination).open('wb') as f:shutil.copyfileobj(r,f,1024*1024)
                return
            return r.read(head or 1024*1024)
    def put(self,path,source,immutable=False):
        self.mkdir(posixpath.dirname(path));source=Path(source)
        try:
            with source.open('rb') as stream,self.request('PUT',path,stream,{'Content-Length':str(source.stat().st_size),**({'If-None-Match':'*'} if immutable else {})}):pass
        except HTTPError as e:
            if e.code!=412 or not immutable:raise
            with tempfile.TemporaryDirectory() as temp:
                other=Path(temp)/'check';self.get(path,other)
                if digest(other)!=digest(source):raise ValueError('同名云端备份已存在，内容不同，未覆盖')
    def delete(self,path):
        with self.request('DELETE',path):pass

class GitHub:
    LIMIT=90*1024*1024
    def __init__(self,settings,secret):
        self.repo=settings.get('github_repo','').strip().removeprefix('https://github.com/').removesuffix('.git').strip('/')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',self.repo):raise ValueError('GitHub 仓库格式：用户名/仓库名')
        if not secret:raise ValueError('请填写仓库的 GitHub Token')
        self.branch=settings.get('github_branch','').strip()
        self.timeout=max(10,min(120,int(settings.get('cloud_timeout',20))))
        self.headers={'Authorization':'Bearer '+secret,'User-Agent':'GameCloudSave/2.7','X-GitHub-Api-Version':'2022-11-28'}
        self.opener=build_opener(SameOrigin())
    def request(self,method,path='',data=None,raw=False):
        url='https://api.github.com/repos/'+self.repo+'/'+path
        body=data if isinstance(data,FileJSON) else json.dumps(data).encode() if data is not None else None
        extra={'Content-Length':str(data.length)} if isinstance(data,FileJSON) else {}
        try:return self.opener.open(Request(url,body,method=method,headers={**self.headers,**extra,'Accept':'application/vnd.github.raw+json' if raw else 'application/vnd.github+json','Content-Type':'application/json'}),timeout=self.timeout)
        except HTTPError as e:
            if e.code==404:raise
            raise ValueError({401:'GitHub Token 无效',403:'GitHub 权限不足或请求受限',409:'仓库或分支冲突，请刷新后重试',422:'GitHub 拒绝写入，请检查分支和文件大小'}.get(e.code,'GitHub 请求失败：HTTP '+str(e.code))) from None
        except (URLError,TimeoutError):raise ValueError('GitHub 连接失败或超时') from None
    def json(self,method,path='',data=None):
        with self.request(method,path,data) as r:return json.load(r)
    def ref(self):return ('?ref='+quote(self.branch,safe='')) if self.branch else ''
    def content(self,path):return 'contents/'+quote(folder_path(path),safe='/')
    def metadata(self,path):
        path=folder_path(path);parent,name=posixpath.split(path)
        try:rows=self.json('GET',self.content(parent)+self.ref())
        except HTTPError as e:
            if e.code==404:return None
            raise
        if not isinstance(rows,list):raise ValueError('GitHub 目标目录无效')
        if len(rows)>=1000:raise ValueError('GitHub 目录文件过多，请分目录保存')
        return next((row for row in rows if row.get('name')==name),None)
    def list(self,path):
        try:rows=self.json('GET',self.content(path)+self.ref())
        except HTTPError as e:
            if e.code==404 and not path:return []
            raise
        if not isinstance(rows,list):raise ValueError('请选择 GitHub 仓库中的目录')
        return [dict(Name=r['name'],Path=r['name'],IsDir=r['type']=='dir',Size=r.get('size',0),ModTime='') for r in rows if r['name']!='.gitkeep' and r['type'] in ('file','dir')]
    def mkdir(self,path):
        if path:self.put(folder_path(path)+'/.gitkeep',None,True)
    def get(self,path,destination=None,head=None):
        with self.request('GET',self.content(path)+self.ref(),raw=True) as r:
            if destination:
                with Path(destination).open('wb') as f:shutil.copyfileobj(r,f,1024*1024)
                return
            return r.read(head or 1024*1024)
    def put(self,path,source,immutable=False):
        if source and Path(source).stat().st_size>self.LIMIT:raise ValueError('GitHub 单份备份限 90 MiB；更大存档请选择 WebDAV')
        previous=self.metadata(path)
        if previous and immutable:
            size=Path(source).stat().st_size if source else 0
            hasher=hashlib.sha1(b'blob '+str(size).encode()+b'\0')
            if source:
                with Path(source).open('rb') as stream:
                    while chunk:=stream.read(1024*1024):hasher.update(chunk)
            expected=hasher.hexdigest()
            if previous.get('sha')!=expected:raise ValueError('同名 GitHub 备份已存在，内容不同，未覆盖')
            return
        data={'message':'GameCloudSave backup'}
        if self.branch:data['branch']=self.branch
        if previous:data['sha']=previous['sha']
        self.json('PUT',self.content(path),FileJSON(data,source))
    def delete(self,path):
        previous=self.metadata(path)
        if not previous:return
        data={'message':'GameCloudSave remove verification file','sha':previous['sha']}
        if self.branch:data['branch']=self.branch
        self.json('DELETE',self.content(path),data)

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(store,command,folder='',values=None):
    settings={**store.settings,**(values or {})};github=settings.get('cloud_provider','webdav')=='github'
    secret=settings.get('github_token','') or store.github_token() if github else settings.get('password','') or store.password()
    client=(GitHub if github else WebDAV)(settings,secret)
    def remote(value):
        if not str(value).startswith('gamecloud:'):raise ValueError('云端路径无效')
        return folder_path(str(value)[10:])
    def listing(path,recursive=False,max_depth=4):
        rows=client.list(path);result=[]
        for row in rows:
            result.append(row)
            if recursive and row['IsDir'] and max_depth>1:
                for sub in listing(posixpath.join(path,row['Name']),True,max_depth-1):result.append({**sub,'Path':row['Name']+'/'+sub.get('Path',sub['Name'])})
        return result
    try:
        if command=='list':return sorted(listing(folder_path(folder)),key=lambda r:(not r['IsDir'],r['Name'].casefold()))
        op,*args=command
        if op=='lsjson':
            rows=listing(remote(args[0]),'--recursive' in args,int(args[args.index('--max-depth')+1]) if '--max-depth' in args else 4)
            if '--files-only' in args:rows=[r for r in rows if not r['IsDir']]
            return json.dumps(rows)
        if op=='mkdir':client.mkdir(remote(args[0]));return ''
        if op=='deletefile':client.delete(remote(args[0]));return ''
        if op=='cat':return client.get(remote(args[0]),head=int(args[args.index('--head')+1]) if '--head' in args else 1024*1024).decode('utf-8-sig')
        if op=='copyto':
            source,destination=args[:2]
            if source.startswith('gamecloud:'):
                dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as f:temporary=Path(f.name)
                try:client.get(remote(source),temporary);temporary.replace(dest)
                finally:temporary.unlink(missing_ok=True)
            else:client.put(remote(destination),source,'--immutable' in args)
            return ''
        if op=='copy' and '--files-from-raw' in args:
            base=remote(args[0]);destination=Path(args[1]);names=Path(args[args.index('--files-from-raw')+1]).read_text(encoding='utf-8').splitlines()
            for name in names:
                name=folder_path(name);dest=destination/name
                if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('下载路径无效')
                dest.parent.mkdir(parents=True,exist_ok=True);client.get(posixpath.join(base,name),dest)
            return ''
        raise ValueError('云端操作暂不支持：'+str(op))
    except HTTPError as e:
        raise ValueError('云端目录或文件暂不可用' if e.code==404 else '云端请求失败：HTTP '+str(e.code)) from None
