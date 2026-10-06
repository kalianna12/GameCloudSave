"""Explicit live DAV test; all writes stay in a newly generated test directory."""
from pathlib import Path
import sys,tempfile,json,uuid,gc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from cloud_management import digest
source=Store()
root=source.settings['cloud_folder'].strip('/')
test_root=root+'/_GameCloudTest-'+str(uuid.uuid4())
assert test_root.startswith(root+'/_GameCloudTest-')
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    store=Store(Path(temporary),'live-cloud-paths')
    store.save_settings({**source.settings,'password':source.password(),'cloud_folder':test_root,'snapshots':str(store.profile/'snapshots')})
    ident=str(uuid.uuid4());store.games=[{'id':ident,'name':'中文游戏/存档测试','cover':''}]
    save=store.root/'游戏存档';save.mkdir();(save/'progress.json').write_text('{"chapter":42}')
    store.save_game(ident,{'save_dir':str(save)})
    report={'passed':False,'test_root':test_root}
    try:
        source.create_cloud_folder(root,test_root.rsplit('/',1)[1])
        archive=store.backup(ident);store.upload(ident,archive)
        folder=store.cloud_directory(ident)
        entry=next(e for e in store.rclone('list',folder) if e['Name']==archive.name)
        download=store.root/'downloaded.zip';store.download_cloud(folder,entry,download)
        assert digest(archive)==digest(download)
        assert '/中文游戏／存档测试/游戏存档/' in store.history(ident)[0]['cloud_ref']
        report.update({'passed':True,'directory':folder,'sha256':digest(download),'bytes':download.stat().st_size})
    finally:
        source.rclone(['purge','gamecloud:'+test_root])
        report['test_directory_removed']=True
        write_json(ROOT/'test-data/live-cloud-paths.json',report)
        gc.collect()
print(json.dumps(report,ensure_ascii=True))
