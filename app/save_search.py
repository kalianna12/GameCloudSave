"""Explicit search scopes; confirmed device paths stay out of routine searches."""
FINISHED={'review','notfound','failed','applied','ready','uploaded','local_only'}

def searched(row):
    return bool(row and row.get('completed') is not False and row.get('status') in FINISHED)

def targets(store,scope='pending',installed_only=True,idents=None):
    if scope not in ('pending','unsearched','all'):raise ValueError('查找范围无效')
    reports={row['id']:row for row in store.match_report}
    allowed=set(idents) if idents else None
    games=[]
    for game in store.games:
        ident=game['id'];local=store.local.get(ident,{})
        if allowed is not None and ident not in allowed:continue
        if installed_only and not local.get('installed',game.get('installed',False)):continue
        if scope!='all' and local.get('save_dir'):continue
        if scope=='unsearched' and searched(reports.get(ident)):continue
        games.append(game)
    # Preserve user priorities when the worker pool is filled: never-searched first.
    games.sort(key=lambda game:str(game.get('added_at') or ''),reverse=True)
    games.sort(key=lambda game:(searched(reports.get(game['id'])),str(reports.get(game['id'],{}).get('checked_at') or '')))
    return [game['id'] for game in games]
