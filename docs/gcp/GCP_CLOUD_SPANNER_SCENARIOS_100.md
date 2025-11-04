# CloudWaste - Couverture 100% GCP Cloud Spanner

**Resource Type:** `Database : Cloud Spanner`
**Provider:** Google Cloud Platform (GCP)
**API:** `spanner.googleapis.com` (Cloud Spanner API v1)
**Équivalents:** AWS Aurora Global Database, Azure Cosmos DB
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing Cloud Spanner](#modèle-de-pricing-cloud-spanner)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Instances Sous-Utilisées](#1-cloud_spanner_underutilized---instances-sous-utilisées)
  - [2. Multi-Regional Inutile](#2-cloud_spanner_unnecessary_multiregional---multi-regional-inutile)
  - [3. Instances Dev/Test Over-Provisioned](#3-cloud_spanner_devtest_overprovisioned---instances-devtest-over-provisioned)
  - [4. Instances Idle (Zero Queries)](#4-cloud_spanner_idle---instances-idle-zero-queries)
  - [5. Processing Units Suboptimal](#5-cloud_spanner_pu_suboptimal---processing-units-suboptimal)
  - [6. Instances avec Databases Vides](#6-cloud_spanner_empty_databases---instances-avec-databases-vides)
  - [7. Instances Non Taguées](#7-cloud_spanner_untagged---instances-non-taguées)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Nodes avec CPU Faible](#8-cloud_spanner_low_cpu---nodes-avec-cpu-faible)
  - [9. Storage Over-Provisioned](#9-cloud_spanner_storage_overprovisioned---storage-over-provisioned)
  - [10. Backups Excessifs](#10-cloud_spanner_excessive_backups---backups-excessifs)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte Cloud Spanner

**Cloud Spanner** est la base de données **distribuée globalement** de GCP, offrant :

- **Strong consistency** (ACID complet)
- **Horizontal scaling** (jusqu'à millions d'opérations/sec)
- **Global distribution** (multi-régions avec latence <10ms)
- **SQL interface** (ANSI SQL 2011)
- **Automatic sharding** et réplication

### Caractéristiques Uniques

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Nodes** | Unités compute (1 node = 1000 Processing Units) | $657-2190/node/mois |
| **Processing Units (PU)** | Granularité fine (100 PU minimum) | $0.657/PU/mois |
| **Regional** | 1 région (3 zones) | ~$657/node/mois |
| **Multi-Regional** | 2+ régions (9+ zones) | ~$2,190/node/mois (3.3x+) |
| **Storage** | SSD automatique | $0.30-0.50/GB/mois |
| **Backups** | Point-in-time recovery | $0.20-0.30/GB/mois |

### Pricing Model

**Cloud Spanner = Nodes/PU + Storage + Backups**

#### Nodes vs Processing Units

- **1 node = 1000 Processing Units (PU)**
- **Minimum:** 100 PU (0.1 node) pour dev/test
- **Production:** Recommandé ≥1 node (1000 PU)
- **Multi-regional:** Minimum 3 nodes (1 par région)

### Configuration Typique

#### Regional Instance (Production)

```
Nodes: 3 nodes (3000 PU)
Storage: 500 GB
Backups: 1 TB (7 jours rétention)
─────────────────────────────
Nodes: 3 × $657 = $1,971/mois
Storage: 500 × $0.30 = $150/mois
Backups: 1000 × $0.20 = $200/mois
─────────────────────────────
TOTAL: $2,321/mois (~$27,852/an)
```

#### Multi-Regional Instance (Global)

```
Nodes: 3 nodes (minimum, 1 par région)
Storage: 500 GB
Backups: 1 TB
─────────────────────────────
Nodes: 3 × $2,190 = $6,570/mois
Storage: 500 × $0.50 = $250/mois
Backups: 1000 × $0.30 = $300/mois
─────────────────────────────
TOTAL: $7,120/mois (~$85,440/an)
```

### Waste Typique

1. **Multi-regional inutile** : 3.3x+ coût vs regional ($6,570 vs $1,971/mois)
2. **Nodes over-provisioned** : 3 nodes pour 100 queries/sec = surcoût
3. **Dev/test avec nodes production** : $657/node/mois pour environnement non-prod
4. **Processing Units fixes** : 1000 PU (1 node) alors que 300 PU suffisent
5. **Storage non optimisé** : Pas de TTL, données anciennes non supprimées
6. **Backups excessifs** : Rétention 365 jours pour dev/test
7. **Instances idle** : Zero queries mais nodes actifs

---

## Modèle de Pricing Cloud Spanner

### Nodes Pricing (par mois)

| Configuration | Nodes | Processing Units | Regional | Multi-Regional | Ratio |
|--------------|-------|-----------------|---------|----------------|-------|
| **Minimum (dev/test)** | 0.1 | 100 PU | $65.70 | $219.00 | 3.3x |
| **Small** | 1 | 1000 PU | $657.00 | $2,190.00 | 3.3x |
| **Medium** | 3 | 3000 PU | $1,971.00 | $6,570.00 | 3.3x |
| **Large** | 5 | 5000 PU | $3,285.00 | $10,950.00 | 3.3x |
| **X-Large** | 10 | 10000 PU | $6,570.00 | $21,900.00 | 3.3x |

**Formules :**
- **Regional node :** $0.90/hour = $657/mois
- **Multi-regional node :** $3.00/hour = $2,190/mois
- **Processing Unit :** $0.0009/hour/PU = $0.657/mois/PU

### Storage Pricing

| Type | Regional | Multi-Regional | Différence |
|------|---------|----------------|-----------|
| **Storage (SSD)** | $0.30/GB/mois | $0.50/GB/mois | +67% |
| **Backups** | $0.20/GB/mois | $0.30/GB/mois | +50% |

**Comparaison Cloud SQL :**
- Cloud SQL SSD : $0.17/GB/mois
- Cloud Spanner Regional : $0.30/GB/mois (+76%)
- Cloud Spanner Multi-Regional : $0.50/GB/mois (+194%)

### Exemples Coûts Mensuels

#### Scénario 1 : Dev/Test Minimal

```
Config: 100 PU regional, 10 GB storage
─────────────────────────────
Nodes: 100 PU × $0.657 = $65.70
Storage: 10 GB × $0.30 = $3.00
Backups: 15 GB × $0.20 = $3.00
─────────────────────────────
TOTAL: $71.70/mois
```

#### Scénario 2 : Production Regional

```
Config: 3 nodes (3000 PU), 1 TB storage
─────────────────────────────
Nodes: 3 × $657 = $1,971.00
Storage: 1000 GB × $0.30 = $300.00
Backups: 2000 GB × $0.20 = $400.00
─────────────────────────────
TOTAL: $2,671.00/mois
```

#### Scénario 3 : Production Multi-Regional

```
Config: 5 nodes (5000 PU), 2 TB storage, 3 régions
─────────────────────────────
Nodes: 5 × $2,190 = $10,950.00
Storage: 2000 GB × $0.50 = $1,000.00
Backups: 4000 GB × $0.30 = $1,200.00
─────────────────────────────
TOTAL: $13,150.00/mois (~$157,800/an)
```

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `cloud_spanner_underutilized` - Instances Sous-Utilisées

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances Cloud Spanner
from google.cloud import spanner_admin_instance_v1

spanner_client = spanner_admin_instance_v1.InstanceAdminClient()

parent = f"projects/{project_id}"
instances = spanner_client.list_instances(parent=parent)

# 2. Pour chaque instance, récupérer config nodes/PU
for instance in instances:
    instance_name = instance.name
    instance_config = instance.config  # "regional-us-central1" ou "nam3" (multi-regional)

    # Récupérer node count ou processing units
    node_count = instance.node_count
    processing_units = instance.processing_units

    # Note: soit node_count soit processing_units est défini
    if node_count > 0:
        total_pu = node_count * 1000
    else:
        total_pu = processing_units

    # 3. Récupérer métriques utilisation (14 jours)
    from google.cloud import monitoring_v3

    monitoring_client = monitoring_v3.MetricServiceClient()

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Métrique: spanner.googleapis.com/instance/cpu/utilization
    cpu_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="spanner_instance" AND resource.instance_id="{instance_name.split("/")[-1]}" AND metric.type="spanner.googleapis.com/instance/cpu/utilization"',
            "interval": interval,
        }
    )

    # 4. Calculer CPU moyenne
    cpu_values = [
        point.value.double_value
        for series in cpu_metrics
        for point in series.points
    ]

    avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

    # 5. Recommandation PU basée sur CPU
    # Spanner optimal CPU: 65% (Google recommendation)
    # Si avg_cpu < 30%, over-provisioned

    if avg_cpu < cpu_threshold:
        # Calculer PU recommandés
        # Formule: PU_optimal = PU_actuel * (avg_cpu / 65)
        optimal_pu = int(total_pu * (avg_cpu / 65.0))
        optimal_pu = max(100, optimal_pu)  # Minimum 100 PU

        if optimal_pu < total_pu:
            # Instance sous-utilisée = waste détecté
```

**Critères :**
- `avg_cpu < 30%` sur 14 jours
- PU recommandés < PU actuels
- Instance active (state = READY)

**API Calls :**
```python
# Cloud Spanner Admin API
from google.cloud import spanner_admin_instance_v1

spanner_client = spanner_admin_instance_v1.InstanceAdminClient()
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/cpu/utilization"'
)
```

#### Calcul de Coût

**Formule :**

Under-utilization = différence PU actuels vs recommandés :

```python
# Exemple: 3000 PU (3 nodes) regional avec CPU 20%

current_pu = 3000
avg_cpu = 20.0

# PU optimal pour CPU 65% (Google best practice)
optimal_pu = int(current_pu * (avg_cpu / 65.0))  # 923 PU
optimal_pu = max(100, optimal_pu)  # Arrondi à 1000 (1 node)

# Instance config
is_multiregional = 'nam' in instance_config or 'eur' in instance_config

if is_multiregional:
    cost_per_pu = 2.19  # $/PU/mois
else:
    cost_per_pu = 0.657  # $/PU/mois

# Coût actuel
current_cost = current_pu * cost_per_pu  # 3000 × $0.657 = $1,971

# Coût optimal
optimal_cost = optimal_pu * cost_per_pu  # 1000 × $0.657 = $657

# Waste
monthly_waste = current_cost - optimal_cost  # $1,314

# Storage et backups identiques (pas de waste)

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance regional 3 nodes (3000 PU) avec CPU 20% depuis 90 jours :
```python
current_cost = 3000 * $0.657 = $1,971/mois
optimal_cost = 1000 * $0.657 = $657/mois (1 node)
monthly_waste = $1,314
already_wasted = $1,314 * (90/30) = $3,942
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 30.0 | CPU % maximum pour sous-utilisation |
| `target_cpu` | float | 65.0 | CPU optimal Spanner (Google recommendation) |
| `lookback_days` | int | 14 | Période analyse métriques |
| `min_savings_threshold` | float | 100.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1234567890",
  "resource_name": "prod-spanner-regional",
  "resource_type": "cloud_spanner_underutilized",
  "instance_config": "regional-us-central1",
  "state": "READY",
  "current_node_count": 3,
  "current_processing_units": 3000,
  "cpu_metrics": {
    "avg_cpu_14d": 22.3,
    "max_cpu_14d": 45.8
  },
  "recommended_processing_units": 1000,
  "recommended_node_count": 1,
  "current_cost_monthly": 1971.00,
  "recommended_cost_monthly": 657.00,
  "estimated_monthly_waste": 1314.00,
  "already_wasted": 3942.00,
  "confidence": "high",
  "recommendation": "Reduce from 3 nodes to 1 node (3000 PU → 1000 PU)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `cloud_spanner_unnecessary_multiregional` - Multi-Regional Inutile

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances multi-régionales
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

multiregional_instances = [
    i for i in instances
    if 'nam' in i.config or 'eur' in i.config or 'asia' in i.config
]

# 2. Pour chaque instance multi-régionale, analyser usage
for instance in multiregional_instances:
    instance_name = instance.name

    # 3. Vérifier labels (dev/test ne nécessite pas multi-regional)
    labels = instance.labels if hasattr(instance, 'labels') else {}
    environment = labels.get('environment', '').lower()

    if environment in ['dev', 'test', 'staging', 'development']:
        # Multi-regional pour dev/test = waste évident
        # Économie: 3.3x coût
        continue

    # 4. Analyser pattern géographique queries (si prod)
    # Métrique: spanner.googleapis.com/instance/api_request_count par région

    # Query requests par région
    regions_metrics = get_api_requests_by_region(instance, lookback_days=14)

    # 5. Calculer distribution géographique
    total_requests = sum(regions_metrics.values())
    max_region_requests = max(regions_metrics.values()) if regions_metrics else 0

    # Si >90% requests viennent d'une seule région, multi-regional inutile
    if total_requests > 0:
        max_region_pct = (max_region_requests / total_requests) * 100

        if max_region_pct >= regional_concentration_threshold:
            # Multi-regional inutile, regional suffit
            # Économie: ~70% coût nodes
```

**Critères :**
- Instance multi-régionale (`config` contient 'nam', 'eur', 'asia')
- Labels `environment in ['dev', 'test']` OU
- >90% requests depuis une seule région (multi-regional inutile)

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API (requests par région)
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/api_request_count"'
)
```

#### Calcul de Coût

**Formule :**

Multi-regional → Regional = -70% coût nodes :

```python
# Exemple: 3 nodes multi-regional (nam3) pour dev

current_nodes = 3
current_pu = 3000

# Multi-regional pricing
multiregional_cost_per_pu = 2.19  # $/PU/mois

current_cost = current_pu * multiregional_cost_per_pu  # $6,570

# Regional pricing (équivalent)
regional_cost_per_pu = 0.657  # $/PU/mois

recommended_cost = current_pu * regional_cost_per_pu  # $1,971

# Waste = différence multi-regional vs regional
monthly_waste = current_cost - recommended_cost  # $4,599 (!!)

# Storage aussi plus cher en multi-regional
storage_size_gb = 500

current_storage_cost = storage_size_gb * 0.50  # Multi-regional
recommended_storage_cost = storage_size_gb * 0.30  # Regional

storage_waste = current_storage_cost - recommended_storage_cost  # $100

# Backups
backup_size_gb = 1000

current_backup_cost = backup_size_gb * 0.30  # Multi-regional
recommended_backup_cost = backup_size_gb * 0.20  # Regional

backup_waste = current_backup_cost - recommended_backup_cost  # $100

# Waste total
total_monthly_waste = monthly_waste + storage_waste + backup_waste  # $4,799

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = total_monthly_waste * age_months
```

**Exemple :**

Instance multi-regional 3 nodes (nam3) pour dev depuis 120 jours :
```python
current_cost = $6,570 + $250 + $300 = $7,120/mois
recommended_cost = $1,971 + $150 + $200 = $2,321/mois
monthly_waste = $4,799
already_wasted = $4,799 * (120/30) = $19,196
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels non-prod |
| `regional_concentration_threshold` | float | 90.0 | % requests max depuis une région |
| `lookback_days` | int | 14 | Période analyse pattern géographique |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9876543210",
  "resource_name": "dev-spanner-multiregional",
  "resource_type": "cloud_spanner_unnecessary_multiregional",
  "instance_config": "nam3",
  "is_multiregional": true,
  "state": "READY",
  "node_count": 3,
  "processing_units": 3000,
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "storage_size_gb": 500,
  "current_cost_monthly": 7120.00,
  "recommended_config": "regional-us-central1",
  "recommended_cost_monthly": 2321.00,
  "estimated_monthly_waste": 4799.00,
  "already_wasted": 19196.00,
  "savings_percentage": 67.4,
  "confidence": "high",
  "recommendation": "Migrate to regional configuration - dev environment doesn't need multi-regional",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `cloud_spanner_devtest_overprovisioned` - Instances Dev/Test Over-Provisioned

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, vérifier labels
for instance in instances:
    labels = instance.labels if hasattr(instance, 'labels') else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test
    if environment in ['dev', 'test', 'staging', 'development']:
        # 4. Vérifier config nodes/PU
        if instance.node_count > 0:
            total_pu = instance.node_count * 1000
        else:
            total_pu = instance.processing_units

        # 5. Dev/test devrait utiliser minimum PU (100-500 PU)
        # Si >1000 PU (1+ node), probablement over-provisioned

        if total_pu >= devtest_pu_threshold:
            # Dev/test avec ≥1 node = waste

            # Recommandation: 100-300 PU pour dev/test
            recommended_pu = 300

            # Calculer économie
            is_multiregional = 'nam' in instance.config or 'eur' in instance.config

            if is_multiregional:
                cost_per_pu = 2.19
            else:
                cost_per_pu = 0.657

            current_cost = total_pu * cost_per_pu
            recommended_cost = recommended_pu * cost_per_pu

            monthly_waste = current_cost - recommended_cost

            if monthly_waste >= min_savings_threshold:
                # Dev/test over-provisioned = waste détecté
```

**Critères :**
- `labels.environment in ['dev', 'test', 'staging']`
- `processing_units >= 1000` (≥1 node)
- Recommandation: 100-300 PU suffisants pour dev/test

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

Dev/test avec production config = surcoût :

```python
# Exemple: Instance dev avec 3 nodes regional

current_pu = 3000  # 3 nodes
cost_per_pu = 0.657  # Regional

current_cost = 3000 * 0.657 = $1,971/mois

# Recommandation dev/test: 300 PU
recommended_pu = 300
recommended_cost = 300 * 0.657 = $197/mois

# Waste
monthly_waste = $1,971 - $197 = $1,774

# Storage et backups identiques (minimes pour dev)

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance dev 3 nodes regional depuis 90 jours :
```python
current_cost = $1,971/mois
recommended_cost = $197/mois (300 PU)
monthly_waste = $1,774
already_wasted = $1,774 * (90/30) = $5,322
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `devtest_pu_threshold` | int | 1000 | PU max recommandé pour dev/test |
| `recommended_devtest_pu` | int | 300 | PU optimal dev/test |
| `min_savings_threshold` | float | 100.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-5555555555",
  "resource_name": "dev-spanner-large",
  "resource_type": "cloud_spanner_devtest_overprovisioned",
  "instance_config": "regional-us-central1",
  "state": "READY",
  "node_count": 3,
  "processing_units": 3000,
  "labels": {
    "environment": "dev",
    "team": "platform"
  },
  "current_cost_monthly": 1971.00,
  "recommended_processing_units": 300,
  "recommended_cost_monthly": 197.10,
  "estimated_monthly_waste": 1773.90,
  "already_wasted": 5321.70,
  "savings_percentage": 90,
  "confidence": "high",
  "recommendation": "Reduce to 300 PU for dev/test environment",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `cloud_spanner_idle` - Instances Idle (Zero Queries)

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, récupérer métriques API requests (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances:
    instance_id = instance.name.split('/')[-1]

    # 3. Query API request count
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    api_requests_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="spanner_instance" AND resource.instance_id="{instance_id}" AND metric.type="spanner.googleapis.com/instance/api_request_count"',
            "interval": interval,
        }
    )

    # 4. Calculer total requests
    total_requests = sum([
        point.value.int64_value
        for series in api_requests_metrics
        for point in series.points
    ])

    # 5. Détection si zero requests
    if total_requests == 0:
        # Instance idle = 100% waste
```

**Critères :**
- `total_api_requests == 0` sur 14 jours
- Instance active (state = READY)
- Age >7 jours (éviter faux positifs)

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/api_request_count"'
)
```

#### Calcul de Coût

**Formule :**

Instance idle = 100% waste :

```python
# Récupérer config instance
if instance.node_count > 0:
    total_pu = instance.node_count * 1000
else:
    total_pu = instance.processing_units

is_multiregional = 'nam' in instance.config or 'eur' in instance.config

if is_multiregional:
    cost_per_pu = 2.19
else:
    cost_per_pu = 0.657

# Coût nodes
nodes_cost = total_pu * cost_per_pu

# Storage
storage_size_gb = get_storage_size(instance)  # Via métriques
storage_pricing = 0.50 if is_multiregional else 0.30
storage_cost = storage_size_gb * storage_pricing

# Backups
backup_size_gb = storage_size_gb * 2  # Estimation
backup_pricing = 0.30 if is_multiregional else 0.20
backup_cost = backup_size_gb * backup_pricing

# Coût total = 100% waste
monthly_cost = nodes_cost + storage_cost + backup_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Instance regional 1 node idle depuis 60 jours :
```python
nodes_cost = 1000 * $0.657 = $657
storage_cost = 100 * $0.30 = $30
backup_cost = 200 * $0.20 = $40
monthly_cost = $727
already_wasted = $727 * (60/30) = $1,454
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 14 | Période analyse requests |
| `min_age_days` | int | 7 | Âge minimum instance |
| `min_requests_threshold` | int | 0 | Requests min pour être actif |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-7777777777",
  "resource_name": "unused-spanner-db",
  "resource_type": "cloud_spanner_idle",
  "instance_config": "regional-us-east1",
  "state": "READY",
  "node_count": 1,
  "processing_units": 1000,
  "api_metrics": {
    "total_requests_14d": 0
  },
  "creation_time": "2024-09-05T10:00:00Z",
  "age_days": 58,
  "estimated_monthly_cost": 727.00,
  "already_wasted": 1404.23,
  "confidence": "high",
  "recommendation": "Delete instance - zero API requests in 14 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `cloud_spanner_pu_suboptimal` - Processing Units Suboptimal

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances avec nodes (pas PU granulaires)
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

node_based_instances = [i for i in instances if i.node_count > 0]

# 2. Pour chaque instance, analyser si PU granulaire serait mieux
for instance in node_based_instances:
    current_nodes = instance.node_count
    current_pu = current_nodes * 1000

    # 3. Récupérer CPU moyen
    avg_cpu = get_avg_cpu(instance, lookback_days=14)

    # 4. Calculer PU optimal
    # Spanner optimal: 65% CPU
    optimal_pu = int(current_pu * (avg_cpu / 65.0))
    optimal_pu = max(100, optimal_pu)

    # 5. Vérifier si PU granulaire offre économie
    # Si optimal_pu n'est pas multiple de 1000, PU plus efficace

    if optimal_pu % 1000 != 0 and optimal_pu < current_pu:
        # Exemple: optimal = 1500 PU
        # Nodes: 2 nodes (2000 PU) = over-provisioned
        # PU: 1500 PU exact = économie

        # Calculer économie
        is_multiregional = 'nam' in instance.config or 'eur' in instance.config
        cost_per_pu = 2.19 if is_multiregional else 0.657

        current_cost = current_pu * cost_per_pu
        optimal_cost = optimal_pu * cost_per_pu

        monthly_waste = current_cost - optimal_cost

        if monthly_waste >= min_savings_threshold:
            # PU granulaire recommandé = économie
```

**Critères :**
- Instance avec `node_count > 0` (pas déjà en PU)
- `optimal_pu % 1000 != 0` (besoin granularité)
- `optimal_pu < current_pu` (économie possible)

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API (CPU)
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/cpu/utilization"'
)
```

#### Calcul de Coût

**Formule :**

Nodes → Processing Units = économie granularité :

```python
# Exemple: 2 nodes avec CPU 50%

current_nodes = 2
current_pu = 2000
avg_cpu = 50.0

# PU optimal pour 65% CPU
optimal_pu = int(2000 * (50.0 / 65.0))  # 1538 PU

# Arrondi à centaine supérieure
optimal_pu = 1600  # PU (granularité 100)

# Regional instance
cost_per_pu = 0.657

# Coût actuel (nodes)
current_cost = 2000 * 0.657 = $1,314

# Coût optimal (PU)
optimal_cost = 1600 * 0.657 = $1,051

# Waste
monthly_waste = $1,314 - $1,051 = $263

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance 2 nodes avec CPU 50% depuis 120 jours :
```python
current_cost = $1,314/mois (2 nodes)
optimal_cost = $1,051/mois (1600 PU)
monthly_waste = $263
already_wasted = $263 * (120/30) = $1,052
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `target_cpu` | float | 65.0 | CPU optimal Spanner |
| `lookback_days` | int | 14 | Période analyse CPU |
| `min_savings_threshold` | float | 50.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3333333333",
  "resource_name": "prod-spanner-nodes",
  "resource_type": "cloud_spanner_pu_suboptimal",
  "instance_config": "regional-europe-west1",
  "state": "READY",
  "current_node_count": 2,
  "current_processing_units": 2000,
  "cpu_metrics": {
    "avg_cpu_14d": 51.2
  },
  "recommended_processing_units": 1600,
  "current_cost_monthly": 1314.00,
  "recommended_cost_monthly": 1051.20,
  "estimated_monthly_waste": 262.80,
  "already_wasted": 1051.20,
  "savings_percentage": 20,
  "confidence": "medium",
  "recommendation": "Switch to Processing Units for better granularity (2 nodes → 1600 PU)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `cloud_spanner_empty_databases` - Instances avec Databases Vides

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, lister databases
from google.cloud import spanner_admin_database_v1

database_admin_client = spanner_admin_database_v1.DatabaseAdminClient()

for instance in instances:
    instance_path = instance.name

    # 3. Lister databases
    databases = database_admin_client.list_databases(parent=instance_path)

    database_list = list(databases)

    # 4. Vérifier si databases vides
    if len(database_list) == 0:
        # Instance sans databases = waste évident
        continue

    # 5. Pour chaque database, vérifier si tables existent
    empty_databases = 0

    for database in database_list:
        database_path = database.name

        # Récupérer DDL (schema)
        db_ddl = database_admin_client.get_database_ddl(database=database_path)

        # Si aucune DDL statement = database vide
        if not db_ddl.statements or len(db_ddl.statements) == 0:
            empty_databases += 1

    # 6. Détection si toutes databases vides
    if empty_databases == len(database_list) and len(database_list) > 0:
        # Instance avec databases vides = waste
```

**Critères :**
- Instance active (state = READY)
- Databases existent MAIS sans tables (DDL vide)
- Age >7 jours

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Spanner Database Admin API
database_admin_client.list_databases(parent=instance_path)
database_admin_client.get_database_ddl(database=database_path)
```

#### Calcul de Coût

**Formule :**

Databases vides = 100% waste (aucune donnée) :

```python
# Instance avec databases vides = inutilisée

if instance.node_count > 0:
    total_pu = instance.node_count * 1000
else:
    total_pu = instance.processing_units

is_multiregional = 'nam' in instance.config or 'eur' in instance.config
cost_per_pu = 2.19 if is_multiregional else 0.657

# Coût nodes
nodes_cost = total_pu * cost_per_pu

# Storage minimal (databases vides)
storage_cost = 10 * (0.50 if is_multiregional else 0.30)  # 10 GB minimal

# Backups
backup_cost = 15 * (0.30 if is_multiregional else 0.20)

# Coût total = 100% waste
monthly_cost = nodes_cost + storage_cost + backup_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Instance regional 1 node avec databases vides depuis 30 jours :
```python
nodes_cost = 1000 * $0.657 = $657
storage_cost = 10 * $0.30 = $3
backup_cost = 15 * $0.20 = $3
monthly_cost = $663
already_wasted = $663 * (30/30) = $663
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 7 | Âge minimum instance |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-8888888888",
  "resource_name": "empty-spanner-instance",
  "resource_type": "cloud_spanner_empty_databases",
  "instance_config": "regional-us-central1",
  "state": "READY",
  "node_count": 1,
  "processing_units": 1000,
  "databases": [
    {
      "name": "test-db",
      "state": "READY",
      "has_tables": false
    }
  ],
  "total_databases": 1,
  "empty_databases": 1,
  "creation_time": "2024-10-03T10:00:00Z",
  "age_days": 30,
  "estimated_monthly_cost": 663.00,
  "already_wasted": 663.00,
  "confidence": "high",
  "recommendation": "Delete instance - all databases are empty",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `cloud_spanner_untagged` - Instances Non Taguées

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque instance, vérifier labels
for instance in instances:
    labels = instance.labels if hasattr(instance, 'labels') else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged instance = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Instances non taguées = perte de visibilité
# Coût estimé = 5% du coût instance

if instance.node_count > 0:
    total_pu = instance.node_count * 1000
else:
    total_pu = instance.processing_units

is_multiregional = 'nam' in instance.config or 'eur' in instance.config
cost_per_pu = 2.19 if is_multiregional else 0.657

nodes_cost = total_pu * cost_per_pu

# Governance waste = 5%
governance_waste_percentage = 0.05
monthly_waste = nodes_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance multi-regional 3 nodes sans labels depuis 180 jours :
```python
nodes_cost = 3000 * $2.19 = $6,570
monthly_waste = $6,570 * 0.05 = $328.50
already_wasted = $328.50 * (180/30) = $1,971.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1010101010",
  "resource_name": "unnamed-spanner-47",
  "resource_type": "cloud_spanner_untagged",
  "instance_config": "nam3",
  "state": "READY",
  "node_count": 3,
  "processing_units": 3000,
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_time": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "instance_monthly_cost": 6570.00,
  "estimated_monthly_waste": 328.50,
  "already_wasted": 1971.00,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `cloud_spanner_low_cpu` - Nodes avec CPU Faible

#### Détection

**Logique :**

Analyser CPU node par node (granularité fine) :

```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, récupérer CPU par node (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances:
    instance_id = instance.name.split('/')[-1]

    # 3. Query CPU utilization moyenne ET par node
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Métrique CPU avec dimension node
    cpu_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="spanner_instance" AND resource.instance_id="{instance_id}" AND metric.type="spanner.googleapis.com/instance/cpu/utilization_by_priority"',
            "interval": interval,
        }
    )

    # 4. Analyser CPU global
    all_cpu_values = [
        point.value.double_value
        for series in cpu_metrics
        for point in series.points
    ]

    avg_cpu = (sum(all_cpu_values) / len(all_cpu_values) * 100) if all_cpu_values else 0

    # 5. Détection si CPU <20% (très sous-utilisé)
    if avg_cpu < cpu_threshold:
        # Recommandation agressive: réduire PU
        # Spanner optimal = 65% CPU
        # Si 15% CPU → réduire à ~25% des PU actuels

        if instance.node_count > 0:
            current_pu = instance.node_count * 1000
        else:
            current_pu = instance.processing_units

        # PU optimal
        optimal_pu = max(100, int(current_pu * (avg_cpu / 65.0)))

        # Low CPU = waste significatif
```

**Critères :**
- `avg_cpu < 20%` sur 14 jours
- Instance active (state = READY)
- Recommandation: réduction agressive PU

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API (CPU détaillé)
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/cpu/utilization_by_priority"'
)
```

#### Calcul de Coût

**Formule :**

CPU <20% = opportunité réduction massive :

```python
# Exemple: 5 nodes avec CPU 15%

current_pu = 5000
avg_cpu = 15.0

# PU optimal pour 65% CPU
optimal_pu = int(5000 * (15.0 / 65.0))  # 1154 PU
optimal_pu = max(100, optimal_pu)
optimal_pu = 1200  # Arrondi

# Regional instance
cost_per_pu = 0.657

current_cost = 5000 * 0.657 = $3,285
optimal_cost = 1200 * 0.657 = $788

# Waste
monthly_waste = $3,285 - $788 = $2,497

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance 5 nodes avec CPU 15% depuis 90 jours :
```python
current_cost = $3,285/mois
optimal_cost = $788/mois (1200 PU)
monthly_waste = $2,497
already_wasted = $2,497 * (90/30) = $7,491
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 20.0 | CPU % maximum |
| `target_cpu` | float | 65.0 | CPU optimal Spanner |
| `lookback_days` | int | 14 | Période analyse |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-2020202020",
  "resource_name": "low-traffic-spanner",
  "resource_type": "cloud_spanner_low_cpu",
  "instance_config": "regional-us-west1",
  "state": "READY",
  "node_count": 5,
  "processing_units": 5000,
  "cpu_metrics": {
    "avg_cpu_14d": 16.8,
    "max_cpu_14d": 28.3
  },
  "recommended_processing_units": 1200,
  "current_cost_monthly": 3285.00,
  "recommended_cost_monthly": 788.40,
  "estimated_monthly_waste": 2496.60,
  "already_wasted": 7489.80,
  "savings_percentage": 76,
  "confidence": "high",
  "recommendation": "Reduce from 5 nodes to 1200 PU (76% cost savings)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `cloud_spanner_storage_overprovisioned` - Storage Over-Provisioned

#### Détection

**Logique :**

Analyser croissance storage et projections :

```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, récupérer storage utilisé
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances:
    instance_id = instance.name.split('/')[-1]

    # 3. Query storage used (30 derniers jours pour trend)
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 30*24*3600},
    })

    storage_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="spanner_instance" AND resource.instance_id="{instance_id}" AND metric.type="spanner.googleapis.com/instance/storage/used_bytes"',
            "interval": interval,
        }
    )

    # 4. Calculer storage moyen et tendance
    storage_values = [
        point.value.int64_value
        for series in storage_metrics
        for point in series.points
    ]

    if not storage_values:
        continue

    avg_storage_bytes = sum(storage_values) / len(storage_values)
    avg_storage_gb = avg_storage_bytes / (1024**3)

    # 5. Analyser tendance croissance (30 jours)
    # Si storage stable ou décroît, surprovisioning détectable

    first_week_storage = sum(storage_values[:len(storage_values)//4]) / (len(storage_values)//4)
    last_week_storage = sum(storage_values[-len(storage_values)//4:]) / (len(storage_values)//4)

    growth_rate = ((last_week_storage - first_week_storage) / first_week_storage * 100) if first_week_storage > 0 else 0

    # 6. Détection si storage stable (<5% growth) et faible
    if growth_rate < 5.0 and avg_storage_gb < 100:
        # Storage minimal = possibilité réduction coûts via TTL, archiving
        # Ou migration vers Cloud SQL (moins cher pour petit storage)
```

**Critères :**
- `avg_storage_gb < 100 GB` (petit storage)
- Croissance <5% sur 30 jours (stable)
- Recommandation: optimisation storage ou migration Cloud SQL

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Monitoring API (storage metrics)
monitoring_client.list_time_series(
    filter='metric.type="spanner.googleapis.com/instance/storage/used_bytes"'
)
```

#### Calcul de Coût

**Formule :**

Petit storage sur Spanner = surcoût vs Cloud SQL :

```python
# Exemple: Instance regional 1 node avec 50 GB storage

# Spanner costs
spanner_nodes_cost = 1000 * 0.657 = $657
spanner_storage_cost = 50 * 0.30 = $15
spanner_backup_cost = 100 * 0.20 = $20
spanner_total = $692/mois

# Cloud SQL équivalent (db-n1-standard-2, 50 GB SSD)
cloudsql_instance_cost = 92.40
cloudsql_storage_cost = 50 * 0.17 = $8.50
cloudsql_backup_cost = 75 * 0.08 = $6
cloudsql_total = $106.90/mois

# Waste = différence Spanner vs Cloud SQL
# Note: migration complexe, mais économie significative
monthly_waste = spanner_total - cloudsql_total  # $585.10

# Économie potentielle
# Confidence: low (migration complexe)
```

**Exemple :**

Instance Spanner 1 node avec 50 GB vs Cloud SQL équivalent :
```python
spanner_cost = $692/mois
cloudsql_cost = $107/mois
monthly_waste = $585 (si migration acceptable)
```

**Note :** Scénario à confidence LOW car migration Spanner → Cloud SQL complexe.

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_storage_gb` | int | 100 | Storage max pour recommandation |
| `max_growth_rate_pct` | float | 5.0 | Croissance max % |
| `lookback_days` | int | 30 | Période analyse trend |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3030303030",
  "resource_name": "small-spanner-db",
  "resource_type": "cloud_spanner_storage_overprovisioned",
  "instance_config": "regional-us-central1",
  "state": "READY",
  "node_count": 1,
  "processing_units": 1000,
  "storage_metrics": {
    "avg_storage_gb": 52.3,
    "growth_rate_30d_pct": 2.1
  },
  "current_cost_monthly": 692.00,
  "alternative_cloudsql_cost_monthly": 106.90,
  "estimated_monthly_waste": 585.10,
  "confidence": "low",
  "recommendation": "Consider migrating to Cloud SQL for small datasets (<100 GB)",
  "migration_complexity": "high",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `cloud_spanner_excessive_backups` - Backups Excessifs

#### Détection

**Logique :**

Analyser rétention backups et coût cumulé :

```python
# 1. Lister toutes les instances
instances = spanner_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, lister backups
from google.cloud import spanner_admin_database_v1

database_admin_client = spanner_admin_database_v1.DatabaseAdminClient()

for instance in instances:
    # 3. Lister databases
    databases = database_admin_client.list_databases(parent=instance.name)

    for database in databases:
        # 4. Lister backups pour database
        backup_parent = instance.name

        backups = database_admin_client.list_backups(parent=backup_parent)

        backup_list = list(backups)

        # 5. Analyser âge et taille backups
        total_backup_size_gb = 0
        old_backups = []

        for backup in backup_list:
            backup_size_bytes = backup.size_bytes
            backup_size_gb = backup_size_bytes / (1024**3)

            total_backup_size_gb += backup_size_gb

            # Calculer âge backup
            creation_time = backup.create_time
            age_days = (now - creation_time).days

            # 6. Identifier backups >90 jours (rétention excessive pour non-prod)
            if age_days >= excessive_retention_days:
                old_backups.append({
                    'name': backup.name,
                    'age_days': age_days,
                    'size_gb': backup_size_gb
                })

        # 7. Détection si backups excessifs
        # Labels instance pour vérifier environment
        labels = instance.labels if hasattr(instance, 'labels') else {}
        environment = labels.get('environment', '').lower()

        # Dev/test avec backups >90 jours = waste
        if environment in ['dev', 'test', 'staging'] and len(old_backups) > 0:
            # Backups excessifs pour dev/test
```

**Critères :**
- Backups >90 jours pour dev/test OU
- Backups >365 jours pour prod
- Labels `environment` indiquant non-prod

**API Calls :**
```python
# Cloud Spanner Admin API
spanner_client.list_instances(parent=f"projects/{project_id}")

# Cloud Spanner Database Admin API
database_admin_client.list_databases(parent=instance_path)
database_admin_client.list_backups(parent=instance_path)
```

#### Calcul de Coût

**Formule :**

Backups excessifs = coût storage backups :

```python
# Exemple: Instance dev avec 500 GB backups (>90 jours)

excessive_backup_size_gb = 500

# Regional ou multi-regional
is_multiregional = 'nam' in instance.config or 'eur' in instance.config

backup_pricing = 0.30 if is_multiregional else 0.20

# Coût backups excessifs
monthly_waste = excessive_backup_size_gb * backup_pricing  # $100 (regional)

# Coût gaspillé cumulé
# Backups >90 jours = 3+ mois de coût
months_excessive = 3  # Estimation conservative
already_wasted = monthly_waste * months_excessive
```

**Exemple :**

Instance dev regional avec 500 GB backups >90 jours :
```python
excessive_backup_size = 500 GB
backup_pricing = $0.20/GB/mois
monthly_waste = 500 * $0.20 = $100
already_wasted = $100 * 3 = $300 (derniers 3 mois)
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `excessive_retention_days_devtest` | int | 90 | Rétention max dev/test |
| `excessive_retention_days_prod` | int | 365 | Rétention max production |
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels non-prod |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-4040404040",
  "resource_name": "dev-spanner-with-old-backups",
  "resource_type": "cloud_spanner_excessive_backups",
  "instance_config": "regional-us-central1",
  "state": "READY",
  "labels": {
    "environment": "dev"
  },
  "backup_analysis": {
    "total_backups": 12,
    "old_backups": 8,
    "total_backup_size_gb": 500,
    "old_backup_size_gb": 400,
    "oldest_backup_age_days": 180
  },
  "estimated_monthly_waste": 80.00,
  "already_wasted": 240.00,
  "confidence": "medium",
  "recommendation": "Delete backups >90 days for dev environment",
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
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable spanner.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account

```bash
# Ajouter permissions Cloud Spanner
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/spanner.viewer"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

---

### Tests Unitaires - Créer Instances de Test

#### Scénario 1: Instance Sous-Utilisée

```bash
# Créer instance regional avec 3 nodes
gcloud spanner instances create test-underutilized-instance \
  --config=regional-us-central1 \
  --description="Test underutilized" \
  --nodes=3

# Créer database
gcloud spanner databases create test-db \
  --instance=test-underutilized-instance

# Générer très faible charge (<30% CPU)
# Utiliser gcloud spanner queries périodiques légères

# Attendre 14 jours pour métriques
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_underutilized",
  "node_count": 3,
  "processing_units": 3000,
  "cpu_metrics": {"avg_cpu_14d": "<30"},
  "estimated_monthly_waste": "~1314"
}
```

---

#### Scénario 2: Multi-Regional Inutile

```bash
# Créer instance multi-regional pour dev
gcloud spanner instances create test-multiregional-dev \
  --config=nam3 \
  --description="Test multi-regional dev" \
  --nodes=3 \
  --labels=environment=dev,team=backend
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_unnecessary_multiregional",
  "instance_config": "nam3",
  "labels": {"environment": "dev"},
  "estimated_monthly_waste": "~4799"
}
```

---

#### Scénario 3: Dev/Test Over-Provisioned

```bash
# Créer instance dev avec 3 nodes
gcloud spanner instances create test-devtest-large \
  --config=regional-us-east1 \
  --description="Test dev large" \
  --nodes=3 \
  --labels=environment=dev,team=platform
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_devtest_overprovisioned",
  "node_count": 3,
  "labels": {"environment": "dev"},
  "estimated_monthly_waste": "~1774"
}
```

---

#### Scénario 4: Instance Idle

```bash
# Créer instance
gcloud spanner instances create test-idle-instance \
  --config=regional-us-central1 \
  --description="Test idle" \
  --nodes=1

# Créer database mais NE PAS exécuter de queries
gcloud spanner databases create test-db \
  --instance=test-idle-instance

# Attendre 14 jours sans aucune requête
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_idle",
  "api_metrics": {"total_requests_14d": 0},
  "estimated_monthly_cost": "~727"
}
```

---

#### Scénario 5: Processing Units Suboptimal

```bash
# Créer instance avec nodes (pas PU)
gcloud spanner instances create test-pu-suboptimal \
  --config=regional-europe-west1 \
  --description="Test PU suboptimal" \
  --nodes=2

