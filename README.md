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

* `terraform-plan.yml` runs on pull requests and validates the Terraform changes before they land.
* `terraform-apply.yml` is manually triggered to deploy the environment into AWS account `161486985462` (`cybersecurity1st`).

The workflows expect a repository secret named `AWS_ROLE_ARN` that points to an IAM role in that AWS account with Terraform permissions and GitHub OIDC trust.

The Terraform stack now creates that OIDC trust path under [infra/terraform/github_oidc.tf](infra/terraform/github_oidc.tf). Set `github_repository` to your GitHub repository in `OWNER/REPO` format when you apply Terraform, then copy the `github_actions_deploy_role_arn` output into the `AWS_ROLE_ARN` secret.

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
