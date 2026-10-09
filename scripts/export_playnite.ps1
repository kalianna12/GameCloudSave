param([string]$AssemblyPath, [string]$DatabasePath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -Path $AssemblyPath
$taskLibrary = [LiteDB.LiteDatabase]::new("Filename=$DatabasePath;ReadOnly=true", $null, $null)
try {
    $taskMaps=@{}
    foreach($taskKind in @('sources','genres','tags')) {
        $taskPath=Join-Path (Split-Path -Parent $DatabasePath) ($taskKind+'.db')
        $taskMap=@{}
        if(Test-Path -LiteralPath $taskPath) {
            $taskExtra=[LiteDB.LiteDatabase]::new("Filename=$taskPath;ReadOnly=true",$null,$null)
            try {
                foreach($taskCollection in $taskExtra.GetCollectionNames()) {
                    foreach($taskEntry in $taskExtra.GetCollection($taskCollection).FindAll()) { $taskMap[$taskEntry['_id'].AsGuid.ToString()]=$taskEntry['Name'].AsString }
                }
            } finally { $taskExtra.Dispose() }
        }
        $taskMaps[$taskKind]=$taskMap
    }
    $taskRows = [System.Collections.Generic.List[string]]::new()
    foreach ($taskGame in $taskLibrary.GetCollection('Game').FindAll()) {
        foreach($taskPair in @(@('genres','GenreIds','ResolvedGenres'),@('tags','TagIds','ResolvedTags'))) {
            $taskValues=[LiteDB.BsonArray]::new()
            if($taskGame.ContainsKey($taskPair[1]) -and $taskGame[$taskPair[1]].IsArray) {
                foreach($taskId in $taskGame[$taskPair[1]].AsArray) {
                    $taskName=$taskMaps[$taskPair[0]][$taskId.AsGuid.ToString()]
                    if($taskName) { $taskValues.Add([LiteDB.BsonValue]::new([string]$taskName)) }
                }
            }
            $taskGame[$taskPair[2]]=$taskValues
        }
        $taskRows.Add([LiteDB.JsonSerializer]::Serialize($taskGame))
    }
    [System.IO.File]::WriteAllText($OutputPath, '[' + ($taskRows -join ',') + ']', [System.Text.UTF8Encoding]::new($false))
} finally { $taskLibrary.Dispose() }
