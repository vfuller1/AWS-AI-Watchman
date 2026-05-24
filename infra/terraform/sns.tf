resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"
  kms_master_key_id = aws_kms_key.watchman.arn
  tags = local.common_tags
}

