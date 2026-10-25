"""Serialized read-only live record checks, independent of game-window discovery."""
from pathlib import Path
import time
from achievement_files import canonical_states, discover, empty_record, merge_progress, parse_state


def file_signature(path):
    """Steam progress also depends on its separate group/bit definition file."""
    def stamp(file):
        stat=file.stat();return stat.st_mtime_ns, stat.st_size, stat.st_ino
    result=stamp(path)
    if path.suffix.casefold()=='.bin' and path.name.casefold().startswith('usergamestats_'):
        from achievement_steam import progress_schema_path
        result+=(stamp(progress_schema_path(path)),)
    return result


def check(repository, session):
    ident = session['ident'];changed = False
    previous_health = repository.health.get(ident)
    try:
        config = repository.config(ident)
        if not config.get('enabled', True): return False
        source = config.get('source', '')
        if not source and time.monotonic()-session['discovery'] > 8:
            found = discover(session['game'], dict(session['local'],achievement_roots=config.get('roots',[])), config.get('appid', ''))
            session['discovery'] = time.monotonic(); config['sources'] = found['sources']
            if len(found['sources']) == 1:
                source = config['source'] = found['sources'][0]
                repository.save(); changed = True
        if not source:
            repository.health[ident] = '找到多个记录，请选择游玩账号／目录' if len(config.get('sources', [])) > 1 else '尚无可读取的记录；仅匹配成就列表不能产生进度'
        else:
            path = Path(source); files = file_signature(path)
            # Late metadata must retry an unchanged file whose CRC/Steam IDs
            # could not be resolved at the previous tick.
            schema_ids = tuple(r['id'] for r in config.get('schema', []))
            signature = (config.get('appid'), source, files, schema_ids)
            if signature != session.get('signature'):
                raw = parse_state(path)
                states = canonical_states(raw, config.get('schema', []))
                if not states and not empty_record(path):
                    raise ValueError('记录正在写入或格式未识别，保留进度并重试')
                if files != file_signature(path):
                    raise ValueError('记录正在写入，等待完整文件')
                config['record_empty'] = not states
                record = repository.record(ident, config)
                if not record.get('initialized') and any(k.startswith('crc32:') for k in raw): record['pending_baseline'] = raw
                baseline = record.get('pending_baseline')
                baseline_dirty = False
                if baseline and config.get('schema'):
                    _, baseline_dirty = merge_progress(record, canonical_states(baseline, config['schema']))
                    record.pop('pending_baseline', None); baseline_dirty = True
                _, dirty = merge_progress(record, states, notify=True)
                dirty = dirty or baseline_dirty
                session['signature'] = signature
                if dirty: repository.save(); changed = True
            repository.health[ident] = '后台同步记录；等待游戏写入'
    except Exception as exc:
        repository.health[ident] = '读取暂未成功，自动重试：' + str(exc)[:160]
    return changed or previous_health != repository.health.get(ident)
