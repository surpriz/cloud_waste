# Next Phases - ML Data Collection Roadmap

**Last Updated:** November 7, 2025
**Current Phase:** Phase 1 Complete ✅
**Next Phase:** Phase 2 (Data Enrichment)

---

## 🗺️ Roadmap Overview

| Phase | Timeline | Status | Priority | Complexity |
|-------|----------|--------|----------|------------|
| **Phase 1** | ✅ Complete | DONE | - | - |
| **Phase 2** | Weeks 1-4 | 📅 Planned | 🔥 High | Medium |
| **Phase 3** | Weeks 5-8 | 📅 Planned | 🔥 High | Medium |
| **Phase 4** | Weeks 9-12 | 📅 Planned | 🟡 Medium | Low |
| **Phase 5** | Month 4+ | 📅 Future | 🟢 Low | High |

---

## ✅ Phase 1: Automatic Collection (COMPLETE)

**Status:** ✅ Complete (November 7, 2025)

**What Was Done:**
- Removed consent verification → Automatic collection
- Added ML export to admin panel (UI + endpoints)
- Archived privacy settings page
- Restarted backend + Celery worker

**Result:** CloudWaste now collects ML data automatically for all users.

---

## 🔥 Phase 2: Data Enrichment (HIGH PRIORITY)

**Timeline:** Weeks 1-4 (4 weeks)
**Priority:** 🔥 High
**Complexity:** Medium
**Goal:** Collect MORE and BETTER data for ML models

### Why Phase 2 is Important

Current data is **basic**. To train accurate ML models, we need:
- Resource tags (anonymized) → Understand resource purpose
- Real AWS costs (Cost Explorer API) → Compare estimated vs actual
- Full CloudWatch time series → Better trend analysis
- Resource relationships → Understand dependencies

### 2.1 Add Resource Tags (Anonymized)

**Goal:** Collect resource tags while maintaining anonymity

**Files to Modify:**
- `backend/app/providers/aws.py` (EBS, EC2, RDS, etc.)
- `backend/app/providers/azure.py`
- `backend/app/services/ml_anonymization.py`

**Implementation:**

```python
# In aws.py - Example for EBS volumes
def _get_orphan_volumes(self, ec2_client, region: str):
    volumes = ec2_client.describe_volumes(...)

    for volume in volumes:
        # NEW: Collect tags
        tags = {tag['Key']: tag['Value'] for tag in volume.get('Tags', [])}

        # Anonymize tags
        anonymized_tags = anonymize_tags(tags)
        # → {"purpose": "backup", "env": "prod", "team": "backend"}
        # Remove PII: names, emails, phone numbers

        metadata = {
            ...
            "tags_anonymized": anonymized_tags,  # NEW
        }
```

**New Function in ml_anonymization.py:**

```python
def anonymize_tags(tags: Dict[str, str]) -> Dict[str, str]:
    """
    Anonymize resource tags.
    Keep: environment, purpose, tier, criticality
    Remove: names, emails, contact info, custom IDs
    """
    whitelist = ['env', 'environment', 'tier', 'purpose', 'criticality', 'backup']
    return {k: v for k, v in tags.items() if k.lower() in whitelist}
```

**Estimated Time:** 3-5 days

---

### 2.2 Add Real AWS Costs (Cost Explorer API)

**Goal:** Compare estimated costs vs real AWS costs

**Why:** Current costs are ESTIMATES. Real costs would improve accuracy.

**Files to Modify:**
- `backend/app/providers/aws.py`
- `backend/app/models/ml_training_data.py` (add `cost_real_monthly` field)

**Implementation:**

```python
# In aws.py
async def get_real_costs_for_resource(
    self,
    resource_id: str,
    start_date: datetime,
    end_date: datetime
) -> float:
    """
    Get actual AWS costs for a specific resource.
    Uses Cost Explorer API.
    """
    ce_client = self.session.client('ce', region_name='us-east-1')

    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date.strftime('%Y-%m-%d'),
            'End': end_date.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',
        Filter={
            'Dimensions': {
                'Key': 'RESOURCE_ID',
                'Values': [resource_id]
            }
        },
        Metrics=['UnblendedCost']
    )

    total_cost = sum(
        float(result['Total']['UnblendedCost']['Amount'])
        for result in response['ResultsByTime']
    )

    return total_cost
```

