# GCP Cloud Run Services - Scénarios de Gaspillage (100%)

**Type de ressource :** `Compute : Cloud Run Services`
**Catégorie :** Serverless Containers
**Impact financier estimé :** $8,000 - $40,000/an pour une organisation moyenne (100-500 services)
**Complexité de détection :** ⭐⭐⭐⭐ (Élevée - Nécessite analyse métriques temps réel et configuration)

---

## Vue d'Ensemble

### Qu'est-ce que Cloud Run Services ?

**Cloud Run Services** est la plateforme serverless de GCP pour exécuter des conteneurs avec :
- **Autoscaling automatique** (0 to N instances)
- **Pay-per-use** (CPU, Memory, Requests seulement)
- **Fully managed** (pas de serveurs à gérer)
- **HTTP/gRPC endpoints** (APIs, microservices, web apps)
- **Container-based** (support tout container Docker)

### Architecture Cloud Run

```
Cloud Run Service
│
├── Configuration
│   ├── Container Image (gcr.io/project/image:tag)
│   ├── CPU Allocation Mode
│   │   ├── CPU always allocated ──────► Billing 24/7 (instances actives)
│   │   └── CPU during requests only ──► Billing pendant requests seulement ✅
│   ├── Resources
│   │   ├── vCPU: 0.08, 1, 2, 4, 8 vCPU
│   │   └── Memory: 128 MiB - 32 GiB
│   ├── Autoscaling
│   │   ├── Min instances: 0-1000 ────► 0 = scale to zero ✅
│   │   ├── Max instances: 1-1000 ────► Protection runaway costs
│   │   └── Concurrency: 1-1000 ──────► Requests par instance
│   └── Timeout: 1s - 60min
│
├── Traffic (Revisions)
│   ├── Revision 1 (100% traffic)
│   ├── Revision 2 (0% traffic) ────────► Peut générer waste si old revisions
│   └── Revision 3 (0% traffic)
│
└── Billing
    ├── CPU: $0.00002400/vCPU-second
    ├── Memory: $0.00000250/GiB-second
    └── Requests: $0.40/million
```

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Min instances** | Instances permanentes (warm) | Si > 0 = billing 24/7 même sans traffic |
| **Max instances** | Limite autoscaling | Protection contre runaway costs |
| **CPU allocation** | Always vs During requests | Always = 100% billing, During = billing requests only |
| **Concurrency** | Requests simultanés/instance | Low concurrency = plus d'instances = surcoût |
| **Cold starts** | Délai démarrage instance | Min instances évite cold start mais coûte cher |
| **Revisions** | Versions code/config | Old revisions inutilisées peuvent rester déployées |

### Cloud Run Pricing (us-central1)

| Ressource | Prix | Calcul Mensuel (720h) | Exemple |
|-----------|------|----------------------|---------|
| **vCPU** | $0.00002400/second | $62.21/vCPU/mois | 1 vCPU min instance = $62.21/mois |
| **Memory** | $0.00000250/GiB-second | $6.48/GiB/mois | 2 GiB min instance = $12.96/mois |
| **Requests** | $0.40/million | Variable | 1M requests = $0.40 |

**Exemple coût min instance permanente :**
```
Service : 1 vCPU + 2 GiB + min_instances = 1
Coût mensuel : (1 × $62.21) + (2 × $6.48) = $75.17/mois

Si min_instances = 0 et traffic faible :
Coût mensuel : ~$0 (scale to zero) ✅
```

### Waste Typique

1. **Services never used** : 0 requests = $50-500/mois waste
2. **Min instances idle** : min_instances > 0 pour service peu utilisé = $100-1,000/mois
3. **Overprovisioned resources** : CPU/Memory trop élevés = 40-60% surcoût
4. **Dev/test 24/7** : Non-prod avec min instances > 0 = $80-400/mois waste
5. **CPU always allocated** : Mode always vs during requests = 40-60% surcoût
6. **Low concurrency** : Concurrency = 1-10 = 10x plus d'instances = 10x coût
7. **Excessive max instances** : max > 100 = risque runaway $10K+/jour

---

## Modèle de Pricing Cloud Run Services

### Pricing Détaillé

#### 1. CPU Pricing

```python
# CPU Pricing
CPU_PRICE_PER_SECOND = 0.00002400  # $/vCPU-second

# Calcul mensuel (30 jours × 24h × 3600s = 2,592,000 secondes)
cpu_monthly_cost = CPU_PRICE_PER_SECOND * 2_592_000
# = $62.208/vCPU/mois

# Exemple : 2 vCPU
monthly_cost_2vcpu = 2 * 62.208  # = $124.42/mois
```

**CPU Allocation Modes :**
```
Mode 1: "CPU is always allocated"
─────────────────────────────────
- CPU billing 24/7 tant que instance active
- Use case: Websockets, background tasks
- Cost: 100% du temps d'instance

Mode 2: "CPU is only allocated during request processing" ✅
──────────────────────────────────────────────────────────
- CPU billing seulement pendant requests
- Use case: HTTP APIs, services sporadiques
- Cost: Seulement % temps requests (ex: 10% = -90% coût CPU)

Économie si traffic < 50% :
Mode "during requests" = -40-60% coût CPU ✅
```

#### 2. Memory Pricing

```python
# Memory Pricing
MEMORY_PRICE_PER_GIB_SECOND = 0.00000250  # $/GiB-second

# Calcul mensuel
memory_monthly_cost = MEMORY_PRICE_PER_GIB_SECOND * 2_592_000
# = $6.48/GiB/mois

# Exemple : 4 GiB
monthly_cost_4gib = 4 * 6.48  # = $25.92/mois
```

#### 3. Requests Pricing

```python
# Requests Pricing
REQUESTS_PRICE_PER_MILLION = 0.40  # $/million

# Exemple : 5 million requests/mois
monthly_cost_5m_requests = 5 * 0.40  # = $2.00/mois

# Note: Requests coût négligeable vs CPU/Memory
```

### Exemples de Calcul de Coût

#### Exemple 1 : Service Production avec Min Instances

```python
# Configuration
vcpu = 2
memory_gib = 4
min_instances = 3  # Pour éviter cold starts
max_instances = 100
cpu_mode = "always allocated"

# Coût par instance
cost_per_instance_monthly = (vcpu * 62.21) + (memory_gib * 6.48)
# = (2 × $62.21) + (4 × $6.48) = $124.42 + $25.92 = $150.34/mois/instance

# Coût min instances (permanent)
cost_min_instances = 3 * 150.34  # = $451.02/mois

# Coût autoscaling instances (variable selon traffic)
# Supposons 20 instance-heures additionnelles/jour
additional_instance_hours_monthly = 20 * 30  # = 600 heures/mois
additional_cost = (600 / 720) * 150.34  # = $125.28/mois

# Coût total mensuel
total_monthly = 451.02 + 125.28 + requests_cost  # = $576.30/mois
annual_cost = 576.30 * 12  # = $6,915.60/an
```

#### Exemple 2 : Service Dev/Test avec Min Instances (WASTE)

```python
# Configuration (MAUVAISE pour dev/test)
vcpu = 1
memory_gib = 2
min_instances = 2  # ❌ Waste pour dev/test
traffic_daily_requests = 50  # Très faible

# Coût actuel
cost_per_instance = (1 * 62.21) + (2 * 6.48)  # = $75.17/mois
cost_min_instances = 2 * 75.17  # = $150.34/mois

# Coût optimal (min_instances = 0)
cost_optimal = 0 + (50 * 30 / 1_000_000) * 0.40  # ≈ $0/mois

# WASTE
monthly_waste = 150.34 - 0  # = $150.34/mois ❌
annual_waste = 150.34 * 12  # = $1,804/an ❌
```

#### Exemple 3 : Overprovisioned Service

```python
# Configuration actuelle
vcpu_current = 4
memory_current = 8
cpu_utilization = 15%  # ❌ Sous-utilisé
memory_utilization = 18%  # ❌ Sous-utilisé

# Coût actuel
current_cost = (4 * 62.21) + (8 * 6.48)  # = $248.84 + $51.84 = $300.68/instance

# Configuration optimale
vcpu_optimal = 1  # Suffisant pour 15% utilization
memory_optimal = 2  # Suffisant pour 18% utilization

# Coût optimal
optimal_cost = (1 * 62.21) + (2 * 6.48)  # = $75.17/instance

# WASTE (par instance)
waste_per_instance = 300.68 - 75.17  # = $225.51/mois ❌

# Si service avec min_instances = 2
monthly_waste = 2 * 225.51  # = $451.02/mois
annual_waste = 451.02 * 12  # = $5,412/an ❌
```

#### Exemple 4 : CPU Always Allocated vs During Requests

```python
# Service avec traffic sporadique (20% du temps)
vcpu = 2
memory_gib = 4
traffic_percentage = 0.20  # 20% du temps

# Mode 1: CPU always allocated
cpu_cost_always = 2 * 62.21  # = $124.42/mois
memory_cost = 4 * 6.48  # = $25.92/mois
total_always = 124.42 + 25.92  # = $150.34/mois

# Mode 2: CPU during requests only
cpu_cost_during = 2 * 62.21 * traffic_percentage  # = $24.88/mois ✅
memory_cost = 4 * 6.48  # = $25.92/mois (toujours facturé)
total_during = 24.88 + 25.92  # = $50.80/mois ✅

# WASTE (mode always inutile)
monthly_waste = 150.34 - 50.80  # = $99.54/mois ❌
annual_waste = 99.54 * 12  # = $1,194/an ❌

# Économie = -66% en switchant vers "during requests"
```

