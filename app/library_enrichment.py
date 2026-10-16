"""Preview source/AI enrichment; applying rechecks missing fields and never replaces data."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib,shutil,threading,time,json

from library_sources import release_date,guid,playnite_metadata
from tag_catalog import effective_tags,normalize_tags,vocabulary
from library_catalog import primary
from catalog_match import query_hints,search_queries,best_match

def cover_path(store,game):
    value=game.get('cover') or ''
    if value.startswith(('http://','https://')):return value
    if not value:return ''
    for path in [Path(value),store.root/'covers'/Path(value).name]:
        if path.is_file():return str(path.resolve())
    return ''

def missing(store,game):
    from library_artwork import existing
    return {
        'release_date':not game.get('release_date') and not game.get('release_date_manual'),
        'category':game.get('category') in (None,'','其他') and not game.get('category_manual'),
        'tags':not any(str(tag).strip() for tag in game.get('tags',[])) and not effective_tags(game) and not game.get('tags_manual'),
        'series':not game.get('series') and not game.get('series_manual'),
        'cover':not cover_path(store,game),'background':not existing(store,game)}

def cached_lookup(store,game):
    from library_metadata import lookup
    from services import read_json,write_json
    cache_file=store.root/'enrichment-metadata-cache.json'
    key=json.dumps(['titles-v3-artwork',game['name'],game.get('source_name'),game.get('aliases'),game.get('steam_appid'),game.get('metadata_steam_appid'),game.get('category'),effective_tags(game)],ensure_ascii=False)
    with store.match_lock:entry=read_json(cache_file,{}).get(key)
    if entry and time.time()-entry['time']<(86400 if entry['fields'].get('release_date') else 300):return entry['fields']
    fields=lookup(game)
    with store.match_lock:
        cache=read_json(cache_file,{});cache[key]={'time':time.time(),'fields':fields}
        write_json(cache_file,dict(list(cache.items())[-4000:]))
    return fields

def preview(store,idents=None,options=None,cancel=None,notify=lambda row,done,total,phase:None):
    from cover_sources import search,download
    from library_organizer import suggestions
    from services import safe_child
    from library_artwork import prepare as prepare_background,existing as existing_background
    options={**{'dates':True,'tags':True,'covers':True,'backgrounds':False,'use_ai':False},**(options or {})}
    cancel=cancel or threading.Event()
    games=deepcopy(store.games);known={game['id']:game for game in games}
    if idents and any(ident not in known for ident in idents):raise ValueError('游戏条目已不存在，请重新选择')
    targets=[game for game in games if not idents or game['id'] in idents]
    total=len(targets);notify(None,0,total,'正在读取现有资料')
    raw_by_id={};warnings=[]
    if any(options[key] for key in ('dates','tags','covers','backgrounds')) and any(game.get('import_source')=='playnite' for game in targets) and not cancel.is_set():
        try:raw_by_id={guid(row.get('_id')):row for row in store.read_playnite()}
        except Exception:warnings.append('Playnite 暂不可读取，继续使用其他资料来源')
    rows={}
    def query(game):
        needs=missing(store,game);fields={};sources={};notes=[];source_game=dict(game)
        row={'id':game['id'],'name':game['name'],'before':{'release_date':game.get('release_date',''),'category':game.get('category',''),'tags':effective_tags(game),'series':game.get('series','')},
             'before_cover':cover_path(store,game),'before_background':existing_background(store,game),'fields':fields,'sources':sources,'cover_name':'','notes':notes,'cancelled':False,'applied':False}
        def offer(key,value,source):
            enabled=options['dates'] if key=='release_date' else options['covers'] if key=='cover' else options['backgrounds'] if key=='background' else options['tags']
            if enabled and needs.get(key) and value and key not in fields:fields[key]=value;sources[key]={'steam':'Steam','vndb':'VNDB'}.get(source,source)
        if cancel.is_set():row['cancelled']=True;return row
        raw=raw_by_id.get(game['id'])
        if raw:
            details=playnite_metadata(raw)
            offer('release_date',details.get('release_date'),'Playnite')
            offer('tags',details.get('tags'),'Playnite')
            # Only use source hints in the query snapshot; existing ownership remains unchanged.
            source_game={**source_game,**details}
            if options['backgrounds'] and needs['background'] and raw.get('BackgroundImage'):
                try:
                    value=raw['BackgroundImage']
                    if not value.startswith(('http://','https://')):value=str(safe_child(Path(store.settings['library'])/'files',value.replace('\\','/')))
                    offer('background',prepare_background(store,value,cancel),'Playnite')
                except Exception:notes.append('Playnite 横幅未读取成功')
            if options['covers'] and needs['cover'] and raw.get('CoverImage'):
                try:
                    original=safe_child(Path(store.settings['library'])/'files',raw['CoverImage'].replace('\\','/'))
                    if original.is_file():
                        directory=store.root/'covers';directory.mkdir(exist_ok=True)
                        cached=directory/('preview-playnite-'+hashlib.sha256(game['id'].encode()).hexdigest()[:20]+original.suffix.lower())
                        if not cached.exists():shutil.copy2(original,cached)
                        offer('cover',str(cached),'Playnite');row['cover_name']=game['name']
                except Exception:notes.append('Playnite 封面未读取成功')
        if options['tags']:
            category=primary(fields.get('tags') or effective_tags(source_game))
            if category!='其他':offer('category',category,sources.get('tags',game.get('tags_source','现有标签')))
        needs_date=options['dates'] and needs['release_date'] and 'release_date' not in fields
        needs_tags=options['tags'] and needs['tags'] and 'tags' not in fields
        needs_background=options['backgrounds'] and needs['background'] and 'background' not in fields
        def offer_background(data):
            if needs_background and 'background' not in fields and data.get('background_url') and not cancel.is_set():
                try:offer('background',prepare_background(store,data['background_url'],cancel),data.get('background_source','资料库'))
                except Exception:notes.append('横幅下载失败，可重试')
        if (needs_date or needs_tags or needs_background) and not cancel.is_set():
            try:
                data=cached_lookup(store,source_game)
                offer('release_date',data.get('release_date'),data.get('release_date_source','资料库'))
                offer('tags',data.get('tags'),data.get('tags_source','资料库'))
                offer_background(data)
                if data.get('metadata_url'):row['metadata_url']=data['metadata_url']
                if data.get('matched_name'):row['matched_name']=data['matched_name']
            except Exception:notes.append('资料库查询失败，可重试')
        # Trusted app IDs bypass fuzzy cover search. Otherwise preview only a strong, unambiguous match.
        needs_cover=options['covers'] and needs['cover'] and 'cover' not in fields
        if (needs_cover or needs_background and 'background' not in fields or needs_date and 'release_date' not in fields) and not cancel.is_set():
            try:
                appid=str(source_game.get('steam_appid') or source_game.get('metadata_steam_appid') or '')
                candidate=None
                if appid.isdigit():candidate={'id':'steam:'+appid,'appid':appid,'name':game['name'],'provider':'steam','image':'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/'+appid+'/library_600x900.jpg','fallback':'','score':1}
                else:
                    providers=['vndb','steam'] if source_game.get('category')=='视觉小说' or primary(effective_tags(source_game))=='视觉小说' else ['steam']
                    for provider in providers:
                        if cancel.is_set():break
                        results=search(store,game['name'],provider,False,cancel)
                        if results and results[0]['score']>=.93 and (len(results)==1 or results[0]['score']-results[1]['score']>=.08):candidate=results[0];break
                if candidate and not cancel.is_set():
                    row['matched_name']=row.get('matched_name') or candidate['name']
                    if candidate.get('provider')=='vndb':
                        offer('release_date',release_date(candidate.get('released')),'VNDB（首次发行）')
                        if 'release_date' in fields:row['metadata_url']=candidate.get('page','')
                        offer_background({**candidate,'background_source':'VNDB 截图'})
                    if needs_cover and candidate.get('image'):
                        try:offer('cover',download(store,candidate),candidate.get('provider','资料库'));row['cover_name']=candidate['name']
                        except Exception:notes.append('封面下载失败，可重试')
                    if candidate.get('appid') and (needs_date or needs_tags or needs_background) and not cancel.is_set():
                        row['metadata_steam_appid']=candidate['appid']
                        data=cached_lookup(store,{**source_game,'metadata_steam_appid':candidate['appid']})
                        offer('release_date',data.get('release_date'),data.get('release_date_source','Steam'))
                        offer('tags',data.get('tags'),'Steam')
                        offer_background(data)
                        if data.get('metadata_url'):row['metadata_url']=data['metadata_url']
            except Exception:notes.append('封面或名称匹配未完成，可重试')
        if options['tags'] and fields.get('tags'):
            category=primary(fields['tags'])
            if category!='其他':offer('category',category,sources.get('tags','资料库'))
        row['cancelled']=cancel.is_set()
        return row
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(query,game):game for game in targets}
        for done,future in enumerate(as_completed(futures),1):
            row=future.result();rows[row['id']]=row
            notify(row,done,total,'正在查询缺失资料和封面' if not cancel.is_set() else '正在停止，已有结果保留')
    def unresolved(game):
        needs=missing(store,game);row=rows[game['id']]
        return (options['dates'] and needs['release_date'] and 'release_date' not in row['fields'] or
                options['backgrounds'] and needs['background'] and 'background' not in row['fields'] or
                options['covers'] and needs['cover'] and 'cover' not in row['fields'] or
                options['tags'] and needs['tags'] and 'tags' not in row['fields'] and not row.get('metadata_url') and not row.get('matched_name'))
    retry_targets=[game for game in targets if unresolved(game)]
    if retry_targets and not cancel.is_set():
        notify(None,total,total,f'正在二次查询 {len(retry_targets)} 款未匹配游戏')
        def retry(game):
            row=rows[game['id']];fields=row['fields'];needs=missing(store,game)
            raw=raw_by_id.get(game['id']);source_game={**game,**(playnite_metadata(raw) if raw else {})}
            names=query_hints(store,{**game,'aliases':[*game.get('aliases',[]),row.get('matched_name','')]},raw);errors=False;matched=False
            providers=['vndb','steam'] if source_game.get('category')=='视觉小说' or primary(effective_tags(source_game))=='视觉小说' else ['steam','vndb']
            row['second_pass']=True
            def offer(key,value,source):
                enabled=options['dates'] if key=='release_date' else options['covers'] if key=='cover' else options['backgrounds'] if key=='background' else options['tags']
                if enabled and needs.get(key) and value and key not in fields:
                    fields[key]=value;row['sources'][key]=source
            def accept(candidate):
                nonlocal matched
                matched=True;before_date=fields.get('release_date');before=len(fields)
                if candidate.get('provider')=='vndb':
                    offer('release_date',release_date(candidate.get('released')),'VNDB（首次发行）')
                    if not before_date and fields.get('release_date'):row['metadata_url']=candidate.get('page','')
                    if options['backgrounds'] and needs['background'] and 'background' not in fields and candidate.get('background_url'):
                        try:offer('background',prepare_background(store,candidate['background_url'],cancel),'VNDB 截图')
                        except Exception:row['notes'].append('VNDB 横幅下载失败，可重试')
                elif candidate.get('appid'):
                    try:
                        data=cached_lookup(store,{**source_game,'name':candidate['name'],'steam_appid':'','metadata_steam_appid':candidate['appid']})
                        offer('release_date',data.get('release_date'),data.get('release_date_source','Steam'))
                        offer('tags',data.get('tags'),'Steam')
                        if options['backgrounds'] and needs['background'] and 'background' not in fields and data.get('background_url'):
                            try:offer('background',prepare_background(store,data['background_url'],cancel),data.get('background_source','Steam'))
                            except Exception:row['notes'].append('Steam 横幅下载失败，可重试')
                        row['metadata_steam_appid']=candidate['appid']
                        if data.get('metadata_url') and not before_date and fields.get('release_date'):row['metadata_url']=data['metadata_url']
                    except Exception:row['notes'].append('二次匹配已找到，资料读取失败，可重试')
                if options['covers'] and needs['cover'] and 'cover' not in fields and candidate.get('image') and not cancel.is_set():
                    try:
                        offer('cover',download(store,candidate),{'steam':'Steam','vndb':'VNDB'}.get(candidate.get('provider'),'资料库'))
                        row['cover_name']=candidate['name']
                    except Exception:row['notes'].append('二次匹配已找到，封面下载失败，可重试')
                if len(fields)>before or not row.get('matched_name'):
                    row['matched_name']=candidate['name'];row['match_score']=round(candidate['score'],3)
            def outstanding():
                return any(enabled and needs[key] and key not in fields for key,enabled in [('release_date',options['dates']),('tags',options['tags']),('cover',options['covers']),('background',options['backgrounds'])])
            for provider in providers:
                candidates={};candidate=None
                for name in search_queries(names):
                    if cancel.is_set():return row
                    try:
                        for record in search(store,name,provider,False,cancel):candidates[record['id']]=record
                    except Exception:errors=True;continue
                    candidate=best_match(list(candidates.values()),names,True)
                    if candidate and candidate['score']>=.999:break
                if candidate:accept(candidate)
                if not outstanding():break
            if outstanding() and options['use_ai'] and not cancel.is_set() and (store.profile/'ai-key.dpapi').is_file():
                try:
                    from ai_match import identify_game
                    from services import protect
                    # Ask for names, then verify against actual database candidates.
                    identity=identify_game(game['name'],'',protect((store.profile/'ai-key.dpapi').read_bytes(),True).decode(),store.settings['ai_model'],cancel=cancel)
                    hints=[name for name in [identity.get('english_name'),*identity.get('aliases',[])] if isinstance(name,str) and name.strip()][:4]
                    for provider in providers:
                        records={}
                        for name in search_queries(hints):
                            if cancel.is_set():return row
                            for record in search(store,name,provider,False,cancel):records[record['id']]=record
                            candidate=best_match(list(records.values()),[*names,*hints],True,threshold=.96)
                            if candidate:
                                accept(candidate);row['notes'].append('DeepSeek 补充别名后匹配，请核对资料名称');break
                        if not outstanding():break
                except Exception:errors=True
            row['notes'].append('已使用原始名称、别名或繁简体完成二次查询' if matched else '二次查询仍未可靠匹配，保留缺失项'+('；部分来源暂不可用' if errors else ''))
            if options['dates'] and needs['release_date'] and 'release_date' not in fields:
                row['notes'].append('已匹配名称，但来源未提供完整发行日期' if matched else '名称未匹配到可靠资料，未填写发行日期')
            return row
        with ThreadPoolExecutor(max_workers=2) as pool:
            for future in as_completed([pool.submit(retry,game) for game in retry_targets]):
                row=future.result();row['cancelled']=cancel.is_set()
                notify(row,total,total,'正在二次查询未匹配游戏' if not cancel.is_set() else '正在停止，已有结果保留')
    if options['tags'] and not cancel.is_set():
        # The organizer only sees a detached library with source proposals filled in.
        proposed=deepcopy(games)
        for game in proposed:
            row=rows.get(game['id'])
            if row:game.update({key:value for key,value in row['fields'].items() if key not in ('cover','background')})
        view=SimpleNamespace(games=proposed,local=deepcopy(store.local),settings=dict(store.settings),groups=list(store.groups),profile=store.profile)
        ids=[game['id'] for game in targets if any(missing(store,game)[key] and key not in rows[game['id']]['fields'] for key in ('tags','category','series'))]
        if ids:
            notify(None,total,total,'正在补充分类、标签和系列')
            try:
                results=suggestions(view,options['use_ai'],ids,True,cancel)
                for suggested in results:
                    ident=suggested['id']
                    if ident not in ids:continue
                    row=rows[ident];needs=missing(store,known[ident])
                    for key in ('tags','category','series'):
                        value=suggested.get(key)
                        if needs[key] and key not in row['fields'] and value and (key!='category' or value!='其他'):
                            row['fields'][key]=value
                            origin=suggested.get('tags_source') if key=='tags' else None
                            row['sources'][key]=origin if origin and origin!='未记录' else 'DeepSeek' if options['use_ai'] else '名称规则'
                    notify(row,total,total,'正在整理预览')
            except Exception:warnings.append('分类建议未完成，资料库结果仍可应用；检查 DeepSeek 设置后可重试')
    return {'rows':[rows[game['id']] for game in targets], 'cancelled':cancel.is_set(),'warnings':warnings}

def apply(store,rows,idents):
    from services import write_json
    selected=set(idents);proposals={row['id']:row for row in rows}
    if any(ident not in proposals for ident in selected):raise ValueError('预览已变化，请重新查询')
    games=deepcopy(store.games);known={game['id']:game for game in games}
    changed=0;skipped=0;covers=False
    for ident in selected:
        if ident not in known:skipped+=1;continue
        game=known[ident];row=proposals[ident];needs=missing(store,game);updated=False
        for key,value in row['fields'].items():
            if not needs.get(key):skipped+=1;continue
            if key=='release_date':
                value=release_date(value)
                if not value:continue
                game['release_date_source']=row['sources'].get(key,'资料库')
                if row.get('metadata_url'):game['metadata_url']=row['metadata_url']
            elif key=='tags':
                value=normalize_tags(value,vocabulary([]))[:6]
                if not value:continue
                game.update(tags_source=row['sources'].get(key,'资料库'),tags_manual=False)
                if game['tags_source'] in ('Playnite','Steam'):game['source_tags']=value
            elif key=='category':
                from library_catalog import CATEGORIES
                if value not in [*CATEGORIES,*store.groups] or value=='其他':continue
                game['groups']=[value]
            elif key=='series':
                if not isinstance(value,str) or not value.strip() or len(value)>80:continue
            elif key=='cover':
                path=Path(value).resolve()
                if not path.is_relative_to((store.root/'covers').resolve()) or not path.is_file():skipped+=1;continue
                covers=True
            elif key=='background':
                from library_artwork import landscape
                path=Path(value).resolve()
                if not path.is_relative_to((store.root/'backgrounds').resolve()) or not path.is_file() or not landscape(path):skipped+=1;continue
                game['background_source']=row['sources'].get(key,'资料库')
            game[key]=value;updated=True
            if row['sources'].get(key)=='手动' and key in ('release_date','tags','category','series'):game[key+'_manual']=True
        changed+=updated
        if updated and row.get('metadata_steam_appid') and not game.get('metadata_steam_appid'):game['metadata_steam_appid']=row['metadata_steam_appid']
    if changed:
        write_json(store.root/'library.json',games);store.games=games
        store.groups=sorted(set(store.groups)|{game.get('category','其他') for game in games});write_json(store.root/'groups.json',store.groups)
        if covers:store.prepare_thumbnails()
    return f'已补全 {changed} 款游戏'+(f'；{skipped} 项已填写或不可用，已跳过' if skipped else '')
