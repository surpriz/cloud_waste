# CloudWaste - Couverture 100% GCP Cloud SQL

**Resource Type:** `Database : Cloud SQL`
**Provider:** Google Cloud Platform (GCP)
**API:** `sqladmin.googleapis.com` (Cloud SQL Admin API v1)
**Équivalents:** AWS RDS, Azure SQL Database
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing Cloud SQL](#modèle-de-pricing-cloud-sql)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Instances Arrêtées >30 Jours](#1-cloud_sql_stopped---instances-arrêtées-30-jours)
  - [2. Instances Idle (Zero Connections)](#2-cloud_sql_idle---instances-idle-zero-connections)
  - [3. Instances Over-Provisioned](#3-cloud_sql_overprovisioned---instances-over-provisioned)
  - [4. Ancien Type de Machine](#4-cloud_sql_old_machine_type---ancien-type-de-machine)
  - [5. Instances Dev/Test 24/7](#5-cloud_sql_devtest_247---instances-devtest-247)
  - [6. Read Replicas Inutilisés](#6-cloud_sql_unused_replicas---read-replicas-inutilisés)
  - [7. Instances Non Taguées](#7-cloud_sql_untagged---instances-non-taguées)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Instances avec Zéro I/O](#8-cloud_sql_zero_io---instances-avec-zéro-io)
  - [9. Storage Over-Provisioned](#9-cloud_sql_storage_overprovisioned---storage-over-provisioned)
  - [10. High Availability Inutile](#10-cloud_sql_unnecessary_ha---high-availability-inutile)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte Cloud SQL

**Cloud SQL** est le service de bases de données relationnelles **managé** de GCP, supportant :

- **MySQL** (5.6, 5.7, 8.0)
- **PostgreSQL** (9.6, 10, 11, 12, 13, 14, 15)
- **SQL Server** (2017 Standard, 2017 Enterprise, 2019 Standard, 2019 Enterprise)

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Machine Types** | Shared-core, Standard, High-memory | Core pricing component |
| **Storage** | SSD (performance) ou HDD (économique) | $0.17/GB (SSD), $0.09/GB (HDD) |
| **Backups** | Automatiques (7-365 jours rétention) | $0.08/GB/mois |
| **High Availability** | Multi-zone failover | +100% instance cost |
| **Read Replicas** | Scaling lecture | Full instance cost/replica |
| **Private IP** | VPC peering | Inclus |
| **Public IP** | Internet access | Inclus |

### États d'Instance et Facturation

| État | Instance Cost | Storage Cost | Backup Cost | Notes |
|------|--------------|--------------|-------------|-------|
| **RUNNABLE** | ✅ 100% | ✅ 100% | ✅ 100% | Facturé pleinement |
| **STOPPED** | ❌ 0% | ✅ 100% | ✅ 100% | Économie instance uniquement |
| **SUSPENDED** | ❌ 0% | ✅ 100% | ✅ 100% | Suspendu (billing issue) |
| **DELETED** | ❌ 0% | ❌ 0% | ❌ 0% | Plus de coûts |

**⚠️ Important :** Instance arrêtée continue de payer **storage + backups** (~30-50% du coût total).

### Waste Typique

1. **Instances arrêtées** : Storage + backups facturés ($20-100/mois)
2. **Instances idle** : Zero connections = 100% gaspillage
3. **Over-provisioning** : db-n1-standard-8 pour 10 connexions = surcoût
4. **High Availability** : HA activé pour dev/test = +100% coût inutile
5. **Read replicas** : Réplicas sans lecture = instance complète gaspillée
6. **Storage over-provisioned** : 500 GB alloué, 50 GB utilisé = 450 GB × $0.17
7. **Backups excessifs** : Rétention 365 jours pour dev = coûts cumulés

---

## Modèle de Pricing Cloud SQL

### Machine Types Pricing (par mois, us-central1)

#### MySQL / PostgreSQL

| Machine Type | vCPUs | RAM (GB) | Prix/Mois | Use Case |
|-------------|-------|---------|-----------|----------|
| **db-f1-micro** | Shared | 0.6 GB | $7.67 | Dev/Test minimal |
| **db-g1-small** | Shared | 1.7 GB | $25.00 | Dev/Test léger |
| **db-n1-standard-1** | 1 | 3.75 GB | $46.20 | Small production |
| **db-n1-standard-2** | 2 | 7.5 GB | $92.40 | Medium workloads |
| **db-n1-standard-4** | 4 | 15 GB | $184.80 | Production standard |
| **db-n1-standard-8** | 8 | 30 GB | $369.60 | Large production |
| **db-n1-highmem-2** | 2 | 13 GB | $113.52 | Memory-intensive |
| **db-n1-highmem-4** | 4 | 26 GB | $227.04 | High-memory DB |
| **db-custom-2-7680** | 2 | 7.5 GB | $51.10 | Custom (flexible) |
| **db-custom-4-15360** | 4 | 15 GB | $102.20 | Custom (flexible) |

**Notes :**
- db-n1 = génération ancienne (standard depuis années)
- db-custom = personnalisable (vCPU + RAM séparément)
- Pricing inclut management (pas de fee séparé comme RDS)

#### SQL Server

| Edition | Machine Type | vCPUs | RAM (GB) | Prix/Mois |
|---------|-------------|-------|---------|-----------|
| **Standard 2019** | db-custom-2-7680 | 2 | 7.5 GB | $351.00 |
| **Standard 2019** | db-custom-4-15360 | 4 | 15 GB | $702.00 |
| **Enterprise 2019** | db-custom-4-15360 | 4 | 15 GB | $2,106.00 |

**Note :** SQL Server significativement plus cher (licences Microsoft incluses).

### Storage Pricing

| Type | Prix/GB/Mois | Throughput | Use Case |
|------|-------------|-----------|----------|
| **SSD** | $0.17 | Haute performance | Production, OLTP |
| **HDD** | $0.09 | Standard | Dev/Test, archivage |

**Capacité :** 10 GB à 64 TB (SSD), 10 GB à 64 TB (HDD)

### Backups Pricing

- **Coût :** $0.08/GB/mois
- **Rétention :** 1 à 365 jours (7 jours par défaut)
- **Première backup complète, ensuite incrémentales**

Exemple : 100 GB database, backups 30 jours
```
Backup storage ≈ 150 GB (complet + incrémentaux)
Coût = 150 GB × $0.08 = $12.00/mois
```

### High Availability (HA)

- **Coût :** +100% du coût instance (standby replica dans autre zone)
- **Storage :** Répliqué automatiquement (inclus)
- **Failover :** Automatique (<60 secondes)

Exemple : db-n1-standard-2 avec HA
```
Instance sans HA: $92.40/mois
Instance avec HA: $92.40 × 2 = $184.80/mois
```

### Read Replicas

- **Coût :** Instance complète (même machine type que master)
- **Storage :** Séparé (répliqué depuis master)
- **Use case :** Scaling lecture, analytique

Exemple : 1 master + 2 read replicas (db-n1-standard-2)
```
Master: $92.40/mois
Replica 1: $92.40/mois
Replica 2: $92.40/mois
TOTAL: $277.20/mois
```

### Exemple Coût Total

**Production MySQL (db-n1-standard-4 + HA + 500 GB SSD):**
```
Instance (no HA): $184.80/mois
High Availability: $184.80/mois (standby)
Storage SSD: 500 GB × $0.17 = $85.00/mois
Backups: ~750 GB × $0.08 = $60.00/mois (30 jours rétention)
─────────────────────────────────────
TOTAL: $514.60/mois (~$6,175/an)
```

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `cloud_sql_stopped` - Instances Arrêtées >30 Jours

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances Cloud SQL
from google.cloud import sql_v1

sql_client = sql_v1.SqlInstancesServiceClient()

parent = f"projects/{project_id}"
instances = sql_client.list(parent=parent)

# 2. Pour chaque instance, vérifier state
for instance in instances:
    instance_name = instance.name
    state = instance.state  # RUNNABLE, STOPPED, SUSPENDED

    # 3. Détection si state = STOPPED
    if state == sql_v1.Instance.State.STOPPED:
        # 4. Calculer depuis quand arrêtée
        # Note: API ne fournit pas lastStopTime, utiliser state_change_timestamp
        # Ou analyser logs audit pour trouver dernière action STOP

        # Approximation: vérifier age instance et si jamais RUNNABLE récemment
        creation_time = instance.create_time
        age_days = (now - creation_time).days

        # Si instance créée >30 jours et STOPPED, probable waste
        if age_days >= min_age_days:
            # Instance arrêtée = waste détecté
```

**Critères :**
- `state == 'STOPPED'`
- `age >= min_age_days` (défaut: 30 jours)

**API Calls :**
```python
# Cloud SQL Admin API
from google.cloud import sql_v1

sql_client = sql_v1.SqlInstancesServiceClient()

# Lister instances
instances = sql_client.list(
    parent=f"projects/{project_id}"
)

# Get instance details
instance = sql_client.get(
    name=f"projects/{project_id}/instances/{instance_name}"
)
```

#### Calcul de Coût

**Formule :**

Instance arrêtée = paiement storage + backups (pas instance) :

```python
# Instance arrêtée ne paie PAS le coût instance
# MAIS paie storage + backups

# Récupérer config instance
database_engine = instance.database_version  # MYSQL_8_0, POSTGRES_14, etc.
machine_type = instance.settings.tier  # "db-n1-standard-2"
storage_size_gb = instance.settings.data_disk_size_gb
storage_type = instance.settings.data_disk_type  # PD_SSD, PD_HDD

# Storage cost (continue même si arrêté)
storage_pricing = {
    'PD_SSD': 0.17,   # $/GB/mois
    'PD_HDD': 0.09,
}

storage_cost = storage_size_gb * storage_pricing.get(storage_type, 0.17)

# Backup cost (continue même si arrêté)
# Estimation: backups ≈ 1.5x database size (complet + incrémentaux)
backup_size_gb = storage_size_gb * 1.5
backup_price_per_gb = 0.08

backup_cost = backup_size_gb * backup_price_per_gb

# Coût mensuel = storage + backups
monthly_cost = storage_cost + backup_cost

# Coût gaspillé depuis arrêt
stopped_days = age_days  # Approximation (si toujours arrêté)
already_wasted = monthly_cost * (stopped_days / 30.0)
```

**Exemple :**

Instance MySQL arrêtée avec 500 GB SSD depuis 60 jours :
```python
storage_size_gb = 500
storage_type = 'PD_SSD'
storage_cost = 500 * $0.17 = $85.00/mois

backup_size_gb = 500 * 1.5 = 750 GB
backup_cost = 750 * $0.08 = $60.00/mois

monthly_cost = $85.00 + $60.00 = $145.00/mois
already_wasted = $145.00 * (60/30) = $290.00
```

**Note :** Si instance jamais redémarrée, recommandation = créer snapshot final et supprimer.

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 30 | Âge minimum arrêt avant détection |
| `exclude_labels` | dict | `{}` | Labels pour exclure instances |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1234567890",
  "resource_name": "prod-mysql-stopped",
  "resource_type": "cloud_sql_stopped",
  "region": "us-central1",
  "database_version": "MYSQL_8_0",
  "state": "STOPPED",
  "tier": "db-n1-standard-2",
  "storage_size_gb": 500,
  "storage_type": "PD_SSD",
  "creation_time": "2024-07-05T10:00:00Z",
  "age_days": 120,
  "stopped_days": 60,
  "storage_cost_monthly": 85.00,
  "backup_cost_monthly": 60.00,
  "estimated_monthly_cost": 145.00,
  "already_wasted": 290.00,
  "confidence": "high",
  "recommendation": "Create final snapshot and delete instance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `cloud_sql_idle` - Instances Idle (Zero Connections)

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances RUNNABLE
instances = sql_client.list(parent=f"projects/{project_id}")

runnable_instances = [i for i in instances if i.state == sql_v1.Instance.State.RUNNABLE]

# 2. Pour chaque instance, récupérer métriques connexions
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in runnable_instances:
    instance_name = instance.name

    # 3. Query active connections (14 derniers jours)
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Métrique: cloudsql.googleapis.com/database/network/connections
    connections_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/network/connections"',
            "interval": interval,
        }
    )

    # 4. Calculer connexions moyennes et max
    connection_values = [
        point.value.double_value
        for series in connections_metrics
        for point in series.points
    ]

    if not connection_values:
        # Pas de métriques = instance créée récemment ou problème
        continue

    avg_connections = sum(connection_values) / len(connection_values)
    max_connections = max(connection_values)

    # 5. Détection si zero connections
    if avg_connections == 0 and max_connections == 0:
        # Instance idle = waste détecté
```

**Critères :**
- `state == 'RUNNABLE'`
- `avg_connections == 0` sur 14 jours
- `max_connections == 0` (jamais de connexion)

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="cloudsql.googleapis.com/database/network/connections"'
)
```

#### Calcul de Coût

**Formule :**

Instance idle = 100% waste (aucune utilisation) :

```python
# Récupérer coût instance
machine_type = instance.settings.tier  # "db-n1-standard-2"

# Pricing machine types (MySQL/PostgreSQL)
machine_pricing = {
    'db-f1-micro': 7.67,
    'db-g1-small': 25.00,
    'db-n1-standard-1': 46.20,
    'db-n1-standard-2': 92.40,
    'db-n1-standard-4': 184.80,
    'db-n1-standard-8': 369.60,
    'db-custom-2-7680': 51.10,
    'db-custom-4-15360': 102.20,
}

instance_cost = machine_pricing.get(machine_type, 0)

# Storage cost
storage_size_gb = instance.settings.data_disk_size_gb
storage_type = instance.settings.data_disk_type

storage_pricing = {'PD_SSD': 0.17, 'PD_HDD': 0.09}
storage_cost = storage_size_gb * storage_pricing.get(storage_type, 0.17)

# Backup cost
backup_size_gb = storage_size_gb * 1.5
backup_cost = backup_size_gb * 0.08

# High Availability (si activé)
ha_enabled = instance.settings.availability_type == 'REGIONAL'  # HA enabled
if ha_enabled:
    instance_cost = instance_cost * 2  # Standby replica

# Coût total mensuel = 100% waste
monthly_cost = instance_cost + storage_cost + backup_cost

# Coût gaspillé depuis création (si jamais utilisé)
creation_time = instance.create_time
age_days = (now - creation_time).days
already_wasted = monthly_cost * (age_days / 30.0)
```

**Exemple :**

Instance db-n1-standard-2 + HA + 200 GB SSD, idle depuis création (90 jours) :
```python
instance_cost = $92.40 * 2 = $184.80 (avec HA)
storage_cost = 200 * $0.17 = $34.00
backup_cost = 300 * $0.08 = $24.00
monthly_cost = $242.80
already_wasted = $242.80 * (90/30) = $728.40
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 14 | Période analyse connexions |
| `min_connections_threshold` | float | 0.0 | Connexions min pour être actif |
| `exclude_labels` | dict | `{}` | Labels pour exclure |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9876543210",
  "resource_name": "unused-postgres-db",
  "resource_type": "cloud_sql_idle",
  "region": "us-east1",
  "database_version": "POSTGRES_14",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "availability_type": "REGIONAL",
  "storage_size_gb": 200,
  "storage_type": "PD_SSD",
  "connection_metrics": {
    "avg_connections_14d": 0.0,
    "max_connections_14d": 0.0
  },
  "creation_time": "2024-08-05T09:00:00Z",
  "age_days": 89,
  "instance_cost_monthly": 184.80,
  "storage_cost_monthly": 34.00,
  "backup_cost_monthly": 24.00,
  "estimated_monthly_cost": 242.80,
  "already_wasted": 721.13,
  "confidence": "high",
  "recommendation": "Delete instance - zero connections in 14 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `cloud_sql_overprovisioned` - Instances Over-Provisioned

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances RUNNABLE
instances = sql_client.list(parent=f"projects/{project_id}")

runnable_instances = [i for i in instances if i.state == sql_v1.Instance.State.RUNNABLE]

# 2. Pour chaque instance, récupérer métriques CPU et Memory
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in runnable_instances:
    instance_name = instance.name

    # 3. Query CPU utilization (14 jours)
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # CPU metric
    cpu_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/cpu/utilization"',
            "interval": interval,
        }
    )

    cpu_values = [point.value.double_value for series in cpu_metrics for point in series.points]
    avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

    # Memory metric
    memory_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/memory/utilization"',
            "interval": interval,
        }
    )

    memory_values = [point.value.double_value for series in memory_metrics for point in series.points]
    avg_memory = (sum(memory_values) / len(memory_values) * 100) if memory_values else 0

    # 4. Détection si CPU <30% ET Memory <40%
    if avg_cpu < cpu_threshold and avg_memory < memory_threshold:
        # 5. Calculer machine type recommandée (downgrade)
        current_tier = instance.settings.tier
        recommended_tier = calculate_recommended_tier(current_tier, avg_cpu, avg_memory)

        # Over-provisioned = waste détecté
```

**Critères :**
- `state == 'RUNNABLE'`
- `avg_cpu < 30%` ET `avg_memory < 40%` sur 14 jours
- Possibilité downgrade machine type

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/cpu/utilization"'
)

monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/memory/utilization"'
)
```

#### Calcul de Coût

**Formule :**

Over-provisioning = différence coût actuel vs recommandé :

```python
# Exemple: db-n1-standard-4 avec CPU 20%, Memory 30%

current_tier = 'db-n1-standard-4'
current_cost = 184.80  # $/mois

# Recommandation: db-n1-standard-2 (moitié ressources)
recommended_tier = 'db-n1-standard-2'
recommended_cost = 92.40  # $/mois

# Waste instance
instance_waste = current_cost - recommended_cost  # $92.40

# Si HA activé, waste doublé
ha_enabled = instance.settings.availability_type == 'REGIONAL'
if ha_enabled:
    instance_waste = instance_waste * 2  # Standby aussi over-provisioned

# Storage et backups identiques (pas de waste)
storage_cost = 100 * 0.17  # $17.00 (identique)
backup_cost = 150 * 0.08   # $12.00 (identique)

# Waste total
monthly_waste = instance_waste

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance db-n1-standard-4 + HA avec CPU 20%, Memory 30% depuis 120 jours :
```python
current_instance_cost = $184.80 * 2 = $369.60 (HA)
recommended_instance_cost = $92.40 * 2 = $184.80 (HA)
monthly_waste = $184.80
already_wasted = $184.80 * (120/30) = $739.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 30.0 | CPU % maximum pour over-provisioning |
| `memory_threshold` | float | 40.0 | Memory % maximum |
| `lookback_days` | int | 14 | Période analyse métriques |
| `min_savings_threshold` | float | 20.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-5555555555",
  "resource_name": "overprovisioned-mysql",
  "resource_type": "cloud_sql_overprovisioned",
  "region": "europe-west1",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-4",
  "availability_type": "REGIONAL",
  "cpu_metrics": {
    "avg_cpu_14d": 22.3,
    "max_cpu_14d": 45.1
  },
  "memory_metrics": {
    "avg_memory_14d": 31.8,
    "max_memory_14d": 52.0
  },
  "current_cost_monthly": 369.60,
  "recommended_tier": "db-n1-standard-2",
  "recommended_cost_monthly": 184.80,
  "estimated_monthly_waste": 184.80,
  "already_wasted": 739.20,
  "confidence": "high",
  "recommendation": "Downgrade to db-n1-standard-2 (half resources)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `cloud_sql_old_machine_type` - Ancien Type de Machine

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = sql_client.list(parent=f"projects/{project_id}")

for instance in instances:
    tier = instance.settings.tier  # "db-n1-standard-2"

    # 2. Détection si db-n1 (ancienne génération)
    if tier.startswith('db-n1-'):
        # 3. Calculer équivalent db-custom (plus flexible)
        # db-n1-standard-2 (2 vCPU, 7.5 GB) → db-custom-2-7680

        # Extraire vCPUs depuis tier name
        # db-n1-standard-X où X = vCPUs
        if 'standard' in tier:
            vcpus = int(tier.split('-')[-1])
            memory_gb = vcpus * 3.75  # n1-standard ratio

            # Équivalent db-custom
            custom_tier = f"db-custom-{vcpus}-{int(memory_gb * 1024)}"
            # db-custom-2-7680 (2 vCPU, 7.5 GB)

        # 4. Comparer coûts
        n1_cost = get_tier_cost(tier)
        custom_cost = get_tier_cost(custom_tier)

        # db-custom souvent ~10% plus cher mais plus flexible
        # Recommandation si active connections et bénéfice flexibilité

        # Ou recommander db-standard (nouvelle génération si disponible)
        # Pour l'instant, db-n1 encore standard, pas de génération plus récente

        # Note: Scénario moins critique que AWS/Azure car GCP n'a pas encore db-n2
        # Garder pour futur-proofing
```

**Critères :**
- `tier.startswith('db-n1-')`
- Optionnel: migration vers db-custom pour flexibilité

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

db-n1 vs db-custom = trade-off flexibilité :

```python
# Exemple: db-n1-standard-2

current_tier = 'db-n1-standard-2'
current_cost = 92.40  # $/mois

# Équivalent db-custom
recommended_tier = 'db-custom-2-7680'
recommended_cost = 51.10  # $/mois

# db-custom MOINS CHER ! (-45%)
monthly_waste = current_cost - recommended_cost  # $41.30

# Si HA
if ha_enabled:
    monthly_waste = monthly_waste * 2  # $82.60

# Coût gaspillé
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance db-n1-standard-2 + HA depuis 180 jours :
```python
current_cost = $92.40 * 2 = $184.80 (HA)
recommended_cost = $51.10 * 2 = $102.20 (HA, db-custom)
monthly_waste = $82.60
already_wasted = $82.60 * (180/30) = $495.60
```

**Note :** db-custom offre aussi flexibilité (ajuster vCPU/RAM indépendamment).

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `old_tiers` | list | `['db-n1']` | Tiers considérés anciens |
| `preferred_tier_type` | str | `'db-custom'` | Type recommandé |
| `min_savings_threshold` | float | 10.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3333333333",
  "resource_name": "legacy-tier-mysql",
  "resource_type": "cloud_sql_old_machine_type",
  "region": "us-central1",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "availability_type": "REGIONAL",
  "current_cost_monthly": 184.80,
  "recommended_tier": "db-custom-2-7680",
  "recommended_cost_monthly": 102.20,
  "estimated_monthly_waste": 82.60,
  "already_wasted": 495.60,
  "savings_percentage": 44.7,
  "confidence": "medium",
  "recommendation": "Migrate to db-custom-2-7680 for -45% cost and better flexibility",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `cloud_sql_devtest_247` - Instances Dev/Test 24/7

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances RUNNABLE
instances = sql_client.list(parent=f"projects/{project_id}")

runnable_instances = [i for i in instances if i.state == sql_v1.Instance.State.RUNNABLE]

# 2. Pour chaque instance, vérifier labels
for instance in runnable_instances:
    labels = instance.settings.user_labels if hasattr(instance.settings, 'user_labels') else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test/staging
    if environment in ['dev', 'test', 'staging', 'development']:
        # 4. Vérifier uptime
        creation_time = instance.create_time
        age_days = (now - creation_time).days

        # 5. Détection si uptime >7 jours continus
        if age_days >= min_uptime_days:
            # 6. Calculer économie arrêts nocturnes/weekends
            # Business hours: 8h-20h Lun-Ven = 60h/semaine
            # Actuel: 24/7 = 168h/semaine
            # Économie: (168-60)/168 = 64%

            # Dev/Test 24/7 = waste détecté
```

**Critères :**
- `state == 'RUNNABLE'`
- `labels.environment in ['dev', 'test', 'staging']`
- `uptime_days >= 7`

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

Instance dev 24/7 vs horaires business :

```python
# Instance dev: db-n1-standard-2 + 100 GB SSD

# Coût actuel (24/7)
instance_cost = 92.40  # $/mois
storage_cost = 100 * 0.17 = 17.00  # $/mois (reste)
backup_cost = 150 * 0.08 = 12.00   # $/mois (reste)

monthly_cost = 92.40 + 17.00 + 12.00 = 121.40  # $/mois

# Coût optimal (60h/semaine)
hours_optimal = 60
hours_actual = 168

# Instance peut être arrêtée → économie 64%
optimal_instance_cost = instance_cost * (hours_optimal / hours_actual)  # $33.00

# Storage + backups restent (instance arrêtée)
optimal_cost = optimal_instance_cost + storage_cost + backup_cost  # $62.00

monthly_waste = monthly_cost - optimal_cost  # $59.40

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance dev db-n1-standard-2 + 100 GB depuis 90 jours :
```python
current_cost = $121.40/mois (24/7)
optimal_cost = $62.00/mois (60h/semaine)
monthly_waste = $59.40
already_wasted = $59.40 * (90/30) = $178.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `min_uptime_days` | int | 7 | Uptime minimum pour détection |
| `business_hours_per_week` | int | 60 | Heures optimales/semaine |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-7777777777",
  "resource_name": "dev-postgres-db",
  "resource_type": "cloud_sql_devtest_247",
  "region": "us-east1",
  "database_version": "POSTGRES_14",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "creation_time": "2024-08-05T09:00:00Z",
  "uptime_days": 89,
  "current_uptime_hours_weekly": 168,
  "optimal_uptime_hours_weekly": 60,
  "current_cost_monthly": 121.40,
  "optimal_cost_monthly": 62.00,
  "estimated_monthly_waste": 59.40,
  "already_wasted": 176.53,
  "waste_percentage": 49,
  "confidence": "high",
  "recommendation": "Implement automated start/stop schedule (8am-8pm Mon-Fri)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `cloud_sql_unused_replicas` - Read Replicas Inutilisés

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = sql_client.list(parent=f"projects/{project_id}")

# 2. Pour chaque instance, identifier read replicas
for instance in instances:
    # Vérifier si instance est un replica
    if instance.replica_configuration:
        # C'est un read replica

        # 3. Récupérer master instance
        # Note: API Cloud SQL ne fournit pas directement master name
        # Utiliser instance.master_instance_name (disponible dans certaines versions API)

        instance_name = instance.name

        # 4. Récupérer métriques read queries (14 jours)
        from google.cloud import monitoring_v3

        monitoring_client = monitoring_v3.MetricServiceClient()

        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 14*24*3600},
        })

        # Métrique: cloudsql.googleapis.com/database/queries
        # Filtrer SELECT queries
        queries_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/queries"',
                "interval": interval,
            }
        )

        total_queries = sum([
            point.value.int64_value
            for series in queries_metrics
            for point in series.points
        ])

        # 5. Détection si zero queries
        if total_queries == 0:
            # Read replica inutilisé = waste (coût instance complète)
```

**Critères :**
- Instance est un read replica
- `total_queries == 0` sur 14 jours
- Replica actif (state = RUNNABLE)

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/queries"'
)
```

#### Calcul de Coût

**Formule :**

Read replica inutilisé = 100% coût instance :

```python
# Read replica = instance complète (même tier que master)

tier = instance.settings.tier  # "db-n1-standard-2"
instance_cost = get_tier_cost(tier)  # $92.40

# Storage (répliqué depuis master)
storage_size_gb = instance.settings.data_disk_size_gb
storage_cost = storage_size_gb * 0.17  # SSD

# Backup (read replicas ont leurs propres backups)
backup_size_gb = storage_size_gb * 1.5
backup_cost = backup_size_gb * 0.08

# Coût total = 100% waste (replica jamais utilisé)
monthly_cost = instance_cost + storage_cost + backup_cost

# Coût gaspillé depuis création replica
creation_time = instance.create_time
age_days = (now - creation_time).days
already_wasted = monthly_cost * (age_days / 30.0)
```

**Exemple :**

Read replica db-n1-standard-2 + 200 GB SSD inutilisé depuis 60 jours :
```python
instance_cost = $92.40
storage_cost = 200 * $0.17 = $34.00
backup_cost = 300 * $0.08 = $24.00
monthly_cost = $150.40
already_wasted = $150.40 * (60/30) = $300.80
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 14 | Période analyse queries |
| `min_queries_threshold` | int | 0 | Queries minimum pour être actif |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-8888888888",
  "resource_name": "mysql-read-replica-1",
  "resource_type": "cloud_sql_unused_replicas",
  "region": "us-west1",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "is_replica": true,
  "master_instance": "prod-mysql-master",
  "storage_size_gb": 200,
  "storage_type": "PD_SSD",
  "query_metrics": {
    "total_queries_14d": 0
  },
  "creation_time": "2024-09-05T10:00:00Z",
  "age_days": 58,
  "instance_cost_monthly": 92.40,
  "storage_cost_monthly": 34.00,
  "backup_cost_monthly": 24.00,
  "estimated_monthly_cost": 150.40,
  "already_wasted": 290.11,
  "confidence": "high",
  "recommendation": "Delete read replica - zero queries in 14 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `cloud_sql_untagged` - Instances Non Taguées

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = sql_client.list(parent=f"projects/{project_id}")

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque instance, vérifier labels
for instance in instances:
    labels = instance.settings.user_labels if hasattr(instance.settings, 'user_labels') else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged instance = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise
- Optionnel: valeurs de labels invalides

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Instances non taguées = perte de visibilité + risque coût
# Coût estimé = 5% du coût instance (estimation)

# Calculer coût instance total
tier = instance.settings.tier
instance_cost = get_tier_cost(tier)

storage_size_gb = instance.settings.data_disk_size_gb
storage_cost = storage_size_gb * 0.17

backup_size_gb = storage_size_gb * 1.5
backup_cost = backup_size_gb * 0.08

# HA
ha_enabled = instance.settings.availability_type == 'REGIONAL'
if ha_enabled:
    instance_cost = instance_cost * 2

instance_monthly_cost = instance_cost + storage_cost + backup_cost

# Governance waste = 5%
governance_waste_percentage = 0.05
monthly_waste = instance_monthly_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance db-n1-standard-2 + HA + 200 GB sans labels depuis 180 jours :
```python
instance_monthly_cost = $184.80 + $34.00 + $24.00 = $242.80
monthly_waste = $242.80 * 0.05 = $12.14
already_wasted = $12.14 * (180/30) = $72.84
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |
| `enforce_values` | dict | `{}` | Valeurs autorisées par label |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1010101010",
  "resource_name": "unnamed-mysql-47",
  "resource_type": "cloud_sql_untagged",
  "region": "europe-west4",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "availability_type": "REGIONAL",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_time": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "instance_monthly_cost": 242.80,
  "estimated_monthly_waste": 12.14,
  "already_wasted": 72.84,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `cloud_sql_zero_io` - Instances avec Zéro I/O

#### Détection

**Logique :**

Détecter instances sans activité I/O (database vide ou inutilisée) :

```python
# 1. Lister toutes les instances RUNNABLE
instances = sql_client.list(parent=f"projects/{project_id}")

runnable_instances = [i for i in instances if i.state == sql_v1.Instance.State.RUNNABLE]

# 2. Pour chaque instance, récupérer métriques I/O (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in runnable_instances:
    instance_name = instance.name

    # 3. Query read/write I/O
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Read bytes
    read_io = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/disk/read_ops_count"',
            "interval": interval,
        }
    )

    # Write bytes
    write_io = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/disk/write_ops_count"',
            "interval": interval,
        }
    )

    # 4. Calculer total I/O
    total_read_ops = sum([point.value.int64_value for series in read_io for point in series.points])
    total_write_ops = sum([point.value.int64_value for series in write_io for point in series.points])

    # 5. Détection si zero I/O
    if total_read_ops == 0 and total_write_ops == 0:
        # Instance avec zéro I/O = database vide/inutilisée
