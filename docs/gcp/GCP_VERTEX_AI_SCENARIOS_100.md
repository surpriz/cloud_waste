# CloudWaste - Couverture 100% GCP Vertex AI

**Resource Type:** `AI/ML : Vertex AI`
**Provider:** Google Cloud Platform (GCP)
**API:** `aiplatform.googleapis.com` (Vertex AI API v1)
**Équivalents:** AWS SageMaker, Azure Machine Learning
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing Vertex AI](#modèle-de-pricing-vertex-ai)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Endpoints Jamais Utilisés](#1-vertex_ai_zero_predictions---endpoints-jamais-utilisés)
  - [2. Endpoints Idle](#2-vertex_ai_idle_endpoints---endpoints-idle-10-predictionsjo

ur)
  - [3. GPU Waste](#3-vertex_ai_gpu_waste---gpu-endpoint-mais-cpu-inference-suffit)
  - [4. Machines Over-Provisioned](#4-vertex_ai_overprovisioned_machines---machines-over-provisioned)
  - [5. Dev/Test Endpoints 24/7](#5-vertex_ai_devtest_247---devtest-endpoints-247)
  - [6. Old Model Versions](#6-vertex_ai_old_model_versions---old-model-versions)
  - [7. Endpoints Non Tagués](#7-vertex_ai_untagged_endpoints---endpoints-non-tagués)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Traffic Split Inutile](#8-vertex_ai_unused_traffic_split---traffic-split-inutile)
  - [9. Training Jobs Failed](#9-vertex_ai_failed_training_jobs---training-jobs-failedabandoned)
  - [10. Feature Store Unused](#10-vertex_ai_unused_feature_store---feature-store-unused)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte Vertex AI

**Vertex AI** est la plateforme **ML unifiée** de GCP, offrant :

- **Model Training** (Custom + AutoML)
- **Model Serving** (Endpoints real-time predictions)
- **Workbench** (Managed Jupyter notebooks)
- **Feature Store** (Feature management)
- **Pipelines** (MLOps workflows)
- **Monitoring** (Model performance tracking)

### Architecture Vertex AI

```
Vertex AI Platform
├── Models Registry
│   ├── Trained models
│   ├── Model versions
│   └── Model artifacts
├── Endpoints (Serving)
│   ├── Deployed models
│   ├── Traffic split (A/B)
│   ├── Machine instances (CPU/GPU)
│   └── Autoscaling config
├── Training
│   ├── Custom training jobs
│   ├── AutoML
│   └── Hyperparameter tuning
├── Workbench (Notebooks)
│   ├── User-managed notebooks
│   └── Managed notebooks
├── Feature Store
│   ├── Entity types
│   ├── Features
│   └── Online/Batch serving
└── Pipelines (Kubeflow)
    └── ML workflows
```

### Caractéristiques Principales

| Composant | Description | Coût Typique |
|-----------|-------------|--------------|
| **Endpoints** | Real-time model serving | $112-1,072/mois |
| **GPUs** | NVIDIA T4, V100, A100 | $350-1,460/mois |
| **Training** | Custom jobs + AutoML | $1-100/job |
| **Workbench** | Managed notebooks | $112-1,072/mois |
| **Feature Store** | Feature management | $70-500/mois |
| **Predictions** | API calls | $0.05-0.50/1K predictions |

### Endpoints Types

| Type | Use Case | Machine | GPU | Coût/Mois |
|------|----------|---------|-----|-----------|
| **Small CPU** | Low traffic | n1-standard-2 | - | $56 |
| **Standard CPU** | Medium traffic | n1-standard-4 | - | $112 |
| **Large CPU** | High traffic | n1-standard-8 | - | $225 |
| **GPU T4** | GPU inference | n1-standard-4 | T4 | $462 |
| **GPU V100** | High-perf GPU | n1-highmem-4 | V100 | $1,594 |
| **GPU A100** | Latest GPU | n1-highmem-8 | A100 | $1,072 |

### Waste Typique

1. **Endpoints jamais utilisés** : $112-1,072/mois par endpoint = 100% waste
2. **GPU inutile** : $350-1,460/mois surcoût vs CPU
3. **Dev/test 24/7** : $112/mois × 3 environnements = $336/mois waste
4. **Over-provisioned machines** : n1-standard-8 ($225) au lieu de n1-standard-4 ($112)
5. **Training jobs failed** : $50-500 waste par job failed
6. **Workbench 24/7** : $112-1,072/mois si jamais arrêté
7. **Feature store unused** : $70-500/mois storage + serving

---

## Modèle de Pricing Vertex AI

### Endpoints Pricing (Model Serving)

#### Machine Types - CPU Only

| Machine Type | vCPUs | Memory (GB) | Prix/Heure | Prix/Mois (730h) |
|--------------|-------|-------------|-----------|------------------|
| **n1-standard-1** | 1 | 3.75 | $0.0385 | $28.11 |
| **n1-standard-2** | 2 | 7.5 | $0.0770 | $56.21 |
| **n1-standard-4** | 4 | 15 | $0.1540 | $112.42 |
| **n1-standard-8** | 8 | 30 | $0.3080 | $224.84 |
| **n1-standard-16** | 16 | 60 | $0.6160 | $449.68 |
| **n1-highmem-2** | 2 | 13 | $0.0920 | $67.16 |
| **n1-highmem-4** | 4 | 26 | $0.1840 | $134.32 |
| **n1-highmem-8** | 8 | 52 | $0.3680 | $268.64 |
| **n1-highcpu-4** | 4 | 3.6 | $0.1100 | $80.30 |
| **n1-highcpu-8** | 8 | 7.2 | $0.2200 | $160.60 |

#### GPUs Pricing

| GPU Type | GPU Memory | Prix/Heure | Prix/Mois (730h) | Use Case |
|----------|-----------|-----------|------------------|----------|
| **NVIDIA T4** | 16 GB | $0.48 | $350.40 | General GPU inference |
| **NVIDIA V100** | 16 GB | $2.00 | $1,460.00 | High-performance inference |
| **NVIDIA P4** | 8 GB | $0.70 | $511.00 | Medium GPU inference |
| **NVIDIA P100** | 16 GB | $1.60 | $1,168.00 | Training + inference |
| **NVIDIA A100 (40GB)** | 40 GB | $1.10 | $803.00 | Latest generation |
| **NVIDIA A100 (80GB)** | 80 GB | $1.65 | $1,204.50 | Large models |

**Note :** Les GPUs sont attachés à une machine type (CPU + Memory), donc coût total = Machine + GPU

#### Exemples Endpoints

**Exemple 1 : Small CPU Endpoint**
```
Machine: n1-standard-2
GPU: None
─────────────────────────────
Machine: $56.21/mois
GPU: $0
─────────────────────────────
TOTAL: $56.21/mois
```

**Exemple 2 : Standard CPU Endpoint**
```
Machine: n1-standard-4
GPU: None
─────────────────────────────
Machine: $112.42/mois
GPU: $0
─────────────────────────────
TOTAL: $112.42/mois
```

**Exemple 3 : GPU T4 Endpoint (Most Common)**
```
Machine: n1-standard-4 (4 vCPU, 15 GB)
GPU: NVIDIA T4 (16 GB)
─────────────────────────────
Machine: $112.42/mois
GPU: $350.40/mois
─────────────────────────────
TOTAL: $462.82/mois
```

**Exemple 4 : High-End GPU A100 Endpoint**
```
Machine: n1-highmem-8 (8 vCPU, 52 GB)
GPU: NVIDIA A100 40GB
─────────────────────────────
Machine: $268.64/mois
GPU: $803.00/mois
─────────────────────────────
TOTAL: $1,071.64/mois
```

---

### Training Jobs Pricing

#### Custom Training

Pricing basé sur Compute Engine machines + GPUs :

**Exemple 1 : CPU Training (10 heures)**
```
Machine: n1-standard-4 ($0.154/h)
Duration: 10 hours
─────────────────────────────
Cost: 10 × $0.154 = $1.54
```

**Exemple 2 : GPU T4 Training (5 heures)**
```
Machine: n1-standard-4 ($0.154/h)
GPU: T4 ($0.48/h)
Duration: 5 hours
─────────────────────────────
Machine: 5 × $0.154 = $0.77
GPU: 5 × $0.48 = $2.40
─────────────────────────────
TOTAL: $3.17
```

**Exemple 3 : Multi-GPU Training (8 heures, 4× V100)**
```
Machine: n1-highmem-16 ($0.736/h)
GPU: 4× V100 (4 × $2.00/h = $8.00/h)
Duration: 8 hours
─────────────────────────────
Machine: 8 × $0.736 = $5.89
GPU: 8 × $8.00 = $64.00
─────────────────────────────
TOTAL: $69.89
```

#### AutoML Training

| Model Type | Training | Deployment (per node hour) |
|-----------|----------|---------------------------|
| **AutoML Tables** | $19.32/node hour | $76.65/node hour |
| **AutoML Vision** | $3.15/node hour | $1.25/node hour |
| **AutoML NLP** | $3.00/node hour | $5.00/node hour |

**Exemple AutoML Tables (5 heures training)** :
```
Training: 5 × $19.32 = $96.60
```

---

### Workbench (Notebooks) Pricing

Workbench utilise le même pricing que Compute Engine :

| Configuration | Prix/Heure | Prix/Mois (8h/j, 22j) | Prix/Mois (24/7) |
|---------------|-----------|----------------------|-----------------|
| **n1-standard-4 (CPU)** | $0.154 | $27.10 | $112.42 |
| **n1-standard-4 + T4** | $0.634 | $111.57 | $462.82 |
| **n1-highmem-8 (CPU)** | $0.368 | $64.74 | $268.64 |
| **n1-highmem-8 + A100** | $1.468 | $258.30 | $1,071.64 |

**Waste typique :** Notebooks running 24/7 au lieu de 8h/jour = 3x surcoût

---

### Feature Store Pricing

| Component | Prix | Unité |
|-----------|------|-------|
| **Online serving reads** | $0.35 | per 1M reads |
| **Batch serving reads** | $0.05 | per 1M reads |
| **Storage** | $0.70 | per GB/mois |

**Exemple Feature Store (100 GB, 500M reads/mois)** :
```
Storage: 100 GB × $0.70 = $70/mois
Online reads: 500M × $0.35/1M = $175/mois
─────────────────────────────
TOTAL: $245/mois
```

---

### Predictions Pricing

| Prediction Type | Prix | Notes |
|----------------|------|-------|
| **Online predictions** | Included in endpoint cost | No per-prediction fee |
| **Batch predictions** | $0.05 per 1K predictions | Plus compute costs |

---

### Exemples Coûts Mensuels

#### Scénario 1 : Startup ML (1 endpoint, 1 notebook)

```
Endpoint:
- n1-standard-4 (prod, 24/7) = $112.42

Workbench:
- n1-standard-4 (8h/j, 22j) = $27.10

Training:
- 2 jobs/mois × 10h × $0.154 = $3.08

─────────────────────────────
TOTAL: $142.60/mois (~$1,711/an)
```

#### Scénario 2 : PME ML Platform (3 endpoints, 1 GPU, 3 notebooks)

```
Endpoints:
- Prod CPU (n1-standard-4, 24/7) = $112.42
- Dev CPU (n1-standard-2, 24/7) = $56.21
- GPU endpoint (n1-standard-4 + T4, 24/7) = $462.82

Workbench (8h/j, 22j):
- Data Scientist 1 (n1-standard-4) = $27.10
- Data Scientist 2 (n1-standard-4) = $27.10
- ML Engineer (n1-standard-4 + T4) = $111.57

Training:
- 10 jobs/mois × 8h × $0.634 = $50.72

─────────────────────────────
TOTAL: $847.94/mois (~$10,175/an)
```

#### Scénario 3 : Entreprise ML (10 endpoints, GPUs, feature store)

```
Endpoints:
- 5 prod CPU (5 × $112.42) = $562.10
- 2 GPU T4 (2 × $462.82) = $925.64
- 3 dev/staging (3 × $56.21) = $168.63

Workbench (8h/j, 22j):
- 5 data scientists (5 × $27.10) = $135.50
- 2 ML engineers avec GPU (2 × $111.57) = $223.14

Training:
- 50 jobs/mois × 8h × $0.634 = $253.60

Feature Store:
- Storage (200 GB) = $140
- Online reads (1B reads) = $350

─────────────────────────────
TOTAL: $2,758.61/mois (~$33,103/an)
```

#### Scénario 4 : Waste Typique (Avant CloudWaste)

```
Endpoints:
- 3 prod actifs (3 × $112) = $336 ✅
- 5 dev/test jamais utilisés (5 × $112) = $560 ❌ WASTE
- 2 GPU (CPU suffit) (2 × $350) = $700 ❌ WASTE
- 1 over-provisioned (n1-standard-8 vs 4) = $112 ❌ WASTE

Workbench (24/7 au lieu de 8h/j):
- 3 notebooks (3 × $112) = $336
- Devrait être: 3 × $27 = $81
- Waste: $255 ❌ WASTE

Training:
- 20 failed jobs (20 × $30) = $600 ❌ WASTE

Feature Store:
- Unused (100 GB + 0 reads) = $70 ❌ WASTE

─────────────────────────────
TOTAL: $2,969/mois
WASTE: $2,297/mois (~$27,564/an) = 77% ❌
OPTIMAL: $672/mois (~$8,064/an)
```

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `vertex_ai_zero_predictions` - Endpoints Jamais Utilisés

#### Détection

**Logique :**
```python
# 1. Lister tous les endpoints Vertex AI
from google.cloud import aiplatform

aiplatform.init(project=project_id, location=region)

endpoints = aiplatform.Endpoint.list()

# 2. Pour chaque endpoint, récupérer métriques predictions (30 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for endpoint in endpoints:
    endpoint_id = endpoint.name.split('/')[-1]

    # 3. Query Cloud Monitoring pour prediction_count
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 30*24*3600},
    })

    # Métrique: aiplatform.googleapis.com/prediction/prediction_count
    metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="aiplatform.googleapis.com/Endpoint" '
                     f'AND resource.endpoint_id="{endpoint_id}" '
                     f'AND metric.type="aiplatform.googleapis.com/prediction/prediction_count"',
            "interval": interval,
        }
    )

    # 4. Calculer total predictions
    total_predictions = sum([
        point.value.int64_value
        for series in metrics
        for point in series.points
    ])

    # 5. Détection si 0 predictions
    if total_predictions == 0:
        # Endpoint jamais utilisé = 100% waste

        # Calculer coût endpoint
        deployed_models = endpoint.list_models()

        for model in deployed_models:
            machine_type = model.machine_spec.machine_type
            accelerator_type = model.machine_spec.accelerator_type if model.machine_spec.accelerator_type else None

            # Calculer coût mensuel
            monthly_cost = calculate_endpoint_cost(machine_type, accelerator_type)
```

**Critères :**
- `total_predictions == 0` sur 30 jours
- Endpoint actif (deployed models)
- Age >7 jours (éviter faux positifs nouveaux endpoints)

**API Calls :**
```python
# Vertex AI API
from google.cloud import aiplatform

aiplatform.init(project=project_id, location=region)
endpoints = aiplatform.Endpoint.list()
endpoint = aiplatform.Endpoint(endpoint_name)
deployed_models = endpoint.list_models()

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="aiplatform.googleapis.com/prediction/prediction_count"'
)
```

#### Calcul de Coût

**Formule :**

Endpoint jamais utilisé = 100% waste :

```python
# Récupérer machine specs
machine_type = model.machine_spec.machine_type  # e.g., "n1-standard-4"
accelerator_type = model.machine_spec.accelerator_type  # e.g., "NVIDIA_TESLA_T4"
accelerator_count = model.machine_spec.accelerator_count or 0

# Machine pricing (par heure)
machine_pricing = {
    'n1-standard-1': 0.0385,
    'n1-standard-2': 0.0770,
    'n1-standard-4': 0.1540,
    'n1-standard-8': 0.3080,
    'n1-highmem-4': 0.1840,
    'n1-highmem-8': 0.3680,
}

machine_cost_per_hour = machine_pricing.get(machine_type, 0.1540)

# GPU pricing (par heure, par GPU)
gpu_pricing = {
    'NVIDIA_TESLA_T4': 0.48,
    'NVIDIA_TESLA_V100': 2.00,
    'NVIDIA_TESLA_P4': 0.70,
    'NVIDIA_TESLA_P100': 1.60,
    'NVIDIA_TESLA_A100': 1.10,
    'NVIDIA_A100_80GB': 1.65,
}

gpu_cost_per_hour = gpu_pricing.get(accelerator_type, 0) * accelerator_count

# Coût total par heure
total_cost_per_hour = machine_cost_per_hour + gpu_cost_per_hour

# Coût mensuel (730 heures)
hours_per_month = 730
monthly_cost = total_cost_per_hour * hours_per_month

# Endpoint jamais utilisé = 100% waste
monthly_waste = monthly_cost

# Coût gaspillé depuis création
age_days = (now - endpoint.create_time).days
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Endpoint n1-standard-4 + T4 GPU jamais utilisé depuis 90 jours :
```python
machine_cost = 0.1540 * 730 = $112.42
gpu_cost = 0.48 * 730 = $350.40
monthly_cost = $462.82
already_wasted = $462.82 * (90/30) = $1,388.46
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `zero_predictions_days` | int | 30 | Période sans predictions pour détection |
| `min_age_days` | int | 7 | Âge minimum endpoint |
| `min_cost_threshold` | float | 50.0 | Coût minimum pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/456",
  "resource_name": "unused-ml-endpoint",
  "resource_type": "vertex_ai_zero_predictions",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "456",
  "creation_time": "2024-08-01T10:00:00Z",
  "age_days": 93,
  "deployed_models": [
    {
      "model_id": "model-789",
      "model_display_name": "my_model_v1",
      "machine_type": "n1-standard-4",
      "accelerator_type": "NVIDIA_TESLA_T4",
      "accelerator_count": 1,
      "min_replica_count": 1,
      "max_replica_count": 1
    }
  ],
  "prediction_metrics_30d": {
    "total_predictions": 0,
    "avg_predictions_per_day": 0.0
  },
  "machine_cost_monthly": 112.42,
  "gpu_cost_monthly": 350.40,
  "estimated_monthly_cost": 462.82,
  "already_wasted": 1435.74,
  "confidence": "high",
  "recommendation": "Delete endpoint - zero predictions in 30 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `vertex_ai_idle_endpoints` - Endpoints Idle (<10 Predictions/Jour)

#### Détection

**Logique :**
```python
# 1. Lister endpoints (même que scénario 1)
endpoints = aiplatform.Endpoint.list()

# 2. Pour chaque endpoint, calculer avg predictions/jour
for endpoint in endpoints:
    # Query predictions sur 30 jours
    total_predictions = get_prediction_count(endpoint, days=30)

    # 3. Calculer moyenne quotidienne
    avg_predictions_per_day = total_predictions / 30.0

    # 4. Détection si très faible usage
    if avg_predictions_per_day < idle_threshold_predictions_per_day:
        # Endpoint idle = candidate for batch predictions ou deletion

        # Vérifier si batch predictions serait moins cher
        # Batch prediction: $0.05/1K predictions + compute
        # Real-time endpoint: $112-1,072/mois

        monthly_predictions = total_predictions  # Estimé pour 30j
        batch_cost = (monthly_predictions / 1000) * 0.05

        # Coût endpoint actuel
        endpoint_cost = calculate_endpoint_cost(endpoint)

        if batch_cost < endpoint_cost * 0.10:  # Batch <10% du coût endpoint
            # Recommandation: migrer vers batch predictions
            potential_savings = endpoint_cost - batch_cost
```

**Critères :**
- `avg_predictions_per_day < 10` (configurable)
- Endpoint actif (deployed models)
- Batch prediction serait plus économique

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="aiplatform.googleapis.com/prediction/prediction_count"'
)
```

#### Calcul de Coût

**Formule :**

Endpoint idle → Batch predictions :

```python
# Endpoint actuel
monthly_endpoint_cost = calculate_endpoint_cost(endpoint)

# Batch predictions alternative
monthly_predictions = avg_predictions_per_day * 30
batch_predictions_cost = (monthly_predictions / 1000) * 0.05  # $0.05/1K

# Compute cost pour batch (estimé)
# Hypothèse: 1 job/jour × 1h × machine type
jobs_per_month = 30
job_duration_hours = 1
compute_cost_per_hour = machine_pricing.get(machine_type, 0.1540)
batch_compute_cost = jobs_per_month * job_duration_hours * compute_cost_per_hour

# Coût total batch
total_batch_cost = batch_predictions_cost + batch_compute_cost

# Waste = différence
monthly_waste = monthly_endpoint_cost - total_batch_cost

# Si batch >90% moins cher → recommandation migration
if total_batch_cost < (monthly_endpoint_cost * 0.10):
    savings_percentage = ((monthly_endpoint_cost - total_batch_cost) / monthly_endpoint_cost) * 100
```

**Exemple :**

Endpoint n1-standard-4 avec 5 predictions/jour (150/mois) :
```python
monthly_endpoint_cost = $112.42

# Batch alternative
batch_predictions_cost = (150 / 1000) * 0.05 = $0.0075
batch_compute_cost = 30 × 1 × 0.1540 = $4.62
total_batch_cost = $4.63

# Waste
monthly_waste = $112.42 - $4.63 = $107.79
savings_percentage = 96%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `idle_threshold_predictions_per_day` | float | 10.0 | Predictions/jour max pour idle |
| `lookback_days` | int | 30 | Période analyse usage |
| `batch_cost_threshold_pct` | float | 0.10 | % coût endpoint pour recommandation batch |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/789",
  "resource_name": "low-traffic-endpoint",
  "resource_type": "vertex_ai_idle_endpoints",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "789",
  "machine_type": "n1-standard-4",
  "accelerator_type": null,
  "prediction_metrics_30d": {
    "total_predictions": 150,
    "avg_predictions_per_day": 5.0
  },
  "current_monthly_cost": 112.42,
  "recommended_approach": "batch_predictions",
  "batch_predictions_cost": 0.01,
  "batch_compute_cost": 4.62,
  "recommended_monthly_cost": 4.63,
  "estimated_monthly_waste": 107.79,
  "savings_percentage": 95.9,
  "confidence": "high",
  "recommendation": "Migrate to batch predictions - 96% cost reduction for low traffic",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `vertex_ai_gpu_waste` - GPU Endpoint Mais CPU Inference Suffit

#### Détection

**Logique :**
```python
# 1. Lister endpoints avec GPU
endpoints = aiplatform.Endpoint.list()

for endpoint in endpoints:
    deployed_models = endpoint.list_models()

    for model in deployed_models:
        accelerator_type = model.machine_spec.accelerator_type

        # 2. Filtrer uniquement endpoints GPU
        if accelerator_type:
            # 3. Query GPU utilization metrics (14 jours)
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(time.time())},
                "start_time": {"seconds": int(time.time()) - 14*24*3600},
            })

            # Métrique: aiplatform.googleapis.com/prediction/online/accelerator_duty_cycle
            gpu_metrics = monitoring_client.list_time_series(
                request={
                    "name": f"projects/{project_id}",
                    "filter": f'resource.type="aiplatform.googleapis.com/Endpoint" '
                             f'AND resource.endpoint_id="{endpoint.name.split("/")[-1]}" '
                             f'AND metric.type="aiplatform.googleapis.com/prediction/online/accelerator_duty_cycle"',
                    "interval": interval,
                }
            )

            # 4. Calculer avg GPU utilization
            gpu_values = [
                point.value.double_value
                for series in gpu_metrics
                for point in series.points
            ]

            avg_gpu_utilization = (sum(gpu_values) / len(gpu_values) * 100) if gpu_values else 0

            # 5. Détection si GPU underutilized
            if avg_gpu_utilization < gpu_utilization_threshold:
                # GPU inutile, CPU suffit
                # Calculer économie en retirant GPU

                gpu_cost = get_gpu_cost(accelerator_type) * 730  # $/mois

                # Waste = coût GPU
                monthly_waste = gpu_cost
```

**Critères :**
- `accelerator_type IS NOT NULL` (endpoint has GPU)
- `avg_gpu_utilization < 30%` sur 14 jours
- Predictions actives (pas endpoint unused)

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()
deployed_models = endpoint.list_models()

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="aiplatform.googleapis.com/prediction/online/accelerator_duty_cycle"'
)
```

#### Calcul de Coût

**Formule :**

GPU → CPU migration = -75-90% coût :

```python
# Endpoint actuel (avec GPU)
machine_cost = machine_pricing.get(machine_type, 0.1540) * 730
gpu_cost = gpu_pricing.get(accelerator_type, 0.48) * 730
current_cost = machine_cost + gpu_cost

# Endpoint recommandé (CPU only)
recommended_cost = machine_cost  # Même machine, sans GPU

# Waste = coût GPU
monthly_waste = gpu_cost

# Savings percentage
savings_percentage = (gpu_cost / current_cost) * 100
```

**Exemple :**

Endpoint n1-standard-4 + T4 GPU avec GPU utilization 15% :
```python
machine_cost = 0.1540 * 730 = $112.42
gpu_cost = 0.48 * 730 = $350.40
current_cost = $462.82

recommended_cost = $112.42 (CPU only)
monthly_waste = $350.40
savings_percentage = 75.7%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `gpu_utilization_threshold` | float | 30.0 | GPU % utilization max |
| `lookback_days` | int | 14 | Période analyse GPU metrics |
| `min_gpu_cost_threshold` | float | 100.0 | Coût GPU min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/111",
  "resource_name": "cpu-model-on-gpu",
  "resource_type": "vertex_ai_gpu_waste",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "111",
  "machine_type": "n1-standard-4",
  "accelerator_type": "NVIDIA_TESLA_T4",
  "accelerator_count": 1,
  "gpu_metrics_14d": {
    "avg_gpu_utilization": 18.3,
    "max_gpu_utilization": 42.1
  },
  "machine_cost_monthly": 112.42,
  "gpu_cost_monthly": 350.40,
  "current_monthly_cost": 462.82,
  "recommended_machine_type": "n1-standard-4",
  "recommended_accelerator": null,
  "recommended_monthly_cost": 112.42,
  "estimated_monthly_waste": 350.40,
  "savings_percentage": 75.7,
  "confidence": "high",
  "recommendation": "Remove GPU - average utilization 18% (CPU inference sufficient)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `vertex_ai_overprovisioned_machines` - Machines Over-Provisioned

#### Détection

**Logique :**
```python
# 1. Lister endpoints
endpoints = aiplatform.Endpoint.list()

for endpoint in endpoints:
    deployed_models = endpoint.list_models()

    for model in deployed_models:
        machine_type = model.machine_spec.machine_type

        # 2. Query CPU utilization metrics (14 jours)
        cpu_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="aiplatform.googleapis.com/Endpoint" '
                         f'AND resource.endpoint_id="{endpoint.name.split("/")[-1]}" '
                         f'AND metric.type="aiplatform.googleapis.com/prediction/online/cpu/utilization"',
                "interval": interval,
            }
        )

        # 3. Calculer avg CPU utilization
        cpu_values = [
            point.value.double_value
            for series in cpu_metrics
            for point in series.points
        ]

        avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

        # 4. Détection si CPU très faible
        if avg_cpu < cpu_threshold:
            # Machine over-provisioned
            # Recommander downgrade

            # Mapping downgrade
            downgrade_map = {
                'n1-standard-16': 'n1-standard-8',
                'n1-standard-8': 'n1-standard-4',
                'n1-standard-4': 'n1-standard-2',
                'n1-highmem-8': 'n1-highmem-4',
                'n1-highmem-4': 'n1-highmem-2',
            }

            recommended_machine = downgrade_map.get(machine_type)

            if recommended_machine:
                # Calculer économie
                current_cost = machine_pricing.get(machine_type, 0.1540) * 730
                recommended_cost = machine_pricing.get(recommended_machine, 0.0770) * 730
                monthly_waste = current_cost - recommended_cost
```

**Critères :**
- `avg_cpu < 10%` sur 14 jours
- Downgrade machine type possible
- Predictions actives (pas endpoint unused)

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="aiplatform.googleapis.com/prediction/online/cpu/utilization"'
)
```

#### Calcul de Coût

**Formule :**

Downgrade machine type = -50% coût :

```python
# Machine actuelle
current_machine = 'n1-standard-8'
current_cost_per_hour = machine_pricing.get(current_machine, 0.3080)
current_monthly_cost = current_cost_per_hour * 730

# Machine recommandée
recommended_machine = 'n1-standard-4'
recommended_cost_per_hour = machine_pricing.get(recommended_machine, 0.1540)
recommended_monthly_cost = recommended_cost_per_hour * 730

# Waste
monthly_waste = current_monthly_cost - recommended_monthly_cost

# Savings percentage
savings_percentage = (monthly_waste / current_monthly_cost) * 100
```

**Exemple :**

Endpoint n1-standard-8 avec CPU 8% → downgrade n1-standard-4 :
```python
current_cost = 0.3080 * 730 = $224.84
recommended_cost = 0.1540 * 730 = $112.42
monthly_waste = $112.42
savings_percentage = 50%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 10.0 | CPU % max pour over-provisioning |
| `lookback_days` | int | 14 | Période analyse CPU |
| `min_savings_threshold` | float | 50.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/222",
  "resource_name": "overprovisioned-endpoint",
  "resource_type": "vertex_ai_overprovisioned_machines",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "222",
  "machine_type": "n1-standard-8",
  "cpu_metrics_14d": {
    "avg_cpu_utilization": 9.2,
    "max_cpu_utilization": 18.5
  },
  "current_monthly_cost": 224.84,
  "recommended_machine_type": "n1-standard-4",
  "recommended_monthly_cost": 112.42,
  "estimated_monthly_waste": 112.42,
  "savings_percentage": 50.0,
  "confidence": "high",
  "recommendation": "Downgrade from n1-standard-8 to n1-standard-4 - 50% cost reduction",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `vertex_ai_devtest_247` - Dev/Test Endpoints 24/7

#### Détection

**Logique :**
```python
# 1. Lister endpoints
endpoints = aiplatform.Endpoint.list()

# 2. Pour chaque endpoint, vérifier labels
for endpoint in endpoints:
    labels = endpoint.labels if endpoint.labels else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test
    if environment in devtest_labels:
        # Dev/test endpoint running 24/7 = waste

        # Vérifier si endpoint toujours actif
        deployed_models = endpoint.list_models()

        if deployed_models:
            # Calculer coût actuel (24/7)
            current_cost = calculate_endpoint_cost(endpoint)

            # Recommandation: delete après testing OU schedule on/off
            # Hypothèse: dev/test utilisé 8h/j, 5j/semaine
            recommended_hours_per_month = 8 * 22  # 176 heures/mois
            hours_per_month = 730

            # Coût recommandé
            cost_per_hour = current_cost / hours_per_month
            recommended_cost = cost_per_hour * recommended_hours_per_month

            # Waste
            monthly_waste = current_cost - recommended_cost
```

**Critères :**
- `labels.environment in ['dev', 'test', 'staging', 'development']`
- Endpoint running 24/7 (deployed models)
- Recommandation : schedule ou delete

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()
endpoint.labels  # Dict de labels
```

#### Calcul de Coût

**Formule :**

Dev/test 24/7 → 8h/jour :

```python
# Coût actuel (24/7)
hours_per_month = 730
cost_per_hour = machine_pricing.get(machine_type, 0.1540)
current_monthly_cost = cost_per_hour * hours_per_month

# Coût recommandé (8h/jour, 22 jours)
recommended_hours_per_month = 8 * 22  # 176 heures
recommended_monthly_cost = cost_per_hour * recommended_hours_per_month

# Waste
monthly_waste = current_monthly_cost - recommended_monthly_cost

# Savings percentage
savings_percentage = (monthly_waste / current_monthly_cost) * 100
```

**Exemple :**

Endpoint dev n1-standard-4 running 24/7 → 8h/j recommandé :
```python
cost_per_hour = $0.1540
current_cost = 0.1540 * 730 = $112.42
recommended_cost = 0.1540 * 176 = $27.10
monthly_waste = $85.32
savings_percentage = 75.9%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `recommended_hours_per_day` | int | 8 | Heures/jour recommandées dev/test |
| `recommended_days_per_month` | int | 22 | Jours/mois recommandés |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/333",
  "resource_name": "dev-ml-endpoint",
  "resource_type": "vertex_ai_devtest_247",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "333",
  "labels": {
    "environment": "dev",
    "team": "ml-platform"
  },
  "machine_type": "n1-standard-4",
  "current_hours_per_month": 730,
  "current_monthly_cost": 112.42,
  "recommended_hours_per_month": 176,
  "recommended_monthly_cost": 27.10,
  "estimated_monthly_waste": 85.32,
  "savings_percentage": 75.9,
  "confidence": "high",
  "recommendation": "Schedule dev/test endpoint for 8h/day instead of 24/7 - 76% cost reduction",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `vertex_ai_old_model_versions` - Old Model Versions

#### Détection

**Logique :**
```python
# 1. Lister endpoints
endpoints = aiplatform.Endpoint.list()

for endpoint in endpoints:
    deployed_models = endpoint.list_models()

    for deployed_model in deployed_models:
        # 2. Récupérer model info
        model_id = deployed_model.id
        model = aiplatform.Model(model_name=model_id)

        # 3. Vérifier upload time (dernière mise à jour)
        model_upload_time = model.create_time

        # 4. Calculer age
        age_days = (datetime.utcnow() - model_upload_time).days

        # 5. Détection si model très vieux
        if age_days >= old_model_threshold_days:
            # Model pas updated depuis longtemps
            # Potentiellement stale, risque qualité

            # Coût indirect (governance waste)
            endpoint_cost = calculate_endpoint_cost(endpoint)
            governance_waste = endpoint_cost * 0.05  # 5% du coût
```

**Critères :**
- `model.upload_time < now() - 180 days` (6 mois)
- Model toujours déployé
- Pas de update récent

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()
deployed_models = endpoint.list_models()
model = aiplatform.Model(model_name=model_id)
model.create_time  # Timestamp
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Model vieux = risque qualité/performance
# Coût estimé = 5% du coût endpoint

endpoint_monthly_cost = calculate_endpoint_cost(endpoint)

# Governance waste
governance_waste_pct = 0.05
monthly_waste = endpoint_monthly_cost * governance_waste_pct

# Waste cumulé depuis 180 jours
months_old = age_days / 30.0
already_wasted = monthly_waste * months_old
```

**Exemple :**

Endpoint $462/mois avec model 240 jours sans update :
```python
endpoint_monthly_cost = $462.82
governance_waste = $462.82 * 0.05 = $23.14/mois
already_wasted = $23.14 * (240/30) = $185.12
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `old_model_threshold_days` | int | 180 | Âge model max sans update |
| `governance_waste_pct` | float | 0.05 | % coût attribué governance |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/444",
  "resource_name": "old-model-endpoint",
  "resource_type": "vertex_ai_old_model_versions",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "444",
  "deployed_model": {
    "model_id": "model-555",
    "model_display_name": "fraud_detection_v1",
    "upload_time": "2024-03-01T10:00:00Z",
    "age_days": 246
  },
  "endpoint_monthly_cost": 462.82,
  "estimated_monthly_waste": 23.14,
  "already_wasted": 190.65,
  "confidence": "medium",
  "recommendation": "Update model - deployed version is 246 days old (quality/performance risk)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `vertex_ai_untagged_endpoints` - Endpoints Non Tagués

#### Détection

**Logique :**
```python
# 1. Lister endpoints
endpoints = aiplatform.Endpoint.list()

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'model', 'cost-center']

# 3. Pour chaque endpoint, vérifier labels
for endpoint in endpoints:
    labels = endpoint.labels if endpoint.labels else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged endpoint = governance waste

        # Calculer coût endpoint
        endpoint_cost = calculate_endpoint_cost(endpoint)

        # Governance waste = 5%
        governance_waste = endpoint_cost * 0.05
```

**Critères :**
- Labels manquants parmi la liste requise
- Endpoint actif (deployed models)

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()
endpoint.labels  # Dict ou None
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Endpoints non tagués = perte visibilité coûts
# Coût estimé = 5% du coût endpoint

endpoint_monthly_cost = calculate_endpoint_cost(endpoint)

# Governance waste = 5%
governance_waste_pct = 0.05
monthly_waste = endpoint_monthly_cost * governance_waste_pct

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Endpoint $112/mois sans labels depuis 120 jours :
```python
endpoint_monthly_cost = $112.42
governance_waste = $112.42 * 0.05 = $5.62/mois
already_wasted = $5.62 * (120/30) = $22.48
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'model', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/666",
  "resource_name": "untagged-ml-endpoint",
  "resource_type": "vertex_ai_untagged_endpoints",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "666",
  "creation_time": "2024-07-05T08:00:00Z",
  "age_days": 120,
  "labels": {},
  "missing_labels": ["environment", "owner", "model", "cost-center"],
  "endpoint_monthly_cost": 112.42,
  "estimated_monthly_waste": 5.62,
  "already_wasted": 22.48,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `vertex_ai_unused_traffic_split` - Traffic Split Inutile

#### Détection

**Logique :**

Analyser traffic split configuration (A/B testing) :

```python
# 1. Lister endpoints
endpoints = aiplatform.Endpoint.list()

for endpoint in endpoints:
    deployed_models = endpoint.list_models()

    # 2. Vérifier traffic split
    if len(deployed_models) >= 2:
        # Multiple models déployés = traffic split configuré

        # 3. Récupérer traffic split percentages
        for deployed_model in deployed_models:
            traffic_percentage = deployed_model.traffic_split

            # 4. Détection si model avec 0% traffic
            if traffic_percentage == 0:
                # Model déployé mais 0% traffic = waste
                # Model consomme resources mais pas utilisé

                # Calculer coût model
                # Note: Dans Vertex AI, tous models sur endpoint partagent resources
                # Mais si traffic split = 0%, model devrait être undeploy

                # Waste = overhead management + potentiel autoscaling
```

**Critères :**
- `len(deployed_models) >= 2` (traffic split configuré)
- Un ou plusieurs models avec `traffic_percentage == 0`
- Age du traffic split >7 jours (pas test temporaire)

**API Calls :**
```python
# Vertex AI API
endpoints = aiplatform.Endpoint.list()
deployed_models = endpoint.list_models()
deployed_model.traffic_split  # % traffic
```

#### Calcul de Coût

**Formule :**

Traffic split avec models 0% = overhead :

```python
# Vertex AI partage resources entre models sur endpoint
# Donc pas de coût additionnel direct

# MAIS:
# 1. Overhead management
# 2. Confusion opérationnelle
# 3. Si autoscaling, peut causer over-provisioning

# Coût estimé = overhead 2% du coût endpoint
endpoint_monthly_cost = calculate_endpoint_cost(endpoint)
overhead_waste_pct = 0.02
monthly_waste = endpoint_monthly_cost * overhead_waste_pct

# Si 2+ models avec 0% traffic
unused_models_count = len([m for m in deployed_models if m.traffic_split == 0])
monthly_waste = monthly_waste * unused_models_count
```

**Exemple :**

Endpoint $462/mois avec 2 models (100% + 0%) :
```python
endpoint_monthly_cost = $462.82
unused_models_count = 1
monthly_waste = $462.82 * 0.02 * 1 = $9.26/mois
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_traffic_split_age_days` | int | 7 | Âge min traffic split pour détection |
| `overhead_waste_pct` | float | 0.02 | % overhead par model unused |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/endpoints/777",
  "resource_name": "ab-test-endpoint",
  "resource_type": "vertex_ai_unused_traffic_split",
  "project_id": "my-project-123",
  "location": "us-central1",
  "endpoint_id": "777",
  "deployed_models": [
    {
      "model_id": "model-888",
      "model_display_name": "fraud_v2",
      "traffic_percentage": 100,
      "deploy_time": "2024-09-01T10:00:00Z"
    },
    {
      "model_id": "model-999",
      "model_display_name": "fraud_v3",
      "traffic_percentage": 0,
      "deploy_time": "2024-08-15T08:00:00Z",
      "days_at_zero_traffic": 79
    }
  ],
  "unused_models_count": 1,
  "endpoint_monthly_cost": 462.82,
  "estimated_monthly_waste": 9.26,
  "confidence": "medium",
  "recommendation": "Undeploy model fraud_v3 - 0% traffic for 79 days (A/B test completed)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `vertex_ai_failed_training_jobs` - Training Jobs Failed/Abandoned

#### Détection

**Logique :**

Analyser training jobs failed ou cancelled :

```python
# 1. Lister training jobs (30 derniers jours)
from google.cloud import aiplatform

aiplatform.init(project=project_id, location=region)

# Query training pipelines
training_jobs = aiplatform.CustomJob.list(
    filter=f'create_time > "{thirty_days_ago}"'
)

failed_jobs = []
cancelled_jobs = []

# 2. Pour chaque job, vérifier state
for job in training_jobs:
    if job.state == 'FAILED':
        failed_jobs.append(job)

    elif job.state == 'CANCELLED':
        cancelled_jobs.append(job)

# 3. Analyser patterns d'erreur
error_patterns = {}

for job in failed_jobs:
    error_message = job.error.message if job.error else 'Unknown error'

    # Grouper erreurs similaires
    if error_message not in error_patterns:
        error_patterns[error_message] = []

    error_patterns[error_message].append(job)

# 4. Détection si même erreur répétée
for error, jobs_list in error_patterns.items():
    if len(jobs_list) >= repeated_failure_threshold:
        # Même erreur répétée X fois = waste pattern

        # Calculer coût total gaspillé
        total_waste = sum([estimate_job_cost(j) for j in jobs_list])
```

**Critères :**
- `job.state in ['FAILED', 'CANCELLED']`
- Jobs dans 30 derniers jours
- Même erreur répétée ≥3 fois (pattern)

**API Calls :**
```python
# Vertex AI API
from google.cloud import aiplatform

aiplatform.init(project=project_id, location=region)
training_jobs = aiplatform.CustomJob.list()
job.state  # 'FAILED', 'CANCELLED', 'SUCCEEDED', etc.
job.error.message  # Error message
```

#### Calcul de Coût

**Formule :**

Failed training job = partial compute waste :

```python
# Pour chaque failed job, estimer coût
def estimate_job_cost(job):
    # Récupérer machine specs
    worker_pool_specs = job.job_spec.worker_pool_specs

    for spec in worker_pool_specs:
        machine_type = spec.machine_spec.machine_type
        accelerator_type = spec.machine_spec.accelerator_type
        replica_count = spec.replica_count

        # Coût par heure
        machine_cost_per_hour = machine_pricing.get(machine_type, 0.1540)
        gpu_cost_per_hour = gpu_pricing.get(accelerator_type, 0) if accelerator_type else 0
        cost_per_hour = (machine_cost_per_hour + gpu_cost_per_hour) * replica_count

        # Durée job avant failure
        if job.start_time and job.end_time:
            duration_hours = (job.end_time - job.start_time).total_seconds() / 3600
        else:
            duration_hours = 1  # Estimé

        # Coût waste
        job_waste = cost_per_hour * duration_hours

    return job_waste

# Total waste pour tous failed jobs
total_monthly_waste = sum([estimate_job_cost(j) for j in failed_jobs])
```

**Exemple :**

10 failed jobs n1-standard-4 × 2h chacun :
```python
machine_cost_per_hour = $0.1540
replica_count = 1
duration_hours = 2

cost_per_job = 0.1540 * 1 * 2 = $0.308
total_waste = 10 * $0.308 = $3.08/mois

# Si failed jobs avec GPU T4
gpu_cost_per_hour = $0.48
cost_per_job = (0.1540 + 0.48) * 2 = $1.268
total_waste = 10 * $1.268 = $12.68/mois
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 30 | Période analyse training jobs |
| `repeated_failure_threshold` | int | 3 | Nombre min erreurs identiques |
| `min_cost_threshold` | float | 5.0 | Coût min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "training_jobs_analysis",
  "resource_name": "failed_training_jobs_pattern",
  "resource_type": "vertex_ai_failed_training_jobs",
  "project_id": "my-project-123",
  "location": "us-central1",
  "analysis_period_days": 30,
  "failed_jobs_count": 15,
  "cancelled_jobs_count": 5,
  "error_patterns": [
    {
      "error_message": "OutOfMemoryError: CUDA out of memory",
      "occurrence_count": 8,
      "jobs": ["job-111", "job-222", "job-333"],
      "estimated_waste": 15.42
    },
    {
      "error_message": "FileNotFoundError: Training data not found",
      "occurrence_count": 5,
      "jobs": ["job-444", "job-555"],
      "estimated_waste": 2.31
    }
  ],
  "total_failed_jobs_waste": 17.73,
  "confidence": "high",
  "recommendation": "Fix recurring errors: CUDA OOM (use smaller batch size), FileNotFoundError (validate data path)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `vertex_ai_unused_feature_store` - Feature Store Unused

#### Détection

**Logique :**

Identifier feature stores jamais utilisés :

```python
# 1. Lister feature stores
from google.cloud import aiplatform

featurestores = aiplatform.Featurestore.list()

# 2. Pour chaque feature store, vérifier usage (30 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for featurestore in featurestores:
    featurestore_id = featurestore.name.split('/')[-1]

    # 3. Query Cloud Monitoring pour online serving requests
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 30*24*3600},
    })

    # Métrique: aiplatform.googleapis.com/featurestore/online_serving/request_count
    request_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="aiplatform.googleapis.com/Featurestore" '
                     f'AND resource.featurestore_id="{featurestore_id}" '
                     f'AND metric.type="aiplatform.googleapis.com/featurestore/online_serving/request_count"',
            "interval": interval,
        }
    )

    # 4. Calculer total requests
    total_requests = sum([
        point.value.int64_value
        for series in request_metrics
        for point in series.points
    ])

    # 5. Détection si 0 requests
    if total_requests == 0:
        # Feature store jamais utilisé = waste

        # Calculer coût storage
        # Query storage size via API
        storage_size_gb = get_featurestore_storage_size(featurestore)

        storage_cost = storage_size_gb * 0.70  # $0.70/GB/mois
        monthly_waste = storage_cost  # + overhead infrastructure
```

**Critères :**
- `total_requests == 0` sur 30 jours (online serving)
- Feature store actif (non deleted)
- Age >7 jours

**API Calls :**
```python
# Vertex AI API
featurestores = aiplatform.Featurestore.list()

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="aiplatform.googleapis.com/featurestore/online_serving/request_count"'
)
```

#### Calcul de Coût

**Formule :**

Feature store unused = storage waste :

```python
# Feature store pricing
storage_price_per_gb = 0.70  # $/GB/mois
online_serving_price = 0.35  # $/1M reads

# Coût storage
storage_size_gb = get_featurestore_storage_size(featurestore)
storage_cost = storage_size_gb * storage_price_per_gb

# Online serving cost = 0 (no requests)
online_serving_cost = 0

# Waste = storage cost
monthly_waste = storage_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Feature store 100 GB jamais utilisé depuis 60 jours :
```python
storage_size_gb = 100
storage_cost = 100 * 0.70 = $70/mois
monthly_waste = $70
already_wasted = $70 * (60/30) = $140
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 30 | Période sans usage pour détection |
| `min_age_days` | int | 7 | Âge minimum feature store |
| `min_storage_gb` | float | 1.0 | Storage minimum pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "projects/123/locations/us-central1/featurestores/999",
  "resource_name": "unused-feature-store",
  "resource_type": "vertex_ai_unused_feature_store",
  "project_id": "my-project-123",
  "location": "us-central1",
  "featurestore_id": "999",
  "creation_time": "2024-09-01T10:00:00Z",
  "age_days": 62,
  "storage_size_gb": 120.5,
  "request_metrics_30d": {
    "online_serving_requests": 0,
    "batch_serving_requests": 0
  },
  "storage_cost_monthly": 84.35,
  "estimated_monthly_waste": 84.35,
  "already_wasted": 174.32,
  "confidence": "high",
  "recommendation": "Delete unused feature store - zero requests in 30 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Protocole de Test

### Prérequis

#### 1. Compte GCP et Projet Test

```bash
# Utiliser projet test existant
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
export REGION="us-central1"
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable aiplatform.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account

```bash
# Ajouter permissions Vertex AI
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/monitoring.viewer"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

#### 3. Installer gcloud AI Platform CLI

```bash
# gcloud AI Platform inclus avec gcloud SDK
gcloud ai --help

# Ou utiliser Python SDK
pip install google-cloud-aiplatform
```

---

### Tests Unitaires - Créer Ressources Test

#### Scénario 1: Endpoint Zero Predictions

```bash
# Créer endpoint vide
gcloud ai endpoints create \
  --region=$REGION \
  --display-name="test-unused-endpoint"

# Récupérer endpoint ID
ENDPOINT_ID=$(gcloud ai endpoints list --region=$REGION \
  --filter="displayName:test-unused-endpoint" \
  --format="value(name)")

echo "Endpoint created: $ENDPOINT_ID"

# NE PAS déployer de model = endpoint vide
# Attendre 30 jours (ou ajuster threshold à 1 jour pour test)
```

**Validation attendue :**
```json
{
  "resource_type": "vertex_ai_zero_predictions",
  "prediction_count_30d": 0,
  "deployed_models_count": 0
}
```

---

#### Scénario 2: Endpoint Idle (Deploy Simple Model)

```bash
# Créer model simple (pour test)
# Note: Nécessite trained model artifacts
# Alternative: utiliser model pré-entraîné

# Si vous avez model artifacts:
MODEL_ID="your-model-id"

# Deploy model sur endpoint
gcloud ai endpoints deploy-model $ENDPOINT_ID \
  --region=$REGION \
  --model=$MODEL_ID \
  --display-name="deployed-model-v1" \
  --machine-type=n1-standard-2 \
  --min-replica-count=1 \
  --max-replica-count=1

# Faire 1-2 predictions seulement (très peu)
gcloud ai endpoints predict $ENDPOINT_ID \
  --region=$REGION \
  --json-request=test_request.json

# avg_predictions_per_day = 0.1 → idle
```

**test_request.json :**
```json
{
  "instances": [
    {"feature1": 1.0, "feature2": 2.0}
  ]
}
```

**Validation attendue :**
```json
{
  "resource_type": "vertex_ai_idle_endpoints",
  "avg_predictions_per_day": "<10",
  "estimated_monthly_waste": ">= 50"
}
```

---

#### Scénario 3: GPU Waste

```bash
# Deploy model avec GPU (mais model CPU-based)
gcloud ai endpoints deploy-model $ENDPOINT_ID \
  --region=$REGION \
  --model=$MODEL_ID \
  --display-name="cpu-model-on-gpu" \
  --machine-type=n1-standard-4 \
  --accelerator=type=NVIDIA_TESLA_T4,count=1 \
  --min-replica-count=1 \
  --max-replica-count=1

# Model est CPU-based, GPU jamais utilisé
# GPU utilization = 0% → waste $350/mois
```

**Validation attendue :**
```json
{
  "resource_type": "vertex_ai_gpu_waste",
  "accelerator_type": "NVIDIA_TESLA_T4",
  "avg_gpu_utilization": "<30",
  "estimated_monthly_waste": "350"
}
```

---

#### Scénario 5: Dev/Test 24/7

```bash
# Créer endpoint avec label dev
gcloud ai endpoints create \
  --region=$REGION \
  --display-name="test-dev-endpoint" \
  --labels=environment=dev,team=ml-platform

# Deploy model
gcloud ai endpoints deploy-model $DEV_ENDPOINT_ID \
  --region=$REGION \
  --model=$MODEL_ID \
  --machine-type=n1-standard-4 \
  --min-replica-count=1

# Endpoint dev running 24/7 = waste
# Devrait être: 8h/j seulement
```

**Validation attendue :**
```json
{
  "resource_type": "vertex_ai_devtest_247",
  "labels": {"environment": "dev"},
  "current_monthly_cost": "112",
  "recommended_monthly_cost": "27",
  "estimated_monthly_waste": "85"
}
```

---

#### Scénario 9: Failed Training Jobs

```bash
# Lancer training job qui va fail (invalid config)
gcloud ai custom-jobs create \
  --region=$REGION \
  --display-name="test-failed-job" \
  --worker-pool-spec=machine-type=n1-standard-4,replica-count=1,container-image-uri=INVALID_IMAGE_URI

# Job va fail immédiatement
# Compute wasted

# Répéter 3× avec même erreur pour pattern detection
```

**Validation attendue :**
```json
{
  "resource_type": "vertex_ai_failed_training_jobs",
  "failed_jobs_count": ">= 3",
  "error_patterns": ["ImageNotFound"],
  "estimated_waste": ">= 1"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script validation Vertex AI waste detection
"""

from google.cloud import aiplatform
from google.cloud import monitoring_v3
import os

PROJECT_ID = os.environ['PROJECT_ID']
REGION = os.environ.get('REGION', 'us-central1')

def test_all_scenarios():
    aiplatform.init(project=PROJECT_ID, location=REGION)

    scenarios_detected = {
        'zero_predictions': 0,
        'idle_endpoints': 0,
        'gpu_waste': 0,
        'overprovisioned_machines': 0,
        'devtest_247': 0,
        'old_model_versions': 0,
        'untagged_endpoints': 0,
        'unused_traffic_split': 0,
        'failed_training_jobs': 0,
        'unused_feature_store': 0,
    }

    # Test 1: List endpoints
    endpoints = aiplatform.Endpoint.list()
    print(f"✅ Found {len(endpoints)} endpoints")

    # Test 3: GPU waste
    for endpoint in endpoints:
        deployed_models = endpoint.list_models()
        for model in deployed_models:
            if model.machine_spec.accelerator_type:
                scenarios_detected['gpu_waste'] += 1
                print(f"✅ Scenario 3 (GPU endpoint): {endpoint.display_name}")

    # Test 5: Dev/test 24/7
    for endpoint in endpoints:
        labels = endpoint.labels or {}
        if labels.get('environment') in ['dev', 'test']:
            scenarios_detected['devtest_247'] += 1
            print(f"✅ Scenario 5 (dev/test): {endpoint.display_name}")

    # Test 7: Untagged endpoints
    for endpoint in endpoints:
        labels = endpoint.labels or {}
        if not labels:
            scenarios_detected['untagged_endpoints'] += 1
            print(f"✅ Scenario 7 (untagged): {endpoint.display_name}")

    # Test 9: Failed training jobs
    training_jobs = aiplatform.CustomJob.list()
    failed_jobs = [j for j in training_jobs if j.state == 'FAILED']
    scenarios_detected['failed_training_jobs'] = len(failed_jobs)
    print(f"✅ Scenario 9 (failed jobs): {len(failed_jobs)} jobs")

    # Rapport final
    print("\n📊 Detection Summary:")
    total_waste = sum([v for v in scenarios_detected.values() if isinstance(v, int)])
    for scenario, count in scenarios_detected.items():
        if count > 0:
            print(f"  - {scenario}: {count} resources")

    print(f"\n✅ Total waste resources detected: {total_waste}")

if __name__ == '__main__':
    test_all_scenarios()
```

**Exécution :**
```bash
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
export REGION="us-central1"
python3 validate_vertex_ai_scenarios.py
```

---

### Cleanup

```bash
# Undeploy models from endpoints
gcloud ai endpoints undeploy-model $ENDPOINT_ID \
  --region=$REGION \
  --deployed-model-id=$DEPLOYED_MODEL_ID

# Delete endpoints
gcloud ai endpoints delete $ENDPOINT_ID \
  --region=$REGION \
  --quiet

# Cancel training jobs
gcloud ai custom-jobs cancel $JOB_ID \
  --region=$REGION

# Delete models
gcloud ai models delete $MODEL_ID \
  --region=$REGION \
  --quiet
```

---

## Références

### Documentation GCP

- [Vertex AI API](https://cloud.google.com/vertex-ai/docs/reference/rest)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [Endpoints Guide](https://cloud.google.com/vertex-ai/docs/predictions/deploy-model-api)
- [Training Guide](https://cloud.google.com/vertex-ai/docs/training/overview)
- [GPUs on Vertex AI](https://cloud.google.com/vertex-ai/docs/training/configure-compute#gpus)
- [Feature Store Guide](https://cloud.google.com/vertex-ai/docs/featurestore/overview)
- [Monitoring Metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-aiplatform)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md)
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md)
- [GCP_GKE_CLUSTER_SCENARIOS_100.md](./GCP_GKE_CLUSTER_SCENARIOS_100.md)
- [GCP_CLOUD_SQL_SCENARIOS_100.md](./GCP_CLOUD_SQL_SCENARIOS_100.md)
- [GCP_CLOUD_SPANNER_SCENARIOS_100.md](./GCP_CLOUD_SPANNER_SCENARIOS_100.md)
- [GCP_BIGTABLE_SCENARIOS_100.md](./GCP_BIGTABLE_SCENARIOS_100.md)
- [GCP_BIGQUERY_SCENARIOS_100.md](./GCP_BIGQUERY_SCENARIOS_100.md)

### Équivalences AWS/Azure

- **AWS SageMaker Endpoints** → GCP Vertex AI Endpoints
- **Azure ML Endpoints** → GCP Vertex AI Endpoints
- **AWS SageMaker Training** → Vertex AI Custom Training
- **AWS SageMaker Notebooks** → Vertex AI Workbench
- **AWS SageMaker Feature Store** → Vertex AI Feature Store

### Best Practices

1. **Endpoints** : Delete unused endpoints (0 predictions >30 jours)
2. **GPUs** : Use GPUs only for GPU-accelerated inference
3. **Dev/Test** : Schedule dev/test endpoints (8h/jour au lieu de 24/7)
4. **Machine Types** : Right-size based on CPU utilization
5. **Traffic Split** : Undeploy models avec 0% traffic après A/B tests
6. **Training Jobs** : Monitor failures, fix recurring errors
7. **Feature Store** : Delete unused feature stores
8. **Labels** : Tag tous endpoints pour cost allocation
9. **Autoscaling** : Configure autoscaling pour variable traffic
10. **Batch vs Real-time** : Use batch predictions pour low traffic

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
