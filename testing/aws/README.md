# AWS Cost Optimization Testing Infrastructure

Infrastructure automatisée pour créer des ressources AWS de test et valider la détection Cost Optimization de CutCosts.

## 📋 Prérequis

- **AWS CLI** installé et configuré
- **Terraform** >= 1.5.0
- **Credentials AWS** avec permissions pour créer ressources
- **Région** : Europe (Stockholm) - `eu-north-1`

## 🚀 Quick Start

### 1. Configuration initiale

```bash
cd testing/aws

# Copier le template de variables
cp .env.example .env

# Éditer .env avec vos credentials AWS
vim .env

# Initialiser Terraform
cd terraform && terraform init && cd ..
```

### 2. Créer toutes les ressources de test

```bash
# Créer toutes les ressources AWS (Batch 1-5)
./scripts/create.sh

# Attendre 3+ jours pour que CutCosts détecte (min_age_days)
# OU utiliser l'endpoint /test/detect-resources en mode DEBUG
```

### 3. Vérifier le statut

```bash
# Afficher toutes les ressources créées
./scripts/status.sh

# Estimation des coûts
terraform -chdir=terraform show | grep -A 5 "monthly_cost"
```

### 4. Détruire toutes les ressources

```bash
# ⚠️  ATTENTION : Supprime TOUTES les ressources de test
./scripts/destroy.sh
```

## 🎉 Implementation Status (November 25, 2025)

### ✅ AWS Cost Optimization Hub - COMPLETE

L'implémentation de **AWS Cost Optimization Hub** est **terminée et validée** avec succès le **25 novembre 2025**.

**Résultats de test Batch 4** :
- ✅ **10 types de ressources** détectés avec précision à 100%
- ✅ **Coût total détecté** : $1,295.43/mois
- ✅ **Dual scanner system** : `AWSProvider` (Waste) + `AWSInventoryScanner` (Optimization)
- ✅ **Zéro duplicate** après correction des bugs

**Ressources testées avec succès** :
1. **Redshift Cluster** - $792.78/mois (CRITICAL - 0 connections)
2. **DocumentDB Cluster** - $202.21/mois (CRITICAL - 0 connections)
3. **MSK Cluster** - $104.20/mois (CRITICAL - 0 throughput)
4. **Neptune Cluster** - $63.39/mois (CRITICAL - 0 connections)
5. **VPN Connection** - $36.00/mois (CRITICAL - 0 data transfer)
6. **Transit Gateway** - $36.00/mois (CRITICAL - 0 data transfer)
7. **Load Balancer (ALB)** - $28.45/mois (Optimized)
8. **Global Accelerator** - $18.00/mois (HIGH - 0 traffic)
9. **VPC Endpoint S3** - $7.20/mois (HIGH - migrate to gateway)
10. **VPC Endpoint** - $7.20/mois (LOW - enable private DNS)

**🎯 Prochaines étapes** :
- 🔄 **Waste Detection** : Implémentation de scénarios supplémentaires pour AWS
- 🔄 **Azure/GCP/M365** : Extension du Cost Optimization Hub aux autres providers

---

## 📊 Ressources Créées

### Batch 1 : Core Resources (7 ressources)
- ✅ EBS Volume 1GB (non attaché) - `$0.10/mois`
- ✅ Elastic IP (non associée) - `$3.60/mois`
- ✅ EBS Snapshot 1GB - `$0.05/mois`
- ✅ EC2 Instance t3.micro (stopped) - `$0/mois quand stopped`
- ✅ Application Load Balancer - `$16/mois`
- ✅ RDS db.t3.micro (stopped) - `$0/mois quand stopped`
- ✅ NAT Gateway - `$32/mois`

**Sous-total Batch 1** : ~$52/mois (si tout actif) | ~$20/mois (EC2/RDS stopped)

### Batch 2 : Advanced Resources (8 ressources)
- ✅ FSx for Lustre 1.2TB - `$0/mois` (dans free tier si éligible)
- ✅ Neptune db.t3.medium - `$66/mois`
- ✅ MSK t3.small (1 broker) - `$65/mois`
- ✅ EKS Cluster - `$72/mois` (control plane)
- ✅ SageMaker Endpoint ml.t2.medium - `$47/mois`
- ✅ Redshift dc2.large - `$180/mois`
- ✅ ElastiCache cache.t3.micro - `$12/mois`
- ✅ VPN Connection - `$36/mois`

