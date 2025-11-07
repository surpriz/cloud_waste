# CloudWaste - ML Data Collection Documentation

**Last Updated:** November 7, 2025
**Current Phase:** Phase 1 Complete ✅
**Next Phase:** Data Enrichment (Phase 2)

---

## 📚 Table of Contents

### 1. [Current Status](./01_CURRENT_STATUS.md)
État actuel EXACT du système de collecte ML :
- ✅ Ce qui est implémenté et fonctionne
- ⚠️ Ce qui est partiellement implémenté
- ❌ Ce qui n'est pas encore fait
- 📊 Comment vérifier que la collecte fonctionne

### 2. [Architecture](./02_ARCHITECTURE.md)
Architecture technique et schéma de base de données :
- Database schema (6 tables ML)
- Services créés (collectors, anonymization, pipeline)
- Intégration avec les scans AWS/Azure
- Flow de collecte des données

### 3. [Usage Guide](./03_USAGE_GUIDE.md)
Guide d'utilisation pour AUJOURD'HUI :
- Comment exporter les données ML (admin panel)
- Comment monitorer la collecte
- Workflow de collecte automatique
- Timeline recommandée

### 4. [Next Phases](./04_NEXT_PHASES.md)
Roadmap des prochaines étapes :
- **Phase 2:** Enrichir la collecte de données
- **Phase 3:** Support GCP/Microsoft365
- **Phase 4:** Optimisation et monitoring
- **Phase 5:** ML Model Training

### 5. [Troubleshooting](./05_TROUBLESHOOTING.md)
Debugging et résolution de problèmes :
- Vérifier que la collecte fonctionne
- Problèmes courants et solutions
- Commandes de vérification SQL
- Logs à surveiller

---

## 🎯 Quick Start

### Vérifier l'Installation

```bash
# 1. Vérifier que les tables existent
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "\dt" | grep ml_

# 2. Lancer un scan via UI
# → http://localhost:3000/dashboard

# 3. Vérifier la collecte
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) FROM ml_training_data WHERE created_at > NOW() - INTERVAL '1 hour';"

# 4. Exporter les données via admin panel
# → http://localhost:3000/dashboard/admin (section ML Data Collection)
```

---

## 🚀 État Actuel (Phase 1)

**✅ Fonctionnel:**
- Collecte automatique des données ML lors de chaque scan
- 6 tables PostgreSQL avec données anonymisées
- Admin panel avec statistiques et export (JSON/CSV)
- Intégration AWS + Azure scans

**🔄 À Venir (Phase 2+):**
- Enrichissement des données (tags, real costs, relationships)
- Support GCP et Microsoft365
- Export automatisé hebdomadaire (Celery Beat)
- ML model training (100K+ samples requis)

---

## 📊 Progression

| Phase | Status | Completion | Next Milestone |
|-------|--------|------------|----------------|
| **Phase 1** | ✅ Complete | 100% | 10K+ records collected |
| **Phase 2** | 📅 Planned | 0% | Data enrichment |
| **Phase 3** | 📅 Planned | 0% | GCP integration |
| **Phase 4** | 📅 Planned | 0% | Optimization |
| **Phase 5** | 📅 Planned | 0% | ML training |

---

## 📞 Support

- **Current Status:** [01_CURRENT_STATUS.md](./01_CURRENT_STATUS.md)
- **Troubleshooting:** [05_TROUBLESHOOTING.md](./05_TROUBLESHOOTING.md)
- **Contact:** jerome0laval@gmail.com

---

**🎉 Phase 1 Complete - CloudWaste is now collecting ML data automatically!**
