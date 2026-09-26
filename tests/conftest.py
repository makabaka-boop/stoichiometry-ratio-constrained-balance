"""Shared pytest fixtures/path setup."""

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
