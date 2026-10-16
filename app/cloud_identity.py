"""Ownership IDs survive library renames; metadata-only links are not ownership."""
import hashlib
import json
import re


def identity(game):
    platform=game.get('platform','local')
    external=str(game.get('external_id') or (game.get('steam_appid') if platform=='steam' else '') or '')
    if platform not in ('steam','epic','ubisoft') or not external:return {}
    if platform=='steam' and not re.fullmatch(r'\d{1,12}',external):return {}
    return {'platform':platform,'external_id':external}


def key(game):
    value=identity(game)
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:32] if value else ''


def compatible(game,metadata,record):
    expected=identity(game)
    actual=metadata.get('identity') or record.get('identity') or {field:record.get(field,'') for field in ('platform','external_id')}
    if expected and actual.get('external_id'):
        return expected==actual
    if metadata.get('game')==game['id']:return True
    return bool(record.get('sha256') and record.get('game_name')==game['name'])


def register(store,game,folder):
    ident=key(game)
    if not ident:return
    from cloud_paths import folder_path
    from pathlib import Path
    import tempfile
    path=folder_path(store.settings['cloud_folder'])+'/.gamecloud-index/'+ident+'/'
    path+=hashlib.sha256(folder.encode()).hexdigest()[:24]+'.json'
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        file=Path(temporary)/'index.json'
        file.write_text(json.dumps({'folder':folder,'identity':identity(game)},ensure_ascii=False),encoding='utf-8')
        store.rclone(['copyto',str(file),'gamecloud:'+path])


def folders(store,game):
    ident=key(game)
    if not ident:return []
    from cloud_paths import folder_path,component
    base='gamecloud:'+folder_path(store.settings['cloud_folder'])+'/.gamecloud-index/'+ident
    entries=json.loads(store.rclone(['lsjson',base,'--files-only']))
    result=[]
    for row in entries[:100]:
        name=row.get('Name','')
        if not re.fullmatch(r'[0-9a-f]{24}\.json',name):continue
        try:data=json.loads(store.rclone(['cat',base+'/'+name,'--head','65536']))
        except (ValueError,TypeError):continue
        if not isinstance(data,dict):continue
        folder=data.get('folder','')
        if isinstance(folder,str) and folder and component(folder)==folder and '/' not in folder and '\\' not in folder and data.get('identity')==identity(game):result.append(folder)
    return list(dict.fromkeys(result))
