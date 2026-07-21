param(
    [switch]$SkipDependencies
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendEnv = Join-Path $ProjectRoot "backend\.env"
$FrontendEnv = Join-Path $ProjectRoot "frontend\.env"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function New-SecretValue {
    $bytes = New-Object byte[] 48
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value,
        [switch]$OnlyWhenEmpty
    )

    $content = [System.IO.File]::ReadAllText($Path)
    $pattern = "(?m)^" + [Regex]::Escape($Name) + "=(.*)$"
    $match = [Regex]::Match($content, $pattern)
    if ($match.Success) {
        if ($OnlyWhenEmpty -and $match.Groups[1].Value.Trim().Length -gt 0) {
            return
        }
        $content = [Regex]::Replace($content, $pattern, "$Name=$Value", 1)
    }
    else {
        $content = $content.TrimEnd() + [Environment]::NewLine + "$Name=$Value" + [Environment]::NewLine
    }
    [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding($false)))
}

Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath $BackendEnv)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "backend\.env.example") -Destination $BackendEnv
    Write-Host "backend/.env created."
}

if (-not (Test-Path -LiteralPath $FrontendEnv)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "frontend\.env.example") -Destination $FrontendEnv
    Write-Host "frontend/.env created."
}

Set-EnvValue -Path $BackendEnv -Name "APP_SECRET_KEY" -Value (New-SecretValue) -OnlyWhenEmpty

if (-not $SkipDependencies) {
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv (Join-Path $ProjectRoot ".venv")
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv (Join-Path $ProjectRoot ".venv")
        }
        else {
            throw "Python 3 was not found."
        }
    }

    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt")
    & $VenvPython -m playwright install chromium

    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "Node.js and npm were not found."
    }
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        & npm.cmd ci
    }
    finally {
        Pop-Location
    }
}

if (-not (Get-Command mongosh -ErrorAction SilentlyContinue) -and -not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Warning "MongoDB was not found. Install MongoDB 7 or use Docker Compose before starting the site."
}

Write-Host "Setup completed."
Write-Host "Start backend:  Set-Location backend; ..\.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000"
Write-Host "Start frontend: Set-Location frontend; npm.cmd start"
Write-Host "Open: http://localhost:3000"
Write-Host "The first-run screen will ask for the administrator password."
