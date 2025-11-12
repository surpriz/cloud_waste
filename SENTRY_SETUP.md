# 🚨 Sentry Error Tracking - Guide de Configuration

Ce guide vous accompagne dans la configuration de **Sentry** pour CloudWaste, un outil d'error tracking et de performance monitoring essentiel pour la production.

## 📋 Table des matières

1. [Qu'est-ce que Sentry ?](#quest-ce-que-sentry-)
2. [Configuration (30 minutes)](#configuration-30-minutes)
3. [Tests et validation](#tests-et-validation)
4. [Déploiement en production](#déploiement-en-production)
5. [Utilisation quotidienne](#utilisation-quotidienne)
6. [Dépannage](#dépannage)

---

## Qu'est-ce que Sentry ?

**Sentry** est une plateforme d'error tracking qui capture automatiquement toutes les erreurs de votre application et vous envoie des alertes en temps réel.

### Avant Sentry (❌)
```
User: "J'ai une erreur 500 quand je lance un scan"
Vous: "Je ne vois rien dans les logs... Pouvez-vous me donner plus de détails ?"
User: "Je ne sais pas, ça ne marche pas"
Vous: 😩
```

### Avec Sentry (✅)
```
Email: "🚨 New Issue: botocore.exceptions.ClientError in scan_cloud_account"
Dashboard Sentry:
  - Stack trace complète
  - User affecté: jerome0laval@gmail.com
  - Account ID: 852815611543
  - Region: eu-west-1
  - Error: InvalidClientTokenId (credentials AWS invalides)

Vous: "Ah, ses credentials AWS ont expiré"
Fix en 5 minutes ✅
```

---

## Configuration (30 minutes)

### Étape 1: Créer un compte Sentry (5 min)

1. **Aller sur** https://sentry.io/signup/
2. **Créer un compte gratuit**
   - Email: jerome0laval@gmail.com
   - Organisation: CloudWaste (ou votre nom)
3. **Confirmer votre email**

**Free Tier Sentry:**
- ✅ 5,000 errors/mois
- ✅ 10,000 performance transactions/mois
- ✅ 30 jours de rétention
- ✅ Illimité users/projets

---

### Étape 2: Créer les projets Sentry (5 min)

Créez **2 projets** (backend + frontend) :

#### Projet 1: Backend (Python/FastAPI)

1. Dans le dashboard Sentry → **Create Project**
2. **Platform:** Python
3. **Project name:** `cloudwaste-backend`
4. **Alert me on every new issue:** ✅ Coché
5. Copier le **DSN** affiché (exemple: `https://abc123@o123456.ingest.sentry.io/456789`)

#### Projet 2: Frontend (Next.js)

1. **Create Project** → **Platform:** Next.js
2. **Project name:** `cloudwaste-frontend`
3. **Alert me on every new issue:** ✅ Coché
4. Copier le **DSN**

---

### Étape 3: Configuration Backend (10 min)

#### 3.1 Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

✅ Sentry SDK déjà ajouté dans `requirements.txt`

#### 3.2 Configurer les variables d'environnement

Éditer `backend/.env` :

```bash
# Sentry Error Tracking
SENTRY_DSN=https://YOUR_BACKEND_DSN_HERE@o123456.ingest.sentry.io/456789
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

**Remplacez** `YOUR_BACKEND_DSN_HERE` par le DSN du projet backend copié à l'étape 2.

#### 3.3 Redémarrer le backend

```bash
docker-compose restart backend
```

Vérifier les logs :

```bash
docker logs cloudwaste_backend --tail 20
```

Vous devriez voir:
```
✅ Sentry initialized (environment: development)
```

---

### Étape 4: Configuration Frontend (10 min)

#### 4.1 Installer les dépendances

```bash
cd frontend
npm install
```

✅ `@sentry/nextjs` déjà ajouté dans `package.json`

#### 4.2 Configurer les variables d'environnement

Éditer `frontend/.env.local` :

```bash
# Sentry Error Tracking
NEXT_PUBLIC_SENTRY_DSN=https://YOUR_FRONTEND_DSN_HERE@o123456.ingest.sentry.io/789012
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development

# Optionnel: Pour upload de source maps en production
SENTRY_ORG=cloudwaste
SENTRY_PROJECT=cloudwaste-frontend
SENTRY_AUTH_TOKEN=  # Obtenir dans sentry.io → Settings → Auth Tokens
```

**Remplacez** `YOUR_FRONTEND_DSN_HERE` par le DSN du projet frontend copié à l'étape 2.

#### 4.3 Architecture Frontend Sentry

CloudWaste utilise une architecture **SentryProvider** pour initialiser Sentry côté client :

- **`SentryProvider.tsx`** : Composant React qui initialise Sentry au chargement de la page
- **`instrumentation.ts`** : Initialise Sentry pour le server-side rendering (Node.js + Edge runtime)
- **`next.config.js`** : Plugin webpack pour upload automatique des source maps en production

Cette approche garantit que Sentry s'initialise correctement sans conflits "Multiple instances".

#### 4.4 Rebuild et redémarrer le frontend

```bash
docker-compose down frontend
docker-compose build frontend
docker-compose up -d frontend
```

---

## Tests et validation

### Test 1: Backend - Vérifier la configuration

```bash
curl -X GET "http://localhost:8000/api/v1/test/sentry/status" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Réponse attendue:**
```json
{
  "status": "success",
  "message": "Sentry is configured and enabled (environment: development)",
  "sentry_enabled": true,
  "sentry_environment": "development"
}
```

---

### Test 2: Backend - Déclencher une erreur test

```bash
curl -X POST "http://localhost:8000/api/v1/test/sentry/error" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Résultat attendu:**
- L'API renvoie une erreur 500 (normal)
- **Allez sur sentry.io → cloudwaste-backend**
- Vous devriez voir une nouvelle erreur: `ZeroDivisionError: 🚨 TEST ERROR`

**Dashboard Sentry vous montre:**
- Stack trace complète
- User email
- Context: `test_context` avec `"purpose": "Sentry integration test"`
- Breadcrumbs (actions avant l'erreur)

---

### Test 3: Frontend - Déclencher une erreur test

1. **Connectez-vous à** http://localhost:3000
2. **Ouvrir la console développeur** (F12)
3. **Vérifier que Sentry est initialisé** - vous devriez voir :
   ```
   🔍 [SentryProvider] Initialisation Sentry...
   ✅ [SentryProvider] Sentry initialisé avec succès !
   ✅ [SentryProvider] window.Sentry disponible pour tests console
   ```
4. **Exécuter ce code dans la console:**

```javascript
window.Sentry.captureException(new Error("🚨 TEST ERROR from browser console"));
```

**Résultat attendu:**
- Console affiche : `🔍 [Sentry] Envoi événement: ...`
- **Allez sur sentry.io → cloudwaste-frontend**
- Vous devriez voir: `Error: 🚨 TEST ERROR from browser console`

---

### Test 4: Backend - Envoyer un message test

```bash
curl -X POST "http://localhost:8000/api/v1/test/sentry/message" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Résultat attendu:**
- Retourne: `{"status":"success","message":"Test message sent to Sentry"}`
- **Dans Sentry:** Nouveau message `✅ Sentry test message from CloudWaste`
- **Level:** Info (pas une erreur, juste un message)

---

## Déploiement en production

### Backend (production)

Éditer `backend/.env.production` :

```bash
# Sentry (Production)
SENTRY_DSN=https://YOUR_BACKEND_DSN_HERE@o123456.ingest.sentry.io/456789
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% des transactions (économise quota)
SENTRY_PROFILES_SAMPLE_RATE=0.1

# IMPORTANT: Désactiver debug en production
DEBUG=False
```

### Frontend (production)

Éditer `frontend/.env.production` :

```bash
# Sentry (Production)
NEXT_PUBLIC_SENTRY_DSN=https://YOUR_FRONTEND_DSN_HERE@o123456.ingest.sentry.io/789012
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production

# Source maps upload (optionnel mais recommandé)
SENTRY_ORG=cloudwaste
SENTRY_PROJECT=cloudwaste-frontend
SENTRY_AUTH_TOKEN=sntrys_YOUR_AUTH_TOKEN  # Créer dans sentry.io → Settings → Auth Tokens
```

**Pour créer le SENTRY_AUTH_TOKEN:**
1. Aller sur https://sentry.io/settings/account/api/auth-tokens/
2. **Create New Token**
3. **Scopes:** `project:read`, `project:releases`, `org:read`
4. Copier le token et l'ajouter dans `.env.production`

---

## Utilisation quotidienne

### Dashboard Sentry

**Aller sur:** https://sentry.io/organizations/YOUR_ORG/issues/

Vous verrez:
- 📊 Graphique des erreurs au fil du temps
- 🔥 Erreurs les plus fréquentes
- 👥 Utilisateurs affectés
- ⏱️ Performance des endpoints API

### Configurer les alertes

**Settings → Alerts → Create Alert Rule:**

1. **When:** An event is seen
2. **If:** Error level is `error` or `fatal`
3. **Then:** Send notification to:
   - ✉️ Email: jerome0laval@gmail.com
   - 💬 Slack (optionnel): #cloudwaste-alerts

### Trier les erreurs

**Dans Sentry Dashboard:**
- **Resolve:** Marquer comme résolue (ne recevrez plus d'alertes pour cette erreur)
- **Ignore:** Ignorer cette erreur (ne sera plus comptée)
- **Assign to:** Assigner à un membre de l'équipe
- **Create Issue:** Créer un ticket GitHub/Jira

---

## Ce que Sentry capture automatiquement

### Backend (FastAPI + Celery)
✅ **Toutes les exceptions** non gérées
✅ **Erreurs dans Celery tasks** (scans)
✅ **Erreurs AWS credentials** (providers)
✅ **Erreurs database** (SQLAlchemy)
✅ **Erreurs Redis** (cache)
✅ **Performance monitoring** (temps de réponse API)

### Frontend (Next.js + React)
✅ **Erreurs React** (render errors, hooks)
✅ **Erreurs API** (fetch failures sauf 401/403)
✅ **Erreurs non gérées** (JavaScript exceptions)
✅ **Performance monitoring** (temps de chargement pages)
✅ **Session Replay** (vidéo de la session avant l'erreur) 🎥

---

## Exemples d'erreurs que Sentry capturera

### Exemple 1: Credentials AWS invalides

**Scénario:** User ajoute un compte AWS avec de mauvaises credentials

**Sentry vous envoie:**
```
🚨 ClientError in validate_credentials (providers/aws.py:232)
Error: InvalidClientTokenId - AWS Access Key ID is invalid

Context:
  - User: jerome0laval@gmail.com
  - Account ID: 852815611543
  - Region: us-east-1

Stack Trace:
  File "providers/aws.py", line 186, in validate_credentials
    response = await sts.get_caller_identity()
  botocore.exceptions.ClientError: InvalidClientTokenId
```

**Vous savez exactement:**
- ✅ Quel utilisateur est affecté
- ✅ Quel compte cloud pose problème
- ✅ Quelle erreur AWS exacte
- ✅ Où dans le code (ligne 186)

**Fix:** Contacter l'utilisateur pour lui demander de vérifier ses credentials.

---

### Exemple 2: Scan qui plante

**Scénario:** Un scan plante à cause d'une région AWS inaccessible

**Sentry vous envoie:**
```
🚨 Exception in _scan_cloud_account_async (workers/tasks.py:591)
Error: EndpointConnectionError - Could not connect to eu-south-2

Context:
  - Scan ID: abc-123
  - Cloud Account: 852815611543
  - Provider: aws
  - Account Name: "Mon compte AWS prod"

Breadcrumbs:
  1. Validating credentials... ✅
  2. Scanning region eu-west-1... ✅
  3. Scanning region eu-south-2... ❌
```

**Vous savez exactement:**
- ✅ Le scan ID
- ✅ La région qui pose problème (eu-south-2)
- ✅ Toutes les étapes avant l'erreur (breadcrumbs)

**Fix:** Exclure cette région des scans futurs.

---

## Dépannage

### Problème: "Sentry DSN not set - Error tracking disabled"

**Solution:**
1. Vérifier que `SENTRY_DSN` est bien défini dans `.env`
2. Redémarrer Docker:
```bash
docker-compose restart backend
```

---

### Problème: Pas d'erreurs dans Sentry dashboard

**Vérifications:**
1. **Le DSN est-il correct ?**
   ```bash
   docker logs cloudwaste_backend | grep Sentry
   ```
   Devrait afficher: `✅ Sentry initialized`

2. **Tester avec endpoint de test:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/test/sentry/error" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Vérifier l'environnement:**
   - Dashboard Sentry → Settings → Filters
   - Assurez-vous que `development` n'est pas filtré

---

### Problème: Trop d'erreurs dans Sentry (quota dépassé)

**Solutions:**

1. **Augmenter le sample rate** (capturer moins d'événements):
```bash
# backend/.env
SENTRY_TRACES_SAMPLE_RATE=0.05  # 5% au lieu de 10%
```

2. **Ignorer certaines erreurs** dans Sentry dashboard:
   - Aller sur l'erreur
   - Cliquer "Ignore"

3. **Filtrer les erreurs non-critiques:**
   - Settings → Inbound Filters
   - Activer: "Filter out known web crawlers"

---

## Ressources

- **Documentation officielle:** https://docs.sentry.io/
- **Dashboard Sentry:** https://sentry.io/
- **Support:** support@sentry.io
- **Status page:** https://status.sentry.io/

---

## Checklist finale

Avant de passer en production, vérifiez:

- [ ] Sentry configuré pour backend (DSN dans `.env.production`)
- [ ] Sentry configuré pour frontend (DSN dans `.env.production`)
- [ ] Test backend réussi (`/api/v1/test/sentry/error`)
- [ ] Test frontend réussi (console.log dans Sentry dashboard)
- [ ] Alertes email configurées
- [ ] Source maps uploadés (frontend production)
- [ ] Sample rate ajusté pour production (10% recommandé)
- [ ] Documentation lue et comprise

---

**🎉 Félicitations ! Sentry est maintenant configuré pour CloudWaste.**

Vous recevrez des alertes instantanées pour toute erreur en production, avec stack traces complètes et contexte utilisateur.

**En cas de problème:** jerome0laval@gmail.com
