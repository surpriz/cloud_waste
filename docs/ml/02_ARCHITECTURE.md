# Architecture - ML Data Collection

**Last Updated:** November 7, 2025

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CloudWaste ML Collection                     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Frontend   │────────▶│   Backend    │────────▶│  PostgreSQL  │
│              │         │   FastAPI    │         │   (6 tables) │
└──────────────┘         └──────────────┘         └──────────────┘
                                │
                                │ Celery Task
                                ▼
                         ┌──────────────┐
                         │  AWS/Azure   │
                         │   Providers  │
                         └──────────────┘
                                │
                                │ Scan
                                ▼
                         ┌──────────────┐
                         │ ML Data      │
                         │ Collector    │
                         └──────────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │ Anonymization│
                         │   Service    │
                         └──────────────┘
                                │
                                ▼
                         [PostgreSQL ML Tables]
```

---

## 🗄️ Database Schema

### 1. `user_preferences`

**Purpose:** Manage ML data collection consent (currently not enforced)

**Schema:**
```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- ML Consent (not currently enforced)
    ml_data_collection_consent BOOLEAN DEFAULT FALSE NOT NULL,
    ml_consent_date TIMESTAMP,

    -- Optional demographic data
    anonymized_industry VARCHAR(50),
    anonymized_company_size VARCHAR(20),

    -- Data retention
    data_retention_years VARCHAR(10) DEFAULT '3',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_user_prefs_user ON user_preferences(user_id);
CREATE INDEX idx_user_prefs_consent ON user_preferences(ml_data_collection_consent);
```

**Current Usage:** ⚠️ Table exists but consent not enforced (collection is automatic)

---

### 2. `ml_training_data`

**Purpose:** Store anonymized resource patterns for ML training

**Schema:**
```sql
CREATE TABLE ml_training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Anonymized identifiers (SHA256)
    account_hash VARCHAR(64) NOT NULL,
    resource_hash VARCHAR(64) NOT NULL,

    -- Resource metadata
    resource_type VARCHAR(50) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    region_anonymized VARCHAR(20) NOT NULL,
    resource_age_days INTEGER NOT NULL,

    -- Detection info
    detection_scenario VARCHAR(50) NOT NULL,
    confidence_level VARCHAR(20) NOT NULL,

    -- Metrics (anonymized aggregates)
    metrics_summary JSONB,

    -- Cost
    cost_monthly FLOAT NOT NULL,

    -- User action (nullable until action taken)
    user_action VARCHAR(30),

    -- Configuration (anonymized)
    resource_config JSONB,

    -- Timestamps
    detected_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_ml_training_resource_type ON ml_training_data(resource_type);
CREATE INDEX idx_ml_training_provider ON ml_training_data(provider);
CREATE INDEX idx_ml_training_region ON ml_training_data(region_anonymized);
CREATE INDEX idx_ml_training_scenario ON ml_training_data(detection_scenario);
CREATE INDEX idx_ml_training_confidence ON ml_training_data(confidence_level);
CREATE INDEX idx_ml_training_user_action ON ml_training_data(user_action);
CREATE INDEX idx_ml_training_detected_at ON ml_training_data(detected_at);
CREATE INDEX idx_ml_training_account ON ml_training_data(account_hash);
```

**Example Record:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "account_hash": "8f4e33f3df...hash...7d0f",
  "resource_hash": "a1b2c3d4e5...hash...f6g7",
  "resource_type": "ebs_volume",
  "provider": "aws",
  "region_anonymized": "us-*",
  "resource_age_days": 127,
  "detection_scenario": "idle_volume",
  "confidence_level": "high",
  "metrics_summary": {
    "VolumeReadOps": {"avg": 0.2, "p95": 1.5, "trend": "stable"},
    "VolumeWriteOps": {"avg": 0.0, "p95": 0.1, "trend": "stable"}
  },
  "cost_monthly": 45.20,
  "user_action": null,
  "resource_config": {"size_gb": 500, "volume_type": "gp3"},
  "detected_at": "2025-11-07T10:30:00Z",
  "created_at": "2025-11-07T10:30:00Z"
}
```

---

### 3. `resource_lifecycle_events`

**Purpose:** Track resource state changes over time

