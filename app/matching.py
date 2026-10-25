"""Bounded local verification of model aliases and directory suggestions."""
from difflib import SequenceMatcher
import os
from pathlib import Path
import re
import time

SAVE_TYPES={'.sav','.save','.dat','.json','.slot','.profile','.bin','.rpgsave','.rmmzsave','.rvdata','.rvdata2','.rxdata','.lsv','.sl2','.celeste','.ksd','.es3','.nson','.uberstate'}
GENERIC_INSTALL={'game','games','common','steamapps','bin','binaries','win64','x64','release','debug'}

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

def normalize(name): return re.sub(r'[\W_]','',name.casefold())

def numbered_title(name):
    match=re.search(r'(?:\s+([IVX]{1,5})|\s*([0-9]{1,2}))$',name.strip(),re.I)
    if not match:return normalize(name),None
    roman={'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}
    number=int(match[2]) if match[2] else roman.get(match[1].upper())
    return normalize(name[:match.start()]),number

def inspect_directory(path):
    files=[]
    try:
        from collections import deque
        from itertools import islice
        queue=deque([(path,0)]);visited=0
        while queue and visited<400:
            parent,depth=queue.popleft()
            try:
                for file in islice(parent.iterdir(),100):
                    visited+=1
                    if file.is_symlink() or not file.resolve().is_relative_to(path.resolve()):continue
                    if file.is_file() and file.suffix.casefold() in SAVE_TYPES:files.append(file.relative_to(path).as_posix())
                    elif file.is_dir() and depth<2:queue.append((file,depth+1))
                    if visited>=400:break
            except OSError:pass
    except OSError: pass
    from save_workflow import STRONG,re_configuration
    return sorted(files,key=lambda name:(re_configuration(Path(name).name),Path(name).suffix.casefold() not in STRONG,'save' not in name.casefold(),name))[:30]

def scan(title, local, identity=None, root_override=None,cancel=None):
    identity=identity or {'english_name':'','aliases':[],'hints':[],'note':''}
    roots=root_override or roots_for(local)
    installation=Path(local.get('install_dir',''))
    install_alias=installation.name if installation.name.casefold() not in GENERIC_INSTALL else ''
    executables=[]
    if local.get('exe'):executables.append(Path(local['exe']).stem)
    if local.get('install_dir') and installation.is_dir():
        from itertools import islice
        executables.extend(file.stem for file in islice(installation.glob('*.exe'),20))
    executables=[name for name in executables if normalize(name) not in GENERIC_INSTALL and not any(word in name.casefold() for word in ('launcher','setup','unins','crashhandler','update'))]
    aliases=list(dict.fromkeys([title,identity.get('english_name',''),*identity.get('aliases',[]),install_alias,*executables]))
    aliases.extend(base+str(number) for base,number in map(numbered_title,list(aliases)) if number is not None and base)
    names=[normalize(name) for name in aliases if len(normalize(name))>=3 and normalize(name) not in GENERIC_INSTALL.union({'save','saves','savedata','saved','savegames','userdata','profiles'})]
    version=re.search(r'(?:\s|[-_])(\d{1,2})$',title.strip())
    version_base=normalize(title[:version.start()]) if version else ''
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
        sample_backup=any(part.casefold() in ('补丁','patch','patches','crack') or any(word in part.casefold() for word in ('全cg','全通关','全要素','100%存档')) for part in path.parts)
        if sample_backup:
            confidence=min(confidence,.55);reason+='；附带补丁/示例存档，需手动核对'
        candidate={'path':value,'confidence':round(confidence,2),'reason':reason,'source':origin,'files':files,
                   'fileSummary':', '.join(files[:6]) or '该层未发现常见存档文件，请检查子目录',
                   'score_details':{'developer_match':developer_match,'strong_files':strong},'verified':bool(files),'has_save_evidence':strong,'sample_backup':sample_backup}
        candidate['evidence_version']=4
        for kind,root in roots.items():
            if path.resolve().is_relative_to(root.resolve()):
                candidate['root']=kind;candidate['relative']=path.resolve().relative_to(root.resolve()).as_posix();break
        if value not in found or found[value]['confidence']<confidence: found[value]=candidate
    import json
    from services import RESOURCES
    try:rules=json.loads((RESOURCES/'ui/save-rules.json').read_text(encoding='utf-8'))['rules']
    except (OSError,ValueError,KeyError):rules=[]
    rule_names={normalize(title),normalize(identity.get('english_name',''))}
    versions=[numbered_title(value) for value in (title,identity.get('english_name','')) if value]
    versions=[(base,number) for base,number in versions if number is not None and len(base)>=4 and base not in GENERIC_INSTALL]
    # Steam Cloud's per-app remote folder is keyed by AppID, not the game title.
    appid=str(local.get('_steam_appid',''))
    if root_override is None and re.fullmatch(r'\d{1,12}',appid):
        from library_sources import steam_roots
        from itertools import islice
        for steam in steam_roots():
            userdata=steam/'userdata'
            if not userdata.is_dir():continue
            try:
                for account in islice(userdata.iterdir(),100):
                    if cancel and cancel.is_set():break
                    if account.name.isdigit() and account.is_dir() and not account.is_symlink():
                        path=account/appid/'remote'
                        if path.resolve().is_relative_to(userdata.resolve()):
                            add(path,.9,'Steam AppID 精确匹配的云存档目录','Steam 本地存档')
                            key=str(path.resolve())
                            if key in found:found[key].update(root='steam_userdata',relative=account.name+'/'+appid+'/remote')
            except OSError:continue
    for rule in rules:
        root=roots.get(rule.get('root'))
        if root is None or not any(normalize(alias) in rule_names for alias in rule.get('aliases',[])):continue
        candidate=(root/rule['relative']).resolve()
        if not candidate.is_relative_to(root.resolve()):continue
        checked.append({'path':str(candidate),'exists':candidate.is_dir(),'reason':'已验证的游戏路径规则'})
        add(candidate,.89,'已验证路径规则 + 本地文件检查','路径规则')
        if rule.get('source_url'):
            from save_groups import complete_directory
            key=str(complete_directory(candidate).resolve())
            if key in found:found[key]['source_url']=rule['source_url']
    for hint in identity.get('hints',[]):
        root=roots.get(hint['root'])
        if root is None: continue
        from itertools import islice
        choices=list(islice(root.glob(hint['relative']),64)) if '*' in hint['relative'] and hint.get('verified_rule') else [root/hint['relative']]
        for candidate in choices:
            candidate=candidate.resolve()
            if not candidate.is_relative_to(root.resolve()): continue
            exists=candidate.is_dir()
            checked.append({'path':str(candidate),'exists':exists,'reason':hint['reason']})
            if exists:
                add(candidate,.92 if hint.get('verified_rule') else .8,hint['reason']+'；已确认目录存在','Steam 云存档配置' if hint.get('verified_rule') else '网页路径 + 本地验证' if hint.get('source_url') else '目录建议')
                from save_groups import complete_directory
                key=str(complete_directory(candidate).resolve())
                if key in found:
                    if hint.get('source_url'):found[key]['source_url']=hint['source_url']
                    if hint.get('verified_rule'):found[key]['verified_rule']=True
    from local_index import directories
    from concurrent.futures import ThreadPoolExecutor
    name_scores={}
    def name_score(normalized):
        if normalized in GENERIC_INSTALL or normalized in ('save','saves','savedata','saved','savegames','userdata','profiles'):return 0
        if normalized not in name_scores:
            def same_series(left,right):
                a=re.findall(r'\d+',left);b=re.findall(r'\d+',right)
                return not a or not b or a==b
            name_scores[normalized]=max((.82 if normalized==name else .76 if any(normalized==name+language for language in ('ch','chs','cht','cn','sc','tc','en','eng','jp','ja')) else .70 if min(len(name),len(normalized))>=5 and same_series(normalized,name) and (name in normalized or normalized in name) else .62 if same_series(normalized,name) and SequenceMatcher(None,normalized,name).ratio()>.86 else 0 for name in names),default=0)
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
            if any(part_base==base and part_number!=number for part_base,part_number in map(numbered_title,parts) for base,number in versions):continue
            if version and any(version_base in normalize(part) and (number:=re.search(r'(\d{1,2})$',part)) and number.group(1)!=version.group(1) for part in parts):continue
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
