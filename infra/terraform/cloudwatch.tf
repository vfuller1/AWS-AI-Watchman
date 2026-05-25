# =============================================================================
# AWS AI Watchman — CloudWatch Observability Layer
#
# Covers three visibility concerns:
#   1. Structured logging  — agent invocations captured as JSON log events
#   2. Custom metrics      — guardrail blocks and latency extracted from logs
#   3. Dashboard + alarms  — ops-ready view into governance and performance
#
# All log groups are KMS-encrypted with the project CMK and set to the
# shared log_retention_days variable (default 90 days).
# =============================================================================

# ---------------------------------------------------------------------------
# Log groups
# ---------------------------------------------------------------------------

# Orchestration runtime (Lambda, Step Functions, etc.)
resource "aws_cloudwatch_log_group" "orchestration" {
  name              = "/aws/${var.project_name}/${var.environment}/orchestration"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.watchman.arn
  tags              = local.common_tags
}

# Equipment Agent — Python agent runtime (equipment_agent.py) sends JSON here
resource "aws_cloudwatch_log_group" "agent" {
  name              = "/aws/${var.project_name}/${var.environment}/agent"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.watchman.arn
  tags              = local.common_tags
}

# ---------------------------------------------------------------------------
# Metric filters — extract custom metrics from agent JSON logs
#
# Log event shape (emitted by equipment_agent.py):
#   {"blocked": true|false, "latency_ms": 543, "block_reason": "...", ...}
# ---------------------------------------------------------------------------

