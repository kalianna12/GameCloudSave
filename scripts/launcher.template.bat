@echo off
cd /d "%~dp0workspace"
set "GAMECLOUD_DATA=%~dp0workspace\data"
if exist "dist\GameCloudSave\GameCloudSave.exe" (
  start "" "dist\GameCloudSave\GameCloudSave.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please install workspace dependencies first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "app\main.py"
