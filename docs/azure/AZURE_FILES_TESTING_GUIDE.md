# 🧪 Guide de Test - Azure Files Detection

Ce guide explique comment tester manuellement les 7 scénarios de détection Azure Files implémentés dans CloudWaste.

---

## 📋 Prérequis

### 1. Compte Azure
- Subscription Azure active
- Permissions **Contributor** ou **Owner** sur la subscription
- Budget ~$5-10 pour tests (storage minimal)

### 2. Service Principal CloudWaste
```bash
# Créer Service Principal (si non existant)
az ad sp create-for-rbac --name "CloudWaste-Scanner" \
  --role "Reader" \
  --scopes "/subscriptions/{subscription-id}"

# Output attendu:
# {
#   "appId": "...",        # CLIENT_ID
#   "password": "...",     # CLIENT_SECRET
#   "tenant": "..."        # TENANT_ID
# }
```

### 3. Permissions Requises
Le Service Principal doit avoir:
- **Reader** sur subscription (lire Storage Accounts)
- **Storage Account Key Operator Service Role** (lire keys pour File Service access)

```bash
# Attribuer Storage Account Key Operator
az role assignment create \
  --assignee {appId} \
  --role "Storage Account Key Operator Service Role" \
  --scope "/subscriptions/{subscription-id}"
```

### 4. CloudWaste Configuré
- Backend démarré : `http://localhost:8000`
- Compte Azure ajouté dans CloudWaste
- Token JWT valide

---

## 🎯 Scénario 1: File Share Vide (`file_share_empty`)

### Setup
```bash
# 1. Créer Storage Account
az storage account create \
  --name cloudwastetestfiles001 \
  --resource-group rg-cloudwaste-test \
  --location eastus \
  --sku Premium_LRS \
  --kind FileStorage

# 2. Créer file share VIDE avec quota 1000 GB
az storage share create \
  --name empty-premium-share \
  --account-name cloudwastetestfiles001 \
  --quota 1000

# 3. NE PAS uploader de fichiers (rester vide)

# 4. Vérifier (doit être 0 GB usage)
az storage share show \
  --name empty-premium-share \
  --account-name cloudwastetestfiles001 \
  --query "properties.shareUsageBytes"
# Output attendu: 0
```

### Test CloudWaste
```bash
# 1. Lancer scan Azure
curl -X POST http://localhost:8000/api/v1/scans/start \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "{azure-account-id}"
  }'

# 2. Attendre fin du scan (~2-3 min)
# 3. Récupérer résultats
curl -X GET "http://localhost:8000/api/v1/resources?resource_type=azure_file_share_empty" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Résultat Attendu
```json
{
  "resource_type": "azure_file_share_empty",
  "resource_name": "empty-premium-share",
  "estimated_monthly_cost": 160.0,
  "resource_metadata": {
    "storage_account": "cloudwastetestfiles001",
    "quota_gb": 1000,
    "usage_gb": 0.0,
    "access_tier": "Premium",
    "reason": "File share is empty (0 GB used, 1000 GB quota)"
  }
}
```

### Cleanup
```bash
az storage share delete --name empty-premium-share \
  --account-name cloudwastetestfiles001
```

---

## 🎯 Scénario 2: File Share Jamais Utilisé (`file_share_never_used`)

### Setup
```bash
# 1. Créer Storage Account
az storage account create \
  --name cloudwastetestfiles002 \
  --resource-group rg-cloudwaste-test \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2

# 2. Créer file share
az storage share create \
  --name old-unused-share \
  --account-name cloudwastetestfiles002 \
  --quota 100

# 3. Uploader 1 fichier ancien (simuler)
echo "Old data" > old-file.txt
az storage file upload \
  --share-name old-unused-share \
  --source old-file.txt \
  --account-name cloudwastetestfiles002

# 4. Attendre 1-2 jours OU modifier manuellement last_modified via API
# (Pour test rapide: Azure ne permet pas modifier last_modified directement)
# → Solution: créer le share 90+ jours avant test, ou accepter age=1 jour pour test

