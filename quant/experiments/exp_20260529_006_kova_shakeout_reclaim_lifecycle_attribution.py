"""exp-20260529-006: Kova shakeout/reclaim lifecycle attribution.

This is an observed-only Kova direction from docs/kova-research-directions.md:
after a VCP paper entry, does an early shakeout that quickly reclaims the
entry/pivot level identify a better lifecycle bucket than early shakeouts that
do not reclaim?

No production strategy, backtester, ranking, entry, sizing, universe, LLM/news,
or live order path changes here. No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay import (  # noqa: E402
    REPO_ROOT,
    SOURCE_VARIANT,
    _audit_open_positions,
    _field,
    _find_index,
    _load_ohlcv_by_window,
    _load_source_rank_profile,
    _metric_summary,
    _num,
    _repo_rel,
    _row_date,
    _safe,
    _source_trade_rows,
    _write_json,
)
from exp_20260526_022_vcp_base_geometry_higher_low_attribution import WINDOWS  # noqa: E402


EXPERIMENT_ID = "exp-20260529-006"
STEM = "kova_shakeout_reclaim_lifecycle_attribution"
TRIAL_FAMILY = "kova_shakeout_reclaim_lifecycle"
TRIAL_VARIANT_ID = "kova_shakeout_reclaim_lifecycle_v1"
CHANGED_VARIABLE = "kova_shakeout_reclaim_lifecycle_bucket_v1"
RULE_VERSION = "kova_shakeout_reclaim_lifecycle_bucket_v1"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-007"
    / "vcp_rank_notional_profile.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

EARLY_WINDOW_TRADING_DAYS = 5
SHAKEOUT_LOW_RETURN_MAX = -0.04
RECLAIM_CLOSE_RETURN_MIN = 0.0
RECLAIM_CLOSE_LOCATION_MIN = 0.55
MIN_RECLAIM_TRADES = 10
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.50
ANTI_JS = "No JavaScript was used."

BUCKET_RECLAIM = "early_shakeout_reclaim"
BUCKET_NO_RECLAIM = "early_shakeout_no_reclaim"
BUCKET_NO_SHAKEOUT = "no_early_shakeout"
BUCKET_UNAVAILABLE = "unavailable"
BUCKET_ORDER = [
    BUCKET_RECLAIM,
    BUCKET_NO_RECLAIM,
    BUCKET_NO_SHAKEOUT,
    BUCKET_UNAVAILABLE,
]

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _infer_pivot_level(trade: dict[str, Any]) -> tuple[float | None, str]:
    signal_close = _num(trade.get("close") if "close" in trade else trade.get("Close"))
    breakout_pct = _num(trade.get("breakout_above_prior_20d_high_pct"))
    if signal_close is not None and signal_close > 0 and breakout_pct is not None:
        if breakout_pct > -0.99:
            return (
                signal_close / (1.0 + breakout_pct),
                "prior_20d_high_from_breakout_pct",
            )
    if signal_close is not None and signal_close > 0:
        return signal_close, "signal_close_fallback"
    return None, "missing_signal_close"


def _close_location(row: dict[str, Any]) -> float | None:
    high = _field(row, "High")
    low = _field(row, "Low")
    close = _field(row, "Close")
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _positive_pnl_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl = float(row.get("base_pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl": round(value, 4),
            "share": value / total if total > 0 else None,
        }
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_pnl_total": round(total, 4),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_pnl_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked,
    }


def _classify_trade(
    trade: dict[str, Any],
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    entry_date = _date10(trade.get("entry_date"))
    exit_date = _date10(trade.get("exit_date"))
    entry_price = _num(trade.get("entry_price"))
    base_pnl = _num(trade.get("pnl")) or 0.0
    base_notional = _num(trade.get("paper_notional_usd")) or 0.0
    base_pnl_pct = base_pnl / base_notional if base_notional else None
    pivot_level, pivot_source = _infer_pivot_level(trade)
    reclaim_level_values = [
        value
        for value in [entry_price, pivot_level]
        if value is not None and value > 0
    ]
    reclaim_level = max(reclaim_level_values) if reclaim_level_values else None

    result: dict[str, Any] = {
        "window": window,
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "vcp_candidate_rank_on_signal_date": trade.get("vcp_candidate_rank_on_signal_date"),
        "base_notional": round(base_notional, 4),
        "base_pnl": round(base_pnl, 4),
        "base_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "entry_price": round(entry_price, 4) if entry_price is not None else None,
        "pivot_level": round(pivot_level, 4) if pivot_level is not None else None,
        "pivot_source": pivot_source,
        "reclaim_level": round(reclaim_level, 4) if reclaim_level is not None else None,
        "lifecycle_bucket": BUCKET_UNAVAILABLE,
        "classification_status": "unavailable",
        "observed_early_days": 0,
        "first_shakeout_date": None,
        "first_reclaim_date": None,
        "first_reclaim_close_location": None,
        "first_reclaim_close_return": None,
        "max_high_return_early": None,
        "min_low_return_early": None,
        "close_return_at_early_end": None,
        "bars_available": False,
    }

    bars = ohlcv_by_window.get(window, {}).get(ticker, [])
    entry_idx = _find_index(bars, entry_date)
    exit_idx = _find_index(bars, exit_date)
    if not bars:
        result["classification_status"] = "missing_ohlcv_rows"
        return result
    if entry_idx is None or exit_idx is None:
        result["classification_status"] = "missing_entry_or_exit_bar"
        return result
    if entry_price is None or entry_price <= 0 or reclaim_level is None:
        result["classification_status"] = "missing_entry_or_reclaim_level"
        return result

    end_idx = min(exit_idx, entry_idx + EARLY_WINDOW_TRADING_DAYS - 1)
    early_bars = bars[entry_idx : end_idx + 1]
    if not early_bars:
        result["classification_status"] = "missing_early_window"
        return result

    shakeout_seen = False
    reclaim_seen = False
    max_high_return = None
    min_low_return = None
    close_return_at_end = None

    for row in early_bars:
        row_date = _row_date(row)
        high = _field(row, "High")
        low = _field(row, "Low")
        close = _field(row, "Close")
        if high is not None and high > 0:
            high_ret = high / entry_price - 1.0
            max_high_return = high_ret if max_high_return is None else max(max_high_return, high_ret)
        if low is not None and low > 0:
            low_ret = low / entry_price - 1.0
            min_low_return = low_ret if min_low_return is None else min(min_low_return, low_ret)
            if not shakeout_seen and low_ret <= SHAKEOUT_LOW_RETURN_MAX:
                shakeout_seen = True
                result["first_shakeout_date"] = row_date
        if close is not None and close > 0:
            close_return_at_end = close / entry_price - 1.0
            close_loc = _close_location(row)
            if (
                shakeout_seen
                and not reclaim_seen
                and close >= reclaim_level
                and close_return_at_end >= RECLAIM_CLOSE_RETURN_MIN
                and close_loc is not None
                and close_loc >= RECLAIM_CLOSE_LOCATION_MIN
            ):
                reclaim_seen = True
                result["first_reclaim_date"] = row_date
                result["first_reclaim_close_location"] = round(close_loc, 6)
                result["first_reclaim_close_return"] = round(close_return_at_end, 6)

    if shakeout_seen and reclaim_seen:
        bucket = BUCKET_RECLAIM
    elif shakeout_seen:
        bucket = BUCKET_NO_RECLAIM
    else:
        bucket = BUCKET_NO_SHAKEOUT

    result.update(
        {
            "bars_available": True,
            "lifecycle_bucket": bucket,
            "classification_status": "classified",
            "observed_early_days": len(early_bars),
            "max_high_return_early": _round(max_high_return, 6),
            "min_low_return_early": _round(min_low_return, 6),
            "close_return_at_early_end": _round(close_return_at_end, 6),
        }
    )
    return result


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _metric_summary(rows, "base_pnl")
    concentration = _positive_pnl_concentration(rows)
    summary.update(
        {
            "positive_pnl_concentration": concentration,
            "tickers": sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        }
    )
    return summary


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for bucket in BUCKET_ORDER:
        by_bucket[bucket] = _bucket_summary(
            [row for row in rows if row.get("lifecycle_bucket") == bucket]
        )

    by_window_bucket: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for window in WINDOWS:
        by_window_bucket[window] = OrderedDict()
        window_rows = [row for row in rows if row.get("window") == window]
        for bucket in BUCKET_ORDER:
            by_window_bucket[window][bucket] = _bucket_summary(
                [row for row in window_rows if row.get("lifecycle_bucket") == bucket]
            )

    reclaim = by_bucket[BUCKET_RECLAIM]
    no_reclaim = by_bucket[BUCKET_NO_RECLAIM]
    no_shakeout = by_bucket[BUCKET_NO_SHAKEOUT]
    reclaim_top_share = reclaim["positive_pnl_concentration"]["top_ticker_positive_pnl_share"]
    sample_ok = reclaim["trade_count"] >= MIN_RECLAIM_TRADES
    positive_ok = reclaim["total_pnl"] > 0
    comparator_ok = (
        no_reclaim["trade_count"] > 0
        and reclaim["avg_pnl"] > no_reclaim["avg_pnl"]
        and reclaim["return_on_notional"] > no_reclaim["return_on_notional"]
    )
    concentration_ok = reclaim_top_share is not None and reclaim_top_share <= MAX_SINGLE_POSITIVE_PNL_SHARE
    observed_gate_passed = sample_ok and positive_ok and comparator_ok and concentration_ok

    return {
        "source_population": _metric_summary(rows, "base_pnl"),
        "by_bucket": by_bucket,
        "by_window_bucket": by_window_bucket,
        "classification_counts": dict(Counter(row.get("classification_status") for row in rows)),
        "bucket_counts": dict(Counter(row.get("lifecycle_bucket") for row in rows)),
        "decision_evidence": {
            "observed_gate_passed": observed_gate_passed,
            "sample_ok": sample_ok,
            "positive_ok": positive_ok,
            "comparator_ok": comparator_ok,
            "concentration_ok": concentration_ok,
            "reclaim_trade_count": reclaim["trade_count"],
            "reclaim_total_pnl": reclaim["total_pnl"],
            "reclaim_avg_pnl": reclaim["avg_pnl"],
            "reclaim_return_on_notional": reclaim["return_on_notional"],
            "no_reclaim_trade_count": no_reclaim["trade_count"],
            "no_reclaim_total_pnl": no_reclaim["total_pnl"],
            "no_reclaim_avg_pnl": no_reclaim["avg_pnl"],
            "no_reclaim_return_on_notional": no_reclaim["return_on_notional"],
            "no_shakeout_trade_count": no_shakeout["trade_count"],
            "no_shakeout_total_pnl": no_shakeout["total_pnl"],
            "reclaim_avg_pnl_minus_no_reclaim": round(
                reclaim["avg_pnl"] - no_reclaim["avg_pnl"],
                4,
            ),
            "reclaim_return_minus_no_reclaim": round(
                reclaim["return_on_notional"] - no_reclaim["return_on_notional"],
                6,
            ),
            "reclaim_top_positive_ticker_share": reclaim_top_share,
            "min_reclaim_trades": MIN_RECLAIM_TRADES,
            "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
        },
    }


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys_to_skip = {"classified_trades", "by_window_bucket"}
    return {key: value for key, value in payload.items() if key not in keys_to_skip}


def _build_payload() -> dict[str, Any]:
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    trades = [row for rows in trades_by_window.values() for row in rows]
    ohlcv_by_window = _load_ohlcv_by_window()
    classified_rows = [_classify_trade(trade, ohlcv_by_window) for trade in trades]
    summaries = _summaries(classified_rows)
    evidence = summaries["decision_evidence"]

    if evidence["observed_gate_passed"]:
        decision = "observed_only_candidate_not_promoted"
        summary = (
            "The early shakeout/reclaim bucket passed the observed-only candidate "
            "screen, but it is not production-promoted without a full slot/heat/"
            "replacement-value replay."
        )
        rejection_reason = None
    else:
        decision = "observed_only_no_promotable_edge"
        failed = [
            name
            for name in ["sample_ok", "positive_ok", "comparator_ok", "concentration_ok"]
            if not evidence[name]
        ]
        summary = (
            "The early shakeout/reclaim bucket is not promotable from this closed "
            f"paper attribution. Failed checks: {', '.join(failed) or 'none'}."
        )
        rejection_reason = summary

    timestamp = _now()
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOCS_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(SOURCE_ARTIFACT),
    ]
    before_metrics = summaries["source_population"]
    after_metrics = summaries["by_bucket"][BUCKET_RECLAIM]
    no_reclaim_metrics = summaries["by_bucket"][BUCKET_NO_RECLAIM]
    delta_metrics = {
        "avg_pnl_vs_no_reclaim": evidence["reclaim_avg_pnl_minus_no_reclaim"],
        "return_on_notional_vs_no_reclaim": evidence["reclaim_return_minus_no_reclaim"],
        "reclaim_trade_count": evidence["reclaim_trade_count"],
        "no_reclaim_trade_count": evidence["no_reclaim_trade_count"],
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
    }
    actual_success = 1 if evidence["observed_gate_passed"] else 0
    predicted_success_probability = 0.25

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "registry_lane": "alpha_discovery",
        "lane": "alpha_discovery",
        "decision": decision,
        "summary": summary,
        "hypothesis": (
            "Kova VCP trades with an early shakeout that quickly reclaim entry/"
            "pivot may identify a better hold or future re-entry lifecycle "
            "bucket than early shakeouts that fail to reclaim."
        ),
        "change_summary": (
            "Observed-only attribution buckets accepted exp-20260526-007 VCP "
            "top-2 paper trades by early shakeout/reclaim behavior; no trading "
            "policy changed."
        ),
        "change_type": "observed_only_lifecycle_attribution",
        "mechanism_family": "kova_vcp_lifecycle_reentry",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260426-047",
            "exp-20260426-051",
            "exp-20260426-060",
            "exp-20260528-002",
            "exp-20260528-016",
            "exp-20260528-031",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "existing_closed_paper_lifecycle_rows",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "early_window_trading_days_including_entry": EARLY_WINDOW_TRADING_DAYS,
            "shakeout_low_return_max": SHAKEOUT_LOW_RETURN_MAX,
            "reclaim_close_return_min": RECLAIM_CLOSE_RETURN_MIN,
            "reclaim_close_location_min": RECLAIM_CLOSE_LOCATION_MIN,
            "reclaim_level": "max(entry_price, inferred_prior_20d_high_pivot)",
            "min_reclaim_trades": MIN_RECLAIM_TRADES,
            "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
            "anti_js": ANTI_JS,
        },
        "date_range": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Exit/re-entry lifecycle attribution: early shakeout plus quick "
                "reclaim may separate recoverable VCP trades from failed breakouts."
            ),
            "1_playbook_alignment": (
                "Follows the Kova document's open shakeout and re-entry direction, "
                "while avoiding frozen stop, pocket-pivot, and simple low-MFE exits."
            ),
            "2_history_check": (
                "Prior reclaim entry scouts were not production-promoted; Kova "
                "entry-day-low/fixed/max-loss/high-volume weak-close/day-3 low-MFE "
                "exits failed. This specific post-entry bucket was not directly tested."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only candidate if reclaim bucket has at least 10 trades, "
                "positive PnL, better avg PnL and return on notional than no-reclaim, "
                "and top positive ticker share <= 50%."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260529_006_kova_shakeout_reclaim_lifecycle_attribution.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp-20260526-007 source sleeve",
            "paper_exit": "10 trading days after signal from exp-20260526-007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
            "observed_only_attribution": True,
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "baseline_result_file": _repo_rel(SOURCE_ARTIFACT),
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source["variant"].get("expected_value_score_delta"),
                "total_pnl_delta_vs_core": source["variant"].get("total_pnl_delta"),
                "target_trade_count": len(trades),
                "target_trade_summary": source["variant"].get("target_trade_summary"),
            },
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": _audit_open_positions().get("passed") is True,
            "open_positions": _audit_open_positions(),
            "required_trade_fields": [
                "ticker",
                "signal_date",
                "entry_date",
                "entry_price",
                "exit_date",
                "paper_notional_usd",
                "pnl",
                "breakout_above_prior_20d_high_pct",
            ],
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close"],
            "classification_coverage": summaries["classification_counts"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "core_survival_changed": False,
            "note": "No entry filter or exit rule is added; this buckets existing closed paper trades.",
        },
        "gate4": {
            "passed": evidence["observed_gate_passed"],
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": "Observed-only closed-paper lifecycle attribution; no production strategy rule changed.",
            "decision_evidence": evidence,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "comparator_metrics": {
            BUCKET_NO_RECLAIM: no_reclaim_metrics,
            BUCKET_NO_SHAKEOUT: summaries["by_bucket"][BUCKET_NO_SHAKEOUT],
        },
        "delta_metrics": delta_metrics,
        "bucket_metrics": summaries["by_bucket"],
        "window_bucket_metrics": summaries["by_window_bucket"],
        "bucket_counts": summaries["bucket_counts"],
        "classified_trades": classified_rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "prediction": {
            "success_probability": predicted_success_probability,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "sample_too_thin",
                "single_ticker_concentration",
                "no_edge_vs_no_reclaim",
            ],
            "confidence_reason": (
                "Kova documents explicitly leave shakeout/re-entry open, but adjacent "
                "simple stop and low-MFE exits failed and prior reclaim entry replays "
                "were not promotable."
            ),
            "recorded_at": "2026-05-29T05:11:04+00:00",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_success_probability,
            "brier_score": round((predicted_success_probability - actual_success) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "ev_prediction_error": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "pnl_prediction_error": 0.0,
            "predicted_failure_modes": [
                "sample_too_thin",
                "single_ticker_concentration",
                "no_edge_vs_no_reclaim",
            ],
            "realized_failure_mode": rejection_reason,
            "predicted_failure_mode_hit": actual_success == 0,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "full_shared_lifecycle_replay_with_slot_heat_and_replacement_value_accounting",
            "forward_vcp_rows_showing_reentry_after_actual_stop_or_exit",
            "evidence_that_reclaim_bucket_beats_no_reclaim_without_ticker_concentration",
        ],
        "related_files": related_files,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260529_006_kova_shakeout_reclaim_lifecycle_attribution.py"
        ),
        "why_not_other_changes": (
            "Did not alter VCP entries, rank-notional profile, ranking, sizing, "
            "universe, LLM/news, backtester, run.py, or live/default orders."
        ),
        "anti_js": ANTI_JS,
    }


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | trades | total pnl | avg pnl | return on notional | win rate | top positive ticker share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_metrics"].items():
        concentration = row["positive_pnl_concentration"]
        lines.append(
            "| {bucket} | {trades} | {pnl} | {avg} | {ret} | {win} | {share} |".format(
                bucket=bucket,
                trades=row["trade_count"],
                pnl=row["total_pnl"],
                avg=row["avg_pnl"],
                ret=row["return_on_notional"],
                win=row["win_rate"],
                share=concentration["top_ticker_positive_pnl_share"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | reclaim trades | reclaim pnl | no-reclaim trades | no-reclaim pnl | no-shakeout trades | no-shakeout pnl |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window, buckets in payload["window_bucket_metrics"].items():
        reclaim = buckets[BUCKET_RECLAIM]
        no_reclaim = buckets[BUCKET_NO_RECLAIM]
        no_shakeout = buckets[BUCKET_NO_SHAKEOUT]
        lines.append(
            "| {window} | {rt} | {rp} | {nt} | {np} | {st} | {sp} |".format(
                window=window,
                rt=reclaim["trade_count"],
                rp=reclaim["total_pnl"],
                nt=no_reclaim["trade_count"],
                np=no_reclaim["total_pnl"],
                st=no_shakeout["trade_count"],
                sp=no_shakeout["total_pnl"],
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        f"# {EXPERIMENT_ID} Kova Shakeout/Reclaim Lifecycle Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Evidence",
        "",
        f"- Reclaim trades: `{evidence['reclaim_trade_count']}`.",
        f"- Reclaim total PnL: `{evidence['reclaim_total_pnl']}`.",
        f"- Reclaim avg PnL: `{evidence['reclaim_avg_pnl']}`.",
        f"- No-reclaim avg PnL: `{evidence['no_reclaim_avg_pnl']}`.",
        f"- Avg PnL edge vs no-reclaim: `{evidence['reclaim_avg_pnl_minus_no_reclaim']}`.",
        f"- Reclaim top positive ticker share: `{evidence['reclaim_top_positive_ticker_share']}`.",
        f"- Gate checks: sample `{evidence['sample_ok']}`, positive `{evidence['positive_ok']}`, comparator `{evidence['comparator_ok']}`, concentration `{evidence['concentration_ok']}`.",
        "",
        "## Bucket Metrics",
        "",
        *_bucket_table(payload),
        "",
        "## Window Buckets",
        "",
        *_window_table(payload),
        "",
        "## Related Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _build_card(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        'status: "observed_only"',
        'lane: "alpha_discovery"',
        'change_type: "observed_only_lifecycle_attribution"',
        'mechanism_family: "kova_vcp_lifecycle_reentry"',
        f'trial_family: "{TRIAL_FAMILY}"',
        f'trial_variant_id: "{TRIAL_VARIANT_ID}"',
        f'changed_variable: "{CHANGED_VARIABLE}"',
        'new_evidence_type: "existing_closed_paper_lifecycle_rows"',
        f'updated_at: "{payload["timestamp"]}"',
        'hub_repo_id: "ginger/experiments/exp-20260529-006"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Reclaim trades: `{evidence['reclaim_trade_count']}`",
        f"- Reclaim total PnL: `{evidence['reclaim_total_pnl']}`",
        f"- Reclaim avg PnL minus no-reclaim: `{evidence['reclaim_avg_pnl_minus_no_reclaim']}`",
        f"- Top positive ticker share: `{evidence['reclaim_top_positive_ticker_share']}`",
        "",
        "## Reserved Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(_log_payload(payload)), ensure_ascii=True, sort_keys=True)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "decision": payload["decision"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": f"experiments/manifests/{EXPERIMENT_ID}.json",
        "result_files": {
            "json": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "report": _repo_rel(ARTIFACT_MD),
        },
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**item, **row}
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    registry["updated_at"] = payload["timestamp"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    log_payload = _log_payload(payload)
    _write_json(LOG_JSON, log_payload)
    ticket = {
        "artifact_file": _repo_rel(OUT_JSON),
        "baseline_result_file": _repo_rel(SOURCE_ARTIFACT),
        "change_type": payload["change_type"],
        "completed_at": payload["timestamp"],
        "decision": payload["decision"],
        "experiment_uid": "expuid-426e0b15e6334c3e",
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "owner": "codex",
        "prior_trial_count": payload["prior_trial_count"],
        "result_file": _repo_rel(LOG_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "updated_at": payload["timestamp"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_DIR),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            f"experiments/manifests/{EXPERIMENT_ID}.json",
            _repo_rel(ARTIFACT_MD),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
            "docs/kova-research-directions.md",
            "docs/alpha-optimization-playbook.md",
            "docs/current_state.md",
            "docs/data_edge_context_layers.md",
        ],
        "locked_variables": [CHANGED_VARIABLE],
        "acceptance_rule": (
            "Observed-only candidate if the shakeout_reclaim bucket has at least "
            "10 trades, positive total PnL, higher average PnL than "
            "shakeout_no_reclaim, and no single positive ticker exceeds 50 "
            "percent of positive PnL."
        ),
        "prediction": payload["prediction"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = _build_payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "bucket_counts": payload["bucket_counts"],
                "delta_metrics": payload["delta_metrics"],
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
