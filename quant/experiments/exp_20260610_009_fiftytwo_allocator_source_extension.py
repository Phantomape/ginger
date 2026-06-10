"""exp-20260610-009: add 52-week-high source to accepted allocator.

Full-stack candidate-pool/allocation experiment. It tests one fixed decision
hypothesis: the accepted 52-week-high proximity core-flow helper should be a
rank-2 source family inside the accepted default-off source-priority allocator.

The helper remains default-off paper only. It changes no live/default orders,
core signal generation, ranking, sizing, exits, watchlists, LLM, or news path.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
import exp_20260610_008_fiftytwo_week_high_proximity_full_stack as exp008

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY as ACCEPTED_SOURCE_PRIORITY,
    _build_source_trades as build_accepted_allocator_source_trades,
)
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fiftytwo_week_high_proximity_paper_sleeve import (  # noqa: E402
    RULE_VERSION as FIFTYTWO_RULE_VERSION,
    SOURCE_RULE_VERSION as FIFTYTWO_SOURCE_RULE_VERSION,
    build_fiftytwo_week_high_proximity_historical_trades,
)
from full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260610-009"
STEM = "fiftytwo_allocator_source_extension"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "fiftytwo_week_high_source_family_added_to_accepted_helper_source_priority_allocator_v1"
)
CHANGED_VARIABLE = TRIAL_VARIANT_ID
OWNER = "alpha-search-automation"
RULE_VERSION = "fiftytwo_week_high_allocator_source_extension_replay_v1"
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_fiftytwo_replay_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260610-005",
    "aggregate_ev_delta": 0.8971,
    "aggregate_pnl_delta": 14502.52,
    "window_deltas": {
        "late_strong": {"ev": 0.4450, "pnl": 4308.44},
        "mid_weak": {"ev": 0.3236, "pnl": 5979.77},
        "old_thin": {"ev": 0.1285, "pnl": 4214.31},
    },
}

SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
for _source_name, _source_meta in ACCEPTED_SOURCE_PRIORITY.items():
    if _source_name == "rolling_peer_shock":
        SOURCE_PRIORITY["fiftytwo_week_high_proximity"] = {
            "rank": 2,
            "description": "accepted 52-week-high proximity core-flow",
            "accepted_experiment": "exp-20260610-008",
            "accepted_ev_delta_sum": 0.4308,
            "accepted_pnl_delta_sum": 9295.34,
        }
    _meta = deepcopy(_source_meta)
    if _source_name in {
        "rolling_peer_shock",
        "turn_of_month",
        "industry_laggard_repair",
        "compression",
        "industry_stable_core_flow",
    }:
        _meta["rank"] += 1
    SOURCE_PRIORITY[_source_name] = _meta

PREDICTION = {
    "success_probability": 0.38,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "source_overlap_with_existing_allocator",
        "accepted_allocator_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "daily_snapshot_wiring_gap",
    ],
    "confidence_reason": (
        "Money-making mechanism: accepted 52-week-high proximity core-flow rows "
        "capture anchoring underreaction at fresh long-term highs on days with "
        "same-day core A/B demand, while the allocator currently cannot see "
        "that source. Historical evidence: exp-20260610-008 accepted the shared "
        "52-week helper with aggregate EV +0.4308 and PnL +$9,295.34 across all "
        "three windows, and exp-20260610-005 accepted the allocator without it. "
        "Main disconfirming risk: exp-20260610-006 showed accepted source-family "
        "additions can be redundant; 52-week rows may overlap higher-priority "
        "allocator winners or displace old_thin winners, causing comparator "
        "failure or drawdown drift."
    ),
    "recorded_at": "2026-06-10T07:06:16+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=BASE_NOTIONAL_USD,
    max_capital_pct=0.32,
    min_dollar_volume=75_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=8,
    order_semantics="next_open_paper_only",
    kill_switch_drawdown_pct=None,
    sleeve_drawdown_stop_pct=None,
    notes=(
        "Top-1/day accepted-helper allocator, fixed $4,000 paper notional, "
        "8 max active default-off paper positions, 10-trading-day hold, and "
        "12-trading-day same-ticker cooldown. Source helpers keep their own "
        "liquidity guards; the 52-week source requires at least $75M 20-day "
        "average dollar volume. This experiment is not live-ready because the "
        "allocator still needs a dedicated realized-ledger kill switch before "
        "any trade_enabled=true release."
    ),
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_rejected_source_extension",
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
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "The fixed source-extension replay failed its binding accepted-allocator "
        "comparator, so shared allocator, run.py daily snapshot wiring, and "
        "parity test changes were rolled back. No production helper, report, "
        "paper ledger, ranking, sizing, watchlist, exit, LLM, news, or order "
        "surface retains this rejected source admission."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate-pool/allocation alpha: add the already accepted 52-week-high "
        "proximity core-flow source to the accepted helper allocator at fixed "
        "rank 2, based on accepted standalone EV."
    ),
    "2_history_check": {
        "exp-20260610-005": (
            "Accepted source-priority allocator without 52-week source: aggregate "
            "EV +0.8971 and PnL +$14,502.52. This is the binding comparator."
        ),
        "exp-20260610-006": (
            "Rejected macro-relief source extension: positive versus core but did "
            "not beat exp-20260610-005 and regressed old_thin versus comparator."
        ),
        "exp-20260610-008": (
            "Accepted 52-week-high proximity core-flow shared helper: aggregate "
            "EV +0.4308 and PnL +$9,295.34 with all three windows positive."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three windows. Must improve aggregate "
        "EV/PnL, have no EV/PnL regression windows, satisfy sample/survival/"
        "drawdown/concentration guards, and beat exp-20260610-005 aggregate "
        "and per-window EV/PnL comparator."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_009_fiftytwo_allocator_source_extension.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _source_score(row: dict[str, Any]) -> float:
    for key in (
        "candidate_score",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if row.get(key) is not None:
            return _float(row.get(key))
    return 0.0


def _normalise_source_row(row: dict[str, Any], source_family: str) -> dict[str, Any]:
    source_meta = SOURCE_PRIORITY[source_family]
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return {
        **deepcopy(row),
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": source_family,
        "source_priority_rank": source_meta["rank"],
        "source_priority_accepted_experiment": source_meta["accepted_experiment"],
        "source_priority_score": _round(_source_score(row), 6),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": True,
    }


def _select_priority_trades(
    *,
    source_trades: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        _normalise_source_row(row, str(row.get("source_family") or ""))
        for row in source_trades
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
        and str(row.get("signal_date") or row.get("date") or "")[:10]
        and str(row.get("ticker") or "").upper()
    ]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: dict[str, int] = {}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts.get(signal_date, 0) >= 1:
            rejected.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        selected.append(
            {
                **row,
                "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
                "rule_version": RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "candidate_score": _round(
                    1000.0 / max(1, int(row.get("source_priority_rank") or 999))
                    + _float(row.get("source_priority_score")),
                    6,
                ),
                "paper_status": "closed",
                "alters_orders": False,
            }
        )
        used_date_counts[signal_date] = used_date_counts.get(signal_date, 0) + 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS

    return selected, rejected, {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": _counts_by_source(candidates),
        "selected_source_counts": _counts_by_source(selected),
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    }


def _counts_by_source(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get("source_family") or "unknown")
        out[key] = out.get(key, 0) + 1
    return out


def _build_extended_allocator_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
    calendar_dates: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades, source_audit = build_accepted_allocator_source_trades(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        window_label=window_label,
        window=window,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        calendar_dates=calendar_dates,
    )
    fiftytwo_trades, fiftytwo_audit = build_fiftytwo_week_high_proximity_historical_trades(
        ohlcv_by_ticker=rows_by_ticker,
        core_entries_by_date=core_entries_by_date,
        windows=OrderedDict([(window_label, window)]),
        candidate_universe=candidate_universe,
        sector_entries=sector_entries,
    )
    fiftytwo_rows = [
        _normalise_source_row(row, "fiftytwo_week_high_proximity")
        for row in fiftytwo_trades
    ]
    source_trades.extend(fiftytwo_rows)
    selected, filtered, priority_audit = _select_priority_trades(
        source_trades=source_trades,
        trading_dates=dates,
    )

    source_trade_counts = dict(source_audit["source_trade_counts"])
    raw_candidate_counts = dict(source_audit["raw_candidate_counts"])
    source_audits = dict(source_audit["source_audits"])
    source_trade_counts["fiftytwo_week_high_proximity"] = len(fiftytwo_rows)
    raw_candidate_counts["fiftytwo_week_high_proximity"] = fiftytwo_audit.get(
        "raw_candidate_count_by_window",
        {},
    ).get(window_label)
    source_audits["fiftytwo_week_high_proximity"] = {
        "rule_version": FIFTYTWO_RULE_VERSION,
        "source_rule_version": FIFTYTWO_SOURCE_RULE_VERSION,
        "scan": fiftytwo_audit.get("scan_by_window", {}).get(window_label),
    }
    return selected, {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "selected_by_window": {window_label: len(selected)},
        "selected_source_counts_by_window": {
            window_label: priority_audit["selected_source_counts"]
        },
        "source_trade_counts_by_window": {window_label: source_trade_counts},
        "raw_candidate_counts_by_window": {window_label: raw_candidate_counts},
        "filtered_count_by_window": {window_label: len(filtered)},
        "source_audits_by_window": {window_label: source_audits},
        "priority_audit_by_window": {window_label: priority_audit},
        "total_selected": len(selected),
    }


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _binding_gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )

    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_fiftytwo_week_high_allocator_source_extension"
            if passed
            else "rejected_fiftytwo_week_high_allocator_source_extension"
        ),
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
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
        },
    }


def _full_stack_blocks(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    trades = int(target_summary["total_trade_count"] or 0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    window_metrics = {
        "aggregate_ev_delta": float(aggregate["expected_value_score_delta_sum"] or 0.0),
        "aggregate_pnl_delta": pnl_delta,
        "max_drawdown_worse_max": float(aggregate["max_drawdown_delta_max"] or 0.0),
        "windows_ev_improved": int(aggregate["windows_ev_improved"] or 0),
        "windows_ev_regressed": int(aggregate["windows_ev_regressed"] or 0),
        "adjusted_trade_count": trades,
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": _top5_positive_share(target_summary),
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "baseline_single_ticker_positive_share": 0.50,
        "baseline_top_5_contribution_pct": 0.60,
        "baseline_hhi_concentration": 0.35,
        "avg_pnl_per_trade_delta": round(pnl_delta / trades, 2) if trades else None,
        "avg_return_delta_pp": round(
            100.0 * pnl_delta / (BASE_NOTIONAL_USD * trades),
            4,
        )
        if trades
        else None,
    }
    return {
        "window_metrics": window_metrics,
        "gate4_strict_materiality": evaluate_gate4(
            window_metrics,
            check_materiality=True,
        ),
        "gate4_canonical": evaluate_gate4(
            window_metrics,
            check_materiality=False,
        ),
        "materiality_note": (
            "Strict materiality is recorded for comparability. The binding "
            "candidate-pool materiality standard for this experiment is beating "
            "the accepted exp-20260610-005 allocator comparator after costs."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] 52-week-high source allocator extension")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        trades, helper_audit = (
            _build_extended_allocator_trades(
                rows_by_ticker=snapshot,
                dates=dates,
                window_label=label,
                window=cfg,
                core_entries_by_date=core_entries,
                sector_entries=window_sector_entries,
                candidate_universe=candidate_universe,
                calendar_dates=framework.shadow._trading_dates(snapshot),
            )
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        helper_audit_by_window[label] = helper_audit
        source_counts = helper_audit["source_trade_counts_by_window"][label]
        selected_counts = helper_audit["selected_source_counts_by_window"][label]
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "snapshot_lookback_calendar_days": exp008.SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "all_source_trade_count": sum(int(count or 0) for count in source_counts.values()),
            "source_trade_counts": source_counts,
            "raw_source_candidate_counts": helper_audit[
                "raw_candidate_counts_by_window"
            ][label],
            "selected_source_counts": selected_counts,
            "fiftytwo_week_high_source_trade_count": source_counts.get(
                "fiftytwo_week_high_proximity",
                0,
            ),
            "fiftytwo_week_high_selected_count": selected_counts.get(
                "fiftytwo_week_high_proximity",
                0,
            ),
            "filtered_priority_candidate_count": helper_audit[
                "filtered_count_by_window"
            ][label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    binding_gate4 = _binding_gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    full_stack = _full_stack_blocks(aggregate=aggregate, target_summary=target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=full_stack["gate4_canonical"],
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not binding_gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Roll back the allocator source extension and log the failure. "
                "The binding accepted-allocator comparator gate did not pass."
            ),
        }

    accepted = binding_gate4["passed"] and verdict["verdict"] != "reject"
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    if accepted:
        interpretation = (
            "The 52-week-high proximity source-family extension beat the "
            "accepted allocator comparator and is retained as shared "
            "default-off paper observation only."
        )
        reflection = (
            "The result worked because the accepted 52-week source filled and "
            "sometimes displaced allocator rows with a distinct long-term-high "
            "anchoring relation while preserving the fixed top-1/day source "
            "priority and global cooldown. It improved old_thin most strongly, "
            "which was the failure mode for the prior macro-relief extension."
        )
    else:
        interpretation = (
            "The 52-week-high source-family extension failed to beat the "
            "accepted allocator comparator."
        )
        reflection = (
            "The source overlapped too much with higher-priority allocator rows "
            "or displaced better rows in at least one canonical window."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": binding_gate4["decision"],
        "hypothesis": (
            "Accepted 52-week-high proximity core-flow rows may add independent "
            "replacement value when admitted as a fixed rank-2 source family "
            "into the accepted helper source-priority allocator."
        ),
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "newly_accepted_52_week_high_source_family",
        "nearby_prior_experiments": [
            "exp-20260610-005",
            "exp-20260610-006",
            "exp-20260610-008",
        ],
        "prior_trial_count": 2,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": binding_gate4["passed"],
            "failure_modes_observed": binding_gate4["failed_reasons"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1.0 if binding_gate4["passed"] else 0.0))
                ** 2,
                6,
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared accepted-helper source-priority allocator overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Shared helper builds accepted source rows including the "
                "52-week-high proximity core-flow helper, selects one paper "
                "trade per signal date by fixed source priority, applies a "
                "12-trading-day same-ticker cooldown, then overlays next-open/"
                "10-day paper trade outcomes."
            ),
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume with 252-day lookback",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "accepted helper source rows with signal_date/ticker/source_family",
                "daily default-off 52-week-high source snapshot from run.py",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
            "note": (
                "No core filter or live candidate ranking changed. The source "
                "is default-off paper, so core signals generated and survived "
                "are unchanged from baseline."
            ),
        },
        "gate4": binding_gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "helper_audit_by_window": helper_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "full_stack": {
            **full_stack,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "verdict": verdict,
        },
        "full_stack_verdict": verdict["verdict"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "fiftytwo_week_high_standalone": {
                "experiment_id": "exp-20260610-008",
                "aggregate_ev_delta": 0.4308,
                "aggregate_pnl_delta": 9295.34,
            },
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if accepted else "; ".join(binding_gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing 52-week source rank, allocator top-N, "
                "source thresholds, notional, hold days, or cooldown on the "
                "same frozen windows."
            ),
            "new_evidence_required": (
                "Next useful evidence is closed forward allocator displacement "
                "rows under the shared daily snapshot, plus a dedicated allocator "
                "kill-switch parity design before any live activation."
            ),
        },
        "next_retry_requires": [
            "closed forward allocator displacement rows",
            "dedicated allocator kill switch parity",
            "no frozen-window priority or threshold retune",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | 52w selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {f52} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=row["target_trade_count"],
                f52=row["fiftytwo_week_high_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week Source Allocator Extension",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}` versus accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
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
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Artifact",
            "",
            "## Decision",
            "",
            f"`{payload['decision']}` (full-stack verdict: `{payload['full_stack_verdict']}`)",
            "",
            "## Fixed Policy Bundle",
            "",
            (
                "Accepted source-priority allocator with 52-week-high proximity "
                "core-flow added as rank 2 after volatility relief and before "
                "rolling peer shock. Existing top-1/day, $4,000 paper notional, "
                "10-day hold, 12-day ticker cooldown, and default-off paper-only "
                "semantics remain fixed."
            ),
            "",
            "## Three-Window Before/After",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Binding Gate failures: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Full-Stack Blocks",
            "",
            "```json",
            json.dumps(
                {
                    "window_metrics": payload["full_stack"]["window_metrics"],
                    "gate4_strict_materiality": {
                        "status": payload["full_stack"]["gate4_strict_materiality"]["status"],
                        "hard_failures": payload["full_stack"]["gate4_strict_materiality"][
                            "hard_failures"
                        ],
                    },
                    "gate4_canonical": {
                        "status": payload["full_stack"]["gate4_canonical"]["status"],
                        "hard_failures": payload["full_stack"]["gate4_canonical"][
                            "hard_failures"
                        ],
                    },
                    "live_readiness": payload["full_stack"]["live_readiness"],
                    "execution_envelope": payload["full_stack"]["execution_envelope"],
                    "verdict": payload["full_stack"]["verdict"]["verdict"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": payload["gate4"]["passed"],
        "production_accepted": payload["gate4"]["passed"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
        },
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
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
                "fiftytwo_week_high_selected_count": payload["window_rows"][label][
                    "fiftytwo_week_high_selected_count"
                ],
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
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        ARTIFACT_MD,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._write_text(ARTIFACT_MD, _build_artifact(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