```

**Critères :**
- `state == 'RUNNABLE'`
- `total_read_ops == 0` ET `total_write_ops == 0` sur 14 jours
- Instance créée >7 jours (éviter faux positifs)

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/disk/read_ops_count"'
)

monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/disk/write_ops_count"'
)
```

#### Calcul de Coût

**Formule :**

Zéro I/O = 100% waste (database inutilisée) :

```python
# Instance avec zero I/O = probablement vide

tier = instance.settings.tier
instance_cost = get_tier_cost(tier)

storage_cost = instance.settings.data_disk_size_gb * 0.17
backup_cost = instance.settings.data_disk_size_gb * 1.5 * 0.08

# HA
ha_enabled = instance.settings.availability_type == 'REGIONAL'
if ha_enabled:
    instance_cost = instance_cost * 2

# Coût total = 100% waste
monthly_cost = instance_cost + storage_cost + backup_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Instance db-n1-standard-2 + 100 GB avec zéro I/O depuis 90 jours :
```python
instance_cost = $92.40
storage_cost = 100 * $0.17 = $17.00
backup_cost = 150 * $0.08 = $12.00
monthly_cost = $121.40
already_wasted = $121.40 * (90/30) = $364.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 14 | Période analyse I/O |
| `min_age_days` | int | 7 | Âge minimum instance |
| `zero_io_threshold` | int | 0 | Nombre max opérations I/O |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-2020202020",
  "resource_name": "empty-database",
  "resource_type": "cloud_sql_zero_io",
  "region": "us-central1",
  "database_version": "POSTGRES_14",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "storage_size_gb": 100,
  "io_metrics": {
    "total_read_ops_14d": 0,
    "total_write_ops_14d": 0
  },
  "creation_time": "2024-08-05T09:00:00Z",
  "age_days": 89,
  "estimated_monthly_cost": 121.40,
  "already_wasted": 360.53,
  "confidence": "high",
  "recommendation": "Delete instance - zero I/O for 14 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `cloud_sql_storage_overprovisioned` - Storage Over-Provisioned

