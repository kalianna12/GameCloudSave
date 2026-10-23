"""Serialized read-only live record checks, independent of game-window discovery."""
from pathlib import Path
import time
import psutil
from achievement_files import canonical_states, discover, empty_record, merge_progress, parse_state


def check(repository, session):
    ident = session['ident']; target = dict(session['target'])
    changed = False; ended = False; events = []
    previous_health = repository.health.get(ident)
    try:
        if not session.get('passive'):
            if not session.get('primed'): return False, [], False
            if not target:
                ended = time.monotonic()-session['created'] > 360
            else:
                try:
                    process = psutil.Process(target['pid'])
                    if process.create_time() != target.get('created', process.create_time()): return False, [], True
                except psutil.NoSuchProcess:
                    ended = True  # Some games flush only at process exit.
        config = repository.config(ident)
        if not config.get('enabled', True): return False, [], ended
        source = config.get('source', '')
        if not source and time.monotonic()-session['discovery'] > 8:
            found = discover(session['game'], dict(session['local'],achievement_roots=config.get('roots',[])), config.get('appid', ''))
            session['discovery'] = time.monotonic(); config['sources'] = found['sources']
            if len(found['sources']) == 1:
                source = config['source'] = found['sources'][0]
                # During launch the baseline predates this newly created file.
                # Idle imports instead keep the normal first-baseline behavior.
                if not session.get('passive'): repository.record(ident, config)['initialized'] = True
                repository.save(); changed = True
        if not source:
            repository.health[ident] = '找到多个记录，请选择游玩账号／目录' if len(config.get('sources', [])) > 1 else '尚无可读取的记录；仅匹配成就列表不能产生进度'
        else:
            path = Path(source); stat = path.stat()
            # Late metadata must retry an unchanged file whose CRC/Steam IDs
            # could not be resolved at the previous tick.
            schema_ids = tuple(r['id'] for r in config.get('schema', []))
            signature = (config.get('appid'), source, stat.st_mtime_ns, stat.st_size, stat.st_ino, schema_ids)
            if signature != session.get('signature'):
                raw = parse_state(path)
                states = canonical_states(raw, config.get('schema', []))
                if not states and not empty_record(path):
                    raise ValueError('记录正在写入或格式未识别，保留进度并重试')
                after = path.stat()
                if (stat.st_mtime_ns, stat.st_size, stat.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
                    raise ValueError('记录正在写入，等待完整文件')
                config['record_empty'] = not states
                record = repository.record(ident, config)
                if not record.get('initialized') and any(k.startswith('crc32:') for k in raw): record['pending_baseline'] = raw
                baseline = record.get('pending_baseline')
                baseline_dirty = False
                if baseline and config.get('schema'):
                    _, baseline_dirty = merge_progress(record, canonical_states(baseline, config['schema']))
                    record.pop('pending_baseline', None); baseline_dirty = True
                keys, dirty = merge_progress(record, states, notify=True)
                dirty = dirty or baseline_dirty
                session['signature'] = signature
                if dirty: repository.save(); changed = True
                schema = {r['id']: r for r in config.get('schema', [])}
                if target and not session.get('passive') and config.get('notifications', True) and session['game'].get('platform') != 'steam':
                    for key in keys:
                        row = dict(schema.get(key) or {'id': key, 'name': key, 'description': ''})
                        row.update(game_id=ident, game_name=session['game']['name'], icon_path=repository.icon_path(row))
                        events.append((row, target))
            repository.health[ident] = '正在监听记录（约每秒）；等待游戏写入' if target else '后台同步记录（约每秒）；游戏内弹窗需从游戏库启动并识别窗口'
    except Exception as exc:
        repository.health[ident] = '读取暂未成功，自动重试：' + str(exc)[:160]
    return changed or previous_health != repository.health.get(ident), events, ended
