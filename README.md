# AWS AI Watchman

> Enterprise AI governance framework on AWS — event-driven ETL pipeline, Bedrock guardrails, RAG knowledge base, and a CloudWatch ops dashboard. Inspired by United Rentals' Equipment Agent use case.

---

## What It Does

Field technicians at equipment rental companies need fast, accurate answers about machinery faults. **AWS AI Watchman** is an AI agent that:

- Answers equipment maintenance questions grounded in OEM service manuals (RAG)
- Enforces enterprise governance on **every** invocation — PII anonymisation, topic restrictions, prompt-injection protection
- Processes raw PDFs automatically through a Bronze → Silver → Gold data lakehouse
- Exposes a live CloudWatch operations dashboard with guardrail block rate, latency percentiles, and token throughput

**Cost: $0 when idle. ~$0.13 per PDF processed. RAG layer is toggleable (~$0.96/hr when on).**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER / TECHNICIAN                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ question
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GOVERNANCE LAYER (always on)                  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │            Bedrock Guardrail  ag08rtzcjw3e               │  │
│   │   • PII anonymise / block (SSN, AWS keys, phone)         │  │
│   │   • Topic deny  (legal advice, rental pricing)           │  │
│   │   • Content filter  (hate, violence)                     │  │
│   │   • Prompt-attack detection  (HIGH sensitivity)          │  │
│   └──────────┬───────────────────────────────────────────────┘  │
│              │ PASS                          BLOCKED → user      │
└──────────────┼──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFERENCE LAYER                               │
│                                                                  │
│   Claude Haiku 4.5  (us.anthropic.claude-haiku-4-5-*)           │
│   + optional RAG retrieval from Bedrock Knowledge Base           │
│     └── OpenSearch Serverless  (enable_bedrock_kb=true)         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAKEHOUSE (ETL)                          │
│                                                                  │
│  PDF upload                                                      │
│     │                                                            │
│     ▼                                                            │
│  S3 Bronze  ──► Router Lambda ──► S3 Bronze/manuals/            │
│                      │                                           │
│                      │ lambda:InvokeFunction (async)            │
│                      ▼                                           │
│              etl_bronze_to_silver                                │
│              (pypdf extraction → JSON)                           │
│                      │                                           │
│                      ▼                                           │
│                 S3 Silver/manuals/  ──► S3 event                │
│                                             │                    │
│                                             ▼                    │
│                                   etl_silver_to_gold             │
│                                   (2 000-char chunks)            │
│                                             │                    │
│                                             ▼                    │
│                                     S3 Gold/manuals/             │
│                                     (1 050 .txt chunks)          │
│                                             │                    │
│                                             ▼                    │
│                               StartIngestionJob  (KB enabled)    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                                  │
│                                                                  │
│  CloudWatch Log Group  /aws/aws-ai-watchman/{env}/agent          │
│     │                                                            │
│     ├── Metric Filter → GuardrailBlocked  (Watchman/Agent)      │
│     ├── Metric Filter → GuardrailAllowed  (Watchman/Agent)      │
│     ├── Metric Filter → InvocationLatency (Watchman/Agent)      │
│     └── Metric Filter → OutputTokens      (Watchman/Agent)      │
│                                                                  │
│  Dashboard  aws-ai-watchman-dev                                  │
│     • Guardrail outcomes (allowed vs blocked)                    │
│     • Block rate % (1-hour rolling, 10% alarm threshold)        │
│     • Agent latency P50 / P90 / P99 (10 s SLO)                 │
│     • Token throughput (cost proxy)                              │
│                                                                  │
│  Alarms → SNS → alerts topic                                     │
│     • guardrail-block-spike  (> 5 blocks in 5 min)              │
│     • agent-latency-high     (P90 > 10 s)                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Service |
|---|---|
| AI model | Amazon Bedrock — Claude Haiku 4.5 (cross-region inference) |
| Governance | Amazon Bedrock Guardrails |
| RAG | Bedrock Knowledge Base + OpenSearch Serverless |
| Embeddings | Amazon Titan Text Embeddings V2 (1 024-dim) |
| ETL | AWS Lambda (Python 3.12) + Lambda Layer (pypdf) |
| Data lake | Amazon S3 (Bronze / Silver / Gold medallion) |
| Cataloguing | AWS Glue Data Catalog + Crawler |
| Observability | CloudWatch Logs, Metric Filters, Dashboard, Alarms, SNS |
| State | DynamoDB |
| Encryption | AWS KMS (CMK) — all buckets, log groups, DynamoDB, SNS |
| IaC | Terraform (remote state in S3 + DynamoDB lock) |
| CI/CD | GitHub Actions — OIDC (no static credentials in CI) |

