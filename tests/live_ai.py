"""Real matching test using the locally encrypted key; never changes save paths."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,protect,write_json
from ai_match import identify_game
from matching import scan
store=Store()
store.save_settings({'ai_enabled':True})
results={row['id']:row for row in store.match_report}
for prefix in ('ELDEN RING','Chinese Parents','CODE VEIN'):
    game=next(g for g in store.games if g['name'].startswith(prefix))
    result=store.match_game(game['id'])
    results[game['id']]=result
    store.save_match_report(list(results.values()))
    print(json.dumps({'game':game['name'],'status':result['status'],'candidate_count':len(result['candidates']),'seconds':result['elapsed'],'message':result['message']},ensure_ascii=True),flush=True)
key=protect((store.profile/'ai-key.dpapi').read_bytes(),True).decode()
identity=identify_game('艾尔登法环','ELDEN RING',key,store.settings['ai_model'])
write_json(ROOT/'test-data/chinese-ai-probe.json',identity)
assert 'elden' in identity['english_name'].casefold()
print('PASS: Chinese title identified as Elden Ring; no save paths applied',flush=True)
