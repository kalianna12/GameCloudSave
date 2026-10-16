"""Real rclone local backend: isolated two-device transfer, index, metadata and restore."""
from pathlib import Path
import json,sys,tempfile,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,run_process

with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    root=Path(directory);remote=root/'remote';remote.mkdir()
    config=root/'rclone.conf';config.write_text('')
    calls=[]
    def transfer(arguments,*args,**kwargs):
        translated=[str(remote/value[len('gamecloud:'):]) if isinstance(value,str) and value.startswith('gamecloud:') else str(value) for value in arguments]
        result=run_process([shutil.which('rclone'),'--config',str(config),*translated],timeout=15)
        if result.returncode:raise ValueError(result.stderr)
        calls.append(arguments[0]);return result.stdout
    def fixture(device,ident,title,account):
        store=Store(root/device,device);store.games=[{'id':ident,'name':title,'platform':'steam','external_id':'2680010','cover':''}]
        store.settings.update(computer=device,cloud_folder='isolated-saves',cloud_separate_computer=True)
        store.rclone=transfer
        saves=root/device/'SaveGames';(saves/account).mkdir(parents=True)
        for number in ('01','02'):(saves/account/('SaveGame'+number+'_Player.sav')).write_text(device+'-'+number)
        store.save_game(ident,{'save_dir':str(saves)});return store,saves
    source='76561198000000001';target='76561198000000002'
    a,one=fixture('PC-A','source','English title',source)
    b,two=fixture('PC-B','target','中文游戏名',target)
    a.upload('source',a.backup('source'))
    rows=b.cloud_history('target');assert len(rows)==1 and rows[0]['verified']
    snapshot=b.receive_cloud_snapshot('target',rows[0])
    assert (two/target/'SaveGame01_Player.sav').read_text()=='PC-B-01'
    assert b.restore_preview('target',snapshot)['needs_mapping']
    b.restore('target',snapshot,{'source_account':source,'target_account':target,'slot':source+'/SaveGame01'})
    assert (two/target/'SaveGame01_Player.sav').read_text()=='PC-A-01'
    assert (two/target/'SaveGame02_Player.sav').read_text()=='PC-B-02'
    assert not (two/source).exists()
    b.set_snapshot_note('target',snapshot,'Continued on B')
    row=a.cloud_history('source')[0];assert row['note']=='Continued on B' and row['computer']=='PC-A'
    assert (one/source/'SaveGame01_Player.sav').read_text()=='PC-A-01'
    report={'passed':True,'rclone_calls':len(calls),'operations':sorted(set(calls)),
            'independent_names_and_ids':True,'account_mapping':True,'partial_slot':True,'cloud_notes':True}
    (ROOT/'test-data/save-reliability/rclone-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('PASS: real rclone local transfer, bounded metadata fetch, stable identity index, account mapping, one-slot restore and note sync')
