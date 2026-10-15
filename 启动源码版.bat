@echo off
cd /d "%~dp0"
set "GAMECLOUD_DATA=%~dp0test-data\source-preview"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Source environment not found. Install workspace requirements first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "app\main.py"
