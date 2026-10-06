"""Readable DAV paths; Playnite IDs remain internal database identifiers."""
from pathlib import PureWindowsPath
import re

def component(name):
    replacements=dict(zip('<>:"/\\|?*','＜＞：＂／＼｜？＊'))
    value=''.join(replacements.get(c,c) for c in str(name) if ord(c)>=32).strip().rstrip('.')
    if not value or value in ('.','..'): value='未命名'
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',value,re.I):
        value = value + "_"
    if len(value)>120:
        import hashlib
        value=value[:110]+'-'+hashlib.sha256(value.encode()).hexdigest()[:8]
    return value

def folder_path(value):
    path=str(value).strip().replace('\\','/').strip('/')
    if any(part in ('.','..') for part in path.split('/')) or any(ord(c)<32 for c in path):
        raise ValueError('云端路径不能包含上级跳转或控制字符')
    return path

def game_folder(games,ident):
    game=next((g for g in games if g['id']==ident),None)
    if game is None: raise ValueError('游戏不在当前 Playnite 游戏库中')
    name=component(game['name'])
    if sum(component(g['name']).casefold()==name.casefold() for g in games)>1:
        name+=' ['+ident[:8]+']'
    return name

def save_folder(path):
    return component(PureWindowsPath(str(path)).name or '存档目录')

def directory(games,ident,save_dir,settings):
    root=folder_path(settings.get('cloud_folder',''))
    parts=[root,game_folder(games,ident),save_folder(save_dir)]
    if settings.get('cloud_separate_computer'): parts.append(component(settings.get('computer','本机')))
    return '/'.join(part for part in parts if part)