#### Détection

**Logique :**

Analyser utilisation storage réelle vs allouée :

```python
# 1. Lister toutes les instances
instances = sql_client.list(parent=f"projects/{project_id}")

for instance in instances:
    instance_name = instance.name

    # 2. Récupérer taille storage allouée
    allocated_storage_gb = instance.settings.data_disk_size_gb

    # 3. Récupérer métriques utilisation storage (14 jours)
    from google.cloud import monitoring_v3

    monitoring_client = monitoring_v3.MetricServiceClient()

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Métrique: cloudsql.googleapis.com/database/disk/bytes_used
    storage_used_metrics = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'resource.type="cloudsql_database" AND resource.database_id="{project_id}:{instance_name}" AND metric.type="cloudsql.googleapis.com/database/disk/bytes_used"',
            "interval": interval,
        }
    )

    # 4. Calculer utilisation moyenne
    used_bytes_values = [
        point.value.double_value
        for series in storage_used_metrics
        for point in series.points
    ]

    if not used_bytes_values:
        continue

    avg_used_bytes = sum(used_bytes_values) / len(used_bytes_values)
    avg_used_gb = avg_used_bytes / (1024**3)

    # 5. Calculer % utilisé
    used_percent = (avg_used_gb / allocated_storage_gb * 100) if allocated_storage_gb > 0 else 0
    free_percent = 100 - used_percent

    # 6. Détection si >80% espace libre
    if free_percent >= free_space_threshold:
        # 7. Calculer taille recommandée
        recommended_storage_gb = int(avg_used_gb * 1.30)  # +30% buffer

        # Storage over-provisioned = waste détecté
```

