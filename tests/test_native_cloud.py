from pathlib import Path
import base64,hashlib,json,sys,tempfile,threading,unittest
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,unquote,quote
from urllib.request import Request,build_opener
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store
import cloud_transport as cloud

class Server(BaseHTTPRequestHandler):
    files={};folders=set();auth=[]
    def log_message(self,*args):pass
    def reply(self,code,body=b'',kind='application/json'):
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def name(self):return unquote(urlsplit(self.path).path).removeprefix('/dav/').rstrip('/')
    def payload(self):return self.rfile.read(int(self.headers.get('Content-Length',0)))
    def do_MKCOL(self):self.folders.add(self.name());self.reply(201)
    def do_PROPFIND(self):
        self.payload();base=self.name();prefix=base+'/' if base else '';names=set()
        for name in list(self.files)+list(self.folders):
            if name.startswith(prefix) and name!=base:names.add(name[len(prefix):].split('/')[0])
        import xml.sax.saxutils as xml
        body='<d:multistatus xmlns:d="DAV:">'
        for name in sorted(names):
            full=prefix+name;is_dir=full in self.folders or any(k.startswith(full+'/') for k in self.files)
            body+='<d:response><d:href>/dav/'+quote(full,safe='/')+'</d:href><d:propstat><d:prop><d:resourcetype>'+('<d:collection/>' if is_dir else '')+'</d:resourcetype><d:getcontentlength>'+str(len(self.files.get(full,b'')))+'</d:getcontentlength></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'
        self.reply(207,(body+'</d:multistatus>').encode(), 'application/xml')
    def do_GET(self):
        self.auth.append(self.headers.get('Authorization'))
        if self.path.startswith('/repos/'):
            name=unquote(urlsplit(self.path).path.split('/contents/',1)[-1])
            if name in self.files:
                data=self.files[name]
                if 'raw' in self.headers.get('Accept',''):return self.reply(200,data,'application/octet-stream')
                return self.reply(200,json.dumps({'sha':self.sha(data),'size':len(data),'type':'file'}).encode())
            prefix=name+'/' if name else '';children={}
            for path,data in self.files.items():
                if path.startswith(prefix):
                    leaf=path[len(prefix):].split('/')[0];children[leaf]={'name':leaf,'type':'dir' if '/' in path[len(prefix):] else 'file','size':len(data),'sha':self.sha(data)}
            return self.reply(200,json.dumps(list(children.values())).encode()) if children else self.reply(404)
        name=self.name()
        self.reply(200,self.files[name],'application/octet-stream') if name in self.files else self.reply(404)
    @staticmethod
    def sha(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    def do_PUT(self):
        if self.path.startswith('/repos/'):
            data=json.loads(self.payload());name=unquote(urlsplit(self.path).path.split('/contents/',1)[-1]);old=self.files.get(name)
            if old is not None and data.get('sha')!=self.sha(old):return self.reply(409)
            self.files[name]=base64.b64decode(data['content']);return self.reply(201,b'{}')
        name=self.name();data=self.payload()
        if self.headers.get('If-None-Match')=='*' and name in self.files:return self.reply(412)
        self.files[name]=data;self.reply(201)
    def do_DELETE(self):
        name=unquote(urlsplit(self.path).path.split('/contents/',1)[-1]) if self.path.startswith('/repos/') else self.name()
        if self.path.startswith('/repos/'):self.payload()
        self.files.pop(name,None);self.reply(200,b'{}')

class NativeCloud(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'data','isolated')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Server);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        Server.files={};Server.folders=set();Server.auth=[]
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.store.settings.update(dav_url=self.base+'/dav/',dav_user='fixture')
        self.store.password=lambda:'fixture-secret';self.store.github_token=lambda:'fixture-token'
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def roundtrip(self):
        file=self.root/'save.zip';file.write_bytes(b'fixture-archive-contents')
        self.store.rclone(['mkdir','gamecloud:备份'])
        self.store.rclone(['copyto',str(file),'gamecloud:备份/测试.zip','--immutable'])
        self.assertTrue(any(r['Name']=='测试.zip' for r in self.store.rclone('list','备份')))
        output=self.root/'download.zip';self.store.rclone(['copyto','gamecloud:备份/测试.zip',str(output)])
        self.assertEqual(output.read_bytes(),file.read_bytes())
        self.store.rclone(['copyto',str(file),'gamecloud:备份/测试.zip','--immutable'])
        file.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.store.rclone(['copyto',str(file),'gamecloud:备份/测试.zip','--immutable'])
        self.assertEqual(self.store.rclone(['cat','gamecloud:备份/测试.zip','--head','7']),'fixture')
        rows=json.loads(self.store.rclone(['lsjson','gamecloud:备份','--recursive','--files-only']))
        self.assertEqual(rows[0]['Path'],'测试.zip')
        self.store.rclone(['deletefile','gamecloud:备份/测试.zip'])
    def test_webdav_streaming_immutable_unicode_and_list(self):self.roundtrip()
    def test_github_contents_same_archive_operations(self):
        self.store.settings.update(cloud_provider='github',github_repo='fixture/saves',github_branch='saves')
        real=build_opener()
        base=self.base
        class Local:
            def open(self,req,timeout):
                parsed=urlsplit(req.full_url)
                target=Request(base+parsed.path+('?' + parsed.query if parsed.query else ''),req.data,headers=dict(req.headers),method=req.method)
                return real.open(target,timeout=timeout)
        with patch('cloud_transport.build_opener',return_value=Local()):self.roundtrip()
        self.assertTrue(all(x=='Bearer fixture-token' for x in Server.auth))
    def test_token_encrypted_and_not_settings_json(self):
        self.store.save_settings({'cloud_provider':'github','github_repo':'fixture/saves','github_token':'fixture-token'})
        self.assertNotIn('fixture-token',(self.store.profile/'settings.json').read_text())
        self.assertNotIn(b'fixture-token',(self.store.profile/'github-token.dpapi').read_bytes())
    def test_paths_rejected_before_network(self):
        for path in ('../bad','a/../../bad'):
            with self.assertRaises(ValueError):self.store.rclone('list',path)
    def test_github_size_limit_before_read(self):
        file=self.root/'large';file.touch()
        with patch.object(cloud.GitHub,'LIMIT',3),file.open('wb') as stream:stream.write(b'1234')
        client=cloud.GitHub({'github_repo':'fixture/saves'},'fixture')
        with patch.object(client,'LIMIT',3),self.assertRaises(ValueError):client.put('save',file)

if __name__=='__main__':unittest.main()
