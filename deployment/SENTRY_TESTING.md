# 🧪 Guide de Test Sentry en Production

Ce guide explique comment tester en profondeur l'intégration Sentry pour le backend (FastAPI) et le frontend (Next.js).

---

## 📋 Table des matières

1. [Vérification de la configuration](#1-vérification-de-la-configuration)
2. [Test du Backend (FastAPI)](#2-test-du-backend-fastapi)
3. [Test du Frontend (Next.js)](#3-test-du-frontend-nextjs)
4. [Validation dans le Dashboard Sentry](#4-validation-dans-le-dashboard-sentry)
5. [Tests avancés](#5-tests-avancés)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Vérification de la Configuration

### Backend (FastAPI)

Depuis le VPS, vérifier que les variables Sentry sont bien configurées :

```bash
ssh administrator@155.117.43.17
docker exec cloudwaste_backend env | grep SENTRY
```

**Résultat attendu :**
```bash
SENTRY_DSN=https://1e103a6f257e3a1c7f286efb9fa42c75@o4510350814085121.ingest.de.sentry.io/4510350841086032
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

### Frontend (Next.js)

```bash
docker exec cloudwaste_frontend env | grep NEXT_PUBLIC_SENTRY
```

**Résultat attendu :**
```bash
NEXT_PUBLIC_SENTRY_DSN=https://442a2365755e0b972138478b85fdb5a7@o4510350814085121.ingest.de.sentry.io/4510350846984272
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
```

### Vérifier l'initialisation de Sentry

Consulter les logs de démarrage :

```bash
# Backend
docker logs cloudwaste_backend --tail 50 | grep -i sentry

# Frontend
docker logs cloudwaste_frontend --tail 50 | grep -i sentry
```

---

## 2. Test du Backend (FastAPI)

### Méthode 1 : Endpoint de test Sentry (Recommandé)

**⚠️ Prérequis :** Mode DEBUG activé + compte superuser

```bash
# 1. Obtenir un token d'authentification
ACCESS_TOKEN=$(curl -s -X POST "https://cutcosts.tech/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_EMAIL&password=YOUR_PASSWORD" | jq -r '.access_token')

# 2. Tester l'exception capturée (retourne HTTP 200)
curl -X GET "https://cutcosts.tech/api/v1/test/sentry-test" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Résultat attendu :**
```json
{
  "status": "success",
  "message": "Test exception sent to Sentry successfully",
  "sentry_dsn_configured": true,
  "sentry_environment": "production",
  "user_context": {
    "id": "uuid",
    "email": "your-email@example.com"
  },
  "instructions": "Check your Sentry dashboard at https://sentry.io for the captured exception"
}
```

**Résultat dans Sentry :**
- **Issue Title :** `ValueError: 🧪 Test Sentry Exception - This is a controlled test error to verify Sentry integration`
- **Tags :**
  - `test_type: manual_sentry_test`
  - `environment: production`
- **User Context :** Email + User ID
- **Breadcrumbs :** "Sentry test endpoint called"

### Méthode 2 : Test d'erreur non capturée (HTTP 500)

```bash
curl -X GET "https://cutcosts.tech/api/v1/test/sentry-test-division-by-zero" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Résultat attendu :** HTTP 500 Internal Server Error

**Résultat dans Sentry :**
- **Issue Title :** `ZeroDivisionError: division by zero`
- **Stack Trace :** Trace complète avec ligne de code
- **Environment :** production

### Méthode 3 : Déclencher une vraie erreur (Scan invalide)

Simuler une erreur réelle en tentant un scan avec des credentials AWS invalides :

```bash
# Via l'interface web : Dashboard → Accounts → Add Account
# Saisir des credentials AWS invalides et lancer un scan
```

**Résultat dans Sentry :**
- **Issue Title :** `botocore.exceptions.ClientError` ou `AWSValidationError`
- **Tags :** `provider: aws`, `operation: scan`
- **Contexte :** Region, account_id, scan_id

---

## 3. Test du Frontend (Next.js)

### Méthode 1 : Console JavaScript (Recommandé)

1. Ouvrir le frontend : `https://cutcosts.tech`
2. Ouvrir la console JavaScript (F12 → Console)
3. Exécuter :

```javascript
// Test 1 : Exception simple
Sentry.captureException(new Error("🧪 Test Frontend Sentry Error"));

// Test 2 : Message personnalisé
Sentry.captureMessage("Test Sentry Message from Frontend", "info");

// Test 3 : Breadcrumb + Exception
Sentry.addBreadcrumb({
  category: "test",
  message: "User clicked test button",
  level: "info",
});
Sentry.captureException(new Error("Test error after breadcrumb"));
```

**Résultat attendu dans la console :**
```
[Sentry] Event sent to Sentry: {"event_id":"..."}
```

**Résultat dans Sentry :**
- **Issue Title :** `Error: 🧪 Test Frontend Sentry Error`
- **Source :** `@sentry/browser` ou `@sentry/nextjs`
- **Tags :** `environment: production`

### Méthode 2 : Déclencher une erreur React

Provoquer une erreur dans l'interface :

1. Aller sur une page du dashboard
2. Modifier l'état pour casser un composant (ex: accéder à une propriété `undefined`)

**Exemple de test :**
```typescript
// Dans un composant React
throw new Error("🧪 Test React Component Error");
```

**Résultat dans Sentry :**
- **Issue Title :** `Error: 🧪 Test React Component Error`
- **Component Stack :** Hiérarchie complète des composants React
- **Source Maps :** Code source original (non minifié)

### Méthode 3 : Test de navigation (Session Replay)

Si Session Replay est activé, tester :

1. Naviguer sur plusieurs pages
2. Déclencher une erreur (via console JavaScript)
3. Vérifier dans Sentry → Issue → Session Replay

**Résultat attendu :** Vidéo de la session utilisateur avant l'erreur.

---

## 4. Validation dans le Dashboard Sentry

### Accès au Dashboard Sentry

1. Aller sur : `https://sentry.io`
2. Se connecter avec votre compte Sentry
3. Sélectionner l'organisation : `jerome-laval-x3`
4. Projets :
   - **Backend :** `cloudwaste` (Python)
   - **Frontend :** `cloudwaste-frontend` (JavaScript)

### Vérifier les événements capturés

**Issues → All Issues**
- Filtrer par `environment:production`
- Vérifier que les erreurs de test apparaissent (délai 1-5 secondes)

### Informations à vérifier

Pour chaque issue, valider :

1. **Event Details :**
   - ✅ Exception type correct (ValueError, ZeroDivisionError, Error)
   - ✅ Stack trace complet avec numéros de ligne
   - ✅ Message d'erreur correct

2. **Tags :**
   - ✅ `environment: production`
   - ✅ `release: <git_commit_sha>` (si configuré)
   - ✅ Tags personnalisés (ex: `test_type: manual_sentry_test`)

3. **User Context :**
   - ✅ User ID présent
   - ✅ Email utilisateur
   - ✅ Username

4. **Breadcrumbs :**
   - ✅ Actions utilisateur avant l'erreur
   - ✅ Logs d'événements

5. **Additional Data :**
   - ✅ Request URL
   - ✅ HTTP method
   - ✅ Headers

### Dashboard Metrics

**Performance → Overview**
- Vérifier que les transactions sont trackées
- Sample rate : 10% (SENTRY_TRACES_SAMPLE_RATE=0.1)

**Profiling → Overview**
- Vérifier les profils de performance (backend uniquement)
- Sample rate : 10% (SENTRY_PROFILES_SAMPLE_RATE=0.1)

---

## 5. Tests Avancés

### Test 1 : Performance Monitoring (Backend)

Déclencher un endpoint lent :

```bash
curl -X GET "https://cutcosts.tech/api/v1/scans" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Vérifier dans Sentry :**
- Performance → Transactions
- Transaction : `GET /api/v1/scans`
- Durée, nombre d'appels, P95, etc.

### Test 2 : Profiling (Backend)

Lancer un scan complet (opération lourde) :

```bash
curl -X POST "https://cutcosts.tech/api/v1/scans/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"YOUR_ACCOUNT_UUID"}'
```

**Vérifier dans Sentry :**
- Profiling → Profiles
- Fonction : `scan_all_regions()` ou `scan_unattached_volumes()`
- Temps CPU, call graph

### Test 3 : Frontend Source Maps

Forcer une erreur dans un composant minifié :

```javascript
// Dans la console du navigateur
throw new Error("Test Source Maps");
```

**Vérifier dans Sentry :**
- Stack trace montre le code source original (pas minifié)
- Fichier : `components/dashboard/ResourcesList.tsx:45` (exemple)

### Test 4 : Contexte utilisateur enrichi

Tester avec un utilisateur connecté réel :

```javascript
// Dans la console
Sentry.setUser({
  id: "test-user-id",
  email: "test@example.com",
  username: "Test User",
  ip_address: "127.0.0.1",
});

Sentry.captureException(new Error("Test with enriched user context"));
```

**Vérifier dans Sentry :**
- Issue → User → Toutes les informations présentes

### Test 5 : Tags personnalisés

```javascript
// Backend (dans un endpoint)
sentry_sdk.set_tag("cloud_provider", "aws")
sentry_sdk.set_tag("region", "eu-west-1")
sentry_sdk.set_tag("scan_type", "full_scan")

# Frontend (dans un composant)
Sentry.setTag("page", "dashboard");
Sentry.setTag("feature", "resource_list");
```

**Vérifier dans Sentry :**
- Issue → Tags → Tags personnalisés présents
- Possibilité de filtrer par tags

---

## 6. Troubleshooting

### Problème 1 : Aucun événement dans Sentry

**Symptômes :**
- Aucune erreur n'apparaît dans le dashboard Sentry
- Console JavaScript : pas de message `[Sentry] Event sent`

**Solutions :**

```bash
# 1. Vérifier les variables d'environnement
docker exec cloudwaste_backend env | grep SENTRY_DSN
docker exec cloudwaste_frontend env | grep NEXT_PUBLIC_SENTRY_DSN

# 2. Vérifier que Sentry SDK est installé
docker exec cloudwaste_backend pip list | grep sentry-sdk
docker exec cloudwaste_frontend npm list | grep @sentry/nextjs

# 3. Vérifier les logs de démarrage
docker logs cloudwaste_backend --tail 100 | grep -i sentry
docker logs cloudwaste_frontend --tail 100 | grep -i sentry

# 4. Tester la connexion Sentry manuellement
docker exec cloudwaste_backend python -c "import sentry_sdk; sentry_sdk.init('YOUR_SENTRY_DSN'); sentry_sdk.capture_message('Test'); print('OK')"
```

### Problème 2 : Erreurs non capturées

**Symptômes :**
- Erreurs visibles dans les logs Docker
- Mais pas dans Sentry

**Solutions :**

```python
# Backend : Vérifier que l'exception n'est pas "swallowed"
try:
    risky_operation()
except Exception as e:
    # ❌ MAUVAIS - Exception perdue
    pass

try:
    risky_operation()
except Exception as e:
    # ✅ BON - Exception capturée par Sentry
    sentry_sdk.capture_exception(e)
    raise  # ou handle proprement
```

```javascript
// Frontend : Utiliser ErrorBoundary
import * as Sentry from "@sentry/nextjs";

class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    Sentry.captureException(error, { contexts: { react: errorInfo } });
  }

  render() {
    return this.props.children;
  }
}
```

### Problème 3 : Source Maps manquantes (Frontend)

**Symptômes :**
- Stack traces montrent du code minifié
- Numéros de ligne incorrects

**Solutions :**

```bash
# 1. Vérifier que les source maps sont générées
ls frontend/.next/static/chunks/*.js.map

# 2. Vérifier la configuration Sentry dans next.config.js
cat frontend/next.config.js | grep -A 10 "sentry"

# 3. Vérifier l'upload des source maps
docker logs cloudwaste_frontend --tail 200 | grep "Sentry"
```

### Problème 4 : Trop d'événements (Quota dépassé)

**Symptômes :**
- Email Sentry : "Quota exceeded"
- Événements plus anciens supprimés

**Solutions :**

```bash
# Réduire le sample rate dans .env.prod
SENTRY_TRACES_SAMPLE_RATE=0.05  # 5% au lieu de 10%
SENTRY_PROFILES_SAMPLE_RATE=0.05

# Redémarrer les conteneurs
docker compose -f deployment/docker-compose.prod.yml restart backend frontend
```

### Problème 5 : Environnement incorrect

**Symptômes :**
- Erreurs taggées "development" au lieu de "production"

**Solutions :**

```bash
# Vérifier APP_ENV
docker exec cloudwaste_backend env | grep APP_ENV
# Devrait être : APP_ENV=production

# Vérifier SENTRY_ENVIRONMENT
docker exec cloudwaste_backend env | grep SENTRY_ENVIRONMENT
# Devrait être : SENTRY_ENVIRONMENT=production

# Si incorrect, corriger dans .env.prod et redémarrer
```

---

## Checklist de Test Complet

- [ ] **Backend - Configuration vérifiée**
  - [ ] Variables d'environnement présentes
  - [ ] Sentry SDK installé
  - [ ] Logs de démarrage OK

- [ ] **Backend - Tests fonctionnels**
  - [ ] Test endpoint `/api/v1/test/sentry-test` → HTTP 200
  - [ ] Exception capturée visible dans Sentry
  - [ ] User context présent
  - [ ] Tags personnalisés présents
  - [ ] Test ZeroDivisionError → HTTP 500 → Visible dans Sentry

- [ ] **Frontend - Configuration vérifiée**
  - [ ] Variables d'environnement présentes
  - [ ] Sentry SDK installé
  - [ ] Console ne montre pas d'erreur Sentry

- [ ] **Frontend - Tests fonctionnels**
  - [ ] `Sentry.captureException()` depuis console → Visible dans Sentry
  - [ ] `Sentry.captureMessage()` depuis console → Visible dans Sentry
  - [ ] Erreur React → Capturée par ErrorBoundary → Visible dans Sentry
  - [ ] Source maps fonctionnent (code non minifié dans stack trace)

- [ ] **Dashboard Sentry - Validation**
  - [ ] Issues backend visibles (projet Python)
  - [ ] Issues frontend visibles (projet JavaScript)
  - [ ] Environnement correct : `production`
  - [ ] User context enrichi
  - [ ] Breadcrumbs présents
  - [ ] Performance tracking actif (10% sample)
  - [ ] Profiling actif (10% sample)

- [ ] **Tests avancés**
  - [ ] Performance monitoring (transactions trackées)
  - [ ] Profiling CPU (backend uniquement)
  - [ ] Tags personnalisés fonctionnent
  - [ ] Contexte enrichi fonctionne

---

## Résumé des Endpoints de Test

| Endpoint | Méthode | Authentification | Résultat |
|----------|---------|------------------|----------|
| `/api/v1/test/sentry-test` | GET | Superuser | HTTP 200 + Exception capturée |
| `/api/v1/test/sentry-test-division-by-zero` | GET | Superuser | HTTP 500 + Exception non capturée |
| Console JS : `Sentry.captureException()` | - | - | Exception frontend |
| Console JS : `Sentry.captureMessage()` | - | - | Message custom |

---

## Ressources Sentry

- **Dashboard Backend :** https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste/
- **Dashboard Frontend :** https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste-frontend/
- **Documentation Sentry Python :** https://docs.sentry.io/platforms/python/
- **Documentation Sentry Next.js :** https://docs.sentry.io/platforms/javascript/guides/nextjs/

---

## Support

En cas de problème persistant :
1. Vérifier les logs Docker : `docker logs cloudwaste_backend --tail 200`
2. Vérifier la configuration : `deployment/sync-sentry-env.sh --local`
3. Consulter la documentation Sentry

---

**📌 Note importante :** Les endpoints `/api/v1/test/sentry-*` ne sont accessibles qu'avec :
- `DEBUG=True` dans `.env.prod`
- Compte utilisateur avec `is_superuser=True`

En production finale, désactiver `DEBUG=False` pour sécuriser ces endpoints.
