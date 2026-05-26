# =============================================================================
# AWS AI Watchman - Build Lambda Layers
#
# Run this once before "terraform apply" if the pypdf layer zip is missing
# or after upgrading the pypdf library version.
#
# Usage: .\scripts\build_lambda_layers.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$layerDir  = "infra\terraform\lambda\pypdf_layer\python"
$zipPath   = "infra\terraform\lambda\pypdf_layer.zip"

Write-Host "Building pypdf Lambda Layer..." -ForegroundColor Cyan

# Install pypdf into the layer directory
New-Item -ItemType Directory -Force -Path $layerDir | Out-Null
pip install pypdf -t $layerDir -q

# Package as zip
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path "infra\terraform\lambda\pypdf_layer\*" -DestinationPath $zipPath
$kb = [math]::Round((Get-Item $zipPath).Length / 1KB, 0)

Write-Host "OK  $zipPath ($kb KB)" -ForegroundColor Green
Write-Host "    Run 'terraform apply' to deploy the updated layer."
