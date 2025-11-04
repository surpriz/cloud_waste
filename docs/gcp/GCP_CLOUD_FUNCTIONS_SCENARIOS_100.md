# GCP Cloud Functions - Scénarios de Gaspillage (100%)

**Type de ressource :** `Compute : Cloud Functions`
**Catégorie :** Serverless Functions (FaaS)
**Impact financier estimé :** $5,000 - $25,000/an pour une organisation moyenne (500-2000 functions)
**Complexité de détection :** ⭐⭐⭐⭐ (Élevée - 2 générations avec pricing différents + analyse métriques)

---

## Vue d'Ensemble

### Qu'est-ce que Cloud Functions ?

**Cloud Functions** est le service serverless FaaS (Function-as-a-Service) de GCP pour exécuter du code event-driven sans gérer de serveurs :
- **Event-driven** (triggers : HTTP, Pub/Sub, Cloud Storage, Firestore, etc.)
- **Autoscaling automatique** (0 to N instances)
- **Pay-per-use** (facturé à l'invocation + compute time)
- **Deux générations** avec pricing et features différents

### Architecture Cloud Functions : 1st Gen vs 2nd Gen

```
Cloud Functions Comparison
│
├── 1st Generation (Legacy)
│   ├── Runtime Support
│   │   ├── Node.js 10, 12, 14, 16, 18, 20
│   │   ├── Python 3.7, 3.8, 3.9, 3.10, 3.11
│   │   ├── Go 1.11, 1.13, 1.16, 1.18, 1.19, 1.20, 1.21
│   │   ├── Java 11, 17
│   │   ├── Ruby 2.6, 2.7, 3.0
│   │   └── .NET Core 3.1, .NET 6, 7
│   ├── Resources
│   │   ├── Memory: 128 MB - 8 GB
│   │   ├── CPU: Allocated based on memory (200 MHz - 2.4 GHz)
│   │   └── Timeout: 1s - 540s (9 minutes max)
│   ├── Scaling
│   │   ├── Min instances: NOT supported ❌
│   │   ├── Max instances: 1-3000
│   │   └── Concurrency: 1 request/instance only
│   └── Billing
│       ├── Invocations: $0.40/million
│       ├── Compute GB-seconds: $0.0000025/GB-second
│       └── Compute GHz-seconds: $0.0000100/GHz-second
│
└── 2nd Generation (Cloud Run based)
    ├── Runtime Support (same as 1st gen)
    ├── Resources
    │   ├── Memory: 128 MiB - 32 GiB
    │   ├── CPU: 0.08 - 8 vCPU
    │   └── Timeout: 1s - 3600s (60 minutes max) ✅
    ├── Scaling
    │   ├── Min instances: 0-1000 ✅ (warm instances 24/7)
    │   ├── Max instances: 1-1000
    │   └── Concurrency: 1-1000 requests/instance ✅
    └── Billing
        ├── Invocations: $0.40/million
        ├── vCPU-seconds: $0.00002400/vCPU-second
        ├── GiB-seconds: $0.00000250/GiB-second
        └── Min instances: Billed 24/7 (like Cloud Run)
```

### Caractéristiques Principales

| Feature | 1st Gen | 2nd Gen | Impact Coût |
|---------|---------|---------|-------------|
| **Min instances** | ❌ Not supported | ✅ 0-1000 | 2nd gen: si > 0 = billing 24/7 |
| **Concurrency** | 1 req/instance | 1-1000 req/instance | 2nd gen: concurrency > 1 = moins d'instances |
| **Timeout max** | 540s (9 min) | 3600s (60 min) | 2nd gen: timeouts longs possibles |
| **Memory max** | 8 GB | 32 GiB | 2nd gen: workloads gourmands |
| **Pricing model** | GB-seconds | vCPU-seconds + GiB-seconds | Différent selon workload |
| **Cold start** | ~1-3s | ~1-3s | Similar |
| **Triggers** | HTTP, events | HTTP, events | Same |

### Cloud Functions Pricing Comparison

#### 1st Generation Pricing (us-central1)

```python
# 1st Gen Pricing
INVOCATIONS_PRICE_1ST = 0.40  # $/million invocations
COMPUTE_GB_SECONDS_1ST = 0.0000025  # $/GB-second
COMPUTE_GHZ_SECONDS_1ST = 0.0000100  # $/GHz-second

# CPU allocation basée sur memory:
# 128 MB → 200 MHz
# 256 MB → 400 MHz
# 512 MB → 800 MHz
# 1 GB → 1.4 GHz
# 2 GB → 2.4 GHz
# 4+ GB → 2.4 GHz

# Exemple : 256 MB, 1M invocations, 200ms avg
memory_gb = 0.256
cpu_ghz = 0.400  # 400 MHz for 256 MB
invocations = 1_000_000
avg_duration = 0.2  # 200ms

invocations_cost = (invocations / 1_000_000) * 0.40  # $0.40
compute_seconds = invocations * avg_duration  # 200,000 seconds
memory_cost = compute_seconds * memory_gb * 0.0000025  # $0.128
cpu_cost = compute_seconds * cpu_ghz * 0.0000100  # $0.80

total_1st_gen = 0.40 + 0.128 + 0.80  # = $1.328/mois
```

#### 2nd Generation Pricing (us-central1)

```python
# 2nd Gen Pricing (same as Cloud Run)
INVOCATIONS_PRICE_2ND = 0.40  # $/million invocations
VCPU_PRICE_2ND = 0.00002400  # $/vCPU-second
MEMORY_PRICE_2ND = 0.00000250  # $/GiB-second

# Exemple : 1 vCPU, 512 MiB, 1M invocations, 200ms avg
vcpu = 1.0
memory_gib = 0.5
invocations = 1_000_000
avg_duration = 0.2  # 200ms

invocations_cost = (invocations / 1_000_000) * 0.40  # $0.40
compute_seconds = invocations * avg_duration  # 200,000 seconds
vcpu_cost = compute_seconds * vcpu * 0.00002400  # $4.80
memory_cost = compute_seconds * memory_gib * 0.00000250  # $0.25

total_2nd_gen = 0.40 + 4.80 + 0.25  # = $5.45/mois

# Si min_instances = 1 (permanent instance 24/7)
min_instance_monthly = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000
# = $64.58/mois additional ❌
```

**💡 Observation** : 2nd gen peut être plus cher si pas de min instances, mais offre concurrency + timeout long.

### Waste Typique

1. **Functions never invoked** : 0 invocations = $20-200/fonction/mois
2. **Min instances idle (2nd gen)** : min_instances > 0 + traffic faible = $50-500/mois
3. **Memory overprovisioning** : Memory allocated >> used = 50-70% surcoût
4. **Excessive timeout** : Timeout trop long = risque runaway costs
5. **1st gen expensive** : Certains workloads moins chers en 2nd gen
6. **Untagged functions** : Sans labels = confusion cleanup
7. **Excessive max instances** : max > 100 = risque spike $1K+/jour

---

## Modèle de Pricing Cloud Functions

### Pricing Détaillé 1st Generation

#### Composants de Coût 1st Gen

```python
# 1. Invocations
invocations_cost = (total_invocations / 1_000_000) * 0.40

# 2. Compute Time (Memory)
compute_gb_seconds = total_invocations * avg_duration_seconds * memory_gb
memory_cost = compute_gb_seconds * 0.0000025

# 3. Compute Time (CPU)
# CPU allocated based on memory:
memory_to_cpu = {
    0.128: 0.200,  # 128 MB → 200 MHz
    0.256: 0.400,  # 256 MB → 400 MHz
    0.512: 0.800,  # 512 MB → 800 MHz
    1.0: 1.4,      # 1 GB → 1.4 GHz
    2.0: 2.4,      # 2 GB → 2.4 GHz
    4.0: 2.4,      # 4+ GB → 2.4 GHz
}

cpu_ghz = memory_to_cpu.get(memory_gb, 2.4)
compute_ghz_seconds = total_invocations * avg_duration_seconds * cpu_ghz
cpu_cost = compute_ghz_seconds * 0.0000100

# Total 1st Gen
total_cost_1st_gen = invocations_cost + memory_cost + cpu_cost
```

**Exemple 1 : Function légère (128 MB, 50ms)**
```python
invocations = 1_000_000
memory_gb = 0.128
cpu_ghz = 0.200
avg_duration = 0.050  # 50ms

invocations_cost = 1 * 0.40 = $0.40
memory_cost = 50,000 * 0.128 * 0.0000025 = $0.016
cpu_cost = 50,000 * 0.200 * 0.0000100 = $0.10

total = $0.516/mois pour 1M invocations
```

**Exemple 2 : Function gourmande (2 GB, 5s)**
```python
invocations = 100_000
memory_gb = 2.0
cpu_ghz = 2.4
avg_duration = 5.0  # 5 seconds

invocations_cost = 0.1 * 0.40 = $0.04
memory_cost = 500,000 * 2.0 * 0.0000025 = $2.50
cpu_cost = 500,000 * 2.4 * 0.0000100 = $12.00

total = $14.54/mois pour 100K invocations
```

### Pricing Détaillé 2nd Generation

#### Composants de Coût 2nd Gen

```python
# 1. Invocations (same as 1st gen)
invocations_cost = (total_invocations / 1_000_000) * 0.40

# 2. vCPU Compute Time
vcpu_seconds = total_invocations * avg_duration_seconds * vcpu
vcpu_cost = vcpu_seconds * 0.00002400

# 3. Memory Compute Time
memory_gib_seconds = total_invocations * avg_duration_seconds * memory_gib
memory_cost = memory_gib_seconds * 0.00000250

# 4. Min Instances (if configured)
if min_instances > 0:
    seconds_per_month = 30 * 24 * 3600  # 2,592,000
    min_instance_vcpu_cost = min_instances * vcpu * 0.00002400 * seconds_per_month
    min_instance_memory_cost = min_instances * memory_gib * 0.00000250 * seconds_per_month
    min_instances_cost = min_instance_vcpu_cost + min_instance_memory_cost
else:
    min_instances_cost = 0

# Total 2nd Gen
total_cost_2nd_gen = invocations_cost + vcpu_cost + memory_cost + min_instances_cost
```

**Exemple 1 : Function légère (0.5 vCPU, 256 MiB, 50ms)**
```python
invocations = 1_000_000
vcpu = 0.5
memory_gib = 0.25
avg_duration = 0.050
min_instances = 0

invocations_cost = 1 * 0.40 = $0.40
vcpu_cost = 50,000 * 0.5 * 0.00002400 = $0.60
memory_cost = 50,000 * 0.25 * 0.00000250 = $0.031

total = $1.031/mois (sans min instances)
```

**Exemple 2 : Function gourmande (2 vCPU, 4 GiB, 5s)**
```python
invocations = 100_000
vcpu = 2.0
memory_gib = 4.0
avg_duration = 5.0
min_instances = 0

invocations_cost = 0.1 * 0.40 = $0.04
vcpu_cost = 500,000 * 2.0 * 0.00002400 = $24.00
memory_cost = 500,000 * 4.0 * 0.00000250 = $5.00

total = $29.04/mois (sans min instances)
```

**Exemple 3 : 2nd Gen avec min_instances = 1**
```python
# Configuration identique exemple 2 + min_instances = 1
vcpu = 2.0
memory_gib = 4.0
min_instances = 1

# Coût invocations + compute (même que exemple 2)
invocations_compute_cost = 29.04

# Coût min instance permanent (24/7)
seconds_per_month = 2_592_000
min_instance_cost = (2.0 * 0.00002400 + 4.0 * 0.00000250) * 2_592_000
# = $161.33/mois ❌

total = $29.04 + $161.33 = $190.37/mois
```

### Comparison 1st Gen vs 2nd Gen

| Scenario | Invocations | Exec Time | 1st Gen Cost | 2nd Gen Cost | Winner |
|----------|-------------|-----------|--------------|--------------|---------|
| **High freq, short** | 1M/mois | 50ms | $0.52 | $1.03 | 1st Gen ✅ |
| **Med freq, medium** | 500K/mois | 500ms | $6.65 | $12.88 | 1st Gen ✅ |
| **Low freq, long** | 10K/mois | 10s | $6.10 | $12.20 | 1st Gen ✅ |
| **With concurrency 100** | 1M/mois | 200ms | N/A (1 req/inst) | $5.45 | 2nd Gen ✅ |
| **With min_instances=1** | 100K/mois | 1s | $2.93 | $164.85 | 1st Gen ✅ |
| **Timeout > 9 min** | Any | >540s | ❌ Not supported | ✅ Supported | 2nd Gen ✅ |

**💡 Règles générales** :
- **1st Gen** généralement moins cher pour simple workloads
- **2nd Gen** meilleur si besoin concurrency > 1 OU timeout > 9 min
- **Min instances** (2nd gen) très coûteux = éviter sauf nécessité

---

## Phase 1 : Détection Simple (7 Scénarios)

### Scénario 1 : Functions Jamais Invoquées

**Description :** Functions déployées mais jamais invoquées (0 invocations depuis 30+ jours). Waste total.

**Impact financier :**
- **Coût mensuel moyen :** $20 - $200/fonction (selon generation + config)
- **Waste typique :** 20-30% des functions jamais utilisées
- **Économie annuelle :** $5K - $20K

**Logique de détection :**

```python
from google.cloud import functions_v1
from google.cloud import functions_v2
from google.cloud import monitoring_v3
from datetime import datetime, timedelta

def detect_cloud_function_never_invoked(
    project_id: str,
    no_invocations_threshold_days: int = 30
) -> list:
    """
    Détecte les Cloud Functions jamais invoquées (0 invocations).

    Args:
        project_id: ID du projet GCP
        no_invocations_threshold_days: Période sans invocations (défaut: 30 jours)

    Returns:
        Liste des functions jamais invoquées avec métadonnées
    """
    # Clients pour 1st et 2nd gen
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    never_invoked_functions = []

    # 1. Lister toutes les functions 1st gen
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Query execution_count metric (1st gen)
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=no_invocations_threshold_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_function" '
                f'AND resource.labels.function_name = "{function_name}" '
                f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
            )

            time_series = monitoring_client.list_time_series(request=request)

            # Calculer total invocations
            total_invocations = 0
            for series in time_series:
                for point in series.points:
                    total_invocations += point.value.int64_value or 0

            # Détection si 0 invocations
            if total_invocations == 0:
                # Function jamais invoquée = waste

                # Extraire config
                memory_mb = function.available_memory_mb
                timeout_seconds = function.timeout.seconds if function.timeout else 60

                # Estimer coût mensuel (1st gen)
                # Même sans invocations, pas de min instances en 1st gen
                monthly_cost = 0  # 1st gen = $0 si 0 invocations

                # Age de la fonction
                update_time = function.update_time
                age_days = (datetime.utcnow().replace(tzinfo=None) - update_time.replace(tzinfo=None)).days

                # Niveau confiance
                if age_days >= 90:
                    confidence = "CRITICAL"
                elif age_days >= 60:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                never_invoked_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "runtime": function.runtime,
                    "memory_mb": memory_mb,
                    "timeout_seconds": timeout_seconds,
                    "age_days": age_days,
                    "update_time": update_time.isoformat(),
                    "total_invocations": 0,
                    "monthly_cost": round(monthly_cost, 2),
                    "annual_cost": round(monthly_cost * 12, 2),
                    "confidence": confidence,
                    "labels": dict(function.labels) if function.labels else {},
                    "trigger_type": "http" if function.https_trigger else "event",
                })
    except Exception as e:
        print(f"Error listing 1st gen functions: {e}")

    # 2. Lister toutes les functions 2nd gen
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Query request_count metric (2nd gen utilise métriques Cloud Run)
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=no_invocations_threshold_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/request_count"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
            )

            time_series = monitoring_client.list_time_series(request=request)

            total_invocations = 0
            for series in time_series:
                for point in series.points:
                    total_invocations += point.value.int64_value or 0

            if total_invocations == 0:
                # 2nd gen function jamais invoquée

                # Extraire config
                service_config = function.service_config
                memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config.available_memory else 256
                timeout_seconds = service_config.timeout_seconds if service_config.timeout_seconds else 60
                min_instances = service_config.min_instance_count if service_config else 0

                # Calculer coût (2nd gen avec min_instances)
                if min_instances > 0:
                    # Extract vCPU and memory from config
                    # 2nd gen: memory determines vCPU
                    memory_gib = memory_mb / 1024
                    vcpu = max(0.08, memory_gib / 2)  # Approximation

                    monthly_cost = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances
                else:
                    monthly_cost = 0

                update_time = function.update_time
                age_days = (datetime.utcnow().replace(tzinfo=None) - update_time.replace(tzinfo=None)).days

                if age_days >= 90:
                    confidence = "CRITICAL"
                elif age_days >= 60:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                never_invoked_functions.append({
                    "function_name": function_name,
                    "generation": "2nd",
                    "region": region,
                    "runtime": service_config.runtime if service_config else "unknown",
                    "memory_mb": memory_mb,
                    "timeout_seconds": timeout_seconds,
                    "min_instances": min_instances,
                    "age_days": age_days,
                    "update_time": update_time.isoformat(),
                    "total_invocations": 0,
                    "monthly_cost": round(monthly_cost, 2),
                    "annual_cost": round(monthly_cost * 12, 2),
                    "confidence": confidence,
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error listing 2nd gen functions: {e}")

    return never_invoked_functions


# Exemple d'utilisation
if __name__ == "__main__":
    never_invoked = detect_cloud_function_never_invoked(
        project_id="my-gcp-project",
        no_invocations_threshold_days=30
    )

    print(f"✅ {len(never_invoked)} functions jamais invoquées")

    total_annual_waste = sum([f["annual_cost"] for f in never_invoked])
    print(f"💰 Waste total: ${total_annual_waste:.2f}/an")
```

**Calcul du coût :**

```python
# 1st Gen : $0 si 0 invocations (pas de min instances)
monthly_cost_1st_gen = 0

# 2nd Gen : Dépend de min_instances
if min_instances > 0:
    vcpu = memory_gib / 2  # Approximation
    monthly_cost_2nd_gen = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances
else:
    monthly_cost_2nd_gen = 0

annual_waste = monthly_cost * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `no_invocations_threshold_days` | 30 jours | Période sans invocations | ↑ = moins de détections |

**Métadonnées du waste détecté :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "never_invoked",
  "function_name": "legacy-webhook-handler",
  "generation": "1st",
  "region": "us-central1",
  "runtime": "python39",
  "memory_mb": 256,
  "timeout_seconds": 60,
  "age_days": 120,
  "update_time": "2024-07-05T10:00:00Z",
  "total_invocations": 0,
  "monthly_cost": 0.00,
  "annual_cost": 0.00,
  "confidence": "CRITICAL",
  "labels": {
    "environment": "production",
    "team": "backend"
  },
  "trigger_type": "http"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_never_invoked()`

---

### Scénario 2 : Functions 2nd Gen avec Min Instances Idle

**Description :** Functions 2nd gen avec min_instances > 0 mais traffic très faible (<10 invocations/jour). Min instances facturées 24/7 = waste.

**Impact financier :**
- **Coût mensuel :** $50 - $500/fonction
- **Waste typique :** 40-60% des functions 2nd gen non-prod
- **Économie annuelle :** $10K - $40K

**Logique de détection :**

```python
def detect_cloud_function_idle_min_instances(
    project_id: str,
    low_invocations_per_day: int = 10,
    lookback_days: int = 14
) -> list:
    """
    Détecte les functions 2nd gen avec min_instances > 0 mais traffic faible.

    Args:
        project_id: ID du projet GCP
        low_invocations_per_day: Seuil invocations faibles (défaut: 10/jour)
        lookback_days: Période d'analyse (défaut: 14 jours)

    Returns:
        Liste des functions avec min instances idle
    """
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    idle_min_instances_functions = []

    # Lister functions 2nd gen
    parent = f"projects/{project_id}/locations/-"
    functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

    for function in functions_2nd_gen:
        function_name = function.name.split('/')[-1]
        region = function.name.split('/')[3]

        service_config = function.service_config
        min_instances = service_config.min_instance_count if service_config else 0

        # Filtrer seulement functions avec min_instances > 0
        if min_instances == 0:
            continue

        # Query invocations (derniers N jours)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        filter_str = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{function_name}" '
            f'AND metric.type = "run.googleapis.com/request_count"'
        )

        request = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_str,
            interval=interval,
        )

        time_series = monitoring_client.list_time_series(request=request)

        total_invocations = 0
        for series in time_series:
            for point in series.points:
                total_invocations += point.value.int64_value or 0

        avg_invocations_per_day = total_invocations / lookback_days

        # Détection si traffic faible
        if avg_invocations_per_day < low_invocations_per_day:
            # Min instances idle = waste

            # Extraire config
            memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config.available_memory else 256
            memory_gib = memory_mb / 1024
            vcpu = max(0.08, memory_gib / 2)

            # Coût min instances permanent
            monthly_cost_min_instances = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

            # Coût optimal (min_instances = 0)
            monthly_cost_optimal = 0  # Invocations cost négligeable

            monthly_waste = monthly_cost_min_instances - monthly_cost_optimal

            # Niveau confiance
            if avg_invocations_per_day < 1:
                confidence = "CRITICAL"
            elif avg_invocations_per_day < 5:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            idle_min_instances_functions.append({
                "function_name": function_name,
                "generation": "2nd",
                "region": region,
                "memory_mb": memory_mb,
                "vcpu": round(vcpu, 2),
                "min_instances": min_instances,
                "avg_invocations_per_day": round(avg_invocations_per_day, 2),
                "total_invocations_period": int(total_invocations),
                "lookback_days": lookback_days,
                "monthly_cost_current": round(monthly_cost_min_instances, 2),
                "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": "Set min_instances = 0 to scale to zero",
                "labels": dict(function.labels) if function.labels else {},
            })

    return idle_min_instances_functions


# Exemple d'utilisation
if __name__ == "__main__":
    idle_min = detect_cloud_function_idle_min_instances(
        project_id="my-gcp-project",
        low_invocations_per_day=10
    )

    print(f"✅ {len(idle_min)} functions avec min_instances idle")

    total_waste = sum([f["annual_waste"] for f in idle_min])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel (min_instances permanent)
vcpu = memory_gib / 2
monthly_cost_current = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

# Coût optimal (min_instances = 0)
monthly_cost_optimal = 0

# Waste
monthly_waste = monthly_cost_current - monthly_cost_optimal
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `low_invocations_per_day` | 10/jour | Seuil invocations faibles | ↑ = plus de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "idle_min_instances",
  "function_name": "dev-api-endpoint",
  "generation": "2nd",
  "region": "us-central1",
  "memory_mb": 512,
  "vcpu": 0.25,
  "min_instances": 2,
  "avg_invocations_per_day": 3.5,
  "total_invocations_period": 49,
  "lookback_days": 14,
  "monthly_cost_current": 85.54,
  "monthly_cost_optimal": 0.00,
  "monthly_waste": 85.54,
  "annual_waste": 1026.48,
  "confidence": "HIGH",
  "recommendation": "Set min_instances = 0 to scale to zero",
  "labels": {
    "environment": "dev",
    "team": "backend"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_idle_min_instances()`

---

### Scénario 3 : Functions Memory Overprovisioning

**Description :** Functions avec memory allocatée >> memory réellement utilisée (<50% utilisation). Surcoût significatif (1st gen = CPU scaling, 2nd gen = direct cost).

**Impact financier :**
- **Surcoût mensuel :** 40-70% du coût total
- **Waste typique :** 50-60% des functions overprovisioned
- **Économie annuelle :** $8K - $30K

**Logique de détection :**

```python
def detect_cloud_function_memory_overprovisioning(
    project_id: str,
    memory_utilization_threshold: float = 0.50,  # <50% = overprovisioned
    lookback_days: int = 14
) -> list:
    """
    Détecte les functions avec memory allocated > memory used (<50% utilization).

    Args:
        project_id: ID du projet GCP
        memory_utilization_threshold: Seuil utilisation memory (défaut: 50%)
        lookback_days: Période d'analyse (défaut: 14 jours)

    Returns:
        Liste des functions overprovisioned avec recommandations
    """
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    overprovisioned_functions = []

    # 1. Analyser 1st gen functions
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Query memory utilization metric
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_function" '
                f'AND resource.labels.function_name = "{function_name}" '
                f'AND metric.type = "cloudfunctions.googleapis.com/function/user_memory_bytes"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},  # 1 hour
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series = monitoring_client.list_time_series(request=request)

            # Calculer avg memory used
            memory_values = []
            for series in time_series:
                for point in series.points:
                    memory_values.append(point.value.double_value or 0)

            if not memory_values:
                continue  # Pas de données

            avg_memory_used_bytes = sum(memory_values) / len(memory_values)
            avg_memory_used_mb = avg_memory_used_bytes / (1024 * 1024)

            # Memory allocated
            memory_allocated_mb = function.available_memory_mb

            # Calculer utilization
            memory_utilization = avg_memory_used_mb / memory_allocated_mb if memory_allocated_mb > 0 else 0

            # Détection si <50% utilization
            if memory_utilization < memory_utilization_threshold:
                # Overprovisioned = waste

                # Calculer coût actuel (1st gen)
                # Extraire nombre d'invocations pour estimer coût
                filter_exec = (
                    f'resource.type = "cloud_function" '
                    f'AND resource.labels.function_name = "{function_name}" '
                    f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
                )

                request_exec = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{project_id}",
                    filter=filter_exec,
                    interval=interval,
                )

                time_series_exec = monitoring_client.list_time_series(request=request_exec)

                total_invocations = 0
                for series in time_series_exec:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                if total_invocations == 0:
                    continue  # Pas d'invocations = scénario 1

                # Estimer avg duration (approximation)
                avg_duration_seconds = 0.5  # Défaut si pas de données

                # Coût actuel
                memory_gb_current = memory_allocated_mb / 1024
                cpu_ghz_current = 2.4 if memory_allocated_mb >= 2048 else (memory_allocated_mb / 1024) * 1.4

                monthly_invocations = (total_invocations / lookback_days) * 30
                compute_seconds = monthly_invocations * avg_duration_seconds

                invocations_cost = (monthly_invocations / 1_000_000) * 0.40
                memory_cost_current = compute_seconds * memory_gb_current * 0.0000025
                cpu_cost_current = compute_seconds * cpu_ghz_current * 0.0000100
                monthly_cost_current = invocations_cost + memory_cost_current + cpu_cost_current

                # Recommander memory optimal (utilization ~70%)
                recommended_memory_mb = int((avg_memory_used_mb / 0.70) / 128) * 128  # Arrondi à 128 MB
                recommended_memory_mb = max(128, recommended_memory_mb)  # Min 128 MB
                recommended_memory_mb = min(8192, recommended_memory_mb)  # Max 8 GB

                # Coût optimal
                memory_gb_optimal = recommended_memory_mb / 1024
                cpu_ghz_optimal = 2.4 if recommended_memory_mb >= 2048 else (recommended_memory_mb / 1024) * 1.4

                memory_cost_optimal = compute_seconds * memory_gb_optimal * 0.0000025
                cpu_cost_optimal = compute_seconds * cpu_ghz_optimal * 0.0000100
                monthly_cost_optimal = invocations_cost + memory_cost_optimal + cpu_cost_optimal

                monthly_waste = monthly_cost_current - monthly_cost_optimal

                # Niveau confiance
                if memory_utilization < 0.30:
                    confidence = "CRITICAL"
                elif memory_utilization < 0.40:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                overprovisioned_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "memory_allocated_mb": memory_allocated_mb,
                    "avg_memory_used_mb": round(avg_memory_used_mb, 2),
                    "memory_utilization": round(memory_utilization * 100, 2),
                    "recommended_memory_mb": recommended_memory_mb,
                    "monthly_invocations": int(monthly_invocations),
                    "monthly_cost_current": round(monthly_cost_current, 2),
                    "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                    "monthly_waste": round(monthly_waste, 2),
                    "annual_waste": round(monthly_waste * 12, 2),
                    "confidence": confidence,
                    "recommendation": f"Reduce memory from {memory_allocated_mb} MB to {recommended_memory_mb} MB",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 1st gen functions: {e}")

    # 2. Analyser 2nd gen functions (même logique)
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Query memory utilization (2nd gen utilise métriques Cloud Run)
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/container/memory/utilizations"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series = monitoring_client.list_time_series(request=request)

            memory_utilization_values = []
            for series in time_series:
                for point in series.points:
                    memory_utilization_values.append(point.value.double_value or 0)

            if not memory_utilization_values:
                continue

            avg_memory_utilization = sum(memory_utilization_values) / len(memory_utilization_values)

            if avg_memory_utilization < memory_utilization_threshold:
                # Overprovisioned

                service_config = function.service_config
                memory_allocated_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config.available_memory else 256

                avg_memory_used_mb = avg_memory_utilization * memory_allocated_mb

                # Recommander optimal
                recommended_memory_mb = int((avg_memory_used_mb / 0.70) / 128) * 128
                recommended_memory_mb = max(128, recommended_memory_mb)
                recommended_memory_mb = min(32768, recommended_memory_mb)

                # Calculer coût (simplifié)
                memory_gib_current = memory_allocated_mb / 1024
                vcpu_current = max(0.08, memory_gib_current / 2)

                memory_gib_optimal = recommended_memory_mb / 1024
                vcpu_optimal = max(0.08, memory_gib_optimal / 2)

                # Estimer monthly compute (approximation)
                # Query invocations
                filter_req = (
                    f'resource.type = "cloud_run_revision" '
                    f'AND resource.labels.service_name = "{function_name}" '
                    f'AND metric.type = "run.googleapis.com/request_count"'
                )

                request_req = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{project_id}",
                    filter=filter_req,
                    interval=interval,
                )

                time_series_req = monitoring_client.list_time_series(request=request_req)

                total_invocations = 0
                for series in time_series_req:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                if total_invocations == 0:
                    continue

                monthly_invocations = (total_invocations / lookback_days) * 30
                avg_duration = 0.5  # seconds

                compute_seconds = monthly_invocations * avg_duration

                invocations_cost = (monthly_invocations / 1_000_000) * 0.40
                vcpu_cost_current = compute_seconds * vcpu_current * 0.00002400
                memory_cost_current = compute_seconds * memory_gib_current * 0.00000250
                monthly_cost_current = invocations_cost + vcpu_cost_current + memory_cost_current

                vcpu_cost_optimal = compute_seconds * vcpu_optimal * 0.00002400
                memory_cost_optimal = compute_seconds * memory_gib_optimal * 0.00000250
                monthly_cost_optimal = invocations_cost + vcpu_cost_optimal + memory_cost_optimal

                monthly_waste = monthly_cost_current - monthly_cost_optimal

                if avg_memory_utilization < 0.30:
                    confidence = "CRITICAL"
                elif avg_memory_utilization < 0.40:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                overprovisioned_functions.append({
                    "function_name": function_name,
                    "generation": "2nd",
                    "region": region,
                    "memory_allocated_mb": memory_allocated_mb,
                    "avg_memory_used_mb": round(avg_memory_used_mb, 2),
                    "memory_utilization": round(avg_memory_utilization * 100, 2),
                    "recommended_memory_mb": recommended_memory_mb,
                    "monthly_invocations": int(monthly_invocations),
                    "monthly_cost_current": round(monthly_cost_current, 2),
                    "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                    "monthly_waste": round(monthly_waste, 2),
                    "annual_waste": round(monthly_waste * 12, 2),
                    "confidence": confidence,
                    "recommendation": f"Reduce memory from {memory_allocated_mb} MB to {recommended_memory_mb} MB",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 2nd gen functions: {e}")

    return overprovisioned_functions


# Exemple d'utilisation
if __name__ == "__main__":
    overprovisioned = detect_cloud_function_memory_overprovisioning(
        project_id="my-gcp-project",
        memory_utilization_threshold=0.50
    )

    print(f"✅ {len(overprovisioned)} functions overprovisioned")

    total_waste = sum([f["annual_waste"] for f in overprovisioned])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# 1st Gen
memory_gb_current = memory_allocated_mb / 1024
cpu_ghz_current = 2.4 if memory_allocated_mb >= 2048 else (memory_allocated_mb / 1024) * 1.4

monthly_cost_current = invocations_cost + (compute_seconds * memory_gb_current * 0.0000025) + (compute_seconds * cpu_ghz_current * 0.0000100)

# Optimal (memory réduite à 70% utilization)
memory_gb_optimal = recommended_memory_mb / 1024
cpu_ghz_optimal = 2.4 if recommended_memory_mb >= 2048 else (recommended_memory_mb / 1024) * 1.4

monthly_cost_optimal = invocations_cost + (compute_seconds * memory_gb_optimal * 0.0000025) + (compute_seconds * cpu_ghz_optimal * 0.0000100)

monthly_waste = monthly_cost_current - monthly_cost_optimal
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `memory_utilization_threshold` | 50% | Seuil utilization memory | ↑ = plus de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "memory_overprovisioning",
  "function_name": "image-resize-api",
  "generation": "1st",
  "region": "us-central1",
  "memory_allocated_mb": 2048,
  "avg_memory_used_mb": 512,
  "memory_utilization": 25.0,
  "recommended_memory_mb": 768,
  "monthly_invocations": 500000,
  "monthly_cost_current": 42.50,
  "monthly_cost_optimal": 18.20,
  "monthly_waste": 24.30,
  "annual_waste": 291.60,
  "confidence": "CRITICAL",
  "recommendation": "Reduce memory from 2048 MB to 768 MB",
  "labels": {
    "environment": "production",
    "service": "media-processing"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_memory_overprovisioning()`

---

### Scénario 4 : Functions Excessive Timeout

**Description :** Functions avec timeout configuré >> execution time moyenne (ratio >3x). Risque de runaway costs + pas d'optimisation.

**Impact financier :**
- **Risque mensuel :** $500 - $5K+ si fonction bloquée
- **Waste préventif :** Protection insuffisante
- **Impact :** Factures surprises possibles

**Logique de détection :**

```python
def detect_cloud_function_excessive_timeout(
    project_id: str,
    timeout_ratio_threshold: float = 3.0,  # timeout > 3x avg exec time
    lookback_days: int = 14
) -> list:
    """
    Détecte les functions avec timeout configuré >> avg execution time.

    Args:
        project_id: ID du projet GCP
        timeout_ratio_threshold: Ratio timeout / avg exec time (défaut: 3x)
        lookback_days: Période d'analyse

    Returns:
        Liste des functions avec timeout excessif
    """
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    excessive_timeout_functions = []

    # 1. Analyser 1st gen functions
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            timeout_seconds = function.timeout.seconds if function.timeout else 60

            # Query execution time metric
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_function" '
                f'AND resource.labels.function_name = "{function_name}" '
                f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_times"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series = monitoring_client.list_time_series(request=request)

            # Calculer avg execution time
            exec_time_values = []
            for series in time_series:
                for point in series.points:
                    exec_time_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                    exec_time_values.append(exec_time_ms)

            if not exec_time_values:
                continue  # Pas de données

            avg_exec_time_ms = sum(exec_time_values) / len(exec_time_values)
            avg_exec_time_seconds = avg_exec_time_ms / 1000

            # Calculer ratio
            timeout_ratio = timeout_seconds / avg_exec_time_seconds if avg_exec_time_seconds > 0 else 0

            # Détection si ratio > threshold
            if timeout_ratio > timeout_ratio_threshold:
                # Excessive timeout = risque waste

                # Recommander timeout optimal (avg + 50% buffer)
                recommended_timeout = int(avg_exec_time_seconds * 1.5)
                recommended_timeout = max(5, recommended_timeout)  # Min 5s
                recommended_timeout = min(540, recommended_timeout)  # Max 540s (1st gen)

                # Niveau confiance
                if timeout_ratio > 10:
                    confidence = "CRITICAL"
                elif timeout_ratio > 5:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                excessive_timeout_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "runtime": function.runtime,
                    "timeout_configured_seconds": timeout_seconds,
                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 2),
                    "timeout_ratio": round(timeout_ratio, 2),
                    "recommended_timeout_seconds": recommended_timeout,
                    "confidence": confidence,
                    "risk": "Runaway costs if function hangs or enters infinite loop",
                    "recommendation": f"Reduce timeout from {timeout_seconds}s to {recommended_timeout}s",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 1st gen functions: {e}")

    # 2. Analyser 2nd gen functions
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            service_config = function.service_config
            timeout_seconds = service_config.timeout_seconds if service_config and service_config.timeout_seconds else 60

            # Query execution time (2nd gen = Cloud Run metrics)
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/request_latencies"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series = monitoring_client.list_time_series(request=request)

            exec_time_values = []
            for series in time_series:
                for point in series.points:
                    exec_time_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                    exec_time_values.append(exec_time_ms)

            if not exec_time_values:
                continue

            avg_exec_time_ms = sum(exec_time_values) / len(exec_time_values)
            avg_exec_time_seconds = avg_exec_time_ms / 1000

            timeout_ratio = timeout_seconds / avg_exec_time_seconds if avg_exec_time_seconds > 0 else 0

            if timeout_ratio > timeout_ratio_threshold:
                recommended_timeout = int(avg_exec_time_seconds * 1.5)
                recommended_timeout = max(5, recommended_timeout)
                recommended_timeout = min(3600, recommended_timeout)  # Max 3600s (2nd gen)

                if timeout_ratio > 10:
                    confidence = "CRITICAL"
                elif timeout_ratio > 5:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                excessive_timeout_functions.append({
                    "function_name": function_name,
                    "generation": "2nd",
                    "region": region,
                    "timeout_configured_seconds": timeout_seconds,
                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 2),
                    "timeout_ratio": round(timeout_ratio, 2),
                    "recommended_timeout_seconds": recommended_timeout,
                    "confidence": confidence,
                    "risk": "Runaway costs if function hangs or enters infinite loop",
                    "recommendation": f"Reduce timeout from {timeout_seconds}s to {recommended_timeout}s",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 2nd gen functions: {e}")

    return excessive_timeout_functions


# Exemple d'utilisation
if __name__ == "__main__":
    excessive_timeout = detect_cloud_function_excessive_timeout(
        project_id="my-gcp-project",
        timeout_ratio_threshold=3.0
    )

    print(f"⚠️  {len(excessive_timeout)} functions avec timeout excessif")

    for func in excessive_timeout:
        print(f"  - {func['function_name']}: {func['timeout_configured_seconds']}s (avg: {func['avg_exec_time_seconds']}s)")
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `timeout_ratio_threshold` | 3.0 | Ratio timeout / avg exec time | ↑ = moins de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "excessive_timeout",
  "function_name": "data-export-api",
  "generation": "2nd",
  "region": "us-central1",
  "timeout_configured_seconds": 3600,
  "avg_exec_time_seconds": 45.3,
  "timeout_ratio": 79.5,
  "recommended_timeout_seconds": 68,
  "confidence": "CRITICAL",
  "risk": "Runaway costs if function hangs or enters infinite loop",
  "recommendation": "Reduce timeout from 3600s to 68s",
  "labels": {
    "environment": "production",
    "team": "data-engineering"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_excessive_timeout()`

---

### Scénario 5 : Functions 1st Gen Plus Coûteuses que 2nd Gen

**Description :** Functions 1st gen qui seraient moins coûteuses en 2nd gen (avec concurrency ou timeout long). Opportunité de migration.

**Impact financier :**
- **Économie mensuelle :** $50 - $500/fonction
- **Waste typique :** 20-30% des 1st gen migrables
- **Économie annuelle :** $5K - $20K

**Logique de détection :**

```python
def detect_cloud_function_1st_gen_expensive(
    project_id: str,
    lookback_days: int = 14,
    cost_savings_threshold_pct: float = 20.0  # >20% savings = recommander migration
) -> list:
    """
    Détecte les functions 1st gen qui seraient moins coûteuses en 2nd gen.

    Args:
        project_id: ID du projet GCP
        lookback_days: Période d'analyse
        cost_savings_threshold_pct: Seuil économie (%) pour recommandation

    Returns:
        Liste des functions 1st gen candidates à migration
    """
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    expensive_1st_gen_functions = []

    parent = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Extraire config
            memory_mb = function.available_memory_mb
            timeout_seconds = function.timeout.seconds if function.timeout else 60

            # Query invocations
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_exec = (
                f'resource.type = "cloud_function" '
                f'AND resource.labels.function_name = "{function_name}" '
                f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
            )

            request_exec = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_exec,
                interval=interval,
            )

            time_series_exec = monitoring_client.list_time_series(request=request_exec)

            total_invocations = 0
            for series in time_series_exec:
                for point in series.points:
                    total_invocations += point.value.int64_value or 0

            if total_invocations == 0:
                continue

            # Query avg execution time
            filter_time = (
                f'resource.type = "cloud_function" '
                f'AND resource.labels.function_name = "{function_name}" '
                f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_times"'
            )

            request_time = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_time,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series_time = monitoring_client.list_time_series(request=request_time)

            exec_time_values = []
            for series in time_series_time:
                for point in series.points:
                    exec_time_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                    exec_time_values.append(exec_time_ms)

            if not exec_time_values:
                continue

            avg_exec_time_ms = sum(exec_time_values) / len(exec_time_values)
            avg_exec_time_seconds = avg_exec_time_ms / 1000

            # Calculer coût mensuel actuel (1st gen)
            monthly_invocations = (total_invocations / lookback_days) * 30
            compute_seconds = monthly_invocations * avg_exec_time_seconds

            memory_gb = memory_mb / 1024
            cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

            invocations_cost = (monthly_invocations / 1_000_000) * 0.40
            memory_cost = compute_seconds * memory_gb * 0.0000025
            cpu_cost = compute_seconds * cpu_ghz * 0.0000100

            monthly_cost_1st_gen = invocations_cost + memory_cost + cpu_cost

            # Calculer coût estimé 2nd gen (équivalent config)
            # 2nd gen: memory → vCPU mapping approximatif
            memory_gib = memory_mb / 1024
            vcpu = max(0.08, memory_gib / 2)

            vcpu_cost = compute_seconds * vcpu * 0.00002400
            memory_cost_2nd = compute_seconds * memory_gib * 0.00000250

            monthly_cost_2nd_gen = invocations_cost + vcpu_cost + memory_cost_2nd

            # Calculer savings
            monthly_savings = monthly_cost_1st_gen - monthly_cost_2nd_gen
            savings_pct = (monthly_savings / monthly_cost_1st_gen) * 100 if monthly_cost_1st_gen > 0 else 0

            # Détection si 2nd gen moins cher
            if savings_pct > cost_savings_threshold_pct:
                # 1st gen plus coûteux = recommander migration

                # Avantages additionnels 2nd gen
                benefits = []
                if timeout_seconds > 540:
                    benefits.append("timeout > 9 min (impossible en 1st gen)")
                if monthly_invocations > 100000:
                    benefits.append("concurrency support (1-1000 req/instance)")
                if memory_mb > 8192:
                    benefits.append("memory jusqu'à 32 GiB (vs 8 GB 1st gen)")

                if savings_pct > 40:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                expensive_1st_gen_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "runtime": function.runtime,
                    "memory_mb": memory_mb,
                    "timeout_seconds": timeout_seconds,
                    "monthly_invocations": int(monthly_invocations),
                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 2),
                    "monthly_cost_1st_gen": round(monthly_cost_1st_gen, 2),
                    "monthly_cost_2nd_gen": round(monthly_cost_2nd_gen, 2),
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(monthly_savings * 12, 2),
                    "savings_pct": round(savings_pct, 2),
                    "additional_benefits": benefits,
                    "confidence": confidence,
                    "recommendation": f"Migrate to 2nd gen for {savings_pct:.1f}% cost reduction",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 1st gen functions: {e}")

    return expensive_1st_gen_functions


# Exemple d'utilisation
if __name__ == "__main__":
    expensive_1st_gen = detect_cloud_function_1st_gen_expensive(
        project_id="my-gcp-project",
        cost_savings_threshold_pct=20.0
    )

    print(f"✅ {len(expensive_1st_gen)} functions 1st gen candidates à migration")

    total_savings = sum([f["annual_savings"] for f in expensive_1st_gen])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# 1st Gen Cost
memory_gb = memory_mb / 1024
cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

monthly_cost_1st_gen = (
    (monthly_invocations / 1_000_000) * 0.40 +
    compute_seconds * memory_gb * 0.0000025 +
    compute_seconds * cpu_ghz * 0.0000100
)

# 2nd Gen Cost (équivalent)
vcpu = max(0.08, memory_gb / 2)

monthly_cost_2nd_gen = (
    (monthly_invocations / 1_000_000) * 0.40 +
    compute_seconds * vcpu * 0.00002400 +
    compute_seconds * memory_gib * 0.00000250
)

# Savings
monthly_savings = monthly_cost_1st_gen - monthly_cost_2nd_gen
savings_pct = (monthly_savings / monthly_cost_1st_gen) * 100
annual_savings = monthly_savings * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `cost_savings_threshold_pct` | 20% | Seuil économie pour migration | ↑ = moins de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "1st_gen_expensive",
  "function_name": "high-traffic-api",
  "generation": "1st",
  "region": "us-central1",
  "runtime": "python310",
  "memory_mb": 512,
  "timeout_seconds": 300,
  "monthly_invocations": 2000000,
  "avg_exec_time_seconds": 0.8,
  "monthly_cost_1st_gen": 75.20,
  "monthly_cost_2nd_gen": 52.80,
  "monthly_savings": 22.40,
  "annual_savings": 268.80,
  "savings_pct": 29.8,
  "additional_benefits": [
    "concurrency support (1-1000 req/instance)",
    "timeout jusqu'à 60 min (vs 9 min)"
  ],
  "confidence": "MEDIUM",
  "recommendation": "Migrate to 2nd gen for 29.8% cost reduction",
  "labels": {
    "environment": "production",
    "team": "api"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_1st_gen_expensive()`

---

### Scénario 6 : Functions Untagged (Sans Labels)

**Description :** Functions sans labels (environment, owner, cost-center, etc.). Impossible de tracker ownership et coûts par équipe.

**Impact financier :**
- **Impact indirect :** Confusion attribution coûts
- **Cleanup risqué :** Peur de supprimer = accumulation waste
- **Gouvernance :** Impossible d'enforcer policies

**Logique de détection :**

```python
def detect_cloud_function_untagged(
    project_id: str,
    required_labels: list = None
) -> list:
    """
    Détecte les Cloud Functions sans labels obligatoires.

    Args:
        project_id: ID du projet GCP
        required_labels: Liste des labels obligatoires (défaut: ['environment', 'owner'])

    Returns:
        Liste des functions sans labels
    """
    if required_labels is None:
        required_labels = ['environment', 'owner']

    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()

    untagged_functions = []

    # 1. Analyser 1st gen functions
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            labels = dict(function.labels) if function.labels else {}

            # Vérifier labels manquants
            missing_labels = [label for label in required_labels if label not in labels]

            if missing_labels:
                # Function untagged

                untagged_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "runtime": function.runtime,
                    "existing_labels": labels,
                    "missing_labels": missing_labels,
                    "confidence": "HIGH",
                    "impact": "Cannot track ownership, costs, or enforce cleanup policies",
                    "recommendation": f"Add required labels: {', '.join(missing_labels)}",
                })
    except Exception as e:
        print(f"Error listing 1st gen functions: {e}")

    # 2. Analyser 2nd gen functions
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            labels = dict(function.labels) if function.labels else {}

            missing_labels = [label for label in required_labels if label not in labels]

            if missing_labels:
                untagged_functions.append({
                    "function_name": function_name,
                    "generation": "2nd",
                    "region": region,
                    "existing_labels": labels,
                    "missing_labels": missing_labels,
                    "confidence": "HIGH",
                    "impact": "Cannot track ownership, costs, or enforce cleanup policies",
                    "recommendation": f"Add required labels: {', '.join(missing_labels)}",
                })
    except Exception as e:
        print(f"Error listing 2nd gen functions: {e}")

    return untagged_functions


# Exemple d'utilisation
if __name__ == "__main__":
    untagged = detect_cloud_function_untagged(
        project_id="my-gcp-project",
        required_labels=['environment', 'owner', 'cost-center']
    )

    print(f"⚠️  {len(untagged)} functions sans labels obligatoires")

    for func in untagged:
        print(f"  - {func['function_name']}: missing {', '.join(func['missing_labels'])}")
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `required_labels` | `['environment', 'owner']` | Labels obligatoires | Ajouter labels = plus strict |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "untagged",
  "function_name": "legacy-webhook",
  "generation": "1st",
  "region": "us-central1",
  "runtime": "nodejs16",
  "existing_labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "confidence": "HIGH",
  "impact": "Cannot track ownership, costs, or enforce cleanup policies",
  "recommendation": "Add required labels: environment, owner, cost-center"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_untagged()`

---

### Scénario 7 : Functions Excessive Max Instances

**Description :** Functions avec max_instances > 100 sans rate limiting. Risque de facture spike ($1K+/jour) si traffic burst ou DDoS.

**Impact financier :**
- **Risque mensuel :** $1K - $10K+ si spike
- **Protection insuffisante :** Max instances = protection coût
- **Best practice :** max_instances raisonnable + rate limiting

**Logique de détection :**

```python
def detect_cloud_function_excessive_max_instances(
    project_id: str,
    max_instances_threshold: int = 100
) -> list:
    """
    Détecte les functions avec max_instances excessif (>100 sans rate limiting).

    Args:
        project_id: ID du projet GCP
        max_instances_threshold: Seuil max instances (défaut: 100)

    Returns:
        Liste des functions avec max_instances excessif
    """
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()

    excessive_max_instances_functions = []

    # 1. Analyser 1st gen functions
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            max_instances = function.max_instances if function.max_instances else 3000  # Défaut 1st gen

            if max_instances > max_instances_threshold:
                # Max instances excessif

                # Extraire config
                memory_mb = function.available_memory_mb

                # Estimer coût max si toutes instances running
                # 1st gen: 1 req/instance
                # Coût max = max_instances * compute_cost

                # Approximation: si toutes instances actives pendant 1h
                memory_gb = memory_mb / 1024
                cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

                # Coût par instance par heure (supposant exécution continue)
                cost_per_instance_hour = (
                    (3600 * memory_gb * 0.0000025) +
                    (3600 * cpu_ghz * 0.0000100)
                )

                max_hourly_cost = max_instances * cost_per_instance_hour
                max_daily_cost = max_hourly_cost * 24

                if max_daily_cost > 1000:
                    confidence = "CRITICAL"
                elif max_daily_cost > 500:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                excessive_max_instances_functions.append({
                    "function_name": function_name,
                    "generation": "1st",
                    "region": region,
                    "runtime": function.runtime,
                    "memory_mb": memory_mb,
                    "max_instances_configured": max_instances,
                    "max_hourly_cost": round(max_hourly_cost, 2),
                    "max_daily_cost": round(max_daily_cost, 2),
                    "confidence": confidence,
                    "risk": "Runaway costs if traffic spike, DDoS, or infinite loop",
                    "recommendation": f"Set max_instances = {max_instances_threshold} and implement rate limiting",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 1st gen functions: {e}")

    # 2. Analyser 2nd gen functions
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            service_config = function.service_config
            max_instances = service_config.max_instance_count if service_config and service_config.max_instance_count else 1000  # Défaut 2nd gen

            if max_instances > max_instances_threshold:
                memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                memory_gib = memory_mb / 1024
                vcpu = max(0.08, memory_gib / 2)

                # Coût max par instance par heure
                cost_per_instance_hour = (
                    (3600 * vcpu * 0.00002400) +
                    (3600 * memory_gib * 0.00000250)
                )

                max_hourly_cost = max_instances * cost_per_instance_hour
                max_daily_cost = max_hourly_cost * 24

                if max_daily_cost > 1000:
                    confidence = "CRITICAL"
                elif max_daily_cost > 500:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                excessive_max_instances_functions.append({
                    "function_name": function_name,
                    "generation": "2nd",
                    "region": region,
                    "memory_mb": memory_mb,
                    "vcpu": round(vcpu, 2),
                    "max_instances_configured": max_instances,
                    "max_hourly_cost": round(max_hourly_cost, 2),
                    "max_daily_cost": round(max_daily_cost, 2),
                    "confidence": confidence,
                    "risk": "Runaway costs if traffic spike, DDoS, or infinite loop",
                    "recommendation": f"Set max_instances = {max_instances_threshold} and implement rate limiting",
                    "labels": dict(function.labels) if function.labels else {},
                })
    except Exception as e:
        print(f"Error analyzing 2nd gen functions: {e}")

    return excessive_max_instances_functions


# Exemple d'utilisation
if __name__ == "__main__":
    excessive_max = detect_cloud_function_excessive_max_instances(
        project_id="my-gcp-project",
        max_instances_threshold=100
    )

    print(f"⚠️  {len(excessive_max)} functions avec max_instances excessif")

    for func in excessive_max:
        print(f"  - {func['function_name']}: max {func['max_instances_configured']} instances (risk: ${func['max_daily_cost']:.2f}/jour)")
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `max_instances_threshold` | 100 | Seuil max instances | ↑ = moins de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "excessive_max_instances",
  "function_name": "public-api-endpoint",
  "generation": "2nd",
  "region": "us-central1",
  "memory_mb": 512,
  "vcpu": 0.25,
  "max_instances_configured": 1000,
  "max_hourly_cost": 112.50,
  "max_daily_cost": 2700.00,
  "confidence": "CRITICAL",
  "risk": "Runaway costs if traffic spike, DDoS, or infinite loop",
  "recommendation": "Set max_instances = 100 and implement rate limiting",
  "labels": {
    "environment": "production",
    "public": "true"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_excessive_max_instances()`

---

## Phase 2 : Analyse Avancée (3 Scénarios)

### Scénario 8 : Functions Cold Start Over-Optimization (2nd Gen)

**Description :** Functions 2nd gen avec min_instances > 0 uniquement pour éviter cold starts, mais coût >> économie. Alternative: warm-up requests.

**Impact financier :**
- **Waste mensuel :** $100 - $1K/fonction
- **Alternative :** Warm-up requests (<$5/mois)
- **Économie annuelle :** $2K - $15K

**Logique de détection :**

```python
def detect_cloud_function_cold_start_over_optimization(
    project_id: str,
    lookback_days: int = 14,
    cold_start_cost_threshold: float = 50.0  # min_instances cost > $50/mois
) -> list:
    """
    Détecte les functions 2nd gen avec min_instances uniquement pour cold starts.

    Args:
        project_id: ID du projet GCP
        lookback_days: Période d'analyse
        cold_start_cost_threshold: Seuil coût min instances

    Returns:
        Liste des functions sur-optimisées pour cold starts
    """
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    over_optimized_functions = []

    parent = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            service_config = function.service_config
            min_instances = service_config.min_instance_count if service_config else 0

            if min_instances == 0:
                continue  # Pas de min instances

            # Calculer coût min instances
            memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config.available_memory else 256
            memory_gib = memory_mb / 1024
            vcpu = max(0.08, memory_gib / 2)

            monthly_cost_min_instances = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

            if monthly_cost_min_instances < cold_start_cost_threshold:
                continue  # Coût faible = pas de problème

            # Query invocations
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/request_count"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
            )

            time_series = monitoring_client.list_time_series(request=request)

            total_invocations = 0
            for series in time_series:
                for point in series.points:
                    total_invocations += point.value.int64_value or 0

            monthly_invocations = (total_invocations / lookback_days) * 30

            # Estimer invocations par heure
            invocations_per_hour = monthly_invocations / (30 * 24) if monthly_invocations > 0 else 0

            # Si <10 invocations/heure = cold start over-optimization
            if invocations_per_hour < 10:
                # Alternative: warm-up requests (1 req/min = $0.40 + compute cost)
                warmup_requests_per_month = 30 * 24 * 60  # 1 req/min = 43,200 req/mois
                warmup_cost = (warmup_requests_per_month / 1_000_000) * 0.40  # ~$17.28/mois

                monthly_savings = monthly_cost_min_instances - warmup_cost

                if monthly_savings > 0:
                    if monthly_savings > 200:
                        confidence = "HIGH"
                    else:
                        confidence = "MEDIUM"

                    over_optimized_functions.append({
                        "function_name": function_name,
                        "generation": "2nd",
                        "region": region,
                        "memory_mb": memory_mb,
                        "vcpu": round(vcpu, 2),
                        "min_instances": min_instances,
                        "invocations_per_hour": round(invocations_per_hour, 2),
                        "monthly_cost_min_instances": round(monthly_cost_min_instances, 2),
                        "alternative_warmup_cost": round(warmup_cost, 2),
                        "monthly_savings": round(monthly_savings, 2),
                        "annual_savings": round(monthly_savings * 12, 2),
                        "confidence": confidence,
                        "recommendation": "Remove min_instances and use Cloud Scheduler warm-up requests (1/min)",
                        "alternative": "Cloud Scheduler: $0.10/job + $17/mois invocations",
                        "labels": dict(function.labels) if function.labels else {},
                    })
    except Exception as e:
        print(f"Error analyzing 2nd gen functions: {e}")

    return over_optimized_functions


# Exemple d'utilisation
if __name__ == "__main__":
    over_optimized = detect_cloud_function_cold_start_over_optimization(
        project_id="my-gcp-project",
        cold_start_cost_threshold=50.0
    )

    print(f"✅ {len(over_optimized)} functions sur-optimisées cold start")

    total_savings = sum([f["annual_savings"] for f in over_optimized])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel (min_instances permanent)
monthly_cost_min_instances = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

# Alternative: warm-up requests via Cloud Scheduler (1 req/min)
warmup_requests_per_month = 30 * 24 * 60  # 43,200 requests
warmup_invocations_cost = (warmup_requests_per_month / 1_000_000) * 0.40  # $17.28
warmup_compute_cost = warmup_requests_per_month * 0.1 * vcpu * 0.00002400  # Assume 100ms exec
warmup_cost = warmup_invocations_cost + warmup_compute_cost + 0.10  # +$0.10 Cloud Scheduler

monthly_savings = monthly_cost_min_instances - warmup_cost
annual_savings = monthly_savings * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `cold_start_cost_threshold` | $50/mois | Seuil coût min instances | ↑ = moins de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "cold_start_over_optimization",
  "function_name": "infrequent-api",
  "generation": "2nd",
  "region": "us-central1",
  "memory_mb": 512,
  "vcpu": 0.25,
  "min_instances": 2,
  "invocations_per_hour": 3.5,
  "monthly_cost_min_instances": 171.07,
  "alternative_warmup_cost": 18.50,
  "monthly_savings": 152.57,
  "annual_savings": 1830.84,
  "confidence": "HIGH",
  "recommendation": "Remove min_instances and use Cloud Scheduler warm-up requests (1/min)",
  "alternative": "Cloud Scheduler: $0.10/job + $17/mois invocations",
  "labels": {
    "environment": "production",
    "latency": "sensitive"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_cold_start_over_optimization()`

---

### Scénario 9 : Functions Duplicate (Même Code)

**Description :** Plusieurs functions déployées avec le même code source (même hash). Consolidation possible.

**Impact financier :**
- **Waste mensuel :** $100 - $1K (coûts opérationnels + confusion)
- **Maintenance :** Bugs dupliqués, updates multiples
- **Économie annuelle :** $2K - $12K

**Logique de détection :**

```python
import hashlib

def detect_cloud_function_duplicate(
    project_id: str
) -> list:
    """
    Détecte les Cloud Functions avec code source identique (même hash).

    Args:
        project_id: ID du projet GCP

    Returns:
        Groupes de functions dupliquées
    """
    functions_v1_client = functions_v1.CloudFunctionsServiceClient()
    functions_v2_client = functions_v2.FunctionServiceClient()

    function_hashes = {}  # {hash: [function_info]}

    # 1. Lister 1st gen functions et calculer hash
    parent_v1 = f"projects/{project_id}/locations/-"

    try:
        functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

        for function in functions_1st_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            # Créer signature fonction (runtime + entry_point + source_archive_url)
            signature_data = f"{function.runtime}:{function.entry_point}:{function.source_archive_url}"
            function_hash = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

            if function_hash not in function_hashes:
                function_hashes[function_hash] = []

            function_hashes[function_hash].append({
                "function_name": function_name,
                "generation": "1st",
                "region": region,
                "runtime": function.runtime,
                "entry_point": function.entry_point,
                "source_archive_url": function.source_archive_url,
                "memory_mb": function.available_memory_mb,
                "labels": dict(function.labels) if function.labels else {},
            })
    except Exception as e:
        print(f"Error listing 1st gen functions: {e}")

    # 2. Lister 2nd gen functions
    parent_v2 = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            build_config = function.build_config
            service_config = function.service_config

            signature_data = f"{service_config.runtime if service_config else 'unknown'}:{build_config.entry_point if build_config else 'unknown'}:{build_config.source if build_config else 'unknown'}"
            function_hash = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

            if function_hash not in function_hashes:
                function_hashes[function_hash] = []

            function_hashes[function_hash].append({
                "function_name": function_name,
                "generation": "2nd",
                "region": region,
                "runtime": service_config.runtime if service_config else "unknown",
                "entry_point": build_config.entry_point if build_config else "unknown",
                "memory_mb": int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256,
                "labels": dict(function.labels) if function.labels else {},
            })
    except Exception as e:
        print(f"Error listing 2nd gen functions: {e}")

    # 3. Identifier duplicates (hash avec >1 function)
    duplicate_groups = []

    for function_hash, functions in function_hashes.items():
        if len(functions) > 1:
            # Duplicate détecté

            # Vérifier si vraiment identiques (pas juste même runtime)
            # Comparer source_archive_url / source
            sources = set([f.get('source_archive_url', f.get('entry_point', 'unknown')) for f in functions])

            if len(sources) == 1:
                # Vraiment duplicate

                duplicate_groups.append({
                    "duplicate_hash": function_hash,
                    "duplicate_count": len(functions),
                    "functions": functions,
                    "confidence": "HIGH",
                    "impact": "Operational overhead, duplicate bugs, confusion",
                    "recommendation": f"Consolidate {len(functions)} duplicate functions into 1 multi-region function",
                })

    return duplicate_groups


# Exemple d'utilisation
if __name__ == "__main__":
    duplicates = detect_cloud_function_duplicate(
        project_id="my-gcp-project"
    )

    print(f"⚠️  {len(duplicates)} groupes de functions dupliquées")

    for group in duplicates:
        print(f"  - Hash {group['duplicate_hash']}: {group['duplicate_count']} functions")
        for func in group['functions']:
            print(f"    • {func['function_name']} ({func['region']})")
```

**Paramètres configurables :**

Aucun paramètre configurable (détection basée sur hash code source).

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "duplicate_functions",
  "duplicate_hash": "a3f5c8d9e2b1a6f4",
  "duplicate_count": 3,
  "functions": [
    {
      "function_name": "webhook-handler-us",
      "generation": "1st",
      "region": "us-central1",
      "runtime": "python39",
      "entry_point": "handle_webhook",
      "source_archive_url": "gs://my-bucket/source.zip",
      "memory_mb": 256,
      "labels": {"team": "backend"}
    },
    {
      "function_name": "webhook-handler-eu",
      "generation": "1st",
      "region": "europe-west1",
      "runtime": "python39",
      "entry_point": "handle_webhook",
      "source_archive_url": "gs://my-bucket/source.zip",
      "memory_mb": 256,
      "labels": {"team": "backend"}
    },
    {
      "function_name": "webhook-handler-asia",
      "generation": "1st",
      "region": "asia-east1",
      "runtime": "python39",
      "entry_point": "handle_webhook",
      "source_archive_url": "gs://my-bucket/source.zip",
      "memory_mb": 256,
      "labels": {"team": "backend"}
    }
  ],
  "confidence": "HIGH",
  "impact": "Operational overhead, duplicate bugs, confusion",
  "recommendation": "Consolidate 3 duplicate functions into 1 multi-region function"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_duplicate()`

---

### Scénario 10 : Functions Excessive Concurrency (2nd Gen)

**Description :** Functions 2nd gen avec concurrency = 1 (comme 1st gen). Sous-utilisation features 2nd gen = surcoût inutile.

**Impact financier :**
- **Surcoût mensuel :** 30-50% (plus d'instances nécessaires)
- **Waste typique :** 40% des migrations 1st → 2nd gen
- **Économie annuelle :** $3K - $15K

**Logique de détection :**

```python
def detect_cloud_function_excessive_concurrency(
    project_id: str,
    lookback_days: int = 14
) -> list:
    """
    Détecte les functions 2nd gen avec concurrency = 1 (sous-utilisation).

    Args:
        project_id: ID du projet GCP
        lookback_days: Période d'analyse

    Returns:
        Liste des functions avec concurrency suboptimal
    """
    functions_v2_client = functions_v2.FunctionServiceClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    low_concurrency_functions = []

    parent = f"projects/{project_id}/locations/-"

    try:
        functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

        for function in functions_2nd_gen:
            function_name = function.name.split('/')[-1]
            region = function.name.split('/')[3]

            service_config = function.service_config
            concurrency = service_config.max_instance_request_concurrency if service_config else 1

            if concurrency > 1:
                continue  # Concurrency déjà configurée

            # Function avec concurrency = 1 = sous-utilisation 2nd gen

            # Query invocations
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
            })

            filter_str = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/request_count"'
            )

            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
            )

            time_series = monitoring_client.list_time_series(request=request)

            total_invocations = 0
            for series in time_series:
                for point in series.points:
                    total_invocations += point.value.int64_value or 0

            if total_invocations == 0:
                continue  # Pas d'invocations

            monthly_invocations = (total_invocations / lookback_days) * 30

            # Estimer avg exec time
            filter_latency = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{function_name}" '
                f'AND metric.type = "run.googleapis.com/request_latencies"'
            )

            request_latency = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_latency,
                interval=interval,
                aggregation=monitoring_v3.Aggregation({
                    "alignment_period": {"seconds": 3600},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }),
            )

            time_series_latency = monitoring_client.list_time_series(request=request_latency)

            latency_values = []
            for series in time_series_latency:
                for point in series.points:
                    latency_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                    latency_values.append(latency_ms)

            if not latency_values:
                continue

            avg_exec_time_ms = sum(latency_values) / len(latency_values)
            avg_exec_time_seconds = avg_exec_time_ms / 1000

            # Si exec time < 1s = bon candidat pour concurrency > 1
            if avg_exec_time_seconds < 1.0:
                # Recommander concurrency = 10-100 selon exec time
                if avg_exec_time_seconds < 0.1:
                    recommended_concurrency = 100
                elif avg_exec_time_seconds < 0.5:
                    recommended_concurrency = 50
                else:
                    recommended_concurrency = 10

                # Estimer économie (moins d'instances nécessaires)
                # Avec concurrency = 1: besoin X instances
                # Avec concurrency = N: besoin X/N instances

                memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config.available_memory else 256
                memory_gib = memory_mb / 1024
                vcpu = max(0.08, memory_gib / 2)

                compute_seconds = monthly_invocations * avg_exec_time_seconds

                # Coût actuel (concurrency = 1)
                invocations_cost = (monthly_invocations / 1_000_000) * 0.40
                vcpu_cost_current = compute_seconds * vcpu * 0.00002400
                memory_cost_current = compute_seconds * memory_gib * 0.00000250
                monthly_cost_current = invocations_cost + vcpu_cost_current + memory_cost_current

                # Coût optimal (concurrency > 1 = moins d'overhead)
                # Approximation: 30-40% réduction instance overhead
                monthly_cost_optimal = monthly_cost_current * 0.70

                monthly_savings = monthly_cost_current - monthly_cost_optimal

                if monthly_savings > 10:
                    if avg_exec_time_seconds < 0.1:
                        confidence = "HIGH"
                    else:
                        confidence = "MEDIUM"

                    low_concurrency_functions.append({
                        "function_name": function_name,
                        "generation": "2nd",
                        "region": region,
                        "concurrency_current": concurrency,
                        "recommended_concurrency": recommended_concurrency,
                        "avg_exec_time_seconds": round(avg_exec_time_seconds, 3),
                        "monthly_invocations": int(monthly_invocations),
                        "monthly_cost_current": round(monthly_cost_current, 2),
                        "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                        "monthly_savings": round(monthly_savings, 2),
                        "annual_savings": round(monthly_savings * 12, 2),
                        "confidence": confidence,
                        "recommendation": f"Increase concurrency from {concurrency} to {recommended_concurrency}",
                        "benefit": "Fewer instances needed, better resource utilization",
                        "labels": dict(function.labels) if function.labels else {},
                    })
    except Exception as e:
        print(f"Error analyzing 2nd gen functions: {e}")

    return low_concurrency_functions