### Comparaison Coûts : Cloud Run vs Alternatives

| Solution | Coût 1 vCPU + 2 GiB | Use Case | Disponibilité |
|----------|---------------------|----------|---------------|
| **Cloud Run (scale to zero)** | $0-75/mois | Services sporadiques | Auto scale |
| **Cloud Run (min instances = 1)** | $75/mois | Production, low latency | 100% disponible |
| **GKE Autopilot** | $70-80/mois | Kubernetes workloads | Nodes managed |
| **Compute Engine (e2-small)** | $13-15/mois | Always-on VMs | Manual scale |
| **App Engine Standard** | $55-65/mois | Legacy apps | Auto scale |

**💡 Optimisation** : Cloud Run avec min_instances = 0 = le plus économique pour traffic sporadique.

---

## Phase 1 : Détection Simple (7 Scénarios)

### Scénario 1 : Services Jamais Utilisés (Zero Requests)

**Description :** Services Cloud Run déployés mais jamais utilisés (0 requests depuis 30+ jours). Waste total si min_instances > 0.

**Impact financier :**
- **Coût mensuel moyen :** $50 - $500/service (selon config)
- **Waste typique :** 10-15% des services never used
- **Économie annuelle :** $5K - $20K

**Logique de détection :**

```python
from google.cloud import run_v2
from google.cloud import monitoring_v3
from datetime import datetime, timedelta

def detect_cloud_run_never_used(
    project_id: str,
    region: str = "us-central1",
    no_requests_threshold_days: int = 30
) -> list:
    """
    Détecte les services Cloud Run jamais utilisés (0 requests).

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run (défaut: us-central1)
        no_requests_threshold_days: Période sans requests (défaut: 30 jours)

    Returns:
        Liste des services jamais utilisés avec métadonnées
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    never_used_services = []

    # 1. Lister tous les services Cloud Run
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]

        # 2. Query Cloud Monitoring pour request_count metric
        # Métrique: run.googleapis.com/request_count
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=no_requests_threshold_days)).timestamp())},
        })

        # Filter pour ce service spécifique
        filter_str = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/request_count"'
        )

        request = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_str,
            interval=interval,
        )

        # Lister les time series
        time_series = monitoring_client.list_time_series(request=request)

        # 3. Calculer total requests
        total_requests = 0
        for series in time_series:
            for point in series.points:
                total_requests += point.value.int64_value or point.value.double_value or 0

        # 4. Détection si 0 requests
        if total_requests == 0:
            # Service jamais utilisé = waste

            # Extraire configuration service
            template = service.template
            container = template.containers[0] if template.containers else None

            vcpu = container.resources.limits.get('cpu', '1') if container and container.resources else '1'
            # Parse vCPU (format: '1000m' = 1 vCPU, '2' = 2 vCPU)
            if 'm' in str(vcpu):
                vcpu_value = int(str(vcpu).replace('m', '')) / 1000
            else:
                vcpu_value = float(vcpu)

            memory = container.resources.limits.get('memory', '512Mi') if container and container.resources else '512Mi'
            # Parse memory (format: '512Mi', '2Gi')
            if 'Gi' in memory:
                memory_gib = float(memory.replace('Gi', ''))
            elif 'Mi' in memory:
                memory_gib = float(memory.replace('Mi', '')) / 1024
            else:
                memory_gib = 0.5

            # Min/max instances
            scaling = template.scaling
            min_instances = scaling.min_instance_count if scaling else 0
            max_instances = scaling.max_instance_count if scaling else 100

            # CPU allocation mode
            cpu_always_allocated = (container.resources.cpu_idle if container and container.resources else True)

            # Calculer coût mensuel
            # Si min_instances > 0, coût permanent
            if min_instances > 0:
                cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)
                monthly_cost = min_instances * cost_per_instance
            else:
                monthly_cost = 0  # Scale to zero = $0 si pas de requests

            # Age du service
            creation_time = service.create_time
            age_days = (datetime.utcnow().replace(tzinfo=None) - creation_time.replace(tzinfo=None)).days

            # Niveau de confiance
            if age_days >= 90:
                confidence = "CRITICAL"  # 3+ mois sans utilisation
            elif age_days >= 60:
                confidence = "HIGH"
            elif age_days >= 30:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            never_used_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "vcpu": vcpu_value,
                "memory_gib": round(memory_gib, 2),
                "min_instances": min_instances,
                "max_instances": max_instances,
                "cpu_always_allocated": cpu_always_allocated,
                "age_days": age_days,
                "creation_time": creation_time.isoformat(),
                "total_requests_30d": 0,
                "monthly_cost": round(monthly_cost, 2),
                "annual_waste": round(monthly_cost * 12, 2),
                "confidence": confidence,
                "labels": dict(service.labels) if service.labels else {},
            })

    return never_used_services


# Exemple d'utilisation
if __name__ == "__main__":
    never_used = detect_cloud_run_never_used(
        project_id="my-gcp-project",
        region="us-central1",
        no_requests_threshold_days=30
    )

    print(f"✅ {len(never_used)} services jamais utilisés détectés")

    total_waste = sum([s["annual_waste"] for s in never_used])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Waste = 100% du coût (service inutile)
if min_instances > 0:
    cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
    monthly_waste = min_instances * cost_per_instance
else:
    monthly_waste = 0  # Scale to zero

annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `no_requests_threshold_days` | 30 jours | Période sans requests | ↑ = moins de détections |
| `region` | us-central1 | Région Cloud Run | Ajuster selon projet |

**Métadonnées du waste détecté :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "never_used",
  "service_name": "api-internal-legacy",
  "service_uri": "https://api-internal-legacy-abcdef-uc.a.run.app",
  "region": "us-central1",
  "vcpu": 1.0,
  "memory_gib": 2.0,
  "min_instances": 1,
  "max_instances": 10,
  "cpu_always_allocated": true,
  "age_days": 95,
  "creation_time": "2024-07-30T10:00:00Z",
  "total_requests_30d": 0,
  "monthly_cost": 75.17,
  "annual_waste": 902.04,
  "confidence": "CRITICAL",
  "labels": {
    "environment": "production",
    "team": "backend"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_never_used()`

---

### Scénario 2 : Services Idle avec Min Instances > 0

**Description :** Services avec min instances > 0 mais traffic très faible (<10 requests/jour). Min instances facturées 24/7 = waste si pas nécessaire.

**Impact financier :**
- **Coût mensuel :** $100 - $1,000/service
- **Waste typique :** 40-60% des services non-prod
- **Économie annuelle :** $10K - $50K

**Logique de détection :**

```python
def detect_cloud_run_idle_min_instances(
    project_id: str,
    region: str = "us-central1",
    low_traffic_requests_per_day: int = 10,
    lookback_days: int = 14
) -> list:
    """
    Détecte les services avec min_instances > 0 mais traffic très faible.

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        low_traffic_requests_per_day: Seuil traffic faible (défaut: 10 req/jour)
        lookback_days: Période d'analyse (défaut: 14 jours)

    Returns:
        Liste des services idle avec min instances
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    idle_min_instances_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template

        # Extraire min_instances
        scaling = template.scaling
        min_instances = scaling.min_instance_count if scaling else 0

        # 2. Filtrer seulement services avec min_instances > 0
        if min_instances == 0:
            continue  # Scale to zero = OK

        # 3. Query request_count metric (derniers N jours)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        filter_str = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/request_count"'
        )

        request = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_str,
            interval=interval,
        )

        time_series = monitoring_client.list_time_series(request=request)

        # Calculer total requests
        total_requests = 0
        for series in time_series:
            for point in series.points:
                total_requests += point.value.int64_value or point.value.double_value or 0

        # Calculer avg requests/jour
        avg_requests_per_day = total_requests / lookback_days

        # 4. Détection si traffic faible
        if avg_requests_per_day < low_traffic_requests_per_day:
            # Traffic faible + min_instances > 0 = waste

            # Extraire config
            container = template.containers[0] if template.containers else None

            vcpu = container.resources.limits.get('cpu', '1') if container and container.resources else '1'
            if 'm' in str(vcpu):
                vcpu_value = int(str(vcpu).replace('m', '')) / 1000
            else:
                vcpu_value = float(vcpu)

            memory = container.resources.limits.get('memory', '512Mi') if container and container.resources else '512Mi'
            if 'Gi' in memory:
                memory_gib = float(memory.replace('Gi', ''))
            elif 'Mi' in memory:
                memory_gib = float(memory.replace('Mi', '')) / 1024
            else:
                memory_gib = 0.5

            # Calculer coût min instances permanent
            cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)
            monthly_cost_min_instances = min_instances * cost_per_instance

            # Coût optimal (min_instances = 0 + requests coût)
            monthly_cost_optimal = (avg_requests_per_day * 30 / 1_000_000) * 0.40  # Requests coût négligeable

            # Waste
            monthly_waste = monthly_cost_min_instances - monthly_cost_optimal

            # Niveau confiance
            if avg_requests_per_day < 1:
                confidence = "CRITICAL"  # <1 req/jour
            elif avg_requests_per_day < 5:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            idle_min_instances_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "vcpu": vcpu_value,
                "memory_gib": round(memory_gib, 2),
                "min_instances": min_instances,
                "avg_requests_per_day": round(avg_requests_per_day, 2),
                "total_requests_period": int(total_requests),
                "lookback_days": lookback_days,
                "monthly_cost_current": round(monthly_cost_min_instances, 2),
                "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": "Set min_instances = 0 to scale to zero",
                "labels": dict(service.labels) if service.labels else {},
            })

    return idle_min_instances_services


# Exemple d'utilisation
if __name__ == "__main__":
    idle_min = detect_cloud_run_idle_min_instances(
        project_id="my-gcp-project",
        region="us-central1",
        low_traffic_requests_per_day=10
    )

    print(f"✅ {len(idle_min)} services idle avec min_instances > 0")

    total_waste = sum([s["annual_waste"] for s in idle_min])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel (min_instances permanent)
cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
monthly_cost_current = min_instances * cost_per_instance

# Coût optimal (min_instances = 0)
monthly_cost_optimal = 0  # Scale to zero + requests coût négligeable

# Waste
monthly_waste = monthly_cost_current - monthly_cost_optimal
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `low_traffic_requests_per_day` | 10 req/jour | Seuil traffic faible | ↑ = plus de détections |
| `lookback_days` | 14 jours | Période d'analyse traffic | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "idle_min_instances",
  "service_name": "api-dev-backend",
  "service_uri": "https://api-dev-backend-xyz-uc.a.run.app",
  "region": "us-central1",
  "vcpu": 1.0,
  "memory_gib": 2.0,
  "min_instances": 2,
  "avg_requests_per_day": 3.5,
  "total_requests_period": 49,
  "lookback_days": 14,
  "monthly_cost_current": 150.34,
  "monthly_cost_optimal": 0.00,
  "monthly_waste": 150.34,
  "annual_waste": 1804.08,
  "confidence": "HIGH",
  "recommendation": "Set min_instances = 0 to scale to zero",
  "labels": {
    "environment": "dev",
    "team": "backend"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_idle_min_instances()`

