# Mouse Dynamics Authentication System - Usage Guide

Complete step-by-step guide for using the incremental enrollment and real-time authentication system.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Step 1: Collect Data](#step-1-collect-data)
5. [Step 2: Enroll Users](#step-2-enroll-users)
6. [Step 3: Authenticate Users](#step-3-authenticate-users)
7. [Performance Targets](#performance-targets)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## System Overview

This system provides **fast incremental enrollment** and **real-time authentication** using mouse dynamics:

| Component | Purpose | Performance Target |
|-----------|---------|-------------------|
| `collect_data_gui.py` | Collect mouse movement sessions | Interactive GUI |
| `feature_extractor.py` | Extract 59 behavioral features | Used by all modules |
| `incremental_enroll.py` | Add new users quickly | **< 15 seconds** |
| `real_time_auth.py` | Authenticate users | **< 1 second** |

**Key Features:**
- 59 biometric features (kinematics, FFT, directional, cognitive latency, etc.)
- No full retraining needed - preserves existing model architecture
- Confidence-based authentication (default 85% threshold)
- Batch authentication with majority voting

---

## Prerequisites

### Required Files
```
Project/
├── mouse_auth_kaggle.pkl      # Pre-trained model (created by advanced_training.py)
├── mouse_features.csv         # Training data (updated during enrollment)
├── feature_extractor.py       # Feature extraction module
├── incremental_enroll.py      # Enrollment script
├── real_time_auth.py          # Authentication script
└── collect_data_gui.py        # Data collection GUI
```

### Python Environment
Activate the `mouse` conda environment:
```powershell
conda activate mouse
```

Verify packages installed:
```powershell
python -c "import numpy, pandas, scipy, sklearn, xgboost; print('All packages OK')"
```

### Initial Model
You need a trained model file `mouse_auth_kaggle.pkl`. Create it by running:
```powershell
python advanced_training.py
```

This trains the initial model on existing users (takes ~10-15 minutes).

---

## Quick Start

**Complete workflow in 3 steps:**

```powershell
# 1. Collect data for new user
python collect_data_gui.py

# 2. Enroll the new user (< 15 seconds)
python incremental_enroll.py --user "Alice" --sessions Alice_session1.csv Alice_session2.csv Alice_session3.csv Alice_session4.csv Alice_session5.csv

# 3. Authenticate a user (< 1 second)
python real_time_auth.py --session test_session.csv --user "Alice"
```

---

## Step 1: Collect Data

### Using the GUI

Run the data collection interface:
```powershell
python collect_data_gui.py
```

**GUI Instructions:**

1. **Enter username** (e.g., "Alice")
2. **Set duration** (default: 45 seconds per session)
3. **Set number of sessions** (recommended: 5 sessions)
4. **Click "▶️ Start Collection"**
5. **Move your mouse naturally** and click the red numbered dots
6. **Wait for timer to reach 0:00**
7. **Repeat** for all sessions (GUI will prompt)
8. **Click "💾 Save All Sessions"** and choose save directory

**Output:**
- `Alice_session1_<timestamp>.csv`
- `Alice_session2_<timestamp>.csv`
- `Alice_session3_<timestamp>.csv`
- `Alice_session4_<timestamp>.csv`
- `Alice_session5_<timestamp>.csv`

**CSV Format:**
```csv
timestamp,x,y,event_type
0.001,245,312,move
0.015,247,314,move
0.032,250,315,down
0.145,250,315,up
...
```

### Best Practices for Data Collection

✅ **Do:**
- Collect at least 5 sessions per user
- Use natural mouse movements
- Include clicks, drags, and scrolling motions
- Collect on the same device/setup as authentication
- Allow 30-60 seconds per session

❌ **Don't:**
- Rush through collection
- Use trackpad if authenticating with mouse (or vice versa)
- Collect while distracted or fatigued
- Use automated scripts to move mouse

---

## Step 2: Enroll Users

### Command-Line Enrollment

Enroll a new user with collected sessions:

```powershell
python incremental_enroll.py --user "Alice" --sessions Alice_session1.csv Alice_session2.csv Alice_session3.csv Alice_session4.csv Alice_session5.csv
```

**Output:**
```
Loading model from: mouse_auth_kaggle.pkl
Current users: ['jonathan', 'user1', 'user2', ...]

Enrolling user: Alice
Processing 5 session(s)...

Extracted features: (1250, 59)
Retraining model with new user...
Training complete!

Saved updated model to: mouse_auth_kaggle.pkl
Backup created: mouse_auth_kaggle_backup_1234567890.pkl

✅ Enrollment complete!
   Time taken: 12.4 seconds
   Target: < 15 seconds
```

### Optional Parameters

Specify custom paths:
```powershell
python incremental_enroll.py ^
    --user "Bob" ^
    --sessions session1.csv session2.csv session3.csv ^
    --model "path/to/model.pkl" ^
    --csv "path/to/training_data.csv"
```

### Using the Python API

```python
from incremental_enroll import IncrementalEnroller

# Initialize
enroller = IncrementalEnroller(
    model_path='mouse_auth_kaggle.pkl',
    csv_path='mouse_features.csv'
)

# Load sessions
import pandas as pd
sessions = [pd.read_csv(f'session{i}.csv') for i in range(1, 6)]

# Enroll user
result = enroller.enroll_user(
    username='Alice',
    sessions_data=sessions,
    csv_path='mouse_features.csv'
)

print(f"Time taken: {result['time_taken']:.2f} seconds")
print(f"Total users: {result['num_users']}")
```

---

## Step 3: Authenticate Users

### Single Session Authentication

Authenticate with one session:

```powershell
python real_time_auth.py --session test_session.csv --user "Alice"
```

**Output (Success):**
```
Loading model: mouse_auth_kaggle.pkl
Enrolled users: 16

Authenticating user: Alice
Session file: test_session.csv

Extracting features... Done (250 samples)
Predicting... Done

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   AUTHENTICATION RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Claimed User: Alice
Decision:     ✅ ACCEPT
Confidence:   92.3%
Predicted:    Alice

Top 5 Candidates:
  1. Alice     - 92.3%
  2. Bob       -  3.1%
  3. Charlie   -  2.4%
  4. David     -  1.2%
  5. Eve       -  0.8%

Processing Time:
  - Feature extraction: 0.12s
  - Prediction:        0.05s
  - Total:             0.17s

✅ Authentication successful!
```

**Output (Failure):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   AUTHENTICATION RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Claimed User: Alice
Decision:     ❌ REJECT
Confidence:   42.1%
Predicted:    Eve

Top 5 Candidates:
  1. Eve       - 42.1%
  2. Bob       - 31.2%
  3. Alice     - 15.3%
  ...

❌ Authentication failed!
```

### Batch Authentication (Multiple Sessions)

Use majority voting for higher accuracy:

```powershell
python real_time_auth.py --sessions test1.csv test2.csv test3.csv --user "Alice"
```

**Output:**
```
Batch Authentication (3 sessions)

Session 1: ACCEPT (Alice, 91.2%)
Session 2: ACCEPT (Alice, 88.7%)
Session 3: ACCEPT (Alice, 93.1%)

Final Decision: ✅ ACCEPT
Confidence: 91.0% (average)
Predicted: Alice
```

### Adjust Confidence Threshold

Default threshold is 85%. Lower for more lenient, higher for stricter:

```powershell
# More lenient (75%)
python real_time_auth.py --session test.csv --user "Alice" --threshold 0.75

# Stricter (95%)
python real_time_auth.py --session test.csv --user "Alice" --threshold 0.95
```

### Using the Python API

```python
from real_time_auth import MouseAuthenticator
import pandas as pd

# Initialize
auth = MouseAuthenticator('mouse_auth_kaggle.pkl')

# Load test session
session_df = pd.read_csv('test_session.csv')

# Authenticate
result = auth.authenticate(
    session_data=session_df,
    claimed_user='Alice',
    threshold=0.85
)

if result['authenticated']:
    print(f"✅ ACCEPTED - {result['confidence']*100:.1f}% confident")
else:
    print(f"❌ REJECTED - Only {result['confidence']*100:.1f}% confident")
    print(f"Predicted user: {result['predicted_user']}")

# Batch mode with multiple sessions
sessions = [pd.read_csv(f'test{i}.csv') for i in range(1, 4)]
batch_result = auth.batch_authenticate(sessions, claimed_user='Alice')
print(f"Final decision: {batch_result['final_decision']}")
```

---

## Performance Targets

### Enrollment Performance

| Metric | Target | Typical |
|--------|--------|---------|
| Enrollment time | < 15 seconds | 8-12 seconds |
| Sessions needed | 5 | 5 |
| Samples per session | 200-300 | ~250 |

**Factors affecting speed:**
- CPU speed (XGBoost retraining)
- Number of existing users (larger dataset = slower)
- Number of sessions provided

### Authentication Performance

| Metric | Target | Typical |
|--------|--------|---------|
| Authentication time | < 1 second | 0.15-0.30 seconds |
| Feature extraction | - | ~0.10 seconds |
| Prediction | - | ~0.05 seconds |

**Breakdown:**
- **Feature extraction:** 0.10s (59 features from raw data)
- **Prediction:** 0.05s (stacking ensemble inference)
- **Total:** ~0.15s (well under 1 second target)

---

## Troubleshooting

### Model Not Found

**Error:**
```
FileNotFoundError: Model file not found: mouse_auth_kaggle.pkl
```

**Solution:**
Train initial model first:
```powershell
python advanced_training.py
```

### User Already Exists

**Error:**
```
ValueError: User 'Alice' already enrolled! (16 users total)
```

**Solution:**
- Use a different username, or
- Remove the user from `mouse_features.csv` and retrain

### Low Confidence

**Issue:**
Authentication keeps rejecting legitimate user (confidence < 85%).

**Solutions:**
1. **Collect more sessions** - 5+ sessions recommended
2. **Lower threshold temporarily:**
   ```powershell
   python real_time_auth.py --session test.csv --user "Alice" --threshold 0.70
   ```
3. **Re-enroll** with better quality data
4. **Use batch mode** (majority voting):
   ```powershell
   python real_time_auth.py --sessions s1.csv s2.csv s3.csv --user "Alice"
   ```

### Slow Enrollment (> 15 seconds)

**Causes:**
- Large existing dataset (many users)
- Slow CPU (XGBoost training)

**Solutions:**
- Use GPU-enabled environment (if available)
- Reduce number of sessions (minimum 3)
- Ensure no other programs using CPU

### CSV Format Errors

**Error:**
```
KeyError: 'timestamp' / 'x' / 'y' / 'event_type'
```

**Solution:**
CSV must have these exact columns:
```csv
timestamp,x,y,event_type
0.001,245,312,move
0.015,247,314,move
...
```

Use the GUI to generate correct format automatically.

---

## API Reference

### FeatureExtractor

```python
from feature_extractor import MouseFeatureExtractor

extractor = MouseFeatureExtractor()

# Extract from session
features = extractor.extract_from_session(
    positions=[(t, x, y), ...],  # List of (timestamp, x, y)
    click_data=[(t, x, y, event), ...]  # List of click events
)
# Returns: np.ndarray of shape (n_samples, 59)

# Get feature names
names = extractor.get_feature_names()
# Returns: List of 59 feature names
```

### IncrementalEnroller

```python
from incremental_enroll import IncrementalEnroller

enroller = IncrementalEnroller(
    model_path='mouse_auth_kaggle.pkl',
    csv_path='mouse_features.csv'
)

result = enroller.enroll_user(
    username='Alice',
    sessions_data=[df1, df2, df3],  # List of pandas DataFrames
    csv_path='mouse_features.csv'
)

# Result dict:
# {
#     'success': True,
#     'username': 'Alice',
#     'num_users': 16,
#     'time_taken': 12.4,
#     'samples_added': 1250
# }
```

### MouseAuthenticator

```python
from real_time_auth import MouseAuthenticator

auth = MouseAuthenticator('mouse_auth_kaggle.pkl')

# Single session
result = auth.authenticate(
    session_data=df,  # pandas DataFrame
    claimed_user='Alice',
    threshold=0.85
)

# Result dict:
# {
#     'authenticated': True,
#     'predicted_user': 'Alice',
#     'confidence': 0.923,
#     'decision': 'ACCEPT',
#     'processing_time': 0.17,
#     'all_probabilities': {'Alice': 0.923, 'Bob': 0.031, ...},
#     'top_5': [('Alice', 0.923), ('Bob', 0.031), ...]
# }

# Batch authentication
batch_result = auth.batch_authenticate(
    sessions_data=[df1, df2, df3],
    claimed_user='Alice',
    threshold=0.85
)

# Batch result includes:
# {
#     'final_decision': 'ACCEPT',
#     'avg_confidence': 0.91,
#     'session_results': [...],
#     'accept_count': 3,
#     'reject_count': 0
# }
```

---

## File Structure

```
Project/
│
├── mouse_auth_kaggle.pkl              # Trained model (pickle)
├── mouse_features.csv                 # Training data (CSV)
│
├── feature_extractor.py               # Feature extraction module
├── incremental_enroll.py              # Enrollment script
├── real_time_auth.py                  # Authentication script
├── collect_data_gui.py                # Data collection GUI
│
├── README_usage.md                    # This file
│
└── data/                              # Collected session CSVs
    ├── Alice_session1.csv
    ├── Alice_session2.csv
    └── ...
```

---

## Model Format

The `mouse_auth_kaggle.pkl` file contains:

```python
{
    'model': StackingClassifier,      # Trained ensemble model
    'scaler': StandardScaler,         # Feature scaler
    'users': ['user1', 'user2', ...], # List of enrolled usernames
    'features': ['avg_velocity', ...] # List of 59 feature names
}
```

**Important:** Always use the API functions to load/save. Don't manually edit the pickle file.

---

## Tips for Best Results

### Data Collection
- ✅ Natural movements - don't try to "game" the system
- ✅ Consistent environment - same device, same mouse
- ✅ 5+ sessions - more data = better accuracy
- ✅ Adequate duration - 30-60 seconds per session

### Enrollment
- ✅ High-quality data - follow collection best practices
- ✅ Unique username - avoid duplicates
- ✅ Multiple sessions - minimum 3, recommended 5+

### Authentication
- ✅ Use batch mode for critical decisions
- ✅ Adjust threshold based on security needs:
  - **High security:** 90-95% threshold
  - **Balanced:** 85% threshold (default)
  - **Convenience:** 75-80% threshold
- ✅ Re-enroll if accuracy degrades over time

---

## Examples

### Complete Workflow Example

```powershell
# 1. Train initial model (one-time setup)
python advanced_training.py

# 2. Collect data for new user "Alice"
python collect_data_gui.py
# (Use GUI to collect 5 sessions, save to data/)

# 3. Enroll Alice
python incremental_enroll.py --user "Alice" --sessions data/Alice_session1.csv data/Alice_session2.csv data/Alice_session3.csv data/Alice_session4.csv data/Alice_session5.csv

# 4. Collect test session
python collect_data_gui.py
# (Collect 1 session, save as Alice_test.csv)

# 5. Authenticate Alice
python real_time_auth.py --session data/Alice_test.csv --user "Alice"

# Expected output: ✅ ACCEPT (confidence > 85%)
```

### Python API Example

```python
import pandas as pd
from incremental_enroll import IncrementalEnroller
from real_time_auth import MouseAuthenticator

# Enroll new user
enroller = IncrementalEnroller()
sessions = [pd.read_csv(f'Alice_session{i}.csv') for i in range(1, 6)]
result = enroller.enroll_user('Alice', sessions, 'mouse_features.csv')
print(f"Enrollment time: {result['time_taken']:.2f}s")

# Authenticate
auth = MouseAuthenticator()
test_session = pd.read_csv('Alice_test.csv')
auth_result = auth.authenticate(test_session, claimed_user='Alice')

if auth_result['authenticated']:
    print(f"✅ Welcome, {auth_result['predicted_user']}!")
else:
    print(f"❌ Access denied. You appear to be {auth_result['predicted_user']}")
```

---

## Support

For issues or questions:
1. Check this guide first
2. Review the troubleshooting section
3. Verify all prerequisites are met
4. Check that model file exists and is valid

**Common issues resolved:** Model not found, CSV format errors, slow performance, low confidence

---

**Last Updated:** 2025-01-15  
**System Version:** 1.0  
**Performance Targets:** Enrollment < 15s, Authentication < 1s
