param(
    [string]$ApkPath = (Join-Path $PSScriptRoot "dist\ShopHunter-Radar-0.1.4-test.apk")
)

$ErrorActionPreference = "Stop"
$Adb = Join-Path $PSScriptRoot ".toolchain\android-sdk\platform-tools\adb.exe"
if (-not (Test-Path -LiteralPath $Adb)) { throw "adb bulunamadı. Önce Android araçlarını kurun." }
if (-not (Test-Path -LiteralPath $ApkPath)) { throw "APK bulunamadı: $ApkPath" }

& $Adb devices
& $Adb install -r $ApkPath
if ($LASTEXITCODE -ne 0) { throw "APK kurulamadı. USB hata ayıklama iznini kontrol edin." }
