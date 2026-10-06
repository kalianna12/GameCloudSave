"""Live test using an isolated fixture; only its exact remote file is deleted."""
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services import Store, ROOT

source = Store()
test = Store(ROOT / 'test-data/live-dav', 'live-test')
ident = str(uuid.uuid4())
test.save_settings({**source.settings, 'snapshots':str(test.profile / 'snapshots'), 'password':source.password(), 'cloud_folder':'电脑/GameCloudSave'})
test.games = [{'id':ident,'name':'中文测试游戏（非真实存档）','cover':'','installed':True}]
save = test.profile / 'fixture'
save.mkdir(exist_ok=True)
(save / 'save.json').write_text(json.dumps({'说明':'隔离上传验证','进度':42},ensure_ascii=False),encoding='utf-8')
test.save_game(ident, {'save_dir':str(save)})
assert len(test.rclone('list')) >= 1
archive = test.backup(ident)
target = 'gamecloud:电脑/GameCloudSave/' + ident + '/' + archive.name
uploaded = False
extra_targets=[]
try:
    test.upload(ident, archive)
    uploaded = True
    download = test.profile / 'download.zip'
    test.rclone(['copyto', target, str(download)])
    assert hashlib.sha256(download.read_bytes()).digest() == hashlib.sha256(archive.read_bytes()).digest()
    assert test.history(ident)[0]['uploaded'] == 1
    text=save/'preview.json'
    text_target='gamecloud:电脑/GameCloudSave/'+ident+'/preview.json'
    test.rclone(['copyto',str(save/'save.json'),text_target])
    extra_targets.append(text_target)
    entries=test.rclone('list','电脑/GameCloudSave/'+ident)
    entry=next(row for row in entries if row['Name']=='preview.json')
    preview=test.preview_cloud('电脑/GameCloudSave/'+ident,entry)
    assert json.loads(preview['text'])['进度']==42
    print('PASS: DAV file listing and live JSON content preview')
    print('PASS: DAV listing, local snapshot, live upload, download SHA256, uploaded state')
finally:
    if uploaded:
        for remote in extra_targets: test.rclone(['deletefile',remote])
        test.rclone(['deletefile', target])
        test.rclone(['rmdir', 'gamecloud:电脑/GameCloudSave/' + ident])
        print('PASS: isolated remote fixture removed')
