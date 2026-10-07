"""Claimed runner for exp-20260817-001."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.current_paper_core_allocator import main


if __name__ == "__main__":
    main()
