param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [string]$MongoUrl = $env:MONGO_URL,
    [string]$Database = $env:DB_NAME,
    [switch]$Apply
)

if (-not $Apply) { throw "Geri yukleme icin -Apply bayragi zorunludur" }
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) { throw "Yedek dosyasi bulunamadi" }
if (-not $MongoUrl) { $MongoUrl = "mongodb://localhost:27017" }
if (-not $Database) { $Database = "shoehunter_ai" }

$resolvedArchive = (Resolve-Path -LiteralPath $Archive).Path
& mongorestore --uri $MongoUrl --nsFrom "$Database.*" --nsTo "$Database.*" --archive=$resolvedArchive --gzip
if ($LASTEXITCODE -ne 0) { throw "mongorestore basarisiz oldu" }
