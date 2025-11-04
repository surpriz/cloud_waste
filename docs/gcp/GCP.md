# 📊 CloudWaste - Google Cloud Platform (GCP) Resources Inventory

**Status:** 🚧 Phase 2 - Not Yet Implemented
**Total Resources:** 27 ressources GCP
**Total Scenarios:** 270 scénarios de gaspillage (27 × 10 = 100% coverage per resource)
**Estimated Annual Savings:** $100,000 - $300,000 (organization moyenne avec infrastructure GCP mature)

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Tableau Récapitulatif Complet](#tableau-récapitulatif-complet)
3. [Détail par Catégorie](#détail-par-catégorie)
4. [APIs GCP Requises](#apis-gcp-requises)
5. [Permissions IAM Nécessaires](#permissions-iam-nécessaires)
6. [Roadmap d'Implémentation](#roadmap-dimplémentation)

---

## 🎯 Vue d'Ensemble

Google Cloud Platform (GCP) offre une infrastructure cloud complète avec des services équivalents à AWS et Azure. Bien que GCP soit souvent moins cher que AWS (10-30% en moyenne), les mêmes patterns de gaspillage s'appliquent:

### Sources principales de gaspillage GCP:
- **Compute Engine VMs arrêtées** - Disques attachés facturés même si VM arrêtée
- **Persistent Disks non attachés** - Oubliés après suppression de VM
- **Static IPs non assignées** - $7.30/mois par IP
- **GKE Clusters idle** - Control plane $73/mois + nodes inutilisés
- **Cloud SQL instances stopped** - Storage facturé même si stopped
- **BigQuery datasets oubliés** - Storage + long-term coûts
- **Cloud Storage buckets abandonnés** - Accumulation de données
- **Cloud Functions non invoquées** - Memory reservations inutiles
- **Cloud NAT sans traffic** - $45/mois par gateway
- **Load Balancers sans backends** - $18-25/mois gaspillés

### Différences clés GCP vs AWS/Azure:
| Aspect | GCP | AWS | Azure |
|--------|-----|-----|-------|
| **Pricing Model** | Per-second billing | Per-second (min 60s) | Per-minute (min 60s) |
| **Sustained Use Discounts** | ✅ Automatique (30% max) | ❌ Manual Reserved/Savings | ❌ Manual Reserved |
| **VM Stopped Billing** | ✅ Disques seuls | ✅ Disques seuls | ⚠️ Compute+Storage (deallocated) |
| **Free Tier** | ✅ Always Free (e1-micro) | ✅ 12 mois | ✅ 12 mois |
| **GKE Control Plane** | ✅ Gratuit (1 cluster) | ❌ $73/mois | ❌ $73/mois |
| **Regional Resources** | Multi-regional options | Regional | Regional + ZRS |

💡 **Avantage GCP:** Sustained Use Discounts automatiques (jusqu'à -30%) réduisent le gaspillage naturellement, mais les ressources orphelines/idle restent un problème majeur.

---

## 📊 Tableau Récapitulatif Complet

| ID | Catégorie | Ressource GCP | Équivalent AWS/Azure | Scénarios | Priorité | Coût/Mois | Impact/An | Status | Complexité |
|----|-----------|---------------|----------------------|-----------|----------|-----------|-----------|--------|------------|
| **COMPUTE (7 resources)** |
| 1 | Compute | **Compute Engine Instances** | EC2 / Azure VM | 10 | 🔴 Critical | $25-500 | $30K-100K | Not Started | Medium |
| 2 | Compute | **Persistent Disks** | EBS / Managed Disks | 10 | 🔴 Critical | $10-200 | $20K-50K | Not Started | Low |
| 3 | Compute | **Disk Snapshots** | EBS Snapshots | 10 | 🟡 High | $5-100 | $5K-20K | Not Started | Low |
| 4 | Compute | **GKE Clusters** | EKS / AKS | 10 | 🔴 Critical | $150-1000 | $50K-150K | Not Started | High |
| 5 | Compute | **Cloud Run Services** | Fargate / Container Apps | 10 | 🟡 High | $10-200 | $10K-30K | Not Started | Medium |
| 6 | Compute | **Cloud Functions** | Lambda / Functions | 10 | 🟡 High | $5-100 | $5K-15K | Not Started | Medium |
| 7 | Compute | **App Engine** | Elastic Beanstalk / App Service | 10 | 🟢 Medium | $20-300 | $5K-20K | Not Started | Medium |
| **STORAGE (2 resources)** |
| 8 | Storage | **Cloud Storage Buckets** | S3 / Storage Accounts | 10 | 🟡 High | $5-500 | $10K-40K | Not Started | Low |
| 9 | Storage | **Filestore** | EFS / Azure Files | 10 | 🟡 High | $50-500 | $5K-25K | Not Started | Medium |
| **NETWORKING (5 resources)** |
| 10 | Networking | **Static External IPs** | Elastic IP / Public IP | 10 | 🟡 High | $7.30 | $1K-5K | Not Started | Low |
| 11 | Networking | **Cloud Load Balancers** | ALB/NLB / Load Balancer | 10 | 🟡 High | $18-150 | $5K-30K | Not Started | Medium |
| 12 | Networking | **Cloud NAT** | NAT Gateway | 10 | 🟡 High | $45-200 | $5K-20K | Not Started | Low |
| 13 | Networking | **VPN Tunnels** | VPN Connection | 10 | 🟢 Medium | $36 | $2K-10K | Not Started | Low |
| 14 | Networking | **Cloud Router** | Transit Gateway | 10 | 🟢 Medium | $0.10/h | $1K-5K | Not Started | Medium |
| **DATABASES (5 resources)** |
| 15 | Database | **Cloud SQL** | RDS / SQL Database | 10 | 🔴 Critical | $25-500 | $20K-80K | Not Started | Medium |
| 16 | Database | **Cloud Spanner** | Aurora Global / Cosmos DB | 10 | 🔴 Critical | $300-2000 | $30K-100K | Not Started | High |
| 17 | Database | **Firestore** | DynamoDB / Cosmos DB | 10 | 🟡 High | $10-200 | $5K-25K | Not Started | Medium |
| 18 | Database | **Bigtable** | DynamoDB / Cosmos DB | 10 | 🔴 Critical | $200-1000 | $20K-50K | Not Started | Medium |
| 19 | Database | **Memorystore** | ElastiCache / Redis Cache | 10 | 🟡 High | $30-300 | $5K-30K | Not Started | Medium |
| **ANALYTICS & BIG DATA (4 resources)** |
| 20 | Analytics | **BigQuery** | Redshift / Synapse | 10 | 🔴 Critical | $100-5000 | $50K-200K | Not Started | Medium |
| 21 | Analytics | **Dataproc Clusters** | EMR / HDInsight | 10 | 🟡 High | $100-1000 | $10K-50K | Not Started | Medium |
| 22 | Analytics | **Pub/Sub Topics** | Kinesis / Event Hubs | 10 | 🟢 Medium | $5-100 | $2K-15K | Not Started | Low |
| 23 | Analytics | **Dataflow Jobs** | Kinesis Analytics | 10 | 🟡 High | $50-500 | $5K-30K | Not Started | High |
| **AI/ML (2 resources)** |
| 24 | AI/ML | **Vertex AI Endpoints** | SageMaker / ML Services | 10 | 🔴 Critical | $100-1000 | $10K-50K | Not Started | High |
| 25 | AI/ML | **AI Platform Notebooks** | SageMaker Notebooks | 10 | 🟡 High | $50-500 | $5K-20K | Not Started | Medium |
| **MANAGED SERVICES (2 resources)** |
| 26 | Orchestration | **Cloud Composer** | MWAA / Data Factory | 10 | 🟢 Medium | $150-600 | $5K-20K | Not Started | Medium |
| 27 | Security | **Cloud Armor** | WAF / Firewall | 10 | 🟢 Low | $20-200 | $2K-10K | Not Started | Low |

### Légende Priorité:
- 🔴 **Critical** - Coût élevé (>$100/mois), impact majeur (>$20K/an)
- 🟡 **High** - Coût moyen ($20-100/mois), impact important ($5K-20K/an)
- 🟢 **Medium/Low** - Coût faible (<$20/mois), impact limité (<$5K/an)

### Légende Complexité:
- **Low** - API simple, métriques de base (1-2 jours dev)
- **Medium** - Métriques Cloud Monitoring, logique métier (3-5 jours dev)
- **High** - Multiples APIs, corrélations complexes (5-10 jours dev)

---

## 🔍 Détail par Catégorie

### 1️⃣ COMPUTE (7 ressources) - $130K-385K/an potentiel

#### 1.1 Compute Engine Instances (VM) - 10 scénarios
**Équivalent:** EC2 (AWS) / Virtual Machines (Azure)
**API:** `compute.instances` via `google-cloud-compute`
**Métriques:** Cloud Monitoring (CPU, Memory, Disk I/O, Network)

**Scénarios de gaspillage:**
1. **VM Stopped >30 Days** - Disques persistants facturés (même si VM arrêtée)
2. **Idle Running VMs** - CPU <5% pendant 7+ jours
3. **Over-Provisioned CPU** - CPU <30% pendant 30+ jours
4. **Over-Provisioned Memory** - Memory <40% pendant 30+ jours
5. **Old Machine Types** - n1-standard → n2/n2d (15% savings)
6. **No Sustained Use Discount** - Spot/Preemptible eligible (70% savings)
7. **Untagged VMs** - Aucun label (ownership tracking)
8. **Dev/Test 24/7** - Labels dev/staging running full-time
9. **Right-Sizing Opportunities** - Downgrade machine type
10. **Burstable Waste** - e2-micro/small under-utilized

**Pricing:**
- n1-standard-1 (1 vCPU, 3.75 GB): **$24.27/mois**
- n2-standard-4 (4 vCPU, 16 GB): **$121.36/mois**
- n2d-highmem-8 (8 vCPU, 64 GB): **$349.52/mois**
- Spot/Preemptible: **-60-91% off**

**Impact:** Organisation avec 200 VMs → $30K-100K/an gaspillés

---

#### 1.2 Persistent Disks - 10 scénarios
**Équivalent:** EBS Volumes (AWS) / Managed Disks (Azure)
**API:** `compute.disks` via `google-cloud-compute`
**Métriques:** Cloud Monitoring (Read/Write Ops, Throughput)

**Scénarios de gaspillage:**
1. **Unattached Disks** - Disques non attachés >7 jours
2. **Disks on Stopped VMs** - VM stopped mais disque facturé
3. **Idle Attached Disks** - 0 IOPS pendant 30+ jours
4. **Over-Provisioned Size** - Usage <20% capacity
5. **Wrong Disk Type** - pd-ssd où pd-standard suffit (50% cheaper)
6. **Unnecessary SSD Persistent** - pd-ssd avec <100 IOPS avg
7. **Snapshot-Restorable** - Disques anciens avec snapshots récents
8. **Regional PD Waste** - Regional PD (2x coût) en dev/test
9. **Over-Provisioned IOPS** - pd-extreme sur-dimensionné
10. **Unused Boot Disks** - Boot disks de VMs supprimées

**Pricing:**
- pd-standard: **$0.040/GB/mois** (HDD)
- pd-balanced: **$0.100/GB/mois** (SSD performant)
- pd-ssd: **$0.170/GB/mois** (SSD haute perf)
- pd-extreme: **$0.125/GB/mois + $0.140/IOPS**

**Impact:** 100 disques × 100 GB × 50% gaspillage = **$20K-50K/an**

---

#### 1.3 Disk Snapshots - 10 scénarios
**Équivalent:** EBS Snapshots (AWS)
**API:** `compute.snapshots`
**Pricing:** $0.026/GB/mois (multi-regional: $0.032/GB/mois)

**Scénarios:**
1. **Orphaned Snapshots** - Source disk deleted
2. **Redundant Snapshots** - >5 snapshots per disk
3. **Old Unused Snapshots** - >365 days unused
4. **No Retention Policy** - Manual snapshots without lifecycle
5. **Snapshot of Deleted VMs** - VM deleted but snapshots remain
6. **Failed Snapshots** - Status = FAILED
7. **Untagged Snapshots** - No labels for tracking
8. **Excessive Retention (Non-Prod)** - >90 days in dev/test
9. **Duplicate Snapshots** - Multiple snapshots same timestamp
10. **Never Restored Snapshots** - Created but never used

**Impact:** $5K-20K/an

---

#### 1.4 GKE Clusters (Google Kubernetes Engine) - 10 scénarios
**Équivalent:** EKS (AWS) / AKS (Azure)
**API:** `container.projects.locations.clusters`
**Pricing:** Control plane = $73/mois/cluster (autopilot), nodes = Compute Engine pricing

**Scénarios:**
1. **No Worker Nodes** - Cluster sans nodes actifs
2. **All Nodes Unhealthy** - Tous nodes en état NotReady
3. **Low CPU Utilization** - CPU <10% sur tous nodes
4. **Over-Provisioned Nodes** - Machine type trop puissant
5. **Old Node Version** - >2 versions derrière latest
6. **No Spot/Preemptible Nodes** - 100% On-Demand
7. **Dev/Test 24/7** - Cluster dev running full-time
8. **Idle Node Pools** - Node pool avec 0 pods
9. **Bad Autoscaling Config** - Target <30% ou >80%
10. **Unused Cluster Addons** - Addons activés non utilisés

**Impact:** $50K-150K/an (coût élevé clusters)

---

#### 1.5 Cloud Run Services - 10 scénarios
**Équivalent:** AWS Fargate / Azure Container Apps
**API:** `run.projects.locations.services`
**Pricing:** $0.00002400/vCPU-second + $0.00000250/GiB-second

**Scénarios:**
1. **Zero Invocations** - Service jamais invoqué (30+ days)
2. **Idle Running** - Min instances >0 sans traffic
3. **Over-Provisioned CPU** - CPU <10% avg
4. **Over-Provisioned Memory** - Memory <20% avg
5. **Excessive Min Instances** - Min >1 sans justification
6. **No Concurrency Optimization** - Concurrency = 1 (défaut)
7. **Cold Start Not Optimized** - Min = 0 mais latency critique
8. **Always-On Dev/Staging** - Env non-prod always warm
9. **Wrong Region** - Deployed far from users
10. **Unused Revisions** - Old revisions still allocated

**Impact:** $10K-30K/an

---

#### 1.6 Cloud Functions - 10 scénarios
**Équivalent:** AWS Lambda / Azure Functions
**API:** `cloudfunctions.projects.locations.functions`
**Pricing:** $0.40/million invocations + $0.0000025/GB-second

**Scénarios:**
1. **Never Invoked** - Function created but 0 invocations
2. **Zero Invocations (30d)** - Pas invoquée depuis 30+ jours
3. **100% Failures** - Toutes invocations échouent
4. **Over-Provisioned Memory** - Memory >allocated usage
5. **Excessive Timeout** - Timeout = 540s (max) but avg <10s
6. **Cold Start Overhead** - No min instances but latency critical
7. **Wrong Runtime** - Old runtime (Node 10/12)
8. **Ingress = All** - Should be internal-only
9. **No VPC Connector** - Public IP unnecessary cost
10. **Unused Triggers** - Trigger configured but not firing

**Impact:** $5K-15K/an

---

#### 1.7 App Engine - 10 scénarios
**Équivalent:** Elastic Beanstalk / Azure App Service
**API:** `appengine.apps.services.versions`
**Pricing:** Variable selon instance class (F1/F2/F4 free, B1-B8 billable)

**Scénarios:**
1. **Zero Traffic Versions** - Old versions with 0% traffic
2. **Idle Services** - Service avec 0 requests (30d)
3. **Over-Provisioned Instances** - CPU <20% avg
4. **Basic Scaling Waste** - Basic scaling in prod (should use auto)
5. **Manual Scaling Idle** - Manual instances always on
6. **Old Versions Not Deleted** - >10 versions per service
7. **Unnecessary Standard Environment** - Flexible cheaper for this workload
8. **Dev/Test Always On** - Non-prod not stopped off-hours
9. **Wrong Instance Class** - F4 où F2 suffit
10. **Unused Custom Domains** - Domain mapping sans traffic

**Impact:** $5K-20K/an

---

### 2️⃣ STORAGE (2 ressources) - $15K-65K/an potentiel

#### 2.1 Cloud Storage Buckets - 10 scénarios
**Équivalent:** S3 (AWS) / Storage Accounts (Azure)
**API:** `storage.buckets` via `google-cloud-storage`
**Pricing:**
- Standard: $0.020/GB/mois
- Nearline: $0.010/GB/mois (30d min)
- Coldline: $0.004/GB/mois (90d min)
- Archive: $0.0012/GB/mois (365d min)

**Scénarios:**
1. **Empty Buckets** - 0 objects pendant 90+ jours
2. **Old Objects (Standard)** - Objects >365 days en Standard (should be Nearline/Coldline)
3. **Incomplete Multipart Uploads** - Failed uploads not cleaned
4. **No Lifecycle Policy** - Aucune policy de transition/expiration
5. **Public Buckets Unused** - allUsers permission mais 0 traffic
6. **Versioning Overhead** - Versioning enabled avec 100+ versions/object
7. **Wrong Storage Class** - Standard pour archives (4x too expensive)
8. **Unused Buckets** - 0 GET/PUT requests (90d)
9. **Large Abandoned Buckets** - >1 TB avec owner inconnu
10. **Redundancy Waste** - Multi-regional où Regional suffit

**Impact:** $10K-40K/an

---

#### 2.2 Filestore (Managed NFS) - 10 scénarios
**Équivalent:** EFS (AWS) / Azure Files Premium
**API:** `file.projects.locations.instances`
**Pricing:**
- Basic HDD: $0.20/GB/mois (1 TB min)
- Basic SSD: $0.30/GB/mois (2.5 TB min)
- High Scale SSD: $0.30/GB/mois (10 TB min)

**Scénarios:**
1. **Zero Connections** - Aucune connexion client (30d)
2. **Idle Filestore** - 0 read/write ops (30d)
3. **Under-Utilized Capacity** - Usage <10% capacity
4. **Wrong Tier** - Basic SSD où Basic HDD suffit
5. **Over-Provisioned Size** - Min 1 TB mais 50 GB utilisés
6. **No Backup Policy** - Pas de backups configurés
7. **Dev/Test High-Scale** - High-scale tier en dev (overkill)
8. **Unused NFS Exports** - Exports configurés non montés
9. **Old Generation** - Basic tier (should migrate to Enterprise)
10. **Regional Waste** - Instance dans région non utilisée

**Impact:** $5K-25K/an (coût minimum élevé: 1-10 TB)

---

### 3️⃣ NETWORKING (5 ressources) - $14K-70K/an potentiel

#### 3.1 Static External IPs - 10 scénarios
**Équivalent:** Elastic IP (AWS) / Public IP (Azure)
**API:** `compute.addresses`
**Pricing:** $7.30/mois (ephemeral = gratuit si used, reserved = $7.30 if unused)

**Scénarios:**
1. **Unassigned IPs** - IP reserved mais non assignée
2. **IPs on Stopped VMs** - VM stopped mais IP reserved
3. **IPs on Detached NICs** - NIC deleted mais IP persiste
4. **Never Used IPs** - Créée mais jamais assignée
5. **IPs on Unused Load Balancers** - LB sans backends
6. **Idle IPs** - <100 KB traffic (30d)
7. **Low Traffic IPs** - <1 GB traffic (30d)
8. **IPs on Failed VMs** - VM en status TERMINATED
9. **Multiple IPs per VM** - >1 IP par VM (rarely needed)
10. **Regional IPs Unused** - Regional IP sans utilisation

**Impact:** $1K-5K/an (200 IPs × $7.30 = $1,460/mois)

---

#### 3.2 Cloud Load Balancers - 10 scénarios
**Équivalent:** ALB/NLB (AWS) / Azure Load Balancer
**API:**
- `compute.forwardingRules` (L4)
- `compute.urlMaps` (L7)
- `compute.targetPools` (Legacy)

**Pricing:**
- HTTP(S) Load Balancer: $18/mois (5 rules) + $10/rule extra
- Network Load Balancer: $0.025/h = $18.25/mois
- Internal Load Balancer: $0.025/h = $18.25/mois

**Scénarios:**
1. **No Backend Services** - LB sans backend configuré
2. **No Healthy Backends** - Tous backends unhealthy
3. **Never Used** - 0 requests depuis création (30d)
4. **Unhealthy Long-Term** - Backends unhealthy 30+ jours
5. **Security Group Blocks Traffic** - Firewall rules blocking all traffic
6. **Low Traffic** - <1000 requests/mois (over-kill)
7. **Wrong Type** - HTTPS LB pour TCP (should be Network LB)
8. **Unused SSL Certificates** - Cert attached mais 0 HTTPS traffic
9. **Regional LB Waste** - Regional LB pour single-zone backend
10. **No CDN** - Global LB sans Cloud CDN (should enable)

**Impact:** $5K-30K/an

---

#### 3.3 Cloud NAT - 10 scénarios
**Équivalent:** NAT Gateway (AWS/Azure)
**API:** `compute.routers.nats`
**Pricing:** $0.045/h = **$32.85/mois** + $0.045/GB processed

**Scénarios:**
1. **Zero Traffic** - 0 bytes processed (30d)
2. **Low Traffic** - <1 GB/mois (VPC endpoint cheaper)
3. **No Route Table** - NAT configuré mais pas dans routing
4. **Subnets Not Associated** - Aucun subnet using NAT
5. **Misconfigured Firewall** - Egress blocked by firewall
6. **Redundant Same Region** - Multiple NATs même région
7. **Dev/Test 24/7** - Dev environment NAT always on
8. **VPC Endpoint Opportunity** - Traffic vers Google APIs (should use Private Google Access)
9. **Obsolete After Migration** - NAT créé pour migration complétée
10. **Wrong Region** - NAT dans région non utilisée

**Impact:** $5K-20K/an

---

#### 3.4 VPN Tunnels (Cloud VPN) - 10 scénarios
**Équivalent:** VPN Connection (AWS/Azure)
**API:** `compute.vpnTunnels`
**Pricing:** $0.05/h/tunnel = **$36.50/mois** + data transfer

**Scénarios:**
1. **Zero Data Transfer** - 0 bytes transferred (30d)
2. **Tunnel Down** - Status = ESTABLISHED mais 0 traffic
3. **Redundant Tunnels** - >2 tunnels même gateway (only need 2 for HA)
4. **No BGP Sessions** - Dynamic routing non configuré
5. **Idle VPN Gateway** - Gateway sans tunnels actifs
6. **Classic VPN** - Devrait migrer vers HA VPN (99.99% SLA)
7. **Dev/Test VPN** - Non-prod VPN running 24/7
8. **Wrong IKE Version** - IKEv1 (should be IKEv2)
9. **Unused Remote Peer** - Peer IP unreachable
10. **Shared Secret Weak** - Security risk

**Impact:** $2K-10K/an

---

#### 3.5 Cloud Router - 10 scénarios
**Équivalent:** Transit Gateway (AWS) / Virtual Network Gateway (Azure)
**API:** `compute.routers`
**Pricing:** $0.10/h = **$73/mois** (Cloud Router itself free, BGP sessions charged)

**Scénarios:**
1. **No BGP Peers** - Router sans BGP sessions
2. **All Peers Down** - Tous BGP peers en status DOWN
3. **No Routes Advertised** - 0 routes dans BGP
4. **Unused NAT** - Router NAT configuré mais 0 usage
5. **Redundant Routers** - Multiple routers même région/VPC
6. **No VPN Attachments** - Router créé pour VPN mais no tunnels
7. **Idle Interconnect** - Router pour Cloud Interconnect mais 0 traffic
8. **Wrong ASN** - ASN conflict ou incorrect
9. **Over-Complex Routing** - >10 routes (should simplify)
10. **No Route Policies** - Aucun filtering/manipulation routes

**Impact:** $1K-5K/an

---

### 4️⃣ DATABASES (5 ressources) - $80K-285K/an potentiel

#### 4.1 Cloud SQL (MySQL/PostgreSQL/SQL Server) - 10 scénarios
**Équivalent:** RDS (AWS) / Azure SQL Database
**API:** `sqladmin.instances`
**Pricing:**
- db-n1-standard-1: **$25/mois** (shared-core)
- db-n1-standard-4: **$185/mois**
- db-n1-highmem-8: **$585/mois**

**Scénarios:**
1. **Stopped Instances** - Instance stopped >30 jours (storage still billed)
2. **Never Connected** - 0 connections since creation
3. **Idle Running** - 0 connections pendant 30+ jours
4. **Zero I/O** - 0 read/write queries (30d)
5. **No Backups** - automated_backup_enabled = false (risk)
6. **Over-Provisioned CPU** - CPU <10% avg
7. **Over-Provisioned Memory** - Memory <40% avg
8. **Old Generation** - 1st gen MySQL (migrate to 2nd gen)
9. **Storage Over-Provisioned** - Disk usage <20%
10. **HA Waste** - High Availability en dev/test (2x cost)

**Impact:** $20K-80K/an

---

#### 4.2 Cloud Spanner (Distributed SQL) - 10 scénarios
**Équivalent:** Aurora Global (AWS) / Cosmos DB (Azure)
**API:** `spanner.projects.instances`
**Pricing:** **$90/node/mois** (min 1 node regional, 3 nodes multi-regional)

**Scénarios:**
1. **Zero Queries** - 0 queries pendant 30+ jours
2. **Over-Provisioned Nodes** - CPU <10% sur tous nodes
3. **Single-Region Opportunity** - Multi-regional mais 1 seul région used
4. **Idle Database** - Database créée mais 0 tables/data
5. **Development Instance** - Prod-grade config en dev (overkill)
6. **No Autoscaling** - Fixed nodes mais workload variable
7. **Storage Waste** - <10 GB data sur instance expensive
8. **Unused Read Replicas** - Replicas configurés mais 0 read traffic
9. **Wrong Processing Units** - Over-provisioned PUs
10. **Backup Retention Excessive** - >90 days backups en non-prod

**Impact:** $30K-100K/an (coût très élevé)

---

#### 4.3 Firestore (NoSQL Document DB) - 10 scénarios
**Équivalent:** DynamoDB (AWS) / Cosmos DB (Azure)
**API:** `firestore.projects.databases`
**Pricing:**
- Reads: $0.06/100K
- Writes: $0.18/100K
- Storage: $0.18/GB/mois
- Network: $0.12/GB

**Scénarios:**
1. **Empty Collections** - 0 documents pendant 90+ jours
2. **Never Queried** - Collection créée mais 0 reads
3. **Write-Only Collections** - Writes mais 0 reads (logs abandonnés)
4. **Over-Indexed** - >10 indexes par collection (slow writes)
5. **Unused Indexes** - Index created mais never used
6. **Large Documents** - Docs >1 MB (should split)
7. **No TTL** - Pas de TTL sur data temporaire
8. **Wrong Mode** - Datastore mode où Native better
9. **Excessive Reads** - App re-reading same data (should cache)
10. **Abandoned Projects** - Database dans projet non actif

**Impact:** $5K-25K/an

---

#### 4.4 Bigtable (NoSQL Wide-Column) - 10 scénarios
**Équivalent:** DynamoDB (AWS) / Cosmos DB (Azure)
**API:** `bigtableadmin.projects.instances`
**Pricing:**
- Node: **$0.65/h = $474.50/mois**
- Storage HDD: $0.02/GB/mois
- Storage SSD: $0.17/GB/mois

**Scénarios:**
1. **Zero Throughput** - 0 read/write ops (30d)
2. **Over-Provisioned Nodes** - CPU <10% avg per node
3. **Single-Cluster Opportunity** - Replication non nécessaire
4. **HDD vs SSD** - SSD storage où HDD suffit
5. **Under-Utilized Storage** - <100 GB sur cluster cher
6. **Development Instance** - Prod nodes en dev (overkill)
7. **No Autoscaling** - Fixed nodes avec workload variable
8. **Wrong Region** - Instance far from users
9. **No Column Families Pruning** - Trop de column families (slow)
10. **Unused Tables** - Tables créées mais 0 scans

**Impact:** $20K-50K/an (coût élevé: min $475/mois)

---

#### 4.5 Memorystore (Redis/Memcached) - 10 scénarios
**Équivalent:** ElastiCache (AWS) / Azure Redis Cache
**API:** `redis.projects.locations.instances`
**Pricing:**
- Basic M1 (1 GB): **$35/mois**
- Standard M3 (5 GB): **$175/mois**
- Standard M5 (25 GB): **$875/mois**

**Scénarios:**
1. **Zero Cache Hits** - 0 cache hits (30d) - unused cache
2. **Low Hit Rate** - Hit rate <20% (cache ineffective)
3. **No Connections** - 0 active connections (30d)
4. **Over-Provisioned Memory** - Memory usage <10%
5. **Standard Tier in Dev** - HA tier en non-prod (2x cost)
6. **Wrong Eviction Policy** - Policy pas adaptée workload
7. **Idle Redis** - 0 commands/sec avg (30d)
8. **No Persistence** - RDB/AOF disabled (data loss risk)
9. **Old Redis Version** - Redis 4.x (should be 6.x+)
10. **Unused Replicas** - Read replicas mais 0 read traffic

**Impact:** $5K-30K/an

---

### 5️⃣ ANALYTICS & BIG DATA (4 ressources) - $67K-295K/an potentiel

#### 5.1 BigQuery (Data Warehouse) - 10 scénarios
**Équivalent:** Redshift (AWS) / Synapse Analytics (Azure)
**API:** `bigquery.datasets`, `bigquery.tables`
**Pricing:**
- Storage: $0.020/GB/mois (active), $0.010/GB/mois (long-term >90d)
- Queries: $5/TB scanned (on-demand) OU slots $2,000/mois (flat-rate)

**Scénarios:**
1. **Empty Datasets** - 0 tables pendant 90+ jours
2. **Never Queried Tables** - Table créée mais 0 queries
3. **Active Storage Waste** - Data >90 days old en Active tier (should be Long-term)
4. **Partitioning Missing** - Large tables sans partitioning (expensive scans)
5. **No Clustering** - Tables >100 GB sans clustering
6. **Excessive Scans** - Queries scan full table (should add WHERE)
7. **Duplicate Tables** - Multiple tables mêmes données
8. **No Expiration** - Temporary tables sans expiration
9. **Unused Views** - Views créées mais 0 queries
10. **Wrong Pricing Model** - On-demand avec usage predictable (should be flat-rate)

**Impact:** $50K-200K/an (potentiel énorme)

---

#### 5.2 Dataproc Clusters (Hadoop/Spark) - 10 scénarios
**Équivalent:** EMR (AWS) / HDInsight (Azure)
**API:** `dataproc.projects.regions.clusters`
**Pricing:** Compute Engine pricing + 1% Dataproc fee

**Scénarios:**
1. **Idle Clusters** - 0 jobs running (30d)
2. **Cluster Always Running** - Cluster running 24/7 avec usage intermittent
3. **Over-Provisioned Workers** - Worker nodes CPU <10%
4. **Wrong Machine Type** - High-mem où standard suffit
5. **No Autoscaling** - Fixed workers avec workload variable
6. **Preemptible Not Used** - 100% standard workers (should mix 50% preemptible)
7. **Old Dataproc Version** - Image 1.x (should be 2.x)
8. **Unused Secondary Workers** - Secondary workers mais 0 utilization
9. **Wrong Storage** - Local SSD où pd-standard suffit
10. **Cluster Not Deleted** - Ephemeral cluster pas supprimé après job

**Impact:** $10K-50K/an

---

#### 5.3 Pub/Sub Topics - 10 scénarios
**Équivalent:** Kinesis (AWS) / Event Hubs (Azure)
**API:** `pubsub.projects.topics`, `pubsub.projects.subscriptions`
**Pricing:** $40/TiB throughput + $0.10/GB storage (message retention)

**Scénarios:**
1. **No Subscriptions** - Topic sans aucune subscription
2. **Zero Messages** - Topic créé mais 0 messages published (30d)
3. **Dead Letter Subscriptions** - Subscription avec 100% dead letters
4. **Excessive Retention** - Message retention >7 days où 1 day suffit
5. **Unused Subscriptions** - Subscription jamais pulled
6. **No Acknowledgments** - Messages publiés mais jamais acked
7. **Over-Provisioned Throughput** - Reserved capacity non utilisée
8. **Duplicate Topics** - Multiple topics même purpose
9. **No Schema** - Topics sans schema validation (data quality risk)
10. **Regional Waste** - Topic dans région non utilisée

**Impact:** $2K-15K/an

---

#### 5.4 Dataflow Jobs (Apache Beam) - 10 scénarios
**Équivalent:** Kinesis Analytics (AWS) / Stream Analytics (Azure)
**API:** `dataflow.projects.locations.jobs`
**Pricing:** Compute Engine pricing + network

**Scénarios:**
1. **Failed Jobs** - Job en status FAILED depuis >7 jours
2. **Idle Streaming Jobs** - 0 messages processed (30d)
3. **Over-Provisioned Workers** - Worker CPU <10%
4. **No Autoscaling** - Fixed workers avec throughput variable
5. **Wrong Machine Type** - n1-highmem où n1-standard suffit
6. **Long-Running Batch** - Batch job running >24h (should optimize)
7. **No Pipeline Optimization** - Transforms inefficients (should use Combine)
8. **Regional Waste** - Job dans région far from data source
9. **Old Apache Beam SDK** - SDK 2.x (should be latest)
10. **Unused Side Inputs** - Side inputs loaded mais pas used

**Impact:** $5K-30K/an

---

### 6️⃣ AI/ML (2 ressources) - $15K-70K/an potentiel

#### 6.1 Vertex AI Endpoints (ML Model Serving) - 10 scénarios
**Équivalent:** SageMaker Endpoints (AWS) / Azure ML Endpoints
**API:** `aiplatform.projects.locations.endpoints`
**Pricing:**
- n1-standard-4: **$140/mois**
- n1-highmem-8: **$430/mois**
- GPU T4: **$350/mois**

**Scénarios:**
1. **Zero Predictions** - Endpoint créé mais 0 predict requests (30d)
2. **Idle Endpoint** - <10 predictions/jour
3. **Over-Provisioned Machine** - CPU <10% avg
4. **No Autoscaling** - Fixed machines avec traffic variable
5. **GPU Waste** - GPU endpoint mais CPU inference suffit
6. **Dev/Test 24/7** - Dev endpoint always on
7. **Old Model Version** - Model pas updated depuis 180+ jours
8. **Unused Traffic Split** - Traffic split configuré mais 100% to 1 model
9. **Wrong Region** - Endpoint far from clients
10. **No Request Batching** - Single predictions (should batch)

**Impact:** $10K-50K/an

---

#### 6.2 AI Platform Notebooks (Managed Jupyter) - 10 scénarios
**Équivalent:** SageMaker Notebooks (AWS)
**API:** `notebooks.projects.locations.instances`
**Pricing:**
- n1-standard-4: **$140/mois**
- n1-highmem-8 + GPU: **$800/mois**

**Scénarios:**
1. **Stopped >30 Days** - Instance stopped mais not deleted
2. **Idle Running** - Instance running mais 0 kernel activity (7d)
3. **Over-Provisioned Machine** - Machine type trop puissant
4. **GPU Unused** - GPU instance mais kernels CPU-only
5. **24/7 Running** - Notebook running nights/weekends
6. **Old TensorFlow Version** - TF 1.x (should be 2.x)
7. **No Idle Shutdown** - Pas de auto-shutdown after X minutes idle
8. **Unused Notebooks** - Notebook créé mais jamais ouvert
9. **Large Disk Unused** - Disk 500 GB mais 10 GB used
10. **Wrong Environment** - Custom environment où default suffit

**Impact:** $5K-20K/an

---

### 7️⃣ MANAGED SERVICES (2 ressources) - $7K-30K/an potentiel

#### 7.1 Cloud Composer (Managed Airflow) - 10 scénarios
**Équivalent:** MWAA (AWS) / Azure Data Factory
**API:** `composer.projects.locations.environments`
**Pricing:** **$300-600/mois** (small/medium/large environment)

**Scénarios:**
1. **Zero DAG Runs** - Environnement créé mais 0 DAG runs (30d)
2. **Idle Environment** - Tous DAGs disabled
3. **Over-Provisioned Workers** - Worker count trop élevé
4. **Wrong Machine Type** - High-mem où standard suffit
5. **Old Airflow Version** - Airflow 1.x (should be 2.x)
6. **Unused DAGs** - DAGs créés mais jamais triggered
7. **Failed DAGs** - DAGs en status FAILED depuis 30+ jours
8. **Dev/Test Environment** - Prod-sized environment en dev
9. **No Autoscaling** - Fixed workers avec load variable
10. **Excessive Scheduler Instances** - >1 scheduler (overkill)

**Impact:** $5K-20K/an

---

#### 7.2 Cloud Armor (WAF/DDoS Protection) - 10 scénarios
**Équivalent:** AWS WAF / Azure Firewall
**API:** `compute.securityPolicies`
**Pricing:** $5/policy + $1/rule + $0.75/million requests

**Scénarios:**
1. **Unused Policies** - Policy créée mais pas attached à LB
2. **Zero Requests** - Policy attached mais 0 requests processed
3. **Default Rules Only** - Aucune custom rule (pas de valeur)
4. **Over-Complex Rules** - >50 rules (maintenance nightmare)
5. **Duplicate Rules** - Multiple rules même condition
6. **Wrong Action** - Allow all (should be specific)
7. **No Logging** - Logging disabled (monitoring blind)
8. **Rate Limiting Missing** - Pas de rate limit rules
9. **Geoblocking Waste** - Geo-blocking pays jamais source de traffic
10. **Outdated Threat Intelligence** - Rules pas updated

**Impact:** $2K-10K/an

---

## 🔌 APIs GCP Requises

Pour implémenter la détection de gaspillage, CloudWaste nécessite les APIs GCP suivantes:

### Core APIs (obligatoires):
```python
# Compute & Networking
google-cloud-compute==1.15.0          # Instances, Disks, IPs, Load Balancers, NAT
google-cloud-container==2.35.0        # GKE Clusters
google-cloud-run==0.10.0             # Cloud Run Services
google-cloud-functions==1.13.0       # Cloud Functions

# Storage
google-cloud-storage==2.14.0         # Cloud Storage Buckets
google-cloud-filestore==1.7.0        # Filestore

# Databases
google-cloud-sql==1.10.0             # Cloud SQL
google-cloud-spanner==3.38.0         # Cloud Spanner
google-cloud-firestore==2.14.0       # Firestore
google-cloud-bigtable==2.21.0        # Bigtable
google-cloud-redis==2.13.0           # Memorystore

# Analytics
google-cloud-bigquery==3.14.0        # BigQuery
google-cloud-dataproc==5.8.0         # Dataproc
google-cloud-pubsub==2.18.0          # Pub/Sub
google-cloud-dataflow-client==0.8.0  # Dataflow

# AI/ML
google-cloud-aiplatform==1.38.0      # Vertex AI
google-cloud-notebooks==1.8.0        # AI Platform Notebooks

# Monitoring (critical for usage metrics)
google-cloud-monitoring==2.16.0      # Cloud Monitoring (métriques)

# Orchestration & Security
google-cloud-composer==1.10.0        # Cloud Composer
google-cloud-armor==1.0.0            # Cloud Armor

# Authentication
google-auth==2.25.0                  # Service Account auth
google-auth-httplib2==0.1.1
google-auth-oauthlib==1.2.0
```

### APIs à activer dans GCP Console:
```bash
# Compute & Networking
compute.googleapis.com               # Compute Engine API
container.googleapis.com             # Kubernetes Engine API
run.googleapis.com                   # Cloud Run API
cloudfunctions.googleapis.com        # Cloud Functions API

# Storage
storage.googleapis.com               # Cloud Storage API
file.googleapis.com                  # Filestore API

# Databases
sqladmin.googleapis.com              # Cloud SQL Admin API
spanner.googleapis.com               # Cloud Spanner API
firestore.googleapis.com             # Cloud Firestore API
bigtableadmin.googleapis.com         # Cloud Bigtable Admin API
redis.googleapis.com                 # Memorystore for Redis API

# Analytics
bigquery.googleapis.com              # BigQuery API
dataproc.googleapis.com              # Cloud Dataproc API
pubsub.googleapis.com                # Cloud Pub/Sub API
dataflow.googleapis.com              # Dataflow API

# AI/ML
aiplatform.googleapis.com            # Vertex AI API
notebooks.googleapis.com             # Notebooks API

# Monitoring (CRITICAL)
monitoring.googleapis.com            # Cloud Monitoring API
logging.googleapis.com               # Cloud Logging API

# Orchestration & Security
composer.googleapis.com              # Cloud Composer API
```

---

## 🔐 Permissions IAM Nécessaires

CloudWaste nécessite un **Service Account** avec les permissions **READ-ONLY** suivantes:

### Custom Role recommandé: `cloudwaste.scanner`
```yaml
title: "CloudWaste Scanner"
description: "Read-only access for waste detection"
stage: "GA"
includedPermissions:
  # Compute
  - compute.instances.list
  - compute.instances.get
  - compute.disks.list
  - compute.disks.get
  - compute.snapshots.list
  - compute.addresses.list
  - compute.forwardingRules.list
  - compute.targetPools.list
  - compute.routers.list
  - compute.vpnTunnels.list

  # GKE
  - container.clusters.list
  - container.clusters.get
  - container.nodes.list

  # Cloud Run
  - run.services.list
  - run.services.get
  - run.revisions.list

  # Cloud Functions
  - cloudfunctions.functions.list
  - cloudfunctions.functions.get

  # Storage
  - storage.buckets.list
  - storage.buckets.get
  - storage.objects.list

  # Databases
  - cloudsql.instances.list
  - cloudsql.instances.get
  - spanner.instances.list
  - spanner.databases.list
  - datastore.entities.list
  - bigtable.instances.list
  - bigtable.tables.list

  # Analytics
  - bigquery.datasets.get
  - bigquery.tables.list
  - bigquery.jobs.list
  - dataproc.clusters.list
  - pubsub.topics.list
  - pubsub.subscriptions.list

  # Monitoring (REQUIRED)
  - monitoring.timeSeries.list
  - logging.logEntries.list

  # AI/ML
  - aiplatform.endpoints.list
  - notebooks.instances.list
```

### Commande création Service Account:
```bash
# Créer Service Account
gcloud iam service-accounts create cloudwaste-scanner \
  --display-name="CloudWaste Scanner" \
  --description="Read-only scanner for CloudWaste waste detection"

# Attacher custom role au projet
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@PROJECT_ID.iam.gserviceaccount.com" \
  --role="projects/PROJECT_ID/roles/cloudwaste.scanner"

# Générer JSON key
gcloud iam service-accounts keys create cloudwaste-key.json \
  --iam-account=cloudwaste-scanner@PROJECT_ID.iam.gserviceaccount.com
```

**⚠️ SÉCURITÉ CRITIQUE:**
- ✅ **READ-ONLY** uniquement (aucune permission `*.delete`, `*.update`, `*.create`)
- ✅ **Principe du moindre privilège** - uniquement `list` et `get`
- ❌ **JAMAIS** de permissions `compute.instances.delete`, `storage.buckets.delete`, etc.
- ✅ **Rotation des clés** tous les 90 jours

---

## 🗓️ Roadmap d'Implémentation

### **Phase 1 : Ressources Prioritaires (6-8 semaines)**
**Objectif:** Implémenter les 10 ressources avec le plus gros ROI

| Semaine | Ressources | Raison Priorité |
|---------|-----------|-----------------|
| 1-2 | **Compute Engine VMs** + **Persistent Disks** | 40% du coût cloud typique |
| 3 | **Cloud SQL** | Bases de données coûteuses |
| 4 | **GKE Clusters** | Kubernetes = coût élevé si mal géré |
| 5 | **BigQuery** | Storage + queries = potentiel $100K+/an |
| 6 | **Cloud Storage** | Accumulation données = croissance exponentielle |
| 7 | **Static IPs** + **Cloud NAT** | Quick wins, faible complexité |
| 8 | **Cloud Load Balancers** | Coût récurrent sans valeur |

**Livrable Phase 1:** 10 ressources, 100 scénarios, $150K-400K/an économies potentielles

---

### **Phase 2 : Ressources Avancées (4-6 semaines)**
**Objectif:** Compléter couverture analytics, AI/ML, managed services

| Semaine | Ressources | Raison Priorité |
|---------|-----------|-----------------|
| 9 | **Dataproc** + **Pub/Sub** | Analytics waste (Hadoop/Spark clusters) |
| 10 | **Cloud Spanner** + **Bigtable** | High-cost databases |
| 11 | **Vertex AI** + **AI Notebooks** | ML endpoints coûteux |
| 12 | **Cloud Run** + **Cloud Functions** | Serverless compute waste |
| 13 | **Firestore** + **Memorystore** | NoSQL + caching waste |
| 14 | Remaining networking + managed services | Compléter 100% |

**Livrable Phase 2:** 27 ressources, 270 scénarios, $250K-600K/an économies potentielles

---

### **Phase 3 : Optimisations & Métriques Avancées (2-3 semaines)**
**Objectif:** Cloud Monitoring intégration, ML-based anomaly detection

- Intégration Cloud Monitoring pour toutes les ressources
- Détection anomalies avec ML (Vertex AI AutoML)
- Recommandations automatiques (rightsize, migrate)
- Dashboards GCP-specific (Looker Studio integration)

---

## 📈 Impact Financier Estimé

### Par Taille d'Organisation:

| Taille Organisation | Infra GCP | Waste Detecté | Économies/An | ROI CloudWaste |
|---------------------|-----------|---------------|--------------|----------------|
| **Startup (10-50 employees)** | $5K-20K/mois | 20-35% | **$12K-84K** | 10-50x |
| **PME (50-200 employees)** | $20K-100K/mois | 25-40% | **$60K-480K** | 20-100x |
| **Entreprise (200-1000)** | $100K-500K/mois | 30-50% | **$360K-3M** | 50-200x |
| **Grande Entreprise (1000+)** | $500K-5M/mois | 35-60% | **$2M-36M** | 100-500x |

### Top 10 Ressources par Impact:
1. **BigQuery** - $50K-200K/an (storage + queries)
2. **GKE Clusters** - $50K-150K/an (nodes over-provisioned)
3. **Compute Engine VMs** - $30K-100K/an (stopped/idle)
4. **Cloud Spanner** - $30K-100K/an (coût élevé)
5. **Cloud SQL** - $20K-80K/an (stopped/idle)
6. **Persistent Disks** - $20K-50K/an (unattached)
7. **Bigtable** - $20K-50K/an (over-provisioned nodes)
8. **Vertex AI** - $10K-50K/an (idle endpoints)
9. **Dataproc** - $10K-50K/an (clusters always-on)
10. **Cloud Storage** - $10K-40K/an (old objects)

---

## 🎯 Conclusion

Ce document constitue le **référentiel complet** pour l'implémentation GCP dans CloudWaste:

- ✅ **27 ressources GCP** identifiées et documentées
- ✅ **270 scénarios** de gaspillage (10 par ressource)
- ✅ **APIs et permissions** requises
- ✅ **Roadmap** d'implémentation en 3 phases
- ✅ **ROI estimé** : $100K-$300K/an économies (organisation moyenne)

**Prochaines étapes:**
1. Valider la liste avec l'équipe
2. Prioriser les ressources Phase 1 (6-10)
3. Créer fichiers individuels `GCP_XXX_SCENARIOS_100.md` pour chaque ressource
4. Implémenter providers GCP dans `/backend/app/providers/gcp.py`
5. Tester avec compte GCP staging

---

**Dernière mise à jour:** 2 novembre 2025
**Version:** 1.0
**Auteur:** CloudWaste Team + Claude Code
**Status:** 🚧 Documentation Phase - Ready for Implementation
