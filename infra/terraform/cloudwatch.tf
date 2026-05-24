resource "aws_cloudwatch_log_group" "orchestration" {
  name = "/aws/${var.project_name}/${var.environment}/orchestration"
  retention_in_days = var.log_retention_days
  kms_key_id = aws_kms_key.watchman.arn
  tags = local.common_tags
}

