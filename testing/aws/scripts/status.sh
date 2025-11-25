#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (works from anywhere)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "CutCosts AWS Resources Status"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Expected location: $PROJECT_DIR/.env"
    exit 1
fi

# Source .env
source "$PROJECT_DIR/.env"

# Change to terraform directory
cd "$PROJECT_DIR/terraform"

# Check if terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo -e "${YELLOW}⚠ No terraform state found${NC}"
    echo "No resources have been created yet"
    echo "Run: ./scripts/create.sh"
    exit 0
fi

# Get terraform outputs
echo "Fetching resource information..."
echo ""

# VPC Info
VPC_ID=$(terraform output -raw vpc_id 2>/dev/null || echo "N/A")
echo -e "${BLUE}VPC:${NC}"
echo "  VPC ID: $VPC_ID"
echo ""

# Batch 1 Resources
if [ "${TF_VAR_enable_batch_1}" = "true" ]; then
    echo -e "${BLUE}Batch 1 Resources (Core):${NC}"

    # EBS Volume
    EBS_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"ebs_volume_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EBS_ID" ] && [ "$EBS_ID" != "null" ]; then
        EBS_STATE=$(aws ec2 describe-volumes --volume-ids $EBS_ID --query 'Volumes[0].State' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        EBS_SIZE=$(aws ec2 describe-volumes --volume-ids $EBS_ID --query 'Volumes[0].Size' --output text --region $AWS_REGION 2>/dev/null || echo "?")
        echo "  ✓ EBS Volume: $EBS_ID - ${EBS_SIZE}GB - $EBS_STATE (~\$0.10/month)"
    fi

    # Elastic IP
    EIP=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"elastic_ip":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EIP" ] && [ "$EIP" != "null" ]; then
        echo "  ✓ Elastic IP: $EIP - Unassociated (~\$3.60/month)"
    fi

    # Snapshot
    SNAP_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"snapshot_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$SNAP_ID" ] && [ "$SNAP_ID" != "null" ]; then
        echo "  ✓ Snapshot: $SNAP_ID (~\$0.05/month)"
    fi

    # EC2 Instance
    EC2_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"ec2_instance_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EC2_ID" ] && [ "$EC2_ID" != "null" ]; then
        EC2_STATE=$(aws ec2 describe-instances --instance-ids $EC2_ID --query 'Reservations[0].Instances[0].State.Name' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        echo "  ✓ EC2 Instance: $EC2_ID - $EC2_STATE (~\$0/month when stopped)"
    fi

    # ALB
    ALB_ARN=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"alb_arn":"[^"]*' | cut -d'"' -f4)
    if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "null" ]; then
        ALB_NAME=$(echo $ALB_ARN | awk -F'/' '{print $3}')
        echo "  ✓ Load Balancer: $ALB_NAME (~\$16/month)"
    fi

    # RDS
    RDS_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"rds_instance_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$RDS_ID" ] && [ "$RDS_ID" != "null" ]; then
        RDS_STATE=$(aws rds describe-db-instances --db-instance-identifier $RDS_ID --query 'DBInstances[0].DBInstanceStatus' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        echo "  ✓ RDS Instance: $RDS_ID - $RDS_STATE (~\$0/month when stopped)"
    fi

    # NAT Gateway
    NAT_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"nat_gateway_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$NAT_ID" ] && [ "$NAT_ID" != "null" ]; then
        echo "  ✓ NAT Gateway: $NAT_ID (~\$32/month)"
    fi

    echo ""
fi

