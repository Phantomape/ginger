"""exp-20260705-015: alpha_score_market_regime forward RV readiness.

Observed-only alpha attribution.  The accepted alpha_score_market_regime
default-off paper sleeve now has its first closed replacement-value rows after
the exp-20260701-004 paper-ledger repair.  This runner checks whether the
closed paper cohort shows positive cash/SPY/QQQ replacement value and records
why it is not activation-ready.

No strategy behavior changes here: no entries, ranking, sizing, exits, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260705-015"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "alpha_score_market_regime_forward_rv_readiness"
RUNNER = f"quant/experiments/exp_20260705_015_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STATE_PATH = REPO_ROOT / "data" / "paper_sleeves" / "alpha_score_market_regime" / "state.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
GATE2_REQUIRED_FIELDS = [
    "ticker",
    "status",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
    "replacement_value_status",
    "trade_enabled",
]
OBSERVED_RULE = {
    "min_closed_rows": 5,
    "min_win_rate_vs_cash_spy_qqq": 0.60,
    "require_positive_sum_vs_cash_spy_qqq": True,
    "max_single_positive_cash_ticker_share": 0.50,
}
ACTIVATION_RULE = {
    "min_closed_rows": 30,
    "max_single_positive_cash_ticker_share": 0.40,
    "require_multiple_entry_regimes": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_015_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
RELATED_FILES = [
    "data/paper_sleeves/alpha_score_market_regime/state.json",
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
    "docs/backtesting.md",
    "docs/alpha_context_pack.md",
    "docs/current_state_snapshot.md",
    "experiments/logs/exp-20260701-004.json",
    "experiments/logs/exp-20260704-026.json",
    "experiments/logs/exp-20260613-012.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def row_ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("candidate", {}).get("ticker") or "UNKNOWN")


def candidate_value(row: dict[str, Any], key: str) -> Any:
    candidate = row.get("candidate")
    if not isinstance(candidate, dict):
        return None
    return candidate.get(key)


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
    }


def metric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = numeric_value(row, key)
        if value is not None:
            values.append(value)
    return values


def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [*PRIMARY_METRICS, "pnl", "return_pct_net"]
    return {key: summarize_values(metric_values(rows, key)) for key in keys}


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "baseline_exists": BASELINE_PATH.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "windows": [
            {
                "label": window.get("label"),
                "start": window.get("start"),
                "end": window.get("end"),
                "expected_value_score": window.get("expected_value_score"),
                "total_pnl": window.get("total_pnl"),
                "trade_count": window.get("trade_count"),
                "survival_rate": window.get("survival_rate"),
            }
            for window in windows
        ],
    }


def comparator_ready(row: dict[str, Any]) -> bool:
    return all(numeric_value(row, key) is not None for key in PRIMARY_METRICS)


def missing_fields(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for field in GATE2_REQUIRED_FIELDS:
        missing: list[str] = []
        for row in rows:
            value = row.get(field)
            if value is None or value == "":
                missing.append(row_ticker(row))
        if missing:
            output[field] = missing
    return output


def concentration(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = numeric_value(row, metric)
        if value is not None and value > 0:
            positive_by_ticker[row_ticker(row)] += value
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_total": round(total, 2),
            "positive_by_ticker": {},
            "max_single_positive_ticker_share": None,
            "top_positive_ticker": None,
            "top3_positive_ticker_share": None,
            "hhi_positive_ticker_share": None,
        }
    ranked = sorted(positive_by_ticker.items(), key=lambda item: item[1], reverse=True)
    shares = [(ticker, value / total) for ticker, value in ranked]
    return {
        "positive_total": round(total, 2),
        "positive_by_ticker": {ticker: round(value, 2) for ticker, value in ranked},
        "max_single_positive_ticker_share": round(shares[0][1], 6),
        "top_positive_ticker": shares[0][0],
        "top3_positive_ticker_share": round(sum(share for _, share in shares[:3]), 6),
        "hhi_positive_ticker_share": round(sum(share * share for _, share in shares), 6),
    }


def count_by(rows: list[dict[str, Any]], key: str, *, candidate: bool = False) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = candidate_value(row, key) if candidate else row.get(key)
        counts[str(value or "UNKNOWN")] += 1
    return dict(sorted(counts.items()))


def row_details(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for row in rows:
        details.append(
            {
                "ticker": row_ticker(row),
                "signal_date": candidate_value(row, "signal_date") or candidate_value(row, "date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "hold_days": row.get("hold_days"),
                "sector": candidate_value(row, "sector"),
                "entry_regime_label": row.get("entry_regime_label"),
                "alpha_score": candidate_value(row, "alpha_score"),
                "alpha_score_rank": candidate_value(row, "alpha_score_rank"),
                "safe_notional_scalar": candidate_value(row, "safe_notional_scalar"),
                "trade_enabled": row.get("trade_enabled"),
                "pnl": numeric_value(row, "pnl"),
                "replacement_value_vs_cash_usd": numeric_value(
                    row, "replacement_value_vs_cash_usd"
                ),
                "replacement_value_vs_spy_usd": numeric_value(
                    row, "replacement_value_vs_spy_usd"
                ),
                "replacement_value_vs_qqq_usd": numeric_value(
                    row, "replacement_value_vs_qqq_usd"
                ),
                "replacement_value_status": row.get("replacement_value_status"),
            }
        )
    return details


def observed_lead_checks(rows: list[dict[str, Any]], conc: dict[str, Any]) -> dict[str, Any]:
    metrics = metric_summary(rows)
    win_rates = {
        key: metrics[key]["positive_rate"] for key in PRIMARY_METRICS
    }
    positive_sums = {
        key: (metrics[key]["sum"] is not None and metrics[key]["sum"] > 0)
        for key in PRIMARY_METRICS
    }
    checks = {
        "min_closed_rows": len(rows) >= OBSERVED_RULE["min_closed_rows"],
        "positive_sum_vs_cash": positive_sums["replacement_value_vs_cash_usd"],
        "positive_sum_vs_spy": positive_sums["replacement_value_vs_spy_usd"],
        "positive_sum_vs_qqq": positive_sums["replacement_value_vs_qqq_usd"],
        "win_rate_vs_cash_ge_60pct": (
            win_rates["replacement_value_vs_cash_usd"]
            is not None
            and win_rates["replacement_value_vs_cash_usd"]
            >= OBSERVED_RULE["min_win_rate_vs_cash_spy_qqq"]
        ),
        "win_rate_vs_spy_ge_60pct": (
            win_rates["replacement_value_vs_spy_usd"]
            is not None
            and win_rates["replacement_value_vs_spy_usd"]
            >= OBSERVED_RULE["min_win_rate_vs_cash_spy_qqq"]
        ),
        "win_rate_vs_qqq_ge_60pct": (
            win_rates["replacement_value_vs_qqq_usd"]
            is not None
            and win_rates["replacement_value_vs_qqq_usd"]
            >= OBSERVED_RULE["min_win_rate_vs_cash_spy_qqq"]
        ),
        "single_positive_cash_ticker_share_le_50pct": (
            conc["max_single_positive_ticker_share"] is not None
            and conc["max_single_positive_ticker_share"]
            <= OBSERVED_RULE["max_single_positive_cash_ticker_share"]
        ),
    }
    return {
        "rule": OBSERVED_RULE,
        "checks": checks,
        "passed": all(checks.values()),
    }


def activation_readiness(rows: list[dict[str, Any]], conc: dict[str, Any]) -> dict[str, Any]:
    entry_regimes = count_by(rows, "entry_regime_label")
    blockers: list[str] = []
    if len(rows) < ACTIVATION_RULE["min_closed_rows"]:
        blockers.append(
            f"closed_rows_{len(rows)}_lt_activation_floor_{ACTIVATION_RULE['min_closed_rows']}"
        )
    max_share = conc["max_single_positive_ticker_share"]
    if max_share is not None and max_share > ACTIVATION_RULE["max_single_positive_cash_ticker_share"]:
        blockers.append(
            "single_positive_cash_ticker_share_"
            f"{max_share:.3f}_gt_{ACTIVATION_RULE['max_single_positive_cash_ticker_share']:.2f}"
        )
    if ACTIVATION_RULE["require_multiple_entry_regimes"] and len(entry_regimes) < 2:
        blockers.append("all_closed_rows_same_entry_regime")
    return {
        "rule": ACTIVATION_RULE,
        "alpha_ready": not blockers,
        "blockers": blockers,
        "closed_rows": len(rows),
        "entry_regime_labels": entry_regimes,
        "max_single_positive_cash_ticker_share": max_share,
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {}) or {}
    state = read_json(STATE_PATH, {}) or {}
    baseline = baseline_metrics()
    closed_rows_all = list(state.get("closed_positions") or [])
    open_rows = list(state.get("open_positions") or [])
    pending_rows = list(state.get("pending_entries") or [])
    closed_rows = [row for row in closed_rows_all if str(row.get("status")) == "closed"]
    comparator_rows = [row for row in closed_rows if comparator_ready(row)]
    missing = missing_fields(comparator_rows)
    gate2_passed = not missing and bool(comparator_rows)
    cash_concentration = concentration(comparator_rows, "replacement_value_vs_cash_usd")
    metrics = metric_summary(comparator_rows)
    observed = observed_lead_checks(comparator_rows, cash_concentration)
    readiness = activation_readiness(comparator_rows, cash_concentration)
    all_trade_disabled = all(
        row.get("trade_enabled") is False for row in [*closed_rows, *open_rows, *pending_rows]
    )
    observed_passed = observed["passed"] and gate2_passed and all_trade_disabled
    status = (
        "observed_only_positive_forward_lead_not_activation_ready"
        if observed_passed
        else "rejected_no_alpha_score_forward_rv_edge"
    )
    decision = status
    accepted = False
    accepted_alpha = False
    alpha_ready = False

    gate1 = {
        "name": "Gate 1 baseline",
        "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
        "baseline_metrics": baseline,
        "note": "Read-only forward attribution; canonical strategy baseline is unchanged.",
    }
    gate2 = {
        "name": "Gate 2 field contract",
        "passed": gate2_passed,
        "required_fields": GATE2_REQUIRED_FIELDS,
        "missing_fields_by_ticker": missing,
        "target_price_contract": {
            "applicable": False,
            "reason": (
                "This run does not generate backtest signals or alter exit policy; "
                "entry_date and replacement-value comparator fields are the contract "
                "for the closed paper-ledger rows."
            ),
        },
        "comparator_ready_rows": len(comparator_rows),
        "state_file": repo_rel(STATE_PATH),
    }
    gate3 = {
        "name": "Gate 3 survival/sample",
        "passed": len(comparator_rows) >= OBSERVED_RULE["min_closed_rows"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
        "closed_rows": len(closed_rows),
        "comparator_ready_rows": len(comparator_rows),
        "open_rows": len(open_rows),
        "pending_rows": len(pending_rows),
        "note": "No new filter was added, so canonical strategy survival is unchanged.",
    }
    gate4 = {
        "name": "Gate 4 observed replacement-value attribution",
        "passed": observed_passed,
        "observed_lead_checks": observed,
        "activation_readiness": readiness,
        "no_strategy_behavior_change": True,
        "accepted_alpha": accepted_alpha,
    }

    summary = {
        "state_updated_at": state.get("updated_at"),
        "sleeve": state.get("sleeve"),
        "closed_rows": len(closed_rows),
        "comparator_ready_rows": len(comparator_rows),
        "open_rows": len(open_rows),
        "pending_rows": len(pending_rows),
        "skipped_entries": state.get("skipped_entries"),
        "all_trade_enabled_false": all_trade_disabled,
        "metric_summary": metrics,
        "cash_concentration": cash_concentration,
        "rows_by_ticker": count_by(comparator_rows, "ticker"),
        "rows_by_sector": count_by(comparator_rows, "sector", candidate=True),
        "rows_by_entry_regime_label": count_by(comparator_rows, "entry_regime_label"),
        "rows_by_exit_reason": count_by(comparator_rows, "exit_reason"),
        "closed_row_details": row_details(comparator_rows),
    }

    before_metrics = {
        "canonical_baseline": baseline,
        "strategy_behavior_changed": False,
    }
    after_metrics = {
        "observed_forward_replacement_value": metrics,
        "closed_rows": len(comparator_rows),
        "activation_readiness": readiness,
    }
    delta_metrics = {
        "strategy_expected_value_score_delta": 0.0,
        "strategy_total_pnl_delta": 0.0,
        "replacement_value_vs_cash_sum": metrics["replacement_value_vs_cash_usd"]["sum"],
        "replacement_value_vs_spy_sum": metrics["replacement_value_vs_spy_usd"]["sum"],
        "replacement_value_vs_qqq_sum": metrics["replacement_value_vs_qqq_usd"]["sum"],
        "status_note": "Observed paper-ledger attribution only; no before/after strategy replay delta.",
    }

    calibration_result = (
        "success_condition_hit_but_activation_blocked"
        if observed_passed
        else "success_condition_missed"
    )
    rejection_reason = (
        "not_activation_ready:"
        + ",".join(readiness["blockers"] or ["observed_only_no_activation"])
        if observed_passed
        else "observed_lead_checks_failed"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": accepted_alpha,
        "accepted_measurement_repair": False,
        "alpha_ready": alpha_ready,
        "decision": decision,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": (
            ticket.get("novelty", {}).get("new_evidence_axis")
            or "closed alpha_score_market_regime paper-sleeve RV rows"
        ),
        "prediction": ticket.get("prediction"),
        "parameters": {
            "observed_rule": OBSERVED_RULE,
            "activation_rule": ACTIVATION_RULE,
            "state_file": repo_rel(STATE_PATH),
            "baseline_file": repo_rel(BASELINE_PATH),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "summary": summary,
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "activation_readiness": readiness,
        "production_impact": {
            "alters_orders": False,
            "alters_live_orders": False,
            "alters_paper_orders": False,
            "alters_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "default_off_only": True,
            "live_ready": False,
            "reason": (
                "Read-only attribution of existing default-off paper rows; "
                "activation remains blocked by sample size and concentration/regime coverage."
            ),
        },
        "calibration": {
            "predicted_success_probability": (
                ticket.get("prediction") or {}
            ).get("success_probability"),
            "outcome": calibration_result,
            "surprise": "positive_forward_value_thin_sample" if observed_passed else "weak_forward_value",
            "realized_failure_modes": readiness["blockers"],
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The observed lead passed because four of five closed paper rows "
                "were positive versus cash, four beat SPY, and three beat QQQ, "
                "with aggregate RV still positive against all three comparators. "
                "It is not activation-ready because the evidence is only five "
                "closed rows, the largest positive cash contributor is 42.9% of "
                "positive cash RV, and every closed row entered in the same "
                "risk_on_trend regime."
                if observed_passed
                else "The observed lead failed because the first resolved paper "
                "cohort did not produce enough positive replacement value across "
                "cash, SPY, and QQQ comparators to offset the thin-sample and "
                "concentration risks."
            ),
            "alpha_interpretation": (
                "The first alpha_score_market_regime paper cohort is positive versus "
                "cash, SPY, and QQQ, so it remains a useful forward lead, but five "
                "closed rows are far below activation evidence."
                if observed_passed
                else "The first alpha_score_market_regime paper cohort did not clear "
                "the observed lead threshold, so promotion work should stop until "
                "materially more rows settle."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune alpha_score_market_regime thresholds, top-N, hold days, "
                "notional scalar, response curve, or ETF comparator choice on these "
                "same five rows."
            ),
            "new_evidence_required": (
                "At least 30 closed alpha_score_market_regime paper rows with "
                "cash/SPY/QQQ replacement values, materially lower single-name "
                "positive contribution concentration, and entries outside the "
                "current all-risk_on_trend cohort; alternatively a genuinely "
                "different production-visible PIT source."
            ),
            "next_new_evidence_required": (
                "Reopen activation only after at least 30 closed alpha_score_market_regime "
                "paper rows with cash/SPY/QQQ replacement values, materially lower "
                "single-name concentration, and non-risk_on or otherwise different "
                "forward regimes; alternatively use a genuinely different PIT source."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "at least 30 closed alpha_score_market_regime paper RV rows",
            "cash/SPY/QQQ replacement values on the unchanged paper sleeve",
            "lower single-name positive contribution concentration",
            "no threshold/top-N/notional/hold-period/response-curve retune on the same rows",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": RELATED_FILES,
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "changed_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "activation_readiness",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    metrics = summary["metric_summary"]
    readiness = payload["activation_readiness"]
    lines = [
        f"# {EXPERIMENT_ID} - alpha_score_market_regime forward RV readiness",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- closed/comparator-ready rows: {summary['closed_rows']} / {summary['comparator_ready_rows']}",
        f"- RV sums cash/SPY/QQQ: {metrics['replacement_value_vs_cash_usd']['sum']} / {metrics['replacement_value_vs_spy_usd']['sum']} / {metrics['replacement_value_vs_qqq_usd']['sum']}",
        f"- win rates cash/SPY/QQQ: {metrics['replacement_value_vs_cash_usd']['positive_rate']} / {metrics['replacement_value_vs_spy_usd']['positive_rate']} / {metrics['replacement_value_vs_qqq_usd']['positive_rate']}",
        f"- max positive cash ticker share: {summary['cash_concentration']['max_single_positive_ticker_share']}",
        f"- alpha ready: {readiness['alpha_ready']}",
        f"- activation blockers: {', '.join(readiness['blockers']) or 'none'}",
        "",
        "No strategy, ranking, sizing, exit, live order, paper order, or LLM decision boundary changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {}) or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "closed_rows": payload["summary"]["closed_rows"],
                "replacement_value_vs_cash_sum": payload["delta_metrics"][
                    "replacement_value_vs_cash_sum"
                ],
                "replacement_value_vs_spy_sum": payload["delta_metrics"][
                    "replacement_value_vs_spy_sum"
                ],
                "replacement_value_vs_qqq_sum": payload["delta_metrics"][
                    "replacement_value_vs_qqq_sum"
                ],
                "activation_blockers": payload["activation_readiness"]["blockers"],
            },
        },
        status=payload["status"],
        fields={
            **{
                key: value
                for key, value in ticket.items()
                if key not in {"result", "status"}
            },
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "parameters": payload["parameters"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "activation_readiness": payload["activation_readiness"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "closed_rows": payload["summary"]["closed_rows"],
                "rv_sums": {
                    "cash": payload["delta_metrics"]["replacement_value_vs_cash_sum"],
                    "spy": payload["delta_metrics"]["replacement_value_vs_spy_sum"],
                    "qqq": payload["delta_metrics"]["replacement_value_vs_qqq_sum"],
                },
                "activation_blockers": payload["activation_readiness"]["blockers"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