**Database Migration:**

```sql
-- Add column to ml_training_data
ALTER TABLE ml_training_data ADD COLUMN cost_real_monthly FLOAT;
ALTER TABLE ml_training_data ADD COLUMN cost_variance_pct FLOAT; -- estimated vs real
```

**Estimated Time:** 5-7 days

---

### 2.3 Add Full CloudWatch Time Series

**Goal:** Store full time series (not just aggregates) for better trend analysis

**Current:** We store only avg, p95, trend
**Proposed:** Store full 30-day time series (hourly/daily)

**Files to Modify:**
- `backend/app/models/cloudwatch_metrics_history.py` (already exists!)
- `backend/app/services/ml_data_collector.py`

**Implementation:**

```python
# In ml_data_collector.py - collect_cloudwatch_metrics_history()
async def collect_cloudwatch_metrics_history(
    resource_hash: str,
    resource_type: str,
    provider: str,
    metrics: Dict,
    db: AsyncSession
) -> None:
    """
    Store FULL time series (not just aggregates).
    """
    # Example: Store 30 days of hourly CPU data
    metric_values = {
        "timeseries": [65.2, 58.1, 72.3, ...],  # 720 hourly values (30 days)
        "timestamps": ["2025-10-08T00:00:00Z", ...],
        "avg": 62.5,
        "p50": 61.2,
        "p95": 89.7,
        "p99": 95.3,
        "trend": "stable"
    }

    history = CloudWatchMetricsHistory(
        resource_hash=resource_hash,
        resource_type=resource_type,
        provider=provider,
        metric_name="CPUUtilization",
        metric_values=metric_values,  # Full time series
        aggregation_period="hourly",
        start_date=start_date,
        end_date=end_date,
    )

    db.add(history)
```

**Benefit:** Better anomaly detection, trend analysis

**Estimated Time:** 3-4 days

---

### 2.4 Add Resource Relationships

**Goal:** Understand parent-child relationships (EBS → Instance, Instance → VPC)

**Why:** ML can learn that "EBS attached to stopped instance = likely waste"

**Files to Modify:**
- `backend/app/models/ml_training_data.py` (add `parent_resource_hash` field)
- `backend/app/providers/aws.py`

**Implementation:**

```python
# Example: EBS Volume attached to EC2 Instance
metadata = {
    ...
    "parent_resource_type": "ec2_instance",
    "parent_resource_hash": anonymize_resource_id(instance_id),
    "parent_resource_state": "stopped",  # NEW: Parent state matters!
}

# Example: EC2 Instance in VPC
metadata = {
    ...
    "parent_resource_type": "vpc",
    "parent_resource_hash": anonymize_resource_id(vpc_id),
}
```

**Database Migration:**

```sql
ALTER TABLE ml_training_data ADD COLUMN parent_resource_hash VARCHAR(64);
ALTER TABLE ml_training_data ADD COLUMN parent_resource_type VARCHAR(50);
ALTER TABLE ml_training_data ADD COLUMN parent_resource_state VARCHAR(30);
```

**Benefit:** ML models can learn contextual patterns

**Estimated Time:** 4-6 days

---

### 2.5 Add Temporal Patterns

**Goal:** Capture when resources are created (hour/day patterns)

**Why:** Resources created at 3 AM on weekends might be test/temporary

**Files to Modify:**
- `backend/app/models/ml_training_data.py`

**Implementation:**

```python
# Add to ml_training_data collection
temporal_features = {
    "created_hour_of_day": 15,  # 3 PM
    "created_day_of_week": 2,   # Tuesday
    "created_day_of_month": 7,  # 7th
    "is_weekend": False,
    "is_business_hours": True,  # 9 AM - 6 PM
}

# Store in resource_config or new JSON field
```

