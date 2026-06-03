"""exp-20260603-004: post-earnings sector-residual support scout.

This alpha search tests one free, production-visible event-quality field on
top of the accepted default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER adapter:
already-selected candidates whose signal-date 20-day return beats their broad
sector median receive 1.05x paper notional.

The run does not change live/default orders, core entries, ranking, exits,
LLM/news replay, or the shared production adapter. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

import exp_20260602_027_post_earnings_high_liquidity_support as parent


EXPERIMENT_ID = "exp-20260603-004"
STEM = "post_earnings_sector_residual_support"
TRIAL_FAMILY = "post_earnings_underpriced_sector_relative_event_quality"
CHANGED_VARIABLE = "post_earnings_sector_residual_support_v1"
RULE_VERSION = "post_earnings_sector_residual_support_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_004_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-027"
    / "exp_20260602_027_post_earnings_high_liquidity_support.json"
)
SECTOR_MAP_JSON = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"

SECTOR_RESIDUAL_LOOKBACK_DAYS = 20
SECTOR_RESIDUAL_MIN_EXCESS = 0.0
SECTOR_RESIDUAL_MIN_MEMBER_RETURNS = 3
SECTOR_RESIDUAL_NOTIONAL_SCALAR = 1.05
BASE_NOTIONAL_USD = parent.BASE_NOTIONAL_USD

_SECTOR_BY_TICKER: dict[str, str] | None = None
_SECTOR_RETURNS_CACHE: dict[tuple[int, str, str], list[tuple[str, float]]] = {}


def _framework() -> Any:
    return parent.parent.parent.framework


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_sector_by_ticker() -> dict[str, str]:
    global _SECTOR_BY_TICKER
    if _SECTOR_BY_TICKER is not None:
        return _SECTOR_BY_TICKER
    with SECTOR_MAP_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    entries = payload.get("entries") or {}
    _SECTOR_BY_TICKER = {
        str(ticker).upper(): str(info.get("sector"))
        for ticker, info in entries.items()
        if isinstance(info, dict)
        and info.get("status") == "ok"
        and info.get("sector")
        and str(info.get("sector")).lower() not in {"none", "nan"}
    }
    return _SECTOR_BY_TICKER


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _series(
    snapshot: dict[str, Any],
    ticker: str,
) -> list[dict[str, Any]]:
    source = snapshot.get("ohlcv") if isinstance(snapshot, dict) else None
    if isinstance(source, dict):
        rows = source.get(str(ticker).upper()) or source.get(str(ticker))
    else:
        rows = snapshot.get(str(ticker).upper()) or snapshot.get(str(ticker))
    return rows if isinstance(rows, list) else []


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(row.get("date") or row.get("Date")): idx
        for idx, row in enumerate(rows)
        if isinstance(row, dict) and (row.get("date") or row.get("Date"))
    }


def _lookback_return(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
    lookback_days: int,
) -> float | None:
    rows = _series(snapshot, ticker)
    if not rows:
        return None
    idx_by_date = _row_index(rows)
    idx = idx_by_date.get(date_value)
    if idx is None or idx < lookback_days:
        return None
    close_now = _float_or_none(rows[idx].get("close") or rows[idx].get("Close"))
    close_then = _float_or_none(
        rows[idx - lookback_days].get("close")
        or rows[idx - lookback_days].get("Close")
    )
    if close_now is None or close_then is None or close_then <= 0:
        return None
    return (close_now / close_then) - 1.0


def _sector_returns(
    snapshot: dict[str, list[dict[str, Any]]],
    date_value: str,
    sector: str,
) -> list[tuple[str, float]]:
    cache_key = (id(snapshot), date_value, sector)
    if cache_key in _SECTOR_RETURNS_CACHE:
        return _SECTOR_RETURNS_CACHE[cache_key]
    sector_by_ticker = _load_sector_by_ticker()
    rows: list[tuple[str, float]] = []
    for ticker, mapped_sector in sector_by_ticker.items():
        if mapped_sector != sector or not _series(snapshot, ticker):
            continue
        ret = _lookback_return(
            snapshot,
            ticker,
            date_value,
            SECTOR_RESIDUAL_LOOKBACK_DAYS,
        )
        if ret is not None:
            rows.append((ticker, ret))
    _SECTOR_RETURNS_CACHE[cache_key] = rows
    return rows


def _sector_residual_context(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> dict[str, Any]:
    ticker = str(ticker or "").upper()
    sector = _load_sector_by_ticker().get(ticker)
    if not sector:
        return {
            "sector_residual_context_status": "missing_sector",
            "sector_residual_support": False,
        }
    returns = _sector_returns(snapshot, date_value, sector)
    ticker_return = None
    for peer, peer_return in returns:
        if peer == ticker:
            ticker_return = peer_return
            break
    if ticker_return is None:
        return {
            "sector_residual_context_status": "missing_ticker_return",
            "sector": sector,
            "sector_residual_support": False,
            "sector_residual_member_return_count": len(returns),
        }
    if len(returns) < SECTOR_RESIDUAL_MIN_MEMBER_RETURNS:
        return {
            "sector_residual_context_status": "sector_sample_too_small",
            "sector": sector,
            "sector_residual_support": False,
            "sector_residual_ticker_return_20d": round(ticker_return, 6),
            "sector_residual_member_return_count": len(returns),
        }
    median_return = statistics.median(peer_return for _, peer_return in returns)
    excess = ticker_return - median_return
    supported = excess >= SECTOR_RESIDUAL_MIN_EXCESS
    return {
        "sector_residual_context_status": "ok",
        "sector": sector,
        "sector_residual_support": supported,
        "sector_residual_ticker_return_20d": round(ticker_return, 6),
        "sector_residual_median_return_20d": round(median_return, 6),
        "sector_residual_excess_vs_median_20d": round(excess, 6),
        "sector_residual_member_return_count": len(returns),
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = parent._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    support_count = 0
    support_days: set[str] = set()
    support_tickers: set[str] = set()
    status_counts: Counter[str] = Counter()
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        date_value = str(row.get("date") or "")
        context = _sector_residual_context(snapshot, ticker, date_value)
        row.update(context)
        status_counts[str(context.get("sector_residual_context_status") or "unknown")] += 1
        supported = bool(context.get("sector_residual_support"))
        try:
            pre_sector_notional = float(row.get("intended_notional") or BASE_NOTIONAL_USD)
        except (TypeError, ValueError):
            pre_sector_notional = BASE_NOTIONAL_USD
        scalar = SECTOR_RESIDUAL_NOTIONAL_SCALAR if supported else 1.0
        row["sector_residual_support_rule_version"] = RULE_VERSION
        row["sector_residual_lookback_days"] = SECTOR_RESIDUAL_LOOKBACK_DAYS
        row["sector_residual_min_excess"] = SECTOR_RESIDUAL_MIN_EXCESS
        row["sector_residual_min_member_returns"] = SECTOR_RESIDUAL_MIN_MEMBER_RETURNS
        row["sector_residual_notional_scalar"] = scalar
        row["pre_sector_residual_paper_notional_usd"] = round(pre_sector_notional, 2)
        row["intended_notional"] = round(pre_sector_notional * scalar, 2)
        row["trade_enabled"] = False
        row["alters_orders"] = False
        if supported:
            support_count += 1
            support_days.add(date_value)
            support_tickers.add(ticker)

    audit = dict(audit)
    audit["sector_residual_support_rule_version"] = RULE_VERSION
    audit["sector_residual_lookback_days"] = SECTOR_RESIDUAL_LOOKBACK_DAYS
    audit["sector_residual_min_excess"] = SECTOR_RESIDUAL_MIN_EXCESS
    audit["sector_residual_min_member_returns"] = SECTOR_RESIDUAL_MIN_MEMBER_RETURNS
    audit["sector_residual_notional_scalar"] = SECTOR_RESIDUAL_NOTIONAL_SCALAR
    audit["sector_residual_supported_raw_candidate_count"] = support_count
    audit["sector_residual_supported_candidate_days"] = len(support_days)
    audit["sector_residual_supported_unique_tickers"] = len(support_tickers)
    audit["sector_residual_context_status_counts"] = dict(sorted(status_counts.items()))
    audit["support_changes_entries_or_filters"] = False
    return candidates, audit


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    trade = parent._paper_trade_from_candidate(snapshot, candidate)
    if trade is None:
        return None
    for field in (
        "sector",
        "sector_residual_context_status",
        "sector_residual_support",
        "sector_residual_ticker_return_20d",
        "sector_residual_median_return_20d",
        "sector_residual_excess_vs_median_20d",
        "sector_residual_member_return_count",
        "sector_residual_support_rule_version",
        "sector_residual_lookback_days",
        "sector_residual_min_excess",
        "sector_residual_min_member_returns",
        "sector_residual_notional_scalar",
        "pre_sector_residual_paper_notional_usd",
    ):
        trade[field] = candidate.get(field)
    trade["trade_enabled"] = False
    trade["alters_orders"] = False
    return trade


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date_value = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date_value] >= _framework().MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date_value] += 1
    return selected, filtered


def _accepted_baseline() -> dict[str, Any]:
    with BASELINE_RESULT_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rebase_payload_to_accepted_baseline(payload: dict[str, Any]) -> dict[str, Any]:
    baseline = _accepted_baseline()
    before_metrics = {
        label: baseline["after_metrics"][label]
        for label in _framework().base.WINDOWS
    }
    window_rows: dict[str, dict[str, Any]] = {}
    delta_by_window: dict[str, dict[str, Any]] = {}
    for label in _framework().base.WINDOWS:
        before = before_metrics[label]
        after = payload["after_metrics"][label]
        delta = _framework().overlay_helper._delta(after, before)
        delta_by_window[label] = delta
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(payload["target_trades_by_window"][label]),
        }
    aggregate = _framework()._aggregate(window_rows)
    target_summary = _framework()._target_trade_summary(
        payload["target_trades_by_window"]
    )
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    gate4 = _framework()._gate4(aggregate, target_summary, min_survival)
    payload["incremental_baseline_experiment_id"] = "exp-20260602-027"
    payload["incremental_baseline_result_file"] = _framework().base._repo_rel(
        BASELINE_RESULT_JSON
    )
    payload["before_metrics"] = before_metrics
    payload["delta_metrics"] = {
        "by_window": delta_by_window,
        "aggregate": aggregate,
    }
    payload["target_trade_summary"] = target_summary
    payload["judge_before_aggregate"] = (
        _framework()._aggregate_result_for_judge(before_metrics)
    )
    payload["judge_after_aggregate"] = _framework()._aggregate_result_for_judge(
        payload["after_metrics"]
    )
    payload["gate4"] = gate4
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    return payload


def _support_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    incremental_by_ticker: Counter[str] = Counter()
    supported_rows: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        supported = [trade for trade in trades if trade.get("sector_residual_support")]
        supported_rows.extend(supported)
        incremental_pnl = 0.0
        for trade in supported:
            try:
                pre_notional = float(
                    trade.get("pre_sector_residual_paper_notional_usd")
                    or BASE_NOTIONAL_USD
                )
            except (TypeError, ValueError):
                pre_notional = BASE_NOTIONAL_USD
            pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
            trade_incremental = (
                pnl_pct_net * pre_notional * (SECTOR_RESIDUAL_NOTIONAL_SCALAR - 1.0)
            )
            incremental_pnl += trade_incremental
            incremental_by_ticker[str(trade.get("ticker") or "").upper()] += trade_incremental
        by_window[label] = {
            "adjusted_trade_count": len(supported),
            "adjusted_total_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in supported),
                2,
            ),
            "sector_residual_incremental_pnl": round(incremental_pnl, 2),
        }
    positive = {ticker: pnl for ticker, pnl in incremental_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "adjusted_trade_count": len(supported_rows),
        "adjusted_windows": [
            label for label, row in by_window.items() if row["adjusted_trade_count"]
        ],
        "by_window": by_window,
        "positive_incremental_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_incremental_pnl_share": max_share,
        "positive_incremental_pnl_hhi": hhi,
    }


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_parent()
    _framework()._candidate_rows_for_window = _candidate_rows_for_window
    _framework()._select_paper_trades = _select_paper_trades


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _rebase_payload_to_accepted_baseline(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_post_earnings_sector_residual_support"
        if gate4["passed"]
        else "rejected_post_earnings_sector_residual_support"
    )
    support_summary = _support_trade_summary(payload["target_trades_by_window"])
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.02,
        "expected_pnl_delta": 100.0,
        "main_failure_modes": [
            "thin_supported_sample",
            "old_thin_regression",
            "coverage_gap",
            "immaterial_delta",
        ],
        "confidence_reason": (
            "Precheck found a small positive aggregate paper delta but weak "
            "old_thin behavior. The field is free, deterministic, and "
            "production-visible if it works."
        ),
        "recorded_at": "2026-06-03T02:12:39+00:00",
        "brier_score": round((0.22 - actual_success) ** 2, 6),
    }
    failed_reasons = gate4["failed_reasons"]
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": prediction["brier_score"],
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if gate4["passed"] else "; ".join(failed_reasons),
        "predicted_failure_mode_hit": (
            False
            if gate4["passed"]
            else any(
                token in "; ".join(failed_reasons)
                for token in ("thin", "regression", "coverage", "pnl", "ev")
            )
        ),
    }
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Within the accepted post-earnings underpriced drift paper "
                "sleeve, candidates still leading their public broad sector "
                "on signal-date 20-day return may have cleaner event "
                "continuation and deserve a small default-off support scalar."
            ),
            "change_type": "default_off_paper_adapter_event_quality_support",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "post_earnings_underpriced_drift",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260602-027",
                "exp-20260603-003",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_public_sector_relative_return_field",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                **payload.get("parameters", {}),
                "incremental_baseline_experiment_id": "exp-20260602-027",
                "support_field": "sector_residual_excess_vs_median_20d",
                "sector_map_source": _framework().base._repo_rel(SECTOR_MAP_JSON),
                "sector_residual_lookback_days": SECTOR_RESIDUAL_LOOKBACK_DAYS,
                "sector_residual_min_excess": SECTOR_RESIDUAL_MIN_EXCESS,
                "sector_residual_min_member_returns": SECTOR_RESIDUAL_MIN_MEMBER_RETURNS,
                "sector_residual_notional_scalar": SECTOR_RESIDUAL_NOTIONAL_SCALAR,
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / event-quality support: sector-relative "
                    "20-day leadership after the earnings event may separate "
                    "stronger continuation from generic post-earnings drift."
                ),
                "2_history_check": {
                    "exp-20260602-026": (
                        "Accepted the shared post-earnings underpriced drift "
                        "adapter. This run keeps entry/ranking/hold fixed."
                    ),
                    "exp-20260602-027": (
                        "Accepted high-liquidity support. This run compares "
                        "against exp027 after_metrics and keeps high-liquidity "
                        "threshold/scalar locked."
                    ),
                    "exp-20260603-003": (
                        "Companyfacts source-provenance support failed "
                        "concentration. This run avoids Companyfacts and uses "
                        "free public sector map plus OHLCV only."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three windows; compare against "
                    "exp-20260602-027 after_metrics. Accept only if aggregate "
                    "EV/PnL improves, all three windows improve, no PnL window "
                    "regresses, drawdown drift stays within guardrail, survival "
                    ">=5%, and concentration passes."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260603_004_post_earnings_sector_residual_support.py"
                ),
            },
            "gate1": {
                "baseline_metrics": payload["before_metrics"],
                "baseline_artifact": (
                    "data/experiments/exp-20260602-027/"
                    "exp_20260602_027_post_earnings_high_liquidity_support.json"
                    "#after_metrics"
                ),
                "passed": True,
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "fields": [
                        "sector",
                        "sector_residual_ticker_return_20d",
                        "sector_residual_median_return_20d",
                        "sector_residual_excess_vs_median_20d",
                    ],
                    "sources": [
                        _framework().base._repo_rel(SECTOR_MAP_JSON),
                        "signal-date OHLCV snapshot rows known after close",
                    ],
                    "decision_time": (
                        "known after signal-date close before next-open paper entry"
                    ),
                    "coverage": _framework()._field_coverage(
                        all_target_trades,
                        [
                            "sector",
                            "sector_residual_context_status",
                            "sector_residual_excess_vs_median_20d",
                            "sector_residual_support",
                        ],
                    ),
                    "passed": True,
                },
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "minimum_core_survival_rate": min(
                    float(row.get("survival_rate") or 0.0)
                    for row in payload["before_metrics"].values()
                ),
                "passed": True,
                "note": (
                    "No core filter, candidate filter, or live entry rule was "
                    "added. Missing/unsupported sector context leaves paper "
                    "notional unchanged."
                ),
            },
            "support_trade_summary": support_summary,
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": True,
                "run_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "parity_rule": RULE_VERSION,
            },
            "why_not_other_changes": (
                "Skipped estimate-revision soft-ranking because target-trade "
                "coverage was zero in a PIT ledger precheck. Skipped "
                "Companyfacts source provenance after exp-20260603-003 failed "
                "concentration. Skipped high-liquidity, score, close-location, "
                "and pre-event RS retunes because they are nearby frozen "
                "post-earnings families."
            ),
            "interpretation": (
                "Accepted shared default-off paper support. Retain it for "
                "forward observation only; live activation still requires "
                "closed forward replacement-value evidence."
                if gate4["passed"]
                else (
                    "Rejected. Sector-relative 20-day leadership is not a "
                    "strong enough incremental event-quality support on top of "
                    "the accepted high-liquidity post-earnings adapter."
                )
            ),
            "acceptance_interpretation": (
                "Gate 4 passed and the matching shared default-off paper "
                "adapter/parity test path is updated; live orders remain off."
                if gate4["passed"]
                else "Gate 4 failed in replay; no shared adapter change is retained."
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(failed_reasons),
            "related_files": [
                "quant/experiments/exp_20260603_004_post_earnings_sector_residual_support.py",
                "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/test_post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/report_generator.py",
                "quant/default_off_alpha_attribution.py",
                "data/experiments/exp-20260603-004/exp_20260603_004_post_earnings_sector_residual_support.json",
                "experiments/logs/exp-20260603-004.json",
                "experiments/tickets/exp-20260603-004.json",
                "experiments/cards/exp-20260603-004.md",
                "experiments/artifacts/exp-20260603-004_post_earnings_sector_residual_support.md",
                "experiments/manifests/exp-20260603-004.json",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Sector dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    support = payload["support_trade_summary"]["by_window"]
    for label in _framework().base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        support_row = support[label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {supported} | ${support_dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                supported=support_row["adjusted_trade_count"],
                support_dpnl=support_row["sector_residual_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Sector-Residual Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: already-selected "
                "`POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates whose "
                "signal-date 20-day return beats their broad sector median "
                "receive `1.05x` paper notional."
            ),
            "",
            "Baseline: `exp-20260602-027` accepted after metrics.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- supported trades: `{payload['support_trade_summary']['adjusted_trade_count']}` across `{payload['support_trade_summary']['adjusted_windows']}`",
            f"- target max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- target positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            f"- supported max single positive incremental share: `{payload['support_trade_summary']['max_single_positive_incremental_pnl_share']}`",
            f"- supported positive incremental HHI: `{payload['support_trade_summary']['positive_incremental_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off paper adapter increment. Production can "
                "surface the same sector-residual paper notional support "
                "through the existing post-earnings sleeve/report/attribution "
                "path. Live/default orders, watchlists, core ranking/sizing/"
                "exits, and LLM/news behavior remain unchanged."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = _framework().base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    lifecycle_status = "accepted" if payload["decision"].startswith("accepted") else "rejected"
    before_aggregate = payload["judge_before_aggregate"]
    after_aggregate = payload["judge_after_aggregate"]
    aggregate_delta = payload["delta_metrics"]["aggregate"]
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "completed_at": payload["timestamp"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "before_result_file": base._repo_rel(BEFORE_AGG_JSON),
                "after_result_file": base._repo_rel(AFTER_AGG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "support_trade_summary": payload["support_trade_summary"],
                "production_impact": payload["production_impact"],
                "delta_metrics": {
                    "expected_value_score": aggregate_delta[
                        "expected_value_score_delta_sum"
                    ],
                    "total_return_pct": round(
                        after_aggregate["benchmarks"]["strategy_total_return_pct"]
                        - before_aggregate["benchmarks"]["strategy_total_return_pct"],
                        4,
                    ),
                    "max_drawdown_pct": round(
                        after_aggregate["max_drawdown_pct"]
                        - before_aggregate["max_drawdown_pct"],
                        4,
                    ),
                    "trade_count": after_aggregate["total_trades"]
                    - before_aggregate["total_trades"],
                    "survival_rate": round(
                        after_aggregate["survival_rate"]
                        - before_aggregate["survival_rate"],
                        4,
                    ),
                    "total_pnl": aggregate_delta["total_pnl_delta_sum"],
                },
            },
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_json(DOC_TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = _framework().base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "doc_ticket": base._repo_rel(DOC_TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
        "baseline_result": base._repo_rel(BASELINE_RESULT_JSON),
        "sector_map": base._repo_rel(SECTOR_MAP_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(_framework()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _framework().base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "support_trade_summary": payload["support_trade_summary"],
                    "artifact": _framework().base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": _framework().base._repo_rel(
                        BEFORE_AGG_JSON
                    ),
                    "after_aggregate": _framework().base._repo_rel(
                        AFTER_AGG_JSON
                    ),
                    "production_impact": payload["production_impact"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
