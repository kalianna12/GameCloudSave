"""Bounded local verification of model aliases and directory suggestions."""
from difflib import SequenceMatcher
import os
from pathlib import Path
import re
import time

SAVE_TYPES={'.sav','.save','.dat','.json','.slot','.profile','.bin','.rpgsave','.rvdata2','.lsv','.sl2','.celeste','.ksd','.es3'}

def roots_for(local):
    documents=Path.home()/'Documents'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
            documents=Path(winreg.QueryValueEx(key,'Personal')[0])
    except OSError: pass
    roots={'local':Path(os.environ['LOCALAPPDATA']), 'roaming':Path(os.environ['APPDATA']),
           'locallow':Path.home()/'AppData/LocalLow','documents':documents,'savedgames':Path.home()/'Saved Games'}
    if local.get('install_dir'): roots['install']=Path(local['install_dir'])
    return roots

def normalize(name): return re.sub(r'[^\w]','',name.casefold())

def inspect_directory(path):
    files=[]
    try:
        from collections import deque
        from itertools import islice
        queue=deque([(path,0)]);visited=0
        while queue and len(files)<30 and visited<400:
            parent,depth=queue.popleft()
            try:
                for file in islice(parent.iterdir(),100):
                    visited+=1
                    if file.is_symlink() or not file.resolve().is_relative_to(path.resolve()):continue
                    if file.is_file() and file.suffix.casefold() in SAVE_TYPES:files.append(file.relative_to(path).as_posix())
                    elif file.is_dir() and depth<2:queue.append((file,depth+1))
                    if len(files)>=30 or visited>=400:break
            except OSError:pass
    except OSError: pass
    return files

def scan(title, local, identity=None, root_override=None,cancel=None):
    identity=identity or {'english_name':'','aliases':[],'hints':[],'note':''}
    roots=root_override or roots_for(local)
    aliases=list(dict.fromkeys([title,identity.get('english_name',''),*identity.get('aliases',[]),Path(local.get('install_dir','')).name]))
    names=[normalize(name) for name in aliases if len(normalize(name))>=4]
    found={}; checked=[]
    def add(path, confidence, reason, origin):
        try:
            if not path.is_dir(): return
        except OSError: return
        from save_groups import complete_directory
        complete=complete_directory(path)
        if complete!=path:
            reason+='；包含多个存档槽，备份整个父目录'
            path=complete
        value=str(path.resolve())
        files=inspect_directory(path)
        developer_names=[normalize(name) for name in identity.get('developers',[])+identity.get('publishers',[]) if name]
        developer_match=any(normalize(part) in developer_names for part in path.parts)
        from save_workflow import evidence
        strong=evidence({'path':value,'files':files})
        confidence=min(.97,confidence+(0.08 if strong else 0)+(0.05 if developer_match else 0))
        candidate={'path':value,'confidence':round(confidence,2),'reason':reason,'source':origin,'files':files,
                   'fileSummary':', '.join(files[:6]) or '该层未发现常见存档文件，请检查子目录',
                   'score_details':{'developer_match':developer_match,'strong_files':strong},'verified':bool(files)}
        for kind,root in roots.items():
            if path.resolve().is_relative_to(root.resolve()):
                candidate['root']=kind;candidate['relative']=path.resolve().relative_to(root.resolve()).as_posix();break
        if value not in found or found[value]['confidence']<confidence: found[value]=candidate
    for hint in identity.get('hints',[]):
        root=roots.get(hint['root'])
        if root is None: continue
        candidate=(root/hint['relative']).resolve()
        if not candidate.is_relative_to(root.resolve()): continue
        exists=candidate.is_dir()
        checked.append({'path':str(candidate),'exists':exists,'reason':hint['reason']})
        if exists: add(candidate,.8,hint['reason']+'；已确认目录存在','DeepSeek 建议 + 本地验证')
    from local_index import directories
    from concurrent.futures import ThreadPoolExecutor
    name_scores={}
    def name_score(normalized):
        if normalized not in name_scores:
            name_scores[normalized]=max((.82 if normalized==name else .70 if len(normalized)>=5 and (name in normalized or normalized in name) else .62 if SequenceMatcher(None,normalized,name).ratio()>.86 else 0 for name in names),default=0)
        return name_scores[normalized]
    with ThreadPoolExecutor(max_workers=min(6,max(1,len(roots)))) as pool:
        indexed=list(pool.map(lambda item:(item[0],item[1],directories(item[1],cancel=cancel)),roots.items()))
    for kind,root,paths in indexed:
        if cancel and cancel.is_set():break
        if kind=='install':
            for relative in ('save','saves','savedata','SaveData','Saved/SaveGames','Saved','userdata','www/save','game/saves'):
                add(root/relative,.78,'游戏安装目录中的常见存档位置','本地规则')
        for child in paths:
            if cancel and cancel.is_set():break
            parts=child.relative_to(root).parts
            if any(part.casefold() in ('unity','shadervariantanalytics','monobleedingedge','managed','d3d12') or part.casefold().endswith('_data') for part in parts):continue
            normalized_parts=[normalize(part) for part in parts]
            confidence=max((name_score(normalized) for normalized in normalized_parts),default=0)
            container=child.name.casefold() in ('release','save','saves','savedata','savegames','saved','userdata','profiles')
            if kind=='install' and not container and not re.search(r'save|存档',child.name.casefold()):continue
            if confidence:
                add(child,confidence+(.03 if container else 0),'游戏名称/别名匹配'+('，已定位存档容器' if container else ''),'本地模糊搜索')
            elif kind=='install' and re.search(r'save|存档',child.name.casefold()):
                add(child,.83,'安装目录中带存档标识的文件夹，已核查文件','本地规则')
    ordered=sorted(found.values(),key=lambda c:-c['confidence'])[:30]
    return ordered,checked
