# 🖱️ Mouse Auth GUI - Quick Reference

## Launch Application

**Option 1: Double-click**
```
run_gui.bat
```

**Option 2: Command line**
```powershell
conda activate mouse
python mouse_auth_app.py
```

---

## GUI Workflow

### ✅ COMPLETE ENROLLMENT WORKFLOW (5 minutes)

```
1. Open GUI → Tab 1: Collect Data
   └─ Enter username: "Professor"
   └─ Sessions: 5
   └─ Duration: 45 seconds
   └─ Click "▶️ Start Collection"
   └─ Move mouse naturally, click dots
   └─ Wait for all 5 sessions
   
2. Auto-switch to Tab 2: Enroll
   └─ User "Professor" auto-selected
   └─ All 5 sessions checked
   └─ Click "➕ Enroll User"
   └─ Wait ~10 seconds
   └─ ✅ Enrollment complete!
   
3. Switch to Tab 3: Authenticate
   └─ Select "Professor" from dropdown
   └─ Click "🎯 Collect Session & Authenticate"
   └─ Move mouse for 30 seconds
   └─ ✅ AUTHENTICATED (96.4%)
```

---

## Tab-by-Tab Guide

### 📊 TAB 1: Collect Data

**Purpose:** Record mouse movement sessions from users

**Steps:**
1. Enter username (e.g., "Alice")
2. Set sessions (5 recommended)
3. Set duration (30-60 seconds)
4. Click "▶️ Start Collection"
5. Move mouse naturally, click numbered dots
6. Repeat for all sessions (auto-advances)
7. Click "➡️ Go to Enroll Tab" when done

**Tips:**
- Use natural mouse movements
- Don't rush - be yourself
- Click the red numbered dots for interactive tasks
- Each session auto-saves to `data/sessions/{username}/`

---

### ➕ TAB 2: Enroll User

**Purpose:** Add new user to authentication system

**Steps:**
1. Click "🔄 Refresh" to see available users
2. Select user from dropdown
3. Check sessions to enroll (or "☑️ Select All")
4. Click "➕ Enroll User"
5. Watch progress bar and log
6. ✅ Success! (should take <15 seconds)

**Requirements:**
- Minimum 3 sessions (5 recommended)
- Model file must exist: `mouse_auth_kaggle.pkl`
- If missing, run: `python advanced_training.py`

**What Happens:**
- Extracts 59 features from sessions
- Adds user to existing model (no full retrain!)
- Creates automatic backup
- Updates model with new user

---

### 🔐 TAB 3: Authenticate

**Purpose:** Verify user identity in real-time

**Two Options:**

**Option A: Collect Live Session**
1. Select user to verify from dropdown
2. Adjust threshold (default 85%)
   - 70-80%: More lenient
   - 85%: Balanced (recommended)
   - 90-95%: Strict
3. Click "🎯 Collect Session & Authenticate"
4. Move mouse for 30 seconds
5. View result (✅ ACCEPT or ❌ REJECT)

**Option B: Load Existing Session**
1. Select user to verify
2. Click "📁 Load Session File"
3. Browse to CSV file
4. View result

**Results Show:**
- ✅ ACCEPT or ❌ REJECT decision
- Confidence percentage
- Top 5 candidate matches
- Processing time (<1 second!)
- Authentication history (last 10)

---

## Menu Bar Functions

### 📁 File Menu

**Load Model**
- Open different model file
- Useful for switching projects

**Backup Model**
- One-click backup
- Creates: `mouse_auth_kaggle_BACKUP_{timestamp}.pkl`
- Always backup before major changes!

**Restore Backup**
- Restore from previous backup
- Useful if enrollment fails

**Exit**
- Close application

---

### 👥 Users Menu

**View All Users**
- Shows enrolled users list
- Displays total count

**Remove User**
- (Not implemented - requires full retrain)

**Export Data**
- Save training CSV to another location

**Import Data**
- (Not implemented)

---

### ❓ Help Menu

**Quick Start Guide**
- Complete workflow instructions
- Best practices

**Troubleshooting**
- Common issues and solutions
- Performance tips

**About**
- System information
- Version details

---

## File Structure Created

```
Project/
├── mouse_auth_app.py           ← Main GUI application
├── run_gui.bat                 ← Double-click launcher
│
├── mouse_auth_kaggle.pkl       ← Trained model
├── mouse_features.csv          ← Training data
│
├── feature_extractor.py        ← Backend (59 features)
├── incremental_enroll.py       ← Backend (enrollment)
├── real_time_auth.py          ← Backend (authentication)
│
└── data/
    └── sessions/
        ├── Professor/
        │   ├── Professor_session_1.csv
        │   ├── Professor_session_2.csv
        │   └── ...
        └── Alice/
            └── ...
```

---

## Keyboard Shortcuts

- **Ctrl+Tab**: Switch between tabs
- **Alt+F4**: Close application
- **F1**: Help (if implemented)

---

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Enrollment | <15 sec | 8-12 sec |
| Authentication | <1 sec | 0.15-0.30 sec |
| Feature Extraction | - | ~0.10 sec |

---

## Troubleshooting

### Model Not Found
**Error:** "Model file not found: mouse_auth_kaggle.pkl"

**Solution:**
```powershell
conda activate mouse
python advanced_training.py
```
Wait 10-15 minutes for training to complete.

---

### User Already Exists
**Error:** "User 'Alice' is already enrolled!"

**Solution:**
- Choose different username, OR
- Use Menu → File → Restore Backup to earlier model

---