**Sous-total Batch 2** : ~$478/mois

### Batch 3 : Data/Transfer (3 ressources)
- ✅ EMR Cluster m5.xlarge - `$115/mois`
- ✅ SageMaker Notebook ml.t3.medium - `$47/mois`
- ✅ Transfer Family Server - `$216/mois`

**Sous-total Batch 3** : ~$378/mois

### Batch 4 : Cost Optimization Hub Resources (10 ressources)
- ✅ Redshift Cluster dc2.large - `$792.78/mois`
- ✅ DocumentDB Cluster db.t3.medium - `$202.21/mois`
- ✅ MSK Cluster t3.small (1 broker) - `$104.20/mois`
- ✅ Neptune Cluster db.t3.medium - `$63.39/mois`
- ✅ VPN Connection - `$36.00/mois`
- ✅ Transit Gateway - `$36.00/mois`
- ✅ Application Load Balancer - `$28.45/mois`
- ✅ Global Accelerator - `$18.00/mois`
- ✅ VPC Endpoint S3 - `$7.20/mois`
- ✅ VPC Endpoint - `$7.20/mois`

**Sous-total Batch 4** : ~$1,295/mois

**⚠️ IMPORTANT** : Batch 4 contient des ressources coûteuses (Redshift, DocumentDB, Neptune). Utilisé exclusivement pour valider **AWS Cost Optimization Hub**.

### Batch 5 : Search/IaC (2 ressources)
- ✅ Kendra Index Developer Edition - `$700/mois`
- ✅ CloudFormation Stack - `$0/mois` (service gratuit)

**Sous-total Batch 5** : ~$700/mois

---

**💰 COÛT TOTAL ESTIMÉ** : ~$1,851/mois si TOUT actif

⚠️  **RECOMMANDATION** :
- Créer UNIQUEMENT Batch 1 pour commencer (~$20/mois avec stopped instances)
- Détruire immédiatement après test avec `./scripts/destroy.sh`
- Services coûteux (Kendra, Redshift, Neptune) : NE PAS ACTIVER sauf besoin

## 🎯 Scénarios de Détection Testés

### Batch 1
1. **EBS Volume** - Unattached (Scenario 1 - HIGH)
2. **Elastic IP** - Unassociated (Scenario 1 - HIGH)
3. **EC2 Instance** - Stopped (Scenario 2 - MEDIUM)
4. **Load Balancer** - Zero traffic (Scenario 1 - HIGH)
5. **RDS** - Stopped instance (Scenario 2 - MEDIUM)
6. **NAT Gateway** - Zero traffic (Scenario 1 - HIGH)
7. **Snapshot** - Old snapshot (Scenario 3 - MEDIUM)

### Batch 2-5
- **FSx** - Zero connections
- **Neptune** - Zero connections
- **MSK** - Zero traffic
- **EKS** - Idle cluster
- Etc.

## 🔧 Scripts Disponibles

### `./scripts/create.sh`
Crée toutes les ressources AWS via Terraform.

**Options** :
```bash
./scripts/create.sh                # Créer Batch 1 uniquement (recommandé)
./scripts/create.sh --all          # Créer TOUS les batches (⚠️  COÛTEUX)
./scripts/create.sh --batch 1 2 3  # Créer batches spécifiques
```

### `./scripts/destroy.sh`
Détruit toutes les ressources créées.

**Options** :
```bash
./scripts/destroy.sh              # Détruire tout (avec confirmation)
./scripts/destroy.sh --force      # Détruire sans confirmation (DANGER)
./scripts/destroy.sh --batch 2    # Détruire batch spécifique
```

### `./scripts/status.sh`
Affiche le statut de toutes les ressources.

**Output** :
```
✅ EBS Volume (vol-xxx) - 1GB - Unattached - $0.10/mois
✅ Elastic IP (eip-xxx) - Unassociated - $3.60/mois
⚠️  Total : $52.15/mois
```

### `./scripts/setup.sh`
Vérifie les prérequis et initialise l'environnement.

## 📝 Variables d'Environnement

Créer `.env` depuis `.env.example` :

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=eu-north-1

# Testing Configuration
TF_VAR_environment=test
TF_VAR_project_name=cutcosts-testing
TF_VAR_owner_email=your-email@example.com