**Schema:**
```sql
CREATE TABLE resource_lifecycle_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Anonymized resource identifier
    resource_hash VARCHAR(64) NOT NULL,

    -- Event details
    event_type VARCHAR(30) NOT NULL,  -- detected, status_changed, deleted, metrics_updated
    resource_type VARCHAR(50) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    region_anonymized VARCHAR(20),

    -- State at event
    age_at_event_days INTEGER,
    cost_at_event FLOAT,
    metrics_snapshot JSONB,

    -- Timestamps
    event_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_lifecycle_resource ON resource_lifecycle_events(resource_hash);
CREATE INDEX idx_lifecycle_event_type ON resource_lifecycle_events(event_type);
CREATE INDEX idx_lifecycle_resource_type ON resource_lifecycle_events(resource_type);
CREATE INDEX idx_lifecycle_timestamp ON resource_lifecycle_events(event_timestamp);
CREATE INDEX idx_lifecycle_provider ON resource_lifecycle_events(provider);
```

**Use Case:** Time-series analysis of resource evolution

---

### 4. `cloudwatch_metrics_history`

**Purpose:** Extended CloudWatch metrics for time-series ML

**Schema:**
```sql
CREATE TABLE cloudwatch_metrics_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Resource info
    resource_hash VARCHAR(64) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    provider VARCHAR(20) NOT NULL,

    -- Metric info
    metric_name VARCHAR(100) NOT NULL,
    metric_values JSONB NOT NULL,  -- Time series data
    aggregation_period VARCHAR(20) NOT NULL,  -- hourly, daily, weekly

    -- Time range
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,

    -- Collection timestamp
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_cw_metrics_resource ON cloudwatch_metrics_history(resource_hash);
CREATE INDEX idx_cw_metrics_type ON cloudwatch_metrics_history(resource_type);
CREATE INDEX idx_cw_metrics_name ON cloudwatch_metrics_history(metric_name);
```

**Use Case:** Anomaly detection, trend analysis

---

### 5. `user_action_patterns`

**Purpose:** Track user decisions on resources

**Schema:**
```sql
CREATE TABLE user_action_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Anonymized identifiers
    user_hash VARCHAR(64) NOT NULL,
    account_hash VARCHAR(64) NOT NULL,
    resource_hash VARCHAR(64) NOT NULL,

    -- Resource info
    resource_type VARCHAR(50) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    region_anonymized VARCHAR(20),

    -- Detection context
    detection_scenario VARCHAR(50) NOT NULL,
    confidence_level VARCHAR(20) NOT NULL,

    -- User decision
    action_taken VARCHAR(30) NOT NULL,  -- deleted, ignored, kept
    time_to_action_hours INTEGER NOT NULL,

    -- Cost impact
    cost_monthly FLOAT NOT NULL,
    cost_saved_monthly FLOAT NOT NULL,

    -- Optional demographics (if provided)
    industry_anonymized VARCHAR(50),
    company_size_bucket VARCHAR(20),

    -- Timestamps
    detected_at TIMESTAMP NOT NULL,
    action_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_user_action_user ON user_action_patterns(user_hash);
CREATE INDEX idx_user_action_resource_type ON user_action_patterns(resource_type);
CREATE INDEX idx_user_action_scenario ON user_action_patterns(detection_scenario);
CREATE INDEX idx_user_action_action ON user_action_patterns(action_taken);
CREATE INDEX idx_user_action_detected ON user_action_patterns(detected_at);
CREATE INDEX idx_user_action_action_at ON user_action_patterns(action_at);
CREATE INDEX idx_user_action_provider ON user_action_patterns(provider);
```

**Use Case:** Learn which recommendations users accept/reject

---

### 6. `cost_trend_data`

**Purpose:** Monthly cost aggregation and trends

**Schema:**
```sql
CREATE TABLE cost_trend_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Anonymized account
    account_hash VARCHAR(64) NOT NULL,

    -- Time period
    month VARCHAR(7) NOT NULL,  -- YYYY-MM format

    -- Provider
    provider VARCHAR(20) NOT NULL,

    -- Cost metrics
    total_spend FLOAT NOT NULL,
    waste_detected FLOAT NOT NULL,
    waste_eliminated FLOAT NOT NULL,
    waste_percentage FLOAT NOT NULL,

    -- Breakdown
    top_waste_categories JSONB NOT NULL,
    regional_breakdown JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_cost_trend_account ON cost_trend_data(account_hash);
CREATE INDEX idx_cost_trend_month ON cost_trend_data(month);
CREATE INDEX idx_cost_trend_provider ON cost_trend_data(provider);
CREATE INDEX idx_cost_trend_waste_pct ON cost_trend_data(waste_percentage);
```

