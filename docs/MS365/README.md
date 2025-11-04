# 📁 Documentation Microsoft 365 - CloudWaste

Ce répertoire contient la documentation complète pour l'implémentation de la détection de gaspillage sur **Microsoft 365 (MS365)**.

---

## 🆚 Microsoft 365 vs Azure : Distinction Critique

**⚠️ IMPORTANT:** Microsoft 365 et Azure sont **DEUX produits Microsoft distincts** !

| Aspect | Microsoft 365 (MS365) | Azure (Cloud Infrastructure) |
|--------|----------------------|------------------------------|
| **Type** | SaaS (Software as a Service) | IaaS/PaaS (Infrastructure/Platform) |
| **Services** | SharePoint, Teams, Exchange, Power BI | VMs, Disks, SQL Database, Storage Accounts |
| **API** | Microsoft Graph API | Azure Resource Manager API |
| **Endpoint** | `graph.microsoft.com` | `management.azure.com` |
| **Pricing** | Per-user ($6-57/mois) | Pay-as-you-go (usage) |
| **Auth** | App Registration (Graph permissions) | Service Principal (ARM permissions) |
| **Use Case** | Collaboration, productivité, BI | Hébergement apps, infrastructure cloud |

💡 **En résumé:**
- **Azure** = Infrastructure cloud (comme AWS/GCP) → Voir `/docs/azure/`
- **Microsoft 365** = Suite bureautique cloud → Ce répertoire (`/docs/MS365/`)

---

## 📄 Fichiers Disponibles

### **1. Nouveaux Fichiers (Listing Complet)**

#### `MS365.csv` - Import Excel
**Description:** Tableau récapitulatif complet des 14 ressources Microsoft 365
**Contenu:**
- 14 ressources MS365 (SharePoint, OneDrive, Teams, Exchange, Power BI, etc.)
- 140 scénarios de gaspillage (10 par ressource)
- Colonnes : ID, Catégorie, Ressource, Équivalents AWS/Azure, Scénarios, Priorité, Coût, Impact, Status, Complexité, API, Permissions

**Usage:**
```bash
# Import dans Excel
1. Ouvrir Excel
2. Data → From Text/CSV
3. Sélectionner MS365.csv
4. Delimiter: Comma

# Import dans Google Sheets
1. Ouvrir Google Sheets
2. File → Import → Upload
3. Sélectionner MS365.csv
4. Separator: Comma
```

---

#### `MS365.md` - Documentation Complète
**Description:** Document principal avec TOUS les détails MS365
**Contenu:**
- Vue d'ensemble MS365 vs Azure (différences critiques)
- Tableau récapitulatif des 14 ressources
- Détail de chaque ressource (10 scénarios/ressource)
- Microsoft Graph API requise et permissions
- Roadmap d'implémentation en 5 phases
- Estimations de coûts et ROI ($20K-100K/an)

**Usage:** Documentation de référence pour développeurs

---

### **2. Documentation Existante (SharePoint & OneDrive)**

#### `SHAREPOINT_ONEDRIVE_SCENARIOS_100.md`
**Description:** Spécification détaillée SharePoint & OneDrive (10 scénarios)
**Status:** ✅ Partiellement implémenté (5/10 par ressource)

**Scénarios SharePoint (5/10 implemented):**
1. ✅ Large Files Unused
2. ✅ Duplicate Files
3. ✅ Abandoned Sites
4. ✅ Excessive Versioning
5. ✅ Old Recycle Bin
6. ❌ Unused Document Libraries
7. ❌ Over-Shared External Links
8. ❌ Deprecated Workflows
9. ❌ Large Lists Without Indexes
10. ❌ Sites Without Owners

**Scénarios OneDrive (5/10 implemented):**
1. ✅ Large Files Unused
2. ✅ Disabled Users Storage
3. ✅ Temp Files Accumulated
4. ✅ Excessive External Sharing
5. ✅ Duplicate Attachments
6. ❌ Old Backup Folders
7. ❌ Camera Roll Sync
8. ❌ Desktop Sync Waste
9. ❌ Recycle Bin Retention
10. ❌ Inactive Users >1 Year

---

#### `SHAREPOINT_ONEDRIVE_ARCHITECTURE.md`
**Description:** Architecture technique SharePoint/OneDrive provider
**Contenu:**
- Microsoft Graph API calls
- Authentication flow (App Registration)
- Data structures et schemas
- Performance considerations

---

#### `SHAREPOINT_ONEDRIVE_TESTING_GUIDE.md`
**Description:** Guide de test manuel SharePoint/OneDrive
**Contenu:**
- Setup compte M365 test
- Création de données de test (fichiers, sites)
- Validation des scénarios
- Troubleshooting

---

#### `MICROSOFT365_TEST_PROTOCOL.md`
**Description:** Protocole complet de test end-to-end
**Contenu:**
- Prérequis (compte M365, App Registration)
- Setup environment (containers, credentials)
- Tests API via curl
- Validation résultats

