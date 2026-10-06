@echo off
cd /d "%~dp0workspace"
set "GAMECLOUD_DATA=%~dp0workspace\data"
if exist "dist\GameCloudSave-V1.3\GameCloudSave-V1.3.exe" (
  start "" "dist\GameCloudSave-V1.3\GameCloudSave-V1.3.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.2\GameCloudSave-V1.2.exe" (
  start "" "dist\GameCloudSave-V1.2\GameCloudSave-V1.2.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.1\GameCloudSave-V1.1.exe" (
  start "" "dist\GameCloudSave-V1.1\GameCloudSave-V1.1.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1\GameCloudSave-V1.exe" (
  start "" "dist\GameCloudSave-V1\GameCloudSave-V1.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please install workspace dependencies first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "app\main.py"
