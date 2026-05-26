# =============================================================================
# AWS AI Watchman - Automated ETL Pipeline
#
# Event-driven, fully serverless:
#
#   Bronze PDF upload
#     -> Router Lambda (existing)  routes to manuals/
#     -> etl_bronze_to_silver      S3 trigger on manuals/*.pdf
#         -> Silver JSON
#     -> etl_silver_to_gold        S3 trigger on manuals/*.json
#         -> Gold chunks
#         -> StartIngestionJob      (only when enable_bedrock_kb=true)
#
# Cost: $0 when idle. ~$0.13 per PDF uploaded (Glue/Lambda/ingestion).
# =============================================================================

# ---------------------------------------------------------------------------
# pypdf Lambda Layer — provides PDF text extraction for etl_bronze_to_silver
# Build the zip first:  scripts/build_lambda_layers.ps1
# ---------------------------------------------------------------------------
resource "aws_lambda_layer_version" "pypdf" {
  filename            = "${path.module}/lambda/pypdf_layer.zip"
  layer_name          = "${var.project_name}-${var.environment}-pypdf"
  compatible_runtimes = ["python3.12"]
  source_code_hash    = filebase64sha256("${path.module}/lambda/pypdf_layer.zip")

  lifecycle {
    create_before_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Lambda: etl_bronze_to_silver
# ---------------------------------------------------------------------------
data "archive_file" "etl_bronze_to_silver" {
  type        = "zip"
  source_file = "${path.module}/lambda/etl_bronze_to_silver.py"
  output_path = "${path.module}/lambda/etl_bronze_to_silver.zip"
}

resource "aws_cloudwatch_log_group" "etl_bronze_to_silver" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-etl-bronze-to-silver"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.watchman.arn
  tags              = local.common_tags
}

resource "aws_lambda_function" "etl_bronze_to_silver" {
  function_name    = "${var.project_name}-${var.environment}-etl-bronze-to-silver"
  role             = aws_iam_role.etl_pipeline.arn
  runtime          = "python3.12"
  handler          = "etl_bronze_to_silver.handler"
  filename         = data.archive_file.etl_bronze_to_silver.output_path
  source_code_hash = data.archive_file.etl_bronze_to_silver.output_base64sha256
  timeout          = 120 # PDF extraction can take time for large documents
  memory_size      = 512 # pypdf needs headroom for in-memory PDF parsing
  layers           = [aws_lambda_layer_version.pypdf.arn]

  environment {
    variables = {
      SILVER_BUCKET = aws_s3_bucket.silver.bucket
    }
  }

  depends_on = [aws_cloudwatch_log_group.etl_bronze_to_silver]
  tags       = local.common_tags
}

resource "aws_lambda_permission" "allow_bronze_s3_etl" {
  statement_id  = "AllowS3InvokeEtlBronzeToSilver"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.etl_bronze_to_silver.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bronze.arn
}

# ---------------------------------------------------------------------------
# Lambda: etl_silver_to_gold (pure Python — no layer needed)
# ---------------------------------------------------------------------------
data "archive_file" "etl_silver_to_gold" {
  type        = "zip"
  source_file = "${path.module}/lambda/etl_silver_to_gold.py"
  output_path = "${path.module}/lambda/etl_silver_to_gold.zip"
}

resource "aws_cloudwatch_log_group" "etl_silver_to_gold" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-etl-silver-to-gold"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.watchman.arn
  tags              = local.common_tags
}

resource "aws_lambda_function" "etl_silver_to_gold" {
  function_name    = "${var.project_name}-${var.environment}-etl-silver-to-gold"
  role             = aws_iam_role.etl_pipeline.arn
  runtime          = "python3.12"
  handler          = "etl_silver_to_gold.handler"
  filename         = data.archive_file.etl_silver_to_gold.output_path
  source_code_hash = data.archive_file.etl_silver_to_gold.output_base64sha256
  timeout          = 300 # 1,050 S3 PUTs per run (210 chunks x 5 manuals)
  memory_size      = 256

  environment {
    variables = {
      GOLD_BUCKET = aws_s3_bucket.gold.bucket
      # These are empty strings when KB is disabled — Lambda skips ingestion trigger
      KB_ID = var.enable_bedrock_kb ? aws_bedrockagent_knowledge_base.watchman[0].id : ""
      DS_ID = var.enable_bedrock_kb ? aws_bedrockagent_data_source.gold[0].data_source_id : ""
    }
  }

  depends_on = [aws_cloudwatch_log_group.etl_silver_to_gold]
  tags       = local.common_tags
}

resource "aws_lambda_permission" "allow_silver_s3_etl" {
  statement_id  = "AllowS3InvokeEtlSilverToGold"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.etl_silver_to_gold.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.silver.arn
}

# ---------------------------------------------------------------------------
# S3 bucket notifications — wire each stage to the next Lambda
# ---------------------------------------------------------------------------

# Silver bucket: new JSON in manuals/ -> etl_silver_to_gold
resource "aws_s3_bucket_notification" "silver" {
  bucket = aws_s3_bucket.silver.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.etl_silver_to_gold.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "manuals/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.allow_silver_s3_etl]
}
