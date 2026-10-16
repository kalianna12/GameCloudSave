"""Opt-in real DAV roundtrip in a marked, unique sandbox; never upload real game data."""
from pathlib import Path
import json,sys,tempfile,uuid,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,DATA,machine_id,read_json
from cloud_paths import folder_path

profile=DATA/'machines'/machine_id();settings=read_json(profile/'settings.json',{})
base=folder_path(settings.get('cloud_folder',''))
if not base:raise ValueError('未配置云端根目录')
nonce=uuid.uuid4().hex;name='__GameCloudSave_SAVE_TEST_'+nonce;scratch=base+'/'+name
report={'passed':False,'cleanup':False,'test_name':name}
output=ROOT/'test-data/save-reliability/live-dav-result.json'
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    root=Path(directory)
    def fixture(device,ident,title,account):
        store=Store(root/device,device)
        store.settings.update({key:settings[key] for key in ('dav_url','dav_user','rclone','cloud_timeout','cloud_retries') if key in settings})
        store.settings.update(cloud_folder=scratch,computer=device,cloud_separate_computer=True)
        shutil.copy2(profile/'credential.dpapi',store.profile/'credential.dpapi')
        store.games=[{'id':ident,'name':title,'platform':'steam','external_id':'2680010','cover':''}]
        saves=store.profile/'SaveGames';(saves/account).mkdir(parents=True)
        for number in ('01','02'):(saves/account/('SaveGame'+number+'_Player.sav')).write_text(device+'-'+number)
        store.save_game(ident,{'save_dir':str(saves)});return store,saves
    source='76561198000000001';target='76561198000000002'
    a,one=fixture('fixture-PC-A','source','Generated save fixture A',source)
    b,two=fixture('fixture-PC-B','target','隔离目标游戏',target)
    marker=root/'owner.json';marker.write_text(json.dumps({'nonce':nonce,'purpose':'isolated-save-test'}))
    remote_marker='gamecloud:'+scratch+'/owner.json';created=False
    try:
        a.rclone(['copyto',str(marker),remote_marker,'--immutable']);created=True
        a.upload('source',a.backup('source'))
        records=b.cloud_history('target');assert len(records)==1 and records[0]['verified']
        snapshot=b.receive_cloud_snapshot('target',records[0])
        assert (two/target/'SaveGame01_Player.sav').read_text()=='fixture-PC-B-01'
        assert b.restore_preview('target',snapshot)['needs_mapping']
        b.restore('target',snapshot,{'source_account':source,'target_account':target,'slot':source+'/SaveGame01'})
        assert (two/target/'SaveGame01_Player.sav').read_text()=='fixture-PC-A-01'
        assert (two/target/'SaveGame02_Player.sav').read_text()=='fixture-PC-B-02'
        assert not (two/source).exists()
        b.set_snapshot_note('target',snapshot,'verified on isolated B')
        record=a.cloud_history('source')[0]
        assert record['note']=='verified on isolated B' and record['computer']=='fixture-PC-A'
        report['passed']=True
        print('PASS: real DAV upload/index/list/metadata/download/hash, independent IDs and names, account mapping, one-slot restore and notes',flush=True)
    finally:
        try:
            if created:
                assert scratch==base+'/'+name and name=='__GameCloudSave_SAVE_TEST_'+nonce and '..' not in scratch.split('/')
                owner=json.loads(a.rclone(['cat',remote_marker,'--head','1024']))
                assert owner=={'nonce':nonce,'purpose':'isolated-save-test'},'Sandbox ownership marker mismatch; cleanup refused'
                a.rclone(['purge','gamecloud:'+scratch]);report['cleanup']=True
                print('PASS: only the marked DAV sandbox removed',flush=True)
        finally:output.write_text(json.dumps(report,indent=2),encoding='utf-8')