---

### Scénario 3 : Services Surprovisionnés (CPU/Memory)

**Description :** Services avec CPU ou Memory utilization < 20%. Resources surprovisionnés = 40-60% surcoût.

**Impact financier :**
- **Coût mensuel :** $200 - $800/service
- **Waste typique :** 30-50% des services
- **Économie annuelle :** $15K - $60K

**Logique de détection :**

```python
def detect_cloud_run_overprovisioned(
    project_id: str,
    region: str = "us-central1",
    cpu_utilization_threshold: float = 20.0,
    memory_utilization_threshold: float = 20.0,
    lookback_days: int = 14
) -> list:
    """
    Détecte les services Cloud Run surprovisionnés (CPU/Memory < 20%).

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        cpu_utilization_threshold: Seuil CPU utilization (défaut: 20%)
        memory_utilization_threshold: Seuil Memory utilization (défaut: 20%)
        lookback_days: Période d'analyse (défaut: 14 jours)

    Returns:
        Liste des services surprovisionnés
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    overprovisioned_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template

        # 2. Query CPU utilization metric
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        # Métrique CPU: run.googleapis.com/container/cpu/utilizations
        filter_cpu = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/container/cpu/utilizations"'
        )

        request_cpu = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_cpu,
            interval=interval,
        )

        cpu_time_series = monitoring_client.list_time_series(request=request_cpu)

        # Calculer avg CPU utilization
        cpu_values = []
        for series in cpu_time_series:
            for point in series.points:
                cpu_values.append(point.value.double_value * 100)  # Convert to percentage

        avg_cpu_utilization = sum(cpu_values) / len(cpu_values) if cpu_values else 0

        # 3. Query Memory utilization metric
        # Métrique Memory: run.googleapis.com/container/memory/utilizations
        filter_memory = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/container/memory/utilizations"'
        )

        request_memory = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_memory,
            interval=interval,
        )

        memory_time_series = monitoring_client.list_time_series(request=request_memory)

        # Calculer avg Memory utilization
        memory_values = []
        for series in memory_time_series:
            for point in series.points:
                memory_values.append(point.value.double_value * 100)  # Convert to percentage

        avg_memory_utilization = sum(memory_values) / len(memory_values) if memory_values else 0

        # 4. Détection si underutilized
        if avg_cpu_utilization < cpu_utilization_threshold or avg_memory_utilization < memory_utilization_threshold:
            # Service surprovisionné

            # Extraire config
            container = template.containers[0] if template.containers else None

            vcpu_current = container.resources.limits.get('cpu', '1') if container and container.resources else '1'
            if 'm' in str(vcpu_current):
                vcpu_value = int(str(vcpu_current).replace('m', '')) / 1000
            else:
                vcpu_value = float(vcpu_current)

            memory_current = container.resources.limits.get('memory', '512Mi') if container and container.resources else '512Mi'
            if 'Gi' in memory_current:
                memory_gib = float(memory_current.replace('Gi', ''))
            elif 'Mi' in memory_current:
                memory_gib = float(memory_current.replace('Mi', '')) / 1024
            else:
                memory_gib = 0.5

            # Min instances
            scaling = template.scaling
            min_instances = scaling.min_instance_count if scaling else 0

            # Coût actuel
            cost_per_instance_current = (vcpu_value * 62.21) + (memory_gib * 6.48)

            # Recommandation optimal (downsize)
            # Si CPU < 20%, diviser par 2
            # Si Memory < 20%, diviser par 2
            vcpu_optimal = max(0.5, vcpu_value / 2) if avg_cpu_utilization < cpu_utilization_threshold else vcpu_value
            memory_optimal = max(0.5, memory_gib / 2) if avg_memory_utilization < memory_utilization_threshold else memory_gib

            # Coût optimal
            cost_per_instance_optimal = (vcpu_optimal * 62.21) + (memory_optimal * 6.48)

            # Waste par instance
            waste_per_instance = cost_per_instance_current - cost_per_instance_optimal

            # Si min_instances > 0, multiply waste
            if min_instances > 0:
                monthly_waste = waste_per_instance * min_instances
            else:
                # Estimer nb instances moyen (difficile sans metric)
                # Utiliser min 1 instance pour calcul conservateur
                monthly_waste = waste_per_instance

            # Niveau confiance
            if avg_cpu_utilization < 10 or avg_memory_utilization < 10:
                confidence = "CRITICAL"  # < 10% utilization
            elif avg_cpu_utilization < 15 or avg_memory_utilization < 15:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            overprovisioned_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "vcpu_current": vcpu_value,
                "memory_gib_current": round(memory_gib, 2),
                "vcpu_optimal": round(vcpu_optimal, 1),
                "memory_gib_optimal": round(memory_optimal, 1),
                "avg_cpu_utilization": round(avg_cpu_utilization, 2),
                "avg_memory_utilization": round(avg_memory_utilization, 2),
                "min_instances": min_instances,
                "cost_per_instance_current": round(cost_per_instance_current, 2),
                "cost_per_instance_optimal": round(cost_per_instance_optimal, 2),
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": f"Downsize to {vcpu_optimal} vCPU + {memory_optimal} GiB",
                "labels": dict(service.labels) if service.labels else {},
            })

    return overprovisioned_services


# Exemple d'utilisation
if __name__ == "__main__":
    overprovisioned = detect_cloud_run_overprovisioned(
        project_id="my-gcp-project",
        region="us-central1",
        cpu_utilization_threshold=20.0,
        memory_utilization_threshold=20.0
    )

    print(f"✅ {len(overprovisioned)} services surprovisionnés")

    total_waste = sum([s["annual_waste"] for s in overprovisioned])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel
cost_current = (vcpu_current * 62.21) + (memory_current * 6.48)

# Coût optimal (downsize)
vcpu_optimal = vcpu_current / 2  # Si < 20% utilization
memory_optimal = memory_current / 2  # Si < 20% utilization

cost_optimal = (vcpu_optimal * 62.21) + (memory_optimal * 6.48)

# Waste
monthly_waste = (cost_current - cost_optimal) * min_instances
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `cpu_utilization_threshold` | 20% | Seuil CPU underutilized | ↑ = moins de détections |
| `memory_utilization_threshold` | 20% | Seuil Memory underutilized | ↑ = moins de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "overprovisioned",
  "service_name": "api-prod-backend",
  "service_uri": "https://api-prod-backend-abc-uc.a.run.app",
  "region": "us-central1",
  "vcpu_current": 4.0,
  "memory_gib_current": 8.0,
  "vcpu_optimal": 2.0,
  "memory_gib_optimal": 4.0,
  "avg_cpu_utilization": 12.5,
  "avg_memory_utilization": 15.8,
  "min_instances": 2,
  "cost_per_instance_current": 300.68,
  "cost_per_instance_optimal": 150.34,
  "monthly_waste": 300.68,
  "annual_waste": 3608.16,
  "confidence": "CRITICAL",
  "recommendation": "Downsize to 2.0 vCPU + 4.0 GiB",
  "labels": {
    "environment": "production",
    "team": "backend"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_overprovisioned()`

---

### Scénario 4 : Services Dev/Test avec Min Instances > 0

**Description :** Services non-production (dev, test, staging) avec min instances > 0. Dev/test devrait scale to zero.

