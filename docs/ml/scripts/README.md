# ML Scripts (Archived for Future Use)

**Status:** 📦 Archived - Not needed yet
**Use When:** Phase 5 (ML Training) - When you have 100K+ samples

---

## 📄 Scripts

### `export_ml_data.py`

**Purpose:** Export ML datasets from PostgreSQL to JSON/CSV files

**When to Use:**
- ⚠️ Not needed now (use admin panel export instead)
- ✅ Use in Phase 5 when training ML models
- ✅ Use if you need automated exports (not via UI)

**Usage:**
```bash
# From project root
python docs/ml/scripts/export_ml_data.py

# Creates files in:
# ./ml_datasets/ml_training_data_20251107.json
# ./ml_datasets/user_action_patterns_20251107.json
# ./ml_datasets/cost_trends_20251107.json
```

**Current Alternative:** Use admin panel export
- Go to: http://localhost:3000/dashboard/admin
- Click "Export Last 90 Days (JSON)"

---

### `train_model.py`

**Purpose:** Train ML model for waste prediction

**When to Use:**
- ❌ Not yet - need 100K+ labeled samples first
- ✅ Use in Phase 5 (Month 4+)
- ✅ When you're ready to train CloudWaste V2 AI models

**Usage:**
```bash
# From project root
python docs/ml/scripts/train_model.py

# Requires:
# - 100K+ records in ml_training_data
# - 10K+ user actions (deleted/kept labels)
# - pip install pandas scikit-learn numpy

# Output:
# 🤖 Training Random Forest model...
# 📈 Model Performance: Accuracy: 87.32%
# 💾 Model saved to: ./ml_models/waste_prediction_model.pkl
```

**Prerequisites:**
```bash
pip install pandas scikit-learn numpy
```

---

## 📊 Current Status (Phase 1)

**What You Should Do Now:**
1. ✅ Let CloudWaste collect data automatically
2. ✅ Monitor growth via admin panel
3. ✅ Export via admin panel when needed
4. ❌ Don't use these scripts yet

**Timeline:**
- **Month 1-3:** Collect data (target: 10K → 100K samples)
- **Month 4+:** Use these scripts for ML training

---

## 🔄 Migration Path

### Phase 1 (Now): Admin Panel Export
```
Admin Panel → Click Export → Download JSON
```

### Phase 5 (Future): Automated Training
```bash
# 1. Export data
python docs/ml/scripts/export_ml_data.py

# 2. Train model
python docs/ml/scripts/train_model.py

# 3. Deploy model to backend
# (integrate with FastAPI)

# 4. Launch CloudWaste V2 with AI! 🚀
```

---

## 📞 Questions?

**"Should I delete these scripts?"**
→ No, keep them archived. You'll need them in Phase 5.

**"Can I use export_ml_data.py now?"**
→ Yes, but admin panel is easier for now.

**"When will I need train_model.py?"**
→ When you have 100K+ samples (Month 3-4).

---

**See Also:**
- [04_NEXT_PHASES.md](../04_NEXT_PHASES.md) - Phase 5 details
- [03_USAGE_GUIDE.md](../03_USAGE_GUIDE.md) - Current usage (admin panel)
