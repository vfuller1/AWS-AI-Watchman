# =============================================================================
# AWS AI Watchman - Enable Bedrock Knowledge Base (RAG ON)
#
# Creates:
#   - OpenSearch Serverless collection (~$0.96/hr while running)
#   - Bedrock Knowledge Base + Data Source pointed at Gold bucket
#   - Bedrock KB IAM role
#
# Gold bucket data (1,050 manual chunks) is already staged.
# After apply, this script triggers the ingestion job automatically.
#
# Usage:  .\scripts\kb_enable.ps1
# Cost:   ~$0.96/hr while active. Run kb_disable.ps1 after your demo.
# =============================================================================

$ErrorActionPreference = "Stop"
$TF_DIR = Join-Path $PSScriptRoot "..\infra\terraform"
$REGION = "us-east-1"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " AWS AI Watchman - Enabling Knowledge Base (RAG ON)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Cost: ~`$0.96/hr while active (4 OpenSearch OCUs)" -ForegroundColor Yellow
Write-Host "  Data: 1,050 Gold chunks already staged, no re-upload needed" -ForegroundColor Green
Write-Host ""

# Step 1: Terraform apply to create KB resources
Write-Host "[1/3] Running terraform apply (enable_bedrock_kb=true)..." -ForegroundColor White
Push-Location $TF_DIR
try {
    terraform apply -auto-approve -var="enable_bedrock_kb=true"
    if ($LASTEXITCODE -ne 0) { throw "terraform apply failed" }
} finally {
    Pop-Location
}

# Step 2: Read KB outputs
Write-Host ""
Write-Host "[2/3] Reading Knowledge Base IDs from Terraform output..." -ForegroundColor White
Push-Location $TF_DIR
try {
    $KB_ID = terraform output -raw knowledge_base_id 2>$null
    $DS_ID = terraform output -raw knowledge_base_data_source_id 2>$null
} finally {
    Pop-Location
}

if (-not $KB_ID -or $KB_ID -eq "null") {
    Write-Host "  WARNING: Could not read knowledge_base_id from output." -ForegroundColor Yellow
    Write-Host "  Trigger ingestion manually from the AWS Console." -ForegroundColor Yellow
    exit 0
}

Write-Host "  Knowledge Base ID : $KB_ID" -ForegroundColor Green
Write-Host "  Data Source ID    : $DS_ID" -ForegroundColor Green

# Step 3: Start ingestion job
Write-Host ""
Write-Host "[3/3] Triggering Knowledge Base ingestion job..." -ForegroundColor White
$result = python -c "
import boto3, json
client = boto3.client('bedrock-agent', region_name='$REGION')
try:
    r = client.start_ingestion_job(
        knowledgeBaseId='$KB_ID',
        dataSourceId='$DS_ID',
        description='Initial ingestion from Gold bucket manuals/'
    )
    job = r['ingestionJob']
    print(json.dumps({'jobId': job['ingestionJobId'], 'status': job['status']}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
" 2>&1

Write-Host "  $result"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Knowledge Base is being built. Ingestion takes 2-5 minutes." -ForegroundColor Green
Write-Host " Check status in: AWS Console -> Bedrock -> Knowledge Bases" -ForegroundColor Green
Write-Host ""
Write-Host " To test RAG in the agent:" -ForegroundColor White
Write-Host "   python scripts/agent/equipment_agent.py --kb-id $KB_ID --demo" -ForegroundColor Cyan
Write-Host ""
Write-Host " When done demoing, run:" -ForegroundColor White
Write-Host "   .\scripts\kb_disable.ps1" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
