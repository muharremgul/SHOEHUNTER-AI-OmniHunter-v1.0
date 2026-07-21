param(
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Starter = Join-Path $Root "scripts\start-lan.ps1"

if (-not (Test-Path -LiteralPath $Starter)) {
    throw "Yerel ag baslatma betigi bulunamadi: $Starter"
}

& $Starter -FrontendPort $FrontendPort -BackendPort $BackendPort
