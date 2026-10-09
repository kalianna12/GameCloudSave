"""Explicit cloud history refresh and verified download; never auto-restore."""
from pathlib import Path,PurePosixPath
from contextlib import closing
import hashlib
import json
import tempfile
import zipfile
from cloud_paths import folder_path,game_folder

def digest(file):
    with Path(file).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def publish(store,ident,archive,target):
    game=next(game for game in store.games if game['id']==ident)
    row=next(row for row in store.history(ident) if row['archive_path']==str(archive))
    metadata={'version':1,'game_id':ident,'game_name':game['name'],'platform':game.get('platform','local'),
              'external_id':game.get('external_id',''),'sha256':digest(archive),'created_at':row['created_at'],
              'note':row['note'],'computer':store.settings['computer']}
    if row['event']=='cloud_download':
        original=json.loads(store.rclone(['cat',target+'.json','--head','65536']))
        if original.get('sha256')!=metadata['sha256']:raise ValueError('云端版本已改变，备注未覆盖')
        metadata={**original,'note':row['note']}
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        file=Path(temporary)/'record.json';file.write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
        store.rclone(['copyto',str(file),target+'.json'])
def listing(store,ident):
    root=folder_path(store.settings['cloud_folder'])
    if not root:raise ValueError('请先配置云端存储')
    folder='/'.join((root,game_folder(store.games,ident)))
    entries=json.loads(store.rclone(['lsjson','gamecloud:'+folder,'--recursive','--max-depth','4','--files-only']))
    records=[]
    for entry in entries:
        relative=entry.get('Path',entry['Name']);parts=PurePosixPath(relative).parts
        if entry.get('IsDir') or '..' in parts or relative.startswith('/') or '\\' in relative or not relative.casefold().endswith('.zip'):continue
        records.append({'remote':'gamecloud:'+folder+'/'+relative,'name':Path(relative).name,'created_at':entry.get('ModTime',''),
                        'note':'','computer':'','size':entry.get('Size',0),'verified':False})
    records.sort(key=lambda row:row['created_at'],reverse=True)
    if len(records)>200:raise ValueError('云端记录超过 200 份，请在云端窗口按文件夹查看')
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        store.rclone(['copy','gamecloud:'+folder,temporary,'--include','*.zip.json','--max-depth','4','--max-size','64k','--transfers','2'])
        for row in records:
            relative=row['remote'][len('gamecloud:'+folder+'/'):]
            file=Path(temporary)/(relative+'.json')
            if file.is_file():
                try:
                    metadata=json.loads(file.read_text(encoding='utf-8'))
                    row.update({key:metadata.get(key,row.get(key,'')) for key in ('created_at','note','computer','sha256','game_id','game_name','platform','external_id')})
                    row['verified']=bool(row.get('sha256'))
                except (ValueError,OSError):pass
    return sorted(records,key=lambda row:row['created_at'],reverse=True)
def receive(store,ident,record):
    if not store.local.get(ident,{}).get('save_dir'):raise ValueError('请先设置此电脑的存档目录')
    # Paths supplied by the UI must remain beneath this game's configured cloud folder.
    prefix='gamecloud:'+folder_path(store.settings['cloud_folder'])+'/'+game_folder(store.games,ident)+'/'
    remote=record['remote']
    if not remote.startswith(prefix) or '..' in PurePosixPath(remote[len(prefix):]).parts or '\\' in remote:raise ValueError('云端记录路径无效')
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        downloaded=Path(temporary)/'download.zip';store.rclone(['copyto',remote,str(downloaded)])
        sha=digest(downloaded)
        if record.get('sha256') and sha!=record['sha256']:raise ValueError('下载文件校验失败，未恢复')
        with zipfile.ZipFile(downloaded) as zipped:
            if zipped.testzip() or not any(name.startswith('save/') for name in zipped.namelist()):raise ValueError('云端备份损坏')
            info=zipped.getinfo('_snapshot_meta.json')
            if info.file_size>65536:raise ValueError('备份元数据过大')
            meta=json.loads(zipped.read(info))
            if any('..' in PurePosixPath(name.replace('\\','/')).parts or name.startswith(('/','\\')) or ':' in name for name in zipped.namelist()):raise ValueError('备份包含无效路径')
        game=next(game for game in store.games if game['id']==ident)
        if meta.get('game')!=ident:
            if record.get('game_name')!=game['name'] or not record.get('sha256'):raise ValueError('备份属于其他游戏，未导入')
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
