# 🚀 Prochaines Étapes - Déploiement CloudWaste

## ✅ Ce qui a été créé

Tous les fichiers de déploiement ont été générés avec succès :

```
deployment/
├── docker-compose.prod.yml    ✅ Stack Docker optimisée pour production
├── nginx.conf                 ✅ Configuration reverse proxy + SSL
├── setup-server.sh            ✅ Script d'installation initiale du VPS
├── quick-deploy.sh            ✅ Script de déploiement rapide
├── backup-db.sh               ✅ Script de backup automatique
└── README.md                  ✅ Documentation complète

backend/Dockerfile.prod        ✅ Dockerfile multi-stage optimisé
frontend/Dockerfile.prod       ✅ Dockerfile multi-stage optimisé
.env.prod.example              ✅ Template variables d'environnement
```

---

## 📋 Checklist de Déploiement

### 🔧 ÉTAPE 1 : Configuration Locale (5 minutes)

#### 1.1 - Mettre à jour l'URL du dépôt GitHub

```bash
# Ouvrir le fichier
nano deployment/setup-server.sh

# Ligne 37 : Remplacer par votre URL GitHub
GITHUB_REPO="https://github.com/VOTRE_USERNAME/CloudWaste.git"
```

#### 1.2 - Générer une clé SSH pour GitHub Actions

```bash
# Générer la clé
ssh-keygen -t ed25519 -f ~/.ssh/cloudwaste_deploy -N ""

# Afficher la clé publique
cat ~/.ssh/cloudwaste_deploy.pub
```

**➡️ Copier cette clé publique (vous en aurez besoin à l'étape 2.1)**

#### 1.3 - Afficher la clé privée pour GitHub Secrets

```bash
cat ~/.ssh/cloudwaste_deploy
```

**➡️ Copier cette clé privée (vous en aurez besoin à l'étape 1.5)**

#### 1.4 - Commiter les fichiers de déploiement

```bash
git add deployment/ backend/Dockerfile.prod frontend/Dockerfile.prod .env.prod.example
git commit -m "feat: Add production deployment configuration"
git push origin master
```

#### 1.5 - Configurer les Secrets GitHub

1. Aller sur votre dépôt GitHub
2. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
3. Ajouter ces 3 secrets :

| Nom du Secret | Valeur |
|---------------|--------|
| `VPS_HOST` | `155.117.43.17` |
| `VPS_USER` | `administrator` |
| `VPS_SSH_PRIVATE_KEY` | Coller le contenu de `~/.ssh/cloudwaste_deploy` (étape 1.3) |

---

### 🖥️ ÉTAPE 2 : Configuration du VPS (15 minutes)

#### 2.1 - Ajouter la clé SSH publique au VPS

```bash
# Se connecter au VPS
ssh administrator@155.117.43.17

# Créer le dossier .ssh s'il n'existe pas
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Ajouter votre clé publique (de l'étape 1.2)
nano ~/.ssh/authorized_keys
# → Coller la clé publique générée à l'étape 1.2
# → Sauvegarder (Ctrl+O, Enter, Ctrl+X)

# Sécuriser les permissions
chmod 600 ~/.ssh/authorized_keys

# Déconnexion
exit
```

#### 2.2 - Tester la connexion SSH sans mot de passe

```bash
ssh -i ~/.ssh/cloudwaste_deploy administrator@155.117.43.17
```

Si vous êtes connecté sans demande de mot de passe : **✅ Succès !**

#### 2.3 - Transférer le script de setup au VPS

```bash
# Depuis votre machine locale
scp -i ~/.ssh/cloudwaste_deploy deployment/setup-server.sh administrator@155.117.43.17:~/
```

#### 2.4 - Exécuter le script de setup initial

```bash
# Se connecter au VPS
ssh -i ~/.ssh/cloudwaste_deploy administrator@155.117.43.17

# Rendre le script exécutable
chmod +x setup-server.sh

# Exécuter en tant que root
sudo ./setup-server.sh
```

**⚠️ IMPORTANT :** Le script va :
- Installer Docker, Nginx, Certbot
- Configurer le firewall
- Générer les certificats SSL pour **cutcosts.tech** (vérifiez que le DNS pointe bien vers 155.117.43.17)
- Cloner le dépôt dans `/opt/cloudwaste`
- Créer `.env.prod` avec des secrets générés automatiquement

**Durée estimée :** ~10 minutes

#### 2.5 - (Optionnel) Configurer l'email SMTP

```bash
# Sur le VPS
nano /opt/cloudwaste/.env.prod

# Mettre à jour ces lignes avec vos credentials SendGrid (ou autre)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=VOTRE_CLE_API_SENDGRID
EMAILS_FROM_EMAIL=noreply@cutcosts.tech
```

#### 2.6 - Premier déploiement manuel

```bash
# Sur le VPS
cd /opt/cloudwaste
bash deployment/quick-deploy.sh
```

**✅ Si tout se passe bien, après 2-3 minutes :**
- Frontend : https://cutcosts.tech
- API Docs : https://cutcosts.tech/api/docs

---

### 🔄 ÉTAPE 3 : Tester le Déploiement Automatique (2 minutes)

#### 3.1 - Faire un changement et le pousser

```bash
# Sur votre machine locale
echo "# Test deployment" >> README.md
git add README.md
git commit -m "test: Verify GitHub Actions deployment"
git push origin master
```

#### 3.2 - Vérifier GitHub Actions

1. Aller sur votre dépôt GitHub
2. Cliquer sur l'onglet **Actions**
3. Vous devriez voir le workflow "Deploy to Production" en cours d'exécution

**✅ Si le workflow passe au vert : Déploiement automatique fonctionnel !**

---

## 🎯 Résumé des URLs Importantes

| Service | URL |
|---------|-----|
| **Application** | https://cutcosts.tech |
| **API Docs** | https://cutcosts.tech/api/docs |
| **GitHub Actions** | https://github.com/VOTRE_USERNAME/CloudWaste/actions |

---

## 📚 Commandes Utiles

### Sur le VPS :

```bash
# Voir les logs
docker logs -f cloudwaste_backend
docker logs -f cloudwaste_frontend

# Redémarrer un service
docker compose -f deployment/docker-compose.prod.yml restart backend

# Vérifier l'état des containers
docker ps

# Backup de la base de données
bash deployment/backup-db.sh
```

### En local :

```bash
# Déployer manuellement (déclenche GitHub Actions)
git push origin master

# Voir les workflows
gh run list  # Nécessite GitHub CLI
```

---

## 🆘 En Cas de Problème

### Le SSL ne fonctionne pas

**Cause :** DNS ne pointe pas vers le VPS

**Solution :**
1. Vérifier que `cutcosts.tech` pointe vers `155.117.43.17`
2. Attendre la propagation DNS (jusqu'à 48h)
3. Régénérer le certificat : `sudo certbot certonly --standalone -d cutcosts.tech`

### Les containers ne démarrent pas

**Solution :**
```bash
# Sur le VPS
docker logs cloudwaste_backend
docker logs cloudwaste_postgres

# Vérifier .env.prod
cat /opt/cloudwaste/.env.prod
```

### GitHub Actions échoue

**Vérifier :**
1. Les secrets GitHub sont bien configurés (VPS_HOST, VPS_USER, VPS_SSH_PRIVATE_KEY)
2. La clé SSH publique est dans `~/.ssh/authorized_keys` sur le VPS
3. Le dépôt est bien cloné dans `/opt/cloudwaste`

---

## 📖 Documentation Complète

Pour tous les détails, voir : **`deployment/README.md`**

---

**Bon déploiement ! 🚀**
