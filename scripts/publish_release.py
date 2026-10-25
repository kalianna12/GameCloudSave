"""Upload verified release assets to a draft, then optionally publish it."""
from pathlib import Path
import argparse,hashlib,subprocess,sys
from github_api import request,upload
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--version',required=True);parser.add_argument('--publish',action='store_true');args=parser.parse_args()
import re
if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise ValueError('Invalid release version')
tag='v'+args.version;repo='repos/kalianna12/GameCloudSave'
def git(*arguments):return subprocess.check_output(['git',*arguments],cwd=ROOT,text=True).strip()
if git('status','--porcelain'):raise ValueError('Commit the release source first')
if git('rev-parse','HEAD')!=git('rev-list','-n','1',tag):raise ValueError('Release tag must point to HEAD')
out=ROOT/'dist/releases'
files=[ROOT/('dist/installers/GameCloudSave-Setup-V'+args.version+'.exe'),out/('GameCloudSave-V'+args.version+'-Portable.zip'),out/('GameCloudSave-V'+args.version+'-Source.zip'),out/('GameCloudSave-V'+args.version+'-Report.md'),out/'SHA256SUMS.txt']
for file in files:
    if not file.is_file():raise ValueError('Missing '+file.name)
for line in files[-1].read_text(encoding='utf-8').splitlines():
    expected,name=line.split('  ',1);file=next(f for f in files if f.name==name)
    with file.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected
try:release=request(repo+'/releases/tags/'+tag)
except RuntimeError as error:
    if not str(error).startswith('404:'):raise
    release=request(repo+'/releases','POST',{'tag_name':tag,'target_commitish':git('rev-parse','HEAD'),'name':'GameCloudSave V'+args.version,'draft':True,'body':(ROOT/('docs/V'+args.version+'发布说明.md')).read_text(encoding='utf-8')})
if not release['draft']:raise ValueError('Release is already public; no assets were changed')
known={asset['name']:asset for asset in release['assets']}
for file in files:
    with file.open('rb') as stream:digest='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
    if file.name in known:
        asset=known[file.name]
        assert asset['size']==file.stat().st_size and asset.get('digest')==digest,('Existing draft asset differs',file.name)
    else:asset=upload(release['upload_url'],file)
    print('VERIFIED '+file.name+' '+str(asset['size'])+' bytes',flush=True)
if args.publish:
    release=request(repo+'/releases/'+str(release['id']),'PATCH',{'draft':False,'make_latest':'true'})
print(release['html_url'],flush=True)
