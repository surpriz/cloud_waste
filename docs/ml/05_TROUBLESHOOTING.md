# Troubleshooting - ML Data Collection

**Last Updated:** November 7, 2025

---

## 🔍 Quick Diagnostic

Run these commands to check system health:

```bash
# 1. Check tables exist
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "\dt" | grep ml_
# Expected: 6 tables

# 2. Check data exists
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM ml_training_data;"
# Expected: 0+ (increases after each scan)

# 3. Check backend running
docker ps | grep cloudwaste_backend
# Expected: Up X minutes

# 4. Check Celery worker running
docker ps | grep cloudwaste_celery_worker
# Expected: Up X minutes

# 5. Check admin endpoint
curl http://localhost:8000/api/v1/admin/ml-stats \
  -H "Authorization: Bearer YOUR_TOKEN" | jq
# Expected: JSON with statistics
```

---

## ❌ Problem: No Data Being Collected

### Symptom

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) FROM ml_training_data;"

# Result: 0 (even after multiple scans)
```

---

### Check 1: Tables Exist?

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "\dt" | grep -E "ml_|user_preferences"
```

**Expected Output:**
```
 cloudwatch_metrics_history
 cost_trend_data
 ml_training_data
 resource_lifecycle_events
 user_action_patterns
 user_preferences
```

**If tables missing:**
```bash
# Run migration
docker exec cloudwaste_backend alembic upgrade head
```

---

### Check 2: Celery Worker Running?

```bash
docker ps | grep celery_worker
```

**Expected:**
```
cloudwaste_celery_worker   Up 5 minutes
```

**If not running:**
```bash
docker start cloudwaste_celery_worker
# Or
docker-compose up -d cloudwaste_celery_worker
```

---

### Check 3: Celery Worker Logs

```bash
docker logs cloudwaste_celery_worker --tail 50
```

**Look for:**
- ✅ `Collected X ML training records for scan {id}`
- ❌ `ERROR` or `Exception` in logs

**If errors:**
```bash
# Check full error
docker logs cloudwaste_celery_worker -f | grep -i "error\|exception"
```

---

### Check 4: Backend Logs

```bash
docker logs cloudwaste_backend --tail 50 | grep -i "ml\|collect"
```

**Look for:**
- ✅ `Application startup complete`
- ❌ Import errors or exceptions

---

### Check 5: Scan Completed Successfully?

```bash
# Check scans table
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT id, status, orphan_resources_found, completed_at
   FROM scans
   ORDER BY completed_at DESC
   LIMIT 5;"
```

**Expected:**
```
 status   | orphan_resources_found | completed_at
----------+------------------------+---------------------
 completed|                     23 | 2025-11-07 18:30:00
 completed|                     15 | 2025-11-07 16:15:00
```

**If status = 'failed' or 'pending':**
- Scan didn't complete → No ML data collected
- Check scan logs for errors

---

## ❌ Problem: Admin Panel Shows 0 Records

### Symptom

