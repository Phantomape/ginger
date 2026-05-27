"""exp-20260527-016: Kova entry-day-low protective stop shadow replay.

This replay reads the accepted default-off VCP top-2 rank-notional paper sleeve
from exp-20260526-007 and tests one Kova lifecycle exit variable:

``entry_day_low_minus_2pct_stop_v1``

The stop is PIT-conservative: the entry-day low is known only after the entry
day closes, so the stop can trigger starting on the next trading day. Entries,
candidate selection, ranking, rank-notional profile, universe, LLM/news, and
live/default orders are unchanged.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _flatten,
    _load_json,
    _load_snapshot,
    _now,
    _num,
    _repo_rel,
    _round,
    _safe,
    _write_json,
    _write_text,
)

QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from fill_model import SLIPPAGE_BPS_STOP, apply_stop_fill  # noqa: E402


EXPERIMENT_ID = "exp-20260527-016"
STEM = "kova_entry_day_low_stop_shadow_replay"
TRIAL_FAMILY = "kova_protective_stop_shadow_replay"
CHANGED_VARIABLE = "entry_day_low_minus_2pct_stop_v1"
RULE_VERSION = "entry_day_low_minus_2pct_stop_v1"
SOURCE_VARIANT = "rank2_125"

ENTRY_DAY_LOW_BUFFER_PCT = 0.02
MIN_TRIGGERED_TRADES = 20

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _row_date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") if "Date" in row else row.get("date"))


def _row_value(row: dict[str, Any], field: str) -> float | None:
    return _num(row.get(field) if field in row else row.get(field.lower()))


def _trade_path(
    rows: list[dict[str, Any]],
    *,
    entry_date: str,
    exit_date: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in sorted(rows, key=_row_date)
        if entry_date <= _row_date(row) <= exit_date
    ]


def _pnl_from_exit(
    *,
    entry_price: float,
    exit_price: float,
    notional: float,
) -> tuple[float, float]:
    pnl_pct = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    return round(pnl_pct, 6), round(notional * pnl_pct, 2)


def _stop_context(rows: list[dict[str, Any]], trade: dict[str, Any]) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = _date10(trade.get("entry_date"))
    exit_date = _date10(trade.get("exit_date"))
    entry_price = _num(trade.get("entry_price"))
    source_exit_price = _num(trade.get("exit_price"))
    notional = _num(trade.get("paper_notional_usd")) or _num(trade.get("base_paper_notional_usd"))
    source_pnl = _num(trade.get("pnl")) or 0.0
    source_pnl_pct = _num(trade.get("pnl_pct_net")) or 0.0
    shell = {
        "kova_entry_day_low_stop_rule_version": RULE_VERSION,
        "kova_entry_day_low_stop_buffer_pct": ENTRY_DAY_LOW_BUFFER_PCT,
        "kova_entry_day_low_stop_known_at": (
            "entry_day_close; stop can trigger from next trading day only"
        ),
        "kova_entry_day_low_stop_alters_orders": False,
        "kova_entry_day_low_stop_trade_enabled": False,
        "kova_entry_day_low_stop_slippage_bps": SLIPPAGE_BPS_STOP,
        "kova_entry_day_low_stop_round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "kova_entry_day_low_stop_source_pnl": _round(source_pnl, 2),
        "kova_entry_day_low_stop_source_pnl_pct_net": _round(source_pnl_pct, 6),
    }
    if not ticker or not entry_date or not exit_date or not entry_price or not notional:
        return {
            **shell,
            "kova_entry_day_low_stop_status": "unavailable_missing_trade_fields",
            "kova_entry_day_low_stop_triggered": False,
            "kova_entry_day_low_stop_pnl": _round(source_pnl, 2),
            "kova_entry_day_low_stop_pnl_pct_net": _round(source_pnl_pct, 6),
            "kova_entry_day_low_stop_pnl_delta_vs_source": 0.0,
        }
    path = _trade_path(rows, entry_date=entry_date, exit_date=exit_date)
    entry_rows = [row for row in path if _row_date(row) == entry_date]
    if not entry_rows:
        return {
            **shell,
            "kova_entry_day_low_stop_status": "unavailable_missing_entry_day_ohlcv",
            "kova_entry_day_low_stop_triggered": False,
            "kova_entry_day_low_stop_pnl": _round(source_pnl, 2),
            "kova_entry_day_low_stop_pnl_pct_net": _round(source_pnl_pct, 6),
            "kova_entry_day_low_stop_pnl_delta_vs_source": 0.0,
        }
    entry_low = _row_value(entry_rows[0], "Low")
    if entry_low is None or entry_low <= 0:
        return {
            **shell,
            "kova_entry_day_low_stop_status": "unavailable_missing_entry_day_low",
            "kova_entry_day_low_stop_triggered": False,
            "kova_entry_day_low_stop_pnl": _round(source_pnl, 2),
            "kova_entry_day_low_stop_pnl_pct_net": _round(source_pnl_pct, 6),
            "kova_entry_day_low_stop_pnl_delta_vs_source": 0.0,
        }
    stop_price = entry_low * (1.0 - ENTRY_DAY_LOW_BUFFER_PCT)
    trigger_row = None
    for row in path:
        row_date = _row_date(row)
        if row_date <= entry_date:
            continue
        low = _row_value(row, "Low")
        if low is not None and low <= stop_price:
            trigger_row = row
            break
    if trigger_row is None:
        return {
            **shell,
            "kova_entry_day_low_stop_status": "not_triggered",
            "kova_entry_day_low_stop_triggered": False,
            "kova_entry_day_low_stop_price": _round(stop_price, 4),
            "kova_entry_day_low": _round(entry_low, 4),
            "kova_entry_day_low_stop_exit_date": exit_date,
            "kova_entry_day_low_stop_exit_price": _round(source_exit_price, 4),
            "kova_entry_day_low_stop_pnl": _round(source_pnl, 2),
            "kova_entry_day_low_stop_pnl_pct_net": _round(source_pnl_pct, 6),
            "kova_entry_day_low_stop_pnl_delta_vs_source": 0.0,
        }
    raw_open = _row_value(trigger_row, "Open")
    raw_low = _row_value(trigger_row, "Low")
    if raw_open is None:
        return {
            **shell,
            "kova_entry_day_low_stop_status": "unavailable_missing_trigger_open",
            "kova_entry_day_low_stop_triggered": False,
            "kova_entry_day_low_stop_price": _round(stop_price, 4),
            "kova_entry_day_low": _round(entry_low, 4),
            "kova_entry_day_low_stop_pnl": _round(source_pnl, 2),
            "kova_entry_day_low_stop_pnl_pct_net": _round(source_pnl_pct, 6),
            "kova_entry_day_low_stop_pnl_delta_vs_source": 0.0,
        }
    exit_price = apply_stop_fill(raw_open, stop_price)
    pnl_pct, pnl = _pnl_from_exit(
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        notional=float(notional),
    )
    return {
        **shell,
        "kova_entry_day_low_stop_status": "triggered",
        "kova_entry_day_low_stop_triggered": True,
        "kova_entry_day_low": _round(entry_low, 4),
        "kova_entry_day_low_stop_price": _round(stop_price, 4),
        "kova_entry_day_low_stop_exit_date": _row_date(trigger_row),
        "kova_entry_day_low_stop_trigger_open": _round(raw_open, 4),
        "kova_entry_day_low_stop_trigger_low": _round(raw_low, 4),
        "kova_entry_day_low_stop_exit_price": _round(exit_price, 4),
        "kova_entry_day_low_stop_gap_fill": raw_open < stop_price,
        "kova_entry_day_low_stop_days_held": max(0, len([row for row in path if _row_date(row) <= _row_date(trigger_row)]) - 1),
        "kova_entry_day_low_stop_pnl": pnl,
        "kova_entry_day_low_stop_pnl_pct_net": pnl_pct,
        "kova_entry_day_low_stop_pnl_delta_vs_source": _round(pnl - source_pnl, 2),
    }


def _enrich_trades(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        rows = []
        for trade in source["target_trades_by_window"].get(label, []):
            ticker = str(trade.get("ticker") or "").upper()
            context = _stop_context(snapshot.get(ticker, []), trade)
            rows.append({**trade, "window": label, **context})
        out[label] = rows
    return out


def _trade_samples(rows: list[dict[str, Any]], *, pnl_field: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date") or row.get("date"),
                "entry_date": row.get("entry_date"),
                "source_exit_date": row.get("exit_date"),
                "stop_exit_date": row.get("kova_entry_day_low_stop_exit_date"),
                "rank": row.get("vcp_candidate_rank_on_signal_date"),
                "triggered": row.get("kova_entry_day_low_stop_triggered"),
                "entry_day_low": row.get("kova_entry_day_low"),
                "stop_price": row.get("kova_entry_day_low_stop_price"),
                "source_pnl": _round(row.get("pnl"), 2),
                "stop_pnl": _round(row.get(pnl_field), 2),
                "delta": row.get("kova_entry_day_low_stop_pnl_delta_vs_source"),
                "source_pnl_pct_net": row.get("pnl_pct_net"),
                "stop_pnl_pct_net": row.get("kova_entry_day_low_stop_pnl_pct_net"),
            }
        )
    return out


def _trade_summary(rows: list[dict[str, Any]], *, pnl_field: str) -> dict[str, Any]:
    pnl_values = [float(row.get(pnl_field) or 0.0) for row in rows]
    by_ticker_pnl: Counter[str] = Counter()
    by_window_count: Counter[str] = Counter()
    by_rank_count: Counter[str] = Counter()
    for row, pnl in zip(rows, pnl_values):
        by_ticker_pnl[str(row.get("ticker") or "").upper()] += pnl
        by_window_count[str(row.get("window") or "")] += 1
        by_rank_count[str(row.get("vcp_candidate_rank_on_signal_date") or "")] += 1
    positive_by_ticker = {
        ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0
    }
    positive_total = sum(positive_by_ticker.values())
    return {
        "trade_count": len(rows),
        "triggered_trade_count": sum(
            1 for row in rows if row.get("kova_entry_day_low_stop_triggered")
        ),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "win_rate": _round(
            sum(1 for value in pnl_values if value > 0) / len(pnl_values),
            6,
        )
        if pnl_values
        else None,
        "by_window_count": dict(sorted(by_window_count.items())),
        "by_rank_count": dict(sorted(by_rank_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "max_single_positive_pnl_share": _round(
            max(positive_by_ticker.values()) / positive_total,
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "positive_pnl_hhi": _round(
            sum((pnl / positive_total) ** 2 for pnl in positive_by_ticker.values()),
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "worst_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get(pnl_field) or 0.0)[:5],
            pnl_field=pnl_field,
        ),
        "best_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get(pnl_field) or 0.0, reverse=True)[:5],
            pnl_field=pnl_field,
        ),
    }


def _comparison(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_window: "OrderedDict[str, Any]" = OrderedDict()
    all_rows = _flatten(rows_by_window)
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        source_pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
        stop_pnl = sum(float(row.get("kova_entry_day_low_stop_pnl") or 0.0) for row in rows)
        triggered = sum(1 for row in rows if row.get("kova_entry_day_low_stop_triggered"))
        by_window[label] = {
            "trade_count": len(rows),
            "triggered_trade_count": triggered,
            "source_total_pnl": _round(source_pnl, 2),
            "stop_total_pnl": _round(stop_pnl, 2),
            "stop_pnl_delta_vs_source": _round(stop_pnl - source_pnl, 2),
            "source_summary": _trade_summary(rows, pnl_field="pnl"),
            "stop_summary": _trade_summary(rows, pnl_field="kova_entry_day_low_stop_pnl"),
        }
    source_total = sum(float(row.get("pnl") or 0.0) for row in all_rows)
    stop_total = sum(float(row.get("kova_entry_day_low_stop_pnl") or 0.0) for row in all_rows)
    triggered_total = sum(1 for row in all_rows if row.get("kova_entry_day_low_stop_triggered"))
    return {
        "aggregate": {
            "trade_count": len(all_rows),
            "triggered_trade_count": triggered_total,
            "source_total_pnl": _round(source_total, 2),
            "stop_total_pnl": _round(stop_total, 2),
            "stop_pnl_delta_vs_source": _round(stop_total - source_total, 2),
            "windows_pnl_improved": sum(
                1
                for row in by_window.values()
                if (row.get("stop_pnl_delta_vs_source") or 0) > 0
            ),
            "windows_pnl_regressed": sum(
                1
                for row in by_window.values()
                if (row.get("stop_pnl_delta_vs_source") or 0) < 0
            ),
        },
        "by_window": by_window,
        "triggered_summary": _trade_summary(
            [row for row in all_rows if row.get("kova_entry_day_low_stop_triggered")],
            pnl_field="kova_entry_day_low_stop_pnl",
        ),
        "not_triggered_summary": _trade_summary(
            [row for row in all_rows if not row.get("kova_entry_day_low_stop_triggered")],
            pnl_field="kova_entry_day_low_stop_pnl",
        ),
    }


def _decision(comparison: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    agg = comparison["aggregate"]
    triggered = agg["triggered_trade_count"]
    positive_delta = agg["stop_pnl_delta_vs_source"] > 0
    no_window_regression = agg["windows_pnl_regressed"] == 0
    evidence = {
        "triggered_trade_count": triggered,
        "triggered_trade_count_min": MIN_TRIGGERED_TRADES,
        "triggered_sample_passed": triggered >= MIN_TRIGGERED_TRADES,
        "aggregate_stop_pnl_delta_vs_source": agg["stop_pnl_delta_vs_source"],
        "aggregate_delta_positive": positive_delta,
        "windows_pnl_improved": agg["windows_pnl_improved"],
        "windows_pnl_regressed": agg["windows_pnl_regressed"],
        "no_window_pnl_regression": no_window_regression,
    }
    if triggered < MIN_TRIGGERED_TRADES:
        return (
            "observed_only_insufficient_trigger_sample_entry_day_low_stop",
            (
                "The entry-day-low minus 2% stop did not trigger on enough "
                "closed paper trades to justify a rule. Keep the source VCP "
                "top-2 rank-notional sleeve unchanged."
            ),
            evidence,
        )
    if positive_delta and no_window_regression:
        return (
            "observed_only_promising_entry_day_low_stop_shadow_replay",
            (
                "The Kova entry-day-low stop improved the frozen paper replay "
                "without a window PnL regression, but this run still does not "
                "promote an exit rule. A later closed Gate 1-4 replay is required."
            ),
            evidence,
        )
    return (
        "rejected_entry_day_low_stop_shadow_replay",
        (
            "The Kova entry-day-low stop failed the shadow replay gate. Keep "
            "the fixed 10-day VCP top-2 paper exit unchanged."
        ),
        evidence,
    )


def _build_payload() -> dict[str, Any]:
    source = _load_source_rank_profile()
    rows_by_window = _enrich_trades(source)
    all_rows = _flatten(rows_by_window)
    comparison = _comparison(rows_by_window)
    decision, interpretation, evidence = _decision(comparison)
    source_variant = source["variant"]
    source_trade_count = sum(len(rows) for rows in source["target_trades_by_window"].values())
    open_positions_audit = _audit_open_positions()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only" if decision.startswith("observed_only") else "rejected",
        "decision": decision,
        "created_at": _now(),
        "lane": "alpha_search",
        "registry_lane": "alpha_discovery",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "summary": interpretation,
        "alpha_hypothesis": (
            "Kova's entry-day-low protective stop may cut failed breakouts in "
            "the accepted default-off VCP top-2 rank-notional paper sleeve."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Exit/risk-allocation alpha: a PIT-conservative stop at entry "
                "day low minus 2% may improve paper sleeve replacement value."
            ),
            "2_history_check": {
                "exp-20260526-008": "Post-entry pivot failure was attribution-only.",
                "exp-20260526-022": "Higher-low base geometry was attribution-only.",
                "exp-20260526-037": "Kova lifecycle stop ideas remained not fully tested.",
                "exp-20260527-015": "Kova fundamental+RS proxy did not clear promotion bar.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: >=20 stop triggers, positive aggregate PnL "
                "delta, and no window PnL regression before any later replay."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "single_causal_variable_definition": {
            "name": CHANGED_VARIABLE,
            "entry_day_low_buffer_pct": ENTRY_DAY_LOW_BUFFER_PCT,
            "activation": "next trading day after entry date",
            "trigger": "daily Low <= entry_day_low * (1 - 0.02)",
            "fill_model": (
                "apply_stop_fill(open, stop_price): gap-down fills at open, "
                "otherwise at stop price, with stop-side sell slippage"
            ),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": (
                "This is a frozen paper replay of one exit variable only. It "
                "does not change shared strategy logic or live/default orders."
            ),
            "shadow_exit_gate": (
                "triggered trades >=20, aggregate stop PnL delta positive, "
                "and no window PnL regression."
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "source_paper_exit": "10 trading days after signal from exp007 source sleeve",
            "shadow_exit": "entry-day-low minus 2% stop, active next trading day",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
        },
        "gate1": {
            "passed": True,
            "baseline_core_stack": "exp-20260517-009 accepted core stack",
            "source_paper_baseline": "exp-20260526-007 rank2_125 VCP top-2 paper sleeve",
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get(
                    "expected_value_score_delta"
                ),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_open_position_fields": ["entry_date", "target_price"],
            "required_source_trade_fields": [
                "ticker",
                "entry_date",
                "exit_date",
                "entry_price",
                "paper_notional_usd",
                "pnl",
                "pnl_pct_net",
            ],
            "required_ohlcv_fields": ["Date", "Open", "Low"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "source_paper_survival_changed": False,
            "note": "Exit shadow replay on already selected exp007 paper trades.",
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": (
                "Observed-only frozen paper exit replay. No strategy exit rule is "
                "kept without a later closed Gate 1-4 replay."
            ),
            "decision_evidence": evidence,
        },
        "source_trade_count": source_trade_count,
        "enriched_trade_count": len(all_rows),
        "comparison": comparison,
        "target_trades_by_window": rows_by_window,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "metadata_surface_changed": False,
            "read_only_exit_replay": True,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_016_kova_entry_day_low_stop_shadow_replay.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not retune VCP entry, ranking, top-N, rank-notional profile, "
            "hold days absent stop, target, universe, LLM/news, Kova fundamentals, "
            "intraday timing, pyramiding, or live/default orders."
        ),
    }


def _comparison_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | trades | triggers | source pnl | stop pnl | delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["comparison"]["by_window"].items():
        lines.append(
            "| {label} | {trades} | {triggers} | {source} | {stop} | {delta} |".format(
                label=label,
                trades=row["trade_count"],
                triggers=row["triggered_trade_count"],
                source=row["source_total_pnl"],
                stop=row["stop_total_pnl"],
                delta=row["stop_pnl_delta_vs_source"],
            )
        )
    agg = payload["comparison"]["aggregate"]
    lines.append(
        "| aggregate | {trades} | {triggers} | {source} | {stop} | {delta} |".format(
            trades=agg["trade_count"],
            triggers=agg["triggered_trade_count"],
            source=agg["source_total_pnl"],
            stop=agg["stop_total_pnl"],
            delta=agg["stop_pnl_delta_vs_source"],
        )
    )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    agg = payload["comparison"]["aggregate"]
    triggered = payload["comparison"]["triggered_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Kova Entry-Day-Low Stop Shadow Replay",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Source",
        "",
        "- Source population: `exp-20260526-007` `rank2_125` selected paper trades.",
        "- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, ranking, LLM/news, universe, and live/default orders unchanged.",
        f"- Tested exit field: `{CHANGED_VARIABLE}`.",
        "",
        "## PnL Comparison",
        "",
        *_comparison_table(payload),
        "",
        "## Triggered Stop Readout",
        "",
        f"- Triggered trades: `{agg['triggered_trade_count']}`.",
        f"- Triggered stop total PnL: `{triggered['total_pnl']}`.",
        f"- Triggered stop average PnL: `{triggered['avg_pnl']}`.",
        f"- Triggered stop win rate: `{triggered['win_rate']}`.",
        "",
        "## Gate 4",
        "",
        "No strategy promotion was possible in this experiment because this is a read-only exit replay.",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": row.get("lane") or payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    existing = _existing_ticket()
    ticket_payload = {
        **existing,
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": "kova_entry_day_low_stop_shadow_replay",
        "mechanism_family": "kova_lifecycle_exit_risk_management",
        "trial_family": payload["trial_family"],
        "trial_variant_id": CHANGED_VARIABLE,
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 5),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "kova_lifecycle_stop_replay_on_existing_daily_ohlcv_path",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_016_kova_entry_day_low_stop_shadow_replay.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "must_not_touch": [
            "quant/backtester.py",
            "quant/run.py",
            "quant/volatility_contraction_paper_sleeve.py",
            "operator_inputs/open_positions.json",
        ],
        "locked_variables": [
            "core entries",
            "VCP compression and breakout",
            "QQQ/SPY gate",
            "top2 selection",
            "candidate ranking",
            "rank-notional profile",
            "sizing",
            "LLM/news",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "comparison": payload["comparison"]["aggregate"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
