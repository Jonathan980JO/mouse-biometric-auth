import tkinter as tk
from tkinter import messagebox, simpledialog
import pandas as pd
import numpy as np
import os
import time
import threading
import pickle
import shutil
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from scipy.stats import entropy, skew, kurtosis
try:
    import xgboost as xgb
except Exception as _e:
    xgb = None
    print(f"Warning: xgboost import failed - XGBoost disabled ({_e})")

# Shared session-builder — single source of truth for the session-vector layout.
# Both training (_train_model) and auth (_build_session_vectors) use it.
from shared_session_builder import (
    BASE_FEATURES        as SHARED_BASE_FEATURES,
    BASE_FEATURE_COUNT   as SHARED_BASE_FEATURE_COUNT,
    CHUNK_FEATURE_COLS   as SHARED_CHUNK_FEATURE_COLS,
    CHUNK_FEATURE_COUNT  as SHARED_CHUNK_FEATURE_COUNT,
    SESSION_SIZE         as SHARED_SESSION_SIZE,
    N_CHUNKS             as SHARED_N_CHUNKS,
    CHUNK_SIZE           as SHARED_CHUNK_SIZE,
    SCHEMA_CHANGE_MESSAGE,
    TOTAL_DIM            as SHARED_TOTAL_DIM,
    build_chunk_features_from_df,
    build_session_vectors_from_array,
    has_legacy_base_schema as shared_has_legacy_base_schema,
    make_feature_names   as shared_make_feature_names,
    session_meta         as shared_session_meta,
    validate_required_columns as shared_validate_required_columns,
    self_check           as shared_self_check,
)


# ===~=========================================================================
# CONFIGURATION
# ============================================================================
DEFAULT_CSV_FILE = "data/mouse_features.csv"
MODEL_FILE = "models/mouse_auth_model.pkl"
# Improved session-level model produced by train_improved.py.
# Loaded automatically at startup if it exists; falls back to MODEL_FILE otherwise.
IMPROVED_MODEL_FILE = "models/mouse_auth_improved.pkl"

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("models", exist_ok=True)

# ==================== AUTHENTICATION CONFIGURATION ====================
# Threshold raised to 65% based on observed behavior ranges:
#   Normal baseline:     avg_confidence 64–75%  (should PASS)
#   Anomaly/confused:    avg_confidence 54–66%  (should FAIL or flag)
# 65% sits at the crossover — normal sessions clear it, anomalous sessions often don't.
# 70% was considered but risks rejecting valid lower-end normal sessions (64–65%).
CONFIDENCE_THRESHOLD = 0.65      # 65% minimum avg confidence for AUTHENTICATED

# Anomaly detection thresholds (based on observed behavior ranges)
VOTE_AGREEMENT_THRESHOLD = 80    # % — below this signals inconsistent/anomalous behavior
STD_DEV_ANOMALY_THRESHOLD = 0.15 # above this signals high variance (unstable behavior)
UNCERTAIN_CONF_FLOOR = 0.55      # minimum avg confidence to reach UNCERTAIN (not ANOMALY)
UNCERTAIN_VOTE_FLOOR = 60        # minimum vote% to reach UNCERTAIN

# Stable-session bypass — generic secondary AUTHENTICATED path.
# If the session shows 100% vote agreement AND low std-dev, the user's
# behavior is clearly stable even if avg confidence sits just below the
# primary 65% threshold (common with multi-class models that spread
# probability mass across many users).  The softer confidence floor
# below is the minimum that still rules out random/uniform predictions.
# No user name is referenced here — the rule is purely signal-based.
STABLE_CONF_FLOOR = 0.55         # must still beat 55% to count as stable-auth
STABLE_VOTE_FLOOR = 100.0        # require perfect vote agreement
STABLE_STD_CEILING = STD_DEV_ANOMALY_THRESHOLD  # same variance guard as main rule

MIN_SAMPLES_FOR_AUTH = 10    # Minimum mouse samples before prediction
CONFUSION_THRESHOLD = 0.10   # Flag user pairs with >10% confusion rate

# Generic exclusion list — users in this list are skipped from active training.
# Edit this list to exclude weak/noisy classes. No model code references names.
# Leave empty [] to include all users that have data.
EXCLUDED_TRAINING_USERS = []   # e.g. ["Shady_Youssry"] to exclude that class
# =====================================================================


# ============================================================================
# ANTI-CHEATING AUDIT
# ============================================================================
def _run_anti_cheating_audit():
    """Scan project code for forbidden biometric shortcuts and print PASS/FAIL."""
    import ast as _ast
    import io as _io
    import re as _re
    import tokenize as _tokenize

    src_paths = [
        os.path.abspath(__file__),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_session_builder.py"),
    ]

    def _read(path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def _code_only(src):
        parts = []
        try:
            tokens = _tokenize.generate_tokens(_io.StringIO(src).readline)
            for token_type, token_text, *_rest in tokens:
                if token_type in (_tokenize.COMMENT, _tokenize.STRING):
                    parts.append(" ")
                else:
                    parts.append(token_text)
                    parts.append(" ")
            return "".join(parts)
        except Exception:
            return src

    raw_sources = []
    code_sources = []
    trees = []
    for path in src_paths:
        try:
            src = _read(path)
            raw_sources.append(src)
            code_sources.append(_code_only(src))
            trees.append(_ast.parse(src))
        except Exception as _e:
            print(f"[AUDIT] Could not read/parse {path}: {_e}")

    scanned_code = "\n".join(code_sources)
    scanned_raw = "\n".join(raw_sources)

    def _has_user_literal_compare():
        for tree in trees:
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Compare):
                    continue
                compare_text = _ast.unparse(node).lower() if hasattr(_ast, "unparse") else ""
                if "user" not in compare_text:
                    continue
                if any(isinstance(comp, _ast.Constant) and isinstance(comp.value, str)
                       for comp in node.comparators):
                    return True
        return False

    try:
        builder_info = shared_self_check(verbose=False)
        feature_parity = bool(
            builder_info.get('dimensions_match')
            and builder_info.get('base_feature_count') == SHARED_BASE_FEATURE_COUNT
            and builder_info.get('expected_dim') == SHARED_TOTAL_DIM
        )
    except Exception:
        feature_parity = False

    checks = {
        "user-specific logic": not _has_user_literal_compare(),
        "hardcoded boosts": _re.search(
            r'(confidence|proba|score)\s*(\+=|-=|\*=)\s*[0-9]', scanned_code, _re.I
        ) is None,
        "manual confidence manipulation": _re.search(
            r'proba\s*\[[^\]]+\]\s*=\s*[0-9]', scanned_code, _re.I
        ) is None,
        "synthetic data": _re.search(
            r'\b(SMOTE|make_classification|np\.random\.normal|augment_minority|generate_synthetic)\b',
            scanned_code,
            _re.I,
        ) is None,
        "role-based logic": _re.search(
            r'\brole\s*=|\bif\s+role\b', scanned_code, _re.I
        ) is None,
        "duplicate hidden train/auth implementations": (
            len(_re.findall(r'\n\s+def\s+_train_model\b', scanned_raw)) <= 1
            and len(_re.findall(r'\n\s+def\s+_build_session_vectors\b', scanned_raw)) <= 1
        ),
        "feature mismatch between train and auth": feature_parity,
    }

    print("[AUDIT] Anti-cheating scan:")
    for label, ok in checks.items():
        print(f"   {label:<45} {'PASS' if ok else 'FAIL'}")
    return checks



# ============================================================================
# FEATURE COLUMNS (25 features per sample - shared raw schema)
# ============================================================================
# Keep the raw schema in lock-step with shared_session_builder.py.
FEATURE_COLUMNS = list(SHARED_BASE_FEATURES)


def extract_fitts_features(positions, target_width=30):
    """Compute simple Fitts' law related features from a trajectory.

    Returns dict with 'fitts_ID', 'throughput', 'fitts_compliance'.
    This is a lightweight, robust implementation that returns zeros
    for small or invalid inputs.
    """
    try:
        positions = np.array(positions, dtype=np.float32)
    except Exception:
        return {'fitts_ID': 0.0, 'throughput': 0.0, 'fitts_compliance': 0.0}

    if len(positions) < 2:
        return {'fitts_ID': 0.0, 'throughput': 0.0, 'fitts_compliance': 0.0}

    dx = np.diff(positions[:, 0])
    dy = np.diff(positions[:, 1])
    distances = np.hypot(dx, dy)
    total_distance = float(np.sum(distances))

    movement_time = float(positions[-1, 2] - positions[0, 2])
    movement_time = max(0.001, movement_time)

    # Fitts' Index of Difficulty (simple approximation)
    try:
        fitts_ID = float(np.log2(total_distance / (target_width + 1e-6) + 1.0)) if total_distance > 0 else 0.0
    except Exception:
        fitts_ID = 0.0

    throughput = total_distance / movement_time if movement_time > 0 else 0.0

    # Compliance metric is expensive; return a conservative default here
    fitts_compliance = 0.0

    return {'fitts_ID': fitts_ID, 'throughput': throughput, 'fitts_compliance': fitts_compliance}


def extract_widget_context(segment_positions, dot_pos, target_width=30, target_height=30):
    """Lightweight widget/context features for a single movement segment.

    Returns: dict with 'target_distance', 'target_precision_required', 'approach_angle', 'overshoot_ratio'
    """
    try:
        seg = np.array(segment_positions, dtype=np.float32)
    except Exception:
        return {'target_distance': 0.0, 'target_precision_required': 0.0, 'approach_angle': 0.0, 'overshoot_ratio': 0.0}

    if len(seg) < 2:
        return {'target_distance': 0.0, 'target_precision_required': 0.0, 'approach_angle': 0.0, 'overshoot_ratio': 0.0}

    target_x, target_y = dot_pos
    mean_x = float(np.mean(seg[:, 0]))
    mean_y = float(np.mean(seg[:, 1]))

    dist = float(np.hypot(mean_x - target_x, mean_y - target_y))
    precision = float((target_width + target_height) / 2.0)

    # Approach angle: angle from first point to last point relative to target
    vx = seg[-1, 0] - seg[0, 0]
    vy = seg[-1, 1] - seg[0, 1]
    approach_angle = float(np.arctan2(vy, vx)) if (vx != 0 or vy != 0) else 0.0

    # Overshoot: proportion of last-point distance that exceeded target distance
    last_dist = float(np.hypot(seg[-1, 0] - target_x, seg[-1, 1] - target_y))
    overshoot_ratio = max(0.0, (last_dist - precision) / (precision + 1e-6))

    return {
        'target_distance': dist,
        'target_precision_required': precision,
        'approach_angle': approach_angle,
        'overshoot_ratio': overshoot_ratio
    }


def _blank_final_approach_features():
    return {
        'final_approach_speed_mean': 0.0,
        'final_approach_speed_std': 0.0,
        'final_angle_change_mean': 0.0,
        'final_path_efficiency': 1.0,
        'final_micro_corrections': 0.0,
        'hover_time_before_click': 0.0,
        'final_distance_to_target': 0.0,
    }


def _angle_deltas(angles):
    """Return wrapped absolute angle deltas in radians."""
    if len(angles) < 2:
        return np.array([], dtype=np.float32)
    deltas = np.diff(angles)
    return np.abs((deltas + np.pi) % (2 * np.pi) - np.pi)


def _event_near_time(events, event_time, tolerance=0.12):
    if not events:
        return None
    best_event = None
    best_delta = float("inf")
    for event in events:
        try:
            delta = abs(float(event.get('time', 0.0)) - float(event_time))
        except Exception:
            continue
        if delta < best_delta:
            best_delta = delta
            best_event = event
    return best_event if best_delta <= tolerance else None


def extract_final_approach_features(segment_positions, dot_pos, click_time,
                                    click_event=None, target_radius=30.0):
    """Extract last-approach control features for one successful target click."""
    try:
        segment = np.array(segment_positions, dtype=np.float32)
    except Exception:
        return _blank_final_approach_features()

    result = _blank_final_approach_features()
    if len(segment) < 2:
        if click_event is not None:
            try:
                result['final_distance_to_target'] = float(np.hypot(
                    float(click_event.get('x', 0.0)) - dot_pos[0],
                    float(click_event.get('y', 0.0)) - dot_pos[1],
                ))
            except Exception:
                pass
        return result

    target_x, target_y = dot_pos
    approach_count = max(3, int(np.ceil(len(segment) * 0.20)))
    approach_count = min(len(segment), approach_count)
    final_segment = segment[-approach_count:]

    final_dx = np.diff(final_segment[:, 0])
    final_dy = np.diff(final_segment[:, 1])
    final_dt = np.diff(final_segment[:, 2])
    final_dt = np.where(final_dt <= 0, 0.02, final_dt)
    final_distances = np.hypot(final_dx, final_dy)
    final_speeds = final_distances / final_dt

    if len(final_speeds) > 0:
        result['final_approach_speed_mean'] = float(np.mean(final_speeds))
        result['final_approach_speed_std'] = float(np.std(final_speeds))

    final_angles = np.arctan2(final_dy, final_dx)
    final_angle_deltas = _angle_deltas(final_angles)
    if len(final_angle_deltas) > 0:
        result['final_angle_change_mean'] = float(np.mean(final_angle_deltas))

    straight_dist = float(np.hypot(
        final_segment[-1, 0] - final_segment[0, 0],
        final_segment[-1, 1] - final_segment[0, 1],
    ))
    actual_path = float(np.sum(final_distances))
    if actual_path > 1e-6:
        result['final_path_efficiency'] = float(np.clip(straight_dist / actual_path, 0.0, 1.0))

    target_distances = np.hypot(final_segment[:, 0] - target_x, final_segment[:, 1] - target_y)
    radial_steps = np.diff(target_distances)
    moving_away_count = int(np.sum(radial_steps > 2.0)) if len(radial_steps) else 0
    angle_instability_count = int(np.sum(final_angle_deltas > np.deg2rad(35))) if len(final_angle_deltas) else 0
    sign_change_count = 0
    if len(final_dx) > 1:
        step_mask = final_distances > 1.0
        x_signs = np.sign(final_dx[step_mask])
        y_signs = np.sign(final_dy[step_mask])
        if len(x_signs) > 1:
            sign_change_count += int(np.sum(x_signs[1:] * x_signs[:-1] < 0))
        if len(y_signs) > 1:
            sign_change_count += int(np.sum(y_signs[1:] * y_signs[:-1] < 0))
    result['final_micro_corrections'] = float(
        moving_away_count + angle_instability_count + sign_change_count
    )

    hover_window = segment[(segment[:, 2] >= click_time - 1.0) & (segment[:, 2] <= click_time)]
    if len(hover_window) >= 2:
        hover_dx = np.diff(hover_window[:, 0])
        hover_dy = np.diff(hover_window[:, 1])
        hover_dt = np.diff(hover_window[:, 2])
        hover_dt = np.where(hover_dt <= 0, 0.02, hover_dt)
        hover_speeds = np.hypot(hover_dx, hover_dy) / hover_dt
        hover_radius = max(float(target_radius) * 2.5, 60.0)
        hover_distances = np.hypot(hover_window[:, 0] - target_x, hover_window[:, 1] - target_y)
        near_target = (hover_distances[:-1] <= hover_radius) & (hover_distances[1:] <= hover_radius)
        slow_near_target = near_target & (hover_speeds <= 60.0)
        result['hover_time_before_click'] = float(np.sum(hover_dt[slow_near_target]))

    if click_event is not None:
        try:
            click_x = float(click_event.get('x', final_segment[-1, 0]))
            click_y = float(click_event.get('y', final_segment[-1, 1]))
            result['final_distance_to_target'] = float(np.hypot(click_x - target_x, click_y - target_y))
        except Exception:
            result['final_distance_to_target'] = float(target_distances[-1])
    else:
        result['final_distance_to_target'] = float(target_distances[-1])

    return result