# Optional: S3 Backend for Terraform State
# TF_VAR_state_bucket=your-terraform-state-bucket
```

## 🔐 Sécurité

### IAM Permissions Requises

Pour créer les ressources :
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*",
        "rds:*",
        "elasticloadbalancing:*",
        "s3:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "kendra:*",
        "cloudformation:*"
      ],
      "Resource": "*"
    }
  ]
}
```

**⚠️  IMPORTANT** : Utilisez un IAM user DÉDIÉ pour ces tests, PAS votre compte admin.

### Nettoyage Automatique

Pour éviter les coûts imprévus :
```bash
# Cron job pour auto-destroy après 24h
0 0 * * * cd /path/to/testing/aws && ./scripts/destroy.sh --force
```

## 📚 Documentation Terraform

### Structure

```
terraform/
├── main.tf          # Configuration VPC, networking
├── provider.tf      # AWS provider
├── variables.tf     # Variables globales
├── outputs.tf       # Outputs (IDs, ARNs)
├── batch1.tf        # Ressources Batch 1
├── batch2.tf        # Ressources Batch 2
├── batch3.tf        # Ressources Batch 3
├── batch4.tf        # Ressources Batch 4
├── batch5.tf        # Ressources Batch 5
└── versions.tf      # Versions Terraform/providers
```

### Commandes Terraform Utiles

```bash
cd terraform

# Initialiser
terraform init

# Planifier changements
terraform plan

# Appliquer (créer ressources)
terraform apply -auto-approve

# Détruire tout
terraform destroy -auto-approve

# Afficher state
terraform show

# Lister ressources
terraform state list
```

## 🐛 Bugs Corrigés Pendant l'Implémentation

### Bug 1 : Détection en Double (DocumentDB/Neptune)

**Problème** : Le cluster Neptune apparaissait 2 fois (comme `neptune_cluster` ET `documentdb_cluster`), résultant en 12 ressources au lieu de 10.

**Cause** : L'API AWS DocumentDB (`docdb.describe_db_clusters()`) retourne à la fois DocumentDB ET Neptune car ils partagent la même API.

**Correction** : Ajout d'un filtre dans `scan_documentdb_clusters()` pour ignorer les clusters Neptune.

**Fichier** : `/backend/app/services/inventory_scanner.py:11195-11197`

```python
engine = cluster.get("Engine", "docdb")

# Skip Neptune clusters (handled by scan_neptune_clusters)
if engine != "docdb":
    continue
```

**Date de correction** : 25 novembre 2025

---

### Bug 2 : Mauvaise Classification RDS

**Problème** : Les instances DocumentDB et Neptune apparaissaient comme `rds_instance`, causant des duplicates supplémentaires.

**Cause** : L'API AWS RDS (`rds.describe_db_instances()`) retourne TOUTES les instances de bases de données, incluant DocumentDB et Neptune.

**Correction** : Ajout d'un filtre dans `scan_rds_instances()` pour ignorer DocumentDB/Neptune.

**Fichier** : `/backend/app/services/inventory_scanner.py:1257-1259`

```python
db_engine = db_instance["Engine"]

# Skip DocumentDB and Neptune instances (handled by their dedicated cluster scanners)
if db_engine in ["docdb", "neptune"]:
    continue
```

**Date de correction** : 25 novembre 2025

---

### Bug 3 : VPN Connection Non Détectée

**Problème** : La VPN Connection existait dans AWS mais n'était pas détectée lors du scan.

**Erreur Celery** :
```
[error] vpn.connection_scan_failed error=AWSInventoryScanner._get_cloudwatch_metric_sum() missing 1 required positional argument: 'statistic'
```

**Cause** : La méthode `_get_cloudwatch_metric_sum()` requiert le paramètre `statistic` mais les appels ne le fournissaient pas.

**Correction** : Ajout de `statistic="Sum"` aux deux appels CloudWatch dans `scan_vpn_connections()`.

**Fichier** : `/backend/app/services/inventory_scanner.py:9779, 9793`

