# AWS-AI-Watchman
Enterprise AI orchestration framework providing automated guardrails, observability, and cost-governance for AWS Bedrock agentic workloads. Engineered for production-scale reliability and security.

## Infrastructure

The repository includes a Terraform foundation under [infra/terraform](infra/terraform) for the core Watchman platform resources:

* KMS encryption for shared platform data
* Encrypted S3 buckets for artifacts and access logs
* DynamoDB state storage with point-in-time recovery
* Encrypted CloudWatch Logs retention for orchestration telemetry
* SNS alerts topic for operational notifications
* A least-privilege orchestration IAM role for future Bedrock runtime integration
* GitHub Actions OIDC provider and deploy role (no long-lived credentials in CI)

## GitHub Actions

Three workflows are included under [.github/workflows](.github/workflows):

* `terraform-plan.yml` — runs on pull requests and pushes to `main` when Terraform files change. Uses OIDC to assume the deploy role; no static AWS keys required.
* `terraform-apply.yml` — runs automatically after a successful plan on `main`, then waits for approval from the `aws-deploy` GitHub environment before applying.
* `aws-oidc-test.yml` — manual trigger (`workflow_dispatch`) to verify the OIDC token exchange is working after a new deploy.

Both workflows read the account ID from the `AWS_ACCOUNT_ID` GitHub Actions **variable** (not a secret). Set it in your repository settings under **Settings → Variables → Actions**.

For the approval gate, configure the GitHub environment named `aws-deploy` with required reviewers in the repository settings under **Settings → Environments**.

## One-time Bootstrap (Required Before CI Works)

The OIDC provider and deploy IAM role are managed by Terraform. Before GitHub Actions can authenticate via OIDC, you must create those resources once using your personal AWS credentials:

```bash
cd infra/terraform

# Uses your local AWS credentials (e.g. ~/.aws/credentials or env vars)
terraform init
terraform apply \
  -var="aws_region=us-east-1" \
  -var="environment=dev" \
  -var="github_repository=VFull/AWS-AI-Watchman"
```

After apply completes, GitHub Actions will authenticate using the OIDC role — no static keys stored anywhere.

You can verify the trust works by running the `AWS OIDC Smoke Test` workflow manually from the Actions tab.

## Branch Protection

To keep `main` from merging before the plan succeeds, enable branch protection on `main` in GitHub and require status checks to pass before merging.

Recommended settings:

* Require pull request reviews before merging.
* Require status checks to pass before merging.
* Select the `Terraform Plan / Terraform Plan` check from the plan workflow.
* Optionally require linear history to keep the promotion path clean.

This makes the merge gate wait for the plan workflow first, and the `workflow_run` apply workflow only starts after that successful plan on `main`.
