"""exp-20260707-011: validate live drift hot-warehouse coverage repair."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from live_drift_reconciliation import (  # noqa: E402
    DATA_ROOT,
    DEFAULT_POSITIONS_PATH,
    WAREHOUSE_PATHS,
    build_live_drift_reconciliation,
)

EXP_ID = "exp-20260707-011"
ARTIFACT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXP_ID
    / "exp_20260707_011_live_drift_hot_warehouse_coverage.json"
)
BEFORE_PATH = ARTIFACT_PATH.parent / "before_measurement.json"
AFTER_PATH = ARTIFACT_PATH.parent / "after_measurement.json"
AS_OF_DATE = "2026-07-06"
OLD_WAREHOUSE_PATHS = (
    DATA_ROOT / "warehouse" / "warehouse_main.sqlite",
    DATA_ROOT / "tmp" / "warehouse_main_alpha_search_readcopy.sqlite",
)
MISSING_TICKERS = ("GEV", "HOOD", "SNXX", "TQQQ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bars_from_paths(paths: tuple[Path, ...]):
    def _lookup(ticker: str) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for path in paths:
            if not path.exists():
                continue
            try:
                con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
                try:
                    rows = con.execute(
                        "select date, open, close from ohlcv where ticker=? order by date",
                        (str(ticker).upper(),),
                    ).fetchall()
                finally:
                    con.close()
                if rows:
                    return [{"date": r[0], "open": r[1], "close": r[2]} for r in rows]
            except sqlite3.OperationalError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise RuntimeError(f"warehouse unavailable: {last_error}")
        return []

    return _lookup


def _coverage_probe(paths: tuple[Path, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    positions = json.loads(DEFAULT_POSITIONS_PATH.read_text(encoding="utf-8-sig")).get(
        "positions", []
    )
    entry_dates = {
        str(p.get("ticker") or "").upper(): str(p.get("entry_date") or "")[:10]
        for p in positions
        if str(p.get("ticker") or "").upper() in MISSING_TICKERS
    }
    for path in paths:
        label = path.as_posix()
        out[label] = {"exists": path.exists(), "tickers": {}}
        if not path.exists():
            continue
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            for ticker in MISSING_TICKERS:
                min_date, max_date, count = con.execute(
                    "select min(date), max(date), count(*) from ohlcv where ticker=?",
                    (ticker,),
                ).fetchone()
                entry_or_later = con.execute(
                    "select date, open, close from ohlcv where ticker=? and date>=? "
                    "order by date limit 1",
                    (ticker, entry_dates.get(ticker, "")),
                ).fetchone()
                out[label]["tickers"][ticker] = {
                    "entry_date": entry_dates.get(ticker),
                    "min_date": min_date,
                    "max_date": max_date,
                    "row_count": count,
                    "entry_or_later_bar": list(entry_or_later) if entry_or_later else None,
                }
        finally:
            con.close()
    return out


def _missing_entry_count(state: dict[str, Any]) -> int:
    return sum(
        1
        for row in state.get("unreconcilable", [])
        if row.get("reason") == "missing_entry_bar"
    )


def main() -> int:
    before = build_live_drift_reconciliation(
        as_of=AS_OF_DATE,
        bars_fn=_bars_from_paths(OLD_WAREHOUSE_PATHS),
        persist=False,
    )
    after = build_live_drift_reconciliation(
        as_of=AS_OF_DATE,
        bars_fn=_bars_from_paths(WAREHOUSE_PATHS),
        persist=False,
    )
    artifact = {
        "experiment_id": EXP_ID,
        "timestamp": _utc_now(),
        "hypothesis": (
            "Live drift reconciliation is undercounting current sleeve production drift "
            "because it reads stale warehouse surfaces while the daily hot OHLCV warehouse "
            "already contains entry/as-of bars for new live sleeve tickers."
        ),
        "change_type": "identity_or_measurement_repair",
        "changed_variable": "live_drift_hot_warehouse_current_bar_fallback",
        "as_of_date": AS_OF_DATE,
        "old_warehouse_paths": [p.as_posix() for p in OLD_WAREHOUSE_PATHS],
        "new_warehouse_paths": [p.as_posix() for p in WAREHOUSE_PATHS],
        "coverage_probe": _coverage_probe(OLD_WAREHOUSE_PATHS + WAREHOUSE_PATHS),
        "before_state": before,
        "after_state": after,
        "delta": {
            "reconciled_count": after.get("reconciled_count", 0)
            - before.get("reconciled_count", 0),
            "missing_entry_bar_count": _missing_entry_count(after)
            - _missing_entry_count(before),
            "sleeve_weighted_trajectory_drift_pct_before": (
                before.get("buckets", {}).get("sleeve", {}).get("weighted_trajectory_drift_pct")
            ),
            "sleeve_weighted_trajectory_drift_pct_after": (
                after.get("buckets", {}).get("sleeve", {}).get("weighted_trajectory_drift_pct")
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "scope": "observe_only_live_drift_measurement",
        },
        "decision_basis": (
            "Accept measurement repair if hot warehouse coverage removes current "
            "missing_entry_bar rows without changing orders, ranking, sizing, or exits."
        ),
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BEFORE_PATH.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
    AFTER_PATH.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": ARTIFACT_PATH.as_posix(),
                "before": BEFORE_PATH.as_posix(),
                "after": AFTER_PATH.as_posix(),
                "delta": artifact["delta"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