# Batch 3 Resources
if [ "${TF_VAR_enable_batch_3}" = "true" ]; then
    echo -e "${BLUE}Batch 3 Resources (Advanced Services):${NC}"

    # ElastiCache
    ELASTICACHE_ID=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"elasticache_cluster_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$ELASTICACHE_ID" ] && [ "$ELASTICACHE_ID" != "null" ]; then
        echo "  ✓ ElastiCache: $ELASTICACHE_ID (~\$15/month)"
    fi

    # Kinesis Stream
    KINESIS_NAME=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"kinesis_stream_name":"[^"]*' | cut -d'"' -f4)
    if [ -n "$KINESIS_NAME" ] && [ "$KINESIS_NAME" != "null" ]; then
        echo "  ✓ Kinesis Stream: $KINESIS_NAME (~\$11/month)"
    fi

    # EFS File System
    EFS_ID=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"efs_file_system_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EFS_ID" ] && [ "$EFS_ID" != "null" ]; then
        echo "  ✓ EFS File System: $EFS_ID (~\$0.50/month)"
    fi

    # OpenSearch Domain
    OPENSEARCH_ENDPOINT=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"opensearch_domain_endpoint":"[^"]*' | cut -d'"' -f4)
    if [ -n "$OPENSEARCH_ENDPOINT" ] && [ "$OPENSEARCH_ENDPOINT" != "null" ]; then
        OPENSEARCH_DOMAIN=$(echo $OPENSEARCH_ENDPOINT | cut -d'.' -f1 | sed 's/vpc-//')
        echo "  ✓ OpenSearch Domain: $OPENSEARCH_DOMAIN (~\$35/month)"
    fi

    # API Gateway
    API_ID=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"api_gateway_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$API_ID" ] && [ "$API_ID" != "null" ]; then
        echo "  ✓ API Gateway: $API_ID (~\$0/month)"
    fi

    # CloudWatch Log Group
    LOG_GROUP=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"cloudwatch_log_group_name":"[^"]*' | cut -d'"' -f4)
    if [ -n "$LOG_GROUP" ] && [ "$LOG_GROUP" != "null" ]; then
        echo "  ✓ CloudWatch Log Group: $LOG_GROUP (~\$0.50/month)"
    fi

    # ECS Cluster
    ECS_NAME=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"ecs_cluster_name":"[^"]*' | cut -d'"' -f4)
    if [ -n "$ECS_NAME" ] && [ "$ECS_NAME" != "null" ]; then
        echo "  ✓ ECS Cluster: $ECS_NAME (~\$0/month)"
    fi

    # CloudFront Distribution
    CF_ID=$(terraform output -json batch_3_resources 2>/dev/null | grep -o '"cloudfront_distribution_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$CF_ID" ] && [ "$CF_ID" != "null" ]; then
        echo "  ✓ CloudFront Distribution: $CF_ID (~\$0/month)"
    fi

    echo ""
fi

# Batch 4 Resources
if [ "${TF_VAR_enable_batch_4}" = "true" ]; then
    echo -e "${BLUE}Batch 4 Resources (Advanced Services):${NC}"

    # VPC Endpoint
    VPC_ENDPOINT_ID=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"vpc_endpoint_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$VPC_ENDPOINT_ID" ] && [ "$VPC_ENDPOINT_ID" != "null" ]; then
        echo "  ✓ VPC Endpoint: $VPC_ENDPOINT_ID (~\$7.20/month)"
    fi

    # Neptune Cluster
    NEPTUNE_ENDPOINT=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"neptune_cluster_endpoint":"[^"]*' | cut -d'"' -f4)
    if [ -n "$NEPTUNE_ENDPOINT" ] && [ "$NEPTUNE_ENDPOINT" != "null" ]; then
        NEPTUNE_CLUSTER=$(echo $NEPTUNE_ENDPOINT | cut -d'.' -f1)
        echo "  ✓ Neptune Cluster: $NEPTUNE_CLUSTER (~\$80/month)"
    fi

    # MSK Cluster
    MSK_ARN=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"msk_cluster_arn":"[^"]*' | cut -d'"' -f4)
    if [ -n "$MSK_ARN" ] && [ "$MSK_ARN" != "null" ]; then
        MSK_NAME=$(echo $MSK_ARN | awk -F'/' '{print $2}')
        echo "  ✓ MSK Cluster: $MSK_NAME (~\$70/month)"
    fi

    # Redshift Cluster
    REDSHIFT_ID=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"redshift_cluster_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$REDSHIFT_ID" ] && [ "$REDSHIFT_ID" != "null" ]; then
        echo "  ✓ Redshift Cluster: $REDSHIFT_ID (~\$793/month)"
    fi

    # VPN Connection
    VPN_ID=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"vpn_connection_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$VPN_ID" ] && [ "$VPN_ID" != "null" ]; then
        echo "  ✓ VPN Connection: $VPN_ID (~\$36/month)"
    fi

    # Transit Gateway
    TGW_ID=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"transit_gateway_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$TGW_ID" ] && [ "$TGW_ID" != "null" ]; then
        echo "  ✓ Transit Gateway: $TGW_ID (~\$36/month attachment)"
    fi

    # Application Load Balancer
    ALB_DNS=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"alb_dns_name":"[^"]*' | cut -d'"' -f4)
    if [ -n "$ALB_DNS" ] && [ "$ALB_DNS" != "null" ]; then
        ALB_NAME=$(echo $ALB_DNS | cut -d'-' -f1-3)
        echo "  ✓ Load Balancer: $ALB_NAME (~\$27/month)"
    fi

    # Global Accelerator
    GA_DNS=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"global_accelerator_dns_name":"[^"]*' | cut -d'"' -f4)
    if [ -n "$GA_DNS" ] && [ "$GA_DNS" != "null" ]; then
        echo "  ✓ Global Accelerator: $GA_DNS (~\$18/month)"
    fi

    # DocumentDB Cluster
    DOCDB_ENDPOINT=$(terraform output -json batch_4_resources 2>/dev/null | grep -o '"documentdb_cluster_endpoint":"[^"]*' | cut -d'"' -f4)
    if [ -n "$DOCDB_ENDPOINT" ] && [ "$DOCDB_ENDPOINT" != "null" ]; then
        DOCDB_CLUSTER=$(echo $DOCDB_ENDPOINT | cut -d'.' -f1)
        echo "  ✓ DocumentDB Cluster: $DOCDB_CLUSTER (~\$80/month)"
    fi

    echo ""
fi

# Calculate total cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 20))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 478))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 378))
[ "${TF_VAR_enable_batch_4}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 1166))
[ "${TF_VAR_enable_batch_5}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 700))

echo -e "${YELLOW}=========================================="
echo "Estimated Total Cost: ~\$${TOTAL_COST}/month"
echo "==========================================${NC}"
echo ""
echo "Commands:"
echo "  View detailed costs: terraform -chdir=$PROJECT_DIR/terraform show"
echo "  Destroy resources: $PROJECT_DIR/scripts/destroy.sh"
echo ""
