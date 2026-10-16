"""Explicit cloud history refresh and verified download; never auto-restore."""
from pathlib import Path,PurePosixPath
from contextlib import closing
import hashlib
import json
import tempfile
import zipfile
from cloud_paths import folder_path,game_folder,component

def digest(file):
    with Path(file).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def publish(store,ident,archive,target):
    game=next(game for game in store.games if game['id']==ident)
    row=next(row for row in store.history(ident) if row['archive_path']==str(archive))
    from cloud_identity import identity,register
    metadata={'version':2,'game_id':ident,'game_name':game['name'],'platform':game.get('platform','local'),'identity':identity(game),
              'external_id':game.get('external_id',''),'sha256':digest(archive),'created_at':row['created_at'],
              'note':row['note'],'computer':store.settings['computer'],'computer_id':store.identity,'event':row['event']}
    if row['event']=='cloud_download':
        original=json.loads(store.rclone(['cat',target+'.json','--head','65536']))
        if original.get('sha256')!=metadata['sha256']:raise ValueError('云端版本已改变，备注未覆盖')
        metadata={**original,'note':row['note']}
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        file=Path(temporary)/'record.json';file.write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
        store.rclone(['copyto',str(file),target+'.json'])
    # Separate index files per readable folder avoid concurrent-device lost updates.
    if row['event']!='cloud_download':register(store,game,game_folder(store.games,ident))
def listing(store,ident):
    root=folder_path(store.settings['cloud_folder'])
    if not root:raise ValueError('请先配置云端存储')
    game=next(game for game in store.games if game['id']==ident)
    from cloud_identity import folders,identity
    primary=game_folder(store.games,ident)
    try:aliases=folders(store,game)
    except (ValueError,OSError,TypeError,KeyError):aliases=[]
    legacy_names=[component(game[field]) for field in ('source_name','english_name','metadata_name') if isinstance(game.get(field),str) and game[field].strip()]
    candidates=list(dict.fromkeys([primary,*aliases,*legacy_names]));all_records=[];errors=[];allowed=[]
    for name in candidates:
        try:
            all_records.extend(_listing_folder(store,'/'.join((root,name))))
            allowed.append(name)
        except ValueError as error:errors.append(error)
    if not allowed and errors:raise errors[-1]
    expected=identity(game)
    if expected:
        all_records=[row for row in all_records if not (row.get('identity') or {}).get('external_id') or row['identity']==expected]
    store._cloud_history_folders=getattr(store,'_cloud_history_folders',{})
    store._cloud_history_folders[ident]=allowed
    from datetime import datetime
    def stamp(row):
        try:return datetime.fromisoformat(row['created_at'].replace('Z','+00:00')).timestamp()
        except (ValueError,TypeError):return 0
    return sorted(all_records,key=stamp,reverse=True)[:200]

def _listing_folder(store,folder):
    entries=json.loads(store.rclone(['lsjson','gamecloud:'+folder,'--recursive','--max-depth','4','--files-only']))
    records=[]
    for entry in entries:
        relative=entry.get('Path',entry['Name']);parts=PurePosixPath(relative).parts
        if entry.get('IsDir') or '..' in parts or relative.startswith('/') or '\\' in relative or any(ord(c)<32 for c in relative) or not relative.casefold().endswith('.zip'):continue
        records.append({'remote':'gamecloud:'+folder+'/'+relative,'name':Path(relative).name,'created_at':str(entry.get('ModTime') or ''),
                        'note':'','computer':'','size':entry.get('Size',0),'verified':False})
    records.sort(key=lambda row:row['created_at'],reverse=True)
    records=records[:200]
    available={entry.get('Path',entry.get('Name','')) for entry in entries if not entry.get('IsDir') and isinstance(entry.get('Size',0),(int,float)) and 0<=entry.get('Size',0)<=65536}
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        selected=Path(temporary)/'selected-records.txt'
        metadata_names=[row['remote'][len('gamecloud:'+folder+'/'):]+'.json' for row in records]
        metadata_names=[name for name in metadata_names if name in available]
        selected.write_text('\n'.join(metadata_names),encoding='utf-8')
        if metadata_names:store.rclone(['copy','gamecloud:'+folder,temporary,'--files-from-raw',str(selected),'--transfers','2'])
        for row in records:
            relative=row['remote'][len('gamecloud:'+folder+'/'):]
            file=Path(temporary)/(relative+'.json')
            if file.is_file() and file.stat().st_size<=65536:
                try:
                    metadata=json.loads(file.read_text(encoding='utf-8'))
                    if not isinstance(metadata,dict):continue
                    row.update({key:metadata[key] for key in ('created_at','note','computer','computer_id','event','sha256','game_id','game_name','platform','external_id') if isinstance(metadata.get(key),str)})
                    value=metadata.get('identity') or {'platform':row.get('platform',''),'external_id':row.get('external_id','')}
                    if isinstance(value,dict):row['identity']={key:str(value.get(key,'')) for key in ('platform','external_id')}
                    import re
                    row['verified']=bool(re.fullmatch(r'[0-9a-fA-F]{64}',row.get('sha256','')))
                except (ValueError,OSError):pass
    return sorted(records,key=lambda row:row['created_at'],reverse=True)
def receive(store,ident,record):
    if not store.local.get(ident,{}).get('save_dir'):raise ValueError('请先设置此电脑的存档目录')
    # Paths supplied by the UI must remain beneath this game's configured cloud folder.
    folder_names=getattr(store,'_cloud_history_folders',{}).get(ident,[game_folder(store.games,ident)])
    prefixes=['gamecloud:'+folder_path(store.settings['cloud_folder'])+'/'+folder+'/' for folder in folder_names]
    remote=record['remote']
    if not any(remote.startswith(prefix) for prefix in prefixes) or '..' in PurePosixPath(remote).parts or '\\' in remote:raise ValueError('云端记录路径无效')
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        downloaded=Path(temporary)/'download.zip';store.rclone(['copyto',remote,str(downloaded)])
        sha=digest(downloaded)
        if record.get('sha256') and sha!=record['sha256']:raise ValueError('下载文件校验失败，未恢复')
        from save_restore import archive_info
        try:meta,files,_=archive_info(downloaded)
        except (zipfile.BadZipFile,KeyError):raise ValueError('云端备份损坏或缺少元数据') from None
        if not files:raise ValueError('云端备份没有可恢复的存档文件')
        game=next(game for game in store.games if game['id']==ident)
        from cloud_identity import compatible
        if not compatible(game,meta,record):raise ValueError('备份属于其他游戏或平台版本，未导入')
        directory=Path(store.settings['snapshots'])/'cloud'/ident;directory.mkdir(parents=True,exist_ok=True)
        destination=directory/(sha+'.zip')
        import shutil
        if not destination.exists():shutil.copy2(downloaded,destination)
        core=store.core();game_row=store.game(ident)
        with closing(core.connect_db()) as connection:
            existing=connection.execute('SELECT id FROM snapshots WHERE game_id=? AND archive_path=?',(game_row.id,str(destination))).fetchone()
            if existing:return existing['id']
            cursor=connection.execute('INSERT INTO snapshots(game_id,created_at,event,note,archive_path,sha256,uploaded,cloud_ref) VALUES(?,?,?,?,?,?,1,?)',
                (game_row.id,meta.get('created_at') or core.now_iso(),'cloud_download',record.get('note') or meta.get('note',''),str(destination),sha,remote))
            connection.commit();return cursor.lastrowid
