# =============================================================================
# AWS AI Watchman — Bedrock Knowledge Base
#
# Implements RAG (Retrieval-Augmented Generation) by connecting the Gold
# S3 bucket to a Bedrock Knowledge Base backed by an OpenSearch Serverless
# vector store. The Knowledge Base chunks, embeds, and indexes curated
# equipment manuals and service logs so Claude can answer technician
# queries with zero hallucination on proprietary fleet data.
#
# COST WARNING:
#   OpenSearch Serverless vector search requires a minimum of 2 OCUs each
#   for indexing and search = ~$700/month minimum.
#   Leave enable_bedrock_kb=false (the default) for dev/POC work.
#   Enable only when actively demonstrating RAG:
#     terraform apply -var="enable_bedrock_kb=true"
#   Destroy when done:
#     terraform destroy -target=aws_bedrockagent_knowledge_base.watchman \
#                       -target=aws_opensearchserverless_collection.kb
#
# Architecture flow:
#   Gold S3 → Bedrock Data Source → Chunker → Titan Embed v2 →
#   OpenSearch Serverless (vector index) → Bedrock Knowledge Base → Claude
# =============================================================================

locals {
  kb_collection_arn = var.enable_bedrock_kb ? aws_opensearchserverless_collection.kb[0].arn : ""
}

# =============================================================================
# OpenSearch Serverless — Vector Store
# =============================================================================

resource "aws_opensearchserverless_security_policy" "kb_encryption" {
  count = var.enable_bedrock_kb ? 1 : 0

  # Policy names: max 32 chars, alphanumeric + hyphens only
  name        = "${var.project_name}-${var.environment}-kb-enc"
  type        = "encryption"
  description = "Encryption policy for the Watchman KB vector collection."
  policy = jsonencode({
    Rules = [{
      Resource     = ["collection/${var.project_name}-${var.environment}-kb"]
      ResourceType = "collection"
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "kb_network" {
  count = var.enable_bedrock_kb ? 1 : 0

  name        = "${var.project_name}-${var.environment}-kb-net"
  type        = "network"
  description = "Network policy — public access for Bedrock service plane."
  policy = jsonencode([{
    Description = "Public access for Bedrock Knowledge Base ingestion and query"
    Rules = [
      {
        Resource     = ["collection/${var.project_name}-${var.environment}-kb"]
        ResourceType = "collection"
      },
    ]
    AllowFromPublic = true
  }])
}

resource "aws_opensearchserverless_collection" "kb" {
  count = var.enable_bedrock_kb ? 1 : 0

  name        = "${var.project_name}-${var.environment}-kb"
  type        = "VECTORSEARCH"
  description = "Vector store for the AWS-AI-Watchman Bedrock Knowledge Base."
  tags        = merge(local.common_tags, { DataLayer = "gold" })

  depends_on = [
    aws_opensearchserverless_security_policy.kb_encryption,
    aws_opensearchserverless_security_policy.kb_network,
  ]
}

# Grant the Bedrock KB role (and the deploy principal) data-plane access
# to create/read the vector index inside the collection.
resource "aws_opensearchserverless_access_policy" "kb" {
  count = var.enable_bedrock_kb ? 1 : 0

  name        = "${var.project_name}-${var.environment}-kb-acc"
  type        = "data"
  description = "Data-plane access for Bedrock KB role and bootstrap principal."
  policy = jsonencode([{
    Rules = [
      {
        Resource     = ["collection/${var.project_name}-${var.environment}-kb"]
        ResourceType = "collection"
        Permission   = ["aoss:DescribeCollectionItems"]
      },
      {
        Resource     = ["index/${var.project_name}-${var.environment}-kb/*"]
        ResourceType = "index"
        Permission = [
          "aoss:CreateIndex",
          "aoss:DeleteIndex",
          "aoss:UpdateIndex",
          "aoss:DescribeIndex",
          "aoss:ReadDocument",
          "aoss:WriteDocument",
        ]
      },
    ]
    Principal = [
      aws_iam_role.bedrock_kb[0].arn,
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
    ]
  }])
}

# =============================================================================
# Bedrock Knowledge Base
# =============================================================================

resource "aws_bedrockagent_knowledge_base" "watchman" {
  count = var.enable_bedrock_kb ? 1 : 0

  name        = "${var.project_name}-${var.environment}-knowledge-base"
  description = "RAG knowledge base grounded on curated fleet manuals and service logs from the Gold S3 layer."
  role_arn    = aws_iam_role.bedrock_kb[0].arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      # Titan Embed Text v2 — 1 024-dimension embeddings, supports up to 8 192 tokens
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.kb[0].arn
      vector_index_name = "watchman-gold-index"

      field_mapping {
        vector_field   = "watchman-embedding"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_opensearchserverless_access_policy.kb,
    aws_iam_role_policy.bedrock_kb,
  ]
}

# =============================================================================
# Data Source — Gold S3 Bucket
# The Knowledge Base ingestion job chunks documents from Gold and embeds them.
# Trigger a sync after uploading processed data:
#   aws bedrock-agent start-ingestion-job \
#     --knowledge-base-id <id> --data-source-id <id>
# =============================================================================

resource "aws_bedrockagent_data_source" "gold" {
  count = var.enable_bedrock_kb ? 1 : 0

  knowledge_base_id = aws_bedrockagent_knowledge_base.watchman[0].id
  name              = "${var.project_name}-${var.environment}-gold-source"
  description       = "Gold-layer S3 bucket containing chunked OEM manuals and service logs."

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.gold.arn
    }
  }
}