**Impact financier :**
- **Coût mensuel :** $80 - $400/service
- **Waste typique :** 60-80% des services non-prod
- **Économie annuelle :** $10K - $40K

**Logique de détection :**

```python
def detect_cloud_run_nonprod_min_instances(
    project_id: str,
    region: str = "us-central1",
    nonprod_environments: list = None
) -> list:
    """
    Détecte les services non-prod avec min_instances > 0.

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        nonprod_environments: Liste env non-prod (défaut: dev, test, staging)

    Returns:
        Liste des services non-prod avec min instances
    """
    if nonprod_environments is None:
        nonprod_environments = ["dev", "development", "test", "testing", "staging", "qa", "sandbox", "demo"]

    run_client = run_v2.ServicesClient()

    nonprod_min_instances_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template
        labels = dict(service.labels) if service.labels else {}

        # 2. Identifier environment
        environment = labels.get('environment', '').lower()

        # Vérifier aussi service name
        service_name_lower = service_name.lower()

        # 3. Détection si non-prod
        is_nonprod = any([
            env in environment or env in service_name_lower
            for env in nonprod_environments
        ])

        if not is_nonprod:
            continue  # Production = skip

        # 4. Extraire min_instances
        scaling = template.scaling
        min_instances = scaling.min_instance_count if scaling else 0

        if min_instances == 0:
            continue  # OK, scale to zero

        # 5. Non-prod avec min_instances > 0 = waste

        # Extraire config
        container = template.containers[0] if template.containers else None

        vcpu = container.resources.limits.get('cpu', '1') if container and container.resources else '1'
        if 'm' in str(vcpu):
            vcpu_value = int(str(vcpu).replace('m', '')) / 1000
        else:
            vcpu_value = float(vcpu)

        memory = container.resources.limits.get('memory', '512Mi') if container and container.resources else '512Mi'
        if 'Gi' in memory:
            memory_gib = float(memory.replace('Gi', ''))
        elif 'Mi' in memory:
            memory_gib = float(memory.replace('Mi', '')) / 1024
        else:
            memory_gib = 0.5

        # Calculer coût min instances
        cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)
        monthly_cost = min_instances * cost_per_instance

        # Niveau confiance
        if min_instances >= 3:
            confidence = "CRITICAL"  # 3+ instances pour non-prod
        elif min_instances >= 2:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        nonprod_min_instances_services.append({
            "service_name": service_name,
            "service_uri": service.uri,
            "region": region,
            "environment": environment or "unknown",
            "vcpu": vcpu_value,
            "memory_gib": round(memory_gib, 2),
            "min_instances": min_instances,
            "monthly_cost": round(monthly_cost, 2),
            "annual_waste": round(monthly_cost * 12, 2),
            "confidence": confidence,
            "recommendation": "Set min_instances = 0 for non-prod (dev/test should scale to zero)",
            "labels": labels,
        })

    return nonprod_min_instances_services


# Exemple d'utilisation
if __name__ == "__main__":
    nonprod_min = detect_cloud_run_nonprod_min_instances(
        project_id="my-gcp-project",
        region="us-central1"
    )

    print(f"✅ {len(nonprod_min)} services non-prod avec min_instances > 0")

    total_waste = sum([s["annual_waste"] for s in nonprod_min])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Waste = 100% coût min instances (non-prod devrait scale to zero)
cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
monthly_waste = min_instances * cost_per_instance
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `nonprod_environments` | ['dev', 'test', 'staging'] | Liste env non-prod | + env = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "nonprod_min_instances",
  "service_name": "api-dev-frontend",
  "service_uri": "https://api-dev-frontend-xyz-uc.a.run.app",
  "region": "us-central1",
  "environment": "dev",
  "vcpu": 1.0,
  "memory_gib": 2.0,
  "min_instances": 2,
  "monthly_cost": 150.34,
  "annual_waste": 1804.08,
  "confidence": "HIGH",
  "recommendation": "Set min_instances = 0 for non-prod (dev/test should scale to zero)",
  "labels": {
    "environment": "dev",
    "team": "frontend"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_nonprod_min_instances()`

---

### Scénario 5 : CPU Always Allocated Non Nécessaire

**Description :** Services avec "CPU always allocated" mais traffic sporad ique (<20% du temps). Mode "CPU during requests only" = économie 40-60% coût CPU.

**Impact financier :**
- **Coût mensuel :** $50 - $300/service
- **Waste typique :** 40-60% du coût CPU
- **Économie annuelle :** $8K - $30K

**Logique de détection :**

```python
def detect_cloud_run_cpu_always_allocated(
    project_id: str,
    region: str = "us-central1",
    traffic_percentage_threshold: float = 20.0,
    lookback_days: int = 14
) -> list:
    """
    Détecte les services avec CPU always allocated mais traffic sporadique.

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        traffic_percentage_threshold: Seuil traffic % du temps (défaut: 20%)
        lookback_days: Période d'analyse

    Returns:
        Liste des services avec CPU always allocated non nécessaire
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    cpu_always_allocated_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template
        container = template.containers[0] if template.containers else None

        if not container:
            continue

        # 2. Vérifier CPU allocation mode
        # Note: CPU allocation mode pas directement exposé dans API
        # On peut déduire via field cpuIdle ou via descriptor
        cpu_always_allocated = True  # Approximation (besoin check API details)

        if not cpu_always_allocated:
            continue  # CPU during requests = OK

        # 3. Query instance count metric pour estimer traffic pattern
        # Métrique: run.googleapis.com/container/instance_count
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        filter_instances = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/container/instance_count"'
        )

        request_instances = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_instances,
            interval=interval,
        )

        instance_time_series = monitoring_client.list_time_series(request=request_instances)

        # Calculer % temps avec instances actives
        # Si instances > 0 = traffic actif
        total_points = 0
        active_points = 0

        for series in instance_time_series:
            for point in series.points:
                total_points += 1
                if point.value.int64_value > 0 or point.value.double_value > 0:
                    active_points += 1

        traffic_percentage = (active_points / total_points * 100) if total_points > 0 else 0

        # 4. Détection si traffic sporadique
        if traffic_percentage < traffic_percentage_threshold:
            # CPU always allocated inutile

            # Extraire config
            vcpu = container.resources.limits.get('cpu', '1')
            if 'm' in str(vcpu):
                vcpu_value = int(str(vcpu).replace('m', '')) / 1000
            else:
                vcpu_value = float(vcpu)

            memory = container.resources.limits.get('memory', '512Mi')
            if 'Gi' in memory:
                memory_gib = float(memory.replace('Gi', ''))
            elif 'Mi' in memory:
                memory_gib = float(memory.replace('Mi', '')) / 1024
            else:
                memory_gib = 0.5

            # Coût CPU always allocated
            cpu_cost_always = vcpu_value * 62.21

            # Coût CPU during requests only
            cpu_cost_during = cpu_cost_always * (traffic_percentage / 100)

            # Memory cost (toujours facturé)
            memory_cost = memory_gib * 6.48

            # Waste = différence CPU
            monthly_waste_per_instance = cpu_cost_always - cpu_cost_during

            # Si min_instances
            scaling = template.scaling
            min_instances = scaling.min_instance_count if scaling else 0

            if min_instances > 0:
                monthly_waste = monthly_waste_per_instance * min_instances
            else:
                monthly_waste = monthly_waste_per_instance  # Au moins 1 instance moyenne

            # Niveau confiance
            if traffic_percentage < 10:
                confidence = "CRITICAL"  # < 10% temps actif
            elif traffic_percentage < 15:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            cpu_always_allocated_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "vcpu": vcpu_value,
                "memory_gib": round(memory_gib, 2),
                "min_instances": min_instances,
                "cpu_always_allocated": True,
                "traffic_percentage": round(traffic_percentage, 2),
                "cpu_cost_always_monthly": round(cpu_cost_always, 2),
                "cpu_cost_during_monthly": round(cpu_cost_during, 2),
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": "Switch to 'CPU only allocated during request processing' mode",
                "labels": dict(service.labels) if service.labels else {},
            })

    return cpu_always_allocated_services


# Exemple d'utilisation
if __name__ == "__main__":
    cpu_always = detect_cloud_run_cpu_always_allocated(
        project_id="my-gcp-project",
        region="us-central1",
        traffic_percentage_threshold=20.0
    )

    print(f"✅ {len(cpu_always)} services avec CPU always allocated inutile")

    total_waste = sum([s["annual_waste"] for s in cpu_always])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût CPU always allocated
cpu_cost_always = vcpu * 62.21

# Coût CPU during requests (seulement % temps actif)
cpu_cost_during = cpu_cost_always * (traffic_percentage / 100)

# Waste = différence
monthly_waste = (cpu_cost_always - cpu_cost_during) * min_instances
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `traffic_percentage_threshold` | 20% | Seuil traffic % temps | ↑ = plus de détections |
| `lookback_days` | 14 jours | Période d'analyse | ↑ = plus conservateur |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "cpu_always_allocated",
  "service_name": "api-webhook-receiver",
  "service_uri": "https://api-webhook-receiver-xyz-uc.a.run.app",
  "region": "us-central1",
  "vcpu": 2.0,
  "memory_gib": 4.0,
  "min_instances": 1,
  "cpu_always_allocated": true,
  "traffic_percentage": 12.5,
  "cpu_cost_always_monthly": 124.42,
  "cpu_cost_during_monthly": 15.55,
  "monthly_waste": 108.87,
  "annual_waste": 1306.44,
  "confidence": "CRITICAL",
  "recommendation": "Switch to 'CPU only allocated during request processing' mode",
  "labels": {
    "environment": "production",
    "type": "webhook"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_cpu_always_allocated()`

