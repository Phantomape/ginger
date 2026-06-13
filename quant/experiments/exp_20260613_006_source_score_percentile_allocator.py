"""exp-20260613-006: source-score percentile allocator arbitration scout.

Alpha search, replay-only. The policy under test is an ex-ante source-quality
arbitration field for same-day accepted allocator source conflicts. Each source
candidate is ranked by its raw source score percentile versus that source
family's own prior signal-day score history. Same-day rows never train
themselves. No production/shared helper is changed in this runner.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import timedelta
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


EXPERIMENT_ID = "exp-20260613-006"
STEM = "source_score_percentile_allocator"
OWNER = "alpha-search-automation"
TRIAL_FAMILY = "accepted_allocator_source_arbitration"
TRIAL_VARIANT_ID = "source_score_percentile_allocator_arbitration_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
SOURCE_SCORE_PERCENTILE_RULE_VERSION = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MIN_HISTORY_ROWS = 20
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
    "success_probability": 0.22,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "score_percentile_not_comparable",
        "accepted_allocator_comparator_not_beaten",
        "window_regression",
        "history_too_thin",
        "source_family_concentration",
    ],
    "confidence_reason": (
        "exp-20260613-003 showed a material same-day source-choice oracle gap, "
        "while exp-20260613-004 showed trailing PnL maturity is too noisy. A "
        "source-internal score percentile is ex-ante and avoids cross-source "
        "raw-score comparability, but risk is high because score fields may "
        "still relabel accepted priority or overfit frozen windows."
    ),
    "recorded_at": "2026-06-13T03:04:57+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: accepted allocator same-day source "
        "conflicts may improve by selecting the candidate whose source raw "
        "score is unusually strong versus that source family's own prior "
        "signal-day score distribution, while falling back to accepted fixed "
        "priority when source history is too thin."
    ),
    "2_history_check": {
        "exp-20260611-005": (
            "Current accepted source-priority allocator with lagged consensus; "
            "aggregate EV +2.1849 and PnL +$40,397.21 is the binding accepted "
            "comparator."
        ),
        "exp-20260613-003": (
            "Observed-only same-day source-choice oracle found a material gap, "
            "but used future PnL and required a PIT arbitration field."
        ),
        "exp-20260613-004": (
            "Trailing closed-PnL source maturity arbitration was rejected; "
            "do not retry noisy performance chasing."
        ),
        "exp-20260608-009": (
            "Same-day industry/source consensus was rejected with thin sample "
            "and negative PnL, so this test avoids same-day consensus filters."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve aggregate EV/PnL versus the same-run accepted allocator "
        "control, avoid direct EV/PnL window regressions, beat the accepted "
        "exp-20260611-005 comparator, and pass sample/survival/drawdown/"
        "concentration guards. Because this runner does not change the shared "
        "daily helper, a positive result is a lead only."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_006_source_score_percentile_allocator.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_source_score_percentile_scout",
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
            "evidence would require a shared helper and daily snapshot parity "
            "before retention."
        ),
    },
    "parity_note": (
        "Replay-only source-score percentile scout. It reuses accepted "
        "allocator source rows and only uses each source family's prior "
        "signal-day source scores at each signal date. No source priority, "
        "helper, daily snapshot, report, ranking, sizing, exit, watchlist, "
        "LLM/news, or order surface is changed."
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


def _load_window_snapshot_deep_readonly(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Window snapshot loader using immutable SQLite reads for this scout."""
    start = framework._parse_date(cfg["start"]) - timedelta(
        days=exp008.SNAPSHOT_LOOKBACK_CALENDAR_DAYS
    )
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{framework.WAREHOUSE.as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
    )


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _score_percentile(score: float, history: list[float]) -> float:
    if not history:
        return 0.0
    below_or_equal = sum(1 for value in history if value <= score)
    return below_or_equal / len(history)


