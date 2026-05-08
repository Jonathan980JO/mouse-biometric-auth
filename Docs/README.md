# 🔐 Mouse Biometric Authentication System

A continuous behavioral authentication system using mouse movement dynamics for secure access control.

## 📋 Table of Contents
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Feature Taxonomy](#feature-taxonomy)
- [System Flowchart](#system-flowchart)
- [Installation](#installation)
- [Usage](#usage)
- [Technical Specifications](#technical-specifications)
- [Performance Metrics](#performance-metrics)

---

## 🎯 Overview

This project implements a **behavioral biometric authentication system** that identifies users based on their unique mouse movement patterns. Unlike traditional password-based systems that authenticate only at login, this system provides **continuous authentication** throughout a user session.

### Key Features
- ✅ Non-intrusive behavioral biometrics
- ✅ Continuous authentication capability
- ✅ Multi-level security (Low/Medium/High)
- ✅ GPU-accelerated machine learning
- ✅ Professional dark-mode UI
- ✅ Real-time confidence scoring

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Data         │  │ Model        │  │ Authentication│      │
│  │ Collection   │  │ Training     │  │ Testing       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 DATA PROCESSING LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Mouse        │  │ Feature      │  │ Quality      │      │
│  │ Tracking     │  │ Extraction   │  │ Filtering    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 MACHINE LEARNING LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ XGBoost      │  │ Random       │  │ Voting       │      │
│  │ (GPU/CPU)    │  │ Forest       │  │ Ensemble     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   DECISION LAYER                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Multi-Metric Confidence Calculation              │       │
│  │  • Overall Confidence ≥ Threshold                │       │
│  │  • Vote Consistency ≥ Threshold                  │       │
│  │  • Minimum Sample Confidence                     │       │
│  └──────────────────────────────────────────────────┘       │
│                  ↓                    ↓                      │
│           ✅ GRANT ACCESS      ❌ DENY ACCESS               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Feature Taxonomy

### Feature Categories

```
MOUSE DYNAMICS FEATURES (13 Total)
│
├── 🔷 SPATIAL FEATURES (Position & Distance)
│   ├── dx: Change in X-coordinate
│   ├── dy: Change in Y-coordinate
│   ├── dir_change_x: Directional change in X-axis
│   └── dir_change_y: Directional change in Y-axis
│
├── 🔶 KINEMATIC FEATURES (Motion Dynamics)
│   ├── speed: Instantaneous velocity (pixels/time)
│   ├── accel: Acceleration (change in speed)
│   └── jerk: Rate of change of acceleration
│
├── 🔵 GEOMETRIC FEATURES (Path Shape)
│   ├── angle: Movement angle (arctan2)
│   ├── angle_change: Angular variation
│   └── curvature: Path curvature (angle/distance)
│
└── 🟢 TEMPORAL FEATURES (Time-based Statistics)
    ├── time_elapsed: Cumulative time from start
    ├── speed_variance: Rolling variance of speed (4-sample window)
    └── speed_std: Rolling standard deviation of speed (4-sample window)
```

### Feature Extraction Pipeline

```
Raw Mouse Positions
        ↓
┌─────────────────┐
│ Vectorization   │ → Convert to NumPy arrays
└─────────────────┘
        ↓
┌─────────────────┐
│ Differences     │ → Calculate dx, dy
└─────────────────┘
        ↓
┌─────────────────┐
│ Kinematics      │ → Compute speed, accel, jerk
└─────────────────┘
        ↓
┌─────────────────┐
│ Geometry        │ → Calculate angles, curvature
└─────────────────┘
        ↓
┌─────────────────┐
│ Statistics      │ → Rolling window variance/std
└─────────────────┘
        ↓
13 Features per Sample
```

---

## 🔄 System Flowchart

### Training Phase

```
                    ┌─────────────────┐
                    │  Start Training │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Load CSV Data  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Data Valid?    │
                    └────┬────────┬───┘
                         │ Yes    │ No
                         │   ┌────▼──────────────────┐
                         │   │ Error: Missing Data   │
                         │   └───────────────────────┘
                    ┌────▼────────┐
                    │ Remove      │
                    │ Duplicates  │
                    └────┬────────┘
                         │
                    ┌────▼────────┐
                    │ Extract     │
                    │ Features    │
                    └────┬────────┘
                         │
                    ┌────▼─────────────┐
                    │ Sufficient       │
                    │ Samples (≥40)?   │
                    └────┬─────────┬───┘
                         │ Yes     │ No
                         │    ┌────▼─────────────────────┐
                         │    │ Error: Need 40+ Samples  │
                         │    └──────────────────────────┘
                    ┌────▼──────────┐
                    │ Split Data    │
                    │ 70/30         │
                    └────┬──────────┘
                         │
                    ┌────▼──────────┐
                    │ Apply         │
                    │ StandardScaler│
                    └────┬──────────┘
                         │
                    ┌────▼──────────────┐
                    │ Class Imbalance?  │
                    │ (Ratio > 2:1)     │
                    └────┬──────────┬───┘
                    Yes  │          │ No
                  ┌──────▼───┐   ┌──▼────────────┐
                  │  Apply   │   │ Use Class     │
                  │  SMOTE   │   │ Weights       │
                  └──────┬───┘   └──┬────────────┘
                         │          │
                         └────┬─────┘
                              │
                    ┌─────────▼─────────┐
                    │ Train XGBoost     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ GPU Available?    │
                    └────┬──────────┬───┘
                    Yes  │          │ No
                ┌────────▼───┐  ┌──▼──────────┐
                │ GPU        │  │ CPU         │
                │ Training   │  │ Training    │
                └────────┬───┘  └──┬──────────┘
                         │         │
                         └────┬────┘
                              │
                    ┌─────────▼─────────┐
                    │ Train Random      │
                    │ Forest            │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Create Voting     │
                    │ Ensemble          │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 3-Fold Cross      │
                    │ Validation        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Calculate Metrics │
                    │ (Accuracy, FAR,   │
                    │  FRR, EER)        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Save Model +      │
                    │ Scaler            │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Display Results   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  End Training     │
                    └───────────────────┘
```

### Authentication Phase

```
                    ┌─────────────────────┐
                    │ Start Authentication│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Model Loaded?       │
                    └──────┬──────────┬───┘
                      Yes  │          │ No
                           │     ┌────▼────────────────┐
                           │     │ Error: Train First  │
                           │     └─────────────────────┘
                    ┌──────▼──────────┐
                    │ Select Security │
                    │ Level (L/M/H)   │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ Display 10-Dot  │
                    │ Pattern         │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ Track Mouse     │
                    │ Movements       │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ Extract 13      │
                    │ Features        │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ Enough Samples? │
                    │ (≥ 10)          │
                    └──────┬──────┬───┘
                      Yes  │      │ No
                           │  ┌───▼───────────────────┐
                           │  │ Error: Insufficient   │
                           │  │ Data                  │
                           │  └───────────────────────┘
                    ┌──────▼──────────┐
                    │ Scale Features  │
                    │ (StandardScaler)│
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ Predict with    │
                    │ Ensemble        │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────────────┐
                    │ Calculate Confidence:   │
                    │ • Mean (30%)            │
                    │ • Vote % (25%)          │
                    │ • Median (20%)          │
                    │ • Min (15%)             │
                    │ • Margin (10%)          │
                    └──────┬──────────────────┘
                           │
                    ┌──────▼──────────┐
                    │ Compute Vote    │
                    │ Consistency     │
                    └──────┬──────────┘
                           │
                    ┌──────▼────────────────────┐
                    │ All Checks Pass?          │
                    │ • Confidence ≥ Threshold  │
                    │ • Consistency ≥ Threshold │
                    │ • Min ≥ (Threshold-0.15)  │
                    └──────┬───────────┬────────┘
                      Yes  │           │ No
                           │    ┌──────▼───────────────┐
                           │    │ Calculate Failure    │
                           │    │ Reasons              │
                           │    └──────┬───────────────┘
                           │           │
                           │    ┌──────▼───────────────┐
                           │    │ Show: Model thinks   │
                           │    │ you are [User X]     │
                           │    └──────┬───────────────┘
                           │           │
                    ┌──────▼─────┐  ┌──▼──────────┐
                    │ Identify   │  │ ❌ DENY     │
                    │ User       │  │ ACCESS      │
                    └──────┬─────┘  └─────────────┘
                           │
                    ┌──────▼─────┐
                    │ ✅ GRANT   │
                    │ ACCESS     │
                    └──────┬─────┘
                           │
                    ┌──────▼──────────┐
                    │ Display         │
                    │ Confidence      │
                    │ Details         │
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │ End             │
                    └─────────────────┘
```

### Data Collection Phase

```
                    ┌─────────────────┐
                    │ Start Collection│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Enter Username  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Valid Name?     │
                    └────┬────────┬───┘
                    Yes  │        │ No
                         │   ┌────▼──────────────┐
                         │   │ Error: Enter Name │
                         │   └───────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Session Loop       │
              │  (i = 1 to 4)       │
              └──────────┬──────────┘
                         │
                ┌────────▼─────────┐
                │ Display 10 Random│
                │ Dots on Screen   │
                └────────┬─────────┘
                         │
                ┌────────▼─────────┐
                │ User Follows Dots│
                │ Track Mouse Path │
                └────────┬─────────┘
                         │
                ┌────────▼─────────┐
                │ Extract Features │
                │ (13 per sample)  │
                └────────┬─────────┘
                         │
                ┌────────▼─────────┐
                │ Session < 4?     │
                └────┬────────┬────┘
                Yes  │        │ No
                     │        │
              ┌──────▼─────┐  │
              │ i = i + 1  │  │
              │ (Next      │  │
              │  Session)  │  │
              └──────┬─────┘  │
                     │        │
                     └────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Combine All 4     │
                    │ Sessions          │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Create DataFrame  │
                    │ with User Label   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Append to CSV     │
                    │ (or create new)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Update Metrics    │
                    │ Display           │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Success Message:  │
                    │ "Collected N      │
                    │  samples"         │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ End Collection    │
                    └───────────────────┘
```

---

## 🚀 Installation

### Prerequisites
- Python 3.10+
- Conda (Miniconda or Anaconda)
- Windows OS (current implementation)

### Setup

1. **Clone or download the project:**
   ```bash
   cd "C:\Users\Jonathan\Desktop\AAST\Cyper Physical System\Project"
   ```

2. **The conda environment is already set up at:**
   ```
   C:\Users\Jonathan\Desktop\AAST\Cyper Physical System\Project\mouse
   ```

3. **Run the application:**
   ```bash
   run.bat
   ```

### Dependencies
The environment includes:
- `pandas` - Data manipulation
- `numpy` - Numerical computing
- `scikit-learn 1.7.2` - ML algorithms
- `xgboost` - Gradient boosting (GPU/CPU)
- `imbalanced-learn` - SMOTE for class balancing
- `pyautogui` - Mouse tracking
- `tkinter` - GUI framework
- `joblib` - Model persistence

---

## 💻 Usage

### 1. Data Collection

```python
# In the GUI:
1. Enter username (e.g., "Jonathan")
2. Click "🎯 Collect Training Data (4 Sessions)"
3. Follow the 10 red dots smoothly with your mouse
4. Complete all 4 sessions
5. Repeat for 2-3 more users
```

**Tips for Best Results:**
- ✅ Move smoothly and naturally
- ✅ Use consistent speed
- ✅ Follow curved paths
- ❌ Avoid jerky movements
- ❌ Don't move too fast

### 2. Model Training

```python
# In the GUI:
1. Click "🎓 Train Model"
2. Wait for training to complete (10-30 seconds)
3. Review accuracy metrics and per-user performance
4. Click "💾 Save" to persist the model
```

### 3. Authentication

```python
# In the GUI:
1. Select security level:
   - Low: 40% confidence, 50% consistency
   - Medium: 55% confidence, 65% consistency
   - High: 70% confidence, 80% consistency
   
2. Click "🔓 Authenticate User"
3. Follow the 10 dots naturally
4. System will:
   ✅ Grant access if all checks pass
   ❌ Deny access and show predicted user
```

---

## 🔧 Technical Specifications

### Machine Learning Pipeline

#### Model Architecture
```
Voting Classifier (Soft Voting)
├── XGBoost (Weight: 1.5)
│   ├── Objective: Multi-class softmax
│   ├── Learning Rate: 0.03
│   ├── Estimators: 200
│   ├── Max Depth: 5
│   ├── Regularization: L1=1.0, L2=2.0
│   └── Early Stopping: Enabled
│
└── Random Forest (Weight: 1.0)
    ├── Estimators: 75
    ├── Max Depth: 6
    ├── Class Weight: Balanced
    └── Parallel Jobs: All CPUs
```

#### Data Processing
- **Train/Test Split:** 70/30 stratified
- **Feature Scaling:** StandardScaler (zero mean, unit variance)
- **Class Balancing:** SMOTE when imbalance ratio > 2:1
- **Cross-Validation:** 3-fold stratified

#### Authentication Algorithm
```python
overall_confidence = (
    0.30 × mean_sample_confidence +
    0.25 × vote_consistency +
    0.20 × median_confidence +
    0.15 × min_sample_confidence +
    0.10 × top2_margin
)

authentication_passed = (
    overall_confidence ≥ threshold AND
    vote_consistency ≥ consistency_threshold AND
    min_confidence ≥ (threshold - 0.15)
)
```

---

## 📈 Performance Metrics

### Academic Metrics (for reporting)

| Metric | Formula | Purpose |
|--------|---------|---------|
| **Accuracy** | Correct predictions / Total predictions | Overall system performance |
| **FAR** | False Acceptances / Total Impostor Attempts | Security (lower is better) |
| **FRR** | False Rejections / Total Genuine Attempts | Usability (lower is better) |
| **EER** | Point where FAR = FRR | Overall balance point |

### System Performance Indicators

```
Training Metrics:
├── Training Accuracy: Model fit quality
├── Test Accuracy: Generalization capability
├── Cross-Validation: Stability across folds
└── Overfitting Gap: Train - Test accuracy

Per-User Metrics:
├── Individual Accuracy: User-specific performance
├── Sample Count: Training data per user
└── Pattern Consistency: Speed variation coefficient

Authentication Metrics:
├── Overall Confidence: Weighted multi-metric score
├── Vote Consistency: Prediction agreement %
├── Min Sample Confidence: Worst-case scenario
└── Consistency Score: 1 - (std_dev / 0.3)
```

---

## 📁 Project Structure

```
Project/
├── Mouse-Recognition-FIXED.py    # Main application
├── run.bat                        # Environment launcher
├── README.md                      # This file
├── mouse_features.csv             # Training data
├── mouse_auth_model.pkl           # Saved model (generated)
├── mouse/                         # Conda environment
│   ├── python.exe
│   └── Lib/site-packages/
└── CSV_TEST/                      # Test datasets
    ├── 1/
    └── 4 Person/
```

---

## 🎨 User Interface

### Dark Mode Theme
- Background: `#0f172a` (Dark Navy)
- Cards: `#1e293b` (Dark Slate)
- Primary: `#3b82f6` (Bright Blue)
- Success: `#10b981` (Green)
- Warning: `#f59e0b` (Orange)
- Danger: `#ef4444` (Red)

### Main Sections
1. **Data Collection** - 10-dot pattern tracking
2. **Model Management** - Train/Save/Load
3. **Authentication** - Real-time verification
4. **Security Levels** - Adjustable thresholds
5. **Analytics** - Data quality & performance reports

---

## 🔬 Research Applications

This system demonstrates:
- ✅ Behavioral biometrics feasibility
- ✅ Continuous authentication viability
- ✅ Machine learning for security
- ✅ Real-time pattern recognition
- ✅ Multi-user classification

### Suitable For:
- 🎓 Academic research projects
- 🔐 Secondary authentication layer
- 💻 Workstation access control
- 🏢 Shared computer environments
- 📊 Behavioral analysis studies

---

## 🚧 Limitations & Future Work

### Current Limitations
- Windows-only (PyAutoGUI implementation)
- Requires consistent mouse usage
- Performance varies by user (91% to 2%)
- No click/scroll dynamics captured
- Static 10-dot pattern

### Proposed Enhancements
1. **Multi-Modal Biometrics:** Add keystroke dynamics
2. **Advanced Features:** Click timing, scroll patterns, drag-drop
3. **Adaptive Learning:** Online updates for concept drift
4. **Deep Learning:** LSTM/Transformer for temporal sequences
5. **Privacy:** Differential privacy mechanisms
6. **Cross-Platform:** macOS and Linux support

---

## 👥 Contributors

- **Jonathan** - Project Lead & Development
- **Dr. Hisham** - Academic Supervision
- **Mariam** - Testing & Validation

---

## 📄 License

This project is part of an academic research study for the Cyper Physical Systems course at AAST.

---

## 📞 Support

For questions or issues:
1. Check **Data Quality Report** in the app
2. Review training metrics for accuracy issues
3. Ensure smooth mouse movements during collection
4. Try different security levels (Low for testing)

---

**Built with 💙 using Python, XGBoost, and Scikit-learn**
