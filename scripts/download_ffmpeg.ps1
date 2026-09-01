$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BinDir = Join-Path $ProjectRoot "bin"
$TempDir = Join-Path $env:TEMP ("imageToAnimation_ffmpeg_" + [Guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempDir "ffmpeg.zip"
$ExtractDir = Join-Path $TempDir "extract"

$Url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

try {
    Write-Host "[INFO] Downloading FFmpeg essentials build..."
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing

    Write-Host "[INFO] Extracting..."
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force

    $Ffmpeg = Get-ChildItem -Path $ExtractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    $Ffprobe = Get-ChildItem -Path $ExtractDir -Recurse -Filter "ffprobe.exe" | Select-Object -First 1

    if (-not $Ffmpeg) {
        throw "ffmpeg.exe was not found after extraction."
    }

    Copy-Item $Ffmpeg.FullName (Join-Path $BinDir "ffmpeg.exe") -Force

    if ($Ffprobe) {
        Copy-Item $Ffprobe.FullName (Join-Path $BinDir "ffprobe.exe") -Force
    }

    Write-Host "[OK] FFmpeg installed to $BinDir"
}
finally {
    if (Test-Path $TempDir) {
        Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
