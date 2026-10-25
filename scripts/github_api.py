from pathlib import Path
import os,subprocess,json,urllib.request,urllib.error,mimetypes,hashlib

def headers():
    r=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never'},timeout=25)
    fields=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or fields.get('password')
    if not token:raise RuntimeError('No GitHub credential available')
    return {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'GameCloudSave-Release','X-GitHub-Api-Version':'2022-11-28'}

def request(path,method='GET',body=None):
    url=path if path.startswith('https://') else 'https://api.github.com/'+path
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    q=urllib.request.Request(url,data=data,method=method,headers={**headers(),'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(q,timeout=45) as response:return json.load(response) if response.status!=204 else None
    except urllib.error.HTTPError as error:
        details=json.loads(error.read()).get('message','GitHub request rejected')
        raise RuntimeError(str(error.code)+': '+details) from None

def upload(url,file):
    from urllib.parse import urlencode
    file=Path(file);url=url.split('{')[0]+'?'+urlencode({'name':file.name})
    with file.open('rb') as stream:
        q=urllib.request.Request(url,data=stream,method='POST',headers={**headers(),'Content-Type':mimetypes.guess_type(file.name)[0] or 'application/octet-stream','Content-Length':str(file.stat().st_size)})
        with urllib.request.urlopen(q,timeout=300) as response:result=json.load(response)
    with file.open('rb') as stream:digest='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
    assert result['state']=='uploaded' and result['size']==file.stat().st_size
    if result.get('digest'):assert result['digest']==digest
    return result
