# AWS-AI-Watchman
Enterprise AI orchestration framework providing automated guardrails, observability, and cost-governance for AWS Bedrock agentic workloads. Engineered for production-scale reliability and security.

## Infrastructure

The repository now includes a Terraform foundation under [infra/terraform](infra/terraform) for the core Watchman platform resources:

* KMS encryption for shared platform data
* Encrypted S3 buckets for artifacts and access logs
* DynamoDB state storage with point-in-time recovery
* Encrypted CloudWatch Logs retention for orchestration telemetry
* SNS alerts topic for operational notifications
* A least-privilege orchestration IAM role for future Bedrock runtime integration

## GitHub Actions

Two workflows are included under [.github/workflows](.github/workflows):

* `terraform-plan.yml` runs automatically on pull requests and on pushes to `main` when Terraform files change.
* `terraform-apply.yml` runs automatically after a successful `terraform-plan.yml` run on `main`, and still waits for any GitHub environment approval you configure for `aws-deploy`.

The apply workflow uses the dev deploy role ARN directly, so no `AWS_ROLE_ARN` secret is required.

For the approval gate, configure the GitHub environment named `aws-deploy` with required reviewers in the repository settings.

## Branch Protection

To keep `main` from merging before the plan succeeds, enable branch protection on `main` in GitHub and require status checks to pass before merging.

Recommended settings:

* Require pull request reviews before merging.
* Require status checks to pass before merging.
* Select the `Terraform Plan / Terraform Plan` check from the plan workflow.
* Optionally require linear history to keep the promotion path clean.

This makes the merge gate wait for the plan workflow first, and the `workflow_run` apply workflow only starts after that successful plan on `main`.

The Terraform stack now creates that OIDC trust path under [infra/terraform/github_oidc.tf](infra/terraform/github_oidc.tf). Set `github_repository` to your GitHub repository in `OWNER/REPO` format when you apply Terraform.

### Quick start

```bash
cd infra/terraform
terraform init
terraform plan -var="aws_region=us-east-1" -var="environment=dev"
```

Apply only after reviewing the plan:

```bash
terraform apply -var="aws_region=us-east-1" -var="environment=dev"
```
