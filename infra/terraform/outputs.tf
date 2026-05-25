output "artifacts_bucket_name" {
  description = "S3 bucket used for Watchman artifacts."
  value = aws_s3_bucket.artifacts.bucket
}

output "log_archive_bucket_name" {
  description = "S3 bucket used for access and platform logs."
  value = aws_s3_bucket.log_archive.bucket
}

output "state_table_name" {
  description = "DynamoDB table that stores Watchman state."
  value = aws_dynamodb_table.watchman_state.name
}

output "alerts_topic_arn" {
  description = "SNS topic for Watchman alerts."
  value = aws_sns_topic.alerts.arn
}

output "orchestrator_role_arn" {
  description = "IAM role for the orchestration runtime."
  value = aws_iam_role.orchestrator.arn
}

output "github_actions_deploy_role_arn" {
  description = "IAM role ARN that GitHub Actions assumes via OIDC to run Terraform."
  value       = aws_iam_role.github_actions_deploy.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

