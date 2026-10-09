"""Stable tag vocabulary: reuse library terms and reject invented model tags."""
from collections import Counter
import re,unicodedata

ALIASES={
 '视觉小说':['gal','galgame','visual novel','visual novels','vn'],
 '恋爱':['恋爱冒险','恋爱模拟','romance','dating sim'],
 '剧情':['剧情向','故事丰富','story rich','story-rich','story'],
 '角色扮演':['rpg','role playing','role-playing'],
 '动作角色扮演':['arpg','action rpg','action-rpg','动作rpg'],
 '魂类':['soulslike','souls-like','类魂'],
 'Roguelike':['roguelike','rogue-like','肉鸽','类rogue'],
 '恐怖':['horror','生存恐怖','survival horror'],
 '独立':['indie','独立游戏'],
 '合作':['co-op','coop','cooperative','多人合作'],
 '竞技':['competitive','多人竞技'],
 '平台跳跃':['platformer','platforming','平台动作'],
 '开放世界':['open world','open-world'],
 '解谜':['puzzle','puzzles','益智'],
 '策略':['strategy','战略'],
 '模拟':['simulation','sim'],
 '射击':['shooter','shooting','fps','第一人称射击'],
 '动作':['action'], '冒险':['adventure'],
 '回合制':['turn-based','turn based'],
 '音乐节奏':['rhythm','music','音乐','节奏','音游'],
 '竞速':['racing','赛车'], '体育':['sports'],
 '养成':['养成模拟'], '休闲':['casual'],
 '悬疑':['mystery'], '科幻':['sci-fi','science fiction'],
 '奇幻':['fantasy'], '探索':['exploration'], '建造':['building'],
 '经营':['management'], '生存':['survival'], '工具':['software','软件'],
 '校园':[], '治愈':[], '历史':[], '成人':[]}

def normalized(value):
    return re.sub(r'[\s_-]+',' ',unicodedata.normalize('NFKC',value).casefold()).strip()

def key(value):
    text=normalized(value)
    for name,aliases in ALIASES.items():
        if text in {normalized(name),*(normalized(alias) for alias in aliases)}:return normalized(name)
    return text

def vocabulary(games):
    counts=Counter(tag.strip() for game in games for tag in game.get('tags',[]) if isinstance(tag,str) and tag.strip() and tag.strip()!='其他')
    result={}
    # Existing spelling wins. Frequency and a stable tie-break avoid output drift.
    for tag in sorted(counts,key=lambda tag:(-counts[tag],normalized(tag),tag)):
        result.setdefault(key(tag),tag)
    if not result:
        for tag in ALIASES:result.setdefault(key(tag),tag)
    return sorted(result.values(),key=lambda value:(normalized(value),value))

def normalize_tags(values,allowed):
    known={key(value):value for value in allowed}
    output=[]
    for value in values:
        canonical=known.get(key(value))
        if canonical and canonical not in output:output.append(canonical)
    return output

def classified(game):
    tags=[tag for tag in game.get('tags',[]) if isinstance(tag,str) and tag.strip() and tag.strip()!='其他']
    category=game.get('category','')
    return bool(tags or category and category!='其他' or game.get('series'))
