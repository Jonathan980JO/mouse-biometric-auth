"""
Shared session-builder module.

Single source of truth for:
    * 25 base per-sample features (kinematic + final-approach microbehavior)
  * Session size / chunk count / chunk size
  * Chunk-feature column subset
    * Final session-vector layout

Used by BOTH:
  * GUI training path  (MouseAuth.py -> _train_model)
  * GUI authentication (MouseAuth.py -> _quick_authenticate)
  * Standalone wrapper (train_improved.py)

NO user-name logic, NO hardcoded boosts, NO synthetic data,
NO role-based functions, NO duplicated train/auth implementations.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

# ────────────────────────────────────────────────────────────────────────────
# CANONICAL CONSTANTS  (do NOT redefine elsewhere)
# ────────────────────────────────────────────────────────────────────────────
SESSION_SIZE: int = 40
N_CHUNKS:     int = 4
CHUNK_SIZE:   int = SESSION_SIZE // N_CHUNKS   # = 10

LEGACY_BASE_FEATURE_COUNT: int = 18
SCHEMA_CHANGE_MESSAGE: str = (
    "Feature schema changed from 18 to 25. Old CSV data must be recollected "
    "before training this model."
)

ORIGINAL_BASE_FEATURES: List[str] = [
    "dx", "dy", "speed", "accel", "jerk", "angle",
    "angle_change", "curvature", "dir_change_x", "dir_change_y",
    "time_elapsed", "speed_variance", "speed_std",
    "click_time", "click_duration", "pause_before_click",
    "overshoot_distance", "path_efficiency",
]

FINAL_APPROACH_FEATURES: List[str] = [
    "final_approach_speed_mean",
    "final_approach_speed_std",
    "final_angle_change_mean",
    "final_path_efficiency",
    "final_micro_corrections",
    "hover_time_before_click",
    "final_distance_to_target",
]

BASE_FEATURES: List[str] = ORIGINAL_BASE_FEATURES + FINAL_APPROACH_FEATURES
BASE_FEATURE_COUNT: int = len(BASE_FEATURES)

CHUNK_FEATURE_COLS: List[str] = [
    "speed", "accel", "jerk",
    "angle_change", "curvature",
    "pause_before_click", "path_efficiency",
    "final_approach_speed_mean", "final_approach_speed_std",
    "final_angle_change_mean", "final_path_efficiency",
    "final_micro_corrections", "hover_time_before_click",
    "final_distance_to_target",
]
CHUNK_FEATURE_COUNT: int = len(CHUNK_FEATURE_COLS)

# 25 global means + 4 chunks x selected movement/final-approach features.
TOTAL_DIM: int = BASE_FEATURE_COUNT + N_CHUNKS * CHUNK_FEATURE_COUNT


# ────────────────────────────────────────────────────────────────────────────
# Public helpers
# ────────────────────────────────────────────────────────────────────────────
def make_feature_names() -> List[str]:
    """Ordered names for each feature in the session vector."""
    names = [f"g_{f}" for f in BASE_FEATURES]
    for c in range(N_CHUNKS):
        for f in CHUNK_FEATURE_COLS:
            names.append(f"c{c}_{f}")
    return names


def session_meta() -> dict:
    """Return the session-meta dict stored alongside the trained model."""
    return {
        "model_format":       "improved",
        "base_feature_count": BASE_FEATURE_COUNT,
        "session_vector_dim": TOTAL_DIM,
        "feature_names":      make_feature_names(),
        "session_size":       SESSION_SIZE,
        "chunk_count":        N_CHUNKS,
        "n_chunks":           N_CHUNKS,
        "chunk_size":         CHUNK_SIZE,
        "chunk_feature_names": list(CHUNK_FEATURE_COLS),
        "chunk_feature_cols": list(CHUNK_FEATURE_COLS),
        "base_features":      list(BASE_FEATURES),
    }


def validate_required_columns(df: pd.DataFrame) -> List[str]:
    """Return the list of missing required base-feature columns (empty = OK)."""
    return [c for c in BASE_FEATURES if c not in df.columns]


def has_legacy_base_schema(columns) -> bool:
    """Return True when columns look like the old 18-feature raw schema."""
    column_set = set(columns)
    return (
        all(c in column_set for c in ORIGINAL_BASE_FEATURES)
        and any(c not in column_set for c in FINAL_APPROACH_FEATURES)
    )


def build_chunk_features_from_df(group: pd.DataFrame) -> np.ndarray:
    """
    Training path: convert one user's DataFrame rows into session vectors.

    Every non-overlapping window of SESSION_SIZE rows produces one vector.
    Layout per vector:
      [0:BASE_FEATURE_COUNT] global mean of the 25 base features
      then each ordered chunk mean of CHUNK_FEATURE_COLS
    """
    missing = validate_required_columns(group)
    if missing:
        detail = SCHEMA_CHANGE_MESSAGE if has_legacy_base_schema(group.columns) else ""
        raise ValueError(
            f"DataFrame missing required columns: {missing}. {detail}".strip()
        )

    group = group.reset_index(drop=True)
    n_sessions = len(group) // SESSION_SIZE
    if n_sessions == 0:
        return np.empty((0, TOTAL_DIM), dtype=np.float32)

    records: List[np.ndarray] = []
    for s in range(n_sessions):
        sess = group.iloc[s * SESSION_SIZE:(s + 1) * SESSION_SIZE]
        global_means = sess[BASE_FEATURES].mean().to_numpy(dtype=np.float32)
        chunk_means: List[np.ndarray] = []
        for c in range(N_CHUNKS):
            chunk = sess.iloc[c * CHUNK_SIZE:(c + 1) * CHUNK_SIZE]
            chunk_means.append(
                chunk[CHUNK_FEATURE_COLS].mean().to_numpy(dtype=np.float32)
            )
        records.append(np.concatenate([global_means] + chunk_means))
    return np.array(records, dtype=np.float32)


def _coerce_to_numeric_array(features) -> np.ndarray:
    """
    Accept list / numpy array / DataFrame and return a numeric (N, 25) ndarray.
    Raises ValueError with a readable message on bad shape / non-numeric content.
    """
    if features is None:
        raise ValueError("features is None")

    # DataFrame → numeric ndarray
    if isinstance(features, pd.DataFrame):
        missing = [c for c in BASE_FEATURES if c not in features.columns]
        if missing:
            detail = SCHEMA_CHANGE_MESSAGE if has_legacy_base_schema(features.columns) else ""
            raise ValueError(
                f"DataFrame missing required columns: {missing}. {detail}".strip()
            )
        arr = features[BASE_FEATURES].to_numpy(dtype=np.float32)
    else:
        # list / tuple / ndarray
        try:
            arr = np.asarray(features, dtype=np.float32)
        except Exception as e:
            raise ValueError(f"could not convert features to numeric array: {e}")

    if arr.ndim != 2:
        raise ValueError(
            f"features must be 2-D (rows × {len(BASE_FEATURES)}), got shape {arr.shape}"
        )
    if arr.shape[1] != len(BASE_FEATURES):
        detail = f" {SCHEMA_CHANGE_MESSAGE}" if arr.shape[1] == LEGACY_BASE_FEATURE_COUNT else ""
        raise ValueError(
            f"features must have {len(BASE_FEATURES)} columns, got {arr.shape[1]}.{detail}"
        )
    if arr.shape[0] == 0:
        raise ValueError("features array is empty (0 rows)")

    # Replace any NaN/inf with 0 so downstream means/scaling don't explode
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def build_session_vectors_from_array(
    features,
    meta: dict | None = None,
    debug: bool = True,
) -> np.ndarray:
    """
    Authentication path: convert live (N, 25) feature rows into session vectors.

    Accepts list / numpy array / DataFrame.  Always converts to a float32 ndarray
    first, then applies the same chunk-mean layout used during training.
    """
    if meta is None:
        meta = session_meta()

    meta_base_count = int(meta.get("base_feature_count", len(meta.get("base_features", BASE_FEATURES))))
    if meta_base_count != BASE_FEATURE_COUNT:
        raise ValueError(
            f"Loaded model expects {meta_base_count} base features, but the current "
            f"extractor produces {BASE_FEATURE_COUNT}. {SCHEMA_CHANGE_MESSAGE}"
        )

    raw_type = type(features).__name__
    raw_len = (
        len(features) if hasattr(features, "__len__") else "n/a"
    )
    if debug:
        print(f"[BUILD] raw feature type    : {raw_type}")
        print(f"[BUILD] raw feature length  : {raw_len}")

    arr = _coerce_to_numeric_array(features)
    if debug:
        print(f"[BUILD] converted shape     : {arr.shape}")

    session_size       = int(meta.get("session_size", SESSION_SIZE))
    n_chunks           = int(meta.get("chunk_count", meta.get("n_chunks", N_CHUNKS)))
    chunk_size         = int(meta.get("chunk_size", CHUNK_SIZE))
    chunk_feature_cols = list(meta.get("chunk_feature_names", meta.get("chunk_feature_cols", CHUNK_FEATURE_COLS)))
    expected_dim       = int(meta.get("session_vector_dim", BASE_FEATURE_COUNT + n_chunks * len(chunk_feature_cols)))

    feat_to_idx = {f: i for i, f in enumerate(BASE_FEATURES)}
    missing_chunk_cols = [f for f in chunk_feature_cols if f not in feat_to_idx]
    if missing_chunk_cols:
        raise ValueError(f"chunk features missing from base schema: {missing_chunk_cols}")
    chunk_idx = [feat_to_idx[f] for f in chunk_feature_cols]

    n_rows     = arr.shape[0]
    n_sessions = n_rows // session_size

    if n_sessions == 0:
        if debug:
            print(f"[BUILD] not enough rows for one session "
                  f"({n_rows} < {session_size})")
        return np.empty((0, expected_dim), dtype=np.float32)

    records: List[np.ndarray] = []
    for s in range(n_sessions):
        sess         = arr[s * session_size:(s + 1) * session_size]
        global_means = sess.mean(axis=0)
        chunk_means  = []
        for c in range(n_chunks):
            chunk = sess[c * chunk_size:(c + 1) * chunk_size]
            chunk_means.append(chunk[:, chunk_idx].mean(axis=0))
        records.append(np.concatenate([global_means] + chunk_means))

    out = np.array(records, dtype=np.float32)
    if out.shape[1] != expected_dim:
        raise ValueError(
            f"session vector dimension mismatch: produced {out.shape[1]}, expected {expected_dim}"
        )
    if debug:
        print(f"[BUILD] final session vec   : {out.shape}")
    return out


# ────────────────────────────────────────────────────────────────────────────
# Self-check helpers
# ────────────────────────────────────────────────────────────────────────────
def self_check(verbose: bool = True) -> dict:
    """
    Verify both training-path and auth-path produce the same dimension.
    Returns a dict with the diagnostic info; prints a summary if verbose.
    """
    rng = np.random.RandomState(0)
    sample_rows = rng.rand(SESSION_SIZE * 3, len(BASE_FEATURES)).astype(np.float32)

    # Auth path (array in)
    auth_vecs = build_session_vectors_from_array(sample_rows.tolist(), debug=False)

    # Training path (DataFrame in)
    df = pd.DataFrame(sample_rows, columns=BASE_FEATURES)
    train_vecs = build_chunk_features_from_df(df)

    info = {
        "shared_builder_active": True,
        "base_feature_count":    BASE_FEATURE_COUNT,
        "chunk_feature_count":   CHUNK_FEATURE_COUNT,
        "training_dim":          int(train_vecs.shape[1]) if train_vecs.size else 0,
        "auth_dim":              int(auth_vecs.shape[1]) if auth_vecs.size else 0,
        "expected_dim":          TOTAL_DIM,
    }
    info["dimensions_match"] = (
        info["training_dim"] == info["auth_dim"] == TOTAL_DIM
    )
    if verbose:
        print("[SHARED BUILDER SELF-CHECK]")
        print(f"  shared builder active : YES")
        print(f"  base feature count    : {info['base_feature_count']}")
        print(f"  chunk feature count   : {info['chunk_feature_count']}")
        print(f"  total vector dim      : {info['expected_dim']}")
        print(f"  training-path dim     : {info['training_dim']}")
        print(f"  auth-path dim         : {info['auth_dim']}")
        print(f"  dimensions match      : {'YES' if info['dimensions_match'] else 'NO'}")
    return info


if __name__ == "__main__":
    self_check()
