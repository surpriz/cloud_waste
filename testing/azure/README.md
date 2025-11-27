# Azure Cost Optimization Testing Infrastructure

Infrastructure automatisée pour créer des ressources Azure de test et valider la détection Cost Optimization de CutCosts.

## 🎉 Résultats de Test - Batch #1

**Statut : ✅ TESTÉ ET VALIDÉ** (2025-11-26)

| Métrique | Résultat |
|----------|----------|
| **Ressources créées** | 7 ressources |
| **Ressources détectées** | **6/7 (85.7%)** ✅ |
| **Scénarios de détection** | **13 scénarios** validés |
| **Recommandations Cost Optimization** | 6 recommandations |
| **Waste mensuel détecté** | $26.60/mois |
| **Économies potentielles** | $4.83/mois |

### Ressources Testées

- ✅ **Managed Disk** (Unattached) - 1 scénario détecté
- ✅ **Public IP** (Unassociated) - 2 scénarios détectés
- ✅ **Virtual Machine** (Deallocated) - 4 scénarios détectés
- ✅ **Load Balancer** (Zero traffic) - 3 scénarios détectés
- ✅ **Storage Account** (Never used) - 1 scénario détecté
- ❌ **ExpressRoute Circuit** - Non détecté (à implémenter)

**📄 Rapport détaillé :** [RESULTS_BATCH1.md](./RESULTS_BATCH1.md)

## 📋 Prérequis

- **Azure CLI** installé et configuré
- **Terraform** >= 1.5.0
- **Service Principal Azure** avec permissions Reader
- **Région** : Europe (West Europe) - `westeurope`
- **SSH Key** : `~/.ssh/id_rsa.pub` (pour la VM)

## 🚀 Quick Start

### 1. Configuration initiale

```bash
cd testing/azure

# Copier le template de variables
cp .env.example .env

# Créer un Service Principal Azure
az ad sp create-for-rbac --name "CutCosts-Testing" --role Reader --scopes /subscriptions/YOUR_SUBSCRIPTION_ID

# Éditer .env avec les credentials du Service Principal
vim .env

# Générer une clé SSH si nécessaire
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''

# Vérifier les prérequis et initialiser Terraform
./scripts/setup.sh
```

### 2. Créer les ressources de test

```bash
# Créer toutes les ressources Azure (Batch 1)
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

### Batch 1 : Core Resources (6 ressources)

- ✅ **Managed Disk** 10GB Standard HDD (non attaché) - `€1/mois`
- ✅ **Public IP Address** Standard SKU (non associée) - `€3/mois`
- ✅ **Virtual Machine** Standard_B1s (deallocated) - `€0/mois quand stopped`
- ✅ **Load Balancer** Standard SKU (zero traffic) - `€18/mois`
- ✅ **Storage Account** Standard LRS (minimal usage) - `€1/mois`
- ✅ **ExpressRoute Circuit** 50 Mbps Local (zero traffic) - `€45/mois`

**Sous-total Batch 1** : ~€68/mois (~$73/mois)

### Batch 2 : Advanced Resources (À venir)
- 🔄 En cours de planification

### Batch 3 : Premium Resources (À venir)
- 🔄 En cours de planification

---

**💰 COÛT TOTAL ESTIMÉ** : ~€68/mois (Batch 1 uniquement)

⚠️  **RECOMMANDATION** :
- Créer UNIQUEMENT Batch 1 pour commencer (~€68/mois)
- Détruire immédiatement après test avec `./scripts/destroy.sh`
- La VM est automatiquement deallocated (€0/mois)

## 🎯 Scénarios de Détection Testés

### Batch 1
1. **Managed Disk** - Unattached (Scenario 1 - HIGH)
2. **Public IP Address** - Unassociated (Scenario 1 - HIGH)
3. **Virtual Machine** - Deallocated (Scenario 2 - MEDIUM)
4. **Load Balancer** - Zero traffic (Scenario 1 - HIGH)
5. **Storage Account** - Minimal usage (Scenario 3 - LOW)
6. **ExpressRoute Circuit** - Zero traffic (Scenario 1 - CRITICAL)

## 🔧 Scripts Disponibles

### `./scripts/setup.sh`
Vérifie les prérequis et initialise Terraform.

**Vérifications** :
- ✅ Azure CLI installé
- ✅ Terraform >= 1.5.0
- ✅ Credentials Azure (Service Principal)
- ✅ SSH Key présent (~/.ssh/id_rsa.pub)

### `./scripts/create.sh`
Crée toutes les ressources Azure via Terraform.

**Options** :
```bash
./scripts/create.sh                # Créer Batch 1 uniquement (recommandé)
./scripts/create.sh --all          # Créer TOUS les batches
./scripts/create.sh --batch 1 2    # Créer batches spécifiques
./scripts/create.sh --force        # Sans confirmation
```

### `./scripts/status.sh`
Affiche le statut de toutes les ressources.

**Output** :
```
✅ Managed Disk: cutcosts-testing-unattached-disk - 10GB - Unattached - €1/mois
✅ Public IP: 51.124.xxx.xxx - Unassociated - €3/mois
✅ Virtual Machine: cutcosts-testing-stopped-vm - VM deallocated - €0/mois
⚠️  Total : €68/mois
```

### `./scripts/destroy.sh`
Détruit toutes les ressources créées.

**Options** :
```bash
./scripts/destroy.sh              # Détruire tout (avec confirmation)
./scripts/destroy.sh --force      # Détruire sans confirmation (DANGER)
```

## 📝 Variables d'Environnement

Créer `.env` depuis `.env.example` :

```bash
# Azure Service Principal Credentials
ARM_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ARM_CLIENT_SECRET=your-secret-here
ARM_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ARM_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Azure Region
AZURE_REGION=westeurope