```python
# Before fix
total_bytes_in_30d = await self._get_cloudwatch_metric_sum(
    region=region,
    namespace="AWS/VPN",
    metric_name="TunnelDataIn",
    dimensions=[{"Name": "VpnId", "Value": vpn_id}],
    start_time=start_time,
    end_time=end_time,
    period=86400,
    # statistic parameter was MISSING
)

# After fix
total_bytes_in_30d = await self._get_cloudwatch_metric_sum(
    region=region,
    namespace="AWS/VPN",
    metric_name="TunnelDataIn",
    dimensions=[{"Name": "VpnId", "Value": vpn_id}],
    start_time=start_time,
    end_time=end_time,
    period=86400,
    statistic="Sum",  # ✅ ADDED
)
```

**Date de correction** : 25 novembre 2025

---

## 🐛 Dépannage

### Erreur : "Insufficient permissions"
➜ Vérifiez que votre IAM user a les permissions requises

### Erreur : "Resource quota exceeded"
➜ Certaines ressources ont des limites par région (ex: Elastic IPs = 5 par défaut)
➜ Demandez une augmentation de quota via AWS Support

### Erreur : "State lock"
➜ Si Terraform state verrouillé : `terraform force-unlock <lock-id>`

### Coûts inattendus
➜ Vérifiez que toutes les ressources ont été détruites : `./scripts/status.sh`
➜ Vérifiez AWS Cost Explorer pour les coûts cachés

### CloudWatch Log Groups orphelins
⚠️ **Comportement AWS** : Certains services créent automatiquement des CloudWatch Log Groups qui ne sont PAS gérés par Terraform.

**Services concernés** :
- `/aws/sagemaker/*` - SageMaker Endpoints
- `/aws/lambda/*` - Lambda functions
- `/aws/ecs/*` - ECS tasks
- `/aws/apigateway/*` - API Gateway (si logging activé)

**Problème** : Quand vous faites `terraform destroy`, ces logs ne sont PAS supprimés automatiquement et génèrent des coûts (même minimes).

**Solution** : Le script `destroy.sh` nettoie maintenant AUTOMATIQUEMENT tous les CloudWatch Log Groups orphelins contenant "cutcosts" dans leur nom.

```bash
./scripts/destroy.sh --force

# Output:
# Destroying AWS resources...
# Terraform destroy complete!
#
# Checking for orphaned CloudWatch Log Groups...
# Found orphaned log groups:
#   - /aws/sagemaker/Endpoints/cutcosts-testing-sagemaker-endpoint
#     ✓ Deleted
#
# All resources destroyed successfully!
```

**Vérification manuelle** :
```bash
aws logs describe-log-groups \
  --region eu-north-1 \
  --query "logGroups[?contains(logGroupName, 'cutcosts')].logGroupName" \
  --output table
```

## 🔄 Workflow Recommandé

1. **Jour 1** : Créer Batch 1 uniquement
   ```bash
   ./scripts/create.sh
   ```

2. **Jour 1** : Ajouter compte AWS à CutCosts
   - Dashboard → Cloud Accounts → Add AWS Account
   - Access Key : read-only IAM user
   - Régions : `eu-north-1`

3. **Jour 1** : Scanner immédiatement (mode DEBUG)
   - CutCosts détecte ressources MAIS les marque comme "trop récentes"
   - OU utiliser `/api/v1/test/detect-resources` avec `min_age_days: 0`

4. **Jour 4** : Scanner en mode normal
   - CutCosts détecte ressources comme waste (>3 jours)
   - Vérifier scénarios d'optimisation

5. **Jour 4** : Détruire ressources
   ```bash
   ./scripts/destroy.sh
   ```

## 💡 Astuces

- **Coûts minimaux** : Créer uniquement Batch 1 (~$20/mois)
- **Test rapide** : Utiliser endpoint `/test/detect-resources` (DEBUG mode)
- **Stop instances** : EC2 et RDS sont automatiquement stopped après création
- **Tags** : Toutes les ressources ont `Environment=test` et `Project=cutcosts-testing`
- **Cleanup** : Script `destroy.sh` vérifie que TOUT est supprimé

## 📞 Support

Pour des questions sur cette infrastructure de test :
- Consultez les logs : `./scripts/*.sh` affichent des logs détaillés
- Terraform plan : `cd terraform && terraform plan` pour voir ce qui sera créé
- AWS Console : Vérifiez manuellement dans la console AWS (région Stockholm)

---

**Version** : 2.0
**Dernière mise à jour** : 2025-11-25
**Région** : eu-north-1 (Europe Stockholm)
**Statut** : AWS Cost Optimization Hub - IMPLÉMENTATION TERMINÉE ✅