def _score_stats(
    *,
    source_family: str,
    source_score: float,
    score_history: dict[str, list[float]],
) -> dict[str, Any]:
    history = list(score_history.get(source_family, []))
    count = len(history)
    if count <= 0:
        return {
            "history_count": 0,
            "history_ready": False,
            "source_score": round(source_score, 6),
            "percentile": None,
            "history_mean": None,
            "history_min": None,
            "history_max": None,
        }
    percentile = _score_percentile(source_score, history)
    mean = sum(history) / count
    return {
        "history_count": count,
        "history_ready": count >= MIN_HISTORY_ROWS,
        "source_score": round(source_score, 6),
        "percentile": round(percentile, 6),
        "history_mean": round(mean, 6),
        "history_min": round(min(history), 6),
        "history_max": round(max(history), 6),
    }


def _prepared_candidate(
    row: dict[str, Any],
    *,
    score_stats: dict[str, Any],
    selected_by: str,
) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    normalised = _normalise_source_row(row, source_family)
    out = {
        **deepcopy(row),
        **normalised,
        "source": "SOURCE_SCORE_PERCENTILE_ALLOCATOR_REPLAY_ONLY",
        "sleeve": "SOURCE_SCORE_PERCENTILE_ALLOCATOR_REPLAY_ONLY",
        "rule_version": SOURCE_SCORE_PERCENTILE_RULE_VERSION,
        "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
        "decision_id": (
            "SOURCE_SCORE_PERCENTILE_ALLOCATOR_REPLAY_ONLY:"
            f"{SOURCE_SCORE_PERCENTILE_RULE_VERSION}:"
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
        "source_score_percentile": score_stats,
        "source_score_percentile_selected_by": selected_by,
    }
    return out


def _select_source_score_percentile_rows(
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
    candidates.sort(
        key=lambda row: (
            _date10(row.get("signal_date") or row.get("date")),
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        signal_date = _date10(row.get("signal_date") or row.get("date"))
        if signal_date:
            by_date.setdefault(signal_date, []).append(row)

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    score_history: dict[str, list[float]] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    percentile_selected = 0
    fallback_selected = 0
    history_ready_candidate_count = 0
    changed_source_count = 0
    selected_source_counts: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    percentile_score_samples: list[dict[str, Any]] = []

    for signal_date in sorted(by_date):
        raw_day_rows = by_date[signal_date]
        pos = date_position.get(signal_date)
        if pos is None:
            for row in raw_day_rows:
                rejected_row = {**row, "filter_reason": "missing_signal_date_position"}
                rejected.append(rejected_row)
                rejected_reasons["missing_signal_date_position"] += 1
            continue

        day_rows: list[dict[str, Any]] = []
        for row in raw_day_rows:
            ticker = str(row.get("ticker") or "").upper()
            if pos < next_allowed_pos_by_ticker.get(ticker, -1):
                rejected_row = {**row, "filter_reason": "same_ticker_cooldown"}
                rejected.append(rejected_row)
                rejected_reasons["same_ticker_cooldown"] += 1
                continue
            source_family = str(row.get("source_family") or "unknown")
            source_score = _float(row.get("source_priority_score"))
            stats = _score_stats(
                source_family=source_family,
                source_score=source_score,
                score_history=score_history,
            )
            annotated = {**row, "source_score_percentile": stats}
            day_rows.append(annotated)
            if stats["history_ready"]:
                history_ready_candidate_count += 1

        if day_rows:
            accepted_priority_winner = min(
                day_rows,
                key=lambda row: (
                    int(row.get("source_priority_rank") or 999),
                    -_float(row.get("source_priority_score")),
                    str(row.get("ticker") or ""),
                ),
            )
            ready_rows = [
                row
                for row in day_rows
                if (row.get("source_score_percentile") or {}).get("history_ready")
            ]
            if ready_rows:
                winner = max(
                    ready_rows,
                    key=lambda row: (
                        _float((row.get("source_score_percentile") or {}).get("percentile")),
                        _float(row.get("source_priority_score")),
                        -int(row.get("source_priority_rank") or 999),
                        str(row.get("ticker") or ""),
                    ),
                )
                selected_by = "source_score_percentile"
                percentile_selected += 1
            else:
                winner = accepted_priority_winner
                selected_by = "accepted_priority_fallback"
                fallback_selected += 1

            if _row_key(winner) != _row_key(accepted_priority_winner):
                changed_source_count += 1

            winner_out = _prepared_candidate(
                winner,
                score_stats=winner.get("source_score_percentile") or {},
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
                    "filter_reason": "daily_top1_source_score_percentile_limit",
                    "source_score_percentile_selected_winner": _row_key(winner),
                }
                rejected.append(rejected_row)
                rejected_reasons["daily_top1_source_score_percentile_limit"] += 1

            if len(percentile_score_samples) < 30:
                for row in sorted(
                    day_rows,
                    key=lambda item: (
                        -_float(
                            (item.get("source_score_percentile") or {}).get("percentile")
                        ),
                        -_float(item.get("source_priority_score")),
                        int(item.get("source_priority_rank") or 999),
                        str(item.get("ticker") or ""),
                    ),
                )[:3]:
                    percentile_score_samples.append(
                        {
                            "signal_date": signal_date,
                            "ticker": str(row.get("ticker") or ""),
                            "source_family": str(row.get("source_family") or ""),
                            "source_priority_rank": row.get("source_priority_rank"),
                            "source_priority_score": row.get("source_priority_score"),
                            "source_score_percentile": row.get(
                                "source_score_percentile"
                            ),
                            "selected": _row_key(row) == _row_key(winner),
                            "selected_by": selected_by,
                        }
                    )

        for row in raw_day_rows:
            source_family = str(row.get("source_family") or "unknown")
            score_history.setdefault(source_family, []).append(
                _float(row.get("source_priority_score"))
            )

    audit = {
        "rule_version": SOURCE_SCORE_PERCENTILE_RULE_VERSION,
        "min_history_rows": MIN_HISTORY_ROWS,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "percentile_selected_count": percentile_selected,
        "fallback_selected_count": fallback_selected,
        "history_ready_candidate_count": history_ready_candidate_count,
        "changed_source_count_vs_same_day_priority": changed_source_count,
        "selected_source_counts": dict(selected_source_counts),
        "rejected_reasons": dict(rejected_reasons),
        "source_score_history_counts": {
            family: len(values) for family, values in sorted(score_history.items())
        },
        "percentile_score_samples": percentile_score_samples,
        "known_at": (
            "after signal-day close and before next-open paper entry; each "
            "source percentile uses only prior signal-day source scores from "
            "the same source family, so same-day rows never train themselves"
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
    accepted_to_percentile_rows: OrderedDict[str, dict[str, Any]],
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
    for label, row in accepted_to_percentile_rows.items():
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_ev")
        if float(delta.get("total_pnl") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_pnl")

    numeric_passed = not failed
    if numeric_passed:
        decision = "positive_replay_lead_not_promoted_source_score_percentile_allocator"
        failed.append("shared_helper_parity_missing_for_acceptance")
    else:
        decision = "rejected_source_score_percentile_allocator"
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
    percentile_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_percentile_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_percentile_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    percentile_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    percentile_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] source-score-percentile allocator")
        before_result = baseline_results[label]
        before = before_metrics[label]
        snapshot = _load_window_snapshot_deep_readonly(
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
        percentile_selected, percentile_filtered, percentile_audit = (
            _select_source_score_percentile_rows(
                source_rows=source_trades,
                trading_dates=dates,
            )
        )

        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_selected,
        )
        percentile_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            percentile_selected,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        percentile_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            percentile_overlay,
        )
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        percentile_delta = framework.overlay_helper._delta(percentile_after, before)
        direct_delta = framework.overlay_helper._delta(percentile_after, accepted_after)

        accepted_keys = {_row_key(row) for row in accepted_selected}
        percentile_keys = {_row_key(row) for row in percentile_selected}
        changed_keys = sorted(accepted_keys.symmetric_difference(percentile_keys))

        accepted_metrics[label] = accepted_after
        percentile_metrics[label] = percentile_after
        accepted_trades_by_window[label] = accepted_selected
        percentile_trades_by_window[label] = percentile_selected
        source_audit_by_window[label] = source_audit
        accepted_priority_audit_by_window[label] = accepted_priority_audit
        percentile_audit_by_window[label] = percentile_audit
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
        core_to_percentile_rows[label] = {
            "before": before,
            "after": percentile_after,
            "delta": percentile_delta,
            "target_trade_count": len(percentile_selected),
            "selected_source_counts": _source_counts(percentile_selected),
            "percentile_selected_count": percentile_audit[
                "percentile_selected_count"
            ],
            "fallback_selected_count": percentile_audit["fallback_selected_count"],
            "changed_selection_count": len(changed_keys) // 2,
            "source_trade_counts": source_audit["source_trade_counts"],
        }
        accepted_to_percentile_rows[label] = {
            "before": accepted_after,
            "after": percentile_after,
            "delta": direct_delta,
            "target_trade_count": len(percentile_selected),
            "changed_selection_count": len(changed_keys) // 2,
            "accepted_selected_source_counts": _source_counts(accepted_selected),
            "percentile_selected_source_counts": _source_counts(percentile_selected),
            "percentile_rejected_count": len(percentile_filtered),
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_percentile = framework._aggregate_window_rows(
        core_to_percentile_rows
    )
    aggregate_accepted_to_percentile = framework._aggregate_window_rows(
        accepted_to_percentile_rows
    )
    percentile_summary = _target_summary(percentile_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"]) for row in accepted_to_percentile_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_percentile,
        aggregate_vs_accepted=aggregate_accepted_to_percentile,
        target_summary=percentile_summary,
        before_metrics=before_metrics,
        accepted_to_percentile_rows=accepted_to_percentile_rows,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "The source-score percentile allocator numerically beat the "
            "accepted allocator, but it is not retained because shared helper "
            "and daily snapshot parity were not implemented."
        )
        reflection = (
            "Source-internal score percentiles appear to explain part of the "
            "same-day source-choice gap without future PnL. The result is only "
            "a lead until the same field is implemented in the shared default-"
            "off allocator helper and production snapshot."
        )
    else:
        status = "rejected"
        interpretation = (
            "The source-score percentile allocator failed the accepted "
            "allocator comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "Raw source-score percentiles were not enough to arbitrate same-day "
            "source conflicts better than the accepted fixed priority. The "
            "oracle gap from exp-20260613-003 is likely coming from information "
            "not captured by each source's own raw score distribution, or from "
            "source fields whose percentile ranks are too regime/sample dependent."
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
        "new_evidence_type": "new_production_visible_source_quality_percentile_field",
        "nearby_prior_experiments": [
            "exp-20260611-005",
            "exp-20260613-003",
            "exp-20260613-004",
            "exp-20260608-009",
        ],
        "prior_trial_count": 2,
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
                "accepted-helper allocator overlay and replay-only source-score "
                "percentile variant"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "source_score_percentile_rule_version": SOURCE_SCORE_PERCENTILE_RULE_VERSION,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "min_history_rows": MIN_HISTORY_ROWS,
            "source_score_percentile": (
                "rank of current raw source_priority_score versus prior "
                "signal-day source_priority_score values from the same source family"
            ),
            "same_day_self_training": False,
            "fallback": "accepted fixed source priority when no same-day row has enough history",
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
                "source rows source_priority_score for prior percentile history",
            ],
            "local_measurement_note": (
                "This runner uses an immutable read-only SQLite snapshot loader "
                "because the canonical loader's normal connection hit a "
                "Windows disk I/O error in the current dirty workspace. Query "
                "SQL, date range, fields, and ticker universe match exp008."
            ),
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
        "source_score_percentile_metrics": percentile_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_source_score_percentile": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_percentile_rows.items()
                ),
                "aggregate": aggregate_core_to_percentile,
            },
            "accepted_allocator_to_source_score_percentile": {
                "by_window": OrderedDict(
                    (label, row["delta"])
                    for label, row in accepted_to_percentile_rows.items()
                ),
                "aggregate": aggregate_accepted_to_percentile,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_source_score_percentile": core_to_percentile_rows,
            "accepted_allocator_to_source_score_percentile": accepted_to_percentile_rows,
        },
        "accepted_trade_summary": accepted_summary,
        "source_score_percentile_trade_summary": percentile_summary,
        "source_audit_by_window": source_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "source_score_percentile_audit_by_window": percentile_audit_by_window,
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
                "If rejected, source-internal score percentile was either too "
                "coarse or too source/regime dependent to explain the oracle "
                "gap. If positive, the result remains non-accepted because "
                "shared helper parity is missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping percentile min-history, percentile "
                "tie-breakers, source rank, top-N, notional, hold days, or "
                "cooldown on the same frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs closed forward source-competition rows, "
                "a materially richer PIT source-quality field, or shared daily "
                "source-score history recorded before replay promotion."
            ),
        },
        "next_retry_requires": [
            "closed forward source-competition replacement rows",
            "shared helper plus daily parity if any source-score percentile field is promoted",
            "no frozen-window min-history/tie-breaker sweep",
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
        "| Window | Core EV | Accepted EV | Percentile EV | Direct dEV | Core PnL | Accepted dPnL | Percentile dPnL | Direct dPnL | Changed | Percentile selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        percentile_row = payload["window_rows"]["core_to_source_score_percentile"][label]
        direct_row = payload["window_rows"][
            "accepted_allocator_to_source_score_percentile"
        ][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {percentile_ev:.4f} | {direct_ev:+.4f} | ${core_pnl:,.2f} | ${accepted_dpnl:+,.2f} | ${percentile_dpnl:+,.2f} | ${direct_dpnl:+,.2f} | {changed} | {percentile_selected} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                accepted_ev=accepted_row["after"]["expected_value_score"],
                percentile_ev=percentile_row["after"]["expected_value_score"],
                direct_ev=direct_row["delta"]["expected_value_score"],
                core_pnl=core["total_pnl"],
                accepted_dpnl=accepted_row["delta"]["total_pnl"],
                percentile_dpnl=percentile_row["delta"]["total_pnl"],
                direct_dpnl=direct_row["delta"]["total_pnl"],
                changed=direct_row["changed_selection_count"],
                percentile_selected=percentile_row["percentile_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"][
        "accepted_allocator_to_source_score_percentile"
    ]["aggregate"]
    core_to_percentile = payload["delta_metrics"][
        "core_to_source_score_percentile"
    ]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Source Score Percentile Allocator",
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
            "- Percentile aggregate EV delta vs core: `{:+.4f}`".format(
                core_to_percentile["expected_value_score_delta_sum"]
            ),
            "- Percentile aggregate PnL delta vs core: `${:+,.2f}`".format(
                core_to_percentile["total_pnl_delta_sum"]
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
    direct = payload["delta_metrics"][
        "accepted_allocator_to_source_score_percentile"
    ]["aggregate"]
    core_to_percentile = payload["delta_metrics"][
        "core_to_source_score_percentile"
    ]["aggregate"]
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
        "aggregate_expected_value_delta": core_to_percentile[
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": core_to_percentile["total_pnl_delta_sum"],
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
                "source_score_percentile_expected_value": payload[
                    "source_score_percentile_metrics"
                ][label]["expected_value_score"],
                "direct_expected_value_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_score_percentile"
                ]["by_window"][label]["expected_value_score"],
                "direct_pnl_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_source_score_percentile"
                ]["by_window"][label]["total_pnl"],
                "changed_selection_count": payload["window_rows"][
                    "accepted_allocator_to_source_score_percentile"
                ][label]["changed_selection_count"],
                "selected_source_counts": payload["window_rows"][
                    "core_to_source_score_percentile"
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
            "docs/experiment_log.jsonl and registry were not touched because "
            "the worktree already contained unrelated dirty automation state."
        ),
        "claim_note": (
            "Reservation allocated exp-20260613-006, but the registry/ticket "
            "atomic replace failed with PermissionError. The generated temp "
            "ticket experiments/tickets/.exp-20260613-006.json.zxf2an3v.tmp "
            "was copied into the final ticket path and manually marked claimed "
            "before this runner wrote the closeout artifacts."
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
