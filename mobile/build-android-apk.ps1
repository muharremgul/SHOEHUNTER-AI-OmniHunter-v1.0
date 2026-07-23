param(
    [string]$ServerUrl = "https://pc1.tail135515.ts.net"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$AndroidProject = Join-Path $PSScriptRoot "android"
$Toolchain = Join-Path $PSScriptRoot ".toolchain"
$JavaHome = Join-Path $Toolchain "jdk-17"
$AndroidSdk = Join-Path $Toolchain "android-sdk"
$GradleHome = Join-Path $Toolchain "gradle-8.9"
$Gradle = Join-Path $GradleHome "bin\gradle.bat"
$GradleUserHome = Join-Path $Toolchain "gradle-user-home"
$GradleNativeDir = Join-Path $Toolchain "gradle-native"

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
$env:GRADLE_USER_HOME = $GradleUserHome
$env:GRADLE_OPTS = (([string]$env:GRADLE_OPTS) + " -Dorg.gradle.native.dir=$GradleNativeDir").Trim()
$env:JAVA_TOOL_OPTIONS = (([string]$env:JAVA_TOOL_OPTIONS) + " -Dorg.gradle.native.dir=$GradleNativeDir").Trim()
$escapedServerUrl = $ServerUrl.Replace("\\", "\\\\").Replace('"', '\"')

& $Gradle -p $AndroidProject clean assembleDebug "-PshoehunterServerUrl=$escapedServerUrl" --no-daemon --max-workers=1
if ($LASTEXITCODE -ne 0) { throw "Android derlemesi başarısız oldu." }

$SourceApk = Join-Path $AndroidProject "app\build\outputs\apk\debug\app-debug.apk"
$Dist = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$TargetApk = Join-Path $Dist "ShopHunter-Radar-0.1.4-test.apk"
Copy-Item -LiteralPath $SourceApk -Destination $TargetApk -Force
Write-Host "APK hazır: $TargetApk"
