"""exp-20260616-024: FINRA borrow-pressure three-window out-of-sample scout.

Replay-only alpha search. The single decision hypothesis re-tests the ALREADY
ACCEPTED FINRA borrow-pressure source (exp-20260603-006: days_to_cover >= 3.0
AND short_interest_change_pct > 0) across ALL THREE canonical windows, which
only became possible after exp-20260616-020 extended the FINRA short-interest
archive back to 2024-08 (old_thin/mid_weak previously had zero FINRA rows).

Mechanism: forced-covering continuation. High days-to-cover means many short
shares relative to volume (squeeze fuel); rising short interest into liquid
SPY-relative price strength sets up a covering leg over the next 10 trading
days. FINRA biweekly rows are joined point-in-time by their official
publication date (usable_trade_date), never the settlement date.

This is NOT a threshold retune: the fixed exp-20260603-006 policy is held
constant and evaluated out-of-sample on the two windows it could never see
before. No production code, shared adapter, live/default orders, ranking,
sizing, exits, LLM/news path, or watchlist behavior is changed. A positive
replay is only a lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
from finra_iwm_paper_sleeve import load_finra_short_interest_rows


EXPERIMENT_ID = "exp-20260616-024"
STEM = "finra_borrow_pressure_three_window"
TRIAL_FAMILY = "finra_borrow_pressure_three_window_validation"
TRIAL_VARIANT_ID = "finra_borrow_pressure_dtc3_short_rising_top1_next_open_10d_v1"
CHANGED_VARIABLE = "finra_borrow_pressure_three_window_out_of_sample_validation_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
FINRA_ROWS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "rows.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_024_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

# Fixed accepted exp-20260603-006 borrow-pressure policy (held constant).
MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0
# A biweekly print is current for ~one cycle (settlement + ~10 business days to
# publish, then ~14 days to the next print). Keep only the latest published row
# within this freshness window so a stale print cannot be reused indefinitely.
MAX_FINRA_PUBLICATION_AGE_DAYS = 25

PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_sample_high_dtc_rare_in_core_universe",
        "old_thin_mid_weak_window_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "The borrow-pressure source was accepted (exp-20260603-006) but only "
        "late_strong had FINRA data then; the extended three-window archive is "
        "new out-of-sample evidence, not a threshold retune. Forced-covering "
        "continuation is plausible, but the liquid core universe rarely shows "
        "days-to-cover above three so the sample may be thin and the effect may "
        "not hold in the weaker windows."
    ),
    "recorded_at": "2026-06-16T20:55:00+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_revalidation_no_shared_adapter_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_finra_short_interest": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing FINRA short-interest row published on or before the signal "
            "date, a stale latest print, days_to_cover below 3.0, non-positive "
            "short-interest change, missing OHLCV, missing next open, or missing "
            "10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. It re-evaluates the fixed "
        "exp-20260603-006 borrow-pressure policy on the exp-20260616-020 "
        "three-window archive. A positive result confirms the accepted FINRA/IWM "
        "shared default-off helper out-of-sample; it does not alter that helper, "
        "live orders, ranking, sizing, exits, or watchlists."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT FINRA short-interest borrow-pressure (days_to_cover "
        ">= 3.0 AND short_interest_change_pct > 0) with liquid SPY-relative "
        "leadership may produce positive next-open 10-day replacement value "
        "across all three canonical windows now that the archive covers them."
    ),
    "2_history_check": {
        "exp-20260603-006": (
            "Accepted the borrow-pressure source, but old_thin/mid_weak had no "
            "FINRA data then. This run is the out-of-sample test of the same "
            "fixed policy, not a retune."
        ),
        "exp-20260603-007": (
            "Promoted the source into the shared FINRA/IWM default-off adapter. "
            "This run does not change that adapter."
        ),
        "exp-20260616-020": (
            "Measurement repair that extended the FINRA archive to all three "
            "windows; it is the new evidence that justifies this revalidation."
        ),
        "exp-20260529-017": (
            "Rejected an early short-pressure breakout variant on then-thin "
            "data; this run holds the accepted borrow-pressure gate fixed."
        ),
        "exp-20260613-029": (
            "Rejected covering-relief leadership (declining short interest); this "
            "run tests the opposite rising-short borrow-pressure gate."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_024_finra_borrow_pressure_three_window.py"
    ),
}

_FINRA_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_finra_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _FINRA_INDEX_CACHE
    if _FINRA_INDEX_CACHE is not None:
        return _FINRA_INDEX_CACHE

    rows = load_finra_short_interest_rows(FINRA_ROWS_PATH)
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    pubs: list[str] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        usable = str(row.get("usable_trade_date") or row.get("publication_date") or "")[:10]
        if not ticker or not usable:
            stats["rows_missing_ticker_or_publication"] += 1
            continue
        index.setdefault(ticker, []).append(
            {
                "usable_trade_date": usable,
                "publication_date": str(row.get("publication_date") or usable)[:10],
                "settlement_date": str(row.get("settlement_date") or "")[:10],
                "days_to_cover": _as_float(row.get("days_to_cover")),
                "short_interest": _as_float(row.get("short_interest")),
                "short_interest_change_pct": _as_float(row.get("short_interest_change_pct")),
                "average_daily_volume": _as_float(row.get("average_daily_volume")),
            }
        )
        pubs.append(usable)
        stats["rows_indexed"] += 1
    for ticker in index:
        index[ticker].sort(key=lambda r: r["usable_trade_date"])
    summary = {
        "finra_rows_source": _repo_rel(FINRA_ROWS_PATH),
        "indexed_tickers": len(index),
        "publication_date_min": min(pubs) if pubs else None,
        "publication_date_max": max(pubs) if pubs else None,
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
        **dict(stats),
    }
    _FINRA_INDEX_CACHE = (index, summary)
    return _FINRA_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_finra_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "finra_short_interest_rows_json_publication_date_pit",
    }


def _finra_borrow_observation(
    ticker: str,
    asof: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for row in rows:
        if row["usable_trade_date"] > asof:
            break
        latest = row
    if latest is None:
        return None
    age = base._days_between(asof, latest["usable_trade_date"])
    if age is None or age > MAX_FINRA_PUBLICATION_AGE_DAYS:
        return None
    days_to_cover = latest["days_to_cover"]
    short_change_pct = latest["short_interest_change_pct"]
    if days_to_cover is None or short_change_pct is None:
        return None
    if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
        return None
    if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
        return None
    return {
        "ticker": ticker,
        "publication_date": latest["publication_date"],
        "usable_trade_date": latest["usable_trade_date"],
        "settlement_date": latest["settlement_date"],
        "days_to_cover": _round(days_to_cover, 4),
        "short_interest": latest["short_interest"],
        "short_interest_change_pct": _round(short_change_pct, 4),
        "average_daily_volume": latest["average_daily_volume"],
        "publication_age_days": age,
        "known_at": "finra_publication_date_usable_trade_date_before_next_open_paper_entry",
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            observation = _finra_borrow_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_borrow_pressure_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            days_to_cover = float(observation["days_to_cover"] or 0.0)
            short_change_pct = float(observation["short_interest_change_pct"] or 0.0)
            score = (
                0.10 * min(days_to_cover, 15.0)
                + 0.010 * min(short_change_pct, 50.0)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "FINRA_BORROW_PRESSURE_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_finra_short_interest": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"finra_{k}": v for k, v in observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["finra_days_to_cover"] or 0.0),
            -float(row["finra_short_interest_change_pct"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_finra_borrow_pressure_three_window_validated"
        if gate["passed"]
        else "rejected_finra_borrow_pressure_three_window_validation"
    )
    return gate


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The accepted FINRA borrow-pressure policy reproduced positive "
            "three-window replacement value out-of-sample on the extended "
            "archive. This is a validation lead; the shared FINRA/IWM default-off "
            "adapter is unchanged and forward rows remain the next evidence."
        )
    else:
        interpretation = (
            "The accepted FINRA borrow-pressure policy did not clear Gate 4 "
            f"out-of-sample (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "Treat the prior accept as recent-window-limited; do not retune the "
            "fixed borrow-pressure thresholds on the frozen windows."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_finra_short_interest_candidate_pool",
            "new_evidence_type": "finra_three_window_archive_out_of_sample_revalidation",
            "nearby_prior_experiments": [
                "exp-20260603-006",
                "exp-20260603-007",
                "exp-20260529-017",
                "exp-20260613-029",
                "exp-20260616-020",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "FINRA biweekly short-interest rows are joined point-in-time by their "
        "official publication date (usable_trade_date <= signal date); only the "
        "latest published print within 25 calendar days is used. The fixed "
        "exp-20260603-006 borrow-pressure gate (days_to_cover >= 3.0 AND "
        "short_interest_change_pct > 0) plus signal-date OHLCV price confirmation "
        "selects candidates. Paper entry is the next available open with entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["finra_source"] = _repo_rel(FINRA_ROWS_PATH)
    payload["gate2"]["runtime_fields"] = [
        "FINRA short_interest, previous_short_interest, short_interest_change_pct",
        "FINRA days_to_cover, average_daily_volume",
        "FINRA settlement_date, publication_date, usable_trade_date (PIT)",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If positive, the next evidence is closed forward replacement-value rows "
        "from the shared FINRA/IWM default-off ledger tagged with entry-time "
        "borrow-pressure. If negative, a valid retry needs a materially different "
        "PIT borrow-cost / hard-to-borrow / loan-availability field, not a "
        "days_to_cover, short-change, freshness, RS, top-N, hold, cooldown, or "
        "notional retune on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping days_to_cover threshold, short-interest "
            "change threshold, publication freshness window, RS/close/volume "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA Borrow-Pressure Three-Window Validation",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only revalidation of the accepted exp-20260603-006 fixed "
                "policy on the exp-20260616-020 three-window archive. No shared "
                "policy, run adapter, backtester adapter, production watchlist, "
                "order path, core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": base.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get(
                    "eligible_quality_tickers"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
