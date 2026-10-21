"""Compact primary categories, rich searchable tags and local discovery shelves."""
from collections import Counter,defaultdict
import re,unicodedata

CATEGORIES=['视觉小说','角色扮演','动作冒险','射击竞技','策略模拟','解谜休闲','竞速体育','音乐节奏','其他']
CATEGORY_TAGS={
 '视觉小说':['视觉小说','galgame','gal','visual novel','恋爱冒险'],
 '角色扮演':['角色扮演','动作角色扮演','rpg','arpg','魂类','养成rpg','role-playing','action rpg'],
 '动作冒险':['动作','动作冒险','冒险','生存恐怖','开放世界','action','adventure','action-adventure','open world'],
 '射击竞技':['第一人称射击','射击','fps','多人竞技','tps','shooter','first-person shooter'],
 '策略模拟':['策略','模拟','经营','养成','桌游','战略','simulation','strategy','management','board game'],
 '解谜休闲':['平台跳跃','解谜','休闲','益智','puzzle','platformer','casual'],
 '竞速体育':['竞速','赛车','体育','运动','racing','sports'],
 '音乐节奏':['音乐节奏','音乐','节奏','音游','rhythm','music']}
STYLE_TAGS=['恐怖','开放世界','合作','恋爱','独立','悬疑','Roguelike','解谜']

def recently_added(game,now=None):
    from datetime import datetime,timezone,timedelta
    if not isinstance(game.get('added_at'),str):return False
    try:
        added=datetime.fromisoformat(game.get('added_at','').replace('Z','+00:00'))
        if added.tzinfo is None:return False
        age=(now or datetime.now(timezone.utc))-added
        return timedelta(0)<=age<timedelta(days=3)
    except (ValueError,TypeError):return False
def unique(values):return list(dict.fromkeys(value.strip() for value in values if isinstance(value,str) and value.strip()))
def normalized(value):return unicodedata.normalize('NFKC',value or '').casefold().strip()
def primary(tags):
    from tag_catalog import normalize_tags,vocabulary
    tags=normalize_tags(tags,vocabulary([]))
    values={normalized(value) for value in tags}
    for category in ('视觉小说','音乐节奏','竞速体育','射击竞技','角色扮演','策略模拟','解谜休闲','动作冒险'):
        aliases=CATEGORY_TAGS[category]
        if values.intersection(normalized(alias) for alias in aliases):return category
    return '其他'
def canonical_series(value):
    value=(value or '').strip()
    if re.search(r'^9[- ]?nine',value,re.I):return '9-nine'
    if re.search(r'美少女万[華华][鏡镜]',value):return '美少女万华镜'
    if value.casefold().startswith('flowers'):return 'Flowers'
    if value.casefold().startswith('nukitashi'):return 'NUKITASHI'
    if re.search(r'^fate(?:/|系列|$)',value,re.I):return 'Fate'
    return value
def valid_series(games):
    members=defaultdict(list)
    for game in games:
        name=canonical_series(game.get('series',''))
        if name:members[name].append(game)
    return {name:rows for name,rows in members.items() if len({row['id'] for row in rows})>=2}
def prepare_game(game):
    from library_sources import release_date
    game={**game,'release_date':release_date(game.get('release_date'))}
    from tag_catalog import effective_tags
    tags=effective_tags({**game,'tags':unique([*game.get('tags',[]),*game.get('groups',[])])})
    category=game.get('category') or primary(tags)
    name=canonical_series(game.get('series',''))
    return {**game,'category':category,'tags':tags,'series':name,'isNew':recently_added(game),
            'searchText':normalized(' '.join([game['name'],category,name,*tags]))}
def recommend(games,limit=12):
    recent=sorted([game for game in games if game.get('last_played')],key=lambda game:game['last_played'],reverse=True)[:5]
    excluded={game['id'] for game in recent};weights=Counter();categories=Counter()
    for index,game in enumerate(recent):
        for tag in game.get('tags',[]):weights[normalized(tag)]+=1/(index+1)
        categories[game['category']]+=1/(index+1)
    scored=[]
    for game in games:
        if game['id'] in excluded or set(map(normalized,game.get('tags',[]))).intersection({'工具','软件'}):continue
        tags=set(map(normalized,game.get('tags',[])))
        similarity=sum(weights[tag] for tag in tags)/max(1,len(tags))
        score=similarity+categories[game['category']]*.4+bool(game.get('favorite'))*.15+bool(game.get('installed'))*.1+(.1 if not game.get('last_played') else 0)
        scored.append((score,game))
    return [game for score,game in sorted(scored,key=lambda pair:(-pair[0],pair[1]['name']))[:limit]]
def sections(games):
    games=[prepare_game(game) for game in games];output=[]
    recent=sorted([game for game in games if game.get('last_played')],key=lambda game:game['last_played'],reverse=True)[:8]
    output.append({'id':'recent','kind':'recent','title':'最近游玩' if recent else '我的游戏','subtitle':'','items':recent or sorted(games,key=lambda game:(not game.get('favorite'),not game.get('installed'),game['name']))[:8],'target':'recent' if recent else 'all','value':''})
    added=sorted([game for game in games if game['isNew']],key=lambda game:game['added_at'],reverse=True)
    if added:output.append({'id':'new','kind':'games','title':'新加入','subtitle':'近 3 天加入的游戏','items':added[:12],'target':'new','value':''})
    grouped=defaultdict(list)
    for game in games:grouped[game['category']].append(game)
    tiles=[{'id':name,'name':name,'count':len(rows),'games':rows[:3],'target':'category','value':name} for name,rows in grouped.items()]
    tiles.sort(key=lambda tile:(CATEGORIES.index(tile['name']) if tile['name'] in CATEGORIES else 99,tile['name']))
    if tiles:output.append({'id':'categories','kind':'tiles','title':'按类别浏览','subtitle':'','items':tiles,'target':'all','value':''})
    tags=defaultdict(list)
    for game in games:
        for tag in game['tags']:tags[tag].append(game)
    if tags:output.append({'id':'tags','kind':'tiles','title':'按标签浏览','subtitle':'全部有效标签','items':[{'id':tag,'name':tag,'count':len(rows),'games':rows[:3],'target':'tag','value':tag} for tag,rows in sorted(tags.items(),key=lambda pair:(-len(pair[1]),pair[0]))],'target':'all','value':''})
    series=valid_series(games)
    if series:output.append({'id':'series','kind':'tiles','title':'按系列浏览','subtitle':'','items':[{'id':name,'name':name,'count':len(rows),'games':rows[:3],'target':'series','value':name} for name,rows in sorted(series.items(),key=lambda pair:(-len(pair[1]),pair[0]))],'target':'series','value':''})
    recommended=recommend(games)
    if recent and recommended:output.append({'id':'recommend','kind':'games','title':'猜你喜欢','subtitle':'','items':recommended,'target':'all','value':''})
    for name in CATEGORIES+[value for value in grouped if value not in CATEGORIES]:
        rows=grouped.get(name,[])
        if len(rows)>=2:output.append({'id':'category:'+name,'kind':'games','title':name,'subtitle':str(len(rows))+' 款游戏','items':sorted(rows,key=lambda game:(not game.get('installed'),game['name']))[:12],'target':'category','value':name})
    for tag in STYLE_TAGS:
        rows=[game for game in games if tag in game['tags']]
        if len(rows)>=3 and len(rows)<len(games):output.append({'id':'tag:'+tag,'kind':'games','title':tag,'subtitle':'','items':rows[:12],'target':'tag','value':tag})
    return output
