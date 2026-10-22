"""Download the requested repository's WAVs and build a local audition page.

Development utility only. Does not change application audio or user settings.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import base64
import argparse
import json
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build/sound-audition'
REPO = 'TOM-BadEN/Nintendo-Switch-Sounds-Effect'
COMMIT = '70614a3e0b912068476ed54d9836d08e8d6878b0'
EVENTS = {'move': '移动', 'confirm': '确认', 'back': '返回', 'open': '打开', 'group': '分组', 'switch': '布局切换'}


def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=35) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(.5)


def main(offline=False):
    (OUTPUT / 'wav').mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'processed').mkdir(exist_ok=True)
    if offline:
        files = [{'path': 'WAV/' + path.name} for path in sorted((OUTPUT / 'wav').glob('*.wav'))]
        if not files:
            raise ValueError('No downloaded WAVs; run without --offline first')
    else:
        tree = json.loads(fetch(f'https://api.github.com/repos/{REPO}/git/trees/{COMMIT}?recursive=1'))
        files = [item for item in tree['tree'] if item['path'].startswith('WAV/') and item['path'].endswith('.wav')]
    manifest = json.loads((ROOT / 'ui/sounds/library/manifest.json').read_text(encoding='utf-8'))
    selected = {}
    for entry in manifest['sounds']:
        if entry['bank'] != 'classic-clear':
            continue
        name = Path(entry['origins'][0]['source']).name
        selected[name] = {'event': EVENTS[entry['kind']], 'processed': entry['files'][0]}
        shutil.copyfile(ROOT / 'ui/sounds/library' / entry['files'][0], OUTPUT / 'processed' / entry['files'][0])

    def download(item):
        name = Path(item['path']).name
        path = OUTPUT / 'wav' / name
        # Git blob hash also validates cached files, not just their length.
        def valid(raw):
            return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == item['sha']
        if offline:
            if path.read_bytes()[:4] != b'RIFF':
                raise ValueError(f'Invalid local WAV: {name}')
        elif not path.exists() or not valid(path.read_bytes()):
            raw = fetch(f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{item["path"]}')
            if not valid(raw) or raw[:4] != b'RIFF':
                raise ValueError(f'Invalid WAV: {name}')
            path.write_bytes(raw)
        return {'name': name, **selected.get(name, {})}

    with ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(executor.map(download, files))
    rows.sort(key=lambda row: (not bool(row.get('event')), row['name'].lower()))
    data = json.dumps(rows, ensure_ascii=False).replace('<', '\\u003c')
    # Embed exact WAV bytes so decoding also works from file://, without fetch
    # permissions or reloading a media element on each short sound/replay.
    samples = {}
    for row in rows:
        keys = ['wav/' + row['name']]
        if row.get('processed'):
            keys.append('processed/' + row['processed'])
        for key in keys:
            samples[key] = base64.b64encode((OUTPUT / key).read_bytes()).decode('ascii')
    player = (ROOT / 'scripts/sound_audition_player.js').read_text(encoding='utf-8')
    page = '''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Switch 音效试听与指定</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#161b22;color:#e7ecf3;font:16px "Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1050px;margin:auto;padding:30px 24px}h1{font-size:26px;margin:0 0 12px}p{color:#abb7c7;line-height:1.7}a{color:#8bc5ff}
header{position:sticky;top:0;background:#161b22;padding:16px 0;border-bottom:1px solid #344150;z-index:1}
input,select,button,textarea{font:inherit;border:1px solid #46546a;border-radius:8px;background:#242e3d;color:#e7ecf3;padding:9px 12px}
button{cursor:pointer}button:hover{background:#36465c}button[aria-pressed="true"]{border-color:#95cfff;background:#344b66}button:disabled{opacity:.45;cursor:default}input{width:min(500px,100%)}label{margin-left:14px}
.transport{display:flex;align-items:center;gap:12px;flex-wrap:wrap}progress{flex:1;min-width:120px;height:9px;accent-color:#95cfff}.transport input{width:120px}#time{font-variant-numeric:tabular-nums}
.row{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid #2a3441;flex-wrap:wrap}.name{flex:1;min-width:280px;overflow-wrap:anywhere}.tag{font-size:13px;color:#95cfff;margin-left:10px}
textarea{display:block;width:100%;height:175px;resize:vertical;margin:12px 0}.status{font-size:14px;color:#95cfff;margin:10px 0}small{color:#abb7c7}
</style><main>
<h1>Switch 音效试听与指定</h1>
<p>来源：<a href="https://github.com/TOM-BadEN/Nintendo-Switch-Sounds-Effect">你指定的 GitHub 仓库</a>，固定提交 70614a3。仓库标注 Nintendo Switch，未核实为 Switch 2。版权归 Nintendo。<br>
“原文件”是仓库原始 WAV；“当前效果”是程序目前使用的裁剪、淡入淡出、响度处理版，不使用低通滤波或回响。浏览器音量与程序不同，请主要比较音色。开头六项标出了当前用途。</p>
<header><input id="search" placeholder="搜索文件名，如 Focus / Back / Startup"><label><input id="only" type="checkbox" style="width:auto">仅当前六项</label>
<div class="status" id="playing" role="status">点击原文件或当前效果试听；每次从头播放，只播放最后一次选择。</div>
<div class="transport"><button id="replay" disabled>重播</button><button id="stop" disabled>停止</button><progress id="progress" value="0" max="1" aria-label="播放进度"></progress><small id="time">0.000 / 0.000 秒</small><label for="volume">音量</label><input id="volume" type="range" min="0" max="100" value="100"><small id="volumeValue">100%</small></div></header>
<div id="list"></div><p id="count"></p>
<h2 style="font-size:20px">给你的选择</h2><small>试听后，在文件右侧选择用途。可将下方文字复制发给我；未指定的用途保持待选。</small>
<textarea id="choices" readonly></textarea><button id="copy">复制选择</button><span class="status" id="copyStatus"></span>
<p>此页面仅用于试听和记录选择，不会修改程序配置或替换音效。</p>
<script>
const rows=__ROWS__,audioFiles=__AUDIO_FILES__,events=['移动','确认','返回','打开','分组','布局切换','启动游戏'],picks={};
__PLAYER__
function choices(){document.querySelector('#choices').value=events.map(e=>e+' = '+(picks[e]||'待指定')).join('\\n')}
function render(){const query=document.querySelector('#search').value.toLowerCase(),only=document.querySelector('#only').checked,list=document.querySelector('#list');list.replaceChildren();const filtered=rows.filter(r=>(!only||r.event)&&r.name.toLowerCase().includes(query));for(const row of filtered){
const line=document.createElement('div');line.className='row';const name=document.createElement('div');name.className='name';name.textContent=row.name;if(row.event){const tag=document.createElement('span');tag.className='tag';tag.textContent='当前：'+row.event;name.append(tag)}line.append(name);
for(const processed of (row.processed?[false,true]:[false])){const b=document.createElement('button');b.textContent=processed?'当前效果':'原文件';b.dataset.audioKey=processed?'processed/'+row.processed:'wav/'+row.name;b.setAttribute('aria-pressed',String(auditionPlayer.key===b.dataset.audioKey));b.onclick=()=>play(row,processed);line.append(b)}
const select=document.createElement('select');select.setAttribute('aria-label',row.name+' 用途');for(const title of ['指定用途…',...events]){const option=document.createElement('option');option.textContent=title;select.append(option)}select.onchange=()=>{if(select.selectedIndex){picks[select.value]=row.name;choices();select.selectedIndex=0}};line.append(select);list.append(line)}document.querySelector('#count').textContent='显示 '+filtered.length+' / '+rows.length+' 个 WAV';}
document.querySelector('#search').oninput=render;document.querySelector('#only').onchange=render;
document.querySelector('#copy').onclick=async()=>{const field=document.querySelector('#choices');field.select();try{await navigator.clipboard.writeText(field.value);document.querySelector('#copyStatus').textContent=' 已复制'}catch(e){document.querySelector('#copyStatus').textContent=' 已选中，请按 Ctrl+C 复制'}};choices();render();
</script></main></html>'''.replace('__ROWS__', data).replace('__AUDIO_FILES__', json.dumps(samples)).replace('__PLAYER__', player)
    (OUTPUT / 'index.html').write_text(page, encoding='utf-8')
    source = 'cached originals (offline)' if offline else 'verified originals'
    print(f'Ready: {len(rows)} {source}, {len(selected)} processed samples: {OUTPUT / "index.html"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Regenerate from previously downloaded WAVs without a network request')
    main(parser.parse_args().offline)
