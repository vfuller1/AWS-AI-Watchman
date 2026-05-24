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

