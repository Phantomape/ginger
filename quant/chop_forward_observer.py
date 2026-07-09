"""Daily forward observer for the frozen chop paper bundles (exp-20260708-030).

Default-off, read-only for the strategy: replays the two frozen chop bundles
(``chop_mean_reversion_v1``, exp-20260708-023; ``chop_pairs_spread_v1``,
exp-20260708-025) over a trailing window of the OHLCV frames the daily
pipeline already loads, and idempotently upserts the resulting paper rows
into a forward ledger. Historical windows hold only ~33 chop-labeled days,
so verdicts on these bundles can only come from forward chop days accruing
here — one wiring, no further per-day experiment IDs (AGENTS.md §2.4).

The replays are the SAME functions Gate 1-4 judged, run on the same shared
regime module, so forward rows are replay-parity by construction. Because the
bundles are deterministic, re-running daily just re-derives the same rows:
open rows converge to closed rows as bars arrive (upsert key: bundle +
instrument + signal_date). No orders are produced; ``trade_enabled`` is false.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chop_mean_reversion_sleeve import (
    SLEEVE_RULE_VERSION as MR_RULE_VERSION,
    breadth_by_date,
    regime_labels_by_date,
    replay_chop_mean_reversion,
)
from chop_pairs_spread_sleeve import (
    SLEEVE_RULE_VERSION as PAIRS_RULE_VERSION,
    replay_chop_pairs_spread,
)
from data_paths import DATA_ROOT, atomic_write_text

LEDGER_DIR_NAME = "paper_sleeves/chop_forward"
ROWS_NAME = "rows.jsonl"
SUMMARY_NAME = "summary.json"

# Entries are observed over this trailing window each day; indicators use the
# full frame history. 45 trading days comfortably covers open lots (max hold
# 10 days) plus convergence lag, while keeping the daily run cheap.
ENTRY_WINDOW_TRADING_DAYS = 45


def _frames_to_bars(ohlcv_by_ticker: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """pandas frames (data_layer/get_ohlcv shape) -> plain bar dicts."""
    bars_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in (ohlcv_by_ticker or {}).items():
        if frame is None or getattr(frame, "empty", True):
            continue
        rows: list[dict[str, Any]] = []
        closes = frame.get("Close")
        opens = frame.get("Open") if "Open" in frame else None
        highs = frame.get("High") if "High" in frame else None
        lows = frame.get("Low") if "Low" in frame else None
        for idx in range(len(frame)):
            close = closes.iloc[idx]
            if close is None or close != close:
                continue
            date = str(frame.index[idx])[:10]
            rows.append(
                {
                    "Date": date,
                    "Open": float(opens.iloc[idx]) if opens is not None and opens.iloc[idx] == opens.iloc[idx] else float(close),
                    "High": float(highs.iloc[idx]) if highs is not None and highs.iloc[idx] == highs.iloc[idx] else float(close),
                    "Low": float(lows.iloc[idx]) if lows is not None and lows.iloc[idx] == lows.iloc[idx] else float(close),
                    "Close": float(close),
                }
            )
        if rows:
            bars_by_ticker[str(ticker).upper()] = rows
    return bars_by_ticker


def _row_key(row: dict[str, Any]) -> str:
    instrument = row.get("pair") or row.get("ticker") or ""
    return f"{row.get('bundle')}|{instrument}|{row.get('signal_date')}"


def _read_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows[_row_key(row)] = row
    return rows


def persist_chop_forward_observations(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of: str,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Replay both frozen bundles over the trailing window and upsert rows."""
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    ledger_dir = root / LEDGER_DIR_NAME
    rows_path = ledger_dir / ROWS_NAME
    summary_path = ledger_dir / SUMMARY_NAME

    bars_by_ticker = _frames_to_bars(ohlcv_by_ticker)
    spy_bars = bars_by_ticker.get("SPY") or []
    spy_dates = [b["Date"] for b in spy_bars]
    if len(spy_dates) < ENTRY_WINDOW_TRADING_DAYS + 1:
        return {
            "status": "skipped_insufficient_spy_history",
            "as_of_date": as_of,
            "generated_at": generated_at,
            "spy_bars": len(spy_dates),
        }
    window_days = [d for d in spy_dates if d <= as_of][-ENTRY_WINDOW_TRADING_DAYS:]
    start, end = window_days[0], window_days[-1]

    breadth = breadth_by_date(bars_by_ticker, window_days)
    labels = regime_labels_by_date(spy_bars, breadth, window_days)

    mr = replay_chop_mean_reversion(
        bars_by_ticker, spy_bars, start, end,
        regime_labels=labels, qqq_bars=bars_by_ticker.get("QQQ") or [],
    )
    pairs = replay_chop_pairs_spread(
        bars_by_ticker, spy_bars, start, end, regime_labels=labels,
    )

    existing = _read_rows(rows_path)
    upserted = 0
    for bundle, replay in ((MR_RULE_VERSION, mr), (PAIRS_RULE_VERSION, pairs)):
        for trade in replay["trades"]:
            row = {"bundle": bundle, "observed_at": generated_at, **trade}
            key = _row_key(row)
            prior = existing.get(key)
            # window_end_force_close rows are provisional (the lot is really
            # still open); never let them overwrite a genuinely closed row.
            if prior and prior.get("exit_reason") not in (None, "window_end_force_close"):
                continue
            if row.get("exit_reason") == "window_end_force_close":
                row["row_status"] = "open"
            else:
                row["row_status"] = "closed"
            existing[key] = row
            upserted += 1

    ordered = sorted(existing.values(), key=_row_key)
    atomic_write_text(
        "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in ordered),
        rows_path,
    )
    closed = [r for r in ordered if r.get("row_status") == "closed"]
    label_today = (labels.get(end) or {}).get("regime_label")
    summary = {
        "status": "ok",
        "as_of_date": as_of,
        "generated_at": generated_at,
        "window_start": start,
        "window_end": end,
        "regime_label_asof": label_today,
        "chop_days_in_window": sum(
            1 for d in window_days if (labels.get(d) or {}).get("regime_label") == "choppy_range"
        ),
        "rows_total": len(ordered),
        "rows_closed": len(closed),
        "rows_open": len(ordered) - len(closed),
        "rows_upserted_this_run": upserted,
        "closed_by_bundle": {
            bundle: sum(1 for r in closed if r.get("bundle") == bundle)
            for bundle in (MR_RULE_VERSION, PAIRS_RULE_VERSION)
        },
        "closed_pnl_by_bundle": {
            bundle: round(sum(r.get("pnl_usd") or 0 for r in closed if r.get("bundle") == bundle), 2)
            for bundle in (MR_RULE_VERSION, PAIRS_RULE_VERSION)
        },
        "rows_path": str(rows_path).replace("\\", "/"),
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "default_off_forward_chop_bundle_observation",
        },
    }
    atomic_write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        summary_path,
    )
    return summary
