param(
  [string]$Target = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdministrator) {
  Write-Host "Tailscale Windows servisine erisim icin yonetici onayi istenecek."
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $PSCommandPath),
    "-Target", ('"{0}"' -f $Target)
  )
  $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
  exit $process.ExitCode
}

$ResultPath = Join-Path $PSScriptRoot "..\mobile\tailscale-connection.json"
trap {
  $failure = @{
    ok = $false
    error = [string]$_.Exception.Message
    updated_at = [DateTimeOffset]::Now.ToString("o")
  } | ConvertTo-Json
  [IO.File]::WriteAllText($ResultPath, $failure, [Text.UTF8Encoding]::new($false))
  throw
}

if (-not (Test-Path -LiteralPath $Tailscale)) {
  throw "Tailscale kurulu degil. Once resmi Windows istemcisini kurun."
}

try {
  $health = Invoke-WebRequest "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 8
  if ($health.StatusCode -ne 200) { throw "HTTP $($health.StatusCode)" }
} catch {
  throw "ShopHunter backend calismiyor. Once mobile/start-mobile-test-server.ps1 calistirin."
}

$statusRaw = & $Tailscale status --json 2>$null
$status = if ($statusRaw) {
  try { $statusRaw | ConvertFrom-Json } catch { $null }
} else { $null }
if (-not $status -or $status.BackendState -ne "Running") {
  Write-Host "Tailscale hesap girisi gerekli. Tarayicida acilan adresten giris yapin."
  & $Tailscale up --unattended
  if ($LASTEXITCODE -ne 0) {
    throw "Tailscale girisi tamamlanamadi. Sistem tepsisindeki Tailscale simgesinden Log in secin."
  }
  $status = & $Tailscale status --json | ConvertFrom-Json
  if ($status.BackendState -ne "Running") {
    throw "Tailscale baglantisi Running durumuna gecmedi."
  }
}

& $Tailscale serve --bg --yes $Target
if ($LASTEXITCODE -ne 0) {
  throw "Tailscale Serve yapilandirilamadi. Komutun gosterdigi HTTPS etkinlestirme adresini onaylayin."
}

$status = & $Tailscale status --json | ConvertFrom-Json
$dnsName = [string]$status.Self.DNSName
$url = if ($dnsName) { "https://$($dnsName.TrimEnd('.'))" } else { "" }

Write-Host "ShopHunter yalniz Tailscale ozel aginda HTTPS ile hazir."
if ($url) { Write-Host "Uygulama sunucu adresi: $url" }
& $Tailscale serve status

$result = @{
  ok = $true
  url = $url
  target = $Target
  dns_name = $dnsName.TrimEnd('.')
  updated_at = [DateTimeOffset]::Now.ToString("o")
} | ConvertTo-Json
[IO.File]::WriteAllText($ResultPath, $result, [Text.UTF8Encoding]::new($false))
