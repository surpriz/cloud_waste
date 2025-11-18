# VPC Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = [aws_subnet.public_1.id, aws_subnet.public_2.id]
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}

output "security_group_id" {
  description = "Default security group ID"
  value       = aws_security_group.default.id
}

# Batch 1 Outputs
output "batch_1_resources" {
  description = "Batch 1 resource IDs and ARNs"
  value = var.enable_batch_1 ? {
    ebs_volume_id       = try(aws_ebs_volume.unattached[0].id, null)
    elastic_ip          = try(aws_eip.unassociated[0].public_ip, null)
    snapshot_id         = try(aws_ebs_snapshot.old[0].id, null)
    ec2_instance_id     = try(aws_instance.stopped[0].id, null)
    alb_arn             = try(aws_lb.zero_traffic[0].arn, null)
    rds_instance_id     = try(aws_db_instance.stopped[0].id, null)
    nat_gateway_id      = try(aws_nat_gateway.zero_traffic[0].id, null)
  } : null
}

# Batch 2 Outputs
output "batch_2_resources" {
  description = "Batch 2 resource IDs and ARNs"
  value = var.enable_batch_2 ? {
    # Will be populated when batch2.tf is created
  } : null
}

# Cost Estimation
output "estimated_monthly_cost" {
  description = "Estimated monthly cost in USD"
  value = {
    batch_1 = var.enable_batch_1 ? 20 : 0
    batch_2 = var.enable_batch_2 ? 478 : 0
    batch_3 = var.enable_batch_3 ? 378 : 0
    batch_4 = var.enable_batch_4 ? 243 : 0
    batch_5 = var.enable_batch_5 ? 700 : 0
    total   = (var.enable_batch_1 ? 20 : 0) + (var.enable_batch_2 ? 478 : 0) + (var.enable_batch_3 ? 378 : 0) + (var.enable_batch_4 ? 243 : 0) + (var.enable_batch_5 ? 700 : 0)
  }
}
