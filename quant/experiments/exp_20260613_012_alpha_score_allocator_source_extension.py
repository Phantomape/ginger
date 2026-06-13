"""exp-20260613-012: alpha-score rank-2 allocator source extension.

Alpha search, replay-only first pass. The fixed policy hypothesis is that the
accepted alpha_score_market_regime signal can add replacement value as a rank-2
source in the accepted source-priority allocator. The source signal is built
from the accepted alpha-score market-regime candidate definition, but replayed
under the allocator's 10-trading-day paper execution envelope so historical and
daily semantics would match if promoted.

No shared helper, run adapter, live/default orders, core strategy, LLM/news, or
watchlist behavior is changed unless this scout first clears Gate 4. No
JavaScript is used.
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
import exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional as alpha21

framework = accepted.framework
exp008 = accepted.exp008
alpha16 = alpha21.source

REPO_ROOT = accepted.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260613-012"
STEM = "alpha_score_allocator_source_extension"
OWNER = "codex-alpha-search"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "alpha_score_market_regime_rank2_source_family_added_to_allocator_v1"
)
CHANGED_VARIABLE = (
    "alpha_score_market_regime_rank2_source_family_added_to_accepted_helper_"
    "source_priority_allocator_v1"
)
ALPHA_SCORE_SOURCE_FAMILY = "alpha_score_market_regime"
ALPHA_SCORE_SOURCE_RULE_VERSION = "alpha_score_market_regime_allocator_signal_10d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = allocator.BASE_NOTIONAL_USD
HOLD_DAYS = allocator.HOLD_DAYS
MAX_ALPHA_SCORE_SOURCE_PER_DAY = 1
MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MIN_CHANGED_SELECTIONS = 9
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
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_allocator_window_comparator_regression",
        "source_overlap_displaces_better_rows",
        "broad_alpha_score_relabels_momentum",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "The accepted alpha_score_market_regime helper has strong standalone "
        "three-window EV and a shared daily/replay boundary, but recent source-"
        "extension attempts often failed by displacing better allocator rows; "
        "success requires alpha_score to supply dates or tickers not already "
        "covered by lagged consensus and relation helpers."
    ),
    "recorded_at": "2026-06-13T08:08:49+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: accepted alpha_score_market_regime "
        "default-off paper rows may add distinct broad cross-sectional "
        "replacement value when admitted as a fixed rank-2 source inside the "
        "accepted source-priority allocator."
    ),
    "2_history_check": {
        "exp-20260531-023": (
            "Accepted alpha_score_market_regime shared default-off adapter; "
            "standalone aggregate EV +1.6439 and PnL +$32,770.52."
        ),
        "exp-20260611-005": (
            "Current accepted allocator with lagged consensus rank 1; "
            "aggregate EV +2.1849 and PnL +$40,397.21 is the binding "
            "allocator comparator."
        ),
        "exp-20260611-008": (
            "Distribution source extension was positive versus core but failed "
            "after lagged consensus/accepted allocator comparison."
        ),
        "exp-20260611-015": (
            "SEC FTD+FINRA source extension failed the accepted allocator "
            "comparator despite positive core-relative EV."
        ),
        "exp-20260613-004/006/009/011": (
            "Recent allocator source-maturity, source-score, microstructure, "
            "and front-loaded-tail retunes all failed; do not tune rank/score "
            "fields here."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The variant must "
        "improve aggregate EV/PnL directly versus same-run accepted allocator, "
        "avoid direct EV/PnL regressions in every canonical window, beat the "
        "exp-20260611-005 accepted allocator comparator versus core, and pass "
        "sample/survival/drawdown/concentration guards. A positive scout is "
        "not accepted until the same source is implemented in the shared daily "
        "allocator helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_012_alpha_score_allocator_source_extension.py"
    ),
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_alpha_score_allocator_source_scout",
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
    "uses_free_ohlcv_only": True,
    "uses_free_non_ohlcv": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "daily_entry_slots": allocator.MAX_PAPER_TRADES_PER_DAY,
        "max_concurrent": allocator.EXECUTION_ENVELOPE["max_concurrent_positions"],
        "same_ticker_cooldown_days": allocator.SAME_TICKER_COOLDOWN_DAYS,
        "order_semantics": "next_open_paper_only_no_orders_emitted",
        "kill_switch_drawdown_pct": allocator.EXECUTION_ENVELOPE[
            "kill_switch_drawdown_pct"
        ],
    },
    "parity_note": (
        "Replay-only source-extension scout. It keeps alpha_score as a "
        "production-visible source signal, but replays entries under the "
        "accepted allocator's 10-day envelope to avoid the 20-day standalone "
        "alpha_score helper creating a daily/backtest mismatch. No shared "
        "allocator helper or run.py source snapshot is changed unless Gate 4 "
        "passes and the behavior is promoted in a separate shared step."
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


def _float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


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


def _extended_source_priority() -> OrderedDict[str, dict[str, Any]]:
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for source_family, meta in allocator.SOURCE_PRIORITY.items():
        if source_family == "lagged_cross_source_consensus":
            out[source_family] = dict(meta)
            out[ALPHA_SCORE_SOURCE_FAMILY] = {
                "rank": 2,
                "description": (
                    "accepted alpha-score market-regime broad cross-sectional "
                    "source, replayed under allocator 10-day envelope"
                ),
                "accepted_experiment": "exp-20260531-023",
                "accepted_ev_delta_sum": 1.6439,
                "accepted_pnl_delta_sum": 32770.52,
            }
            continue
        shifted = dict(meta)
        shifted["rank"] = int(meta["rank"]) + 1
        out[source_family] = shifted
    return out


def _with_source_priority(priority: OrderedDict[str, dict[str, Any]], fn):
    old_priority = allocator.SOURCE_PRIORITY
    allocator.SOURCE_PRIORITY = priority
    try:
        return fn()
    finally:
        allocator.SOURCE_PRIORITY = old_priority


def _paper_trade_10d_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = str(candidate.get("date") or candidate.get("signal_date") or "")[:10]
    rows = snapshot.get(ticker) or []
    row_index = {str(row.get("Date") or "")[:10]: idx for idx, row in enumerate(rows)}
    idx = row_index.get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = framework.ohlcv_helper._value(rows[entry_idx], "Open")
    exit_raw = framework.ohlcv_helper._value(rows[exit_idx], "Close")
    if entry_raw is None or exit_raw is None or entry_raw <= 0:
        return None
    entry_price = framework.fill_model.apply_entry_fill(entry_raw)
    exit_price = framework.fill_model.apply_slippage(
        exit_raw,
        bps=framework.fill_model.SLIPPAGE_BPS_TARGET,
        side="sell",
    )
    pnl_pct_net = (exit_price / entry_price) - 1.0 - framework.constants.ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        **deepcopy(candidate),
        "date": signal_date,
        "signal_date": signal_date,
        "source_family": ALPHA_SCORE_SOURCE_FAMILY,
        "source_rule_version": ALPHA_SCORE_SOURCE_RULE_VERSION,
        "source_score": _float(candidate.get("alpha_score")),
        "candidate_score": _float(candidate.get("alpha_score")),
        "entry_date": str(rows[entry_idx].get("Date") or "")[:10],
        "exit_date": str(rows[exit_idx].get("Date") or "")[:10],
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_status": "closed",
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _build_alpha_score_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = alpha21._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_ALPHA_SCORE_SOURCE_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_10d_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
    return selected, {
        "rule_version": ALPHA_SCORE_SOURCE_RULE_VERSION,
        "source_from": "exp-20260531-023 accepted alpha_score_market_regime helper",
        "execution_envelope": "accepted allocator 10d paper envelope",
        "candidate_count": len(candidates),
        "selected_trade_count": len(selected),
        "filtered_count": len(filtered),
        "filtered_reasons": dict(Counter(str(row.get("filter_reason")) for row in filtered)),
        "candidate_audit": audit,
    }


def _select_extended_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    priority = _extended_source_priority()

    def _run():
        return allocator.select_accepted_helper_source_priority_rows(
            source_rows=source_rows,
            trading_dates=trading_dates,
            config=None,
            create_trades=True,
        )

    selected, filtered, audit = _with_source_priority(priority, _run)
    audit["source_priority"] = priority
    audit["rank2_source_family"] = ALPHA_SCORE_SOURCE_FAMILY
    return selected, filtered, audit


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
    accepted_to_extended_rows: OrderedDict[str, dict[str, Any]],
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
    for label, row in accepted_to_extended_rows.items():
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_ev")
        if float(delta.get("total_pnl") or 0.0) < 0.0:
            comparator_regressions.append(f"{label}_direct_pnl")

    numeric_passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_alpha_score_allocator_source"
        if numeric_passed
        else "rejected_alpha_score_allocator_source_extension"
    )
    if numeric_passed:
        failed.append("shared_helper_parity_missing_for_acceptance")
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
    alpha21._patch_framework()
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    extended_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_extended_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_extended_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    extended_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    alpha_score_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    extended_priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator vs alpha-score rank-2 source")
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
        source_trades, source_audit = allocator._build_source_trades(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        alpha_score_trades, alpha_score_audit = _build_alpha_score_source_trades(
            snapshot=snapshot,
            cfg=cfg,
            universe=universe,
            before_result=before_result,
        )
        extended_source_trades = [*source_trades, *alpha_score_trades]
        accepted_selected, accepted_filtered, accepted_priority_audit = (
            allocator.select_accepted_helper_source_priority_rows(
                source_rows=source_trades,
                trading_dates=dates,
                config=None,
                create_trades=True,
            )
        )
        extended_selected, extended_filtered, extended_priority_audit = (
            _select_extended_rows(
                source_rows=extended_source_trades,
                trading_dates=dates,
            )
        )
        accepted_kept, accepted_skipped, accepted_envelope = (
            allocator.apply_execution_envelope_to_trades(accepted_selected)
        )
        extended_kept, extended_skipped, extended_envelope = (
            allocator.apply_execution_envelope_to_trades(extended_selected)
        )
        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            accepted_kept,
        )
        extended_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            extended_kept,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        extended_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            extended_overlay,
        )
        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        extended_delta = framework.overlay_helper._delta(extended_after, before)
        direct_delta = framework.overlay_helper._delta(extended_after, accepted_after)

        accepted_keys = {_row_key(row) for row in accepted_kept}
        extended_keys = {_row_key(row) for row in extended_kept}
        changed_keys = sorted(accepted_keys.symmetric_difference(extended_keys))
        changed_count = len(changed_keys) // 2

        accepted_metrics[label] = accepted_after
        extended_metrics[label] = extended_after
        accepted_trades_by_window[label] = accepted_kept
        extended_trades_by_window[label] = extended_kept
        source_audit_by_window[label] = {
            **source_audit,
            "source_trade_counts_with_alpha_score": {
                **source_audit["source_trade_counts"],
                ALPHA_SCORE_SOURCE_FAMILY: len(alpha_score_trades),
            },
            "raw_candidate_counts_with_alpha_score": {
                **source_audit["raw_candidate_counts"],
                ALPHA_SCORE_SOURCE_FAMILY: alpha_score_audit["candidate_count"],
            },
        }
        alpha_score_audit_by_window[label] = alpha_score_audit
        accepted_priority_audit_by_window[label] = {
            **accepted_priority_audit,
            "envelope": accepted_envelope,
            "envelope_skipped_count": len(accepted_skipped),
        }
        extended_priority_audit_by_window[label] = {
            **extended_priority_audit,
            "envelope": extended_envelope,
            "envelope_skipped_count": len(extended_skipped),
        }
        core_to_accepted_rows[label] = {
            "before": before,
            "after": accepted_after,
            "delta": accepted_delta,
            "target_trade_count": len(accepted_kept),
            "selected_source_counts": _source_counts(accepted_kept),
            "filtered_daily_top1_count": sum(
                1
                for row in accepted_filtered
                if row.get("filter_reason") == "daily_top1_source_priority_limit"
            ),
        }
        core_to_extended_rows[label] = {
            "before": before,
            "after": extended_after,
            "delta": extended_delta,
            "target_trade_count": len(extended_kept),
            "selected_source_counts": _source_counts(extended_kept),
            "alpha_score_selected_count": _source_counts(extended_kept).get(
                ALPHA_SCORE_SOURCE_FAMILY,
                0,
            ),
            "changed_selection_count": changed_count,
            "source_trade_counts": source_audit_by_window[label][
                "source_trade_counts_with_alpha_score"
            ],
        }
        accepted_to_extended_rows[label] = {
            "before": accepted_after,
            "after": extended_after,
            "delta": direct_delta,
            "target_trade_count": len(extended_kept),
            "changed_selection_count": changed_count,
            "accepted_selected_source_counts": _source_counts(accepted_kept),
            "extended_selected_source_counts": _source_counts(extended_kept),
            "extended_rejected_count": len(extended_filtered),
            "changed_keys_sample": changed_keys[:50],
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_core_to_extended = framework._aggregate_window_rows(core_to_extended_rows)
    aggregate_accepted_to_extended = framework._aggregate_window_rows(
        accepted_to_extended_rows
    )
    extended_summary = _target_summary(extended_trades_by_window)
    accepted_summary = _target_summary(accepted_trades_by_window)
    changed_selection_count = sum(
        int(row["changed_selection_count"])
        for row in accepted_to_extended_rows.values()
    )
    gate4 = _gate4(
        aggregate_vs_core=aggregate_core_to_extended,
        aggregate_vs_accepted=aggregate_accepted_to_extended,
        target_summary=extended_summary,
        before_metrics=before_metrics,
        accepted_to_extended_rows=accepted_to_extended_rows,
        changed_selection_count=changed_selection_count,
    )

    if gate4["numeric_gate4_passed"]:
        status = "positive_replay_lead"
        interpretation = (
            "The alpha-score rank-2 source numerically beat the accepted "
            "allocator, but it is not retained because shared helper and daily "
            "snapshot parity were not implemented in this scout."
        )
        reflection = (
            "Alpha-score supplied enough broad cross-sectional rows under the "
            "allocator 10-day envelope to improve direct replacement value. "
            "The next step would be a shared helper promotion, not another "
            "rank or threshold sweep."
        )
    else:
        status = "rejected"
        interpretation = (
            "The alpha-score rank-2 allocator source failed the accepted "
            "allocator comparison; no strategy or production behavior is retained."
        )
        reflection = (
            "The broad alpha_score source did not add distinct replacement "
            "value after lagged consensus and relation helpers under the "
            "allocator's 10-day envelope. Its standalone 20-day edge likely "
            "does not survive displacement by the accepted source-priority "
            "stack, or it relabels momentum already captured by higher-priority "
            "sources."
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
        "new_evidence_type": "production_visible_accepted_source_family_replay",
        "nearby_prior_experiments": [
            "exp-20260531-023",
            "exp-20260610-005",
            "exp-20260611-005",
            "exp-20260611-008",
            "exp-20260611-015",
            "exp-20260613-004",
            "exp-20260613-009",
        ],
        "prior_trial_count": 0,
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
            "predicted_failure_mode_hit": any(
                mode in ";".join(gate4["failed_reasons"])
                for mode in PREDICTION["main_failure_modes"]
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted-helper allocator overlay and replay-only rank-2 "
                "alpha_score source extension"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "accepted_allocator_rule_version": allocator.RULE_VERSION,
            "accepted_allocator_source_rule_version": allocator.SOURCE_RULE_VERSION,
            "alpha_score_source_rule_version": ALPHA_SCORE_SOURCE_RULE_VERSION,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "rank_inserted": 2,
            "rank_basis": (
                "pre-existing standalone accepted EV: lagged consensus +1.9949 "
                "> alpha_score_market_regime +1.6439 > all lower accepted sources"
            ),
            "alpha_score_signal_source": "exp-20260531-023",
            "allocator_execution_envelope": "exp-20260612-024 v2",
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "daily_entry_slots": allocator.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": allocator.SAME_TICKER_COOLDOWN_DAYS,
            "locked_variables": [
                "alpha_score weights and top-decile source definition",
                "lagged consensus remains rank 1",
                "allocator top1_per_day",
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
                "alpha_score candidates alpha_score/alpha_score_rank_pct",
            ],
        },
        "gate3": {
            "passed": min(
                float(row.get("survival_rate") or 0.0)
                for row in before_metrics.values()
            )
            >= 0.05,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(
                    float(row.get("survival_rate") or 0.0)
                    for row in before_metrics.values()
                ),
                6,
            ),
            "note": "Default-off paper allocator only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "alpha_score_allocator_metrics": extended_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "core_to_alpha_score_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_extended_rows.items()
                ),
                "aggregate": aggregate_core_to_extended,
            },
            "accepted_allocator_to_alpha_score_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"])
                    for label, row in accepted_to_extended_rows.items()
                ),
                "aggregate": aggregate_accepted_to_extended,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "core_to_alpha_score_allocator": core_to_extended_rows,
            "accepted_allocator_to_alpha_score_allocator": accepted_to_extended_rows,
        },
        "accepted_trade_summary": accepted_summary,
        "alpha_score_allocator_trade_summary": extended_summary,
        "source_audit_by_window": source_audit_by_window,
        "alpha_score_source_audit_by_window": alpha_score_audit_by_window,
        "accepted_priority_audit_by_window": accepted_priority_audit_by_window,
        "extended_priority_audit_by_window": extended_priority_audit_by_window,
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
                "If rejected, broad alpha_score did not supply enough "
                "independent replacement value under the accepted allocator "
                "envelope. If positive, the result remains non-accepted because "
                "shared helper parity is missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing alpha_score source rank, alpha_score "
                "thresholds, score weights, allocator top-N, notional, hold days, "
                "cooldown, or adding more already accepted helpers on the frozen "
                "windows."
            ),
            "new_evidence_required": (
                "A retry needs closed forward source-competition replacement rows, "
                "a materially new PIT data edge beyond broad alpha_score momentum, "
                "or a shared-helper promotion only if this exact fixed bundle first "
                "passes Gate 4."
            ),
        },
        "next_retry_requires": [
            "closed forward source-competition replacement rows",
            "materially new PIT source-quality field",
            "no frozen-window rank/threshold/hold/notional sweep",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Core EV | Accepted EV | AlphaScore EV | Direct dEV | Core PnL | Accepted dPnL | AlphaScore dPnL | Direct dPnL | Changed | AlphaScore selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        extended_row = payload["window_rows"]["core_to_alpha_score_allocator"][label]
        direct_row = payload["window_rows"][
            "accepted_allocator_to_alpha_score_allocator"
        ][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {extended_ev:.4f} | {direct_ev:+.4f} | ${core_pnl:,.2f} | ${accepted_dpnl:+,.2f} | ${extended_dpnl:+,.2f} | ${direct_dpnl:+,.2f} | {changed} | {alpha_selected} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                accepted_ev=accepted_row["after"]["expected_value_score"],
                extended_ev=extended_row["after"]["expected_value_score"],
                direct_ev=direct_row["delta"]["expected_value_score"],
                core_pnl=core["total_pnl"],
                accepted_dpnl=accepted_row["delta"]["total_pnl"],
                extended_dpnl=extended_row["delta"]["total_pnl"],
                direct_dpnl=direct_row["delta"]["total_pnl"],
                changed=direct_row["changed_selection_count"],
                alpha_selected=extended_row["alpha_score_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    direct = payload["delta_metrics"][
        "accepted_allocator_to_alpha_score_allocator"
    ]["aggregate"]
    core_to_extended = payload["delta_metrics"]["core_to_alpha_score_allocator"][
        "aggregate"
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Alpha-Score Allocator Source Extension",
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
            "- Alpha-score allocator aggregate EV delta vs core: `{:+.4f}`".format(
                core_to_extended["expected_value_score_delta_sum"]
            ),
            "- Alpha-score allocator aggregate PnL delta vs core: `${:+,.2f}`".format(
                core_to_extended["total_pnl_delta_sum"]
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
        "accepted_allocator_to_alpha_score_allocator"
    ]["aggregate"]
    core_to_extended = payload["delta_metrics"]["core_to_alpha_score_allocator"][
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
        "aggregate_expected_value_delta": core_to_extended[
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": core_to_extended["total_pnl_delta_sum"],
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
                "alpha_score_allocator_expected_value": payload[
                    "alpha_score_allocator_metrics"
                ][label]["expected_value_score"],
                "direct_expected_value_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_alpha_score_allocator"
                ]["by_window"][label]["expected_value_score"],
                "direct_pnl_delta_vs_accepted": payload["delta_metrics"][
                    "accepted_allocator_to_alpha_score_allocator"
                ]["by_window"][label]["total_pnl"],
                "changed_selection_count": payload["window_rows"][
                    "accepted_allocator_to_alpha_score_allocator"
                ][label]["changed_selection_count"],
                "selected_source_counts": payload["window_rows"][
                    "core_to_alpha_score_allocator"
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
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
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


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
    _write_json(TICKET_JSON, ticket)


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
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        status=payload["status"],
        result={
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": PRODUCTION_IMPACT,
        },
        prediction=PREDICTION,
        fields={
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "owner": OWNER,
        },
    )
    _upsert_jsonl(EXPERIMENT_LOG, log_record)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(payload)
    _persist_registry(payload, log_record)


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
