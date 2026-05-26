# =============================================================================
# Bronze Router Lambda
# Triggered by S3 ObjectCreated events; routes raw files into typed
# sub-folders (manuals/, telemetry/, service-logs/) within the Bronze bucket.
# =============================================================================

data "archive_file" "router" {
  type        = "zip"
  source_file = "${path.module}/lambda/router.py"
  output_path = "${path.module}/lambda/router.zip"
}

resource "aws_cloudwatch_log_group" "lambda_router" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-bronze-router"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.watchman.arn
  tags              = local.common_tags
}

resource "aws_lambda_function" "bronze_router" {
  function_name    = "${var.project_name}-${var.environment}-bronze-router"
  role             = aws_iam_role.lambda_router.arn
  runtime          = "python3.12"
  handler          = "router.handler"
  filename         = data.archive_file.router.output_path
  source_code_hash = data.archive_file.router.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      PROJECT     = var.project_name
      ENVIRONMENT = var.environment
    }
  }

  # Ensure log group exists before function (avoids race on first deploy)
  depends_on = [aws_cloudwatch_log_group.lambda_router]

  tags = local.common_tags
}

# Grant S3 permission to invoke this Lambda
resource "aws_lambda_permission" "allow_bronze_s3" {
  statement_id  = "AllowS3InvokeRouter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bronze_router.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bronze.arn
}

# Wire S3 → Lambda: Bronze bucket triggers the router on every new object.
# The router moves files into typed sub-folders (manuals/, telemetry/, etc.).
#
# Note: S3 does not allow a no-filter rule (router) and a prefix-filtered rule
# (ETL) on the same bucket/event-type because they overlap.  The ETL pipeline
# is therefore triggered differently:
#   - etl_bronze_to_silver is invoked directly by the router Lambda after it
#     moves a PDF into manuals/ (see lambda/router.py).
#   - etl_silver_to_gold   is triggered by the Silver bucket notification
#     defined in etl_pipeline.tf (no overlap issue there).
resource "aws_s3_bucket_notification" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.bronze_router.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_bronze_s3]
}
