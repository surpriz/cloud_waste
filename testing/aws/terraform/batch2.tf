# Batch 2: Advanced Resources - EKS, S3, Lambda, DynamoDB, Fargate
# Estimated monthly cost: ~$95/month (minimal configuration)
#
# Breakdown:
# - EKS Cluster: $72/month (control plane)
# - EKS Node Group: ~$15/month (1x t3.micro on-demand)
# - S3 Bucket: ~$1/month (10GB storage + requests)
# - Lambda Function: ~$0.50/month (1M invocations/month)
# - DynamoDB Table: ~$5/month (1GB storage + 5 RCU/WCU)
# - Fargate Tasks: ~$1/month (minimal vCPU/memory)

# ========== EKS Cluster ==========

# EKS Cluster ($72/month for control plane)
resource "aws_eks_cluster" "test" {
  count    = var.enable_batch_2 ? 1 : 0
  name     = "${var.project_name}-eks-cluster"
  role_arn = aws_iam_role.eks_cluster[0].arn
  version  = "1.31"  # Latest EKS version

  vpc_config {
    subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

    # Public endpoint for easier testing
    endpoint_public_access = true
    endpoint_private_access = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
  ]

  tags = {
    Name         = "${var.project_name}-eks-cluster"
    TestScenario = "EKS Cluster with minimal nodes"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# IAM Role for EKS Cluster
resource "aws_iam_role" "eks_cluster" {
  count = var.enable_batch_2 ? 1 : 0
  name  = "${var.project_name}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-eks-cluster-role"
  }
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster[0].name
}

# EKS Node Group (1x t3.micro ~ $15/month)
resource "aws_eks_node_group" "test" {
  count           = var.enable_batch_2 ? 1 : 0
  cluster_name    = aws_eks_cluster.test[0].name
  node_group_name = "${var.project_name}-node-group"
  node_role_arn   = aws_iam_role.eks_nodes[0].arn
  subnet_ids      = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  scaling_config {
    desired_size = 1
    max_size     = 1
    min_size     = 1
  }

  instance_types = ["t3.micro"]  # Minimal cost
  capacity_type  = "ON_DEMAND"   # Predictable pricing

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_group_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_registry_policy,
  ]

  tags = {
    Name         = "${var.project_name}-node-group"
    TestScenario = "Minimal EKS node group"
  }
}

# IAM Role for EKS Nodes
resource "aws_iam_role" "eks_nodes" {
  count = var.enable_batch_2 ? 1 : 0
  name  = "${var.project_name}-eks-nodes-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-eks-nodes-role"
  }
}

resource "aws_iam_role_policy_attachment" "eks_node_group_policy" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_nodes[0].name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_nodes[0].name
}

resource "aws_iam_role_policy_attachment" "eks_registry_policy" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_nodes[0].name
}

# ========== S3 Bucket ==========

# Random suffix for globally unique bucket name
resource "random_id" "bucket_suffix" {
  count       = var.enable_batch_2 ? 1 : 0
  byte_length = 4
}

