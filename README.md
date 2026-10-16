# GameCloudSave V2.5.0

Windows 游戏库与存档备份管理器，Python + PySide6 / Qt Quick。支持 Playnite、Steam/Epic/Ubisoft 已安装游戏、本地 EXE/BAT/CMD 扫描；先保存本地快照，再通过 rclone WebDAV 上传到 AList。

从 [V2.5.0 发行页](https://github.com/kalianna12/GameCloudSave/releases/tag/v2.5.0) 下载安装包或便携包。安装版运行 `GameCloudSave-Setup-V2.5.0.exe`；便携包完整解压后运行 `GameCloudSave.exe`，无需另装 Python。当前本机便携目录仍可双击上级目录的 `启动新版.bat`。

V2.5.0 保留原版默认布局，新增书柜 SHELF、影院 CINEMA、星图 ATLAS，支持分组、随机选游戏、木材与日光、Playnite 媒体和动态星云。整合退出后一次自动备份、本机自动备份默认保留 5 份、页内封面/横幅搜索、资料补全预览、全屏、启动窗口交接和手柄导航修复。存档时间跟随电脑时区；已有资料保留，候选需预览后应用。

[完整发布说明](docs/V2.5.0发布说明.md) · [安装、更新和卸载说明](docs/安装与便携使用说明.txt)

V2.3.3 修复重复焦点高亮，首页与子页面支持平滑手柄滚动。手柄操作隐藏鼠标并暂停悬停，移动鼠标恢复；导航提示音可在个性化中关闭。沿用固定标签词库和已有分类保护。[本轮说明与验证](docs/V2.3.3输入与网络.md)

V2.3.1 精简查找页和首页文字，统一输入框、按钮与下拉框高度。查找显示游戏进度，可继续搜索、浏览结果或停止；Playnite、DeepSeek 和 DAV 在同一个向导内配置。重复启动唤回已有窗口，开发与打包使用固定程序目录。[验证记录及发行限制](docs/V2.3.1验证记录.md)

V2.3 重构游戏库首页：最近游戏、类别磁贴、系列磁贴、基于最近游玩的本地推荐、类型与风格横排。主分类收敛为九个默认选项，标签可多选、组合搜索；只有至少两款不同游戏才展示系列。平台归属来自 Playnite 库插件或实际平台安装记录，Steam 封面与商店链接只作为元数据。支持更新已导入 Playnite 信息，导入真实最近游玩时间、类型与标签。旧分类迁移保留为标签，并备份原数据。

[V2.3 平台判据、主页与标签说明](docs/V2.3游戏库主页.md)

V2.2.1 将存档候选评分默认改为 DeepSeek 75%、本地规则 25%。在“DeepSeek / API Key”面板可调整权重；低分配置目录也参与降分，已保存的目录比较结果自动按新权重重算，不改变人工确认的存档路径。只有单个候选时也比较目录，最多比较 30 个候选；未开启或请求失败时使用本地规则。

[使用说明、封面来源及主题接口](docs/V2.2使用说明.md) · [主题示例](docs/theme.example.json) · [主题格式规范](docs/theme.schema.json) · [MIT 许可](LICENSE) · [第三方组件](THIRD_PARTY_NOTICES.md)

V2.2 增加收藏、最近游玩、自定义分类、系列、规则/DeepSeek 分组预览，四种主题和强调色；导入时预览与重复检查；Steam Store、VNDB 软件内封面搜索与其他网站的浏览器入口；逐页设置向导、独立批量确认页、自动备份托盘通知、安装与卸载程序。

云端按游戏名称和原存档目录分级，版本支持备注、校验与跨设备下载恢复。各电脑独立设置本地路径和凭据，不自动覆盖其他设备存档。未运行过的游戏可能没有存档；候选和分数是查找依据，需核对实际文件。

便携数据位于 `data`；安装版数据位于 `%LOCALAPPDATA%/GameCloudSave/data`。密码和 Key 使用当前 Windows 用户 DPAPI 保存，个人数据不进入 Git 或安装包。`test-data` 为隔离测试输出。真实云端回归只使用独立临时目录和生成的测试存档。

## 开发

本机源码预览可双击 workspace 下的 `启动源码版.bat`，使用隔离的 `test-data/source-preview`。V2.5.0 已将本轮源码改动纳入便携程序和安装包；见 [设计与体验说明](docs/首页适配与主题扩展.md)。后续日常修改仍仅测试源码，发行文件以对应版本标签为准。

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
$env:GAMECLOUD_DATA = "$PWD\test-data\source-preview"
.\.venv\Scripts\python.exe app/main.py
```

需要 Windows 和 rclone（放入 PATH）。Playnite 读取使用其 LiteDB.dll，只读导出数据库副本，客户端锁库时提示关闭后重试。扫描不执行游戏启动文件。

## 验证与打包

```powershell
.\.venv\Scripts\python.exe tests/test_regression.py
.\.venv\Scripts\python.exe tests/test_sources_and_sync.py
.\.venv\Scripts\python.exe tests/test_library_v22.py
.\.venv\Scripts\python.exe tests/test_library_ui_v22.py
.\.venv\Scripts\python.exe tests/test_wizard_batch_v21.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release.ps1 -Version 2.5.0
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_installer.ps1 -Version 2.5.0
.\.venv\Scripts\python.exe scripts/package_release.py --version 2.5.0
```

构建脚本从当前虚拟环境打包 Qt、Python、rclone、卸载程序、许可证和 source.zip，无需目标电脑安装 Python。安装包按用户安装，默认创建桌面和开始菜单快捷方式，卸载保留个人数据。构建安装包需网络获取第三方许可文本。

日常小版本修改只运行源码并使用隔离数据，不同步便携版或重建安装包；用户明确要求打包与发布后才运行构建脚本。可执行文件固定输出至 `dist/GameCloudSave/GameCloudSave.exe`，不按版本复制多份便携程序。旧版本源码和标签保留于 Git，需要回退时从对应标签重新构建。
