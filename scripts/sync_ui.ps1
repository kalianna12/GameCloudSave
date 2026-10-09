# Fast preview for QML-only changes. Python changes still need build_release.ps1.
$ErrorActionPreference='Stop'
$taskWorkspace=(Resolve-Path -LiteralPath (Split-Path $PSScriptRoot -Parent)).Path
$taskDestination=Join-Path $taskWorkspace 'dist\GameCloudSave\_internal\ui'
if(-not (Test-Path -LiteralPath (Join-Path $taskWorkspace 'dist\GameCloudSave\GameCloudSave.exe'))) { throw 'Build the executable first' }
if(-not (Test-Path -LiteralPath $taskDestination)) { throw 'Packaged UI directory missing' }
Copy-Item -LiteralPath (Join-Path $taskWorkspace 'ui') -Destination (Join-Path $taskWorkspace 'dist\GameCloudSave\_internal') -Recurse -Force
Write-Output 'UI resources updated in the existing executable directory.'
