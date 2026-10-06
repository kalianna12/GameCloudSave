# GameCloudSave V1.1 工作目录

源码从 D:/Playground/06_脚本与生成器 复制迁入 legacy，保留原位置以便回退。当前便携版 EXE 不变。

- legacy：现有 Python 核心、Tkinter 界面、依赖、旧打包配置。
- docs：上传操作说明及重构方案。
- tests：隔离验证脚本。
- test-data：仅测试数据，不连接真实游戏存档。

V1.1 已完成，双击上级目录“启动新版.bat”。优先运行 dist/GameCloudSave-V1.1 下的独立 EXE；V1 二进制仍保留，源码运行环境也已配置。

新 UI 在 ui，Python 服务与界面桥接在 app。共享游戏清单和封面在 data，电脑独立设置在 data/machines/<机器与用户标识>。密码/API Key 使用 Windows DPAPI 保存，不在 JSON 中保存明文。启动脚本把共享数据位置指定为 workspace/data。

当前使用方法和测试结果见 docs/V1.1使用与测试.md。docs 中的“第一版”文档保留为 V1.0 历史记录。

开发测试（在 workspace 下执行）：

```powershell
.\.venv\Scripts\python.exe tests\test_regression.py
.\.venv\Scripts\python.exe tests\test_watcher.py
.\.venv\Scripts\python.exe tests\test_iteration.py
.\.venv\Scripts\python.exe tests\ui_iteration.py
```

live_dav.py 使用本机已保存的连接，上传并清理独立测试 ZIP 和 JSON。ui_iteration.py 也会创建、预览、清理一个独立远端 JSON。live_ai.py 使用已保存的 DeepSeek Key 执行真实匹配，消耗 API 配额并保存匹配报告。

重新打包：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release.ps1`。构建脚本使用 requirements-dev.txt 中的依赖，并从 scripts/launcher.template.bat 更新上级启动脚本。打包目录包含 Qt、Python 运行库与 rclone，不需要在目标电脑安装 Python。

Git 仓库位于 workspace。V1.0 基线标签：v1.0-baseline；本轮版本标签：v1.1。运行旧版二进制可选择 dist/GameCloudSave-V1/GameCloudSave-V1.exe。回溯源码后可运行 `.\.venv\Scripts\python.exe app\main.py` 验证对应代码版本；启动新版.bat 始终优先运行已打包的 V1.1。

旧 spec 含旧源码绝对路径，不能直接作为新版打包配置。