# 5. NE PLUS toucher le share (pas d'upload/download/modification)
```

### Test CloudWaste
Même procédure que Scénario 1, filtrer par `azure_file_share_never_used`

### Résultat Attendu
Si `last_modified` > 90 jours:
```json
{
  "resource_type": "azure_file_share_never_used",
  "age_days": 92,
  "reason": "File share not modified for 92 days (likely no SMB/NFS connections)"
}
```

**Note** : Pour test rapide, modifier `min_age_days` via Detection Rules API:
```bash
curl -X POST http://localhost:8000/api/v1/detection-rules \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "resource_type": "azure_file_share",
    "rules": {
      "file_share_never_used": {
        "enabled": true,
        "min_age_days": 1
      }
    }
  }'
```

---

## 🎯 Scénario 3: File Share Sur-Provisionné (`file_share_over_provisioned`)

### Setup
```bash
# 1. Créer Storage Account Premium
az storage account create \
  --name cloudwastetestfiles003 \
  --resource-group rg-cloudwaste-test \
  --location eastus \
  --sku Premium_LRS \
  --kind FileStorage

# 2. Créer file share avec GROS quota (5000 GB)
az storage share create \
  --name overprovisioned-share \
  --account-name cloudwastetestfiles003 \
  --quota 5000

# 3. Uploader seulement 100 GB de données (usage=100, quota=5000)
# Créer fichier 1 GB
dd if=/dev/zero of=1gb-file.bin bs=1M count=1024

# Upload 100 fois (ou créer script loop)
for i in {1..100}; do
  az storage file upload \
    --share-name overprovisioned-share \
    --source 1gb-file.bin \
    --path "file-$i.bin" \
    --account-name cloudwastetestfiles003
done

# 4. Vérifier usage
az storage share show \
  --name overprovisioned-share \
  --account-name cloudwastetestfiles003 \
  --query "properties.shareUsageBytes"
# Doit être ~100 GB (107374182400 bytes)
```

### Résultat Attendu
```json
{
  "resource_type": "azure_file_share_over_provisioned",
  "quota_gb": 5000,
  "usage_gb": 100.0,
  "unused_gb": 4900.0,
  "utilization_pct": 2.0,
  "reason": "Premium file share over-provisioned: 2.0% used (100/5000 GB)",
  "recommendation": "Reduce quota to 120 GB to save $784.00/month"
}
```

---

## 🎯 Scénario 4: Premium Sous-Utilisé (`file_share_premium_underutilized`)

### Setup
Même que Scénario 3 (sur-provisionné = sous-utilisé)

### Résultat Attendu
```json
{
  "resource_type": "azure_file_share_premium_underutilized",
  "current_tier": "Premium",
  "recommended_tier": "Hot",
  "monthly_savings": 797.0
}
```

---

## 🎯 Scénario 6: Hot Tier Données Froides (`file_share_hot_tier_cold_data`)

### Setup
```bash
# 1. Créer Storage Account Hot tier
az storage account create \
  --name cloudwastetestfiles006 \
  --resource-group rg-cloudwaste-test \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Hot

# 2. Créer file share
az storage share create \
  --name hot-cold-data-share \
  --account-name cloudwastetestfiles006 \
  --quota 500

# 3. Uploader des fichiers
# Upload 200 GB de données
for i in {1..200}; do
  dd if=/dev/zero of=1gb-file.bin bs=1M count=1024
  az storage file upload \
    --share-name hot-cold-data-share \
    --source 1gb-file.bin \
    --path "file-$i.bin" \
    --account-name cloudwastetestfiles006
done

# 4. NE PLUS toucher pendant 30+ jours
# (Ou modifier detection rule pour min_age_days=1 pour test rapide)
```

### Résultat Attendu (si age > 30 jours)
```json
{
  "resource_type": "azure_file_share_hot_tier_cold_data",
  "current_tier": "Hot",
  "recommended_tier": "Cool",
  "monthly_savings": 3.0,
  "last_modified_days_ago": 35
}
```

---

## 🎯 Scénario 7: GRS en Dev/Test (`file_share_unnecessary_grs`)

### Setup
```bash
# 1. Créer Storage Account GRS avec tag "environment=dev"
az storage account create \
  --name cloudwastetestfiles007 \
  --resource-group rg-cloudwaste-dev \
  --location eastus \
  --sku Standard_GRS \
  --kind StorageV2 \
  --tags environment=dev team=engineering

