# Mouse Dynamics Authentication System

A behavioral biometric authentication system that identifies users through their unique mouse movement patterns using machine learning and session-based analysis.

## Application Preview

![GUI Preview](assets/gui-preview.png)

## Features

- **Behavioral Biometric Authentication**
  - Identifies users through unique mouse movement patterns

- **Session-Based Analysis**
  - Builds robust feature vectors from grouped mouse activity sessions

- **Machine Learning Pipeline**
  - RandomForest-based authentication with optional XGBoost support

- **GUI Application**
  - Desktop interface for data collection, training, and authentication testing

- **Confidence & Anomaly Detection**
  - Detects imposters, inconsistent behavior, and uncertain sessions

- **Anti-Cheating Validation**
  - Includes integrity checks against hardcoded thresholds and synthetic manipulation

## Project Structure

```text
src/
  ├── MouseAuth.py
  ├── shared_session_builder.py
  └── train_improved.py

scripts/
  ├── run.bat
  ├── run_gui.bat
  └── test_gui_ready.bat

assets/
  └── gui-preview.png

data/
models/
logs/
```

## Installation

### Prerequisites

- Python 3.7+
- Windows / Linux / macOS

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install pandas numpy scikit-learn scipy xgboost
```

## Usage

### Launch GUI Application

**Windows**
```bash
scripts\run_gui.bat
```

**Command Line**
```bash
python src/MouseAuth.py
```

## Training Workflow

1. Launch the application
2. Load or collect mouse session data
3. Train the authentication model
4. Save the trained model locally

## Authentication Workflow

1. Launch the application
2. Select a user session
3. Perform authentication analysis
4. Review:
   - Confidence score
   - Session analysis
   - Authentication result

## How It Works

### Feature Extraction

Mouse events are converted into behavioral biometric features such as:

- Speed
- Acceleration
- Jerk
- Angle changes
- Curvature
- Path efficiency
- Click timing behavior
- Final movement approach patterns

### Session Vector Building

- 40 mouse samples are grouped into sessions
- Sessions are divided into ordered chunks
- Global and chunk-level statistics are extracted
- Feature vectors are used for machine learning classification

### Authentication Logic

The system:
- Trains on user-labeled mouse sessions
- Predicts user identity using behavioral patterns
- Detects anomalies and inconsistent behavior
- Aggregates chunk-based voting for stability

## Technologies Used

- Python
- tkinter
- pandas
- numpy
- scikit-learn
- scipy
- xgboost

## Privacy Notice

Biometric datasets, trained models, logs, and local project documentation are excluded from GitHub using `.gitignore` for privacy and repository cleanliness.

## Development

### Run Pre-Launch Tests

```bash
scripts\test_gui_ready.bat
```

### Verify Python Files

```bash
python -m py_compile src/MouseAuth.py
python -m py_compile src/shared_session_builder.py
python -m py_compile src/train_improved.py
```

## Notes

- The project uses a shared session-vector pipeline to keep training and authentication behavior consistent.
- Local datasets and trained models are intentionally not uploaded to GitHub.
- The repository structure was cleaned and reorganized for maintainability and scalability.

## License

Educational and research use only.