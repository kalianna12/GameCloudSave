"""Bounded local verification of model aliases and directory suggestions."""
from difflib import SequenceMatcher
import os
from pathlib import Path
import re
import time

SAVE_TYPES={'.sav','.save','.dat','.json','.slot','.profile','.bin','.rpgsave','.rvdata2','.lsv','.sl2'}

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
        for file in path.iterdir():
            if file.is_file() and file.suffix.casefold() in SAVE_TYPES:
                files.append(file.name)
                if len(files)>=30: break
            elif file.is_dir() and len(files)<30:
                try:
                    for nested in list(file.iterdir())[:100]:
                        if nested.is_file() and nested.suffix.casefold() in SAVE_TYPES:
                            files.append(file.name+'/'+nested.name)
                            if len(files)>=30: break
                except OSError: pass
    except OSError: pass
    return files

def scan(title, local, identity=None, root_override=None):
    identity=identity or {'english_name':'','aliases':[],'hints':[],'note':''}
    roots=root_override or roots_for(local)
    aliases=list(dict.fromkeys([title,identity['english_name'],*identity['aliases'],Path(local.get('install_dir','')).name]))
    names=[normalize(name) for name in aliases if len(normalize(name))>=4]
    found={}; checked=[]
    def add(path, confidence, reason, origin):
        try:
            if not path.is_dir(): return
        except OSError: return
        value=str(path.resolve())
        files=inspect_directory(path)
        confidence=min(.97,confidence+(0.08 if any(Path(f).suffix.casefold() in ('.sav','.save','.lsv','.rpgsave','.sl2') for f in files) else 0))
        candidate={'path':value,'confidence':round(confidence,2),'reason':reason,'source':origin,'files':files,
                   'fileSummary':', '.join(files[:6]) or '该层未发现常见存档文件，请检查子目录'}
        if value not in found or found[value]['confidence']<confidence: found[value]=candidate
    for hint in identity['hints']:
        root=roots.get(hint['root'])
        if root is None: continue
        candidate=(root/hint['relative']).resolve()
        if not candidate.is_relative_to(root.resolve()): continue
        exists=candidate.is_dir()
        checked.append({'path':str(candidate),'exists':exists,'reason':hint['reason']})
        if exists: add(candidate,.8,hint['reason']+'；已确认目录存在','DeepSeek 建议 + 本地验证')
    deadline=time.monotonic()+5
    for kind,root in roots.items():
        if not root.is_dir(): continue
        if kind=='install':
            for name in ('save','saves','savedata','SaveData','Saved','userdata','www/save','game/saves'):
                add(root/name,.78,'游戏安装目录中的常见存档位置','本地规则')
            continue
        try: children=list(root.iterdir())[:1500]
        except OSError: continue
        for child in children:
            if time.monotonic()>deadline: break
            if not child.is_dir(): continue
            normalized=normalize(child.name)
            confidence=max((.82 if normalized==name else .68 if len(normalized)>=5 and (name in normalized or normalized in name) else .6 if SequenceMatcher(None,normalized,name).ratio()>.85 else 0 for name in names),default=0)
            if confidence: add(child,confidence,'目录名与游戏名称或别名匹配','本地规则')
            if normalized in ('mygames','savedgames','larianstudios','cdprojektred','fromsoftware','rockstargames') or confidence:
                try:
                    for nested in list(child.iterdir())[:120]:
                        if nested.is_dir() and any(name in normalize(nested.name) or normalize(nested.name)==name for name in names):
                            add(nested,.78,'发布商/游戏目录下的名称匹配','本地规则')
                except OSError: pass
    ordered=sorted(found.values(),key=lambda c:-c['confidence'])[:30]
    return ordered,checked