**Use Case:** Cost forecasting, budget prediction

---

## 🔧 Services Architecture

### 1. ML Data Collector

**File:** `backend/app/services/ml_data_collector.py`

**Key Functions:**

```python
async def collect_ml_training_data(
    scan: Scan,
    orphan_resources: List[OrphanResource],
    user: User,
    db: AsyncSession
) -> int:
    """
    Collect anonymized ML training data from scan results.
    Returns number of records created.
    """

async def collect_resource_lifecycle_event(
    resource_hash: str,
    event_type: str,
    resource_type: str,
    db: AsyncSession
) -> None:
    """Record resource lifecycle event."""

async def collect_cloudwatch_metrics_history(
    resource_hash: str,
    resource_type: str,
    metrics: Dict,
    db: AsyncSession
) -> None:
    """Store extended CloudWatch metrics."""

async def aggregate_monthly_cost_trends(
    cloud_account: CloudAccount,
    month: str,
    scan: Scan,
    orphan_resources: List[OrphanResource],
    db: AsyncSession
) -> None:
    """Aggregate monthly cost trends."""

async def update_ml_training_data_with_user_action(
    resource_hash: str,
    user_action: str,
    db: AsyncSession
) -> None:
    """Update ML record when user takes action."""
```

---

### 2. Anonymization Service

**File:** `backend/app/services/ml_anonymization.py`

**Key Functions:**

```python
def anonymize_user_id(user_id: str) -> str:
    """SHA256 hash with salt."""
    salt = settings.SECRET_KEY
    hash_input = f"{user_id}{salt}".encode()
    return hashlib.sha256(hash_input).hexdigest()

def anonymize_account_id(account_id: str) -> str:
    """Anonymize cloud account ID."""

def anonymize_resource_id(resource_id: str) -> str:
    """Anonymize resource identifier."""

def anonymize_region(region: str) -> str:
    """Generalize region (us-east-1 → us-*, eu-west-3 → eu-*)."""

def anonymize_metrics(metrics: Dict) -> Dict:
    """Keep only aggregates (avg, p50, p95, p99, trend)."""

def calculate_trend(timeseries: List[float]) -> str:
    """Returns: increasing, decreasing, stable, volatile."""

def anonymize_resource_config(config: Dict) -> Dict:
    """Whitelist safe fields (size, type, SKU), remove PII."""
```

**Security:**
- Uses `settings.SECRET_KEY` as salt for all hashes
- SHA256 for consistent anonymization
- No identifiable data stored

---

### 3. User Action Tracker

**File:** `backend/app/services/user_action_tracker.py`

**Key Function:**

```python
async def track_user_action(
    resource: OrphanResource,
    action: str,  # deleted, ignored, kept
    user: User,
    cloud_account: CloudAccount,
    db: AsyncSession
) -> None:
    """
    Record user action anonymously.
    Called when user updates resource status.
    """
```

**Integration:** Called from `backend/app/api/v1/resources.py` on PATCH `/resources/{id}`

---

### 4. ML Data Pipeline

**File:** `backend/app/ml/data_pipeline.py`

**Key Functions:**

```python
async def export_ml_training_dataset(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json"
) -> str:
    """Export ML training data to JSON/CSV."""

async def export_user_action_patterns(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json"
) -> str:
    """Export user action patterns."""

async def export_cost_trends(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json"
) -> str:
    """Export cost trends."""

async def validate_data_quality(df) -> Dict[str, Any]:
    """Validate exported data quality."""

async def export_all_ml_datasets(
    output_format: str = "json",
    output_dir: str = "./ml_datasets"
) -> Dict[str, str]:
    """Export all datasets at once."""
```

---

## 🔄 Data Collection Flow

### Scan Flow (AWS/Azure)