**Database Migration:**

```sql
ALTER TABLE ml_training_data ADD COLUMN temporal_features JSONB;
```

**Benefit:** Detect patterns like "weekend test resources"

**Estimated Time:** 2-3 days

---

### Phase 2 Summary

**Total Estimated Time:** 3-4 weeks

**Priority Tasks:**
1. ✅ Resource tags (3-5 days) - HIGH PRIORITY
2. ✅ Real AWS costs (5-7 days) - HIGH PRIORITY
3. ✅ Full time series (3-4 days) - MEDIUM PRIORITY
4. ✅ Resource relationships (4-6 days) - MEDIUM PRIORITY
5. ✅ Temporal patterns (2-3 days) - LOW PRIORITY

**Result:** Much richer data for ML training

---

## 🌐 Phase 3: GCP & Microsoft365 Support (HIGH PRIORITY)

**Timeline:** Weeks 5-8 (4 weeks)
**Priority:** 🔥 High
**Complexity:** Medium
**Goal:** Collect ML data from ALL cloud providers, not just AWS/Azure

### Why Phase 3 is Important

Currently:
- ✅ AWS: ML collection works
- ✅ Azure: ML collection works
- ❌ GCP: NO ML collection (scans return empty list)
- ❌ Microsoft365: Not implemented

### 3.1 Add GCP ML Collection

**Files to Modify:**
- `backend/app/workers/tasks.py` (add ML collection for GCP)
- `backend/app/providers/gcp.py` (enhance scan to return resources)

**Implementation:**

```python
# In tasks.py - _scan_cloud_account_async()
# Add GCP section
elif account.provider == "gcp":
    # Existing GCP scan logic
    orphan_resources = await scanner.scan_gcp(account)

    # NEW: Add ML collection (same as AWS/Azure)
    if user:
        try:
            ml_records = await collect_ml_training_data(
                scan, orphan_resources_from_db, user, db
            )
            await aggregate_monthly_cost_trends(
                account,
                datetime.now(timezone.utc).strftime("%Y-%m"),
                scan,
                orphan_resources_from_db,
                db,
            )
            logger.info(f"Collected {ml_records} ML records for GCP scan {scan.id}")
        except Exception as e:
            logger.error(f"Failed to collect GCP ML data: {e}")
```

**Estimated Time:** 1-2 weeks

---

### 3.2 Add Microsoft365 ML Collection

**Status:** Microsoft365 provider not yet implemented

**If Implemented in Future:**
- Same pattern as AWS/Azure/GCP
- Collect Office 365 license waste, unused mailboxes, etc.

**Estimated Time:** 1-2 weeks (if Microsoft365 provider exists)

---

### Phase 3 Summary

**Total Estimated Time:** 4 weeks

**Tasks:**
1. ✅ GCP ML collection integration (1-2 weeks)
2. ⚠️ Microsoft365 ML collection (1-2 weeks, if applicable)
3. ✅ Test all providers end-to-end

**Result:** Complete multi-cloud ML data collection

---

## 🔧 Phase 4: Optimization & Automation (MEDIUM PRIORITY)

**Timeline:** Weeks 9-12 (4 weeks)
**Priority:** 🟡 Medium
**Complexity:** Low
**Goal:** Optimize performance and automate exports

### 4.1 Configure Automated Weekly Exports

**Goal:** Auto-export datasets weekly for ML training

**Current:** Admin must manually click export button

**Files to Modify:**
- `backend/app/workers/celery_app.py` (add beat schedule)

**Implementation:**

```python
# In celery_app.py
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Existing tasks...

    # NEW: ML data export hebdomadaire
    "export-ml-datasets-weekly": {
        "task": "app.workers.ml_tasks.export_ml_datasets_weekly",
        "schedule": crontab(day_of_week=1, hour=3, minute=0),  # Monday 3 AM
    },

    # NEW: ML data cleanup (GDPR - delete data > 3 years)
    "cleanup-old-ml-data-monthly": {
        "task": "app.workers.ml_tasks.cleanup_old_ml_data",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),  # 1st of month 2 AM
    },
}
```