# 2. Créer file share
az storage share create \
  --name grs-dev-share \
  --account-name cloudwastetestfiles007 \
  --quota 500

# 3. Uploader 100 GB
for i in {1..100}; do
  dd if=/dev/zero of=1gb-file.bin bs=1M count=1024
  az storage file upload \
    --share-name grs-dev-share \
    --source 1gb-file.bin \
    --path "file-$i.bin" \
    --account-name cloudwastetestfiles007
done
```

### Résultat Attendu
```json
{
  "resource_type": "azure_file_share_unnecessary_grs",
  "current_replication": "Standard_GRS",
  "recommended_replication": "Standard_LRS",
  "environment": "dev",
  "monthly_savings": 3.0
}
```

---

## 🎯 Scénario 10: Données Anciennes (`file_share_old_data_never_accessed`)

### Setup
Similaire au Scénario 2, mais avec `min_age_days=180`

Pour test rapide:
```bash
# Modifier detection rule
curl -X POST http://localhost:8000/api/v1/detection-rules \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "resource_type": "azure_file_share",
    "rules": {
      "file_share_old_data_never_accessed": {
        "enabled": true,
        "min_age_days": 1
      }
    }
  }'
```

---

## 🧹 Cleanup Complet

```bash
# Supprimer tous les Storage Accounts de test
az storage account delete --name cloudwastetestfiles001 --yes
az storage account delete --name cloudwastetestfiles002 --yes
az storage account delete --name cloudwastetestfiles003 --yes
az storage account delete --name cloudwastetestfiles006 --yes
az storage account delete --name cloudwastetestfiles007 --yes

# Supprimer resource group (si créé uniquement pour tests)
az group delete --name rg-cloudwaste-test --yes
```

---

## 🔍 Vérification Dashboard

### 1. Naviguer vers Dashboard
```
http://localhost:3000/dashboard/resources
```

### 2. Filtrer par Azure Files
- Resource Type filter: `azure_file_share_*`
- Provider: `Azure`

### 3. Vérifier Metadata
Chaque orphan resource doit afficher:
- ✅ `storage_account` name
- ✅ `quota_gb` et `usage_gb`
- ✅ `access_tier` (Hot/Cool/Premium)
- ✅ `estimated_monthly_cost`
- ✅ `already_wasted`
- ✅ `recommendation`
- ✅ `confidence` level

---

## 📊 Scénarios TODO Phase 2

Les scénarios suivants nécessitent implémentation Phase 2:

### 5. `file_share_snapshots_accumulated`
- **Blocage** : Nécessite `ShareClient.list_share_snapshots()` API call
- **Implémentation actuelle** : Retourne `None`

### 8. `file_share_snapshots_orphaned`
- **Blocage** : Nécessite cross-checking snapshots vs parent shares
- **Implémentation actuelle** : Retourne `[]`

### 9. `file_share_soft_delete_retention`
- **Blocage** : Nécessite File Service properties API
- **Implémentation actuelle** : Retourne `None`

**Ces scénarios seront implémentés dans Phase 2 avec Azure Monitor metrics.**

---

## ❓ FAQ Troubleshooting

### Q: "No file shares detected" malgré shares existants
**A**: Vérifier:
1. Service Principal a role **Storage Account Key Operator**
2. Storage Account `kind` ∈ `["FileStorage", "StorageV2", "Storage"]`
3. Resource group dans scope (si filtrage configuré)

### Q: Tous les shares détectés comme "empty" alors qu'ils ont des fichiers
**A**: Vérifier:
1. `usage_bytes` > 0 via `az storage share show`
2. Fichiers réellement uploadés (pas juste créés localement)
3. Logs CloudWaste backend pour errors API

### Q: Pricing incorrect (différent de docs)
**A**:
- Pricing hardcodé dans MVP : Hot=$0.03, Cool=$0.0152, Premium=$0.16
- Phase 2 intégrera Azure Pricing API pour pricing dynamique
- Pricing peut varier selon région (docs basés sur US East)

---

## 📚 Références

- [Azure Files Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
- [Azure CLI - Storage Files](https://learn.microsoft.com/en-us/cli/azure/storage/share)
- [Service Principal Permissions](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#storage-account-key-operator-service-role)

---

**✅ Guide complet pour tester 7/10 scénarios Azure Files implémentés**
