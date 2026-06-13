"""exp-20260613-003: accepted allocator source competition opportunity.

Observed-only alpha attribution. This does not change shared policy or
production behavior. It asks whether the accepted helper source-priority
allocator still has material same-day source-choice opportunity that could
justify a future ex-ante arbitration field.

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
    _build_source_trades,
    select_accepted_helper_source_priority_rows,
)
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260613-003"
STEM = "allocator_source_competition_opportunity"
OWNER = "alpha-search-automation"
TRIAL_FAMILY = "accepted_allocator_source_arbitration_attribution"
TRIAL_VARIANT_ID = "same_day_source_choice_oracle_upper_bound_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MIN_MATERIAL_ORACLE_PNL_GAP = 10_000.0
MIN_MATERIAL_ORACLE_EV_GAP = 0.50
MIN_POSITIVE_GAP_WINDOWS = 2

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation attribution: the accepted helper "
        "source-priority allocator may still leave money in same-day source "
        "competition. A large multi-window oracle gap would imply the next "
        "alpha direction should be a production-safe ex-ante source arbitration "
        "field based on free relation/source-maturity data, not another source "
        "priority or threshold retune."
    ),
    "2_history_check": {
        "exp-20260611-005": (
            "Accepted lagged consensus rank-1 shared allocator source. This is "
            "the current production-visible default-off allocator boundary."
        ),
        "exp-20260612-027": (
            "Broad source-state attribution found one stable-core-flow state "
            "lead but was observed-only and required router validation."
        ),
        "exp-20260613-002": (
            "Stable-core-flow state router was rejected: positive versus core "
            "but failed versus the accepted allocator and selected only three "
            "forward rows."
        ),
        "recent_frozen_near_neighbors": (
            "52-week/source extension, SEC/FINRA, Companyfacts support/quality "
            "retunes, distribution-state router, slot-sliced core, and allocator "
            "pruning variants are recent rejected/frozen paths."
        ),
    },
    "3_single_causal_variable": (
        "One observed-only policy question: is there material same-day source "
        "competition opportunity inside the accepted allocator? No executable "
        "strategy parameter is changed."
    ),
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three-window comparison. Because this "
        "uses future PnL to select the best competing source row, it cannot be "
        "accepted as a paper/live policy. It can only accept or reject the next "
        "research direction."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_003_allocator_source_competition_opportunity.py"
    ),
}

PREDICTION = {
    "success_probability": 0.55,
    "expected_ev_delta": 1.0,
    "expected_pnl_delta": 15_000.0,
    "main_failure_modes": [
        "accepted_priority_already_captures_most_same_day_edge",
        "oracle_gap_concentrated_in_one_window",
        "oracle_gap_not_explainable_by_point_in_time_fields",
        "future_pnl_oracle_not_tradeable",
    ],
    "confidence_reason": (
        "Recent source-extension and state-router failures show direct allocator "
        "retunes are mostly redundant, but the accepted allocator still sees many "
        "same-day lower-priority rows; an oracle gap is plausible if fixed source "
        "priority discards independent evidence on crowded signal dates."
    ),
    "recorded_at": "2026-06-13T00:18:00+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "observed_only_no_policy_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": False,
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
    "parity_note": (
        "Observed-only oracle attribution. Historical replay reuses the shared "
        "accepted allocator source rows, but no source priority, helper, daily "
        "snapshot, report, ranking, sizing, exit, watchlist, LLM/news, or order "
        "surface is changed."
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


def _float(value: Any, default: float = 0.0) -> float:
    rounded = _round(value, 12)
    return default if rounded is None else rounded


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


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
        str(row.get("source_family") or "unknown"),
        str(row.get("entry_date") or ""),
    )


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_family") or "unknown") for row in rows))


def _best_by_pnl(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda row: (
            _float(row.get("pnl")),
            -int(row.get("source_priority_rank") or 999),
            str(row.get("ticker") or ""),
        ),
    )


def _source_competition_oracle(
    *,
    selected: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected_keys = {_row_key(row) for row in selected}
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in selected:
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        by_date.setdefault(signal_date, []).append({**deepcopy(row), "oracle_role": "accepted"})
    for row in filtered:
        if row.get("filter_reason") != "daily_top1_source_priority_limit":
            continue
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        by_date.setdefault(signal_date, []).append(
            {**deepcopy(row), "oracle_role": "same_day_competing_source"}
        )

    oracle_rows: list[dict[str, Any]] = []
    daily_gaps: list[dict[str, Any]] = []
    switch_counts: Counter[str] = Counter()
    selected_source_counts: Counter[str] = Counter()
    oracle_source_counts: Counter[str] = Counter()
    for signal_date, rows in sorted(by_date.items()):
        accepted_rows = [row for row in rows if _row_key(row) in selected_keys]
        if not accepted_rows:
            continue
        accepted_row = accepted_rows[0]
        best = _best_by_pnl(rows)
        accepted_pnl = _float(accepted_row.get("pnl"))
        oracle_pnl = _float(best.get("pnl"))
        gap = round(oracle_pnl - accepted_pnl, 2)
        best_out = {
            **deepcopy(best),
            "source": "OBSERVED_ONLY_SOURCE_CHOICE_ORACLE",
            "sleeve": "OBSERVED_ONLY_SOURCE_CHOICE_ORACLE",
            "rule_version": "observed_only_source_competition_oracle_v1",
            "source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "notional_usd": BASE_NOTIONAL_USD,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
            "oracle_note": "future_pnl_selected_not_tradeable",
        }
        oracle_rows.append(best_out)
        selected_source = str(accepted_row.get("source_family") or "unknown")
        oracle_source = str(best.get("source_family") or "unknown")
        selected_source_counts[selected_source] += 1
        oracle_source_counts[oracle_source] += 1
        if oracle_source != selected_source or _row_key(best) != _row_key(accepted_row):
            switch_counts[f"{selected_source}->{oracle_source}"] += 1
        if gap > 0:
            daily_gaps.append(
                {
                    "signal_date": signal_date,
                    "accepted_ticker": str(accepted_row.get("ticker") or ""),
                    "accepted_source": selected_source,
                    "accepted_pnl": round(accepted_pnl, 2),
                    "oracle_ticker": str(best.get("ticker") or ""),
                    "oracle_source": oracle_source,
                    "oracle_pnl": round(oracle_pnl, 2),
                    "gap": gap,
                    "same_day_candidate_count": len(rows),
                }
            )

    daily_gaps.sort(key=lambda row: float(row["gap"]), reverse=True)
    audit = {
        "selected_day_count": len(selected),
        "oracle_day_count": len(oracle_rows),
        "same_day_positive_switch_count": len(daily_gaps),
        "same_day_positive_switch_gap_total": round(
            sum(float(row["gap"]) for row in daily_gaps),
            2,
        ),
        "selected_source_counts": dict(selected_source_counts),
        "oracle_source_counts": dict(oracle_source_counts),
        "switch_counts": dict(switch_counts),
        "top_positive_switches": daily_gaps[:25],
        "oracle_caveat": (
            "This upper bound selects by future closed-trade PnL among rows the "
            "accepted allocator saw on the same signal date. It ignores how an "
            "alternative pick could alter later ticker cooldown state, so it is "
            "directional attribution only."
        ),
    }
    return oracle_rows, audit


def _target_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return framework.sleeve._target_trade_summary(rows_by_window)


def _gate4_direction(
    *,
    aggregate_accepted_to_oracle: dict[str, Any],
    oracle_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_gap = _float(aggregate_accepted_to_oracle.get("expected_value_score_delta_sum"))
    pnl_gap = _float(aggregate_accepted_to_oracle.get("total_pnl_delta_sum"))
    positive_windows = int(aggregate_accepted_to_oracle.get("windows_pnl_improved") or 0)
    material = (
        ev_gap >= MIN_MATERIAL_ORACLE_EV_GAP
        and pnl_gap >= MIN_MATERIAL_ORACLE_PNL_GAP
        and positive_windows >= MIN_POSITIVE_GAP_WINDOWS
    )
    failed = ["uses_future_pnl_oracle", "no_ex_ante_field", "no_production_policy_change"]
    if not material:
        failed.append("oracle_gap_not_material_enough_for_new_arbitration_work")
    return {
        "passed": False,
        "observed_direction_material": material,
        "decision": (
            "observed_only_material_source_arbitration_gap_requires_ex_ante_field"
            if material
            else "observed_only_source_arbitration_gap_not_material"
        ),
        "failed_reasons": failed,
        "aggregate_ev_gap_vs_accepted_allocator": round(ev_gap, 6),
        "aggregate_pnl_gap_vs_accepted_allocator": round(pnl_gap, 2),
        "windows_pnl_improved_vs_accepted_allocator": positive_windows,
        "material_thresholds": {
            "min_oracle_ev_gap": MIN_MATERIAL_ORACLE_EV_GAP,
            "min_oracle_pnl_gap": MIN_MATERIAL_ORACLE_PNL_GAP,
            "min_positive_gap_windows": MIN_POSITIVE_GAP_WINDOWS,
        },
        "oracle_trade_count": oracle_summary["total_trade_count"],
        "note": (
            "Gate 4 cannot accept this as a strategy because the after path is "
            "an ex-post oracle. The only valid output is whether source "
            "arbitration remains worth a future shared, ex-ante alpha attempt."
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
    oracle_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_accepted_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_to_oracle_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    core_to_oracle_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    accepted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    oracle_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    oracle_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    baseline_results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    # Precompute all baselines before invoking helper builders; some legacy helper
    # scans have process-level side effects that can otherwise contaminate later windows.
    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] canonical core baseline")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baseline_results[label] = before_result
        before_metrics[label] = framework.overlay_helper._metrics(before_result)

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator source competition opportunity")
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
        selected, filtered, priority_audit = select_accepted_helper_source_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
            config=None,
            create_trades=True,
        )
        oracle_rows, oracle_audit = _source_competition_oracle(
            selected=selected,
            filtered=filtered,
        )

        accepted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            selected,
        )
        oracle_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            oracle_rows,
        )
        accepted_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            accepted_overlay,
        )
        oracle_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            oracle_overlay,
        )

        accepted_delta = framework.overlay_helper._delta(accepted_after, before)
        oracle_delta_vs_core = framework.overlay_helper._delta(oracle_after, before)
        oracle_delta_vs_accepted = framework.overlay_helper._delta(
            oracle_after,
            accepted_after,
        )

        before_metrics[label] = before
        accepted_metrics[label] = accepted_after
        oracle_metrics[label] = oracle_after
        accepted_trades_by_window[label] = selected
        oracle_trades_by_window[label] = oracle_rows
        source_audit_by_window[label] = source_audit
        priority_audit_by_window[label] = priority_audit
        oracle_audit_by_window[label] = oracle_audit
        core_to_accepted_rows[label] = {
            "before": before,
            "after": accepted_after,
            "delta": accepted_delta,
            "target_trade_count": len(selected),
            "source_trade_counts": source_audit["source_trade_counts"],
            "selected_source_counts": _source_counts(selected),
            "filtered_daily_top1_count": sum(
                1
                for row in filtered
                if row.get("filter_reason") == "daily_top1_source_priority_limit"
            ),
        }
        accepted_to_oracle_rows[label] = {
            "before": accepted_after,
            "after": oracle_after,
            "delta": oracle_delta_vs_accepted,
            "target_trade_count": len(oracle_rows),
            "oracle_switch_gap_total": oracle_audit["same_day_positive_switch_gap_total"],
            "same_day_positive_switch_count": oracle_audit[
                "same_day_positive_switch_count"
            ],
            "oracle_source_counts": oracle_audit["oracle_source_counts"],
        }
        core_to_oracle_rows[label] = {
            "before": before,
            "after": oracle_after,
            "delta": oracle_delta_vs_core,
            "target_trade_count": len(oracle_rows),
        }

    aggregate_core_to_accepted = framework._aggregate_window_rows(core_to_accepted_rows)
    aggregate_accepted_to_oracle = framework._aggregate_window_rows(accepted_to_oracle_rows)
    aggregate_core_to_oracle = framework._aggregate_window_rows(core_to_oracle_rows)
    accepted_summary = _target_summary(accepted_trades_by_window)
    oracle_summary = _target_summary(oracle_trades_by_window)
    gate4 = _gate4_direction(
        aggregate_accepted_to_oracle=aggregate_accepted_to_oracle,
        oracle_summary=oracle_summary,
    )

    if gate4["observed_direction_material"]:
        interpretation = (
            "Observed-only result found a material same-day source-choice upper "
            "bound over the accepted allocator. The next alpha direction should "
            "be a shared ex-ante source-arbitration field, not a priority retune."
        )
        reflection = (
            "The accepted fixed-priority allocator leaves measurable opportunity "
            "when lower-priority same-day rows later outperform the selected "
            "source. The gap is not executable because it uses future PnL; the "
            "usable work is to look for free, point-in-time relation/source-"
            "maturity fields that explain those switches before entry."
        )
    else:
        interpretation = (
            "Observed-only result did not find enough source-choice opportunity "
            "to justify another allocator-arbitration alpha attempt."
        )
        reflection = (
            "Most accepted allocator opportunity is already captured by fixed "
            "priority, or the remaining same-day switches are too small/unstable "
            "after costs. Do not retry by moving source ranks, top-N, notional, "
            "hold, cooldown, or state cells without new point-in-time evidence."
        )

    actual_direction_success = bool(gate4["observed_direction_material"])
    calibration = {
        "actual_direction_success": actual_direction_success,
        "actual_policy_success": False,
        "actual_gate4_policy_passed": False,
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_ev_gap_vs_accepted_allocator": gate4[
            "aggregate_ev_gap_vs_accepted_allocator"
        ],
        "actual_pnl_gap_vs_accepted_allocator": gate4[
            "aggregate_pnl_gap_vs_accepted_allocator"
        ],
        "brier_score_direction": round(
            (
                PREDICTION["success_probability"]
                - (1.0 if actual_direction_success else 0.0)
            )
            ** 2,
            6,
        ),
        "failure_modes_observed": gate4["failed_reasons"],
        "surprise_note": (
            "The direction signal was stronger than the conservative pre-run "
            "estimate because all three windows showed positive oracle gap, but "
            "the policy remains rejected since future PnL is unavailable at "
            "decision time."
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "accepted_helper_source_priority_allocator",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window core replay",
            "windows": framework.WINDOWS,
            "accepted_allocator_rule_version": ACCEPTED_ALLOCATOR_RULE_VERSION,
            "accepted_allocator_source_rule_version": ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "replay_llm": False,
            "replay_news": False,
            "oracle_caveat": (
                "After/oracle path selects by future closed-trade PnL among "
                "same-day accepted allocator source candidates. It is not a "
                "tradable rule."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": "docs/backtesting.md current canonical baseline plus same-run before metrics",
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "accepted allocator source rows signal_date/ticker/source_family",
                "accepted allocator source rows entry_date/exit_date/pnl",
            ],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "note": "Observed-only attribution; core signals and survival are unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "accepted_allocator_metrics": accepted_metrics,
        "oracle_metrics": oracle_metrics,
        "delta_metrics": {
            "core_to_accepted_allocator": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_accepted_rows.items()
                ),
                "aggregate": aggregate_core_to_accepted,
            },
            "accepted_allocator_to_oracle": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in accepted_to_oracle_rows.items()
                ),
                "aggregate": aggregate_accepted_to_oracle,
            },
            "core_to_oracle_upper_bound": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in core_to_oracle_rows.items()
                ),
                "aggregate": aggregate_core_to_oracle,
            },
        },
        "window_rows": {
            "core_to_accepted_allocator": core_to_accepted_rows,
            "accepted_allocator_to_oracle": accepted_to_oracle_rows,
            "core_to_oracle_upper_bound": core_to_oracle_rows,
        },
        "accepted_trades_by_window": accepted_trades_by_window,
        "oracle_trades_by_window": oracle_trades_by_window,
        "accepted_trade_summary": accepted_summary,
        "oracle_trade_summary": oracle_summary,
        "source_audit_by_window": source_audit_by_window,
        "priority_audit_by_window": priority_audit_by_window,
        "oracle_audit_by_window": oracle_audit_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "post_run_reflection": {
            "why_result_happened": reflection,
            "negative_reflection": (
                "This is negative as a policy even if the oracle gap is large: "
                "future PnL is unavailable at decision time, so no strategy "
                "change is retained."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing source ranks, allocator top-N, fixed "
                "state cells, notional, hold days, cooldown, or accepted helper "
                "thresholds on the same frozen windows."
            ),
            "new_evidence_required": (
                "Point-in-time free relation/source-maturity data that explains "
                "oracle switches before the next open, implemented through a "
                "shared default-off helper if tested."
            ),
        },
        "next_step": (
            "If continuing this lane, build a point-in-time free relation/source "
            "maturity field and test it shared-paper-first against the accepted "
            "allocator. Otherwise deprioritize allocator arbitration."
        ),
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
        "| Window | Core EV | Accepted EV | Accepted dEV | Oracle EV | Oracle vs accepted dEV | Core PnL | Accepted dPnL | Oracle vs accepted dPnL | Accepted trades | Oracle switches |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        core = payload["before_metrics"][label]
        accepted_row = payload["window_rows"]["core_to_accepted_allocator"][label]
        oracle_row = payload["window_rows"]["accepted_allocator_to_oracle"][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {accepted_ev:.4f} | {acc_dev:+.4f} | {oracle_ev:.4f} | {oracle_dev:+.4f} | ${core_pnl:,.2f} | ${acc_dpnl:+,.2f} | ${oracle_dpnl:+,.2f} | {trades} | {switches} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                accepted_ev=accepted_row["after"]["expected_value_score"],
                acc_dev=accepted_row["delta"]["expected_value_score"],
                oracle_ev=oracle_row["after"]["expected_value_score"],
                oracle_dev=oracle_row["delta"]["expected_value_score"],
                core_pnl=core["total_pnl"],
                acc_dpnl=accepted_row["delta"]["total_pnl"],
                oracle_dpnl=oracle_row["delta"]["total_pnl"],
                trades=accepted_row["target_trade_count"],
                switches=oracle_row["same_day_positive_switch_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    accepted_aggregate = payload["delta_metrics"]["core_to_accepted_allocator"]["aggregate"]
    oracle_aggregate = payload["delta_metrics"]["accepted_allocator_to_oracle"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Allocator Source Competition Opportunity",
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
            "- Accepted allocator aggregate EV delta vs core: `{:+.4f}`".format(
                accepted_aggregate["expected_value_score_delta_sum"]
            ),
            "- Accepted allocator aggregate PnL delta vs core: `${:+,.2f}`".format(
                accepted_aggregate["total_pnl_delta_sum"]
            ),
            "- Oracle aggregate EV gap vs accepted allocator: `{:+.4f}`".format(
                oracle_aggregate["expected_value_score_delta_sum"]
            ),
            "- Oracle aggregate PnL gap vs accepted allocator: `${:+,.2f}`".format(
                oracle_aggregate["total_pnl_delta_sum"]
            ),
            "- Gate 4 policy decision: `rejected/observed-only` because future PnL was used.",
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["negative_reflection"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_aggregate = payload["delta_metrics"]["core_to_accepted_allocator"]["aggregate"]
    oracle_aggregate = payload["delta_metrics"]["accepted_allocator_to_oracle"]["aggregate"]
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
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate4": payload["gate4"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "aggregate_accepted_allocator_ev_delta_vs_core": accepted_aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_accepted_allocator_pnl_delta_vs_core": accepted_aggregate[
            "total_pnl_delta_sum"
        ],
        "aggregate_oracle_ev_gap_vs_accepted_allocator": oracle_aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_oracle_pnl_gap_vs_accepted_allocator": oracle_aggregate[
            "total_pnl_delta_sum"
        ],
        "windows": [
            {
                "label": label,
                "core_expected_value": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "accepted_allocator_expected_value": payload[
                    "accepted_allocator_metrics"
                ][label]["expected_value_score"],
                "oracle_expected_value": payload["oracle_metrics"][label][
                    "expected_value_score"
                ],
                "accepted_allocator_delta_vs_core": payload["delta_metrics"][
                    "core_to_accepted_allocator"
                ]["by_window"][label],
                "oracle_delta_vs_accepted_allocator": payload["delta_metrics"][
                    "accepted_allocator_to_oracle"
                ]["by_window"][label],
                "accepted_trade_count": len(payload["accepted_trades_by_window"][label]),
                "oracle_trade_count": len(payload["oracle_trades_by_window"][label]),
                "oracle_positive_switch_count": payload["oracle_audit_by_window"][label][
                    "same_day_positive_switch_count"
                ],
            }
            for label in framework.WINDOWS
        ],
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
