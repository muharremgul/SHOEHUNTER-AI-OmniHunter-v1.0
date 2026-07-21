param()

$ErrorActionPreference = "Stop"
$Toolchain = Join-Path $PSScriptRoot ".toolchain"
$Downloads = Join-Path $Toolchain "downloads"
$JavaHome = Join-Path $Toolchain "jdk-17"
$AndroidSdk = Join-Path $Toolchain "android-sdk"
$GradleHome = Join-Path $Toolchain "gradle-8.9"

New-Item -ItemType Directory -Force -Path $Downloads, $AndroidSdk | Out-Null

function Assert-ToolchainPath([string]$Path) {
    $ResolvedRoot = [System.IO.Path]::GetFullPath($Toolchain).TrimEnd('\') + '\'
    $ResolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $ResolvedPath.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Güvensiz araç yolu reddedildi: $ResolvedPath"
    }
}

function Download-File([string]$Url, [string]$Destination) {
    Assert-ToolchainPath $Destination
    & curl.exe --fail --location --retry 3 --connect-timeout 20 --output $Destination $Url
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Destination) -or (Get-Item -LiteralPath $Destination).Length -lt 1MB) {
        throw "Araç indirilemedi: $Url"
    }
}

$JdkZip = Join-Path $Downloads "jdk17.zip"
$JdkUrl = "https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip"
if (-not (Test-Path -LiteralPath (Join-Path $JavaHome "bin\java.exe"))) {
    Download-File $JdkUrl $JdkZip
    $JdkExtract = Join-Path $Toolchain "jdk-extract"
    Assert-ToolchainPath $JdkExtract
    if (Test-Path -LiteralPath $JdkExtract) { Remove-Item -LiteralPath $JdkExtract -Recurse -Force }
    Expand-Archive -LiteralPath $JdkZip -DestinationPath $JdkExtract -Force
    $ExtractedJdk = Get-ChildItem -LiteralPath $JdkExtract -Directory | Select-Object -First 1
    Move-Item -LiteralPath $ExtractedJdk.FullName -Destination $JavaHome
    Remove-Item -LiteralPath $JdkExtract -Recurse -Force
}

$GradleZip = Join-Path $Downloads "gradle-8.9-bin.zip"
if (-not (Test-Path -LiteralPath (Join-Path $GradleHome "bin\gradle.bat"))) {
    Download-File "https://services.gradle.org/distributions/gradle-8.9-bin.zip" $GradleZip
    Expand-Archive -LiteralPath $GradleZip -DestinationPath $Toolchain -Force
}

$CommandToolsZip = Join-Path $Downloads "commandlinetools-win.zip"
$SdkManager = Join-Path $AndroidSdk "cmdline-tools\latest\bin\sdkmanager.bat"
if (-not (Test-Path -LiteralPath $SdkManager)) {
    Download-File "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip" $CommandToolsZip
    $CommandExtract = Join-Path $Toolchain "cmdline-extract"
    Assert-ToolchainPath $CommandExtract
    if (Test-Path -LiteralPath $CommandExtract) { Remove-Item -LiteralPath $CommandExtract -Recurse -Force }
    Expand-Archive -LiteralPath $CommandToolsZip -DestinationPath $CommandExtract -Force
    $Latest = Join-Path $AndroidSdk "cmdline-tools\latest"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Latest) | Out-Null
    Move-Item -LiteralPath (Join-Path $CommandExtract "cmdline-tools") -Destination $Latest
    Remove-Item -LiteralPath $CommandExtract -Recurse -Force
}

$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk

$LicenseInput = (1..20 | ForEach-Object { "y" }) -join [Environment]::NewLine
$LicenseInput | & $SdkManager --sdk_root=$AndroidSdk --licenses | Out-Host
& $SdkManager --sdk_root=$AndroidSdk "platform-tools" "platforms;android-35" "build-tools;35.0.0"
if ($LASTEXITCODE -ne 0) { throw "Android SDK paketleri kurulamadı." }

Write-Host "Android araçları hazır: $Toolchain"
