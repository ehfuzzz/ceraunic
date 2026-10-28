"""Phase 3 (EVAL-02 / EVAL-03): geography basis + residual design bake-off.

  uv run python scripts/eval03.py --pull     # one-time top-up pulls into data/cache/eval03 (network)
  uv run python scripts/eval03.py --dq       # data-quality check only (writes tables.md section 1)
  uv run python scripts/eval03.py --all      # full evaluation -> reports/eval-03/*
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wi.eval03.run import main  # noqa: E402

if __name__ == "__main__":
    main()
