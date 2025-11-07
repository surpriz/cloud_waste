# ML Data Collection Documentation

**📁 All ML documentation has been moved to:** `/docs/ml/`

---

## 📚 Documentation Structure

### Quick Links

| Document | Description |
|----------|-------------|
| [**README**](./docs/ml/README.md) | Table of contents and overview |
| [**01_CURRENT_STATUS**](./docs/ml/01_CURRENT_STATUS.md) | What's working right now ✅ |
| [**02_ARCHITECTURE**](./docs/ml/02_ARCHITECTURE.md) | Technical architecture & database schema |
| [**03_USAGE_GUIDE**](./docs/ml/03_USAGE_GUIDE.md) | How to use the system today |
| [**04_NEXT_PHASES**](./docs/ml/04_NEXT_PHASES.md) | Roadmap for future phases 🗺️ |
| [**05_TROUBLESHOOTING**](./docs/ml/05_TROUBLESHOOTING.md) | Debug guide & common issues |

---

## 🚀 Quick Start

```bash
# 1. Verify ML collection is working
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) FROM ml_training_data;"

# 2. Launch a scan
# Go to: http://localhost:3000/dashboard

# 3. View ML stats in admin panel
# Go to: http://localhost:3000/dashboard/admin

# 4. Export data
# Click "Export Last 90 Days (JSON)" in admin panel
```

---

## 📊 What's Implemented (Phase 1)

✅ **Automatic data collection** during every scan
✅ **6 PostgreSQL tables** with anonymized data
✅ **Admin panel export** (JSON/CSV)
✅ **AWS + Azure support**

---

## 🔄 What's Next (Phase 2+)

📅 **Phase 2:** Data enrichment (tags, real costs, relationships)
📅 **Phase 3:** GCP + Microsoft365 support
📅 **Phase 4:** Optimization & automation
📅 **Phase 5:** ML model training (when 100K+ samples)

**See:** [04_NEXT_PHASES.md](./docs/ml/04_NEXT_PHASES.md) for detailed roadmap

---

## 📞 Need Help?

- **Check status:** [01_CURRENT_STATUS.md](./docs/ml/01_CURRENT_STATUS.md)
- **Troubleshooting:** [05_TROUBLESHOOTING.md](./docs/ml/05_TROUBLESHOOTING.md)
- **Contact:** jerome0laval@gmail.com

---

**🎉 Phase 1 Complete - CloudWaste is now collecting ML data automatically!**
