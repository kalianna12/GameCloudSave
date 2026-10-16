"""Opt-in real Search + model lookup; only generated saves and isolated caches are used."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,DATA,ROOT,machine_id,read_json
from match_engine import match
from save_workflow import select_candidate

profile=DATA/'machines'/machine_id()
settings=read_json(profile/'settings.json',{})
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as directory:
    root=Path(directory);store=Store(root/'data','web-live')
    store.games=[{'id':'khazan','name':'The First Berserker: Khazan','steam_appid':'2680010','external_id':'2680010','platform':'steam'}]
    store.settings.update(watch=False,ai_enabled=True,ai_model=settings.get('ai_model','deepseek-flash'),match_network=True,match_web_search=True,match_ai_review=True)
    shutil.copy2(profile/'ai-key.dpapi',store.profile/'ai-key.dpapi')
    save=root/'local/BBQ/Saved/SaveGames';save.mkdir(parents=True);(save/'SaveGame01_Player.sav').write_bytes(b'isolated progress')
    resources=root/'resources/ui';resources.mkdir(parents=True);(resources/'save-rules.json').write_text('{"rules":[]}')
    identity={'english_name':'The First Berserker: Khazan','aliases':[],'hints':[],'sources':[]}
    # Known title and absent offline rules force the real webpage-discovery path.
    with patch('matching.roots_for',return_value={'local':root/'local'}),patch('library_sources.steam_roots',return_value=[]),patch('services.RESOURCES',resources.parent),patch('match_engine.cached_ai',return_value=identity),patch('match_engine.cached_network',return_value=identity):
        result=match(store,'khazan');selected=select_candidate(result)
    report={key:result.get(key) for key in ('status','elapsed','scan_modes','sources','web_warning','note')}
    report['found_BBQ']=bool(selected and selected['path']==str(save.resolve()))
    report['candidate_sources']=[candidate.get('source') for candidate in result['candidates']]
    output=ROOT/'test-data/save-reliability';output.mkdir(exist_ok=True)
    (output/'live-web-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
    assert report['found_BBQ'],'Real web lookup did not resolve the alternate folder; inspect the isolated report'
