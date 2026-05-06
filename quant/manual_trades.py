"""Lightweight manual trade ledger helpers.

The ledger is intentionally append-only JSONL so user-directed trades can be
audited by the production rule layer without changing open_positions schema.
"""

from __future__ import annotations

import json
import os

from operator_input_paths import MANUAL_TRADES_PATH, manual_trades_path


DEFAULT_MANUAL_TRADES_PATH = str(MANUAL_TRADES_PATH)


def load_manual_trades(path: str | os.PathLike | None = None) -> list[dict]:
    """Load manual trades from JSONL, ignoring malformed blank lines."""
    resolved = manual_trades_path(path)
    if not resolved.exists():
        return []

    trades: list[dict] = []
    with open(resolved, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                trades.append(item)
    return trades