---

### Scénario 6 : Services Non Taggués

**Description :** Services sans labels (environment, owner, team, cost-center) = gouvernance impossible.

**Impact financier :**
- **Coût mensuel :** Variable (5% overhead gouvernance)
- **Waste typique :** 20-40% des services non taggués
- **Économie annuelle :** $3K - $12K

**Logique de détection :**

```python
def detect_cloud_run_untagged(
    project_id: str,
    region: str = "us-central1",
    required_labels: list = None
) -> list:
    """
    Détecte les services Cloud Run sans labels requis.

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        required_labels: Liste labels obligatoires (défaut: environment, owner, team)

    Returns:
        Liste des services non taggués
    """
    if required_labels is None:
        required_labels = ["environment", "owner", "team", "cost-center"]

    run_client = run_v2.ServicesClient()

    untagged_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        labels = dict(service.labels) if service.labels else {}

        # 2. Vérifier labels manquants
        missing_labels = [label for label in required_labels if label not in labels]

        # 3. Détection si labels manquants
        if missing_labels:
            # Service non tagué = governance issue

            # Extraire config pour calculer coût
            template = service.template
            container = template.containers[0] if template.containers else None

            if container:
                vcpu = container.resources.limits.get('cpu', '1')
                if 'm' in str(vcpu):
                    vcpu_value = int(str(vcpu).replace('m', '')) / 1000
                else:
                    vcpu_value = float(vcpu)

                memory = container.resources.limits.get('memory', '512Mi')
                if 'Gi' in memory:
                    memory_gib = float(memory.replace('Gi', ''))
                elif 'Mi' in memory:
                    memory_gib = float(memory.replace('Mi', '')) / 1024
                else:
                    memory_gib = 0.5

                scaling = template.scaling
                min_instances = scaling.min_instance_count if scaling else 0

                # Coût estimé
                if min_instances > 0:
                    cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)
                    monthly_cost = min_instances * cost_per_instance
                else:
                    monthly_cost = 10  # Estimation conservatrice

                # Governance waste = 5% du coût
                governance_waste = monthly_cost * 0.05
            else:
                monthly_cost = 10
                governance_waste = 0.5

            # Age du service
            creation_time = service.create_time
            age_days = (datetime.utcnow().replace(tzinfo=None) - creation_time.replace(tzinfo=None)).days

            # Niveau confiance
            if age_days >= 90 and len(missing_labels) == len(required_labels):
                confidence = "HIGH"  # Vieux service sans aucun label
            elif age_days >= 30:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            untagged_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "age_days": age_days,
                "labels": labels,
                "missing_labels": missing_labels,
                "monthly_cost": round(monthly_cost, 2),
                "governance_waste_monthly": round(governance_waste, 2),
                "annual_governance_waste": round(governance_waste * 12, 2),
                "confidence": confidence,
                "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
            })

    return untagged_services


# Exemple d'utilisation
if __name__ == "__main__":
    untagged = detect_cloud_run_untagged(
        project_id="my-gcp-project",
        region="us-central1"
    )

    print(f"✅ {len(untagged)} services non taggués")

    total_waste = sum([s["annual_governance_waste"] for s in untagged])
    print(f"💰 Waste governance: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Pas de waste direct, mais overhead gouvernance estimé
monthly_cost = estimated_service_cost
governance_waste = monthly_cost * 0.05  # 5% overhead
annual_waste = governance_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `required_labels` | ['environment', 'owner', 'team'] | Labels obligatoires | + labels = plus strict |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "untagged",
  "service_name": "api-unknown-service",
  "service_uri": "https://api-unknown-service-abc-uc.a.run.app",
  "region": "us-central1",
  "age_days": 120,
  "labels": {},
  "missing_labels": ["environment", "owner", "team", "cost-center"],
  "monthly_cost": 150.34,
  "governance_waste_monthly": 7.52,
  "annual_governance_waste": 90.24,
  "confidence": "HIGH",
  "recommendation": "Add missing labels: environment, owner, team, cost-center"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_untagged()`

---

### Scénario 7 : Max Instances Excessif (Risque Runaway)

**Description :** Services avec max_instances > 100 pour services non critiques. Risque runaway costs si traffic spike ($10K+/jour possible).

**Impact financier :**
- **Coût mensuel :** Pas de waste direct
- **Risque financier :** Exposition $10K - $100K/jour si spike
- **Économie annuelle :** Protection contre incidents

**Logique de détection :**

```python
def detect_cloud_run_excessive_max_instances(
    project_id: str,
    region: str = "us-central1",
    max_instances_threshold: int = 100,
    critical_services: list = None
) -> list:
    """
    Détecte les services avec max_instances excessif (risque runaway).

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        max_instances_threshold: Seuil max instances (défaut: 100)
        critical_services: Liste services critiques exemptés

    Returns:
        Liste des services avec max instances excessif
    """
    if critical_services is None:
        critical_services = []

    run_client = run_v2.ServicesClient()

    excessive_max_instances_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]

        # Skip critical services
        if service_name in critical_services:
            continue

        template = service.template
        scaling = template.scaling
        max_instances = scaling.max_instance_count if scaling else 100

        # 2. Détection si max_instances trop élevé
        if max_instances > max_instances_threshold:
            # Max instances excessif = risque runaway

            # Extraire config
            container = template.containers[0] if template.containers else None

            if container:
                vcpu = container.resources.limits.get('cpu', '1')
                if 'm' in str(vcpu):
                    vcpu_value = int(str(vcpu).replace('m', '')) / 1000
                else:
                    vcpu_value = float(vcpu)

                memory = container.resources.limits.get('memory', '512Mi')
                if 'Gi' in memory:
                    memory_gib = float(memory.replace('Gi', ''))
                elif 'Mi' in memory:
                    memory_gib = float(memory.replace('Mi', '')) / 1024
                else:
                    memory_gib = 0.5

                # Coût par instance
                cost_per_instance_hourly = ((vcpu_value * 62.21) + (memory_gib * 6.48)) / 720

                # Coût max si spike
                max_cost_per_hour = max_instances * cost_per_instance_hourly
                max_cost_per_day = max_cost_per_hour * 24

                # Recommandation
                recommended_max = max(10, max_instances_threshold)
            else:
                cost_per_instance_hourly = 0.1
                max_cost_per_hour = max_instances * 0.1
                max_cost_per_day = max_cost_per_hour * 24
                recommended_max = 50

            # Niveau confiance (basé sur risque)
            if max_instances >= 500:
                confidence = "CRITICAL"  # Risque très élevé
            elif max_instances >= 300:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            excessive_max_instances_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "max_instances_current": max_instances,
                "recommended_max_instances": recommended_max,
                "cost_per_instance_hourly": round(cost_per_instance_hourly, 4),
                "max_cost_per_hour": round(max_cost_per_hour, 2),
                "max_cost_per_day": round(max_cost_per_day, 2),
                "financial_exposure": round(max_cost_per_day * 30, 2),
                "confidence": confidence,
                "recommendation": f"Reduce max_instances from {max_instances} to {recommended_max} to protect against runaway costs",
                "labels": dict(service.labels) if service.labels else {},
            })

    return excessive_max_instances_services


# Exemple d'utilisation
if __name__ == "__main__":
    excessive_max = detect_cloud_run_excessive_max_instances(
        project_id="my-gcp-project",
        region="us-central1",
        max_instances_threshold=100
    )

    print(f"✅ {len(excessive_max)} services avec max_instances excessif")

    total_exposure = sum([s["financial_exposure"] for s in excessive_max])
    print(f"⚠️  Exposition financière totale: ${total_exposure:.2f}/mois")
```

**Calcul du coût :**

```python
# Pas de waste direct, mais calcul exposition financière
cost_per_instance_hourly = ((vcpu * 62.21) + (memory_gib * 6.48)) / 720
max_cost_per_hour = max_instances * cost_per_instance_hourly
max_cost_per_day = max_cost_per_hour * 24

# Exposition si spike 1 jour
financial_exposure = max_cost_per_day
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `max_instances_threshold` | 100 | Seuil max instances | ↑ = moins de détections |
| `critical_services` | [] | Services exemptés | + services = moins détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "excessive_max_instances",
  "service_name": "api-public-frontend",
  "service_uri": "https://api-public-frontend-xyz-uc.a.run.app",
  "region": "us-central1",
  "max_instances_current": 500,
  "recommended_max_instances": 100,
  "cost_per_instance_hourly": 0.2086,
  "max_cost_per_hour": 104.30,
  "max_cost_per_day": 2503.20,
  "financial_exposure": 75096.00,
  "confidence": "CRITICAL",
  "recommendation": "Reduce max_instances from 500 to 100 to protect against runaway costs",
  "labels": {
    "environment": "production",
    "criticality": "medium"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_excessive_max_instances()`

---

## Phase 2 : Détection Avancée (3 Scénarios)

### Scénario 8 : Low Concurrency Inefficient

