param(
    [ValidateSet("desktop", "mobile")]
    [string]$Mode = "desktop",
    [int]$Port = 8931
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $root "tools\playwright-mcp\node_modules\@playwright\mcp\cli.js"
$outputDir = Join-Path $root "tools\playwright-mcp\output"

if (!(Test-Path $cli)) {
    throw "Playwright MCP is not installed. Run npm install in tools\playwright-mcp first."
}

New-Item -ItemType Directory -Force $outputDir | Out-Null

$args = @(
    $cli,
    "--headless",
    "--browser", "chrome",
    "--isolated",
    "--output-dir", $outputDir,
    "--port", $Port,
    "--host", "127.0.0.1"
)

if ($Mode -eq "mobile") {
    $args += "--mobile"
}

Write-Host "Starting Playwright MCP ($Mode) on http://127.0.0.1:$Port/mcp"
& node @args
