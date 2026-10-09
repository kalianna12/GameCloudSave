"""Use an isolated cloud folder and generated save data; never touch real saves."""
from pathlib import Path
import sys
import uuid
import tempfile
import gc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from cloud_paths import folder_path

source=Store()
configured=folder_path(source.settings['cloud_folder'])
if not configured:raise ValueError('Cloud folder is not configured')
test_name='__GameCloudSave_V20_TEST_'+uuid.uuid4().hex
scratch=configured+'/'+test_name
assert scratch.startswith(configured+'/__GameCloudSave_V20_TEST_') and '..' not in scratch.split('/')
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    stores=[]
    for computer in ('test-PC-A','test-PC-B'):
        store=Store(Path(temporary)/computer,computer)
        snapshots=store.settings['snapshots']
        store.settings.update(source.settings)
        store.settings.update(snapshots=snapshots,cloud_folder=scratch,computer=computer)
        store.password=source.password
        game_id=str(uuid.uuid4())
        store.games=[{'id':game_id,'name':'Generated test game','cover':''}]
        save=store.profile/'Release';save.mkdir();(save/'slot1.sav').write_text(computer)
        store.save_game(game_id,{'save_dir':str(save)});stores.append((store,game_id,save))
    a,a_id,_=stores[0];b,b_id,b_save=stores[1]
    try:
        archive=a.backup(a_id);a.set_snapshot_note(a_id,a.history(a_id)[0]['id'],'roundtrip fixture');a.upload(a_id,archive)
        records=b.cloud_history(b_id)
        assert len(records)==1 and records[0]['note']=='roundtrip fixture'
        snapshot=b.receive_cloud_snapshot(b_id,records[0]);b.restore(b_id,snapshot)
        assert (b_save/'slot1.sav').read_text()=='test-PC-A'
        b.set_snapshot_note(b_id,snapshot,'verified from second computer')
        assert a.cloud_history(a_id)[0]['note']=='verified from second computer'
        print('PASS: actual DAV fixture upload, metadata, second-device list/download/hash/restore, shared note update')
    finally:
        assert scratch==configured+'/'+test_name and test_name.startswith('__GameCloudSave_V20_TEST_')
        a.rclone(['purge','gamecloud:'+scratch])
        gc.collect()