# S3 Bucket (~$1/month for 10GB storage)
resource "aws_s3_bucket" "test" {
  count  = var.enable_batch_2 ? 1 : 0
  bucket = "${var.project_name}-s3-bucket-${random_id.bucket_suffix[0].hex}"

  tags = {
    Name         = "${var.project_name}-test-bucket"
    TestScenario = "S3 Bucket with minimal data"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Disable public access
resource "aws_s3_bucket_public_access_block" "test" {
  count  = var.enable_batch_2 ? 1 : 0
  bucket = aws_s3_bucket.test[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload test files (10 small files for cost estimation)
resource "aws_s3_object" "test_file" {
  count  = var.enable_batch_2 ? 10 : 0  # 10 small files
  bucket = aws_s3_bucket.test[0].id
  key    = "test-data/file-${count.index}.txt"
  content = "Test file ${count.index} for CutCosts bucket detection - ${timestamp()}"

  tags = {
    Name = "test-file-${count.index}"
  }
}

# ========== Lambda Function ==========

# Create Lambda source file
resource "local_file" "lambda_source" {
  count    = var.enable_batch_2 ? 1 : 0
  filename = "${path.module}/lambda_temp/index.py"
  content  = <<-PYTHON
import json

def handler(event, context):
    """Simple Lambda function for testing CutCosts detection."""
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from CutCosts test Lambda!')
    }
PYTHON
}

# Create Lambda deployment package (zip)
data "archive_file" "lambda_package" {
  count       = var.enable_batch_2 ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/lambda_temp"
  output_path = "${path.module}/lambda_function.zip"

  depends_on = [local_file.lambda_source]
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  count = var.enable_batch_2 ? 1 : 0
  name  = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-lambda-role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda[0].name
}

# Lambda Function (~$0.50/month for minimal invocations)
resource "aws_lambda_function" "test" {
  count         = var.enable_batch_2 ? 1 : 0
  filename      = data.archive_file.lambda_package[0].output_path
  function_name = "${var.project_name}-lambda-function"
  role          = aws_iam_role.lambda[0].arn
  handler       = "index.handler"
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128  # Minimal memory

  source_code_hash = data.archive_file.lambda_package[0].output_base64sha256

  environment {
    variables = {
      ENV = var.environment
    }
  }

  tags = {
    Name         = "${var.project_name}-lambda-function"
    TestScenario = "Lambda function with minimal invocations"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== DynamoDB Table ==========

# DynamoDB Table (~$5/month for 1GB storage + minimal throughput)
resource "aws_dynamodb_table" "test" {
  count          = var.enable_batch_2 ? 1 : 0
  name           = "${var.project_name}-dynamodb-table"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5   # Minimal RCU
  write_capacity = 5   # Minimal WCU
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Name         = "${var.project_name}-dynamodb-table"
    TestScenario = "DynamoDB table with minimal throughput"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Insert test data into DynamoDB (10 items)
resource "null_resource" "dynamodb_data" {
  count = var.enable_batch_2 ? 1 : 0

  depends_on = [aws_dynamodb_table.test]

  provisioner "local-exec" {
    command = <<-EOT
      for i in {1..10}; do
        aws dynamodb put-item \
          --table-name ${aws_dynamodb_table.test[0].name} \
          --item "{\"id\": {\"S\": \"test-item-$i\"}, \"data\": {\"S\": \"Test data $i\"}}" \
          --region ${var.aws_region} || true
      done
    EOT
  }

  triggers = {
    table_id = aws_dynamodb_table.test[0].id
  }
}

# ========== Fargate Task ==========

# ECS Cluster for Fargate (~$0/month, pay per task execution)
resource "aws_ecs_cluster" "test" {
  count = var.enable_batch_2 ? 1 : 0
  name  = "${var.project_name}-ecs-cluster"

  tags = {
    Name         = "${var.project_name}-ecs-cluster"
    TestScenario = "ECS cluster for Fargate tasks"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# IAM Role for Fargate Execution
resource "aws_iam_role" "fargate_execution" {
  count = var.enable_batch_2 ? 1 : 0
  name  = "${var.project_name}-fargate-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-fargate-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "fargate_execution_policy" {
  count      = var.enable_batch_2 ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  role       = aws_iam_role.fargate_execution[0].name
}

# Fargate Task Definition (~$1/month for minimal vCPU/memory)
resource "aws_ecs_task_definition" "test" {
  count                    = var.enable_batch_2 ? 1 : 0
  family                   = "${var.project_name}-fargate-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"   # 0.25 vCPU (minimal)
  memory                   = "512"   # 0.5 GB (minimal)
  execution_role_arn       = aws_iam_role.fargate_execution[0].arn

  container_definitions = jsonencode([{
    name  = "test-container"
    image = "nginx:latest"
    portMappings = [{
      containerPort = 80
      protocol      = "tcp"
    }]
  }])

  tags = {
    Name         = "${var.project_name}-fargate-task"
    TestScenario = "Fargate task with minimal resources"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Run 1 Fargate task (for testing)
resource "aws_ecs_service" "test" {
  count           = var.enable_batch_2 ? 1 : 0
  name            = "${var.project_name}-fargate-service"
  cluster         = aws_ecs_cluster.test[0].id
  task_definition = aws_ecs_task_definition.test[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_1.id]
    security_groups  = [aws_security_group.default.id]
    assign_public_ip = false
  }

  tags = {
    Name         = "${var.project_name}-fargate-service"
    TestScenario = "Running Fargate service"
  }
}
