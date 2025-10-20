# ✅ Checklist de Déploiement CloudWaste

Utilisez cette checklist pour vous assurer que tout est correctement configuré.

## 📋 Avant de Commencer

- [ ] VPS Ubuntu accessible (IP: 155.117.43.17)
- [ ] Accès root au VPS (mot de passe ou clé SSH)
- [ ] Nom de domaine: cutcosts.tech
- [ ] Repository GitHub avec le code CloudWaste
- [ ] Fichier .env de développement local
- [ ] Fichier encryption_key de développement local
- [ ] Clés API (Azure, AWS, Anthropic) prêtes

## 🌐 Configuration DNS

- [ ] Enregistrement A pour @ → 155.117.43.17
- [ ] Enregistrement A pour www → 155.117.43.17
- [ ] DNS propagé (vérifier avec: `nslookup cutcosts.tech`)

## 🔧 Initialisation du VPS

- [ ] Script `setup-vps.sh` copié sur le VPS
- [ ] Script `setup-vps.sh` exécuté avec succès
- [ ] Utilisateur `cloudwaste` créé
- [ ] Mot de passe pour `cloudwaste` défini
- [ ] Clés SSH configurées
- [ ] Connexion SSH testée: `ssh cloudwaste@155.117.43.17`
- [ ] Docker installé et fonctionnel
- [ ] Nginx installé et actif
- [ ] Certbot installé
- [ ] Portainer démarré
- [ ] Ollama installé
- [ ] Netdata installé
- [ ] Firewall (UFW) actif
- [ ] Fail2Ban actif

## 📦 Déploiement de l'Application

- [ ] Repository cloné dans `/opt/cloudwaste/`
- [ ] Fichier `docker-compose.production.yml` copié à la racine
- [ ] Scripts de déploiement copiés et rendus exécutables
- [ ] Fichier `.env` créé et rempli
  - [ ] SECRET_KEY généré
  - [ ] JWT_SECRET_KEY généré
  - [ ] POSTGRES_PASSWORD généré et ajouté à DATABASE_URL
  - [ ] ENCRYPTION_KEY copié depuis local
  - [ ] ANTHROPIC_API_KEY ajouté
  - [ ] Azure credentials ajoutés (si applicable)
  - [ ] AWS credentials ajoutés (si applicable)
  - [ ] ALLOWED_ORIGINS contient cutcosts.tech
  - [ ] NEXT_PUBLIC_API_URL = https://cutcosts.tech
- [ ] Fichier `encryption_key` créé (copié depuis local)

## 🌍 Configuration Nginx

- [ ] Configuration Nginx installée: `/etc/nginx/sites-available/cutcosts.tech`
- [ ] Lien symbolique créé: `/etc/nginx/sites-enabled/cutcosts.tech`
- [ ] Site par défaut désactivé
- [ ] Configuration Nginx testée: `sudo nginx -t`
- [ ] Nginx rechargé: `sudo systemctl reload nginx`

## 🔒 Configuration SSL

- [ ] Certbot exécuté: `sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech`
- [ ] Email fourni pour les notifications
- [ ] Conditions d'utilisation acceptées
- [ ] Certificat SSL créé avec succès
- [ ] Renouvellement automatique testé: `sudo certbot renew --dry-run`

## 🚀 Premier Déploiement

- [ ] Script `deploy.sh` exécuté
- [ ] Images Docker construites
- [ ] Migrations de base de données exécutées
- [ ] Tous les conteneurs démarrés
- [ ] Aucune erreur dans les logs: `docker compose logs`

## ✅ Vérifications Post-Déploiement

### Tests Manuels

- [ ] Site accessible: https://cutcosts.tech
- [ ] Redirection HTTP → HTTPS fonctionne
- [ ] API accessible: https://cutcosts.tech/api/v1/docs
- [ ] Certificat SSL valide (cadenas vert dans le navigateur)
- [ ] Portainer accessible: https://cutcosts.tech:9443
- [ ] Netdata accessible: https://cutcosts.tech/netdata
- [ ] Login utilisateur fonctionne
- [ ] Scan de ressources cloud fonctionne
- [ ] Chat AI fonctionne

### Health Check

- [ ] Script `health-check.sh` exécuté
- [ ] Tous les conteneurs running
- [ ] PostgreSQL répond
- [ ] Redis répond
- [ ] Backend health check: OK
- [ ] Frontend répond
- [ ] Celery workers actifs
- [ ] Nginx actif
- [ ] Aucune erreur critique

### Logs

