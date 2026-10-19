"""Pytest configuration for counter service tests.

Ensures proper sys.path and module aliasing whether run from the monorepo root
or directly from within services/counter.
"""

from pathlib import Path
import sys

COUNTER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = COUNTER_DIR.parent.parent

if str(COUNTER_DIR) not in sys.path:
    sys.path.insert(0, str(COUNTER_DIR))

if (REPO_ROOT / "services").is_dir() and str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
