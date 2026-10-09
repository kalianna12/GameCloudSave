# GameCloudSave

本地游戏云存档工具（CLI 版），支持：
- 添加游戏（自动尝试识别存档目录）
- 手动设置存档目录
- 监听游戏进程，启动/退出时自动快照
- 游戏运行中手动快照（带时间和自定义备注）
- 快照历史与恢复
- 云端上传（通过 `rclone`，可接入百度网盘）

## 1. 安装

```powershell
cd C:\Users\kalianna\Documents\Playground
python -m pip install -r requirements.txt
```

## 2. 初始化

```powershell
python .\gamecloud.py init
```

数据目录默认在：
- `%APPDATA%\GameCloudSave`
- 快照文件在 `%APPDATA%\GameCloudSave\snapshots`

可改为自定义快照目录（例如 D 盘）：
```powershell
python .\gamecloud.py config-snapshot --path "D:\GameCloudSaveSnapshots"
```

## 3. 配置百度网盘云端（通过 rclone）

1) 安装并配置 rclone（只需一次）：
```powershell
rclone config
```
在交互里添加一个 remote，例如命名为 `baidu`。

2) 设置默认上传位置：
```powershell
python .\gamecloud.py config-cloud --remote baidu --path game-saves
```

## 4. 添加游戏

### 自动识别存档目录
```powershell
python .\gamecloud.py add "Cyberpunk 2077" --exe "D:\Games\Cyberpunk2077\bin\x64\Cyberpunk2077.exe"
```

### 自动识别失败时手动指定
```powershell
python .\gamecloud.py add "Elden Ring" --exe "D:\Games\EldenRing\Game\eldenring.exe" --save-dir "C:\Users\kalianna\AppData\Roaming\EldenRing"
```

### 查看已添加游戏
```powershell
python .\gamecloud.py list
```

## 5. 自动备份监听

启动监听（常驻运行）：
```powershell
python .\gamecloud.py watch --interval 3
```

行为：
- 检测到游戏进程启动 -> 自动快照一次并尝试上传
- 检测到游戏进程退出 -> 自动快照一次并尝试上传

## GUI 桌面版

启动图形界面：
```powershell
python .\gamecloud_gui.py
```

界面功能：
- 添加游戏（自动识别或手动选择存档目录）
- 修改存档目录
- 配置每个游戏的云端 remote/path
- 设置快照目录（快照 zip 本地保存位置）
- 手动存档并写备注
- 启动/停止监听（自动在启动和退出时备份）
- 查看历史并恢复选中快照

## 6. 游戏运行中手动打点（带备注）

```powershell
python .\gamecloud.py save "Cyberpunk 2077" --note "打完主线第3章，准备试不同分支"
```

## 7. 历史与恢复

查看快照历史：
```powershell
python .\gamecloud.py history "Cyberpunk 2077" --limit 20
```

恢复某条快照：
```powershell
python .\gamecloud.py restore 12
```

恢复时会先自动备份当前存档，再覆盖。

## 8. 常见问题

1) `watch` 报错缺少 `psutil`
- 执行：`python -m pip install -r requirements.txt`

2) 上传失败
- 检查 `rclone` 是否安装：`rclone version`
- 检查 remote 是否可用：`rclone lsd baidu:`

3) 自动识别存档目录不准
- 用 `set-save` 手动修正：
```powershell
python .\gamecloud.py set-save "Cyberpunk 2077" "C:\Path\To\SaveDir"
```

## 9. 像 Git 一样的使用习惯

- `save --note` 类似 `commit -m`
- `history` 类似 `log`
- `restore` 类似 `checkout` 到某次存档

这套工具是本地优先，云端只是同步副本，避免网络问题影响游戏。
