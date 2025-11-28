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

### Batch 4 : Platform/Messaging (3 ressources)
- ✅ Elastic Beanstalk Environment - `$0/mois` (service gratuit, paie EC2)
- ✅ Direct Connect Connection 1Gbps - `$216/mois`
- ✅ MQ Broker t3.micro - `$27/mois`

**Sous-total Batch 4** : ~$243/mois

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

- **Coûts minimaux** : Créer uniquement Batch 1 (~$20/mois)destroy
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

**Version** : 1.0
**Dernière mise à jour** : 2025-01-18
**Région** : eu-north-1 (Europe Stockholm)
