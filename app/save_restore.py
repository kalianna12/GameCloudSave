"""Inspect first, explicitly map accounts, stage restore and roll back failed swaps."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile

from save_groups import account_name, slot_name, SHARED


def slot_member(name, slot):
    return name == slot or (name.startswith(slot) and name[len(slot):len(slot)+1] in ('/', '_', '.', '-', ' '))


def archive_info(path):
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        for entry in archive.infolist():
            name=entry.filename
            if ('..' in PurePosixPath(name.replace('\\','/')).parts or name.startswith(('/','\\'))
                    or ':' in name or '\\' in name or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('备份包含无效路径或链接')
        if archive.testzip() or not any(name.startswith('save/') for name in names):
            raise ValueError('备份损坏或缺少存档内容')
        metadata={}
        if '_snapshot_meta.json' in names:
            info=archive.getinfo('_snapshot_meta.json')
            if info.file_size>65536:raise ValueError('备份元数据过大')
            metadata=json.loads(archive.read(info))
            if not isinstance(metadata,dict):raise ValueError('备份元数据无效')
            if not isinstance(metadata.get('save_dir',''),str) or not isinstance(metadata.get('identity',{}),dict):raise ValueError('备份身份或目录信息无效')
        files=[name[5:] for name in names if name.startswith('save/') and not name.endswith('/')]
        directories=[name[5:].rstrip('/') for name in names if name.startswith('save/') and name.endswith('/') and name!='save/']
    return metadata,files,directories


def inspect(store,ident,snapshot):
    store.game(ident)
    row=next((row for row in store.history(ident) if row['id']==snapshot),None)
    if row is None:raise ValueError('快照不属于当前游戏')
    archive=Path(row['archive_path'])
    if not archive.is_file():raise ValueError('本地快照文件不存在')
    with archive.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    if row.get('sha256') and row['sha256']!=sha:raise ValueError('备份校验失败，未恢复')
    metadata,files,dirs=archive_info(archive)
    if not files:raise ValueError('备份中没有可恢复的存档文件')
    configured=Path(store.local[ident]['save_dir'])
    if configured.is_symlink() or getattr(configured,'is_junction',lambda:False)():raise ValueError('请选择实际存档目录，不能恢复到链接')
    current=configured.resolve()
    game_steam=current.name.casefold()=='steam' and current.parent.parent.name.casefold() in ('roaming','local','locallow','saved games')
    if (current.name.casefold() in SHARED and not game_steam) or current==current.parent:raise ValueError('请选择游戏专用存档目录，不能恢复到共享根目录')
    if Path(store.settings['snapshots']).resolve().is_relative_to(current):raise ValueError('备份目录不能位于待恢复的游戏目录内')
    original=PureWindowsPath(str(metadata.get('save_dir','')))
    top={PurePosixPath(name).parts[0] for name in files+dirs if name}
    accounts=sorted(name for name in top if account_name(name))
    legacy_account=account_name(original.name) and not accounts
    if legacy_account:accounts=[original.name]
    targets=sorted(child.name for child in current.iterdir() if child.is_dir() and not child.is_symlink() and account_name(child.name))
    slots=set()
    for name in files+dirs:
        parts=PurePosixPath(name).parts
        for index,part in enumerate(parts):
            if index<len(parts)-1 and slot_name(part):slots.add('/'.join(parts[:index+1]))
        if parts:
            match=re.match(r'(SaveGame\d+)(?:[_ .-])',parts[-1],re.I)
            if match:slots.add('/'.join((*parts[:-1],match[1])))
    needs_mapping=bool(accounts and any(account not in targets for account in accounts) and targets)
    return {'ident':ident,'snapshot':snapshot,'archive':str(archive),'sha256':sha,'target':str(current),
            'source_accounts':accounts,'target_accounts':targets,'needs_mapping':needs_mapping,
            'legacy_account':legacy_account,'original':str(original),'slots':sorted(slots),
            'files':files,'directories':dirs,'file_count':len(files)}


def restore(store,ident,snapshot,options=None):
    options=options or {};plan=inspect(store,ident,snapshot)
    current=Path(plan['target']);source_account=options.get('source_account','');target_account=options.get('target_account','')
    slot=options.get('slot','')
    if slot and slot not in plan['slots']:raise ValueError('所选存档槽不在此备份中')
    if source_account or target_account:
        if source_account not in plan['source_accounts'] or target_account not in plan['target_accounts']:
            raise ValueError('请选择备份账号与此电脑的目标账号')
        if slot and not plan['legacy_account'] and not slot.startswith(source_account+'/'):
            raise ValueError('所选存档槽不属于选择的备份账号')
    elif plan['needs_mapping']:
        raise ValueError('备份与本机账号目录不同，请在恢复预览中选择账号映射')
    original=PureWindowsPath(plan['original']);legacy_slot=''
    if not plan['source_accounts'] and slot_name(original.name) and not slot_name(current.name):
        if original.parent.name.casefold()!=current.name.casefold():raise ValueError('这是旧版单存档备份，请选择对应存档槽目录后恢复')
        legacy_slot=original.name
    # Reject links in the destination before copytree can follow them.
    for item in (current,*current.rglob('*')):
        if item.is_symlink() or getattr(item,'is_junction',lambda:False)():raise ValueError('存档目录包含链接，请选择实际目录后恢复')
    with tempfile.TemporaryDirectory(prefix='.gamecloud-restore-',dir=current.parent) as temporary:
        stage=Path(temporary);extracted=stage/'incoming';prepared=stage/'prepared'
        extracted.mkdir()
        with zipfile.ZipFile(plan['archive']) as archive:
            for name in archive.namelist():
                if name.startswith('save/'):archive.extract(name,extracted)
        incoming=extracted/'save'
        scoped=bool(slot or source_account or legacy_slot or plan['legacy_account'])
        if scoped:shutil.copytree(current,prepared)
        else:shutil.copytree(incoming,prepared)
        if scoped:
            source_prefix=source_account if source_account and not plan['legacy_account'] else ''
            destination_prefix=target_account or (original.name if plan['legacy_account'] else legacy_slot)
            src=incoming/source_prefix;dest=prepared/destination_prefix
            if slot:
                relative=slot[len(source_prefix)+1:] if source_prefix else slot
                candidates=[name for name in plan['files'] if slot_member(name,slot)]
                if not candidates:raise ValueError('此存档槽没有可恢复的文件')
                # Replace this slot only; retain other slots and common settings.
                target_slot=dest/relative
                if target_slot.is_dir():shutil.rmtree(target_slot)
                elif target_slot.is_file():target_slot.unlink()
                elif target_slot.parent.is_dir():
                    for old in target_slot.parent.iterdir():
                        if old.is_file() and slot_member(old.name,target_slot.name):old.unlink()
                for name in candidates:
                    source=incoming/name;relative_name=name[len(source_prefix)+1:] if source_prefix else name
                    output=dest/relative_name;output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,output)
            else:
                if dest.exists():shutil.rmtree(dest)
                shutil.copytree(src,dest)
        backup=current.parent/(current.name+'.before-restore.'+store.core().now_file_ts())
        shutil.copytree(current,backup)
        previous=stage/'previous'
        current.rename(previous)
        try:prepared.rename(current)
        except Exception:
            previous.rename(current)
            raise
    return {'backup':str(backup),'files':plan['file_count']}
