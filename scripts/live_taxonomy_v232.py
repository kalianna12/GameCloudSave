"""Real DeepSeek preview using a disposable library; never change user tags."""
from pathlib import Path
import sys,tempfile,copy,shutil,time,json,uuid,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from library_organizer import suggestions
from tag_catalog import vocabulary
source=Store();original=hashlib.sha256((source.root/'library.json').read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temporary:
    test=Store(temporary,'live-tags');test.settings=dict(source.settings);test.games=copy.deepcopy(source.games);test.groups=list(source.groups)
    shutil.copy2(source.profile/'ai-key.dpapi',test.profile/'ai-key.dpapi')
    ids=[]
    for title in ['Rubinite','Celeste','Fate/stay night']:
        ident='check-'+str(uuid.uuid4());ids.append(ident);test.games.append({'id':ident,'name':title,'tags':[],'cover':''})
    before=json.dumps(test.games,sort_keys=True);allowed=set(vocabulary(test.games));started=time.monotonic()
    first=suggestions(test,True,ids);elapsed=time.monotonic()-started
    second=suggestions(test,True,ids)
    assert first==second and json.dumps(test.games,sort_keys=True)==before
    results=[row for row in first if row['id'] in ids]
    assert all(set(row['tags'])<=allowed for row in results)
    assert hashlib.sha256((source.root/'library.json').read_bytes()).hexdigest()==original
    report={'passed':True,'seconds':round(elapsed,2),'games':[{'name':row['name'],'category':row['category'],'tags':row['tags']} for row in results],'cached_result_equal':True,'library_changed':False}
    output=ROOT/'test-data/v232';output.mkdir(exist_ok=True)
    (output/'live-tags.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False))
