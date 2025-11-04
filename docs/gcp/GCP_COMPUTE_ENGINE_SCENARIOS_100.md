# CloudWaste - Couverture 100% GCP Compute Engine Instances

**Resource Type:** `Compute : Compute Engine Instances`
**Provider:** Google Cloud Platform (GCP)
**API:** `compute.googleapis.com` (Compute Engine API v1)
**Équivalents:** AWS EC2 Instances, Azure Virtual Machines
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing GCP](#modèle-de-pricing-gcp)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Instances Arrêtées >30 Jours](#1-compute_instance_stopped---instances-arrêtées-30-jours)
  - [2. Instances Inactives (CPU <5%)](#2-compute_instance_idle---instances-inactives-cpu-5)
  - [3. Instances Sur-Provisionnées (CPU <30%)](#3-compute_instance_overprovisioned---instances-sur-provisionnées-cpu-30)
  - [4. Anciennes Générations de Machines](#4-compute_instance_old_generation---anciennes-générations-de-machines)
  - [5. Absence d'Usage Spot/Preemptible](#5-compute_instance_no_spot---absence-dusage-spotpreemptible)
  - [6. Instances Non Taguées](#6-compute_instance_untagged---instances-non-taguées)
  - [7. Instances Dev/Test 24/7](#7-compute_instance_devtest_247---instances-devtest-247)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Mémoire Sur-Provisionnée (<40% usage)](#8-compute_instance_memory_waste---mémoire-sur-provisionnée-40-usage)
  - [9. Opportunités de Right-Sizing](#9-compute_instance_rightsizing---opportunités-de-right-sizing)
  - [10. Instances Burstable Sous-Utilisées](#10-compute_instance_burstable_waste---instances-burstable-sous-utilisées)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte GCP Compute Engine

Google Cloud Platform facture les **Compute Engine Instances** à la seconde (minimum 1 minute) avec des **Sustained Use Discounts (SUD)** automatiques :

- **Sustained Use Discounts (SUD)** : -30% automatique après 25% du mois d'utilisation
- **Committed Use Discounts (CUD)** : -57% pour 1 an, -70% pour 3 ans (engagement)
- **Spot VMs** : -60% à -91% (anciennes preemptible) - interruptibles
- **Machine Types** : n1 (ancienne génération), n2/n2d (moderne), e2 (burstable), c2/c2d (compute-optimized)

### Waste Typique

1. **Instances arrêtées** : Paiement des disques attachés ($0.04-0.17/GB/mois)
2. **Idle instances** : CPU <5% - 95% de gaspillage
3. **Over-provisioning** : CPU <30% - opportunités de downgrade
4. **Anciennes générations** : n1 → n2 = -20% à -30% de coût
5. **Non-usage Spot** : 60-91% d'économies potentielles

---

## Modèle de Pricing GCP

### Exemples de Coûts Mensuels (us-central1)

| Machine Type | vCPUs | RAM (GB) | Prix Standard | Prix Spot | Économie Spot |
|-------------|-------|---------|---------------|-----------|---------------|
| **e2-micro** | 0.25 | 1 GB | $7.11/mois | $2.84/mois | -60% |
| **e2-small** | 0.5 | 2 GB | $14.23/mois | $5.69/mois | -60% |
| **n1-standard-1** | 1 | 3.75 GB | $24.27/mois | $7.30/mois | -70% |
| **n2-standard-2** | 2 | 8 GB | $71.17/mois | $17.08/mois | -76% |
| **n2-standard-4** | 4 | 16 GB | $142.34/mois | $34.16/mois | -76% |
| **n2-standard-8** | 8 | 32 GB | $284.68/mois | $68.32/mois | -76% |
| **c2-standard-4** | 4 | 16 GB | $163.73/mois | $39.30/mois | -76% |
| **c2-standard-8** | 8 | 32 GB | $327.46/mois | $78.59/mois | -76% |

**Notes :**
- Pricing incluant Sustained Use Discounts (SUD) automatique
- Spot pricing variable selon disponibilité (60-91% discount)
- n2/n2d 20-30% moins cher que n1 à performance équivalente
- Disques persistants facturés même quand instance arrêtée

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `compute_instance_stopped` - Instances Arrêtées >30 Jours

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances via Compute Engine API
instances = compute_client.instances().aggregatedList(project=project_id).execute()

# 2. Filtrer instances avec status = 'TERMINATED'
for zone, instances_scoped in instances.get('items', {}).items():
    for instance in instances_scoped.get('instances', []):
        if instance['status'] == 'TERMINATED':
            # 3. Calculer âge depuis dernière modification
            last_stop = parse_timestamp(instance.get('lastStopTimestamp'))
            age_days = (now - last_stop).days

            # 4. Détection si âge > seuil configurable (défaut: 30 jours)
            if age_days >= min_age_days:
                # Instance arrêtée = waste détecté
```

**Critères :**
- `status == 'TERMINATED'`
- `age >= min_age_days` (défaut: 30 jours)

**API Calls :**
```python
# Google Cloud Compute Engine API v1
compute_client.instances().aggregatedList(
    project='my-project',
    filter='status=TERMINATED'
).execute()
```

#### Calcul de Coût

**Formule :**

Instances arrêtées ne paient **QUE les disques attachés** (pas de compute) :

```python
# Coût mensuel = somme des disques persistants attachés
monthly_cost = 0

for disk in instance['disks']:
    disk_size_gb = disk['diskSizeGb']
    disk_type = disk['type']  # pd-standard, pd-ssd, pd-balanced

    # Prix par GB/mois selon type
    disk_pricing = {
        'pd-standard': 0.040,  # $0.040/GB/mois (HDD)
        'pd-balanced': 0.100,  # $0.100/GB/mois (SSD équilibré)
        'pd-ssd': 0.170,       # $0.170/GB/mois (SSD performance)
    }

    monthly_cost += disk_size_gb * disk_pricing.get(disk_type, 0.040)

# Coût gaspillé cumulé
already_wasted = monthly_cost * (age_days / 30.0)
```

**Exemple :**

Instance arrêtée avec 100 GB pd-standard + 50 GB pd-ssd depuis 60 jours :
```python
monthly_cost = (100 * $0.040) + (50 * $0.170) = $4 + $8.50 = $12.50/mois
already_wasted = $12.50 * (60/30) = $25.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 30 | Âge minimum en jours avant détection |
| `exclude_labels` | dict | `{}` | Labels pour exclure instances (ex: `{'environment': 'backup'}`) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1234567890123456789",
  "resource_name": "dev-api-server",
  "resource_type": "compute_instance_stopped",
  "zone": "us-central1-a",
  "machine_type": "n1-standard-2",
  "status": "TERMINATED",
  "last_stop_timestamp": "2024-09-15T10:30:00Z",
  "age_days": 48,
  "disks": [
    {
      "name": "dev-api-boot",
      "size_gb": 100,
      "type": "pd-standard"
    },
    {
      "name": "dev-api-data",
      "size_gb": 50,
      "type": "pd-ssd"
    }
  ],
  "estimated_monthly_cost": 12.50,
  "already_wasted": 20.00,
  "confidence": "high",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `compute_instance_idle` - Instances Inactives (CPU <5%)

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

# 2. Pour chaque instance, récupérer métriques Cloud Monitoring
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances:
    # 3. Query CPU utilization (14 derniers jours)
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    results = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="compute.googleapis.com/instance/cpu/utilization" AND resource.instance_id="{instance.id}"',
            "interval": interval,
        }
    )

    # 4. Calculer moyenne CPU
    cpu_values = [point.value.double_value for series in results for point in series.points]
    avg_cpu = sum(cpu_values) / len(cpu_values) * 100  # Convertir en %

    # 5. Détection si CPU < seuil (défaut: 5%)
    if avg_cpu < cpu_threshold:
        # Instance idle = waste détecté
```

**Critères :**
- `status == 'RUNNING'`
- `avg_cpu_14d < cpu_threshold` (défaut: 5%)
- Minimum 50 data points (éviter faux positifs)

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Cloud Monitoring API
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/cpu/utilization"',
    interval={"start_time": ..., "end_time": ...}
)
```

#### Calcul de Coût

**Formule :**

Instances idle paient **100% du coût compute** alors que CPU <5% :

```python
# Récupérer pricing via Cloud Billing API ou hard-coded
machine_type = instance['machineType'].split('/')[-1]  # "n1-standard-2"

# Pricing mensuel par machine type (us-central1, avec SUD)
machine_pricing = {
    'n1-standard-1': 24.27,
    'n1-standard-2': 48.54,
    'n2-standard-2': 71.17,
    'n2-standard-4': 142.34,
    'e2-small': 14.23,
}

monthly_cost = machine_pricing.get(machine_type, 0)

# Waste = 95% du coût si CPU <5% (garder 5% pour coût minimal)
waste_percentage = (100 - avg_cpu) / 100.0
monthly_waste = monthly_cost * waste_percentage

# Coût déjà gaspillé depuis création
creation_date = parse_timestamp(instance['creationTimestamp'])
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-4 avec CPU à 3% depuis 90 jours :
```python
monthly_cost = $142.34
waste_percentage = (100 - 3) / 100 = 0.97
monthly_waste = $142.34 * 0.97 = $138.07/mois
already_wasted = $138.07 * (90/30) = $414.21
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 5.0 | CPU % maximum pour être considéré idle |
| `lookback_days` | int | 14 | Période d'analyse des métriques |
| `min_datapoints` | int | 50 | Nombre minimum de points de données |
| `exclude_labels` | dict | `{}` | Labels pour exclure instances |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9876543210987654321",
  "resource_name": "staging-web-server",
  "resource_type": "compute_instance_idle",
  "zone": "us-central1-b",
  "machine_type": "n2-standard-4",
  "status": "RUNNING",
  "creation_timestamp": "2024-08-05T08:00:00Z",
  "age_days": 89,
  "cpu_metrics": {
    "avg_cpu_14d": 3.2,
    "max_cpu_14d": 8.5,
    "min_cpu_14d": 0.8,
    "datapoints": 672
  },
  "estimated_monthly_cost": 142.34,
  "estimated_monthly_waste": 138.07,
  "already_wasted": 414.21,
  "confidence": "high",
  "recommendation": "Downgrade to n2-standard-2 or e2-small",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `compute_instance_overprovisioned` - Instances Sur-Provisionnées (CPU <30%)

#### Détection

**Logique :**

Similaire à `compute_instance_idle` mais avec seuil plus élevé (30%) pour détecter over-provisioning :

```python
# 1. Instances RUNNING avec CPU <30% sur 14 jours
instances = get_running_instances()

for instance in instances:
    # 2. Récupérer métriques CPU via Cloud Monitoring
    avg_cpu = get_avg_cpu(instance, lookback_days=14)

    # 3. Détection si 5% < CPU < 30%
    if cpu_min_threshold < avg_cpu < cpu_max_threshold:
        # 4. Calculer machine type recommandée (downgrade)
        current_type = instance['machineType'].split('/')[-1]
        recommended_type = calculate_recommended_size(current_type, avg_cpu)

        # Over-provisioned = waste détecté
```

**Critères :**
- `status == 'RUNNING'`
- `5% < avg_cpu_14d < 30%`
- Possibilité de downgrade machine type

**API Calls :** Identiques à `compute_instance_idle`

#### Calcul de Coût

**Formule :**

Calcul de l'économie potentielle en downgradant :

```python
# Coût actuel
current_machine = 'n2-standard-8'
current_cost = 284.68  # $/mois

# Machine recommandée (basé sur avg_cpu)
# Si CPU = 20% → recommandation = n2-standard-4 (50% des vCPUs)
recommended_machine = 'n2-standard-4'
recommended_cost = 142.34  # $/mois

# Waste = différence entre actuel et recommandé
monthly_waste = current_cost - recommended_cost  # $142.34/mois

# Coût déjà gaspillé depuis création
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-8 avec CPU à 22% depuis 180 jours :
```python
current_cost = $284.68
recommended_cost = $142.34  # n2-standard-4
monthly_waste = $142.34
already_wasted = $142.34 * (180/30) = $852.04
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_min_threshold` | float | 5.0 | CPU % minimum (éviter overlap avec idle) |
| `cpu_max_threshold` | float | 30.0 | CPU % maximum pour over-provisioning |
| `lookback_days` | int | 14 | Période d'analyse |
| `downgrade_ratio` | float | 0.5 | Ratio de downgrade (0.5 = moitié des vCPUs) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1122334455667788990",
  "resource_name": "prod-batch-processor",
  "resource_type": "compute_instance_overprovisioned",
  "zone": "europe-west1-b",
  "machine_type": "n2-standard-8",
  "status": "RUNNING",
  "cpu_metrics": {
    "avg_cpu_14d": 22.4,
    "max_cpu_14d": 45.2,
    "min_cpu_14d": 5.1
  },
  "current_cost_monthly": 284.68,
  "recommended_machine_type": "n2-standard-4",
  "recommended_cost_monthly": 142.34,
  "estimated_monthly_waste": 142.34,
  "already_wasted": 852.04,
  "confidence": "medium",
  "recommendation": "Downgrade from 8 vCPUs to 4 vCPUs",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `compute_instance_old_generation` - Anciennes Générations de Machines

#### Détection

**Logique :**

Détecter instances utilisant anciennes générations de machine types (n1) au lieu de modernes (n2/n2d) :

```python
# 1. Lister toutes les instances RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

# 2. Pour chaque instance, extraire machine type
for instance in instances:
    machine_type = instance['machineType'].split('/')[-1]  # "n1-standard-4"

    # 3. Détecter génération ancienne
    if machine_type.startswith('n1-'):
        # 4. Calculer machine type équivalente moderne
        n2_equivalent = machine_type.replace('n1-', 'n2-')

        # 5. Calculer économie potentielle (n2 = -20% à -30% vs n1)
        n1_cost = get_machine_cost(machine_type)
        n2_cost = get_machine_cost(n2_equivalent)

        if n2_cost < n1_cost:
            # Old generation = waste détecté
```

**Critères :**
- `status == 'RUNNING'`
- `machine_type.startswith('n1-')`
- Équivalent n2/n2d moins cher existe

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Machine Types API (pour pricing)
compute_client.machineTypes().get(
    project=project_id,
    zone='us-central1-a',
    machineType='n1-standard-4'
).execute()
```

#### Calcul de Coût

**Formule :**

Économie potentielle en migrant n1 → n2/n2d :

```python
# Mapping n1 → n2 pricing (us-central1, avec SUD)
n1_pricing = {
    'n1-standard-1': 24.27,
    'n1-standard-2': 48.54,
    'n1-standard-4': 97.08,
    'n1-standard-8': 194.16,
}

n2_pricing = {
    'n2-standard-2': 71.17,   # n2-standard-1 n'existe pas
    'n2-standard-4': 142.34,
    'n2-standard-8': 284.68,
}

# Note: n2 a 2x moins de vCPUs minimum (n2-standard-2 vs n1-standard-1)
# Comparaison équivalente: n1-standard-2 ($48.54) → n2-standard-2 ($71.17)
# MAIS n2 a +46% performance → coût/performance réduit de -20%

# Pour n1-standard-4 → n2-standard-4
n1_cost = 97.08
n2_cost = 142.34

# N2 a +40% performance, donc coût effectif ajusté:
n2_cost_adjusted = n2_cost / 1.40 = 101.67

# Waste = différence (si migration vers n2d au lieu de n2, économie de -30%)
# Utiliser n2d pour économies maximales:
n2d_cost = n2_cost * 0.87  # n2d = -13% vs n2
monthly_waste = n1_cost - n2d_cost

# Coût déjà gaspillé depuis création
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n1-standard-4 depuis 120 jours :
```python
n1_cost = $97.08/mois
n2d_cost = $142.34 * 0.87 = $123.84/mois (ajusté pour performance)

# Coût/performance: n1 moins bon, recommandation n2d-standard-4
# Si on considère coût brut: économie via migration n1→n2d pour perf
# Exemple simplifié: migration vers n2-standard-2 (moitié vCPUs mais +40% perf)
recommended_cost = $71.17
monthly_waste = $97.08 - $71.17 = $25.91
already_wasted = $25.91 * (120/30) = $103.64
```

**Note :** Calcul complexe car n2 a minimum 2 vCPUs. Recommandation réelle dépend du workload.

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `old_generations` | list | `['n1']` | Générations considérées anciennes |
| `preferred_generation` | str | `'n2d'` | Génération recommandée (n2, n2d, c2, etc.) |
| `min_savings_threshold` | float | 10.0 | Économie minimum en $/mois pour alerte |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-5566778899001122334",
  "resource_name": "legacy-app-server",
  "resource_type": "compute_instance_old_generation",
  "zone": "us-central1-a",
  "machine_type": "n1-standard-4",
  "status": "RUNNING",
  "creation_timestamp": "2024-07-05T10:00:00Z",
  "age_days": 120,
  "current_cost_monthly": 97.08,
  "recommended_machine_type": "n2-standard-2",
  "recommended_cost_monthly": 71.17,
  "estimated_monthly_waste": 25.91,
  "already_wasted": 103.64,
  "confidence": "medium",
  "recommendation": "Migrate to n2-standard-2 (similar performance, -27% cost)",
  "migration_notes": "n2 instances have +40% performance per vCPU vs n1",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `compute_instance_no_spot` - Absence d'Usage Spot/Preemptible

#### Détection

**Logique :**

Détecter instances standard (on-demand) qui pourraient utiliser **Spot VMs** (-60% à -91%) :

```python
# 1. Lister toutes les instances RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

# 2. Pour chaque instance, vérifier si Spot/Preemptible
for instance in instances:
    scheduling = instance.get('scheduling', {})
    is_preemptible = scheduling.get('preemptible', False)

    # 3. Vérifier labels pour identifier workload type
    labels = instance.get('labels', {})
    workload_type = labels.get('workload', 'unknown')

    # 4. Détection si instance standard ET workload tolérant interruptions
    if not is_preemptible and workload_type in ['batch', 'dev', 'test', 'staging']:
        # 5. Calculer économie potentielle avec Spot
        machine_type = instance['machineType'].split('/')[-1]
        standard_cost = get_machine_cost(machine_type, spot=False)
        spot_cost = get_machine_cost(machine_type, spot=True)

        savings = standard_cost - spot_cost

        if savings >= min_savings_threshold:
            # No Spot usage = waste détecté
```

**Critères :**
- `status == 'RUNNING'`
- `scheduling.preemptible == False`
- `labels.workload in ['batch', 'dev', 'test', 'staging']`
- Économie Spot > seuil (défaut: $20/mois)

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Instance details (pour scheduling + labels)
compute_client.instances().get(
    project=project_id,
    zone='us-central1-a',
    instance='my-instance'
).execute()
```

#### Calcul de Coût

**Formule :**

Économie potentielle en convertissant vers Spot :

```python
# Pricing standard vs Spot (us-central1)
machine_type = 'n2-standard-4'

standard_cost = 142.34  # $/mois (avec SUD)
spot_cost = 34.16       # $/mois (-76%)

# Waste = différence standard - spot
monthly_waste = standard_cost - spot_cost  # $108.18/mois

# Coût déjà gaspillé depuis création
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-4 standard (batch workload) depuis 60 jours :
```python
standard_cost = $142.34
spot_cost = $34.16
monthly_waste = $108.18
already_wasted = $108.18 * (60/30) = $216.36
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `spot_eligible_labels` | list | `['batch', 'dev', 'test', 'staging']` | Workload types éligibles Spot |
| `min_savings_threshold` | float | 20.0 | Économie minimum en $/mois |
| `exclude_production` | bool | `True` | Exclure instances avec label `env=production` |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9988776655443322110",
  "resource_name": "batch-processing-worker",
  "resource_type": "compute_instance_no_spot",
  "zone": "us-central1-c",
  "machine_type": "n2-standard-4",
  "status": "RUNNING",
  "scheduling": {
    "preemptible": false,
    "onHostMaintenance": "MIGRATE"
  },
  "labels": {
    "workload": "batch",
    "environment": "staging"
  },
  "creation_timestamp": "2024-09-05T12:00:00Z",
  "age_days": 58,
  "current_cost_monthly": 142.34,
  "spot_cost_monthly": 34.16,
  "estimated_monthly_waste": 108.18,
  "already_wasted": 216.36,
  "spot_discount_percentage": 76,
  "confidence": "high",
  "recommendation": "Convert to Spot VM for batch workloads (-76% cost)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `compute_instance_untagged` - Instances Non Taguées

#### Détection

**Logique :**

Détecter instances sans **labels GCP** requis pour gouvernance :

```python
# 1. Lister toutes les instances
instances = compute_client.instances().aggregatedList(
    project=project_id
).execute()

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque instance, vérifier labels
for instance in instances:
    labels = instance.get('labels', {})

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise
- Optionnel: valeurs de labels invalides

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project).execute()
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Instances non taguées = perte de visibilité + risque coût
# Coût estimé = temps management + over-provisioning caché

# Estimations:
# - 5% de coût additionnel par manque de visibilité
# - Risque de duplication/non-nettoyage

machine_type = instance['machineType'].split('/')[-1]
instance_monthly_cost = get_machine_cost(machine_type)

# Governance waste = 5% du coût instance (estimation)
governance_waste_percentage = 0.05
monthly_waste = instance_monthly_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-8 sans labels depuis 90 jours :
```python
instance_monthly_cost = $284.68
monthly_waste = $284.68 * 0.05 = $14.23
already_wasted = $14.23 * (90/30) = $42.69
```

**Note :** Coût gouvernance est estimé. Impact réel = meilleure visibilité coûts + prévention waste.

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |
| `enforce_values` | dict | `{}` | Valeurs autorisées par label (ex: `{'environment': ['dev', 'staging', 'prod']}`) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1231231231231231231",
  "resource_name": "unnamed-instance-47",
  "resource_type": "compute_instance_untagged",
  "zone": "asia-southeast1-a",
  "machine_type": "n2-standard-8",
  "status": "RUNNING",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_timestamp": "2024-08-05T06:00:00Z",
  "age_days": 89,
  "instance_monthly_cost": 284.68,
  "estimated_monthly_waste": 14.23,
  "already_wasted": 42.69,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `compute_instance_devtest_247` - Instances Dev/Test 24/7

#### Détection

**Logique :**

Détecter instances **dev/test** tournant 24/7 (économies via arrêts nocturnes/weekends) :

```python
# 1. Lister toutes les instances RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

# 2. Pour chaque instance, vérifier labels environment
for instance in instances:
    labels = instance.get('labels', {})
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test/staging
    if environment in ['dev', 'test', 'staging', 'development']:
        # 4. Vérifier si instance tourne 24/7 (uptime >7 jours continus)
        creation_timestamp = parse_timestamp(instance['creationTimestamp'])
        last_start = instance.get('lastStartTimestamp', creation_timestamp)
        uptime_days = (now - parse_timestamp(last_start)).days

        if uptime_days >= min_uptime_days:
            # 5. Calculer économie potentielle (arrêt 12h/jour + weekends)
            # Business hours: 8h-20h (12h/jour), Lun-Ven (5/7 jours)
            # Uptime optimal: 12h * 5j = 60h/semaine vs 168h actuel
            # Économie: (168-60)/168 = 64%

            machine_type = instance['machineType'].split('/')[-1]
            monthly_cost = get_machine_cost(machine_type)

            # Waste = 64% du coût (instance arrêtée 64% du temps)
            monthly_waste = monthly_cost * 0.64

            # Dev/Test 24/7 = waste détecté
```

**Critères :**
- `status == 'RUNNING'`
- `labels.environment in ['dev', 'test', 'staging']`
- `uptime_days >= min_uptime_days` (défaut: 7 jours)

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')
```

#### Calcul de Coût

**Formule :**

Économie potentielle avec arrêts planifiés :

```python
# Scénario: Instance dev tournant 24/7
# Optimal: 8h-20h Lun-Ven (60h/semaine)
# Actuel: 24/7 (168h/semaine)

machine_type = 'n2-standard-4'
monthly_cost = 142.34  # $/mois (24/7)

# Calcul coût optimal (60h vs 168h par semaine)
hours_optimal = 60  # 12h/jour * 5 jours
hours_actual = 168  # 24h * 7 jours

optimal_cost = monthly_cost * (hours_optimal / hours_actual)  # $50.83/mois
monthly_waste = monthly_cost - optimal_cost  # $91.51/mois

# Coût déjà gaspillé depuis création
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-4 dev depuis 120 jours :
```python
monthly_cost = $142.34
optimal_cost = $50.83  # (60/168 = 35.7% uptime)
monthly_waste = $91.51
already_wasted = $91.51 * (120/30) = $366.04
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging', 'development']` | Labels indiquant environnement non-prod |
| `min_uptime_days` | int | 7 | Uptime minimum pour détection |
| `business_hours_per_day` | int | 12 | Heures optimales par jour (8h-20h) |
| `business_days_per_week` | int | 5 | Jours optimaux par semaine (Lun-Ven) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-4564564564564564564",
  "resource_name": "dev-frontend-server",
  "resource_type": "compute_instance_devtest_247",
  "zone": "europe-west1-b",
  "machine_type": "n2-standard-4",
  "status": "RUNNING",
  "labels": {
    "environment": "dev",
    "team": "frontend"
  },
  "creation_timestamp": "2024-07-05T09:00:00Z",
  "last_start_timestamp": "2024-07-05T09:00:00Z",
  "uptime_days": 120,
  "current_uptime_hours_weekly": 168,
  "optimal_uptime_hours_weekly": 60,
  "current_cost_monthly": 142.34,
  "optimal_cost_monthly": 50.83,
  "estimated_monthly_waste": 91.51,
  "already_wasted": 366.04,
  "waste_percentage": 64,
  "confidence": "high",
  "recommendation": "Implement automated start/stop schedule (8am-8pm Mon-Fri) for 64% cost savings",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `compute_instance_memory_waste` - Mémoire Sur-Provisionnée (<40% usage)

#### Détection

**Logique :**

Utiliser **Cloud Monitoring** pour analyser usage mémoire réel :

```python
# 1. Lister toutes les instances RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

# 2. Pour chaque instance, récupérer métriques mémoire
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances:
    # 3. Query memory utilization (14 derniers jours)
    # Note: Nécessite Cloud Monitoring Agent installé sur instance
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    results = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="agent.googleapis.com/memory/percent_used" AND resource.instance_id="{instance.id}"',
            "interval": interval,
        }
    )

    # 4. Calculer moyenne mémoire utilisée
    memory_values = [point.value.double_value for series in results for point in series.points]

    if not memory_values:
        # Agent non installé, skip
        continue

    avg_memory = sum(memory_values) / len(memory_values)  # En %

    # 5. Détection si mémoire <40% utilisée
    if avg_memory < memory_threshold:
        # 6. Calculer machine type avec moins de RAM
        current_type = instance['machineType'].split('/')[-1]
        recommended_type = calculate_memory_rightsizing(current_type, avg_memory)

        # Memory waste = détecté
```

**Critères :**
- `status == 'RUNNING'`
- Cloud Monitoring Agent installé (metrics disponibles)
- `avg_memory_used_14d < 40%`
- Possibilité downgrade RAM (ex: n2-standard → n2-highmem inutile)

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Cloud Monitoring API (memory metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="agent.googleapis.com/memory/percent_used"',
    interval={"start_time": ..., "end_time": ...}
)
```

#### Calcul de Coût

**Formule :**

GCP facture RAM séparément des vCPUs :

```python
# GCP Pricing (us-central1, avec SUD):
# vCPU: $0.031611/hour
# RAM: $0.004237/GB/hour

# Exemple: n2-standard-8 (8 vCPUs, 32 GB RAM)
vcpu_cost = 8 * 0.031611 * 730 = $184.61/mois
ram_cost = 32 * 0.004237 * 730 = $99.07/mois
total_cost = $283.68/mois

# Si RAM utilisée = 30%, recommandation: n2-highcpu-8 (8 vCPUs, 8 GB RAM)
new_vcpu_cost = 8 * 0.031611 * 730 = $184.61/mois (identique)
new_ram_cost = 8 * 0.004237 * 730 = $24.77/mois
new_total_cost = $209.38/mois

# Waste = différence RAM
monthly_waste = ram_cost - new_ram_cost  # $74.30/mois

# Coût déjà gaspillé
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-8 (32 GB) avec RAM à 28% depuis 90 jours :
```python
current_ram_cost = $99.07/mois
recommended_ram_cost = $24.77/mois (8 GB au lieu de 32 GB)
monthly_waste = $74.30
already_wasted = $74.30 * (90/30) = $222.90
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `memory_threshold` | float | 40.0 | Mémoire % maximum pour over-provisioning |
| `lookback_days` | int | 14 | Période d'analyse |
| `min_datapoints` | int | 50 | Points minimum requis |
| `require_monitoring_agent` | bool | `True` | Exiger agent installé (sinon skip) |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-7897897897897897897",
  "resource_name": "app-server-highram",
  "resource_type": "compute_instance_memory_waste",
  "zone": "us-central1-a",
  "machine_type": "n2-standard-8",
  "status": "RUNNING",
  "memory_specs": {
    "total_gb": 32,
    "avg_used_gb": 8.96,
    "avg_used_percent": 28.0,
    "max_used_percent": 42.1
  },
  "current_cost_monthly": 283.68,
  "current_ram_cost_monthly": 99.07,
  "recommended_machine_type": "n2-highcpu-8",
  "recommended_ram_gb": 8,
  "recommended_cost_monthly": 209.38,
  "estimated_monthly_waste": 74.30,
  "already_wasted": 222.90,
  "confidence": "high",
  "recommendation": "Downgrade from 32GB to 8GB RAM (n2-highcpu-8)",
  "monitoring_agent_installed": true,
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `compute_instance_rightsizing` - Opportunités de Right-Sizing

#### Détection

**Logique :**

Analyse holistique CPU + RAM + Disk I/O pour recommandation précise :

```python
# 1. Instances RUNNING uniquement
instances = get_running_instances()

for instance in instances:
    # 2. Récupérer toutes les métriques (14 jours)
    metrics = {
        'cpu': get_avg_cpu(instance, lookback_days=14),
        'memory': get_avg_memory(instance, lookback_days=14),
        'disk_read_ops': get_avg_disk_read_ops(instance, lookback_days=14),
        'disk_write_ops': get_avg_disk_write_ops(instance, lookback_days=14),
        'network_in': get_avg_network_in(instance, lookback_days=14),
        'network_out': get_avg_network_out(instance, lookback_days=14),
    }

    # 3. Algorithme de right-sizing
    current_type = instance['machineType'].split('/')[-1]
    current_specs = get_machine_specs(current_type)  # vCPUs, RAM

    # 4. Calculer ressources optimales basées sur métriques
    optimal_vcpus = calculate_optimal_vcpus(metrics['cpu'], current_specs['vcpus'])
    optimal_ram_gb = calculate_optimal_ram(metrics['memory'], current_specs['ram_gb'])

    # 5. Trouver machine type correspondante
    recommended_type = find_closest_machine_type(optimal_vcpus, optimal_ram_gb)

    # 6. Détection si machine recommandée != actuelle ET économie >10%
    current_cost = get_machine_cost(current_type)
    recommended_cost = get_machine_cost(recommended_type)

    savings_percentage = (current_cost - recommended_cost) / current_cost * 100

    if recommended_type != current_type and savings_percentage >= min_savings_pct:
        # Right-sizing opportunity = détecté
```

**Critères :**
- Métriques complètes disponibles (CPU, RAM, Disk, Network)
- Économie potentielle >10%
- Recommandation basée sur usage réel

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Cloud Monitoring API (multiple metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/cpu/utilization"'
)

monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="agent.googleapis.com/memory/percent_used"'
)

# Disk I/O metrics, Network metrics, etc.
```

#### Calcul de Coût

**Formule :**

Calcul précis basé sur analyse multi-métriques :

```python
# Exemple: Instance actuelle n2-standard-8 (8 vCPUs, 32 GB)
current_cost = 283.68  # $/mois

# Métriques observées:
# - CPU: 18% avg
# - Memory: 35% avg (11.2 GB / 32 GB)
# - Disk I/O: Low
# - Network: Moderate

# Recommandation algorithme:
# - vCPUs requis: 18% * 8 = 1.44 vCPUs → arrondi à 2 vCPUs
# - RAM requis: 11.2 GB * 1.3 (safety margin) = 14.56 GB → arrondi à 16 GB
# - Machine recommandée: n2-standard-4 (4 vCPUs, 16 GB) - over spec for safety

recommended_type = 'n2-standard-4'
recommended_cost = 142.34  # $/mois

# Waste
monthly_waste = current_cost - recommended_cost  # $141.34/mois
savings_percentage = (monthly_waste / current_cost) * 100  # 49.8%

# Coût déjà gaspillé
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance n2-standard-8 depuis 180 jours :
```python
monthly_waste = $141.34
already_wasted = $141.34 * (180/30) = $848.04
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_savings_pct` | float | 10.0 | Économie minimum % pour recommandation |
| `safety_margin_cpu` | float | 1.5 | Marge sécurité vCPU (1.5x usage observé) |
| `safety_margin_ram` | float | 1.3 | Marge sécurité RAM (1.3x usage observé) |
| `lookback_days` | int | 14 | Période analyse métriques |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1471471471471471471",
  "resource_name": "api-backend-overspec",
  "resource_type": "compute_instance_rightsizing",
  "zone": "us-east1-b",
  "machine_type": "n2-standard-8",
  "status": "RUNNING",
  "current_specs": {
    "vcpus": 8,
    "ram_gb": 32
  },
  "metrics_analysis": {
    "avg_cpu_percent": 18.2,
    "avg_memory_percent": 35.0,
    "avg_memory_used_gb": 11.2,
    "avg_disk_read_iops": 120,
    "avg_disk_write_iops": 80,
    "avg_network_in_mbps": 5.4,
    "avg_network_out_mbps": 8.2
  },
  "optimal_specs": {
    "vcpus": 2,
    "ram_gb": 15
  },
  "recommended_machine_type": "n2-standard-4",
  "recommended_specs": {
    "vcpus": 4,
    "ram_gb": 16
  },
  "current_cost_monthly": 283.68,
  "recommended_cost_monthly": 142.34,
  "estimated_monthly_waste": 141.34,
  "already_wasted": 848.04,
  "savings_percentage": 49.8,
  "confidence": "high",
  "recommendation": "Right-size from n2-standard-8 to n2-standard-4 for 50% cost savings",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `compute_instance_burstable_waste` - Instances Burstable Sous-Utilisées

#### Détection

**Logique :**

Détecter instances **e2** (burstable) qui n'utilisent pas les bursts → downgrade vers f1/g1 :

```python
# 1. Lister instances e2 (burstable) RUNNING
instances = compute_client.instances().aggregatedList(
    project=project_id,
    filter='status=RUNNING'
).execute()

e2_instances = [i for i in instances if i['machineType'].split('/')[-1].startswith('e2-')]

# 2. Pour chaque instance e2, analyser CPU burst usage
for instance in e2_instances:
    # 3. Récupérer CPU utilization (14 jours)
    cpu_values = get_cpu_timeseries(instance, lookback_days=14)

    # 4. Identifier bursts (CPU >20% pour e2-micro/small)
    # e2 instances ont baseline CPU: e2-micro=12.5%, e2-small=25%
    machine_type = instance['machineType'].split('/')[-1]

    baseline_cpu = {
        'e2-micro': 12.5,
        'e2-small': 25.0,
        'e2-medium': 50.0,
    }

    baseline = baseline_cpu.get(machine_type, 50.0)

    # 5. Calculer % temps au-dessus baseline (= burst usage)
    burst_percentage = sum(1 for cpu in cpu_values if cpu > baseline) / len(cpu_values) * 100

    # 6. Détection si burst <5% (jamais utilisé)
    if burst_percentage < max_burst_pct:
        # 7. Recommandation: downgrade vers f1-micro/g1-small (shared-core)
        # e2-micro ($7.11/mois) → f1-micro ($3.88/mois) = -45%

        recommended_type = 'f1-micro' if machine_type == 'e2-micro' else 'g1-small'

        # Burstable waste = détecté
```

**Critères :**
- `machine_type.startswith('e2-')`
- `status == 'RUNNING'`
- Burst usage <5% du temps (jamais dépasse baseline)

**API Calls :**
```python
# Compute Engine API
compute_client.instances().aggregatedList(project, filter='status=RUNNING')

# Cloud Monitoring API (CPU utilization)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/cpu/utilization"',
    interval={"start_time": ..., "end_time": ...}
)
```

#### Calcul de Coût

**Formule :**

Économie en downgradant e2 → f1/g1 :

```python
# Pricing (us-central1, avec SUD)
e2_pricing = {
    'e2-micro': 7.11,   # $/mois
    'e2-small': 14.23,
    'e2-medium': 28.45,
}

f1g1_pricing = {
    'f1-micro': 3.88,   # $/mois (shared-core)
    'g1-small': 13.23,  # $/mois (shared-core, 1.7 GB)
}

# Exemple: e2-micro → f1-micro
current_cost = 7.11
recommended_cost = 3.88
monthly_waste = 3.23  # -45%

# Coût déjà gaspillé
age_months = (now - creation_date).days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance e2-micro (burst jamais utilisé) depuis 120 jours :
```python
current_cost = $7.11
recommended_cost = $3.88
monthly_waste = $3.23
already_wasted = $3.23 * (120/30) = $12.92
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_burst_pct` | float | 5.0 | % temps maximum au-dessus baseline pour détection |
| `lookback_days` | int | 14 | Période d'analyse |
| `e2_baseline_cpu` | dict | `{'e2-micro': 12.5, 'e2-small': 25.0}` | CPU baseline par type |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9639639639639639639",
  "resource_name": "low-traffic-web",
  "resource_type": "compute_instance_burstable_waste",
  "zone": "us-west1-a",
  "machine_type": "e2-micro",
  "status": "RUNNING",
  "cpu_analysis": {
    "baseline_cpu_percent": 12.5,
    "avg_cpu_percent": 6.2,
    "max_cpu_percent": 15.8,
    "time_above_baseline_percent": 2.3,
    "burst_usage_percent": 2.3
  },
  "current_cost_monthly": 7.11,
  "recommended_machine_type": "f1-micro",
  "recommended_cost_monthly": 3.88,
  "estimated_monthly_waste": 3.23,
  "already_wasted": 12.92,
  "savings_percentage": 45.4,
  "confidence": "high",
  "recommendation": "Downgrade to f1-micro (shared-core) - burst capability unused",
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
# Créer projet GCP dédié testing
gcloud projects create cloudwaste-test-$(date +%s) \
  --name="CloudWaste Testing" \
  --labels=environment=test

# Définir projet actif
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable compute.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account Setup

```bash
# Créer Service Account
gcloud iam service-accounts create cloudwaste-scanner \
  --display-name="CloudWaste Scanner" \
  --description="Read-only scanner for waste detection"

# Attacher rôles read-only
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/compute.viewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/monitoring.viewer"

# Générer clé JSON
gcloud iam service-accounts keys create cloudwaste-key.json \
  --iam-account=cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com

# Définir credentials
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

#### 3. Installer Cloud Monitoring Agent

**Important :** Requis pour métriques mémoire (scénarios 8-10)

```bash
# Template installation agent (à exécuter sur instances)
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

---

### Tests Unitaires - Créer Instances de Test

#### Scénario 1: Instance Arrêtée >30 Jours

```bash
# Créer instance avec disques
gcloud compute instances create test-stopped-instance \
  --zone=us-central1-a \
  --machine-type=n1-standard-2 \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-standard \
  --create-disk=size=50GB,type=pd-ssd

# Arrêter instance
gcloud compute instances stop test-stopped-instance --zone=us-central1-a

# Modifier lastStopTimestamp (simuler 30+ jours) - via API ou attendre
# Note: Pour tests, utiliser instance réellement arrêtée depuis >30 jours
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_stopped",
  "resource_name": "test-stopped-instance",
  "status": "TERMINATED",
  "age_days": ">=30",
  "estimated_monthly_cost": "~12.50",
  "confidence": "high"
}
```

---

#### Scénario 2: Instance Idle (CPU <5%)

```bash
# Créer instance n2-standard-2
gcloud compute instances create test-idle-instance \
  --zone=us-central1-a \
  --machine-type=n2-standard-2 \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --labels=environment=test

# SSH et installer monitoring agent
gcloud compute ssh test-idle-instance --zone=us-central1-a

# Sur instance:
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

# Laisser tourner idle (aucune charge) pendant 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_idle",
  "avg_cpu_14d": "<5%",
  "estimated_monthly_waste": "~67.61",
  "recommendation": "Downgrade to e2-small"
}
```

---

#### Scénario 3: Instance Over-Provisioned (CPU <30%)

```bash
# Créer instance n2-standard-8 (large)
gcloud compute instances create test-overprovisioned \
  --zone=us-central1-a \
  --machine-type=n2-standard-8 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# SSH et générer charge CPU à 20%
gcloud compute ssh test-overprovisioned --zone=us-central1-a

# Sur instance: stress CPU à 20% constant
sudo apt-get update && sudo apt-get install -y stress-ng
stress-ng --cpu 1 --cpu-load 20 --timeout 0 &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_overprovisioned",
  "avg_cpu_14d": "~20%",
  "recommended_machine_type": "n2-standard-4",
  "estimated_monthly_waste": "~142.34"
}
```

---

#### Scénario 4: Ancienne Génération (n1)

```bash
# Créer instance n1-standard-4
gcloud compute instances create test-old-generation \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --image-family=debian-11 \
  --image-project=debian-cloud
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_old_generation",
  "machine_type": "n1-standard-4",
  "recommended_machine_type": "n2-standard-2",
  "estimated_monthly_waste": "~25.91"
}
```

---

#### Scénario 5: No Spot Usage

```bash
# Créer instance standard avec label batch
gcloud compute instances create test-no-spot \
  --zone=us-central1-a \
  --machine-type=n2-standard-4 \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --labels=workload=batch,environment=staging
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_no_spot",
  "scheduling": {"preemptible": false},
  "labels": {"workload": "batch"},
  "spot_discount_percentage": 76,
  "estimated_monthly_waste": "~108.18"
}
```

---

#### Scénario 6: Instances Non Taguées

```bash
# Créer instance SANS labels
gcloud compute instances create test-untagged \
  --zone=us-central1-a \
  --machine-type=n2-standard-8 \
  --image-family=debian-11 \
  --image-project=debian-cloud
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_untagged",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~14.23"
}
```

---

#### Scénario 7: Dev/Test 24/7

```bash
# Créer instance dev
gcloud compute instances create test-devtest-247 \
  --zone=europe-west1-b \
  --machine-type=n2-standard-4 \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --labels=environment=dev,team=backend

# Laisser tourner 7+ jours sans arrêt
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_devtest_247",
  "labels": {"environment": "dev"},
  "uptime_days": ">=7",
  "waste_percentage": 64,
  "estimated_monthly_waste": "~91.51"
}
```

---

#### Scénario 8: Mémoire Sur-Provisionnée

```bash
# Créer instance n2-standard-8 (32 GB RAM)
gcloud compute instances create test-memory-waste \
  --zone=us-central1-a \
  --machine-type=n2-standard-8 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# SSH, installer agent, laisser RAM idle (<40% usage)
gcloud compute ssh test-memory-waste --zone=us-central1-a

# Sur instance: installer monitoring agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

# Laisser tourner 14 jours avec faible usage mémoire
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_memory_waste",
  "avg_memory_percent": "<40%",
  "recommended_machine_type": "n2-highcpu-8",
  "estimated_monthly_waste": "~74.30"
}
```

---

#### Scénario 9: Right-Sizing

```bash
# Créer instance large (n2-standard-8) sous-utilisée
gcloud compute instances create test-rightsizing \
  --zone=us-east1-b \
  --machine-type=n2-standard-8 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# SSH, installer agent, stress CPU à 18% + RAM à 35%
gcloud compute ssh test-rightsizing --zone=us-east1-b

# Sur instance:
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

sudo apt-get update && sudo apt-get install -y stress-ng
stress-ng --cpu 1 --cpu-load 18 --vm 1 --vm-bytes 11G --timeout 0 &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_rightsizing",
  "avg_cpu_percent": "~18%",
  "avg_memory_percent": "~35%",
  "recommended_machine_type": "n2-standard-4",
  "savings_percentage": "~50%",
  "estimated_monthly_waste": "~141.34"
}
```

---

#### Scénario 10: Burstable Waste

```bash
# Créer instance e2-micro
gcloud compute instances create test-burstable-waste \
  --zone=us-west1-a \
  --machine-type=e2-micro \
  --image-family=debian-11 \
  --image-project=debian-cloud

# SSH, installer agent, laisser CPU <12.5% (baseline)
gcloud compute ssh test-burstable-waste --zone=us-west1-a

# Sur instance:
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

# Laisser tourner 14 jours sans burst
```

**Validation attendue :**
```json
{
  "resource_type": "compute_instance_burstable_waste",
  "machine_type": "e2-micro",
  "burst_usage_percent": "<5%",
  "recommended_machine_type": "f1-micro",
  "estimated_monthly_waste": "~3.23"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script de validation complet pour GCP Compute Engine Instances
"""

from google.cloud import compute_v1
from google.cloud import monitoring_v3
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    compute_client = compute_v1.InstancesClient()

    # 1. Lister toutes les instances
    request = compute_v1.AggregatedListInstancesRequest(
        project=PROJECT_ID
    )

    agg_list = compute_client.aggregated_list(request=request)

    instances = []
    for zone, response in agg_list:
        if response.instances:
            instances.extend(response.instances)

    print(f"✅ Found {len(instances)} instances")

    # 2. Vérifier détection pour chaque scénario
    scenarios_detected = {
        'stopped': 0,
        'idle': 0,
        'overprovisioned': 0,
        'old_generation': 0,
        'no_spot': 0,
        'untagged': 0,
        'devtest_247': 0,
        'memory_waste': 0,
        'rightsizing': 0,
        'burstable_waste': 0,
    }

    for instance in instances:
        name = instance.name

        # Logique de détection (simplifié)
        if instance.status == 'TERMINATED':
            scenarios_detected['stopped'] += 1
            print(f"✅ Detected scenario 1 (stopped): {name}")

        if instance.machine_type.endswith('n1-standard-4'):
            scenarios_detected['old_generation'] += 1
            print(f"✅ Detected scenario 4 (old generation): {name}")

        # ... (implémenter logique pour autres scénarios)

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
python3 test_gcp_compute_instances.py
```

**Résultat attendu :**
```
✅ Found 10 instances
✅ Detected scenario 1 (stopped): test-stopped-instance
✅ Detected scenario 2 (idle): test-idle-instance
✅ Detected scenario 3 (overprovisioned): test-overprovisioned
✅ Detected scenario 4 (old generation): test-old-generation
✅ Detected scenario 5 (no spot): test-no-spot
✅ Detected scenario 6 (untagged): test-untagged
✅ Detected scenario 7 (devtest 24/7): test-devtest-247
✅ Detected scenario 8 (memory waste): test-memory-waste
✅ Detected scenario 9 (rightsizing): test-rightsizing
✅ Detected scenario 10 (burstable waste): test-burstable-waste

📊 Detection Summary:
  - stopped: 1 instances
  - idle: 1 instances
  - overprovisioned: 1 instances
  - old_generation: 1 instances
  - no_spot: 1 instances
  - untagged: 1 instances
  - devtest_247: 1 instances
  - memory_waste: 1 instances
  - rightsizing: 1 instances
  - burstable_waste: 1 instances

✅ Total waste detected: 10 instances
```

---

### Cleanup

```bash
# Supprimer toutes les instances de test
gcloud compute instances delete test-stopped-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-idle-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-overprovisioned --zone=us-central1-a --quiet
gcloud compute instances delete test-old-generation --zone=us-central1-a --quiet
gcloud compute instances delete test-no-spot --zone=us-central1-a --quiet
gcloud compute instances delete test-untagged --zone=us-central1-a --quiet
gcloud compute instances delete test-devtest-247 --zone=europe-west1-b --quiet
gcloud compute instances delete test-memory-waste --zone=us-central1-a --quiet
gcloud compute instances delete test-rightsizing --zone=us-east1-b --quiet
gcloud compute instances delete test-burstable-waste --zone=us-west1-a --quiet

# Supprimer Service Account
gcloud iam service-accounts delete cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com --quiet

# Supprimer projet test (optionnel)
gcloud projects delete $PROJECT_ID --quiet
```

---

## Références

### Documentation GCP

- [Compute Engine Instances API](https://cloud.google.com/compute/docs/reference/rest/v1/instances)
- [Cloud Monitoring API](https://cloud.google.com/monitoring/api/v3)
- [Machine Types Pricing](https://cloud.google.com/compute/vm-instance-pricing)
- [Spot VMs Documentation](https://cloud.google.com/compute/docs/instances/spot)
- [Sustained Use Discounts](https://cloud.google.com/compute/docs/sustained-use-discounts)
- [Committed Use Discounts](https://cloud.google.com/compute/docs/instances/signing-up-committed-use-discounts)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing complet 27 ressources GCP
- [GCP.csv](./GCP.csv) - Tableau Excel ressources GCP
- [README.md](./README.md) - Guide utilisation documentation GCP

### Équivalences AWS/Azure

- **AWS EC2 Instances** → GCP Compute Engine Instances
- **Azure Virtual Machines** → GCP Compute Engine Instances
- **AWS CloudWatch** → GCP Cloud Monitoring
- **Azure Monitor** → GCP Cloud Monitoring
- **AWS Spot Instances** → GCP Spot VMs
- **Azure Spot VMs** → GCP Spot VMs

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
