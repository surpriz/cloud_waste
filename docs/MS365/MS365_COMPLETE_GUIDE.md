# 📘 Guide Complet - Microsoft 365 Detection (SharePoint + OneDrive)

Guide utilisateur complet pour configurer et utiliser la détection de gaspillage Microsoft 365 dans CloudWaste.

---

## 📖 Table des Matières

1. [Introduction](#introduction)
2. [Prérequis](#prérequis)
3. [Configuration Entra ID](#configuration-entra-id)
4. [Connexion du Compte M365](#connexion-du-compte-m365)
5. [Premier Scan](#premier-scan)
6. [Scénarios de Détection](#scénarios-de-détection)
7. [Interprétation des Résultats](#interprétation-des-résultats)
8. [Troubleshooting](#troubleshooting)

---

## Introduction

Le provider Microsoft 365 de CloudWaste détecte **10 scénarios de gaspillage** dans votre tenant M365 :
- **5 scénarios SharePoint** : Fichiers volumineux inutilisés, duplicata, sites abandonnés, versioning excessif, corbeille ancienne
- **5 scénarios OneDrive** : Fichiers volumineux inutilisés, utilisateurs désactivés, fichiers temporaires, partages excessifs, pièces jointes dupliquées

**Bénéfices :**
- 💰 Réduction des coûts de stockage M365 (économie moyenne : 15-30%)
- 🧹 Nettoyage automatisé des fichiers obsolètes
- 📊 Visibilité sur l'utilisation réelle du stockage
- ⚡ Amélioration des performances SharePoint/OneDrive

---

## Prérequis

### 1. Compte Microsoft 365

Vous avez besoin d'un tenant Microsoft 365 avec :
- **Abonnement actif** : Business Standard/Premium OU Office 365 E3/E5
- **Rôle requis** : Global Administrator (pour créer l'App Registration)
- **Environnement** : Au moins 1 utilisateur actif + 1 site SharePoint

**💡 Essai gratuit disponible :**
Si vous n'avez pas de tenant M365, Microsoft propose un essai gratuit 30 jours :
```
https://www.microsoft.com/en-us/microsoft-365/enterprise/office-365-e3?activetab=pivot:overviewtab
```

### 2. CloudWaste Configuré

- Backend démarré sur `http://localhost:8000` (ou votre URL)
- Frontend accessible sur `http://localhost:3000`
- Compte utilisateur CloudWaste créé

### 3. Navigateur Web

Pour la configuration Entra ID :
- Microsoft Edge, Chrome, Firefox ou Safari
- Accès à Azure Portal (https://portal.azure.com)

---

## Configuration Entra ID

Pour permettre à CloudWaste de scanner votre tenant M365, vous devez créer une **App Registration** (Service Principal) dans Entra ID avec les permissions Microsoft Graph nécessaires.

### Étape 1 : Accéder au Portail Azure

1. Ouvrir **Azure Portal** : https://portal.azure.com
2. Se connecter avec votre compte **Global Administrator** M365
3. Naviguer vers **Entra ID** (anciennement Azure Active Directory)

### Étape 2 : Créer l'App Registration

1. Dans Entra ID, cliquer sur **App registrations** (dans le menu de gauche)
2. Cliquer sur **+ New registration**
3. Remplir le formulaire :
   - **Name** : `CloudWaste-M365-Scanner`
   - **Supported account types** : `Accounts in this organizational directory only (Single tenant)`
   - **Redirect URI** : Laisser vide
4. Cliquer sur **Register**

✅ L'application est créée. Vous êtes redirigé vers la page Overview.

### Étape 3 : Noter les Identifiants (1/3)

Sur la page **Overview** de votre App Registration, **noter ces 2 valeurs** :

```
Application (client) ID : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Directory (tenant) ID   : yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

💡 **Alternative pour Tenant ID** : Vous pouvez aussi utiliser votre domaine M365, ex: `contoso.onmicrosoft.com`

### Étape 4 : Créer un Client Secret (2/3)

1. Dans votre App Registration, cliquer sur **Certificates & secrets** (menu gauche)
2. Onglet **Client secrets** → Cliquer **+ New client secret**
3. Remplir :
   - **Description** : `CloudWaste-Scanner-Secret`
   - **Expires** : `24 months` (recommandé)
4. Cliquer sur **Add**
5. ⚠️ **COPIER IMMÉDIATEMENT** la valeur du secret (colonne "Value")
   - Le secret n'est affiché qu'une seule fois !
   - Si vous fermez la page sans le copier, vous devrez recréer un nouveau secret

```
Client secret value : zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
```

### Étape 5 : Configurer les Permissions API (3/3)

1. Dans votre App Registration, cliquer sur **API permissions** (menu gauche)
2. Cliquer sur **+ Add a permission**
3. Sélectionner **Microsoft Graph**
4. Sélectionner **Application permissions** (pas "Delegated")
5. Rechercher et cocher les 4 permissions suivantes :

   ☑️ **Files.Read.All**
   → Lire tous les fichiers SharePoint et OneDrive

   ☑️ **Sites.Read.All**
   → Lire tous les sites SharePoint

   ☑️ **User.Read.All**
   → Lire les utilisateurs M365 (pour OneDrive)

   ☑️ **Directory.Read.All**
   → Lire le tenant Azure AD (pour info organisation)

6. Cliquer sur **Add permissions**

7. ⚠️ **ÉTAPE CRITIQUE** : Accorder le consentement administrateur
   - Cliquer sur le bouton **"Grant admin consent for [Organization]"** (en haut de la liste)
   - Confirmer "Yes" dans la popup
   - Vérifier que toutes les permissions affichent un **statut vert** "Granted for [Organization]"

**❌ Si vous oubliez cette étape, CloudWaste ne pourra PAS accéder à votre tenant !**

### Récapitulatif des Credentials

Vous devriez maintenant avoir **3 valeurs** :

```bash
CLIENT_ID       = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   (Application ID)
TENANT_ID       = yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy   (Directory ID ou contoso.onmicrosoft.com)
CLIENT_SECRET   = zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz   (Secret value)
```

✅ **Gardez ces credentials en sécurité** - CloudWaste les chiffrera avant stockage en base.

---

## Connexion du Compte M365

### Via l'Interface CloudWaste (Frontend)

1. **Accéder à la page Cloud Accounts**
   ```
   http://localhost:3000/dashboard/accounts
   ```

2. **Cliquer sur "Add Cloud Account"**

3. **Sélectionner le provider "Microsoft 365"**
   - Une carte verte avec le logo Microsoft 365 devrait apparaître

4. **Remplir le formulaire** avec vos credentials Entra ID :
   ```
   Account Name        : Mon Tenant M365 Principal
   Tenant ID           : contoso.onmicrosoft.com  (ou Directory ID)
   Client ID           : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   Client Secret       : zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
   Description         : Tenant M365 pour CloudWaste detection
   ```

5. **Cliquer sur "Validate Credentials"** (recommandé)
   - CloudWaste va tester la connexion à Microsoft Graph
   - Vous devriez voir : ✅ "Microsoft 365 credentials are valid! Organization: [Nom]"

6. **Cliquer sur "Create Account"**

7. **Vérifier** que votre compte M365 apparaît dans la liste avec :
   - Badge vert "Active"
   - Icône Microsoft 365
   - Nom de votre organisation

### Via l'API CloudWaste (curl)

Si le frontend n'est pas disponible, vous pouvez utiliser l'API directement :

```bash
# 1. Se connecter pour obtenir JWT token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=votre-email@example.com" \
  -d "password=votre-mot-de-passe"

# Réponse : {"access_token": "eyJhbGciOiJIUzI1Ni...", ...}
export JWT_TOKEN="eyJhbGciOiJIUzI1Ni..."

# 2. Créer compte M365
curl -X POST "http://localhost:8000/api/v1/accounts" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "microsoft365",
    "account_name": "Mon Tenant M365",
    "account_identifier": "contoso.onmicrosoft.com",
    "microsoft365_tenant_id": "contoso.onmicrosoft.com",
    "microsoft365_client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "microsoft365_client_secret": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
    "description": "Tenant principal M365"
  }'

# Réponse : {"id": "abc123...", "provider": "microsoft365", ...}
```

---

## Premier Scan

### Via l'Interface CloudWaste

1. **Accéder à la page Cloud Accounts**
   ```
   http://localhost:3000/dashboard/accounts
   ```

2. **Trouver votre compte M365** dans la liste

3. **Cliquer sur "Start Scan"** (bouton à droite du compte)

4. **Confirmer** le scan manuel

5. **Suivre la progression**
   - Status change : `Pending` → `In Progress` → `Completed`
   - Durée estimée :
     - Petit tenant (<10 sites, <10 users) : 2-5 minutes
     - Moyen tenant (10-50 sites, 10-50 users) : 5-15 minutes
     - Large tenant (50+ sites, 100+ users) : 15-30 minutes

6. **Voir les résultats**
   - Nombre de ressources scannées
   - Gaspillages détectés
   - Coût mensuel estimé en $

### Via l'API CloudWaste

```bash
# 1. Lancer scan manuel
curl -X POST "http://localhost:8000/api/v1/scans/start" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cloud_account_id": "abc123..."}'

# Réponse : {"id": "scan-456...", "status": "pending", ...}
export SCAN_ID="scan-456..."

# 2. Vérifier progression (toutes les 30s)
curl -X GET "http://localhost:8000/api/v1/scans/$SCAN_ID" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 3. Lister les ressources orphelines détectées
curl -X GET "http://localhost:8000/api/v1/resources?cloud_account_id=abc123..." \
  -H "Authorization: Bearer $JWT_TOKEN"
```

---

## Scénarios de Détection

CloudWaste détecte **10 scénarios de gaspillage** dans votre tenant Microsoft 365.

### 📁 SharePoint (5 scénarios)

#### 1. 📦 Fichiers Volumineux Inutilisés
**Détection** : Fichiers >100 MB non consultés depuis 180+ jours

**Exemple :**
```
Fichier     : Presentation-Q4-2023.pptx (750 MB)
Site        : Sales Team Site
Dernier accès : Il y a 210 jours
Coût mensuel : $0.15
Recommandation : Archiver vers Azure Blob Cool tier ou supprimer
```

**Règle personnalisable :**
```json
{
  "large_files_unused": {
    "enabled": true,
    "min_file_size_mb": 100,
    "min_age_days": 180
  }
}
```

#### 2. 🔁 Fichiers Dupliqués
**Détection** : Fichiers identiques (même hash) présents en plusieurs exemplaires

**Exemple :**
```
Fichier     : Contract-2024.pdf
Duplicata   : 4 copies identiques
Taille      : 25 MB × 5 = 125 MB total
Gaspillage  : 100 MB (4 copies à supprimer)
Coût mensuel : $0.02
Recommandation : Conserver 1 seule copie, créer des liens
```

**Règle personnalisable :**
```json
{
  "duplicate_files": {
    "enabled": true
  }
}
```

#### 3. 🏚️ Sites Abandonnés
**Détection** : Sites SharePoint sans activité depuis 90+ jours

**Exemple :**
```
Site        : Project Alpha 2023
Stockage    : 10.5 GB
Inactif depuis : 92 jours
Activité    : 0 vues, 0 modifications
Coût mensuel : $2.10
Recommandation : Archiver vers Azure Blob ou supprimer
```

**Règle personnalisable :**
```json
{
  "sites_abandoned": {
    "enabled": true,
    "min_inactive_days": 90
  }
}
```

#### 4. 📚 Versioning Excessif
**Détection** : Fichiers avec 50+ versions conservées

**Exemple :**
```
Fichier     : Design-Final.psd
Versions    : 85 versions conservées
Taille      : 2.5 GB par version = 212.5 GB total
Versions récentes : 5 (12.5 GB)
Versions anciennes : 80 (200 GB à supprimer)
Coût mensuel : $40.00
Recommandation : Réduire à 10 dernières versions
```

**Règle personnalisable :**
```json
{
  "excessive_versions": {
    "enabled": true,
    "max_versions_threshold": 50
  }
}
```

#### 5. 🗑️ Corbeille Ancienne
**Détection** : Fichiers dans la corbeille depuis 30+ jours

**Exemple :**
```
Corbeille   : Site Marketing Team
Fichiers    : 47 fichiers (total 8.2 GB)
Ancienneté  : 35-90 jours
Coût mensuel : $1.64
Recommandation : Vider la corbeille (auto-suppression après 93 jours)
```

**Règle personnalisable :**
```json
{
  "recycle_bin_old": {
    "enabled": true,
    "max_retention_days": 30
  }
}
```

---

### 💾 OneDrive (5 scénarios)

#### 6. 📦 Fichiers Volumineux Inutilisés
**Détection** : Fichiers >100 MB non consultés depuis 180+ jours (même logique que SharePoint)

**Exemple :**
```
Utilisateur : john.doe@contoso.com
Fichier     : OldProject.zip (2.5 GB)
Dernier accès : Il y a 250 jours
Coût mensuel : $0.50
Recommandation : Archiver ou supprimer
```

#### 7. 👤 Utilisateurs Désactivés
**Détection** : OneDrive d'utilisateurs désactivés depuis 93+ jours

**Exemple :**
```
Utilisateur : jane.smith@contoso.com (désactivé)
OneDrive    : 45 GB
Inactif depuis : 120 jours
Coût mensuel : $9.00
Recommandation : Sauvegarder puis supprimer OneDrive
```

**Règle personnalisable :**
```json
{
  "disabled_users": {
    "enabled": true,
    "retention_days": 93
  }
}
```

#### 8. 🗂️ Fichiers Temporaires Accumulés
**Détection** : Fichiers temporaires (.tmp, ~$, .bak, .swp) datant de 7+ jours

**Exemple :**
```
Utilisateur : bob.jones@contoso.com
Fichiers    : 23 fichiers temporaires (total 1.2 GB)
Types       : .tmp, ~$Document.docx, backup.bak
Ancienneté  : 15-60 jours
Coût mensuel : $0.24
Recommandation : Supprimer automatiquement
```

**Règle personnalisable :**
```json
{
  "temp_files_accumulated": {
    "enabled": true,
    "min_age_days": 7,
    "file_patterns": [".tmp", "~$", ".bak", ".swp"]
  }
}
```

#### 9. 🔗 Partages Excessifs
**Détection** : Fichiers partagés mais non consultés depuis 90+ jours

**Exemple :**
```
Fichier     : Confidential-Report.pdf
Partagé avec : 12 personnes
Dernier accès : Il y a 120 jours
Risque      : Sécurité + stockage inutile
Recommandation : Révoquer les partages
```

#### 10. 📎 Pièces Jointes Dupliquées
**Détection** : Pièces jointes Outlook sauvegardées en doublon dans OneDrive

**Exemple :**
```
Fichier     : Invoice-2024-03.pdf
Duplicata   : 3 copies identiques
Taille      : 5 MB × 3 = 15 MB
Gaspillage  : 10 MB (2 copies à supprimer)
Coût mensuel : $0.002
Recommandation : Supprimer duplicata, conserver 1 seule copie
```

---

## Interprétation des Résultats

### Tableau de Bord Ressources

Dans l'interface CloudWaste → **Resources**, vous verrez :

| Colonne | Description |
|---------|-------------|
| **Resource Type** | Type de gaspillage détecté (ex: `sharepoint_large_files_unused`) |
| **Resource Name** | Nom du fichier/site concerné |
| **Cloud Account** | Votre tenant M365 |
| **Region** | `global` (M365 est mondial) |
| **Monthly Cost** | Coût mensuel estimé en $ si non supprimé |
| **Status** | `Active` / `Ignored` / `Marked for deletion` |
| **Actions** | Ignorer, Marquer pour suppression, Voir détails |

### Niveaux de Confiance

Chaque ressource orpheline a un **niveau de confiance** :

- 🔴 **CRITICAL (90+ jours)** : Très forte probabilité de gaspillage
- 🟠 **HIGH (30-90 jours)** : Forte probabilité
- 🟡 **MEDIUM (7-30 jours)** : Probabilité moyenne
- 🟢 **LOW (<7 jours)** : Faible probabilité (vérifier avant suppression)

### Actions Recommandées

Pour chaque ressource détectée :

1. **Consulter les métadonnées** (cliquer sur la ligne)
   - Site/Utilisateur concerné
   - Date dernier accès
   - Taille fichier
   - Raison détection
   - Recommandation

2. **Vérifier manuellement** (pour fichiers critiques)
   - Ouvrir SharePoint/OneDrive
   - Vérifier avec l'utilisateur propriétaire

3. **Choisir action** :
   - **Ignorer** : Fichier légitime, ne plus détecter
   - **Marquer pour suppression** : Planifier nettoyage
   - **Supprimer immédiatement** : Via SharePoint/OneDrive (action manuelle)

### Coûts Estimés

CloudWaste calcule les coûts basés sur les **tarifs Microsoft 365 standard** :

| Service | Coût par GB/mois |
|---------|------------------|
| SharePoint Online | $0.20 / GB / mois |
| OneDrive for Business | $0.20 / GB / mois |

**💡 Note** : Si vous avez un plan illimité M365, les coûts représentent le gaspillage de quota utilisateur.

**Exemple de Calcul** :
```
Fichier : 2.5 GB inutilisé
Coût mensuel = 2.5 GB × $0.20 = $0.50/mois
Coût annuel = $0.50 × 12 = $6.00/an
```

---

## Troubleshooting

### Erreur : "Insufficient privileges to complete the operation"

**Cause** : L'admin consent n'a pas été accordé pour les permissions API.

**Solution** :
1. Retourner dans Azure Portal → Entra ID → App registrations
2. Ouvrir votre CloudWaste-M365-Scanner
3. API permissions → Cliquer "Grant admin consent for [Organization]"
4. Vérifier que toutes les permissions sont "Granted" (vert)
5. Relancer le scan CloudWaste

---

### Erreur : "Invalid client secret"

**Cause** : Le client secret a expiré ou est incorrect.

**Solution** :
1. Vérifier la date d'expiration du secret (Certificates & secrets)
2. Si expiré : Créer un nouveau client secret
3. Mettre à jour le compte M365 dans CloudWaste avec le nouveau secret
4. Relancer le scan

---

### Scan Status = "Failed"

**Cause** : Erreur pendant l'exécution du scan (credentials, permissions, Graph API, etc.).

**Solution** :
1. Vérifier les logs Celery :
   ```bash
   docker-compose logs celery_worker | grep -i error
   ```
2. Erreurs courantes :
   - `401 Unauthorized` → Vérifier client_id/client_secret
   - `403 Forbidden` → Vérifier admin consent
   - `404 Not Found` → Vérifier tenant_id
   - `429 Too Many Requests` → Graph API rate limiting, attendre 30 min

---

### Aucune Ressource Détectée

**Cause 1 (Normal)** : Votre tenant M365 est bien optimisé, aucun gaspillage !

**Cause 2** : Les seuils de détection sont trop élevés.

**Solution** :
- Ajuster les règles de détection dans Settings :
  ```
  http://localhost:3000/dashboard/settings
  ```
- Réduire les seuils (ex: `min_age_days` de 180 à 30)
- Relancer un scan

**Cause 3** : Permissions insuffisantes.

**Solution** : Vérifier que toutes les permissions API sont accordées (voir section Configuration Entra ID)

---

### Performance : Scan Très Lent

**Cause** : Large tenant avec beaucoup de sites/utilisateurs + rate limiting Microsoft Graph API.

**Optimisations** :
1. **Rate Limiting** : Microsoft Graph limite à ~1200 requêtes/minute
   - CloudWaste respecte ces limites automatiquement
   - Temps moyen : ~5-10 secondes par site SharePoint
2. **Scan Incrémental** : Activer scheduled scans (1x/jour la nuit)
3. **Filtrage** : Exclure certains sites si nécessaire (feature à venir)

---

### Erreur : "The user or administrator has not consented to use the application"

**Cause** : Admin consent manquant.

**Solution** : Voir section "Insufficient privileges" ci-dessus.

---

## 💬 Support

Pour toute question ou problème :

1. **Documentation technique** : Consultez `MS365_TECHNICAL_REFERENCE.md`
2. **Logs détaillés** : `docker-compose logs -f celery_worker`
3. **Issues GitHub** : Ouvrir un ticket avec logs + configuration

---

## ✅ Checklist Complète

- [ ] Compte Microsoft 365 avec abonnement actif
- [ ] Rôle Global Administrator
- [ ] App Registration créée dans Entra ID
- [ ] Permissions API configurées (Files.Read.All, Sites.Read.All, User.Read.All, Directory.Read.All)
- [ ] Admin consent accordé (statut vert)
- [ ] Client secret créé et copié
- [ ] Compte M365 ajouté dans CloudWaste
- [ ] Credentials validés avec succès
- [ ] Premier scan lancé
- [ ] Résultats consultés
- [ ] Actions planifiées (ignorer/supprimer)

**🎉 Félicitations ! Votre détection Microsoft 365 est opérationnelle !**
