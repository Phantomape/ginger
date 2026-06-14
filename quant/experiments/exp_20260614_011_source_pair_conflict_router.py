"""exp-20260614-011: source-family pair conflict router scout.

Alpha search, replay-only. The policy under test is an ex-ante source-family
pair conflict score for same-day accepted allocator conflicts. Pair outcomes
are learned only from prior signal dates whose competing paper rows have
already exited before the current signal date.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260613_004_source_maturity_allocator as base

framework = base.framework
exp008 = base.exp008

REPO_ROOT = base.REPO_ROOT
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


EXPERIMENT_ID = "exp-20260614-011"
STEM = "source_pair_conflict_router"
OWNER = "alpha-search-automation"
TRIAL_FAMILY = "accepted_allocator_source_arbitration"
TRIAL_VARIANT_ID = "source_pair_conflict_router_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
PAIR_ROUTER_RULE_VERSION = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MIN_PAIR_HISTORY_EVENTS = 3
LOOKBACK_PAIR_EVENTS = 16
MIN_AVG_PAIR_GAP_USD = 100.0
MAX_DRAWDOWN_WORSE = 0.005
MIN_CHANGED_SELECTIONS = 9
MIN_TARGET_TRADES = 20
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
    "success_probability": 0.16,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "source_pair_overfit",
        "accepted_priority_already_sufficient",
        "window_regression",
        "thin_changed_selection_count",
        "source_family_concentration",
    ],
    "confidence_reason": (
        "exp-20260613-003 showed an oracle gap, but source-maturity, source "
        "score percentile, microstructure, confirmation, and crowding scouts "
        "failed. Pair-conflict relative history is a different source-family "
        "structure field, but it is high-risk."
    ),
    "recorded_at": "2026-06-14T09:12:48+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "allocation/ranking: accepted allocator same-day source conflicts may "
        "be improved by routing only when a specific challenger-vs-priority "
        "source-family pair has prior closed relative outperformance, while "
        "falling back to the accepted fixed priority otherwise."
    ),
    "2_history_check": {
        "exp-20260613-003": (
            "Observed-only oracle found material same-day source-choice gap, "
            "but used future PnL and could not be promoted."
        ),
        "exp-20260613-004": "Trailing absolute source-family PnL maturity failed.",
        "exp-20260613-006": "Source-score percentile arbitration failed.",
        "exp-20260613-009": "Candidate microstructure arbitration failed.",
        "exp-20260613-015": "Same-ticker source confirmation failed.",
        "exp-20260613-033": "Correlation crowding scout failed.",
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve direct aggregate EV/PnL versus the same-run accepted allocator "
        "control, avoid direct window regressions, beat exp-20260611-005, and "
        "pass sample, survival, drawdown, and concentration guards."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_011_source_pair_conflict_router.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_source_pair_conflict_router_scout",
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
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "kill_switch_drawdown_pct": 0.15,
        "notes": (
            "Same accepted-helper allocator execution envelope as exp-"
            "20260611-005. This scout does not change production; positive "
            "evidence would require a shared helper, a daily shadow-candidate "
            "outcome ledger, and snapshot parity before retention."
        ),
    },
    "parity_note": (
        "Replay-only source-pair router. It reuses accepted allocator source "
        "rows and only uses prior closed pair-relative outcomes at each signal "
        "date. No source priority, helper, daily snapshot, report, ranking, "
        "sizing, exit, watchlist, LLM/news, or order surface is changed."
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


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _date10(row.get("signal_date") or row.get("date")),
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
    )


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _family_representatives(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    reps: dict[str, dict[str, Any]] = {}
    for row in rows:
        family = str(row.get("source_family") or "unknown")
        current = reps.get(family)
        if current is None or (
            _float(row.get("source_priority_score")),
            -int(row.get("source_priority_rank") or 999),
            str(row.get("ticker") or ""),
        ) > (
            _float(current.get("source_priority_score")),
            -int(current.get("source_priority_rank") or 999),
            str(current.get("ticker") or ""),
        ):
            reps[family] = row
    return reps


def _accepted_priority_winner(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        rows,
        key=lambda row: (
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        ),
    )


def _build_pair_event_history(
    candidates: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        signal_date = _date10(row.get("signal_date") or row.get("date"))
        if signal_date:
            by_date.setdefault(signal_date, []).append(row)

    history: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for signal_date, day_rows in sorted(by_date.items()):
        reps = _family_representatives(day_rows)
        if len(reps) < 2:
            continue
        priority = _accepted_priority_winner(list(reps.values()))
        priority_family = str(priority.get("source_family") or "unknown")
        priority_exit = _date10(priority.get("exit_date"))
        priority_pnl = _float(priority.get("pnl"))
        for family, challenger in reps.items():
            if family == priority_family:
                continue
            challenger_exit = _date10(challenger.get("exit_date"))
            event = {
                "signal_date": signal_date,
                "exit_date": max(priority_exit, challenger_exit),
                "challenger_source_family": family,
                "priority_source_family": priority_family,
                "challenger_ticker": str(challenger.get("ticker") or "").upper(),
                "priority_ticker": str(priority.get("ticker") or "").upper(),
                "challenger_pnl": _round(challenger.get("pnl"), 2),
                "priority_pnl": _round(priority.get("pnl"), 2),
                "pair_gap": round(_float(challenger.get("pnl")) - priority_pnl, 2),
            }
            history.setdefault((family, priority_family), []).append(event)
    return history


def _pair_stats(
    *,
    challenger_source_family: str,
    priority_source_family: str,
    signal_date: str,
    pair_history: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    events = [
        event
        for event in pair_history.get((challenger_source_family, priority_source_family), [])
        if _date10(event.get("exit_date")) < signal_date
    ][-LOOKBACK_PAIR_EVENTS:]
    count = len(events)
    if count <= 0:
        return {
            "pair_key": [challenger_source_family, priority_source_family],
            "history_count": 0,
            "history_ready": False,
            "avg_pair_gap": None,
            "win_rate": None,
            "latest_exit_date": None,
        }
    gaps = [_float(event.get("pair_gap")) for event in events]
    return {
        "pair_key": [challenger_source_family, priority_source_family],
        "history_count": count,
        "history_ready": count >= MIN_PAIR_HISTORY_EVENTS,
        "avg_pair_gap": round(sum(gaps) / count, 6),
        "win_rate": round(sum(1 for gap in gaps if gap > 0.0) / count, 6),
        "latest_exit_date": max(_date10(event.get("exit_date")) for event in events),
        "sample_events": events[-5:],
    }


def _prepared_candidate(
    row: dict[str, Any],
    *,
    pair_stats: dict[str, Any],
    selected_by: str,
) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    normalised = _normalise_source_row(row, source_family)
    return {
        **deepcopy(row),
        **normalised,
        "source": "SOURCE_PAIR_CONFLICT_ROUTER_REPLAY_ONLY",
        "sleeve": "SOURCE_PAIR_CONFLICT_ROUTER_REPLAY_ONLY",
        "rule_version": PAIR_ROUTER_RULE_VERSION,
        "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
        "decision_id": (
            "SOURCE_PAIR_CONFLICT_ROUTER_REPLAY_ONLY:"
            f"{PAIR_ROUTER_RULE_VERSION}:"
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
        "source_pair_conflict_stats": pair_stats,
        "source_pair_conflict_selected_by": selected_by,
    }


def _select_source_pair_rows(
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
    for row in candidates:
        signal_date = _date10(row.get("signal_date") or row.get("date"))
        if signal_date:
            by_date.setdefault(signal_date, []).append(row)

    pair_history = _build_pair_event_history(candidates)
    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    pair_selected = 0
    fallback_selected = 0
    changed_source_count = 0
    pair_ready_candidate_count = 0
    selected_source_counts: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    pair_score_samples: list[dict[str, Any]] = []

    for signal_date in sorted(by_date):
        pos = date_position.get(signal_date)
        if pos is None:
            for row in by_date[signal_date]:
                rejected.append({**row, "filter_reason": "missing_signal_date_position"})
                rejected_reasons["missing_signal_date_position"] += 1
            continue

        cooled_rows: list[dict[str, Any]] = []
        for row in by_date[signal_date]:
            ticker = str(row.get("ticker") or "").upper()
            if pos < next_allowed_pos_by_ticker.get(ticker, -1):
                rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
                rejected_reasons["same_ticker_cooldown"] += 1
                continue
            cooled_rows.append(row)
        if not cooled_rows:
            continue

        family_reps = _family_representatives(cooled_rows)
        day_rows = list(family_reps.values())
        accepted_priority = _accepted_priority_winner(day_rows)
        priority_family = str(accepted_priority.get("source_family") or "unknown")

        pair_candidates: list[dict[str, Any]] = []
        for row in day_rows:
            source_family = str(row.get("source_family") or "unknown")
            if source_family == priority_family:
                continue
            stats = _pair_stats(
                challenger_source_family=source_family,
                priority_source_family=priority_family,
                signal_date=signal_date,
                pair_history=pair_history,
            )
            annotated = {**row, "source_pair_conflict_stats": stats}
            if stats["history_ready"]:
                pair_ready_candidate_count += 1
            if stats["history_ready"] and _float(stats.get("avg_pair_gap")) >= MIN_AVG_PAIR_GAP_USD:
                pair_candidates.append(annotated)

        if pair_candidates:
            winner = max(
                pair_candidates,
                key=lambda row: (
                    _float((row.get("source_pair_conflict_stats") or {}).get("avg_pair_gap")),
                    _float((row.get("source_pair_conflict_stats") or {}).get("win_rate")),
                    int((row.get("source_pair_conflict_stats") or {}).get("history_count") or 0),
                    -int(row.get("source_priority_rank") or 999),
                    _float(row.get("source_priority_score")),
                    str(row.get("ticker") or ""),
                ),
            )
            selected_by = "source_pair_conflict_router"
            pair_selected += 1
            stats = winner.get("source_pair_conflict_stats") or {}
        else:
            winner = accepted_priority
            selected_by = "accepted_priority_fallback"
            fallback_selected += 1
            stats = {
                "pair_key": None,
                "history_count": 0,
                "history_ready": False,
                "avg_pair_gap": None,
                "win_rate": None,
                "latest_exit_date": None,
            }

        if _row_key(winner) != _row_key(accepted_priority):
            changed_source_count += 1

        winner_out = _prepared_candidate(winner, pair_stats=stats, selected_by=selected_by)
        selected.append(winner_out)
        selected_source_counts[str(winner_out.get("source_family") or "unknown")] += 1
        next_allowed_pos_by_ticker[str(winner_out.get("ticker") or "").upper()] = (
            pos + SAME_TICKER_COOLDOWN_DAYS
        )

        for row in day_rows:
            if _row_key(row) == _row_key(winner):
                continue
            rejected.append(
                {
                    **row,
                    "filter_reason": "daily_top1_source_pair_conflict_limit",
                    "source_pair_selected_winner": _row_key(winner),
                }
            )
            rejected_reasons["daily_top1_source_pair_conflict_limit"] += 1

        if len(pair_score_samples) < 30:
            for row in sorted(
                pair_candidates,
                key=lambda item: (
                    -_float((item.get("source_pair_conflict_stats") or {}).get("avg_pair_gap")),
                    int(item.get("source_priority_rank") or 999),
                    str(item.get("ticker") or ""),
                ),
            )[:3]:
                pair_score_samples.append(
                    {
                        "signal_date": signal_date,
                        "ticker": str(row.get("ticker") or ""),
                        "source_family": str(row.get("source_family") or ""),
                        "priority_source_family": priority_family,
                        "source_priority_rank": row.get("source_priority_rank"),
                        "source_pair_conflict_stats": row.get("source_pair_conflict_stats"),
                        "selected": _row_key(row) == _row_key(winner),
                        "selected_by": selected_by,
                    }
                )

    audit = {
        "rule_version": PAIR_ROUTER_RULE_VERSION,
        "min_pair_history_events": MIN_PAIR_HISTORY_EVENTS,
        "lookback_pair_events": LOOKBACK_PAIR_EVENTS,
        "min_avg_pair_gap_usd": MIN_AVG_PAIR_GAP_USD,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "pair_selected_count": pair_selected,
        "fallback_selected_count": fallback_selected,
        "pair_ready_candidate_count": pair_ready_candidate_count,
        "changed_source_count_vs_same_day_priority": changed_source_count,
        "selected_source_counts": dict(selected_source_counts),
        "rejected_reasons": dict(rejected_reasons),
        "pair_score_samples": pair_score_samples,
        "pair_history_event_counts": {
            f"{key[0]}__vs__{key[1]}": len(value)
            for key, value in sorted(pair_history.items())
        },
        "known_at": (
            "after prior competing source-family paper rows have closed; rows "
            "with exit_date >= current signal_date are excluded from the score"
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
    changed_selection_count: int,
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    direct_ev = float(aggregate_vs_accepted.get("expected_value_score_delta_sum") or 0.0)
    direct_pnl = float(aggregate_vs_accepted.get("total_pnl_delta_sum") or 0.0)
    if direct_ev <= 0.0:
        failed.append("direct_ev_vs_accepted_allocator_not_positive")
    if direct_pnl <= 0.0:
        failed.append("direct_pnl_vs_accepted_allocator_not_positive")
    if int(aggregate_vs_accepted.get("windows_ev_regressed") or 0) > 0:
        failed.append("direct_window_ev_regression_vs_accepted_allocator")
    if int(aggregate_vs_accepted.get("windows_pnl_regressed") or 0) > 0:
        failed.append("direct_window_pnl_regression_vs_accepted_allocator")
    if float(aggregate_vs_accepted.get("max_drawdown_delta_max") or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("direct_drawdown_drift_too_high")
    if int(target_summary.get("total_trade_count") or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if min_survival < 0.05:
        failed.append("baseline_survival_below_gate3")
    if changed_selection_count < MIN_CHANGED_SELECTIONS:
        failed.append("changed_selection_count_too_low")
    top5_share = _top5_positive_share(target_summary)
    if top5_share is not None and top5_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("positive_pnl_top5_ticker_share_too_high")
    positive_hhi = target_summary.get("positive_pnl_hhi")
    if positive_hhi is not None and float(positive_hhi) > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_too_high")
    if float(aggregate_vs_core.get("expected_value_score_delta_sum") or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]
    ):
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if float(aggregate_vs_core.get("total_pnl_delta_sum") or 0.0) <= (
        ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]
    ):
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    return {
        "numeric_gate4_passed": not failed,
        "decision": "positive_replay_lead" if not failed else "rejected",
        "failed_reasons": failed,
        "direct_ev_delta_vs_accepted": aggregate_vs_accepted.get(
            "expected_value_score_delta_sum"
        ),
        "direct_pnl_delta_vs_accepted": aggregate_vs_accepted.get("total_pnl_delta_sum"),
        "aggregate_ev_delta_vs_core": aggregate_vs_core.get("expected_value_score_delta_sum"),
        "aggregate_pnl_delta_vs_core": aggregate_vs_core.get("total_pnl_delta_sum"),
        "direct_windows_ev_improved": aggregate_vs_accepted.get("windows_ev_improved"),
        "direct_windows_ev_regressed": aggregate_vs_accepted.get("windows_ev_regressed"),
        "direct_windows_pnl_improved": aggregate_vs_accepted.get("windows_pnl_improved"),
        "direct_windows_pnl_regressed": aggregate_vs_accepted.get("windows_pnl_regressed"),
        "max_direct_drawdown_worse": aggregate_vs_accepted.get("max_drawdown_delta_max"),
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "changed_selection_count": changed_selection_count,
        "changed_selection_count_min": MIN_CHANGED_SELECTIONS,
        "target_trade_count": target_summary.get("total_trade_count"),
        "target_trade_count_min": MIN_TARGET_TRADES,
        "min_survival_rate": round(min_survival, 6),
        "top5_positive_pnl_share": top5_share,
        "positive_pnl_hhi": positive_hhi,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
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
    pair_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_pair_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_pair_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    pair_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    pair_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] source-pair conflict router")
        before_result = baseline_results[label]
        before = before_metrics[label]
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = base._candidate_universe_from_sector_entries(window_sector_entries)
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
        pair_selected, pair_filtered, pair_audit = _select_source_pair_rows(
            source_rows=source_trades,
            trading_dates=dates,
        )

        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_selected,
        )
        pair_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            pair_selected,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        pair_after = framework.overlay_helper._metrics_with_overlay(before_result, pair_overlay)
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        pair_delta = framework.overlay_helper._delta(pair_after, before)
        direct_delta = framework.overlay_helper._delta(pair_after, accepted_after)

        accepted_keys = {_row_key(row) for row in accepted_selected}
        pair_keys = {_row_key(row) for row in pair_selected}
        changed_keys = sorted(accepted_keys.symmetric_difference(pair_keys))

        accepted_metrics[label] = accepted_after
        pair_metrics[label] = pair_after
        accepted_trades_by_window[label] = accepted_selected
        pair_trades_by_window[label] = pair_selected
        source_audit_by_window[label] = source_audit
        accepted_priority_audit_by_window[label] = accepted_priority_audit
        pair_audit_by_window[label] = pair_audit
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
        core_to_pair_rows[label] = {
            "before": before,
            "after": pair_after,
            "delta": pair_delta,
            "target_trade_count": len(pair_selected),
            "selected_source_counts": _source_counts(pair_selected),
            "pair_selected_count": pair_audit["pair_selected_count"],
            "fallback_selected_count": pair_audit["fallback_selected_count"],
            "changed_selection_count": len(changed_keys) // 2,
            "source_trade_counts": source_audit["source_trade_counts"],
        }
        accepted_to_pair_rows[label] = {
            "before": accepted_after,
            "after": pair_after,
            "delta": direct_delta,
            "target_trade_count": len(pair_selected),
            "changed_selection_count": len(changed_keys) // 2,
            "accepted_selected_source_counts": _source_counts(accepted_selected),
            "pair_selected_source_counts": _source_counts(pair_selected),
            "pair_rejected_count": len(pair_filtered),
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_pair = framework._aggregate_window_rows(core_to_pair_rows)
    aggregate_accepted_to_pair = framework._aggregate_window_rows(accepted_to_pair_rows)
    pair_summary = _target_summary(pair_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"]) for row in accepted_to_pair_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_pair,
        aggregate_vs_accepted=aggregate_accepted_to_pair,
        target_summary=pair_summary,
        before_metrics=before_metrics,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "The source-pair conflict router numerically beat the accepted "
            "allocator, but it is not retained because shared helper, daily "
            "shadow-candidate outcome tracking, and snapshot parity were not "
            "implemented."
        )
        reflection = (
            "Pair-relative source-family history may explain part of the "
            "same-day source-choice gap. Treat this as a lead only; promotion "
            "would require shared default-off helper work and forward rows."
        )
    else:
        status = "rejected"
        interpretation = (
            "The source-pair conflict router failed the accepted allocator "
            "comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "The same-day source-choice oracle gap is not explained by simple "
            "pair-relative source-family history. Prior source arbitration "
            "failures plus this result suggest the accepted fixed priority is "
            "already capturing most deterministic source conflict structure on "
            "the frozen windows."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "change_type": "alpha_search_allocation",
        "mechanism_family": "accepted_allocator_source_arbitration",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "status": status,
        "decision": status,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "prediction": PREDICTION,
        "production_impact": PRODUCTION_IMPACT,
        "parameters": {
            "rule_version": PAIR_ROUTER_RULE_VERSION,
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "base_notional_usd": BASE_NOTIONAL_USD,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_pair_history_events": MIN_PAIR_HISTORY_EVENTS,
            "lookback_pair_events": LOOKBACK_PAIR_EVENTS,
            "min_avg_pair_gap_usd": MIN_AVG_PAIR_GAP_USD,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
        },
        "gate2": {
            "required_fields": [
                "entry_date",
                "target_price",
                "ticker",
                "signal_date",
                "source_family",
                "source_priority_rank",
                "source_priority_score",
                "exit_date",
                "pnl",
            ],
            "open_position_audit": gate2_open_positions,
            "passed": bool(gate2_open_positions["passed"]),
        },
        "gate3": {
            "min_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
            "new_core_filter_added": False,
            "note": "Default-off paper allocator scout only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "source_pair_metrics": pair_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_source_pair": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_pair_rows.items()
                ),
                "aggregate": aggregate_core_to_pair,
            },
            "accepted_allocator_to_source_pair": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in accepted_to_pair_rows.items()
                ),
                "aggregate": aggregate_accepted_to_pair,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_source_pair": core_to_pair_rows,
            "accepted_allocator_to_source_pair": accepted_to_pair_rows,
        },
        "target_trades_by_window": pair_trades_by_window,
        "accepted_trades_by_window": accepted_trades_by_window,
        "target_summary": pair_summary,
        "accepted_allocator_target_summary": accepted_summary,
        "source_audit_by_window": source_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "source_pair_audit_by_window": pair_audit_by_window,
        "accepted_comparators": {
            "binding_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "same_run_accepted_allocator_control": aggregate_core_to_accepted,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["numeric_gate4_passed"] else "; ".join(
            gate4["failed_reasons"]
        ),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "negative_reflection": (
                "If rejected, the source-family pair field was still too thin "
                "or too noisy to explain the oracle gap. If positive, it "
                "remains non-accepted because shared helper parity and daily "
                "shadow-candidate outcome tracking are missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping pair lookback, min-history, or "
                "avg-gap thresholds on the same frozen windows. New evidence "
                "would require forward closed conflict rows or a genuinely new "
                "production-visible relation field."
            ),
            "new_evidence_required": (
                "Forward default-off source-conflict outcome ledger or a "
                "separate relation-aware candidate-pool source, not another "
                "allocator source arbitration scalar."
            ),
        },
        "changed_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
        ],
        "reproduction_commands": [
            (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260614_011_source_pair_conflict_router.py"
            )
        ],
        "no_javascript_used": True,
    }
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Core EV | Accepted EV | Pair EV | Direct dEV | Core PnL | Accepted dPnL | Pair dPnL | Direct dPnL | Changed | Pair selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        pair_row = payload["window_rows"]["core_to_source_pair"][label]
        direct_row = payload["window_rows"]["accepted_allocator_to_source_pair"][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {pair_ev:.4f} | {direct_ev:+.4f} | ${core_pnl:,.2f} | ${accepted_pnl:+,.2f} | ${pair_pnl:+,.2f} | ${direct_pnl:+,.2f} | {changed} | {selected} |".format(
                label=label,
                core_ev=float(core["expected_value_score"]),
                accepted_ev=float(accepted_row["after"]["expected_value_score"]),
                pair_ev=float(pair_row["after"]["expected_value_score"]),
                direct_ev=float(direct_row["delta"]["expected_value_score"]),
                core_pnl=float(core["total_pnl"]),
                accepted_pnl=float(accepted_row["delta"]["total_pnl"]),
                pair_pnl=float(pair_row["delta"]["total_pnl"]),
                direct_pnl=float(direct_row["delta"]["total_pnl"]),
                changed=int(direct_row["changed_selection_count"]),
                selected=int(pair_row["target_trade_count"]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"]["accepted_allocator_to_source_pair"]["aggregate"]
    core_to_pair = payload["delta_metrics"]["core_to_source_pair"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Source-Pair Conflict Router",
            "",
            f"- Decision: `{payload['decision']}`",
            "- Direct aggregate EV delta vs accepted allocator: `{:+.4f}`".format(
                direct["expected_value_score_delta_sum"]
            ),
            "- Direct aggregate PnL delta vs accepted allocator: `${:+,.2f}`".format(
                direct["total_pnl_delta_sum"]
            ),
            "- Pair aggregate EV delta vs core: `{:+.4f}`".format(
                core_to_pair["expected_value_score_delta_sum"]
            ),
            "- Pair aggregate PnL delta vs core: `${:+,.2f}`".format(
                core_to_pair["total_pnl_delta_sum"]
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Window Table",
            "",
            *_window_table(payload),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    direct = payload["delta_metrics"]["accepted_allocator_to_source_pair"]["aggregate"]
    core_to_pair = payload["delta_metrics"]["core_to_source_pair"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "status": payload["status"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "history_check": PRE_RUN_QUESTIONS["2_history_check"],
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows, same-run core "
            "baseline, same-run accepted allocator control, and replay-only "
            "source-pair conflict router overlay."
        ),
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": core_to_pair["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": core_to_pair["total_pnl_delta_sum"],
        "direct_expected_value_delta_vs_accepted": direct["expected_value_score_delta_sum"],
        "direct_pnl_delta_vs_accepted": direct["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "accepted_allocator_expected_value": payload["accepted_allocator_metrics"][label][
                    "expected_value_score"
                ],
                "source_pair_expected_value": payload["source_pair_metrics"][label][
                    "expected_value_score"
                ],
                "direct_expected_value_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_pair"
                ]["by_window"][label]["expected_value_score"],
                "direct_pnl_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_pair"
                ]["by_window"][label]["total_pnl"],
                "changed_selection_count": payload["window_rows"][
                    "accepted_allocator_to_source_pair"
                ][label]["changed_selection_count"],
            }
            for label, cfg in framework.WINDOWS.items()
        ],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload["rejection_reason"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "no_javascript_used": True,
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(__file__), OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD, MANIFEST_JSON]
    file_hashes: dict[str, str] = {}
    for path in paths:
        if not path.exists() or path == MANIFEST_JSON:
            continue
        file_hashes[_repo_rel(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "decision": payload["decision"],
        "files": payload["changed_files"],
        "file_hashes": file_hashes,
        "reproduction_commands": payload["reproduction_commands"],
    }
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_JSON.open("w", encoding="utf-8") as handle:
        json.dump(_safe(manifest), handle, indent=2, sort_keys=True)
        handle.write("\n")


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")
    with LOG_JSON.open("w", encoding="utf-8") as handle:
        json.dump(_safe(_build_log_record(payload)), handle, indent=2, sort_keys=True)
        handle.write("\n")
    CARD_MD.write_text(_build_card(payload), encoding="utf-8")
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    direct = payload["delta_metrics"]["accepted_allocator_to_source_pair"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "direct_ev_delta_vs_accepted": direct["expected_value_score_delta_sum"],
                "direct_pnl_delta_vs_accepted": direct["total_pnl_delta_sum"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "card": _repo_rel(CARD_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
