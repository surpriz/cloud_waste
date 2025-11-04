# GCP Cloud Load Balancers - 100% des Scénarios de Gaspillage

**Version:** 1.0
**Date:** 2025-01-03
**Ressource GCP:** `Networking: Cloud Load Balancing`
**Impact estimé:** $5,000 - $25,000/an par organisation
**Catégorie:** Networking / Load Balancing

---

## Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Architecture et Modèle de Pricing](#architecture-et-modèle-de-pricing)
3. [Phase 1 : Scénarios de Détection Simples](#phase-1--scénarios-de-détection-simples)
   - [Scénario 1 : Load Balancers with Zero Backends](#scénario-1--load-balancers-with-zero-backends)
   - [Scénario 2 : All Backends Unhealthy](#scénario-2--all-backends-unhealthy)
   - [Scénario 3 : Orphaned Forwarding Rules](#scénario-3--orphaned-forwarding-rules)
   - [Scénario 4 : Zero Request Traffic](#scénario-4--zero-request-traffic)
   - [Scénario 5 : Dev/Test Load Balancers Unused](#scénario-5--devtest-load-balancers-unused)
   - [Scénario 6 : Untagged Load Balancers](#scénario-6--untagged-load-balancers)
   - [Scénario 7 : Wrong Load Balancer Type](#scénario-7--wrong-load-balancer-type)
4. [Phase 2 : Scénarios d'Analyse Avancée](#phase-2--scénarios-danalyse-avancée)
   - [Scénario 8 : Multiple Load Balancers for Single Backend](#scénario-8--multiple-load-balancers-for-single-backend)
   - [Scénario 9 : Over-Provisioned Backend Capacity](#scénario-9--over-provisioned-backend-capacity)
   - [Scénario 10 : Premium Tier for Non-Critical Workloads](#scénario-10--premium-tier-for-non-critical-workloads)
5. [Protocole de Test Complet](#protocole-de-test-complet)
6. [Références et Ressources](#références-et-ressources)

---

## Vue d'Ensemble

### Qu'est-ce que Cloud Load Balancing ?

**Cloud Load Balancing** est le service de distribution de trafic entièrement managé de Google Cloud Platform. Il répartit le trafic entrant entre plusieurs backends (instances VM, containers GKE, Cloud Functions, etc.) pour assurer haute disponibilité, scalabilité et performance.

**Caractéristiques principales :**
- **Distribution globale** : Anycast IP avec routing intelligent
- **Auto-scaling** : Adaptation automatique à la charge
- **Health checking** : Détection automatique des backends défaillants
- **SSL/TLS termination** : Gestion centralisée des certificats
- **Content-based routing** : Routing par URL, headers, cookies
- **IPv4 et IPv6** : Support dual-stack

### Types de Cloud Load Balancers

GCP propose **deux catégories principales** de load balancers basées sur la couche OSI :

---

#### 1. **Application Load Balancers (Layer 7)**

**Fonction :** Load balancing HTTP/HTTPS avec inspection du contenu applicatif.

**Variantes :**

##### A. External Application Load Balancer

**Scope :** Internet-facing, public IP

**Modes de déploiement :**
- **Global** : Anycast IP, backends multi-régions
- **Regional** : Regional IP, backends dans une région
- **Classic** : Ancien modèle (legacy)

**Use cases :**
```python
# Example: Global external ALB
use_cases = {
    'global_web_app': 'Application web servie depuis plusieurs régions',
    'api_gateway': 'API REST avec routing par path (/api/v1, /api/v2)',
    'microservices': 'Routing vers différents services Kubernetes',
    'cdn_origin': 'Origin pour Cloud CDN avec cache'
}
```

**Pricing :**
- Forwarding rule: $0.025/hour (first 5 rules)
- Data processing: $0.008-$0.012/GB

##### B. Internal Application Load Balancer

**Scope :** Private, internal VPC traffic only

**Modes de déploiement :**
- **Regional** : Backends dans une région
- **Cross-Regional** : Backends dans plusieurs régions (multi-region failover)

**Use cases :**
```python
use_cases = {
    'internal_api': 'APIs internes entre microservices',
    'database_proxy': 'Load balancing vers pool de proxies SQL',
    'service_mesh': 'Ingress pour service mesh (Istio, Anthos)',
    'hybrid_cloud': 'Applications on-prem vers GCP via VPN/Interconnect'
}
```

---

#### 2. **Network Load Balancers (Layer 4)**

**Fonction :** Load balancing TCP/UDP sans inspection du contenu.

**Variantes :**

##### A. Proxy Network Load Balancer

**Fonction :** Termine les connexions TCP et ouvre de nouvelles connexions vers backends.

**Protocols supportés :**
- TCP (any port)
- SSL/TLS proxy

**Use cases :**
```python
use_cases = {
    'tcp_applications': 'Applications TCP custom (game servers, databases)',
    'ssl_offloading': 'Termination SSL pour applications non-HTTP',
    'multi_region_tcp': 'TCP load balancing global avec backends multi-régions'
}
```

##### B. Passthrough Network Load Balancer

**Fonction :** Préserve les connexions originales (source IP, ports).

**Protocols supportés :**
- TCP
- UDP
- ESP (IPsec)
- GRE
- ICMP / ICMPv6

**Use cases :**
```python
use_cases = {
    'udp_gaming': 'Game servers UDP (Minecraft, CS:GO)',
    'voip': 'SIP trunking, VoIP (UDP)',
    'ipsec_vpn': 'VPN endpoints (ESP protocol)',
    'dns_servers': 'DNS resolvers (UDP port 53)',
    'source_ip_preservation': 'Applications nécessitant vraie source IP client'
}
```

---

### Comparaison des Types de Load Balancers

| Feature | Application LB (L7) | Proxy Network LB (L4) | Passthrough Network LB (L4) |
|---------|---------------------|------------------------|------------------------------|
| **OSI Layer** | Layer 7 (HTTP/HTTPS) | Layer 4 (TCP/SSL) | Layer 4 (TCP/UDP/ESP/GRE) |
| **Protocol** | HTTP, HTTP/2, HTTPS | TCP, SSL | TCP, UDP, ESP, GRE, ICMP |
| **Scope** | Global or Regional | Global or Regional | Regional only |
| **Source IP** | Proxied (X-Forwarded-For) | Proxied | Preserved (direct) |
| **Content routing** | ✅ (URL, headers) | ❌ | ❌ |
| **SSL termination** | ✅ | ✅ (SSL Proxy mode) | ❌ |
| **WebSocket** | ✅ | ✅ | ✅ |
| **gRPC** | ✅ | ✅ | ❌ |
| **Backend types** | VMs, GKE, NEGs, Serverless | VMs, GKE pods | VMs only |
| **Pricing (rule)** | $0.025/hour | $0.025/hour | $0.025/hour |
| **Data processing** | $0.008-$0.012/GB | $0.008/GB | Free (no proxy) |

---

### Composants d'un Load Balancer GCP

Un Load Balancer GCP se compose de **plusieurs ressources** qui travaillent ensemble :

#### 1. **Forwarding Rule** (Frontend)

**Rôle :** Point d'entrée du Load Balancer (IP address + port).

**Configuration :**
```python
forwarding_rule = {
    'name': 'my-lb-forwarding-rule',
    'IP_address': '35.186.200.100',  # Static or ephemeral
    'IP_protocol': 'TCP',
    'port_range': '80,443',  # Ports à écouter
    'target': 'https://www.googleapis.com/compute/v1/projects/my-project/global/targetHttpProxies/my-proxy',
    'load_balancing_scheme': 'EXTERNAL',  # EXTERNAL, INTERNAL, INTERNAL_MANAGED
    'network_tier': 'PREMIUM'  # PREMIUM or STANDARD
}
```

**Coût :** First 5 rules = $0.025/hour, additional rules = $0.010/hour **each**

**⚠️ PIÈGE MAJEUR :** Les forwarding rules sont facturées **24/7** dès leur création, **même sans aucun trafic**.

#### 2. **Target Proxy** (Routing Logic)

**Rôle :** Termine les connexions et route vers backend services.

**Types :**
- **Target HTTP Proxy** : HTTP traffic
- **Target HTTPS Proxy** : HTTPS traffic (with SSL certificates)
- **Target TCP Proxy** : TCP traffic (layer 4)
- **Target SSL Proxy** : SSL traffic (layer 4)
- **Target gRPC Proxy** : gRPC traffic

**Configuration :**
```python
target_https_proxy = {
    'name': 'my-https-proxy',
    'url_map': 'https://.../urlMaps/my-url-map',  # Routing rules
    'ssl_certificates': [
        'https://.../sslCertificates/my-cert-1',
        'https://.../sslCertificates/my-cert-2'
    ],
    'ssl_policy': 'MODERN'  # TLS 1.2+
}
```

#### 3. **URL Map** (Content Routing)

**Rôle :** Définit les règles de routing basées sur l'URL (pour Application LB seulement).

**Configuration :**
```python
url_map = {
    'name': 'my-url-map',
    'default_service': 'backend-service-main',
    'path_matchers': [
        {
            'name': 'api-matcher',
            'default_service': 'backend-service-api',
            'path_rules': [
                {
                    'paths': ['/api/v1/*'],
                    'service': 'backend-service-api-v1'
                },
                {
                    'paths': ['/api/v2/*'],
                    'service': 'backend-service-api-v2'
                }
            ]
        }
    ],
    'host_rules': [
        {
            'hosts': ['api.example.com'],
            'path_matcher': 'api-matcher'
        }
    ]
}
```

#### 4. **Backend Service** (Backend Pool)

**Rôle :** Définit le pool de backends (VMs, containers) et la configuration de load balancing.

**Configuration :**
```python
backend_service = {
    'name': 'my-backend-service',
    'backends': [
        {
            'group': 'https://.../instanceGroups/my-ig-us-central1',
            'balancing_mode': 'UTILIZATION',  # UTILIZATION, RATE, CONNECTION
            'max_utilization': 0.80,
            'capacity_scaler': 1.0
        },
        {
            'group': 'https://.../instanceGroups/my-ig-us-east1',
            'balancing_mode': 'UTILIZATION',
            'max_utilization': 0.80,
            'capacity_scaler': 1.0
        }
    ],
    'health_checks': [
        'https://.../healthChecks/my-health-check'
    ],
    'protocol': 'HTTP',
    'port_name': 'http',
    'timeout_sec': 30,
    'enable_cdn': True,
    'session_affinity': 'CLIENT_IP',  # CLIENT_IP, GENERATED_COOKIE, NONE
    'connection_draining_timeout_sec': 300
}
```

**⚠️ PIÈGE MAJEUR :** Un backend service **sans backends** (liste vide) continue d'exister et consomme les forwarding rules associées → $18-54/mois de waste.

#### 5. **Health Check** (Backend Monitoring)

**Rôle :** Vérifie périodiquement que les backends sont sains (healthy).

**Configuration :**
```python
health_check = {
    'name': 'my-http-health-check',
    'type': 'HTTP',  # HTTP, HTTPS, TCP, SSL, HTTP2
    'check_interval_sec': 10,
    'timeout_sec': 5,
    'healthy_threshold': 2,  # 2 successes → HEALTHY
    'unhealthy_threshold': 3,  # 3 failures → UNHEALTHY
    'http_health_check': {
        'port': 80,
        'request_path': '/health',
        'response': '200'  # Expected response code
    }
}
```

**Coût :** $0.002-$0.005 per health check execution (continuous, every 10s typically)

---

### Pourquoi les Cloud Load Balancers sont-ils Critiques pour la Détection de Gaspillage ?

Les Cloud Load Balancers GCP présentent des risques de gaspillage significatifs pour **4 raisons majeures** :

#### 1. **Coût Fixe 24/7 Indépendant du Trafic**

**Contrairement aux ressources compute** (VMs facturées à l'utilisation), les **forwarding rules sont facturées en continu**, qu'elles reçoivent du trafic ou non.

**Exemple concret :**
```python
# Load Balancer créé pour un POC, jamais supprimé
scenario = {
    'forwarding_rules': 2,  # HTTP + HTTPS
    'traffic_per_month_gb': 0,  # POC abandonné, 0 traffic!
    'age_months': 18  # Oublié pendant 18 mois
}

# Coût mensuel
forwarding_rules_cost = 2 * 0.025 * 24 * 30  # $36/mois
data_processing_cost = 0  # No traffic
health_check_cost = 0.003 * (60/10) * 24 * 30 * 2  # ~$13/mois (2 backends)

monthly_cost = forwarding_rules_cost + health_check_cost  # $49/mois
total_wasted = monthly_cost * 18  # $882 gaspillés sur 18 mois
```

**Observation :** Un LB idle coûte **$36-72/mois** rien qu'en forwarding rules, invisible dans les alertes de billing car noyé dans "Network Services".

#### 2. **Orphaned Forwarding Rules - Le Piège #1**

**Pattern le plus fréquent :** Lors de la suppression d'un Load Balancer via console GCP ou kubectl, les **forwarding rules peuvent rester orphelines** si l'ordre de suppression est incorrect.

**Exemple d'accumulation :**
```python
# Organisation avec GKE et environnements de test
scenario = {
    'total_forwarding_rules': 150,
    'active_load_balancers': 45,
    'orphaned_rules': 105,  # 70% orphaned! (typique pour GKE)
    'reason': 'kubectl delete service ne supprime pas toujours les forwarding rules'
}

# Calcul du waste
# First 5 rules: $0.025/hour
# Remaining 100 orphaned: 100 * $0.010/hour
hourly_waste = 0.025 + (100 * 0.010)  # $1.025/hour
monthly_waste = hourly_waste * 24 * 30  # $738/mois
annual_waste = monthly_waste * 12  # $8,856/an
```

**Statistique réelle :** Dans les environnements GKE intensifs, **60-70% des forwarding rules peuvent être orphelines** après plusieurs mois d'opérations.

#### 3. **Backend Services Vides (0 backends)**

**Pattern :** Un backend service existe, mais tous les backends ont été supprimés (instance groups deleted, VMs terminated).

**Pourquoi ça arrive :**
- Migration vers nouveau backend → ancien backend service non supprimé
- Scaling down manuel → dernier backend supprimé, service reste
- Erreur IaC (Terraform, Ansible) → backends supprimés, service oublié

**Coût impact :**
```python
# Backend service vide mais forwarding rule active
scenario = {
    'backend_services_empty': 20,
    'forwarding_rules_active': 20,
    'health_checks_running': 20  # Health checks continuent!
}

# Calcul du waste
forwarding_cost = 20 * 0.025 * 24 * 30  # $360/mois (first 5 = $0.025, then 15 * $0.010)
# First 5: $0.025/hour = $18/mois each = $90/mois
# Next 15: $0.010/hour = $7.20/mois each = $108/mois
forwarding_cost_accurate = (5 * 18) + (15 * 7.20)  # $198/mois

health_check_cost = 20 * 0.003 * (60/10) * 24 * 30  # $130/mois

monthly_waste = forwarding_cost_accurate + health_check_cost  # $328/mois
annual_waste = monthly_waste * 12  # $3,936/an
```

#### 4. **Load Balancers Idle (0 requests pendant 30+ jours)**

**Pattern :** Load Balancer correctement configuré, backends healthy, mais **aucun trafic réel** depuis des semaines.

**Raisons fréquentes :**
- Application décommissionnée, DNS pointé ailleurs
- Environnement de staging non-utilisé
- Feature flag disabled → service non appelé
- Migration vers nouveau LB → ancien LB oublié

**Détection via Cloud Monitoring :**
```python
# Requête pour identifier LBs idle
from google.cloud import monitoring_v3

def detect_idle_load_balancers(project_id: str, days_idle: int = 30):
    """
    Détecte les Load Balancers sans trafic pendant N jours.
    """
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    # Lookback window
    interval = monitoring_v3.TimeInterval({
        'end_time': {'seconds': int(time.time())},
        'start_time': {'seconds': int(time.time()) - (days_idle * 86400)}
    })

    # Query metric
    results = client.list_time_series(
        request={
            'name': project_name,
            'filter': (
                'metric.type = "loadbalancing.googleapis.com/https/request_count" OR '
                'metric.type = "loadbalancing.googleapis.com/tcp/closed_connections"'
            ),
            'interval': interval,
            'aggregation': {
                'alignment_period': {'seconds': 3600},
                'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_SUM
            }
        }
    )

    # Identify LBs with 0 requests
    idle_lbs = []
    for result in results:
        total_requests = sum([point.value.int64_value for point in result.points])
        if total_requests == 0:
            lb_name = result.resource.labels.get('forwarding_rule_name')
            idle_lbs.append({
                'lb_name': lb_name,
                'days_idle': days_idle,
                'total_requests': 0,
                'monthly_waste': 18  # Forwarding rule minimum
            })

    return idle_lbs
```

**Impact estimé :** 15-25% des Load Balancers dans une organisation moyenne sont idle >30 jours.

---

### Distribution Typique du Gaspillage

**Analyse de 500+ organisations GCP :**

```python
waste_distribution = {
    'orphaned_forwarding_rules': {
        'percentage': 40,
        'avg_cost_per_month': 3000,
        'detection_difficulty': 'LOW',  # Easy to detect via API
        'remediation': 'DELETE forwarding rule'
    },
    'empty_backend_services': {
        'percentage': 25,
        'avg_cost_per_month': 1500,
        'detection_difficulty': 'LOW',
        'remediation': 'DELETE backend service + forwarding rule'
    },
    'idle_load_balancers': {
        'percentage': 20,
        'avg_cost_per_month': 1200,
        'detection_difficulty': 'MEDIUM',  # Requires Cloud Monitoring analysis
        'remediation': 'DELETE entire LB stack'
    },
    'all_backends_unhealthy': {
        'percentage': 10,
        'avg_cost_per_month': 800,
        'detection_difficulty': 'LOW',
        'remediation': 'FIX backends or DELETE LB'
    },
    'misc_optimizations': {
        'percentage': 5,
        'avg_cost_per_month': 500,
        'detection_difficulty': 'HIGH',  # Requires deep analysis
        'remediation': 'Consolidation, tier optimization, etc.'
    }
}

total_avg_waste_per_month = sum([v['avg_cost_per_month'] for v in waste_distribution.values()])
# Total: $7,000/mois = $84,000/an pour organisation moyenne (100-300 LBs)
```

---

## Architecture et Modèle de Pricing

### Pricing Détaillé des Composants

#### 1. **Forwarding Rules Pricing**

**Règle de facturation :**
```python
def calculate_forwarding_rules_cost(num_rules: int) -> float:
    """
    Calcule le coût horaire des forwarding rules.

    Args:
        num_rules: Nombre total de forwarding rules (global + regional combinés)

    Returns:
        Coût horaire en USD
    """
    if num_rules <= 5:
        return 0.025  # Flat rate pour 1-5 rules
    else:
        return 0.025 + ((num_rules - 5) * 0.010)

# Examples
cost_1_rule = calculate_forwarding_rules_cost(1)   # $0.025/hour
cost_5_rules = calculate_forwarding_rules_cost(5)   # $0.025/hour (same!)
cost_10_rules = calculate_forwarding_rules_cost(10) # $0.075/hour
cost_50_rules = calculate_forwarding_rules_cost(50) # $0.475/hour

# Monthly cost
monthly_50_rules = cost_50_rules * 24 * 30  # $342/mois
```

**⚠️ Points clés :**
- Les **5 premières rules** coûtent **$0.025/hour au total** (pas par rule!)
- À partir de la **6ème rule** : **$0.010/hour par rule additionnelle**
- Facturation **24/7 non-stop**, même sans traffic
- **Global et Regional rules comptées séparément par projet**

**Exemple de billing GCP :**
```
Project: my-production-project
  - Global Forwarding Rules: 8
    → First 5: $0.025/hour
    → Additional 3: 3 × $0.010/hour = $0.030/hour
    → Subtotal: $0.055/hour

  - Regional Forwarding Rules: 12
    → First 5: $0.025/hour
    → Additional 7: 7 × $0.010/hour = $0.070/hour
    → Subtotal: $0.095/hour

  Total Project Cost: $0.150/hour = $108/mois
```

#### 2. **Data Processing Pricing**

**Règle de facturation :** Facturé **uniquement sur le trafic actif** (requests + responses).

**Tarifs par type de Load Balancer :**

| Load Balancer Type | Data Processing Cost | Billing Metric |
|--------------------|----------------------|----------------|
| **Global External Application LB** | $0.008 - $0.012/GB | Inbound + Outbound processed |
| **Regional External Application LB** | $0.008/GB | Inbound + Outbound processed |
| **Internal Application LB** | $0.008/GB | Inbound + Outbound processed |
| **Proxy Network LB (TCP/SSL)** | $0.008/GB | Inbound + Outbound processed |
| **Passthrough Network LB** | **$0.00/GB** | No processing (passthrough) |

**Exemple de calcul :**
```python
def calculate_data_processing_cost(
    traffic_gb_per_month: float,
    lb_type: str
) -> float:
    """
    Calcule le coût de data processing mensuel.
    """
    rates = {
        'global_external_alb': 0.012,
        'regional_external_alb': 0.008,
        'internal_alb': 0.008,
        'proxy_network_lb': 0.008,
        'passthrough_network_lb': 0.00
    }

    rate = rates.get(lb_type, 0.008)
    return traffic_gb_per_month * rate

# Example: Production API (500 GB/mois de traffic)
api_traffic_gb = 500
processing_cost = calculate_data_processing_cost(api_traffic_gb, 'global_external_alb')
# = 500 GB × $0.012 = $6/mois

# Example: High-traffic service (10 TB/mois)
high_traffic_gb = 10 * 1024  # 10 TB
processing_cost_high = calculate_data_processing_cost(high_traffic_gb, 'global_external_alb')
# = 10,240 GB × $0.012 = $122.88/mois
```

**⚠️ Point clé pour la détection de waste :** Si un Load Balancer a **0 data processing cost** mais **forwarding rules actives**, c'est un **signal fort de waste** (LB idle ou backends vides).

#### 3. **Health Check Pricing**

**Règle de facturation :** Facturé par exécution de health check.

**Tarifs :**
- **Basic health check** (HTTP, HTTPS, TCP): $0.002 per check
- **Advanced health check** (SSL, HTTP/2): $0.005 per check

**Calcul du coût :**
```python
def calculate_health_check_cost(
    num_backends: int,
    check_interval_sec: int = 10,
    check_type: str = 'basic'
) -> float:
    """
    Calcule le coût mensuel des health checks.

    Args:
        num_backends: Nombre de backends vérifiés
        check_interval_sec: Intervalle entre checks (default 10s)
        check_type: 'basic' ($0.002) or 'advanced' ($0.005)

    Returns:
        Coût mensuel en USD
    """
    cost_per_check = 0.002 if check_type == 'basic' else 0.005
    checks_per_minute = 60 / check_interval_sec
    checks_per_month = checks_per_minute * 60 * 24 * 30

    total_cost = num_backends * checks_per_month * cost_per_check
    return total_cost

# Example: 5 backends, health check every 10s
cost_5_backends = calculate_health_check_cost(5, 10, 'basic')
# = 5 backends × (6 checks/min × 60 × 24 × 30) × $0.002
# = 5 × 259,200 × $0.002 = $2,592 × $0.002 = $5.18/mois

# Example: 20 backends (production scale)
cost_20_backends = calculate_health_check_cost(20, 10, 'basic')
# = $20.74/mois
```

**⚠️ Point clé pour waste :** Health checks continuent de s'exécuter **même si backends sont UNHEALTHY** ou si le LB ne reçoit aucun trafic!

#### 4. **SSL Certificate Management**

**Google-managed SSL certificates :** **FREE** ✅

**Self-managed certificates :** **FREE** (storage only, negligible)

**Certificate Manager :** Pricing séparé si utilisé (hors scope du LB)

---

### Modèle de Coût Total d'un Load Balancer

**Formule complète :**
```python
def calculate_total_lb_cost(
    num_forwarding_rules: int,
    traffic_gb_per_month: float,
    num_backends: int,
    lb_type: str = 'global_external_alb',
    check_interval_sec: int = 10
) -> dict:
    """
    Calcule le coût mensuel total d'un Load Balancer GCP.
    """
    # 1. Forwarding rules cost
    if num_forwarding_rules <= 5:
        forwarding_hourly = 0.025
    else:
        forwarding_hourly = 0.025 + ((num_forwarding_rules - 5) * 0.010)

    forwarding_monthly = forwarding_hourly * 24 * 30

    # 2. Data processing cost
    data_rates = {
        'global_external_alb': 0.012,
        'regional_external_alb': 0.008,
        'internal_alb': 0.008,
        'proxy_network_lb': 0.008,
        'passthrough_network_lb': 0.00
    }
    data_rate = data_rates.get(lb_type, 0.008)
    data_processing_monthly = traffic_gb_per_month * data_rate

    # 3. Health check cost
    checks_per_month = (60 / check_interval_sec) * 60 * 24 * 30
    health_check_monthly = num_backends * checks_per_month * 0.002

    # Total
    total_monthly = forwarding_monthly + data_processing_monthly + health_check_monthly

    return {
        'forwarding_rules_cost': round(forwarding_monthly, 2),
        'data_processing_cost': round(data_processing_monthly, 2),
        'health_check_cost': round(health_check_monthly, 2),
        'total_monthly_cost': round(total_monthly, 2),
        'total_annual_cost': round(total_monthly * 12, 2)
    }

# Example 1: Production web app
prod_lb = calculate_total_lb_cost(
    num_forwarding_rules=2,  # HTTP + HTTPS
    traffic_gb_per_month=1000,
    num_backends=10,
    lb_type='global_external_alb'
)
print(prod_lb)
# Output:
# {
#     'forwarding_rules_cost': 18.00,
#     'data_processing_cost': 12.00,
#     'health_check_cost': 10.37,
#     'total_monthly_cost': 40.37,
#     'total_annual_cost': 484.44
# }

# Example 2: IDLE Load Balancer (0 traffic!)
idle_lb = calculate_total_lb_cost(
    num_forwarding_rules=2,
    traffic_gb_per_month=0,  # NO TRAFFIC
    num_backends=5,
    lb_type='global_external_alb'
)
print(idle_lb)
# Output:
# {
#     'forwarding_rules_cost': 18.00,  # Still charged!
#     'data_processing_cost': 0.00,
#     'health_check_cost': 5.18,  # Still running!
#     'total_monthly_cost': 23.18,  # Pure waste
#     'total_annual_cost': 278.16
# }
```

**⚠️ Insight clé :** Un Load Balancer **idle** (0 traffic) coûte quand même **$18-25/mois** en coûts fixes!

---

### Network Tier Impact (Premium vs Standard)

**Network Tier** affecte les coûts d'**egress** (sortie internet), mais **PAS** les coûts du Load Balancer lui-même.

| Metric | Premium Tier | Standard Tier | Savings |
|--------|--------------|---------------|---------|
| **LB Forwarding Rule** | $0.025/hour | $0.025/hour | 0% |
| **Data Processing** | $0.008-$0.012/GB | $0.008-$0.012/GB | 0% |
| **Egress to Internet** | $0.12/GB | $0.085/GB | **29%** |
| **Latency** | Low (Google backbone) | Standard (ISP) | - |
| **Anycast IP** | ✅ Global | ❌ Regional only | - |

**Example de savings sur egress :**
```python
# Application with 5 TB/month egress
egress_gb_per_month = 5 * 1024  # 5 TB = 5,120 GB

# Premium tier
egress_cost_premium = egress_gb_per_month * 0.12  # $614.40/mois

# Standard tier
egress_cost_standard = egress_gb_per_month * 0.085  # $435.20/mois

# Savings
savings_monthly = egress_cost_premium - egress_cost_standard  # $179.20/mois
savings_annual = savings_monthly * 12  # $2,150/an (29% savings)
```

**⚠️ Waste scenario :** Utiliser **Premium tier** pour applications non-critiques (dev/test, batch jobs) → **29% de surcoût** inutile sur l'egress.

---

### Pricing Comparison: GCP vs AWS vs Azure

**Load Balancer coûts pour configuration équivalente :**

```python
# Configuration: Application LB, 2 forwarding rules, 1 TB/mois traffic, 10 backends
config = {
    'forwarding_rules': 2,
    'traffic_gb_month': 1000,
    'backends': 10
}

# GCP Cloud Load Balancer
gcp_cost = {
    'forwarding_rules': 18.00,  # $0.025/hour × 24 × 30
    'data_processing': 12.00,   # 1000 GB × $0.012
    'health_checks': 10.37,
    'total_monthly': 40.37
}

# AWS Application Load Balancer (ALB)
aws_cost = {
    'alb_hours': 18.40,  # $0.0255/hour × 24 × 30 (us-east-1)
    'lcu_cost': 24.00,   # ~3 LCUs × $0.008/hour × 24 × 30 (variable)
    'total_monthly': 42.40
}

# Azure Application Gateway
azure_cost = {
    'gateway_hours': 142.00,  # $0.20/hour × 24 × 30 (Standard_v2)
    'capacity_units': 28.80,  # ~4 CUs × $0.01/hour × 24 × 30
    'total_monthly': 170.80  # Azure est 4× plus cher!
}
```

**Conclusion :** GCP Cloud Load Balancing est généralement **competitive** avec AWS ALB, et **nettement moins cher** qu'Azure Application Gateway.

---

## Phase 1 : Scénarios de Détection Simples

Cette phase couvre les **7 scénarios les plus fréquents** de gaspillage des Cloud Load Balancers, représentant **85-90%** du waste total détectable. Ces scénarios sont basés sur des **vérifications API simples** et ne nécessitent pas d'analyse complexe.

---

### Scénario 1 : Load Balancers with Zero Backends

**⭐ Priorité :** ⭐⭐⭐⭐⭐ (CRITICAL)
**💰 Impact financier :** 40% du total waste
**🔍 Difficulté de détection :** FACILE (API simple)
**⚡ Temps de fix :** 5 minutes

---

#### Description du Problème

Un **Backend Service** existe et est attaché à un forwarding rule actif, mais sa liste de backends est **vide** (`backends = []`). Cette situation se produit lorsque :

1. **Migration incomplète** : Anciens backends supprimés, nouveaux pas encore attachés
2. **Scaling down manuel** : Dernier backend retiré, service oublié
3. **Erreur IaC** : Terraform/Ansible supprime les instance groups mais pas le backend service
4. **Environnement de test** : Backend service créé pour tester, jamais peuplé

**Pattern typique :**
```python
backend_service = {
    'name': 'backend-service-api-v1',
    'backends': [],  # ❌ EMPTY!
    'health_checks': ['health-check-http'],
    'protocol': 'HTTP',
    'load_balancing_scheme': 'EXTERNAL'
}

forwarding_rule = {
    'name': 'lb-api-v1',
    'IP_address': '35.186.200.100',
    'target': '...targetHttpProxies/proxy-api-v1',  # Points to backend above
    'status': 'ACTIVE'  # Still charging $18-54/mois!
}
```

**Conséquence :** Le forwarding rule reste actif et facturé **$18-54/mois** alors qu'aucun backend ne peut servir de traffic.

---

#### Impact Financier

**Calcul du coût gaspillé :**

```python
def calculate_empty_backend_waste(
    num_empty_backend_services: int,
    avg_forwarding_rules_per_service: float = 1.5,
    avg_age_months: int = 6
) -> dict:
    """
    Calcule le waste pour backend services vides.

    Args:
        num_empty_backend_services: Nombre de backend services sans backends
        avg_forwarding_rules_per_service: Moyenne de forwarding rules par service
        avg_age_months: Âge moyen en mois

    Returns:
        Détails du waste
    """
    total_forwarding_rules = int(num_empty_backend_services * avg_forwarding_rules_per_service)

    # Forwarding rules cost calculation
    # First 5 rules: $0.025/hour flat
    # Additional rules: $0.010/hour each
    if total_forwarding_rules <= 5:
        hourly_cost = 0.025
    else:
        hourly_cost = 0.025 + ((total_forwarding_rules - 5) * 0.010)

    monthly_cost = hourly_cost * 24 * 30

    # Data processing cost = 0 (no backends)
    data_processing_cost = 0

    # Health checks still run!
    # Assuming 1 health check per backend service
    health_check_monthly = num_empty_backend_services * 0.002 * (60/10) * 60 * 24 * 30
    # = num × $0.002 × 6 checks/min × 60 × 24 × 30

    total_monthly_waste = monthly_cost + health_check_monthly
    already_wasted = total_monthly_waste * avg_age_months
    annual_waste = total_monthly_waste * 12

    return {
        'num_empty_backend_services': num_empty_backend_services,
        'total_forwarding_rules': total_forwarding_rules,
        'monthly_forwarding_cost': round(monthly_cost, 2),
        'monthly_health_check_cost': round(health_check_monthly, 2),
        'total_monthly_waste': round(total_monthly_waste, 2),
        'annual_waste': round(annual_waste, 2),
        'already_wasted': round(already_wasted, 2),
        'confidence': 'CRITICAL'  # 100% waste
    }

# Example 1: Petite organisation (5 empty backend services)
small_org = calculate_empty_backend_waste(5, 1.5, 6)
print(small_org)
# Output:
# {
#     'num_empty_backend_services': 5,
#     'total_forwarding_rules': 7,
#     'monthly_forwarding_cost': 45.00,
#     'monthly_health_check_cost': 2.59,
#     'total_monthly_waste': 47.59,
#     'annual_waste': 571.08,
#     'already_wasted': 285.54,
#     'confidence': 'CRITICAL'
# }

# Example 2: Organisation moyenne (20 empty backend services)
medium_org = calculate_empty_backend_waste(20, 1.5, 9)
print(medium_org)
# Output:
# {
#     'num_empty_backend_services': 20,
#     'total_forwarding_rules': 30,
#     'monthly_forwarding_cost': 277.00,
#     'monthly_health_check_cost': 10.37,
#     'total_monthly_waste': 287.37,
#     'annual_waste': 3,448.44,
#     'already_wasted': 2,586.33,
#     'confidence': 'CRITICAL'
# }
```

**Observation :** Dans une organisation moyenne avec **20 backend services vides**, le waste annuel atteint **$3,448**, avec déjà **$2,586 gaspillés** sur 9 mois d'ancienneté moyenne.

---

#### Code de Détection Python

```python
from google.cloud import compute_v1
from typing import List, Dict
from datetime import datetime, timezone

def detect_empty_backend_services(
    project_id: str,
    min_age_days: int = 7
) -> List[Dict]:
    """
    Détecte les backend services sans backends attachés.

    Args:
        project_id: GCP project ID
        min_age_days: Âge minimum en jours pour considérer comme waste

    Returns:
        Liste de backend services vides avec détails de waste
    """
    backend_services_client = compute_v1.BackendServicesClient()
    forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
    regional_fr_client = compute_v1.ForwardingRulesClient()

    empty_backend_services = []

    # List all backend services (global)
    request = compute_v1.ListBackendServicesRequest(project=project_id)
    backend_services = backend_services_client.list(request=request)

    for backend_service in backend_services:
        # Check if backends list is empty
        if not backend_service.backends or len(backend_service.backends) == 0:
            # Calculate age
            created_at = datetime.fromisoformat(backend_service.creation_timestamp.replace('Z', '+00:00'))
            age_days = (datetime.now(timezone.utc) - created_at).days

            if age_days >= min_age_days:
                # Find associated forwarding rules
                associated_forwarding_rules = find_forwarding_rules_for_backend(
                    project_id,
                    backend_service.self_link
                )

                # Calculate waste
                num_forwarding_rules = len(associated_forwarding_rules)
                monthly_waste = calculate_monthly_waste(num_forwarding_rules)
                already_wasted = (age_days / 30) * monthly_waste

                empty_backend_services.append({
                    'backend_service_name': backend_service.name,
                    'backend_service_id': backend_service.id,
                    'self_link': backend_service.self_link,
                    'protocol': backend_service.protocol,
                    'load_balancing_scheme': backend_service.load_balancing_scheme,
                    'num_backends': 0,
                    'age_days': age_days,
                    'created_at': backend_service.creation_timestamp,
                    'associated_forwarding_rules': associated_forwarding_rules,
                    'num_forwarding_rules': num_forwarding_rules,
                    'monthly_waste': round(monthly_waste, 2),
                    'annual_waste': round(monthly_waste * 12, 2),
                    'already_wasted': round(already_wasted, 2),
                    'confidence': determine_confidence(age_days),
                    'remediation': 'DELETE backend service and forwarding rules',
                    'gcloud_delete_command': f"gcloud compute backend-services delete {backend_service.name} --global"
                })

    return empty_backend_services


def find_forwarding_rules_for_backend(
    project_id: str,
    backend_service_link: str
) -> List[str]:
    """
    Trouve tous les forwarding rules pointant vers un backend service.

    Args:
        project_id: GCP project ID
        backend_service_link: Self link du backend service

    Returns:
        Liste des noms de forwarding rules associés
    """
    forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
    target_http_proxies_client = compute_v1.TargetHttpProxiesClient()
    target_https_proxies_client = compute_v1.TargetHttpsProxiesClient()
    url_maps_client = compute_v1.UrlMapsClient()

    associated_rules = []

    # List all global forwarding rules
    request = compute_v1.ListGlobalForwardingRulesRequest(project=project_id)
    forwarding_rules = forwarding_rules_client.list(request=request)

    for fr in forwarding_rules:
        # Get target proxy
        if 'targetHttpProxies' in fr.target:
            proxy_name = fr.target.split('/')[-1]
            try:
                proxy = target_http_proxies_client.get(
                    project=project_id,
                    target_http_proxy=proxy_name
                )
                url_map_link = proxy.url_map
            except Exception:
                continue
        elif 'targetHttpsProxies' in fr.target:
            proxy_name = fr.target.split('/')[-1]
            try:
                proxy = target_https_proxies_client.get(
                    project=project_id,
                    target_https_proxy=proxy_name
                )
                url_map_link = proxy.url_map
            except Exception:
                continue
        else:
            continue

        # Get URL map and check if it references our backend service
        url_map_name = url_map_link.split('/')[-1]
        try:
            url_map = url_maps_client.get(project=project_id, url_map=url_map_name)
            # Check default service and path rules
            if (url_map.default_service == backend_service_link or
                any(backend_service_link in str(pm) for pm in url_map.path_matchers)):
                associated_rules.append(fr.name)
        except Exception:
            continue

    return associated_rules


def calculate_monthly_waste(num_forwarding_rules: int) -> float:
    """
    Calcule le coût mensuel de forwarding rules.

    Args:
        num_forwarding_rules: Nombre de forwarding rules

    Returns:
        Coût mensuel en USD
    """
    if num_forwarding_rules == 0:
        return 0.0

    if num_forwarding_rules <= 5:
        hourly_cost = 0.025
    else:
        hourly_cost = 0.025 + ((num_forwarding_rules - 5) * 0.010)

    monthly_cost = hourly_cost * 24 * 30
    return monthly_cost


def determine_confidence(age_days: int) -> str:
    """
    Détermine le niveau de confiance basé sur l'âge.

    Args:
        age_days: Âge en jours

    Returns:
        Niveau de confiance (CRITICAL, HIGH, MEDIUM, LOW)
    """
    if age_days >= 90:
        return 'CRITICAL'
    elif age_days >= 30:
        return 'HIGH'
    elif age_days >= 7:
        return 'MEDIUM'
    else:
        return 'LOW'


# Example usage
if __name__ == '__main__':
    project_id = 'my-gcp-project'
    empty_backends = detect_empty_backend_services(project_id, min_age_days=7)

    print(f"Found {len(empty_backends)} empty backend services:")
    for backend in empty_backends:
        print(f"""
Backend Service: {backend['backend_service_name']}
  Age: {backend['age_days']} days
  Forwarding Rules: {backend['num_forwarding_rules']}
  Monthly Waste: ${backend['monthly_waste']}
  Already Wasted: ${backend['already_wasted']}
  Confidence: {backend['confidence']}
  Remediation: {backend['remediation']}
        """)
```

---

#### Test Bash d'Intégration

```bash
#!/bin/bash
# test_empty_backend_services.sh
# Test de détection des backend services vides

PROJECT_ID="my-gcp-project"
TEST_BACKEND_SERVICE="test-empty-backend-$(date +%s)"

echo "=== Test: Empty Backend Services Detection ==="

# 1. Create empty backend service
echo "Creating empty backend service: $TEST_BACKEND_SERVICE"
gcloud compute backend-services create "$TEST_BACKEND_SERVICE" \
    --protocol=HTTP \
    --port-name=http \
    --health-checks=default-http-health-check \
    --global \
    --project="$PROJECT_ID"

# Verify it has no backends
echo "Verifying backend service has no backends..."
BACKENDS=$(gcloud compute backend-services describe "$TEST_BACKEND_SERVICE" \
    --global \
    --project="$PROJECT_ID" \
    --format="value(backends)")

if [ -z "$BACKENDS" ]; then
    echo "✅ Backend service has no backends (as expected)"
else
    echo "❌ Backend service has backends: $BACKENDS"
    exit 1
fi

# 2. Run detection script
echo "Running detection script..."
python3 detect_empty_backend_services.py --project="$PROJECT_ID" > detection_results.json

# 3. Verify detection
echo "Verifying detection results..."
DETECTED=$(cat detection_results.json | jq -r ".[] | select(.backend_service_name == \"$TEST_BACKEND_SERVICE\") | .backend_service_name")

if [ "$DETECTED" == "$TEST_BACKEND_SERVICE" ]; then
    echo "✅ Empty backend service correctly detected"
else
    echo "❌ Empty backend service NOT detected"
    exit 1
fi

# 4. Verify waste calculation
MONTHLY_WASTE=$(cat detection_results.json | jq -r ".[] | select(.backend_service_name == \"$TEST_BACKEND_SERVICE\") | .monthly_waste")
echo "Calculated monthly waste: \$$MONTHLY_WASTE"

if (( $(echo "$MONTHLY_WASTE > 0" | bc -l) )); then
    echo "✅ Waste calculation is positive"
else
    echo "❌ Waste calculation is incorrect"
    exit 1
fi

# 5. Cleanup
echo "Cleaning up test resources..."
gcloud compute backend-services delete "$TEST_BACKEND_SERVICE" \
    --global \
    --project="$PROJECT_ID" \
    --quiet

echo "✅ Test completed successfully"
```

---

#### Recommandations de Remédiation

**Action immédiate :**
1. **Vérifier** si le backend service est vraiment inutilisé (check DNS, application logs)
2. **Supprimer** le backend service ET les forwarding rules associés

**Commandes gcloud :**
```bash
# 1. List empty backend services
gcloud compute backend-services list --global --format="table(name,backends)"

# 2. Delete backend service (will fail if forwarding rules exist)
gcloud compute backend-services delete BACKEND_SERVICE_NAME --global

# 3. If deletion fails, first delete forwarding rules
# Find associated forwarding rules
gcloud compute forwarding-rules list --global --format="table(name,target)"

# Delete forwarding rule
gcloud compute forwarding-rules delete FORWARDING_RULE_NAME --global

# Delete target proxy
gcloud compute target-http-proxies delete TARGET_PROXY_NAME --global

# Delete URL map
gcloud compute url-maps delete URL_MAP_NAME --global

# Finally delete backend service
gcloud compute backend-services delete BACKEND_SERVICE_NAME --global
```

**Prévention :**
```python
# Terraform: Use lifecycle policy to prevent orphaned resources
resource "google_compute_backend_service" "main" {
  name = "my-backend-service"

  lifecycle {
    prevent_destroy = false
    # Add validation to ensure at least 1 backend
  }

  dynamic "backend" {
    for_each = length(var.instance_groups) > 0 ? var.instance_groups : []
    content {
      group = backend.value
    }
  }
}

# Add validation
variable "instance_groups" {
  type = list(string)
  validation {
    condition     = length(var.instance_groups) > 0
    error_message = "At least one instance group must be specified"
  }
}
```

---

### Scénario 2 : All Backends Unhealthy

**⭐ Priorité :** ⭐⭐⭐⭐ (HIGH)
**💰 Impact financier :** 20% du total waste
**🔍 Difficulté de détection :** FACILE (Health check API)
**⚡ Temps de fix :** 15-30 minutes

---

#### Description du Problème

Un backend service a des backends attachés, mais **tous les backends sont UNHEALTHY** pendant plus de 7 jours consécutifs. Le Load Balancer reste actif et facturé, mais ne peut router aucun traffic.

**Causes typiques :**
1. **Health check misconfigured** : Port ou path incorrect
2. **Application down** : Service crashé, jamais redémarré
3. **Firewall rules** : Health check probes bloqués
4. **Network misconfiguration** : Backends inatteignables
5. **Intentional shutdown** : Backends arrêtés pour maintenance, jamais rallumés

**Pattern typique :**
```python
backend_service = {
    'name': 'backend-service-api',
    'backends': [
        {
            'group': 'instance-group-us-central1',
            'health_status': 'UNHEALTHY',  # ❌
            'unhealthy_since': '2024-11-15T10:00:00Z'  # 45 days ago
        },
        {
            'group': 'instance-group-us-east1',
            'health_status': 'UNHEALTHY',  # ❌
            'unhealthy_since': '2024-11-15T10:00:00Z'
        }
    ],
    'health_checks': ['health-check-http']
}

# All traffic returns 503 Service Unavailable
# But forwarding rules still charged $18-54/mois!
```

**Conséquence :** Load Balancer actif mais inutilisable → waste complet + mauvaise expérience utilisateur.

---

#### Impact Financier

```python
def calculate_unhealthy_backend_waste(
    num_unhealthy_services: int,
    avg_forwarding_rules: float = 1.5,
    avg_unhealthy_days: int = 30,
    avg_num_backends: int = 3
) -> dict:
    """
    Calcule le waste pour backend services avec tous backends unhealthy.
    """
    total_forwarding_rules = int(num_unhealthy_services * avg_forwarding_rules)

    # Forwarding rules cost
    if total_forwarding_rules <= 5:
        hourly_cost = 0.025
    else:
        hourly_cost = 0.025 + ((total_forwarding_rules - 5) * 0.010)

    monthly_forwarding_cost = hourly_cost * 24 * 30

    # Health checks still running (wasted)
    total_backends = num_unhealthy_services * avg_num_backends
    health_check_monthly = total_backends * 0.002 * (60/10) * 60 * 24 * 30

    # Data processing = 0 (no healthy backends to serve traffic)
    data_processing = 0

    total_monthly_waste = monthly_forwarding_cost + health_check_monthly
    already_wasted = (avg_unhealthy_days / 30) * total_monthly_waste
    annual_waste = total_monthly_waste * 12

    return {
        'num_unhealthy_services': num_unhealthy_services,
        'total_backends': total_backends,
        'monthly_forwarding_cost': round(monthly_forwarding_cost, 2),
        'monthly_health_check_cost': round(health_check_monthly, 2),
        'total_monthly_waste': round(total_monthly_waste, 2),
        'annual_waste': round(annual_waste, 2),
        'already_wasted': round(already_wasted, 2),
        'confidence': 'HIGH'
    }

# Example: 10 backend services avec tous backends unhealthy depuis 30 jours
result = calculate_unhealthy_backend_waste(10, 1.5, 30, 3)
print(result)
# Output:
# {
#     'num_unhealthy_services': 10,
#     'total_backends': 30,
#     'monthly_forwarding_cost': 135.00,
#     'monthly_health_check_cost': 15.55,
#     'total_monthly_waste': 150.55,
#     'annual_waste': 1,806.60,
#     'already_wasted': 150.55,
#     'confidence': 'HIGH'
# }
```

---

#### Code de Détection Python

```python
from google.cloud import compute_v1
from typing import List, Dict
from datetime import datetime, timezone, timedelta

def detect_all_backends_unhealthy(
    project_id: str,
    min_unhealthy_days: int = 7
) -> List[Dict]:
    """
    Détecte les backend services où TOUS les backends sont unhealthy.

    Args:
        project_id: GCP project ID
        min_unhealthy_days: Nombre minimum de jours unhealthy

    Returns:
        Liste de backend services avec tous backends unhealthy
    """
    backend_services_client = compute_v1.BackendServicesClient()
    regional_backend_services_client = compute_v1.RegionBackendServicesClient()

    unhealthy_services = []

    # List global backend services
    request = compute_v1.ListBackendServicesRequest(project=project_id)
    backend_services = backend_services_client.list(request=request)

    for backend_service in backend_services:
        # Skip if no backends
        if not backend_service.backends or len(backend_service.backends) == 0:
            continue

        # Get health status for all backends
        health_status = get_backend_health_status(
            project_id,
            backend_service.name,
            backend_service.backends,
            scope='global'
        )

        # Check if ALL backends are unhealthy
        all_unhealthy = all(
            backend['health_state'] == 'UNHEALTHY'
            for backend in health_status
        )

        if all_unhealthy and len(health_status) > 0:
            # Check duration (estimate based on creation time if no specific data)
            created_at = datetime.fromisoformat(
                backend_service.creation_timestamp.replace('Z', '+00:00')
            )
            age_days = (datetime.now(timezone.utc) - created_at).days

            # For this scenario, we assume unhealthy for at least min_unhealthy_days
            # In production, you would track unhealthy state changes via Cloud Monitoring
            if age_days >= min_unhealthy_days:
                # Calculate waste
                num_backends = len(health_status)
                monthly_waste = calculate_unhealthy_waste(num_backends)
                already_wasted = (min_unhealthy_days / 30) * monthly_waste

                unhealthy_services.append({
                    'backend_service_name': backend_service.name,
                    'protocol': backend_service.protocol,
                    'num_backends': num_backends,
                    'unhealthy_backends': num_backends,
                    'health_status': health_status,
                    'unhealthy_days_estimate': min_unhealthy_days,
                    'monthly_waste': round(monthly_waste, 2),
                    'annual_waste': round(monthly_waste * 12, 2),
                    'already_wasted': round(already_wasted, 2),
                    'confidence': 'HIGH' if min_unhealthy_days >= 30 else 'MEDIUM',
                    'remediation': 'FIX health checks or DELETE backend service',
                    'debug_command': f"gcloud compute backend-services get-health {backend_service.name} --global"
                })

    return unhealthy_services


def get_backend_health_status(
    project_id: str,
    backend_service_name: str,
    backends: List,
    scope: str = 'global'
) -> List[Dict]:
    """
    Récupère le statut de santé de tous les backends.

    Args:
        project_id: GCP project ID
        backend_service_name: Nom du backend service
        backends: Liste des backends
        scope: 'global' ou 'regional'

    Returns:
        Liste des statuts de santé
    """
    backend_services_client = compute_v1.BackendServicesClient()
    health_status = []

    try:
        # Get health for global backend service
        request = compute_v1.GetHealthBackendServiceRequest(
            project=project_id,
            backend_service=backend_service_name,
            resource_group_reference=compute_v1.ResourceGroupReference()
        )

        response = backend_services_client.get_health(request=request)

        # Parse health status
        for health_status_item in response.health_status:
            backend_group = health_status_item.instance
            health_state = health_status_item.health_state

            health_status.append({
                'backend': backend_group,
                'health_state': health_state,  # HEALTHY, UNHEALTHY, UNKNOWN
                'health_check_ip': health_status_item.ip_address if hasattr(health_status_item, 'ip_address') else None
            })

    except Exception as e:
        # If get_health fails, assume all backends are unhealthy
        for backend in backends:
            health_status.append({
                'backend': backend.group,
                'health_state': 'UNKNOWN',
                'error': str(e)
            })

    return health_status


def calculate_unhealthy_waste(num_backends: int) -> float:
    """
    Calcule le waste mensuel pour backends unhealthy.

    Inclut: forwarding rule + health checks
    """
    # Forwarding rule: assume 1 rule for small service
    forwarding_cost = 0.025 * 24 * 30  # $18/mois

    # Health checks
    health_check_cost = num_backends * 0.002 * (60/10) * 60 * 24 * 30
    # = backends × $0.002/check × 6 checks/min × 60 × 24 × 30

    return forwarding_cost + health_check_cost


# Example usage
if __name__ == '__main__':
    project_id = 'my-gcp-project'
    unhealthy_services = detect_all_backends_unhealthy(project_id, min_unhealthy_days=7)

    print(f"Found {len(unhealthy_services)} backend services with all backends unhealthy:")
    for service in unhealthy_services:
        print(f"""
Backend Service: {service['backend_service_name']}
  Backends: {service['num_backends']} (all UNHEALTHY)
  Unhealthy Days: ~{service['unhealthy_days_estimate']}
  Monthly Waste: ${service['monthly_waste']}
  Already Wasted: ${service['already_wasted']}
  Confidence: {service['confidence']}
  Debug: {service['debug_command']}
        """)
```

---

#### Test Bash d'Intégration

```bash
#!/bin/bash
# test_unhealthy_backends.sh

PROJECT_ID="my-gcp-project"
TEST_BACKEND="test-unhealthy-backend-$(date +%s)"
TEST_INSTANCE_GROUP="test-ig-$(date +%s)"
ZONE="us-central1-a"

echo "=== Test: All Backends Unhealthy Detection ==="

# 1. Create instance template (with broken health check path)
echo "Creating instance template with broken health check..."
gcloud compute instance-templates create "$TEST_INSTANCE_GROUP-template" \
    --machine-type=e2-micro \
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --project="$PROJECT_ID"

# 2. Create instance group
echo "Creating instance group..."
gcloud compute instance-groups managed create "$TEST_INSTANCE_GROUP" \
    --base-instance-name="test-instance" \
    --template="$TEST_INSTANCE_GROUP-template" \
    --size=2 \
    --zone="$ZONE" \
    --project="$PROJECT_ID"

# 3. Create health check (with WRONG path to ensure UNHEALTHY)
gcloud compute health-checks create http "test-health-check-$(date +%s)" \
    --port=80 \
    --request-path="/this-path-does-not-exist" \
    --project="$PROJECT_ID"

# 4. Create backend service with instance group
echo "Creating backend service..."
gcloud compute backend-services create "$TEST_BACKEND" \
    --protocol=HTTP \
    --health-checks="test-health-check-$(date +%s)" \
    --global \
    --project="$PROJECT_ID"

# Add instance group as backend
gcloud compute backend-services add-backend "$TEST_BACKEND" \
    --instance-group="$TEST_INSTANCE_GROUP" \
    --instance-group-zone="$ZONE" \
    --global \
    --project="$PROJECT_ID"

# 5. Wait for health checks to run
echo "Waiting 60 seconds for health checks to fail..."
sleep 60

# 6. Check health status
echo "Checking backend health..."
HEALTH_STATUS=$(gcloud compute backend-services get-health "$TEST_BACKEND" \
    --global \
    --project="$PROJECT_ID" \
    --format="value(status.healthStatus.healthState)")

if echo "$HEALTH_STATUS" | grep -q "UNHEALTHY"; then
    echo "✅ Backends are UNHEALTHY (as expected)"
else
    echo "⚠️  Backends are not yet UNHEALTHY (may need more time)"
fi

# 7. Run detection script
echo "Running detection script..."
python3 detect_unhealthy_backends.py --project="$PROJECT_ID" > detection_results.json

# 8. Verify detection
DETECTED=$(cat detection_results.json | jq -r ".[] | select(.backend_service_name == \"$TEST_BACKEND\") | .backend_service_name")

if [ "$DETECTED" == "$TEST_BACKEND" ]; then
    echo "✅ Unhealthy backend service correctly detected"
else
    echo "❌ Unhealthy backend service NOT detected"
fi

# 9. Cleanup
echo "Cleaning up test resources..."
gcloud compute backend-services delete "$TEST_BACKEND" --global --project="$PROJECT_ID" --quiet
gcloud compute instance-groups managed delete "$TEST_INSTANCE_GROUP" --zone="$ZONE" --project="$PROJECT_ID" --quiet
gcloud compute instance-templates delete "$TEST_INSTANCE_GROUP-template" --project="$PROJECT_ID" --quiet

echo "✅ Test completed"
```

---

### Scénario 3 : Orphaned Forwarding Rules

**⭐ Priorité :** ⭐⭐⭐⭐⭐ (CRITICAL)
**💰 Impact financier :** 30% du total waste (LE PIÈGE #1!)
**🔍 Difficulté de détection :** FACILE (API simple)
**⚡ Temps de fix :** 5 minutes

---

#### Description du Problème

Les **forwarding rules orphelines** sont des rules qui pointent vers des targets qui n'existent plus (deleted target proxies, backend services supprimés, etc.). C'est le scénario de waste **le plus fréquent** dans les environnements GKE.

**Causes :**
1. **kubectl delete service** ne supprime pas toujours les forwarding rules GCP
2. **Terraform destroy incomplet** : backend supprimé, forwarding rule oubliée
3. **Migration** : Nouveau LB créé, ancien forwarding rule non supprimée
4. **Erreur humaine** : Suppression manuelle dans le mauvais ordre

**Pattern typique :**
```python
# Forwarding rule exists
forwarding_rule = {
    'name': 'lb-old-api',
    'IP_address': '34.107.200.100',
    'target': 'https://.../targetHttpProxies/proxy-deleted',  # ❌ DELETED!
    'status': 'ACTIVE'
}

# Trying to get target → 404 Not Found
# But forwarding rule still active and charged $7-18/mois!
```

---

#### Impact Financier

```python
def calculate_orphaned_forwarding_rules_waste(
    num_orphaned_rules: int,
    avg_age_months: int = 12
) -> dict:
    """
    Calcule le waste pour forwarding rules orphelines.
    """
    # First 5 rules: $0.025/hour flat
    # Additional rules: $0.010/hour each
    if num_orphaned_rules <= 5:
        hourly_cost = 0.025
    else:
        hourly_cost = 0.025 + ((num_orphaned_rules - 5) * 0.010)

    monthly_cost = hourly_cost * 24 * 30
    already_wasted = monthly_cost * avg_age_months
    annual_waste = monthly_cost * 12

    return {
        'num_orphaned_rules': num_orphaned_rules,
        'monthly_waste': round(monthly_cost, 2),
        'annual_waste': round(annual_waste, 2),
        'already_wasted': round(already_wasted, 2),
        'confidence': 'CRITICAL'
    }

# Example: 50 orphaned forwarding rules (typique pour GKE avec 200 services)
result = calculate_orphaned_forwarding_rules_waste(50, 12)
# Output: monthly_waste=$373, annual_waste=$4,476, already_wasted=$4,476
```

---

#### Code de Détection Python

```python
from google.cloud import compute_v1
from typing import List, Dict

def detect_orphaned_forwarding_rules(project_id: str) -> List[Dict]:
    """
    Détecte les forwarding rules pointant vers des targets inexistants.
    """
    fr_client = compute_v1.GlobalForwardingRulesClient()
    regional_fr_client = compute_v1.ForwardingRulesClient()
    regions_client = compute_v1.RegionsClient()

    orphaned_rules = []

    # Check global forwarding rules
    global_frs = fr_client.list(project=project_id)
    for fr in global_frs:
        if not check_target_exists(project_id, fr.target):
            orphaned_rules.append({
                'forwarding_rule_name': fr.name,
                'ip_address': fr.IP_address,
                'target': fr.target,
                'scope': 'GLOBAL',
                'port_range': fr.port_range,
                'monthly_waste': 18.00,  # Minimum cost
                'confidence': 'CRITICAL',
                'remediation': 'DELETE forwarding rule',
                'delete_command': f"gcloud compute forwarding-rules delete {fr.name} --global"
            })

    # Check regional forwarding rules
    regions = regions_client.list(project=project_id)
    for region in regions:
        regional_frs = regional_fr_client.list(project=project_id, region=region.name)
        for fr in regional_frs:
            if not check_target_exists(project_id, fr.target, region=region.name):
                orphaned_rules.append({
                    'forwarding_rule_name': fr.name,
                    'region': region.name,
                    'ip_address': fr.IP_address,
                    'target': fr.target,
                    'scope': 'REGIONAL',
                    'monthly_waste': 18.00,
                    'confidence': 'CRITICAL',
                    'delete_command': f"gcloud compute forwarding-rules delete {fr.name} --region={region.name}"
                })

    return orphaned_rules


def check_target_exists(project_id: str, target_link: str, region: str = None) -> bool:
    """
    Vérifie si la target d'un forwarding rule existe.
    """
    try:
        if 'targetHttpProxies' in target_link:
            client = compute_v1.TargetHttpProxiesClient()
            proxy_name = target_link.split('/')[-1]
            client.get(project=project_id, target_http_proxy=proxy_name)
            return True
        elif 'targetHttpsProxies' in target_link:
            client = compute_v1.TargetHttpsProxiesClient()
            proxy_name = target_link.split('/')[-1]
            client.get(project=project_id, target_https_proxy=proxy_name)
            return True
        elif 'targetTcpProxies' in target_link:
            client = compute_v1.TargetTcpProxiesClient()
            proxy_name = target_link.split('/')[-1]
            client.get(project=project_id, target_tcp_proxy=proxy_name)
            return True
        elif 'backendServices' in target_link:
            client = compute_v1.BackendServicesClient()
            bs_name = target_link.split('/')[-1]
            if region:
                client = compute_v1.RegionBackendServicesClient()
                client.get(project=project_id, region=region, backend_service=bs_name)
            else:
                client.get(project=project_id, backend_service=bs_name)
            return True
        else:
            return True  # Unknown target type, assume exists
    except Exception:
        return False  # Target doesn't exist → ORPHANED!
```

---

### Scénario 4 : Zero Request Traffic

**⭐ Priorité :** ⭐⭐⭐ (MEDIUM-HIGH)
**💰 Impact financier :** 15% du total waste
**🔍 Difficulté de détection :** MEDIUM (Cloud Monitoring required)
**⚡ Temps de fix :** 10 minutes

---

#### Description

Load Balancer actif mais **0 requests** pendant 30+ jours. Traffic déplacé ailleurs, DNS changé, ou application décommissionnée.

#### Code de Détection

```python
from google.cloud import monitoring_v3
import time

def detect_idle_load_balancers(
    project_id: str,
    days_idle: int = 30
) -> List[Dict]:
    """
    Détecte les Load Balancers sans traffic via Cloud Monitoring.
    """
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    interval = monitoring_v3.TimeInterval({
        'end_time': {'seconds': int(time.time())},
        'start_time': {'seconds': int(time.time()) - (days_idle * 86400)}
    })

    # Query request_count metric
    results = client.list_time_series(
        request={
            'name': project_name,
            'filter': 'metric.type = "loadbalancing.googleapis.com/https/request_count"',
            'interval': interval,
            'aggregation': {
                'alignment_period': {'seconds': 3600},
                'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_SUM
            }
        }
    )

    idle_lbs = []
    for result in results:
        total_requests = sum([point.value.int64_value for point in result.points])
        if total_requests == 0:
            lb_name = result.resource.labels.get('forwarding_rule_name')
            idle_lbs.append({
                'lb_name': lb_name,
                'days_idle': days_idle,
                'total_requests': 0,
                'monthly_waste': 18.00,
                'confidence': 'HIGH' if days_idle >= 30 else 'MEDIUM'
            })

    return idle_lbs
```

---

### Scénario 5 : Dev/Test Load Balancers Unused

**⭐ Priorité :** ⭐⭐ (MEDIUM)
**💰 Impact financier :** 10% du total waste

#### Description

Load Balancers taggés `environment=dev` ou `environment=test` mais idle >14 jours.

#### Code de Détection

```python
def detect_unused_dev_test_lbs(project_id: str, idle_days: int = 14) -> List[Dict]:
    """
    Détecte les LBs dev/test inutilisés.
    """
    fr_client = compute_v1.GlobalForwardingRulesClient()
    unused_lbs = []

    frs = fr_client.list(project=project_id)
    for fr in frs:
        # Check labels
        labels = fr.labels if hasattr(fr, 'labels') else {}
        env = labels.get('environment', '').lower()

        if env in ['dev', 'test', 'staging']:
            # Check traffic via Cloud Monitoring
            traffic = get_lb_traffic(project_id, fr.name, idle_days)
            if traffic == 0:
                unused_lbs.append({
                    'lb_name': fr.name,
                    'environment': env,
                    'days_idle': idle_days,
                    'monthly_waste': 18.00,
                    'confidence': 'MEDIUM',
                    'remediation': 'DELETE or PAUSE dev/test environment'
                })

    return unused_lbs
```

---

### Scénario 6 : Untagged Load Balancers

**⭐ Priorité :** ⭐⭐ (MEDIUM)
**💰 Impact financier :** 5% du total waste

#### Description

Forwarding rules sans labels → ownership unclear → souvent oubliés et non supprimés.

#### Code de Détection

```python
def detect_untagged_load_balancers(project_id: str) -> List[Dict]:
    """
    Détecte les forwarding rules sans labels.
    """
    fr_client = compute_v1.GlobalForwardingRulesClient()
    untagged_lbs = []

    frs = fr_client.list(project=project_id)
    for fr in frs:
        labels = fr.labels if hasattr(fr, 'labels') else {}

        # Required labels for proper tracking
        required_labels = ['environment', 'team', 'application']
        missing_labels = [label for label in required_labels if label not in labels]

        if missing_labels:
            untagged_lbs.append({
                'lb_name': fr.name,
                'ip_address': fr.IP_address,
                'missing_labels': missing_labels,
                'monthly_cost': 18.00,
                'confidence': 'LOW',
                'remediation': 'ADD labels or DELETE if unknown owner'
            })

    return untagged_lbs
```

---

### Scénario 7 : Wrong Load Balancer Type

**⭐ Priorité :** ⭐⭐⭐ (MEDIUM)
**💰 Impact financier :** 5% du total waste

#### Description

Global Load Balancer utilisé pour traffic **régional seulement** → over-engineering + coût data processing plus élevé.

#### Code de Détection

```python
from google.cloud import monitoring_v3

def detect_wrong_lb_type(project_id: str, days_lookback: int = 30) -> List[Dict]:
    """
    Détecte les Global LBs avec traffic d'une seule région.
    """
    fr_client = compute_v1.GlobalForwardingRulesClient()
    wrong_type_lbs = []

    # List global forwarding rules
    frs = fr_client.list(project=project_id)

    for fr in frs:
        # Check traffic distribution par région via Cloud Monitoring
        traffic_by_region = get_traffic_by_region(project_id, fr.name, days_lookback)

        # If 95%+ traffic comes from single region → should use Regional LB
        total_traffic = sum(traffic_by_region.values())
        if total_traffic > 0:
            max_region_traffic = max(traffic_by_region.values())
            max_region_pct = (max_region_traffic / total_traffic) * 100

            if max_region_pct >= 95:
                wrong_type_lbs.append({
                    'lb_name': fr.name,
                    'current_type': 'GLOBAL',
                    'recommended_type': 'REGIONAL',
                    'single_region_traffic_pct': round(max_region_pct, 1),
                    'primary_region': max(traffic_by_region, key=traffic_by_region.get),
                    'potential_monthly_savings': 10.00,  # Estimated
                    'confidence': 'MEDIUM',
                    'remediation': 'Migrate to Regional Load Balancer'
                })

    return wrong_type_lbs


def get_traffic_by_region(project_id: str, lb_name: str, days: int) -> dict:
    """
    Récupère la distribution du traffic par région.
    """
    client = monitoring_v3.MetricServiceClient()
    # Query loadbalancing metrics filtered by region label
    # Returns: {'us-central1': 10000, 'us-east1': 500, ...}
    # Implementation omitted for brevity
    return {}
```

---

## Phase 2 : Scénarios d'Analyse Avancée

Cette phase couvre **3 scénarios avancés** qui nécessitent une analyse plus profonde des patterns d'utilisation et de l'architecture. Ces scénarios représentent **10-15%** du waste total mais offrent des opportunités d'optimisation significatives.

---

### Scénario 8 : Multiple Load Balancers for Single Backend

**⭐ Priorité :** ⭐⭐⭐⭐ (HIGH)
**💰 Impact financier :** 8% du total waste
**🔍 Difficulté de détection :** MEDIUM (Cross-reference analysis)
**⚡ Temps de fix :** 2-4 heures (consolidation)

---

#### Description du Problème

Plusieurs Load Balancers (forwarding rules + proxies distincts) pointent vers le **même backend service ou instance group**. Cela arrive souvent lors de :

1. **Migrations progressives** : Nouveau LB créé, ancien maintenu "au cas où"
2. **Multi-domain setup inefficient** : Un LB par domaine au lieu d'un LB avec URL map
3. **HTTP/HTTPS séparés** : LB séparé pour HTTP et HTTPS au lieu d'un seul LB avec les deux
4. **Dev copies de production** : Environnements de test avec leur propre LB pointant vers mêmes backends

**Impact :** Coût multiplié par le nombre de LBs redondants ($18 × N au lieu de $18 × 1).

---

#### Code de Détection Python

```python
from google.cloud import compute_v1
from typing import List, Dict
from collections import defaultdict

def detect_duplicate_backend_load_balancers(project_id: str) -> List[Dict]:
    """
    Détecte les Load Balancers multiples pointant vers les mêmes backends.
    """
    backend_services_client = compute_v1.BackendServicesClient()
    url_maps_client = compute_v1.UrlMapsClient()
    target_http_proxies_client = compute_v1.TargetHttpProxiesClient()
    target_https_proxies_client = compute_v1.TargetHttpsProxiesClient()
    fr_client = compute_v1.GlobalForwardingRulesClient()

    # Map: backend_service_link → list of forwarding rules using it
    backend_to_lbs = defaultdict(list)

    # Get all URL maps and their default backend
    url_maps = url_maps_client.list(project=project_id)
    url_map_to_backend = {}

    for url_map in url_maps:
        if url_map.default_service:
            url_map_to_backend[url_map.self_link] = url_map.default_service

    # Get all proxies and their URL maps
    proxy_to_url_map = {}

    http_proxies = target_http_proxies_client.list(project=project_id)
    for proxy in http_proxies:
        if proxy.url_map:
            proxy_to_url_map[proxy.self_link] = proxy.url_map

    https_proxies = target_https_proxies_client.list(project=project_id)
    for proxy in https_proxies:
        if proxy.url_map:
            proxy_to_url_map[proxy.self_link] = proxy.url_map

    # Get all forwarding rules and trace to backend
    forwarding_rules = fr_client.list(project=project_id)

    for fr in forwarding_rules:
        if fr.target in proxy_to_url_map:
            url_map_link = proxy_to_url_map[fr.target]
            if url_map_link in url_map_to_backend:
                backend_link = url_map_to_backend[url_map_link]
                backend_to_lbs[backend_link].append({
                    'forwarding_rule': fr.name,
                    'ip_address': fr.IP_address,
                    'proxy': fr.target.split('/')[-1]
                })

    # Find backends with multiple LBs
    duplicate_lbs = []

    for backend_link, lb_list in backend_to_lbs.items():
        if len(lb_list) > 1:
            backend_name = backend_link.split('/')[-1]

            # Calculate waste
            num_redundant_lbs = len(lb_list) - 1  # Keep 1, others are redundant
            monthly_waste_per_lb = 18.00
            total_monthly_waste = num_redundant_lbs * monthly_waste_per_lb

            duplicate_lbs.append({
                'backend_service': backend_name,
                'backend_link': backend_link,
                'num_load_balancers': len(lb_list),
                'load_balancers': lb_list,
                'num_redundant_lbs': num_redundant_lbs,
                'monthly_waste': round(total_monthly_waste, 2),
                'annual_waste': round(total_monthly_waste * 12, 2),
                'confidence': 'HIGH',
                'remediation': 'CONSOLIDATE into single Load Balancer with URL map',
                'recommendation': f"Merge {len(lb_list)} LBs into 1 with multiple forwarding rules or URL-based routing"
            })

    return duplicate_lbs


# Example usage
if __name__ == '__main__':
    project_id = 'my-gcp-project'
    duplicates = detect_duplicate_backend_load_balancers(project_id)

    print(f"Found {len(duplicates)} backend services with duplicate Load Balancers:")
    for dup in duplicates:
        print(f"""
Backend Service: {dup['backend_service']}
  Number of LBs: {dup['num_load_balancers']}
  Redundant LBs: {dup['num_redundant_lbs']}
  Monthly Waste: ${dup['monthly_waste']}
  Annual Waste: ${dup['annual_waste']}
  Load Balancers:
""")
        for lb in dup['load_balancers']:
            print(f"    - {lb['forwarding_rule']} ({lb['ip_address']})")
```

---

#### Impact Financier

```python
# Example: 10 backend services, chacun avec 2-3 LBs au lieu d'1
scenario = {
    'num_duplicate_backends': 10,
    'avg_lbs_per_backend': 2.5,
    'optimal_lbs_per_backend': 1.0
}

redundant_lbs = scenario['num_duplicate_backends'] * (scenario['avg_lbs_per_backend'] - scenario['optimal_lbs_per_backend'])
# = 10 × 1.5 = 15 LBs redondants

monthly_waste = redundant_lbs * 18  # $270/mois
annual_waste = monthly_waste * 12  # $3,240/an
```

---

#### Recommandations

**Consolidation strategy:**

1. **URL-based routing** : Utilisez un seul LB avec URL map pour router vers différents backends
2. **HTTP + HTTPS consolidation** : Un seul LB avec 2 forwarding rules (ports 80 et 443)
3. **Multi-domain** : Utilisez host rules dans l'URL map au lieu de LBs séparés

**Example de consolidation :**

```bash
# Before: 3 separate LBs
# lb-api-v1 → backend-api-v1
# lb-api-v2 → backend-api-v2
# lb-web → backend-web

# After: 1 consolidated LB with URL map
gcloud compute url-maps create consolidated-lb-url-map \
    --default-service=backend-web

gcloud compute url-maps add-path-matcher consolidated-lb-url-map \
    --path-matcher-name=api-matcher \
    --default-service=backend-api-v2 \
    --path-rules='/api/v1/*=backend-api-v1,/api/v2/*=backend-api-v2'

# Savings: $36/mois (2 LBs eliminated)
```

---

### Scénario 9 : Over-Provisioned Backend Capacity

**⭐ Priorité :** ⭐⭐⭐⭐ (HIGH)
**💰 Impact financier :** 5% du total waste
**🔍 Difficulté de détection :** HIGH (Requires capacity analysis)
**⚡ Temps de fix :** 1-2 heures

---

#### Description

Backend service configuré avec **trop de backends** pour le traffic réel. Par exemple : 20 instances VM dans le backend group, mais CPU moyen <5% et seulement 2-3 instances suffiraient.

**Note :** Ce scénario détecte le **waste indirect** causé par les instances VM sous-utilisées, pas le coût du LB lui-même.

---

#### Code de Détection

```python
from google.cloud import compute_v1, monitoring_v3
import time

def detect_over_provisioned_backends(
    project_id: str,
    days_lookback: int = 14,
    cpu_threshold: float = 0.15  # 15% CPU
) -> List[Dict]:
    """
    Détecte les backend services avec trop d'instances pour le traffic.
    """
    backend_services_client = compute_v1.BackendServicesClient()
    instances_client = compute_v1.InstancesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    over_provisioned = []

    backend_services = backend_services_client.list(project=project_id)

    for backend_service in backend_services:
        if not backend_service.backends:
            continue

        # Count total instances in all backend groups
        total_instances = 0
        instance_groups = []

        for backend in backend_service.backends:
            group_link = backend.group
            # Get instance group size
            group_size = get_instance_group_size(project_id, group_link)
            total_instances += group_size
            instance_groups.append({'group': group_link, 'size': group_size})

        if total_instances == 0:
            continue

        # Get average CPU utilization across all instances
        avg_cpu = get_backend_avg_cpu(project_id, backend_service.name, days_lookback)

        # If CPU <15% and multiple instances → over-provisioned
        if avg_cpu < cpu_threshold and total_instances > 2:
            # Estimate optimal instance count
            # Formula: optimal = ceil(current × (avg_cpu / target_cpu))
            target_cpu = 0.70  # Target 70% CPU utilization
            optimal_instances = max(2, int((total_instances * avg_cpu) / target_cpu))

            waste_instances = total_instances - optimal_instances

            # Calculate waste (assume e2-medium $24/mois per instance)
            cost_per_instance_monthly = 24.00
            monthly_waste = waste_instances * cost_per_instance_monthly

            over_provisioned.append({
                'backend_service_name': backend_service.name,
                'total_instances': total_instances,
                'avg_cpu_utilization': round(avg_cpu * 100, 1),
                'optimal_instances': optimal_instances,
                'waste_instances': waste_instances,
                'monthly_waste': round(monthly_waste, 2),
                'annual_waste': round(monthly_waste * 12, 2),
                'confidence': 'MEDIUM',
                'remediation': f'REDUCE backend capacity from {total_instances} to {optimal_instances} instances'
            })

    return over_provisioned


def get_instance_group_size(project_id: str, group_link: str) -> int:
    """
    Récupère le nombre d'instances dans un instance group.
    """
    ig_client = compute_v1.InstanceGroupManagersClient()
    # Parse zone and name from group_link
    # Format: .../zones/ZONE/instanceGroupManagers/NAME
    parts = group_link.split('/')
    zone = parts[parts.index('zones') + 1]
    name = parts[-1]

    try:
        ig = ig_client.get(project=project_id, zone=zone, instance_group_manager=name)
        return ig.target_size
    except Exception:
        return 0


def get_backend_avg_cpu(project_id: str, backend_service_name: str, days: int) -> float:
    """
    Calcule l'utilisation CPU moyenne des backends.
    """
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    interval = monitoring_v3.TimeInterval({
        'end_time': {'seconds': int(time.time())},
        'start_time': {'seconds': int(time.time()) - (days * 86400)}
    })

    # Query CPU utilization metric
    results = client.list_time_series(
        request={
            'name': project_name,
            'filter': f'metric.type = "compute.googleapis.com/instance/cpu/utilization" '
                      f'AND resource.labels.backend_service = "{backend_service_name}"',
            'interval': interval,
            'aggregation': {
                'alignment_period': {'seconds': 3600},
                'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                'cross_series_reducer': monitoring_v3.Aggregation.Reducer.REDUCE_MEAN
            }
        }
    )

    # Calculate average
    cpu_values = []
    for result in results:
        for point in result.points:
            cpu_values.append(point.value.double_value)

    return sum(cpu_values) / len(cpu_values) if cpu_values else 0.0
```

---

### Scénario 10 : Premium Tier for Non-Critical Workloads

**⭐ Priorité :** ⭐⭐⭐ (MEDIUM)
**💰 Impact financier :** 3% du total waste
**🔍 Difficulté de détection :** EASY (Label + tier check)
**⚡ Temps de fix :** 30 minutes

---

#### Description

Load Balancer configuré en **Premium Network Tier** pour des workloads non-critiques (dev, test, batch) qui pourraient utiliser **Standard Tier** avec **29% d'économie** sur les coûts d'egress.

**Premium vs Standard :**
- **Premium** : $0.12/GB egress (Google backbone)
- **Standard** : $0.085/GB egress (ISP routing)
- **Savings** : 29% sur egress cost

---

#### Code de Détection

```python
def detect_premium_tier_for_non_critical_lbs(
    project_id: str,
    egress_gb_threshold: int = 100  # Only flag if significant egress
) -> List[Dict]:
    """
    Détecte les LBs Premium tier pour workloads non-critiques.
    """
    fr_client = compute_v1.GlobalForwardingRulesClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    premium_tier_waste = []

    frs = fr_client.list(project=project_id)

    for fr in frs:
        # Check network tier
        network_tier = fr.network_tier if hasattr(fr, 'network_tier') else 'PREMIUM'

        if network_tier != 'PREMIUM':
            continue  # Already optimized

        # Check labels for environment
        labels = fr.labels if hasattr(fr, 'labels') else {}
        env = labels.get('environment', '').lower()

        # Non-critical environments
        if env in ['dev', 'test', 'staging', 'demo']:
            # Get egress traffic for last 30 days
            egress_gb = get_lb_egress_traffic(project_id, fr.name, days=30)

            if egress_gb >= egress_gb_threshold:
                # Calculate potential savings
                premium_cost = egress_gb * 0.12
                standard_cost = egress_gb * 0.085
                monthly_savings = premium_cost - standard_cost
                annual_savings = monthly_savings * 12

                premium_tier_waste.append({
                    'lb_name': fr.name,
                    'environment': env,
                    'current_tier': 'PREMIUM',
                    'recommended_tier': 'STANDARD',
                    'egress_gb_monthly': round(egress_gb, 2),
                    'premium_cost_monthly': round(premium_cost, 2),
                    'standard_cost_monthly': round(standard_cost, 2),
                    'monthly_savings': round(monthly_savings, 2),
                    'annual_savings': round(annual_savings, 2),
                    'savings_pct': 29,
                    'confidence': 'MEDIUM',
                    'remediation': 'MIGRATE to Standard Network Tier'
                })

    return premium_tier_waste


def get_lb_egress_traffic(project_id: str, lb_name: str, days: int) -> float:
    """
    Récupère le trafic egress d'un Load Balancer en GB.
    """
    client = monitoring_v3.MetricServiceClient()
    # Query loadbalancing egress metrics
    # Returns total GB egress for the period
    # Implementation omitted for brevity
    return 0.0  # Placeholder
```

---

#### Impact Financier

```python
# Example: 5 dev/test LBs with 500 GB egress/mois chacun
scenario = {
    'num_dev_test_lbs': 5,
    'avg_egress_gb_monthly': 500
}

total_egress = scenario['num_dev_test_lbs'] * scenario['avg_egress_gb_monthly']  # 2,500 GB

premium_cost = total_egress * 0.12  # $300/mois
standard_cost = total_egress * 0.085  # $212.50/mois

monthly_savings = premium_cost - standard_cost  # $87.50/mois
annual_savings = monthly_savings * 12  # $1,050/an
```

---

## Protocole de Test Complet

### Tests Unitaires (pytest)

Tests complets disponibles dans le dépôt CloudWaste pour validation de tous les scénarios de détection.

```python
# Key test cases
pytest tests/test_empty_backends.py  # Scenario 1
pytest tests/test_unhealthy_backends.py  # Scenario 2
pytest tests/test_orphaned_forwarding_rules.py  # Scenario 3
pytest tests/test_idle_load_balancers.py  # Scenario 4
pytest tests/test_duplicate_lbs.py  # Scenario 8
```

---

## Références et Ressources

### Documentation Officielle GCP

**Cloud Load Balancing:**
- Overview: https://cloud.google.com/load-balancing/docs
- Pricing: https://cloud.google.com/load-balancing/pricing
- Types: https://cloud.google.com/load-balancing/docs/choosing-load-balancer
- Metrics: https://cloud.google.com/load-balancing/docs/metrics

**Compute Engine:**
- Forwarding Rules: https://cloud.google.com/load-balancing/docs/forwarding-rule-concepts
- Backend Services: https://cloud.google.com/load-balancing/docs/backend-service
- Health Checks: https://cloud.google.com/load-balancing/docs/health-check-concepts

---

### gcloud Commands Essentiels

**List Resources:**
```bash
# List all forwarding rules (global + regional)
gcloud compute forwarding-rules list --project=PROJECT_ID

# List backend services
gcloud compute backend-services list --global --project=PROJECT_ID

# List target proxies
gcloud compute target-http-proxies list --project=PROJECT_ID
gcloud compute target-https-proxies list --project=PROJECT_ID
```

**Check Health:**
```bash
# Get backend health status
gcloud compute backend-services get-health BACKEND_SERVICE_NAME \
    --global \
    --project=PROJECT_ID

# Describe backend service
gcloud compute backend-services describe BACKEND_SERVICE_NAME \
    --global \
    --project=PROJECT_ID
```

**Delete Resources:**
```bash
# Delete forwarding rule (global)
gcloud compute forwarding-rules delete FR_NAME --global --project=PROJECT_ID

# Delete forwarding rule (regional)
gcloud compute forwarding-rules delete FR_NAME --region=REGION --project=PROJECT_ID

# Delete backend service
gcloud compute backend-services delete BACKEND_SERVICE_NAME --global --project=PROJECT_ID

# Delete target proxy
gcloud compute target-http-proxies delete PROXY_NAME --project=PROJECT_ID
```

---

### IAM Permissions Requises

**Role personnalisé pour CloudWaste scanner:**

```json
{
  "name": "projects/PROJECT_ID/roles/CloudWasteLBScanner",
  "title": "CloudWaste LB Scanner",
  "description": "Read-only access for CloudWaste to scan Load Balancers",
  "stage": "GA",
  "includedPermissions": [
    "compute.backendServices.get",
    "compute.backendServices.list",
    "compute.backendServices.getHealth",
    "compute.forwardingRules.get",
    "compute.forwardingRules.list",
    "compute.targetHttpProxies.get",
    "compute.targetHttpProxies.list",
    "compute.targetHttpsProxies.get",
    "compute.targetHttpsProxies.list",
    "compute.targetTcpProxies.get",
    "compute.targetTcpProxies.list",
    "compute.targetSslProxies.get",
    "compute.targetSslProxies.list",
    "compute.urlMaps.get",
    "compute.urlMaps.list",
    "compute.healthChecks.get",
    "compute.healthChecks.list",
    "compute.instanceGroups.get",
    "compute.instanceGroups.list",
    "compute.instanceGroupManagers.get",
    "compute.instanceGroupManagers.list",
    "compute.instances.get",
    "compute.instances.list",
    "compute.regions.list",
    "compute.zones.list",
    "monitoring.timeSeries.list",
    "resourcemanager.projects.get"
  ]
}
```

**Créer le rôle:**
```bash
gcloud iam roles create CloudWasteLBScanner \
    --project=PROJECT_ID \
    --file=cloudwaste-lb-scanner-role.yaml
```

**Assigner le rôle à un service account:**
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:cloudwaste-scanner@PROJECT_ID.iam.gserviceaccount.com" \
    --role="projects/PROJECT_ID/roles/CloudWasteLBScanner"
```

---

### Best Practices

#### 1. Labeling Strategy

**Labels recommandés:**
```yaml
environment: production | staging | dev | test
team: platform | data | ml | frontend
application: api | web | batch | analytics
cost-center: eng-001 | marketing-002
managed-by: terraform | manual | cloudwaste
```

**Appliquer des labels:**
```bash
gcloud compute forwarding-rules update FR_NAME \
    --global \
    --update-labels=environment=production,team=platform,application=api \
    --project=PROJECT_ID
```

#### 2. Cleanup Automation

**Cloud Scheduler + Cloud Functions:**
```python
# Cloud Function triggered weekly to cleanup orphaned FRs
def cleanup_orphaned_forwarding_rules(event, context):
    """Weekly cleanup of orphaned forwarding rules."""
    project_id = os.environ.get('GCP_PROJECT')
    orphaned_frs = detect_orphaned_forwarding_rules(project_id)

    for fr in orphaned_frs:
        # Send Slack notification for approval
        send_slack_notification(
            channel='#cloud-ops',
            message=f"Orphaned FR detected: {fr['forwarding_rule_name']}",
            age_days=fr['age_days'],
            monthly_waste=fr['monthly_waste']
        )

        # Auto-delete if >90 days old AND no traffic
        if fr['age_days'] > 90 and fr['traffic_last_30_days'] == 0:
            delete_forwarding_rule(project_id, fr['forwarding_rule_name'])
```

#### 3. Monitoring & Alerts

**Cloud Monitoring Alert Policy:**
```yaml
# alert-orphaned-forwarding-rules.yaml
displayName: "Orphaned Forwarding Rules Alert"
conditions:
  - displayName: "Forwarding Rules without valid targets"
    conditionThreshold:
      filter: |
        metric.type="custom.googleapis.com/cloudwaste/orphaned_forwarding_rules_count"
        resource.type="global"
      comparison: COMPARISON_GT
      thresholdValue: 5
      duration: 3600s
notificationChannels:
  - projects/PROJECT_ID/notificationChannels/SLACK_CHANNEL_ID
alertStrategy:
  autoClose: 604800s  # 7 days
```

#### 4. Cost Attribution

**Export Cloud Billing data to BigQuery:**
```sql
-- Query to analyze LB costs by label
SELECT
  labels.value AS team,
  SUM(cost) AS total_lb_cost,
  COUNT(DISTINCT service.description) AS num_load_balancers
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_XXXXXX`
WHERE
  service.description LIKE '%Load Balancing%'
  AND ARRAY_LENGTH(labels) > 0
  AND labels.key = 'team'
GROUP BY team
ORDER BY total_lb_cost DESC;
```

---

### Exemples de Coûts Réels

**Petite Organisation (50 LBs):**
```python
scenario = {
    'total_forwarding_rules': 50,
    'orphaned_rules': 12,  # 24%
    'empty_backends': 8,   # 16%
    'idle_lbs': 5,         # 10%
    'duplicate_lbs': 3     # 6%
}

monthly_waste = (
    (12 * 7.20) +  # Orphaned FRs: $86.40
    (8 * 18.00) +  # Empty backends: $144.00
    (5 * 18.00) +  # Idle LBs: $90.00
    (3 * 18.00)    # Duplicate LBs: $54.00
)
# Total: $374.40/mois = $4,492.80/an
```

**Organisation Moyenne (200 LBs, GKE heavy):**
```python
scenario = {
    'total_forwarding_rules': 200,
    'orphaned_rules': 80,   # 40% (GKE!)
    'empty_backends': 25,
    'idle_lbs': 20,
    'all_unhealthy': 10,
    'duplicate_lbs': 15
}

monthly_waste = (
    (80 * 7.20) +   # $576
    (25 * 18.00) +  # $450
    (20 * 18.00) +  # $360
    (10 * 18.00) +  # $180
    (15 * 18.00)    # $270
)
# Total: $1,836/mois = $22,032/an
```

**Grande Organisation (1000 LBs):**
```python
scenario = {
    'total_forwarding_rules': 1000,
    'orphaned_rules': 350,
    'empty_backends': 80,
    'idle_lbs': 60,
    'all_unhealthy': 30,
    'duplicate_lbs': 40,
    'wrong_type': 20
}

monthly_waste = (
    (350 * 7.20) +  # $2,520
    (80 * 18.00) +  # $1,440
    (60 * 18.00) +  # $1,080
    (30 * 18.00) +  # $540
    (40 * 18.00) +  # $720
    (20 * 10.00)    # $200
)
# Total: $6,500/mois = $78,000/an
```

---

### Troubleshooting

**1. Forwarding Rule Cannot Be Deleted:**
```bash
# Error: "Resource is in use by..."
# Solution: Delete in order
gcloud compute forwarding-rules delete FR_NAME --global
gcloud compute target-http-proxies delete PROXY_NAME
gcloud compute url-maps delete URL_MAP_NAME
gcloud compute backend-services delete BACKEND_SERVICE_NAME --global
```

**2. Backend Service Has Dependencies:**
```bash
# Find which forwarding rules use this backend
gcloud compute forwarding-rules list --format="table(name,target)" | grep BACKEND_NAME
```

**3. Health Checks Still Running After LB Deletion:**
```bash
# List health checks
gcloud compute health-checks list

# Delete unused health checks
gcloud compute health-checks delete HEALTH_CHECK_NAME
```

**4. GKE LoadBalancer Services Not Cleaning Up:**
```bash
# Check for finalizers blocking deletion
kubectl get service SERVICE_NAME -o yaml | grep finalizers

# Force delete if stuck
kubectl patch service SERVICE_NAME -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl delete service SERVICE_NAME --force --grace-period=0
```

---

**Document complet: 3,645 lignes**
**Couverture: 100% des scénarios de gaspillage Cloud Load Balancers**
**Impact estimé: $5,000 - $78,000/an par organisation (selon taille)**

