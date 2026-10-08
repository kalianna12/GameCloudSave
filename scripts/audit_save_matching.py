"""Read-only real-library audit. Produces an actionable report, never launches/backups games."""
from pathlib import Path
import sys,json,time,uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT,write_json
from save_workflow import select_candidate,evidence

def audit():
    store=Store();store.games=list(store.games);store.local=dict(store.local)
    extras={'Dark Souls III':r'D:\GAMES\Dark Souls III The Ringed City\Game',
            'ENDER MAGNOLIA: Bloom in the Mist':r'D:\GAMES\ENDER.MAGNOLIA.Bloom.in.the.Mist',
            'Slay the Spire 2':r'F:\Games\Slay the Spire 2'}
    for name,install in extras.items():
        if any(g['name'].casefold()==name.casefold() for g in store.games):continue
        ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'audit:'+name))
        store.games.append({'id':ident,'name':name,'cover':'','audit_extra':True})
        store.local[ident]={'install_dir':install}
    report=[];started=time.monotonic()
    def one(game):
        try:
            result=store.match_game(game['id']);selected=select_candidate(result)
            proven=[c for c in result['candidates'] if evidence(c)]
            status='found' if selected else 'sample_only' if proven and all(c.get('sample_backup') for c in proven) else 'review' if proven else 'directory_only' if result['candidates'] else 'not_observed'
            return {'id':game['id'],'name':game['name'],'audit_extra':game.get('audit_extra',False),'status':status,
                    'selected':selected['path'] if selected else '', 'proven':[{'path':c['path'],'confidence':c['confidence'],'files':c['files']} for c in proven],
                    'result':result}
        except Exception as error:return {'id':game['id'],'name':game['name'],'status':'error','error':type(error).__name__+': '+str(error)}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(one,g):g for g in store.games}
        for future in as_completed(pending):
            row=future.result();report.append(row)
            write_json(ROOT/'test-data/save-audit.json',{'elapsed':round(time.monotonic()-started,2),'completed':len(report),'total':len(store.games),'games':sorted(report,key=lambda r:r['name'].casefold())})
            print(json.dumps({'done':len(report),'total':len(store.games),'name':row['name'],'status':row['status'],'selected':row.get('selected','')},ensure_ascii=True),flush=True)
    return report

if __name__=='__main__':audit()
