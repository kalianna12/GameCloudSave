# GameCloudSave V1 工作目录

源码从 D:/Playground/06_脚本与生成器 复制迁入 legacy，保留原位置以便回退。当前便携版 EXE 不变。

- legacy：现有 Python 核心、Tkinter 界面、依赖、旧打包配置。
- docs：上传操作说明及重构方案。
- tests：隔离验证脚本。
- test-data：仅测试数据，不连接真实游戏存档。

第一版已完成，双击上级目录“启动新版.bat”。优先运行 dist/GameCloudSave-V1 下的独立 EXE；源码运行环境也已配置。

新 UI 在 ui，Python 服务与界面桥接在 app。共享游戏清单和封面在 data，电脑独立设置在 data/machines/<机器与用户标识>。密码/API Key 使用 Windows DPAPI 保存，不在 JSON 中保存明文。启动脚本把共享数据位置指定为 workspace/data。

使用方法见 docs/第一版使用说明.md，测试结果见 docs/第一版测试报告.md。

开发测试（在 workspace 下执行）：

```powershell
.\.venv\Scripts\python.exe tests\test_regression.py
.\.venv\Scripts\python.exe tests\test_watcher.py
.\.venv\Scripts\python.exe tests\ui_regression.py
```

live_dav.py 使用本机已保存的连接，上传并清理独立测试 ZIP。不要把它当作普通离线测试运行。

重新打包：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release.ps1`。打包目录包含 Qt、Python 运行库与 rclone，不需要在目标电脑安装 Python。

旧 spec 含旧源码绝对路径，不能直接作为新版打包配置。
