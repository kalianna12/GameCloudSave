# Run only after the stable executable and installer have passed their checks.
param([string]$KeepVersion='2.3.3')
$ErrorActionPreference='Stop'
$taskWorkspace=(Resolve-Path -LiteralPath (Split-Path $PSScriptRoot -Parent)).Path
$taskDist=(Resolve-Path -LiteralPath (Join-Path $taskWorkspace 'dist')).Path
if(-not (Test-Path -LiteralPath (Join-Path $taskDist 'GameCloudSave\GameCloudSave.exe'))) { throw 'Latest executable missing' }
$taskOldFolders=@(Get-ChildItem -LiteralPath $taskDist -Directory | Where-Object Name -Match '^GameCloudSave-V\d+(\.\d+){0,2}$')
$taskProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^GameCloudSave-V\d+(\.\d+){0,2}\.exe$' -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($taskDist+'\',[StringComparison]::OrdinalIgnoreCase) })
$taskPids=@($taskProcesses | ForEach-Object ProcessId)
$taskChildren=@(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -in $taskPids -and $_.Name -match 'rclone|powershell|cmd' })
if($taskChildren.Count) { throw 'An old version is running a transfer or helper. Wait until it finishes.' }
foreach($taskFolder in $taskOldFolders) {
    $taskResolved=(Resolve-Path -LiteralPath $taskFolder.FullName).Path
    if((Split-Path $taskResolved -Parent) -ne $taskDist) { throw 'Unexpected cleanup path' }
    if(Test-Path -LiteralPath (Join-Path $taskResolved 'data')) { throw 'Old release contains user data. Preserve it before cleanup.' }
}
foreach($taskProcess in $taskProcesses) { Stop-Process -Id $taskProcess.ProcessId -ErrorAction SilentlyContinue }
foreach($taskFolder in $taskOldFolders) { Remove-Item -LiteralPath $taskFolder.FullName -Recurse -Force }
$taskOldInstallers=@(Get-ChildItem -LiteralPath (Join-Path $taskDist 'installers') -File | Where-Object { $_.Name -match '^GameCloudSave-Setup-V\d+(\.\d+){0,2}\.exe$' -and $_.Name -ne ('GameCloudSave-Setup-V'+$KeepVersion+'.exe') })
foreach($taskFile in $taskOldInstallers) { Remove-Item -LiteralPath $taskFile.FullName -Force }
$taskPortableRoot=(Resolve-Path -LiteralPath (Split-Path $taskWorkspace -Parent)).Path
foreach($taskName in @('gamecloud.exe','gamecloud_gui.exe','gamecloud_gui.exe - 快捷方式.lnk','启动GUI.bat','启动监听.bat')) {
    $taskLegacy=Join-Path $taskPortableRoot $taskName
    if(Test-Path -LiteralPath $taskLegacy) {
        $taskResolved=(Resolve-Path -LiteralPath $taskLegacy).Path
        if((Split-Path $taskResolved -Parent) -ne $taskPortableRoot) { throw 'Unexpected legacy file path' }
        Remove-Item -LiteralPath $taskResolved -Force
    }
}
# Remove only the known shortcut made by an isolated upgrade regression.
$taskFixtureRoot=Join-Path $taskWorkspace '2.3.1'
$taskFixtureLink=Join-Path $taskFixtureRoot 'GameCloudSave.lnk'
if(Test-Path -LiteralPath $taskFixtureLink) {
    $taskResolved=(Resolve-Path -LiteralPath $taskFixtureRoot).Path
    if((Split-Path $taskResolved -Parent) -ne $taskWorkspace) { throw 'Unexpected fixture path' }
    Remove-Item -LiteralPath $taskFixtureLink -Force
    if(@(Get-ChildItem -LiteralPath $taskResolved -Force).Count -eq 0) { Remove-Item -LiteralPath $taskResolved }
}
$taskRemovedBuilds=0
foreach($taskBuild in @(Get-ChildItem -LiteralPath (Join-Path $taskWorkspace 'build') -Directory | Where-Object Name -match '^GameCloudSave-V\d+(\.\d+){0,2}$')) {
    $taskResolved=(Resolve-Path -LiteralPath $taskBuild.FullName).Path
    if((Split-Path $taskResolved -Parent) -ne (Join-Path $taskWorkspace 'build')) { throw 'Unexpected build path' }
    Remove-Item -LiteralPath $taskResolved -Recurse -Force;$taskRemovedBuilds++
}
$taskReport=@{stopped_old_processes=$taskProcesses.Count;removed_release_folders=$taskOldFolders.Count;removed_installers=$taskOldInstallers.Count;removed_build_folders=$taskRemovedBuilds;latest=(Join-Path $taskDist 'GameCloudSave\GameCloudSave.exe');data_preserved=$true}
$taskReport | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskWorkspace 'test-data\v231\cleanup.json') -Encoding UTF8
$taskReport | ConvertTo-Json
