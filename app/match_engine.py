"""Concurrent local, Steam and model hints; filesystem evidence remains decisive."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from pathlib import Path
import hashlib,json,time,threading,re,math

_ai_limit=threading.Semaphore(2)
EMPTY={'english_name':'','aliases':[],'developers':[],'publishers':[],'hints':[],'note':'','sources':[]}

def ai_weight(settings):
    try:value=float(settings.get('match_ai_weight',75))
    except (TypeError,ValueError):value=75
    if not math.isfinite(value):value=75
    return max(.5,min(.95,value/100))

def score_reviews(candidates,scores,weight):
    """AI can reject configuration folders; automatic use still requires save evidence."""
    for index,candidate in enumerate(candidates[:30]):
        verdict=scores.get(index,scores.get(str(index)))
        if not verdict:continue
        local=candidate.get('local_confidence',candidate['confidence'])
        candidate.update(ai_confidence=verdict['confidence'],ai_reason=verdict['reason'],local_confidence=local,ai_weight=weight)
        combined=(1-weight)*local+weight*verdict['confidence']
        path=Path(candidate['path']).resolve()
        try:
            has_files=path.is_dir() and any((path/name).resolve().is_relative_to(path) and (path/name).is_file() for name in candidate.get('files',[]))
        except (OSError,ValueError):has_files=False
        if not has_files:combined=min(local,combined)
        if candidate.get('sample_backup'):combined=min(.55,combined)
        candidate['confidence']=math.floor(combined*100+.5+1e-9)/100
    candidates.sort(key=lambda candidate:-candidate['confidence'])

def merge(*identities):
    result={**EMPTY}
    for field in ('aliases','developers','publishers','hints','sources'):result[field]=[]
    for identity in identities:
        if not identity:continue
        for field in ('english_name','engine','note'):
            if identity.get(field):result[field]=identity[field]
        for field in ('aliases','developers','publishers','hints','sources'):
            for value in identity.get(field,[]):
                if value not in result[field]:result[field].append(value)
    return result

def context(local,title,cancel):
    from matching import roots_for,normalize
    from local_index import directories
    root=roots_for(local)['locallow'];keys=[normalize(title),normalize(Path(local.get('install_dir','')).name)]
    return [{'root':'locallow','relative':re.sub(r'\d{6,}','<账户>',p.relative_to(root).as_posix())}
            for p in directories(root,depth=2,budget=2000,seconds=.6,cancel=cancel)
            if any(key and key in normalize(p.name) for key in keys)][:20]

def cached_ai(store,item,local,cancel):
    from ai_match import identify_game
    from services import protect,write_json
    key_path=store.profile/'ai-key.dpapi'
    if not key_path.exists():raise ValueError('未配置 DeepSeek API Key，已使用本地规则')
    cache_key=hashlib.sha256((item['name']+local.get('install_dir','')+store.settings['ai_model']+'v3').encode()).hexdigest()
    with store.match_lock:
        if cache_key in store.identities:return store.identities[cache_key]
    with _ai_limit:
        if cancel.is_set():return {}
        identity=identify_game(item['name'],Path(local.get('install_dir','')).name,protect(key_path.read_bytes(),True).decode(),store.settings['ai_model'],context(local,item['name'],cancel),cancel)
    if not cancel.is_set():
        with store.match_lock:
            store.identities[cache_key]=identity;write_json(store.profile/'ai-identities.json',store.identities)
    return identity

def cached_network(store,item,local,cancel,title=None):
    from network_metadata import lookup
    from services import write_json
    title=title or item['name'];key=hashlib.sha256((title+local.get('install_dir','')).encode()).hexdigest()
    with store.match_lock:
        record=store.network_cache.get(key)
        if record and time.time()-record['time']<86400:return record['identity']
    identity=lookup(title,Path(local.get('install_dir','')).name,item.get('steam_appid',''),cancel)
    if identity and not cancel.is_set():
        with store.match_lock:
            store.network_cache[key]={'time':time.time(),'identity':identity};write_json(store.root/'network-identities.json',store.network_cache)
    return identity

def match(store,ident,progress=None,cancel=None):
    from matching import scan
    item=next(g for g in store.games if g['id']==ident)
    local=dict(store.local.get(ident,{}));cancel=cancel or threading.Event()
    if not local.get('install_dir') and local.get('exe'):local['install_dir']=str(Path(local['exe']).parent)
    started=time.monotonic();identities={};candidates=[];checked=[];warnings={};modes=[]
    def result(status='running'):
        identity=merge(identities.get('ai'),identities.get('network'))
        return {'id':ident,'name':item['name'],'status':status,'message':'找到 '+str(len(candidates))+' 个候选目录' if candidates else '正在查找存档',
                'candidates':candidates,'checked':checked,'english_name':identity['english_name'],'aliases':identity['aliases'],
                'developers':identity['developers'],'publishers':identity['publishers'],'engine':identity.get('engine',''),
                'note':identity['note'],'sources':identity['sources'],'scan_modes':list(modes),
                'ai_warning':warnings.get('ai',''),'network_warning':warnings.get('network',''),
                'elapsed':round(time.monotonic()-started,2),'model':store.settings['ai_model'] if store.settings.get('ai_enabled') else '本地规则'}
    pool=ThreadPoolExecutor(max_workers=3)
    futures={pool.submit(scan,item['name'],local,None,None,cancel):'local'}
    if store.settings.get('match_network',True):futures[pool.submit(cached_network,store,item,local,cancel)]='network'
    if store.settings.get('ai_enabled'):futures[pool.submit(cached_ai,store,item,local,cancel)]='ai'
    try:
        while futures and not cancel.is_set():
            completed,_=wait(futures,timeout=.05,return_when=FIRST_COMPLETED)
            for future in completed:
                mode=futures.pop(future)
                try:
                    value=future.result()
                    if mode=='local':candidates,checked=value
                    else:identities[mode]=value
                    modes.append({'mode':mode,'state':'done'})
                except Exception as error:
                    warnings[mode]=str(error) if isinstance(error,ValueError) else ('联网资料暂不可用' if mode=='network' else '本地扫描失败' if mode=='local' else 'DeepSeek 暂不可用')
                    modes.append({'mode':mode,'state':'failed'})
                if progress and not cancel.is_set():progress(result())
        if cancel.is_set():
            row=result('review' if candidates else 'notfound');row['message']='查找已停止，已找到的目录保留';return row
        if identities:candidates,checked=scan(item['name'],local,merge(*identities.values()),cancel=cancel)
        # A Chinese store query can miss an English title: retry with the model's identified name.
        english=identities.get('ai',{}).get('english_name','')
        if store.settings.get('match_network',True) and not identities.get('network') and english and english!=item['name']:
            try:
                identities['network']=cached_network(store,item,local,cancel,english)
                candidates,checked=scan(item['name'],local,merge(*identities.values()),cancel=cancel)
            except Exception:pass
        if store.settings.get('ai_enabled') and not warnings.get('ai') and store.settings.get('match_ai_review',True) and candidates and not cancel.is_set():
            try:
                from ai_match import review_directories
                from services import protect,read_json,write_json
                signatures=[{'path':c['path'],'files':c['files']} for c in candidates[:30]]
                cache_key=hashlib.sha256(json.dumps(['directory-review-v2',item['name'],store.settings['ai_model'],signatures],sort_keys=True).encode()).hexdigest()
                with store.match_lock:reviews=read_json(store.profile/'ai-reviews.json',{});scores=reviews.get(cache_key)
                if scores is None:
                    with _ai_limit:
                        if cancel.is_set():return result('review')
                        scores=review_directories(item['name'],candidates,protect((store.profile/'ai-key.dpapi').read_bytes(),True).decode(),store.settings['ai_model'])
                    with store.match_lock:
                        reviews=read_json(store.profile/'ai-reviews.json',{});reviews[cache_key]=scores;write_json(store.profile/'ai-reviews.json',reviews)
                score_reviews(candidates,scores,ai_weight(store.settings))
            except Exception:warnings['ai']=warnings.get('ai') or '目录辅助比较暂不可用，保留本地验证结果'
        row=result('review' if candidates else 'failed' if warnings.get('ai') else 'notfound')
        if not candidates:row['message']=warnings.get('ai') or '未找到存档，请手动选择目录或补充游戏别名'
        return row
    finally:pool.shutdown(wait=False,cancel_futures=True)
