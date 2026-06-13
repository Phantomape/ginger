"""exp-20260613-015: same-ticker source-confirmation allocator scout.

Alpha search, replay-only. The policy under test is an ex-ante confirmation
score for same-day accepted allocator source conflicts. The score only uses
accepted allocator source rows visible on or before the current signal date.
No production/shared helper is changed in this runner.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as accepted

framework = accepted.framework
exp008 = accepted.exp008

REPO_ROOT = accepted.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    RULE_VERSION as ACCEPTED_ALLOCATOR_RULE_VERSION,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY,
    SOURCE_RULE_VERSION as ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
    _allocator_score,
    _build_source_trades,
    _decision_id,
    _float,
    _normalise_source_row,
    select_accepted_helper_source_priority_rows,
)
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260613-015"
STEM = "source_confirmation_allocator"
OWNER = "alpha-search-automation"
TRIAL_FAMILY = "accepted_allocator_source_arbitration"
TRIAL_VARIANT_ID = "same_ticker_independent_source_confirmation_arbitration_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
SOURCE_CONFIRMATION_RULE_VERSION = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

LOOKBACK_TRADING_DAYS = 5
MIN_DISTINCT_CONFIRMING_SOURCES = 2
MAX_DRAWDOWN_WORSE = 0.005
MIN_CHANGED_SELECTIONS = 9
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "aggregate_ev_delta": 2.1849,
    "aggregate_pnl_delta": 40397.21,
    "window_deltas": {
        "late_strong": {"ev": 0.9092, "pnl": 9431.68},
        "mid_weak": {"ev": 0.6352, "pnl": 11133.95},
        "old_thin": {"ev": 0.6405, "pnl": 19831.58},
    },
}

PREDICTION = {
    "success_probability": 0.21,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "accepted_allocator_already_captures_consensus",
        "confirmation_rows_too_sparse",
        "window_regression",
        "source_concentration",
        "shared_helper_parity_missing",
    ],
    "confidence_reason": (
        "exp-20260613-003 left a same-day source-choice oracle gap, while "
        "exp-20260613-004/006/009 rejected source-maturity, source-score, "
        "and microstructure arbitration. Same-ticker independent confirmation "
        "breadth is PIT and production-visible, but the accepted lagged "
        "consensus source may already capture much of it."
    ),
    "recorded_at": "2026-06-13T11:08:54+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: when accepted default-off paper sources "
        "conflict on the same day, a ticker supported by multiple independent "
        "accepted source families during the current/prior five trading days "
        "may be a better top-1 allocator choice than fixed source priority."
    ),
    "2_history_check": {
        "exp-20260611-005": (
            "Current accepted source-priority allocator with lagged consensus; "
            "aggregate EV +2.1849 and PnL +$40,397.21 is the binding comparator."
        ),
        "exp-20260613-003": (
            "Observed-only source-choice oracle found a material gap but used "
            "future PnL; it asked for a PIT source-arbitration field."
        ),
        "exp-20260613-004": (
            "Source-maturity trailing closed-PnL arbitration was rejected versus "
            "the accepted allocator."
        ),
        "exp-20260613-006": (
            "Source-score percentile arbitration was rejected versus the "
            "accepted allocator."
        ),
        "exp-20260613-009": (
            "Uniform OHLCV microstructure arbitration failed the accepted "
            "allocator comparison."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve aggregate EV/PnL versus the same-run accepted allocator "
        "control, avoid direct EV/PnL window regressions, beat the accepted "
        "exp-20260611-005 comparator, and pass sample/survival/drawdown/"
        "concentration guards. Because this runner does not change the shared "
        "daily helper, a positive numeric result is a lead only."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_015_source_confirmation_allocator.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_source_confirmation_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "max_capital_pct": 0.32,
        "max_concurrent": 8,
        "max_displacement": 1,
        "min_dollar_volume": 10_000_000.0,
        "slippage_bps": 5.0,
        "order_semantics": "next_open_paper_only",
        "kill_switch_drawdown_pct": 0.15,
        "notes": (
            "Same accepted-helper allocator bucket as exp-20260611-005. This "
            "scout does not change production; positive evidence would require "
            "a shared helper and daily snapshot parity before retention."
        ),
    },
    "parity_note": (
        "Replay-only source-confirmation scout. It reuses accepted allocator "
        "source rows and only uses rows visible on or before each signal date. "
        "No source priority, helper, daily snapshot, report, ranking, sizing, "
        "exit, watchlist, LLM/news, or order surface is changed."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
    )


def _trade_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
    )


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _confirmation_stats(
    row: dict[str, Any],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    date_position: dict[str, int],
) -> dict[str, Any]:
    signal_date = _date10(row.get("signal_date") or row.get("date"))
    signal_pos = date_position.get(signal_date)
    ticker = str(row.get("ticker") or "").upper()
    if signal_pos is None or not ticker:
        return {
            "confirmation_ready": False,
            "distinct_source_count": 0,
            "same_day_source_count": 0,
            "prior_source_count": 0,
            "confirmation_score": None,
            "supporting_sources": [],
            "supporting_dates": [],
            "min_support_age_days": None,
        }

    support_rows: list[dict[str, Any]] = []
    for candidate in rows_by_ticker.get(ticker, []):
        candidate_date = _date10(candidate.get("signal_date") or candidate.get("date"))
        candidate_pos = date_position.get(candidate_date)
        if candidate_pos is None or candidate_pos > signal_pos:
            continue
        age = signal_pos - candidate_pos
        if age > LOOKBACK_TRADING_DAYS:
            continue
        source_family = str(candidate.get("source_family") or "unknown")
        if source_family not in SOURCE_PRIORITY:
            continue
        support_rows.append(candidate)

    distinct_sources = sorted(
        {str(candidate.get("source_family") or "unknown") for candidate in support_rows}
    )
    same_day_sources = sorted(
        {
            str(candidate.get("source_family") or "unknown")
            for candidate in support_rows
            if _date10(candidate.get("signal_date") or candidate.get("date")) == signal_date
        }
    )
    prior_sources = sorted(set(distinct_sources) - set(same_day_sources))
    supporting_dates = sorted(
        {_date10(candidate.get("signal_date") or candidate.get("date")) for candidate in support_rows}
    )
    ages = [
        signal_pos
        - int(date_position[_date10(candidate.get("signal_date") or candidate.get("date"))])
        for candidate in support_rows
        if _date10(candidate.get("signal_date") or candidate.get("date")) in date_position
    ]
    min_age = min(ages) if ages else None
    freshness = 0.0
    if min_age is not None:
        freshness = max(0.0, 1.0 - min(min_age, LOOKBACK_TRADING_DAYS) / LOOKBACK_TRADING_DAYS)
    score = (
        float(len(distinct_sources))
        + 0.35 * float(len(same_day_sources))
        + 0.20 * float(len(prior_sources))
        + 0.10 * freshness
    )
    ready = len(distinct_sources) >= MIN_DISTINCT_CONFIRMING_SOURCES
    return {
        "confirmation_ready": ready,
        "distinct_source_count": len(distinct_sources),
        "same_day_source_count": len(same_day_sources),
        "prior_source_count": len(prior_sources),
        "confirmation_score": round(score, 6) if ready else None,
        "supporting_sources": distinct_sources,
        "same_day_sources": same_day_sources,
        "prior_sources": prior_sources,
        "supporting_dates": supporting_dates,
        "min_support_age_days": min_age,
        "known_at": "accepted source rows with signal_date <= current signal_date",
    }


def _prepared_candidate(
    row: dict[str, Any],
    *,
    confirmation_stats: dict[str, Any],
    selected_by: str,
) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    normalised = _normalise_source_row(row, source_family)
    out = {
        **deepcopy(row),
        **normalised,
        "source": "SOURCE_CONFIRMATION_ALLOCATOR_REPLAY_ONLY",
        "sleeve": "SOURCE_CONFIRMATION_ALLOCATOR_REPLAY_ONLY",
        "rule_version": SOURCE_CONFIRMATION_RULE_VERSION,
        "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
        "decision_id": (
            "SOURCE_CONFIRMATION_ALLOCATOR_REPLAY_ONLY:"
            f"{SOURCE_CONFIRMATION_RULE_VERSION}:"
            f"{_date10(row.get('signal_date') or row.get('date'))}:"
            f"{str(row.get('ticker') or '').upper()}:{source_family}"
        ),
        "accepted_allocator_decision_id": _decision_id(normalised),
        "candidate_score": _allocator_score(normalised),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
        "source_confirmation": confirmation_stats,
        "source_confirmation_selected_by": selected_by,
    }
    return out


def _select_confirmation_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    del config
    candidates = [
        _normalise_source_row(row, str(row.get("source_family") or ""))
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    by_date: dict[str, list[dict[str, Any]]] = {}
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        signal_date = _date10(row.get("signal_date") or row.get("date"))
        ticker = str(row.get("ticker") or "").upper()
        if signal_date:
            by_date.setdefault(signal_date, []).append(row)
        if ticker:
            rows_by_ticker.setdefault(ticker, []).append(row)

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    confirmation_selected = 0
    fallback_selected = 0
    confirmation_ready_candidate_count = 0
    changed_trade_count = 0
    changed_source_count = 0
    selected_source_counts: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    confirmation_samples: list[dict[str, Any]] = []

    for signal_date in sorted(by_date):
        pos = date_position.get(signal_date)
        if pos is None:
            for row in by_date[signal_date]:
                rejected_row = {**row, "filter_reason": "missing_signal_date_position"}
                rejected.append(rejected_row)
                rejected_reasons["missing_signal_date_position"] += 1
            continue

        day_rows: list[dict[str, Any]] = []
        for row in by_date[signal_date]:
            ticker = str(row.get("ticker") or "").upper()
            if pos < next_allowed_pos_by_ticker.get(ticker, -1):
                rejected_row = {**row, "filter_reason": "same_ticker_cooldown"}
                rejected.append(rejected_row)
                rejected_reasons["same_ticker_cooldown"] += 1
                continue
            stats = _confirmation_stats(
                row,
                rows_by_ticker=rows_by_ticker,
                date_position=date_position,
            )
            annotated = {**row, "source_confirmation": stats}
            day_rows.append(annotated)
            if stats["confirmation_ready"]:
                confirmation_ready_candidate_count += 1

        if not day_rows:
            continue

        accepted_priority_winner = min(
            day_rows,
            key=lambda row: (
                int(row.get("source_priority_rank") or 999),
                -_float(row.get("source_priority_score")),
                str(row.get("ticker") or ""),
            ),
        )
        confirmed_rows = [
            row
            for row in day_rows
            if (row.get("source_confirmation") or {}).get("confirmation_ready")
        ]
        if confirmed_rows:
            winner = max(
                confirmed_rows,
                key=lambda row: (
                    _float((row.get("source_confirmation") or {}).get("confirmation_score")),
                    int(
                        (row.get("source_confirmation") or {}).get(
                            "distinct_source_count"
                        )
                        or 0
                    ),
                    int(
                        (row.get("source_confirmation") or {}).get(
                            "same_day_source_count"
                        )
                        or 0
                    ),
                    int(
                        (row.get("source_confirmation") or {}).get(
                            "prior_source_count"
                        )
                        or 0
                    ),
                    -int(row.get("source_priority_rank") or 999),
                    _float(row.get("source_priority_score")),
                    str(row.get("ticker") or ""),
                ),
            )
            selected_by = "source_confirmation"
            confirmation_selected += 1
        else:
            winner = accepted_priority_winner
            selected_by = "accepted_priority_fallback"
            fallback_selected += 1

        if _trade_key(winner) != _trade_key(accepted_priority_winner):
            changed_trade_count += 1
        if _row_key(winner) != _row_key(accepted_priority_winner):
            changed_source_count += 1

        winner_out = _prepared_candidate(
            winner,
            confirmation_stats=winner.get("source_confirmation") or {},
            selected_by=selected_by,
        )
        selected.append(winner_out)
        selected_source_counts[str(winner_out.get("source_family") or "unknown")] += 1
        next_allowed_pos_by_ticker[str(winner_out.get("ticker") or "").upper()] = (
            pos + SAME_TICKER_COOLDOWN_DAYS
        )

        for row in day_rows:
            if _row_key(row) == _row_key(winner):
                continue
            rejected_row = {
                **row,
                "filter_reason": "daily_top1_source_confirmation_limit",
                "source_confirmation_selected_winner": _row_key(winner),
            }
            rejected.append(rejected_row)
            rejected_reasons["daily_top1_source_confirmation_limit"] += 1

        if len(confirmation_samples) < 30:
            for row in sorted(
                day_rows,
                key=lambda item: (
                    -_float(
                        (item.get("source_confirmation") or {}).get(
                            "confirmation_score"
                        )
                    ),
                    int(item.get("source_priority_rank") or 999),
                    str(item.get("ticker") or ""),
                ),
            )[:3]:
                confirmation_samples.append(
                    {
                        "signal_date": signal_date,
                        "ticker": str(row.get("ticker") or ""),
                        "source_family": str(row.get("source_family") or ""),
                        "source_priority_rank": row.get("source_priority_rank"),
                        "source_confirmation": row.get("source_confirmation"),
                        "selected": _row_key(row) == _row_key(winner),
                        "selected_by": selected_by,
                    }
                )

    audit = {
        "rule_version": SOURCE_CONFIRMATION_RULE_VERSION,
        "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "min_distinct_confirming_sources": MIN_DISTINCT_CONFIRMING_SOURCES,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "confirmation_selected_count": confirmation_selected,
        "fallback_selected_count": fallback_selected,
        "confirmation_ready_candidate_count": confirmation_ready_candidate_count,
        "changed_trade_count_vs_same_day_priority": changed_trade_count,
        "changed_source_count_vs_same_day_priority": changed_source_count,
        "selected_source_counts": dict(selected_source_counts),
        "rejected_reasons": dict(rejected_reasons),
        "confirmation_samples": confirmation_samples,
        "known_at": (
            "accepted allocator source rows with signal_date on or before the "
            "current signal date; no future exits or future PnL are used"
        ),
    }
    return selected, rejected, audit


def _target_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return framework.sleeve._target_trade_summary(rows_by_window)


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0.0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _gate4(
    *,
    aggregate_vs_core: dict[str, Any],
    aggregate_vs_accepted: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    accepted_to_confirmation_rows: OrderedDict[str, dict[str, Any]],
    changed_selection_count: int,
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    direct_ev = float(aggregate_vs_accepted["expected_value_score_delta_sum"] or 0.0)
    direct_pnl = float(aggregate_vs_accepted["total_pnl_delta_sum"] or 0.0)
    if direct_ev <= 0.0:
        failed.append("direct_ev_vs_accepted_allocator_not_positive")
    if direct_pnl <= 0.0:
        failed.append("direct_pnl_vs_accepted_allocator_not_positive")
    if int(aggregate_vs_accepted["windows_ev_regressed"] or 0) > 0:
        failed.append("direct_window_ev_regression_vs_accepted_allocator")
    if int(aggregate_vs_accepted["windows_pnl_regressed"] or 0) > 0:
        failed.append("direct_window_pnl_regression_vs_accepted_allocator")
    if float(aggregate_vs_accepted["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("direct_drawdown_drift_too_high")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if changed_selection_count < MIN_CHANGED_SELECTIONS:
        failed.append("changed_selection_sample_too_small")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if float(aggregate_vs_core["expected_value_score_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]
    ):
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if float(aggregate_vs_core["total_pnl_delta_sum"] or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]
    ):
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in accepted_to_confirmation_rows.items():
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_ev")
        if float(delta.get("total_pnl") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_pnl")

    numeric_passed = not failed
    if numeric_passed:
        decision = "positive_replay_lead_not_promoted_source_confirmation_allocator"
        failed.append("shared_helper_parity_missing_for_acceptance")
    else:
        decision = "rejected_source_confirmation_allocator"
    return {
        "passed": False,
        "numeric_gate4_passed": numeric_passed,
        "decision": decision,
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "direct_ev_delta_vs_accepted_allocator": round(direct_ev, 6),
        "direct_pnl_delta_vs_accepted_allocator": round(direct_pnl, 2),
        "aggregate_ev_delta_vs_core": aggregate_vs_core["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": aggregate_vs_core["total_pnl_delta_sum"],
        "direct_windows_ev_improved": aggregate_vs_accepted["windows_ev_improved"],
        "direct_windows_ev_regressed": aggregate_vs_accepted["windows_ev_regressed"],
        "direct_windows_pnl_improved": aggregate_vs_accepted["windows_pnl_improved"],
        "direct_windows_pnl_regressed": aggregate_vs_accepted["windows_pnl_regressed"],
        "max_direct_drawdown_worse": aggregate_vs_accepted["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "changed_selection_count": changed_selection_count,
        "changed_selection_count_min": MIN_CHANGED_SELECTIONS,
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_share": _top5_positive_share(target_summary),
        },
        "note": (
            "Even if numeric Gate 4 passes, this runner is not accepted alpha "
            "because the shared daily allocator helper was not changed."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    confirmation_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_confirmation_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_confirmation_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    confirmation_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    confirmation_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] source-confirmation allocator")
        before_result = baseline_results[label]
        before = before_metrics[label]
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        calendar_dates = framework.shadow._trading_dates(snapshot)
        dates = [day for day in calendar_dates if str(cfg["start"]) <= day <= str(cfg["end"])]
        source_trades, source_audit = _build_source_trades(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        accepted_selected, accepted_filtered, accepted_priority_audit = (
            select_accepted_helper_source_priority_rows(
                source_rows=source_trades,
                trading_dates=dates,
                config=None,
                create_trades=True,
            )
        )
        confirmation_selected, confirmation_filtered, confirmation_audit = (
            _select_confirmation_rows(
                source_rows=source_trades,
                trading_dates=dates,
            )
        )

        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_selected,
        )
        confirmation_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            confirmation_selected,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        confirmation_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            confirmation_overlay,
        )
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        confirmation_delta = framework.overlay_helper._delta(confirmation_after, before)
        direct_delta = framework.overlay_helper._delta(confirmation_after, accepted_after)

        accepted_keys = {_trade_key(row) for row in accepted_selected}
        confirmation_keys = {_trade_key(row) for row in confirmation_selected}
        changed_keys = sorted(accepted_keys.symmetric_difference(confirmation_keys))

        accepted_metrics[label] = accepted_after
        confirmation_metrics[label] = confirmation_after
        accepted_trades_by_window[label] = accepted_selected
        confirmation_trades_by_window[label] = confirmation_selected
        source_audit_by_window[label] = source_audit
        accepted_priority_audit_by_window[label] = accepted_priority_audit
        confirmation_audit_by_window[label] = confirmation_audit
        core_to_accepted_rows[label] = {
            "before": before,
            "after": accepted_after,
            "delta": accepted_delta,
            "target_trade_count": len(accepted_selected),
            "selected_source_counts": _source_counts(accepted_selected),
            "filtered_daily_top1_count": sum(
                1
                for row in accepted_filtered
                if row.get("filter_reason") == "daily_top1_source_priority_limit"
            ),
        }
        core_to_confirmation_rows[label] = {
            "before": before,
            "after": confirmation_after,
            "delta": confirmation_delta,
            "target_trade_count": len(confirmation_selected),
            "selected_source_counts": _source_counts(confirmation_selected),
            "confirmation_selected_count": confirmation_audit[
                "confirmation_selected_count"
            ],
            "fallback_selected_count": confirmation_audit["fallback_selected_count"],
            "changed_selection_count": len(changed_keys) // 2,
            "source_trade_counts": source_audit["source_trade_counts"],
        }
        accepted_to_confirmation_rows[label] = {
            "before": accepted_after,
            "after": confirmation_after,
            "delta": direct_delta,
            "target_trade_count": len(confirmation_selected),
            "changed_selection_count": len(changed_keys) // 2,
            "accepted_selected_source_counts": _source_counts(accepted_selected),
            "confirmation_selected_source_counts": _source_counts(
                confirmation_selected
            ),
            "confirmation_rejected_count": len(confirmation_filtered),
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_confirmation = framework._aggregate_window_rows(
        core_to_confirmation_rows
    )
    aggregate_accepted_to_confirmation = framework._aggregate_window_rows(
        accepted_to_confirmation_rows
    )
    confirmation_summary = _target_summary(confirmation_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"])
        for row in accepted_to_confirmation_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_confirmation,
        aggregate_vs_accepted=aggregate_accepted_to_confirmation,
        target_summary=confirmation_summary,
        before_metrics=before_metrics,
        accepted_to_confirmation_rows=accepted_to_confirmation_rows,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "The source-confirmation allocator numerically beat the accepted "
            "allocator, but it is not retained because shared helper and daily "
            "snapshot parity were not implemented."
        )
        reflection = (
            "Independent same-ticker source confirmation appears to explain "
            "part of the source-choice gap without future PnL. The result is "
            "only a lead until the same field is implemented in the shared "
            "default-off allocator helper and daily snapshot."
        )
    else:
        status = "rejected"
        interpretation = (
            "The source-confirmation allocator failed the accepted allocator "
            "comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "Same-ticker source confirmation either arrived too sparsely or "
            "mostly duplicated the accepted lagged-consensus signal. It did "
            "not explain the oracle source-choice gap better than the accepted "
            "fixed priority."
        )

    actual_success = bool(gate4["numeric_gate4_passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": (
            "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
        ),
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": (
            "PIT independent source confirmation breadth/freshness over "
            "accepted allocator source rows"
        ),
        "nearby_prior_experiments": [
            "exp-20260611-005",
            "exp-20260613-003",
            "exp-20260613-004",
            "exp-20260613-006",
            "exp-20260613-009",
        ],
        "prior_trial_count": 3,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": actual_success,
            "actual_success": int(actual_success),
            "actual_ev_delta_vs_accepted_allocator": gate4[
                "direct_ev_delta_vs_accepted_allocator"
            ],
            "actual_pnl_delta_vs_accepted_allocator": gate4[
                "direct_pnl_delta_vs_accepted_allocator"
            ],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1.0 if actual_success else 0.0))
                ** 2,
                6,
            ),
            "failure_modes_observed": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"])
                & set(gate4["failed_reasons"])
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted-helper allocator overlay and replay-only source-"
                "confirmation variant"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "source_confirmation_rule_version": SOURCE_CONFIRMATION_RULE_VERSION,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "lookback_trading_days": LOOKBACK_TRADING_DAYS,
            "min_distinct_confirming_sources": MIN_DISTINCT_CONFIRMING_SOURCES,
            "source_confirmation_score": (
                "distinct accepted source-family breadth plus same-day/prior "
                "support freshness"
            ),
            "fallback": (
                "accepted fixed source priority when no same-day row has enough "
                "independent source confirmation"
            ),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "locked_variables": [
                "source_priority_rank",
                "top1_per_day",
                "notional",
                "hold_days",
                "cooldown",
                "core_strategy",
                "live_orders",
            ],
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "accepted allocator source rows signal_date/ticker/source_family",
            ],
        },
        "gate3": {
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "note": "Default-off paper allocator only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "source_confirmation_metrics": confirmation_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_source_confirmation": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_confirmation_rows.items()
                ),
                "aggregate": aggregate_core_to_confirmation,
            },
            "accepted_allocator_to_source_confirmation": {
                "by_window": OrderedDict(
                    (label, row["delta"])
                    for label, row in accepted_to_confirmation_rows.items()
                ),
                "aggregate": aggregate_accepted_to_confirmation,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_source_confirmation": core_to_confirmation_rows,
            "accepted_allocator_to_source_confirmation": accepted_to_confirmation_rows,
        },
        "accepted_trade_summary": accepted_summary,
        "source_confirmation_trade_summary": confirmation_summary,
        "source_audit_by_window": source_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "source_confirmation_audit_by_window": confirmation_audit_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "same_run_accepted_allocator_control": aggregate_core_to_accepted,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["numeric_gate4_passed"] else "; ".join(
            gate4["failed_reasons"]
        ),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "negative_reflection": (
                "If rejected, the confirmation field was too sparse or already "
                "absorbed by the accepted lagged-consensus source. If positive, "
                "the result remains non-accepted because shared helper parity is missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping source-confirmation lookback, "
                "distinct-source threshold, score weights, source rank, top-N, "
                "notional, hold days, or cooldown on the same frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs closed forward source-competition rows, a "
                "new PIT relation map, or a richer production-visible source "
                "quality field recorded in daily snapshots."
            ),
        },
        "next_retry_requires": [
            "closed forward source-competition replacement rows",
            "shared helper plus daily parity if any confirmation field is promoted",
            "no frozen-window lookback/min-threshold sweep",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Core EV | Accepted EV | Confirmation EV | Direct dEV | Core PnL | Accepted dPnL | Confirmation dPnL | Direct dPnL | Changed | Confirm selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        confirmation_row = payload["window_rows"]["core_to_source_confirmation"][label]
        direct_row = payload["window_rows"]["accepted_allocator_to_source_confirmation"][
            label
        ]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {confirmation_ev:.4f} | {direct_ev:+.4f} | ${core_pnl:,.2f} | ${accepted_dpnl:+,.2f} | ${confirmation_dpnl:+,.2f} | ${direct_dpnl:+,.2f} | {changed} | {confirmation_selected} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                accepted_ev=accepted_row["after"]["expected_value_score"],
                confirmation_ev=confirmation_row["after"]["expected_value_score"],
                direct_ev=direct_row["delta"]["expected_value_score"],
                core_pnl=core["total_pnl"],
                accepted_dpnl=accepted_row["delta"]["total_pnl"],
                confirmation_dpnl=confirmation_row["delta"]["total_pnl"],
                direct_dpnl=direct_row["delta"]["total_pnl"],
                changed=direct_row["changed_selection_count"],
                confirmation_selected=confirmation_row["confirmation_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"]["accepted_allocator_to_source_confirmation"][
        "aggregate"
    ]
    core_to_confirmation = payload["delta_metrics"]["core_to_source_confirmation"][
        "aggregate"
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Source Confirmation Allocator",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4 Three-Window Readout",
            "",
            *_window_table(payload),
            "",
            "- Direct EV delta vs accepted allocator: `{:+.4f}`".format(
                direct["expected_value_score_delta_sum"]
            ),
            "- Direct PnL delta vs accepted allocator: `${:+,.2f}`".format(
                direct["total_pnl_delta_sum"]
            ),
            "- Confirmation aggregate EV delta vs core: `{:+.4f}`".format(
                core_to_confirmation["expected_value_score_delta_sum"]
            ),
            "- Confirmation aggregate PnL delta vs core: `${:+,.2f}`".format(
                core_to_confirmation["total_pnl_delta_sum"]
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload["delta_metrics"]["accepted_allocator_to_source_confirmation"][
        "aggregate"
    ]
    core_to_confirmation = payload["delta_metrics"]["core_to_source_confirmation"][
        "aggregate"
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "direct_expected_value_delta_vs_accepted_allocator": direct[
            "expected_value_score_delta_sum"
        ],
        "direct_pnl_delta_vs_accepted_allocator": direct["total_pnl_delta_sum"],
        "aggregate_expected_value_delta": core_to_confirmation[
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": core_to_confirmation["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "accepted_allocator_expected_value": payload[
                    "accepted_allocator_metrics"
                ][label]["expected_value_score"],
                "source_confirmation_expected_value": payload[
                    "source_confirmation_metrics"
                ][label]["expected_value_score"],
                "direct_expected_value_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_confirmation"
                ]["by_window"][label]["expected_value_score"],
                "direct_pnl_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_confirmation"
                ]["by_window"][label]["total_pnl"],
                "changed_selection_count": payload["window_rows"][
                    "accepted_allocator_to_source_confirmation"
                ][label]["changed_selection_count"],
                "selected_source_counts": payload["window_rows"][
                    "core_to_source_confirmation"
                ][label]["selected_source_counts"],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "prediction": PREDICTION,
            "calibration": payload["calibration"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
                "gate4": payload["gate4"],
                "accepted": False,
                "calibration": payload["calibration"],
                "post_run_reflection": payload["post_run_reflection"],
                "production_impact": PRODUCTION_IMPACT,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(__file__), OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD, MANIFEST_JSON]
    file_hashes: dict[str, str] = {}
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved.exists():
            file_hashes[_repo_rel(resolved)] = framework._sha256(resolved)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": file_hashes,
        "global_registry_note": (
            "Per-experiment artifact/log/card/ticket were written. Global "
            "docs/experiment_log.jsonl was not touched; registry was reserved "
            "and claimed through scripts/experiment.py before runner creation."
        ),
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
