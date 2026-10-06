param([string]$AssemblyPath, [string]$DatabasePath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -Path $AssemblyPath
$taskLibrary = [LiteDB.LiteDatabase]::new("Filename=$DatabasePath;ReadOnly=true", $null, $null)
try {
    $taskRows = [System.Collections.Generic.List[string]]::new()
    foreach ($taskGame in $taskLibrary.GetCollection('Game').FindAll()) {
        $taskRows.Add([LiteDB.JsonSerializer]::Serialize($taskGame))
    }
    [System.IO.File]::WriteAllText($OutputPath, '[' + ($taskRows -join ',') + ']', [System.Text.UTF8Encoding]::new($false))
} finally { $taskLibrary.Dispose() }
