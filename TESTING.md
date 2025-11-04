# CloudWaste - Testing Guide

This guide explains how to test CloudWaste features, especially resource detection and the dynamic pricing system.

## Table of Contents

1. [Testing Detection Rules Immediately](#testing-detection-rules-immediately)
2. [Testing Dynamic Pricing System](#testing-dynamic-pricing-system)
3. [Testing Detection Scenarios](#testing-detection-scenarios)
4. [Best Practices for Development Testing](#best-practices-for-development-testing)
5. [Automated Testing](#automated-testing)

---

## Testing Detection Rules Immediately

### Problem
By default, CloudWaste ignores resources created within the last 3 days (`min_age_days: 3`) to avoid false positives during active deployments. This makes it difficult to test detection scenarios immediately after creating test resources.

### Solution: Test Detection Endpoint

A special test endpoint allows you to override detection rules in **DEBUG mode only**.

#### Prerequisites

1. Ensure `DEBUG=True` in backend `.env`:
```bash
DEBUG=True
```

2. Restart backend:
```bash
cd backend
uvicorn app.main:app --reload
```

#### Test Elastic IP Detection (Immediate)

**1. Create test Elastic IP on AWS:**
```bash
aws ec2 allocate-address --region us-east-1 --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=test-unassociated-eip}]'
```

**2. Call test detection endpoint:**

```bash
curl -X POST "http://localhost:8000/api/v1/test/detect-resources" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "account_id": "YOUR_CLOUD_ACCOUNT_UUID",
    "region": "us-east-1",
    "resource_types": ["elastic_ip"],
    "overrides": {
      "elastic_ip": {
        "min_age_days": 0,
        "confidence_threshold_days": 0
      }
    }
  }'
```

**3. Expected Response:**

```json
{
  "account_id": "uuid",
  "region": "us-east-1",
  "detection_rules_applied": {
    "elastic_ip": {
      "enabled": true,
      "min_age_days": 0,
      "confidence_threshold_days": 0
    }
  },
  "results": {
    "elastic_ip": [
      {
        "resource_id": "eipalloc-xxx",
        "resource_name": "test-unassociated-eip",
        "estimated_monthly_cost": 3.6,
        "confidence_level": "critical",
        "detection_reason": "Unassociated Elastic IP (age: 0 days)"
      }
    ]
  }
}
```

#### Test Other Resource Types

**EBS Volumes (unattached):**
```json
{
  "account_id": "uuid",
  "region": "us-east-1",
  "resource_types": ["ebs_volume"],
  "overrides": {
    "ebs_volume": {
      "min_age_days": 0,
      "min_idle_days": 0
    }
  }
}
```

**Load Balancers (no targets):**
```json
{
  "account_id": "uuid",
  "region": "us-east-1",
  "resource_types": ["load_balancer"],
  "overrides": {
    "load_balancer": {
      "min_age_days": 0,
      "min_no_targets_days": 0
    }
  }
}
```

**NAT Gateways (no traffic):**
```json
{
  "account_id": "uuid",
  "region": "us-east-1",
  "resource_types": ["nat_gateway"],
  "overrides": {
    "nat_gateway": {
      "min_age_days": 0,
      "min_zero_bytes_days": 0
    }
  }
}
```

#### Security Warning

⚠️ **IMPORTANT**: The test detection endpoint is **only available when `DEBUG=True`**. Never enable DEBUG mode in production.

---

## Testing Dynamic Pricing System

### Using Admin Dashboard (Recommended)

**1. Access Pricing Dashboard:**
- Navigate to: `http://localhost:3000/dashboard/admin/pricing`
- Login with superuser account

**2. View Statistics:**

The dashboard displays 4 key metrics:

| Metric | Description | Healthy Threshold |
|--------|-------------|-------------------|
| **Total Cached Prices** | Number of prices in PostgreSQL cache | > 100 |
| **Last Refresh** | Time since last pricing update | < 24 hours |
| **Cache Hit Rate** | % of requests served from cache | > 90% |
| **API Success Rate** | % of AWS API calls succeeding | > 80% |

**3. Monitor System Status:**

- ✅ **Active**: API Success Rate ≥ 80%
- ⚠️ **Degraded**: API Success Rate < 80%

**4. Manual Refresh:**

Click "Refresh Prices Now" button to trigger immediate pricing update:
- Task is queued to Celery
- Dashboard polls task status every 1 second
- Alert shows results: "Updated: X, Failed: Y"

**5. Filter Pricing Data:**

Use dropdown filters to narrow down cached prices:
- **Provider**: AWS, Azure, GCP
- **Region**: us-east-1, us-west-2, eu-west-1, etc.

**6. Verify Price Sources:**

Check the "Source" column:
- 🟢 **API** (green badge): Price fetched from AWS Pricing API (fresh, accurate)
- 🟠 **Fallback** (orange badge): Hardcoded fallback price (stale, needs refresh)

### Current MVP Limitations

**⚠️ Important**: The dynamic pricing system is **partially implemented** in the current MVP:

| Resource Type | Pricing Source | Status |
|---------------|----------------|--------|
| **EBS Volume** | ✅ Dynamic (AWS Pricing API) | Fully implemented |
| **Elastic IP** | ✅ Dynamic (AWS Pricing API) | Fully implemented |
| **EBS Snapshot** | 🟠 Hardcoded fallback | Not implemented |
| **EC2 Instance** | 🟠 Hardcoded fallback | Not implemented |
| **NAT Gateway** | 🟠 Hardcoded fallback | Not implemented |
| **Load Balancer (ALB/NLB/CLB)** | 🟠 Hardcoded fallback | Not implemented |
| **RDS Instance** | 🟠 Hardcoded fallback | Not implemented |
| **EKS Cluster** | 🟠 Hardcoded fallback | Not implemented |
| **S3 Bucket** | 🟠 Hardcoded fallback | Not implemented |

**Why only 2/9 resources?**
- **Option A (minimal fix)**: We prioritized resource detection reliability over pricing accuracy
- **Hardcoded prices are safe**: They exist in `self.PRICING` dictionary (lines 28-100 of `aws.py`) and won't crash
- **Future work**: Migrate remaining 7 resources to dynamic pricing (estimated 2-3 hours)

**Fallback Pricing Values** (used for 7 MVP resources):
```python
FALLBACK_PRICING = {
    "aws": {
        "ebs_gp3": 0.08,        # $/GB/month
        "ebs_gp2": 0.10,
        "elastic_ip": 3.60,      # $/month (matches dynamic pricing)
        "alb": 16.20,            # Application Load Balancer $/month
        "nlb": 16.20,            # Network Load Balancer $/month
        "clb": 18.00,            # Classic Load Balancer $/month
        "snapshot_per_gb": 0.05, # EBS Snapshot $/GB/month
        # ... more services
    }
}
```

**For Production Readiness:**
- ✅ All 9 MVP resource types are **detectable** (no crashes)
- ⚠️ Only 2/9 use real-time AWS pricing
- 🔄 Consider migrating remaining resources if pricing accuracy is critical

### Using API Endpoints Directly

#### Get Pricing Statistics

```bash
curl -X GET "http://localhost:8000/api/v1/admin/pricing/stats" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "total_cached_prices": 245,
  "expired_prices": 12,
  "api_sourced_prices": 220,
  "fallback_sourced_prices": 25,
  "last_refresh_at": "2025-11-01T02:00:00Z",
  "cache_hit_rate": 94.5,
  "api_success_rate": 89.8
}
```

#### List Cached Prices

**All cached prices:**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/pricing/cache?skip=0&limit=100" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Filter by provider:**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/pricing/cache?provider=aws&limit=100" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Filter by region:**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/pricing/cache?region=us-east-1&limit=100" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "provider": "aws",
    "service": "ElasticIP",
    "region": "us-east-1",
    "price_per_unit": 0.005,
    "unit": "hour",
    "currency": "USD",
    "source": "api",
    "last_updated": "2025-11-01T02:00:00Z",
    "expires_at": "2025-11-02T02:00:00Z",
    "is_expired": false
  }
]
```

#### Trigger Manual Refresh

```bash
curl -X POST "http://localhost:8000/api/v1/admin/pricing/refresh" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "status": "pending",
  "task_id": "1234-5678-abcd-efgh",
  "message": "Pricing refresh task queued"
}
```

#### Check Refresh Task Status

```bash
curl -X GET "http://localhost:8000/api/v1/admin/pricing/refresh/1234-5678-abcd-efgh" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response (pending):**
```json
{
  "status": "pending",
  "task_id": "1234-5678-abcd-efgh",
  "message": "Task is queued"
}
```

**Response (success):**
```json
{
  "status": "success",
  "task_id": "1234-5678-abcd-efgh",
  "message": "Pricing refresh completed",
  "updated_count": 245,
  "failed_count": 3
}
```

**Response (failure):**
```json
{
  "status": "error",
  "task_id": "1234-5678-abcd-efgh",
  "message": "AWS API rate limit exceeded",
  "updated_count": null,
  "failed_count": null
}
```

---

## Testing Detection Scenarios

### Manual Testing Checklist

Use this checklist when implementing new detection scenarios:

#### 1. AWS Elastic IP (7 scenarios)

- [ ] **Scenario 1**: Create unassociated EIP → Verify detection
- [ ] **Scenario 2**: Create EIP, associate to instance → Verify NOT detected
- [ ] **Scenario 3**: Create EIP 7+ days ago → Verify "critical" confidence
- [ ] **Scenario 4**: Create EIP with tag `cloudwaste:ignore=true` → Verify ignored
- [ ] **Scenario 5**: User ignores EIP in dashboard → Verify status updated to "ignored"
- [ ] **Scenario 6**: Cost calculation: Verify $3.60/month (0.005/hour * 720 hours)
- [ ] **Scenario 7**: Multi-region: Create EIP in us-east-1 and eu-west-1 → Verify both detected

#### 2. AWS EBS Volumes (4 scenarios)

- [ ] **Scenario 1**: Create unattached volume → Verify detection
- [ ] **Scenario 2**: Create attached volume → Verify NOT detected
- [ ] **Scenario 3**: Idle volume (low I/O for 14+ days) → Verify detection via CloudWatch
- [ ] **Scenario 4**: Cost varies by size/type: gp3 100GB ≈ $8/month

#### 3. AWS Load Balancers (7 scenarios)

- [ ] **Scenario 1**: ALB with no target groups → Detect
- [ ] **Scenario 2**: ALB with no healthy targets → Detect
- [ ] **Scenario 3**: ALB with no listeners → Detect
- [ ] **Scenario 4**: ALB never used (0 requests CloudWatch) → Detect
- [ ] **Scenario 5**: NLB variants (test all 4 LB types: ALB, NLB, CLB, GWLB)
- [ ] **Scenario 6**: Cost: ALB ≈ $16-$22/month
- [ ] **Scenario 7**: Multi-region detection

#### 4. Azure Managed Disks (3 scenarios)

- [ ] **Scenario 1**: Create unattached Standard HDD → Detect ($2-$5/month)
- [ ] **Scenario 2**: Create unattached Premium SSD → Detect ($10-$20/month)
- [ ] **Scenario 3**: Attached disk → NOT detected

### Automated Test Creation Script

```bash
#!/bin/bash
# create-test-resources.sh
# Creates test resources on AWS for detection testing

set -e

REGION="us-east-1"
TAG_NAME="cloudwaste-test"
TAG_VALUE="$(date +%Y%m%d-%H%M%S)"

echo "🔧 Creating test resources in $REGION..."

# 1. Elastic IP (unassociated)
echo "Creating Elastic IP..."
EIP_ALLOC_ID=$(aws ec2 allocate-address \
  --region $REGION \
  --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$TAG_NAME-eip},{Key=TestSession,Value=$TAG_VALUE}]" \
  --query 'AllocationId' \
  --output text)
echo "✅ Created EIP: $EIP_ALLOC_ID"

# 2. EBS Volume (unattached)
echo "Creating EBS Volume..."
VOLUME_ID=$(aws ec2 create-volume \
  --region $REGION \
  --availability-zone ${REGION}a \
  --size 10 \
  --volume-type gp3 \
  --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=$TAG_NAME-volume},{Key=TestSession,Value=$TAG_VALUE}]" \
  --query 'VolumeId' \
  --output text)
echo "✅ Created Volume: $VOLUME_ID"

# 3. Load Balancer (no targets)
echo "Creating Application Load Balancer..."
# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs --region $REGION --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text)
# Get subnets
SUBNET_IDS=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[0:2].SubnetId' --output text | tr '\t' ' ')

ALB_ARN=$(aws elbv2 create-load-balancer \
  --region $REGION \
  --name ${TAG_NAME}-alb-$(date +%s) \
  --subnets $SUBNET_IDS \
  --tags "Key=Name,Value=$TAG_NAME-alb" "Key=TestSession,Value=$TAG_VALUE" \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)
echo "✅ Created ALB: $ALB_ARN"

echo ""
echo "📋 Test Resources Created:"
echo "  - Elastic IP: $EIP_ALLOC_ID"
echo "  - EBS Volume: $VOLUME_ID"
echo "  - Load Balancer: $ALB_ARN"
echo "  - Tag: TestSession=$TAG_VALUE"
echo ""
echo "⏱️  Wait 3 days for normal detection OR use test endpoint with min_age_days=0"
echo ""
echo "🧹 Cleanup command:"
echo "  ./cleanup-test-resources.sh $TAG_VALUE"
```

### Cleanup Script

```bash
#!/bin/bash
# cleanup-test-resources.sh
# Cleans up test resources created by create-test-resources.sh

set -e

REGION="us-east-1"
TAG_VALUE=$1

if [ -z "$TAG_VALUE" ]; then
  echo "Usage: ./cleanup-test-resources.sh <TestSession value>"
  exit 1
fi

echo "🧹 Cleaning up test resources with TestSession=$TAG_VALUE..."

# 1. Release Elastic IPs
echo "Releasing Elastic IPs..."
aws ec2 describe-addresses --region $REGION \
  --filters "Name=tag:TestSession,Values=$TAG_VALUE" \
  --query 'Addresses[].AllocationId' \
  --output text | xargs -I {} aws ec2 release-address --region $REGION --allocation-id {}
echo "✅ Released Elastic IPs"

# 2. Delete EBS Volumes
echo "Deleting EBS Volumes..."
aws ec2 describe-volumes --region $REGION \
  --filters "Name=tag:TestSession,Values=$TAG_VALUE" \
  --query 'Volumes[].VolumeId' \
  --output text | xargs -I {} aws ec2 delete-volume --region $REGION --volume-id {}
echo "✅ Deleted EBS Volumes"

# 3. Delete Load Balancers
echo "Deleting Load Balancers..."
aws elbv2 describe-load-balancers --region $REGION \
  --query "LoadBalancers[?Tags[?Key=='TestSession' && Value=='$TAG_VALUE']].LoadBalancerArn" \
  --output text | xargs -I {} aws elbv2 delete-load-balancer --load-balancer-arn {}
echo "✅ Deleted Load Balancers"

echo "✅ Cleanup complete!"
```

---

## Best Practices for Development Testing

### 1. Use Test Endpoint During Development

**✅ DO:**
- Use `POST /api/v1/test/detect-resources` with `min_age_days=0` during development
- Test immediately after creating resources
- Verify detection logic before waiting 3 days

**❌ DON'T:**
- Leave `DEBUG=True` in production
- Skip testing detection rules before deploying
- Assume detection works without verifying

### 2. Test Pricing Before Full Scans

**✅ DO:**
- Verify pricing cache has recent data (`/admin/pricing/stats`)
- Trigger manual refresh if `api_success_rate < 80%`
- Check for fallback prices (orange badges) and refresh if found

**❌ DON'T:**
- Run full scans with stale pricing data
- Ignore pricing API errors
- Rely only on hardcoded fallback prices

### 3. Test Multi-Region Detection

**✅ DO:**
- Create test resources in 2+ regions
- Verify detection across all regions
- Check that region-specific pricing is correct

**❌ DON'T:**
- Only test in `us-east-1`
- Assume all regions have same pricing
- Skip cross-region validation

### 4. Test Confidence Levels

**✅ DO:**
- Verify "critical" confidence for resources 90+ days old
- Verify "high" confidence for resources 30+ days old
- Verify "medium" confidence for resources 7-30 days old
- Verify "low" confidence for resources <7 days old

**❌ DON'T:**
- Ignore confidence levels in tests
- Assume all detections are "critical"
- Skip age-based confidence validation

### 5. Test Cost Calculations

**✅ DO:**
- Verify monthly cost matches AWS pricing (e.g., EIP = $3.60/month)
- Check that future waste calculation is correct
- Verify cumulative waste calculation (age × monthly cost)

**❌ DON'T:**
- Hardcode expected costs (prices change)
- Skip cost validation
- Ignore pricing API failures

---

## Automated Testing

### Backend Unit Tests

```python
# tests/api/v1/test_admin_pricing.py
import pytest
from app.core.config import settings

@pytest.mark.asyncio
async def test_get_pricing_stats(client, superuser_token_headers):
    """Test GET /admin/pricing/stats endpoint."""
    response = await client.get(
        "/api/v1/admin/pricing/stats",
        headers=superuser_token_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_cached_prices" in data
    assert "cache_hit_rate" in data
    assert "api_success_rate" in data

@pytest.mark.asyncio
async def test_refresh_pricing(client, superuser_token_headers):
    """Test POST /admin/pricing/refresh endpoint."""
    response = await client.post(
        "/api/v1/admin/pricing/refresh",
        headers=superuser_token_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["pending", "success"]
    assert "task_id" in data

@pytest.mark.asyncio
async def test_test_detection_debug_only(client, superuser_token_headers):
    """Test that test detection endpoint requires DEBUG mode."""
    # Temporarily disable DEBUG
    original_debug = settings.DEBUG
    settings.DEBUG = False

    response = await client.post(
        "/api/v1/test/detect-resources",
        headers=superuser_token_headers,
        json={
            "account_id": "uuid",
            "region": "us-east-1",
            "resource_types": ["elastic_ip"],
            "overrides": {}
        }
    )
    assert response.status_code == 403

    # Restore DEBUG
    settings.DEBUG = original_debug
```

### Frontend Integration Tests

```typescript
// frontend/tests/admin-pricing.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminPricingPage from '@/app/(dashboard)/dashboard/admin/pricing/page';

describe('Admin Pricing Page', () => {
  it('loads pricing statistics', async () => {
    render(<AdminPricingPage />);

    await waitFor(() => {
      expect(screen.getByText(/Total Cached Prices/i)).toBeInTheDocument();
      expect(screen.getByText(/Cache Hit Rate/i)).toBeInTheDocument();
    });
  });

  it('triggers manual refresh', async () => {
    const user = userEvent.setup();
    render(<AdminPricingPage />);

    const refreshButton = screen.getByRole('button', { name: /Refresh Prices Now/i });
    await user.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText(/Refreshing.../i)).toBeInTheDocument();
    });
  });

  it('filters by provider', async () => {
    const user = userEvent.setup();
    render(<AdminPricingPage />);

    const providerSelect = screen.getByLabelText(/Provider/i);
    await user.selectOptions(providerSelect, 'aws');

    // Verify filtered results
    await waitFor(() => {
      const providerCells = screen.getAllByText(/aws/i);
      expect(providerCells.length).toBeGreaterThan(0);
    });
  });
});
```

---

## Troubleshooting

### Issue: Test Detection Endpoint Returns 403

**Cause**: `DEBUG=False` in backend `.env`

**Solution**:
```bash
cd backend
echo "DEBUG=True" >> .env
uvicorn app.main:app --reload
```

### Issue: Pricing Refresh Fails

**Cause**: AWS Pricing API credentials missing or invalid

**Solution**:
1. Verify AWS credentials in cloud account
2. Check IAM permissions include `pricing:GetProducts`
3. Check Celery worker logs:
   ```bash
   docker-compose logs -f celery_worker
   ```

### Issue: Resources Not Detected

**Possible Causes**:
1. Resource age < `min_age_days` threshold
2. Detection rule disabled
3. Resource has `cloudwaste:ignore=true` tag

**Solution**:
1. Use test endpoint with `min_age_days=0`
2. Check detection rules: `GET /api/v1/detection-rules/{resource_type}`
3. Remove ignore tag from resource

### Issue: Incorrect Cost Calculation

**Cause**: Stale pricing data (fallback prices)

**Solution**:
1. Check pricing source: `GET /api/v1/admin/pricing/cache`
2. If source is "fallback", trigger refresh: `POST /api/v1/admin/pricing/refresh`
3. Wait for refresh to complete (check task status)
4. Re-run scan

---

## Quick Reference

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/test/detect-resources` | POST | Test detection with rule overrides (DEBUG only) |
| `/api/v1/admin/pricing/stats` | GET | Get pricing system statistics |
| `/api/v1/admin/pricing/cache` | GET | List cached prices with filters |
| `/api/v1/admin/pricing/refresh` | POST | Trigger manual pricing refresh |
| `/api/v1/admin/pricing/refresh/{task_id}` | GET | Check refresh task status |

### Key Detection Rules

| Rule | Default | Purpose |
|------|---------|---------|
| `min_age_days` | 3 | Ignore resources younger than N days |
| `confidence_threshold_days` | 7 | "High" confidence threshold |
| `min_idle_days` | 14 | Idle detection threshold (CloudWatch) |
| `min_stopped_days` | 30 | Stopped instance threshold |

### Test Commands

```bash
# Create test resources
./create-test-resources.sh

# Test immediate detection (DEBUG mode required)
curl -X POST "http://localhost:8000/api/v1/test/detect-resources" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"account_id":"uuid","region":"us-east-1","resource_types":["elastic_ip"],"overrides":{"elastic_ip":{"min_age_days":0}}}'

# Trigger pricing refresh
curl -X POST "http://localhost:8000/api/v1/admin/pricing/refresh" \
  -H "Authorization: Bearer $TOKEN"

# Cleanup test resources
./cleanup-test-resources.sh <TestSession-value>
```

---

## Additional Resources

- **CLAUDE.md**: Project architecture and standards
- **README.md**: Setup and installation guide
- **Backend API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Admin Dashboard**: `http://localhost:3000/dashboard/admin`
- **Pricing Dashboard**: `http://localhost:3000/dashboard/admin/pricing`
