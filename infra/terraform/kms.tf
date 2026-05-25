resource "aws_kms_key" "watchman" {
  description             = "KMS key for AWS-AI-Watchman encryption."
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_key_policy.json
  tags                    = local.common_tags
}

resource "aws_kms_alias" "watchman" {
  name          = "alias/${var.project_name}-${var.environment}"
  target_key_id = aws_kms_key.watchman.key_id
}

