"""Read-only live lookup of Rubinite with isolated metadata caches and credentials."""
from pathlib import Path
import sys,tempfile,gc,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,protect,write_json
from save_workflow import select_candidate
source=Store()
game=next(game for game in source.games if game['name'] in ('Rubinite','红眼露比'))
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    store=Store(Path(temporary),'live-matching')
    store.games=[game];store.local[game['id']]={k:v for k,v in source.local.get(game['id'],{}).items() if k!='save_dir'}
    key=protect((source.profile/'ai-key.dpapi').read_bytes(),True).decode()
    store.save_settings({**source.settings,'ai_enabled':True,'match_network':True,'ai_key':key})
    measurements=[]
    for phase in ('cold','cached'):
        start=time.monotonic();partials=[]
        row=store.match_game(game['id'],lambda r:partials.append({'seconds':round(time.monotonic()-start,2),'candidates':len(r['candidates'])}))
        selected=select_candidate(row)
        assert selected and selected['path'].endswith(r'Cup Dog Games\Rubinite\Release'),row
        assert 'Cup Dog Games' in row['developers']
        assert len(row['scan_modes'])==3
        measurements.append({'phase':phase,'elapsed':row['elapsed'],'first_local_result':next((r['seconds'] for r in partials if r['candidates']),None),'selected':selected['path'],'score':selected['confidence'],'developers':row['developers'],'warnings':[row['ai_warning'],row['network_warning']]})
        print(json.dumps(measurements[-1],ensure_ascii=True),flush=True)
    write_json(ROOT/'test-data/live-matching-engine.json',measurements)
    # Make the verified result available in the application's results view.
    existing={r['id']:r for r in source.match_report};existing[game['id']]=row
    source.save_match_report(list(existing.values()))
    gc.collect()
