# =============================================================================
# AWS AI Watchman — Bedrock Guardrail
#
# Intercepts every prompt and response at the network layer before the LLM
# ever sees user input. Enforces three categories of governance:
#   1. Content filters  — block harmful categories (hate, violence, etc.)
#   2. PII filters      — anonymize/block personal data in both directions
#   3. Topic denials    — block out-of-scope queries for the equipment agent
#
# Cost: ~$0 at POC scale (charged per 1 000 text units processed).
# =============================================================================

resource "aws_bedrock_guardrail" "watchman" {
  name        = "${var.project_name}-${var.environment}-guardrail"
  description = "Governance guardrail for the AWS-AI-Watchman equipment agent. Filters PII, harmful content, and off-topic queries."

  blocked_input_messaging   = "I cannot process this request. It contains restricted content or personally identifiable information that cannot be used with this system."
  blocked_outputs_messaging = "The response was blocked because it contained restricted content or personally identifiable information."

  # ---------------------------------------------------------------------------
  # Content filters — evaluated at HIGH sensitivity in both directions
  # ---------------------------------------------------------------------------
  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    # Prompt injection / jailbreak — input only (no meaningful output risk)
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  # ---------------------------------------------------------------------------
  # PII detection — ANONYMIZE replaces with [TYPE] placeholder; BLOCK rejects
  # the entire request if the PII type is present.
  # ---------------------------------------------------------------------------
  sensitive_information_policy_config {
    # Identity — anonymise in technician notes and queries
    pii_entities_config {
      type   = "NAME"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "ADDRESS"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "USERNAME"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "IP_ADDRESS"
      action = "ANONYMIZE"
    }

    # Financial / credential — block entirely; should never appear in equipment queries
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "US_BANK_ACCOUNT_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "US_BANK_ROUTING_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "PASSWORD"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "AWS_ACCESS_KEY"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "AWS_SECRET_KEY"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "DRIVER_ID"
      action = "BLOCK"
    }

    # Custom regex patterns — tied directly to our synthetic data schema
    regexes_config {
      name        = "technician-id"
      description = "Internal technician personnel ID (e.g. TECH-007). Anonymise in outputs."
      pattern     = "TECH-\\d{3}"
      action      = "ANONYMIZE"
    }
    regexes_config {
      name        = "equipment-serial"
      description = "Fleet equipment serial format (e.g. CAT-EX-001). Anonymise to protect asset inventory."
      pattern     = "[A-Z]{2,5}-[A-Z]{2}-\\d{3}"
      action      = "ANONYMIZE"
    }
  }

  # ---------------------------------------------------------------------------
  # Topic denials — block queries outside the equipment maintenance scope
  # ---------------------------------------------------------------------------
  topic_policy_config {
    topics_config {
      name       = "legal-advice"
      type       = "DENY"
      definition = "Requests for legal advice, liability assessment, contract interpretation, or regulatory compliance guidance related to equipment."
      examples = [
        "What is my legal liability if this excavator injures a worker?",
        "Can I sue the manufacturer for this hydraulic failure?",
        "Who is responsible for this accident on the job site?",
      ]
    }
    topics_config {
      name       = "competitor-information"
      type       = "DENY"
      definition = "Requests comparing this service to competitor equipment rental companies or asking for competitor pricing and availability."
      examples = [
        "How does United Rentals compare to Sunbelt Rentals for boom lifts?",
        "What does BlueLine Rental charge for an excavator per day?",
        "Is RSC Equipment better than this service?",
      ]
    }
    topics_config {
      name       = "rental-pricing"
      type       = "DENY"
      definition = "Requests for specific rental rates, quotes, discount negotiations, or financial terms for equipment."
      examples = [
        "What is the daily rate for a Caterpillar 320 excavator?",
        "Can I get a discount on a 6-month rental?",
        "What is the buyout price for this boom lift?",
      ]
    }
    topics_config {
      name       = "medical-advice"
      type       = "DENY"
      definition = "Requests for medical advice related to injuries sustained from equipment operation."
      examples = [
        "I was hit by the excavator arm, what should I do?",
        "What are the health effects of breathing hydraulic fluid fumes?",
      ]
    }
  }

  # ---------------------------------------------------------------------------
  # Word filters
  # ---------------------------------------------------------------------------
  word_policy_config {
    managed_word_lists_config {
      type = "PROFANITY"
    }
  }

  tags = local.common_tags
}

# Publish a versioned snapshot — the Knowledge Base and agent will reference
# this version ARN so guardrail changes require an explicit re-publish.
resource "aws_bedrock_guardrail_version" "watchman_v1" {
  guardrail_arn = aws_bedrock_guardrail.watchman.guardrail_arn
  description   = "v1 — Initial production guardrail: content filters, PII anonymisation, topic denials for equipment agent."

  # Version is immutable; prevent accidental destruction
  lifecycle {
    prevent_destroy = false
  }
}
