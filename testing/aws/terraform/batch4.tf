# Batch 4: Advanced AWS Services - VPC Endpoint, Neptune, MSK, Redshift, VPN, Transit Gateway, Global Accelerator, DocumentDB (8 resources)
# Estimated monthly cost: ~$1,166/month (minimal configuration)
#
# Breakdown:
# - VPC Endpoint (Interface): ~$7.20/month (1x endpoint)
# - Neptune: ~$80/month (1x db.t3.medium instance)
# - MSK (Kafka): ~$70/month (2x kafka.t3.small brokers)
# - Redshift: ~$793/month (1x ra3.xlplus node - current generation)
# - VPN Connection: ~$36/month (site-to-site VPN)
# - Transit Gateway Attachment: ~$36/month (VPC attachment)
# - Application Load Balancer: ~$27/month (ALB for Global Accelerator)
# - Global Accelerator: ~$18/month (accelerator + 1 endpoint)
# - DocumentDB: ~$80/month (1x db.t3.medium instance)
#
# Note: SageMaker removed due to health check complexity requiring real ML model artifacts
#
# ⚠️ IMPORTANT: Destruction Time
# - Neptune clusters take 10-15 minutes to delete
# - Redshift clusters take 5-10 minutes to delete (with skip_final_snapshot)
# - DocumentDB clusters take 10-15 minutes to delete
# - MSK clusters take 15-20 minutes to delete
# - Transit Gateway attachments take 5-10 minutes to delete
# - Total destroy time: ~30-45 minutes (be patient!)

# ========== VPC Endpoint (Interface) ==========