# Générer charge CPU ~50%
# Attendre 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_pu_suboptimal",
  "current_node_count": 2,
  "recommended_processing_units": 1600,
  "estimated_monthly_waste": "~263"
}
```

---

#### Scénario 6: Databases Vides

```bash
# Créer instance
gcloud spanner instances create test-empty-databases \
  --config=regional-us-central1 \
  --description="Test empty DBs" \
  --nodes=1

# Créer database SANS tables
gcloud spanner databases create empty-db \
  --instance=test-empty-databases

# Ne pas créer de schema (pas de CREATE TABLE)

# Attendre 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_empty_databases",
  "total_databases": 1,
  "empty_databases": 1,
  "estimated_monthly_cost": "~663"
}
```

---

#### Scénario 7: Instance Non Taguée

```bash
# Créer instance SANS labels
gcloud spanner instances create test-untagged-instance \
  --config=nam3 \
  --description="Test untagged" \
  --nodes=3
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_untagged",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~328.50"
}
```

---

#### Scénario 8: Nodes avec CPU Faible

```bash
# Créer instance large
gcloud spanner instances create test-low-cpu \
  --config=regional-us-west1 \
  --description="Test low CPU" \
  --nodes=5

# Créer database avec charge très légère (CPU <20%)
gcloud spanner databases create test-db \
  --instance=test-low-cpu

