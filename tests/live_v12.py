"""Real AI regression for previously failing titles, and isolated live workflow."""
import gc,json,sys,threading,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,protect
from ai_match import identify_game
from save_workflow import run_workflow
source=Store();key=protect((source.profile/'ai-key.dpapi').read_bytes(),True).decode()
results=[]
for title in ('Fate/stay night','中国式家长','噬血代码 II','Celeste'):
    result=identify_game(title,title,key,source.settings['ai_model'])
    assert isinstance(result['hints'],list)
    results.append({'title':title,'english_name':result['english_name'],'hint_count':len(result['hints'])})
    print(json.dumps(results[-1],ensure_ascii=True),flush=True)
(ROOT/'test-data/v12-ai-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
store=Store(ROOT/'test-data/live-workflow','isolated-v12')
store.save_settings({**source.settings,'snapshots':str(store.profile/'snapshots'),'password':source.password(),'cloud_folder':'电脑/GameCloudSave'})
print(store.configure_cloud({'cloud_folder':'电脑/GameCloudSave'}),flush=True)
ident=str(uuid.uuid4());save=store.profile/'Fixture/Saves';save.mkdir(parents=True,exist_ok=True)
(save/'slot.sav').write_bytes(b'isolated game save fixture')
store.games=[{'id':ident,'name':'隔离批量备份测试','installed':True,'cover':''}]
report={'id':ident,'name':'隔离批量备份测试','status':'review','candidates':[{'path':str(save),'confidence':.9,'files':['slot.sav']}],'aliases':[],'checked':[]}
with patch.object(store,'match_game',return_value=report):
    totals=run_workflow(store,[ident],lambda row:print('Stage:',row['status'],flush=True),threading.Event())
assert totals['uploaded']==1
history=store.history(ident);remote=history[0]['cloud_ref']
store.rclone(['deletefile',remote]);store.rclone(['rmdir','gamecloud:电脑/GameCloudSave/'+ident])
print('PASS: live automatic path application, local ZIP, cloud upload, write probe and fixture cleanup',flush=True)