resource "aws_vpc_endpoint" "test" {
  count               = var.enable_batch_4 ? 1 : 0
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_1.id]
  security_group_ids  = [aws_security_group.default.id]
  private_dns_enabled = false

  tags = {
    Name         = "${var.project_name}-vpc-endpoint-s3"
    TestScenario = "VPC Interface Endpoint with low traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Neptune Database Cluster ==========

# Subnet group for Neptune
resource "aws_neptune_subnet_group" "test" {
  count      = var.enable_batch_4 ? 1 : 0
  name       = "${var.project_name}-neptune-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name        = "${var.project_name}-neptune-subnet-group"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# Neptune cluster parameter group
resource "aws_neptune_cluster_parameter_group" "test" {
  count       = var.enable_batch_4 ? 1 : 0
  family      = "neptune1.3"
  name        = "${var.project_name}-neptune-params"
  description = "CutCosts testing Neptune cluster parameter group"

  tags = {
    Name        = "${var.project_name}-neptune-params"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# Neptune cluster (graph database)
resource "aws_neptune_cluster" "test" {
  count                           = var.enable_batch_4 ? 1 : 0
  cluster_identifier              = "${var.project_name}-neptune-cluster"
  engine                          = "neptune"
  engine_version                  = "1.3.2.1"
  backup_retention_period         = 1
  preferred_backup_window         = "07:00-09:00"
  skip_final_snapshot             = true
  neptune_subnet_group_name       = aws_neptune_subnet_group.test[0].name
  neptune_cluster_parameter_group_name = aws_neptune_cluster_parameter_group.test[0].name
  vpc_security_group_ids          = [aws_security_group.default.id]

  tags = {
    Name         = "${var.project_name}-neptune-cluster"
    TestScenario = "Neptune graph database with low query volume"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Neptune instance (1x db.t3.medium)
resource "aws_neptune_cluster_instance" "test" {
  count              = var.enable_batch_4 ? 1 : 0
  cluster_identifier = aws_neptune_cluster.test[0].id
  instance_class     = "db.t3.medium"
  engine             = "neptune"
  identifier         = "${var.project_name}-neptune-instance"

  tags = {
    Name         = "${var.project_name}-neptune-instance"
    TestScenario = "Neptune instance with minimal usage"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== MSK (Managed Streaming for Kafka) ==========

resource "aws_msk_cluster" "test" {
  count                  = var.enable_batch_4 ? 1 : 0
  cluster_name           = "${var.project_name}-msk-cluster"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_groups = [aws_security_group.default.id]
    storage_info {
      ebs_storage_info {
        volume_size = 10 # GB (minimum for t3.small)
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  tags = {
    Name         = "${var.project_name}-msk-cluster"
    TestScenario = "MSK Kafka cluster with low throughput"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Redshift Cluster ==========

# Subnet group for Redshift
resource "aws_redshift_subnet_group" "test" {
  count      = var.enable_batch_4 ? 1 : 0
  name       = "${var.project_name}-redshift-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name        = "${var.project_name}-redshift-subnet-group"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# Redshift cluster (1x ra3.xlplus node - current generation)
resource "aws_redshift_cluster" "test" {
  count                       = var.enable_batch_4 ? 1 : 0
  cluster_identifier          = "${var.project_name}-redshift-cluster"
  database_name               = "testdb"
  master_username             = "dbadmin"
  master_password             = "TestPassword123!"
  node_type                   = "ra3.xlplus"
  cluster_type                = "single-node"
  cluster_subnet_group_name   = aws_redshift_subnet_group.test[0].name
  vpc_security_group_ids      = [aws_security_group.default.id]
  skip_final_snapshot         = true
  publicly_accessible         = false

  tags = {
    Name         = "${var.project_name}-redshift-cluster"
    TestScenario = "Redshift data warehouse with no queries"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== VPN Connection ==========

# Customer Gateway (simulates on-premises VPN device)
resource "aws_customer_gateway" "test" {
  count      = var.enable_batch_4 ? 1 : 0
  bgp_asn    = 65000
  ip_address = "203.0.113.1" # Example IP (RFC 5737 documentation range)
  type       = "ipsec.1"

  tags = {
    Name         = "${var.project_name}-customer-gateway"
    TestScenario = "Customer gateway for VPN testing"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Virtual Private Gateway
resource "aws_vpn_gateway" "test" {
  count  = var.enable_batch_4 ? 1 : 0
  vpc_id = aws_vpc.main.id

  tags = {
    Name         = "${var.project_name}-vpn-gateway"
    TestScenario = "VPN gateway for site-to-site connection"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Site-to-Site VPN Connection (with zero traffic)
resource "aws_vpn_connection" "test" {
  count               = var.enable_batch_4 ? 1 : 0
  vpn_gateway_id      = aws_vpn_gateway.test[0].id
  customer_gateway_id = aws_customer_gateway.test[0].id
  type                = "ipsec.1"
  static_routes_only  = true

  tags = {
    Name         = "${var.project_name}-vpn-connection"
    TestScenario = "VPN connection with zero traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Transit Gateway ==========

# Transit Gateway
resource "aws_ec2_transit_gateway" "test" {
  count       = var.enable_batch_4 ? 1 : 0
  description = "CutCosts testing transit gateway"

  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"

  tags = {
    Name         = "${var.project_name}-transit-gateway"
    TestScenario = "Transit gateway for VPC interconnection"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Transit Gateway VPC Attachment (with zero traffic)
resource "aws_ec2_transit_gateway_vpc_attachment" "test" {
  count              = var.enable_batch_4 ? 1 : 0
  subnet_ids         = [aws_subnet.private_1.id]
  transit_gateway_id = aws_ec2_transit_gateway.test[0].id
  vpc_id             = aws_vpc.main.id

  tags = {
    Name         = "${var.project_name}-tgw-attachment"
    TestScenario = "Transit gateway attachment with zero traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Application Load Balancer (for Global Accelerator) ==========

# ALB for Global Accelerator endpoint
resource "aws_lb" "batch4_alb" {
  count              = var.enable_batch_4 ? 1 : 0
  name               = "${var.project_name}-batch4-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.default.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  enable_deletion_protection = false

  tags = {
    Name         = "${var.project_name}-batch4-alb"
    TestScenario = "ALB for Global Accelerator endpoint testing"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Target group for ALB (no targets)
resource "aws_lb_target_group" "batch4" {
  count    = var.enable_batch_4 ? 1 : 0
  name     = "${var.project_name}-batch4-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name        = "${var.project_name}-batch4-tg"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# ALB Listener
resource "aws_lb_listener" "batch4" {
  count             = var.enable_batch_4 ? 1 : 0
  load_balancer_arn = aws_lb.batch4_alb[0].arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.batch4[0].arn
  }
}

# ========== Global Accelerator ==========

# Global Accelerator (global service, not region-specific)
resource "aws_globalaccelerator_accelerator" "test" {
  count           = var.enable_batch_4 ? 1 : 0
  name            = "${var.project_name}-global-accelerator"
  ip_address_type = "IPV4"
  enabled         = true

  attributes {
    flow_logs_enabled = false
  }

  tags = {
    Name         = "${var.project_name}-global-accelerator"
    TestScenario = "Global Accelerator with minimal traffic"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# Global Accelerator Listener
resource "aws_globalaccelerator_listener" "test" {
  count           = var.enable_batch_4 ? 1 : 0
  accelerator_arn = aws_globalaccelerator_accelerator.test[0].id
  protocol        = "TCP"

  port_range {
    from_port = 80
    to_port   = 80
  }
}

# Global Accelerator Endpoint Group (pointing to dedicated Batch 4 ALB)
resource "aws_globalaccelerator_endpoint_group" "test" {
  count         = var.enable_batch_4 ? 1 : 0
  listener_arn  = aws_globalaccelerator_listener.test[0].id

  endpoint_configuration {
    endpoint_id = aws_lb.batch4_alb[0].arn
    weight      = 100
  }

  health_check_interval_seconds = 30
  health_check_path             = "/"
  health_check_protocol         = "HTTP"
  threshold_count               = 3
  traffic_dial_percentage       = 0 # 0% traffic for testing
}

# ========== DocumentDB Cluster ==========

# Subnet group for DocumentDB
resource "aws_docdb_subnet_group" "test" {
  count      = var.enable_batch_4 ? 1 : 0
  name       = "${var.project_name}-docdb-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name        = "${var.project_name}-docdb-subnet-group"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# DocumentDB cluster parameter group
resource "aws_docdb_cluster_parameter_group" "test" {
  count       = var.enable_batch_4 ? 1 : 0
  family      = "docdb5.0"
  name        = "${var.project_name}-docdb-params"
  description = "CutCosts testing DocumentDB cluster parameter group"

  tags = {
    Name        = "${var.project_name}-docdb-params"
    ManagedBy   = "Terraform"
    Environment = var.environment
    Purpose     = "CutCosts Testing Infrastructure"
    Owner       = var.owner_email
  }
}

# DocumentDB cluster (MongoDB-compatible)
resource "aws_docdb_cluster" "test" {
  count                           = var.enable_batch_4 ? 1 : 0
  cluster_identifier              = "${var.project_name}-docdb-cluster"
  engine                          = "docdb"
  master_username                 = "dbadmin"
  master_password                 = "TestPassword123!"
  backup_retention_period         = 1
  preferred_backup_window         = "07:00-09:00"
  skip_final_snapshot             = true
  db_subnet_group_name            = aws_docdb_subnet_group.test[0].name
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.test[0].name
  vpc_security_group_ids          = [aws_security_group.default.id]

  tags = {
    Name         = "${var.project_name}-docdb-cluster"
    TestScenario = "DocumentDB cluster with low query volume"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# DocumentDB instance (1x db.t3.medium)
resource "aws_docdb_cluster_instance" "test" {
  count              = var.enable_batch_4 ? 1 : 0
  identifier         = "${var.project_name}-docdb-instance"
  cluster_identifier = aws_docdb_cluster.test[0].id
  instance_class     = "db.t3.medium"

  tags = {
    Name         = "${var.project_name}-docdb-instance"
    TestScenario = "DocumentDB instance with minimal usage"
    ManagedBy    = "Terraform"
    Environment  = var.environment
    Purpose      = "CutCosts Testing Infrastructure"
    Owner        = var.owner_email
  }
}

# ========== Outputs ==========

output "batch_4_resources" {
  description = "Batch 4 resource IDs"
  value = var.enable_batch_4 ? {
    vpc_endpoint_id                       = aws_vpc_endpoint.test[0].id
    neptune_cluster_endpoint              = aws_neptune_cluster.test[0].endpoint
    neptune_instance_id                   = aws_neptune_cluster_instance.test[0].id
    msk_cluster_arn                       = aws_msk_cluster.test[0].arn
    redshift_cluster_id                   = aws_redshift_cluster.test[0].id
    vpn_connection_id                     = aws_vpn_connection.test[0].id
    transit_gateway_id                    = aws_ec2_transit_gateway.test[0].id
    transit_gateway_attachment_id         = aws_ec2_transit_gateway_vpc_attachment.test[0].id
    alb_dns_name                          = aws_lb.batch4_alb[0].dns_name
    global_accelerator_dns_name           = aws_globalaccelerator_accelerator.test[0].dns_name
    documentdb_cluster_endpoint           = aws_docdb_cluster.test[0].endpoint
    documentdb_instance_id                = aws_docdb_cluster_instance.test[0].id
  } : {}
}
