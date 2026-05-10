# Mouse Dynamics Authentication System

A machine learning-based biometric authentication system that identifies users through their unique mouse behavior patterns.

## Features

- **Mouse Behavior Recognition**: Uses 25 kinematic features extracted from mouse movements (speed, acceleration, angle changes, click patterns, etc.)
- **Session-Based Authentication**: Builds feature vectors from 40-sample sessions, processed through 4 ordered chunks for robust identification
- **GUI Application**: User-friendly interface for data collection, model training, and real-time authentication testing
- **Dual Authentication Modes**:
  - User-claimed authentication with confidence scoring
  - Role-based authentication for enhanced security
- **Anti-Cheating Audit**: Automated code scan to ensure model integrity without hardcoded biases or synthetic data
- **XGBoost Support**: Optional gradient boosting for improved accuracy (degrades gracefully if not installed)

## Project Structure

```
src/
  ├── MouseAuth.py                 # Main GUI application (entry point)
  ├── shared_session_builder.py    # Shared session vector builder (single source of truth)
  ├── train_improved.py            # Training wrapper/verification script
  └── quick_auth.py                # [Deprecated] Incomplete quick auth interface

data/
  ├── mouse_features.csv           # Raw mouse feature dataset
  ├── *.csv                         # Additional training datasets
  └── sessions/                    # Session data storage

models/
  ├── mouse_auth_model.pkl         # Base trained model
  └── mouse_auth_improved.pkl      # Improved session-level model (if trained)

scripts/
  ├── run.bat                      # Launch main GUI application
  ├── run_gui.bat                  # Alternative launcher
  └── test_gui_ready.bat           # Pre-launch verification

logs/
  └── auth_feedback_log.csv        # Authentication attempt logs

Docs/
  └── *.md                         # Project documentation and guides
```

## Installation

### Prerequisites
- Python 3.7+
- Windows/Linux/macOS

### Step 1: Install Dependencies

Using pip:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install pandas numpy scikit-learn scipy xgboost
```

### Step 2: Prepare Data

Place your mouse feature CSV file in the `data/` directory as `mouse_features.csv`. The CSV should include columns for user identifiers and the 25 base features:
- Kinematic: dx, dy, speed, accel, jerk, angle, angle_change, curvature, dir_change_x, dir_change_y, time_elapsed, speed_variance, speed_std
- Click behavior: click_time, click_duration, pause_before_click
- Path: overshoot_distance, path_efficiency
- Final approach: final_approach_speed_mean, final_approach_speed_std, final_angle_change_mean, final_path_efficiency, final_micro_corrections, hover_time_before_click, final_distance_to_target

## Usage

### Launch GUI Application

**Windows:**
```bash
scripts\run_gui.bat
```

**Command line:**
```bash
python src/MouseAuth.py
```

### Training a Model

1. Launch the application
2. **Data Collection Tab**: Load your CSV dataset (or collect new mouse sessions)
3. **Train Model Tab**: Click "Train Model" to train the RandomForest classifier
4. The trained model is saved to `models/mouse_auth_improved.pkl`

### Authentication Testing

1. Launch the application
2. **Quick Authenticate Tab**: Select a user and collect a mouse session
3. The system returns:
   - **Result**: AUTHENTICATED, UNCERTAIN, or ANOMALY
   - **Confidence Score**: 0-100% (higher = more confident)
   - **Breakdown**: Per-chunk analysis and feature importance

## How It Works

### Feature Extraction
Raw mouse events (position, click, release) are converted into 25 biometric features per sample, capturing:
- Kinematic properties (speed, acceleration, jerk)
- Behavioral patterns (pause before click, path efficiency)
- Fine-grained approach behavior (final 10% of movement to click)

### Session Vectors
- 40 consecutive samples grouped into 4 chunks (10 samples each)
- Global statistics computed for all 25 features
- Per-chunk features for 14 selected movement/approach metrics
- **Total dimensions: 25 global + 4 chunks × 14 chunk-features = 81 features**

### Authentication Logic
- RandomForest classifier trained on user-labeled sessions
- Returns per-user confidence scores
- Aggregates multi-chunk voting for robust decisions
- Detects anomalies (inconsistent behavior) vs. imposters (wrong user)

## Important Notes

⚠️ **Biometric Dataset Privacy**: Raw mouse feature datasets, trained models, logs, and local documentation are **excluded from GitHub** for privacy and size reasons. These are kept locally only and ignored by `.gitignore`.

✅ **Code Integrity**: The codebase is scanned automatically to ensure:
- No user-specific hardcoded thresholds
- No synthetic data generation
- No manual confidence manipulation
- No duplicate training implementations
- Feature consistency between train and auth phases

## Technologies Used

- **Python 3.7+**
- **GUI**: tkinter (standard library)
- **Data Processing**: pandas, numpy
- **Machine Learning**: scikit-learn (RandomForest)
- **Statistics**: scipy
- **Optional**: xgboost (for gradient boosting)

## Development

### Run Pre-Launch Tests
```bash
scripts\test_gui_ready.bat
```

### Verify Code Compiles
```bash
python -m py_compile src/MouseAuth.py
python -m py_compile src/shared_session_builder.py
python -m py_compile src/train_improved.py
```

### Code Structure
- **Single Source of Truth**: Session vector layout is defined once in `shared_session_builder.py` and imported by both training and authentication
- **No Duplicate Logic**: Training and authentication use the same feature builder
- **Modular Design**: Feature extraction, session building, and model training are separated for clarity and testing

## License

This project is provided as-is for educational and research purposes.

## Author

Developed as a Cyber-Physical Systems biometric authentication project.
