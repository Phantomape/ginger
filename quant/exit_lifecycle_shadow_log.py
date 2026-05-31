"""
Exit lifecycle shadow log - read-only production attribution sidecar.

Records advisory exit events (stop breach, trailing stop trigger, time stop,
target-price reach, high-urgency advisory) as they occur in the production run.
These events are logged to a daily JSONL file so that future closed-position
attribution can compare "signal fired at price X" against "actual close was Y."

This is a prerequisites measurement_repair step for proving exit lifecycle alpha.
It never changes entry, exit, ranking, sizing, heat, LLM, or orders.

exp-20260531-020
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

RULE_VERSION = "exit_lifecycle_shadow_log_v1"
DEFAULT_LOG_DIR = Path("data/exit_lifecycle")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_advisory_events(
    ticker: str,
    as_of: str,
    position_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return advisory exit events from a position_context dict.

    Inspects exit_signals and exit_levels to find triggered advisory events.
    """
    if not isinstance(position_context, dict):
        return []
    exit_signals = position_context.get("exit_signals") or {}
    exit_levels = position_context.get("exit_levels") or {}
    events: list[dict[str, Any]] = []

    # Hard stop breach
    breach = position_context.get("breach_status") or ""
    if breach in ("DELAYED_BREACH", "HISTORIC_BREACH"):
        events.append({
            "event_type": "hard_stop_breach",
            "breach_status": breach,
            "hard_stop_price": exit_levels.get("hard_stop_price"),
        })

    # High-urgency advisory
    if exit_signals.get("high_urgency"):
        events.append({
            "event_type": "high_urgency_advisory",
            "urgency_reasons": exit_signals.get("urgency_reasons") or [],
            "action_recommended": exit_signals.get("action") or "review",
        })

    # Trailing stop trigger
    trailing_stop = position_context.get("trailing_stop_from_20d_high")
    current_price = exit_levels.get("current_price_proxy") or None
    if trailing_stop and current_price and current_price < trailing_stop:
        events.append({
            "event_type": "trailing_stop_triggered",
            "trailing_stop_price": trailing_stop,
            "drawdown_from_hwm_pct": position_context.get("drawdown_from_20d_high_pct"),
            "hwm_source": position_context.get("high_water_mark_source"),
        })

    # Target price reached (SIGNAL_TARGET)
    signal_target = exit_levels.get("signal_target_price")
    if signal_target and current_price and current_price >= signal_target:
        events.append({
            "event_type": "signal_target_reached",
            "signal_target_price": signal_target,
        })

    # Time stop advisory
    days_held = exit_signals.get("days_held")
    time_stop_days = exit_levels.get("time_stop_trading_days")
    if days_held is not None and time_stop_days is not None and days_held >= time_stop_days:
        events.append({
            "event_type": "time_stop_advisory",
            "days_held": days_held,
            "time_stop_days": time_stop_days,
        })

    return events


def build_exit_lifecycle_snapshot(
    as_of: str,
    trend_signals_signals: dict[str, dict[str, Any]],
    open_positions: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a daily exit lifecycle snapshot for all held positions.

    Scans trend_signals_signals for tickers with position context, extracts
    advisory events, and returns a structured snapshot.

    Parameters
    ----------
    as_of:
        Today's ISO date string.
    trend_signals_signals:
        The per-ticker signals dict built in run.py (may have "position" sub-key).
    open_positions:
        The open_positions dict loaded from operator_inputs.
    """
    records: list[dict[str, Any]] = []
    positions_by_ticker = {
        str(pos.get("ticker") or "").upper(): pos
        for pos in ((open_positions or {}).get("positions") or [])
        if isinstance(pos, dict)
    }

    for ticker, sig in (trend_signals_signals or {}).items():
        pos_ctx = (sig or {}).get("position")
        if not isinstance(pos_ctx, dict):
            continue
        events = _extract_advisory_events(ticker, as_of, pos_ctx)
        if not events:
            # Still record a "no_event" row so we can track every active position
            events = [{"event_type": "no_advisory_event"}]

        pos_data = positions_by_ticker.get(ticker.upper()) or {}
        records.append({
            "rule_version": RULE_VERSION,
            "ticker": ticker,
            "as_of_date": as_of[:10],
            "generated_at": utc_now_iso(),
            "shares": pos_ctx.get("shares"),
            "avg_cost": pos_ctx.get("avg_cost"),
            "market_value_usd": pos_ctx.get("market_value_usd"),
            "unrealized_pnl_pct": pos_ctx.get("unrealized_pnl_pct"),
            "daily_return_pct": pos_ctx.get("daily_return_pct"),
            "breach_status": pos_ctx.get("breach_status"),
            "trailing_stop_from_hwm": pos_ctx.get("trailing_stop_from_20d_high"),
            "drawdown_from_hwm_pct": pos_ctx.get("drawdown_from_20d_high_pct"),
            "entry_date": pos_data.get("entry_date"),
            "target_price": pos_data.get("target_price"),
            "advisory_events": events,
            "has_advisory_event": any(
                e.get("event_type") != "no_advisory_event" for e in events
            ),
            "read_only": True,
            "alters_orders": False,
            "trade_enabled": False,
        })

    snapshot = {
        "rule_version": RULE_VERSION,
        "as_of_date": as_of[:10],
        "generated_at": utc_now_iso(),
        "position_count": len(records),
        "advisory_event_count": sum(1 for r in records if r["has_advisory_event"]),
        "records": records,
        "read_only": True,
        "alters_orders": False,
        "trade_enabled": False,
    }
    return snapshot


def persist_exit_lifecycle_snapshot(
    snapshot: dict[str, Any],
    log_dir: Path | str = DEFAULT_LOG_DIR,
) -> Path:
    """Append today's snapshot to the daily JSONL log.

    Creates one JSONL per trading day: data/exit_lifecycle/YYYYMMDD.jsonl.
    Each line is one position record.
    """
    as_of = str(snapshot.get("as_of_date") or "unknown")
    date_str = as_of.replace("-", "")
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    out_path = log_dir_path / f"exit_lifecycle_{date_str}.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for record in snapshot.get("records") or []:
            fh.write(json.dumps(record, default=str, sort_keys=True) + "\n")
    return out_path