**Critères :**
- `free_space >= 80%` (ou utilisé <20%)
- Économie potentielle >$5/mois
- Instance active (state = RUNNABLE)

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="cloudsql.googleapis.com/database/disk/bytes_used"'
)
```

#### Calcul de Coût

**Formule :**

Storage over-provisioned = différence coût actuel vs recommandé :

```python
# Exemple: 1000 GB alloué, 150 GB utilisé

allocated_storage_gb = 1000
avg_used_gb = 150

# Taille recommandée: 150 GB * 1.30 = 195 GB → arrondi 200 GB
recommended_storage_gb = 200

# Storage type
storage_type = instance.settings.data_disk_type  # PD_SSD

storage_pricing = {'PD_SSD': 0.17, 'PD_HDD': 0.09}
price_per_gb = storage_pricing.get(storage_type, 0.17)

# Coût storage
current_storage_cost = allocated_storage_gb * price_per_gb  # $170.00
recommended_storage_cost = recommended_storage_gb * price_per_gb  # $34.00

# Waste storage
storage_waste = current_storage_cost - recommended_storage_cost  # $136.00

# Backup cost aussi impacté (proportionnel à storage)
current_backup_cost = allocated_storage_gb * 1.5 * 0.08  # $120.00
recommended_backup_cost = recommended_storage_gb * 1.5 * 0.08  # $24.00
backup_waste = current_backup_cost - recommended_backup_cost  # $96.00

