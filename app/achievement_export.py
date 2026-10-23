"""Export definitions and cached icons to the application's own export directory."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,json,re


def export_definitions(schema,appid,directory,icon_path):
    if not re.fullmatch(r'[1-9]\d{0,11}',str(appid)):raise ValueError('导出兼容定义包需要明确的 Steam App ID')
    if any(row.get('match_mode')=='title' for row in schema):raise ValueError('此来源缺少内部 ID，请先匹配带内部 ID 的定义再导出')
    target=Path(directory)/str(appid)/'steam_settings';images=target/'img';images.mkdir(parents=True,exist_ok=True)
    rows=[];copied=0
    for row in schema:
        source=icon_path(row);relative=''
        if source:
            source=Path(source)
            if source.is_file() and source.stat().st_size<=1024*1024:
                ext=Path(urlsplit(row.get('icon','')).path).suffix.lower()
                if ext not in ('.jpg','.jpeg','.png','.webp'):ext='.img'
                filename=hashlib.sha256(row['id'].encode()).hexdigest()[:24]+ext
                destination=images/filename;destination.write_bytes(source.read_bytes());relative='img/'+filename;copied+=1
        rows.append(dict(name=row['id'],displayName=row['name'],description=row.get('description',''),hidden='1' if row.get('hidden') else '0',icon=relative,icongray=relative))
    if not rows:raise ValueError('尚无可导出的成就定义')
    output=target/'achievements.json';output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (target.parent/'说明.txt').write_text('此包仅包含成就定义和已缓存图标，不包含运行库或解锁记录。\n适用于已经支持 steam_settings/achievements.json 的兼容运行环境。\n本程序不会自动改动游戏文件；普通游戏或不同运行环境不一定使用此格式。\n即使匹配定义成功，也需游戏实际输出记录后才能监听解锁。\n',encoding='utf-8')
    return dict(path=str(target.parent),count=len(rows),icons=copied)
