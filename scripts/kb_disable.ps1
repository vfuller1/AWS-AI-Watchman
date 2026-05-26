# =============================================================================
# AWS AI Watchman - Disable Bedrock Knowledge Base (RAG OFF)
#
# Destroys:
#   - OpenSearch Serverless collection (stops the ~$0.96/hr charge)
#   - Bedrock Knowledge Base and Data Source
#   - Bedrock KB IAM role
#
# Safe to run: Gold bucket data (1,050 chunks) is NOT deleted.
# Re-enabling with kb_enable.ps1 re-ingests from existing Gold data.
#
# Usage:  .\scripts\kb_disable.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$TF_DIR = Join-Path $PSScriptRoot "..\infra\terraform"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " AWS AI Watchman - Disabling Knowledge Base (RAG OFF)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Gold bucket data is preserved - nothing is deleted from S3." -ForegroundColor Green
Write-Host "  OpenSearch Serverless collection will be destroyed (stops billing)." -ForegroundColor Yellow
Write-Host ""

Push-Location $TF_DIR
try {
    terraform apply -auto-approve
    if ($LASTEXITCODE -ne 0) { throw "terraform apply failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Knowledge Base destroyed. OpenSearch billing stopped." -ForegroundColor Green
Write-Host " Agent reverts to guardrail-only mode (no RAG)." -ForegroundColor White
Write-Host ""
Write-Host " To re-enable for your next demo:" -ForegroundColor White
Write-Host "   .\scripts\kb_enable.ps1" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