# Waste total
monthly_waste = storage_waste + backup_waste  # $232.00

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance avec 1000 GB SSD alloué, 150 GB utilisé depuis 120 jours :
```python
current_storage_cost = 1000 * $0.17 = $170.00
recommended_storage_cost = 200 * $0.17 = $34.00
storage_waste = $136.00

current_backup_cost = 1500 * $0.08 = $120.00
recommended_backup_cost = 300 * $0.08 = $24.00
backup_waste = $96.00

monthly_waste = $232.00
already_wasted = $232.00 * (120/30) = $928.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `free_space_threshold` | float | 80.0 | % minimum espace libre pour détection |
| `safety_buffer` | float | 1.30 | Marge sécurité taille (1.30 = +30%) |
| `min_savings_threshold` | float | 5.0 | Économie minimum $/mois |
| `lookback_days` | int | 14 | Période analyse utilisation |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3030303030",
  "resource_name": "oversized-storage-db",
  "resource_type": "cloud_sql_storage_overprovisioned",
  "region": "europe-west1",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-2",
  "storage_size_gb": 1000,
  "storage_type": "PD_SSD",
  "storage_usage": {
    "avg_used_gb": 152.3,
    "avg_used_percent": 15.2,
    "avg_free_percent": 84.8
  },
  "recommended_storage_gb": 200,
  "current_storage_cost_monthly": 170.00,
  "recommended_storage_cost_monthly": 34.00,
  "current_backup_cost_monthly": 120.00,
  "recommended_backup_cost_monthly": 24.00,
  "estimated_monthly_waste": 232.00,
  "already_wasted": 928.00,
  "savings_percentage": 73,
  "confidence": "high",
  "recommendation": "Reduce storage from 1000GB to 200GB - using only 15%",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `cloud_sql_unnecessary_ha` - High Availability Inutile

#### Détection

**Logique :**

Détecter instances **dev/test avec HA activé** (surcoût +100%) :

```python
# 1. Lister toutes les instances avec HA
instances = sql_client.list(parent=f"projects/{project_id}")

