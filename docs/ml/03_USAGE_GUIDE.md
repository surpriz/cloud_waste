# Usage Guide - ML Data Collection

**Last Updated:** November 7, 2025

---

## 🎯 Overview

CloudWaste automatically collects anonymized ML data during every scan. **No user action required.**

### What Happens Automatically

```
User launches scan → Backend scans cloud → Detects orphans → ✨ ML data collected → PostgreSQL
```

**Result:** Data accumulates silently in background, ready for export via admin panel.

---

## 📊 What Data is Collected

### Every Scan Collects (Anonymized)

1. **Resource Type** - ebs_volume, ec2_instance, rds_instance, etc.
2. **Age** - How long resource has existed (days)
3. **CloudWatch Metrics** - CPU, I/O, network (aggregated: avg, p95, trend)
4. **Cost** - Monthly estimated cost
5. **Region** - Generalized (us-*, eu-*, ap-*)
6. **Detection Scenario** - idle, stopped, unused, no_connections, etc.
7. **Confidence Level** - critical, high, medium, low

### User Actions Tracked

When a user updates a resource status:
- **Action taken** - deleted, ignored, kept
- **Time to action** - Hours between detection and decision
- **Cost saved** - If deleted, how much saved per month

### ❌ What is NOT Collected

- Account IDs (hashed with SHA256)
- Resource IDs (hashed with SHA256)
- Resource names
- Tags with PII
- Absolute metric values (only aggregates)

**Privacy:** All data is anonymized and GDPR-compliant.

---

## 🖥️ How to Use (Admin)

### 1. View ML Statistics

**URL:** http://localhost:3000/dashboard/admin

**What You'll See:**
- Purple/Indigo widget titled "ML Data Collection"
- Total ML records collected
- Records collected in last 7 days
- Records collected in last 30 days
- Last collection timestamp

**Example:**
```
ML Data Collection                    ✅ Active
15,847 total records | 1,847 last 7 days | 8,943 last 30 days

┌────────────────┐ ┌──────────────────┐ ┌──────────────┐
│ Total ML       │ │ User Actions     │ │ Cost Trends  │
│ Records        │ │ Tracked          │ │              │
│ 15,847         │ │ 3,241            │ │ 567          │
└────────────────┘ └──────────────────┘ └──────────────┘

[Export Last 30 Days (JSON)] [Export Last 90 Days (JSON)]
[Export Last 90 Days (CSV)]

Last collection: 11/7/2025, 6:30:00 PM
```

---

### 2. Export ML Data

**Three Export Options:**

#### Option A: Via Admin Panel UI (RECOMMENDED)

1. Go to http://localhost:3000/dashboard/admin
2. Scroll to "ML Data Collection" widget
3. Click one of the export buttons:
   - **"Export Last 30 Days (JSON)"** - Quick export for testing
   - **"Export Last 90 Days (JSON)"** - Standard export
   - **"Export Last 90 Days (CSV)"** - For Excel/Pandas

**Files Created:**
```
./ml_datasets/
├── ml_training_data_20251107.json      (15,847 records)
├── user_action_patterns_20251107.json  (3,241 records)
└── cost_trends_20251107.json           (567 records)
```

---

#### Option B: Via Python Script

```bash
# At project root
python export_ml_data.py
```

**Result:**
```
🚀 CloudWaste ML Data Export
==================================================

📊 Exporting ML datasets...

✅ Export complete!

Files created:
  - ml_training_data: ./ml_datasets/ml_training_data_20251107.json
  - user_action_patterns: ./ml_datasets/user_action_patterns_20251107.json
  - cost_trends: ./ml_datasets/cost_trends_20251107.json

📈 You can now use these files to train your ML models!
```

---

#### Option C: Via SQL Direct Export

```bash
# Export ml_training_data as CSV
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "COPY (SELECT * FROM ml_training_data) TO STDOUT WITH CSV HEADER" \
  > ml_data.csv
```

---

## 📈 Monitoring Data Collection

### Check Collection is Working

```bash
# 1. Launch a scan via UI
# Go to: http://localhost:3000/dashboard
# Click "Run Scan" on any AWS/Azure account

# 2. Wait for scan to complete (1-5 minutes)

# 3. Check ML data was collected
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) as ml_records FROM ml_training_data
   WHERE created_at > NOW() - INTERVAL '1 hour';"

# Expected result:
#  ml_records
# ------------
#     23       ← Should see records from the scan
```

