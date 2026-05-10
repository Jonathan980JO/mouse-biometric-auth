"""
train_improved.py - DEPRECATED ENTRYPOINT (kept as a thin wrapper).

The improved session-level training pipeline now lives INSIDE the GUI
(MouseAuth.py -> _train_model) and uses the shared session builder
(shared_session_builder.py).

Running this script no longer trains by itself - it just launches the GUI
and reminds the user to press the "Train Model" button there.

Why a wrapper instead of a delete?
  * Existing batch files / docs still reference this filename.
  * Keeps a single source of truth for the training logic.
  * Removes the previous duplicate-pipeline conflict.
"""
from __future__ import annotations

import sys


def main() -> int:
    print("=" * 70)
    print("train_improved.py is now a thin wrapper.")
    print("=" * 70)
    print("The improved training pipeline runs INSIDE the GUI:")
    print("  1) python MouseAuth.py")
    print("  2) Click the \"Train Model\" button.")
    print()
    print("Both training and authentication share shared_session_builder.py")
    print("(25 base features, 40-row sessions, 4 ordered chunks).")
    print()

    # Quick sanity check on the shared builder so this file still verifies
    # the train/auth dimension contract when invoked directly.
    try:
        from shared_session_builder import self_check
        self_check(verbose=True)
    except Exception as e:
        print(f"[WRAPPER] shared_session_builder self-check failed: {e}")
        return 1

    # Optionally launch the GUI when invoked with --launch
    if "--launch" in sys.argv:
        try:
            import MouseAuth  # noqa: F401  (importing it triggers no GUI; user must run module)
        except Exception as e:
            print(f"[WRAPPER] Could not import MouseAuth: {e}")
            return 2
        print("Now run: python MouseAuth.py")
    else:
        print("Pass --launch to also import the GUI module for verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
