"""Explicit user matches and edits join the same preview; never write the library."""
from copy import deepcopy
from pathlib import Path
import hashlib,shutil
from library_enrichment import missing,cover_path,cached_lookup
from library_sources import release_date
from tag_catalog import effective_tags,normalize_tags,vocabulary

def base(store,ident,previous=None):
    game=next((g for g in store.games if g['id']==ident),None)
    if game is None:raise ValueError('游戏已不存在')
    from library_artwork import existing
    row=deepcopy(previous) if previous else {'id':ident,'name':game['name'],'before':{'release_date':game.get('release_date',''),'category':game.get('category',''),'tags':effective_tags(game),'series':game.get('series','')},'before_cover':cover_path(store,game),'before_background':existing(store,game),'fields':{},'sources':{},'notes':[],'cover_name':''}
    row.update(applied=False,cancelled=False)
    return game,row,missing(store,game)

def candidate(store,ident,record,previous=None):
    from cover_sources import download
    from library_artwork import prepare
    game,row,needs=base(store,ident,previous);data={}
    if record.get('provider')=='vndb':
        data={'release_date':release_date(record.get('released')),'release_date_source':'VNDB（首次发行）','background_url':record.get('background_url'),'background_source':'VNDB 截图'}
    elif record.get('appid'):
        data=cached_lookup(store,{**game,'name':record['name'],'steam_appid':'','metadata_steam_appid':record['appid']})
        row['metadata_steam_appid']=record['appid']
    def offer(key,value,source):
        if needs.get(key) and value:row['fields'][key]=value;row['sources'][key]=source
    for key in ('release_date','tags'):offer(key,data.get(key),data.get(key+'_source',record.get('provider','资料库')))
    if data.get('tags'):
        from library_catalog import primary
        category=primary(data['tags'])
        if category!='其他':offer('category',category,data.get('tags_source','资料库'))
    if needs['cover'] and record.get('image'):
        try:offer('cover',download(store,record),record.get('provider','资料库'));row['cover_name']=record['name']
        except ValueError:row['notes'].append('封面下载失败，可改用图片链接或本地图片')
    if needs['background'] and data.get('background_url'):
        try:offer('background',prepare(store,data['background_url']),data.get('background_source','资料库'))
        except Exception:row['notes'].append('横幅下载失败，可改用图片链接或本地图片')
    row.update(matched_name=record['name'],metadata_url=data.get('metadata_url') or record.get('page',''))
    row['notes']=['已手动选择资料匹配',*dict.fromkeys(row['notes'][-2:])]
    return row

def values(store,ident,fields,previous=None):
    from library_artwork import prepare
    from cover_sources import download
    from library_catalog import CATEGORIES
    game,row,needs=base(store,ident,previous)
    for key,value in fields.items():
        if not needs.get(key) or not value:continue
        if key=='release_date':
            value=release_date(value)
            if not value:raise ValueError('请输入有效日期，格式为 YYYY-MM-DD')
        elif key=='category':
            if value not in [*CATEGORIES,*store.groups] or value=='其他':continue
        elif key=='tags':value=normalize_tags(value,vocabulary([]))[:6]
        elif key=='series':
            if not isinstance(value,str) or len(value)>80:raise ValueError('系列名称最多 80 字')
            value=value.strip()
        elif key=='background':value=prepare(store,value,user_authorized=True)
        elif key=='cover':
            if value.startswith(('http://','https://')):
                value=download(store,{'id':'manual:'+hashlib.sha256(value.encode()).hexdigest(),'image':value,'user_authorized':True})
            else:
                from PySide6.QtGui import QImageReader
                path=Path(value)
                if not path.is_file() or path.stat().st_size>12*1024*1024:raise ValueError('请选择小于 12 MB 的图片')
                reader=QImageReader(str(path));size=reader.size();del reader
                if not size.isValid() or max(size.width(),size.height())>8192:raise ValueError('无法读取这张封面')
                folder=store.root/'covers';folder.mkdir(exist_ok=True)
                target=folder/('manual-'+hashlib.sha256(path.read_bytes()).hexdigest()[:24]+'.jpg')
                if path.resolve()!=target.resolve():shutil.copyfile(path,target)
                value=str(target)
        else:continue
        if value:row['fields'][key]=value;row['sources'][key]='手动'
    row['notes']=['手动补全，应用后保存']
    return row