---

## Project Structure

```
AWS-AI-Watchman/
├── infra/
│   └── terraform/
│       ├── lambda/
│       │   ├── router.py               # Bronze router — routes + triggers ETL
│       │   ├── etl_bronze_to_silver.py # PDF → JSON extraction (pypdf)
│       │   ├── etl_silver_to_gold.py   # JSON → 2 000-char chunks + KB trigger
│       │   └── pypdf_layer.zip         # Pre-built Lambda layer
│       ├── bedrock_guardrails.tf       # Guardrail: PII, topics, content, prompt-attack
│       ├── bedrock_kb.tf               # Knowledge Base + OpenSearch (feature-flagged)
│       ├── cloudwatch.tf               # Log groups, metric filters, dashboard, alarms
│       ├── datalake.tf                 # Glue catalog + crawler
│       ├── etl_pipeline.tf             # ETL Lambda functions + Silver bucket notification
│       ├── github_oidc.tf              # OIDC provider + GitHub Actions deploy role
│       ├── iam.tf                      # All IAM roles and policies
│       ├── kms.tf                      # Customer-managed encryption key
│       ├── lambda.tf                   # Bronze router Lambda + S3 notification
│       ├── s3.tf                       # Bronze / Silver / Gold / Artifacts / Logs buckets
│       └── variables.tf                # enable_bedrock_kb flag (default: false)
├── scripts/
│   ├── agent/
│   │   └── equipment_agent.py          # Agent runtime — Bedrock Converse + guardrail
│   ├── ingest/
│   │   └── generate_manuals.py         # Synthetic OEM PDF generator (fpdf2)
│   ├── etl/
│   │   ├── bronze_to_silver.py         # Local ETL script (pdfplumber)
│   │   └── silver_to_gold.py           # Local chunking script
│   ├── kb_enable.ps1                   # RAG on  — terraform apply + StartIngestionJob
│   ├── kb_disable.ps1                  # RAG off — destroys OpenSearch (~$0.96/hr)
│   └── build_lambda_layers.ps1         # Rebuilds pypdf_layer.zip
└── .github/
    └── workflows/                      # Terraform plan/apply via OIDC
```

---

## Fleet Data

Five synthetic OEM-style service manuals (~200 pages each):

| ID | Equipment | Manufacturer |
|---|---|---|
| `CAT-EX` | 320 Excavator | Caterpillar |
| `GEN-BL` | S-60 Boom Lift | Genie |
| `JD-BD` | 850K Dozer | John Deere |
| `KOM-FL` | FG25T-16 Forklift | Komatsu |
| `JLG-SC` | 2630ES Scissor Lift | JLG |

Each manual contains: specifications table, OSHA safety warnings, fault codes E001–E005 (root cause + diagnostic steps + resolution), hydraulic troubleshooting, and a 5-interval maintenance schedule.

After ETL: **1,050 Gold chunks** (210 per equipment type, 2,000-char target with 200-char overlap).

---

## Quick Start

### Prerequisites
- AWS CLI configured (`us-east-1`)
- Terraform ≥ 1.5
- Python 3.12 + `boto3`, `fpdf2`, `pdfplumber`
- PowerShell 7+

### Deploy

```powershell
# 1. Build the pypdf Lambda layer
.\scripts\build_lambda_layers.ps1

# 2. Deploy infrastructure (RAG off by default)
cd infra/terraform
terraform init
terraform apply

# 3. Generate synthetic manuals and upload to Bronze
python scripts/ingest/generate_manuals.py
# Upload PDFs to the Bronze S3 bucket — ETL fires automatically
```

### Test the Guardrail (no model access needed)