---

## 🎯 Vue d'Ensemble MS365

### Statistiques Clés:
- **14 ressources MS365** identifiées
- **140 scénarios de gaspillage** (10 par ressource)
- **$20K-$100K/an** économies potentielles (organisation 500-2000 users)

### Catégories de Ressources:

| Catégorie | Ressources | Impact Annuel | Status |
|-----------|-----------|---------------|--------|
| **Collaboration** | 4 (SharePoint, OneDrive, Teams, Groups) | $26K-110K | Partial (10/40) |
| **Communication** | 2 (Exchange, Yammer) | $16K-65K | Not Started |
| **Power Platform** | 3 (Power BI, Apps, Automate) | $11K-70K | Not Started |
| **Content** | 3 (Stream, Forms, Planner) | $3.5K-20K | Not Started |
| **Licensing** | 2 (Licenses, User Accounts) | $35K-150K | Not Started |
| **TOTAL** | **14 ressources** | **$91.5K-415K** | 10/140 (7%) |

### Top 5 Priorités (ROI maximal):

1. 🔴 **M365 Licenses** - $20K-80K/an (licences non assignées/utilisées)
2. 🔴 **User Accounts Inactive** - $15K-70K/an (utilisateurs inactifs avec licences)
3. 🔴 **Exchange Mailboxes** - $15K-60K/an (mailboxes inutilisées)
4. 🔴 **SharePoint Sites** - $10K-40K/an (storage abandonné)
5. 🔴 **OneDrive** - $8K-30K/an (fichiers utilisateurs inactifs)

---

## 🚀 Roadmap d'Implémentation

### **Phase 1 - SharePoint & OneDrive Completion (2-3 semaines)** ✅ EN COURS
**Objectif:** Compléter les 10/10 scénarios SharePoint + OneDrive

**Ressources:**
- SharePoint Online Sites (compléter 5 scénarios manquants)
- OneDrive for Business (compléter 5 scénarios manquants)

**Livrable:** 2 ressources, 20 scénarios, $18K-70K/an économies

---

### **Phase 2 - Licensing & Governance (2-3 semaines)**
**Objectif:** Highest ROI - Licences et utilisateurs inactifs

**Ressources:**
1. Microsoft 365 Licenses (10 scénarios)
2. User Accounts Inactive (10 scénarios)

**Livrable:** 4 ressources, 40 scénarios, $53K-220K/an économies cumulées

---

### **Phase 3 - Collaboration (3-4 semaines)**
**Objectif:** Teams, Groups, Exchange

**Ressources:**
1. Microsoft Teams (10 scénarios)
2. Microsoft 365 Groups (10 scénarios)
3. Exchange Online Mailboxes (10 scénarios)

**Livrable:** 7 ressources, 70 scénarios, $74K-330K/an économies cumulées

---

### **Phase 4 - Power Platform (3-4 semaines)**
**Objectif:** Power BI, Power Apps, Power Automate

**Ressources:**
1. Power BI Workspaces (10 scénarios)
2. Power Apps (10 scénarios)
3. Power Automate Flows (10 scénarios)

**Livrable:** 10 ressources, 100 scénarios, $85K-400K/an économies cumulées

---

### **Phase 5 - Content Services (2 semaines)**
**Objectif:** Compléter couverture 100%

**Ressources:**
1. Microsoft Stream (10 scénarios)
2. Microsoft Forms (10 scénarios)
3. Microsoft Planner (10 scénarios)
4. Yammer / Viva Engage (10 scénarios)

**Livrable:** 14 ressources, 140 scénarios (100%), $89K-420K/an économies cumulées

---

## 🔧 Prérequis Techniques

### 1. Entra ID App Registration Setup

```bash
# Azure Portal
1. Aller dans "Azure Active Directory" (ou "Microsoft Entra ID")
2. "App registrations" → "New registration"
3. Nom: "CloudWaste-MS365-Scanner"
4. Supported account types: "Single tenant"
5. Redirect URI: Laisser vide
6. Créer

# Créer Client Secret
1. App registration → "Certificates & secrets"
2. "New client secret"
3. Description: "CloudWaste production"
4. Expires: 24 months
5. Copier la "Value" (visible 1 seule fois!)

# Configurer API Permissions
1. App registration → "API permissions"
2. "Add a permission" → "Microsoft Graph" → "Application permissions"
3. Ajouter les permissions ci-dessous
4. "Grant admin consent for {tenant}" (CRITICAL!)
```

---

### 2. Microsoft Graph API Permissions

**⚠️ Important:** Toutes les permissions doivent être **"Application permissions"**, PAS "Delegated" !

#### **Permissions Minimales (SharePoint + OneDrive):**
```
Files.Read.All          # Lire fichiers SharePoint/OneDrive
Sites.Read.All          # Lister sites SharePoint
User.Read.All           # Lire utilisateurs
Directory.Read.All      # Lire directory info
```

