param([string]$Version='1.5')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+(\.\d+){0,2}$') { throw 'Invalid release version' }
Set-Location (Split-Path $PSScriptRoot -Parent)
$taskRclone = (Get-Command rclone -ErrorAction Stop).Source
$taskName = 'GameCloudSave-V' + $Version
& .\.venv\Scripts\python.exe scripts\make_exe_icon.py
& .\.venv\Scripts\python.exe scripts\center_icons.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
& .\.venv\Scripts\python.exe -c 'import subprocess,sys;sys.exit(subprocess.call(sys.argv[1:],stderr=subprocess.STDOUT))' .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name $taskName --icon ui\icons\app.ico --add-data 'ui;ui' --add-data 'legacy;legacy' --add-data 'scripts/export_playnite.ps1;scripts' --add-binary "$taskRclone;tools" --hidden-import sqlite3 --hidden-import dataclasses --hidden-import psutil --hidden-import PySide6.QtQuick --hidden-import PySide6.QtSvg app\main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$taskLauncher = [string][char]0x542f + [char]0x52a8 + [char]0x65b0 + [char]0x7248 + '.bat'
Copy-Item -LiteralPath scripts\launcher.template.bat -Destination (Join-Path '..' $taskLauncher) -Force