### Enrollment Failed
**Error:** Enrollment takes >30 seconds or fails

**Solution:**
1. Check you have ≥3 sessions selected
2. Verify CSV files are valid
3. Restore from backup if model corrupted
4. Try fewer sessions (minimum 3)

---

### Low Authentication Confidence
**Issue:** Legitimate user keeps getting rejected

**Solutions:**
1. **Collect more sessions** (5+ recommended)
2. **Lower threshold** (try 75%)
3. **Re-enroll** with better quality data
4. **Batch authenticate** (collect 3 sessions, majority vote)

---

### GUI Won't Start
**Error:** Import errors or crashes

**Solution:**
```powershell
# Ensure environment is activated
conda activate mouse

# Verify packages
python -c "import tkinter; print('Tkinter OK')"
python -c "import pandas, numpy, sklearn; print('ML packages OK')"

# Check backend files exist
dir feature_extractor.py
dir incremental_enroll.py
dir real_time_auth.py
```

---

## Tips for Best Results

### Data Collection
✅ **Do:**
- Natural mouse movements
- Consistent environment (same device/mouse)
- 5+ sessions per user
- 30-60 seconds per session
- Click interactive dots

❌ **Don't:**
- Rush or fake movements
- Switch input devices
- Collect while distracted
- Use automated scripts

---

### Enrollment
✅ **Do:**
- Use high-quality collected data
- Select 5+ sessions
- Backup model first
- Check enrollment log for errors

❌ **Don't:**
- Enroll with <3 sessions
- Enroll same username twice
- Skip backup for important models

---

### Authentication
✅ **Do:**
- Use same environment as collection
- Adjust threshold based on security needs
- Check authentication history
- Use batch mode for critical decisions

❌ **Don't:**
- Set threshold too high (90%+) initially
- Authenticate with poor quality sessions
- Ignore confidence scores

---

## Security Settings

### Threshold Recommendations

| Use Case | Threshold | False Accept | False Reject |
|----------|-----------|--------------|--------------|
| **High Security** | 90-95% | Very Low | Higher |
| **Balanced** | 85% | Low | Low |
| **Convenience** | 75-80% | Higher | Very Low |

**Default:** 85% (good balance)

---

## Advanced Features

### Batch Authentication
1. Collect 3-5 test sessions
2. Load each one via "📁 Load Session File"
3. Check authentication history
4. Majority vote = final decision

**Example:**
- Session 1: ✅ ACCEPT (92%)
- Session 2: ✅ ACCEPT (88%)
- Session 3: ❌ REJECT (81%)
- **Result:** 2/3 ACCEPT → User verified

---

### Auto-Backup System
- Automatic backup on startup
- Format: `mouse_auth_kaggle_BACKUP_{timestamp}.pkl`
- Location: Project root folder
- Keeps last 5 backups (manual cleanup)

---

### Session Storage
**Location:** `data/sessions/{username}/`

**Format:**
```csv
timestamp,x,y,event_type
0.001,245,312,move
0.015,247,314,move
0.032,250,315,down
0.145,250,315,up
```

**Files:**
- `{username}_session_1.csv`
- `{username}_session_2.csv`
- etc.

---

## Demo Scenarios

### Scenario 1: Enroll Professor (5 min)
```
1. Tab 1: Enter "Professor", 5 sessions, 45s each
2. Collect 5 sessions (move mouse naturally)
3. Auto-switch to Tab 2
4. Click "Enroll User" → Wait 10s
5. ✅ Professor enrolled!
```

### Scenario 2: Quick Authentication (1 min)
```
1. Tab 3: Select "Professor"
2. Click "Collect Session & Authenticate"
3. Move mouse for 30s
4. ✅ AUTHENTICATED (94.7%) in 0.18s
```

### Scenario 3: Disaster Recovery (30 sec)
```
1. Enrollment fails or model corrupted
2. Menu → File → Restore Backup
3. Select recent backup file
4. ✅ Model restored
5. Try enrollment again
```

---

## FAQ

**Q: How many sessions do I need to collect?**
A: Minimum 3, recommended 5 for best accuracy.

**Q: Can I enroll multiple users?**
A: Yes! Enroll as many users as needed. Each enrollment takes ~10 seconds.

**Q: What if authentication fails for legitimate user?**
A: Lower the threshold (try 75-80%) or collect more enrollment sessions.

**Q: Can I use this on different computers?**
A: Yes, but re-enroll on each computer for best results (different mouse/environment).

**Q: How accurate is the system?**
A: Typically 92-96% with 5 sessions and 85% threshold.

**Q: What happens if I close GUI during collection?**
A: Sessions already saved are preserved. Restart and continue.

---

## System Requirements

- **OS:** Windows (tested), macOS, Linux
- **Python:** 3.10+
- **RAM:** 4GB minimum, 8GB recommended
- **CPU:** Any modern CPU (GPU optional for training)
- **Disk:** 500MB for environment + models

---

## Version History

**v1.0** (2025-01-15)
- Initial release
- 3-tab interface
- Auto-backup system
- Real-time authentication
- Incremental enrollment
- 59 biometric features

---

## Support

For issues:
1. Check this guide
2. Try Menu → Help → Troubleshooting
3. Verify all backend files exist
4. Check model file exists

**Common Solutions:**
- Model not found: Run `python advanced_training.py`
- Imports fail: Activate environment `conda activate mouse`
- Low confidence: Collect more sessions or lower threshold

---

**Last Updated:** 2025-01-15  
**Application:** mouse_auth_app.py v1.0  
**Author:** Graduation Project Demo