Admin panel (http://localhost:3000/dashboard/admin) shows:
```
Total ML Records: 0
Records last 7 days: 0
```

---

### Check 1: Are You Logged in as Superuser?

```bash
# Check your user status
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT email, is_superuser, is_active FROM users WHERE email = 'your-email@example.com';"
```

**Expected:**
```
 email               | is_superuser | is_active
---------------------+--------------+-----------
 your-email@...com   | true         | true
```

**If is_superuser = false:**
```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "UPDATE users SET is_superuser = true WHERE email = 'your-email@example.com';"
```

---

### Check 2: Backend API Endpoint Works?

```bash
# Get JWT token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your-email@example.com", "password": "your-password"}' \
  | jq -r '.access_token')

# Test ML stats endpoint
curl http://localhost:8000/api/v1/admin/ml-stats \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Expected:**
```json
{
  "total_ml_records": 0,
  "total_user_actions": 0,
  "total_cost_trends": 0,
  "records_last_7_days": 0,
  "records_last_30_days": 0,
  "last_collection_date": null
}
```

**If 404 or 500 error:**
- Backend not running or endpoint missing
- Check backend logs

---

### Check 3: Frontend Running?

```bash
cd frontend
npm run dev
```

**Check browser console for errors:**
- F12 → Console tab
- Look for API errors

---

## ❌ Problem: Export Not Working

### Symptom

Clicking "Export Last 90 Days (JSON)" does nothing or shows error.

---

### Check 1: Directory Exists?

```bash
ls -la ./ml_datasets
```

**If not exists:**
```bash
mkdir -p ./ml_datasets
```

---

### Check 2: Backend Permissions?

```bash
# Check if backend can write to ml_datasets
docker exec cloudwaste_backend touch /app/ml_datasets/test.txt
docker exec cloudwaste_backend ls -la /app/ml_datasets/
```

**If permission denied:**
```bash
# Fix permissions
chmod 777 ./ml_datasets
```

---

### Check 3: Export Script Works?

```bash
# Test export_ml_data.py directly
python export_ml_data.py
```

**Expected:**
```
🚀 CloudWaste ML Data Export
==================================================

📊 Exporting ML datasets...

✅ Export complete!

Files created:
  - ml_training_data: ./ml_datasets/ml_training_data_20251107.json
  ...
```

**If ImportError:**
```bash
# Install missing dependencies
cd backend
pip install -r requirements.txt
```

---

## ❌ Problem: Data Quality Issues

### Symptom

Exported data has NULL values or missing fields.

---

### Check 1: NULL Values in Critical Fields

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    COUNT(*) as total_records,
    COUNT(CASE WHEN resource_type IS NULL THEN 1 END) as null_resource_type,
    COUNT(CASE WHEN detection_scenario IS NULL THEN 1 END) as null_scenario,
    COUNT(CASE WHEN cost_monthly IS NULL THEN 1 END) as null_cost,
    COUNT(CASE WHEN confidence_level IS NULL THEN 1 END) as null_confidence
  FROM ml_training_data;
"
```

**Expected:** All NULL counts = 0

**If NULLs found:**
- Bug in ml_data_collector.py
- Check Celery worker logs for errors during collection

---

### Check 2: Duplicate Records

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT resource_hash, COUNT(*) as count
  FROM ml_training_data
  GROUP BY resource_hash
  HAVING COUNT(*) > 1
  ORDER BY count DESC
  LIMIT 10;
"
```

**Expected:** No duplicates (or very few)

**If many duplicates:**
- Same resource detected multiple times
- Expected behavior (resource detected in multiple scans)

---

### Check 3: Metrics Summary Format

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT resource_type, metrics_summary
  FROM ml_training_data
  LIMIT 3;
"
```

**Expected:**
```json
{
  "VolumeReadOps": {"avg": 0.2, "p95": 1.5, "trend": "stable"},
  "VolumeWriteOps": {"avg": 0.0, "p95": 0.1, "trend": "stable"}
}
```

**If malformed JSON:**
- Bug in ml_anonymization.py
- Check anonymize_metrics() function

---

## ❌ Problem: GCP Resources Not Collected

### Symptom

GCP scans complete but no ML data collected.

---

### Root Cause

GCP scan integration not complete. See [Next Phases - Phase 3](./04_NEXT_PHASES.md#phase-3-gcp--microsoft365-support).

---

### Workaround

Use AWS/Azure for ML data collection. GCP support coming in Phase 3.

---

### Check GCP Scan Status

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT id, provider, status, orphan_resources_found
   FROM scans
   WHERE provider = 'gcp'
   ORDER BY completed_at DESC
   LIMIT 5;"
```

**If orphan_resources_found = 0:**
- GCP scan returns empty list (MVP phase)
- ML collection skipped (no resources to collect)

---

## ❌ Problem: Backend Import Errors

### Symptom

```bash
docker logs cloudwaste_backend | grep -i "error\|exception"

# Shows:
# ImportError: cannot import name 'MLTrainingData'
```

---

### Fix: Restart Backend

```bash
docker restart cloudwaste_backend cloudwaste_celery_worker
```

---

### Check Imports Work

```bash
docker exec cloudwaste_backend python -c "
from app.services.ml_data_collector import collect_ml_training_data
from app.services.ml_anonymization import anonymize_user_id
from app.services.user_action_tracker import track_user_action
from app.ml.data_pipeline import export_ml_training_dataset
print('✅ All imports successful!')
"
```

**Expected:**
```
✅ All imports successful!
```

**If ImportError:**
- File missing or syntax error
- Check file exists: `ls backend/app/services/ml_*.py`

---

## ❌ Problem: Slow Exports

### Symptom

Export takes 5+ minutes for 10K records.

---

### Solution 1: Check Database Performance

```bash
# Check slow queries
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  WHERE query LIKE '%ml_training_data%'
  ORDER BY mean_exec_time DESC
  LIMIT 5;
"
```

**If slow queries found:**
- Add indexes (should already exist from migration)
- Check indexes: `\d ml_training_data`

---

### Solution 2: Export in Batches

```python
# Instead of exporting all data at once
# Export in monthly batches
for month in range(1, 13):
    start_date = datetime(2025, month, 1)
    end_date = datetime(2025, month, 28)
    export_ml_training_dataset(start_date, end_date)
```

---

### Solution 3: Use Parquet Format

See [Next Phases - Phase 4.2](./04_NEXT_PHASES.md#42-optimize-export-performance)

---

## 🔧 Common Fixes

### Fix 1: Restart All Services

```bash
# Nuclear option - restart everything
docker-compose down
docker-compose up -d

# Wait 30 seconds
sleep 30

# Check status
docker ps
```

---

### Fix 2: Clear Redis Cache

```bash
# Clear Celery task queue
docker exec cloudwaste_redis redis-cli FLUSHALL
```

---

### Fix 3: Rebuild Backend Image

```bash
# If code changes not reflected
docker-compose build cloudwaste_backend
docker-compose up -d cloudwaste_backend cloudwaste_celery_worker
```

---

### Fix 4: Check Disk Space

```bash
# Check available disk space
df -h

# Check PostgreSQL disk usage
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    pg_size_pretty(pg_database_size('cloudwaste')) as db_size;
"
```

---

## 📊 Verification Commands

### Full System Check

```bash
#!/bin/bash
echo "CloudWaste ML Data Collection - System Check"
echo "=============================================="
echo ""

echo "1. Docker Containers"
docker ps | grep cloudwaste | awk '{print $NF, $7}'
echo ""

echo "2. ML Tables"
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "\dt" | grep ml_ | wc -l
echo "   Expected: 6 tables"
echo ""

echo "3. ML Records"
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM ml_training_data;" | grep -v "count" | grep -v "\-\-" | tr -d ' '
echo ""

echo "4. Recent Scans"
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM scans WHERE status = 'completed' AND completed_at > NOW() - INTERVAL '24 hours';" | grep -v "count" | grep -v "\-\-" | tr -d ' '
echo "   (last 24 hours)"
echo ""

echo "5. Backend Health"
curl -s http://localhost:8000/health | jq '.status' || echo "❌ Backend not responding"
echo ""

echo "✅ System check complete"
```

Save as `check_ml_system.sh` and run:
```bash
chmod +x check_ml_system.sh
./check_ml_system.sh
```

---

## 📞 Getting Help

### Debug Checklist

Before asking for help, run:

1. ✅ System check script (above)
2. ✅ Check backend logs: `docker logs cloudwaste_backend --tail 100`
3. ✅ Check Celery logs: `docker logs cloudwaste_celery_worker --tail 100`
4. ✅ Check PostgreSQL connection: `docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT 1;"`
5. ✅ Check ML table counts: `docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM ml_training_data;"`

### Provide This Info

When asking for help, provide:
- Output of system check script
- Backend logs (last 100 lines)
- Celery logs (last 100 lines)
- What you were trying to do
- What error message you saw

---

## 🎯 Performance Benchmarks

### Expected Performance

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Records per scan | 10-50 | ___ | ✅ / ❌ |
| Collection overhead | <500ms | ___ | ✅ / ❌ |
| Export time (10K records) | <10s | ___ | ✅ / ❌ |
| Database size (100K records) | ~50MB | ___ | ✅ / ❌ |

**Check Your Performance:**

```bash
# Records per scan (average)
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT AVG(records_per_scan)::int as avg_records
  FROM (
    SELECT DATE(created_at), COUNT(*) as records_per_scan
    FROM ml_training_data
    GROUP BY DATE(created_at)
  ) daily;
"

# Database size
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT pg_size_pretty(pg_database_size('cloudwaste'));
"
```

---

## 🔍 Advanced Debugging

### Enable Debug Logging

```bash
# Edit docker-compose.yml
# Add environment variable to backend:
environment:
  - LOG_LEVEL=DEBUG

# Restart
docker-compose restart cloudwaste_backend cloudwaste_celery_worker
```

---

### SQL Query Debugging

```bash
# Enable query logging
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  ALTER DATABASE cloudwaste SET log_statement = 'all';
"

# View logs
docker logs cloudwaste_postgres -f | grep "SELECT\|INSERT"
```

---

### Python Debugging

```python
# Add to ml_data_collector.py for debugging
import logging
logger = logging.getLogger(__name__)

async def collect_ml_training_data(...):
    logger.debug(f"Starting ML collection for scan {scan.id}")
    logger.debug(f"Found {len(orphan_resources)} orphan resources")

    for i, resource in enumerate(orphan_resources):
        logger.debug(f"Processing resource {i+1}/{len(orphan_resources)}: {resource.resource_type}")
        ...
```

---

**See Also:**
- [Current Status](./01_CURRENT_STATUS.md) - What's working
- [Usage Guide](./03_USAGE_GUIDE.md) - How to use
- [Architecture](./02_ARCHITECTURE.md) - Technical details

**Contact:** jerome0laval@gmail.com
