# GCP Cloud Filestore - 100% des Scénarios de Gaspillage

**Version:** 1.0
**Date:** 2025-01-03
**Ressource GCP:** `Storage: Filestore`
**Impact estimé:** $10,000 - $60,000/an par organisation
**Catégorie:** Network-attached storage (NAS) haute performance

---

## Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Architecture et Modèle de Pricing](#architecture-et-modèle-de-pricing)
3. [Phase 1 : Scénarios de Détection Simples](#phase-1--scénarios-de-détection-simples)
   - [Scénario 1 : Filestore Instances Sous-Utilisées](#scénario-1--filestore-instances-sous-utilisées)
   - [Scénario 2 : Wrong Tier (Enterprise pour Dev/Test)](#scénario-2--wrong-tier-enterprise-pour-devtest)
   - [Scénario 3 : Filestore Instances Idle (0 Connections)](#scénario-3--filestore-instances-idle-0-connections)
   - [Scénario 4 : Overprovisioned Capacity](#scénario-4--overprovisioned-capacity)
   - [Scénario 5 : Filestore Instances Untagged](#scénario-5--filestore-instances-untagged)
   - [Scénario 6 : No Backup Policy](#scénario-6--no-backup-policy)
   - [Scénario 7 : Legacy Tier (Basic HDD vs Zonal)](#scénario-7--legacy-tier-basic-hdd-vs-zonal)
4. [Phase 2 : Scénarios d'Analyse Avancée](#phase-2--scénarios-danalyse-avancée)
   - [Scénario 8 : Multi-Share Consolidation Opportunity](#scénario-8--multi-share-consolidation-opportunity)
   - [Scénario 9 : Snapshot Waste (Old Snapshots)](#scénario-9--snapshot-waste-old-snapshots)
   - [Scénario 10 : Wrong NFS Protocol (NFSv3 vs v4.1)](#scénario-10--wrong-nfs-protocol-nfsv3-vs-v41)
5. [Protocole de Test Complet](#protocole-de-test-complet)
6. [Références et Ressources](#références-et-ressources)

---

## Vue d'Ensemble

### Qu'est-ce que Cloud Filestore ?

**Cloud Filestore** est le service de stockage de fichiers entièrement managé de Google Cloud Platform. Il fournit des partages de fichiers réseau (NFS) haute performance pour les applications qui nécessitent un système de fichiers traditionnel.

**Caractéristiques principales :**
- **Protocole NFS** standard (v3 et v4.1)
- **Performance scalable** : jusqu'à 100,000 IOPS et 2 GB/s de throughput
- **5 tiers de service** : Zonal, Basic HDD, Basic SSD, High Scale SSD, Enterprise
- **Capacités** : de 1 TB à 100 TB (selon le tier)
- **Backups automatiques** : schedules configurables
- **Multi-share** : jusqu'à 10 shares par instance (Enterprise)
- **Montage concurrent** : milliers de clients simultanés

### Cas d'Usage Principaux

1. **Content Management Systems** - WordPress, Drupal, Joomla
2. **Media Processing** - Render farms, video transcoding
3. **Genomics Workloads** - Analyse de données biologiques
4. **Enterprise Applications** - ERP, CRM legacy nécessitant NFS
5. **Development Environments** - Shared code repositories
6. **Home Directories** - User home directories pour GKE/GCE

### Pourquoi Cloud Filestore est-il Critique pour la Détection de Gaspillage ?

Cloud Filestore présente des risques de gaspillage significatifs pour **3 raisons majeures** :

#### 1. **Facturation sur Capacité Provisionnée (NON Utilisée)**

**Contrairement à Cloud Storage** (qui facture uniquement les données stockées), **Filestore facture la capacité provisionnée**, que vous l'utilisiez ou non.

**Exemple concret :**
```python
# Filestore 10 TB provisionné, 2 TB réellement utilisé
provisioned_capacity_tb = 10
actual_usage_tb = 2
tier_price_per_gb = 0.20  # Basic HDD

# Coût mensuel
monthly_cost = provisioned_capacity_tb * 1024 * tier_price_per_gb
# = 10 * 1024 * $0.20 = $2,048/mois

# Coût optimal (provision 3 TB avec 20% buffer)
optimal_cost = 3 * 1024 * 0.20  # $614.40/mois

# Gaspillage annuel
annual_waste = (monthly_cost - optimal_cost) * 12  # $17,203/an
```

**Conséquence :** Une instance provisionnée à 20% d'utilisation gaspille **80% de son budget**.

#### 2. **Différences de Prix Entre Tiers Extrêmes**

Les 5 tiers de Filestore ont des prix variant de **1:3.3** (Zonal vs Enterprise).

**Tableau comparatif :**
```
Tier               | Prix/GB/Mois | Instance 5 TB/Mois | Performance
------------------|--------------|--------------------|--------------
Zonal             | $0.18        | $921.60           | Basic
Basic HDD         | $0.20        | $1,024.00         | Standard
Basic SSD         | $0.30        | $1,536.00         | Fast
High Scale SSD    | $0.30        | $1,536.00         | Very Fast
Enterprise        | $0.60        | $3,072.00         | Multi-share
```

**Gaspillage typique :**
- Utiliser Enterprise pour environnement de développement (233% plus cher que Zonal)
- Utiliser Basic SSD pour cold data (67% plus cher que Basic HDD)

#### 3. **Instances Idle et Oubliées**

Les instances Filestore sont souvent créées pour des projets temporaires et oubliées :
- POCs/tests abandonnés
- Environnements de dev/staging non supprimés
- Migration d'applications terminée (données déjà copiées ailleurs)

**Impact :**
- Une instance 5 TB Enterprise idle = **$36,864/an gaspillés**
- Coût silencieux car aucune alerte automatique

### Métriques Clés pour la Détection

Cloud Filestore expose plusieurs métriques via **Cloud Monitoring API** :

| Métrique | Type | Utilité |
|----------|------|---------|
| `file.googleapis.com/nfs/server/used_bytes_percent` | Gauge | Taux d'utilisation (0-100%) |
| `file.googleapis.com/nfs/server/used_bytes` | Gauge | Bytes utilisés |
| `file.googleapis.com/nfs/server/free_bytes` | Gauge | Bytes disponibles |
| `file.googleapis.com/nfs/server/read_ops_count` | Counter | Nombre d'opérations de lecture |
| `file.googleapis.com/nfs/server/write_ops_count` | Counter | Nombre d'opérations d'écriture |
| `file.googleapis.com/nfs/server/connections` | Gauge | Nombre de connexions actives |
| `file.googleapis.com/nfs/server/procedure_count` | Counter | Appels NFS par type |

**Détection de gaspillage typique :**
```python
# Instance sous-utilisée
if used_bytes_percent < 30:
    waste_category = "UNDERUTILIZED"

# Instance idle
if connections == 0 and (read_ops + write_ops) == 0:
    waste_category = "IDLE"

# Instance overprovisionnée
if used_bytes_percent < 10:
    waste_category = "OVERPROVISIONED"
```

### Scope de Couverture : 100% des Scénarios

Ce document couvre **10 scénarios** représentant **100% des patterns de gaspillage** observés en production :

**Phase 1 - Détection Simple (7 scénarios) :**
1. Instances sous-utilisées (<30% capacity)
2. Wrong tier (Enterprise pour dev/test)
3. Instances idle (0 connections + 0 I/O)
4. Overprovisioned capacity (<10% utilisé)
5. Instances untagged (non catégorisées)
6. No backup policy (risque + coût)
7. Legacy tier (Basic HDD vs Zonal moderne)

**Phase 2 - Analyse Avancée (3 scénarios) :**
8. Multi-share consolidation (Enterprise sous-utilisé)
9. Snapshot waste (snapshots anciens jamais utilisés)
10. Wrong NFS protocol (v3 vs v4.1 performance)

**Impact total estimé :** $10,000 - $60,000/an par organisation

---

## Architecture et Modèle de Pricing

### Architecture Cloud Filestore

Cloud Filestore propose **5 tiers** avec des caractéristiques distinctes :

#### 1. **Zonal Tier** (Lancé 2023, recommandé pour la plupart des workloads)

**Caractéristiques :**
- **Capacité :** 1 TB - 10 TB
- **Prix :** $0.18/GB/mois
- **Performance :** 100 MB/s par TB (read), 100 MB/s par TB (write)
- **IOPS :** 5,000 par TB
- **Disponibilité :** 1 zone (99.9% SLA)
- **Backups :** Supportés
- **Multi-share :** Non (1 share par instance)

**Cas d'usage :**
- Applications standard nécessitant NFS
- Dev/test/staging environments
- Workloads tolérant une panne de zone courte

**Pricing exemple :**
```python
# Instance 5 TB Zonal
capacity_tb = 5
price_per_gb = 0.18

monthly_cost = capacity_tb * 1024 * price_per_gb  # $921.60/mois
annual_cost = monthly_cost * 12  # $11,059.20/an
```

#### 2. **Basic HDD Tier** (Original tier, moins recommandé maintenant)

**Caractéristiques :**
- **Capacité :** 1 TB - 10 TB
- **Prix :** $0.20/GB/mois
- **Performance :** 100 MB/s par TB (read), 100 MB/s par TB (write)
- **IOPS :** 5,000 par TB
- **Disponibilité :** 1 zone (99.9% SLA)
- **Backups :** Supportés
- **Multi-share :** Non

**Note :** Zonal tier (plus récent) est 10% moins cher avec mêmes performances. **Migration recommandée.**

#### 3. **Basic SSD Tier**

**Caractéristiques :**
- **Capacité :** 2.5 TB - 10 TB (min varie par région)
- **Prix :** $0.30/GB/mois
- **Performance :** 180 MB/s par TB (read), 120 MB/s par TB (write)
- **IOPS :** 8,000 par TB
- **Disponibilité :** 1 zone (99.9% SLA)
- **Backups :** Supportés
- **Multi-share :** Non

**Cas d'usage :**
- Workloads nécessitant IOPS élevés
- Bases de données NFS
- Media processing workloads

**Performance comparison :**
```python
# Instance 5 TB Basic HDD vs Basic SSD
capacity_tb = 5

# Basic HDD
hdd_throughput_mb = capacity_tb * 100  # 500 MB/s
hdd_iops = capacity_tb * 5000  # 25,000 IOPS
hdd_cost = capacity_tb * 1024 * 0.20  # $1,024/mois

# Basic SSD
ssd_throughput_mb = capacity_tb * 180  # 900 MB/s (80% faster)
ssd_iops = capacity_tb * 8000  # 40,000 IOPS (60% faster)
ssd_cost = capacity_tb * 1024 * 0.30  # $1,536/mois (50% plus cher)
```

#### 4. **High Scale SSD Tier**

**Caractéristiques :**
- **Capacité :** 10 TB - 100 TB
- **Prix :** $0.30/GB/mois
- **Performance :** 1,200 MB/s fixe (max), IOPS scaling
- **IOPS :** 100,000 max
- **Disponibilité :** 1 zone (99.9% SLA)
- **Backups :** Supportés
- **Multi-share :** Non

**Cas d'usage :**
- Workloads très large scale
- Render farms
- Genomics pipelines

**Note :** Prix identique à Basic SSD mais capacité min 10 TB. Performance scale jusqu'à 100 TB.

#### 5. **Enterprise Tier** (Premium, multi-share)

**Caractéristiques :**
- **Capacité :** 1 TB - 10 TB
- **Prix :** $0.60/GB/mois (200% plus cher que Zonal)
- **Performance :** 100 MB/s par TB (read), 100 MB/s par TB (write)
- **IOPS :** 5,000 par TB
- **Disponibilité :** Multi-zone (99.99% SLA - 10x meilleur)
- **Backups :** Supportés
- **Multi-share :** Jusqu'à 10 shares par instance

**Cas d'usage :**
- Applications critiques nécessitant haute disponibilité
- Multi-tenancy (plusieurs applications sur 1 instance)
- Consolidation de plusieurs shares

**Pricing exemple :**
```python
# Instance 5 TB Enterprise avec 3 shares
capacity_tb = 5
price_per_gb = 0.60
num_shares = 3

# Coût total
monthly_cost = capacity_tb * 1024 * price_per_gb  # $3,072/mois

# Coût par share (si consolidation)
cost_per_share = monthly_cost / num_shares  # $1,024/mois par share

# Comparaison : 3 instances Zonal séparées
zonal_cost = (capacity_tb / num_shares) * 1024 * 0.18 * num_shares
# = 1.67 TB * 1024 * 0.18 * 3 = $920.58/mois

# Enterprise est 233% plus cher dans ce cas
```

### Modèle de Pricing Détaillé

#### Pricing de Base (Capacité Provisionnée)

**Règle fondamentale :** Filestore facture **100% de la capacité provisionnée**, pas la capacité utilisée.

```python
def calculate_filestore_monthly_cost(
    capacity_tb: float,
    tier: str
) -> float:
    """
    Calcule le coût mensuel Filestore basé sur capacité provisionnée.

    Args:
        capacity_tb: Capacité provisionnée en TB
        tier: 'zonal', 'basic_hdd', 'basic_ssd', 'high_scale_ssd', 'enterprise'

    Returns:
        Coût mensuel en USD
    """
    tier_pricing = {
        'zonal': 0.18,
        'basic_hdd': 0.20,
        'basic_ssd': 0.30,
        'high_scale_ssd': 0.30,
        'enterprise': 0.60
    }

    price_per_gb = tier_pricing[tier]
    capacity_gb = capacity_tb * 1024

    monthly_cost = capacity_gb * price_per_gb
    return monthly_cost


# Exemple : 5 TB Zonal avec 2 TB utilisés
provisioned_tb = 5
used_tb = 2
tier = 'zonal'

monthly_cost = calculate_filestore_monthly_cost(provisioned_tb, tier)
# = $921.60/mois (facturé sur 5 TB, pas 2 TB)

utilization_percent = (used_tb / provisioned_tb) * 100  # 40%
```

#### Pricing des Backups/Snapshots

Les backups Filestore sont facturés séparément :

**Prix :** $0.10/GB/mois (identique pour tous les tiers)

```python
def calculate_filestore_backup_cost(
    used_capacity_tb: float,
    num_backups: int = 7  # ex: 7 daily backups
) -> float:
    """
    Calcule le coût mensuel des backups Filestore.

    Note: Backups sont facturés sur capacité UTILISÉE, pas provisionnée.
    """
    backup_price_per_gb = 0.10

    # Chaque backup contient les données utilisées
    total_backup_capacity_gb = used_capacity_tb * 1024 * num_backups

    monthly_backup_cost = total_backup_capacity_gb * backup_price_per_gb
    return monthly_backup_cost


# Exemple : Instance 10 TB avec 6 TB utilisés, 7 backups daily
used_tb = 6
num_backups = 7

backup_cost = calculate_filestore_backup_cost(used_tb, num_backups)
# = 6 * 1024 * 7 * $0.10 = $4,300.80/mois
```

**Important :** Le coût des backups peut **dépasser le coût de l'instance** avec des policies de rétention agressives.

#### Coûts de Transfert Réseau (Egress)

Le trafic réseau sortant est facturé selon la grille standard GCP :

| Destination | Prix/GB |
|-------------|---------|
| Même zone GCP | Gratuit |
| Même région (inter-zone) | Gratuit |
| Autre région GCP (même continent) | $0.01 |
| Inter-continental | $0.08 - $0.15 |
| Internet | $0.12 - $0.23 |

**Note :** Trafic Filestore → GCE/GKE dans la même zone = **0$**.

#### Formule de Coût Total

```python
def calculate_total_filestore_cost(
    provisioned_capacity_tb: float,
    used_capacity_tb: float,
    tier: str,
    num_backups: int = 7,
    egress_gb_per_month: float = 0
) -> dict:
    """
    Calcule le coût total mensuel Filestore.

    Returns:
        Dict avec breakdown des coûts
    """
    # Coût de l'instance (capacité provisionnée)
    tier_pricing = {
        'zonal': 0.18,
        'basic_hdd': 0.20,
        'basic_ssd': 0.30,
        'high_scale_ssd': 0.30,
        'enterprise': 0.60
    }

    instance_cost = provisioned_capacity_tb * 1024 * tier_pricing[tier]

    # Coût des backups (capacité utilisée)
    backup_cost = used_capacity_tb * 1024 * num_backups * 0.10

    # Coût d'egress (simplifié : $0.12/GB average)
    egress_cost = egress_gb_per_month * 0.12

    total_cost = instance_cost + backup_cost + egress_cost

    return {
        'instance_cost': instance_cost,
        'backup_cost': backup_cost,
        'egress_cost': egress_cost,
        'total_monthly_cost': total_cost,
        'total_annual_cost': total_cost * 12
    }


# Exemple réaliste
costs = calculate_total_filestore_cost(
    provisioned_capacity_tb=10,
    used_capacity_tb=6,
    tier='basic_hdd',
    num_backups=7,
    egress_gb_per_month=500
)

print(costs)
# {
#     'instance_cost': 2048.0,      # $2,048/mois
#     'backup_cost': 4300.8,        # $4,301/mois (plus cher que l'instance!)
#     'egress_cost': 60.0,          # $60/mois
#     'total_monthly_cost': 6408.8, # $6,409/mois
#     'total_annual_cost': 76905.6  # $76,906/an
# }
```

**Observation critique :** Les backups peuvent représenter **67% du coût total** dans cet exemple.

### Comparaison de Performance par Tier

| Tier | Capacity Range | Read MB/s | Write MB/s | IOPS | Prix/GB | SLA |
|------|---------------|-----------|------------|------|---------|-----|
| Zonal | 1-10 TB | 100/TB | 100/TB | 5K/TB | $0.18 | 99.9% |
| Basic HDD | 1-10 TB | 100/TB | 100/TB | 5K/TB | $0.20 | 99.9% |
| Basic SSD | 2.5-10 TB | 180/TB | 120/TB | 8K/TB | $0.30 | 99.9% |
| High Scale SSD | 10-100 TB | 1200 max | 1200 max | 100K max | $0.30 | 99.9% |
| Enterprise | 1-10 TB | 100/TB | 100/TB | 5K/TB | $0.60 | 99.99% |

**Exemple performance scaling :**
```python
# Instance 5 TB sur différents tiers
capacity_tb = 5

tiers = {
    'zonal': {
        'read_mb_s': 100 * capacity_tb,      # 500 MB/s
        'write_mb_s': 100 * capacity_tb,     # 500 MB/s
        'iops': 5000 * capacity_tb,          # 25,000 IOPS
        'monthly_cost': capacity_tb * 1024 * 0.18  # $921.60
    },
    'basic_ssd': {
        'read_mb_s': 180 * capacity_tb,      # 900 MB/s (+80%)
        'write_mb_s': 120 * capacity_tb,     # 600 MB/s (+20%)
        'iops': 8000 * capacity_tb,          # 40,000 IOPS (+60%)
        'monthly_cost': capacity_tb * 1024 * 0.30  # $1,536 (+67% cost)
    },
    'enterprise': {
        'read_mb_s': 100 * capacity_tb,      # 500 MB/s (identique à Zonal)
        'write_mb_s': 100 * capacity_tb,     # 500 MB/s (identique à Zonal)
        'iops': 5000 * capacity_tb,          # 25,000 IOPS (identique à Zonal)
        'monthly_cost': capacity_tb * 1024 * 0.60,  # $3,072 (+233% cost)
        'multi_share': True,
        'sla': 0.9999
    }
}
```

**Conclusion :** Enterprise est 233% plus cher que Zonal **pour la même performance**. Le surcoût est justifié uniquement par :
- Multi-zone HA (SLA 99.99% vs 99.9%)
- Support de multi-share (10 shares par instance)

### Règles de Dimensionnement

**Capacités minimales par tier :**
```python
min_capacity_tb = {
    'zonal': 1.0,
    'basic_hdd': 1.0,
    'basic_ssd': 2.5,  # Varie par région (1 TB dans certaines)
    'high_scale_ssd': 10.0,
    'enterprise': 1.0
}
```

**Incréments de capacité :**
- Tous les tiers : par incréments de **256 GB** (0.25 TB)

**Limites par projet :**
- **100 instances** Filestore par projet (soft limit, peut être augmenté)

### Migrations Entre Tiers

**Migrations supportées (sans downtime) :**
- Basic HDD → Zonal ✅
- Basic HDD → Basic SSD ✅
- Basic SSD → High Scale SSD ✅ (si capacity ≥ 10 TB)
- Zonal → Enterprise ✅
- Basic HDD → Enterprise ✅

**Migrations NON supportées :**
- Tier supérieur → Tier inférieur ❌ (ex: Enterprise → Zonal)
- High Scale SSD → Basic SSD ❌

**Procédure de migration :**
```bash
gcloud filestore instances update INSTANCE_NAME \
    --zone=ZONE \
    --tier=TIER \
    --project=PROJECT_ID
```

**Downtime :** 0 secondes (migration transparente)

---

## Phase 1 : Scénarios de Détection Simples

### Scénario 1 : Filestore Instances Sous-Utilisées

**Description :**
Instances Filestore avec un taux d'utilisation de capacité **< 30%** pendant une période prolongée (≥ 14 jours). Ces instances gaspillent de l'argent car Filestore facture sur la capacité **provisionnée**, pas utilisée.

**Pourquoi c'est un problème :**
- Filestore coûte $0.18-$0.60/GB/mois **même si l'espace est vide**
- Une instance 10 TB utilisée à 20% (2 TB) gaspille **$14,000/an** (tier Zonal)
- Downsizing permet économie immédiate (migration sans downtime)

**Seuils de Détection :**
```python
UNDERUTILIZATION_THRESHOLDS = {
    'critical': 0.10,   # <10% utilisé pendant 30 jours
    'high': 0.20,       # <20% utilisé pendant 21 jours
    'medium': 0.30,     # <30% utilisé pendant 14 jours
    'low': 0.40         # <40% utilisé pendant 7 jours
}
```

**Métrique Utilisée :**
- `file.googleapis.com/nfs/server/used_bytes_percent` (Gauge)

**Code de Détection Python :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_underutilized(
    project_id: str,
    utilization_threshold: float = 0.30,
    lookback_days: int = 14
) -> List[Dict]:
    """
    Détecte les instances Filestore sous-utilisées (<30% capacity).

    Args:
        project_id: GCP project ID
        utilization_threshold: Seuil d'utilisation (0.30 = 30%)
        lookback_days: Période d'observation (14 jours par défaut)

    Returns:
        Liste d'instances sous-utilisées avec détails et coût gaspillé
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    underutilized_instances = []

    # Liste toutes les instances Filestore
    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]

        # Récupère les métriques d'utilisation
        utilization_metrics = get_filestore_utilization_metrics(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone,
            lookback_days=lookback_days
        )

        if not utilization_metrics:
            logger.warning(f"Aucune métrique pour {instance_name}")
            continue

        avg_utilization = utilization_metrics['avg_utilization_percent'] / 100

        # Vérifie si sous-utilisé
        if avg_utilization < utilization_threshold:
            # Calcule le gaspillage
            waste_analysis = calculate_filestore_waste(
                instance=instance,
                avg_utilization=avg_utilization
            )

            # Détermine confidence level
            confidence = determine_confidence_level(
                avg_utilization=avg_utilization,
                lookback_days=lookback_days
            )

            underutilized_instances.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': instance.tier.name,
                'provisioned_capacity_gb': instance.file_shares[0].capacity_gb,
                'used_capacity_gb': waste_analysis['used_capacity_gb'],
                'utilization_percent': avg_utilization * 100,
                'monthly_cost_current': waste_analysis['current_monthly_cost'],
                'monthly_cost_optimal': waste_analysis['optimal_monthly_cost'],
                'monthly_waste': waste_analysis['monthly_waste'],
                'annual_waste': waste_analysis['annual_waste'],
                'recommended_capacity_gb': waste_analysis['recommended_capacity_gb'],
                'confidence': confidence,
                'lookback_days': lookback_days,
                'labels': dict(instance.labels) if instance.labels else {}
            })

    # Trie par waste annuel décroissant
    underutilized_instances.sort(key=lambda x: x['annual_waste'], reverse=True)

    return underutilized_instances


def get_filestore_utilization_metrics(
    project_id: str,
    instance_name: str,
    zone: str,
    lookback_days: int
) -> Dict:
    """
    Récupère les métriques d'utilisation via Cloud Monitoring API.
    """
    monitoring_client = monitoring_v3.MetricServiceClient()

    project_name = f"projects/{project_id}"

    # Période
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time.timestamp())},
        "start_time": {"seconds": int(start_time.timestamp())},
    })

    # Query pour used_bytes_percent
    filter_str = (
        f'resource.type = "filestore_instance" '
        f'AND resource.labels.instance_name = "{instance_name}" '
        f'AND resource.labels.zone = "{zone}" '
        f'AND metric.type = "file.googleapis.com/nfs/server/used_bytes_percent"'
    )

    aggregation = monitoring_v3.Aggregation({
        "alignment_period": {"seconds": 3600},  # 1 heure
        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    })

    try:
        results = monitoring_client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_str,
                "interval": interval,
                "aggregation": aggregation,
            }
        )

        utilization_values = []
        for result in results:
            for point in result.points:
                utilization_values.append(point.value.double_value)

        if not utilization_values:
            return None

        avg_utilization = sum(utilization_values) / len(utilization_values)
        max_utilization = max(utilization_values)
        min_utilization = min(utilization_values)

        return {
            'avg_utilization_percent': avg_utilization,
            'max_utilization_percent': max_utilization,
            'min_utilization_percent': min_utilization,
            'num_samples': len(utilization_values)
        }

    except Exception as e:
        logger.error(f"Erreur monitoring metrics: {e}")
        return None


def calculate_filestore_waste(
    instance: filestore_v1.Instance,
    avg_utilization: float
) -> Dict:
    """
    Calcule le gaspillage financier d'une instance sous-utilisée.
    """
    # Prix par tier ($/GB/mois)
    tier_pricing = {
        'STANDARD': 0.20,        # Basic HDD (legacy name)
        'PREMIUM': 0.30,         # Basic SSD (legacy name)
        'BASIC_HDD': 0.20,
        'BASIC_SSD': 0.30,
        'HIGH_SCALE_SSD': 0.30,
        'ENTERPRISE': 0.60,
        'ZONAL': 0.18
    }

    tier = instance.tier.name
    price_per_gb = tier_pricing.get(tier, 0.20)

    # Capacité actuelle
    provisioned_capacity_gb = instance.file_shares[0].capacity_gb
    used_capacity_gb = provisioned_capacity_gb * avg_utilization

    # Capacité optimale (add 30% buffer au-dessus de l'utilisation actuelle)
    recommended_capacity_gb = int(used_capacity_gb * 1.30)

    # Arrondi au multiple de 256 GB supérieur
    recommended_capacity_gb = ((recommended_capacity_gb + 255) // 256) * 256

    # Min capacity selon tier
    min_capacity_gb = {
        'ZONAL': 1024,
        'BASIC_HDD': 1024,
        'BASIC_SSD': 2560,
        'HIGH_SCALE_SSD': 10240,
        'ENTERPRISE': 1024
    }

    recommended_capacity_gb = max(
        recommended_capacity_gb,
        min_capacity_gb.get(tier, 1024)
    )

    # Coûts
    current_monthly_cost = provisioned_capacity_gb * price_per_gb
    optimal_monthly_cost = recommended_capacity_gb * price_per_gb
    monthly_waste = current_monthly_cost - optimal_monthly_cost
    annual_waste = monthly_waste * 12

    return {
        'used_capacity_gb': int(used_capacity_gb),
        'recommended_capacity_gb': recommended_capacity_gb,
        'current_monthly_cost': round(current_monthly_cost, 2),
        'optimal_monthly_cost': round(optimal_monthly_cost, 2),
        'monthly_waste': round(monthly_waste, 2),
        'annual_waste': round(annual_waste, 2)
    }


def determine_confidence_level(
    avg_utilization: float,
    lookback_days: int
) -> str:
    """
    Détermine le niveau de confiance de la recommandation.
    """
    if avg_utilization < 0.10 and lookback_days >= 30:
        return 'CRITICAL'
    elif avg_utilization < 0.20 and lookback_days >= 21:
        return 'HIGH'
    elif avg_utilization < 0.30 and lookback_days >= 14:
        return 'MEDIUM'
    else:
        return 'LOW'


# Exemple d'utilisation
if __name__ == "__main__":
    underutilized = detect_filestore_underutilized(
        project_id="my-gcp-project",
        utilization_threshold=0.30,
        lookback_days=14
    )

    print(f"Trouvé {len(underutilized)} instances sous-utilisées")

    for instance in underutilized:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Tier: {instance['tier']}")
        print(f"  Capacité provisionnée: {instance['provisioned_capacity_gb']} GB")
        print(f"  Capacité utilisée: {instance['used_capacity_gb']} GB ({instance['utilization_percent']:.1f}%)")
        print(f"  Recommandation: {instance['recommended_capacity_gb']} GB")
        print(f"  Gaspillage: ${instance['monthly_waste']:.2f}/mois (${instance['annual_waste']:.2f}/an)")
        print(f"  Confiance: {instance['confidence']}")
```

**Exemples de Détection :**

**Exemple 1 : Instance 10 TB utilisée à 15%**
```python
# Instance details
instance_name = "prod-filestore-old"
tier = "BASIC_HDD"
provisioned_capacity_gb = 10240  # 10 TB
used_capacity_gb = 1536  # 1.5 TB (15%)
utilization = 0.15

# Calcul du waste
price_per_gb = 0.20
current_monthly_cost = 10240 * 0.20  # $2,048/mois
optimal_capacity_gb = int(1536 * 1.30)  # 1,997 GB + 30% buffer
optimal_capacity_gb = 2048  # Arrondi à 2 TB (256 GB increments)
optimal_monthly_cost = 2048 * 0.20  # $409.60/mois

monthly_waste = 2048 - 409.60  # $1,638.40/mois
annual_waste = monthly_waste * 12  # $19,660.80/an

# Recommandation
print(f"WASTE DÉTECTÉ:")
print(f"  Instance {instance_name} ({tier})")
print(f"  Capacité provisionnée: 10 TB")
print(f"  Capacité utilisée: 1.5 TB (15%)")
print(f"  Recommandation: Downsize à 2 TB")
print(f"  Économie potentielle: $19,661/an")
print(f"  Confiance: CRITICAL (15% < 30%)")
```

**Exemple 2 : Instance Enterprise 5 TB utilisée à 25%**
```python
# Instance details
instance_name = "dev-filestore-enterprise"
tier = "ENTERPRISE"
provisioned_capacity_gb = 5120  # 5 TB
used_capacity_gb = 1280  # 1.25 TB (25%)

# Calcul
price_per_gb = 0.60
current_monthly_cost = 5120 * 0.60  # $3,072/mois
optimal_capacity_gb = 1664  # 1.25 TB * 1.30 = 1.625 TB → 1.75 TB arrondi
optimal_monthly_cost = 1792 * 0.60  # $1,075.20/mois

monthly_waste = 3072 - 1075.20  # $1,996.80/mois
annual_waste = monthly_waste * 12  # $23,961.60/an

print(f"Instance {instance_name} gaspille $23,962/an")
print(f"Recommandation: Downsize 5 TB → 1.75 TB")
```

**Formule de Coût Optimal :**

```python
def calculate_optimal_capacity(
    used_capacity_gb: int,
    growth_buffer: float = 0.30,  # 30% buffer par défaut
    tier: str = 'ZONAL'
) -> int:
    """
    Calcule la capacité optimale avec buffer de croissance.

    Args:
        used_capacity_gb: Capacité actuellement utilisée
        growth_buffer: Buffer de croissance (0.30 = 30%)
        tier: Tier Filestore

    Returns:
        Capacité optimale en GB (arrondie à 256 GB près)
    """
    # Capacité cible avec buffer
    target_capacity_gb = int(used_capacity_gb * (1 + growth_buffer))

    # Arrondi au multiple de 256 GB supérieur
    optimal_capacity_gb = ((target_capacity_gb + 255) // 256) * 256

    # Min capacity par tier
    min_capacity = {
        'ZONAL': 1024,
        'BASIC_HDD': 1024,
        'BASIC_SSD': 2560,
        'HIGH_SCALE_SSD': 10240,
        'ENTERPRISE': 1024
    }

    optimal_capacity_gb = max(optimal_capacity_gb, min_capacity.get(tier, 1024))

    return optimal_capacity_gb


# Exemples
print(calculate_optimal_capacity(500, tier='ZONAL'))     # 1024 GB (min capacity)
print(calculate_optimal_capacity(1500, tier='ZONAL'))    # 2048 GB
print(calculate_optimal_capacity(8000, tier='BASIC_SSD'))  # 10240 GB (arrondi)
```

**Test d'Intégration Bash :**

```bash
#!/bin/bash
# test_filestore_underutilized.sh

PROJECT_ID="my-gcp-project"
ZONE="us-central1-a"
INSTANCE_NAME="test-underutilized-filestore"

echo "=== Test Scénario 1: Filestore Underutilized ==="

# 1. Créer une instance de test 2 TB
echo "Création instance Filestore 2 TB (Zonal)..."
gcloud filestore instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --tier=ZONAL \
    --file-share=name="test_share",capacity=2TB \
    --network=name="default" \
    --project=$PROJECT_ID

# 2. Attendre 30 secondes
sleep 30

# 3. Monter le share et écrire seulement 300 GB (15% utilization)
echo "Simulation: Utilisation à 15%..."
# (Dans un vrai test, on monterait via NFS et écrirait des données)

# 4. Attendre 1 heure pour collecter métriques
echo "Attente de collecte de métriques (60 min)..."
sleep 3600

# 5. Exécuter le detector
echo "Exécution du detector..."
python3 - <<EOF
from detect_waste import detect_filestore_underutilized

results = detect_filestore_underutilized(
    project_id="$PROJECT_ID",
    utilization_threshold=0.30,
    lookback_days=1  # Test court
)

for r in results:
    if r['instance_name'] == '$INSTANCE_NAME':
        print(f"✓ Instance détectée: {r['instance_name']}")
        print(f"  Utilization: {r['utilization_percent']:.1f}%")
        print(f"  Waste: \${r['annual_waste']:.2f}/an")

        assert r['utilization_percent'] < 30, "Utilization should be <30%"
        assert r['annual_waste'] > 0, "Annual waste should be positive"
        print("✓ Test PASSED")
        exit(0)

print("✗ Instance not detected")
exit(1)
EOF

# 6. Cleanup
echo "Suppression de l'instance de test..."
gcloud filestore instances delete $INSTANCE_NAME \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --quiet

echo "=== Test terminé ==="
```

**Recommandations Utilisateur :**

```python
def generate_filestore_underutilized_recommendation(
    instance: Dict
) -> str:
    """Génère une recommandation lisible pour l'utilisateur."""

    utilization = instance['utilization_percent']
    current_gb = instance['provisioned_capacity_gb']
    recommended_gb = instance['recommended_capacity_gb']
    annual_waste = instance['annual_waste']

    recommendation = f"""
🔴 Filestore Sous-Utilisé Détecté

Instance: {instance['instance_name']}
Tier: {instance['tier']}
Zone: {instance['zone']}

📊 Utilisation:
  • Capacité provisionnée: {current_gb} GB ({current_gb/1024:.1f} TB)
  • Capacité utilisée: {instance['used_capacity_gb']} GB ({utilization:.1f}%)
  • Capacité gaspillée: {current_gb - instance['used_capacity_gb']} GB

💰 Coût:
  • Coût actuel: ${instance['monthly_cost_current']:.2f}/mois
  • Coût optimal: ${instance['monthly_cost_optimal']:.2f}/mois
  • Gaspillage: ${instance['monthly_waste']:.2f}/mois (${annual_waste:.2f}/an)

✅ Recommandation:
  • Downsize: {current_gb} GB → {recommended_gb} GB
  • Économie: ${annual_waste:.2f}/an (80% de réduction)
  • Downtime: 0 secondes (migration transparente)

🔧 Action:
```bash
gcloud filestore instances update {instance['instance_name']} \\
    --zone={instance['zone']} \\
    --file-share=capacity={recommended_gb//1024}TB \\
    --project=YOUR_PROJECT_ID
```

⚠️ Note: Assurez-vous que la nouvelle capacité ({recommended_gb} GB) permet
20-30% de croissance future.
"""

    return recommendation
```

---

### Scénario 2 : Wrong Tier (Enterprise pour Dev/Test)

**Description :**
Instances Filestore utilisant le tier **Enterprise** ($0.60/GB/mois) pour des environnements de développement, staging, ou test qui ne nécessitent pas la haute disponibilité multi-zone. Enterprise coûte **233% plus cher** que Zonal pour la même performance.

**Pourquoi c'est un problème :**
- Enterprise est justifié uniquement pour :
  - Applications critiques nécessitant SLA 99.99% (multi-zone)
  - Besoin de multi-share (10 shares par instance)
- Dev/test/staging n'ont PAS besoin de multi-zone HA
- Une instance 5 TB Enterprise pour dev = **$21,000/an gaspillés** vs Zonal

**Règles de Détection :**
```python
WRONG_TIER_RULES = {
    # Enterprise pour non-prod
    'enterprise_non_prod': {
        'tier': 'ENTERPRISE',
        'labels': ['env:dev', 'env:test', 'env:staging', 'env:qa'],
        'waste_severity': 'CRITICAL'
    },

    # Basic SSD pour cold data
    'ssd_for_cold_data': {
        'tier': 'BASIC_SSD',
        'iops_threshold': 100,  # <100 IOPS sustained = cold data
        'waste_severity': 'HIGH'
    },

    # High Scale SSD sous-utilisé
    'high_scale_underused': {
        'tier': 'HIGH_SCALE_SSD',
        'throughput_threshold_mb': 500,  # <500 MB/s sustained
        'waste_severity': 'HIGH'
    }
}
```

**Métrique Utilisée :**
- Labels d'instance (environment, application)
- `file.googleapis.com/nfs/server/read_ops_count` (IOPS)
- `file.googleapis.com/nfs/server/write_ops_count`

**Code de Détection Python :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_wrong_tier(
    project_id: str,
    lookback_days: int = 14
) -> List[Dict]:
    """
    Détecte les instances Filestore utilisant un tier inapproprié.

    Cas détectés:
    1. Enterprise pour dev/test/staging (label-based)
    2. Basic SSD pour cold data (<100 IOPS sustained)
    3. High Scale SSD sous-utilisé (<500 MB/s throughput)

    Returns:
        Liste d'instances avec wrong tier et économies potentielles
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    wrong_tier_instances = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]
        tier = instance.tier.name
        labels = dict(instance.labels) if instance.labels else {}

        # Cas 1: Enterprise pour non-prod
        if tier == 'ENTERPRISE':
            wrong_tier_result = check_enterprise_for_non_prod(
                instance=instance,
                labels=labels
            )

            if wrong_tier_result:
                wrong_tier_instances.append(wrong_tier_result)

        # Cas 2: Basic SSD pour cold data
        elif tier == 'BASIC_SSD':
            iops_metrics = get_filestore_iops_metrics(
                project_id=project_id,
                instance_name=instance_name,
                zone=zone,
                lookback_days=lookback_days
            )

            if iops_metrics and iops_metrics['avg_total_iops'] < 100:
                wrong_tier_result = calculate_ssd_to_hdd_savings(
                    instance=instance,
                    avg_iops=iops_metrics['avg_total_iops']
                )
                wrong_tier_instances.append(wrong_tier_result)

        # Cas 3: High Scale SSD sous-utilisé
        elif tier == 'HIGH_SCALE_SSD':
            throughput_metrics = get_filestore_throughput_metrics(
                project_id=project_id,
                instance_name=instance_name,
                zone=zone,
                lookback_days=lookback_days
            )

            if throughput_metrics and throughput_metrics['avg_throughput_mb'] < 500:
                wrong_tier_result = calculate_high_scale_downgrade_savings(
                    instance=instance,
                    avg_throughput=throughput_metrics['avg_throughput_mb']
                )
                wrong_tier_instances.append(wrong_tier_result)

    # Trie par waste annuel décroissant
    wrong_tier_instances.sort(key=lambda x: x['annual_waste'], reverse=True)

    return wrong_tier_instances


def check_enterprise_for_non_prod(
    instance: filestore_v1.Instance,
    labels: Dict[str, str]
) -> Dict:
    """
    Vérifie si une instance Enterprise est utilisée pour non-prod.
    """
    # Labels non-prod typiques
    non_prod_labels = {
        'environment': ['dev', 'test', 'staging', 'qa', 'development'],
        'env': ['dev', 'test', 'staging', 'qa'],
        'tier': ['dev', 'test']
    }

    is_non_prod = False
    matching_label = None

    for label_key, non_prod_values in non_prod_labels.items():
        if label_key in labels:
            label_value = labels[label_key].lower()
            if label_value in non_prod_values:
                is_non_prod = True
                matching_label = f"{label_key}={label_value}"
                break

    # Heuristique: instance name contient dev/test/staging
    if not is_non_prod:
        instance_name = instance.name.split('/')[-1].lower()
        non_prod_keywords = ['dev', 'test', 'staging', 'qa', 'sandbox']

        for keyword in non_prod_keywords:
            if keyword in instance_name:
                is_non_prod = True
                matching_label = f"instance_name contains '{keyword}'"
                break

    if not is_non_prod:
        return None

    # Calcul du waste
    capacity_gb = instance.file_shares[0].capacity_gb

    # Enterprise price
    enterprise_price = 0.60
    current_monthly_cost = capacity_gb * enterprise_price

    # Zonal price (recommended)
    zonal_price = 0.18
    optimal_monthly_cost = capacity_gb * zonal_price

    monthly_waste = current_monthly_cost - optimal_monthly_cost
    annual_waste = monthly_waste * 12

    return {
        'instance_name': instance.name.split('/')[-1],
        'zone': instance.name.split('/')[3],
        'tier': 'ENTERPRISE',
        'recommended_tier': 'ZONAL',
        'reason': f"Non-prod environment detected ({matching_label})",
        'capacity_gb': capacity_gb,
        'current_monthly_cost': round(current_monthly_cost, 2),
        'optimal_monthly_cost': round(optimal_monthly_cost, 2),
        'monthly_waste': round(monthly_waste, 2),
        'annual_waste': round(annual_waste, 2),
        'waste_severity': 'CRITICAL',
        'confidence': 'HIGH',
        'labels': labels
    }


def get_filestore_iops_metrics(
    project_id: str,
    instance_name: str,
    zone: str,
    lookback_days: int
) -> Dict:
    """
    Récupère les métriques IOPS (read + write ops).
    """
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time.timestamp())},
        "start_time": {"seconds": int(start_time.timestamp())},
    })

    # Read ops
    read_ops = query_filestore_metric(
        monitoring_client,
        project_name,
        instance_name,
        zone,
        "file.googleapis.com/nfs/server/read_ops_count",
        interval
    )

    # Write ops
    write_ops = query_filestore_metric(
        monitoring_client,
        project_name,
        instance_name,
        zone,
        "file.googleapis.com/nfs/server/write_ops_count",
        interval
    )

    if not read_ops and not write_ops:
        return None

    # Calcul IOPS moyen (ops/seconde)
    total_read_ops = sum(read_ops) if read_ops else 0
    total_write_ops = sum(write_ops) if write_ops else 0

    total_seconds = lookback_days * 24 * 3600
    avg_read_iops = total_read_ops / total_seconds
    avg_write_iops = total_write_ops / total_seconds
    avg_total_iops = avg_read_iops + avg_write_iops

    return {
        'avg_read_iops': avg_read_iops,
        'avg_write_iops': avg_write_iops,
        'avg_total_iops': avg_total_iops
    }


def query_filestore_metric(
    monitoring_client,
    project_name: str,
    instance_name: str,
    zone: str,
    metric_type: str,
    interval
) -> List[float]:
    """Helper pour query une métrique Filestore."""
    filter_str = (
        f'resource.type = "filestore_instance" '
        f'AND resource.labels.instance_name = "{instance_name}" '
        f'AND resource.labels.zone = "{zone}" '
        f'AND metric.type = "{metric_type}"'
    )

    aggregation = monitoring_v3.Aggregation({
        "alignment_period": {"seconds": 3600},
        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
    })

    try:
        results = monitoring_client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_str,
                "interval": interval,
                "aggregation": aggregation,
            }
        )

        values = []
        for result in results:
            for point in result.points:
                values.append(point.value.double_value)

        return values

    except Exception as e:
        logger.error(f"Erreur query metric {metric_type}: {e}")
        return []


def calculate_ssd_to_hdd_savings(
    instance: filestore_v1.Instance,
    avg_iops: float
) -> Dict:
    """
    Calcule les économies en migrant Basic SSD → Basic HDD ou Zonal.
    """
    capacity_gb = instance.file_shares[0].capacity_gb

    # Basic SSD price
    ssd_price = 0.30
    current_monthly_cost = capacity_gb * ssd_price

    # Zonal price (meilleur choix)
    zonal_price = 0.18
    optimal_monthly_cost = capacity_gb * zonal_price

    monthly_waste = current_monthly_cost - optimal_monthly_cost
    annual_waste = monthly_waste * 12

    return {
        'instance_name': instance.name.split('/')[-1],
        'zone': instance.name.split('/')[3],
        'tier': 'BASIC_SSD',
        'recommended_tier': 'ZONAL',
        'reason': f"Low IOPS detected ({avg_iops:.1f} IOPS avg < 100 threshold)",
        'capacity_gb': capacity_gb,
        'avg_iops': round(avg_iops, 1),
        'current_monthly_cost': round(current_monthly_cost, 2),
        'optimal_monthly_cost': round(optimal_monthly_cost, 2),
        'monthly_waste': round(monthly_waste, 2),
        'annual_waste': round(annual_waste, 2),
        'waste_severity': 'HIGH',
        'confidence': 'MEDIUM'
    }


def get_filestore_throughput_metrics(
    project_id: str,
    instance_name: str,
    zone: str,
    lookback_days: int
) -> Dict:
    """
    Récupère les métriques de throughput (MB/s).

    Note: GCP ne fournit pas directement MB/s, on calcule via bytes/second
    """
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time.timestamp())},
        "start_time": {"seconds": int(start_time.timestamp())},
    })

    # Query read_bytes_count et write_bytes_count
    read_bytes = query_filestore_metric(
        monitoring_client,
        project_name,
        instance_name,
        zone,
        "file.googleapis.com/nfs/server/read_bytes_count",
        interval
    )

    write_bytes = query_filestore_metric(
        monitoring_client,
        project_name,
        instance_name,
        zone,
        "file.googleapis.com/nfs/server/write_bytes_count",
        interval
    )

    if not read_bytes and not write_bytes:
        return None

    # Calcul throughput moyen (MB/s)
    avg_read_bytes_per_sec = sum(read_bytes) / len(read_bytes) if read_bytes else 0
    avg_write_bytes_per_sec = sum(write_bytes) / len(write_bytes) if write_bytes else 0

    avg_read_mb_per_sec = avg_read_bytes_per_sec / (1024 * 1024)
    avg_write_mb_per_sec = avg_write_bytes_per_sec / (1024 * 1024)
    avg_throughput_mb = avg_read_mb_per_sec + avg_write_mb_per_sec

    return {
        'avg_read_mb_per_sec': avg_read_mb_per_sec,
        'avg_write_mb_per_sec': avg_write_mb_per_sec,
        'avg_throughput_mb': avg_throughput_mb
    }


def calculate_high_scale_downgrade_savings(
    instance: filestore_v1.Instance,
    avg_throughput: float
) -> Dict:
    """
    Calcule les économies en downgrading High Scale SSD → Basic SSD.
    """
    capacity_gb = instance.file_shares[0].capacity_gb

    # High Scale SSD et Basic SSD ont le même prix
    # Mais High Scale a min capacity 10 TB
    # Recommandation: downgrade si capacity permet + faible throughput

    price = 0.30
    current_monthly_cost = capacity_gb * price

    # Si capacity > 10 TB et throughput faible, recommander Basic SSD
    if capacity_gb > 10240:  # 10 TB
        # Downgrade possible vers Basic SSD
        optimal_capacity_gb = 10240  # Max Basic SSD
        optimal_monthly_cost = optimal_capacity_gb * price
        monthly_waste = current_monthly_cost - optimal_monthly_cost
        annual_waste = monthly_waste * 12

        return {
            'instance_name': instance.name.split('/')[-1],
            'zone': instance.name.split('/')[3],
            'tier': 'HIGH_SCALE_SSD',
            'recommended_tier': 'BASIC_SSD',
            'reason': f"Low throughput ({avg_throughput:.1f} MB/s < 500 MB/s)",
            'capacity_gb': capacity_gb,
            'avg_throughput_mb': round(avg_throughput, 1),
            'current_monthly_cost': round(current_monthly_cost, 2),
            'optimal_monthly_cost': round(optimal_monthly_cost, 2),
            'monthly_waste': round(monthly_waste, 2),
            'annual_waste': round(annual_waste, 2),
            'waste_severity': 'HIGH',
            'confidence': 'MEDIUM'
        }

    # Pas de downgrade possible (capacité déjà min)
    return None


# Exemple d'utilisation
if __name__ == "__main__":
    wrong_tier = detect_filestore_wrong_tier(
        project_id="my-gcp-project",
        lookback_days=14
    )

    print(f"Trouvé {len(wrong_tier)} instances avec wrong tier")

    for instance in wrong_tier:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Tier actuel: {instance['tier']}")
        print(f"  Tier recommandé: {instance['recommended_tier']}")
        print(f"  Raison: {instance['reason']}")
        print(f"  Gaspillage: ${instance['monthly_waste']:.2f}/mois (${instance['annual_waste']:.2f}/an)")
        print(f"  Sévérité: {instance['waste_severity']}")
```

**Exemples de Détection :**

**Exemple 1 : Enterprise pour Dev Environment**
```python
# Instance details
instance_name = "dev-shared-filestore"
tier = "ENTERPRISE"
capacity_gb = 5120  # 5 TB
labels = {'environment': 'development', 'team': 'backend'}

# Detection
matching_label = "environment=development"
is_non_prod = True

# Calcul
enterprise_price = 0.60
current_cost = 5120 * 0.60  # $3,072/mois

zonal_price = 0.18
optimal_cost = 5120 * 0.18  # $921.60/mois

monthly_waste = 3072 - 921.60  # $2,150.40/mois
annual_waste = monthly_waste * 12  # $25,804.80/an

print(f"WASTE DÉTECTÉ:")
print(f"  Instance {instance_name} utilise Enterprise pour dev")
print(f"  Gaspillage: $25,805/an")
print(f"  Recommandation: Migrer vers Zonal (233% moins cher)")
print(f"  Sévérité: CRITICAL")
```

**Exemple 2 : Basic SSD pour Cold Data**
```python
# Instance details
instance_name = "archive-filestore"
tier = "BASIC_SSD"
capacity_gb = 8192  # 8 TB
avg_iops = 45  # Très faible IOPS

# Detection
iops_threshold = 100
is_cold_data = avg_iops < iops_threshold  # True

# Calcul
ssd_price = 0.30
current_cost = 8192 * 0.30  # $2,457.60/mois

zonal_price = 0.18
optimal_cost = 8192 * 0.18  # $1,474.56/mois

monthly_waste = 2457.60 - 1474.56  # $983.04/mois
annual_waste = monthly_waste * 12  # $11,796.48/an

print(f"Instance {instance_name} avec IOPS faibles ({avg_iops})")
print(f"Recommandation: Basic SSD → Zonal (67% moins cher)")
print(f"Économie: $11,796/an")
```

**Test d'Intégration Bash :**

```bash
#!/bin/bash
# test_filestore_wrong_tier.sh

PROJECT_ID="my-gcp-project"
ZONE="us-central1-a"
INSTANCE_NAME="test-dev-enterprise"

echo "=== Test Scénario 2: Wrong Tier ==="

# 1. Créer une instance Enterprise avec label dev
echo "Création instance Enterprise pour dev..."
gcloud filestore instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --tier=ENTERPRISE \
    --file-share=name="dev_share",capacity=2TB \
    --network=name="default" \
    --labels=environment=development,team=test \
    --project=$PROJECT_ID

# 2. Attendre que l'instance soit READY
echo "Attente instance READY..."
sleep 120

# 3. Exécuter le detector
echo "Exécution du detector..."
python3 - <<EOF
from detect_waste import detect_filestore_wrong_tier

results = detect_filestore_wrong_tier(
    project_id="$PROJECT_ID",
    lookback_days=1
)

for r in results:
    if r['instance_name'] == '$INSTANCE_NAME':
        print(f"✓ Instance détectée: {r['instance_name']}")
        print(f"  Tier: {r['tier']}")
        print(f"  Recommandé: {r['recommended_tier']}")
        print(f"  Raison: {r['reason']}")
        print(f"  Waste: \${r['annual_waste']:.2f}/an")

        assert r['tier'] == 'ENTERPRISE', "Should be Enterprise"
        assert r['recommended_tier'] == 'ZONAL', "Should recommend Zonal"
        assert 'development' in r['reason'].lower(), "Should detect dev label"
        print("✓ Test PASSED")
        exit(0)

print("✗ Instance not detected")
exit(1)
EOF

# 4. Cleanup
echo "Suppression de l'instance..."
gcloud filestore instances delete $INSTANCE_NAME \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --quiet

echo "=== Test terminé ==="
```

**Formule de Migration Cost :**

```python
def calculate_tier_migration_savings(
    current_tier: str,
    recommended_tier: str,
    capacity_gb: int
) -> Dict:
    """
    Calcule les économies d'une migration de tier.
    """
    tier_pricing = {
        'ZONAL': 0.18,
        'BASIC_HDD': 0.20,
        'BASIC_SSD': 0.30,
        'HIGH_SCALE_SSD': 0.30,
        'ENTERPRISE': 0.60
    }

    current_price = tier_pricing[current_tier]
    recommended_price = tier_pricing[recommended_tier]

    current_monthly_cost = capacity_gb * current_price
    optimal_monthly_cost = capacity_gb * recommended_price

    monthly_savings = current_monthly_cost - optimal_monthly_cost
    annual_savings = monthly_savings * 12

    savings_percent = (monthly_savings / current_monthly_cost) * 100

    return {
        'current_monthly_cost': round(current_monthly_cost, 2),
        'optimal_monthly_cost': round(optimal_monthly_cost, 2),
        'monthly_savings': round(monthly_savings, 2),
        'annual_savings': round(annual_savings, 2),
        'savings_percent': round(savings_percent, 1)
    }


# Exemples
print(calculate_tier_migration_savings('ENTERPRISE', 'ZONAL', 5120))
# {'monthly_savings': 2150.40, 'annual_savings': 25804.80, 'savings_percent': 70.0}

print(calculate_tier_migration_savings('BASIC_SSD', 'ZONAL', 8192))
# {'monthly_savings': 983.04, 'annual_savings': 11796.48, 'savings_percent': 40.0}
```

---

### Scénario 3 : Filestore Instances Idle (0 Connections)

**Description :**
Instances Filestore sans aucune connexion active et aucune opération I/O pendant ≥7 jours consécutifs. Ces instances sont complètement inutilisées mais continuent de générer des coûts.

**Pourquoi c'est un problème :**
- Instance idle = 100% du coût gaspillé
- Causes typiques :
  - Application migrée vers autre solution
  - Projet/POC abandonné
  - Instance créée pour test et oubliée
- Une instance 5 TB Basic HDD idle = **$12,288/an gaspillés**

**Seuils de Détection :**
```python
IDLE_THRESHOLDS = {
    'critical': {
        'days': 90,
        'connections': 0,
        'total_iops': 0
    },
    'high': {
        'days': 30,
        'connections': 0,
        'total_iops': 10  # <10 IOPS = quasi-idle
    },
    'medium': {
        'days': 14,
        'connections': 0,
        'total_iops': 50
    },
    'low': {
        'days': 7,
        'connections': 0,
        'total_iops': 100
    }
}
```

**Métriques Utilisées :**
- `file.googleapis.com/nfs/server/connections` (Gauge)
- `file.googleapis.com/nfs/server/read_ops_count` (Counter)
- `file.googleapis.com/nfs/server/write_ops_count` (Counter)

**Code de Détection Python :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_idle(
    project_id: str,
    lookback_days: int = 7,
    max_connections: int = 0,
    max_total_iops: float = 10
) -> List[Dict]:
    """
    Détecte les instances Filestore idle (0 connections + faible I/O).

    Args:
        project_id: GCP project ID
        lookback_days: Période d'observation (7 jours par défaut)
        max_connections: Max connections moyennes (0 = strict idle)
        max_total_iops: Max IOPS moyen (10 = quasi-idle)

    Returns:
        Liste d'instances idle avec coût total gaspillé
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    idle_instances = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]

        # Vérifie connections
        connection_metrics = get_filestore_connection_metrics(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone,
            lookback_days=lookback_days
        )

        if not connection_metrics:
            logger.warning(f"Pas de métriques pour {instance_name}")
            continue

        avg_connections = connection_metrics['avg_connections']

        # Vérifie IOPS
        iops_metrics = get_filestore_iops_metrics(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone,
            lookback_days=lookback_days
        )

        avg_total_iops = iops_metrics['avg_total_iops'] if iops_metrics else 0

        # Détecte si idle
        if avg_connections <= max_connections and avg_total_iops <= max_total_iops:
            # Calcule le waste
            waste_analysis = calculate_idle_filestore_waste(
                instance=instance,
                avg_connections=avg_connections,
                avg_total_iops=avg_total_iops,
                lookback_days=lookback_days
            )

            # Confidence level
            confidence = determine_idle_confidence_level(
                avg_connections=avg_connections,
                avg_total_iops=avg_total_iops,
                lookback_days=lookback_days
            )

            idle_instances.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': instance.tier.name,
                'capacity_gb': instance.file_shares[0].capacity_gb,
                'avg_connections': avg_connections,
                'avg_total_iops': round(avg_total_iops, 2),
                'monthly_cost': waste_analysis['monthly_cost'],
                'annual_cost': waste_analysis['annual_cost'],
                'already_wasted': waste_analysis['already_wasted'],
                'confidence': confidence,
                'idle_days': lookback_days,
                'created_at': instance.create_time.isoformat() if instance.create_time else None,
                'labels': dict(instance.labels) if instance.labels else {}
            })

    # Trie par annual cost décroissant
    idle_instances.sort(key=lambda x: x['annual_cost'], reverse=True)

    return idle_instances


def get_filestore_connection_metrics(
    project_id: str,
    instance_name: str,
    zone: str,
    lookback_days: int
) -> Dict:
    """
    Récupère les métriques de connexions actives.
    """
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time.timestamp())},
        "start_time": {"seconds": int(start_time.timestamp())},
    })

    filter_str = (
        f'resource.type = "filestore_instance" '
        f'AND resource.labels.instance_name = "{instance_name}" '
        f'AND resource.labels.zone = "{zone}" '
        f'AND metric.type = "file.googleapis.com/nfs/server/connections"'
    )

    aggregation = monitoring_v3.Aggregation({
        "alignment_period": {"seconds": 3600},  # 1 heure
        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    })

    try:
        results = monitoring_client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_str,
                "interval": interval,
                "aggregation": aggregation,
            }
        )

        connection_values = []
        for result in results:
            for point in result.points:
                connection_values.append(point.value.double_value)

        if not connection_values:
            return None

        avg_connections = sum(connection_values) / len(connection_values)
        max_connections = max(connection_values)

        return {
            'avg_connections': avg_connections,
            'max_connections': max_connections,
            'num_samples': len(connection_values)
        }

    except Exception as e:
        logger.error(f"Erreur query connections metric: {e}")
        return None


def calculate_idle_filestore_waste(
    instance: filestore_v1.Instance,
    avg_connections: float,
    avg_total_iops: float,
    lookback_days: int
) -> Dict:
    """
    Calcule le coût total gaspillé par une instance idle.
    """
    tier_pricing = {
        'STANDARD': 0.20,
        'PREMIUM': 0.30,
        'BASIC_HDD': 0.20,
        'BASIC_SSD': 0.30,
        'HIGH_SCALE_SSD': 0.30,
        'ENTERPRISE': 0.60,
        'ZONAL': 0.18
    }

    tier = instance.tier.name
    price_per_gb = tier_pricing.get(tier, 0.20)
    capacity_gb = instance.file_shares[0].capacity_gb

    # Coût mensuel/annuel
    monthly_cost = capacity_gb * price_per_gb
    annual_cost = monthly_cost * 12

    # Calcul du waste déjà accumulé depuis création
    if instance.create_time:
        created_at = instance.create_time
        age_days = (datetime.now(created_at.tzinfo) - created_at).days

        # Si idle depuis lookback_days, assume idle depuis min(age_days, lookback_days * 3)
        # (heuristique conservative)
        estimated_idle_days = min(age_days, lookback_days * 3)
        already_wasted = (monthly_cost / 30) * estimated_idle_days
    else:
        already_wasted = 0

    return {
        'monthly_cost': round(monthly_cost, 2),
        'annual_cost': round(annual_cost, 2),
        'already_wasted': round(already_wasted, 2)
    }


def determine_idle_confidence_level(
    avg_connections: float,
    avg_total_iops: float,
    lookback_days: int
) -> str:
    """
    Détermine le niveau de confiance.
    """
    if avg_connections == 0 and avg_total_iops == 0 and lookback_days >= 90:
        return 'CRITICAL'
    elif avg_connections == 0 and avg_total_iops < 10 and lookback_days >= 30:
        return 'HIGH'
    elif avg_connections == 0 and avg_total_iops < 50 and lookback_days >= 14:
        return 'MEDIUM'
    else:
        return 'LOW'


# Exemple d'utilisation
if __name__ == "__main__":
    idle_instances = detect_filestore_idle(
        project_id="my-gcp-project",
        lookback_days=30,
        max_connections=0,
        max_total_iops=10
    )

    print(f"Trouvé {len(idle_instances)} instances idle")

    total_monthly_waste = sum(i['monthly_cost'] for i in idle_instances)
    total_annual_waste = sum(i['annual_cost'] for i in idle_instances)

    print(f"Gaspillage total: ${total_monthly_waste:.2f}/mois (${total_annual_waste:.2f}/an)")

    for instance in idle_instances:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Tier: {instance['tier']}")
        print(f"  Capacité: {instance['capacity_gb']} GB")
        print(f"  Connections moyennes: {instance['avg_connections']}")
        print(f"  IOPS moyen: {instance['avg_total_iops']}")
        print(f"  Coût: ${instance['monthly_cost']:.2f}/mois (${instance['annual_cost']:.2f}/an)")
        print(f"  Déjà gaspillé: ${instance['already_wasted']:.2f}")
        print(f"  Confiance: {instance['confidence']}")
```

**Exemples de Détection :**

**Exemple 1 : Instance Complètement Idle (90 jours)**
```python
# Instance details
instance_name = "old-poc-filestore"
tier = "BASIC_HDD"
capacity_gb = 5120  # 5 TB
avg_connections = 0
avg_total_iops = 0
idle_days = 90

# Calcul
price_per_gb = 0.20
monthly_cost = 5120 * 0.20  # $1,024/mois
annual_cost = monthly_cost * 12  # $12,288/an

# Already wasted (assume idle depuis création)
estimated_idle_days = 90
already_wasted = (monthly_cost / 30) * 90  # $3,072

print(f"WASTE DÉTECTÉ:")
print(f"  Instance {instance_name} est complètement idle")
print(f"  0 connections, 0 IOPS pendant 90 jours")
print(f"  Coût: $1,024/mois ($12,288/an)")
print(f"  Déjà gaspillé: $3,072")
print(f"  Recommandation: SUPPRIMER immédiatement")
print(f"  Confiance: CRITICAL")
```

**Exemple 2 : Instance Quasi-Idle (30 jours)**
```python
# Instance details
instance_name = "staging-filestore-unused"
tier = "ENTERPRISE"
capacity_gb = 3072  # 3 TB
avg_connections = 0
avg_total_iops = 8  # Très faible (monitoring checks)
idle_days = 30

# Calcul
price_per_gb = 0.60
monthly_cost = 3072 * 0.60  # $1,843.20/mois
annual_cost = monthly_cost * 12  # $22,118.40/an

already_wasted = (monthly_cost / 30) * 30  # $1,843.20

print(f"Instance {instance_name} quasi-idle")
print(f"8 IOPS avg (probablement monitoring seulement)")
print(f"Gaspillage: $22,118/an")
print(f"Recommandation: Supprimer ou investiguer usage")
```

**Test d'Intégration Bash :**

```bash
#!/bin/bash
# test_filestore_idle.sh

PROJECT_ID="my-gcp-project"
ZONE="us-central1-a"
INSTANCE_NAME="test-idle-filestore"

echo "=== Test Scénario 3: Filestore Idle ==="

# 1. Créer une instance test
echo "Création instance Filestore..."
gcloud filestore instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --tier=ZONAL \
    --file-share=name="idle_share",capacity=1TB \
    --network=name="default" \
    --project=$PROJECT_ID

# 2. Attendre READY mais NE PAS monter le share (reste idle)
echo "Attente instance READY (sans montage = idle)..."
sleep 120

# 3. Attendre période d'observation (min 1 heure pour métriques)
echo "Attente collecte métriques idle (60 min)..."
sleep 3600

# 4. Exécuter le detector
echo "Exécution du detector..."
python3 - <<EOF
from detect_waste import detect_filestore_idle

results = detect_filestore_idle(
    project_id="$PROJECT_ID",
    lookback_days=1,  # Test court
    max_connections=0,
    max_total_iops=10
)

for r in results:
    if r['instance_name'] == '$INSTANCE_NAME':
        print(f"✓ Instance idle détectée: {r['instance_name']}")
        print(f"  Connections: {r['avg_connections']}")
        print(f"  IOPS: {r['avg_total_iops']}")
        print(f"  Coût annuel: \${r['annual_cost']:.2f}")

        assert r['avg_connections'] == 0, "Should have 0 connections"
        assert r['avg_total_iops'] < 10, "Should have <10 IOPS"
        print("✓ Test PASSED")
        exit(0)

print("✗ Instance not detected (peut nécessiter plus de temps pour métriques)")
exit(1)
EOF

TEST_RESULT=$?

# 5. Cleanup
echo "Suppression de l'instance..."
gcloud filestore instances delete $INSTANCE_NAME \
    --zone=$ZONE \
    --project=$PROJECT_ID \
    --quiet

if [ $TEST_RESULT -eq 0 ]; then
    echo "=== Test PASSED ==="
else
    echo "=== Test FAILED (peut être faux négatif si métriques pas encore disponibles) ==="
fi
```

**Recommandations Utilisateur :**

```python
def generate_idle_filestore_recommendation(instance: Dict) -> str:
    """Génère une recommandation pour une instance idle."""

    recommendation = f"""
🔴 Filestore Instance Idle Détectée

Instance: {instance['instance_name']}
Tier: {instance['tier']}
Zone: {instance['zone']}
Capacité: {instance['capacity_gb']} GB ({instance['capacity_gb']/1024:.1f} TB)

📊 Activité:
  • Connections moyennes: {instance['avg_connections']} (aucune!)
  • IOPS moyen: {instance['avg_total_iops']} (quasi-nul)
  • Période idle: {instance['idle_days']} jours consécutifs

💰 Coût:
  • Coût mensuel: ${instance['monthly_cost']:.2f}
  • Coût annuel: ${instance['annual_cost']:.2f}
  • Déjà gaspillé: ${instance['already_wasted']:.2f}

✅ Recommandation: SUPPRIMER L'INSTANCE

Cette instance est complètement inutilisée. Avant suppression:

1. Vérifier si données importantes stockées:
```bash
# Monter temporairement et vérifier contenu
sudo mount -t nfs {instance['instance_name']}.filestore.{instance['zone']}.c.YOUR_PROJECT.internal:/test_share /mnt/temp
ls -lah /mnt/temp
```

2. Backup si nécessaire:
```bash
# Créer backup
gcloud filestore backups create idle-backup-$(date +%Y%m%d) \\
    --instance={instance['instance_name']} \\
    --zone={instance['zone']} \\
    --region={instance['zone'][:-2]}
```

3. Supprimer l'instance:
```bash
gcloud filestore instances delete {instance['instance_name']} \\
    --zone={instance['zone']} \\
    --project=YOUR_PROJECT_ID
```

⚠️ Note: Le backup coûte $0.10/GB/mois. Si les données ne sont jamais
utilisées, supprimer aussi les backups après vérification.

💡 Économie immédiate: ${instance['annual_cost']:.2f}/an
"""

    return recommendation
```

---

### Scénario 4 : Overprovisioned Capacity

**Description :**
Instances Filestore avec une utilisation **< 10%** de la capacité provisionnée pendant ≥30 jours. Ces instances sont sévèrement sur-dimensionnées et gaspillent un budget massif.

**Pourquoi c'est un problème :**
- Différence avec Scénario 1 (sous-utilisation) : Overprovisioning est **extrême** (<10% vs <30%)
- Causes typiques :
  - Provisionnement initial "par sécurité" (10 TB au lieu de 1 TB)
  - Croissance de données surestimée
  - Données supprimées mais capacité jamais réduite
- Une instance 10 TB utilisée à 5% (500 GB) gaspille **$16,000/an** (tier Zonal)

**Seuils de Détection :**
```python
OVERPROVISIONING_THRESHOLDS = {
    'critical': 0.05,   # <5% utilisé pendant 60 jours
    'high': 0.08,       # <8% utilisé pendant 45 jours
    'medium': 0.10,     # <10% utilisé pendant 30 jours
}
```

**Métrique Utilisée :**
- `file.googleapis.com/nfs/server/used_bytes_percent`

**Code de Détection Python :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_overprovisioned(
    project_id: str,
    utilization_threshold: float = 0.10,
    lookback_days: int = 30
) -> List[Dict]:
    """
    Détecte les instances Filestore sévèrement sur-provisionnées (<10% utilization).

    Args:
        project_id: GCP project ID
        utilization_threshold: Seuil d'utilisation (0.10 = 10%)
        lookback_days: Période d'observation (30 jours par défaut)

    Returns:
        Liste d'instances overprovisionnées avec économies potentielles
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    overprovisioned_instances = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]

        # Récupère métriques d'utilisation
        utilization_metrics = get_filestore_utilization_metrics(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone,
            lookback_days=lookback_days
        )

        if not utilization_metrics:
            continue

        avg_utilization = utilization_metrics['avg_utilization_percent'] / 100
        max_utilization = utilization_metrics['max_utilization_percent'] / 100

        # Vérifie overprovisioning
        if avg_utilization < utilization_threshold:
            waste_analysis = calculate_overprovisioning_waste(
                instance=instance,
                avg_utilization=avg_utilization,
                max_utilization=max_utilization
            )

            confidence = determine_overprovisioning_confidence(
                avg_utilization=avg_utilization,
                max_utilization=max_utilization,
                lookback_days=lookback_days
            )

            overprovisioned_instances.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': instance.tier.name,
                'provisioned_capacity_gb': instance.file_shares[0].capacity_gb,
                'used_capacity_gb': waste_analysis['used_capacity_gb'],
                'avg_utilization_percent': avg_utilization * 100,
                'max_utilization_percent': max_utilization * 100,
                'recommended_capacity_gb': waste_analysis['recommended_capacity_gb'],
                'current_monthly_cost': waste_analysis['current_monthly_cost'],
                'optimal_monthly_cost': waste_analysis['optimal_monthly_cost'],
                'monthly_waste': waste_analysis['monthly_waste'],
                'annual_waste': waste_analysis['annual_waste'],
                'waste_percent': waste_analysis['waste_percent'],
                'confidence': confidence,
                'lookback_days': lookback_days
            })

    overprovisioned_instances.sort(key=lambda x: x['annual_waste'], reverse=True)

    return overprovisioned_instances


def calculate_overprovisioning_waste(
    instance: filestore_v1.Instance,
    avg_utilization: float,
    max_utilization: float
) -> Dict:
    """
    Calcule le gaspillage d'une instance overprovisionnée.

    Stratégie: Dimensionner pour max_utilization + 50% buffer (vs 30% pour sous-utilisation).
    """
    tier_pricing = {
        'STANDARD': 0.20,
        'PREMIUM': 0.30,
        'BASIC_HDD': 0.20,
        'BASIC_SSD': 0.30,
        'HIGH_SCALE_SSD': 0.30,
        'ENTERPRISE': 0.60,
        'ZONAL': 0.18
    }

    tier = instance.tier.name
    price_per_gb = tier_pricing.get(tier, 0.20)
    provisioned_capacity_gb = instance.file_shares[0].capacity_gb

    # Capacité utilisée (moyenne)
    used_capacity_gb = int(provisioned_capacity_gb * avg_utilization)

    # Capacité optimale basée sur max utilization + 50% buffer
    max_used_capacity_gb = int(provisioned_capacity_gb * max_utilization)
    recommended_capacity_gb = int(max_used_capacity_gb * 1.50)

    # Arrondi au multiple de 256 GB supérieur
    recommended_capacity_gb = ((recommended_capacity_gb + 255) // 256) * 256

    # Min capacity par tier
    min_capacity = {
        'ZONAL': 1024,
        'BASIC_HDD': 1024,
        'BASIC_SSD': 2560,
        'HIGH_SCALE_SSD': 10240,
        'ENTERPRISE': 1024
    }

    recommended_capacity_gb = max(
        recommended_capacity_gb,
        min_capacity.get(tier, 1024)
    )

    # Coûts
    current_monthly_cost = provisioned_capacity_gb * price_per_gb
    optimal_monthly_cost = recommended_capacity_gb * price_per_gb
    monthly_waste = current_monthly_cost - optimal_monthly_cost
    annual_waste = monthly_waste * 12

    waste_percent = (monthly_waste / current_monthly_cost) * 100

    return {
        'used_capacity_gb': used_capacity_gb,
        'recommended_capacity_gb': recommended_capacity_gb,
        'current_monthly_cost': round(current_monthly_cost, 2),
        'optimal_monthly_cost': round(optimal_monthly_cost, 2),
        'monthly_waste': round(monthly_waste, 2),
        'annual_waste': round(annual_waste, 2),
        'waste_percent': round(waste_percent, 1)
    }


def determine_overprovisioning_confidence(
    avg_utilization: float,
    max_utilization: float,
    lookback_days: int
) -> str:
    """
    Détermine le niveau de confiance pour overprovisioning.
    """
    if avg_utilization < 0.05 and max_utilization < 0.08 and lookback_days >= 60:
        return 'CRITICAL'
    elif avg_utilization < 0.08 and max_utilization < 0.12 and lookback_days >= 45:
        return 'HIGH'
    elif avg_utilization < 0.10 and lookback_days >= 30:
        return 'MEDIUM'
    else:
        return 'LOW'


# Exemple d'utilisation
if __name__ == "__main__":
    overprovisioned = detect_filestore_overprovisioned(
        project_id="my-gcp-project",
        utilization_threshold=0.10,
        lookback_days=30
    )

    print(f"Trouvé {len(overprovisioned)} instances overprovisionnées")

    total_annual_waste = sum(i['annual_waste'] for i in overprovisioned)
    print(f"Gaspillage total: ${total_annual_waste:,.2f}/an")

    for instance in overprovisioned:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Capacité provisionnée: {instance['provisioned_capacity_gb']} GB")
        print(f"  Utilisation moyenne: {instance['avg_utilization_percent']:.1f}%")
        print(f"  Utilisation max: {instance['max_utilization_percent']:.1f}%")
        print(f"  Recommandation: Downsize à {instance['recommended_capacity_gb']} GB")
        print(f"  Gaspillage: ${instance['monthly_waste']:.2f}/mois (${instance['annual_waste']:.2f}/an)")
        print(f"  Économie: {instance['waste_percent']:.1f}%")
```

**Exemple de Détection :**

```python
# Instance 20 TB utilisée à 3%
instance_name = "legacy-filestore-oversized"
tier = "BASIC_HDD"
provisioned_capacity_gb = 20480  # 20 TB
avg_utilization = 0.03  # 3%
max_utilization = 0.05  # 5% (pic)
used_capacity_gb = 614  # ~600 GB

# Calcul optimal
max_used_gb = 1024  # 1 TB (5% de 20 TB)
recommended_gb = int(1024 * 1.50)  # 1.5 TB → 1536 GB arrondi à 1536 GB

# Coûts
price_per_gb = 0.20
current_cost = 20480 * 0.20  # $4,096/mois
optimal_cost = 1536 * 0.20  # $307.20/mois

monthly_waste = 4096 - 307.20  # $3,788.80/mois
annual_waste = monthly_waste * 12  # $45,465.60/an
waste_percent = (monthly_waste / current_cost) * 100  # 92.5%

print(f"WASTE CRITIQUE DÉTECTÉ:")
print(f"  Instance {instance_name}")
print(f"  Provisionnée: 20 TB, Utilisée: 600 GB (3%)")
print(f"  Gaspillage: $45,466/an (92.5% du budget!)")
print(f"  Recommandation: Downsize 20 TB → 1.5 TB")
print(f"  Confiance: CRITICAL")
```

---

### Scénario 5 : Filestore Instances Untagged

**Description :**
Instances Filestore sans labels/tags appropriés pour la catégorisation, le cost allocation, ou la gouvernance. Les instances non-taggées compliquent la gestion des coûts et empêchent l'identification rapide des ressources.

**Pourquoi c'est un problème :**
- Impossible d'allouer les coûts par équipe/projet/environnement
- Risque de garder des instances orphelines (pas d'owner identifiable)
- Impossible de filtrer dev/test/prod pour appliquer policies
- Audit et compliance difficiles

**Labels Critiques Recommandés :**
```python
REQUIRED_LABELS = {
    'environment': ['prod', 'staging', 'dev', 'test'],  # Tier d'environnement
    'team': ['backend', 'frontend', 'data', 'ml'],      # Équipe propriétaire
    'application': ['app-name'],                         # Application utilisant le share
    'cost-center': ['cc-12345'],                        # Centre de coût
    'owner': ['email@example.com']                      # Contact responsable
}
```

**Détection :**

```python
from google.cloud import filestore_v1
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_untagged(
    project_id: str,
    required_labels: List[str] = None
) -> List[Dict]:
    """
    Détecte les instances Filestore sans labels critiques.

    Args:
        project_id: GCP project ID
        required_labels: Liste de labels requis (ex: ['environment', 'team', 'owner'])

    Returns:
        Liste d'instances non-taggées
    """
    if required_labels is None:
        required_labels = ['environment', 'team', 'owner']

    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    untagged_instances = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]
        labels = dict(instance.labels) if instance.labels else {}

        # Vérifie labels manquants
        missing_labels = []
        for required_label in required_labels:
            if required_label not in labels or not labels[required_label]:
                missing_labels.append(required_label)

        if missing_labels:
            # Calcule coût annuel (important pour prioriser remediation)
            tier_pricing = {
                'STANDARD': 0.20,
                'PREMIUM': 0.30,
                'BASIC_HDD': 0.20,
                'BASIC_SSD': 0.30,
                'HIGH_SCALE_SSD': 0.30,
                'ENTERPRISE': 0.60,
                'ZONAL': 0.18
            }

            tier = instance.tier.name
            price_per_gb = tier_pricing.get(tier, 0.20)
            capacity_gb = instance.file_shares[0].capacity_gb
            annual_cost = capacity_gb * price_per_gb * 12

            untagged_instances.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': tier,
                'capacity_gb': capacity_gb,
                'annual_cost': round(annual_cost, 2),
                'existing_labels': labels,
                'missing_labels': missing_labels,
                'risk_level': determine_tagging_risk_level(missing_labels, annual_cost),
                'created_at': instance.create_time.isoformat() if instance.create_time else None
            })

    # Trie par annual cost décroissant
    untagged_instances.sort(key=lambda x: x['annual_cost'], reverse=True)

    return untagged_instances


def determine_tagging_risk_level(
    missing_labels: List[str],
    annual_cost: float
) -> str:
    """
    Détermine le niveau de risque basé sur labels manquants et coût.
    """
    critical_labels = ['owner', 'environment']
    num_critical_missing = sum(1 for label in missing_labels if label in critical_labels)

    if num_critical_missing >= 2 and annual_cost > 10000:
        return 'CRITICAL'
    elif num_critical_missing >= 1 and annual_cost > 5000:
        return 'HIGH'
    elif len(missing_labels) >= 2:
        return 'MEDIUM'
    else:
        return 'LOW'


def generate_tagging_recommendations(
    untagged_instances: List[Dict]
) -> str:
    """
    Génère un script de remediation pour appliquer les labels.
    """
    script = "#!/bin/bash\n"
    script += "# Script de remediation - Ajout de labels Filestore\n\n"

    for instance in untagged_instances:
        script += f"# Instance: {instance['instance_name']} (missing: {', '.join(instance['missing_labels'])})\n"
        script += f"gcloud filestore instances update {instance['instance_name']} \\\n"
        script += f"    --zone={instance['zone']} \\\n"

        # Suggestion de labels
        suggested_labels = {
            'environment': 'TO_BE_FILLED',
            'team': 'TO_BE_FILLED',
            'owner': 'TO_BE_FILLED'
        }

        # Préserve les labels existants
        all_labels = {**instance['existing_labels'], **suggested_labels}

        labels_str = ','.join([f"{k}={v}" for k, v in all_labels.items()])
        script += f"    --update-labels={labels_str}\n\n"

    return script


# Exemple d'utilisation
if __name__ == "__main__":
    untagged = detect_filestore_untagged(
        project_id="my-gcp-project",
        required_labels=['environment', 'team', 'owner', 'cost-center']
    )

    print(f"Trouvé {len(untagged)} instances non-taggées")

    total_annual_cost = sum(i['annual_cost'] for i in untagged)
    print(f"Coût annuel total non-alloué: ${total_annual_cost:,.2f}")

    for instance in untagged:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Labels manquants: {', '.join(instance['missing_labels'])}")
        print(f"  Coût annuel: ${instance['annual_cost']:,.2f}")
        print(f"  Risque: {instance['risk_level']}")

    # Génère script de remediation
    remediation_script = generate_tagging_recommendations(untagged)
    with open('filestore_tagging_remediation.sh', 'w') as f:
        f.write(remediation_script)

    print("\nScript de remediation généré: filestore_tagging_remediation.sh")
```

**Exemple de Détection :**

```python
# Instance sans labels critiques
instance_name = "prod-filestore-001"
tier = "ENTERPRISE"
capacity_gb = 8192  # 8 TB
labels = {'application': 'legacy-app'}  # Seulement 1 label
required_labels = ['environment', 'team', 'owner', 'cost-center']

# Détection
missing_labels = ['environment', 'team', 'owner', 'cost-center']

# Coût annuel
annual_cost = 8192 * 0.60 * 12  # $59,064/an

# Risque
num_critical_missing = 2  # 'environment' et 'owner'
risk_level = 'CRITICAL'  # (2 critical labels missing + $59K/an)

print(f"GOUVERNANCE ISSUE DÉTECTÉE:")
print(f"  Instance {instance_name} (Enterprise, 8 TB)")
print(f"  Labels manquants: {', '.join(missing_labels)}")
print(f"  Coût annuel: $59,064 (non alloué à un cost-center)")
print(f"  Risque: {risk_level}")
print(f"  Recommandation: Appliquer labels immediately")
```

---

### Scénario 6 : No Backup Policy

**Description :**
Instances Filestore **sans backup policy configurée** ou avec une policy inadéquate (rétention trop courte/longue, fréquence incorrecte). Les backups mal configurés génèrent soit un risque de perte de données, soit un surcoût inutile.

**Pourquoi c'est un problème :**
- **Pas de backup** = Risque de perte de données (violation compliance)
- **Trop de backups** = Coût excessif ($0.10/GB/mois par backup)
- **Mauvaise rétention** = Soit risque, soit gaspillage

**Règles de Backup Recommandées :**

```python
BACKUP_POLICY_RULES = {
    'prod': {
        'frequency_hours': 24,      # Daily
        'retention_days': 30,       # 30 jours
        'max_backups': 30           # ~1 mois de daily
    },
    'staging': {
        'frequency_hours': 168,     # Weekly
        'retention_days': 14,       # 2 semaines
        'max_backups': 2
    },
    'dev': {
        'frequency_hours': None,    # Pas de backup automatique
        'retention_days': 7,        # Si backup manuel
        'max_backups': 1
    }
}
```

**Détection :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_no_backup_policy(
    project_id: str
) -> List[Dict]:
    """
    Détecte les instances Filestore sans backup policy ou avec policy inadéquate.

    Returns:
        Liste d'instances avec problèmes de backup
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    issues = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]
        labels = dict(instance.labels) if instance.labels else {}
        environment = labels.get('environment', 'unknown').lower()

        # Récupère les backups existants pour cette instance
        backups = list_filestore_backups(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone
        )

        # Analyse la policy de backup
        backup_analysis = analyze_backup_policy(
            instance=instance,
            backups=backups,
            environment=environment
        )

        if backup_analysis['has_issue']:
            issues.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': instance.tier.name,
                'capacity_gb': instance.file_shares[0].capacity_gb,
                'environment': environment,
                'num_backups': len(backups),
                'issue_type': backup_analysis['issue_type'],
                'issue_description': backup_analysis['issue_description'],
                'risk_level': backup_analysis['risk_level'],
                'monthly_backup_cost': backup_analysis['monthly_backup_cost'],
                'annual_backup_waste': backup_analysis['annual_backup_waste'],
                'recommended_action': backup_analysis['recommended_action']
            })

    # Trie par risk_level puis annual_backup_waste
    risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    issues.sort(key=lambda x: (risk_order[x['risk_level']], -x['annual_backup_waste']))

    return issues


def list_filestore_backups(
    project_id: str,
    instance_name: str,
    zone: str
) -> List:
    """
    Liste les backups pour une instance Filestore.
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    region = zone.rsplit('-', 1)[0]  # us-central1-a → us-central1
    parent = f"projects/{project_id}/locations/{region}"

    try:
        backups = filestore_client.list_backups(parent=parent)

        # Filtre par instance
        instance_backups = [
            backup for backup in backups
            if instance_name in backup.source_instance
        ]

        return instance_backups

    except Exception as e:
        logger.error(f"Erreur récupération backups: {e}")
        return []


def analyze_backup_policy(
    instance: filestore_v1.Instance,
    backups: List,
    environment: str
) -> Dict:
    """
    Analyse la policy de backup et détecte les problèmes.
    """
    capacity_gb = instance.file_shares[0].capacity_gb
    num_backups = len(backups)

    # Règles recommandées par environnement
    recommended_backups = {
        'prod': 30,      # Daily pendant 30 jours
        'production': 30,
        'staging': 2,    # Weekly pendant 2 semaines
        'dev': 0,        # Pas de backup
        'development': 0,
        'test': 0,
        'unknown': 7     # Conservative default
    }

    recommended = recommended_backups.get(environment, 7)

    # Calcul du coût backup
    backup_price_per_gb = 0.10
    monthly_backup_cost = capacity_gb * num_backups * backup_price_per_gb
    annual_backup_cost = monthly_backup_cost * 12

    # Détection des problèmes
    issue_type = None
    issue_description = None
    risk_level = 'LOW'
    annual_backup_waste = 0

    # Problème 1: Aucun backup pour prod
    if environment in ['prod', 'production'] and num_backups == 0:
        issue_type = 'NO_BACKUP_PROD'
        issue_description = f"Instance production sans aucun backup (risque de perte de données)"
        risk_level = 'CRITICAL'
        recommended_action = f"Créer backup policy: daily, rétention 30 jours"

    # Problème 2: Trop de backups
    elif num_backups > recommended * 2:
        issue_type = 'EXCESSIVE_BACKUPS'
        optimal_backups = recommended
        optimal_cost = capacity_gb * optimal_backups * backup_price_per_gb * 12
        annual_backup_waste = annual_backup_cost - optimal_cost

        issue_description = f"{num_backups} backups (recommandé: {recommended}) - surcoût backup"
        risk_level = 'MEDIUM' if annual_backup_waste > 1000 else 'LOW'
        recommended_action = f"Réduire rétention à {recommended} backups"

    # Problème 3: Backups pour dev/test
    elif environment in ['dev', 'development', 'test'] and num_backups > 1:
        issue_type = 'UNNECESSARY_BACKUPS_NON_PROD'
        annual_backup_waste = annual_backup_cost

        issue_description = f"{num_backups} backups pour environnement {environment} (non nécessaire)"
        risk_level = 'LOW' if annual_backup_waste < 500 else 'MEDIUM'
        recommended_action = f"Supprimer backups automatiques pour {environment}"

    # Problème 4: Backups anciens jamais utilisés
    elif num_backups > 0:
        oldest_backup = min(backups, key=lambda b: b.create_time)
        age_days = (datetime.now(oldest_backup.create_time.tzinfo) - oldest_backup.create_time).days

        if age_days > 365 and environment != 'prod':
            issue_type = 'OLD_BACKUPS_NEVER_USED'
            annual_backup_waste = monthly_backup_cost * 12

            issue_description = f"Backups anciens (>{age_days} jours) probablement jamais restaurés"
            risk_level = 'LOW'
            recommended_action = "Vérifier si backups toujours nécessaires, supprimer les plus anciens"

    # Pas de problème détecté
    else:
        return {
            'has_issue': False
        }

    return {
        'has_issue': True,
        'issue_type': issue_type,
        'issue_description': issue_description,
        'risk_level': risk_level,
        'monthly_backup_cost': round(monthly_backup_cost, 2),
        'annual_backup_waste': round(annual_backup_waste, 2),
        'recommended_action': recommended_action
    }


# Exemple d'utilisation
if __name__ == "__main__":
    backup_issues = detect_filestore_no_backup_policy(
        project_id="my-gcp-project"
    )

    print(f"Trouvé {len(backup_issues)} instances avec problèmes de backup")

    total_waste = sum(i['annual_backup_waste'] for i in backup_issues)
    print(f"Gaspillage backup total: ${total_waste:,.2f}/an")

    for issue in backup_issues:
        print(f"\nInstance: {issue['instance_name']}")
        print(f"  Environnement: {issue['environment']}")
        print(f"  Problème: {issue['issue_description']}")
        print(f"  Backups actuels: {issue['num_backups']}")
        print(f"  Coût backup: ${issue['monthly_backup_cost']:.2f}/mois")
        print(f"  Gaspillage: ${issue['annual_backup_waste']:.2f}/an")
        print(f"  Risque: {issue['risk_level']}")
        print(f"  Action: {issue['recommended_action']}")
```

**Exemple de Détection :**

```python
# Exemple 1: Prod sans backup
instance_name = "prod-critical-filestore"
environment = "prod"
capacity_gb = 5120  # 5 TB
num_backups = 0

# Détection
issue_type = "NO_BACKUP_PROD"
risk_level = "CRITICAL"
recommendation = "Créer backup policy: daily, rétention 30 jours"

print(f"RISQUE CRITIQUE:")
print(f"  Instance production {instance_name} sans backup!")
print(f"  Capacité: 5 TB de données non protégées")
print(f"  Action immédiate requise: Configurer backup policy")

# Exemple 2: Dev avec 50 backups
instance_name = "dev-test-filestore"
environment = "dev"
capacity_gb = 2048  # 2 TB
num_backups = 50

# Coût
monthly_backup_cost = 2048 * 50 * 0.10  # $10,240/mois
annual_backup_cost = monthly_backup_cost * 12  # $122,880/an

print(f"\nGASPILLAGE BACKUP DÉTECTÉ:")
print(f"  Instance dev {instance_name} avec 50 backups!")
print(f"  Coût backup: $10,240/mois ($122,880/an)")
print(f"  Recommandation: Supprimer tous les backups (dev n'a pas besoin de backup)")
print(f"  Économie: $122,880/an")
```

---

### Scénario 7 : Legacy Tier (Basic HDD vs Zonal)

**Description :**
Instances Filestore utilisant l'ancien tier **Basic HDD** ($0.20/GB/mois) alors que le nouveau tier **Zonal** ($0.18/GB/mois) offre les mêmes performances pour 10% moins cher.

**Pourquoi c'est un problème :**
- Zonal tier lancé en 2023 comme remplacement de Basic HDD
- **Identiques** en performance et disponibilité (même SLA 99.9%)
- Zonal est 10% moins cher
- Migration supportée sans downtime
- Aucune raison de rester sur Basic HDD

**Caractéristiques Identiques :**
```python
BASIC_HDD_VS_ZONAL = {
    'basic_hdd': {
        'price_per_gb': 0.20,
        'throughput_per_tb': 100,  # MB/s
        'iops_per_tb': 5000,
        'sla': 0.999,
        'availability': 'Single zone'
    },
    'zonal': {
        'price_per_gb': 0.18,
        'throughput_per_tb': 100,  # MB/s (identique)
        'iops_per_tb': 5000,       # (identique)
        'sla': 0.999,              # (identique)
        'availability': 'Single zone'  # (identique)
    }
}
```

**Détection :**

```python
from google.cloud import filestore_v1
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_legacy_tier(
    project_id: str
) -> List[Dict]:
    """
    Détecte les instances Filestore utilisant le tier legacy Basic HDD
    au lieu du tier Zonal moderne.

    Returns:
        Liste d'instances avec économies potentielles de migration
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    legacy_instances = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        tier = instance.tier.name

        # Détecte tier legacy
        if tier in ['BASIC_HDD', 'STANDARD']:  # STANDARD = ancien nom de BASIC_HDD
            instance_name = instance.name.split('/')[-1]
            zone = instance.name.split('/')[3]
            capacity_gb = instance.file_shares[0].capacity_gb

            # Calcul économies
            basic_hdd_price = 0.20
            zonal_price = 0.18

            current_monthly_cost = capacity_gb * basic_hdd_price
            zonal_monthly_cost = capacity_gb * zonal_price

            monthly_savings = current_monthly_cost - zonal_monthly_cost
            annual_savings = monthly_savings * 12
            savings_percent = (monthly_savings / current_monthly_cost) * 100

            legacy_instances.append({
                'instance_name': instance_name,
                'zone': zone,
                'current_tier': tier,
                'recommended_tier': 'ZONAL',
                'capacity_gb': capacity_gb,
                'current_monthly_cost': round(current_monthly_cost, 2),
                'zonal_monthly_cost': round(zonal_monthly_cost, 2),
                'monthly_savings': round(monthly_savings, 2),
                'annual_savings': round(annual_savings, 2),
                'savings_percent': round(savings_percent, 1),
                'migration_downtime': '0 seconds',
                'created_at': instance.create_time.isoformat() if instance.create_time else None
            })

    # Trie par annual savings décroissant
    legacy_instances.sort(key=lambda x: x['annual_savings'], reverse=True)

    return legacy_instances


def generate_migration_script(
    legacy_instances: List[Dict]
) -> str:
    """
    Génère un script de migration Basic HDD → Zonal.
    """
    script = "#!/bin/bash\n"
    script += "# Script de migration Filestore: Basic HDD → Zonal\n"
    script += "# Migration sans downtime, économie immédiate de 10%\n\n"

    total_annual_savings = sum(i['annual_savings'] for i in legacy_instances)
    script += f"# Économie totale annuelle: ${total_annual_savings:,.2f}\n\n"

    for instance in legacy_instances:
        script += f"# Instance: {instance['instance_name']} ({instance['capacity_gb']} GB)\n"
        script += f"# Économie: ${instance['monthly_savings']:.2f}/mois (${instance['annual_savings']:.2f}/an)\n"
        script += f"echo 'Migration de {instance['instance_name']}...'\n"
        script += f"gcloud filestore instances update {instance['instance_name']} \\\n"
        script += f"    --zone={instance['zone']} \\\n"
        script += f"    --tier=ZONAL \\\n"
        script += f"    --project=YOUR_PROJECT_ID\n\n"

        script += f"# Vérifier status\n"
        script += f"gcloud filestore instances describe {instance['instance_name']} \\\n"
        script += f"    --zone={instance['zone']} \\\n"
        script += f"    --format='value(tier)'\n\n"

    script += "echo 'Migration terminée!'\n"

    return script


# Exemple d'utilisation
if __name__ == "__main__":
    legacy_instances = detect_filestore_legacy_tier(
        project_id="my-gcp-project"
    )

    print(f"Trouvé {len(legacy_instances)} instances sur tier legacy (Basic HDD)")

    total_annual_savings = sum(i['annual_savings'] for i in legacy_instances)
    print(f"Économie potentielle totale: ${total_annual_savings:,.2f}/an")

    for instance in legacy_instances:
        print(f"\nInstance: {instance['instance_name']}")
        print(f"  Tier actuel: {instance['current_tier']}")
        print(f"  Capacité: {instance['capacity_gb']} GB")
        print(f"  Économie: ${instance['monthly_savings']:.2f}/mois (${instance['annual_savings']:.2f}/an)")
        print(f"  Migration: 0 downtime")

    # Génère script de migration
    migration_script = generate_migration_script(legacy_instances)
    with open('filestore_migrate_to_zonal.sh', 'w') as f:
        f.write(migration_script)

    print("\nScript de migration généré: filestore_migrate_to_zonal.sh")
    print("Exécution recommandée: ./filestore_migrate_to_zonal.sh")
```

**Exemple de Détection :**

```python
# Instance 10 TB sur Basic HDD
instance_name = "prod-filestore-legacy"
tier = "BASIC_HDD"
capacity_gb = 10240  # 10 TB

# Calcul économies
basic_hdd_price = 0.20
zonal_price = 0.18

current_cost = 10240 * 0.20  # $2,048/mois
zonal_cost = 10240 * 0.18  # $1,843.20/mois

monthly_savings = 2048 - 1843.20  # $204.80/mois
annual_savings = monthly_savings * 12  # $2,457.60/an
savings_percent = (monthly_savings / current_cost) * 100  # 10%

print(f"TIER LEGACY DÉTECTÉ:")
print(f"  Instance {instance_name} sur Basic HDD")
print(f"  Capacité: 10 TB")
print(f"  Coût actuel: $2,048/mois")
print(f"  Coût avec Zonal: $1,843/mois")
print(f"  Économie: $2,458/an (10%)")
print(f"  Migration: 0 downtime, performances identiques")
print(f"  Recommandation: Migrer vers Zonal immédiatement")

# Commande de migration
print(f"\nCommande:")
print(f"gcloud filestore instances update {instance_name} \\")
print(f"    --zone=us-central1-a \\")
print(f"    --tier=ZONAL")
```

---

## Phase 2 : Scénarios d'Analyse Avancée

### Scénario 8 : Multi-Share Consolidation Opportunity

**Description :**
Plusieurs instances Filestore **single-share** pourraient être consolidées sur une seule instance **Enterprise multi-share** pour réduire les coûts et simplifier la gestion. Le tier Enterprise supporte jusqu'à 10 shares par instance.

**Pourquoi c'est un problème :**
- 5 instances Zonal 2 TB = 5 × $368/mois = **$1,840/mois**
- 1 instance Enterprise 10 TB = **$6,144/mois** (mais pour 10 TB vs 10 TB)
- **Consolidation pertinente si** : plusieurs petites instances sous-utilisées

**Cas d'Usage pour Consolidation :**
```python
CONSOLIDATION_CRITERIA = {
    'min_instances': 3,  # Au moins 3 instances à consolider
    'max_total_capacity_tb': 10,  # Total ≤10 TB (max Enterprise)
    'same_region': True,  # Doivent être dans la même région
    'similar_workload': True,  # Workloads compatibles (ex: tous dev/staging)
    'avg_utilization': 0.30  # Instances sous-utilisées (<30%)
}
```

**Détection :**

```python
from google.cloud import filestore_v1
from typing import List, Dict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_multi_share_consolidation(
    project_id: str,
    min_instances_for_consolidation: int = 3
) -> List[Dict]:
    """
    Détecte les opportunités de consolidation multi-share.

    Args:
        project_id: GCP project ID
        min_instances_for_consolidation: Nombre min d'instances pour consolider

    Returns:
        Liste de groupes d'instances candidates à la consolidation
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = list(filestore_client.list_instances(parent=parent))
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    # Groupe instances par région et environnement
    groups = defaultdict(list)

    for instance in instances:
        zone = instance.name.split('/')[3]
        region = zone.rsplit('-', 1)[0]  # us-central1-a → us-central1
        tier = instance.tier.name
        labels = dict(instance.labels) if instance.labels else {}
        environment = labels.get('environment', 'unknown')

        # Ignore instances déjà Enterprise multi-share
        if tier == 'ENTERPRISE' and len(instance.file_shares) > 1:
            continue

        # Groupe par region + environment
        group_key = f"{region}_{environment}"

        capacity_gb = instance.file_shares[0].capacity_gb

        groups[group_key].append({
            'instance_name': instance.name.split('/')[-1],
            'zone': zone,
            'region': region,
            'tier': tier,
            'capacity_gb': capacity_gb,
            'environment': environment,
            'labels': labels
        })

    # Analyse chaque groupe pour consolidation
    consolidation_opportunities = []

    for group_key, group_instances in groups.items():
        if len(group_instances) < min_instances_for_consolidation:
            continue

        # Vérifie si consolidation pertinente
        consolidation_analysis = analyze_consolidation_opportunity(
            instances=group_instances
        )

        if consolidation_analysis['is_consolidation_beneficial']:
            consolidation_opportunities.append(consolidation_analysis)

    # Trie par annual savings décroissant
    consolidation_opportunities.sort(key=lambda x: x['annual_savings'], reverse=True)

    return consolidation_opportunities


def analyze_consolidation_opportunity(
    instances: List[Dict]
) -> Dict:
    """
    Analyse si la consolidation est bénéfique pour un groupe d'instances.
    """
    total_capacity_gb = sum(i['capacity_gb'] for i in instances)
    total_capacity_tb = total_capacity_gb / 1024

    # Limites Enterprise: 1-10 TB, max 10 shares
    if total_capacity_tb > 10 or len(instances) > 10:
        return {'is_consolidation_beneficial': False}

    # Calcul coût actuel (assume majoritairement Zonal/Basic HDD)
    tier_pricing = {
        'ZONAL': 0.18,
        'BASIC_HDD': 0.20,
        'BASIC_SSD': 0.30,
        'ENTERPRISE': 0.60
    }

    current_monthly_cost = sum(
        i['capacity_gb'] * tier_pricing.get(i['tier'], 0.20)
        for i in instances
    )

    # Coût avec consolidation Enterprise
    # Arrondir total capacity au TB supérieur
    consolidated_capacity_tb = int((total_capacity_gb + 1023) / 1024)
    consolidated_capacity_gb = consolidated_capacity_tb * 1024

    enterprise_price = 0.60
    consolidated_monthly_cost = consolidated_capacity_gb * enterprise_price

    # Vérifier si consolidation est bénéfique
    monthly_savings = current_monthly_cost - consolidated_monthly_cost
    annual_savings = monthly_savings * 12

    is_beneficial = monthly_savings > 0

    if not is_beneficial:
        return {'is_consolidation_beneficial': False}

    # Bénéfices additionnels (non financiers)
    additional_benefits = [
        f"Réduction de {len(instances)} instances à 1 instance (gestion simplifiée)",
        "Multi-zone HA (SLA 99.99% vs 99.9%)",
        f"Consolidation de {len(instances)} shares sur 1 instance"
    ]

    return {
        'is_consolidation_beneficial': True,
        'region': instances[0]['region'],
        'environment': instances[0]['environment'],
        'num_instances': len(instances),
        'instance_names': [i['instance_name'] for i in instances],
        'total_current_capacity_gb': total_capacity_gb,
        'consolidated_capacity_gb': consolidated_capacity_gb,
        'current_monthly_cost': round(current_monthly_cost, 2),
        'consolidated_monthly_cost': round(consolidated_monthly_cost, 2),
        'monthly_savings': round(monthly_savings, 2),
        'annual_savings': round(annual_savings, 2),
        'additional_benefits': additional_benefits,
        'recommendation': generate_consolidation_recommendation(instances, consolidated_capacity_tb)
    }


def generate_consolidation_recommendation(
    instances: List[Dict],
    consolidated_capacity_tb: int
) -> str:
    """
    Génère une recommandation de consolidation.
    """
    region = instances[0]['region']
    environment = instances[0]['environment']

    recommendation = f"""
Consolidation: {len(instances)} instances → 1 instance Enterprise multi-share

Étapes:
1. Créer instance Enterprise {consolidated_capacity_tb} TB avec {len(instances)} shares:
   gcloud filestore instances create consolidated-{environment}-filestore \\
       --zone={region}-a \\
       --tier=ENTERPRISE \\
       --file-share=name="share1",capacity={consolidated_capacity_tb}TB \\
       --network=name="default"

2. Créer shares additionnels (max 10):
   gcloud filestore instances update consolidated-{environment}-filestore \\
       --zone={region}-a \\
       --add-file-share=name="share2",capacity=1TB

3. Migrer données depuis instances existantes (rsync via NFS)

4. Supprimer anciennes instances
"""

    for instance in instances:
        recommendation += f"   gcloud filestore instances delete {instance['instance_name']} --zone={instance['zone']}\n"

    return recommendation


# Exemple d'utilisation
if __name__ == "__main__":
    opportunities = detect_filestore_multi_share_consolidation(
        project_id="my-gcp-project",
        min_instances_for_consolidation=3
    )

    print(f"Trouvé {len(opportunities)} opportunités de consolidation")

    total_annual_savings = sum(o['annual_savings'] for o in opportunities)
    print(f"Économie totale potentielle: ${total_annual_savings:,.2f}/an")

    for opportunity in opportunities:
        print(f"\nGroupe: {opportunity['region']} - {opportunity['environment']}")
        print(f"  Instances: {opportunity['num_instances']} ({', '.join(opportunity['instance_names'])})")
        print(f"  Capacité totale: {opportunity['total_current_capacity_gb']} GB")
        print(f"  Coût actuel: ${opportunity['current_monthly_cost']:.2f}/mois")
        print(f"  Coût consolidé: ${opportunity['consolidated_monthly_cost']:.2f}/mois")
        print(f"  Économie: ${opportunity['monthly_savings']:.2f}/mois (${opportunity['annual_savings']:.2f}/an)")
        print(f"  Bénéfices additionnels:")
        for benefit in opportunity['additional_benefits']:
            print(f"    - {benefit}")
```

**Exemple de Détection :**

```python
# 4 instances dev dans us-central1
instances = [
    {'name': 'dev-app1', 'tier': 'ZONAL', 'capacity_gb': 2048},  # 2 TB
    {'name': 'dev-app2', 'tier': 'ZONAL', 'capacity_gb': 1536},  # 1.5 TB
    {'name': 'dev-app3', 'tier': 'BASIC_HDD', 'capacity_gb': 2048},  # 2 TB
    {'name': 'dev-app4', 'tier': 'ZONAL', 'capacity_gb': 1536},  # 1.5 TB
]

# Total: 7 TB

# Coût actuel
current_cost = (2048 * 0.18) + (1536 * 0.18) + (2048 * 0.20) + (1536 * 0.18)
# = $368.64 + $276.48 + $409.60 + $276.48 = $1,331.20/mois

# Coût consolidé (1 instance Enterprise 8 TB pour 4 shares)
consolidated_cost = 8192 * 0.60  # $4,915.20/mois

# Dans ce cas, consolidation N'EST PAS bénéfique
# (Enterprise plus cher)

# MAIS: Si instances sous-utilisées à 30%, on pourrait consolider à 3 TB total
actual_total_used_gb = 7168 * 0.30  # 2,150 GB
consolidated_optimal_gb = 3072  # 3 TB
consolidated_optimal_cost = 3072 * 0.60  # $1,843.20/mois

monthly_savings = 1331.20 - 1843.20  # -$512/mois (pas bénéfique)

print("Consolidation NON recommandée dans ce cas")
print("Raison: Enterprise trop cher pour ce use case")
print("Alternative: Downsize chaque instance individuellement")
```

---

### Scénario 9 : Snapshot Waste (Old Snapshots)

**Description :**
Backups/snapshots Filestore anciens (>90 jours) qui n'ont jamais été restaurés et ne seront probablement jamais utilisés. Les snapshots coûtent **$0.10/GB/mois** et s'accumulent.

**Pourquoi c'est un problème :**
- Backups rarement nettoyés automatiquement
- Coût snapshot = **50% du coût instance** (si ratio pricing)
- 100 backups de 5 TB = **$51,200/mois** de snapshots seuls!
- Compliance nécessite rétention limitée (GDPR: max 90 jours hors cas spéciaux)

**Règles de Détection :**
```python
SNAPSHOT_WASTE_RULES = {
    'old_never_restored': {
        'age_days': 90,
        'never_restored': True,
        'severity': 'HIGH'
    },
    'excessive_retention': {
        'age_days': 365,
        'severity': 'MEDIUM'
    },
    'orphaned_snapshots': {
        'source_instance_deleted': True,
        'severity': 'HIGH'
    }
}
```

**Détection :**

```python
from google.cloud import filestore_v1
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_snapshot_waste(
    project_id: str,
    old_snapshot_threshold_days: int = 90
) -> List[Dict]:
    """
    Détecte les snapshots/backups Filestore wasteful.

    Args:
        project_id: GCP project ID
        old_snapshot_threshold_days: Age threshold pour "old" (90 jours)

    Returns:
        Liste de snapshots avec coût gaspillé
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()

    wasteful_snapshots = []

    # Liste toutes les régions
    regions = [
        'us-central1', 'us-east1', 'us-west1', 'us-west2',
        'europe-west1', 'europe-west2', 'europe-west3',
        'asia-east1', 'asia-southeast1'
    ]

    for region in regions:
        parent = f"projects/{project_id}/locations/{region}"

        try:
            backups = filestore_client.list_backups(parent=parent)

            for backup in backups:
                backup_analysis = analyze_backup_waste(
                    backup=backup,
                    old_threshold_days=old_snapshot_threshold_days
                )

                if backup_analysis['is_wasteful']:
                    wasteful_snapshots.append(backup_analysis)

        except Exception as e:
            # Région sans backups ou erreur d'accès
            continue

    # Trie par monthly cost décroissant
    wasteful_snapshots.sort(key=lambda x: x['monthly_cost'], reverse=True)

    return wasteful_snapshots


def analyze_backup_waste(
    backup: filestore_v1.Backup,
    old_threshold_days: int
) -> Dict:
    """
    Analyse si un backup est wasteful.
    """
    backup_name = backup.name.split('/')[-1]
    region = backup.name.split('/')[3]

    created_at = backup.create_time
    age_days = (datetime.now(created_at.tzinfo) - created_at).days

    # Capacité du backup (en GB)
    capacity_gb = backup.capacity_gb

    # Coût mensuel
    backup_price_per_gb = 0.10
    monthly_cost = capacity_gb * backup_price_per_gb
    annual_cost = monthly_cost * 12

    # Vérifie si source instance existe encore
    source_instance = backup.source_instance
    is_orphaned = False  # TODO: vérifier si instance existe

    # Détecte waste
    is_wasteful = False
    waste_reason = None
    severity = 'LOW'

    # Raison 1: Backup très ancien
    if age_days > old_threshold_days:
        is_wasteful = True
        waste_reason = f"Backup ancien ({age_days} jours > {old_threshold_days} threshold)"
        severity = 'HIGH' if age_days > 365 else 'MEDIUM'

    # Raison 2: Source instance supprimée (backup orphelin)
    # Note: Nécessite check additionnel
    # if is_orphaned:
    #     is_wasteful = True
    #     waste_reason = "Backup orphelin (source instance supprimée)"
    #     severity = 'HIGH'

    if not is_wasteful:
        return {'is_wasteful': False}

    return {
        'is_wasteful': True,
        'backup_name': backup_name,
        'region': region,
        'capacity_gb': capacity_gb,
        'age_days': age_days,
        'created_at': created_at.isoformat(),
        'source_instance': source_instance.split('/')[-1],
        'monthly_cost': round(monthly_cost, 2),
        'annual_cost': round(annual_cost, 2),
        'waste_reason': waste_reason,
        'severity': severity,
        'recommendation': f"Supprimer backup si non nécessaire (économie: ${annual_cost:.2f}/an)"
    }


def generate_snapshot_cleanup_script(
    wasteful_snapshots: List[Dict],
    dry_run: bool = True
) -> str:
    """
    Génère un script de cleanup des backups wasteful.
    """
    script = "#!/bin/bash\n"
    script += "# Script de cleanup - Backups Filestore anciens\n\n"

    if dry_run:
        script += "# MODE DRY-RUN: Review manual avant suppression!\n\n"

    total_annual_savings = sum(s['annual_cost'] for s in wasteful_snapshots)
    script += f"# Économie totale: ${total_annual_savings:,.2f}/an\n\n"

    for snapshot in wasteful_snapshots:
        script += f"# Backup: {snapshot['backup_name']} ({snapshot['capacity_gb']} GB, {snapshot['age_days']} jours)\n"
        script += f"# Raison: {snapshot['waste_reason']}\n"
        script += f"# Économie: ${snapshot['annual_cost']:.2f}/an\n"

        if dry_run:
            script += f"echo 'Dry-run: Suppression de {snapshot['backup_name']}'\n"
        else:
            script += f"gcloud filestore backups delete {snapshot['backup_name']} \\\n"
            script += f"    --region={snapshot['region']} \\\n"
            script += f"    --quiet\n"

        script += "\n"

    return script


# Exemple d'utilisation
if __name__ == "__main__":
    wasteful_snapshots = detect_filestore_snapshot_waste(
        project_id="my-gcp-project",
        old_snapshot_threshold_days=90
    )

    print(f"Trouvé {len(wasteful_snapshots)} backups wasteful")

    total_monthly_waste = sum(s['monthly_cost'] for s in wasteful_snapshots)
    total_annual_waste = sum(s['annual_cost'] for s in wasteful_snapshots)

    print(f"Gaspillage total: ${total_monthly_waste:,.2f}/mois (${total_annual_waste:,.2f}/an)")

    for snapshot in wasteful_snapshots[:10]:  # Top 10
        print(f"\nBackup: {snapshot['backup_name']}")
        print(f"  Age: {snapshot['age_days']} jours")
        print(f"  Capacité: {snapshot['capacity_gb']} GB")
        print(f"  Coût: ${snapshot['monthly_cost']:.2f}/mois")
        print(f"  Raison: {snapshot['waste_reason']}")
        print(f"  Sévérité: {snapshot['severity']}")

    # Génère script de cleanup
    cleanup_script = generate_snapshot_cleanup_script(
        wasteful_snapshots=wasteful_snapshots,
        dry_run=True
    )

    with open('filestore_backup_cleanup.sh', 'w') as f:
        f.write(cleanup_script)

    print("\nScript de cleanup généré: filestore_backup_cleanup.sh")
    print("Review manual recommandé avant exécution!")
```

**Exemple de Détection :**

```python
# Backup 5 TB créé il y a 2 ans
backup_name = "old-prod-backup-2023"
capacity_gb = 5120  # 5 TB
age_days = 730  # 2 ans
source_instance = "prod-filestore-old"  # Instance peut-être déjà supprimée

# Coût
backup_price = 0.10
monthly_cost = 5120 * 0.10  # $512/mois
annual_cost = monthly_cost * 12  # $6,144/an

# Gaspillage sur 2 ans
total_wasted_2_years = monthly_cost * 24  # $12,288

print(f"BACKUP WASTEFUL DÉTECTÉ:")
print(f"  Backup {backup_name}")
print(f"  Age: 730 jours (2 ans)")
print(f"  Capacité: 5 TB")
print(f"  Coût actuel: $512/mois ($6,144/an)")
print(f"  Déjà gaspillé: $12,288 (sur 2 ans)")
print(f"  Recommandation: Supprimer si non nécessaire")
print(f"  Économie future: $6,144/an")
```

---

### Scénario 10 : Wrong NFS Protocol (NFSv3 vs v4.1)

**Description :**
Instances Filestore configurées avec **NFSv3** alors que **NFSv4.1** offre de meilleures performances et fonctionnalités (file locking, meilleur caching, support ACLs).

**Pourquoi c'est un problème :**
- NFSv4.1 offre **20-30% meilleures performances** sur workloads avec small files
- Meilleur caching côté client = moins d'IOPS nécessaires = tier inférieur possible
- NFSv3 est legacy protocol (années 1990)
- Pas de surcoût pour NFSv4.1

**Bénéfices NFSv4.1 :**
```python
NFSV4_BENEFITS = {
    'performance': '+20-30% throughput sur small files',
    'caching': 'Meilleur client-side caching',
    'security': 'Support Kerberos natif',
    'features': 'File locking, ACLs, delegations',
    'latency': 'Moins de round-trips réseau'
}
```

**Note Importante :** GCP ne fournit pas de métrique directe pour le protocol NFS utilisé. La détection se fait via:
1. Analyse des mount options sur les clients
2. Heuristiques basées sur patterns d'IOPS (NFSv3 génère plus d'IOPS)

**Détection (Heuristique) :**

```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def detect_filestore_wrong_nfs_protocol(
    project_id: str,
    lookback_days: int = 14
) -> List[Dict]:
    """
    Détecte les instances Filestore probablement utilisées avec NFSv3.

    Note: Détection heuristique basée sur patterns d'IOPS.
    NFSv3 génère typiquement 30-50% plus d'IOPS que NFSv4.1 pour même workload.

    Returns:
        Liste d'instances candidates à migration NFSv4.1
    """
    filestore_client = filestore_v1.CloudFilestoreManagerClient()
    monitoring_client = monitoring_v3.MetricServiceClient()

    candidates = []

    parent = f"projects/{project_id}/locations/-"

    try:
        instances = filestore_client.list_instances(parent=parent)
    except Exception as e:
        logger.error(f"Erreur récupération instances: {e}")
        return []

    for instance in instances:
        instance_name = instance.name.split('/')[-1]
        zone = instance.name.split('/')[3]

        # Analyse patterns IOPS
        iops_analysis = analyze_iops_pattern_for_nfs_protocol(
            project_id=project_id,
            instance_name=instance_name,
            zone=zone,
            lookback_days=lookback_days
        )

        if not iops_analysis:
            continue

        # Heuristique: High IOPS/MB ratio suggère NFSv3
        if iops_analysis['likely_nfsv3']:
            # Calcule économie potentielle si downgrade tier possible
            savings_analysis = calculate_nfsv4_migration_savings(
                instance=instance,
                current_iops=iops_analysis['avg_iops']
            )

            candidates.append({
                'instance_name': instance_name,
                'zone': zone,
                'tier': instance.tier.name,
                'capacity_gb': instance.file_shares[0].capacity_gb,
                'avg_iops': iops_analysis['avg_iops'],
                'avg_throughput_mb': iops_analysis['avg_throughput_mb'],
                'iops_per_mb_ratio': iops_analysis['iops_per_mb_ratio'],
                'likely_protocol': 'NFSv3',
                'recommended_protocol': 'NFSv4.1',
                'expected_performance_gain': '20-30%',
                'potential_tier_downgrade': savings_analysis['can_downgrade_tier'],
                'annual_savings': savings_analysis['annual_savings'],
                'confidence': iops_analysis['confidence']
            })

    # Trie par annual savings décroissant
    candidates.sort(key=lambda x: x['annual_savings'], reverse=True)

    return candidates


def analyze_iops_pattern_for_nfs_protocol(
    project_id: str,
    instance_name: str,
    zone: str,
    lookback_days: int
) -> Dict:
    """
    Analyse le ratio IOPS/throughput pour deviner le protocol NFS.

    NFSv3: High IOPS/MB ratio (metadata operations intensives)
    NFSv4.1: Lower IOPS/MB ratio (better caching)
    """
    monitoring_client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time.timestamp())},
        "start_time": {"seconds": int(start_time.timestamp())},
    })

    # Récupère IOPS
    iops_values = query_filestore_iops(
        monitoring_client, project_name, instance_name, zone, interval
    )

    # Récupère throughput
    throughput_values = query_filestore_throughput(
        monitoring_client, project_name, instance_name, zone, interval
    )

    if not iops_values or not throughput_values:
        return None

    avg_iops = sum(iops_values) / len(iops_values)
    avg_throughput_mb = sum(throughput_values) / len(throughput_values)

    # Ratio IOPS per MB
    if avg_throughput_mb > 0:
        iops_per_mb_ratio = avg_iops / avg_throughput_mb
    else:
        return None

    # Heuristique: NFSv3 génère 5-10 IOPS par MB/s (metadata intensive)
    # NFSv4.1 génère 2-4 IOPS par MB/s (better caching)
    likely_nfsv3 = iops_per_mb_ratio > 4.5

    confidence = 'MEDIUM' if iops_per_mb_ratio > 6 else 'LOW'

    return {
        'avg_iops': round(avg_iops, 1),
        'avg_throughput_mb': round(avg_throughput_mb, 1),
        'iops_per_mb_ratio': round(iops_per_mb_ratio, 2),
        'likely_nfsv3': likely_nfsv3,
        'confidence': confidence
    }


def query_filestore_iops(
    monitoring_client, project_name, instance_name, zone, interval
) -> List[float]:
    """Query IOPS metrics."""
    # Combine read + write ops
    read_ops = query_metric(
        monitoring_client, project_name, instance_name, zone,
        "file.googleapis.com/nfs/server/read_ops_count", interval
    )
    write_ops = query_metric(
        monitoring_client, project_name, instance_name, zone,
        "file.googleapis.com/nfs/server/write_ops_count", interval
    )

    total_iops = [r + w for r, w in zip(read_ops, write_ops)]
    return total_iops


def query_filestore_throughput(
    monitoring_client, project_name, instance_name, zone, interval
) -> List[float]:
    """Query throughput metrics (MB/s)."""
    read_bytes = query_metric(
        monitoring_client, project_name, instance_name, zone,
        "file.googleapis.com/nfs/server/read_bytes_count", interval
    )
    write_bytes = query_metric(
        monitoring_client, project_name, instance_name, zone,
        "file.googleapis.com/nfs/server/write_bytes_count", interval
    )

    total_throughput_mb = [(r + w) / (1024 * 1024) for r, w in zip(read_bytes, write_bytes)]
    return total_throughput_mb


def query_metric(
    monitoring_client, project_name, instance_name, zone, metric_type, interval
) -> List[float]:
    """Helper to query a metric."""
    filter_str = (
        f'resource.type = "filestore_instance" '
        f'AND resource.labels.instance_name = "{instance_name}" '
        f'AND resource.labels.zone = "{zone}" '
        f'AND metric.type = "{metric_type}"'
    )

    aggregation = monitoring_v3.Aggregation({
        "alignment_period": {"seconds": 3600},
        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
    })

    try:
        results = monitoring_client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_str,
                "interval": interval,
                "aggregation": aggregation,
            }
        )

        values = []
        for result in results:
            for point in result.points:
                values.append(point.value.double_value)

        return values

    except Exception as e:
        logger.error(f"Erreur query metric: {e}")
        return []


def calculate_nfsv4_migration_savings(
    instance: filestore_v1.Instance,
    current_iops: float
) -> Dict:
    """
    Calcule les économies potentielles avec NFSv4.1.

    NFSv4.1 réduit IOPS de 30%, peut permettre downgrade tier.
    """
    tier = instance.tier.name
    capacity_gb = instance.file_shares[0].capacity_gb

    # Économie directe: 0 (pas de coût additionnel pour protocol)
    # Économie indirecte: Si IOPS réduits suffisamment, downgrade tier possible

    can_downgrade = False
    annual_savings = 0

    # Exemple: Basic SSD → Zonal si IOPS requirement réduit
    if tier == 'BASIC_SSD':
        # Basic SSD: 8000 IOPS/TB
        # Zonal: 5000 IOPS/TB

        capacity_tb = capacity_gb / 1024
        zonal_iops_capacity = capacity_tb * 5000

        # Avec NFSv4.1, IOPS réduits de 30%
        expected_iops_with_v4 = current_iops * 0.70

        if expected_iops_with_v4 < zonal_iops_capacity:
            can_downgrade = True

            # Calcul économies
            ssd_cost = capacity_gb * 0.30 * 12
            zonal_cost = capacity_gb * 0.18 * 12
            annual_savings = ssd_cost - zonal_cost

    return {
        'can_downgrade_tier': can_downgrade,
        'annual_savings': round(annual_savings, 2)
    }


# Exemple d'utilisation
if __name__ == "__main__":
    candidates = detect_filestore_wrong_nfs_protocol(
        project_id="my-gcp-project",
        lookback_days=14
    )

    print(f"Trouvé {len(candidates)} instances probablement sur NFSv3")

    total_annual_savings = sum(c['annual_savings'] for c in candidates)
    print(f"Économie potentielle totale: ${total_annual_savings:,.2f}/an")

    for candidate in candidates:
        print(f"\nInstance: {candidate['instance_name']}")
        print(f"  Tier: {candidate['tier']}")
        print(f"  IOPS moyen: {candidate['avg_iops']:.1f}")
        print(f"  Throughput: {candidate['avg_throughput_mb']:.1f} MB/s")
        print(f"  Ratio IOPS/MB: {candidate['iops_per_mb_ratio']:.2f}")
        print(f"  Protocol probable: {candidate['likely_protocol']}")
        print(f"  Recommandation: Migrer vers {candidate['recommended_protocol']}")
        print(f"  Gain performance: {candidate['expected_performance_gain']}")

        if candidate['potential_tier_downgrade']:
            print(f"  Downgrade tier possible: Basic SSD → Zonal")
            print(f"  Économie: ${candidate['annual_savings']:,.2f}/an")

        print(f"  Confiance: {candidate['confidence']}")
```

**Exemple de Détection :**

```python
# Instance Basic SSD avec high IOPS/MB ratio
instance_name = "app-filestore-ssd"
tier = "BASIC_SSD"
capacity_gb = 5120  # 5 TB
avg_iops = 15000  # IOPS élevés
avg_throughput_mb = 200  # MB/s

# Ratio IOPS/MB
iops_per_mb_ratio = 15000 / 200  # 75 IOPS par MB/s

# Heuristique: Ratio > 6 suggère NFSv3
likely_nfsv3 = iops_per_mb_ratio > 6  # True (75 >> 6)

# Avec NFSv4.1, IOPS attendus
expected_iops_v4 = 15000 * 0.70  # 10,500 IOPS (30% réduction)

# Zonal capacity
capacity_tb = 5
zonal_iops_capacity = 5 * 5000  # 25,000 IOPS

# Downgrade possible?
can_downgrade = expected_iops_v4 < zonal_iops_capacity  # True (10,500 < 25,000)

# Économies
ssd_annual_cost = 5120 * 0.30 * 12  # $18,432/an
zonal_annual_cost = 5120 * 0.18 * 12  # $11,059/an
annual_savings = 18432 - 11059  # $7,373/an

print(f"NFS PROTOCOL ISSUE DÉTECTÉ:")
print(f"  Instance {instance_name}")
print(f"  Ratio IOPS/MB: 75 (très élevé = probablement NFSv3)")
print(f"  Recommandation:")
print(f"    1. Migrer clients vers NFSv4.1 (mount option vers=4.1)")
print(f"    2. IOPS attendus: 10,500 (vs 15,000 actuels)")
print(f"    3. Downgrade tier: Basic SSD → Zonal")
print(f"    4. Économie: $7,373/an")
print(f"  Confiance: MEDIUM (basé sur heuristique)")
```

---

## Protocole de Test Complet

### Tests Unitaires (pytest)

```python
# tests/test_filestore_detection.py

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from detect_waste import (
    detect_filestore_underutilized,
    detect_filestore_wrong_tier,
    detect_filestore_idle,
    detect_filestore_overprovisioned,
    detect_filestore_untagged,
    detect_filestore_no_backup_policy,
    detect_filestore_legacy_tier,
    detect_filestore_multi_share_consolidation,
    detect_filestore_snapshot_waste,
    detect_filestore_wrong_nfs_protocol
)


class TestFilestoreUnderutilized:
    """Tests pour Scénario 1: Instances sous-utilisées."""

    @patch('detect_waste.filestore_v1.CloudFilestoreManagerClient')
    @patch('detect_waste.monitoring_v3.MetricServiceClient')
    def test_detect_underutilized_basic(self, mock_monitoring, mock_filestore):
        """Test détection instance 20% utilisée."""
        # Mock instance 10 TB
        mock_instance = Mock()
        mock_instance.name = "projects/test/locations/us-central1-a/instances/test-fs"
        mock_instance.tier.name = "ZONAL"
        mock_instance.file_shares = [Mock(capacity_gb=10240)]
        mock_instance.labels = {}

        mock_filestore.return_value.list_instances.return_value = [mock_instance]

        # Mock métriques: 20% utilization
        mock_monitoring.return_value.list_time_series.return_value = [
            Mock(points=[Mock(value=Mock(double_value=20.0))])
        ]

        # Exécute détection
        results = detect_filestore_underutilized(
            project_id="test-project",
            utilization_threshold=0.30,
            lookback_days=14
        )

        # Assertions
        assert len(results) == 1
        assert results[0]['instance_name'] == 'test-fs'
        assert results[0]['utilization_percent'] < 30
        assert results[0]['annual_waste'] > 0
        assert results[0]['confidence'] in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

    def test_calculate_optimal_capacity(self):
        """Test calcul capacité optimale."""
        from detect_waste import calculate_optimal_capacity

        # Test 1: Small instance
        optimal = calculate_optimal_capacity(500, tier='ZONAL')
        assert optimal == 1024  # Min capacity

        # Test 2: Normal instance
        optimal = calculate_optimal_capacity(1500, tier='ZONAL')
        assert optimal == 2048  # 1500 * 1.30 = 1950, arrondi à 2048

        # Test 3: Basic SSD min capacity
        optimal = calculate_optimal_capacity(2000, tier='BASIC_SSD')
        assert optimal == 2560  # Min capacity Basic SSD


class TestFilestoreWrongTier:
    """Tests pour Scénario 2: Wrong tier."""

    @patch('detect_waste.filestore_v1.CloudFilestoreManagerClient')
    def test_detect_enterprise_for_dev(self, mock_filestore):
        """Test détection Enterprise pour dev."""
        # Mock instance Enterprise avec label dev
        mock_instance = Mock()
        mock_instance.name = "projects/test/locations/us-central1-a/instances/dev-fs"
        mock_instance.tier.name = "ENTERPRISE"
        mock_instance.file_shares = [Mock(capacity_gb=5120)]
        mock_instance.labels = {'environment': 'development'}

        mock_filestore.return_value.list_instances.return_value = [mock_instance]

        # Exécute détection
        results = detect_filestore_wrong_tier(
            project_id="test-project",
            lookback_days=14
        )

        # Assertions
        assert len(results) == 1
        assert results[0]['tier'] == 'ENTERPRISE'
        assert results[0]['recommended_tier'] == 'ZONAL'
        assert 'development' in results[0]['reason'].lower()
        assert results[0]['annual_waste'] > 20000  # ~$25K/an


class TestFilestoreIdle:
    """Tests pour Scénario 3: Instances idle."""

    @patch('detect_waste.filestore_v1.CloudFilestoreManagerClient')
    @patch('detect_waste.monitoring_v3.MetricServiceClient')
    def test_detect_idle_instance(self, mock_monitoring, mock_filestore):
        """Test détection instance 0 connections."""
        # Mock instance
        mock_instance = Mock()
        mock_instance.name = "projects/test/locations/us-central1-a/instances/idle-fs"
        mock_instance.tier.name = "BASIC_HDD"
        mock_instance.file_shares = [Mock(capacity_gb=5120)]
        mock_instance.create_time = datetime.utcnow() - timedelta(days=90)

        mock_filestore.return_value.list_instances.return_value = [mock_instance]

        # Mock métriques: 0 connections, 0 IOPS
        mock_monitoring.return_value.list_time_series.return_value = [
            Mock(points=[Mock(value=Mock(double_value=0.0))])
        ]

        # Exécute détection
        results = detect_filestore_idle(
            project_id="test-project",
            lookback_days=30,
            max_connections=0,
            max_total_iops=10
        )

        # Assertions
        assert len(results) == 1
        assert results[0]['avg_connections'] == 0
        assert results[0]['avg_total_iops'] <= 10
        assert results[0]['confidence'] in ['CRITICAL', 'HIGH']


class TestFilestoreOverprovisioned:
    """Tests pour Scénario 4: Overprovisioned."""

    def test_calculate_overprovisioning_waste(self):
        """Test calcul waste pour instance 5% utilisée."""
        from detect_waste import calculate_overprovisioning_waste

        # Mock instance 20 TB utilisée à 5%
        mock_instance = Mock()
        mock_instance.tier.name = "BASIC_HDD"
        mock_instance.file_shares = [Mock(capacity_gb=20480)]

        waste = calculate_overprovisioning_waste(
            instance=mock_instance,
            avg_utilization=0.05,
            max_utilization=0.07
        )

        # Assertions
        assert waste['used_capacity_gb'] == 1024  # 5% de 20 TB
        assert waste['recommended_capacity_gb'] < 2560  # Much smaller
        assert waste['waste_percent'] > 80  # >80% waste


class TestFilestoreUntagged:
    """Tests pour Scénario 5: Untagged."""

    @patch('detect_waste.filestore_v1.CloudFilestoreManagerClient')
    def test_detect_untagged_instance(self, mock_filestore):
        """Test détection instance sans labels."""
        # Mock instance sans labels
        mock_instance = Mock()
        mock_instance.name = "projects/test/locations/us-central1-a/instances/unlabeled-fs"
        mock_instance.tier.name = "ENTERPRISE"
        mock_instance.file_shares = [Mock(capacity_gb=8192)]
        mock_instance.labels = {}  # Aucun label

        mock_filestore.return_value.list_instances.return_value = [mock_instance]

        # Exécute détection
        results = detect_filestore_untagged(
            project_id="test-project",
            required_labels=['environment', 'team', 'owner']
        )

        # Assertions
        assert len(results) == 1
        assert len(results[0]['missing_labels']) == 3
        assert results[0]['risk_level'] == 'CRITICAL'  # High cost + missing critical labels


class TestFilestoreLegacyTier:
    """Tests pour Scénario 7: Legacy tier."""

    @patch('detect_waste.filestore_v1.CloudFilestoreManagerClient')
    def test_detect_basic_hdd_instance(self, mock_filestore):
        """Test détection instance Basic HDD."""
        # Mock instance Basic HDD
        mock_instance = Mock()
        mock_instance.name = "projects/test/locations/us-central1-a/instances/legacy-fs"
        mock_instance.tier.name = "BASIC_HDD"
        mock_instance.file_shares = [Mock(capacity_gb=10240)]
        mock_instance.create_time = datetime.utcnow() - timedelta(days=365)

        mock_filestore.return_value.list_instances.return_value = [mock_instance]

        # Exécute détection
        results = detect_filestore_legacy_tier(project_id="test-project")

        # Assertions
        assert len(results) == 1
        assert results[0]['current_tier'] in ['BASIC_HDD', 'STANDARD']
        assert results[0]['recommended_tier'] == 'ZONAL'
        assert results[0]['savings_percent'] == 10.0  # Exactly 10%
        assert results[0]['annual_savings'] > 2000  # ~$2,458/an


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, '-v', '--cov=detect_waste', '--cov-report=html'])
```

### Tests d'Intégration (bash)

```bash
#!/bin/bash
# integration_tests_filestore.sh
# Tests d'intégration end-to-end pour détection Filestore

set -e

PROJECT_ID="cloudwaste-test-project"
ZONE="us-central1-a"
REGION="us-central1"

echo "========================================"
echo "Filestore Waste Detection - Integration Tests"
echo "========================================"

# Cleanup function
cleanup() {
    echo "Cleanup: Suppression des ressources de test..."

    # Supprimer instances
    for instance in test-underutilized test-idle test-wrong-tier test-legacy; do
        gcloud filestore instances delete $instance \
            --zone=$ZONE \
            --project=$PROJECT_ID \
            --quiet 2>/dev/null || true
    done

    echo "Cleanup terminé"
}

trap cleanup EXIT

# Test 1: Instance Sous-Utilisée
echo "\n=== Test 1: Instance Sous-Utilisée ==="
echo "Création instance 5 TB Zonal..."
gcloud filestore instances create test-underutilized \
    --zone=$ZONE \
    --tier=ZONAL \
    --file-share=name="share1",capacity=5TB \
    --network=name="default" \
    --project=$PROJECT_ID

# Monter et écrire seulement 500 GB (10% utilization)
echo "Simulation: Écriture 500 GB (10% de 5 TB)..."
# TODO: Monter NFS et écrire données

sleep 1800  # 30 min pour métriques

echo "Exécution detector..."
python3 - <<EOF
from detect_waste import detect_filestore_underutilized

results = detect_filestore_underutilized(
    project_id="$PROJECT_ID",
    utilization_threshold=0.30,
    lookback_days=1
)

assert any(r['instance_name'] == 'test-underutilized' for r in results), "Instance non détectée"
print("✓ Test 1 PASSED")
EOF

# Test 2: Instance Idle
echo "\n=== Test 2: Instance Idle ==="
echo "Création instance 2 TB sans montage (idle)..."
gcloud filestore instances create test-idle \
    --zone=$ZONE \
    --tier=ZONAL \
    --file-share=name="idle_share",capacity=2TB \
    --network=name="default" \
    --project=$PROJECT_ID

sleep 1800  # 30 min pour métriques

python3 - <<EOF
from detect_waste import detect_filestore_idle

results = detect_filestore_idle(
    project_id="$PROJECT_ID",
    lookback_days=1,
    max_connections=0,
    max_total_iops=10
)

assert any(r['instance_name'] == 'test-idle' for r in results), "Instance idle non détectée"
print("✓ Test 2 PASSED")
EOF

# Test 3: Wrong Tier (Enterprise pour dev)
echo "\n=== Test 3: Wrong Tier ==="
echo "Création instance Enterprise avec label dev..."
gcloud filestore instances create test-wrong-tier \
    --zone=$ZONE \
    --tier=ENTERPRISE \
    --file-share=name="dev_share",capacity=2TB \
    --network=name="default" \
    --labels=environment=development \
    --project=$PROJECT_ID

sleep 60

python3 - <<EOF
from detect_waste import detect_filestore_wrong_tier

results = detect_filestore_wrong_tier(
    project_id="$PROJECT_ID",
    lookback_days=1
)

matching = [r for r in results if r['instance_name'] == 'test-wrong-tier']
assert len(matching) > 0, "Wrong tier non détecté"
assert matching[0]['recommended_tier'] == 'ZONAL', "Recommandation incorrecte"
print("✓ Test 3 PASSED")
EOF

# Test 4: Legacy Tier
echo "\n=== Test 4: Legacy Tier ==="
echo "Création instance Basic HDD..."
gcloud filestore instances create test-legacy \
    --zone=$ZONE \
    --tier=BASIC_HDD \
    --file-share=name="legacy_share",capacity=3TB \
    --network=name="default" \
    --project=$PROJECT_ID

sleep 60

python3 - <<EOF
from detect_waste import detect_filestore_legacy_tier

results = detect_filestore_legacy_tier(project_id="$PROJECT_ID")

matching = [r for r in results if r['instance_name'] == 'test-legacy']
assert len(matching) > 0, "Legacy tier non détecté"
assert matching[0]['recommended_tier'] == 'ZONAL', "Recommandation incorrecte"
assert matching[0]['savings_percent'] == 10.0, "Savings percent incorrect"
print("✓ Test 4 PASSED")
EOF

echo "\n========================================"
echo "Tous les tests d'intégration PASSED ✓"
echo "========================================"
```

---

## Références et Ressources

### Documentation Officielle GCP

1. **Cloud Filestore Documentation**
   - https://cloud.google.com/filestore/docs
   - https://cloud.google.com/filestore/docs/service-tiers

2. **Pricing**
   - https://cloud.google.com/filestore/pricing
   - Backup pricing: https://cloud.google.com/filestore/docs/backups

3. **Cloud Monitoring Metrics**
   - https://cloud.google.com/filestore/docs/monitoring
   - Metrics list: https://cloud.google.com/monitoring/api/metrics_gcp#gcp-file

4. **Migration Guides**
   - Tier migration: https://cloud.google.com/filestore/docs/upgrading-instances
   - NFSv4.1: https://cloud.google.com/filestore/docs/mounting-file-shares

### APIs et SDKs

**Python Client Libraries:**
```bash
pip install google-cloud-filestore
pip install google-cloud-monitoring
```

**Code examples:**
```python
from google.cloud import filestore_v1
from google.cloud import monitoring_v3

# Filestore client
filestore_client = filestore_v1.CloudFilestoreManagerClient()

# Monitoring client
monitoring_client = monitoring_v3.MetricServiceClient()
```

### gcloud Commands

**List instances:**
```bash
gcloud filestore instances list \
    --project=PROJECT_ID \
    --format="table(name,tier,capacityGb,state)"
```

**Describe instance:**
```bash
gcloud filestore instances describe INSTANCE_NAME \
    --zone=ZONE \
    --project=PROJECT_ID
```

**Update tier:**
```bash
gcloud filestore instances update INSTANCE_NAME \
    --zone=ZONE \
    --tier=ZONAL \
    --project=PROJECT_ID
```

**Update capacity:**
```bash
gcloud filestore instances update INSTANCE_NAME \
    --zone=ZONE \
    --file-share=name=SHARE_NAME,capacity=3TB \
    --project=PROJECT_ID
```

**Create backup:**
```bash
gcloud filestore backups create BACKUP_NAME \
    --instance=INSTANCE_NAME \
    --zone=ZONE \
    --region=REGION \
    --project=PROJECT_ID
```

**List backups:**
```bash
gcloud filestore backups list \
    --region=REGION \
    --project=PROJECT_ID
```

**Delete backup:**
```bash
gcloud filestore backups delete BACKUP_NAME \
    --region=REGION \
    --project=PROJECT_ID
```

**Add labels:**
```bash
gcloud filestore instances update INSTANCE_NAME \
    --zone=ZONE \
    --update-labels=environment=prod,team=backend \
    --project=PROJECT_ID
```

### IAM Permissions Requises

**Minimum permissions (read-only pour scanning):**
```json
{
  "permissions": [
    "file.instances.list",
    "file.instances.get",
    "file.backups.list",
    "file.backups.get",
    "monitoring.timeSeries.list"
  ]
}
```

**Custom role pour CloudWaste:**
```bash
gcloud iam roles create cloudwaste_filestore_scanner \
    --project=PROJECT_ID \
    --title="CloudWaste Filestore Scanner" \
    --description="Read-only access for waste detection" \
    --permissions=file.instances.list,file.instances.get,file.backups.list,file.backups.get,monitoring.timeSeries.list \
    --stage=GA
```

### Cloud Monitoring Metrics

**Métriques clés:**

| Metric | Type | Description |
|--------|------|-------------|
| `file.googleapis.com/nfs/server/used_bytes` | Gauge | Bytes utilisés |
| `file.googleapis.com/nfs/server/used_bytes_percent` | Gauge | % utilisation |
| `file.googleapis.com/nfs/server/free_bytes` | Gauge | Bytes disponibles |
| `file.googleapis.com/nfs/server/read_ops_count` | Counter | Read operations |
| `file.googleapis.com/nfs/server/write_ops_count` | Counter | Write operations |
| `file.googleapis.com/nfs/server/read_bytes_count` | Counter | Bytes lus |
| `file.googleapis.com/nfs/server/write_bytes_count` | Counter | Bytes écrits |
| `file.googleapis.com/nfs/server/connections` | Gauge | Connexions actives |
| `file.googleapis.com/nfs/server/procedure_count` | Counter | NFS operations par type |

**Query example (gcloud):**
```bash
gcloud monitoring time-series list \
    --filter='resource.type="filestore_instance" AND resource.labels.instance_name="INSTANCE_NAME" AND metric.type="file.googleapis.com/nfs/server/used_bytes_percent"' \
    --project=PROJECT_ID \
    --format=json
```

### Best Practices

**1. Tagging Strategy:**
```python
RECOMMENDED_LABELS = {
    'environment': 'prod|staging|dev|test',
    'team': 'backend|frontend|data|ml',
    'application': 'app-name',
    'cost-center': 'cc-12345',
    'owner': 'email@example.com',
    'backup-required': 'true|false'
}
```

**2. Backup Policy:**
```python
BACKUP_POLICIES = {
    'prod': {
        'schedule': '0 2 * * *',  # Daily at 2 AM
        'retention_days': 30
    },
    'staging': {
        'schedule': '0 2 * * 0',  # Weekly on Sunday
        'retention_days': 14
    },
    'dev': {
        'schedule': None,  # No automatic backup
        'retention_days': 7
    }
}
```

**3. Capacity Planning:**
```python
# Provision with 20-30% buffer
def calculate_capacity_with_buffer(
    current_usage_gb: int,
    growth_buffer: float = 0.30
) -> int:
    """Calculate optimal capacity with growth buffer."""
    target_capacity_gb = int(current_usage_gb * (1 + growth_buffer))

    # Round up to 256 GB increments
    optimal_capacity_gb = ((target_capacity_gb + 255) // 256) * 256

    return optimal_capacity_gb
```

**4. Tier Selection Matrix:**
```python
TIER_SELECTION = {
    'workload': {
        'light_io': 'ZONAL',           # <100 IOPS/TB
        'moderate_io': 'BASIC_SSD',    # 100-500 IOPS/TB
        'heavy_io': 'HIGH_SCALE_SSD',  # >500 IOPS/TB
        'ha_required': 'ENTERPRISE'     # Multi-zone HA
    },
    'environment': {
        'prod': ['ZONAL', 'BASIC_SSD', 'ENTERPRISE'],
        'staging': ['ZONAL', 'BASIC_HDD'],
        'dev': ['ZONAL'],
        'test': ['ZONAL']
    }
}
```

### Exemples de Coûts Réels

**Exemple 1: Instance production typique**
```python
# Instance 10 TB Zonal, 30% utilisée, 30 daily backups
provisioned_capacity_gb = 10240
used_capacity_gb = 3072  # 30%
tier_price = 0.18
num_backups = 30

# Coûts
instance_cost = provisioned_capacity_gb * 0.18  # $1,843.20/mois
backup_cost = used_capacity_gb * 30 * 0.10  # $9,216/mois
total_cost = instance_cost + backup_cost  # $11,059.20/mois ($132,710/an)

# Optimisation
optimal_capacity_gb = 4096  # 3 TB * 1.30 buffer = 4 TB
optimal_backups = 30  # OK pour prod
optimal_instance_cost = 4096 * 0.18  # $737.28/mois
optimal_backup_cost = 3072 * 30 * 0.10  # $9,216/mois (inchangé)
optimal_total = optimal_instance_cost + optimal_backup_cost  # $9,953.28/mois

# Économie
annual_savings = (total_cost - optimal_total) * 12  # $13,270/an
```

**Exemple 2: Dev environment overprovisioned**
```python
# Instance 5 TB Enterprise pour dev, 10% utilisée, 10 backups
provisioned_capacity_gb = 5120
used_capacity_gb = 512  # 10%
tier_price = 0.60
num_backups = 10

# Coûts
instance_cost = 5120 * 0.60  # $3,072/mois
backup_cost = 512 * 10 * 0.10  # $512/mois
total_cost = instance_cost + backup_cost  # $3,584/mois ($43,008/an)

# Optimisation
# 1. Downsize: 5 TB → 1 TB (512 GB * 1.30 = 666 GB → 1 TB)
# 2. Downgrade: Enterprise → Zonal
# 3. Remove backups (dev doesn't need backup)
optimal_capacity_gb = 1024
optimal_tier_price = 0.18
optimal_backups = 0

optimal_instance_cost = 1024 * 0.18  # $184.32/mois
optimal_backup_cost = 0
optimal_total = 184.32  # $184.32/mois

# Économie
annual_savings = (total_cost - optimal_total) * 12  # $40,798/an (95% réduction!)
```

### Troubleshooting

**1. Métriques non disponibles:**
```python
# Les métriques prennent 5-10 minutes à apparaître
# Attendre au moins 1 heure avant détection
```

**2. Migration tier failed:**
```bash
# Vérifier si migration supportée
# Enterprise → Zonal: NON supporté
# Basic HDD → Zonal: Supporté
gcloud filestore instances update INSTANCE_NAME \
    --zone=ZONE \
    --tier=ZONAL  # Peut échouer si downgrade non supporté
```

**3. Backup deletion failed:**
```bash
# Vérifier si backup utilisé pour restore en cours
gcloud filestore operations list --region=REGION
```

---

**Document complet: 3,678 lignes**
**Couverture: 100% des scénarios de gaspillage Filestore**
**Impact estimé: $10,000 - $60,000/an par organisation**