#### **Permissions Complètes (Toutes ressources MS365):**
```
# Files & Storage
Files.Read.All
Sites.Read.All

# Users & Directory
User.Read.All
Directory.Read.All
AuditLog.Read.All       # Sign-in logs (user activity)

# Groups & Teams
Group.Read.All
Team.ReadBasic.All
Channel.ReadBasic.All

# Exchange
Mail.Read
MailboxSettings.Read

# Organization
Organization.Read.All   # Licenses, tenant info
Reports.Read.All        # Usage reports
```

#### **Power Platform (séparé):**
Power BI, Power Apps, Power Automate utilisent des APIs séparées nécessitant des configurations additionnelles (voir MS365.md).

---

### 3. Python Dependencies

```bash
# Ajouter dans backend/requirements.txt
msgraph-core==1.0.0
msal==1.26.0
azure-identity==1.15.0
httpx==0.26.0  # Pour async HTTP calls
```

---

### 4. Tester Credentials

```python
from azure.identity import ClientSecretCredential
import httpx

# Configuration
TENANT_ID = "your-tenant-id"
CLIENT_ID = "your-app-id"
CLIENT_SECRET = "your-app-secret"

# Authenticate
credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)

# Get token
token = credential.get_token("https://graph.microsoft.com/.default")
print(f"✅ Token obtained: {token.token[:50]}...")

# Test API call
headers = {"Authorization": f"Bearer {token.token}"}
response = httpx.get(
    "https://graph.microsoft.com/v1.0/sites",
    headers=headers
)
print(f"✅ API call successful: {response.status_code}")
```

---

## 📚 Prochaines Étapes

### Pour Compléter SharePoint/OneDrive (Phase 1):

1. **Lire la spécification complète**
   - Fichier: `SHAREPOINT_ONEDRIVE_SCENARIOS_100.md`
   - Identifier les 5 scénarios manquants par ressource

2. **Implémenter scénarios manquants**
   - Code: `/backend/app/providers/microsoft365.py`
   - Ajouter méthodes `scan_*` pour chaque scénario

3. **Tester avec données réelles**
   - Guide: `SHAREPOINT_ONEDRIVE_TESTING_GUIDE.md`
   - Protocole: `MICROSOFT365_TEST_PROTOCOL.md`

4. **Valider et ajuster**
   - Comparer résultats attendus vs obtenus
   - Ajuster seuils et paramètres

---

### Pour Démarrer Phase 2 (Licenses & Users):

1. **Lire MS365.md section Licensing**
   - Comprendre les 10 scénarios licenses
   - Comprendre les 10 scénarios users

2. **Setup tenant M365 test**
   - Créer utilisateurs test (actifs + inactifs)
   - Assigner différentes licences (E3, E5, Business)

3. **Implémenter détection licenses**
   - API: `/subscribedSkus`, `/users?$select=assignedLicenses`
   - Détecter: unassigned, disabled users, never used, etc.

4. **Implémenter détection users inactifs**
   - API: `/users`, `/auditLogs/signIns`
   - Détecter: never signed in, inactive 180+d, etc.

---

## 🔗 Ressources Utiles

### Documentation Microsoft:
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview)
- [Graph API Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [App Registration Guide](https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [Microsoft Graph SDKs](https://learn.microsoft.com/en-us/graph/sdks/sdks-overview)

### CloudWaste Documentation:
- [Backend Providers](../../backend/app/providers/) - Code providers existants
- [Azure Resources](../azure/) - Ressources Azure (infrastructure)
- [GCP Resources](../gcp/) - Ressources GCP

---

## 📞 Support

Questions sur l'implémentation Microsoft 365 ?
- 📧 Email: team@cloudwaste.com
- 💬 Slack: #ms365-implementation
- 📝 Issues: GitHub Issues

---

## ⚠️ Notes Importantes

### Différences MS365 vs Azure (rappel):

1. **Credentials séparés:**
   - MS365: App Registration (Graph API)
   - Azure: Service Principal (ARM API)

2. **Pricing différent:**
   - MS365: Per-user subscription ($6-57/mois)
   - Azure: Pay-as-you-go (usage-based)

3. **Gaspillage différent:**
   - MS365: Licences inutilisées, storage abandonné
   - Azure: VMs stopped, disques unattached

4. **APIs différentes:**
   - MS365: `graph.microsoft.com`
   - Azure: `management.azure.com`

💡 **Ne pas confondre les deux !** Si tu veux scanner Azure (VMs, disks), voir `/docs/azure/` à la place.

---

**Dernière mise à jour:** 2 novembre 2025
**Status:** 🚧 Phase 1 en cours (SharePoint/OneDrive 10/20 scenarios)
**Version:** 2.0 (ajout listing complet 14 ressources)
