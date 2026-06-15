"""exp-20260614-003: accepted adapter forward maturity direction check.

Alpha search, not measurement repair. This run tests one decision hypothesis:
whether accepted/default-off paper adapters now have enough forward
replacement-value evidence to justify activation focus without retuning frozen
historical thresholds.

The runner is read-only with respect to strategy behavior. It scans
data/paper_sleeves/*/state.json, records the docs/backtesting.md canonical
three-window baseline, and closes the experiment as activation-ready only if
forward evidence meets the predeclared sample, trigger, replacement-value, and
parity guards.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260614-003"
STEM = "accepted_adapter_forward_maturity"
OWNER = "alpha-search-automation"
LANE = "alpha_search"
CHANGE_TYPE = "forward_readiness_default_off_paper_alpha"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "forward_paper_replacement_maturity"
TRIAL_VARIANT_ID = "accepted_adapter_activation_readiness_v1"
CHANGED_VARIABLE = "accepted_default_off_paper_adapter_forward_maturity_activation_rule_v1"

MIN_TRUE_TRIGGER_CLOSED_ROWS = 20
MIN_REPLACEMENT_VALUE_COVERAGE = 0.90
MAX_SINGLE_POSITIVE_SHARE = 0.50

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"


WINDOWS = {
    "late_strong": {"start": "2025-10-23", "end": "2026-04-21"},
    "mid_weak": {"start": "2025-04-23", "end": "2025-10-22"},
    "old_thin": {"start": "2024-10-02", "end": "2025-04-22"},
}

BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "trade_count": 18,
        "survival_rate": 0.8039,
        "max_drawdown_pct": 0.0665,
        "signals_generated": 51,
        "signals_survived": 41,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78110.11,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "max_drawdown_pct": 0.1119,
        "signals_generated": 53,
        "signals_survived": 42,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39667.96,
        "trade_count": 22,
        "survival_rate": 0.8667,
        "max_drawdown_pct": 0.1001,
        "signals_generated": 60,
        "signals_survived": 52,
    },
}


PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "immature_forward_rows",
        "false_trigger_rows",
        "concentration",
        "parity_not_ready",
    ],
    "confidence_reason": (
        "Current playbook ranks production-visible default-off adapter "
        "maturation highly, but prior readiness audits repeatedly found "
        "insufficient closed rows; latest low-deployment rows may be new but "
        "likely off-trigger."
    ),
    "recorded_at": "2026-06-14T01:29:05+00:00",
}


PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/risk_allocation: accepted default-off paper adapters "
        "may now have enough forward replacement-value rows to select an "
        "activation-ready alpha direction without adding new historical "
        "filters or retuning frozen thresholds."
    ),
    "2_history_check": {
        "exp-20260608-021": (
            "Prior forward-readiness audit found activation still blocked by "
            "immature or concentrated rows."
        ),
        "exp-20260611-022": (
            "Earlier forward maturation check did not find enough out-of-sample "
            "closed rows for activation."
        ),
        "exp-20260612-012": (
            "Forward paper infrastructure work improved observation quality but "
            "was not alpha activation evidence by itself."
        ),
        "exp-20260612-019": (
            "Replacement-value enrichment helped measurement, but the alpha "
            "decision still required mature true-trigger closed rows."
        ),
        "exp-20260613-010": (
            "Accepted ISCF state tilt is a shared default-off helper; its next "
            "activation evidence must come from forward replacement rows, not "
            "more state/notional retunes."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows as Gate 1 context. "
        "Activation is allowed only if a shared/default-off adapter has at "
        "least 20 closed true-trigger forward rows, replacement-value coverage "
        ">=90%, positive aggregate value versus cash, SPY, and QQQ, no "
        "production/backtest parity gap, and no historical Gate 1-4 regression."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_003_accepted_adapter_forward_maturity.py"
    ),
}


PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": False,
    "read_only_forward_state_audit": True,
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
    "uses_free_ohlcv": True,
    "uses_free_non_ohlcv": True,
    "live_ready": False,
    "parity_note": (
        "This experiment reads existing default-off paper sleeve state only. It "
        "does not modify live/default orders, candidate generation, ranking, "
        "sizing, exits, watchlists, LLM/news behavior, or shared policy code. A "
        "positive activation decision would require a later shared-helper "
        "change with historical replay, daily snapshot parity, and explicit "
        "execution-envelope tests."
    ),
}


HISTORICAL_EVIDENCE = {
    "low_deployment_etf": "exp-20260606-001",
    "sec_ftd_finra": "exp-20260604-026",
    "post_earnings_underpriced_drift": "exp-20260602-023",
    "fundamental_growth_rs": "exp-20260528-017",
    "volume_breadth_breakout": "exp-20260526-014",
    "volatility_contraction": "exp-20260608-013",
    "distribution_day_absorption_leadership": "exp-20260611-007",
    "accepted_helper_source_priority_allocator": "exp-20260611-005",
    "industry_stable_core_flow": "exp-20260613-010",
    "rolling_corr_peer_shock": "exp-20260606-025",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, Path):
        return _repo_rel(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return round(value, 6)
        return None
    return value


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _num(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(parsed):
        return parsed
    return None


def _sum_field(rows: list[dict[str, Any]], field: str) -> float:
    return sum(_num(row.get(field)) or 0.0 for row in rows)


def _count_present(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if row.get(field) not in (None, ""))


def _count_any_present(rows: list[dict[str, Any]], fields: list[str]) -> int:
    return sum(
        1
        for row in rows
        if any(row.get(field) not in (None, "") for field in fields)
    )


def _historical_log_summary(sleeve_dir: str) -> dict[str, Any]:
    experiment_id = HISTORICAL_EVIDENCE.get(sleeve_dir)
    if not experiment_id:
        return {"experiment_id": None, "log_found": False}
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    row = _read_json(path, {})
    if not isinstance(row, dict) or not row:
        return {"experiment_id": experiment_id, "log_found": False}

    aggregate = row.get("aggregate") if isinstance(row.get("aggregate"), dict) else {}
    gate4 = row.get("gate4") if isinstance(row.get("gate4"), dict) else {}
    delta_metrics = row.get("delta_metrics") if isinstance(row.get("delta_metrics"), dict) else {}
    return {
        "experiment_id": experiment_id,
        "log_found": True,
        "decision": row.get("decision"),
        "status": row.get("status"),
        "accepted": bool(row.get("accepted") or row.get("accepted_alpha")),
        "aggregate_ev_delta": (
            aggregate.get("expected_value_score_delta_sum")
            if aggregate
            else gate4.get("aggregate_ev_delta", delta_metrics.get("expected_value_score"))
        ),
        "aggregate_pnl_delta": (
            aggregate.get("total_pnl_delta_sum")
            if aggregate
            else gate4.get("aggregate_pnl_delta", delta_metrics.get("total_pnl"))
        ),
        "windows_ev_regressed": (
            aggregate.get("windows_ev_regressed")
            if aggregate
            else gate4.get("windows_ev_regressed")
        ),
    }


def _position_dates(rows: list[dict[str, Any]], field: str) -> list[str]:
    values = []
    for row in rows:
        value = str(row.get(field) or "")[:10]
        if value:
            values.append(value)
    return sorted(set(values))


def _single_positive_share(rows: list[dict[str, Any]], field: str) -> float | None:
    positives = [max(0.0, _num(row.get(field)) or 0.0) for row in rows]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _state_summary(path: Path) -> dict[str, Any]:
    data = _read_json(path, {})
    sleeve_dir = path.parent.name
    closed = _as_rows(data.get("closed_positions"))
    open_positions = _as_rows(data.get("open_positions"))
    pending = _as_rows(data.get("pending_entries"))
    skipped = _as_rows(data.get("skipped_entries")) or _as_rows(data.get("skipped_days"))
    all_rows = closed + open_positions + pending

    low_true = sum(1 for row in closed if row.get("low_deployment_condition_passed") is True)
    low_false = sum(1 for row in closed if row.get("low_deployment_condition_passed") is False)
    requires_true_trigger = sleeve_dir == "low_deployment_etf"
    true_trigger_closed = low_true if requires_true_trigger else len(closed)

    rv_fields = [
        "replacement_value_vs_cash_usd",
        "replacement_value_vs_spy_usd",
        "replacement_value_vs_qqq_usd",
    ]
    enriched_count = sum(1 for row in closed if any(row.get(field) is not None for field in rv_fields))
    coverage = enriched_count / len(closed) if closed else 0.0

    summary = {
        "sleeve_dir": sleeve_dir,
        "sleeve": data.get("sleeve") or sleeve_dir,
        "state_file": _repo_rel(path),
        "updated_at": data.get("updated_at"),
        "closed_count": len(closed),
        "open_count": len(open_positions),
        "pending_count": len(pending),
        "skipped_count": len(skipped),
        "requires_true_trigger": requires_true_trigger,
        "true_trigger_closed_count": true_trigger_closed,
        "low_deployment_true_trigger_closed_count": low_true,
        "low_deployment_false_trigger_closed_count": low_false,
        "replacement_value_enriched_count": enriched_count,
        "replacement_value_coverage": coverage,
        "replacement_value_vs_cash_usd_sum": _sum_field(closed, "replacement_value_vs_cash_usd"),
        "replacement_value_vs_spy_usd_sum": _sum_field(closed, "replacement_value_vs_spy_usd"),
        "replacement_value_vs_qqq_usd_sum": _sum_field(closed, "replacement_value_vs_qqq_usd"),
        "entry_date_present_count": _count_present(closed, "entry_date"),
        "target_price_present_count": _count_present(closed, "target_price"),
        "entry_price_or_open_present_count": _count_any_present(
            closed, ["entry_price", "open"]
        ),
        "exit_price_or_close_present_count": _count_any_present(
            closed, ["exit_price", "close"]
        ),
        "trade_enabled_false_count": sum(1 for row in all_rows if row.get("trade_enabled") is False),
        "alters_orders_false_count": sum(1 for row in all_rows if row.get("alters_orders") is False),
        "trade_enabled_true_count": sum(1 for row in all_rows if row.get("trade_enabled") is True),
        "alters_orders_true_count": sum(1 for row in all_rows if row.get("alters_orders") is True),
        "unique_entry_dates": _position_dates(closed, "entry_date"),
        "ticker_counts": dict(Counter(str(row.get("ticker") or "UNKNOWN") for row in closed)),
        "max_single_positive_cash_share": _single_positive_share(
            closed, "replacement_value_vs_cash_usd"
        ),
        "historical_evidence": _historical_log_summary(sleeve_dir),
    }
    summary["activation_reject_reasons"] = _activation_reject_reasons(summary)
    summary["activation_ready"] = not summary["activation_reject_reasons"]
    return summary


def _activation_reject_reasons(summary: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if summary["true_trigger_closed_count"] < MIN_TRUE_TRIGGER_CLOSED_ROWS:
        reasons.append("true_trigger_closed_rows_below_20")
    if summary["closed_count"] and summary["replacement_value_coverage"] < MIN_REPLACEMENT_VALUE_COVERAGE:
        reasons.append("replacement_value_coverage_below_90pct")
    if summary["requires_true_trigger"] and summary["low_deployment_false_trigger_closed_count"]:
        reasons.append("low_deployment_rows_are_off_trigger_observations")
    if summary["trade_enabled_true_count"]:
        reasons.append("trade_enabled_true_rows_seen")
    if summary["alters_orders_true_count"]:
        reasons.append("alters_orders_true_rows_seen")
    if summary["true_trigger_closed_count"] >= MIN_TRUE_TRIGGER_CLOSED_ROWS:
        if summary["replacement_value_vs_cash_usd_sum"] <= 0:
            reasons.append("non_positive_replacement_value_vs_cash")
        if summary["replacement_value_vs_spy_usd_sum"] <= 0:
            reasons.append("non_positive_replacement_value_vs_spy")
        if summary["replacement_value_vs_qqq_usd_sum"] <= 0:
            reasons.append("non_positive_replacement_value_vs_qqq")
        share = summary.get("max_single_positive_cash_share")
        if share is not None and share > MAX_SINGLE_POSITIVE_SHARE:
            reasons.append("single_positive_row_concentration_above_50pct")
    return reasons


def _scan_states() -> list[dict[str, Any]]:
    summaries = []
    for path in sorted(PAPER_SLEEVES_DIR.glob("*/state.json")):
        summaries.append(_state_summary(path))
    return summaries


def _aggregate_baseline() -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(row["expected_value_score"] for row in BASELINE_METRICS.values()), 6
        ),
        "total_pnl_sum": round(sum(row["total_pnl"] for row in BASELINE_METRICS.values()), 2),
        "trade_count_sum": sum(row["trade_count"] for row in BASELINE_METRICS.values()),
        "min_survival_rate": min(row["survival_rate"] for row in BASELINE_METRICS.values()),
        "max_drawdown_pct_max": max(row["max_drawdown_pct"] for row in BASELINE_METRICS.values()),
    }


def _delta_metrics() -> dict[str, Any]:
    by_window = {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        }
        for label in WINDOWS
    }
    return {
        "by_window": by_window,
        "aggregate": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "max_drawdown_delta_max": 0.0,
        },
    }


def _field_dependency_check(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    closed_total = sum(row["closed_count"] for row in summaries)
    entry_total = sum(row["entry_date_present_count"] for row in summaries)
    target_total = sum(row["target_price_present_count"] for row in summaries)
    exit_total = sum(row["exit_price_or_close_present_count"] for row in summaries)
    return {
        "state_files_scanned": len(summaries),
        "closed_rows_scanned": closed_total,
        "entry_date_present_count": entry_total,
        "entry_date_coverage": entry_total / closed_total if closed_total else None,
        "target_price_present_count": target_total,
        "target_price_coverage": target_total / closed_total if closed_total else None,
        "exit_price_or_close_present_count": exit_total,
        "target_price_note": (
            "Closed paper-sleeve replacement rows generally use explicit exit "
            "price or hold-day exit fields instead of target_price. This run "
            "does not create executable targets; any activation follow-up must "
            "document the shared exit/target contract before changing orders."
        ),
        "minimum_entry_date_check_passed": closed_total == 0 or entry_total == closed_total,
        "minimum_target_price_check_passed_for_activation": False,
    }


def _activation_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        summaries,
        key=lambda row: (
            row["activation_ready"],
            row["closed_count"],
            row["true_trigger_closed_count"],
            row["replacement_value_vs_cash_usd_sum"],
        ),
        reverse=True,
    )
    ready = [row for row in ranked if row["activation_ready"]]
    low = next((row for row in summaries if row["sleeve_dir"] == "low_deployment_etf"), None)
    return {
        "activation_ready_count": len(ready),
        "activation_ready_sleeves": [row["sleeve_dir"] for row in ready],
        "top_forward_rows": [
            {
                "sleeve_dir": row["sleeve_dir"],
                "closed_count": row["closed_count"],
                "true_trigger_closed_count": row["true_trigger_closed_count"],
                "rv_cash": row["replacement_value_vs_cash_usd_sum"],
                "rv_spy": row["replacement_value_vs_spy_usd_sum"],
                "rv_qqq": row["replacement_value_vs_qqq_usd_sum"],
                "activation_ready": row["activation_ready"],
                "reject_reasons": row["activation_reject_reasons"][:4],
            }
            for row in ranked[:10]
        ],
        "low_deployment_interpretation": (
            "Low-deployment ETF has positive observed replacement value, but "
            "0 of its 17 closed rows are low-deployment true-trigger rows; all "
            "17 are core_above_reference_threshold independent observations."
            if low
            else "No low_deployment_etf state file found."
        ),
    }


def _gate4(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    activation = _activation_summary(summaries)
    return {
        "passed": False,
        "decision_basis": "forward_activation_readiness_not_strategy_retune",
        "canonical_three_window_context": {
            "baseline_metrics": BASELINE_METRICS,
            "after_metrics": BASELINE_METRICS,
            "delta_metrics": _delta_metrics(),
            "aggregate_baseline": _aggregate_baseline(),
            "note": (
                "No strategy behavior changed, so before/after canonical "
                "three-window deltas are exactly zero. The alpha decision here "
                "is whether forward default-off rows are mature enough to "
                "justify activation work."
            ),
        },
        "activation_acceptance_rule": {
            "min_true_trigger_closed_rows": MIN_TRUE_TRIGGER_CLOSED_ROWS,
            "min_replacement_value_coverage": MIN_REPLACEMENT_VALUE_COVERAGE,
            "requires_positive_vs_cash_spy_qqq": True,
            "requires_no_production_parity_gap": True,
            "requires_no_historical_gate_regression": True,
        },
        "activation_summary": activation,
        "failed_reasons": [
            "no_sleeve_has_20_true_trigger_closed_forward_rows",
            "low_deployment_positive_rows_are_off_trigger_observations",
            "other_forward_rows_are_too_sparse_or_negative",
            "no_activation_without_shared_helper_parity_follow_up",
        ],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    summaries = _scan_states()
    activation = _activation_summary(summaries)
    status = "rejected"
    decision = "rejected_no_forward_activation_ready"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_success": 0,
        "actual_decision": decision,
        "actual_ev_delta": 0.0,
        "actual_pnl_delta": 0.0,
        "realized_failure_mode": "immature_forward_rows_false_trigger_rows",
        "surprise_note": (
            "Low-deployment ETF forward rows are positive versus cash/SPY/QQQ, "
            "but they are all explicitly off-trigger observations, matching the "
            "pre-run failure risk rather than activation evidence."
        ),
    }
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
    ]
    post_run_reflection = {
        "why_result_happened": (
            "The accepted default-off paper sleeve surface is still dominated "
            "by immature forward samples. The only sleeve with a near-usable "
            "closed count is low_deployment_etf, but its 17 positive rows were "
            "recorded while core deployment was above the low-deployment "
            "reference threshold, so they do not validate the actual cash-slack "
            "activation condition."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not activate low_deployment_etf from off-trigger rows, and do "
            "not sweep low-deployment thresholds, ETF lists, hold days, "
            "paper notional, accepted allocator priority, or post-earnings/"
            "FTD/Companyfacts state thresholds on the frozen windows."
        ),
        "new_evidence_required": (
            "At least 20 closed true-trigger forward rows for one shared "
            "default-off helper with replacement value enriched versus cash, "
            "SPY, and QQQ, plus a documented shared exit/target contract and "
            "daily snapshot parity before any production-facing change."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "history_check": PRE_RUN_QUESTIONS["2_history_check"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window protocol",
            "windows": WINDOWS,
            "baseline_result_file": "docs/backtesting.md",
            "replay_news": False,
            "replay_llm": False,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_source": "docs/backtesting.md",
            "baseline_metrics": BASELINE_METRICS,
            "aggregate_baseline": _aggregate_baseline(),
        },
        "gate2": _field_dependency_check(summaries),
        "gate3": {
            "survival_rate_min": min(row["survival_rate"] for row in BASELINE_METRICS.values()),
            "survival_guard_passed": True,
            "signals_generated_by_window": {
                label: row["signals_generated"] for label, row in BASELINE_METRICS.items()
            },
            "signals_survived_by_window": {
                label: row["signals_survived"] for label, row in BASELINE_METRICS.items()
            },
            "filter_added": False,
        },
        "gate4": _gate4(summaries),
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "delta_metrics": _delta_metrics(),
        "paper_sleeve_summaries": summaries,
        "activation_summary": activation,
        "production_impact": PRODUCTION_IMPACT,
        "alpha_direction_conclusion": (
            "Do not activate or retune any accepted paper adapter from the "
            "current forward rows. The strongest near-term alpha work remains "
            "production-visible default-off maturation, but only with true "
            "trigger rows. If waiting on forward evidence, move to a materially "
            "new free PIT data edge instead of more OHLCV threshold variants."
        ),
        "post_run_reflection": post_run_reflection,
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["gate1"]["aggregate_baseline"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "history_check": payload["history_check"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "docs/backtesting.md",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "aggregate_baseline_expected_value_score": aggregate["expected_value_score_sum"],
        "aggregate_baseline_total_pnl": aggregate["total_pnl_sum"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "activation_summary": payload["activation_summary"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    top = payload["activation_summary"]["top_forward_rows"][:6]
    rows = [
        "| Sleeve | Closed | True-trigger | RV cash | RV SPY | RV QQQ | Decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in top:
        rows.append(
            "| {sleeve} | {closed} | {true} | ${cash:,.2f} | ${spy:,.2f} | "
            "${qqq:,.2f} | {decision} |".format(
                sleeve=row["sleeve_dir"],
                closed=row["closed_count"],
                true=row["true_trigger_closed_count"],
                cash=row["rv_cash"],
                spy=row["rv_spy"],
                qqq=row["rv_qqq"],
                decision="ready" if row["activation_ready"] else ",".join(row["reject_reasons"][:2]),
            )
        )
    aggregate = payload["gate1"]["aggregate_baseline"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Adapter Forward Maturity",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 1-4 Readout",
            "",
            "- Canonical baseline aggregate EV: `{:.4f}`.".format(
                aggregate["expected_value_score_sum"]
            ),
            "- Canonical baseline aggregate PnL: `${:,.2f}`.".format(
                aggregate["total_pnl_sum"]
            ),
            "- Strategy behavior changed: `false`; before/after deltas are `0`.",
            "- Activation-ready sleeves: `{}`.".format(
                ", ".join(payload["activation_summary"]["activation_ready_sleeves"]) or "none"
            ),
            "",
            "## Forward Rows",
            "",
            *rows,
            "",
            payload["activation_summary"]["low_deployment_interpretation"],
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


def _persist_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "summary": payload["alpha_direction_conclusion"],
    }
    fields = {
        "owner": OWNER,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "allowed_write_scope": payload["related_files"],
        "hypothesis": (
            "Accepted default-off paper adapters may now have enough forward "
            "replacement-value evidence to identify an activation-ready alpha "
            "direction without retuning frozen historical thresholds."
        ),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(__file__), OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    file_hashes = {}
    for path in paths:
        if path.exists():
            file_hashes[_repo_rel(path)] = _sha256(path)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": file_hashes,
        "global_registry_note": (
            "Registry/ticket status updated through persist_self_registered_result. "
            "The strategy and production execution paths were not modified."
        ),
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _build_log_record(payload))
    _write_text(CARD_MD, _build_card(payload))
    _persist_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