---

### View Data Growth Over Time

```bash
# Daily growth (last 7 days)
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    DATE(created_at) as date,
    COUNT(*) as records
  FROM ml_training_data
  WHERE created_at >= NOW() - INTERVAL '7 days'
  GROUP BY DATE(created_at)
  ORDER BY date DESC;
"
```

**Example Output:**
```
    date     | records
-------------+---------
 2025-11-07  |   1,847
 2025-11-06  |   2,134
 2025-11-05  |   1,923
 2025-11-04  |   1,756
 2025-11-03  |   2,012
```

---

### View All ML Tables Status

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    'ml_training_data' as table_name,
    COUNT(*) as count
  FROM ml_training_data
  UNION ALL
  SELECT
    'user_action_patterns',
    COUNT(*)
  FROM user_action_patterns
  UNION ALL
  SELECT
    'cost_trend_data',
    COUNT(*
  FROM cost_trend_data;
"
```

**Example Output:**
```
     table_name        | count
-----------------------+--------
 ml_training_data      | 15,847
 user_action_patterns  |  3,241
 cost_trend_data       |    567
```

---

## 🔄 Complete Workflow

### Phase 1: Collection (Months 1-3) - Current Phase

```
Your users use CloudWaste normally
    ↓
Scans run automatically (manual or scheduled)
    ↓
✨ ML data collected in background
    ↓
ZERO changes visible to users
    ↓
Data accumulates in PostgreSQL
```

**Your Action:** Monitor data growth

```bash
# Check every week
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) FROM ml_training_data;"

# Target Month 1: 10,000+ records
# Target Month 2: 50,000+ records
# Target Month 3: 100,000+ records
```

---

### Phase 2: Export (When 10K+ samples)

```bash
# Export via admin panel or script
python export_ml_data.py

# Result:
# ✅ ml_datasets/ml_training_data_20251107.json (15,847 records)
# ✅ ml_datasets/user_action_patterns_20251107.json (3,241 records)
# ✅ ml_datasets/cost_trends_20251107.json (567 records)
```

**Your Action:** Validate export quality

```bash
# Check file size
ls -lh ml_datasets/

# Count records
cat ml_datasets/ml_training_data_*.json | jq '. | length'
```

---

### Phase 3: Training (When 100K+ samples)

```bash
# Train ML model (example with RandomForest)
python train_model.py
```

**Result:**
```
🚀 CloudWaste ML Model Training
============================================================

📂 Loading data from: ml_datasets/ml_training_data_20251107.json

📊 Dataset info:
   Total records: 15,847
   Resources with user action: 3,241
   Labeled records for training: 3,241

🤖 Training Random Forest model...
   Training set: 2,593 samples
   Test set: 648 samples

📈 Model Performance:
   Accuracy: 87.32%

✅ Training complete!
💾 Model saved to: ./ml_models/waste_prediction_model.pkl
```

---

### Phase 4: Production (V2 with AI)

```python
# Use trained model for predictions (future)
import pickle

# Load model
with open('./ml_models/waste_prediction_model.pkl', 'rb') as f:
    model = pickle.load(f)

# Predict for new resource
prediction = model.predict([[resource_features]])
# → 1 = likely waste, 0 = probably not waste

# Display in UI: "⚠️ 87% chance this resource will become waste"
```

---

## ⏱️ Timeline Recommandée

| Period | Objectif | Action | ML Records Target |
|--------|----------|--------|-------------------|
| **Week 1** | Verify collection | Monitor logs, check database | 500-2,000 |
| **Month 1** | Baseline | Let it run, monitor growth | 10,000+ |
| **Month 2** | Quality check | First test export | 50,000+ |
| **Month 3** | Ready for training | Export full dataset | 100,000+ |
| **Month 4-6** | Train models | Use train_model.py | 500,000+ |
| **Month 6+** | V2 Launch | CloudWaste V2 with AI! 🚀 | 1,000,000+ |

---

## 📊 Data Collection Examples

### Example 1: Scan Collects ML Data

```
User: Launches scan on AWS account (10 regions)
    ↓
Backend: Scans 5 regions, finds 23 orphan resources
    ↓
ML Collector:
    - Collects 23 ml_training_data records
    - Collects 23 resource_lifecycle_events
    - Aggregates 1 cost_trend_data record
    - Stores cloudwatch_metrics_history for 15 resources
    ↓
