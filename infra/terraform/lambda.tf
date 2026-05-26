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

# Wire S3 → Lambda: Bronze bucket triggers both router and ETL
# - Router: fires on every object, routes root-level files into typed sub-folders
# - ETL:    fires only on manuals/*.pdf, starts the Bronze->Silver extraction
resource "aws_s3_bucket_notification" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  # Existing router — handles all new objects (skips already-prefixed keys internally)
  lambda_function {
    lambda_function_arn = aws_lambda_function.bronze_router.arn
    events              = ["s3:ObjectCreated:*"]
  }

  # ETL trigger — only fires for PDFs that the router moved to manuals/
  lambda_function {
    lambda_function_arn = aws_lambda_function.etl_bronze_to_silver.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "manuals/"
    filter_suffix       = ".pdf"
  }

  depends_on = [
    aws_lambda_permission.allow_bronze_s3,
    aws_lambda_permission.allow_bronze_s3_etl,
  ]
}
