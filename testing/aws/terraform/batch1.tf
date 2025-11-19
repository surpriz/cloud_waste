# Batch 1: Core Resources (~$20/month with stopped instances)
# These are the most common orphan resources with minimal cost

# 1. EBS Volume - Unattached ($0.10/month)
resource "aws_ebs_volume" "unattached" {
  count             = var.enable_batch_1 ? 1 : 0
  availability_zone = var.availability_zones[0]
  size              = 1  # 1GB minimum
  type              = "gp3"

  tags = {
    Name        = "${var.project_name}-unattached-volume"
    TestScenario = "Unattached EBS Volume"
  }
}

# 2. Elastic IP - Unassociated ($3.60/month)
resource "aws_eip" "unassociated" {
  count  = var.enable_batch_1 ? 1 : 0
  domain = "vpc"

  tags = {
    Name         = "${var.project_name}-unassociated-eip"
    TestScenario = "Unassociated Elastic IP"
  }
}

# 3. EBS Snapshot - Old snapshot ($0.05/month)
resource "aws_ebs_snapshot" "old" {
  count       = var.enable_batch_1 ? 1 : 0
  volume_id   = aws_ebs_volume.unattached[0].id
  description = "Old snapshot for testing orphan detection"

  tags = {
    Name         = "${var.project_name}-old-snapshot"
    TestScenario = "Old EBS Snapshot"
  }
}

# 4. EC2 Instance - Stopped ($0/month when stopped, t3.micro)
resource "aws_instance" "stopped" {
  count                  = var.enable_batch_1 ? 1 : 0
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.default.id]

  tags = {
    Name         = "${var.project_name}-stopped-instance"
    TestScenario = "Stopped EC2 Instance"
  }

  # Stop instance immediately after creation
  lifecycle {
    ignore_changes = [ami]
  }
}

# Stop the EC2 instance using null_resource
resource "null_resource" "stop_instance" {
  count = var.enable_batch_1 ? 1 : 0

  depends_on = [aws_instance.stopped]

  provisioner "local-exec" {
    command = "aws ec2 stop-instances --instance-ids ${aws_instance.stopped[0].id} --region ${var.aws_region}"
  }
}

# 5. Application Load Balancer - Zero traffic ($16/month)
resource "aws_lb" "zero_traffic" {
  count              = var.enable_batch_1 ? 1 : 0
  name               = "cutcosts-zero-traffic-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.default.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  enable_deletion_protection = false

  tags = {
    Name         = "cutcosts-zero-traffic-alb"
    TestScenario = "Load Balancer with Zero Traffic"
  }
}

resource "aws_lb_target_group" "zero_traffic" {
  count    = var.enable_batch_1 ? 1 : 0
  name     = "${var.project_name}-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 10
  }

  tags = {
    Name = "${var.project_name}-target-group"
  }
}

resource "aws_lb_listener" "zero_traffic" {
  count             = var.enable_batch_1 ? 1 : 0
  load_balancer_arn = aws_lb.zero_traffic[0].arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.zero_traffic[0].arn
  }
}

# 6. RDS Instance - Stopped ($0/month when stopped, db.t3.micro)
resource "aws_db_subnet_group" "rds" {
  count      = var.enable_batch_1 ? 1 : 0
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name = "${var.project_name}-rds-subnet-group"
  }
}

resource "aws_db_instance" "stopped" {
  count                  = var.enable_batch_1 ? 1 : 0
  identifier             = "${var.project_name}-stopped-db"
  engine                 = "postgres"
  engine_version         = "15.15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  db_name                = "testdb"
  username               = "dbadmin"
  password               = "ChangeMeL8ter!"
  db_subnet_group_name   = aws_db_subnet_group.rds[0].name
  vpc_security_group_ids = [aws_security_group.default.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  backup_retention_period = 0  # No backups for test

  tags = {
    Name         = "${var.project_name}-stopped-rds"
    TestScenario = "Stopped RDS Instance"
  }
}

# Stop RDS instance using null_resource (must wait 5 minutes after creation)
resource "null_resource" "stop_rds" {
  count = var.enable_batch_1 ? 1 : 0

  depends_on = [aws_db_instance.stopped]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting 5 minutes for RDS to become available..."
      sleep 300
      echo "Stopping RDS instance ${aws_db_instance.stopped[0].id}..."
      aws rds stop-db-instance --db-instance-identifier ${aws_db_instance.stopped[0].id} --region ${var.aws_region} || true
    EOT
  }
}

# 7. NAT Gateway - Zero traffic ($32/month)
resource "aws_nat_gateway" "zero_traffic" {
  count         = var.enable_batch_1 ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public_1.id

  tags = {
    Name         = "${var.project_name}-zero-traffic-nat"
    TestScenario = "NAT Gateway with Zero Traffic"
  }
}

resource "aws_eip" "nat" {
  count  = var.enable_batch_1 ? 1 : 0
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

# Data source for Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
