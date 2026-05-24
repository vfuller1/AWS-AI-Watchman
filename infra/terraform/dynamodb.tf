resource "aws_dynamodb_table" "watchman_state" {
  name = "${var.project_name}-${var.environment}-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
    kms_key_arn = aws_kms_key.watchman.arn
  }

  tags = local.common_tags
}

