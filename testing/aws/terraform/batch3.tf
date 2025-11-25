# Batch 3: Advanced AWS Services - ElastiCache, Kinesis, EFS, OpenSearch, API Gateway, CloudFront, ECS, CloudWatch
# Estimated monthly cost: ~$62/month (minimal configuration)
#
# Breakdown:
# - ElastiCache: ~$15/month (1x cache.t3.micro Redis node)
# - Kinesis Stream: ~$11/month (1 shard)
# - EFS File System: ~$0.50/month (minimal storage, ~1GB)
# - OpenSearch: ~$35/month (1x t3.small.search node)
# - API Gateway: ~$0/month (REST API, pay per request)
# - CloudWatch Log Group: ~$0.50/month (minimal logs)
# - ECS Cluster: ~$0/month (cluster only, no tasks)
# - CloudFront: ~$0/month (distribution only, minimal traffic)
#
# ⚠️ IMPORTANT: Destruction Time
# - CloudFront distributions take 15-30 minutes to disable and delete
# - ElastiCache clusters take 5-10 minutes to delete
# - OpenSearch domains take 10-15 minutes to delete
# - Total destroy time: ~30-45 minutes (be patient!)

# ========== ElastiCache (Redis) ==========

# Subnet group for ElastiCache
resource "aws_elasticache_subnet_group" "test" {
  count      = var.enable_batch_3 ? 1 : 0
  name       = "${var.project_name}-elasticache-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name        = "${var.project_name}-elasticache-subnet-group"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }

  lifecycle {
    create_before_destroy = false
  }
}