# Attendre 14 jours avec charge minimale
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_low_cpu",
  "node_count": 5,
  "cpu_metrics": {"avg_cpu_14d": "<20"},
  "estimated_monthly_waste": "~2497"
}
```

---

#### Scénario 9: Storage Over-Provisioned

```bash
# Créer instance avec 1 node
gcloud spanner instances create test-small-storage \
  --config=regional-us-central1 \
  --description="Test small storage" \
  --nodes=1

# Créer database avec données minimales (<100 GB)
gcloud spanner databases create test-db \
  --instance=test-small-storage

# Insérer 50 GB données max

# Attendre 30 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_storage_overprovisioned",
  "storage_metrics": {"avg_storage_gb": "<100"},
  "alternative_cloudsql_cost_monthly": "~107",
  "confidence": "low"
}
```

---

#### Scénario 10: Backups Excessifs

```bash
# Créer instance dev
gcloud spanner instances create test-excessive-backups \
  --config=regional-us-central1 \
  --description="Test excessive backups" \
  --nodes=1 \
  --labels=environment=dev

# Créer database
gcloud spanner databases create test-db \
  --instance=test-excessive-backups

# Créer backup
gcloud spanner backups create test-backup-old \
  --instance=test-excessive-backups \
  --database=test-db \
  --retention-period=365d

