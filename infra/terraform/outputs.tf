output "artifacts_bucket_name" {
  description = "S3 bucket used for Watchman artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "log_archive_bucket_name" {
  description = "S3 bucket used for access and platform logs."
  value       = aws_s3_bucket.log_archive.bucket
}

output "state_table_name" {
  description = "DynamoDB table that stores Watchman state."
  value       = aws_dynamodb_table.watchman_state.name
}

output "alerts_topic_arn" {
  description = "SNS topic for Watchman alerts."
  value       = aws_sns_topic.alerts.arn
}

output "orchestrator_role_arn" {
  description = "IAM role for the orchestration runtime."
  value       = aws_iam_role.orchestrator.arn
}

output "github_actions_deploy_role_arn" {
  description = "IAM role ARN that GitHub Actions assumes via OIDC to run Terraform."
  value       = aws_iam_role.github_actions_deploy.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

output "bronze_bucket_name" {
  description = "S3 bucket for raw Bronze-layer ingestion."
  value       = aws_s3_bucket.bronze.bucket
}

output "silver_bucket_name" {
  description = "S3 bucket for cleaned Silver-layer data."
  value       = aws_s3_bucket.silver.bucket
}

output "gold_bucket_name" {
  description = "S3 bucket for curated Gold-layer vector-ready data (Bedrock Knowledge Base source)."
  value       = aws_s3_bucket.gold.bucket
}

output "glue_catalog_database" {
  description = "Glue Data Catalog database name for the lakehouse."
  value       = aws_glue_catalog_database.watchman.name
}

output "glue_bronze_crawler_name" {
  description = "Glue Crawler for Bronze layer — run on-demand via CLI or console."
  value       = aws_glue_crawler.bronze.name
}

output "bronze_router_lambda_name" {
  description = "Lambda function that routes new Bronze objects into typed sub-folders."
  value       = aws_lambda_function.bronze_router.function_name
}

output "guardrail_id" {
  description = "Bedrock Guardrail ID — pass as guardrailIdentifier when invoking models."
  value       = aws_bedrock_guardrail.watchman.guardrail_id
}

output "guardrail_arn" {
  description = "Bedrock Guardrail ARN."
  value       = aws_bedrock_guardrail.watchman.guardrail_arn
}

output "guardrail_version" {
  description = "Published Guardrail version — use this in production API calls."
  value       = aws_bedrock_guardrail_version.watchman_v1.version
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (null when enable_bedrock_kb=false)."
  value       = var.enable_bedrock_kb ? aws_bedrockagent_knowledge_base.watchman[0].id : null
}

output "knowledge_base_data_source_id" {
  description = "Bedrock Knowledge Base Data Source ID — use to trigger ingestion jobs."
  value       = var.enable_bedrock_kb ? aws_bedrockagent_data_source.gold[0].data_source_id : null
}

output "agent_log_group_name" {
  description = "CloudWatch Log Group for Equipment Agent JSON logs."
  value       = aws_cloudwatch_log_group.agent.name
}

output "orchestration_log_group_name" {
  description = "CloudWatch Log Group for orchestration runtime logs."
  value       = aws_cloudwatch_log_group.orchestration.name
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch Dashboard name — open in AWS Console for ops view."
  value       = aws_cloudwatch_dashboard.watchman.dashboard_name
}

