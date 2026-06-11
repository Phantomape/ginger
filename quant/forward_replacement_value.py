"""Cost-adjusted replacement-value enrichment for closed forward paper-sleeve rows.

exp-20260608-021 found that every default-off paper sleeve fails the
``replacement_value_rows_present`` activation check because closed forward rows
never record what the same notional would have earned in a cash or liquid ETF
substitute over the same holding window. This module repairs that measurement
surface only. It is read-side enrichment: it never creates, removes, ranks,
sizes, or exits a position, and it never changes orders.

Comparator convention (fixed, recorded on every enriched row):

- comparator deploys the same notional in SPY and QQQ;
- comparator entry fill is the ETF open on ``entry_date`` with buy-side
  ``SLIPPAGE_BPS_ENTRY`` slippage (matching the sleeves' next-open entry);
- comparator exit fill is the ETF close on ``exit_date`` with sell-side
  ``SLIPPAGE_BPS_TARGET`` slippage;
- ``ROUND_TRIP_COST_PCT`` of notional is subtracted, matching sleeve cost
  handling;
- cash comparator earns zero, so replacement value versus cash equals the
  recorded paper pnl.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import atomic_write_json, data_artifact_path
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH
except ImportError:  # pragma: no cover - package-style import fallback
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import atomic_write_json, data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH


RULE_VERSION = "forward_replacement_value_v1"
COMPARATOR_TICKERS = ("SPY", "QQQ")
ARTIFACT_KEY = "paper_sleeves/forward_replacement_value.jsonl"

# Plausible bounds for a derived paper notional; outside this range the
# derivation is treated as failed rather than silently recorded.
MIN_PLAUSIBLE_NOTIONAL_USD = 500.0
MAX_PLAUSIBLE_NOTIONAL_USD = 2_000_000.0

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "default_off_attribution_only": True,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}


def _to_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_comparator_bars(warehouse_path=None, tickers=COMPARATOR_TICKERS):
    """Load daily open/close bars for comparator ETFs from the OHLCV warehouse."""
    path = Path(warehouse_path) if warehouse_path else Path(DEFAULT_WAREHOUSE_PATH)
    bars = {ticker: {} for ticker in tickers}
    if not path.exists():
        return bars
    con = sqlite3.connect(str(path))
    try:
        cur = con.cursor()
        marks = ",".join("?" for _ in tickers)
        cur.execute(
            "SELECT ticker, date, open, close FROM ohlcv WHERE ticker IN (" + marks + ")",
            list(tickers),
        )
        for ticker, date, open_px, close_px in cur.fetchall():
            open_f = _to_float(open_px)
            close_f = _to_float(close_px)
            if open_f is None or close_f is None:
                continue
            bars[str(ticker)][str(date)] = {"open": open_f, "close": close_f}
    finally:
        con.close()
    return bars


def _notional_for_row(row):
    """Best-effort recovery of the paper notional behind a closed row."""
    for key in ("notional_usd", "paper_notional_usd"):
        explicit = _to_float(row.get(key))
        if explicit and explicit > 0:
            return explicit, "explicit"

    pnl = _to_float(row.get("pnl"))
    entry_price = _to_float(row.get("entry_price"))
    exit_price = _to_float(row.get("exit_price"))
    price_net_ret = None
    if entry_price and exit_price and entry_price > 0:
        price_net_ret = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT

    net_return = _to_float(row.get("net_return_pct"))
    if pnl is not None and pnl != 0 and net_return not in (None, 0.0):
        candidates = []  # (|interpretation - price reference|, notional, label)
        for interp_ret, label in ((net_return / 100.0, "percent"), (net_return, "fraction")):
            if interp_ret == 0:
                continue
            notional = pnl / interp_ret
            if not (MIN_PLAUSIBLE_NOTIONAL_USD <= notional <= MAX_PLAUSIBLE_NOTIONAL_USD):
                continue
            if price_net_ret is not None:
                distance = abs(interp_ret - price_net_ret)
            else:
                # Without prices prefer the percent interpretation, the
                # dominant convention across event sleeves.
                distance = 0.0 if label == "percent" else 1.0
            candidates.append((distance, notional, label))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            _, notional, label = candidates[0]
            return round(notional, 2), "derived_from_net_return_" + label

    if pnl is not None and pnl != 0 and price_net_ret is not None:
        if abs(price_net_ret) > 1e-6:
            notional = pnl / price_net_ret
            if MIN_PLAUSIBLE_NOTIONAL_USD <= notional <= MAX_PLAUSIBLE_NOTIONAL_USD:
                return round(notional, 2), "derived_from_prices"

    return None, "missing"


def _comparator_pnl(bars, entry_date, exit_date, notional):
    entry_bar = bars.get(entry_date)
    exit_bar = bars.get(exit_date)
    if not entry_bar or not exit_bar:
        return None
    entry_fill = apply_slippage(entry_bar["open"], SLIPPAGE_BPS_ENTRY, "buy")
    exit_fill = apply_slippage(exit_bar["close"], SLIPPAGE_BPS_TARGET, "sell")
    if not entry_fill or entry_fill <= 0 or exit_fill is None:
        return None
    gross = (exit_fill / entry_fill) - 1.0
    pnl = notional * gross - notional * ROUND_TRIP_COST_PCT
    return {
        "entry_fill": round(entry_fill, 4),
        "exit_fill": round(exit_fill, 4),
        "net_pnl_usd": round(pnl, 2),
    }


def _closed_rows(state):
    for key in ("closed_positions", "closed_trades"):
        rows = state.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def enrich_state_closed_rows(state, bars_by_ticker, asof_date, sleeve_key=""):
    """Add replacement-value fields to closed rows that lack them.

    Mutates ``state`` in place and returns one artifact record per newly
    enriched row. Rows already carrying ``replacement_value_rule_version`` are
    left untouched, so the pass is idempotent.
    """
    records = []
    for row in _closed_rows(state):
        if row.get("replacement_value_rule_version"):
            continue
        pnl = _to_float(row.get("pnl"))
        entry_date = str(row.get("entry_date") or "")
        exit_date = str(row.get("exit_date") or row.get("entry_date") or "")
        notional, notional_method = _notional_for_row(row)

        status = "enriched"
        comparators = {}
        if pnl is None or not entry_date or not exit_date:
            status = "missing_row_fields"
        elif notional is None:
            status = "missing_notional"
        else:
            for ticker in COMPARATOR_TICKERS:
                comparators[ticker] = _comparator_pnl(
                    bars_by_ticker.get(ticker, {}), entry_date, exit_date, notional
                )
            if any(detail is None for detail in comparators.values()):
                status = "missing_comparator_bars"

        row["replacement_value_rule_version"] = RULE_VERSION
        row["replacement_value_asof"] = asof_date
        row["replacement_value_status"] = status
        row["replacement_value_notional_usd"] = notional
        row["replacement_value_notional_method"] = notional_method
        row["replacement_value_vs_cash_usd"] = round(pnl, 2) if pnl is not None else None
        for ticker in COMPARATOR_TICKERS:
            detail = comparators.get(ticker)
            field = "replacement_value_vs_" + ticker.lower() + "_usd"
            if pnl is not None and detail is not None:
                row[field] = round(pnl - detail["net_pnl_usd"], 2)
            else:
                row[field] = None
        row["replacement_value_comparator_detail"] = comparators

        records.append(
            {
                "rule_version": RULE_VERSION,
                "asof_date": asof_date,
                "sleeve_key": sleeve_key,
                "decision_id": row.get("decision_id"),
                "ticker": row.get("ticker"),
                "entry_date": entry_date or None,
                "exit_date": exit_date or None,
                "pnl_usd": round(pnl, 2) if pnl is not None else None,
                "notional_usd": notional,
                "notional_method": notional_method,
                "status": status,
                "replacement_value_vs_cash_usd": row["replacement_value_vs_cash_usd"],
                "replacement_value_vs_spy_usd": row["replacement_value_vs_spy_usd"],
                "replacement_value_vs_qqq_usd": row["replacement_value_vs_qqq_usd"],
                "comparator_detail": comparators,
            }
        )
    return records


def enrich_all_sleeve_states(
    asof_date,
    *,
    sleeves_root=None,
    bars_by_ticker=None,
    warehouse_path=None,
    artifact_path=None,
):
    """Enrich every ``data/paper_sleeves/*/state.json`` closed row in place.

    Appends one JSONL record per newly enriched row to the shared artifact and
    returns an observe-only summary. Safe to call repeatedly per day.
    """
    root = Path(sleeves_root) if sleeves_root else data_artifact_path("paper_sleeves")
    artifact = Path(artifact_path) if artifact_path else data_artifact_path(ARTIFACT_KEY)
    if bars_by_ticker is None:
        bars_by_ticker = load_comparator_bars(warehouse_path)

    summary = {
        "rule_version": RULE_VERSION,
        "asof_date": asof_date,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_impact": dict(PRODUCTION_IMPACT),
        "sleeves_scanned": 0,
        "rows_enriched": 0,
        "rows_enriched_by_status": {},
        "sleeves": {},
    }
    if not root.is_dir():
        summary["status"] = "no_sleeves_root"
        return summary

    new_records = []
    for state_path in sorted(root.glob("*/state.json")):
        sleeve_key = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary["sleeves"][sleeve_key] = {"status": "unreadable_state"}
            continue
        summary["sleeves_scanned"] += 1
        records = enrich_state_closed_rows(state, bars_by_ticker, asof_date, sleeve_key)
        if records:
            atomic_write_json(state, state_path)
            new_records.extend(records)
        summary["sleeves"][sleeve_key] = {
            "rows_enriched": len(records),
            "statuses": sorted({record["status"] for record in records}),
        }

    if new_records:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        with artifact.open("a", encoding="utf-8") as handle:
            for record in new_records:
                handle.write(json.dumps(record, sort_keys=True) + chr(10))
    summary["rows_enriched"] = len(new_records)
    by_status = {}
    for record in new_records:
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
    summary["rows_enriched_by_status"] = by_status
    summary["artifact_path"] = str(artifact)
    summary["status"] = "ok"
    return summary