- [ ] Logs backend propres: `docker compose logs backend`
- [ ] Logs frontend propres: `docker compose logs frontend`
- [ ] Logs Nginx propres: `sudo tail -f /var/log/nginx/cutcosts.tech.error.log`
- [ ] Aucun error 500 dans les logs d'accès

## 🔄 Configuration GitHub Actions (Optionnel)

- [ ] Clé SSH générée: `ssh-keygen -t rsa -b 4096 -f ~/.ssh/cloudwaste_deploy`
- [ ] Clé publique ajoutée au VPS: `ssh-copy-id cloudwaste@155.117.43.17`
- [ ] Test de connexion SSH sans mot de passe réussi
- [ ] Secret GitHub `VPS_SSH_KEY` ajouté (clé PRIVÉE)
- [ ] Secret GitHub `VPS_HOST` ajouté (155.117.43.17)
- [ ] Secret GitHub `VPS_USER` ajouté (cloudwaste)
- [ ] Workflow `.github/workflows/deploy-production.yml` présent
- [ ] Test de déploiement automatique réussi (push sur main)

## 💾 Configuration des Backups

- [ ] Script `backup.sh` exécuté manuellement pour test
- [ ] Backup créé dans `/opt/cloudwaste/backups/`
- [ ] Backup valide (vérification de l'archive)
- [ ] Cron job configuré (vérifié dans `/etc/cron.d/cloudwaste-backup`)
- [ ] Test de restauration effectué: `bash restore.sh <backup-file>`

## 🔐 Sécurité

- [ ] Connexion root SSH désactivée
- [ ] Authentification par mot de passe SSH désactivée
- [ ] Seule l'authentification par clé SSH activée
- [ ] Firewall actif: `sudo ufw status`
- [ ] Fail2Ban actif: `sudo systemctl status fail2ban`
- [ ] Mises à jour automatiques configurées
- [ ] Fichier `.env` avec permissions 600
- [ ] Fichier `encryption_key` avec permissions 600
- [ ] Pas de secrets dans les logs
- [ ] Pas de secrets commitées dans Git

## 📊 Monitoring

- [ ] Netdata accessible et fonctionnel
- [ ] Portainer accessible et configuré
- [ ] Dashboard Portainer exploré
- [ ] Alertes email configurées (optionnel)
- [ ] Monitoring externe configuré (UptimeRobot, etc.) (optionnel)

## 📝 Documentation

- [ ] VPS_PRODUCTION_GUIDE.md lu et compris
- [ ] Commandes de maintenance notées
- [ ] Procédures d'urgence comprises
- [ ] Accès et credentials documentés (dans un endroit sécurisé)

## 🎯 Tests de Charge (Optionnel)

- [ ] Test de charge API effectué
- [ ] Test de charge frontend effectué
- [ ] Temps de réponse acceptable
- [ ] Pas de crash sous charge
- [ ] Mémoire et CPU stables

## 📈 Optimisations (Optionnel)

- [ ] PostgreSQL configuré pour les performances
- [ ] Redis cache configuré
- [ ] Compression Gzip activée dans Nginx
- [ ] CDN configuré pour les assets statiques (si applicable)
- [ ] Rate limiting configuré dans Nginx

## 🔄 Workflow de Maintenance

- [ ] Processus de déploiement documenté
- [ ] Procédure de rollback comprise
- [ ] Procédure de backup/restore testée
- [ ] Procédure de mise à jour des dépendances documentée

## 📞 Plan d'Urgence

- [ ] Contacts d'urgence définis
- [ ] Procédure de rollback documentée
- [ ] Backups récents vérifiés
- [ ] Accès de secours configuré
- [ ] Logs d'erreur surveillés

## ✅ Validation Finale

- [ ] Site en production accessible publiquement
- [ ] Tous les tests passent
- [ ] Performance acceptable
- [ ] Aucune erreur critique
- [ ] Backups fonctionnels
- [ ] Monitoring actif
- [ ] Documentation à jour

---

## 🎉 Félicitations !

Si tous les items sont cochés, votre déploiement CloudWaste est complet et sécurisé !

**Prochaines étapes:**
1. Surveillez les logs pendant les premières 24h
2. Testez les backups régulièrement
3. Surveillez les performances
4. Planifiez les mises à jour
5. Configurez des alertes de monitoring

**Maintenance régulière:**
- Vérifier les backups : Hebdomadaire
- Vérifier les logs : Quotidien (au début)
- Mises à jour de sécurité : Automatiques
- Vérifier l'espace disque : Hebdomadaire
- Vérifier les certificats SSL : Mensuel (renouvellement automatique)

**Date du déploiement**: _______________
**Déployé par**: _______________
**Version déployée**: _______________

