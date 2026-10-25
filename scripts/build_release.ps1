param([string]$Version='2.7.0')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+(\.\d+){0,2}$') { throw 'Invalid release version' }
Set-Location (Split-Path $PSScriptRoot -Parent)
$taskName = 'GameCloudSave'
& .\.venv\Scripts\python.exe scripts\write_version_info.py $Version
& .\.venv\Scripts\python.exe scripts\make_exe_icon.py
& .\.venv\Scripts\python.exe scripts\center_icons.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
& .\.venv\Scripts\python.exe -c 'import subprocess,sys;sys.exit(subprocess.call(sys.argv[1:],stderr=subprocess.STDOUT))' .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name $taskName --version-file build\version_info.txt --icon ui\icons\app.ico --add-data 'ui;ui' --add-data 'legacy/gamecloud.py;legacy' --add-data 'scripts/export_playnite.ps1;scripts' --hidden-import sqlite3 --hidden-import dataclasses --hidden-import psutil --hidden-import PySide6.QtQuick --hidden-import PySide6.QtSvg --hidden-import PySide6.QtMultimedia --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --hidden-import vgamepad --collect-binaries vgamepad --copy-metadata vgamepad app\main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& .\.venv\Scripts\python.exe scripts\prune_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime pruning failed' }
$taskLauncher = [string][char]0x542f + [char]0x52a8 + [char]0x65b0 + [char]0x7248 + '.bat'
Copy-Item -LiteralPath scripts\launcher.template.bat -Destination (Join-Path '..' $taskLauncher) -Force
