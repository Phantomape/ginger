"""Daily live-vs-model drift reconciliation for the real-money book (exp-20260706-019).

Contract: docs/live_drift_reconciliation.md. For every long position in
operator_inputs/open_positions.json this builds one ledger row comparing the
moomoo-realized state against the backtest fill model's expectation for the
same (ticker, entry_date):

  fill_drift_pct       = avg_cost / modeled_entry_price - 1      (paid more?)
  realized_return_pct  = (market_val/shares) / avg_cost - 1      (moomoo mark)
  modeled_return_pct   = close_asof / modeled_entry_price - 1    (model mark)
  trajectory_drift_pct = realized - modeled                      (cumulative gap)

Observe-only: reads positions and OHLCV, writes data/live_pilot/live_drift/,
never touches orders, ranking, sizing, or exits. Exit-side reconciliation
(closed trades) is v2, gated on a materialized moomoo deal-history surface —
see the doc's reopen condition.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from data_paths import DATA_ROOT, atomic_write_json
    from fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_paths import DATA_ROOT, atomic_write_json
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage

RULE_VERSION = "live_drift_reconciliation_v1"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
DEFAULT_SURFACE_DIR = DATA_ROOT / "live_pilot" / "live_drift"
DEFAULT_LEDGER_PATH = DEFAULT_SURFACE_DIR / "ledger.jsonl"
DEFAULT_STATE_PATH = DEFAULT_SURFACE_DIR / "state.json"
WAREHOUSE_PATHS = (
    DATA_ROOT / "warehouse" / "warehouse_main_hot.sqlite",
    DATA_ROOT / "warehouse" / "warehouse_main.sqlite",
    DATA_ROOT / "tmp" / "warehouse_main_alpha_search_readcopy.sqlite",
)

# Alert thresholds (docs/live_drift_reconciliation.md): core-bucket notional-
# weighted trajectory drift below -1.5% for 10 consecutive sessions, or mean
# fill drift above +30bp, counts as an execution/model drift event.
ALERT_TRAJECTORY_DRIFT_PCT = -0.015
ALERT_CONSECUTIVE_SESSIONS = 10
ALERT_MEAN_FILL_DRIFT_PCT = 0.003

# moomoo avg_cost is the blended cost across ALL fills while entry_date is the
# FIRST fill's date, so a scaled-into position shows a huge fake "fill drift"
# vs the first session's open (observed +38% on legacy adds, first live run
# 2026-07-06). Rows beyond this threshold are flagged suspect_multi_fill and
# excluded from bucket aggregates and alerts.
SUSPECT_FILL_DRIFT_PCT = 0.10

_DISCRETIONARY_MARKERS = {"legacy", "manual", "discretionary", "operator", ""}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _round(value: Any, digits: int) -> float | None:
    out = _float_or_none(value)
    return round(out, digits) if out is not None else None


def strategy_bucket(position: dict[str, Any]) -> str:
    sleeve = str(position.get("sleeve") or "").strip().lower()
    opened_by = str(position.get("opened_by_strategy") or "").strip().lower()
    if sleeve in ("discretionary",) or opened_by in _DISCRETIONARY_MARKERS:
        return "discretionary_legacy"
    if sleeve and sleeve not in ("core",):
        return "sleeve"
    return "core"


def _bars_from_warehouse(ticker: str) -> list[dict[str, Any]]:
    last_error = None
    for path in WAREHOUSE_PATHS:
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


def reconcile_position(
    position: dict[str, Any],
    bars: list[dict[str, Any]],
    as_of: str,
) -> dict[str, Any]:
    """One ledger row for one long position; fail-safe with a reason."""
    ticker = str(position.get("ticker") or "").upper()
    row: dict[str, Any] = {
        "asof_date": str(as_of)[:10],
        "position_id": position.get("position_id"),
        "ticker": ticker,
        "strategy_bucket": strategy_bucket(position),
        "entry_date": str(position.get("entry_date") or "")[:10] or None,
        "shares": _float_or_none(position.get("shares")),
        "avg_cost": _float_or_none(position.get("avg_cost")),
        "market_val": _float_or_none(position.get("market_val")),
        "unrealized_pl": _float_or_none(position.get("unrealized_pl")),
        "rule_version": RULE_VERSION,
        "reconcilable": False,
        "reason": None,
    }
    if str(position.get("direction") or "long").lower() != "long":
        row["reason"] = "non_long_direction_v2"
        return row
    if not row["entry_date"]:
        row["reason"] = "missing_entry_date"
        return row
    if row["avg_cost"] is None or row["avg_cost"] <= 0 or not row["shares"]:
        row["reason"] = "missing_cost_basis"
        return row

    by_date = {str(b.get("date") or "")[:10]: b for b in bars}
    dates = sorted(by_date)
    entry_bar = by_date.get(row["entry_date"])
    if entry_bar is None:
        # entry on a non-session date: use the first session at/after it
        later = [d for d in dates if d >= row["entry_date"]]
        entry_bar = by_date.get(later[0]) if later else None
    entry_open = _float_or_none(entry_bar.get("open")) if entry_bar else None
    if entry_open is None or entry_open <= 0:
        row["reason"] = "missing_entry_bar"
        return row
    asof_dates = [d for d in dates if d <= row["asof_date"]]
    close_asof = _float_or_none(by_date[asof_dates[-1]].get("close")) if asof_dates else None
    if close_asof is None or close_asof <= 0:
        row["reason"] = "missing_asof_close"
        return row

    modeled_entry = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
    realized_mark = (
        row["market_val"] / row["shares"]
        if row["market_val"] is not None and row["shares"]
        else None
    )
    if realized_mark is None or realized_mark <= 0:
        row["reason"] = "missing_market_val"
        return row

    fill_drift = row["avg_cost"] / modeled_entry - 1.0
    realized_return = realized_mark / row["avg_cost"] - 1.0
    modeled_return = close_asof / modeled_entry - 1.0
    row.update(
        {
            "reconcilable": True,
            "modeled_entry_price": _round(modeled_entry, 4),
            "close_asof": _round(close_asof, 4),
            "fill_drift_pct": _round(fill_drift, 6),
            "realized_return_pct": _round(realized_return, 6),
            "modeled_return_pct": _round(modeled_return, 6),
            "trajectory_drift_pct": _round(realized_return - modeled_return, 6),
            "suspect_multi_fill": abs(fill_drift) > SUSPECT_FILL_DRIFT_PCT,
        }
    )
    return row


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = buckets.setdefault(
            row["strategy_bucket"],
            {"positions": 0, "reconciled": 0, "notional_usd": 0.0, "_dw": 0.0, "_fd": []},
        )
        bucket["positions"] += 1
        if not row.get("reconcilable"):
            continue
        bucket["reconciled"] += 1
        if row.get("suspect_multi_fill"):
            bucket["suspect_multi_fill"] = bucket.get("suspect_multi_fill", 0) + 1
            continue
        notional = row.get("market_val") or 0.0
        bucket["notional_usd"] += notional
        bucket["_dw"] += notional * (row.get("trajectory_drift_pct") or 0.0)
        bucket["_fd"].append(row.get("fill_drift_pct") or 0.0)
    for bucket in buckets.values():
        notional = bucket["notional_usd"]
        bucket["weighted_trajectory_drift_pct"] = (
            round(bucket.pop("_dw") / notional, 6) if notional > 0 else None
        )
        fills = bucket.pop("_fd")
        bucket["mean_fill_drift_pct"] = (
            round(sum(fills) / len(fills), 6) if fills else None
        )
        bucket["notional_usd"] = round(notional, 2)
    return buckets


def evaluate_drift_alert(
    ledger_rows: list[dict[str, Any]],
    bucket: str = "core",
) -> dict[str, Any]:
    """Consecutive-breach alert over the per-session core-bucket weighted drift."""
    by_asof: dict[str, list[dict[str, Any]]] = {}
    for row in ledger_rows:
        if (
            row.get("strategy_bucket") == bucket
            and row.get("reconcilable")
            and not row.get("suspect_multi_fill")
        ):
            by_asof.setdefault(row["asof_date"], []).append(row)
    sessions = sorted(by_asof)
    breaches = []
    for asof in sessions:
        rows = by_asof[asof]
        notional = sum(r.get("market_val") or 0.0 for r in rows)
        drift = (
            sum((r.get("market_val") or 0.0) * (r.get("trajectory_drift_pct") or 0.0) for r in rows)
            / notional
            if notional > 0
            else None
        )
        breaches.append(drift is not None and drift < ALERT_TRAJECTORY_DRIFT_PCT)
    consecutive = 0
    for breached in reversed(breaches):
        if not breached:
            break
        consecutive += 1
    latest_rows = by_asof.get(sessions[-1], []) if sessions else []
    fills = [r.get("fill_drift_pct") or 0.0 for r in latest_rows]
    mean_fill = sum(fills) / len(fills) if fills else None
    return {
        "bucket": bucket,
        "sessions_observed": len(sessions),
        "consecutive_breach_sessions": consecutive,
        "trajectory_alert": consecutive >= ALERT_CONSECUTIVE_SESSIONS,
        "fill_alert": mean_fill is not None and mean_fill > ALERT_MEAN_FILL_DRIFT_PCT,
        "latest_mean_fill_drift_pct": round(mean_fill, 6) if mean_fill is not None else None,
        "thresholds": {
            "trajectory_drift_pct": ALERT_TRAJECTORY_DRIFT_PCT,
            "consecutive_sessions": ALERT_CONSECUTIVE_SESSIONS,
            "mean_fill_drift_pct": ALERT_MEAN_FILL_DRIFT_PCT,
        },
    }


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_live_drift_reconciliation(
    *,
    as_of: str,
    positions: list[dict[str, Any]] | None = None,
    positions_path: Path | str = DEFAULT_POSITIONS_PATH,
    bars_fn: Any = None,
    persist: bool = True,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
    state_path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    """Build (and by default persist) today's reconciliation rows + summary."""
    as_of_date = str(as_of)[:10]
    if positions is None:
        try:
            payload = json.loads(Path(positions_path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "asof_date": as_of_date,
                "rule_version": RULE_VERSION,
                "status": "positions_unavailable",
                "error": str(exc),
            }
        positions = payload.get("positions") or []
        core = payload.get("core_positions") or []
        seen_ids = {p.get("position_id") for p in positions if isinstance(p, dict)}
        positions = positions + [
            p for p in core if isinstance(p, dict) and p.get("position_id") not in seen_ids
        ]

    lookup = bars_fn or _bars_from_warehouse
    rows: list[dict[str, Any]] = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        try:
            bars = lookup(ticker)
        except Exception as exc:
            rows.append(
                {
                    "asof_date": as_of_date,
                    "position_id": position.get("position_id"),
                    "ticker": ticker,
                    "strategy_bucket": strategy_bucket(position),
                    "rule_version": RULE_VERSION,
                    "reconcilable": False,
                    "reason": f"bars_unavailable: {exc}",
                }
            )
            continue
        rows.append(reconcile_position(position, bars, as_of_date))

    ledger_file = Path(ledger_path)
    history = _load_ledger(ledger_file)
    existing_keys = {(r.get("asof_date"), r.get("position_id")) for r in history}
    new_rows = [
        r for r in rows if (r.get("asof_date"), r.get("position_id")) not in existing_keys
    ]

    alert = evaluate_drift_alert(history + new_rows)
    state = {
        "asof_date": as_of_date,
        "generated_at": _utc_now_iso(),
        "rule_version": RULE_VERSION,
        "status": "ok",
        "position_count": len(rows),
        "reconciled_count": sum(1 for r in rows if r.get("reconcilable")),
        "unreconcilable": [
            {"ticker": r.get("ticker"), "reason": r.get("reason")}
            for r in rows
            if not r.get("reconcilable")
        ],
        "buckets": _bucket_summary(rows),
        "alert": alert,
        "appended_rows": len(new_rows),
        "contract": "docs/live_drift_reconciliation.md",
        "production_impact": "observe_only_no_orders_no_ranking_no_sizing",
    }

    if persist:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        if new_rows:
            with ledger_file.open("a", encoding="utf-8") as handle:
                for row in new_rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
        atomic_write_json(state, Path(state_path))
    return state
