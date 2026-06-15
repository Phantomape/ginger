"""exp-20260615-009: SEC 13F low-crowding leadership filter.

Replay-only alpha search. This tests one fixed crowding-context hypothesis:
among the already PIT 13F sponsorship-acceleration liquid-leadership paper
candidates from exp-20260613-014, keep only the lower-crowding names in each
canonical window. The filter is fixed before the run: holder count at or below
the window median and total reported 13F value at or below the window 75th
percentile.

This is deliberately artifact-limited because historical SEC 13F raw filings
are not locally cached. A positive result would only be a lead until a shared
daily/default-off helper recomputes the same PIT 13F feature and paper ledger
from raw source data. No production code, live/default orders, sizing, ranking,
exits, watchlist behavior, LLM/news path, or shared adapter is changed.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260615-009"
STEM = "sec13f_low_crowding_leadership"
TRIAL_FAMILY = "sec13f_crowding_context_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_low_crowding_filter_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_low_crowding_filter_on_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SOURCE_EXPERIMENT_ID = "exp-20260613-014"
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260613_014_sec13f_sponsorship_acceleration.json"
)
BASELINE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 20

HOLDER_COUNT_MAX_QUANTILE = 0.50
TOTAL_VALUE_MAX_QUANTILE = 0.75
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "filtered_sample_is_only_loss_avoidance",
        "underownership_is_quality_trap",
        "stale_quarterly_data",
        "window_regression",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Direct 13F sponsorship and new-holder accumulation failed, but the "
        "playbook still allows 13F as crowding context. This test asks whether "
        "lower crowding among PIT liquid 13F leaders improves replacement "
        "quality. It is artifact-limited, so confidence is low."
    ),
    "recorded_at": "2026-06-15T08:09:05+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "implementation_mode": "artifact_limited_private_replay_scout",
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
    "uses_free_sec_13f": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "private_replay_scout_escape_reason": (
        "The raw historical SEC 13F candidate universe is not locally cached; "
        "this run filters the realized exp-20260613-014 paper candidates only. "
        "A positive result would need a shared helper that recomputes PIT 13F "
        "crowding fields and the same paper ledger from raw source data."
    ),
    "execution_envelope": {
        "trade_enabled": False,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing source trade, threshold field, or baseline replay rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. Even if numeric Gate 4 "
        "passed, it would remain a replay lead until a shared default-off "
        "helper computes the same PIT 13F low-crowding thresholds, leadership "
        "source, core-overlap handling, next-open entry, 10-day exit, costs, "
        "cooldown, and ledger fields in both historical replay and daily "
        "snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: among PIT SEC 13F sponsorship-acceleration liquid "
        "leaders, the less institutionally crowded names may avoid crowded "
        "unwind risk while retaining enough price leadership to add replacement "
        "value."
    ),
    "2_history_check": {
        "exp-20260613-014": (
            "Rejected direct 13F holder/value sponsorship acceleration: late "
            "and mid improved, but old_thin regressed and drawdown drift was "
            "too high."
        ),
        "exp-20260613-017": (
            "Rejected true new-holder initiation: aggregate EV/PnL were not "
            "positive and late/old windows regressed."
        ),
        "exp-20260612-015/016": (
            "Rejected direct 13D/13G filing-date event triggers, showing stale "
            "institutional-event data is weak as a standalone entry."
        ),
        "difference": (
            "This is not another direct accumulation trigger or threshold sweep. "
            "It tests a fixed under-ownership/crowding-risk context filter on "
            "the already PIT liquid-leadership candidate source."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical late_strong, mid_weak, and old_thin "
        "windows. Aggregate EV/PnL must improve, no window EV/PnL regression is "
        "allowed, at least 20 paper trades must span all 3 windows, survival "
        "must remain >=5%, drawdown drift must be <=0.5pp, and target "
        "concentration must pass. A positive result is lead-only until shared "
        "daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_009_sec13f_low_crowding_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute quantile of empty list")
    index = int((len(ordered) - 1) * q)
    return ordered[index]


def _load_source_payload() -> dict[str, Any]:
    if not SOURCE_ARTIFACT.exists():
        raise FileNotFoundError(f"missing source artifact: {SOURCE_ARTIFACT}")
    return json.loads(SOURCE_ARTIFACT.read_text(encoding="utf-8"))


def _thresholds(trades: list[dict[str, Any]]) -> dict[str, float]:
    holder_counts = [
        value
        for value in (_float(trade.get("sec13f_holder_count")) for trade in trades)
        if value is not None
    ]
    total_values = [
        value
        for value in (_float(trade.get("sec13f_total_value_usd")) for trade in trades)
        if value is not None
    ]
    if not holder_counts or not total_values:
        raise ValueError("source trades missing SEC 13F crowding fields")
    return {
        "holder_count_median": round(float(median(holder_counts)), 6),
        "total_value_q75_usd": round(_quantile(total_values, TOTAL_VALUE_MAX_QUANTILE), 2),
    }


def _select_low_crowding_trades(
    source_trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    limits = _thresholds(source_trades)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for trade in source_trades:
        holder_count = _float(trade.get("sec13f_holder_count"))
        total_value = _float(trade.get("sec13f_total_value_usd"))
        enriched = {
            **trade,
            "source": "SEC13F_LOW_CROWDING_LEADERSHIP_PAPER",
            "rule_version": RULE_VERSION,
            "crowding_filter_rule": (
                "holder_count <= window median and total 13F value <= window q75"
            ),
            "crowding_holder_count_median": limits["holder_count_median"],
            "crowding_total_value_q75_usd": limits["total_value_q75_usd"],
            "trade_enabled": False,
            "uses_llm": False,
        }
        if holder_count is None or total_value is None:
            filtered.append({**enriched, "filter_reason": "missing_crowding_field"})
            continue
        if holder_count > limits["holder_count_median"]:
            filtered.append({**enriched, "filter_reason": "holder_count_above_median"})
            continue
        if total_value > limits["total_value_q75_usd"]:
            filtered.append({**enriched, "filter_reason": "total_13f_value_above_q75"})
            continue
        selected.append(enriched)
    selected.sort(key=lambda row: (str(row.get("signal_date") or row.get("date")), str(row.get("ticker") or "")))
    return selected, filtered, limits


def _configure_framework_globals() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    framework.sleeve.STEM = STEM
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    passed = not failed
    gate.update(
        {
            "passed": passed,
            "decision": (
                "positive_artifact_replay_lead_not_promoted_sec13f_low_crowding"
                if passed
                else "rejected_sec13f_low_crowding_leadership_filter"
            ),
            "failed_reasons": failed,
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework_globals()
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = _load_source_payload()
    source_trades_by_window = source_payload.get("target_trades_by_window") or {}
    universe = sorted(get_universe())

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    threshold_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and SEC 13F low-crowding overlay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        source_trades = list(source_trades_by_window.get(label) or [])
        selected_trades, filtered_trades, thresholds = _select_low_crowding_trades(
            source_trades
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_trades_by_window[label] = filtered_trades[:200]
        threshold_by_window[label] = thresholds
        context_scan_by_window[label] = {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_trade_count": len(source_trades),
            "selected_low_crowding_trade_count": len(selected_trades),
            "filtered_trade_count": len(filtered_trades),
            "holder_count_max_quantile": HOLDER_COUNT_MAX_QUANTILE,
            "total_value_max_quantile": TOTAL_VALUE_MAX_QUANTILE,
            "artifact_limited": True,
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "source_trade_count": len(source_trades),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    passed = bool(gate4["passed"])
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
    }
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    why = (
        "The fixed low-crowding 13F context filter cleared numeric Gate 4, "
        "but it is not accepted alpha because this run is artifact-limited and "
        "has no shared daily/default-off parity surface."
        if passed
        else (
            "The low-crowding filter did not repair direct 13F sponsorship. "
            "It removed some crowded winners as well as crowded losers, leaving "
            "old_thin still negative. Under-ownership appears closer to stale "
            "institutional neglect or smaller-name fragility than to a durable "
            "crowded-unwind risk reducer in this sample."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "experiment_local_replay_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_13f_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260613-014",
            "exp-20260613-017",
            "exp-20260614-018",
            "exp-20260612-015",
            "exp-20260612-016",
        ],
        "prior_trial_count": 5,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pit_sec_13f_crowding_context_filter",
        "prediction": {
            **PREDICTION,
            "actual_success": 1 if passed else 0,
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "brier_score": calibration["brier_score"],
        },
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "artifact-limited SEC 13F low-crowding paper overlay"
            ),
            "windows": framework.WINDOWS,
            "baseline_artifact": _repo_rel(BASELINE_ARTIFACT),
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Reuses exp-20260613-014 PIT 13F leadership paper trades, "
                "then applies fixed window-relative low-crowding thresholds. "
                "Paper entry/exit prices and costs remain those recorded in "
                "the source ledger; after-metrics are recomputed through the "
                "standard overlay against the freshly replayed baseline."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "holder_count_max_quantile": HOLDER_COUNT_MAX_QUANTILE,
            "total_value_max_quantile": TOTAL_VALUE_MAX_QUANTILE,
            "single_causal_variable": CHANGED_VARIABLE,
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
        },
        "gate_questions": PRE_RUN_QUESTIONS,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "canonical_baseline_artifact": _repo_rel(BASELINE_ARTIFACT),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "exp-20260613-014 target_trades_by_window entry_date",
                "exp-20260613-014 target_trades_by_window sec13f_holder_count",
                "exp-20260613-014 target_trades_by_window sec13f_total_value_usd",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core entry filter is added. The low-crowding source is "
                "additive default-off paper; core signals and survival are "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "source_candidate_summary_by_window": context_scan_by_window,
        "crowding_thresholds_by_window": threshold_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_trades_sample_by_window": filtered_trades_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The SEC 13F low-crowding leadership filter cleared numeric Gate 4 "
            "but remains an artifact-limited replay lead only."
            if passed
            else (
                "The SEC 13F low-crowding leadership filter was rejected under "
                "the standard three-window protocol."
            )
        ),
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "Do not retry by sweeping holder/value quantiles on the same "
            "artifact. A credible 13F retry needs raw historical candidate "
            "rows from a shared helper, manager-quality segmentation, "
            "sector-relative underownership surprise, or closed forward rows "
            "from a daily default-off 13F context adapter."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry median/q75, top-N, cooldown, hold-day, notional, "
                "ADV, or close-location sweeps on the same exp-20260613-014 "
                "artifact-limited 13F sponsorship surface."
            ),
            "new_evidence_required": (
                "Raw PIT 13F candidate rows, manager identity/quality, "
                "sector-relative crowding surprise, or daily default-off "
                "forward observations."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_metric_row(payload: dict[str, Any], label: str) -> str:
    before = payload["before_metrics"][label]
    after = payload["after_metrics"][label]
    delta = payload["delta_metrics"]["by_window"][label]
    scan = payload["source_candidate_summary_by_window"][label]
    thresholds = payload["crowding_thresholds_by_window"][label]
    return (
        "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
        "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
        "{source} | {selected} | {holder:.1f} | ${value:,.0f} |"
    ).format(
        label=label,
        bev=float(before.get("expected_value_score") or 0.0),
        aev=float(after.get("expected_value_score") or 0.0),
        dev=float(delta.get("expected_value_score") or 0.0),
        bpnl=float(before.get("total_pnl") or 0.0),
        apnl=float(after.get("total_pnl") or 0.0),
        dpnl=float(delta.get("total_pnl") or 0.0),
        dd=float(delta.get("max_drawdown_pct") or 0.0),
        source=scan["source_trade_count"],
        selected=scan["selected_low_crowding_trade_count"],
        holder=float(thresholds["holder_count_median"]),
        value=float(thresholds["total_value_q75_usd"]),
    )


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Source trades | Kept | Holder median | Value q75 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        rows.append(_window_metric_row(payload, label))
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13F Low-Crowding Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
        "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": f"{_repo_rel(OUT_JSON)}#before_metrics",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "source_trade_count": payload["source_candidate_summary_by_window"][label][
                    "source_trade_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": None
        if payload["gate4"]["passed"]
        else payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
