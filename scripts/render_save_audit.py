"""Render every audited game, including empty/unrecognized locations, into a local report."""
from pathlib import Path
from collections import Counter
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT

def render():
    report=json.loads((ROOT/'test-data/save-audit.json').read_text(encoding='utf-8'))
    if report['completed']!=report['total']:raise ValueError('批量测试尚未完成')
    baseline=json.loads((ROOT/'test-data/save-audit-baseline.json').read_text(encoding='utf-8'))
    labels={'found':'已找到存档特征','directory_only':'目录存在，存档未确认','not_observed':'未发现目录','review':'多个候选待核对','sample_only':'仅附带样例存档','error':'检测错误'}
    counts=Counter(row['status'] for row in report['games'])
    def portable(value):return str(value).replace(str(Path.home()),'%USERPROFILE%').replace('|','\\|')
    lines=['# 54 款游戏存档查找实测报告','',
           '测试日期：2026-10-09。范围为当前 Playnite 游戏库 51 款，加上用户提供的 Dark Souls III、EnderMagnolia、Slay the Spire 2 三款旧工程游戏。',
           '',f"最终统计：{dict((labels.get(k,k),v) for k,v in counts.items())}。首轮找到 {sum(g['status']=='found' for g in baseline['games'])} 款，修复后找到 {counts['found']} 款。",'',
           '未发现不等于没有存档或从未启动；目录存在也不等于已经产生游戏进度。空目录、只含系统/设置文件、未知格式均不强行认定为完整存档。',
           '', '全程只读查找与文件检查，没有启动游戏、创建真实游戏备份、上传、恢复或修改游戏文件。缓存和查找报告会更新。', '',
           '## 修正的问题','',
           '- 增加 `.nson`：DJMAX RESPECT V 和 Magical Girl Witch Trials 都已有实际存档文件。',
           '- 增加已核对路径规则：SHf、SB 等内部代号与显示名称不同；安装目录失效时仍可找到已有的 AppData 存档。',
           '- 从启动 EXE 提取代号，同时拒绝把 Game、Release、Win64 等通用名字作为游戏匹配线索。',
           '- 将账号目录合并到游戏自己的存档根目录，涵盖全部账号；不提升到全局 Steam userdata。旧账号级备份恢复仍限定原账号。',
           '- 不把附带全 CG、补丁里的样例存档自动当成正在使用的存档；这些路径仍可手动核对。',
           '- 过滤编号续作冲突，避免 Monument Valley 3 匹配到本机的 Monument Valley 2。',
           '- 支持以撒的 persistentgamedata `.dat`，保留对未知 `.dat` 的谨慎判断。', '',
           '## 全量结果','', '| 游戏 | 结果 | 选中目录或需要检查的目录 | 说明 |','|---|---|---|---|']
    for row in report['games']:
        candidates=row.get('result',{}).get('candidates',[])
        path=row.get('selected') or (candidates[0]['path'] if candidates else '')
        files=candidates[0].get('files',[]) if candidates else []
        explanation='旧工程补充测试，未写入 Playnite 游戏库。' if row.get('audit_extra') else ''
        if row['status']=='directory_only':explanation+=' 已识别文件：'+(', '.join(files[:4]) or '未发现常见存档文件')
        if row['status']=='not_observed':explanation+=' 本轮未观察到，可启动游戏并产生存档后再核对。'
        lines.append('| '+ ' | '.join((portable(row['name']),labels[row['status']],portable(path) or '—',portable(explanation)))+' |')
    lines+=['','## 用户提供的六款路径','',
            '六款均已观察到真实存档文件，按本机实际目录核对如下：','',
            '| 游戏 | 最终目录 |','|---|---|']
    keys=['CODE VEIN 噬血代码 II','DJMAX RESPECT V','Dark Souls III','ENDER MAGNOLIA: Bloom in the Mist','Slay the Spire 2','Silent Hill f']
    for name in keys:
        row=next(row for row in report['games'] if row['name']==name)
        assert row['status']=='found',row
        lines.append('| '+name+' | '+portable(row['selected'])+' |')
    lines+=['','EnderMagnolia 从 Saved 细化到 SaveGames，避免顺带把着色器缓存当存档；SHf 保留完整 SaveGames，而不是单个账号。Slay the Spire 2 保留整个游戏专属 steam 文件夹，包含账号下的设置、profile.save、各 profile 槽位。',
            '', '## 尚未确认的边界','',
            f"{counts['directory_only']} 款目录已观察到但缺少明确存档证据：有的是空 save/save_chs/SaveData，有的只有 config.dat、SystemData.dat、meta.dat、Graphics.json 或缓存。它们可能是未产生进度，也可能还有未覆盖格式，不能宣布规则已经齐全。",
            '', str(counts['not_observed'])+' 款未发现：'+ '、'.join(row['name'] for row in report['games'] if row['status']=='not_observed')+'。不认定未游玩。',
            '', '沙耶之歌的 saya_ch/1.00 目录已定位，观察到 system.dat；增加了短游戏代号与语言后缀的匹配。只有全局/设置数据时不自动断言已有故事进度。',
            '', '部分 Playnite 安装路径已经不存在，不能据此判断 AppData 存档不存在。测试没有自动修改安装路径。',
            '', '原始逐候选数据保存在 test-data/save-audit.json，首轮基线保存在 test-data/save-audit-baseline.json。']
    path=ROOT/'docs/54款游戏存档查找报告.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    store=Store();known={g['id'] for g in store.games};existing={r['id']:r for r in store.match_report}
    for row in report['games']:
        if row['id'] in known and 'result' in row:existing[row['id']]=row['result']
    store.save_match_report(list(existing.values()))
    print(path)

if __name__=='__main__':render()
