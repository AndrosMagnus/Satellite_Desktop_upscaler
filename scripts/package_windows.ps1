param(
    [string]$PythonExe = "python",
    [string]$OutDir = "dist",
    [string]$SpecPath = "packaging/pyinstaller/satellite_upscale.spec",
    [switch]$BuildMsi
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Building Windows app bundle..."
& $PythonExe -m PyInstaller --noconfirm --distpath $OutDir $SpecPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

if (-not $BuildMsi) {
    Write-Host "Skipping MSI build. Pass -BuildMsi to enable."
    exit 0
}

$wix = Get-Command "wix" -ErrorAction SilentlyContinue
if (-not $wix) {
    throw "WiX CLI not found. Install WiX to build MSI."
}

Write-Host "Building MSI installer..."
& wix build `
    -o "$OutDir/SatelliteUpscale.msi" `
    "packaging/windows/installer.wxs"
if ($LASTEXITCODE -ne 0) {
    throw "WiX build failed with exit code $LASTEXITCODE."
}

Write-Host "MSI build complete."
