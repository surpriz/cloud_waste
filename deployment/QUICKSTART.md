# 🚀 Guide de Démarrage Rapide - CloudWaste Production

Ce guide vous permet de déployer CloudWaste en production en 30 minutes.

## Prérequis

- ✅ VPS Ubuntu avec accès root ou sudo (IP: 155.117.43.17)
- ✅ Domaine configuré: cutcosts.tech
- ✅ Repository GitHub avec CloudWaste
- ✅ Fichiers .env et encryption_key de votre environnement local

> **Note**: Si votre provider vous donne un utilisateur admin (ex: `administrator`) au lieu de `root`, c'est parfait ! Remplacez simplement `root@` par `administrator@` dans toutes les commandes.

## Étape 1: Configurer le DNS (5 min)

Dans votre gestionnaire de domaine, ajoutez ces enregistrements:

```
Type: A    | Nom: @   | Valeur: 155.117.43.17 | TTL: 300
Type: A    | Nom: www | Valeur: 155.117.43.17 | TTL: 300
```

Attendez quelques minutes pour la propagation.

## Étape 2: Initialiser le VPS (15 min)

```bash
# Sur votre machine locale
cd /Users/jerome_laval/Desktop/CloudWaste

# Rendre le script exécutable
chmod +x deployment/setup-vps.sh

# Copier sur le VPS (remplacez 'administrator' par votre utilisateur si différent)
scp deployment/setup-vps.sh administrator@155.117.43.17:~/

# Se connecter et exécuter avec sudo
ssh administrator@155.117.43.17
sudo bash ~/setup-vps.sh
```

Le script va vous demander de définir un mot de passe pour l'utilisateur `cloudwaste`.

**⚠️ IMPORTANT**: Avant de fermer la session root, testez la connexion SSH dans un autre terminal:
```bash
ssh cloudwaste@155.117.43.17
```

## Étape 3: Cloner et Configurer (5 min)

```bash
# Se connecter avec le nouvel utilisateur
ssh cloudwaste@155.117.43.17

# Cloner le repository
cd /opt/cloudwaste
git clone https://github.com/VOTRE_USERNAME/CloudWaste.git .

# Copier le docker-compose de production
cp deployment/docker-compose.production.yml docker-compose.production.yml

# Copier les scripts à la racine
cp deployment/*.sh .
chmod +x *.sh
```

## Étape 4: Variables d'Environnement (3 min)

```bash
# Créer le fichier .env
nano .env
```

Copiez le contenu de `deployment/env.production.template` et remplissez les valeurs:

**Valeurs essentielles à modifier:**
```bash
SECRET_KEY=          # Générer avec: openssl rand -hex 32
JWT_SECRET_KEY=      # Générer avec: openssl rand -hex 32
POSTGRES_PASSWORD=   # Générer avec: openssl rand -base64 32
ENCRYPTION_KEY=      # Copier depuis votre fichier local
ANTHROPIC_API_KEY=   # Votre clé API Claude
```

**Mettre à jour DATABASE_URL avec le mot de passe:**
```bash
DATABASE_URL=postgresql+asyncpg://cloudwaste:VOTRE_MOT_DE_PASSE@postgres:5432/cloudwaste
```

Sauvegardez avec `Ctrl+X`, `Y`, `Enter`.

## Étape 5: Clé de Chiffrement

```bash
# Créer le fichier encryption_key
nano encryption_key
```

Collez le contenu de votre fichier `encryption_key` local, puis sauvegardez.

## Étape 6: Configurer Nginx (2 min)

```bash
# Installer la configuration Nginx
sudo bash deployment/install-nginx-config.sh
```

## Étape 7: Obtenir le Certificat SSL (2 min)

```bash
sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech
```

Suivez les instructions (entrez votre email, acceptez les conditions).

## Étape 8: Premier Déploiement (5 min)

```bash
cd /opt/cloudwaste
bash deploy.sh
```

Le script va:
- 🔨 Construire les images Docker
- 🗄️ Créer la base de données
- 🚀 Démarrer tous les services
- ✅ Vérifier le déploiement

## Étape 9: Vérification

### Tester les services

```bash
# Health check complet
bash health-check.sh
```

### Accès Web

Ouvrez dans votre navigateur:
- ✅ https://cutcosts.tech (Frontend)
- ✅ https://cutcosts.tech/api/v1/docs (API)
- ✅ https://cutcosts.tech:9443 (Portainer)
- ✅ https://cutcosts.tech/netdata (Monitoring)

## Étape 10: Configurer GitHub Actions (Optionnel)

Pour activer le déploiement automatique:

1. Générer une clé SSH sur votre machine locale:
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cloudwaste_deploy
```

2. Ajouter la clé publique au VPS:
```bash
ssh-copy-id -i ~/.ssh/cloudwaste_deploy.pub cloudwaste@155.117.43.17
```

3. Dans GitHub, aller dans Settings → Secrets and variables → Actions

4. Ajouter ces secrets:
   - `VPS_SSH_KEY`: Contenu de `~/.ssh/cloudwaste_deploy` (clé PRIVÉE)
   - `VPS_HOST`: 155.117.43.17
   - `VPS_USER`: cloudwaste

5. Tester le déploiement automatique:
```bash
# Sur votre machine locale
git add .
git commit -m "Test auto-deploy"
git push origin main
```

Le déploiement se lancera automatiquement et sera visible dans l'onglet Actions de GitHub.

## 🎉 C'est fait !

Votre application CloudWaste est maintenant en production!

## Commandes Utiles

```bash
# Voir les logs
docker compose -f docker-compose.production.yml logs -f

# Redémarrer un service
docker compose -f docker-compose.production.yml restart backend

# Health check
bash health-check.sh

# Backup manuel
bash backup.sh

# Déployer une mise à jour
bash deploy.sh
```

## 🆘 Problèmes Courants

### Le site affiche "502 Bad Gateway"
```bash
# Vérifier les logs du backend
docker compose -f docker-compose.production.yml logs backend

# Redémarrer le backend
docker compose -f docker-compose.production.yml restart backend
```

### Erreur "Cannot connect to database"
```bash
# Vérifier que PostgreSQL fonctionne
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs postgres
```

### Certificat SSL non valide
```bash
# Vérifier Certbot
sudo certbot certificates

# Renouveler manuellement
sudo certbot renew
```

## 📚 Documentation Complète

Pour plus de détails, consultez:
- `VPS_PRODUCTION_GUIDE.md` - Guide complet
- `deployment/README.md` - Documentation des scripts

## 🔄 Workflow de Développement

1. Développez localement sur votre machine
2. Testez en local avec `docker compose up`
3. Commitez et poussez sur GitHub
4. Le déploiement se fait automatiquement (ou lancez `bash deploy.sh` manuellement)

## 📞 Support

En cas de problème:
1. Consultez les logs: `docker compose logs -f`
2. Lancez un health check: `bash health-check.sh`
3. Vérifiez la documentation complète
4. Vérifiez l'état des services: `docker compose ps`

---

**Temps total estimé**: 30-40 minutes
**Dernière mise à jour**: 2025-01-20

