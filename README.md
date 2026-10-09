# GameCloudSave V2.2

Windows 游戏库与存档备份管理器，Python + PySide6 / Qt Quick。支持 Playnite、Steam/Epic/Ubisoft 已安装游戏、本地 EXE/BAT/CMD 扫描；先保存本地快照，再通过 rclone WebDAV 上传到 AList。

便携版：双击上级目录的 `启动新版.bat`。安装版：运行 `dist/installers/GameCloudSave-Setup-V2.2.exe`。请先从托盘退出旧版。

[使用说明、封面来源及主题接口](docs/V2.2使用说明.md) · [主题示例](docs/theme.example.json) · [主题格式规范](docs/theme.schema.json) · [MIT 许可](LICENSE) · [第三方组件](THIRD_PARTY_NOTICES.md)

V2.2 增加收藏、最近游玩、自定义分类、系列、规则/DeepSeek 分组预览，四种主题和强调色；导入时预览与重复检查；Steam Store、VNDB 软件内封面搜索与其他网站的浏览器入口；逐页设置向导、独立批量确认页、自动备份托盘通知、安装与卸载程序。

云端按游戏名称和原存档目录分级，版本支持备注、校验与跨设备下载恢复。各电脑独立设置本地路径和凭据，不自动覆盖其他设备存档。未运行过的游戏可能没有存档；候选和分数是查找依据，需核对实际文件。

便携数据位于 `data`；安装版数据位于 `%LOCALAPPDATA%/GameCloudSave/data`。密码和 Key 使用当前 Windows 用户 DPAPI 保存，个人数据不进入 Git 或安装包。`test-data` 为隔离测试输出。真实云端回归只使用独立临时目录和生成的测试存档。

## 开发

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
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
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release.ps1 -Version 2.2
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_installer.ps1 -Version 2.2
```

构建脚本从当前虚拟环境打包 Qt、Python、rclone、卸载程序、许可证和 source.zip，无需目标电脑安装 Python。安装包按用户安装，默认创建桌面和开始菜单快捷方式，卸载保留个人数据。构建安装包需网络获取第三方许可文本。

历史源码和版本标签保留于 Git，原核心保留于 `legacy`。旧版输出保留在 `dist`，发布标签 `v2.0` 可作为回溯基线；重新运行构建脚本生成当前版本二进制。