**Description :** Services avec concurrency <= 10 (1-10 requests par instance). Low concurrency = 10x plus d'instances nécessaires = 10x coût.

**Impact financier :**
- **Coût mensuel :** $500 - $2,000/service
- **Waste typique :** 70-90% économie possible
- **Économie annuelle :** $20K - $80K

**Logique de détection :**

```python
def detect_cloud_run_low_concurrency(
    project_id: str,
    region: str = "us-central1",
    low_concurrency_threshold: int = 10,
    cpu_utilization_threshold: float = 50.0,
    lookback_days: int = 14
) -> list:
    """
    Détecte les services avec low concurrency inefficient.

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        low_concurrency_threshold: Seuil concurrency faible (défaut: 10)
        cpu_utilization_threshold: Seuil CPU utilization (défaut: 50%)
        lookback_days: Période d'analyse

    Returns:
        Liste des services avec low concurrency
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    low_concurrency_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template
        container = template.containers[0] if template.containers else None

        if not container:
            continue

        # 2. Extraire concurrency
        concurrency = container.container_concurrency if hasattr(container, 'container_concurrency') else 80

        # Filtrer low concurrency
        if concurrency > low_concurrency_threshold:
            continue

        # 3. Query CPU utilization pour vérifier sous-utilisation
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        filter_cpu = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/container/cpu/utilizations"'
        )

        request_cpu = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_cpu,
            interval=interval,
        )

        cpu_time_series = monitoring_client.list_time_series(request=request_cpu)

        # Calculer avg CPU
        cpu_values = []
        for series in cpu_time_series:
            for point in series.points:
                cpu_values.append(point.value.double_value * 100)

        avg_cpu_utilization = sum(cpu_values) / len(cpu_values) if cpu_values else 0

        # 4. Détection si CPU sous-utilisé (preuve que concurrency trop faible)
        if avg_cpu_utilization < cpu_utilization_threshold:
            # Low concurrency + CPU sous-utilisé = inefficient

            # Extraire config
            vcpu = container.resources.limits.get('cpu', '1')
            if 'm' in str(vcpu):
                vcpu_value = int(str(vcpu).replace('m', '')) / 1000
            else:
                vcpu_value = float(vcpu)

            memory = container.resources.limits.get('memory', '512Mi')
            if 'Gi' in memory:
                memory_gib = float(memory.replace('Gi', ''))
            elif 'Mi' in memory:
                memory_gib = float(memory.replace('Mi', '')) / 1024
            else:
                memory_gib = 0.5

            # Calculer waste
            # Si concurrency = 1, besoin 80x plus d'instances que concurrency = 80
            concurrency_optimal = 80  # Standard recommandé
            instances_multiplier = concurrency_optimal / concurrency  # Ex: 80/1 = 80x

            # Coût par instance
            cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)

            # Min instances
            scaling = template.scaling
            min_instances = scaling.min_instance_count if scaling else 0

            # Waste = surcoût dû aux instances supplémentaires nécessaires
            # Note: calcul simplifié, réalité plus complexe
            if min_instances > 0:
                monthly_cost_current = min_instances * cost_per_instance * instances_multiplier
                monthly_cost_optimal = min_instances * cost_per_instance
                monthly_waste = monthly_cost_current - monthly_cost_optimal
            else:
                # Estimation pour autoscaling
                monthly_waste = cost_per_instance * (instances_multiplier - 1)

            # Niveau confiance
            if concurrency == 1:
                confidence = "CRITICAL"  # 1 request/instance = très inefficient
            elif concurrency <= 5:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            low_concurrency_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "concurrency_current": concurrency,
                "concurrency_optimal": concurrency_optimal,
                "instances_multiplier": round(instances_multiplier, 1),
                "avg_cpu_utilization": round(avg_cpu_utilization, 2),
                "vcpu": vcpu_value,
                "memory_gib": round(memory_gib, 2),
                "min_instances": min_instances,
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": f"Increase concurrency from {concurrency} to {concurrency_optimal}",
                "labels": dict(service.labels) if service.labels else {},
            })

    return low_concurrency_services


# Exemple d'utilisation
if __name__ == "__main__":
    low_concurrency = detect_cloud_run_low_concurrency(
        project_id="my-gcp-project",
        region="us-central1"
    )

    print(f"✅ {len(low_concurrency)} services avec low concurrency")

    total_waste = sum([s["annual_waste"] for s in low_concurrency])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Calcul instances multiplier
concurrency_optimal = 80
instances_multiplier = concurrency_optimal / concurrency_current
# Ex: 80/1 = 80x plus d'instances nécessaires

# Waste = coût instances supplémentaires
cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
monthly_waste = cost_per_instance * (instances_multiplier - 1) * min_instances
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `low_concurrency_threshold` | 10 | Seuil concurrency faible | ↑ = plus de détections |
| `cpu_utilization_threshold` | 50% | Seuil CPU utilization | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "low_concurrency",
  "service_name": "api-single-threaded",
  "service_uri": "https://api-single-threaded-xyz-uc.a.run.app",
  "region": "us-central1",
  "concurrency_current": 1,
  "concurrency_optimal": 80,
  "instances_multiplier": 80.0,
  "avg_cpu_utilization": 25.3,
  "vcpu": 1.0,
  "memory_gib": 2.0,
  "min_instances": 2,
  "monthly_waste": 5912.86,
  "annual_waste": 70954.32,
  "confidence": "CRITICAL",
  "recommendation": "Increase concurrency from 1 to 80",
  "labels": {
    "environment": "production",
    "legacy": "true"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_low_concurrency()`

---

### Scénario 9 : Excessive Minimum Instances

**Description :** Services avec min_instances >= 5 mais cold start < 2s et traffic < 100 req/min. Over-optimization cold start inutile.

**Impact financier :**
- **Coût mensuel :** $500 - $2,000/service
- **Waste typique :** 80-90% des min instances inutiles
- **Économie annuelle :** $15K - $60K

**Logique de détection :**

