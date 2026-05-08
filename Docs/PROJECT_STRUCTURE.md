# 🖱️ Mouse Biometric Authentication System - Project Structure

## 📁 Main Production Files (Root Directory)

### 🎯 Primary Applications
- **`MouseAuth.py`** - ⭐ Main production app (simple, clean interface)
- **`mouse_auth_app.py`** - Advanced app with 3 tabs (full-featured)
- **`quick_auth.py`** - CSV-based authentication without model
- **`run.bat`** / **`run_gui.bat`** - Quick launch scripts

### 📊 Data & Models
- **`data/`** - Training datasets (CSV files)
  - `mouse_features.csv` - Current training data (59 features, 10 users, 48k samples)
  - `jonathan_backup.csv` - User backup data
- **`models/`** - Trained model files
  - `mouse_auth_model.pkl` - Main production model
  - `mouse_auth_kaggle.pkl` - Kaggle competition model

### 📚 Documentation
- **`README.md`** - Main project documentation
- **`START_HERE.md`** - Quick start guide
- **`QUICK_START_OPTIMIZED.md`** - Optimized workflow
- **`GUI_QUICK_REFERENCE.md`** - GUI usage guide
- **`Docs/`** - Complete technical documentation

---

## 🧪 Organized Folders

### `tests/` - Testing & Validation
One-time test scripts for validation:
- `test_9users_training.py`
- `test_enhanced_features.py`
- `test_ultrafast.py`
- `verify_new_dataset.py`

### `generators/` - Data Generation
Scripts to generate synthetic data:
- `generate_new_fake_data.py` - Creates 59-feature synthetic users
- `train_kaggle_model.py` - Trains Kaggle model

### `archived/` - Deprecated Code
Old implementations kept for reference:
- `advanced_training.py`
- `collect_data_gui.py`
- `feature_extractor.py`
- `incremental_enroll.py`
- `real_time_auth.py`

### `utils/` - Utility Scripts
Helper scripts:
- `generate_fake_data.py` (old version)
- `quick_test_data.py`
- `system_test.py`
- `test_gpu.py`

### `not_imp/` - External Integrations
LLM and experimental features (not implemented in main app)

### `old_code/` - Historical Versions
Previous code versions and backups

---

## 🚀 Quick Start

1. **Run the app**: Double-click `run.bat` or run `python MouseAuth.py`
2. **Collect data**: Click "Collect Training Data" (10 sessions recommended)
3. **Train model**: Click "Train Model"
4. **Authenticate**: Click "Quick Auth" to test who you are

## 📋 Features

✅ **59 Advanced Features** - Statistical moments, FFT, Fitts' Law, cognitive latency, trajectory analysis  
✅ **10 Fake Users** - Pre-generated diverse behavioral profiles (4k-6k samples each)  
✅ **96%+ Accuracy** - State-of-the-art ensemble model (XGBoost + RF + GradientBoosting + ExtraTrees)  
✅ **Simple & Clean UI** - Easy-to-use interface with movement recommendations  

---

## 🔧 Environment

- **Python Environment**: `mouse` or `grad` conda environment
- **GPU Acceleration**: XGBoost with CUDA support
- **Dependencies**: See `requirements_kaggle.txt`

---

**Last Updated**: December 8, 2025
