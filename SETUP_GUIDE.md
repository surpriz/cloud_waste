# CloudWaste - Setup Guide

Complete guide for setting up and using CloudWaste to detect orphaned AWS resources.

---

## 📋 Table of Contents

1. [Initial Setup](#initial-setup)
2. [AWS IAM Configuration](#aws-iam-configuration)
3. [Adding Cloud Accounts](#adding-cloud-accounts)
4. [Running Scans](#running-scans)
5. [Managing Resources](#managing-resources)
6. [API Examples](#api-examples)
7. [Automated Scans](#automated-scans)

---

## 🚀 Initial Setup

### 1. Verify Services Are Running

```bash
cd /Users/jerome_laval/Desktop/CloudWaste
docker-compose ps

# All services should show "Up":
# ✓ postgres          (port 5432)
# ✓ redis             (port 6379)
# ✓ backend           (port 8000)
# ✓ celery_worker
# ✓ celery_beat
# ✓ frontend          (port 3000)
```

### 2. Access the Application

**Frontend (Web Interface):**
- URL: http://localhost:3000
- Landing Page: Features overview
- Login: http://localhost:3000/auth/login
- Register: http://localhost:3000/auth/register

**Backend (API):**
- URL: http://localhost:8000
- API Docs: http://localhost:8000/api/docs (Swagger UI)
- Health Check: http://localhost:8000/api/v1/health

### 3. Create User Account

**Option A: Via Web Interface**
1. Navigate to http://localhost:3000/auth/register
2. Fill in registration form:
   - Email: `your-email@example.com`
   - Password: `SecurePass123!` (min 8 chars)
   - Full Name: `Your Name` (optional)
3. Click "Create account"
4. → Auto-redirect to dashboard

**Option B: Via API**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@cloudwaste.com",
    "password": "Demo123!",
    "full_name": "Demo User"
  }'
```

### 4. Login and Get JWT Token

**Via Web Interface:**
1. Go to http://localhost:3000/auth/login
2. Enter email and password
3. → Redirected to dashboard

**Via API:**
```bash
# Login to get access token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@cloudwaste.com&password=Demo123!"

# Response includes:
# {
#   "access_token": "eyJhbGc...",
#   "refresh_token": "eyJhbGc...",
#   "token_type": "bearer"
# }

# Save token for subsequent requests
export TOKEN="eyJhbGc..."
```

---

## 🔐 AWS IAM Configuration

### Step 1: Create IAM User

**IMPORTANT:** CloudWaste requires READ-ONLY permissions only. Never grant write/delete access.

1. Log into AWS Console
2. Navigate to **IAM** → **Users** → **Create user**
3. User name: `cloudwaste-scanner`
4. Select: ✓ **Programmatic access** (Access key ID + Secret)
5. Click **Next**

### Step 2: Attach Read-Only Policy

**Option A: Use AWS Managed Policies (Quick)**
Attach these managed policies:
- `ReadOnlyAccess`
- `ViewOnlyAccess`

**Option B: Custom Policy (Recommended - More Restrictive)**

Create a new policy with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWasteScannerReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "rds:Describe*",
        "s3:List*",
        "s3:GetBucket*",
        "elasticloadbalancing:Describe*",
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

Policy name: `CloudWasteScannerPolicy`

### Step 3: Retrieve Access Keys

1. Complete user creation
2. **Download** or **copy** the credentials:
   - **Access Key ID**: `AKIAIOSFODNN7EXAMPLE`
   - **Secret Access Key**: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
3. ⚠️ **IMPORTANT**: Store these securely - Secret Key is shown only once

### Step 4: Verify Permissions (Optional)

Test credentials using AWS CLI:

```bash
# Test basic authentication
aws sts get-caller-identity \
  --access-key-id AKIAIOSFODNN7EXAMPLE \
  --secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# Test EC2 describe permissions
aws ec2 describe-volumes \
  --access-key-id AKIAIOSFODNN7EXAMPLE \
  --secret-access-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
  --region us-east-1 \
  --max-results 5

# Should return data without errors
```

### Security Best Practices

✅ **Do:**
- Create dedicated IAM user for CloudWaste
- Use read-only permissions only
- Enable MFA on AWS root account
- Rotate access keys every 90 days
- Monitor IAM user activity in CloudTrail

❌ **Don't:**
- Never grant write/delete permissions
- Never share access keys
- Never commit keys to version control
- Never use root account credentials

---

## ☁️ Adding Cloud Accounts

### Via Web Interface

1. Navigate to **Dashboard** → **Cloud Accounts**
   - URL: http://localhost:3000/dashboard/accounts
2. Click **"Add Account"** button
3. Fill in the form:
   - **Account Name**: `Production AWS` (friendly name)
   - **AWS Account ID**: `123456789012` (12-digit ID)
   - **Access Key ID**: `AKIAIOSFODNN7EXAMPLE`
   - **Secret Access Key**: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
   - **Regions**: Select up to 3 regions (e.g., `us-east-1`, `eu-west-1`, `eu-central-1`)
   - **Description**: `Main production environment` (optional)
4. Click **"Add Account"**
5. → Automatic credential validation via AWS STS

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "account_name": "Production AWS",
    "account_identifier": "123456789012",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "regions": ["us-east-1", "eu-west-1", "eu-central-1"],
    "description": "Main production environment"
  }'
```

**Success Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "provider": "aws",
  "account_name": "Production AWS",
  "account_identifier": "123456789012",
  "regions": {
    "regions": ["us-east-1", "eu-west-1", "eu-central-1"]
  },
  "is_active": true,
  "last_scan_at": null,
  "created_at": "2025-10-02T10:30:00Z"
}
```

**Error Response (Invalid Credentials):**
```json
{
  "detail": "AWS credentials validation failed: Invalid AWS Access Key ID"
}
```

### Validate Account Credentials

```bash
# Manually validate credentials after adding
curl -X POST http://localhost:8000/api/v1/accounts/{account_id}/validate \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "valid": true,
  "account_info": {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/cloudwaste-scanner"
  }
}
```

---

## 🔍 Running Scans

### Manual Scan via Web Interface

1. Navigate to **Dashboard** → **Scans**
   - URL: http://localhost:3000/dashboard/scans
2. Click **"Start New Scan"**
3. Select cloud account from dropdown
4. Click **"Start Scan"**
5. → Scan queued to Celery worker
6. Monitor progress in real-time (status updates)

### Manual Scan via API

```bash
# Start a scan
curl -X POST http://localhost:8000/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "550e8400-e29b-41d4-a716-446655440000",
    "scan_type": "manual"
  }'

# Immediate response (scan queued):
{
  "id": "650e8400-e29b-41d4-a716-446655440002",
  "cloud_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "scan_type": "manual",
  "total_resources_scanned": 0,
  "orphan_resources_found": 0,
  "estimated_monthly_waste": 0.0,
  "created_at": "2025-10-02T10:35:00Z"
}
```

### Check Scan Status

```bash
# Poll scan status
curl http://localhost:8000/api/v1/scans/650e8400-e29b-41d4-a716-446655440002 \
  -H "Authorization: Bearer $TOKEN"

# Status values:
# - "pending": Queued, waiting for worker
# - "in_progress": Scan is running
# - "completed": Scan finished successfully
# - "failed": Scan failed (check error_message)
```

### View Scan Results

```bash
# Get scan details with all orphan resources
curl http://localhost:8000/api/v1/scans/650e8400-e29b-41d4-a716-446655440002 \
  -H "Authorization: Bearer $TOKEN"

# Response when completed:
{
  "id": "650e8400-e29b-41d4-a716-446655440002",
  "status": "completed",
  "total_resources_scanned": 147,
  "orphan_resources_found": 23,
  "estimated_monthly_waste": 342.50,
  "started_at": "2025-10-02T10:35:10Z",
  "completed_at": "2025-10-02T10:38:45Z",
  "orphan_resources": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440003",
      "resource_type": "ebs_volume",
      "resource_id": "vol-0abc123def456",
      "resource_name": "old-backup-volume",
      "region": "us-east-1",
      "estimated_monthly_cost": 80.0,
      "status": "active",
      "resource_metadata": {
        "size_gb": 800,
        "volume_type": "gp2",
        "created_at": "2024-01-15T10:30:00Z",
        "availability_zone": "us-east-1a",
        "encrypted": false
      }
    }
    // ... 22 more resources
  ]
}
```

---

## 🗂️ Managing Resources

### View All Orphan Resources

**Via Web Interface:**
- Navigate to **Dashboard** → **Resources**
- URL: http://localhost:3000/dashboard/resources
- Use filters: Type, Region, Status, Account

**Via API:**
```bash
# List all resources
curl http://localhost:8000/api/v1/resources/ \
  -H "Authorization: Bearer $TOKEN"

# Filter by resource type
curl "http://localhost:8000/api/v1/resources/?resource_type=ebs_volume" \
  -H "Authorization: Bearer $TOKEN"

# Filter by region
curl "http://localhost:8000/api/v1/resources/?region=us-east-1" \
  -H "Authorization: Bearer $TOKEN"

# Filter by status
curl "http://localhost:8000/api/v1/resources/?status=active" \
  -H "Authorization: Bearer $TOKEN"

# Combine filters
curl "http://localhost:8000/api/v1/resources/?resource_type=elastic_ip&region=eu-west-1&status=active" \
  -H "Authorization: Bearer $TOKEN"
```

### View Top Cost Resources

```bash
# Get top 10 most expensive resources
curl "http://localhost:8000/api/v1/resources/top-cost?limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Get top 20
curl "http://localhost:8000/api/v1/resources/top-cost?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Mark Resource as Ignored

```bash
# Ignore a false positive
curl -X PATCH http://localhost:8000/api/v1/resources/750e8400-e29b-41d4-a716-446655440003 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ignored"
  }'
```

### Mark Resource for Deletion

```bash
# Mark for manual deletion
curl -X PATCH http://localhost:8000/api/v1/resources/750e8400-e29b-41d4-a716-446655440003 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "marked_for_deletion"
  }'
```

⚠️ **IMPORTANT:** CloudWaste does NOT delete resources automatically. You must delete them manually via AWS Console.

### View Statistics

```bash
# Global statistics
curl http://localhost:8000/api/v1/resources/stats \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "total_resources": 23,
  "by_type": {
    "ebs_volume": 8,
    "elastic_ip": 5,
    "ebs_snapshot": 6,
    "nat_gateway": 2,
    "load_balancer": 2
  },
  "by_region": {
    "us-east-1": 12,
    "eu-west-1": 8,
    "eu-central-1": 3
  },
  "by_status": {
    "active": 18,
    "ignored": 3,
    "marked_for_deletion": 2
  },
  "total_monthly_cost": 342.50,
  "total_annual_cost": 4110.00
}

# Stats for specific account
curl "http://localhost:8000/api/v1/resources/stats?cloud_account_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer $TOKEN"

# Scan summary statistics
curl http://localhost:8000/api/v1/scans/summary \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "total_scans": 5,
  "completed_scans": 4,
  "failed_scans": 1,
  "total_orphan_resources": 23,
  "total_monthly_waste": 342.50,
  "last_scan_at": "2025-10-02T10:38:45Z"
}
```

---

## 📡 API Examples

### Complete Workflow Script

Save as `cloudwaste-test.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== CloudWaste API Workflow ===${NC}\n"

# 1. Register user
echo -e "${GREEN}1. Creating user...${NC}"
curl -s -X POST $API_URL/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@cloudwaste.com",
    "password": "Demo123!",
    "full_name": "Demo User"
  }' | jq '.'

# 2. Login
echo -e "\n${GREEN}2. Logging in...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST $API_URL/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@cloudwaste.com&password=Demo123!")

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Token obtained: ${TOKEN:0:20}..."

# 3. Add AWS account
echo -e "\n${GREEN}3. Adding AWS account...${NC}"
ACCOUNT_RESPONSE=$(curl -s -X POST $API_URL/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "account_name": "Demo AWS Account",
    "account_identifier": "123456789012",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "regions": ["us-east-1", "eu-west-1"]
  }')

ACCOUNT_ID=$(echo $ACCOUNT_RESPONSE | jq -r '.id')
echo $ACCOUNT_RESPONSE | jq '.'

# 4. Start scan
echo -e "\n${GREEN}4. Starting scan...${NC}"
SCAN_RESPONSE=$(curl -s -X POST $API_URL/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"cloud_account_id\":\"$ACCOUNT_ID\",\"scan_type\":\"manual\"}")

SCAN_ID=$(echo $SCAN_RESPONSE | jq -r '.id')
echo $SCAN_RESPONSE | jq '.'

# 5. Poll scan status
echo -e "\n${GREEN}5. Waiting for scan completion...${NC}"
while true; do
  SCAN_STATUS=$(curl -s $API_URL/api/v1/scans/$SCAN_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')

  echo "  Status: $SCAN_STATUS"

  if [ "$SCAN_STATUS" == "completed" ] || [ "$SCAN_STATUS" == "failed" ]; then
    break
  fi

  sleep 5
done

# 6. Get results
echo -e "\n${GREEN}6. Fetching scan results...${NC}"
curl -s $API_URL/api/v1/scans/$SCAN_ID \
  -H "Authorization: Bearer $TOKEN" | jq '{
    orphan_resources_found,
    estimated_monthly_waste,
    estimated_annual_savings: (.estimated_monthly_waste * 12)
  }'

# 7. List resources by type
echo -e "\n${GREEN}7. Resources breakdown by type...${NC}"
curl -s "$API_URL/api/v1/resources/?cloud_account_id=$ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '[.[].resource_type] | group_by(.) | map({type: .[0], count: length})'

# 8. Get statistics
echo -e "\n${GREEN}8. Global statistics...${NC}"
curl -s $API_URL/api/v1/resources/stats \
  -H "Authorization: Bearer $TOKEN" | jq '{
    total_resources,
    total_monthly_cost,
    total_annual_cost,
    by_type
  }'

echo -e "\n${BLUE}=== Workflow completed! ===${NC}"
```

Run the script:
```bash
chmod +x cloudwaste-test.sh
./cloudwaste-test.sh
```

---

## ⏰ Automated Scans

### Scheduled Scans with Celery Beat

CloudWaste automatically scans all active accounts **daily at 2:00 AM UTC**.

### View Scheduled Tasks

```bash
# Check Celery Beat logs
docker-compose logs -f celery_beat

# Should show:
# [2025-10-02 02:00:00,123: INFO] Scheduler: Sending due task daily-scan-all-accounts
```

### Modify Schedule

Edit `backend/app/workers/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    "daily-scan-all-accounts": {
        "task": "app.workers.tasks.scheduled_scan_all_accounts",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM UTC

        # Examples of other schedules:
        # crontab(hour=8, minute=30)           # 8:30 AM daily
        # crontab(day_of_week=1, hour=9)       # Monday 9:00 AM
        # crontab(hour='*/6')                  # Every 6 hours
        # crontab(day_of_month=1, hour=3)      # 1st of month 3:00 AM
    },
}
```

Restart Celery Beat:
```bash
docker-compose restart celery_beat
```

### Monitor Scan Jobs

```bash
# View active Celery tasks
docker-compose exec celery_worker celery -A app.workers.celery_app inspect active

# View queued tasks
docker-compose exec celery_worker celery -A app.workers.celery_app inspect scheduled

# View worker stats
docker-compose exec celery_worker celery -A app.workers.celery_app inspect stats
```

---

## 📊 Resource Types Detected

CloudWaste detects 7 types of orphaned AWS resources:

### 1. EBS Volumes (Unattached)
- **Criteria:** `status = 'available'` (not attached to any instance)
- **Cost:** Variable by type (gp2: $0.10/GB, gp3: $0.08/GB, io1: $0.125/GB)
- **Metadata:** Size, type, availability zone, encryption status
- **Action:** Delete via AWS Console or attach to instance

### 2. Elastic IPs (Unassigned)
- **Criteria:** No `AssociationId` (not attached to instance/ENI)
- **Cost:** $3.60/month per IP
- **Metadata:** Public IP, domain
- **Action:** Release IP via AWS Console

### 3. EBS Snapshots (Orphaned)
- **Criteria:** Snapshot > 90 days AND source volume deleted
- **Cost:** $0.05/GB/month
- **Metadata:** Size, source volume ID, description
- **Action:** Delete snapshot via AWS Console

### 4. EC2 Instances (Stopped)
- **Criteria:** State = 'stopped' for > 30 days
- **Cost:** Based on attached EBS volumes (compute = $0 when stopped)
- **Metadata:** Instance type, stopped date, days stopped
- **Action:** Terminate instance or start it

### 5. Load Balancers (No Backends)
- **Criteria:** Zero healthy targets
- **Cost:** ALB/NLB: $22/month, Classic LB: $18/month
- **Metadata:** Type, DNS name, scheme
- **Action:** Delete load balancer via AWS Console

### 6. RDS Instances (Stopped)
- **Criteria:** Status = 'stopped'
- **Note:** AWS auto-restarts after 7 days
- **Cost:** Storage only (~$0.115/GB for gp2, compute = $0)
- **Metadata:** Instance class, engine, version, storage
- **Action:** Delete RDS instance (create final snapshot)

### 7. NAT Gateways (Unused)
- **Criteria:** `BytesOutToDestination < 1MB` over 30 days (CloudWatch metrics)
- **Cost:** $32.40/month base cost
- **Metadata:** VPC, subnet, bytes transferred
- **Action:** Delete NAT Gateway via AWS Console

---

## 💡 Best Practices

### Security
1. **Rotate AWS credentials every 90 days**
2. **Monitor CloudWaste access logs**
3. **Use separate AWS accounts for production/staging**
4. **Enable CloudTrail on AWS to track API calls**

### Cost Optimization
1. **Run scans weekly for production accounts**
2. **Review and action resources marked as high-cost first**
3. **Set up Slack/email notifications for new findings** (coming soon)
4. **Export reports for stakeholder reviews**

### Workflow
1. **Verify resources before deletion** - Always check AWS Console
2. **Use "ignore" status for intentional orphans** (e.g., backups)
3. **Mark for deletion, then batch delete monthly**
4. **Document reasons for ignoring resources** (use description field)

---

**Version:** MVP v1.0
**Last Updated:** October 2, 2025
**Status:** ✅ Production Ready
