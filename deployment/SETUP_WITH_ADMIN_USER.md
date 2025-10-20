# 🔧 Setup avec Utilisateur Admin (non-root)

Si votre provider vous donne un utilisateur admin (ex: `administrator`, `admin`, `ubuntu`) au lieu de l'accès root direct, suivez ce guide.

## ✅ Vérifications Initiales

### 1. Vérifier que vous avez sudo

```bash
# Une fois connecté au VPS
sudo whoami
# Devrait afficher: root
```

Si cela fonctionne, vous êtes prêt ! Sinon, contactez votre provider.

## 🚀 Installation en 3 Étapes

### Étape 1: Copier le script (depuis votre Mac)

```bash
cd /Users/jerome_laval/Desktop/CloudWaste
scp deployment/setup-vps.sh administrator@155.117.43.17:~/
```

Remplacez `administrator` par votre nom d'utilisateur si différent.

### Étape 2: Se connecter au VPS

```bash
ssh administrator@155.117.43.17
```

### Étape 3: Exécuter le script avec sudo

```bash
sudo bash ~/setup-vps.sh
```

Le script va:
- ✅ Créer l'utilisateur `cloudwaste` avec sudo
- ✅ Configurer SSH et les clés
- ✅ Installer Docker, Nginx, SSL, Portainer, etc.
- ✅ Configurer le firewall et Fail2Ban
- ✅ Tout sécuriser

## 📝 Notes Importantes

### Le script va vous demander:

1. **Mot de passe pour cloudwaste** - Choisissez un mot de passe fort
2. **Confirmation** - Le script explique chaque étape

### Après l'installation:

Votre utilisateur `administrator` restera disponible avec tous ses droits. Le script crée simplement un utilisateur dédié `cloudwaste` pour l'application.

### Test de connexion:

```bash
# Dans un autre terminal, testez:
ssh cloudwaste@155.117.43.17

# Si cela fonctionne, continuez avec le déploiement
```

## 🔐 Structure des Utilisateurs Après Installation

```
administrator (vous)
├── Accès sudo ✓
├── Connexion SSH ✓
└── Peut gérer le système

cloudwaste (créé par le script)
├── Accès sudo limité (Docker, Nginx, etc.) ✓
├── Connexion SSH ✓
└── Gère l'application CloudWaste
```

## 🎯 Après l'Installation

Une fois `setup-vps.sh` terminé, continuez avec les étapes suivantes du QUICKSTART:

```bash
# Se connecter avec cloudwaste
ssh cloudwaste@155.117.43.17

# Cloner le repository
cd /opt/cloudwaste
git clone https://github.com/VOTRE_USERNAME/CloudWaste.git .

# Continuer avec le guide QUICKSTART.md
```

## 🆘 Problèmes Courants

### "sudo: command not found"

Votre provider n'a pas installé sudo. Demandez l'accès root ou contactez le support.

### "Password:" mais ne marche pas

Assurez-vous d'utiliser le mot de passe correct. Si problème persiste, demandez un reset au provider.

### "Permission denied" sur /opt/cloudwaste

Normal au début. Le script créera ce dossier avec les bonnes permissions.

### Connexion SSH cloudwaste ne fonctionne pas

Le script copie automatiquement les clés SSH de `administrator` vers `cloudwaste`. Si problème:

```bash
# Sur le VPS en tant qu'administrator
sudo cp ~/.ssh/authorized_keys ~cloudwaste/.ssh/authorized_keys
sudo chown cloudwaste:cloudwaste ~cloudwaste/.ssh/authorized_keys
```

## ✅ Validation

Pour vérifier que tout fonctionne:

```bash
# Test 1: sudo fonctionne
ssh administrator@155.117.43.17
sudo docker --version

# Test 2: cloudwaste existe
sudo su - cloudwaste
whoami  # devrait afficher: cloudwaste
exit

# Test 3: connexion SSH cloudwaste
ssh cloudwaste@155.117.43.17
# Devrait fonctionner sans demander de mot de passe (clé SSH)
```

## 🎉 Prêt !

Une fois ces tests passés, suivez le reste du guide QUICKSTART.md depuis l'étape 3.

---

**Résumé**: Remplacez `root@` par `administrator@` (ou votre utilisateur) et ajoutez `sudo` devant les commandes d'installation. C'est tout ! 🚀

