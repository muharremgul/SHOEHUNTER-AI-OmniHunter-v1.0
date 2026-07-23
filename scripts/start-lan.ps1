param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8000,
  [string]$FirebaseProjectId = "shophunter-radar",
  [string]$FirebaseCredentials = (Join-Path $env:USERPROFILE "Documents\ShoeHunter-Secrets\shoehunter-firebase-admin.json")
)

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ReactScripts = Join-Path $Frontend "node_modules\react-scripts\scripts\start.js"
$BundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$Node = if (Test-Path -LiteralPath $BundledNode) { $BundledNode } else { (Get-Command node -ErrorAction Stop).Source }
$LogDir = Join-Path $Root "mobile\logs"

if (-not (Test-Path -LiteralPath $Python)) { throw "Proje Python ortami bulunamadi: $Python" }
if (-not (Test-Path -LiteralPath $ReactScripts)) { throw "Frontend bagimliliklari bulunamadi. Once kurulum yapin." }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Some desktop launchers expose both PATH and Path. Windows Start-Process treats
# them as duplicate dictionary keys, so keep one canonical process value.
$ProcessPath = $env:Path
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $ProcessPath, "Process")

$ip = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
  Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $_.IPAddressToString -notlike "127.*" } |
  Select-Object -First 1 -ExpandProperty IPAddressToString

if (-not $ip) {
  Write-Host "Yerel IP bulunamadi. Bilgisayar Wi-Fi/Ethernet agina bagli mi?"
  exit 1
}

Write-Host "ShoeHunter yerel ag modu baslatiliyor..."
Write-Host "Telefon/tablet adresi: http://$ip`:$FrontendPort"
Write-Host "API adresi: http://$ip`:$BackendPort"

$env:CORS_ORIGINS = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort,http://$ip`:$FrontendPort"
$env:FIREBASE_PROJECT_ID = $FirebaseProjectId
if (Test-Path -LiteralPath $FirebaseCredentials) {
  $env:GOOGLE_APPLICATION_CREDENTIALS = $FirebaseCredentials
  Write-Host "FCM HTTP v1 hazir: $FirebaseProjectId"
} else {
  Remove-Item Env:GOOGLE_APPLICATION_CREDENTIALS -ErrorAction SilentlyContinue
  Write-Warning "FCM servis hesabi bulunamadi; yerel bildirim sorgulama yedegi calismaya devam edecek."
}
# Bu betik kalici scheduler ve kuyruga ozel iki worker baslatir. Sunucunun
# kendi icindeki scheduler/worker da acik kalirsa browser kuyrugundaki ayni isi
# sunucu sureci kapabilir ve Playwright yanlis Windows oturumunda baslayabilir.
# Kuyruklarin tek sahibi olmasi icin bu calistirma modunda gomulu isciyi kapat.
$env:EMBEDDED_SCHEDULER = "false"
$BackendProcess = Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","server:app","--host","0.0.0.0","--port",$BackendPort -WorkingDirectory $Backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "backend.out.log") -RedirectStandardError (Join-Path $LogDir "backend.err.log") -PassThru

$env:WORKER_QUEUE = "default"
$Worker1Process = Start-Process -FilePath $Python -ArgumentList "worker.py" -WorkingDirectory $Backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "worker_default.out.log") -RedirectStandardError (Join-Path $LogDir "worker_default.err.log") -PassThru

$env:WORKER_QUEUE = "browser"
$Worker2Process = Start-Process -FilePath $Python -ArgumentList "worker.py" -WorkingDirectory $Backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "worker_browser.out.log") -RedirectStandardError (Join-Path $LogDir "worker_browser.err.log") -PassThru

$SchedulerProcess = Start-Process -FilePath $Python -ArgumentList "scheduler_worker.py" -WorkingDirectory $Backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "scheduler.out.log") -RedirectStandardError (Join-Path $LogDir "scheduler.err.log") -PassThru

$env:HOST = "0.0.0.0"
$env:PORT = "$FrontendPort"
$env:BROWSER = "none"
Remove-Item Env:REACT_APP_BACKEND_URL -ErrorAction SilentlyContinue
$FrontendProcess = Start-Process -FilePath $Node -ArgumentList $ReactScripts -WorkingDirectory $Frontend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogDir "frontend.out.log") -RedirectStandardError (Join-Path $LogDir "frontend.err.log") -PassThru

Write-Host "Backend PID: $($BackendProcess.Id)"
Write-Host "Worker(Default) PID: $($Worker1Process.Id)"
Write-Host "Worker(Browser) PID: $($Worker2Process.Id)"
Write-Host "Scheduler PID: $($SchedulerProcess.Id)"
Write-Host "Frontend PID: $($FrontendProcess.Id)"
Write-Host "Baslatildi. Android cihazlarda Chrome ile yukaridaki adresi acabilir veya test APK'sini kullanabilirsin."
