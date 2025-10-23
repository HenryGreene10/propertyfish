from __future__ import annotations

import sys
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.utils.normalize import normalize_bbl  # noqa: E402

__all__ = ["normalize_bbl"]
