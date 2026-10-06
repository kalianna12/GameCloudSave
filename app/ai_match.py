"""DeepSeek ranks real local candidates; model output cannot introduce paths."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

def rank_candidates(title, candidates, key, model):
    payload = {'model': model, 'response_format': {'type': 'json_object'}, 'max_tokens': 1000,
               'messages': [
                   {'role': 'system', 'content': '你帮助匹配游戏存档目录。仅根据游戏中英文名称和候选文件夹名称排序。输出 JSON 对象 {"matches":[{"id":0,"confidence":0.8}]}。id 必须来自提供的候选，不得猜测不存在的目录。'},
                   {'role': 'user', 'content': json.dumps({'game': title, 'candidates': [{'id': i, 'folder': Path(p).name} for i,p in enumerate(candidates)]}, ensure_ascii=False)}]}
    request = Request('https://api.deepseek.com/chat/completions', data=json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
        choice = data['choices'][0]
        if choice.get('finish_reason') != 'stop': raise ValueError('AI 输出不完整')
        matches = json.loads(choice['message']['content'])['matches']
        scored = {}
        for match in matches:
            ident = match['id']; confidence = match['confidence']
            if type(ident) is not int or ident not in range(len(candidates)) or ident in scored:
                raise ValueError('AI 返回无效候选')
            if type(confidence) not in (float, int) or not 0 <= confidence <= 1:
                raise ValueError('AI 返回无效置信度')
            scored[ident] = confidence
        return [candidates[i] for i in sorted(range(len(candidates)), key=lambda i: -scored.get(i, 0))]
    except Exception as error:
        raise ValueError('DeepSeek 匹配失败，请检查 API Key/模型，或关闭 AI 使用本地规则扫描') from error