ha_instances = [
    i for i in instances
    if i.settings.availability_type == 'REGIONAL'  # HA enabled
]

# 2. Pour chaque instance HA, vérifier labels
for instance in ha_instances:
    labels = instance.settings.user_labels if hasattr(instance.settings, 'user_labels') else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test/staging
    if environment in ['dev', 'test', 'staging', 'development']:
        # HA pour dev/test = waste (99.95% SLA inutile)

        # 4. Calculer économie en désactivant HA
        tier = instance.settings.tier
        instance_cost = get_tier_cost(tier)

        # HA = +100% coût instance (standby replica)
        ha_cost = instance_cost  # Coût additionnel HA

        # Waste = coût HA inutile
        monthly_waste = ha_cost
```

**Critères :**
- `availability_type == 'REGIONAL'` (HA enabled)
- `labels.environment in ['dev', 'test', 'staging']`
- Instance active (state = RUNNABLE)

**API Calls :**
```python
# Cloud SQL Admin API
sql_client.list(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

HA inutile = +100% instance cost gaspillé :

```python
# Instance dev avec HA: db-n1-standard-4

tier = 'db-n1-standard-4'
instance_cost_single = 184.80  # $/mois (sans HA)

# Coût actuel avec HA
instance_cost_ha = instance_cost_single * 2  # $369.60

# Coût optimal sans HA (dev/test ne nécessite pas 99.95% SLA)
optimal_cost = instance_cost_single  # $184.80

# Waste = coût HA
monthly_waste = instance_cost_ha - optimal_cost  # $184.80

# Storage et backups identiques (pas de waste)

# Coût gaspillé depuis activation HA
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance dev db-n1-standard-4 + HA depuis 180 jours :
```python
instance_cost_single = $184.80
instance_cost_ha = $369.60
monthly_waste = $184.80
already_wasted = $184.80 * (180/30) = $1,108.80
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `allow_ha_for_labels` | dict | `{}` | Labels autorisant HA (ex: `{'critical': 'true'}`) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-4040404040",
  "resource_name": "dev-mysql-ha",
  "resource_type": "cloud_sql_unnecessary_ha",
  "region": "us-central1",
  "database_version": "MYSQL_8_0",
  "state": "RUNNABLE",
  "tier": "db-n1-standard-4",
  "availability_type": "REGIONAL",
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "creation_time": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "instance_cost_single_monthly": 184.80,
  "instance_cost_ha_monthly": 369.60,
  "estimated_monthly_waste": 184.80,
  "already_wasted": 1108.80,
  "confidence": "high",
  "recommendation": "Disable High Availability for dev/test environment",
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
gcloud services enable sqladmin.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account (si pas déjà créé)

```bash
# Ajouter permissions Cloud SQL
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.viewer"

# Utiliser credentials existants
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

---

### Tests Unitaires - Créer Instances de Test

#### Scénario 1: Instance Arrêtée >30 Jours

```bash
# Créer instance MySQL
gcloud sql instances create test-stopped-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-1 \
  --region=us-central1 \
  --storage-size=100GB \
  --storage-type=SSD

# Arrêter instance
gcloud sql instances patch test-stopped-instance \
  --activation-policy=NEVER

# Attendre 30 jours pour détection
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_stopped",
  "resource_name": "test-stopped-instance",
  "state": "STOPPED",
  "storage_cost_monthly": "~17.00",
  "backup_cost_monthly": "~12.00",
  "estimated_monthly_cost": "~29.00"
}
```

---

#### Scénario 2: Instance Idle (Zero Connections)

```bash
# Créer instance PostgreSQL
gcloud sql instances create test-idle-instance \
  --database-version=POSTGRES_14 \
  --tier=db-n1-standard-2 \
  --region=us-east1 \
  --storage-size=200GB \
  --storage-type=SSD \
  --availability-type=REGIONAL

