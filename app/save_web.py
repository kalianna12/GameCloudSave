"""Real, bounded DeepSeek Search requests; web text is evidence, never instructions."""
import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


def search(title, key, cancel=None, deep=False):
    if cancel and cancel.is_set():
        return []
    query_title=re.sub(r'[:：™®]','',title)
    query = (query_title[:65] + (' save location alternative folder internal project name' if deep else ' Windows save file location 存档位置'))[:128]
    request = Request('https://api.deepseek.com/v1/tools/search',
                      data=json.dumps({'query':query, 'count':6, 'need_content':True}).encode(),
                      headers={'Authorization':'Bearer ' + key, 'Content-Type':'application/json'})
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('网页搜索响应过大，已保留本地结果')
        rows = json.loads(raw).get('results')
        if not isinstance(rows, list):
            raise ValueError('网页搜索格式无效，已保留本地结果')
        sources = []
        for row in rows[:6]:
            if not isinstance(row, dict):
                continue
            url = row.get('url', '')
            if not isinstance(url, str) or urlsplit(url).scheme not in ('https', 'http') or not urlsplit(url).hostname:
                continue
            text = '\n'.join(str(row.get(field) or '') for field in ('snippet', 'summary', 'content'))[:16000]
            sources.append({'title':str(row.get('title', '网页资料'))[:200], 'url':url[:2000], 'text':text})
        return [] if cancel and cancel.is_set() else sources
    except HTTPError as error:
        messages = {401:'API Key 无效', 402:'账户余额不足', 403:'此 Key 无网页搜索权限', 404:'网页搜索接口暂不可用', 429:'请求频率受限'}
        raise ValueError('DeepSeek 网页搜索：' + messages.get(error.code, 'HTTP ' + str(error.code))) from None
    except (URLError, TimeoutError):
        raise ValueError('DeepSeek 网页搜索连接失败或超时，已保留本地结果') from None
    except (json.JSONDecodeError, AttributeError):
        raise ValueError('DeepSeek 网页搜索返回格式无效') from None


def supported_hint(hint, sources):
    """A model may only cite supplied pages containing its concrete path."""
    url = hint.get('source_url')
    source = next((source for source in sources if source['url'] == url), None)
    if source is None:
        return False
    normalize = lambda text: re.sub(r'\s+', '', text.replace('\\', '/')).casefold()
    relative = normalize(hint.get('relative', '')).strip('/')
    return len(relative) >= 3 and relative in normalize(source['text'])


def extract_paths(sources,title):
    """Retain literal Windows save-container paths even if a model omits an alternate."""
    anchors=[('local',r'(?:%LOCALAPPDATA%|AppData[/\\]Local)'),
             ('roaming',r'(?:%APPDATA%|AppData[/\\]Roaming)'),
             ('locallow',r'AppData[/\\]LocalLow'),
             ('documents',r'(?:%USERPROFILE%[/\\])?Documents'),
             ('savedgames',r'(?:%USERPROFILE%[/\\])?Saved Games')]
    normalize=lambda value: re.sub(r'[\W_]','',value.casefold())
    result=[]
    for source in sources:
        if normalize(title) not in normalize(source['title']+' '+source['text']):continue
        for root,anchor in anchors:
            pattern=anchor+r'[/\\]((?:[\w .()\-]+[/\\]){0,7}(?:SaveGames|SaveData|Saves|Save|Release))'
            for match in re.finditer(pattern,source['text'],re.I):
                relative=match[1].replace('\\','/').strip('/')
                if len(relative)>240 or '..' in relative.split('/') or any(part.strip()!=part for part in relative.split('/')):continue
                hint={'root':root,'relative':relative,'reason':'网页原文中的存档容器路径','source_url':source['url']}
                if hint not in result:result.append(hint)
    return result[:20]