```powershell
# Run all 6 governance scenarios
python scripts/agent/equipment_agent.py --test-guardrail

# Test any custom message
python scripts/agent/equipment_agent.py --test-guardrail -m "Your question here"

# Interactive mode
python scripts/agent/equipment_agent.py --test-guardrail --interactive
```

### Test with Full Model Responses

Requires Bedrock model access (Bedrock console → Model access → Claude Haiku 4.5):

```powershell
# Interactive chat with guardrail enforcement
python scripts/agent/equipment_agent.py --interactive

# Run all demo scenarios
python scripts/agent/equipment_agent.py --demo
```

### Enable / Disable RAG (~$0.96/hr while active)

```powershell
# Turn RAG on — creates KB + triggers ingestion (~5 min to ready)
.\scripts\kb_enable.ps1

# Turn RAG off — destroys OpenSearch, preserves Gold data
.\scripts\kb_disable.ps1
```

---

## Guardrail Policies

| Policy | Type | Behaviour |
|---|---|---|
| `legal-advice` | Topic deny | Blocks liability / lawsuit questions |
| `rental-pricing` | Topic deny | Blocks pricing / contract questions |
| `competitor-information` | Topic deny | Blocks competitor brand comparisons |
| PII — SSN, AWS keys, phone, credit card | Sensitive info | Block (hard stop) |
| PII — names, technician IDs | Sensitive info | Anonymise (replace with placeholder) |
| Hate, violence, sexual, misconduct | Content filter | Block at HIGH sensitivity |
| Prompt injection / jailbreak | PROMPT_ATTACK | Block at HIGH sensitivity |

---

## Live Demo Scenarios

```
1. CAT 320 fault code E003 + hydraulic pressure drop  → ALLOWED  (~300 ms)
2. Technician name + phone + equipment serial          → BLOCKED  pii:*
3. AWS access key in message                           → BLOCKED  pii:AWS_ACCESS_KEY
4. "What's my legal liability?"                        → BLOCKED  topic:legal-advice
5. "What's the daily rental rate?"                     → BLOCKED  topic:rental-pricing
6. "Ignore all previous instructions..."               → BLOCKED  content:prompt_attack
```

---

## Cost Model

| Component | Cost |
|---|---|
| Lambda (ETL + router) | ~$0.13 per PDF processed |
| Bedrock Guardrail | ~$0.75 / 1 000 text units |
| Bedrock Claude Haiku 4.5 | ~$0.25 / 1M tokens |
| CloudWatch Logs + Metrics | < $1/month at demo volume |
| OpenSearch Serverless (RAG) | ~$0.96/hr — **disabled by default** |
| Everything else (idle) | **$0** |

---

## Security

- All S3 buckets: TLS-only policy, versioning, KMS-SSE, access logging, public access blocked
- All CloudWatch log groups: KMS-encrypted, 90-day retention
- DynamoDB and SNS: KMS-encrypted
- IAM roles: least-privilege, scoped to specific resources and prefixes
- GitHub Actions: OIDC only — no static AWS credentials in CI/CD
- Bedrock KB role: confused-deputy protection (`aws:SourceAccount` condition)

---

## CI/CD

GitHub Actions workflows use OIDC to assume the `aws-ai-watchman-dev-github-actions-deploy` IAM role — no `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in secrets.

```
push to main
  └── terraform plan   (on PR)
  └── terraform apply  (on merge to main)
```

---

## Known Gaps

| Gap | Impact | Fix |
|---|---|---|
| No DLQ on Lambda functions | Failed PDF processing silently dropped after 2 retries | Add `dead_letter_config { target_arn = aws_sqs_queue.dlq.arn }` |
| No X-Ray tracing | Cannot trace a request across Router → ETL Bronze→Silver → ETL Silver→Gold | Add `tracing_config { mode = "Active" }` to all Lambdas |

---

## Bugs Fixed

| Bug | Severity | Fix |
|---|---|---|
| ETL trigger chain silently broken — router never invoked ETL Lambda | Critical | Router now calls `lambda:InvokeFunction` with `InvocationType=Event` after routing PDFs |
| `sequenceToken` in `put_log_events` (deprecated Jan 2023) | Minor | Removed — concurrent writes work without it |
| Log group path hardcoded to `dev` environment | Minor | Now reads `ENVIRONMENT` env var with `dev` fallback |