# NE PAS se connecter (laisser idle)
# Attendre 14 jours pour métriques connexions = 0
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_idle",
  "resource_name": "test-idle-instance",
  "connection_metrics": {
    "avg_connections_14d": 0.0
  },
  "estimated_monthly_cost": "~242.80"
}
```

---

#### Scénario 3: Instance Over-Provisioned

```bash
# Créer instance large
gcloud sql instances create test-overprovisioned-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-4 \
  --region=europe-west1 \
  --storage-size=100GB \
  --storage-type=SSD \
  --availability-type=REGIONAL

# Connecter et générer faible charge (CPU <30%, Memory <40%)
# Utiliser mysql client avec queries très légères
mysql -h <INSTANCE_IP> -u root -p

# Exécuter queries légères périodiquement
while true; do
  mysql -h <IP> -u root -p -e "SELECT 1;"
  sleep 60
done &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_overprovisioned",
  "resource_name": "test-overprovisioned-instance",
  "cpu_metrics": {
    "avg_cpu_14d": "<30"
  },
  "memory_metrics": {
    "avg_memory_14d": "<40"
  },
  "estimated_monthly_waste": "~184.80"
}
```

---

#### Scénario 4: Ancien Type de Machine

```bash
# Créer instance avec db-n1 tier
gcloud sql instances create test-old-tier-instance \
  --database-version=POSTGRES_14 \
  --tier=db-n1-standard-2 \
  --region=us-central1 \
  --storage-size=100GB \
  --storage-type=SSD \
  --availability-type=REGIONAL
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_old_machine_type",
  "resource_name": "test-old-tier-instance",
  "tier": "db-n1-standard-2",
  "recommended_tier": "db-custom-2-7680",
  "estimated_monthly_waste": "~82.60"
}
```

---

#### Scénario 5: Instance Dev/Test 24/7

```bash
# Créer instance avec label dev
gcloud sql instances create test-devtest-247-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-2 \
  --region=us-east1 \
  --storage-size=100GB \
  --storage-type=SSD \
  --labels=environment=dev,team=backend

# Laisser tourner 7+ jours sans arrêt
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_devtest_247",
  "resource_name": "test-devtest-247-instance",
  "labels": {"environment": "dev"},
  "uptime_days": ">=7",
  "estimated_monthly_waste": "~59.40"
}
```

---

#### Scénario 6: Read Replica Inutilisé

```bash
# Créer master instance
gcloud sql instances create test-master-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-2 \
  --region=us-west1 \
  --storage-size=200GB \
  --storage-type=SSD

# Créer read replica
gcloud sql instances create test-unused-replica \
  --master-instance-name=test-master-instance \
  --tier=db-n1-standard-2 \
  --region=us-west1 \
  --replica-type=READ

# NE PAS exécuter de queries sur replica
# Attendre 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_unused_replicas",
  "resource_name": "test-unused-replica",
  "is_replica": true,
  "query_metrics": {
    "total_queries_14d": 0
  },
  "estimated_monthly_cost": "~150.40"
}
```

---

#### Scénario 7: Instance Non Taguée

```bash
# Créer instance SANS labels
gcloud sql instances create test-untagged-instance \
  --database-version=POSTGRES_14 \
  --tier=db-n1-standard-2 \
  --region=europe-west4 \
  --storage-size=200GB \
  --storage-type=SSD \
  --availability-type=REGIONAL
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_untagged",
  "resource_name": "test-untagged-instance",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~12.14"
}
```

---

#### Scénario 8: Instance avec Zéro I/O

```bash
# Créer instance
gcloud sql instances create test-zero-io-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-2 \
  --region=us-central1 \
  --storage-size=100GB \
  --storage-type=SSD

# Connecter mais NE PAS exécuter de queries
# (pas de CREATE TABLE, pas d'INSERT, rien)

# Attendre 14 jours pour métriques I/O = 0
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_zero_io",
  "resource_name": "test-zero-io-instance",
  "io_metrics": {
    "total_read_ops_14d": 0,
    "total_write_ops_14d": 0
  },
  "estimated_monthly_cost": "~121.40"
}
```

---

#### Scénario 9: Storage Over-Provisioned

```bash
# Créer instance avec large storage
gcloud sql instances create test-oversized-storage-instance \
  --database-version=POSTGRES_14 \
  --tier=db-n1-standard-2 \
  --region=europe-west1 \
  --storage-size=1000GB \
  --storage-type=SSD

# Connecter et utiliser seulement 15% storage
psql "host=<IP> user=postgres dbname=postgres"