PostgreSQL: +23 new records in ml_training_data
```

**Verify:**
```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT resource_type, detection_scenario, confidence_level, cost_monthly
   FROM ml_training_data
   ORDER BY created_at DESC
   LIMIT 5;"
```

**Result:**
```
 resource_type | detection_scenario | confidence_level | cost_monthly
---------------+--------------------+------------------+--------------
 ebs_volume    | idle_volume        | high             |        45.20
 ec2_instance  | stopped_instance   | critical         |       127.50
 elastic_ip    | unassociated_ip    | high             |         3.60
 rds_instance  | idle_database      | medium           |       215.80
 nat_gateway   | no_traffic         | high             |        32.40
```

---

### Example 2: User Action Tracked

```
User: Marks ebs_volume as "deleted" after 2 hours
    ↓
Backend: PATCH /api/v1/resources/{id} with status="deleted"
    ↓
Action Tracker:
    - Creates user_action_patterns record
    - Updates ml_training_data with user_action="deleted"
    - Updates cost_trend_data with waste_eliminated +45.20
    ↓
PostgreSQL: User decision recorded for ML training
```

**Verify:**
```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT resource_type, action_taken, time_to_action_hours, cost_saved_monthly
   FROM user_action_patterns
   ORDER BY action_at DESC
   LIMIT 5;"
```

**Result:**
```
 resource_type | action_taken | time_to_action_hours | cost_saved_monthly
---------------+--------------+----------------------+--------------------
 ebs_volume    | deleted      |                    2 |              45.20
 ec2_instance  | ignored      |                   72 |               0.00
 elastic_ip    | deleted      |                    1 |               3.60
 rds_instance  | kept         |                  120 |               0.00
 nat_gateway   | deleted      |                    5 |              32.40
```

---

## 🎯 Key Metrics to Monitor

### 1. Collection Rate

**Target:** 10+ records per scan

```bash
# Average records per scan
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    AVG(records_per_scan) as avg_records
  FROM (
    SELECT DATE(created_at) as date, COUNT(*) as records_per_scan
    FROM ml_training_data
    GROUP BY DATE(created_at)
  ) daily;
"
```

---

### 2. User Action Rate

**Target:** 30%+ of detected resources have user action

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    COUNT(CASE WHEN user_action IS NOT NULL THEN 1 END)::float / COUNT(*) * 100
    AS user_action_percentage
  FROM ml_training_data;
"
```

---

### 3. Data Quality

**Target:** No NULL critical fields

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "
  SELECT
    COUNT(*) as total_records,
    COUNT(CASE WHEN resource_type IS NULL THEN 1 END) as null_resource_type,
    COUNT(CASE WHEN detection_scenario IS NULL THEN 1 END) as null_scenario,
    COUNT(CASE WHEN cost_monthly IS NULL THEN 1 END) as null_cost
  FROM ml_training_data;
"
```

**Expected:** All null counts = 0

---

## ❓ FAQ

### Q: Users see something different on the frontend?
**A: No. Collection is 100% transparent. No visible changes.**

### Q: Is data anonymized?
**A: Yes. SHA256 hashing for IDs, generalized regions, aggregated metrics only.**

### Q: How do I know collection is working?
**A: Launch a scan, then run SQL query to check ml_training_data table.**

### Q: How long to get enough data for ML?
**A: Depends on traffic:**
- 10 scans/day × 20 resources = 200 records/day → 10K in 50 days
- 100 scans/day × 20 resources = 2K records/day → 100K in 50 days

### Q: Can I disable collection?
**A: Yes, comment out ML collection code in backend/app/workers/tasks.py lines 201-234**

### Q: Which ML model to use?
**A: Recommendation:**
- RandomForest (simple, robust) ← Start here
- XGBoost (better performance)
- Neural Networks (if 1M+ samples)

---

## 📞 Support

**Need Help?**
- [Current Status](./01_CURRENT_STATUS.md) - Check what's working
- [Troubleshooting](./05_TROUBLESHOOTING.md) - Debug issues
- [Architecture](./02_ARCHITECTURE.md) - Technical details

**Questions:** jerome0laval@gmail.com

---

**🎉 That's it! CloudWaste is now collecting ML data automatically.**

**Next:** Monitor data growth and export when you reach 10K+ records.
