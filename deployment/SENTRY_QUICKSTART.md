# 🚀 Sentry - Guide de Test Rapide

Guide ultra-simplifié pour tester Sentry en production en **3 étapes**.

---

## ⚡ Test Backend (2 minutes)

### Étape 1 : Exécuter le script de test automatisé

```bash
cd /opt/cloudwaste
bash deployment/test-sentry.sh
```

**Résultat attendu :**
```
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║         ✅ TESTS BACKEND SENTRY TERMINÉS                       ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

📊 Résumé des tests:
   ✅ Authentification réussie
   ✅ Statut Sentry vérifié
   ✅ Message de test envoyé à Sentry
   ✅ Erreur de test déclenchée (ZeroDivisionError)
```

### Étape 2 : Vérifier dans Sentry

1. Aller sur : https://sentry.io
2. Organisation : **jerome-laval-x3**
3. Projet : **cloudwaste** (Backend)
4. **Issues** → Tu devrais voir :
   - ✅ Message : "✅ Sentry test message from CloudWaste"
   - ✅ Erreur : "ZeroDivisionError: 🚨 TEST ERROR: Sentry integration test"
   - ✅ User context : Ton email + User ID
   - ✅ Tags : `environment=production`, `user_triggered=true`

**Délai :** Les événements apparaissent en **10-30 secondes**.

---

## 🌐 Test Frontend (1 minute)

### Étape 1 : Ouvrir la console JavaScript

1. Aller sur : **https://cutcosts.tech**
2. Ouvrir la console : **F12** → **Console**

### Étape 2 : Déclencher une erreur de test

Copie-colle dans la console :

```javascript
Sentry.captureException(new Error("🧪 Test Frontend Sentry Error"));
```

**Résultat attendu dans la console :**
```
[Sentry] Event sent to Sentry: {"event_id":"..."}
```

### Étape 3 : Vérifier dans Sentry

1. Aller sur : https://sentry.io
2. Organisation : **jerome-laval-x3**
3. Projet : **cloudwaste-frontend** (JavaScript)
4. **Issues** → Tu devrais voir :
   - ✅ Erreur : "Error: 🧪 Test Frontend Sentry Error"
   - ✅ Tags : `environment=production`
   - ✅ Stack trace complet (avec source maps)

---

## 🔧 Résolution de Problèmes

### Problème 1 : Script échoue avec "Not authenticated"

**Solution :**
```bash
# Vérifier que DEBUG=True
docker exec cloudwaste_backend env | grep DEBUG

# Si DEBUG=False, activer :
cd /opt/cloudwaste
bash deployment/enable-sentry-testing.sh
```

### Problème 2 : Variables frontend vides

**Solution :**
```bash
# Vérifier les variables
docker exec cloudwaste_frontend env | grep NEXT_PUBLIC_SENTRY

# Si vides, rebuild le frontend :
cd /opt/cloudwaste
git pull origin master
docker compose -f deployment/docker-compose.prod.yml up -d --build frontend
sleep 120  # Attendre 2 minutes
```

### Problème 3 : Aucun événement dans Sentry

**Solution :**
```bash
# Vérifier les logs backend
docker logs cloudwaste_backend --tail 50 | grep -i sentry

# Devrait afficher :
# INFO:app.main:✅ Sentry initialized (environment: production)
```

---

## 📋 Checklist Complète

- [ ] **Backend Test** - Script `test-sentry.sh` exécuté avec succès
- [ ] **Backend Sentry** - Message et erreur visibles dans dashboard
- [ ] **Frontend Test** - Console JavaScript affiche confirmation Sentry
- [ ] **Frontend Sentry** - Erreur visible dans dashboard (projet frontend)
- [ ] **User Context** - Email et User ID présents dans les issues backend
- [ ] **Tags** - `environment=production` présent partout
- [ ] **Désactiver DEBUG** - `bash deployment/disable-sentry-testing.sh`

---

## 🎯 URLs Importantes

| Service | URL |
|---------|-----|
| Dashboard Sentry | https://sentry.io |
| Backend Project | https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste/ |
| Frontend Project | https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste-frontend/ |
| Application | https://cutcosts.tech |
| API Health Check | https://cutcosts.tech/api/v1/health |

---

## 🔐 Endpoints API de Test

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/test/sentry/status` | Vérifier statut Sentry |
| POST | `/api/v1/test/sentry/message` | Envoyer message de test |
| POST | `/api/v1/test/sentry/error` | Déclencher erreur de test (HTTP 500) |

⚠️ **Note:** Ces endpoints nécessitent `DEBUG=True` et authentification.

---

## 📚 Documentation Complète

Pour un guide détaillé avec troubleshooting avancé :
- **Guide complet** : `deployment/SENTRY_TESTING.md`
- **Scripts disponibles** :
  - `deployment/test-sentry.sh` - Test automatisé
  - `deployment/enable-sentry-testing.sh` - Activer mode DEBUG
  - `deployment/disable-sentry-testing.sh` - Désactiver mode DEBUG

---

**✅ Une fois les tests validés, n'oublie pas de désactiver DEBUG mode :**

```bash
bash deployment/disable-sentry-testing.sh
```