# Créer database légère (~150 GB)
CREATE TABLE test_data (id SERIAL, data TEXT);
INSERT INTO test_data (data) SELECT repeat('x', 1000) FROM generate_series(1, 150000000);

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_storage_overprovisioned",
  "resource_name": "test-oversized-storage-instance",
  "storage_usage": {
    "avg_used_percent": "~15",
    "avg_free_percent": "~85"
  },
  "recommended_storage_gb": 200,
  "estimated_monthly_waste": "~232.00"
}
```

---

#### Scénario 10: High Availability Inutile

```bash
# Créer instance dev avec HA
gcloud sql instances create test-unnecessary-ha-instance \
  --database-version=MYSQL_8_0 \
  --tier=db-n1-standard-4 \
  --region=us-central1 \
  --storage-size=100GB \
  --storage-type=SSD \
  --availability-type=REGIONAL \
  --labels=environment=dev,team=backend
```

**Validation attendue :**
```json
{
  "resource_type": "cloud_sql_unnecessary_ha",
  "resource_name": "test-unnecessary-ha-instance",
  "availability_type": "REGIONAL",
  "labels": {"environment": "dev"},
  "estimated_monthly_waste": "~184.80"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script de validation complet pour Cloud SQL
"""

from google.cloud import sql_v1
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    sql_client = sql_v1.SqlInstancesServiceClient()

    # 1. Lister toutes les instances
    instances = list(sql_client.list(parent=f"projects/{PROJECT_ID}"))

    print(f"✅ Found {len(instances)} Cloud SQL instances")

    # 2. Vérifier détection pour chaque scénario
    scenarios_detected = {
        'stopped': 0,
        'idle': 0,
        'overprovisioned': 0,
        'old_machine_type': 0,
        'devtest_247': 0,
        'unused_replicas': 0,
        'untagged': 0,
        'zero_io': 0,
        'storage_overprovisioned': 0,
        'unnecessary_ha': 0,
    }

    for instance in instances:
        name = instance.name

        # Scenario 1: Stopped
        if instance.state == sql_v1.Instance.State.STOPPED:
            scenarios_detected['stopped'] += 1
            print(f"✅ Detected scenario 1 (stopped): {name}")

        # Scenario 4: Old machine type
        if instance.settings.tier.startswith('db-n1-'):
            scenarios_detected['old_machine_type'] += 1
            print(f"✅ Detected scenario 4 (old machine type): {name}")

        # Scenario 5: Dev/Test 24/7
        labels = instance.settings.user_labels if hasattr(instance.settings, 'user_labels') else {}
        if labels.get('environment') in ['dev', 'test', 'staging']:
            scenarios_detected['devtest_247'] += 1
            print(f"✅ Detected scenario 5 (dev/test 24/7): {name}")

        # Scenario 7: Untagged
        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Detected scenario 7 (untagged): {name}")

        # Scenario 10: Unnecessary HA
        if (instance.settings.availability_type == 'REGIONAL' and
            labels.get('environment') in ['dev', 'test', 'staging']):
            scenarios_detected['unnecessary_ha'] += 1
            print(f"✅ Detected scenario 10 (unnecessary HA): {name}")

    # 3. Rapport final
    print("\n📊 Detection Summary:")
    for scenario, count in scenarios_detected.items():
        print(f"  - {scenario}: {count} instances")

    total_detected = sum(scenarios_detected.values())
    print(f"\n✅ Total waste detected: {total_detected} instances")

if __name__ == '__main__':
    test_all_scenarios()
```

#### Exécution

```bash
# Exporter PROJECT_ID
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"

# Exécuter validation
python3 test_gcp_cloud_sql.py
```

**Résultat attendu :**
```
✅ Found 10 Cloud SQL instances
✅ Detected scenario 1 (stopped): test-stopped-instance
✅ Detected scenario 2 (idle): test-idle-instance
✅ Detected scenario 3 (overprovisioned): test-overprovisioned-instance
✅ Detected scenario 4 (old machine type): test-old-tier-instance
✅ Detected scenario 5 (dev/test 24/7): test-devtest-247-instance
✅ Detected scenario 6 (unused replica): test-unused-replica
✅ Detected scenario 7 (untagged): test-untagged-instance
✅ Detected scenario 8 (zero I/O): test-zero-io-instance
✅ Detected scenario 9 (storage overprovisioned): test-oversized-storage-instance
✅ Detected scenario 10 (unnecessary HA): test-unnecessary-ha-instance

📊 Detection Summary:
  - stopped: 1 instances
  - idle: 1 instances
  - overprovisioned: 1 instances
  - old_machine_type: 1 instances
  - devtest_247: 1 instances
  - unused_replicas: 1 instances
  - untagged: 1 instances
  - zero_io: 1 instances
  - storage_overprovisioned: 1 instances
  - unnecessary_ha: 1 instances

✅ Total waste detected: 10 instances
```

---

### Cleanup

```bash
# Supprimer toutes les instances de test
gcloud sql instances delete test-stopped-instance --quiet
gcloud sql instances delete test-idle-instance --quiet
gcloud sql instances delete test-overprovisioned-instance --quiet
gcloud sql instances delete test-old-tier-instance --quiet
gcloud sql instances delete test-devtest-247-instance --quiet
gcloud sql instances delete test-master-instance --quiet  # Supprime aussi replicas
gcloud sql instances delete test-untagged-instance --quiet
gcloud sql instances delete test-zero-io-instance --quiet
gcloud sql instances delete test-oversized-storage-instance --quiet
gcloud sql instances delete test-unnecessary-ha-instance --quiet
```

---

## Références

### Documentation GCP

- [Cloud SQL API](https://cloud.google.com/sql/docs/mysql/admin-api/rest/v1/instances)
- [Cloud SQL Pricing](https://cloud.google.com/sql/pricing)
- [Cloud SQL Machine Types](https://cloud.google.com/sql/docs/mysql/instance-settings)
- [High Availability](https://cloud.google.com/sql/docs/mysql/high-availability)
- [Read Replicas](https://cloud.google.com/sql/docs/mysql/replication)
- [Cloud Monitoring Metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-cloudsql)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing complet 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md) - Compute Instances
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md) - Persistent Disks
- [GCP_GKE_CLUSTER_SCENARIOS_100.md](./GCP_GKE_CLUSTER_SCENARIOS_100.md) - GKE Clusters
- [README.md](./README.md) - Guide documentation GCP

### Équivalences AWS/Azure

- **AWS RDS** → GCP Cloud SQL
- **Azure SQL Database** → GCP Cloud SQL
- **AWS Aurora** → GCP Cloud Spanner (distributed)
- **AWS RDS Multi-AZ** → GCP Cloud SQL HA (REGIONAL)
- **AWS RDS Read Replicas** → GCP Cloud SQL Read Replicas

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