# ElastiCache Redis cluster (1 node, t3.micro)
resource "aws_elasticache_cluster" "test" {
  count                = var.enable_batch_3 ? 1 : 0
  cluster_id           = "${var.project_name}-redis-cluster"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.1"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.test[0].name
  security_group_ids   = [aws_security_group.default.id]

  tags = {
    Name         = "${var.project_name}-redis-cluster"
    TestScenario = "ElastiCache cluster with low utilization"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Kinesis Stream ==========

resource "aws_kinesis_stream" "test" {
  count            = var.enable_batch_3 ? 1 : 0
  name             = "${var.project_name}-kinesis-stream"
  shard_count      = 1
  retention_period = 24 # 24 hours (minimum)

  shard_level_metrics = [
    "IncomingBytes",
    "IncomingRecords",
    "OutgoingBytes",
    "OutgoingRecords",
  ]

  tags = {
    Name         = "${var.project_name}-kinesis-stream"
    TestScenario = "Kinesis stream with minimal throughput"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== EFS File System ==========

resource "aws_efs_file_system" "test" {
  count            = var.enable_batch_3 ? 1 : 0
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name         = "${var.project_name}-efs"
    TestScenario = "EFS file system with low usage"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# EFS Mount Target (required for VPC access)
resource "aws_efs_mount_target" "test" {
  count           = var.enable_batch_3 ? 1 : 0
  file_system_id  = aws_efs_file_system.test[0].id
  subnet_id       = aws_subnet.private_1.id
  security_groups = [aws_security_group.default.id]
}

# ========== OpenSearch Domain ==========

# Service-linked role for OpenSearch VPC access
# This role is automatically created by AWS when first using OpenSearch
# We just reference it instead of trying to create it (which fails if it exists)
data "aws_iam_role" "opensearch" {
  count = var.enable_batch_3 ? 1 : 0
  name  = "AWSServiceRoleForAmazonOpenSearchService"
}

resource "aws_opensearch_domain" "test" {
  count         = var.enable_batch_3 ? 1 : 0
  domain_name   = "${var.project_name}-opensearch"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = "t3.small.search"
    instance_count = 1
    zone_awareness_enabled = false
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10 # Minimum 10 GB
    volume_type = "gp3"
  }

  vpc_options {
    subnet_ids         = [aws_subnet.private_1.id]
    security_group_ids = [aws_security_group.default.id]
  }

  advanced_security_options {
    enabled                        = false
    internal_user_database_enabled = true
  }

  encrypt_at_rest {
    enabled = false # Disabled for t3.small.search (not supported)
  }

  node_to_node_encryption {
    enabled = false # Disabled for testing
  }

  domain_endpoint_options {
    enforce_https       = false
    tls_security_policy = "Policy-Min-TLS-1-0-2019-07"
  }

  tags = {
    Name         = "${var.project_name}-opensearch"
    TestScenario = "OpenSearch domain with minimal usage"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }

  # Service-linked role is managed by AWS, no need for explicit dependency
  depends_on = [data.aws_iam_role.opensearch]
}

# ========== API Gateway ==========

resource "aws_api_gateway_rest_api" "test" {
  count       = var.enable_batch_3 ? 1 : 0
  name        = "${var.project_name}-api-gateway"
  description = "Test API Gateway for CutCosts testing"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name         = "${var.project_name}-api-gateway"
    TestScenario = "API Gateway with zero traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

resource "aws_api_gateway_resource" "test" {
  count       = var.enable_batch_3 ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.test[0].id
  parent_id   = aws_api_gateway_rest_api.test[0].root_resource_id
  path_part   = "test"
}

resource "aws_api_gateway_method" "test" {
  count         = var.enable_batch_3 ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.test[0].id
  resource_id   = aws_api_gateway_resource.test[0].id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "test" {
  count       = var.enable_batch_3 ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.test[0].id
  resource_id = aws_api_gateway_resource.test[0].id
  http_method = aws_api_gateway_method.test[0].http_method
  type        = "MOCK"
}

# Deploy API Gateway
resource "aws_api_gateway_deployment" "test" {
  count       = var.enable_batch_3 ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.test[0].id

  depends_on = [
    aws_api_gateway_integration.test
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage (replaces deprecated stage_name in deployment)
resource "aws_api_gateway_stage" "test" {
  count         = var.enable_batch_3 ? 1 : 0
  deployment_id = aws_api_gateway_deployment.test[0].id
  rest_api_id   = aws_api_gateway_rest_api.test[0].id
  stage_name    = "test"
}

# ========== CloudWatch Log Group ==========

resource "aws_cloudwatch_log_group" "test" {
  count             = var.enable_batch_3 ? 1 : 0
  name              = "/aws/cutcosts/testing/${var.project_name}"
  retention_in_days = 1 # Minimum retention for cost savings

  tags = {
    Name         = "${var.project_name}-log-group"
    TestScenario = "CloudWatch log group with old/unused logs"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Write some sample logs
resource "null_resource" "write_sample_logs" {
  count = var.enable_batch_3 ? 1 : 0

  provisioner "local-exec" {
    command = <<-EOF
      aws logs create-log-stream \
        --log-group-name "${aws_cloudwatch_log_group.test[0].name}" \
        --log-stream-name "test-stream" \
        --region ${var.aws_region} || true

      aws logs put-log-events \
        --log-group-name "${aws_cloudwatch_log_group.test[0].name}" \
        --log-stream-name "test-stream" \
        --log-events timestamp=$(date +%s)000,message="Test log entry for CutCosts testing" \
        --region ${var.aws_region} || true
    EOF
  }

  depends_on = [aws_cloudwatch_log_group.test]
}

# ========== ECS Cluster (without tasks) ==========

resource "aws_ecs_cluster" "test_batch3" {
  count = var.enable_batch_3 ? 1 : 0
  name  = "${var.project_name}-ecs-cluster-batch3"

  setting {
    name  = "containerInsights"
    value = "disabled" # Disabled for cost savings
  }

  tags = {
    Name         = "${var.project_name}-ecs-cluster-batch3"
    TestScenario = "ECS cluster with no running tasks"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== CloudFront Distribution ==========

# Random suffix for S3 bucket (batch 3 specific)
resource "random_id" "cloudfront_bucket_suffix" {
  count       = var.enable_batch_3 ? 1 : 0
  byte_length = 4
}

# S3 bucket for CloudFront origin
resource "aws_s3_bucket" "cloudfront_origin" {
  count  = var.enable_batch_3 ? 1 : 0
  bucket = "${var.project_name}-cloudfront-origin-${random_id.cloudfront_bucket_suffix[0].hex}"

  tags = {
    Name        = "${var.project_name}-cloudfront-origin"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure - CloudFront origin"
    Owner       = var.owner_email
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "cloudfront_origin" {
  count  = var.enable_batch_3 ? 1 : 0
  bucket = aws_s3_bucket.cloudfront_origin[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "test" {
  count                             = var.enable_batch_3 ? 1 : 0
  name                              = "${var.project_name}-oac"
  description                       = "OAC for CutCosts testing"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "test" {
  count               = var.enable_batch_3 ? 1 : 0
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CutCosts testing distribution with minimal traffic"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # US, Canada, Europe only

  origin {
    domain_name              = aws_s3_bucket.cloudfront_origin[0].bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.cloudfront_origin[0].id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.test[0].id
  }

  default_cache_behavior {
    target_origin_id       = "S3-${aws_s3_bucket.cloudfront_origin[0].id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name         = "${var.project_name}-cloudfront"
    TestScenario = "CloudFront distribution with minimal traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }

  # CloudFront distributions are VERY slow to delete (15-30 minutes)
  # This lifecycle prevents accidental deletion and ensures proper cleanup
  lifecycle {
    prevent_destroy = false
    create_before_destroy = false
  }
}

# ========== Outputs ==========

output "batch_3_resources" {
  description = "Batch 3 resource IDs"
  value = var.enable_batch_3 ? {
    elasticache_cluster_id      = aws_elasticache_cluster.test[0].cluster_id
    kinesis_stream_name         = aws_kinesis_stream.test[0].name
    efs_file_system_id          = aws_efs_file_system.test[0].id
    opensearch_domain_endpoint  = aws_opensearch_domain.test[0].endpoint
    api_gateway_id              = aws_api_gateway_rest_api.test[0].id
    api_gateway_url             = aws_api_gateway_stage.test[0].invoke_url
    cloudwatch_log_group_name   = aws_cloudwatch_log_group.test[0].name
    ecs_cluster_name            = aws_ecs_cluster.test_batch3[0].name
    cloudfront_distribution_id  = aws_cloudfront_distribution.test[0].id
    cloudfront_domain_name      = aws_cloudfront_distribution.test[0].domain_name
  } : {}
}