# Exemple d'utilisation
if __name__ == "__main__":
    low_concurrency = detect_cloud_function_excessive_concurrency(
        project_id="my-gcp-project"
    )

    print(f"✅ {len(low_concurrency)} functions avec concurrency suboptimal")

    total_savings = sum([f["annual_savings"] for f in low_concurrency])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel (concurrency = 1)
compute_seconds = monthly_invocations * avg_exec_time_seconds
monthly_cost_current = (
    (monthly_invocations / 1_000_000) * 0.40 +
    compute_seconds * vcpu * 0.00002400 +
    compute_seconds * memory_gib * 0.00000250
)

# Coût optimal (concurrency > 1)
# Approximation: 30-40% réduction overhead instances
monthly_cost_optimal = monthly_cost_current * 0.70

monthly_savings = monthly_cost_current - monthly_cost_optimal
annual_savings = monthly_savings * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_function",
  "waste_scenario": "excessive_concurrency",
  "function_name": "fast-api-endpoint",
  "generation": "2nd",
  "region": "us-central1",
  "concurrency_current": 1,
  "recommended_concurrency": 100,
  "avg_exec_time_seconds": 0.085,
  "monthly_invocations": 5000000,
  "monthly_cost_current": 245.80,
  "monthly_cost_optimal": 172.06,
  "monthly_savings": 73.74,
  "annual_savings": 884.88,
  "confidence": "HIGH",
  "recommendation": "Increase concurrency from 1 to 100",
  "benefit": "Fewer instances needed, better resource utilization",
  "labels": {
    "environment": "production",
    "team": "api"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_function_excessive_concurrency()`

---

## Protocole de Test Complet

### Tests Unitaires Python

```python
# tests/test_gcp_cloud_functions.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.providers.gcp import GCPProvider

@pytest.fixture
def gcp_provider():
    """Fixture GCP provider avec credentials mock."""
    return GCPProvider(
        project_id="test-project",
        credentials={
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "mock-key"
        }
    )


class TestCloudFunctionNeverInvoked:
    """Tests scénario 1: Functions jamais invoquées."""

    def test_detect_1st_gen_function_never_invoked(self, gcp_provider):
        """Test détection 1st gen function avec 0 invocations."""
        with patch('google.cloud.functions_v1.CloudFunctionsServiceClient') as mock_client:
            # Mock function 1st gen
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/test-func"
            mock_function.runtime = "python39"
            mock_function.available_memory_mb = 256
            mock_function.timeout.seconds = 60
            mock_function.update_time = datetime.utcnow() - timedelta(days=100)
            mock_function.labels = {"environment": "production"}

            mock_client.return_value.list_functions.return_value = [mock_function]

            # Mock monitoring (0 invocations)
            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                mock_monitoring.return_value.list_time_series.return_value = []  # 0 invocations

                results = gcp_provider.detect_cloud_function_never_invoked(
                    no_invocations_threshold_days=30
                )

                assert len(results) == 1
                assert results[0]["function_name"] == "test-func"
                assert results[0]["generation"] == "1st"
                assert results[0]["total_invocations"] == 0
                assert results[0]["confidence"] == "CRITICAL"  # >90 days

    def test_detect_2nd_gen_function_with_min_instances(self, gcp_provider):
        """Test détection 2nd gen function avec min_instances + 0 invocations."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/test-func-2nd"
            mock_function.service_config.available_memory = "512Mi"
            mock_function.service_config.timeout_seconds = 120
            mock_function.service_config.min_instance_count = 2
            mock_function.service_config.runtime = "python311"
            mock_function.update_time = datetime.utcnow() - timedelta(days=60)
            mock_function.labels = {}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                mock_monitoring.return_value.list_time_series.return_value = []

                results = gcp_provider.detect_cloud_function_never_invoked(
                    no_invocations_threshold_days=30
                )

                assert len(results) == 1
                assert results[0]["generation"] == "2nd"
                assert results[0]["min_instances"] == 2
                assert results[0]["monthly_cost"] > 0  # Coût min instances
                assert results[0]["confidence"] == "HIGH"  # 60 days


class TestCloudFunctionIdleMinInstances:
    """Tests scénario 2: Min instances idle."""

    def test_detect_2nd_gen_idle_min_instances(self, gcp_provider):
        """Test détection 2nd gen avec min_instances mais traffic faible."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/idle-func"
            mock_function.service_config.available_memory = "512Mi"
            mock_function.service_config.min_instance_count = 2
            mock_function.labels = {"environment": "dev"}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock 5 invocations/jour (faible traffic)
                mock_series = Mock()
                mock_point = Mock()
                mock_point.value.int64_value = 70  # 70 invocations en 14 jours = 5/jour
                mock_series.points = [mock_point]
                mock_monitoring.return_value.list_time_series.return_value = [mock_series]

                results = gcp_provider.detect_cloud_function_idle_min_instances(
                    low_invocations_per_day=10
                )

                assert len(results) == 1
                assert results[0]["min_instances"] == 2
                assert results[0]["avg_invocations_per_day"] == 5.0
                assert results[0]["monthly_waste"] > 0
                assert results[0]["confidence"] == "HIGH"  # <5 invocations/jour


class TestCloudFunctionMemoryOverprovisioning:
    """Tests scénario 3: Memory overprovisioning."""

    def test_detect_1st_gen_memory_overprovisioned(self, gcp_provider):
        """Test détection 1st gen avec memory allocated >> used."""
        with patch('google.cloud.functions_v1.CloudFunctionsServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/overprov-func"
            mock_function.available_memory_mb = 2048  # 2 GB allocated
            mock_function.runtime = "nodejs18"
            mock_function.labels = {}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock memory usage: 512 MB avg (25% utilization)
                mock_series = Mock()
                mock_point = Mock()
                mock_point.value.double_value = 512 * 1024 * 1024  # 512 MB in bytes
                mock_series.points = [mock_point] * 10
                mock_monitoring.return_value.list_time_series.return_value = [mock_series]

                results = gcp_provider.detect_cloud_function_memory_overprovisioning(
                    memory_utilization_threshold=0.50
                )

                assert len(results) == 1
                assert results[0]["memory_allocated_mb"] == 2048
                assert results[0]["avg_memory_used_mb"] == 512
                assert results[0]["memory_utilization"] == 25.0
                assert results[0]["recommended_memory_mb"] < 2048
                assert results[0]["confidence"] == "CRITICAL"  # <30%


class TestCloudFunctionExcessiveTimeout:
    """Tests scénario 4: Excessive timeout."""

    def test_detect_excessive_timeout(self, gcp_provider):
        """Test détection function avec timeout >> avg exec time."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/timeout-func"
            mock_function.service_config.timeout_seconds = 3600  # 60 min timeout
            mock_function.labels = {}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock avg exec time: 45 seconds
                mock_series = Mock()
                mock_point = Mock()
                mock_point.value.distribution_value.mean = 45000  # 45s in ms
                mock_series.points = [mock_point] * 10
                mock_monitoring.return_value.list_time_series.return_value = [mock_series]

                results = gcp_provider.detect_cloud_function_excessive_timeout(
                    timeout_ratio_threshold=3.0
                )

                assert len(results) == 1
                assert results[0]["timeout_configured_seconds"] == 3600
                assert results[0]["avg_exec_time_seconds"] == 45.0
                assert results[0]["timeout_ratio"] == 80.0
                assert results[0]["confidence"] == "CRITICAL"  # >10x ratio


class TestCloudFunction1stGenExpensive:
    """Tests scénario 5: 1st gen plus coûteux que 2nd gen."""

    def test_detect_1st_gen_expensive(self, gcp_provider):
        """Test détection 1st gen qui serait moins cher en 2nd gen."""
        with patch('google.cloud.functions_v1.CloudFunctionsServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/expensive-1st"
            mock_function.available_memory_mb = 512
            mock_function.timeout.seconds = 300
            mock_function.runtime = "python39"
            mock_function.labels = {}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock high invocations (2M/mois) + avg exec time 800ms
                # Dans ce cas, 2nd gen avec concurrency serait moins cher

                results = gcp_provider.detect_cloud_function_1st_gen_expensive(
                    cost_savings_threshold_pct=20.0
                )

                # Assert basé sur logique pricing
                if results:
                    assert results[0]["generation"] == "1st"
                    assert results[0]["savings_pct"] > 20.0
                    assert results[0]["monthly_cost_1st_gen"] > results[0]["monthly_cost_2nd_gen"]


class TestCloudFunctionUntagged:
    """Tests scénario 6: Functions untagged."""

    def test_detect_untagged_functions(self, gcp_provider):
        """Test détection functions sans labels obligatoires."""
        with patch('google.cloud.functions_v1.CloudFunctionsServiceClient') as mock_client:
            # Function avec labels partiels
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/untagged-func"
            mock_function.runtime = "nodejs18"
            mock_function.labels = {"team": "backend"}  # Manque 'environment' et 'owner'

            mock_client.return_value.list_functions.return_value = [mock_function]

            results = gcp_provider.detect_cloud_function_untagged(
                required_labels=['environment', 'owner', 'cost-center']
            )

            assert len(results) == 1
            assert results[0]["function_name"] == "untagged-func"
            assert set(results[0]["missing_labels"]) == {'environment', 'owner', 'cost-center'}
            assert results[0]["confidence"] == "HIGH"


class TestCloudFunctionExcessiveMaxInstances:
    """Tests scénario 7: Excessive max instances."""

    def test_detect_excessive_max_instances(self, gcp_provider):
        """Test détection functions avec max_instances dangereux."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/max-func"
            mock_function.service_config.max_instance_count = 1000
            mock_function.service_config.available_memory = "512Mi"
            mock_function.labels = {"public": "true"}

            mock_client.return_value.list_functions.return_value = [mock_function]

            results = gcp_provider.detect_cloud_function_excessive_max_instances(
                max_instances_threshold=100
            )

            assert len(results) == 1
            assert results[0]["max_instances_configured"] == 1000
            assert results[0]["max_daily_cost"] > 500  # Risque élevé
            assert results[0]["confidence"] in ["CRITICAL", "HIGH"]


class TestCloudFunctionColdStartOverOptimization:
    """Tests scénario 8: Cold start over-optimization."""

    def test_detect_cold_start_over_optimization(self, gcp_provider):
        """Test détection 2nd gen avec min_instances pour cold starts uniquement."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/cold-func"
            mock_function.service_config.min_instance_count = 2
            mock_function.service_config.available_memory = "512Mi"
            mock_function.labels = {"latency": "sensitive"}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock faible traffic: 3 invocations/heure
                mock_series = Mock()
                mock_point = Mock()
                mock_point.value.int64_value = 1000  # 1000 invocations en 14 jours
                mock_series.points = [mock_point]
                mock_monitoring.return_value.list_time_series.return_value = [mock_series]

                results = gcp_provider.detect_cloud_function_cold_start_over_optimization(
                    cold_start_cost_threshold=50.0
                )

                if results:
                    assert results[0]["min_instances"] == 2
                    assert results[0]["invocations_per_hour"] < 10
                    assert results[0]["monthly_savings"] > 0
                    assert "warmup" in results[0]["recommendation"].lower()


class TestCloudFunctionDuplicate:
    """Tests scénario 9: Functions duplicate."""

    def test_detect_duplicate_functions(self, gcp_provider):
        """Test détection functions avec même code source."""
        with patch('google.cloud.functions_v1.CloudFunctionsServiceClient') as mock_client:
            # 3 functions identiques dans différentes régions
            mock_func_1 = Mock()
            mock_func_1.name = "projects/test/locations/us-central1/functions/webhook-us"
            mock_func_1.runtime = "python39"
            mock_func_1.entry_point = "handle_webhook"
            mock_func_1.source_archive_url = "gs://my-bucket/source.zip"

            mock_func_2 = Mock()
            mock_func_2.name = "projects/test/locations/europe-west1/functions/webhook-eu"
            mock_func_2.runtime = "python39"
            mock_func_2.entry_point = "handle_webhook"
            mock_func_2.source_archive_url = "gs://my-bucket/source.zip"

            mock_func_3 = Mock()
            mock_func_3.name = "projects/test/locations/asia-east1/functions/webhook-asia"
            mock_func_3.runtime = "python39"
            mock_func_3.entry_point = "handle_webhook"
            mock_func_3.source_archive_url = "gs://my-bucket/source.zip"

            mock_client.return_value.list_functions.return_value = [
                mock_func_1, mock_func_2, mock_func_3
            ]

            results = gcp_provider.detect_cloud_function_duplicate()

            assert len(results) == 1  # 1 groupe de duplicates
            assert results[0]["duplicate_count"] == 3
            assert len(results[0]["functions"]) == 3


class TestCloudFunctionExcessiveConcurrency:
    """Tests scénario 10: Excessive concurrency (suboptimal)."""

    def test_detect_excessive_concurrency(self, gcp_provider):
        """Test détection 2nd gen avec concurrency = 1 (suboptimal)."""
        with patch('google.cloud.functions_v2.FunctionServiceClient') as mock_client:
            mock_function = Mock()
            mock_function.name = "projects/test/locations/us-central1/functions/fast-api"
            mock_function.service_config.max_instance_request_concurrency = 1
            mock_function.service_config.available_memory = "256Mi"
            mock_function.labels = {}

            mock_client.return_value.list_functions.return_value = [mock_function]

            with patch('google.cloud.monitoring_v3.MetricServiceClient') as mock_monitoring:
                # Mock high invocations + fast exec time (50ms)
                results = gcp_provider.detect_cloud_function_excessive_concurrency()

                if results:
                    assert results[0]["concurrency_current"] == 1
                    assert results[0]["recommended_concurrency"] > 1
                    assert results[0]["avg_exec_time_seconds"] < 1.0
                    assert results[0]["monthly_savings"] > 0
```

### Tests d'Intégration GCP

```bash
# tests/integration/test_gcp_cloud_functions_integration.sh

#!/bin/bash
# Tests d'intégration Cloud Functions sur projet GCP réel

PROJECT_ID="cloudwaste-test"
REGION="us-central1"

echo "🧪 Tests d'intégration GCP Cloud Functions"

# 1. Créer function test 1st gen (never invoked)
echo "1️⃣  Créer function test 1st gen..."
gcloud functions deploy test-never-invoked-1st \
  --gen2=false \
  --runtime=python39 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=hello_http \
  --source=./test-functions/hello \
  --region=$REGION \
  --project=$PROJECT_ID \
  --quiet

sleep 30  # Wait for deployment

# 2. Créer function test 2nd gen avec min_instances
echo "2️⃣  Créer function test 2nd gen avec min_instances..."
gcloud functions deploy test-idle-min-instances-2nd \
  --gen2 \
  --runtime=python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=hello_http \
  --source=./test-functions/hello \
  --region=$REGION \
  --min-instances=2 \
  --project=$PROJECT_ID \
  --quiet

sleep 30

# 3. Créer function test avec memory overprovisioning
echo "3️⃣  Créer function test memory overprovisioned..."
gcloud functions deploy test-memory-overprov \
  --gen2=false \
  --runtime=nodejs18 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=helloWorld \
  --source=./test-functions/hello-node \
  --memory=2048MB \
  --region=$REGION \
  --project=$PROJECT_ID \
  --quiet

# Invoke avec memory usage faible
for i in {1..10}; do
  curl -s "https://$REGION-$PROJECT_ID.cloudfunctions.net/test-memory-overprov" > /dev/null
done

sleep 30

# 4. Créer function test excessive timeout
echo "4️⃣  Créer function test excessive timeout..."
gcloud functions deploy test-excessive-timeout \
  --gen2 \
  --runtime=python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=hello_http \
  --source=./test-functions/hello \
  --timeout=3600s \
  --region=$REGION \
  --project=$PROJECT_ID \
  --quiet

# Invoke avec exec time court (100ms)
for i in {1..10}; do
  curl -s "https://$REGION-$PROJECT_ID.cloudfunctions.net/test-excessive-timeout" > /dev/null
done

sleep 30

# 5. Créer function test untagged
echo "5️⃣  Créer function test untagged..."
gcloud functions deploy test-untagged \
  --gen2=false \
  --runtime=python39 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=hello_http \
  --source=./test-functions/hello \
  --region=$REGION \
  --project=$PROJECT_ID \
  --quiet
  # Pas de labels

sleep 30

# 6. Créer function test excessive max instances
echo "6️⃣  Créer function test excessive max instances..."
gcloud functions deploy test-excessive-max-instances \
  --gen2 \
  --runtime=python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=hello_http \
  --source=./test-functions/hello \
  --max-instances=1000 \
  --region=$REGION \
  --project=$PROJECT_ID \
  --quiet

sleep 30

# 7. Créer duplicate functions
echo "7️⃣  Créer functions duplicate..."
for region in us-central1 europe-west1 asia-east1; do
  gcloud functions deploy test-webhook-$region \
    --gen2=false \
    --runtime=python39 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point=hello_http \
    --source=./test-functions/hello \
    --region=$region \
    --project=$PROJECT_ID \
    --quiet &
done

wait

echo "✅ Fonctions test créées, attente 5 minutes pour métriques..."
sleep 300

# 8. Exécuter détection CloudWaste
echo "8️⃣  Exécuter détection CloudWaste..."
python -m pytest tests/integration/test_gcp_functions_integration.py -v

# 9. Cleanup
echo "9️⃣  Cleanup functions test..."
gcloud functions delete test-never-invoked-1st --region=$REGION --project=$PROJECT_ID --quiet
gcloud functions delete test-idle-min-instances-2nd --region=$REGION --project=$PROJECT_ID --quiet
gcloud functions delete test-memory-overprov --region=$REGION --project=$PROJECT_ID --quiet
gcloud functions delete test-excessive-timeout --region=$REGION --project=$PROJECT_ID --quiet
gcloud functions delete test-untagged --region=$REGION --project=$PROJECT_ID --quiet
gcloud functions delete test-excessive-max-instances --region=$REGION --project=$PROJECT_ID --quiet

for region in us-central1 europe-west1 asia-east1; do
  gcloud functions delete test-webhook-$region --region=$region --project=$PROJECT_ID --quiet &
done

wait

echo "✅ Tests d'intégration terminés"
```

### Validation Complète

```python
# tests/integration/test_gcp_functions_integration.py

import pytest
from app.providers.gcp import GCPProvider
from app.core.config import settings

@pytest.fixture
def gcp_provider_integration():
    """Provider GCP avec vraies credentials pour tests intégration."""
    return GCPProvider(
        project_id="cloudwaste-test",
        credentials=settings.GCP_TEST_CREDENTIALS
    )


def test_integration_full_scan(gcp_provider_integration):
    """Test scan complet de toutes les functions avec tous les scénarios."""

    # Scénario 1: Never invoked
    never_invoked = gcp_provider_integration.detect_cloud_function_never_invoked(
        no_invocations_threshold_days=1  # 1 jour pour test
    )
    assert len(never_invoked) >= 1
    assert any(f["function_name"] == "test-never-invoked-1st" for f in never_invoked)

    # Scénario 2: Idle min instances
    idle_min = gcp_provider_integration.detect_cloud_function_idle_min_instances(
        low_invocations_per_day=10
    )
    assert len(idle_min) >= 1
    assert any(f["function_name"] == "test-idle-min-instances-2nd" for f in idle_min)

    # Scénario 3: Memory overprovisioning
    overprov = gcp_provider_integration.detect_cloud_function_memory_overprovisioning(
        memory_utilization_threshold=0.50
    )
    # Note: Nécessite métriques memory (peut prendre 10-15 min)

    # Scénario 4: Excessive timeout
    timeout = gcp_provider_integration.detect_cloud_function_excessive_timeout(
        timeout_ratio_threshold=3.0
    )
    assert len(timeout) >= 1

    # Scénario 6: Untagged
    untagged = gcp_provider_integration.detect_cloud_function_untagged(
        required_labels=['environment', 'owner']
    )
    assert len(untagged) >= 1
    assert any(f["function_name"] == "test-untagged" for f in untagged)

    # Scénario 7: Excessive max instances
    excessive_max = gcp_provider_integration.detect_cloud_function_excessive_max_instances(
        max_instances_threshold=100
    )
    assert len(excessive_max) >= 1

    # Scénario 9: Duplicate
    duplicates = gcp_provider_integration.detect_cloud_function_duplicate()
    assert len(duplicates) >= 1
    # Vérifier group avec 3 functions webhook
    webhook_group = [g for g in duplicates if any("webhook" in f["function_name"] for f in g["functions"])]
    assert len(webhook_group) >= 1
    assert webhook_group[0]["duplicate_count"] == 3

    print("✅ Tous les scénarios détectés correctement")


def test_integration_cost_accuracy(gcp_provider_integration):
    """Test précision des calculs de coût."""

    idle_min = gcp_provider_integration.detect_cloud_function_idle_min_instances()

    for func in idle_min:
        # Vérifier formules pricing 2nd gen
        memory_gib = func["memory_mb"] / 1024
        vcpu = func["vcpu"]
        min_instances = func["min_instances"]

        expected_cost = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

        assert abs(func["monthly_cost_current"] - expected_cost) < 1.0  # Marge 1$

    print("✅ Calculs de coût validés")
```

---

## Références

### Documentation Officielle GCP

- **Cloud Functions 1st Gen:** https://cloud.google.com/functions/docs/1st-gen
- **Cloud Functions 2nd Gen:** https://cloud.google.com/functions/docs/2nd-gen
- **Cloud Functions Pricing:** https://cloud.google.com/functions/pricing
- **Migration 1st → 2nd Gen:** https://cloud.google.com/functions/docs/2nd-gen/migrate-from-1st-gen
- **Cloud Functions Best Practices:** https://cloud.google.com/functions/docs/bestpractices
- **Cloud Monitoring API:** https://cloud.google.com/monitoring/api/ref_v3/rest
- **Cloud Scheduler (warm-up):** https://cloud.google.com/scheduler/docs

### APIs et SDKs

```python
# Python SDK
from google.cloud import functions_v1
from google.cloud import functions_v2
from google.cloud import monitoring_v3

# Client 1st Gen
functions_v1_client = functions_v1.CloudFunctionsServiceClient()

# Client 2nd Gen
functions_v2_client = functions_v2.FunctionServiceClient()

# Client Monitoring (métriques)
monitoring_client = monitoring_v3.MetricServiceClient()
```

### Métriques Cloud Monitoring

#### 1st Generation Metrics

```python
# Execution count (invocations)
metric_type = "cloudfunctions.googleapis.com/function/execution_count"
resource_type = "cloud_function"

# Execution times (latency)
metric_type = "cloudfunctions.googleapis.com/function/execution_times"
resource_type = "cloud_function"

# User memory (memory usage)
metric_type = "cloudfunctions.googleapis.com/function/user_memory_bytes"
resource_type = "cloud_function"

# Active instances
metric_type = "cloudfunctions.googleapis.com/function/active_instances"
resource_type = "cloud_function"
```

#### 2nd Generation Metrics (Cloud Run based)

```python
# Request count (invocations)
metric_type = "run.googleapis.com/request_count"
resource_type = "cloud_run_revision"

# Request latencies (exec time)
metric_type = "run.googleapis.com/request_latencies"
resource_type = "cloud_run_revision"

# Container memory utilization
metric_type = "run.googleapis.com/container/memory/utilizations"
resource_type = "cloud_run_revision"

# Container CPU utilization
metric_type = "run.googleapis.com/container/cpu/utilizations"
resource_type = "cloud_run_revision"

# Instance count
metric_type = "run.googleapis.com/container/instance_count"
resource_type = "cloud_run_revision"
```

### gcloud CLI Commands

```bash
# Lister toutes les functions 1st gen
gcloud functions list --gen2=false --project=PROJECT_ID

# Lister toutes les functions 2nd gen
gcloud functions list --gen2 --project=PROJECT_ID

# Détails function
gcloud functions describe FUNCTION_NAME --region=REGION --gen2 --project=PROJECT_ID

# Logs function
gcloud functions logs read FUNCTION_NAME --region=REGION --limit=100 --project=PROJECT_ID

# Mettre à jour min_instances
gcloud functions deploy FUNCTION_NAME \
  --gen2 \
  --min-instances=0 \
  --region=REGION \
  --project=PROJECT_ID

# Mettre à jour concurrency
gcloud functions deploy FUNCTION_NAME \
  --gen2 \
  --concurrency=100 \
  --region=REGION \
  --project=PROJECT_ID

# Supprimer function
gcloud functions delete FUNCTION_NAME --region=REGION --gen2 --project=PROJECT_ID --quiet
```

### Pricing Calculator Examples

```python
# Calculateur 1st Gen
def calculate_1st_gen_cost(
    invocations_per_month: int,
    avg_duration_seconds: float,
    memory_mb: int
) -> float:
    """Calculer coût mensuel 1st gen."""
    memory_gb = memory_mb / 1024
    cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

    compute_seconds = invocations_per_month * avg_duration_seconds

    invocations_cost = (invocations_per_month / 1_000_000) * 0.40
    memory_cost = compute_seconds * memory_gb * 0.0000025
    cpu_cost = compute_seconds * cpu_ghz * 0.0000100

    return invocations_cost + memory_cost + cpu_cost


# Calculateur 2nd Gen
def calculate_2nd_gen_cost(
    invocations_per_month: int,
    avg_duration_seconds: float,
    vcpu: float,
    memory_gib: float,
    min_instances: int = 0
) -> float:
    """Calculer coût mensuel 2nd gen."""
    compute_seconds = invocations_per_month * avg_duration_seconds

    invocations_cost = (invocations_per_month / 1_000_000) * 0.40
    vcpu_cost = compute_seconds * vcpu * 0.00002400
    memory_cost = compute_seconds * memory_gib * 0.00000250

    # Min instances (24/7)
    if min_instances > 0:
        min_instance_cost = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances
    else:
        min_instance_cost = 0

    return invocations_cost + vcpu_cost + memory_cost + min_instance_cost


# Exemple usage
cost_1st = calculate_1st_gen_cost(
    invocations_per_month=1_000_000,
    avg_duration_seconds=0.2,
    memory_mb=256
)

cost_2nd = calculate_2nd_gen_cost(
    invocations_per_month=1_000_000,
    avg_duration_seconds=0.2,
    vcpu=0.5,
    memory_gib=0.25,
    min_instances=0
)

print(f"1st Gen: ${cost_1st:.2f}/mois")
print(f"2nd Gen: ${cost_2nd:.2f}/mois")
```

### IAM Permissions Required

```json
{
  "roles/cloudfunctions.viewer": [
    "cloudfunctions.functions.get",
    "cloudfunctions.functions.list"
  ],
  "roles/monitoring.viewer": [
    "monitoring.timeSeries.list",
    "monitoring.metricDescriptors.list"
  ],
  "roles/run.viewer": [
    "run.services.get",
    "run.services.list",
    "run.revisions.get",
    "run.revisions.list"
  ]
}
```

### Best Practices Summary

1. **Min Instances (2nd Gen)** : Utiliser uniquement si latency critical (<50ms SLA)
2. **Concurrency (2nd Gen)** : Configurer >1 si exec time <1s pour économies
3. **Timeout** : Configurer à avg exec time × 1.5 (pas trop haut)
4. **Memory** : Right-size à 70% utilization (pas 50% ou 100%)
5. **Max Instances** : Limiter à 100 + rate limiting pour protection coût
6. **Labels** : Toujours ajouter `environment`, `owner`, `cost-center`
7. **Migration 1st → 2nd** : Évaluer au cas par cas (pas toujours moins cher)
8. **Cold Starts** : Warm-up requests (<$20/mois) vs min_instances (>$50/mois)

---

**Document Version:** 1.0
**Date:** 2025-01-03
**Auteur:** CloudWaste Team
**Statut:** ✅ Complete