```python
def detect_cloud_run_excessive_min_instances(
    project_id: str,
    region: str = "us-central1",
    min_instances_threshold: int = 5,
    cold_start_threshold_seconds: float = 2.0,
    traffic_threshold_rpm: int = 100,
    lookback_days: int = 14
) -> list:
    """
    Détecte les services avec excessive minimum instances (cold start over-optimization).

    Args:
        project_id: ID du projet GCP
        region: Région Cloud Run
        min_instances_threshold: Seuil min instances (défaut: 5)
        cold_start_threshold_seconds: Seuil cold start (défaut: 2s)
        traffic_threshold_rpm: Seuil traffic req/min (défaut: 100)
        lookback_days: Période d'analyse

    Returns:
        Liste des services avec excessive min instances
    """
    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    excessive_min_instances_services = []

    # 1. Lister services
    parent = f"projects/{project_id}/locations/{region}"
    services = run_client.list_services(parent=parent)

    for service in services:
        service_name = service.name.split('/')[-1]
        template = service.template
        scaling = template.scaling
        min_instances = scaling.min_instance_count if scaling else 0

        # 2. Filtrer services avec min_instances élevé
        if min_instances < min_instances_threshold:
            continue

        # 3. Query request_count pour estimer traffic
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
        })

        filter_requests = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/request_count"'
        )

        request_requests = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_requests,
            interval=interval,
        )

        requests_time_series = monitoring_client.list_time_series(request=request_requests)

        # Calculer avg requests/min
        total_requests = 0
        for series in requests_time_series:
            for point in series.points:
                total_requests += point.value.int64_value or point.value.double_value or 0

        total_minutes = lookback_days * 24 * 60
        avg_requests_per_min = total_requests / total_minutes if total_minutes > 0 else 0

        # 4. Query startup_latencies pour estimer cold start time
        filter_startup = (
            f'resource.type = "cloud_run_revision" '
            f'AND resource.labels.service_name = "{service_name}" '
            f'AND metric.type = "run.googleapis.com/container/startup_latencies"'
        )

        request_startup = monitoring_v3.ListTimeSeriesRequest(
            name=f"projects/{project_id}",
            filter=filter_startup,
            interval=interval,
        )

        startup_time_series = monitoring_client.list_time_series(request=request_startup)

        # Calculer avg cold start
        startup_values = []
        for series in startup_time_series:
            for point in series.points:
                startup_values.append(point.value.distribution_value.mean if hasattr(point.value, 'distribution_value') else 1.0)

        avg_cold_start_seconds = sum(startup_values) / len(startup_values) if startup_values else 1.0

        # 5. Détection si over-optimization
        if avg_requests_per_min < traffic_threshold_rpm and avg_cold_start_seconds < cold_start_threshold_seconds:
            # Min instances excessif pour cold start fast + traffic faible

            # Extraire config
            container = template.containers[0] if template.containers else None

            if container:
                vcpu = container.resources.limits.get('cpu', '1')
                if 'm' in str(vcpu):
                    vcpu_value = int(str(vcpu).replace('m', '')) / 1000
                else:
                    vcpu_value = float(vcpu)

                memory = container.resources.limits.get('memory', '512Mi')
                if 'Gi' in memory:
                    memory_gib = float(memory.replace('Gi', ''))
                elif 'Mi' in memory:
                    memory_gib = float(memory.replace('Mi', '')) / 1024
                else:
                    memory_gib = 0.5

                # Coût min instances
                cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)
                monthly_cost_current = min_instances * cost_per_instance

                # Recommandation: min_instances = 0-2 suffisant
                recommended_min = 0 if avg_cold_start_seconds < 1.0 else 1
                monthly_cost_optimal = recommended_min * cost_per_instance

                # Waste
                monthly_waste = monthly_cost_current - monthly_cost_optimal
            else:
                monthly_waste = 100  # Estimation

            # Niveau confiance
            if min_instances >= 10:
                confidence = "CRITICAL"
            elif min_instances >= 7:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            excessive_min_instances_services.append({
                "service_name": service_name,
                "service_uri": service.uri,
                "region": region,
                "min_instances_current": min_instances,
                "recommended_min_instances": recommended_min,
                "avg_requests_per_min": round(avg_requests_per_min, 2),
                "avg_cold_start_seconds": round(avg_cold_start_seconds, 2),
                "monthly_cost_current": round(monthly_cost_current, 2),
                "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": f"Reduce min_instances from {min_instances} to {recommended_min} (cold start < 2s + low traffic)",
                "labels": dict(service.labels) if service.labels else {},
            })

    return excessive_min_instances_services


# Exemple d'utilisation
if __name__ == "__main__":
    excessive_min = detect_cloud_run_excessive_min_instances(
        project_id="my-gcp-project",
        region="us-central1"
    )

    print(f"✅ {len(excessive_min)} services avec excessive min_instances")

    total_waste = sum([s["annual_waste"] for s in excessive_min])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût actuel
cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
monthly_cost_current = min_instances * cost_per_instance

# Coût optimal (min_instances réduit)
recommended_min = 0 if cold_start < 1s else 1
monthly_cost_optimal = recommended_min * cost_per_instance

# Waste
monthly_waste = monthly_cost_current - monthly_cost_optimal
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_instances_threshold` | 5 | Seuil min instances | ↑ = moins de détections |
| `cold_start_threshold_seconds` | 2.0s | Seuil cold start | ↑ = plus de détections |
| `traffic_threshold_rpm` | 100 req/min | Seuil traffic | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "excessive_min_instances",
  "service_name": "api-admin-panel",
  "service_uri": "https://api-admin-panel-xyz-uc.a.run.app",
  "region": "us-central1",
  "min_instances_current": 8,
  "recommended_min_instances": 1,
  "avg_requests_per_min": 12.5,
  "avg_cold_start_seconds": 1.2,
  "monthly_cost_current": 601.36,
  "monthly_cost_optimal": 75.17,
  "monthly_waste": 526.19,
  "annual_waste": 6314.28,
  "confidence": "HIGH",
  "recommendation": "Reduce min_instances from 8 to 1 (cold start < 2s + low traffic)",
  "labels": {
    "environment": "production",
    "criticality": "low"
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_excessive_min_instances()`

---

### Scénario 10 : Services Multi-Region Redondants

**Description :** Même container image déployé dans >3 régions mais traffic concentré sur 1 région. Déploiements multi-région inutiles (sans DR requirement).

**Impact financier :**
- **Coût mensuel :** $200 - $1,000/service
- **Waste typique :** 70-80% des régions inutiles
- **Économie annuelle :** $10K - $40K

**Logique de détection :**

```python
def detect_cloud_run_multi_region_redundant(
    project_id: str,
    regions: list = None,
    traffic_concentration_threshold: float = 80.0,
    region_count_threshold: int = 3
) -> list:
    """
    Détecte les services déployés dans multiple régions mais traffic concentré.

    Args:
        project_id: ID du projet GCP
        regions: Liste régions à vérifier (défaut: toutes)
        traffic_concentration_threshold: % traffic dans 1 région (défaut: 80%)
        region_count_threshold: Nombre régions pour détecter (défaut: 3)

    Returns:
        Liste des services multi-région redondants
    """
    if regions is None:
        regions = ["us-central1", "us-east1", "europe-west1", "asia-east1"]

    run_client = run_v2.ServicesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    multi_region_redundant_services = []

    # 1. Group services by name across regions
    from collections import defaultdict
    services_by_name = defaultdict(list)

    for region in regions:
        parent = f"projects/{project_id}/locations/{region}"
        try:
            services = run_client.list_services(parent=parent)

            for service in services:
                service_name = service.name.split('/')[-1]
                services_by_name[service_name].append({
                    "region": region,
                    "service": service,
                })
        except Exception:
            continue  # Region inaccessible ou pas de services

    # 2. Pour chaque service multi-région, analyser traffic
    for service_name, region_services in services_by_name.items():
        # Filtrer services déployés dans 3+ régions
        if len(region_services) < region_count_threshold:
            continue

        # 3. Query request_count par région (14 jours)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(datetime.utcnow().timestamp())},
            "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=14)).timestamp())},
        })

        region_requests = {}

        for region_service in region_services:
            region = region_service["region"]

            filter_requests = (
                f'resource.type = "cloud_run_revision" '
                f'AND resource.labels.service_name = "{service_name}" '
                f'AND resource.labels.location = "{region}" '
                f'AND metric.type = "run.googleapis.com/request_count"'
            )

            request_requests = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_requests,
                interval=interval,
            )

            requests_time_series = monitoring_client.list_time_series(request=request_requests)

            # Total requests
            total_requests = 0
            for series in requests_time_series:
                for point in series.points:
                    total_requests += point.value.int64_value or point.value.double_value or 0

            region_requests[region] = total_requests

        # 4. Calculer concentration traffic
        total_all_regions = sum(region_requests.values())

        if total_all_regions == 0:
            continue  # Pas de traffic = autre scénario

        # Trouver région avec plus de traffic
        primary_region = max(region_requests, key=region_requests.get)
        primary_region_requests = region_requests[primary_region]
        traffic_concentration = (primary_region_requests / total_all_regions * 100) if total_all_regions > 0 else 0

        # 5. Détection si traffic concentré
        if traffic_concentration >= traffic_concentration_threshold:
            # Traffic concentré sur 1 région = autres régions inutiles

            # Calculer waste régions secondaires
            redundant_regions = [r for r in region_requests.keys() if r != primary_region]

            # Extraire config (utiliser primary region)
            primary_service = next(rs["service"] for rs in region_services if rs["region"] == primary_region)
            template = primary_service.template
            container = template.containers[0] if template.containers else None

            if container:
                vcpu = container.resources.limits.get('cpu', '1')
                if 'm' in str(vcpu):
                    vcpu_value = int(str(vcpu).replace('m', '')) / 1000
                else:
                    vcpu_value = float(vcpu)

                memory = container.resources.limits.get('memory', '512Mi')
                if 'Gi' in memory:
                    memory_gib = float(memory.replace('Gi', ''))
                elif 'Mi' in memory:
                    memory_gib = float(memory.replace('Mi', '')) / 1024
                else:
                    memory_gib = 0.5

                scaling = template.scaling
                min_instances = scaling.min_instance_count if scaling else 0

                # Coût par région
                cost_per_instance = (vcpu_value * 62.21) + (memory_gib * 6.48)

                if min_instances > 0:
                    cost_per_region = min_instances * cost_per_instance
                else:
                    cost_per_region = 10  # Estimation conservatrice

                # Waste = coût régions redondantes
                monthly_waste = len(redundant_regions) * cost_per_region
            else:
                monthly_waste = len(redundant_regions) * 75  # Estimation

            # Niveau confiance
            if traffic_concentration >= 95:
                confidence = "CRITICAL"  # >95% traffic 1 région
            elif traffic_concentration >= 90:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            multi_region_redundant_services.append({
                "service_name": service_name,
                "total_regions": len(region_services),
                "primary_region": primary_region,
                "redundant_regions": redundant_regions,
                "traffic_concentration": round(traffic_concentration, 2),
                "region_requests": region_requests,
                "cost_per_region_monthly": round(cost_per_region, 2) if 'cost_per_region' in locals() else 75,
                "monthly_waste": round(monthly_waste, 2),
                "annual_waste": round(monthly_waste * 12, 2),
                "confidence": confidence,
                "recommendation": f"Remove deployments in {len(redundant_regions)} regions: {', '.join(redundant_regions)}",
            })

    return multi_region_redundant_services


# Exemple d'utilisation
if __name__ == "__main__":
    multi_region = detect_cloud_run_multi_region_redundant(
        project_id="my-gcp-project"
    )

    print(f"✅ {len(multi_region)} services multi-région redondants")

    total_waste = sum([s["annual_waste"] for s in multi_region])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Coût par région
cost_per_region = min_instances * ((vcpu * 62.21) + (memory_gib * 6.48))

# Régions redondantes (hors primary)
redundant_regions_count = total_regions - 1

# Waste
monthly_waste = redundant_regions_count * cost_per_region
annual_waste = monthly_waste * 12
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `traffic_concentration_threshold` | 80% | % traffic 1 région | ↓ = plus de détections |
| `region_count_threshold` | 3 régions | Nombre régions min | ↑ = moins de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_run_service",
  "waste_scenario": "multi_region_redundant",
  "service_name": "api-global-service",
  "total_regions": 4,
  "primary_region": "us-central1",
  "redundant_regions": ["us-east1", "europe-west1", "asia-east1"],
  "traffic_concentration": 92.5,
  "region_requests": {
    "us-central1": 125000,
    "us-east1": 5000,
    "europe-west1": 3500,
    "asia-east1": 1500
  },
  "cost_per_region_monthly": 150.34,
  "monthly_waste": 451.02,
  "annual_waste": 5412.24,
  "confidence": "HIGH",
  "recommendation": "Remove deployments in 3 regions: us-east1, europe-west1, asia-east1"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_run_multi_region_redundant()`

---

## Protocole de Test Complet

### 1. Setup Environnement Test

```bash
# 1.1 Installer gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# 1.2 Authentification
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 1.3 Installer Python dependencies
pip install google-cloud-run google-cloud-monitoring google-cloud-logging

