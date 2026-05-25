# =============================================================================
# AWS AI Watchman — Medallion Data Lakehouse
# Bronze (raw) → Silver (cleaned) → Gold (vector-ready for Bedrock RAG)
# =============================================================================

# =============================================================================
# BRONZE LAYER — Raw Ingestion (immutable landing zone)
# =============================================================================

resource "aws_s3_bucket" "bronze" {
  bucket        = "${var.project_name}-${var.environment}-bronze-raw"
  force_destroy = false
  tags          = merge(local.common_tags, { DataLayer = "bronze" })
}

resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket                  = aws_s3_bucket.bronze.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "bronze" {
  bucket = aws_s3_bucket.bronze.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "bronze" {
  bucket = aws_s3_bucket.bronze.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.watchman.arn
    }
  }
}

resource "aws_s3_bucket_logging" "bronze" {
  bucket        = aws_s3_bucket.bronze.id
  target_bucket = aws_s3_bucket.log_archive.id
  target_prefix = "s3-access/bronze/"
}

resource "aws_s3_bucket_policy" "bronze_tls" {
  bucket = aws_s3_bucket.bronze.id
  policy = data.aws_iam_policy_document.bronze_tls_only.json
}

# FinOps: Raw data transitions to cheaper storage tiers automatically
resource "aws_s3_bucket_lifecycle_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    id     = "bronze-cost-control"
    status = "Enabled"

    filter { prefix = "" }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# =============================================================================
# SILVER LAYER — Cleaned & Filtered
# =============================================================================

resource "aws_s3_bucket" "silver" {
  bucket        = "${var.project_name}-${var.environment}-silver-cleaned"
  force_destroy = false
  tags          = merge(local.common_tags, { DataLayer = "silver" })
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket                  = aws_s3_bucket.silver.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "silver" {
  bucket = aws_s3_bucket.silver.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "silver" {
  bucket = aws_s3_bucket.silver.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.watchman.arn
    }
  }
}

resource "aws_s3_bucket_logging" "silver" {
  bucket        = aws_s3_bucket.silver.id
  target_bucket = aws_s3_bucket.log_archive.id
  target_prefix = "s3-access/silver/"
}

resource "aws_s3_bucket_policy" "silver_tls" {
  bucket = aws_s3_bucket.silver.id
  policy = data.aws_iam_policy_document.silver_tls_only.json
}

# =============================================================================
# GOLD LAYER — Curated & Vector-Ready (feeds Bedrock Knowledge Base)
# =============================================================================

resource "aws_s3_bucket" "gold" {
  bucket        = "${var.project_name}-${var.environment}-gold-vector-ready"
  force_destroy = false
  tags          = merge(local.common_tags, { DataLayer = "gold" })
}

resource "aws_s3_bucket_public_access_block" "gold" {
  bucket                  = aws_s3_bucket.gold.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "gold" {
  bucket = aws_s3_bucket.gold.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "gold" {
  bucket = aws_s3_bucket.gold.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.watchman.arn
    }
  }
}

resource "aws_s3_bucket_logging" "gold" {
  bucket        = aws_s3_bucket.gold.id
  target_bucket = aws_s3_bucket.log_archive.id
  target_prefix = "s3-access/gold/"
}

resource "aws_s3_bucket_policy" "gold_tls" {
  bucket = aws_s3_bucket.gold.id
  policy = data.aws_iam_policy_document.gold_tls_only.json
}

# =============================================================================
# GLUE DATA CATALOG — schema inference for the Bronze layer
# =============================================================================

resource "aws_glue_catalog_database" "watchman" {
  name        = replace("${var.project_name}_${var.environment}_catalog", "-", "_")
  description = "Glue Data Catalog for the AWS-AI-Watchman lakehouse."
  tags        = local.common_tags
}

# Bronze Crawler — on-demand only (never scheduled) to avoid runaway cost.
# Run manually: aws glue start-crawler --name <name>
resource "aws_glue_crawler" "bronze" {
  name          = "${var.project_name}-${var.environment}-bronze-crawler"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.watchman.name

  s3_target {
    path = "s3://${aws_s3_bucket.bronze.bucket}"
  }

  # No schedule block = on-demand only
  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = local.common_tags
}