class MouseRecorder:
    """Simple stub for mouse recording used by some UI paths.

    This minimal implementation collects (x,y,t) events when `record_event`
    is called and exposes `get_events()`.
    """
    def __init__(self):
        self.positions = []  # list of (x, y, t)
        self.click_events = []  # list of dicts {'type','x','y','time'}
        self._running = False
        self._thread = None
        self._window = None
        self._after_id = None
        self._interval_ms = 20

    def start(self, window=None, interval=0.02):
        """Start sampling pointer positions using the Tk `after` loop on the
        main thread (safer than calling Tk from a background thread).
        """
        if self._running:
            return
        self._running = True
        self._window = window
        self._interval_ms = max(1, int(interval * 1000))

        def _sample_once():
            if not self._running:
                return
            try:
                if self._window:
                    x = self._window.winfo_pointerx()
                    y = self._window.winfo_pointery()
                else:
                    # Fallback to default root if available
                    _root = getattr(tk, '_default_root', None)
                    if _root is not None:
                        x = _root.winfo_pointerx()
                        y = _root.winfo_pointery()
                    else:
                        return
                t = time.perf_counter()
                self.positions.append((float(x), float(y), float(t)))
            except Exception:
                pass

            # Schedule next sample
            try:
                if self._window:
                    self._after_id = self._window.after(self._interval_ms, _sample_once)
                else:
                    _root = getattr(tk, '_default_root', None)
                    if _root is not None:
                        self._after_id = _root.after(self._interval_ms, _sample_once)
            except Exception:
                self._after_id = None

        # Kick off the sampling loop on the main thread
        try:
            if self._window:
                self._after_id = self._window.after(0, _sample_once)
            else:
                _root = getattr(tk, '_default_root', None)
                if _root is not None:
                    self._after_id = _root.after(0, _sample_once)
                else:
                    raise RuntimeError("no tk window available")
        except Exception:
            # As a last resort, fall back to a background thread (should be uncommon)
            def _sample_loop_thread():
                while self._running:
                    try:
                        if self._window:
                            x = self._window.winfo_pointerx()
                            y = self._window.winfo_pointery()
                        else:
                            _root = getattr(tk, '_default_root', None)
                            if _root is not None:
                                x = _root.winfo_pointerx()
                                y = _root.winfo_pointery()
                            else:
                                time.sleep(interval)
                                continue
                        t = time.perf_counter()
                        self.positions.append((float(x), float(y), float(t)))
                    except Exception:
                        pass
                    time.sleep(interval)

            self._thread = threading.Thread(target=_sample_loop_thread, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop sampling and return collected positions."""
        self._running = False
        # Cancel any scheduled Tk after callback
        try:
            if self._after_id and self._window:
                self._window.after_cancel(self._after_id)
            elif self._after_id:
                _root = getattr(tk, '_default_root', None)
                if _root is not None:
                    _root.after_cancel(self._after_id)
        except Exception:
            pass

        # Join background thread if it was used
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.1)
        except Exception:
            pass

        return list(self.positions)

    def record_click_event(self, event_type, x, y, t=None):
        if t is None:
            t = time.perf_counter()
        self.click_events.append({'type': event_type, 'x': float(x), 'y': float(y), 'time': float(t)})

    def clear(self):
        self.positions = []
        self.click_events = []


# get_recommendation_for_session() removed — artificial movement patterns are no longer used.
# Both training and authentication now rely on natural, unguided mouse behavior.

def extract_latency_features(positions, click_events):
    """Extract cognitive latency features (Critical for individuality/timing patterns)
    
    Args:
        positions: Array of (x, y, t) positions
        click_events: List of {'type': 'down'/'up', 'x': x, 'y': y, 'time': t}
    
    Returns:
        Dictionary with 4 features:
        - reaction_time: Time between cursor stop and click_down (decision latency)
        - hover_duration: Time spent with velocity < threshold before click
        - double_click_interval: Time between consecutive click_up events
        - click_hold_std: Standard deviation of click durations (consistency)
    """
    if len(positions) < 2 or not click_events:
        return {
            'reaction_time': 0.0,
            'hover_duration': 0.0,
            'double_click_interval': 0.0,
            'click_hold_std': 0.0
        }
    
    positions = np.array(positions, dtype=np.float32)
    
    # Calculate velocities
    dx = np.diff(positions[:, 0])
    dy = np.diff(positions[:, 1])
    dt = np.diff(positions[:, 2])
    dt = np.where(dt == 0, 0.02, dt)
    speeds = np.hypot(dx, dy) / dt
    
    # Separate click events
    down_events = [e for e in click_events if e['type'] == 'down']
    up_events = [e for e in click_events if e['type'] == 'up']
    
    # 1. Reaction time (time from stop to click)
    reaction_times = []
    stop_threshold = 10.0  # pixels/sec
    
    for down_event in down_events:
        click_time = down_event['time']
        
        # Find positions before click
        before_click_mask = positions[:, 2] < click_time
        if np.sum(before_click_mask) < 5:
            continue
        
        before_positions = positions[before_click_mask]
        before_speeds = speeds[:len(before_positions)-1]
        
        # Find last "stop" event (speed < threshold)
        stopped_mask = before_speeds < stop_threshold
        if np.any(stopped_mask):
            # Find last stop index
            stop_indices = np.where(stopped_mask)[0]
            last_stop_idx = stop_indices[-1]
            stop_time = before_positions[last_stop_idx, 2]
            
            reaction_time = click_time - stop_time
            reaction_times.append(max(0.0, reaction_time))
    
    avg_reaction_time = np.mean(reaction_times) if reaction_times else 0.0
    
    # 2. Hover duration (time spent slow before click)
    hover_durations = []
    hover_threshold = 50.0  # pixels/sec
    
    for down_event in down_events:
        click_time = down_event['time']
        
        # Get positions in 0.5s window before click
        time_window = 0.5
        window_mask = (positions[:, 2] >= click_time - time_window) & (positions[:, 2] < click_time)
        
        if np.sum(window_mask) < 2:
            continue
        
        window_positions = positions[window_mask]
        window_dx = np.diff(window_positions[:, 0])
        window_dy = np.diff(window_positions[:, 1])
        window_dt = np.diff(window_positions[:, 2])
        window_dt = np.where(window_dt == 0, 0.02, window_dt)
        window_speeds = np.hypot(window_dx, window_dy) / window_dt
        
        # Calculate time spent hovering (slow movement)
        hovering_mask = window_speeds < hover_threshold
        hover_time = np.sum(window_dt[hovering_mask])
        hover_durations.append(hover_time)
    
    avg_hover_duration = np.mean(hover_durations) if hover_durations else 0.0
    
    # 3. Double-click interval
    double_click_intervals = []
    
    if len(up_events) >= 2:
        for i in range(1, len(up_events)):
            interval = up_events[i]['time'] - up_events[i-1]['time']
            double_click_intervals.append(interval)
    
    avg_double_click_interval = np.mean(double_click_intervals) if double_click_intervals else 0.0
    
    # 4. Click hold consistency (std of click durations)
    click_durations = []
    
    for i in range(min(len(down_events), len(up_events))):
        duration = up_events[i]['time'] - down_events[i]['time']
        click_durations.append(max(0.001, duration))
    
    click_hold_std = np.std(click_durations) if len(click_durations) > 1 else 0.0
    
    return {
        'reaction_time': float(avg_reaction_time),
        'hover_duration': float(avg_hover_duration),
        'double_click_interval': float(avg_double_click_interval),
        'click_hold_std': float(click_hold_std)
    }


def extract_advanced_trajectory(positions):
    """Extract advanced trajectory features (irregularity, entropy, straightness)
    
    Args:
        positions: Array of (x, y, t) positions
    
    Returns:
        Dictionary with 3 features:
        - trajectory_irregularity: Sum of absolute acceleration changes (Jerk metric)
        - movement_entropy: Shannon entropy of speed distribution
        - path_straightness: Euclidean distance / Actual path length
    """
    if len(positions) < 3:
        return {
            'trajectory_irregularity': 0.0,
            'movement_entropy': 0.0,
            'path_straightness': 1.0
        }
    
    positions = np.array(positions, dtype=np.float32)
    
    # Calculate speeds and accelerations
    dx = np.diff(positions[:, 0])
    dy = np.diff(positions[:, 1])
    dt = np.diff(positions[:, 2])
    dt = np.where(dt == 0, 0.02, dt)
    
    distances = np.hypot(dx, dy)
    speeds = distances / dt
    
    # Calculate acceleration
    speed_diff = np.diff(speeds)
    dt_accel = dt[1:]
    accels = speed_diff / dt_accel
    
    # 1. Trajectory irregularity (sum of absolute jerk)
    if len(accels) >= 2:
        accel_changes = np.abs(np.diff(accels))
        trajectory_irregularity = np.sum(accel_changes)
    else:
        trajectory_irregularity = 0.0
    
    # 2. Movement entropy (Shannon entropy of speed distribution)
    if len(speeds) >= 10:
        # Bin speeds into 10 bins
        hist, _ = np.histogram(speeds, bins=10)
        # Normalize to probabilities
        hist_sum = np.sum(hist)
        if hist_sum > 0:
            probabilities = hist / hist_sum
            # Add small epsilon to avoid log(0)
            probabilities = probabilities + 1e-10
            # Calculate Shannon entropy: -sum(p * log2(p))
            movement_entropy = -np.sum(probabilities * np.log2(probabilities))
        else:
            movement_entropy = 0.0
    else:
        movement_entropy = 0.0
    
    # 3. Path straightness (Euclidean / Actual path)
    euclidean_distance = np.hypot(
        positions[-1, 0] - positions[0, 0],
        positions[-1, 1] - positions[0, 1]
    )
    actual_path_length = np.sum(distances)
    
    if actual_path_length > 1e-6:
        path_straightness = euclidean_distance / actual_path_length
        path_straightness = min(1.0, max(0.0, path_straightness))
    else:
        path_straightness = 1.0
    
    return {
        'trajectory_irregularity': float(trajectory_irregularity),
        'movement_entropy': float(movement_entropy),
        'path_straightness': float(path_straightness)
    }


# ============================================================================
# FEATURE EXTRACTION
# ============================================================================
# ============================================================================
# FEATURE EXTRACTION (25-feature raw schema)
# ============================================================================
def extract_features(positions, click_data=None):
    """Extract 25 behavioral biometric raw features from mouse movement data.

    The raw schema is 18 movement/click features plus 7 final-approach
    microbehavior features from the last 15-20% of each successful click path.
    
    click_data: {
        'click_times': [t1, t2, ...],
        'click_events': [{'type': 'down'/'up', 'x': x, 'y': y, 'time': t}, ...],
        'dot_positions': [(x1, y1), (x2, y2), ...]
    }
    """
    if len(positions) < 5:
        return []
    
    positions = np.array(positions, dtype=np.float32)
    n = len(positions)
    
    # Calculate differences
    dx = np.diff(positions[:, 0])
    dy = np.diff(positions[:, 1])
    dt = np.diff(positions[:, 2])
    
    # Prevent division by zero
    dt = np.where(dt == 0, 0.02, dt)
    
    # Calculate speed
    distances = np.hypot(dx, dy)
    speeds = distances / dt
    
    # Calculate acceleration
    speed_diff = np.diff(speeds)
    dt_accel = dt[1:]
    accels = speed_diff / dt_accel
    
    # Calculate jerk
    accel_diff = np.diff(accels)
    dt_jerk = dt[2:]
    jerks = accel_diff / dt_jerk
    
    # Calculate angles
    angles = np.arctan2(dy, dx)
    angle_changes = np.abs(np.diff(angles))
    
    # === GLOBAL ADVANCED FEATURES (computed once per session) ===
    
    # 1. STATISTICAL MOMENTS (skewness, kurtosis)
    global_speed_skew = skew(speeds) if len(speeds) > 3 else 0.0
    global_speed_kurt = kurtosis(speeds) if len(speeds) > 3 else 0.0
    global_accel_skew = skew(accels) if len(accels) > 3 else 0.0
    global_accel_kurt = kurtosis(accels) if len(accels) > 3 else 0.0
    global_jerk_skew = skew(jerks) if len(jerks) > 3 else 0.0
    global_jerk_kurt = kurtosis(jerks) if len(jerks) > 3 else 0.0
    
    # 2. FREQUENCY DOMAIN FEATURES (FFT)
    def extract_top_frequencies(signal, n_top=5):
        """Extract top N dominant frequencies from signal using FFT"""
        if len(signal) < 10:
            return [0.0] * n_top
        
        # Apply FFT
        fft_vals = np.fft.fft(signal)
        fft_freqs = np.fft.fftfreq(len(signal))
        
        # Get magnitude spectrum (only positive frequencies)
        magnitude = np.abs(fft_vals[:len(fft_vals)//2])
        freqs = fft_freqs[:len(fft_freqs)//2]
        
        # Get top N frequencies by magnitude
        top_indices = np.argsort(magnitude)[-n_top:][::-1]
        top_freqs = [abs(freqs[i]) if i < len(freqs) else 0.0 for i in top_indices]
        
        return top_freqs
    
    freq_speed = extract_top_frequencies(speeds, 5)
    freq_accel = extract_top_frequencies(accels, 5)
    
    # 3. MICRO-PAUSE DETECTION
    pause_threshold = 10.0  # pixels/sec
    pause_duration_threshold = 0.1  # seconds
    
    pause_count = 0
    pause_durations = []
    in_pause = False
    pause_start = 0
    
    for i, speed in enumerate(speeds):
        if speed < pause_threshold:
            if not in_pause:
                in_pause = True
                pause_start = i
        else:
            if in_pause:
                pause_duration = sum(dt[pause_start:i])
                if pause_duration >= pause_duration_threshold:
                    pause_count += 1
                    pause_durations.append(pause_duration)
                in_pause = False
    
    global_pause_count = pause_count
    global_pause_mean_duration = np.mean(pause_durations) if pause_durations else 0.0
    
    # 4. DIRECTIONAL HISTOGRAM (8 compass directions)
    # Bin angles into 8 directions: N(90°), NE(45°), E(0°), SE(-45°), S(-90°), SW(-135°), W(±180°), NW(135°)
    dir_bins = np.zeros(8)
    for angle in angles:
        # Convert angle to degrees and normalize to [0, 360)
        deg = np.degrees(angle) % 360
        
        # Assign to bins (each bin is 45 degrees)
        if deg >= 337.5 or deg < 22.5:
            dir_bins[2] += 1  # E
        elif deg >= 22.5 and deg < 67.5:
            dir_bins[1] += 1  # NE
        elif deg >= 67.5 and deg < 112.5:
            dir_bins[0] += 1  # N
        elif deg >= 112.5 and deg < 157.5:
            dir_bins[7] += 1  # NW
        elif deg >= 157.5 and deg < 202.5:
            dir_bins[6] += 1  # W
        elif deg >= 202.5 and deg < 247.5:
            dir_bins[5] += 1  # SW
        elif deg >= 247.5 and deg < 292.5:
            dir_bins[4] += 1  # S
        elif deg >= 292.5 and deg < 337.5:
            dir_bins[3] += 1  # SE
    
    # Normalize to proportions
    total_angles = len(angles) if len(angles) > 0 else 1
    dir_proportions = dir_bins / total_angles
    
    # Extract click data
    click_times = []
    click_diffs = []
    click_durations = []
    pause_times = []
    overshoot_dists = []
    dot_positions = []
    click_events = []  # initialised here so it is always bound even when click_data is None
    down_events = []
    up_events = []
    final_approach_metrics = []
    
    if click_data:
        click_times = click_data.get('click_times', [])
        click_events = click_data.get('click_events', [])
        dot_positions = click_data.get('dot_positions', [])
        
        # Calculate click time differences (time between clicks)
        if len(click_times) > 1:
            for i in range(1, len(click_times)):
                click_diffs.append(click_times[i] - click_times[i-1])
        
        # Calculate click durations (mousedown to mouseup)
        down_events = [e for e in click_events if e['type'] == 'down']
        up_events = [e for e in click_events if e['type'] == 'up']
        
        for i in range(min(len(down_events), len(up_events))):
            duration = up_events[i]['time'] - down_events[i]['time']
            click_durations.append(max(0.01, duration))
        
        # Calculate pause before click
        for i, click_time in enumerate(click_times):
            time_window = 0.3
            mask = (positions[:, 2] >= click_time - time_window) & (positions[:, 2] < click_time)
            recent_positions = positions[mask]
            
            if len(recent_positions) > 5:
                last_positions = recent_positions[-10:]
                movement = 0
                for j in range(1, len(last_positions)):
                    dx_pause = last_positions[j][0] - last_positions[j-1][0]
                    dy_pause = last_positions[j][1] - last_positions[j-1][1]
                    movement += np.hypot(dx_pause, dy_pause)
                
                pause_time = 0.2 if movement < 50 else 0.0
                pause_times.append(pause_time)
            else:
                pause_times.append(0.0)
        
        # Calculate overshoot distance
        for i, dot_pos in enumerate(dot_positions):
            if i < len(click_times):
                click_time = click_times[i]
                time_window = 0.5
                mask = (positions[:, 2] >= click_time - time_window) & \
                       (positions[:, 2] <= click_time + time_window)
                nearby_positions = positions[mask]
                
                if len(nearby_positions) > 0:
                    distances_from_target = []
                    for pos in nearby_positions:
                        dist = np.hypot(pos[0] - dot_pos[0], pos[1] - dot_pos[1])
                        distances_from_target.append(dist)
                    
                    max_dist = max(distances_from_target) if distances_from_target else 0
                    if i < len(down_events):
                        click_x, click_y = down_events[i]['x'], down_events[i]['y']
                        final_dist = np.hypot(click_x - dot_pos[0], click_y - dot_pos[1])
                        overshoot = max(0, max_dist - final_dist - 30)
                        overshoot_dists.append(overshoot)
                    else:
                        overshoot_dists.append(0.0)
                else:
                    overshoot_dists.append(0.0)

        # Calculate final-approach microbehavior per successful click.
        for dot_idx, dot_pos in enumerate(dot_positions):
            if dot_idx >= len(click_times):
                break

            click_time = click_times[dot_idx]
            start_time = positions[0, 2] if dot_idx == 0 else click_times[dot_idx - 1]
            segment_mask = (positions[:, 2] >= start_time) & (positions[:, 2] <= click_time)
            segment_positions = positions[segment_mask]
            click_event = _event_near_time(up_events, click_time)

            final_approach_metrics.append(
                extract_final_approach_features(
                    segment_positions,
                    dot_pos,
                    click_time,
                    click_event=click_event,
                    target_radius=30.0,
                )
            )
    
    # 5. CLICK TIMING ENTROPY
    global_click_timing_entropy = 0.0
    if len(click_diffs) > 2:
        # Create histogram of click intervals
        hist, _ = np.histogram(click_diffs, bins=10)
        # Calculate entropy (add small value to avoid log(0))
        hist_normalized = hist / (np.sum(hist) + 1e-10)
        global_click_timing_entropy = entropy(hist_normalized + 1e-10)
    
    # === NEW STATE-OF-THE-ART FEATURES (extracted once per session) ===
    
    # 6. WIDGET CONTEXT FEATURES (per-click basis, averaged globally)
    widget_context_list = []
    if dot_positions and len(dot_positions) > 0:
        for dot_idx, dot_pos in enumerate(dot_positions):
            # Get positions for this click segment
            if dot_idx < len(click_times):
                # Define time window for this click
                if dot_idx == 0:
                    start_time = positions[0, 2]
                else:
                    start_time = click_times[dot_idx - 1]
                end_time = click_times[dot_idx]
                
                # Extract positions for this segment
                segment_mask = (positions[:, 2] >= start_time) & (positions[:, 2] <= end_time)
                segment_positions = positions[segment_mask]
                
                if len(segment_positions) >= 2:
                    widget_features = extract_widget_context(segment_positions, dot_pos, target_width=30, target_height=30)
                    widget_context_list.append(widget_features)
    
    # Average widget context features across all clicks
    if widget_context_list:
        global_target_distance = np.mean([w['target_distance'] for w in widget_context_list])
        global_target_precision_required = np.mean([w['target_precision_required'] for w in widget_context_list])
        global_approach_angle = np.mean([w['approach_angle'] for w in widget_context_list])
        global_overshoot_ratio = np.mean([w['overshoot_ratio'] for w in widget_context_list])
    else:
        global_target_distance = 0.0
        global_target_precision_required = 0.0
        global_approach_angle = 0.0
        global_overshoot_ratio = 0.0
    
    # 7. FITTS' LAW & EFFICIENCY FEATURES
    fitts_features = extract_fitts_features(positions, target_width=30)
    global_fitts_ID = fitts_features['fitts_ID']
    global_throughput = fitts_features['throughput']
    global_fitts_compliance = fitts_features['fitts_compliance']
    
    # 8. COGNITIVE LATENCY & TIMING FEATURES
    if click_events:
        latency_features = extract_latency_features(positions, click_events)
        global_reaction_time = latency_features['reaction_time']
        global_hover_duration = latency_features['hover_duration']
        global_double_click_interval = latency_features['double_click_interval']
        global_click_hold_std = latency_features['click_hold_std']
    else:
        global_reaction_time = 0.0
        global_hover_duration = 0.0
        global_double_click_interval = 0.0
        global_click_hold_std = 0.0
    
    # 9. ADVANCED TRAJECTORY & ENTROPY FEATURES
    trajectory_features = extract_advanced_trajectory(positions)
    global_trajectory_irregularity = trajectory_features['trajectory_irregularity']
    global_movement_entropy = trajectory_features['movement_entropy']
    global_path_straightness = trajectory_features['path_straightness']
    
    # === BUILD FEATURE VECTORS (one per sample) ===
    features = []
    click_index = 0
    
    for i in range(3, n):
        try:
            # Advance click_index when the current position time passes the next click boundary
            while (click_index + 1 < len(click_times)
                   and positions[i, 2] >= click_times[click_index + 1]):
                click_index += 1
            
            # === BASE MOVEMENT/CLICK FEATURES (1-18) ===
            
            # Basic movement (1-11)
            feat_dx = dx[i-1]
            feat_dy = dy[i-1]
            feat_speed = speeds[i-1]
            feat_accel = accels[i-2] if i-2 < len(accels) else 0
            feat_jerk = jerks[i-3] if i-3 < len(jerks) else 0
            feat_angle = angles[i-1]
            feat_angle_change = angle_changes[i-2] if i-2 < len(angle_changes) else 0
            
            # Curvature
            avg_dist = (distances[i-2] + distances[i-1]) / 2 if i >= 2 else 1
            feat_curvature = feat_angle_change / avg_dist if avg_dist > 0 else 0
            
            # Direction changes
            feat_dir_x = abs(dx[i-1]) - abs(dx[i-2]) if i >= 2 else 0
            feat_dir_y = abs(dy[i-1]) - abs(dy[i-2]) if i >= 2 else 0
            
            # Time
            feat_time = positions[i, 2] - positions[0, 2]
            
            # Speed statistics (12-13)
            window_start = max(0, i-5)
            window_speeds = speeds[window_start:i]
            feat_speed_var = np.var(window_speeds) if len(window_speeds) > 1 else 0
            feat_speed_std = np.std(window_speeds) if len(window_speeds) > 1 else 0
            
            # Click features (14-18)
            feat_click_time = click_diffs[click_index] if click_index < len(click_diffs) else 0
            feat_click_duration = click_durations[click_index] if click_index < len(click_durations) else 0.1
            feat_pause_before_click = pause_times[click_index] if click_index < len(pause_times) else 0.0
            feat_overshoot_distance = overshoot_dists[click_index] if click_index < len(overshoot_dists) else 0.0
            
            # Path efficiency
            if i >= 15:
                start_idx = i - 15
                start_pos = positions[start_idx]
                end_pos = positions[i]
                straight_dist = np.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
                actual_path = np.sum(distances[start_idx:i])
                feat_path_efficiency = straight_dist / actual_path if actual_path > 1 else 1.0
                feat_path_efficiency = min(1.0, max(0.0, feat_path_efficiency))
            else:
                feat_path_efficiency = 1.0
            
            # === SESSION-LEVEL DIAGNOSTIC FEATURES (not part of raw schema) ===
            
            # Statistical moments (19-24)
            feat_speed_skew = global_speed_skew
            feat_speed_kurt = global_speed_kurt
            feat_accel_skew = global_accel_skew
            feat_accel_kurt = global_accel_kurt
            feat_jerk_skew = global_jerk_skew
            feat_jerk_kurt = global_jerk_kurt
            
            # Frequency domain (25-34)
            feat_freq_speed_1 = freq_speed[0]
            feat_freq_speed_2 = freq_speed[1]
            feat_freq_speed_3 = freq_speed[2]
            feat_freq_speed_4 = freq_speed[3]
            feat_freq_speed_5 = freq_speed[4]
            feat_freq_accel_1 = freq_accel[0]
            feat_freq_accel_2 = freq_accel[1]
            feat_freq_accel_3 = freq_accel[2]
            feat_freq_accel_4 = freq_accel[3]
            feat_freq_accel_5 = freq_accel[4]
            
            # Click timing entropy (35)
            feat_click_timing_entropy = global_click_timing_entropy
            
            # Micro-pause (36-37)
            feat_pause_count = global_pause_count
            feat_pause_mean_duration = global_pause_mean_duration
            
            # Directional histogram (38-45)
            feat_dir_N = dir_proportions[0]
            feat_dir_NE = dir_proportions[1]
            feat_dir_E = dir_proportions[2]
            feat_dir_SE = dir_proportions[3]
            feat_dir_S = dir_proportions[4]
            feat_dir_SW = dir_proportions[5]
            feat_dir_W = dir_proportions[6]
            feat_dir_NW = dir_proportions[7]
            
            # Widget context (46-49)
            feat_target_distance = global_target_distance
            feat_target_precision_required = global_target_precision_required
            feat_approach_angle = global_approach_angle
            feat_overshoot_ratio = global_overshoot_ratio
            
            # Fitts' Law & efficiency (50-52)
            feat_fitts_ID = global_fitts_ID
            feat_throughput = global_throughput
            feat_fitts_compliance = global_fitts_compliance
            
            # Cognitive latency (53-56)
            feat_reaction_time = global_reaction_time
            feat_hover_duration = global_hover_duration
            feat_double_click_interval = global_double_click_interval
            feat_click_hold_std = global_click_hold_std
            
            # Advanced trajectory diagnostics
            feat_trajectory_irregularity = global_trajectory_irregularity
            feat_movement_entropy = global_movement_entropy
            feat_path_straightness = global_path_straightness

            if final_approach_metrics:
                metric_idx = int(np.searchsorted(click_times, positions[i, 2], side='left'))
                metric_idx = min(max(metric_idx, 0), len(final_approach_metrics) - 1)
                final_metrics = final_approach_metrics[metric_idx]
            else:
                final_metrics = _blank_final_approach_features()

            feat_final_approach_speed_mean = final_metrics['final_approach_speed_mean']
            feat_final_approach_speed_std = final_metrics['final_approach_speed_std']
            feat_final_angle_change_mean = final_metrics['final_angle_change_mean']
            feat_final_path_efficiency = final_metrics['final_path_efficiency']
            feat_final_micro_corrections = final_metrics['final_micro_corrections']
            feat_hover_time_before_click = final_metrics['hover_time_before_click']
            feat_final_distance_to_target = final_metrics['final_distance_to_target']
            
            # Assemble feature vector — 25 true raw features only.
            features.append([
                feat_dx, feat_dy, feat_speed, feat_accel, feat_jerk, feat_angle,
                feat_angle_change, feat_curvature, feat_dir_x, feat_dir_y,
                feat_time, feat_speed_var, feat_speed_std, feat_click_time,
                feat_click_duration, feat_pause_before_click, feat_overshoot_distance, feat_path_efficiency,
                feat_final_approach_speed_mean, feat_final_approach_speed_std,
                feat_final_angle_change_mean, feat_final_path_efficiency,
                feat_final_micro_corrections, feat_hover_time_before_click,
                feat_final_distance_to_target,
            ])
        except Exception as _feat_err:
            print(f"[FEATURE] Sample {i} skipped due to extraction error: {_feat_err}")
            continue
    
    return features

# ============================================================================
# DOT TRACKING UI
# ============================================================================
class DotTracker:
    def __init__(self, num_dots=10, mode="training"):
        self.num_dots = num_dots
        self.mode = mode
        self.recorder = MouseRecorder()
        self.positions = []
        self.click_times = []  # Track when each dot is clicked
        self.dot_positions = []  # Track dot positions for overshoot calculation
        self.running = True
        
        # Enhanced tracking for new features
        self.dot_metadata = []  # Store size, difficulty, etc. for each dot
        self.cue_times = []  # When gray outline appeared
        self.dot_show_times = []  # When red dot appeared
        self.first_move_times = []  # When mouse started moving
        self.hover_start_times = []  # When mouse slowed down near dot
        self.session_metrics = {  # Track session-level metrics
            'speeds': [],
            'reaction_times': [],
            'pause_counts': [],
            'path_efficiencies': []
        }
        # Show intro instructions once per tracker instance
        self._shown_intro = False
        
    def track(self, parent, session_number=0):
        """Show fullscreen dot tracking interface with pre-click cues and variable dot sizes"""
        # Create fullscreen window
        window = tk.Toplevel(parent)
        window.attributes('-fullscreen', True)
        window.attributes('-topmost', True)
        window.focus_force()
        window.configure(bg='black')
        
        canvas = tk.Canvas(window, bg='black', highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        window.update()  # Ensure window is mapped before starting recorder
        
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        
        # Generate dot positions with metadata (size, difficulty, etc.)
        self.dot_positions = self._generate_positions(screen_w, screen_h)
        
        # Instructions at top — identical for training and auth, no style guidance
        title = f"Click the {self.num_dots} dots naturally"
        canvas.create_text(screen_w//2, 50, text=title, fill='white', font=('Arial', 18, 'bold'))

        # Live consistency reminder (bottom of screen, always visible)
        canvas.create_text(screen_w//2, screen_h - 40,
                           text="Move naturally and consistently",
                           fill='#94a3b8', font=('Arial', 12))
        
        # Real-time metrics display (top-right)
        metrics_text = canvas.create_text(screen_w - 150, 30, 
                                         text="Speed: 0 px/s\nReaction: --",
                                         fill='yellow', font=('Arial', 14), anchor='ne')
        
        dot_index = 0
        dots_clicked = 0
        
        # Tracking variables for current dot
        current_cue_time = None
        current_dot_show_time = None
        current_first_move_time = None
        previous_mouse_pos = None
        movement_started = False
        
        # ID for recurring after callback so we can cancel it on close
        track_after_id = None

        # Start recording (pass window so recorder can sample pointer positions)
        self.recorder.clear()
        self.recorder.start(window)
        
        progress = canvas.create_text(screen_w//2, 100, 
                                     text=f"Progress: {dots_clicked}/{self.num_dots}",
                                     fill='yellow', font=('Arial', 14))
        
        # Placeholder for dot graphics
        cue_circle = None
        dot_circle = None
        
        def show_next_dot():
            """Show pre-click cue, then red dot after delay"""
            nonlocal cue_circle, dot_circle, current_cue_time, current_dot_show_time
            nonlocal movement_started, current_first_move_time, previous_mouse_pos
            
            if dot_index >= self.num_dots:
                return
            
            metadata = self.dot_metadata[dot_index]
            x, y = metadata['position']
            size = metadata['size']
            
            # Reset tracking for this dot
            movement_started = False
            current_first_move_time = None
            try:
                if window.winfo_exists():
                    previous_mouse_pos = (window.winfo_pointerx(), window.winfo_pointery())
                else:
                    return  # Window closed
            except tk.TclError:
                return  # Window destroyed
            
            # STEP 1: Show GRAY CIRCLE OUTLINE (500ms cue)
            current_cue_time = time.perf_counter()
            self.cue_times.append(current_cue_time)
            
            cue_circle = canvas.create_oval(
                x-size-2, y-size-2, x+size+2, y+size+2,
                outline='#666666', width=3, fill=''
            )
            
            # STEP 2: After 500ms, show RED DOT
            def show_red_dot():
                nonlocal dot_circle, current_dot_show_time
                try:
                    # If window was destroyed, skip
                    if not (window.winfo_exists()):
                        return

                    # Remove gray cue
                    try:
                        if cue_circle is not None:
                            canvas.delete(cue_circle)
                    except Exception:
                        pass

                    # Show red dot (size varies based on difficulty)
                    current_dot_show_time = time.perf_counter()
                    self.dot_show_times.append(current_dot_show_time)

                    # Color intensity based on difficulty (hard dots are darker)
                    color = '#FF0000' if metadata.get('difficulty') == 'easy' else '#CC0000'

                    dot_circle = canvas.create_oval(
                        x-size, y-size, x+size, y+size,
                        fill=color, outline=color
                    )
                    window.lift()  # Bring window to front
                    canvas.update()  # Force redraw to ensure visibility
                    window.update()  # Ensure window is updated
                except Exception:
                    # Defensive: ignore any GUI errors if window/canvas gone
                    return
            
            window.after(500, show_red_dot)  # 500ms delay
        
        def track_mouse_movement():
            """Track when mouse starts moving (for first_move_time) and update metrics"""
            nonlocal current_first_move_time, movement_started, previous_mouse_pos, track_after_id, current_dot_show_time

            if not self.running or dot_index >= self.num_dots:
                return

            # Read current pointer position; if the window is gone, stop
            try:
                current_x = window.winfo_pointerx()
                current_y = window.winfo_pointery()
            except tk.TclError:
                return

            # Detect first movement after dot appears
            try:
                if (not movement_started) and (current_dot_show_time is not None):
                    if previous_mouse_pos is not None:
                        distance_moved = np.hypot(current_x - previous_mouse_pos[0],
                                                  current_y - previous_mouse_pos[1])
                        if distance_moved > 5:
                            current_first_move_time = time.perf_counter()
                            movement_started = True
            except Exception:
                # Non-fatal; continue
                pass

            previous_mouse_pos = (current_x, current_y)

            # Update real-time speed metric using recent recorder samples
            try:
                avg_speed = 0
                if len(self.recorder.positions) >= 2:
                    recent_positions = self.recorder.positions[-10:]
                    speeds = []
                    for i in range(1, len(recent_positions)):
                        dx = recent_positions[i][0] - recent_positions[i-1][0]
                        dy = recent_positions[i][1] - recent_positions[i-1][1]
                        dt = recent_positions[i][2] - recent_positions[i-1][2]
                        if dt and dt > 0:
                            speeds.append(np.hypot(dx, dy) / dt)

                    if speeds:
                        avg_speed = int(np.mean(speeds))

                reaction_display = "--"
                if self.session_metrics.get('reaction_times'):
                    try:
                        reaction_display = f"{int(self.session_metrics['reaction_times'][-1] * 1000)}ms"
                    except Exception:
                        reaction_display = "--"

                canvas.itemconfig(metrics_text, text=f"Speed: {avg_speed} px/s\nReaction: {reaction_display}")
                canvas.update()
            except Exception:
                pass

            # Schedule next poll
            try:
                track_after_id = window.after(50, track_mouse_movement)
            except Exception:
                track_after_id = None
        
        def on_mouse_down(event):
            """Record mousedown event"""
            timestamp = time.perf_counter()
            self.recorder.record_click_event('down', event.x, event.y, timestamp)
        
        def on_mouse_up(event):
            """Record mouseup event and check for successful click"""
            nonlocal dot_index, dots_clicked
            
            timestamp = time.perf_counter()
            self.recorder.record_click_event('up', event.x, event.y, timestamp)
            
            # Check if click is near the current dot
            metadata = self.dot_metadata[dot_index]
            x_dot, y_dot = metadata['position']
            size = metadata['size']
            
            distance = np.hypot(event.x - x_dot, event.y - y_dot)
            
            # Click tolerance: dot size + 20px buffer
            if distance <= size + 20:
                # Record successful click time
                self.click_times.append(timestamp)
                
                # Calculate reaction time (click_time - dot_show_time)
                if current_dot_show_time:
                    reaction_time = timestamp - current_dot_show_time
                    self.session_metrics['reaction_times'].append(reaction_time)
                
                # Record first move time
                if current_first_move_time:
                    self.first_move_times.append(current_first_move_time)
                else:
                    self.first_move_times.append(timestamp)  # Instant click
                
                # Calculate hover start time (when mouse slowed down near dot)
                hover_time = self._calculate_hover_start(timestamp, x_dot, y_dot)
                self.hover_start_times.append(hover_time)
                
                # Calculate metrics for this dot
                if len(self.recorder.positions) > 5:
                    # Calculate speed
                    recent_pos = self.recorder.positions[-20:]
                    speeds = []
                    for i in range(1, len(recent_pos)):
                        dx = recent_pos[i][0] - recent_pos[i-1][0]
                        dy = recent_pos[i][1] - recent_pos[i-1][1]
                        dt = recent_pos[i][2] - recent_pos[i-1][2]
                        if dt > 0:
                            speeds.append(np.hypot(dx, dy) / dt)
                    if speeds:
                        self.session_metrics['speeds'].append(np.mean(speeds))
                
                dots_clicked += 1
                canvas.itemconfig(progress, text=f"Progress: {dots_clicked}/{self.num_dots}")
                
                if dots_clicked >= self.num_dots:
                    # Finished - show summary
                    self.positions = self.recorder.stop()
                    self._show_session_summary(window, canvas, screen_w, screen_h)
                else:
                    # Remove current dot and show next
                    if dot_circle:
                        canvas.delete(dot_circle)
                    dot_index += 1
                    show_next_dot()
        
        canvas.bind('<ButtonPress-1>', on_mouse_down)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        
        def on_close():
            self.running = False
            # Cancel the recurring callback if scheduled
            try:
                if track_after_id is not None:
                    window.after_cancel(track_after_id)
            except Exception:
                pass

            self.positions = self.recorder.stop()
            try:
                window.destroy()
            except Exception:
                pass
        
        window.protocol("WM_DELETE_WINDOW", on_close)
        
        # Show introductory instructions for first-time users on the canvas
        intro_shown = False
        if not self._shown_intro and session_number == 0:
            # Unified intro — same for training and auth (no style guidance)
            intro_text = (
                "Dots will appear one at a time. Click each one as it appears.\n\n"
                "Move naturally — there are no special instructions.\n\n"
                "Click anywhere to begin."
            )
            
            # Create text on canvas
            intro_id = canvas.create_text(
                screen_w // 2, screen_h // 2,
                text=intro_text,
                fill='white',
                font=('Arial', 14),
                justify='center',
                width=screen_w - 100
            )
            
            def dismiss_intro(event=None):
                nonlocal intro_shown
                canvas.delete(intro_id)
                canvas.update()
                canvas.unbind('<Button-1>')
                intro_shown = True
                self._shown_intro = True
                # Now start the tracking
                show_next_dot()
                try:
                    track_after_id = window.after(100, track_mouse_movement)
                except Exception:
                    track_after_id = None
            
            canvas.bind('<Button-1>', dismiss_intro)
            intro_shown = False
        else:
            intro_shown = True
        
        if intro_shown:
            # Start tracking and show first dot
            show_next_dot()
            try:
                track_after_id = window.after(100, track_mouse_movement)
            except Exception:
                track_after_id = None
        
        try:
            window.wait_window()
        except tk.TclError:
            # Window was already destroyed, continue
            pass
        
        return self.positions
    
    def _generate_positions(self, w, h):
        """Generate random dot positions with minimum spacing between them.

        All dots use the same size (20px radius) so the task is uniform and
        does not introduce size-based variance between sessions.
        """
        import random
        margin = 120          # keep dots away from screen edges
        min_spacing = 150     # minimum distance between consecutive dots
        dot_size = 20         # uniform radius for all dots

        positions = []
        max_attempts = 200    # safety limit per dot

        for _ in range(self.num_dots):
            for _attempt in range(max_attempts):
                x = random.randint(margin, w - margin)
                y = random.randint(margin, h - margin)
                # Enforce minimum spacing from the previous dot
                if positions:
                    prev = positions[-1]
                    if np.hypot(x - prev[0], y - prev[1]) < min_spacing:
                        continue
                positions.append((x, y))
                break
            else:
                # Fallback: place randomly without spacing constraint
                positions.append((random.randint(margin, w - margin),
                                  random.randint(margin, h - margin)))

        # Build uniform metadata for each dot
        dot_metadata = []
        for i, pos in enumerate(positions):
            if i > 0:
                prev_pos = positions[i - 1]
                distance = np.hypot(pos[0] - prev_pos[0], pos[1] - prev_pos[1])
                width = dot_size * 2
                fitts_ID = np.log2(distance / width + 1.0) if width > 0 else 0
            else:
                fitts_ID = 0
                distance = 0

            dot_metadata.append({
                'position': pos,
                'size': dot_size,
                'difficulty': 'normal',
                'fitts_ID': fitts_ID,
                'distance_from_previous': distance,
                'precision_required': 1.0 / (dot_size * dot_size * 4) if dot_size > 0 else 0
            })
        
        self.dot_metadata = dot_metadata
        return positions
    
    def _calculate_hover_start(self, click_time, target_x, target_y):
        """Calculate when mouse started hovering (slowed down) near target"""
        hover_threshold = 50.0  # pixels/sec
        hover_radius = 100  # pixels from target
        
        # Look backwards from click time
        hover_start = click_time
        
        if len(self.recorder.positions) < 5:
            return hover_start
        
        positions = np.array(self.recorder.positions)
        
        # Find positions near target in last 1 second
        time_window = 1.0
        mask = (positions[:, 2] >= click_time - time_window) & (positions[:, 2] <= click_time)
        recent_positions = positions[mask]
        
        if len(recent_positions) < 2:
            return hover_start
        
        # Calculate speeds
        for i in range(len(recent_positions) - 1, 0, -1):
            # Distance from target
            dist_from_target = np.hypot(
                recent_positions[i, 0] - target_x,
                recent_positions[i, 1] - target_y
            )
            
            # If within hover radius
            if dist_from_target <= hover_radius:
                # Calculate speed
                dx = recent_positions[i, 0] - recent_positions[i-1, 0]
                dy = recent_positions[i, 1] - recent_positions[i-1, 1]
                dt = recent_positions[i, 2] - recent_positions[i-1, 2]
                
                if dt > 0:
                    speed = np.hypot(dx, dy) / dt
                    
                    # If speed is below threshold, this is hover start
                    if speed < hover_threshold:
                        hover_start = recent_positions[i, 2]
                    else:
                        break  # Found where hovering ended (going backwards)
        
        return hover_start
    
    def _show_session_summary(self, window, canvas, screen_w, screen_h):
        """Show post-session summary with metrics"""
        # Clear canvas
        canvas.delete('all')
        canvas.configure(bg='#1a1a2e')
        
        # Calculate summary metrics
        avg_speed = np.mean(self.session_metrics['speeds']) if self.session_metrics['speeds'] else 0
        avg_reaction = np.mean(self.session_metrics['reaction_times']) if self.session_metrics['reaction_times'] else 0
        
        # Calculate pause count
        pause_count = 0
        if len(self.recorder.positions) > 10:
            positions = np.array(self.recorder.positions)
            dx = np.diff(positions[:, 0])
            dy = np.diff(positions[:, 1])
            dt = np.diff(positions[:, 2])
            dt = np.where(dt == 0, 0.02, dt)
            speeds = np.hypot(dx, dy) / dt
            
            # Count pauses (speed < 10 px/s for > 0.1s)
            in_pause = False
            pause_start = 0
            for i, speed in enumerate(speeds):
                if speed < 10:
                    if not in_pause:
                        in_pause = True
                        pause_start = i
                else:
                    if in_pause:
                        pause_duration = sum(dt[pause_start:i])
                        if pause_duration >= 0.1:
                            pause_count += 1
                        in_pause = False
        
        # Calculate path efficiency
        if len(self.recorder.positions) > 2:
            positions = np.array(self.recorder.positions)
            euclidean = np.hypot(
                positions[-1, 0] - positions[0, 0],
                positions[-1, 1] - positions[0, 1]
            )
            dx = np.diff(positions[:, 0])
            dy = np.diff(positions[:, 1])
            actual_path = np.sum(np.hypot(dx, dy))
            path_efficiency = (euclidean / actual_path) if actual_path > 0 else 1.0
        else:
            path_efficiency = 1.0
        
        # ── Consistency feedback ───────────────────────────────────────────────
        # Determine whether movement was stable or varied too much.
        # Use speed_std / avg_speed as a coefficient of variation (CV).
        # CV > 1.5  → unstable  (very high relative variance)
        # CV <= 1.5 → stable
        if avg_speed > 0 and self.session_metrics.get('speeds'):
            speeds_arr = np.array(self.session_metrics['speeds'])
            speed_cv = float(np.std(speeds_arr) / (np.mean(speeds_arr) + 1e-6))
        else:
            speed_cv = 0.0

        if speed_cv <= 1.5:
            consistency_msg = "Your movement was consistent ✅"
            consistency_color = '#10b981'
        else:
            consistency_msg = "Your movement varied too much — try to be more consistent"
            consistency_color = '#f59e0b'
        # ─────────────────────────────────────────────────────────────────────

        # Display summary
        canvas.create_text(screen_w//2, 100,
                          text="Session Complete!",
                          fill='#00d4ff', font=('Arial', 28, 'bold'))

        # Consistency feedback (prominent)
        canvas.create_text(screen_w//2, 160,
                          text=consistency_msg,
                          fill=consistency_color, font=('Arial', 16, 'bold'))

        summary_text = (
            f"\n\nSession Metrics:\n\n"
            f"Average Speed: {int(avg_speed)} px/s\n\n"
            f"Reaction Time: {int(avg_reaction * 1000)} ms\n\n"
            f"Pauses Detected: {pause_count}\n\n"
            f"Path Efficiency: {int(path_efficiency * 100)}%\n\n"
            f"Dots Clicked: {self.num_dots}"
        )

        canvas.create_text(screen_w//2, screen_h//2,
                          text=summary_text,
                          fill='white', font=('Arial', 15), justify='center')
        
        canvas.create_text(screen_w//2, screen_h - 80,
                          text="Click anywhere to continue...",
                          fill='#90EE90', font=('Arial', 14))
        
        def close_summary(event=None):
            try:
                if window.winfo_exists():
                    window.destroy()
            except Exception:
                pass
        
        canvas.bind('<Button-1>', close_summary)
        
        # Auto-close after 8 seconds
        window.after(8000, close_summary)
    
    def get_click_data(self):
        """Return structured click data for feature extraction (ENHANCED)"""
        return {
            'click_times': self.click_times,
            'click_events': self.recorder.click_events,
            'dot_positions': [m['position'] for m in self.dot_metadata],
            # New enhanced data
            'dot_metadata': self.dot_metadata,  # Size, difficulty, Fitts' ID, etc.
            'cue_times': self.cue_times,
            'dot_show_times': self.dot_show_times,
            'first_move_times': self.first_move_times,
            'hover_start_times': self.hover_start_times,
            'session_metrics': self.session_metrics
        }

# ============================================================================
# MAIN APPLICATION
# ============================================================================
class MouseAuthApp:
    def __init__(self, root):
        self.root = root
        root.title("Mouse Biometric Authentication")
        root.geometry("600x800")
        root.configure(bg='#1a1a2e')
        
        # State
        self.model = None
        self.scaler = None
        self.users = []
        self.current_csv = DEFAULT_CSV_FILE
        # Model format: 'improved' (shared session vectors) or 'legacy' (old per-sample)
        self._model_format = 'legacy'
        # Session metadata stored when an improved model is loaded
        self._session_meta = None
        
        # Initialize CSV
        self._init_csv()
        
        # Build UI
        self._build_ui()
        
        # Try to load existing model
        self._try_load_model()
    
    def _init_csv(self):
        """Ensure CSV exists with correct columns"""
        if not os.path.exists(self.current_csv):
            df = pd.DataFrame(columns=FEATURE_COLUMNS + ['user'])
            df.to_csv(self.current_csv, index=False)
            print(f"[CSV] Initialized new schema: {len(FEATURE_COLUMNS)} features + user")
            return

        try:
            header = pd.read_csv(self.current_csv, nrows=0)
            if shared_has_legacy_base_schema(header.columns):
                print(f"[SCHEMA WARNING] {SCHEMA_CHANGE_MESSAGE}")
                print(f"[SCHEMA WARNING] Loaded incompatible CSV: {self.current_csv}")
        except Exception as _e:
            print(f"[CSV] Could not validate schema for {self.current_csv}: {_e}")

    def _schema_error_for_dataframe(self, df):
        """Return a readable schema error string, or empty string when valid."""
        missing = shared_validate_required_columns(df)
        if not missing:
            return ""

        if shared_has_legacy_base_schema(df.columns):
            return (
                f"{SCHEMA_CHANGE_MESSAGE}\n\n"
                f"Missing final-approach columns: {missing}"
            )

        return f"CSV is missing required feature columns: {missing}"

    def _current_csv_schema_error(self):
        try:
            header = pd.read_csv(self.current_csv, nrows=0)
        except Exception as _e:
            return f"Could not read CSV header: {_e}"
        return self._schema_error_for_dataframe(header)
    
    def _build_ui(self):
        """Build the user interface"""
        # Title
        title = tk.Label(self.root, text="🖱️ Mouse Authentication System",
                        font=('Arial', 20, 'bold'), bg='#1a1a2e', fg='#00d4ff')
        title.pack(pady=20)
        
        # Username input
        input_frame = tk.Frame(self.root, bg='#16213e', relief=tk.RAISED, bd=2)
        input_frame.pack(pady=10, padx=20, fill='x')
        
        tk.Label(input_frame, text="Username:", font=('Arial', 12),
                bg='#16213e', fg='white').pack(side=tk.LEFT, padx=10, pady=10)
        
        self.username_entry = tk.Entry(input_frame, font=('Arial', 12), width=20)
        self.username_entry.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg='#1a1a2e')
        btn_frame.pack(pady=20, padx=20, fill='x')
        
        btn_style = {'font': ('Arial', 12, 'bold'), 'width': 25, 'height': 2}
        
        self.collect_btn = tk.Button(btn_frame, text="📊 Collect Training Data",
                                     bg='#10b981', fg='white',
                                     command=self._collect_data, **btn_style)
        self.collect_btn.pack(pady=5)
        
        self.train_btn = tk.Button(btn_frame, text="🤖 Train Model",
                                   bg='#3b82f6', fg='white',
                                   command=self._train_model, **btn_style)
        self.train_btn.pack(pady=5)
        
        self.auth_btn = tk.Button(btn_frame, text="🔍 Authenticate (Auto-Detect Who You Are)",
                                  bg='#10b981', fg='white',
                                  command=self._quick_authenticate, **btn_style)
        self.auth_btn.pack(pady=5)

        self.login_btn = tk.Button(btn_frame, text="🔐 Mouse Login",
                       bg='#06b6d4', fg='white',
                       command=self.open_mouse_login, **btn_style)
        self.login_btn.pack(pady=5)
        
        # Utility buttons
        util_frame = tk.Frame(self.root, bg='#1a1a2e')
        util_frame.pack(pady=10)
        
        small_btn_style = {'font': ('Arial', 9), 'width': 12, 'height': 1}
        
        tk.Button(util_frame, text="💾 Save Model", command=self._save_model,
                 bg='#8b5cf6', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        tk.Button(util_frame, text="📂 Load Model", command=self._load_model,
                 bg='#06b6d4', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        tk.Button(util_frame, text="📋 Show Users", command=self._show_users,
                 bg='#64748b', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        # CSV Management
        csv_frame = tk.Frame(self.root, bg='#1a1a2e')
        csv_frame.pack(pady=5)
        
        tk.Button(csv_frame, text="🔄 Switch CSV", command=self._switch_csv,
                 bg='#f59e0b', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        tk.Button(csv_frame, text="➕ New CSV", command=self._create_csv,
                 bg='#10b981', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        # Deep clean utility
        tk.Button(csv_frame, text="🧹 Deep Clean CSV", command=self._deep_clean_current_csv,
             bg='#06b6d4', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        # User Management
        user_mgmt_frame = tk.Frame(self.root, bg='#1a1a2e')
        user_mgmt_frame.pack(pady=5)
        
        tk.Button(user_mgmt_frame, text="🗑️ Delete User", command=self._delete_user,
                 bg='#ef4444', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        tk.Button(user_mgmt_frame, text="🔄 Merge Users", command=self._merge_users,
                 bg='#8b5cf6', fg='white', **small_btn_style).pack(side=tk.LEFT, padx=3)
        
        # Status
        self.status = tk.Label(self.root, text="✓ Ready", font=('Arial', 11, 'bold'),
                              bg='#1a1a2e', fg='#10b981')
        self.status.pack(pady=20)
        
        # Info panel
        info_frame = tk.Frame(self.root, bg='#16213e', relief=tk.SUNKEN, bd=2)
        info_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        self.info_text = tk.Text(info_frame, height=10, bg='#0f172a', fg='#94a3b8',
                                font=('Consolas', 10), wrap=tk.WORD)
        self.info_text.pack(pady=10, padx=10, fill='both', expand=True)
        
        self._update_info()
    
    def _update_status(self, message, color='#10b981'):
        """Update status message"""
        try:
            if hasattr(self, 'status') and self.status.winfo_exists():
                self.status.config(text=message, fg=color)
                # Only call update if root still exists
                if hasattr(self, 'root') and self.root.winfo_exists():
                    try:
                        self.root.update()
                    except Exception:
                        pass
        except Exception:
            # Widget no longer exists or root destroyed — ignore update
            pass
    
    def _update_info(self):
        """Update info panel"""
        try:
            df = pd.read_csv(self.current_csv)
            user_counts = df['user'].value_counts() if 'user' in df.columns else {}
            schema_error = self._schema_error_for_dataframe(df)
            
            csv_name = os.path.basename(self.current_csv)
            info = f"📁 Dataset: {csv_name}\n"
            info += f"📊 Total Samples: {len(df):,}\n"
            info += f"👥 Users: {len(user_counts)}\n\n"
            
            if len(user_counts) > 0:
                info += "User Data:\n"
                for user, count in user_counts.items():
                    info += f"  • {user}: {count:,} samples\n"

            if schema_error:
                info += "\n⚠️ Schema Warning:\n"
                info += f"{SCHEMA_CHANGE_MESSAGE}\n"
                info += "Old CSV data must be recollected before training this model.\n"
            
            if self.model:
                info += f"\n🤖 Model Status: Trained ✓\n"
                info += f"   Users: {', '.join(self.users)}\n"
            else:
                info += f"\n🤖 Model Status: Not trained\n"
            
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
        except Exception as e:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, f"Error loading data: {e}")
    
    def _collect_data(self):
        """Collect training data for a user"""
        schema_error = self._current_csv_schema_error()
        if schema_error:
            messagebox.showerror(
                "CSV Schema Changed",
                f"{schema_error}\n\nCreate a new CSV before collecting data for the 25-feature model.",
            )
            self._update_status("❌ CSV schema incompatible", "#ef4444")
            return

        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return
        
        # Ask for number of sessions
        response = messagebox.askyesno("Training Sessions",
            "Collect 10 sessions recommended for best accuracy.\n\n"
            "YES = 10 sessions (recommended)\n"
            "NO = 5 sessions (quick training)\n\n"
            "Each session records your natural mouse behavior.")

        num_sessions = 10 if response else 5
        
        all_features = []
        
        for session in range(num_sessions):
            self._update_status(
                f"Session {session+1}/{num_sessions} — click the dots naturally",
                '#f59e0b'
            )
            
            # Brief session prompt — consistency guidance only, no movement style instructions
            messagebox.showinfo(
                f"Session {session+1}/{num_sessions}",
                "Use your normal mouse style.\n"
                "Try to stay consistent between sessions.\n"
                "Avoid exaggerated or unnatural movements.\n\n"
                "Click OK to begin."
            )
            
            tracker = DotTracker(num_dots=25, mode="training")
            positions = tracker.track(self.root, session_number=session)
            
            if len(positions) < 10:
                messagebox.showwarning("Warning", f"Session {session+1} had too few samples. Skipping.")
                continue
            
            # Extract features with enhanced click data
            click_data = tracker.get_click_data()
            features = extract_features(positions, click_data)
            if features and len(features[0]) != len(FEATURE_COLUMNS):
                messagebox.showerror(
                    "Feature Extraction Failed",
                    f"Extractor produced {len(features[0])} features, expected {len(FEATURE_COLUMNS)}.",
                )
                self._update_status("❌ Collection failed", "#ef4444")
                return
            all_features.extend(features)
            
            time.sleep(0.5)  # Brief pause between sessions
        
        if len(all_features) == 0:
            messagebox.showerror("Error", "No data collected!")
            return
        
        # Save to CSV
        df = pd.DataFrame(all_features, columns=FEATURE_COLUMNS)
        df['user'] = username
        
        try:
            if os.path.exists(self.current_csv):
                existing = pd.read_csv(self.current_csv)
                # Fix FutureWarning: only concat if existing has data
                if not existing.empty:
                    df = pd.concat([existing, df], ignore_index=True)
            
            df.to_csv(self.current_csv, index=False)
            
            self._update_status(f"✓ Collected {len(all_features)} samples for {username}", '#10b981')
            messagebox.showinfo("Success",
                f"Great! Collected {len(all_features):,} natural behavior samples for {username}.\n\n"
                f"You completed {num_sessions} natural mouse-behavior sessions.\n\n"
                f"Now you can train the model to recognize your unique mouse behavior!")
            
            self._update_info()
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {e}")
    
    def _train_model(self):
        """Train the IMPROVED session-level model from inside the GUI.

        This is now the ONLY training pipeline.  It:
          * loads rows from self.current_csv
          * applies EXCLUDED_TRAINING_USERS (generic exclusion list, no name logic)
                    * groups rows per user and builds session vectors via the shared
                        session-builder (40-row sessions, 4 ordered chunks)
          * balances classes by random undersampling to the smallest class
          * stratified 80/20 split, StandardScaler
          * RandomizedSearchCV on a relaxed RF space + ExtraTrees -> soft VotingClassifier
          * saves to IMPROVED_MODEL_FILE with full session metadata so auth and
            training stay in lock-step

        Validation gates (graceful, no Tkinter crash):
          * required base columns present
          * enough rows to form at least one session per user
          * at least 2 active users remain after exclusion
                    * X_train / X_test second dimension matches the shared builder
        """
        self._update_status("Training (improved pipeline)...", "#f59e0b")
        try:
            from sklearn.model_selection import RandomizedSearchCV, train_test_split
            from sklearn.ensemble import (
                ExtraTreesClassifier, RandomForestClassifier, VotingClassifier,
            )
            from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
            import time as _time

            # ----- STEP 1: load -------------------------------------------------
            df = pd.read_csv(self.current_csv)

            # ----- STEP 2: validate required columns ----------------------------
            schema_error = self._schema_error_for_dataframe(df)
            if schema_error:
                messagebox.showerror(
                    "CSV Schema Changed",
                    schema_error,
                )
                self._update_status("❌ Training failed", "#ef4444")
                return

            if "user" not in df.columns or df.empty:
                messagebox.showerror("Train Validation Failed", "No training data found!")
                self._update_status("❌ Training failed", "#ef4444")
                return

            print(f"[TRAIN] Base feature count  : {SHARED_BASE_FEATURE_COUNT}")
            print(f"[TRAIN] Chunk feature count : {SHARED_CHUNK_FEATURE_COUNT}")
            print(f"[TRAIN] Session vector dim  : {SHARED_TOTAL_DIM}")

            # ----- STEP 3: exclude noisy users (generic) ------------------------
            if EXCLUDED_TRAINING_USERS:
                excl_mask = df["user"].isin(EXCLUDED_TRAINING_USERS)
                excluded_n = int(excl_mask.sum())
                df = df[~excl_mask].copy()
                print(f"[TRAIN] Excluded users {EXCLUDED_TRAINING_USERS}: "
                      f"{excluded_n} rows removed. Remaining: {len(df)}")

            # ----- STEP 4: build session vectors per user ----------------------
            self._update_status(f"Building {SHARED_TOTAL_DIM}-dim session vectors...", "#f59e0b")
            all_X, all_y = [], []
            per_user_sessions = {}
            for user, group in df.groupby("user", sort=True):
                vecs = build_chunk_features_from_df(group)
                per_user_sessions[user] = len(vecs)
                if len(vecs) == 0:
                    print(f"[TRAIN] Skipped {user}: not enough rows for one session "
                          f"({len(group)} < {SHARED_SESSION_SIZE})")
                    continue
                all_X.append(vecs)
                all_y.extend([user] * len(vecs))

            print("[TRAIN] Sessions per user:")
            for u, n in sorted(per_user_sessions.items()):
                print(f"   {u:<30} {n}")

            active_users = [u for u, n in per_user_sessions.items() if n > 0]
            if len(active_users) < 2:
                messagebox.showerror(
                    "Train Validation Failed",
                    f"Need at least 2 users with >= {SHARED_SESSION_SIZE} rows. "
                    f"Active: {active_users}",
                )
                self._update_status("❌ Training failed", "#ef4444")
                return

            X_all = np.vstack(all_X)
            y_all = np.array(all_y)
            print(f"[TRAIN] Total sessions: {len(y_all)}  |  vector dim: {X_all.shape[1]}")
            if X_all.shape[1] != SHARED_TOTAL_DIM:
                messagebox.showerror(
                    "Train Validation Failed",
                    f"Built vectors have dim {X_all.shape[1]}, expected {SHARED_TOTAL_DIM}",
                )
                self._update_status("❌ Training failed", "#ef4444")
                return

            # ----- STEP 5: balance classes (random undersample) -----------------
            session_counts = pd.Series(y_all).value_counts().sort_index()
            smallest = int(session_counts.min())
            print(f"[TRAIN] Smallest class size: {smallest} -> balancing to that size")
            rng = np.random.RandomState(42)
            parts_X, parts_y = [], []
            for u in np.unique(y_all):
                idx = np.where(y_all == u)[0]
                chosen = rng.choice(idx, size=smallest, replace=False)
                parts_X.append(X_all[chosen])
                parts_y.extend([u] * smallest)
            X_bal = np.vstack(parts_X)
            y_bal = np.array(parts_y)

            # ----- STEP 6: split + scale ----------------------------------------
            X_train, X_test, y_train, y_test = train_test_split(
                X_bal, y_bal, test_size=0.2, random_state=42, stratify=y_bal,
            )
            print(f"[TRAIN] Train: {X_train.shape}  Test: {X_test.shape}")
            if X_train.shape[1] != SHARED_TOTAL_DIM or X_test.shape[1] != SHARED_TOTAL_DIM:
                messagebox.showerror(
                    "Train Validation Failed",
                    f"Train/test dims ({X_train.shape[1]}/{X_test.shape[1]}) "
                    f"!= {SHARED_TOTAL_DIM}",
                )
                self._update_status("❌ Training failed", "#ef4444")
                return

            self.scaler = StandardScaler()
            X_train_s = self.scaler.fit_transform(X_train)
            X_test_s  = self.scaler.transform(X_test)

            # ----- STEP 7: relaxed RF search + ET ensemble ----------------------
            self._update_status("Training ensemble (RF search + ET)...", "#f59e0b")
            t0 = _time.time()

            rf_param_dist = {
                "n_estimators":          [100, 150, 200],
                "max_depth":             [5, 6, 7, 8, 10, None],
                "min_samples_split":     [2, 4, 6, 8],
                "min_samples_leaf":      [1, 2, 3, 4],
                "max_features":          ["sqrt", "log2", 0.4],
                "min_impurity_decrease": [0.0, 1e-5, 1e-4],
            }
            rf_base = RandomForestClassifier(
                random_state=42, n_jobs=-1,
                class_weight="balanced", bootstrap=True,
            )
            rf_search = RandomizedSearchCV(
                rf_base, param_distributions=rf_param_dist,
                n_iter=25, scoring="accuracy", cv=5,
                verbose=0, random_state=42, n_jobs=-1,
            )
            rf_search.fit(X_train_s, y_train)
            best_rf = rf_search.best_estimator_
            best_params = rf_search.best_params_
            print(f"[TRAIN] Best RF params: {best_params}")

            et_model = ExtraTreesClassifier(
                n_estimators=150,
                max_depth=best_params.get("max_depth", 8),
                min_samples_split=max(2, best_params.get("min_samples_split", 4)),
                min_samples_leaf=max(1, best_params.get("min_samples_leaf", 2)),
                max_features="sqrt",
                class_weight="balanced",
                random_state=42, n_jobs=-1,
            )
            self.model = VotingClassifier(
                estimators=[("rf", best_rf), ("et", et_model)],
                voting="soft", weights=[2, 1], n_jobs=-1,
            )
            self.model.fit(X_train_s, y_train)
            train_time = _time.time() - t0

            # ----- STEP 8: evaluate --------------------------------------------
            train_acc = accuracy_score(y_train, self.model.predict(X_train_s))
            test_acc  = accuracy_score(y_test,  self.model.predict(X_test_s))
            gap = train_acc - test_acc
            print(f"[TRAIN] train_acc={train_acc:.4f} test_acc={test_acc:.4f} gap={gap:.4f}")
            print(classification_report(
                y_test, self.model.predict(X_test_s), digits=4, zero_division=0,
            ))

            # Set users from model.classes_ for canonical ordering
            try:
                self.users = list(self.model.classes_)
            except Exception:
                self.users = sorted(active_users)
            self.user_thresholds = {}

            # Mark format and store session meta on the live app instance
            self._model_format = "improved"
            self._session_meta = shared_session_meta()

            # ----- STEP 9: save model in improved format ------------------------
            os.makedirs(os.path.dirname(IMPROVED_MODEL_FILE), exist_ok=True)
            with open(IMPROVED_MODEL_FILE, "wb") as fh:
                pickle.dump(
                    {
                        "model":              self.model,
                        "scaler":             self.scaler,
                        "users":              list(self.model.classes_),
                        "model_format":       "improved",
                        "base_feature_count": SHARED_BASE_FEATURE_COUNT,
                        "session_vector_dim": SHARED_TOTAL_DIM,
                        "feature_names":      shared_make_feature_names(),
                        "session_size":       SHARED_SESSION_SIZE,
                        "chunk_count":        SHARED_N_CHUNKS,
                        "n_chunks":           SHARED_N_CHUNKS,
                        "chunk_size":         SHARED_CHUNK_SIZE,
                        "chunk_feature_names": list(SHARED_CHUNK_FEATURE_COLS),
                        "chunk_feature_cols": list(SHARED_CHUNK_FEATURE_COLS),
                        "base_features":      list(SHARED_BASE_FEATURES),
                        "user_thresholds":    self.user_thresholds,
                    },
                    fh,
                )
            print(f"[TRAIN] Saved improved model -> {IMPROVED_MODEL_FILE}")

            messagebox.showinfo(
                "Training Complete",
                f"Improved pipeline trained successfully.\n\n"
                f"Users           : {len(self.users)}\n"
                f"Sessions total  : {len(y_bal)} (balanced to {smallest}/class)\n"
                f"Base features   : {SHARED_BASE_FEATURE_COUNT}\n"
                f"Vector dim      : {SHARED_TOTAL_DIM}\n"
                f"Train accuracy  : {train_acc:.2%}\n"
                f"Test  accuracy  : {test_acc:.2%}\n"
                f"Gap             : {gap:.2%}\n"
                f"Training time   : {train_time:.1f}s\n"
                f"Saved to        : {IMPROVED_MODEL_FILE}",
            )
            self._update_status(
                f"✅ Trained (improved) - Test {test_acc:.1%} | Gap {gap:.1%}",
                "#10b981",
            )
            self._update_info()

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Error", f"Training failed:\n{e}\n\n{error_details[:400]}")
            self._update_status("❌ Training failed", "#ef4444")
    
    
    def _build_session_vectors(self, features, meta: dict) -> np.ndarray:
        """Convert live feature rows into session-level vectors.

        Delegates to the shared builder which is also used by the GUI training
        path, guaranteeing identical input format between train and auth.

        Accepts list / numpy array / DataFrame.  Always coerces to a numeric
        ndarray first so passing a Python list cannot crash with
        AttributeError: 'list' object has no attribute 'mean'.

        Raises ValueError with a readable message on bad shape / non-numeric
        content; the caller surfaces it via messagebox so Tkinter never crashes.
        """
        return build_session_vectors_from_array(features, meta=meta, debug=True)

    def _quick_authenticate(self, claimed_user=None):
        """Enhanced authentication with detailed results - auto-detect who you are from all users"""
        if self.model is None:
            messagebox.showwarning("Warning", 
                "No model loaded!\n\n"
                "Please train a model first or load an existing one.")
            return
        
        self._update_status("🔍 Authenticating - Move your mouse...", '#f59e0b')
        
        # Collect authentication data
        tracker = DotTracker(num_dots=25, mode="authentication")
        positions = tracker.track(self.root)
        
        if len(positions) < 10:
            messagebox.showerror("Error", "Not enough movement data collected!")
            self._update_status("✗ Failed", '#ef4444')
            return
        
        # Extract features
        click_data = tracker.get_click_data()
        features = extract_features(positions, click_data)

        # ── AUTH VALIDATION (before predict) ───────────────────────────────────
        if features is None or len(features) < 10:
            messagebox.showerror("Error", "Not enough features extracted!")
            self._update_status("✗ Failed", '#ef4444')
            return

        raw_feature_count = len(features[0]) if features and hasattr(features[0], "__len__") else 0
        print(f"[AUTH] Raw feature count produced      : {raw_feature_count}")
        print(f"[AUTH] Expected base feature count    : {SHARED_BASE_FEATURE_COUNT}")
        if raw_feature_count != SHARED_BASE_FEATURE_COUNT:
            messagebox.showerror(
                "Auth Validation Failed",
                f"Extractor produced {raw_feature_count} raw features, expected "
                f"{SHARED_BASE_FEATURE_COUNT}. Retrain/recollect with the current schema.",
            )
            self._update_status("✗ Failed", '#ef4444')
            return

        # Resolve the loaded model's true source path for unambiguous reporting
        loaded_model_path = (
            IMPROVED_MODEL_FILE if self._model_format == 'improved' else MODEL_FILE
        )
        print(f"\n[AUTH] Model path loaded : {loaded_model_path}")
        print(f"[AUTH] Model format      : {self._model_format}")

        if self._model_format == 'improved' and self._session_meta is not None:
            meta = self._session_meta
            try:
                session_vecs = self._build_session_vectors(features, meta)
            except ValueError as _e:
                messagebox.showerror("Auth Validation Failed",
                                     f"Could not build session vectors:\n{_e}")
                self._update_status("✗ Failed", '#ef4444')
                return

            n_sessions   = len(session_vecs)
            produced_dim = session_vecs.shape[1] if n_sessions else 0
            chunk_count = int(meta.get('chunk_count', meta.get('n_chunks', SHARED_N_CHUNKS)))
            chunk_features = list(meta.get('chunk_feature_names', meta.get('chunk_feature_cols', SHARED_CHUNK_FEATURE_COLS)))
            expected_dim = int(meta.get(
                'session_vector_dim',
                len(meta.get('base_features', SHARED_BASE_FEATURES))
                + chunk_count * len(chunk_features)
            ))
            print(f"[AUTH] Session vector dim produced    : {produced_dim}")
            print(f"[AUTH] Expected session vector dim    : {expected_dim}")
            print(f"[AUTH] Session windows built          : {n_sessions}")
            print(f"[AUTH] Raw rows / rows per session    : {len(features)} / {meta['session_size']}")

            # Validate at least one session vector
            if n_sessions == 0:
                messagebox.showerror("Auth Validation Failed",
                                     f"No session vectors produced. Need at least "
                                     f"{meta['session_size']} raw rows for one session.")
                self._update_status("✗ Failed", '#ef4444')
                return

            if produced_dim != expected_dim:
                messagebox.showerror(
                    "Auth Validation Failed",
                    f"Session builder produced {produced_dim} features, expected {expected_dim}. "
                    "Retrain the model from newly recollected data.",
                )
                self._update_status("✗ Failed", '#ef4444')
                return

            # Validate scaler dimension matches produced dimension
            scaler_dim = getattr(self.scaler, 'n_features_in_', produced_dim)
            if scaler_dim != produced_dim:
                messagebox.showerror(
                    "Auth Validation Failed",
                    f"Scaler expects {scaler_dim} features but builder produced "
                    f"{produced_dim}. Retrain the model from the GUI.")
                self._update_status("✗ Failed", '#ef4444')
                return

            try:
                assert self.scaler is not None  # guarded by 'if self.model is None: return' above
                X_test = self.scaler.transform(session_vecs)
            except AssertionError:
                messagebox.showerror("Error", "Scaler not initialised. Train or load a model first.")
                self._update_status("✗ Failed", '#ef4444')
                return
            except Exception as _e:
                messagebox.showerror("Error", f"Session feature scaling failed:\n{_e}")
                self._update_status("✗ Failed", '#ef4444')
                return
        else:
            # Legacy per-sample flow: each of the N rows is predicted independently
            try:
                features = np.asarray(features, dtype=np.float32)
            except Exception as _e:
                messagebox.showerror("Auth Validation Failed",
                                     f"Raw features are not numeric:\n{_e}")
                self._update_status("✗ Failed", '#ef4444')
                return
            expected_dim = len(FEATURE_COLUMNS)
            produced_dim = features.shape[1] if features.ndim == 2 else 0
            n_sessions   = len(features)
            print(f"[AUTH] Raw feature dim expected       : {expected_dim}")
            print(f"[AUTH] Raw feature dim produced       : {produced_dim}")
            print(f"[AUTH] Samples to predict             : {n_sessions}")

            scaler_dim = getattr(self.scaler, 'n_features_in_', produced_dim)
            if scaler_dim != produced_dim:
                messagebox.showerror(
                    "Auth Validation Failed",
                    f"Scaler expects {scaler_dim} features but extractor produced "
                    f"{produced_dim}. Retrain the model from the GUI.")
                self._update_status("✗ Failed", '#ef4444')
                return

            try:
                assert self.scaler is not None  # guarded by 'if self.model is None: return' above
                X_test = self.scaler.transform(features)
            except AssertionError:
                messagebox.showerror("Error", "Scaler not initialised. Train or load a model first.")
                self._update_status("✗ Failed", '#ef4444')
                return
            except Exception as _e:
                messagebox.showerror("Error", f"Feature scaling failed:\n{_e}")
                self._update_status("✗ Failed", '#ef4444')
                return

        # Ensure canonical class ordering at prediction time so indices map to usernames
        try:
            if hasattr(self.model, 'classes_'):
                self.users = list(self.model.classes_)
        except Exception:
            pass

        # Helpful debug logging to diagnose biased decisions
        try:
            print(f"[DEBUG] model.classes_ = {getattr(self.model, 'classes_', None)}")
            print(f"[DEBUG] self.users = {self.users}")
            print(f"[DEBUG] user_thresholds keys = {list(getattr(self, 'user_thresholds', {}).keys())}")
        except Exception:
            pass

        # ==================== PROPER CONFIDENCE-BASED PREDICTION ====================
        # Get ensemble predictions with per-sample confidence threshold
        all_probas = self.model.predict_proba(X_test)  # Shape: (n_samples, n_users)

        CONF_THRESH = CONFIDENCE_THRESHOLD

        predictions = []
        confidences = []
        accepted_flags = []

        print(f"\n{'='*60}")
        print("AUTHENTICATION CONFIDENCE CHECK")
        print(f"{'='*60}")

        for idx, sample_proba in enumerate(all_probas):
            max_confidence = float(sample_proba.max())
            predicted_user_idx = int(sample_proba.argmax())
            predicted_user = self.users[predicted_user_idx]

            # Always record the top prediction and its confidence
            predictions.append(predicted_user)
            confidences.append(max_confidence)

            # Per-user adaptive threshold (fallback to global CONF_THRESH)
            threshold = getattr(self, 'user_thresholds', {}).get(predicted_user, CONF_THRESH)
            accepted = max_confidence >= threshold
            accepted_flags.append(accepted)

            # Print helpful debug info per-sample
            if accepted:
                print(f"Sample {idx+1}: {predicted_user} ({max_confidence:.1%} >= {threshold:.1%}) ✓")
            else:
                # Low-confidence sample — still included in voting but flagged
                # If a claimed_user was provided, show the comparison between
                # the claimed user and the top competitor so output matches
                # the user's expectation (claimed vs actual top prediction).
                if claimed_user is not None and claimed_user in self.users:
                    try:
                        claimed_idx = self.users.index(claimed_user)
                        top_idx = int(sample_proba.argmax())
                        top_user = self.users[top_idx]
                        top_conf = sample_proba[top_idx]
                        claimed_conf = sample_proba[claimed_idx]

                        # If the claimed user is the top prediction, show top two normally
                        if top_idx == claimed_idx:
                            second_idx = sample_proba.argsort()[-2:][::-1][1]
                            second_user = self.users[second_idx]
                            second_conf = sample_proba[second_idx]
                            print(f"Sample {idx+1}: LOW CONFIDENCE ({max_confidence:.1%} < {threshold:.1%})")
                            print(f"  Top candidates: {top_user} ({top_conf:.1%}) vs {second_user} ({second_conf:.1%})")
                        else:
                            # Show claimed user vs top competitor to make intent clear
                            print(f"Sample {idx+1}: LOW CONFIDENCE ({max_confidence:.1%} < {threshold:.1%})")
                            print(f"  Claimed vs Top: {claimed_user} ({claimed_conf:.1%}) vs {top_user} ({top_conf:.1%})")
                    except Exception:
                        # Fallback to generic top-2 display if anything goes wrong
                        top_2_indices = sample_proba.argsort()[-2:][::-1]
                        user1 = self.users[top_2_indices[0]]
                        user2 = self.users[top_2_indices[1]]
                        conf1 = sample_proba[top_2_indices[0]]
                        conf2 = sample_proba[top_2_indices[1]]
                        print(f"Sample {idx+1}: LOW CONFIDENCE ({max_confidence:.1%} < {threshold:.1%})")
                        print(f"  Top candidates: {user1} ({conf1:.1%}) vs {user2} ({conf2:.1%})")
                else:
                    top_2_indices = sample_proba.argsort()[-2:][::-1]
                    user1 = self.users[top_2_indices[0]]
                    user2 = self.users[top_2_indices[1]]
                    conf1 = sample_proba[top_2_indices[0]]
                    conf2 = sample_proba[top_2_indices[1]]
                    print(f"Sample {idx+1}: LOW CONFIDENCE ({max_confidence:.1%} < {threshold:.1%})")
                    print(f"  Top candidates: {user1} ({conf1:.1%}) vs {user2} ({conf2:.1%})")

        print(f"{'='*60}")
        from collections import Counter

        # Total samples in this session (for informative stats)
        total_samples = len(predictions)

        # Prefer counting only high-confidence (accepted) predictions.
        # If there are none, fall back to a confidence-weighted sum across all samples.
        accepted_predictions = [p for p, a in zip(predictions, accepted_flags) if a]

        if accepted_predictions:
            vote_counts = Counter(accepted_predictions)
            total_votes = sum(vote_counts.values())
            top_candidates = vote_counts.most_common(3)
        else:
            # No high-confidence per-sample predictions — use weighted voting by summing
            # model probabilities per user across all samples (more robust than raw argmax counts)
            weighted = {u: 0.0 for u in self.users}
            for proba in all_probas:
                for ui, u in enumerate(self.users):
                    weighted[u] += float(proba[ui])
            vote_counts = Counter(weighted)
            total_votes = sum(weighted.values()) if weighted else 0.0
            top_candidates = vote_counts.most_common(3)

        # Determine winner by selected voting method
        if len(top_candidates) == 0 or total_votes == 0:
            messagebox.showerror("Error", "No reliable predictions made during session!")
            self._update_status("✗ Failed", '#ef4444')
            return

        winner_user, winner_votes = top_candidates[0]
        vote_percentage = (winner_votes / float(total_votes)) * 100

        # Average confidence for the winner across all samples where it was predicted
        winner_confidences = [conf for pred, conf in zip(predictions, confidences) if pred == winner_user]
        avg_confidence = np.mean(winner_confidences) if winner_confidences else 0

        # Calculate detailed metrics across all samples for display
        # NOTE: these are the winner user's probability on ALL samples (not per-sample max).
        # Use distinct variable names to avoid shadowing the per-sample loop's max_confidence.
        all_probs = all_probas
        winner_idx = self.users.index(winner_user)
        winner_prob_slice = [float(proba[winner_idx]) for proba in all_probs]
        display_min_confidence = np.min(winner_prob_slice)
        display_max_confidence = np.max(winner_prob_slice)
        display_std_confidence = np.std(winner_prob_slice)

        # Debug: print raw probability distribution to expose flat/constant model output
        print(f"[PROBA DIST] winner={winner_user} | "
              f"min={display_min_confidence:.4f} max={display_max_confidence:.4f} "
              f"std={display_std_confidence:.4f} mean={np.mean(winner_prob_slice):.4f}")

        # Build detailed results window
        result_window = tk.Toplevel(self.root)
        result_window.title("Authentication Results")
        result_window.geometry("600x700")
        result_window.configure(bg='#1a1a2e')

        # ==================== BEHAVIORAL ANOMALY DETECTION — DECISION LAYER ====================
        # Three-state system based on observed behavior ranges:
        #   Normal baseline:   avg_confidence 64–75%, high vote agreement, low std dev
        #   Anomaly/confused:  avg_confidence 54–66%, lower agreement, higher std dev
        #
        # Decision flow:
        #   1. If claimed_user is provided and doesn't match winner → ANOMALY
        #   2. If vote_agreement < 80% OR std_dev > 0.15           → ANOMALY
        #   3. If avg_confidence >= 65% AND vote_agreement >= 80% AND std_dev <= 0.15 → AUTHENTICATED
        #   3b. If vote_agreement == 100% AND std_dev <= 0.15 AND avg_confidence >= 55% → AUTHENTICATED
        #       (stable-session bypass: perfect agreement + low variance overrides the strict 65% floor)
        #   4. If avg_confidence >= 55% AND vote_agreement >= 60%  → UNCERTAIN
        #   5. Otherwise                                            → ANOMALY
        # ========================================================================================

        # Compute vote fraction and margin
        top_two = vote_counts.most_common(2)
        second_votes = top_two[1][1] if len(top_two) >= 2 else 0
        winner_frac = winner_votes / float(total_samples)
        winner_margin = (winner_votes - second_votes) / float(total_samples)

        # Core signals used in every branch (explicit for explainability)
        vote_agreement = vote_percentage          # % of votes going to the winner
        std_dev = display_std_confidence          # confidence variance across samples

        # Anomaly signals
        low_agreement = vote_agreement < VOTE_AGREEMENT_THRESHOLD   # < 80%
        high_variance = std_dev > STD_DEV_ANOMALY_THRESHOLD          # > 0.15

        # Debug log — full picture of every signal
        print(f"[DECISION] winner={winner_user}, avg_conf={avg_confidence*100:.1f}%, "
              f"vote_agreement={vote_agreement:.1f}%, std_dev={std_dev*100:.1f}%, "
              f"low_agreement={low_agreement}, high_variance={high_variance}")

        # ---- Decision rules ----

        # Rule 0: claimed identity mismatch
        if claimed_user is not None and winner_user != claimed_user:
            decision = "ANOMALY"
            decision_reason = f"Predicted {winner_user}, but user claimed {claimed_user}"

        # Rule 1: anomaly signals present (low agreement OR high variance)
        elif low_agreement or high_variance:
            decision = "ANOMALY"
            signals = []
            if low_agreement:
                signals.append(f"vote agreement {vote_agreement:.0f}% < {VOTE_AGREEMENT_THRESHOLD}%")
            if high_variance:
                signals.append(f"std dev {std_dev*100:.1f}% > {STD_DEV_ANOMALY_THRESHOLD*100:.0f}%")
            decision_reason = "Anomaly signals detected: " + "; ".join(signals)

        # Rule 2: all criteria met — strong confident match
        elif (avg_confidence >= CONFIDENCE_THRESHOLD
              and vote_agreement >= VOTE_AGREEMENT_THRESHOLD
              and std_dev <= STD_DEV_ANOMALY_THRESHOLD):
            decision = "AUTHENTICATED"
            decision_reason = (f"High confidence ({avg_confidence*100:.1f}% ≥ {int(CONFIDENCE_THRESHOLD*100)}%), "
                               f"high agreement ({vote_agreement:.0f}% ≥ {VOTE_AGREEMENT_THRESHOLD}%), "
                               f"low variance ({std_dev*100:.1f}% ≤ {STD_DEV_ANOMALY_THRESHOLD*100:.0f}%)")

        # Rule 2b: stable-session bypass — perfect agreement + low variance + adequate confidence.
        # Justification: with 100% vote agreement and low std-dev the predicted class is
        # unambiguous and the session is clearly stable. In multi-class models probability
        # mass is shared across N classes, so the per-class probability is naturally lower
        # than in a binary model. A slightly-below-65% avg confidence in that context is
        # not a sign of uncertainty — it is a model-calibration artifact.
        # This rule is purely signal-based; no user name is evaluated here.
        elif (vote_agreement >= STABLE_VOTE_FLOOR
              and std_dev <= STABLE_STD_CEILING
              and avg_confidence >= STABLE_CONF_FLOOR):
            decision = "AUTHENTICATED"
            decision_reason = (f"Stable-session bypass: perfect agreement ({vote_agreement:.0f}%), "
                               f"low variance ({std_dev*100:.1f}% ≤ {STABLE_STD_CEILING*100:.0f}%), "
                               f"adequate confidence ({avg_confidence*100:.1f}% ≥ {int(STABLE_CONF_FLOOR*100)}%)")

        # Rule 3: borderline — moderate confidence and agreement
        elif avg_confidence >= UNCERTAIN_CONF_FLOOR and vote_agreement >= UNCERTAIN_VOTE_FLOOR:
            decision = "UNCERTAIN"
            decision_reason = (f"Moderate confidence ({avg_confidence*100:.1f}%) or agreement "
                               f"({vote_agreement:.0f}%) — borderline behavior")

        # Rule 4: everything else falls through to anomaly
        else:
            decision = "ANOMALY"
            decision_reason = (f"Insufficient confidence ({avg_confidence*100:.1f}% < {int(UNCERTAIN_CONF_FLOOR*100)}%) "
                               f"or agreement ({vote_agreement:.0f}% < {UNCERTAIN_VOTE_FLOOR}%)")

        print(f"[DECISION] → {decision}: {decision_reason}")

        # ---- Map decision to UI texts ----
        if decision == "AUTHENTICATED":
            title_text = "✅ AUTHENTICATED"
            title_color = "#10b981"
            result_text = f"AUTHENTICATED — {winner_user}"
            interp = (f"{decision_reason}.\n\n"
                      f"Behavior matches stored profile for {winner_user}.\n"
                      f"• Avg confidence:  {avg_confidence*100:.1f}%\n"
                      f"• Vote agreement:  {vote_agreement:.0f}%\n"
                      f"• Std deviation:   {std_dev*100:.1f}%")
            interp_color = '#10b981'

        elif decision == "UNCERTAIN":
            title_text = "⚠️ UNCERTAIN — Borderline Behavior"
            title_color = "#f59e0b"
            result_text = f"UNCERTAIN — Likely {winner_user}"
            interp = (f"{decision_reason}.\n\n"
                      f"Behavior partially matches {winner_user} but confidence is low.\n"
                      f"• Avg confidence:  {avg_confidence*100:.1f}%  (need ≥ {int(CONFIDENCE_THRESHOLD*100)}% for full auth)\n"
                      f"• Vote agreement:  {vote_agreement:.0f}%\n"
                      f"• Std deviation:   {std_dev*100:.1f}%\n\n"
                      "Consider collecting more training data.")
            interp_color = '#f59e0b'

        else:  # ANOMALY
            title_text = "🚨 ANOMALY DETECTED — Behavior Deviates from Profile"
            title_color = "#ef4444"
            result_text = "ANOMALY DETECTED"
            interp = (f"{decision_reason}.\n\n"
                      f"The recorded mouse behavior does not match any stored profile.\n"
                      f"• Avg confidence:  {avg_confidence*100:.1f}%\n"
                      f"• Vote agreement:  {vote_agreement:.0f}%  (threshold: {VOTE_AGREEMENT_THRESHOLD}%)\n"
                      f"• Std deviation:   {std_dev*100:.1f}%  (threshold: {STD_DEV_ANOMALY_THRESHOLD*100:.0f}%)\n\n"
                      "Possible causes: different user, non-dominant hand, or unusual mouse behavior.")
            interp_color = '#ef4444'

        tk.Label(result_window, text=title_text,
                font=('Arial', 18, 'bold'), bg='#1a1a2e', fg=title_color).pack(pady=20)

        # Main result
        tk.Label(result_window, text=result_text,
                font=('Arial', 20, 'bold'), bg='#1a1a2e', fg='#00d4ff').pack(pady=10)

        # Details frame
        details_frame = tk.Frame(result_window, bg='#16213e', relief=tk.RAISED, bd=2)
        details_frame.pack(pady=20, padx=30, fill='both', expand=True)

        # Decision thresholds reference (explainability)
        threshold_text = (
            f"Auth threshold: {int(CONFIDENCE_THRESHOLD*100)}% conf  |  "
            f"≥{VOTE_AGREEMENT_THRESHOLD}% agreement  |  "
            f"std dev ≤{STD_DEV_ANOMALY_THRESHOLD*100:.0f}%"
        )
        tk.Label(details_frame, text=threshold_text,
                font=('Arial', 10, 'bold'), bg='#16213e', fg='#ffb703').pack(pady=(10, 2))

        # Confidence metrics (required for explainable AI)
        tk.Label(details_frame, text="📊 CONFIDENCE METRICS",
                font=('Arial', 14, 'bold'), bg='#16213e', fg='#00d4ff').pack(pady=10)

        metrics_text = (
            f"Avg Confidence:    {avg_confidence*100:.1f}%\n"
            f"Min Confidence:    {display_min_confidence*100:.1f}%\n"
            f"Max Confidence:    {display_max_confidence*100:.1f}%\n"
            f"Std Deviation:     {std_dev*100:.1f}%\n\n"
            f"Vote Agreement:    {vote_agreement:.0f}%\n"
            f"Classifier Votes:  {winner_votes}/{total_samples}\n"
            f"Samples Analyzed:  {len(features)}"
        )

        tk.Label(details_frame, text=metrics_text,
                font=('Consolas', 11), bg='#16213e', fg='white',
                justify='left').pack(pady=10, padx=20)

        # Top 2 candidates (always shown for explainability)
        tk.Label(details_frame, text="👥 TOP CANDIDATES",
                font=('Arial', 12, 'bold'), bg='#16213e', fg='#00d4ff').pack(pady=(10, 5))

        candidates_text = ""
        for i, (user, votes) in enumerate(top_candidates[:2]):
            pct = (votes / total_samples) * 100
            user_confidences = [conf for pred, conf in zip(predictions, confidences) if pred == user]
            user_avg_conf = np.mean(user_confidences) if user_confidences else 0
            icon = "🏆" if i == 0 else "2."
            candidates_text += f"{icon} {user}:\n"
            candidates_text += f"   Votes: {votes}/{total_samples} ({pct:.0f}%)\n"
            candidates_text += f"   Confidence: {user_avg_conf*100:.1f}%\n\n"

        tk.Label(details_frame, text=candidates_text,
                font=('Consolas', 10), bg='#16213e', fg='#94a3b8',
                justify='left').pack(pady=5, padx=20)

        # Interpretation
        tk.Label(details_frame, text="💡 INTERPRETATION",
                font=('Arial', 12, 'bold'), bg='#16213e', fg='#00d4ff').pack(pady=(10, 5))

        tk.Label(details_frame, text=interp,
                font=('Arial', 10), bg='#16213e', fg=interp_color,
                wraplength=500, justify='center').pack(pady=10, padx=20)

        # ── Feedback buttons ─────────────────────────────────────────────
        tk.Label(result_window, text="Was this result correct?",
                font=('Arial', 11, 'bold'), bg='#1a1a2e', fg='#94a3b8').pack(pady=(10, 4))

        feedback_frame = tk.Frame(result_window, bg='#1a1a2e')
        feedback_frame.pack(pady=(0, 6))

        def _on_feedback(was_correct):
            """Collect ground-truth identity and log the feedback row."""
            # Ask who the real user is; pre-fill with the predicted user
            actual = simpledialog.askstring(
                "Feedback — Actual User",
                "Who was the real user?\n(Leave blank if prediction was correct)",
                initialvalue=winner_user,
                parent=result_window
            )
            if actual is None:        # user cancelled the dialog
                return
            actual = actual.strip() or winner_user

            self._log_auth_feedback(
                predicted_user=winner_user,
                actual_user=actual,
                result_label=decision,
                avg_confidence=avg_confidence,
                min_confidence=display_min_confidence,
                max_confidence=display_max_confidence,
                std_dev=std_dev,
                vote_agreement=vote_agreement,
                samples_count=len(features),
                was_correct=was_correct,
            )
            # Disable both buttons so feedback can only be given once
            btn_correct.config(state='disabled')
            btn_incorrect.config(state='disabled')
            tk.Label(result_window, text="✔ Feedback saved",
                    font=('Arial', 10), bg='#1a1a2e', fg='#10b981').pack()

        btn_correct = tk.Button(feedback_frame, text="✅  Correct",
                                command=lambda: _on_feedback(True),
                                bg='#10b981', fg='white',
                                font=('Arial', 11, 'bold'), width=12, height=1)
        btn_correct.pack(side='left', padx=10)

        btn_incorrect = tk.Button(feedback_frame, text="❌  Incorrect",
                                  command=lambda: _on_feedback(False),
                                  bg='#ef4444', fg='white',
                                  font=('Arial', 11, 'bold'), width=12, height=1)
        btn_incorrect.pack(side='left', padx=10)
        # ─────────────────────────────────────────────────────────────────

        # Close button
        tk.Button(result_window, text="Close", command=result_window.destroy,
                 bg='#3b82f6', fg='white', font=('Arial', 12, 'bold'),
                 width=15, height=2).pack(pady=14)

        # Update status bar
        if decision == "AUTHENTICATED":
            self._update_status(f"✓ AUTHENTICATED as {winner_user}", '#10b981')
        elif decision == "UNCERTAIN":
            self._update_status(f"⚠️ UNCERTAIN — Likely {winner_user}", '#f59e0b')
        else:
            self._update_status("🚨 ANOMALY DETECTED — Behavior Deviates from Profile", '#ef4444')
    
    def _log_auth_feedback(self, predicted_user, actual_user, result_label,
                           avg_confidence, min_confidence, max_confidence,
                           std_dev, vote_agreement, samples_count, was_correct):
        """Append one feedback row to logs/auth_feedback_log.csv.

        Columns:
            timestamp, predicted_user, actual_user, result_label,
            avg_confidence, min_confidence, max_confidence,
            std_dev, vote_agreement, samples_count, was_correct
        """
        import csv

        LOG_DIR = "logs"
        LOG_FILE = os.path.join(LOG_DIR, "auth_feedback_log.csv")
        HEADERS = [
            "timestamp", "predicted_user", "actual_user", "result_label",
            "avg_confidence", "min_confidence", "max_confidence",
            "std_dev", "vote_agreement", "samples_count", "was_correct"
        ]

        row = {
            "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "predicted_user":  predicted_user,
            "actual_user":     actual_user,
            "result_label":    result_label,
            "avg_confidence":  round(avg_confidence, 4),
            "min_confidence":  round(min_confidence, 4),
            "max_confidence":  round(max_confidence, 4),
            "std_dev":         round(std_dev, 4),
            "vote_agreement":  round(vote_agreement, 1),
            "samples_count":   samples_count,
            "was_correct":     was_correct,
        }

        # Console output for quick debugging
        print(f"\n[FEEDBACK]")
        print(f"Predicted: {predicted_user} | Actual: {actual_user} | Correct: {was_correct}")
        print(f"Conf: {avg_confidence:.2f} | Agreement: {vote_agreement:.0f}% | Std: {std_dev:.2f}")

        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            file_exists = os.path.isfile(LOG_FILE)
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
            print(f"[FEEDBACK] Logged to {LOG_FILE}")
        except Exception as e:
            # Never crash the UI over a logging failure
            print(f"[FEEDBACK] WARNING: Could not write log — {e}")

    def _save_model(self):
        """Save trained model.

        If the in-memory model is the improved session-level model the full
        session-builder metadata is written so that auth and re-load stay
        in lock-step. Otherwise a legacy payload is written.
        """
        if self.model is None:
            messagebox.showwarning("Warning", "No model to save!")
            return

        try:
            if self._model_format == 'improved' and self._session_meta is not None:
                target = IMPROVED_MODEL_FILE
                payload = {
                    'model':              self.model,
                    'scaler':             self.scaler,
                    'users':              self.users,
                    'model_format':       'improved',
                    'base_feature_count': SHARED_BASE_FEATURE_COUNT,
                    'session_vector_dim': SHARED_TOTAL_DIM,
                    'feature_names':      shared_make_feature_names(),
                    'session_size':       self._session_meta['session_size'],
                    'chunk_count':        self._session_meta['chunk_count'],
                    'n_chunks':           self._session_meta['n_chunks'],
                    'chunk_size':         self._session_meta['chunk_size'],
                    'chunk_feature_names': list(self._session_meta['chunk_feature_names']),
                    'chunk_feature_cols': list(self._session_meta['chunk_feature_cols']),
                    'base_features':      list(self._session_meta['base_features']),
                    'user_thresholds':    getattr(self, 'user_thresholds', {}),
                }
            else:
                target = MODEL_FILE
                payload = {
                    'model':           self.model,
                    'scaler':          self.scaler,
                    'users':           self.users,
                    'model_format':    'legacy',
                    'user_thresholds': getattr(self, 'user_thresholds', {}),
                }

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'wb') as f:
                pickle.dump(payload, f)

            messagebox.showinfo("Success", f"Model saved to:\n{target}")
            self._update_status("✓ Model saved", '#10b981')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _payload_schema_error(self, data):
        """Return why a saved model payload is incompatible, or empty string."""
        is_improved = data.get('model_format') == 'improved' or 'session_size' in data
        if not is_improved:
            return (
                "Saved legacy per-sample models are incompatible with the current "
                f"{SHARED_BASE_FEATURE_COUNT}-feature final model. {SCHEMA_CHANGE_MESSAGE}"
            )

        scaler = data.get('scaler')
        base_count = int(data.get('base_feature_count', len(data.get('base_features', []))))
        session_dim = int(data.get('session_vector_dim', getattr(scaler, 'n_features_in_', 0) or 0))

        if base_count != SHARED_BASE_FEATURE_COUNT:
            return (
                f"Saved model expects {base_count} base features, but the current "
                f"schema requires {SHARED_BASE_FEATURE_COUNT}. {SCHEMA_CHANGE_MESSAGE}"
            )

        if session_dim != SHARED_TOTAL_DIM:
            return (
                f"Saved model expects session vectors with {session_dim} features, "
                f"but the current builder produces {SHARED_TOTAL_DIM}. Retrain after recollecting data."
            )

        return ""

    def _session_meta_from_payload(self, data):
        chunk_count = int(data.get('chunk_count', data.get('n_chunks', SHARED_N_CHUNKS)))
        chunk_features = list(data.get('chunk_feature_names', data.get('chunk_feature_cols', SHARED_CHUNK_FEATURE_COLS)))
        return {
            'model_format':       'improved',
            'base_feature_count': int(data.get('base_feature_count', SHARED_BASE_FEATURE_COUNT)),
            'session_vector_dim': int(data.get('session_vector_dim', SHARED_TOTAL_DIM)),
            'feature_names':      list(data.get('feature_names', shared_make_feature_names())),
            'session_size':       int(data.get('session_size', SHARED_SESSION_SIZE)),
            'chunk_count':        chunk_count,
            'n_chunks':           chunk_count,
            'chunk_size':         int(data.get('chunk_size', SHARED_CHUNK_SIZE)),
            'chunk_feature_names': chunk_features,
            'chunk_feature_cols': chunk_features,
            'base_features':      list(data.get('base_features', SHARED_BASE_FEATURES)),
        }
    
    def _load_model(self):
        """Load trained model — prefers improved model if it exists, otherwise loads legacy."""
        # Prefer the improved session-level model when available
        if os.path.exists(IMPROVED_MODEL_FILE):
            target_path = IMPROVED_MODEL_FILE
        elif os.path.exists(MODEL_FILE):
            target_path = MODEL_FILE
        else:
            messagebox.showwarning("Warning", "No saved model found!")
            return

        try:
            with open(target_path, 'rb') as f:
                data = pickle.load(f)

            self.model = data.get('model')
            self.scaler = data.get('scaler')
            if self.model is not None and hasattr(self.model, 'classes_'):
                try:
                    self.users = list(self.model.classes_)
                except Exception:
                    self.users = data.get('users', [])
            else:
                self.users = data.get('users', [])

            self.user_thresholds = data.get('user_thresholds', {})

            schema_error = self._payload_schema_error(data)
            if schema_error:
                self.model = None
                self.scaler = None
                self.users = []
                self._model_format = 'legacy'
                self._session_meta = None
                messagebox.showerror("Model Schema Changed", schema_error)
                self._update_status("❌ Saved model incompatible", '#ef4444')
                return

            # Detect model format
            if data.get('model_format') == 'improved' or 'session_size' in data:
                self._model_format = 'improved'
                self._session_meta = self._session_meta_from_payload(data)
                fmt_label = f'improved-format ({SHARED_TOTAL_DIM}-dim session vectors)'
            else:
                self._model_format = 'legacy'
                self._session_meta = None
                fmt_label = 'legacy-format'

            print(f"[LOAD] Model path   : {target_path}")
            print(f"[LOAD] Model format : {fmt_label}")
            print(f"[LOAD] Users        : {self.users}")

            messagebox.showinfo("Success",
                f"Model loaded!\nFormat: {fmt_label}\nUsers: {', '.join(self.users)}")
            self._update_status("Model loaded", '#10b981')
            self._update_info()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
    
    def _try_load_model(self):
        """Try to load model on startup — prefer improved model over legacy."""
        # Prefer improved model; fall back to legacy
        if os.path.exists(IMPROVED_MODEL_FILE):
            target_path = IMPROVED_MODEL_FILE
        elif os.path.exists(MODEL_FILE):
            target_path = MODEL_FILE
        else:
            return

        try:
            with open(target_path, 'rb') as f:
                data = pickle.load(f)
            self.model = data.get('model')
            self.scaler = data.get('scaler')
            if self.model is not None and hasattr(self.model, 'classes_'):
                try:
                    self.users = list(self.model.classes_)
                except Exception:
                    self.users = data.get('users', [])
            else:
                self.users = data.get('users', [])

            self.user_thresholds = data.get('user_thresholds', {})

            schema_error = self._payload_schema_error(data)
            if schema_error:
                self.model = None
                self.scaler = None
                self.users = []
                self._model_format = 'legacy'
                self._session_meta = None
                self._update_status("Saved model incompatible with 25-feature schema", '#ef4444')
                print(f"[STARTUP] Model schema incompatible: {schema_error}")
                return

            if data.get('model_format') == 'improved' or 'session_size' in data:
                self._model_format = 'improved'
                self._session_meta = self._session_meta_from_payload(data)
                fmt_label = f'improved-format ({SHARED_TOTAL_DIM}-dim)'
            else:
                self._model_format = 'legacy'
                self._session_meta = None
                fmt_label = 'legacy-format'

            self._update_status(f"Model loaded ({fmt_label}, {len(self.users)} users)", '#10b981')
            self._update_info()
            print(f"[STARTUP] Loaded model path : {target_path}")
            print(f"[STARTUP] Model format      : {fmt_label}")
            print(f"[STARTUP] Active source     : "
                  f"{'IMPROVED_MODEL_FILE (' + IMPROVED_MODEL_FILE + ')' if self._model_format == 'improved' else 'MODEL_FILE (' + MODEL_FILE + ')'}")
            print(f"[STARTUP] Users             : {self.users}")
        except Exception as _e:
            print(f"[STARTUP] Could not load model: {_e}")
    
    def _show_users(self):
        """Show all users in dataset"""
        try:
            df = pd.read_csv(self.current_csv)
            if 'user' in df.columns:
                user_counts = df['user'].value_counts()
                csv_name = os.path.basename(self.current_csv)
                msg = f"Users in {csv_name}:\n\n"
                for user, count in user_counts.items():
                    msg += f"• {user}: {count:,} samples\n"
                messagebox.showinfo("User List", msg)
            else:
                messagebox.showinfo("User List", "No users found in dataset")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load users: {e}")

    def open_mouse_login(self):
        """Open a small dialog to select a claimed user and run a claimed-user authentication flow."""
        if self.model is None or not self.users:
            messagebox.showerror("Error", "No trained model or users available. Train or load a model first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Mouse Login")
        dialog.geometry("400x350")
        dialog.configure(bg='#1a1a2e')

        tk.Label(dialog, text="Select user to login as:", font=('Arial', 12, 'bold'),
                 bg='#1a1a2e', fg='white').pack(pady=10)

        listbox = tk.Listbox(dialog, font=('Arial', 11), height=10)
        listbox.pack(pady=10, padx=20, fill='both', expand=True)

        for u in self.users:
            listbox.insert(tk.END, u)

        def on_start():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("No Selection", "Please select a user to login as.")
                return
            claimed = self.users[sel[0]]
            dialog.destroy()
            # Run the claimed-user authentication (reuses quick_authenticate)
            try:
                self._quick_authenticate(claimed_user=claimed)
            except Exception as e:
                messagebox.showerror("Error", f"Login attempt failed: {e}")

        tk.Button(dialog, text="Start Mouse Login", command=on_start,
                 bg='#3b82f6', fg='white', font=('Arial', 11, 'bold'), width=18).pack(pady=10)
    
    def _switch_csv(self):
        """Switch between different CSV files in data folder"""
        # Get all CSV files in data folder
        csv_files = [f for f in os.listdir('data') if f.endswith('.csv')]
        
        if len(csv_files) == 0:
            messagebox.showinfo("No CSV Files", "No CSV files found in data folder")
            return
        
        if len(csv_files) == 1:
            messagebox.showinfo("Only One CSV", f"Only one CSV file found: {csv_files[0]}")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Switch CSV File")
        dialog.geometry("400x300")
        dialog.configure(bg='#1a1a2e')
        
        tk.Label(dialog, text="Select CSV File:", font=('Arial', 12, 'bold'),
                bg='#1a1a2e', fg='white').pack(pady=10)
        
        listbox = tk.Listbox(dialog, font=('Arial', 10), height=10)
        listbox.pack(pady=10, padx=20, fill='both', expand=True)
        
        for csv_file in csv_files:
            listbox.insert(tk.END, csv_file)
        
        # Highlight current CSV
        current_name = os.path.basename(self.current_csv)
        if current_name in csv_files:
            listbox.selection_set(csv_files.index(current_name))
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_csv = csv_files[selection[0]]
                new_path = os.path.join('data', selected_csv)
                
                if new_path == self.current_csv:
                    messagebox.showinfo("Same CSV", "This CSV is already selected")
                    dialog.destroy()
                    return
                
                self.current_csv = new_path
                self.model = None
                self.scaler = None
                self.users = []
                
                self._update_info()
                self._update_status(f"✓ Switched to {selected_csv}", '#10b981')

                schema_error = self._current_csv_schema_error()
                if schema_error:
                    messagebox.showwarning("CSV Schema Changed", schema_error)
                
                messagebox.showinfo("CSV Switched",
                    f"Now using: {selected_csv}\n\n"
                    f"You need to train a new model on this data.")
                
                dialog.destroy()
        
        tk.Button(dialog, text="Select", command=on_select,
                 bg='#3b82f6', fg='white', font=('Arial', 10, 'bold'),
                 width=15).pack(pady=10)
    
    def _create_csv(self):
        """Create a new CSV file"""
        filename = simpledialog.askstring("Create New CSV",
            "Enter name for new CSV file (without .csv extension):",
            parent=self.root)
        
        if not filename:
            return
        
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        new_path = os.path.join('data', filename)
        
        if os.path.exists(new_path):
            messagebox.showerror("Error", f"File {filename} already exists!")
            return
        
        try:
            df = pd.DataFrame(columns=FEATURE_COLUMNS + ['user'])
            df.to_csv(new_path, index=False)
            
            # Switch to new CSV
            self.current_csv = new_path
            self.model = None
            self.scaler = None
            self.users = []
            
            self._update_info()
            self._update_status(f"✓ Created {filename}", '#10b981')
            
            messagebox.showinfo("Success",
                f"Created new CSV: {filename}\n\n"
                f"Now using this file for data collection.")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create CSV: {e}")

    def _deep_clean_current_csv(self):
        """Create a timestamped backup of the active CSV, apply conservative cleaning rules,
        overwrite the original CSV with the cleaned data, and prompt the user to retrain.
        """
        try:
            if not os.path.exists(self.current_csv):
                messagebox.showerror("Error", f"CSV not found: {self.current_csv}")
                return

            backup_dir = os.path.join(os.path.dirname(self.current_csv), "backup")
            os.makedirs(backup_dir, exist_ok=True)

            base_name = os.path.basename(self.current_csv)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{base_name}.bak_{timestamp}")

            # Copy original to backup first
            shutil.copy2(self.current_csv, backup_path)

            # Load CSV
            df = pd.read_csv(self.current_csv)
            df_clean = df.copy()

            # Required fields (ensure 'user' exists; include 'timestamp' if present)
            required_cols = ["user"]
            if 'timestamp' in df_clean.columns:
                required_cols.append('timestamp')

            df_clean = df_clean.dropna(subset=required_cols)

            # Identify feature columns (exclude bookkeeping / label cols)
            exclude_cols = set(['user', 'timestamp', 'session_id', '_order', 'orig_index', 'global_session'])
            feature_cols = [c for c in df_clean.columns if c not in exclude_cols]

            # Work only with numeric feature columns when checking for all-zero rows
            numeric_features = df_clean[feature_cols].select_dtypes(include=["number"]) if feature_cols else pd.DataFrame()
            if not numeric_features.empty:
                all_zero_mask = (numeric_features == 0).all(axis=1)
                df_clean = df_clean[~all_zero_mask]

            # Drop rows with impossible timings if such columns exist
            if 'time_elapsed' in df_clean.columns:
                try:
                    df_clean = df_clean[df_clean['time_elapsed'] > 0]
                except Exception:
                    pass
            if 'click_duration' in df_clean.columns:
                try:
                    df_clean = df_clean[df_clean['click_duration'] >= 0]
                except Exception:
                    pass

            # Drop rows flagged as confused if that column exists
            if 'confused' in df_clean.columns:
                try:
                    df_clean = df_clean[~df_clean['confused'].astype(bool)]
                except Exception:
                    pass

            # Summary
            print(f"[DEEP CLEAN] Backup saved to: {backup_path}")
            print(f"[DEEP CLEAN] Original rows: {len(df)}, cleaned rows: {len(df_clean)}, removed: {len(df) - len(df_clean)}")

            # Overwrite original CSV
            df_clean.to_csv(self.current_csv, index=False)

            # Update UI
            self._update_info()
            self._update_status("✓ Deep clean complete — retrain the model", '#10b981')

            messagebox.showinfo(
                "Deep Clean Complete",
                "Backup created in 'backup' folder.\n"
                "CSV cleaned and saved with the same name.\n\n"
                "Please retrain the model now."
            )

        except Exception as e:
            messagebox.showerror("Deep Clean Failed", f"An error occurred: {e}")
    
    def _delete_user(self):
        """Delete a user from the dataset"""
        try:
            df = pd.read_csv(self.current_csv)
            
            if 'user' not in df.columns or df.empty:
                messagebox.showinfo("No Users", "No users found in dataset")
                return
            
            users = list(df['user'].unique())
            
            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Delete User")
            dialog.geometry("400x350")
            dialog.configure(bg='#1a1a2e')
            
            tk.Label(dialog, text="⚠️ Select User to Delete:", font=('Arial', 12, 'bold'),
                    bg='#1a1a2e', fg='#ef4444').pack(pady=10)
            
            listbox = tk.Listbox(dialog, font=('Arial', 10), height=10)
            listbox.pack(pady=10, padx=20, fill='both', expand=True)
            
            for user in users:
                count = len(df[df['user'] == user])
                listbox.insert(tk.END, f"{user} ({count:,} samples)")
            
            def on_delete():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a user")
                    return
                
                user_to_delete = users[selection[0]]
                
                # Confirm deletion
                confirm = messagebox.askyesno("Confirm Delete",
                    f"Delete all data for user '{user_to_delete}'?\n\n"
                    f"This cannot be undone!",
                    icon='warning')
                
                if confirm:
                    df_filtered = df[df['user'] != user_to_delete]
                    df_filtered.to_csv(self.current_csv, index=False)
                    
                    # Reset model if this user was trained
                    if user_to_delete in self.users:
                        self.model = None
                        self.scaler = None
                        self.users = []
                    
                    self._update_info()
                    self._update_status(f"✓ Deleted user {user_to_delete}", '#10b981')
                    
                    messagebox.showinfo("Success",
                        f"Deleted user: {user_to_delete}\n\n"
                        f"Model needs to be retrained.")
                    
                    dialog.destroy()
            
            tk.Button(dialog, text="🗑️ Delete User", command=on_delete,
                     bg='#ef4444', fg='white', font=('Arial', 10, 'bold'),
                     width=15).pack(pady=10)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete user: {e}")
    
    def _merge_users(self):
        """Merge data from multiple users into one"""
        try:
            df = pd.read_csv(self.current_csv)
            
            if 'user' not in df.columns or df.empty:
                messagebox.showinfo("No Users", "No users found in dataset")
                return
            
            users = list(df['user'].unique())
            
            if len(users) < 2:
                messagebox.showinfo("Not Enough Users",
                    "Need at least 2 users to merge")
                return
            
            # Create merge dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Merge Users")
            dialog.geometry("450x400")
            dialog.configure(bg='#1a1a2e')
            
            tk.Label(dialog, text="🔄 Merge Users", font=('Arial', 14, 'bold'),
                    bg='#1a1a2e', fg='#8b5cf6').pack(pady=10)
            
            tk.Label(dialog, text="Select users to merge (Ctrl+Click for multiple):",
                    font=('Arial', 10), bg='#1a1a2e', fg='white').pack(pady=5)
            
            listbox = tk.Listbox(dialog, font=('Arial', 10), height=8,
                               selectmode=tk.MULTIPLE)
            listbox.pack(pady=10, padx=20, fill='both', expand=True)
            
            for user in users:
                count = len(df[df['user'] == user])
                listbox.insert(tk.END, f"{user} ({count:,} samples)")
            
            tk.Label(dialog, text="New username for merged data:",
                    font=('Arial', 10), bg='#1a1a2e', fg='white').pack(pady=5)
            
            new_name_entry = tk.Entry(dialog, font=('Arial', 10), width=25)
            new_name_entry.pack(pady=5)
            
            def on_merge():
                selections = listbox.curselection()
                if len(selections) < 2:
                    messagebox.showwarning("Select Multiple",
                        "Please select at least 2 users to merge")
                    return
                
                new_name = new_name_entry.get().strip()
                if not new_name:
                    messagebox.showwarning("No Name",
                        "Please enter a new username")
                    return
                
                users_to_merge = [users[i] for i in selections]
                
                # Confirm merge
                confirm = messagebox.askyesno("Confirm Merge",
                    f"Merge these users:\n{', '.join(users_to_merge)}\n\n"
                    f"Into: {new_name}\n\n"
                    f"Original users will be deleted!",
                    icon='warning')
                
                if confirm:
                    # Merge the data
                    df_merged = df[df['user'].isin(users_to_merge)].copy()
                    df_merged['user'] = new_name
                    
                    df_remaining = df[~df['user'].isin(users_to_merge)]
                    df_final = pd.concat([df_remaining, df_merged], ignore_index=True)
                    
                    df_final.to_csv(self.current_csv, index=False)
                    
                    # Reset model
                    self.model = None
                    self.scaler = None
                    self.users = []
                    
                    self._update_info()
                    self._update_status(f"✓ Merged into {new_name}", '#10b981')
                    
                    total_samples = len(df_merged)
                    messagebox.showinfo("Success",
                        f"Merged {len(users_to_merge)} users into: {new_name}\n\n"
                        f"Total samples: {total_samples:,}\n\n"
                        f"Model needs to be retrained.")
                    
                    dialog.destroy()
            
            tk.Button(dialog, text="🔄 Merge Users", command=on_merge,
                     bg='#8b5cf6', fg='white', font=('Arial', 10, 'bold'),
                     width=15).pack(pady=10)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to merge users: {e}")

# ============================================================================
# MAIN
# ============================================================================
class DualWriter:
    """Write to both console and file simultaneously"""
    def __init__(self, log_file):
        self.console = __import__('sys').stdout if hasattr(__import__('sys'), 'stdout') else __import__('sys').stderr
        self.file = open(log_file, 'a', encoding='utf-8')
    
    def write(self, msg):
        self.console.write(msg)
        self.file.write(msg)
        self.file.flush()
    
    def flush(self):
        self.console.flush()
        self.file.flush()
    
    def close(self):
        self.file.close()


if __name__ == "__main__":
    import sys
    # Set up logging to Desktop/MouseAuth_Log.txt
    desktop_path = os.path.expanduser("~/Desktop/MouseAuth_Log.txt")
    dual_out = DualWriter(desktop_path)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = dual_out
    sys.stderr = dual_out
    
    try:
        # Shared-builder self-check + anti-cheating audit BEFORE the app starts.
        try:
            shared_self_check(verbose=True)
        except Exception as _e:
            print(f"[STARTUP] Shared-builder self-check failed: {_e}")
        try:
            _run_anti_cheating_audit()
        except Exception as _e:
            print(f"[STARTUP] Anti-cheating audit failed: {_e}")

        root = tk.Tk()
        app = MouseAuthApp(root)

        active_model_path = (
            IMPROVED_MODEL_FILE if getattr(app, '_model_format', 'legacy') == 'improved'
            else MODEL_FILE
        )
        print("✓ Mouse Authentication System Started")
        print(f"  CSV          : {app.current_csv}")
        print(f"  Model format : {getattr(app, '_model_format', 'legacy')}")
        print(f"  Model path   : {active_model_path}")

        root.mainloop()
        
        print("✓ Application closed")
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        dual_out.close()
