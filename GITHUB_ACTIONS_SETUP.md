# 🚀 Configuration GitHub Actions pour Déploiement Automatique

Ce guide explique comment configurer GitHub Actions pour déployer automatiquement CloudWaste sur votre VPS à chaque `git push`.

---

## 📋 **Prérequis**

- ✅ Compte GitHub avec accès au repository
- ✅ VPS configuré et fonctionnel
- ✅ Accès SSH au VPS

---

## 🔐 **ÉTAPE 1 : Générer une Clé SSH pour GitHub Actions**

Sur votre **machine locale** (pas le VPS), exécutez :

```bash
# Générer une nouvelle paire de clés SSH dédiée à GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-cloudwaste" -f ~/.ssh/github_actions_cloudwaste

# Ne mettez PAS de passphrase (appuyez sur Entrée)
```

Cela crée deux fichiers :
- `~/.ssh/github_actions_cloudwaste` → **Clé privée** (à ajouter dans GitHub Secrets)
- `~/.ssh/github_actions_cloudwaste.pub` → **Clé publique** (à ajouter sur le VPS)

---

## 🔑 **ÉTAPE 2 : Ajouter la Clé Publique sur le VPS**

```bash
# Copier la clé publique sur le VPS
ssh-copy-id -i ~/.ssh/github_actions_cloudwaste.pub cloudwaste@155.117.43.17

# OU manuellement :
cat ~/.ssh/github_actions_cloudwaste.pub
# Copiez le contenu, puis sur le VPS :
ssh cloudwaste@155.117.43.17
echo "CONTENU_CLÉ_PUBLIQUE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### **Tester la connexion SSH**

```bash
ssh -i ~/.ssh/github_actions_cloudwaste cloudwaste@155.117.43.17
```

Si ça fonctionne sans demander de mot de passe, c'est bon ! ✅

---

## 🔒 **ÉTAPE 3 : Configurer les Secrets GitHub**

1. **Allez sur votre repository GitHub** :
   ```
   https://github.com/votre-username/cloud_waste
   ```

2. **Accédez aux Settings** :
   - Cliquez sur `Settings` (en haut à droite)
   - Dans le menu de gauche : `Secrets and variables` → `Actions`

3. **Ajoutez les secrets suivants** (cliquez sur `New repository secret`) :

### **Secret 1 : VPS_SSH_PRIVATE_KEY**

```bash
# Sur votre machine locale, affichez la clé privée :
cat ~/.ssh/github_actions_cloudwaste
```

- **Name** : `VPS_SSH_PRIVATE_KEY`
- **Value** : Copiez TOUT le contenu (de `-----BEGIN OPENSSH PRIVATE KEY-----` à `-----END OPENSSH PRIVATE KEY-----`)

⚠️ **Important** : Incluez les lignes `-----BEGIN` et `-----END` !

### **Secret 2 : VPS_HOST**

- **Name** : `VPS_HOST`
- **Value** : `155.117.43.17`

### **Secret 3 : VPS_USER**

- **Name** : `VPS_USER`
- **Value** : `cloudwaste`

---

## ✅ **ÉTAPE 4 : Vérifier la Configuration**

Les secrets devraient apparaître comme ceci dans GitHub :

```
VPS_SSH_PRIVATE_KEY   ******
VPS_HOST              ******
VPS_USER              ******
```

---

## 🎯 **ÉTAPE 5 : Tester le Déploiement Automatique**

### **Test 1 : Déclencher manuellement**

1. Allez dans l'onglet `Actions` de votre repository
2. Cliquez sur `Deploy to Production` (dans la liste à gauche)
3. Cliquez sur `Run workflow` → `Run workflow`
4. Attendez quelques minutes et vérifiez que tout est vert ✅

### **Test 2 : Déploiement automatique sur git push**

```bash
# Sur votre machine locale
cd /Users/jerome_laval/Desktop/CloudWaste

# Faire une petite modification (par exemple dans le README)
echo "\n# Test déploiement automatique" >> README.md

# Commit et push
git add README.md
git commit -m "test: Vérification déploiement automatique"
git push origin master

# Vérifier dans l'onglet Actions de GitHub
# → Un workflow devrait démarrer automatiquement
```

---

## 🔍 **ÉTAPE 6 : Surveillance et Logs**

### **Dans GitHub** :
- Onglet `Actions` → Cliquez sur un workflow pour voir les logs détaillés
- Chaque étape est déroulée avec les logs en temps réel

### **Sur le VPS** :
```bash
# Voir les logs de déploiement
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
docker compose -f docker-compose.production.yml logs --tail=100
```

---

## ⚠️ **TROUBLESHOOTING**

### **Erreur : "Permission denied (publickey)"**

**Problème** : La clé SSH n'est pas correctement configurée.

**Solution** :
1. Vérifiez que la clé privée est complète dans GitHub Secrets (incluant `-----BEGIN` et `-----END`)
2. Vérifiez que la clé publique est dans `~/.ssh/authorized_keys` sur le VPS
3. Testez manuellement : `ssh -i ~/.ssh/github_actions_cloudwaste cloudwaste@155.117.43.17`

### **Erreur : "Host key verification failed"**

**Problème** : L'hôte n'est pas dans les `known_hosts`.

**Solution** : Cela devrait être géré automatiquement par le workflow (`ssh-keyscan`). Si le problème persiste, ajoutez manuellement :

```bash
ssh-keyscan -H 155.117.43.17 >> ~/.ssh/known_hosts
```

### **Erreur : "quick-deploy.sh: No such file or directory"**

**Problème** : Le script n'est pas exécutable ou n'existe pas.

**Solution** :
```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
git pull origin master
chmod +x deployment/quick-deploy.sh
```

---

## 🎉 **WORKFLOW FINAL**

Une fois configuré, votre workflow sera :

```
1. Développer en local
   ↓
2. git add . && git commit -m "feat: nouvelle fonctionnalité"
   ↓
3. git push origin master
   ↓
4. GitHub Actions déclenche le déploiement automatiquement
   ↓
5. Votre VPS télécharge le code et redémarre les services
   ↓
6. https://cutcosts.tech est mis à jour ! 🎉
```

**Temps total** : ~3-5 minutes du `git push` au déploiement complet.

---

## 🔐 **SÉCURITÉ**

✅ **Bonnes pratiques appliquées** :
- Clé SSH dédiée uniquement pour GitHub Actions
- Clé privée stockée de manière sécurisée dans GitHub Secrets
- Aucun mot de passe hardcodé dans le code
- Connexion SSH uniquement (pas d'API ouverte)

⚠️ **Ne jamais** :
- Committer la clé privée dans Git
- Partager les secrets GitHub
- Réutiliser la même clé SSH pour d'autres projets

---

## 📚 **RESSOURCES**

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [SSH Key Authentication](https://www.ssh.com/academy/ssh/public-key-authentication)

---

## 💡 **NOTES**

- Le workflow se déclenche uniquement sur la branche `master`
- Vous pouvez aussi déclencher manuellement depuis l'onglet Actions
- Les logs de déploiement sont visibles dans GitHub Actions
- En cas d'échec, le workflow vous alerte et ne déploie pas

---

Besoin d'aide ? Consultez les logs dans GitHub Actions ou sur le VPS ! 🚀

