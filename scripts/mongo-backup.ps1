param(
    [string]$MongoUrl = $env:MONGO_URL,
    [string]$Database = $env:DB_NAME,
    [string]$Destination = ""
)

if (-not $MongoUrl) { $MongoUrl = "mongodb://localhost:27017" }
if (-not $Database) { $Database = "shoehunter_ai" }
if (-not $Destination) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $Destination = Join-Path $PSScriptRoot "..\backups\shoehunter-mongo-$stamp.archive.gz"
}

$resolvedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $Destination))
New-Item -ItemType Directory -Force -Path $resolvedParent | Out-Null
& mongodump --uri $MongoUrl --db $Database --archive=$Destination --gzip
if ($LASTEXITCODE -ne 0) { throw "mongodump basarisiz oldu" }
Write-Output ([System.IO.Path]::GetFullPath($Destination))
