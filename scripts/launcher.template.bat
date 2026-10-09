@echo off
cd /d "%~dp0workspace"
set "GAMECLOUD_DATA=%~dp0workspace\data"
if exist "dist\GameCloudSave-V2.3\GameCloudSave-V2.3.exe" (
  start "" "dist\GameCloudSave-V2.3\GameCloudSave-V2.3.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V2.2.1\GameCloudSave-V2.2.1.exe" (
  start "" "dist\GameCloudSave-V2.2.1\GameCloudSave-V2.2.1.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V2.2\GameCloudSave-V2.2.exe" (
  start "" "dist\GameCloudSave-V2.2\GameCloudSave-V2.2.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V2.1\GameCloudSave-V2.1.exe" (
  start "" "dist\GameCloudSave-V2.1\GameCloudSave-V2.1.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V2.0\GameCloudSave-V2.0.exe" (
  start "" "dist\GameCloudSave-V2.0\GameCloudSave-V2.0.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.9\GameCloudSave-V1.9.exe" (
  start "" "dist\GameCloudSave-V1.9\GameCloudSave-V1.9.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.8\GameCloudSave-V1.8.exe" (
  start "" "dist\GameCloudSave-V1.8\GameCloudSave-V1.8.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.7\GameCloudSave-V1.7.exe" (
  start "" "dist\GameCloudSave-V1.7\GameCloudSave-V1.7.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.6\GameCloudSave-V1.6.exe" (
  start "" "dist\GameCloudSave-V1.6\GameCloudSave-V1.6.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.5\GameCloudSave-V1.5.exe" (
  start "" "dist\GameCloudSave-V1.5\GameCloudSave-V1.5.exe"
  exit /b 0
)
if exist "dist\GameCloudSave-V1.4\GameCloudSave-V1.4.exe" (
  start "" "dist\GameCloudSave-V1.4\GameCloudSave-V1.4.exe"
  exit /b 0
)
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
