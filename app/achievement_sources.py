"""Exact-AppID definition sources; title ambiguity never joins unrelated progress."""
from achievement_files import fetch_json,normalize_schema,steam_schema

PROVIDERS=[{'id':'auto','name':'自动 · Steam 优先'}, {'id':'steam','name':'Steam'},
           {'id':'steamhunters','name':'SteamHunters'}, {'id':'community','name':'Steam Community'},
           {'id':'completionist','name':'Completionist.me'}, {'id':'local','name':'本地定义 / Steam 缓存'}]


def hunters_schema(appid):
    if not str(appid).isdigit():raise ValueError('App ID 无效')
    payload=fetch_json(f'https://steamhunters.com/api/apps/{appid}/achievements')
    if not isinstance(payload,list):raise ValueError('SteamHunters 未返回成就列表')
    rows=[]
    for entry in payload:
        if isinstance(entry,dict) and entry.get('apiName'):
            rows.append(dict(entry,name=entry['apiName'],displayName=entry.get('name') or entry['apiName']))
    result=normalize_schema(rows,appid=str(appid))
    if not result:raise ValueError('SteamHunters 没有对应的成就定义')
    return result


def resolve(appid,provider='auto',local_schema=None,steam_fetch=None):
    if provider not in {r['id'] for r in PROVIDERS}:raise ValueError('成就来源不存在')
    from achievement_web import community_schema,completionist_schema
    chain=['steam','local','steamhunters','community','completionist'] if provider=='auto' else [provider]
    failures=[]
    for source in chain:
        try:
            rows=(steam_fetch or steam_schema)(appid) if source=='steam' else hunters_schema(appid) if source=='steamhunters' else community_schema(appid) if source=='community' else completionist_schema(appid,local_schema or []) if source=='completionist' else local_schema or []
            if not rows:raise ValueError('没有本地定义')
            return rows,{'steam':'Steam 公开成就资料','local':'本地成就定义 / Steam 缓存','steamhunters':'SteamHunters','community':'Steam Community','completionist':'Completionist.me（标题来源需核对 ID）'}[source],failures
        except Exception as exc:failures.append(source+': '+str(exc)[:120])
    raise ValueError('；'.join(failures))
