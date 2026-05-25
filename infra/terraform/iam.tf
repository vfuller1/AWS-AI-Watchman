resource "aws_iam_role" "orchestrator" {
  name = "${var.project_name}-${var.environment}-orchestrator"
  assume_role_policy = data.aws_iam_policy_document.orchestrator_assume_role.json
  tags = local.common_tags
}

resource "aws_iam_role_policy" "orchestrator" {
  name = "${var.project_name}-${var.environment}-orchestrator"
  role = aws_iam_role.orchestrator.id
  policy = data.aws_iam_policy_document.orchestrator_permissions.json
}

# =============================================================================
# Glue Crawler Role
# =============================================================================

resource "aws_iam_role" "glue_crawler" {
  name               = "${var.project_name}-${var.environment}-glue-crawler"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "glue_crawler" {
  name   = "${var.project_name}-${var.environment}-glue-crawler"
  role   = aws_iam_role.glue_crawler.id
  policy = data.aws_iam_policy_document.glue_crawler_permissions.json
}

# =============================================================================
# Lambda Router Role
# =============================================================================

resource "aws_iam_role" "lambda_router" {
  name               = "${var.project_name}-${var.environment}-lambda-router"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "lambda_router" {
  name   = "${var.project_name}-${var.environment}-lambda-router"
  role   = aws_iam_role.lambda_router.id
  policy = data.aws_iam_policy_document.lambda_router_permissions.json
}

