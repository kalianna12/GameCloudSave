"""Resolve imported launch actions and inspect local installation evidence only."""
from pathlib import Path
import os,re

def launch_actions(raw,playnite=''):
    install=str(raw.get('InstallDirectory') or '').strip().strip('"')
    def expand(value,base=''):
        value=str(value or '').replace('{InstallDir}',install).replace('{PlayniteDir}',str(playnite)).replace('{Name}',str(raw.get('Name') or '')).replace('{GameId}',str(raw.get('GameId') or ''))
        if re.search(r'\{[^{}]+\}',value):return ''
        value=os.path.expandvars(value).strip().strip('"')
        if value and base and not Path(value).is_absolute():value=str(Path(base)/value)
        return value
    output=[]
    for action in raw.get('GameActions') or []:
        if not action.get('IsPlayAction') or action.get('Type',0) not in (0,'0','File'):continue
        path=expand(action.get('Path'),install)
        if not path or not Path(path).is_absolute() or Path(path).suffix.lower() not in ('.exe','.bat','.cmd'):continue
        args=str(action.get('Arguments') or '').replace('{InstallDir}',install)
        if re.search(r'\{[^{}]+\}',args):continue
        if Path(path).suffix.lower() in ('.bat','.cmd') and args.strip():continue
        working=expand(action.get('WorkingDir'),install) or str(Path(path).parent)
        output.append({'exe':path,'arguments':args,'working_dir':working})
    return output

def launch_fields(raw,playnite=''):
    actions=launch_actions(raw,playnite)
    # Scripts/emulators need their original execution environment.
    scripts=any(raw.get(key) for key in ('PreScript','PostScript','GameStartedScript'))
    if scripts:return {}
    existing=[action for action in actions if Path(action['exe']).is_file()]
    chosen=existing if existing else actions
    if len(chosen)!=1:return {}
    return {**chosen[0],'launch_mode':'direct','launch_origin':'playnite'}

def installation(local):
    """A save directory and Playnite's IsInstalled flag are never evidence."""
    exe=str(local.get('exe') or '').strip()
    folder=str(local.get('install_dir') or '').strip()
    if exe:return Path(exe).is_file()
    if folder:
        path=Path(folder)
        try:return path.is_dir() and next(path.iterdir(),None) is not None
        except OSError:return False
    return False

def probe(games,local,raw_rows=(),playnite=''):
    raw_by_id={str(row.get('_id',{}).get('$guid','')).lower():row for row in raw_rows}
    changes={}
    for game in games:
        ident=game['id'];before=dict(local.get(ident,{}));after=dict(before)
        raw=raw_by_id.get(ident.lower())
        if raw is not None:
            after['install_dir']=str(raw.get('InstallDirectory') or '')
            fields=launch_fields(raw,playnite)
            if fields and (not before.get('exe') or before.get('launch_origin')=='playnite' or before.get('launch_mode')=='playnite'):
                after.update(fields)
        if after.get('exe') or after.get('install_dir') or raw is not None or game.get('import_source')=='playnite':
            after['installed']=installation(after)
        update={key:value for key,value in after.items() if before.get(key)!=value}
        if update:changes[ident]={'before':before,'values':update}
    return changes
