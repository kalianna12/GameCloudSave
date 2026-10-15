"""Read existing Playnite media only; never start Playnite or fetch metadata here.

Extra Metadata Loader's documented local layout is ExtraMetadata/games/{guid}/
VideoTrailer.mp4. Its SteamAppDetails cache also provides streaming trailers.
Discovery runs once on a worker; URLs are handed to the player only on request.
"""
from pathlib import Path
import json
import uuid
from urllib.parse import urlsplit
from PySide6.QtCore import QUrl

PLUGIN='705fdbca-e1fc-4004-b839-1d040b8b4429'

def _json(path):
    try:
        if not path.is_file() or path.stat().st_size>4_000_000:return {}
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def _remote(value):
    if not isinstance(value,str):return ''
    try:parsed=urlsplit(value)
    except ValueError:return ''
    return value if parsed.scheme=='https' and parsed.hostname and not parsed.username and len(value)<4096 else ''

def _file(path):
    try:return QUrl.fromLocalFile(str(path.resolve())).toString() if path.is_file() else ''
    except (OSError,ValueError):return ''

def discover(settings,games):
    library=Path(settings.get('library') or '.')
    # Both installed and portable Playnite put these directories beside library.
    config=library.parent
    cache=config/'ExtensionsData'/PLUGIN
    extras=config/'ExtraMetadata/games'
    result={};by_steam={};by_guid={}
    # Bound the optional cache pass and avoid traversing unrelated plugin data.
    for path in sorted(cache.glob('*_SteamAppDetails.json'))[:2000]:
        key=path.name.removesuffix('_SteamAppDetails.json')
        try:key=str(uuid.UUID(key))
        except ValueError:continue
        raw=_json(path)
        for appid,entry in raw.items():
            if not isinstance(entry,dict) or not entry.get('success'):continue
            data=entry.get('data',{})
            if not isinstance(data,dict):continue
            media={}
            background=_remote(data.get('background_raw')) or _remote(data.get('background')) or _remote(data.get('header_image'))
            if background:media['backgroundUrl']=background
            movies=data.get('movies') or []
            if not isinstance(movies,list):movies=[]
            for movie in sorted((m for m in movies if isinstance(m,dict)),key=lambda m:not m.get('highlight')):
                url=''
                for field in ('mp4','webm'):
                    formats=movie.get(field,{})
                    if isinstance(formats,dict):url=_remote(formats.get('480')) or _remote(formats.get('max'))
                    if url:break
                url=url or _remote(movie.get('hls_h264')) or _remote(movie.get('dash_h264'))
                if url:media.update(videoUrl=url,videoSource='Playnite · Steam',videoRemote=True);break
            if media:by_guid[key]=media;by_steam[str(appid)]=media
    for game in games:
        ident=str(game['id']);media=dict(by_guid.get(ident) or by_steam.get(str(game.get('steam_appid') or game.get('metadata_steam_appid') or '')) or {})
        # A local backdrop takes priority over a cached remote image.
        if game.get('background'):
            local=_file(Path(game['background']))
            if local:media['backgroundUrl']=local
        try:guid=str(uuid.UUID(ident))
        except ValueError:guid=''
        if guid:
            video=extras/guid/'VideoTrailer.mp4'
            if not video.is_file():video=extras/guid/'VideoMicrotrailer.mp4'
            if video.is_file():media.update(videoUrl=_file(video),videoSource='Playnite · 本地',videoRemote=False)
            # Read Playnite's exported background relative to its files root when present.
            relative=game.get('playnite_background','')
            if relative:
                remote=_remote(relative)
                if remote:media['backgroundUrl']=remote
                else:
                    try:
                        source=(library/'files'/relative).resolve()
                        if source.is_relative_to((library/'files').resolve()):
                            local=_file(source)
                            if local:media['backgroundUrl']=local
                    except (OSError,ValueError):pass
        if media:result[ident]=media
    return result
