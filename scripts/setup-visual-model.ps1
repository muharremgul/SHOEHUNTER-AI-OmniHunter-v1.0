param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ModelDirectory = Join-Path $Root "backend\.models"
$Target = Join-Path $ModelDirectory "qdrant-clip-vit-b32-vision.onnx"
$Partial = "$Target.part"
$ExpectedSha256 = "c68d3d9a200ddd2a8c8a5510b576d4c94d1ae383bf8b36dd8c084f94e1fb4d63"
$PinnedUrl = "https://huggingface.co/Qdrant/clip-ViT-B-32-vision/resolve/5d56b3a/model.onnx?download=true"

New-Item -ItemType Directory -Force -Path $ModelDirectory | Out-Null

if (Test-Path -LiteralPath $Target) {
    $ExistingHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExistingHash -eq $ExpectedSha256) {
        Write-Host "Doğrulanmış görsel model zaten kurulu: $Target"
        exit 0
    }
    throw "Var olan modelin SHA-256 değeri beklenen değerle uyuşmuyor: $ExistingHash"
}

try {
    & curl.exe --fail --location --retry 3 --connect-timeout 20 --output $Partial $PinnedUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Model indirilemedi. curl çıkış kodu: $LASTEXITCODE"
    }
    $ActualHash = (Get-FileHash -LiteralPath $Partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedSha256) {
        throw "İndirilen modelin SHA-256 değeri beklenen değerle uyuşmuyor: $ActualHash"
    }
    Move-Item -LiteralPath $Partial -Destination $Target -Force
    Write-Host "MIT lisans kayıtlı ve SHA-256 doğrulanmış model hazır: $Target"
} finally {
    if (Test-Path -LiteralPath $Partial) {
        Remove-Item -LiteralPath $Partial -Force
    }
}