```
1. User triggers scan (manual or scheduled)
       ↓
2. Celery task: _scan_cloud_account_async()
       ↓
3. AWS/Azure provider scans resources
       ↓
4. Scanner detects orphan resources
       ↓
5. Resources saved to orphan_resources table
       ↓
6. ✨ ML Data Collector triggered:
       ├─ collect_ml_training_data()
       ├─ collect_resource_lifecycle_event()
       ├─ collect_cloudwatch_metrics_history()
       └─ aggregate_monthly_cost_trends()
       ↓
7. Data saved to 6 ML tables (anonymized)
       ↓
8. Admin can view stats in admin panel
       ↓
9. Admin can export datasets (JSON/CSV)
```

### User Action Flow

```
1. User updates resource status (via UI)
       ↓
2. PATCH /api/v1/resources/{id}
       ↓
3. Status updated in orphan_resources table
       ↓
4. ✨ track_user_action() called
       ├─ Record action in user_action_patterns
       ├─ Update ml_training_data with user_action
       └─ Update cost_trend_data if deleted
       ↓
5. Data ready for ML training
```

---

## 📊 Data Export Architecture

### Admin Panel Export

```
1. Admin clicks export button
       ↓
2. POST /api/v1/admin/ml-export?days=90&output_format=json
       ↓
3. Backend calls export_all_ml_datasets()
       ├─ export_ml_training_dataset()
       ├─ export_user_action_patterns()
       └─ export_cost_trends()
       ↓
4. Files created in ./ml_datasets/
       ├─ ml_training_data_20251107.json
       ├─ user_action_patterns_20251107.json
       └─ cost_trends_20251107.json
       ↓
5. Return file paths + record counts
```

---

## 🔐 Security & Anonymization

### Anonymization Layers

**Layer 1: Hash Identifiers**
- User IDs → SHA256(user_id + salt)
- Account IDs → SHA256(account_id + salt)
- Resource IDs → SHA256(resource_id + salt)

**Layer 2: Generalize Locations**
- us-east-1, us-west-2 → us-*
- eu-west-1, eu-central-1 → eu-*
- ap-southeast-1, ap-northeast-1 → ap-*

**Layer 3: Aggregate Metrics**
- Store only: avg, p50, p95, p99, trend
- Remove absolute values that could identify resources

**Layer 4: Whitelist Config**
- Keep: size, type, SKU, performance tier
- Remove: names, tags with PII, custom identifiers

**Result:** No personally identifiable information stored

---

## 🎯 Use Cases & Features

### Use Case 1: Waste Prediction (Classification)
**ML Tables Used:**
- `ml_training_data` (features: resource_age_days, metrics_summary, detection_scenario)
- `user_action_patterns` (target: action_taken = deleted vs kept)

**Model:** Binary Classification (RandomForest, XGBoost)
**Accuracy Target:** 80-90%

---

### Use Case 2: Anomaly Detection
**ML Tables Used:**
- `cloudwatch_metrics_history` (time series)
- `cost_trend_data` (deviation from baseline)

**Model:** Isolation Forest, Autoencoder
**Output:** Anomaly score (0-100)

---

### Use Case 3: Smart Rightsizing
**ML Tables Used:**
- `cloudwatch_metrics_history` (CPU/RAM usage)
- `ml_training_data` (current instance size)
- `user_action_patterns` (accepted recommendations)

**Model:** Regression
**Output:** Recommended instance type + confidence

---

### Use Case 4: Cost Forecasting
**ML Tables Used:**
- `cost_trend_data` (monthly historical spend)

**Model:** Time Series (Prophet, ARIMA, LSTM)
**Output:** Predicted spend next 3-6 months ±10%

---

## 📈 Scalability Considerations

**Current Capacity:**
- PostgreSQL handles 1M+ records easily
- Indexes on all query-heavy columns
- JSON fields for flexible schema

**Future Optimizations:**
- Partition tables by date (when 10M+ records)
- Archive old data (> 3 years) to S3
- Consider TimescaleDB for time-series metrics

---

**See Also:**
- [Current Status](./01_CURRENT_STATUS.md) - What's working
- [Usage Guide](./03_USAGE_GUIDE.md) - How to use
- [Next Phases](./04_NEXT_PHASES.md) - Roadmap