**Restart Celery Beat:**

```bash
docker restart cloudwaste_celery_beat
```

**Estimated Time:** 1 day

---

### 4.2 Optimize Export Performance

**Goal:** Speed up exports for large datasets (1M+ records)

**Current:** JSON export can be slow for large datasets

**Optimizations:**

1. **Use Parquet format** (faster than JSON for large data)
2. **Stream exports** (don't load everything in memory)
3. **Compress exports** (gzip for JSON files)

**Files to Modify:**
- `backend/app/ml/data_pipeline.py`

**Implementation:**

```python
# Add Parquet export option
async def export_ml_training_dataset(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json"  # or "parquet"
) -> str:
    """Export with Parquet option for large datasets."""
    if output_format == "parquet":
        df = pd.read_sql(query, engine)
        output_path = f"./ml_datasets/ml_training_data_{today}.parquet"
        df.to_parquet(output_path, compression='snappy')
    else:
        # Existing JSON export
        ...
```

**Dependencies:**

```bash
pip install pyarrow  # For Parquet support
```

**Estimated Time:** 2-3 days

---

### 4.3 Add Monitoring Dashboard (Optional)

**Goal:** Visualize ML data collection in Grafana

**Metrics to Track:**
- Records collected per day
- User action rate (%)
- Data quality score
- Export frequency

**Implementation:**
- Add Prometheus metrics in FastAPI
- Create Grafana dashboard

**Estimated Time:** 3-5 days (optional)

---

### Phase 4 Summary

**Total Estimated Time:** 1-2 weeks

**Tasks:**
1. ✅ Automated weekly exports (1 day)
2. ✅ Optimize export performance (2-3 days)
3. ⚠️ Monitoring dashboard (3-5 days, optional)

**Result:** Production-grade ML data pipeline

---

## 🤖 Phase 5: ML Model Training (FUTURE)

**Timeline:** Month 4+ (when 100K+ samples)
**Priority:** 🟢 Low (wait for data)
**Complexity:** High
**Goal:** Train and deploy ML models for CloudWaste V2

### 5.1 When to Start Phase 5

**Prerequisites:**
- ✅ 100,000+ labeled ML records
- ✅ 50,000+ user actions recorded
- ✅ Data quality validated (no major issues)
- ✅ Phase 2 enrichment complete (tags, costs, relationships)

**Timeline Estimate:**
- Month 1: 10,000 records
- Month 2: 50,000 records
- Month 3: 100,000 records ← Ready for Phase 5

---

### 5.2 ML Models to Train

#### Model 1: Waste Prediction (Binary Classification)

**Goal:** Predict if a resource will become waste

**Algorithm:** RandomForest, XGBoost
**Target Accuracy:** 80-90%

**Features:**
- resource_age_days
- metrics_summary (CPU, I/O, etc.)
- detection_scenario
- confidence_level
- tags_anonymized (Phase 2)
- parent_resource_state (Phase 2)
- temporal_features (Phase 2)

**Target:**
- `user_action` = deleted (waste) vs kept/ignored (not waste)

**Training Script:**

```python
# train_model.py already exists!
python train_model.py

# Result:
# 🤖 Training Random Forest model...
# 📈 Model Performance: Accuracy: 87.32%
# ✅ Model saved to: ./ml_models/waste_prediction_model.pkl
```

---

#### Model 2: Cost Forecasting (Time Series)

**Goal:** Predict future cloud costs (3-6 months)

**Algorithm:** Prophet, ARIMA, LSTM
**Target Accuracy:** ±10%

**Features:**
- Historical monthly costs (`cost_trend_data`)
- Seasonality (Q4 spike, holiday patterns)
- Waste elimination trends

---

#### Model 3: Anomaly Detection

**Goal:** Detect unusual resource patterns

**Algorithm:** Isolation Forest, Autoencoder
**Output:** Anomaly score (0-100)

**Features:**
- CloudWatch time series (`cloudwatch_metrics_history`)
- Cost deviations

---

### 5.3 Model Deployment

**Integration:** Add model predictions to backend API

```python
# backend/app/services/ml_predictor.py (NEW)
class MLPredictor:
    def __init__(self):
        self.model = self._load_model()

    def _load_model(self):
        with open('./ml_models/waste_prediction_model.pkl', 'rb') as f:
            return pickle.load(f)

    def predict_waste(self, resource_features: Dict) -> float:
        """Returns waste probability (0.0-1.0)."""
        return self.model.predict_proba([resource_features])[0][1]
```

**Frontend Integration:**

```typescript
// Display prediction in UI
<Badge variant={wasteProbability > 0.7 ? "destructive" : "default"}>
  {wasteProbability > 0.7 && "⚠️"} {(wasteProbability * 100).toFixed(0)}% chance of waste
</Badge>
```

---

### Phase 5 Summary

**Total Estimated Time:** 2-3 months

**Tasks:**
1. Train waste prediction model (2-4 weeks)
2. Train cost forecasting model (2-4 weeks)
3. Train anomaly detection model (2-4 weeks)
4. Deploy models to production (1-2 weeks)
5. A/B test predictions (1-2 weeks)
6. Launch CloudWaste V2 with AI! 🚀

**Result:** CloudWaste V2 with AI-powered predictions

---

## 📊 Roadmap Timeline

```
Month 1: ─────────[Phase 2: Data Enrichment]────────────────────▶
Month 2: ─────────[Phase 3: GCP Support]──────────────────────▶
Month 3: ──────[Phase 4: Optimization]───────[Data grows to 100K+]
Month 4+: ──────────────[Phase 5: ML Training & V2 Launch]──────▶

Current: You are here ─────────────────────────────────────────────▶
         Phase 1 Complete ✅
```

---

## 🎯 Next Actions

### Immediate (This Week)

1. ✅ Review current data collection (verify scans are collecting data)
2. ✅ Monitor data growth (target: 10K+ records in Month 1)
3. ✅ Decide on Phase 2 priority (which enrichments are most important?)

### Short Term (Next 2 Weeks)

1. 📅 Start Phase 2.1: Add resource tags
2. 📅 Start Phase 2.2: Add real AWS costs
3. ✅ Continue monitoring data quality

### Medium Term (Month 2-3)

1. 📅 Complete Phase 2 (all enrichments)
2. 📅 Start Phase 3 (GCP support)
3. 📅 Start Phase 4 (optimization)

### Long Term (Month 4+)

1. 📅 Reach 100K+ samples
2. 📅 Start Phase 5 (ML training)
3. 🚀 Launch CloudWaste V2 with AI

---

## 📝 Decision Points

### Should You Do Phase 2 Now?

**Yes, if:**
- ✅ You want better ML models (higher accuracy)
- ✅ You have development time available (3-4 weeks)
- ✅ You want to maximize data quality from Day 1

**No, if:**
- ❌ You want to focus on other features first
- ❌ Current data collection is enough for now
- ❌ You want to wait until you have 10K+ samples first

**Recommendation:** Do Phase 2.1 (tags) and 2.2 (real costs) now. They add the most value.

---

### Should You Do Phase 3 Now?

**Yes, if:**
- ✅ You have GCP customers
- ✅ GCP scan is functional (currently returns empty list)

**No, if:**
- ❌ You only have AWS/Azure customers
- ❌ GCP scan needs major work first

**Recommendation:** Wait until GCP scan is functional, then add ML collection (easy).

---

## 📞 Support

**Questions about roadmap?**
- Review [Current Status](./01_CURRENT_STATUS.md) - Understand what's done
- Review [Architecture](./02_ARCHITECTURE.md) - Technical details
- Contact: jerome0laval@gmail.com

---

**🚀 Phase 2 is the next big step. Let's enrich that data!**