# Count of guardrail-blocked invocations → Watchman/Agent GuardrailBlocked
resource "aws_cloudwatch_log_metric_filter" "guardrail_blocked" {
  name           = "${var.project_name}-${var.environment}-guardrail-blocked"
  log_group_name = aws_cloudwatch_log_group.agent.name
  pattern        = "{ $.blocked = true }"

  metric_transformation {
    name          = "GuardrailBlocked"
    namespace     = "Watchman/Agent"
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

# Count of allowed (passed) invocations → Watchman/Agent GuardrailAllowed
resource "aws_cloudwatch_log_metric_filter" "guardrail_allowed" {
  name           = "${var.project_name}-${var.environment}-guardrail-allowed"
  log_group_name = aws_cloudwatch_log_group.agent.name
  pattern        = "{ $.blocked = false }"

  metric_transformation {
    name          = "GuardrailAllowed"
    namespace     = "Watchman/Agent"
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

# Agent end-to-end latency → Watchman/Agent InvocationLatency (milliseconds)
resource "aws_cloudwatch_log_metric_filter" "agent_latency" {
  name           = "${var.project_name}-${var.environment}-agent-latency"
  log_group_name = aws_cloudwatch_log_group.agent.name
  pattern        = "{ $.latency_ms > 0 }"

  metric_transformation {
    name          = "InvocationLatency"
    namespace     = "Watchman/Agent"
    value         = "$.latency_ms"
    default_value = "0"
    unit          = "Milliseconds"
  }
}

# LLM output tokens consumed (cost proxy) → Watchman/Agent OutputTokens
resource "aws_cloudwatch_log_metric_filter" "output_tokens" {
  name           = "${var.project_name}-${var.environment}-output-tokens"
  log_group_name = aws_cloudwatch_log_group.agent.name
  pattern        = "{ $.output_tokens > 0 }"

  metric_transformation {
    name          = "OutputTokens"
    namespace     = "Watchman/Agent"
    value         = "$.output_tokens"
    default_value = "0"
    unit          = "Count"
  }
}

# ---------------------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------------------

# Fire when guardrail blocks > 5 in a 5-minute window — potential abuse pattern
resource "aws_cloudwatch_metric_alarm" "guardrail_block_spike" {
  alarm_name          = "${var.project_name}-${var.environment}-guardrail-block-spike"
  alarm_description   = "More than 5 guardrail blocks in 5 minutes — review for potential abuse or misconfiguration."
  namespace           = "Watchman/Agent"
  metric_name         = "GuardrailBlocked"
  statistic           = "Sum"
  period              = 300 # 5 minutes
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = local.common_tags
}

# Fire when agent P90 latency > 10 s in a 5-minute window
resource "aws_cloudwatch_metric_alarm" "agent_latency_high" {
  alarm_name          = "${var.project_name}-${var.environment}-agent-latency-high"
  alarm_description   = "Agent P90 latency exceeded 10 seconds — Bedrock may be throttling or experiencing degraded performance."
  namespace           = "Watchman/Agent"
  metric_name         = "InvocationLatency"
  extended_statistic  = "p90"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10000 # 10 000 ms = 10 s
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# CloudWatch Dashboard — "Watchman Ops View"
#
# Widgets:
#   Row 0: Header text
#   Row 1: Guardrail governance overview (blocks vs allowed, 1-hour sparklines)
#   Row 2: Performance — agent latency + token throughput
#   Row 3: Data ingestion — Lambda Bronze router + S3 PUTs
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "watchman" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [

      # -----------------------------------------------------------------------
      # Row 0 — title
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = join("", [
            "## AWS AI Watchman — Operations Dashboard\n",
            "**Environment:** `${var.environment}` | ",
            "**Guardrail:** `${aws_bedrock_guardrail.watchman.guardrail_id}` (v${aws_bedrock_guardrail_version.watchman_v1.version}) | ",
            "**Model:** `us.anthropic.claude-haiku-4-5-20251001-v1:0`\n\n",
            "Metrics refresh every 5 minutes. ",
            "Guardrail data populates only when the agent runtime emits logs to ",
            "`${aws_cloudwatch_log_group.agent.name}`.",
          ])
        }
      },

      # -----------------------------------------------------------------------
      # Row 1 — Guardrail governance (left: counts, right: block breakdown)
      # -----------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 12
        height = 6
        properties = {
          title   = "Guardrail Outcomes (Sum per 5 min)"
          view    = "timeSeries"
          stacked = false
          period  = 300
          region  = var.aws_region
          metrics = [
            ["Watchman/Agent", "GuardrailAllowed", { label = "Allowed", color = "#2ca02c", stat = "Sum" }],
            ["Watchman/Agent", "GuardrailBlocked", { label = "Blocked", color = "#d62728", stat = "Sum" }],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

      {
        type   = "metric"
        x      = 12
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "Guardrail Block Rate (1 h rolling)"
          view   = "timeSeries"
          period = 3600
          region = var.aws_region
          metrics = [
            [
              {
                expression = "100*(blocked/(allowed+blocked+1))"
                label      = "Block Rate %"
                id         = "rate"
                color      = "#ff7f0e"
              }
            ],
            ["Watchman/Agent", "GuardrailBlocked", { id = "blocked", visible = false, stat = "Sum" }],
            ["Watchman/Agent", "GuardrailAllowed", { id = "allowed", visible = false, stat = "Sum" }],
          ]
          yAxis = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [{ value = 10, label = "10% threshold", color = "#d62728" }]
          }
        }
      },

      # -----------------------------------------------------------------------
      # Row 2 — Performance (latency + tokens)
      # -----------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "Agent End-to-End Latency (ms)"
          view   = "timeSeries"
          period = 300
          region = var.aws_region
          metrics = [
            ["Watchman/Agent", "InvocationLatency", { stat = "p50", label = "P50" }],
            ["Watchman/Agent", "InvocationLatency", { stat = "p90", label = "P90", color = "#ff7f0e" }],
            ["Watchman/Agent", "InvocationLatency", { stat = "p99", label = "P99", color = "#d62728" }],
          ]
          yAxis = { left = { min = 0 } }
          annotations = {
            horizontal = [{ value = 10000, label = "10 s SLO", color = "#d62728" }]
          }
        }
      },

      {
        type   = "metric"
        x      = 12
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "LLM Output Tokens (cost proxy)"
          view   = "timeSeries"
          period = 3600
          region = var.aws_region
          metrics = [
            ["Watchman/Agent", "OutputTokens", { stat = "Sum", label = "Output tokens / hour", color = "#9467bd" }],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

      # -----------------------------------------------------------------------
      # Row 3 — Data ingestion pipeline
      # -----------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 14
        width  = 12
        height = 6
        properties = {
          title  = "Bronze Router Lambda Invocations"
          view   = "timeSeries"
          period = 300
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations",
              "FunctionName", aws_lambda_function.bronze_router.function_name,
              { stat = "Sum", label = "Invocations" }
            ],
            ["AWS/Lambda", "Errors",
              "FunctionName", aws_lambda_function.bronze_router.function_name,
              { stat = "Sum", label = "Errors", color = "#d62728" }
            ],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

      {
        type   = "metric"
        x      = 12
        y      = 14
        width  = 12
        height = 6
        properties = {
          title  = "Bronze Bucket — S3 PUT Requests"
          view   = "timeSeries"
          period = 3600
          region = var.aws_region
          metrics = [
            ["AWS/S3", "NumberOfObjects",
              "BucketName", aws_s3_bucket.bronze.bucket,
              "StorageType", "AllStorageTypes",
              { stat = "Average", label = "Object count", color = "#17becf" }
            ],
          ]
          yAxis = { left = { min = 0 } }
        }
      },

    ]
  })
}
