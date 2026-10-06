$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$taskRclone = (Get-Command rclone -ErrorAction Stop).Source
& .\.venv\Scripts\python.exe scripts\make_exe_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
& .\.venv\Scripts\python.exe -c 'import subprocess,sys;sys.exit(subprocess.call(sys.argv[1:],stderr=subprocess.STDOUT))' .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name GameCloudSave-V1 --icon ui\icons\app.ico --add-data 'ui;ui' --add-data 'legacy;legacy' --add-data 'scripts/export_playnite.ps1;scripts' --add-binary "$taskRclone;tools" --hidden-import sqlite3 --hidden-import dataclasses --hidden-import psutil --hidden-import PySide6.QtQuick --hidden-import PySide6.QtSvg app\main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