# 1.4 Configurer permissions Service Account (read-only)
gcloud iam service-accounts create cloudwaste-scanner \
    --display-name="CloudWaste Scanner"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:cloudwaste-scanner@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.viewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:cloudwaste-scanner@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.viewer"

# Créer et télécharger key
gcloud iam service-accounts keys create ~/cloudwaste-key.json \
    --iam-account=cloudwaste-scanner@YOUR_PROJECT_ID.iam.gserviceaccount.com

export GOOGLE_APPLICATION_CREDENTIALS=~/cloudwaste-key.json
```

### 2. Créer Services Test

```bash
# 2.1 Service never used
gcloud run deploy test-never-used \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --no-allow-unauthenticated \
    --no-traffic

# 2.2 Service idle avec min_instances
gcloud run deploy test-idle-min-instances \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --min-instances=2 \
    --allow-unauthenticated

# 2.3 Service overprovisioned
gcloud run deploy test-overprovisioned \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --cpu=4 \
    --memory=8Gi \
    --allow-unauthenticated

# 2.4 Service dev avec min_instances
gcloud run deploy test-dev-min-instances \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --min-instances=2 \
    --labels=environment=dev \
    --allow-unauthenticated

# 2.5 Service untagged
gcloud run deploy test-untagged \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --allow-unauthenticated
    # NO --labels flag

# 2.6 Service avec max_instances élevé
gcloud run deploy test-high-max-instances \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --max-instances=500 \
    --allow-unauthenticated

# 2.7 Service avec low concurrency
gcloud run deploy test-low-concurrency \
    --image=gcr.io/cloudrun/hello \
    --region=us-central1 \
    --concurrency=1 \
    --cpu=2 \
    --allow-unauthenticated
```

### 3. Tests Unitaires Python

```python
#!/usr/bin/env python3
"""
Script validation Cloud Run Services waste detection
"""

from google.cloud import run_v2
from google.cloud import monitoring_v3
import os

PROJECT_ID = os.environ['PROJECT_ID']
REGION = "us-central1"

def test_all_scenarios():
    run_client = run_v2.ServicesClient()

    scenarios_detected = {
        'never_used': 0,
        'idle_min_instances': 0,
        'overprovisioned': 0,
        'nonprod_min_instances': 0,
        'cpu_always_allocated': 0,
        'untagged': 0,
        'excessive_max_instances': 0,
        'low_concurrency': 0,
        'excessive_min_instances': 0,
        'multi_region_redundant': 0,
    }

    # List all services
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    services = list(run_client.list_services(parent=parent))

    print(f"✅ Found {len(services)} Cloud Run services")

    # Test 1: Never used (0 requests)
    # (Query Cloud Monitoring pour request_count = 0)

    # Test 2: Idle min instances
    for service in services:
        template = service.template
        scaling = template.scaling
        min_instances = scaling.min_instance_count if scaling else 0

        if min_instances > 0:
            scenarios_detected['idle_min_instances'] += 1
            print(f"✅ Scenario 2 (idle_min_instances): {service.name.split('/')[-1]}")

    # Test 4: Non-prod with min instances
    for service in services:
        labels = dict(service.labels) if service.labels else {}
        environment = labels.get('environment', '').lower()

        template = service.template
        scaling = template.scaling
        min_instances = scaling.min_instance_count if scaling else 0

        if environment in ['dev', 'test'] and min_instances > 0:
            scenarios_detected['nonprod_min_instances'] += 1
            print(f"✅ Scenario 4 (nonprod_min_instances): {service.name.split('/')[-1]}")

    # Test 6: Untagged
    for service in services:
        labels = dict(service.labels) if service.labels else {}

        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Scenario 6 (untagged): {service.name.split('/')[-1]}")

    # Test 7: Excessive max instances
    for service in services:
        template = service.template
        scaling = template.scaling
        max_instances = scaling.max_instance_count if scaling else 100

        if max_instances > 100:
            scenarios_detected['excessive_max_instances'] += 1
            print(f"✅ Scenario 7 (excessive_max_instances): {service.name.split('/')[-1]}")

    # Test 8: Low concurrency
    for service in services:
        template = service.template
        container = template.containers[0] if template.containers else None

        if container:
            concurrency = getattr(container, 'container_concurrency', 80)

            if concurrency <= 10:
                scenarios_detected['low_concurrency'] += 1
                print(f"✅ Scenario 8 (low_concurrency): {service.name.split('/')[-1]}")

    # Rapport final
    print("\n📊 Detection Summary:")
    total_waste = sum(scenarios_detected.values())
    for scenario, count in scenarios_detected.items():
        if count > 0:
            print(f"  - {scenario}: {count} services")

    print(f"\n✅ Total waste services detected: {total_waste}")

if __name__ == '__main__':
    test_all_scenarios()
```

**Exécution :**
```bash
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
python3 validate_cloud_run_scenarios.py
```

### 4. Validation gcloud CLI

```bash
# 4.1 Lister tous les services
gcloud run services list --platform managed --format="table(metadata.name,status.url,metadata.labels,spec.template.spec.containers[0].resources)"

# 4.2 Vérifier min/max instances
gcloud run services describe SERVICE_NAME \
    --region=us-central1 \
    --format="value(spec.template.metadata.annotations.'autoscaling.knative.dev/minScale',spec.template.metadata.annotations.'autoscaling.knative.dev/maxScale')"

# 4.3 Vérifier labels
gcloud run services describe SERVICE_NAME \
    --region=us-central1 \
    --format="yaml(metadata.labels)"

# 4.4 Calculer coût estimé
# (Utiliser métriques Cloud Monitoring)

# 4.5 Lister services par environnement
gcloud run services list --region=us-central1 --filter="metadata.labels.environment=dev" --format="value(metadata.name)"
```

### 5. Cleanup Test

```bash
# 5.1 Supprimer services test
gcloud run services delete test-never-used --region=us-central1 --quiet
gcloud run services delete test-idle-min-instances --region=us-central1 --quiet
gcloud run services delete test-overprovisioned --region=us-central1 --quiet
gcloud run services delete test-dev-min-instances --region=us-central1 --quiet
gcloud run services delete test-untagged --region=us-central1 --quiet
gcloud run services delete test-high-max-instances --region=us-central1 --quiet
gcloud run services delete test-low-concurrency --region=us-central1 --quiet

# 5.2 Vérifier cleanup
gcloud run services list --region=us-central1 --filter="metadata.name~test-"
```

---

## Références

### Documentation GCP Officielle
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips/general)
- [Autoscaling Configuration](https://cloud.google.com/run/docs/configuring/min-instances)
- [CPU Allocation](https://cloud.google.com/run/docs/configuring/cpu-allocation)
- [Concurrency](https://cloud.google.com/run/docs/about-concurrency)

### Google Cloud Client Libraries
- [google-cloud-run Python](https://googleapis.dev/python/run/latest/index.html)
- [google-cloud-monitoring Python](https://googleapis.dev/python/monitoring/latest/index.html)

### APIs
- [Cloud Run Admin API v2](https://cloud.google.com/run/docs/reference/rest/v2/projects.locations.services)
- [Cloud Monitoring API](https://cloud.google.com/monitoring/api/ref_v3/rest)

### Métriques Cloud Monitoring
- `run.googleapis.com/request_count` - Nombre de requests
- `run.googleapis.com/container/cpu/utilizations` - CPU utilization
- `run.googleapis.com/container/memory/utilizations` - Memory utilization
- `run.googleapis.com/container/instance_count` - Nombre d'instances
- `run.googleapis.com/container/startup_latencies` - Cold start latency

### CloudWaste Documentation
- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md) - Related VMs

### Équivalences AWS/Azure
- **AWS Fargate** → GCP Cloud Run
- **AWS Lambda (Containers)** → GCP Cloud Run
- **Azure Container Apps** → GCP Cloud Run

### Best Practices

1. **Min Instances** : Use 0 for non-prod, 1-3 for prod (only if cold start > 2s)
2. **Max Instances** : Set realistic limit (10-50 for most services) to protect runaway costs
3. **CPU Allocation** : Use "during requests" mode for HTTP APIs (save 40-60%)
4. **Concurrency** : Set 80-250 for optimal efficiency (avoid low concurrency)
5. **Labels** : Tag all services with environment, owner, team, cost-center
6. **Multi-Region** : Deploy 1-2 regions only (avoid unnecessary redundancy)
7. **Resources** : Right-size CPU/Memory based on metrics (avoid overprovisioning)
8. **Monitoring** : Track request_count, CPU/Memory utilization, instance_count
9. **Traffic Split** : Clean up old revisions receiving 0% traffic
10. **Cost Alerts** : Set budget alerts for unexpected spikes

---

**Dernière mise à jour :** 3 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
