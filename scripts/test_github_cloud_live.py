"""Disposable fixture branch in the release repository; never uploads user data."""
from pathlib import Path
import json,sys,tempfile,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from cloud_transport import GitHub
from github_api import request,headers
repo='kalianna12/GameCloudSave'
base=request('repos/'+repo+'/git/ref/heads/master')['object']['sha']
branch='gcs-cloud-check-'+uuid.uuid4().hex[:12]
created=False
try:
    request('repos/'+repo+'/git/refs','POST',{'ref':'refs/heads/'+branch,'sha':base});created=True
    client=GitHub({'github_repo':repo,'github_branch':branch},headers()['Authorization'].removeprefix('Bearer '))
    with tempfile.TemporaryDirectory() as temp:
        file=Path(temp)/'fixture.txt';file.write_bytes(b'GameCloudSave disposable cloud verification - no user data')
        client.mkdir('cloud-fixture');client.put('cloud-fixture/fixture.txt',file,True)
        assert any(row['Name']=='fixture.txt' for row in client.list('cloud-fixture'))
        downloaded=Path(temp)/'downloaded';client.get('cloud-fixture/fixture.txt',downloaded)
        assert downloaded.read_bytes()==file.read_bytes()
        client.put('cloud-fixture/fixture.txt',file,True)
        client.delete('cloud-fixture/fixture.txt')
    print('PASS: live GitHub fixture upload/list/download/immutable/delete')
finally:
    if created:request('repos/'+repo+'/git/refs/heads/'+branch,'DELETE');print('PASS: disposable fixture branch removed')
