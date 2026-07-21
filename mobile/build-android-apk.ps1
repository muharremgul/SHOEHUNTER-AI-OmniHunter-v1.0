param(
    [string]$ServerUrl = "http://192.168.1.131:3000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$AndroidProject = Join-Path $PSScriptRoot "android"
$Toolchain = Join-Path $PSScriptRoot ".toolchain"
$JavaHome = Join-Path $Toolchain "jdk-17"
$AndroidSdk = Join-Path $Toolchain "android-sdk"
$GradleHome = Join-Path $Toolchain "gradle-8.9"
$Gradle = Join-Path $GradleHome "bin\gradle.bat"

if (-not (Test-Path -LiteralPath (Join-Path $JavaHome "bin\java.exe"))) {
    throw "JDK bulunamadı. Önce mobile/setup-android-toolchain.ps1 çalıştırın."
}
if (-not (Test-Path -LiteralPath (Join-Path $AndroidSdk "platforms\android-35\android.jar"))) {
    throw "Android SDK bulunamadı. Önce mobile/setup-android-toolchain.ps1 çalıştırın."
}
if (-not (Test-Path -LiteralPath $Gradle)) {
    throw "Gradle bulunamadı. Önce mobile/setup-android-toolchain.ps1 çalıştırın."
}

$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$escapedServerUrl = $ServerUrl.Replace("\\", "\\\\").Replace('"', '\"')

& $Gradle -p $AndroidProject clean assembleDebug "-PshoehunterServerUrl=$escapedServerUrl" --no-daemon
if ($LASTEXITCODE -ne 0) { throw "Android derlemesi başarısız oldu." }

$SourceApk = Join-Path $AndroidProject "app\build\outputs\apk\debug\app-debug.apk"
$Dist = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$TargetApk = Join-Path $Dist "ShoeHunter-Radar-0.1.0-test.apk"
Copy-Item -LiteralPath $SourceApk -Destination $TargetApk -Force
Write-Host "APK hazır: $TargetApk"
