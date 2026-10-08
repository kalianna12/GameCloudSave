"""Apply only verified save evidence, then persist each stage of the workflow."""
from pathlib import Path
import json

STRONG={'.sav','.save','.sl2','.lsv','.rpgsave','.rvdata2','.celeste','.ksd','.es3','.nson'}
GENERIC={'renpy','documents','my games','saved games','appdata','local','roaming','locallow','packages'}

def evidence(candidate):
    path=Path(candidate['path'])
    if not path.is_dir() or path.name.casefold() in GENERIC: return False
    from save_groups import slot_name
    try:
        slots=[child for child in path.iterdir() if child.is_dir() and slot_name(child.name) and not child.name.casefold().startswith('backup')]
        if len(slots)>=2:
            for child in slots:
                for name in ('GameData.json','Flags.json','SaveData.json'):
                    file=child/name
                    if file.is_file() and file.stat().st_size<512000:
                        if (child/'GameData.json').is_file() and (child/'Flags.json').is_file():
                            with file.open('rb') as stream:
                                if stream.read(5)==b'ENC1:':return True
                        data=json.loads(file.read_text(encoding='utf-8-sig'))
                        if isinstance(data,(dict,list)) and data:return True
    except (OSError,ValueError):pass
    for name in candidate.get('files',[]):
        file=(path/name).resolve()
        if not file.is_relative_to(path.resolve()) or not file.is_file(): continue
        if file.suffix.casefold() in STRONG: return True
        if file.suffix.casefold()=='.dat' and any(word in file.stem.casefold() for word in ('save','slot','progress','persistentgamedata')): return True
        if file.suffix.casefold()=='.json' and file.stat().st_size<512000:
            try:
                data=json.loads(file.read_text(encoding='utf-8-sig'))
                if isinstance(data,dict) and any(k.casefold() in ('progress','chapter','quests','inventory','checkpoints','进度','章节') for k in data): return True
            except (OSError,ValueError): pass
    return False

def select_candidate(result):
    eligible=[c for c in result.get('candidates',[]) if c.get('confidence',0)>=.78 and evidence(c)]
    from save_groups import complete_directory
    original=eligible
    # Combine sibling slots, but avoid selecting a game root containing Demo and Release together.
    eligible=[c for c in original if not any(
        other['path']!=c['path'] and (
            Path(c['path']).resolve().is_relative_to(Path(other['path']).resolve()) and complete_directory(other['path']).resolve()==complete_directory(c['path']).resolve()
            or Path(other['path']).resolve().is_relative_to(Path(c['path']).resolve()) and complete_directory(other['path']).resolve()!=Path(c['path']).resolve()
        ) for other in original)]
    if not eligible: return None
    eligible.sort(key=lambda c:-c['confidence'])
    if len(eligible)>1 and eligible[0]['confidence']-eligible[1]['confidence']<.12: return None
    return eligible[0]

def run_workflow(store,idents,progress,cancel,upload=True):
    from save_groups import complete_directory
    if upload and not store.settings.get('cloud_folder','').strip(): raise ValueError('请先在云端存储窗口验证并保存统一存储文件夹')
    reports={r['id']:r for r in store.match_report}
    occupied={str(complete_directory(v['save_dir']).resolve()).casefold():ident for ident,v in store.local.items() if v.get('save_dir')}
    totals={'uploaded':0,'local_only':0,'review':0,'failed':0}
    prepared=[]
    for ident in dict.fromkeys(idents):
        if cancel.is_set(): break
        game=next((g for g in store.games if g['id']==ident),None)
        if game is None: continue
        row={'id':ident,'name':game['name'],'status':'running','message':'查找并验证存档目录…','candidates':[],'checked':[],'aliases':[],'english_name':'','note':''}
        progress(row)
        try:
            result=store.match_game(ident)
            result['upload_requested']=upload
            candidate=select_candidate(result)
            manual=store.local.get(ident,{}).get('save_dir','')
            from save_groups import complete_directory
            path=str(complete_directory(manual).resolve()) if manual and Path(manual).is_dir() else str(complete_directory(candidate['path']).resolve()) if candidate else ''
            if not path or path.casefold() in occupied and occupied[path.casefold()]!=ident:
                row={**result,'status':'review','message':'需要集中核对：目录证据不足、存在多个候选或与其他游戏共用目录'}
                totals['review']+=1
            else:
                row={**result,'status':'ready','applied_path':path,'message':'目录验证完成，等待批量冲突检查后自动备份'}
                prepared.append((ident,path,row))
        except Exception as error:
            row={**row,'status':'failed','message':str(error) if isinstance(error,ValueError) else '处理失败，请检查目录权限'}; totals['failed']+=1
        reports[ident]=row; store.save_match_report(list(reports.values())); progress(row)
    for ident,path,result in prepared:
        if cancel.is_set():break
        row=result
        try:
            if sum(other.casefold()==path.casefold() for _,other,_ in prepared)>1:
                row={**row,'status':'review','message':'多个游戏匹配到同一目录，已集中留待核对，未自动备份'}; totals['review']+=1
            else:
                store.save_game(ident,{'save_dir':path}); occupied[path.casefold()]=ident
                row={**result,'status':'saving','applied_path':path,'message':'已自动配置，正在创建本地快照…'}; progress(row)
                archive=store.backup(ident)
                row={**row,'archive_path':str(archive),'status':'local_only','message':'本地快照已保存'}
                if upload:
                    progress({**row,'status':'uploading','message':'本地已保存，正在上传统一云端目录…'})
                    try:
                        store.upload(ident,archive)
                        row={**row,'status':'uploaded','message':'自动配置 → 本地备份 → 云端上传完成'}; totals['uploaded']+=1
                    except Exception as error:
                        row={**row,'status':'local_only','message':'本地备份已保留；'+(str(error) if isinstance(error,ValueError) else '上传失败')+'，可批量补传'}; totals['local_only']+=1
                else: totals['local_only']+=1
        except Exception as error:
            row={**row,'status':'failed','message':str(error) if isinstance(error,ValueError) else '处理失败，请检查目录权限'}; totals['failed']+=1
        reports[ident]=row; store.save_match_report(list(reports.values())); progress(row)
    return totals