# Attendre (ou simuler ancien backup via API timestamp)
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_spanner_excessive_backups",
  "labels": {"environment": "dev"},
  "backup_analysis": {
    "oldest_backup_age_days": ">90"
  },
  "estimated_monthly_waste": "~80"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script validation Cloud Spanner
"""

from google.cloud import spanner_admin_instance_v1
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    spanner_client = spanner_admin_instance_v1.InstanceAdminClient()

    # Lister instances
    instances = list(spanner_client.list_instances(parent=f"projects/{PROJECT_ID}"))

    print(f"✅ Found {len(instances)} Cloud Spanner instances")

    scenarios_detected = {
        'underutilized': 0,
        'unnecessary_multiregional': 0,
        'devtest_overprovisioned': 0,
        'idle': 0,
        'pu_suboptimal': 0,
        'empty_databases': 0,
        'untagged': 0,
        'low_cpu': 0,
        'storage_overprovisioned': 0,
        'excessive_backups': 0,
    }

    for instance in instances:
        name = instance.name.split('/')[-1]

        # Scenario 2: Multi-regional inutile
        if 'nam' in instance.config or 'eur' in instance.config:
            labels = instance.labels if hasattr(instance, 'labels') else {}
            if labels.get('environment') in ['dev', 'test']:
                scenarios_detected['unnecessary_multiregional'] += 1
                print(f"✅ Detected scenario 2 (unnecessary multi-regional): {name}")

        # Scenario 3: Dev/test over-provisioned
        labels = instance.labels if hasattr(instance, 'labels') else {}
        if labels.get('environment') in ['dev', 'test'] and instance.node_count >= 3:
            scenarios_detected['devtest_overprovisioned'] += 1
            print(f"✅ Detected scenario 3 (dev/test over-provisioned): {name}")

        # Scenario 7: Untagged
        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Detected scenario 7 (untagged): {name}")

    # Rapport
    print("\n📊 Detection Summary:")
    for scenario, count in scenarios_detected.items():
        print(f"  - {scenario}: {count} instances")

    print(f"\n✅ Total waste detected: {sum(scenarios_detected.values())} instances")

if __name__ == '__main__':
    test_all_scenarios()
```

---

### Cleanup

```bash
# Supprimer toutes instances test
gcloud spanner instances delete test-underutilized-instance --quiet
gcloud spanner instances delete test-multiregional-dev --quiet
gcloud spanner instances delete test-devtest-large --quiet
gcloud spanner instances delete test-idle-instance --quiet
gcloud spanner instances delete test-pu-suboptimal --quiet
gcloud spanner instances delete test-empty-databases --quiet
gcloud spanner instances delete test-untagged-instance --quiet
gcloud spanner instances delete test-low-cpu --quiet
gcloud spanner instances delete test-small-storage --quiet
gcloud spanner instances delete test-excessive-backups --quiet
```

---

## Références

### Documentation GCP

- [Cloud Spanner API](https://cloud.google.com/spanner/docs/reference/rest)
- [Cloud Spanner Pricing](https://cloud.google.com/spanner/pricing)
- [Processing Units vs Nodes](https://cloud.google.com/spanner/docs/compute-capacity)
- [Instance Configurations](https://cloud.google.com/spanner/docs/instance-configurations)
- [Monitoring Metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-spanner)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md)
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md)
- [GCP_GKE_CLUSTER_SCENARIOS_100.md](./GCP_GKE_CLUSTER_SCENARIOS_100.md)
- [GCP_CLOUD_SQL_SCENARIOS_100.md](./GCP_CLOUD_SQL_SCENARIOS_100.md)

### Équivalences AWS/Azure

- **AWS Aurora Global Database** → GCP Cloud Spanner
- **Azure Cosmos DB** → GCP Cloud Spanner
- **AWS DynamoDB Global Tables** → GCP Cloud Spanner (aspect global)

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
