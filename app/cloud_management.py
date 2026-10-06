"""Copy old flat ZIP backups into named folders without deleting existing backups."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
import time
import zipfile
from cloud_paths import folder_path

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def download(store,source,destination,values):
    for attempt in range(3):
        try:
            store.rclone(['copyto',source,str(destination)],values=values)
            return
        except ValueError:
            if attempt==2: raise
            time.sleep(0.6*(attempt+1))

def organize(store,ident,old_folder,values=None):
    if not any(g['id']==ident for g in store.games): raise ValueError('请选择 Playnite 游戏')
    old_folder=folder_path(old_folder)
    if not old_folder: raise ValueError('请选择旧备份文件夹')
    entries=store.rclone('list',old_folder,values)
    archives=[entry for entry in entries if not entry['IsDir'] and entry['Name'].lower().endswith('.zip')]
    if not archives: raise ValueError('该目录没有旧版 ZIP 备份')
    records=[]
    report=store.profile/'cloud-organize-report.json'
    from services import write_json,read_json
    previous=read_json(report,[])
    with tempfile.TemporaryDirectory(dir=store.profile) as temporary:
        temporary=Path(temporary)
        for entry in archives:
            name=entry['Name']
            if '/' in name or '\\' in name: raise ValueError('无效备份文件名')
            source='gamecloud:'+old_folder+'/'+name
            local=temporary/name
            download(store,source,local,values)
            with zipfile.ZipFile(local) as zipped:
                try: info=zipped.getinfo('_snapshot_meta.json')
                except KeyError: raise ValueError('备份缺少存档目录信息，旧文件保持原位') from None
                if info.file_size>65536: raise ValueError('备份元数据过大')
                metadata=json.loads(zipped.read(info))
                if not metadata.get('save_dir') or zipped.testzip(): raise ValueError('备份不完整，旧文件保持原位')
                # UUID metadata must agree. Old custom names are explicitly assigned by the user.
                import uuid
                try: metadata_id=str(uuid.UUID(metadata.get('game','')))
                except (ValueError,AttributeError): metadata_id=''
                if metadata_id and metadata_id!=ident: raise ValueError('备份属于另一款游戏，请重新选择')
            destination=store.cloud_directory(ident,metadata['save_dir'],values)
            target='gamecloud:'+destination+'/'+name
            if target==source: continue
            try: existing=store.rclone('list',destination,values)
            except ValueError as error:
                if '目录或文件暂不可用' not in str(error): raise
                existing=[]
            if not any(entry['Name']==name for entry in existing):
                store.rclone(['copyto',str(local),target,'--immutable'],values=values)
            verified=temporary/('verify-'+name)
            # Existing destinations are read and verified, never overwritten.
            download(store,target,verified,values)
            if digest(local)!=digest(verified): raise ValueError('云端文件校验未通过，旧备份保持原位')
            records.append({'source':source,'target':target,'sha256':digest(local),'game_id':ident})
            # Save progress after each verified file, so partial operations remain reviewable.
            replaced={record['source'] for record in records}
            write_json(report,[record for record in previous if record['source'] not in replaced]+records)
            with closing(store.core().connect_db()) as connection:
                connection.execute('UPDATE snapshots SET cloud_ref=? WHERE cloud_ref=?',(target,source))
                connection.commit()
    return f'已整理 {len(records)} 份备份并核对完整性；旧备份保留原位'
