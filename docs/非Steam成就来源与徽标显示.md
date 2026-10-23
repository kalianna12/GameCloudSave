# 非 Steam 成就来源与徽标显示

2026-10-23，源码迭代；没有打包、同步便携版或发布发行包。

## 成就徽标

个性化 → 封面成就徽标：

- 悬停或选中时显示（默认）：鼠标离开且没有选中时隐藏；手柄选中的封面显示。
- 始终显示：所有已匹配成就的封面显示。
- 隐藏：仅隐藏封面徽标，保留统计、监听、成就页面及游戏内弹窗设置。

适用于默认主页和内页、书柜、影院、星图。没有成就数据的游戏不画空徽标。“新加入”保持原位，成就徽标放在它下方，显隐不引起标记跳动。徽标不拦截鼠标，不改变封面原有点击行为。书柜关闭界面动效后仍可正常悬停显示。

进度圈按完成比例连续渐变：0 为灰蓝，低完成度偏蓝，中段青色，高完成度青绿，100% 金色；始终保留完成数／总数。没有持续动画或定时重绘，仅进度、尺寸、显隐变化时重画。

## 非 Steam 成就如何实现

必须分别取得两种数据：

1. **定义**：游戏版本／App ID → 成就内部 ID、名称、描述、图标、上限。当前优先 Steam 公开定义，再用本地缓存／导入定义和 SteamHunters；其网络访问情况独立于本机进度。
2. **进度**：该游戏实际生成的本机解锁标记、解锁时间、计数。按照内部 ID 对应定义，不能凭中文标题、普通存档存在或数值达到上限推断解锁。

Achievement Watcher 的核心也是“读取已有记录＋匹配定义”，不会让原本没有成就逻辑的游戏自动产生记录。核查了其 README、兼容文档、`steam.js`、`achievements.js` 和 `sse.js`，以及现有 PlayniteAchievements 参考源码。AW 的兼容 Wiki 较旧，实际格式以解析代码为依据；本程序没有安装或启动 AW 服务，也没有整体复制其 LGPL 实现。

| 真实进度来源 | 当前处理 | 边界 |
| --- | --- | --- |
| Goldberg／GSE 生成的 `achievements.json` | 读取 `earned`、时间、progress 等已有字段 | 只有定义 JSON 不算记录；不同用户目录分别选择 |
| CODEX／RUNE 等兼容 INI | 读取 Achieved、HaveAchieved、State、Unlocked、时间及 CurProgress／MaxProgress | 名称相同可能格式不同；只支持实际识别到的字段 |
| INI 内容的 Achievements.Bin、achieve.dat、achiev.ini、stats.ini、CreamAPI.Achievements.cfg | 按文本 INI 读取，支持独立 AchievementsUnlockTimes 及 ACHIEVE_DATA 节 | 扩展名不能证明内容，未知二进制不当作文本支持 |
| Steam 客户端的本机缓存 | 已有配对 Schema／UserGameStats BIN 适配 | 要匹配账号与 App ID；Steam 条目只统计、不重复弹窗 |
| SmartSteamEmu 的 `stats.bin` | **尚未适配** | AW 使用 24 字节条目和 CRC32 对应定义；不能交给 Steam Binary KeyValues 解析器，也不能把值为 1 的普通统计误认成就 |
| GOG Galaxy、Ubisoft、Epic 或模拟器奖杯 | **尚未适配这些本地格式** | 需要独立的数据格式、平台 ID 和账号映射，Steam App ID 不能通用 |
| 游戏自有成就／普通存档 | **需按游戏适配** | 有明确的解锁标记才可接入；无成就逻辑、仅有封面和定义时无法自动判断 |

### 本轮补齐

- 补查 `%APPDATA%/EMPRESS`、`Steam/CODEX`、CreamAPI，Public 下 EMPRESS，`%PROGRAMDATA%/Steam/<账号>/<AppID>`，以及系统实际“文档”（含重定向）下 SKIDROW／OnlineFix。仅查目标 App ID 和游戏已配置目录，限制深度、数量并跳过重解析点，不扫整盘。
- 补齐 CurProgress／MaxProgress、HaveAchievedTime、State、JSON `apiname`、独立 INI 时间节和上述文本记录文件名。
- 已有显式 false／0 标记优先，即使有时间或计数等于上限也保持未解锁。保留大小限制、首次基线、不重复弹窗及账号隔离。
- 游戏页分别显示“定义已缓存”“进度读到多少项／对应多少项”。ID 完全不匹配会提示核对版本；成就管理列表不再仅凭文件存在就显示“已就绪”。
- 检测详情报告不含解锁标记的疑似配置／统计文件。网络匹配成功不再意味着进度就绪。

### 实际核查及下一步

只读读取用户现有库中的卡赞条目，用扩展后的目录规则重新检测；当次结果：没有发现支持的记录或本地定义，未启动游戏、未改游戏目录或存档。该结果仅代表检测范围内没有发现文件，不能证明游戏所有潜在输出路径都不存在。

因此当前不能宣称卡赞已经实现真实自动解锁。下一步最有价值的是在一次真实解锁前后，确认该版本实际写出的文件、注册表或日志，再选择兼容解析器或单独实现适配；若游戏没有可读输出，则需要游戏专用接口／插件方案。不会通过创建空 INI、写入游戏存档或下载一份成就列表假装解决。

## 验证

- 22 项独立单元测试：原有 JSON／INI、Steam BIN、账号隔离与新增字段／目录／设置持久化。
- 实际 QML 鼠标悬停、手柄选中、隐藏和始终显示、五种进度颜色、鼠标穿透；关闭动效时仍可显示书柜徽标。
- 四布局、新加入标记不跳动、成就管理全页、批量、Steam 静默统计、异步监听／断写回归通过。
- 普通游戏临时窗口弹窗回归本轮未通过显示断言：进一步诊断为测试进程的库窗口保持前台，临时游戏窗口未能激活；文件监听已识别第 2 个解锁并进入弹窗队列，前台检查按设计隐藏它。本轮不将普通／Anime4K 游戏弹窗计作重新验证通过（上一轮结果见原文档），待能稳定切换前台时重验。没有为通过测试放松弹窗的前台保护。
- 480 游戏导航回归：主页派发 P95 8.42ms，帧 P95 26.79ms，最长 31.29ms；0 帧超过 50ms。为隔离数据／模拟输入，不能替代真实手柄与真实游戏解锁体验。
- 真实 data 的 287 个文件 SHA256 与基线一致。仅测试源码版，便携版未同步。

## 参考来源

- [Achievement Watcher README](https://github.com/xan105/Achievement-Watcher/blob/1.x/README.md)
- [Achievement Watcher 兼容文档](https://github.com/xan105/Achievement-Watcher/wiki/Compatibility)
- [本机记录定位及文件格式](https://github.com/xan105/Achievement-Watcher/blob/1.x/app/parser/steam.js)
- [内部 ID／状态对应逻辑](https://github.com/xan105/Achievement-Watcher/blob/1.x/app/parser/achievements.js)
- [SmartSteamEmu 二进制格式](https://github.com/xan105/Achievement-Watcher/blob/1.x/app/parser/sse.js)
- [用户指定 PlayniteAchievements](https://github.com/justin-delano/PlayniteAchievements)

本轮仅依据公开格式独立扩展已有 Python 解析器；上一轮适配的上游 MIT Steam BIN 代码保留了原许可和署名。以上第三方兼容范围与本程序已实现范围分别列出，不表示全量兼容。