# Testing Configuration
TF_VAR_environment=test
TF_VAR_project_name=cutcosts-testing
TF_VAR_owner_email=your-email@example.com

# Batch Control
TF_VAR_enable_batch_1=true   # Core resources (~€68/mois)
TF_VAR_enable_batch_2=false  # Advanced (TBD)
TF_VAR_enable_batch_3=false  # Premium (TBD)
```

## 🔐 Sécurité

### Créer un Service Principal Azure

Pour créer les ressources de test, vous devez créer un **Service Principal** avec le rôle **Reader** :

```bash
# Créer le Service Principal
az ad sp create-for-rbac \
  --name "CutCosts-Testing" \
  --role Reader \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID

# Output:
# {
#   "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",          # ARM_CLIENT_ID
#   "displayName": "CutCosts-Testing",
#   "password": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",      # ARM_CLIENT_SECRET
#   "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"          # ARM_TENANT_ID
# }
```

**⚠️  IMPORTANT** :
- Le Service Principal doit avoir UNIQUEMENT le rôle **Reader** (lecture seule)
- Ne JAMAIS donner des permissions **Contributor** ou **Owner** pour les tests
- Utilisez un Service Principal DÉDIÉ pour ces tests, PAS votre compte admin

### Permissions Requises

Le Service Principal doit avoir :
- ✅ **Reader** sur la subscription (lecture seule)
- ❌ **PAS de Contributor** (pas d'écriture)
- ❌ **PAS de Owner** (pas de gestion IAM)

**Pourquoi Reader ?**
- CutCosts détecte les ressources orphelines en lecture seule
- Pas besoin de permissions d'écriture pour scanner
- Sécurité maximale : impossible de supprimer accidentellement des ressources

### Générer une clé SSH

La Virtual Machine nécessite une clé SSH publique :

```bash
# Générer une nouvelle clé SSH (si nécessaire)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''

# Vérifier la clé
ls -la ~/.ssh/id_rsa.pub
```

### Nettoyage Automatique

Pour éviter les coûts imprévus :
```bash
# Cron job pour auto-destroy après 24h
0 0 * * * cd /path/to/testing/azure && ./scripts/destroy.sh --force
```

## 📚 Documentation Terraform

### Structure

```
terraform/
├── main.tf          # Resource Group, Virtual Network, NSG
├── provider.tf      # Azure provider
├── variables.tf     # Variables globales
├── outputs.tf       # Outputs (IDs, noms)
├── batch1.tf        # Ressources Batch 1
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

## 🔄 Workflow Recommandé

1. **Jour 1** : Créer Batch 1 uniquement
   ```bash
   ./scripts/create.sh
   ```

2. **Jour 1** : Ajouter compte Azure à CutCosts
   - Dashboard → Cloud Accounts → Add Azure Account
   - Service Principal : même credentials que .env
   - Régions : `westeurope`

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

## 🐛 Dépannage

### Erreur : "Insufficient permissions"
➜ Vérifiez que votre Service Principal a le rôle **Reader** sur la subscription

### Erreur : "SSH key not found"
➜ Générez une clé SSH avec `ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''`

### Erreur : "ExpressRoute provider not available"
➜ ExpressRoute nécessite un provider (Equinix, etc.). Si non disponible dans votre région, désactivez cette ressource dans `batch1.tf`

### Erreur : "State lock"
➜ Si Terraform state verrouillé : `terraform force-unlock <lock-id>`

### Coûts inattendus
➜ Vérifiez que toutes les ressources ont été détruites : `./scripts/status.sh`
➜ Vérifiez Azure Cost Management pour les coûts cachés

### VM ne se stop pas
➜ La VM est automatiquement **deallocated** après création via `az vm deallocate`
➜ Vérifiez avec : `az vm show -g cutcosts-testing-rg -n cutcosts-testing-stopped-vm --query "powerState"`

## 💡 Astuces

- **Coûts minimaux** : La VM deallocated coûte €0/mois (seul le disque est facturé)
- **Test rapide** : Utiliser endpoint `/test/detect-resources` (DEBUG mode)
- **Tags** : Toutes les ressources ont `Environment=test` et `Project=cutcosts-testing`
- **Cleanup** : Script `destroy.sh` vérifie que TOUT est supprimé
- **ExpressRoute** : Circuit non provisionné = pas de frais de data transfer

## 🎉 Différences avec AWS

| Aspect | AWS | Azure |
|--------|-----|-------|
| **Credentials** | IAM Access Keys | Service Principal |
| **Networking** | VPC | Virtual Network |
| **Security** | Security Group | Network Security Group |
| **Organization** | Regions only | Resource Groups + Regions |
| **VM Cost (stopped)** | $0 (stopped) | €0 (deallocated) |
| **Pricing** | Per hour | Per hour |

## 📞 Support

Pour des questions sur cette infrastructure de test :
- Consultez les logs : `./scripts/*.sh` affichent des logs détaillés
- Terraform plan : `cd terraform && terraform plan` pour voir ce qui sera créé
- Azure Portal : Vérifiez manuellement dans le portail Azure (West Europe)

---

**Version** : 1.0
**Dernière mise à jour** : 2025-11-26
**Région** : westeurope (Europe West)
**Statut** : Azure Batch 1 - IMPLÉMENTATION COMPLÈTE ✅
