param([string]$Version='2.3.1')
$ErrorActionPreference='Stop'
if ($Version -notmatch '^\d+(\.\d+){0,2}$') { throw 'Invalid release version' }
Set-Location (Split-Path $PSScriptRoot -Parent)
$taskIcon=Join-Path (Get-Location) 'ui\icons\app.ico'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name Uninstall --distpath dist\installer-tools --workpath build\installer-tools --specpath build --icon $taskIcon installer\uninstall.py
if($LASTEXITCODE -ne 0) { throw 'Uninstaller build failed' }
& .\.venv\Scripts\python.exe scripts\prepare_installer.py --version $Version
if($LASTEXITCODE -ne 0) { throw 'Payload generation failed' }
$taskPayload=(Join-Path (Get-Location) 'build\installer-payload\payload.zip')+';.'
$taskMeta=(Join-Path (Get-Location) 'build\installer-payload\payload.json')+';.'
$taskNotice=(Join-Path (Get-Location) 'ui\OPEN_SOURCE_NOTICE.txt')+';.'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name ('GameCloudSave-Setup-V'+$Version) --distpath dist\installers --workpath build\setup --specpath build --icon $taskIcon --add-data $taskPayload --add-data $taskMeta --add-data $taskNotice installer\setup.py
if($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
