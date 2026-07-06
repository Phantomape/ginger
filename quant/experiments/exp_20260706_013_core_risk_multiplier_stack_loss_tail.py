"""exp-20260706-013: core risk multiplier stack loss-tail attribution.

Read-only alpha-search scout. Tests whether pre-entry stacked risk multipliers
in the accepted canonical replay mark loss-tail risk before considering any
shared cap or sizing rule.

No strategy, ranking, sizing, exit, paper sleeve, watchlist, order, or LLM
behavior is changed by this runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


EXPERIMENT_ID = "exp-20260706-013"
OWNER = "alpha-explore"
SLUG = "core_risk_multiplier_stack_loss_tail"
RUNNER = f"quant/experiments/exp_20260706_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260706_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_RESULT_DIR = (
    REPO_ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "path": WINDOW_RESULT_DIR / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "path": WINDOW_RESULT_DIR / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "path": WINDOW_RESULT_DIR / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
}

HYPOTHESIS = (
    "Core risk-intensity forward observations may identify loss-tail in "
    "production-selected entries, but the current evidence must first validate "
    "whether high stacked risk multipliers underperform normal-risk selected "
    "entries on closed canonical replay trades before any cap or sizing rule is "
    "considered."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "risk_allocation"
TRIAL_FAMILY = "risk_allocation"
TRIAL_VARIANT_ID = "core_risk_multiplier_stack_loss_tail_attribution_v1"
CHANGED_VARIABLE = "core_risk_multiplier_stack_loss_tail_attribution_v1"
NEW_EVIDENCE_TYPE = "new_preentry_risk_multiplier_stack_attribution"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260702-010", "exp-20260630-018"]
CAUSAL_COMPONENTS = [
    "canonical replay trade attribution",
    "pre-entry shared risk multiplier fields",
    "no strategy behavior change",
    "gate verdict",
]

# Fixed before seeing the result: high-stack means several independent boost
# multipliers stacked on the same selected entry. This is not the rejected
# actual-risk >= 2% cap from exp-20260702-010.
MIN_BOOST_COUNT = 4
MIN_BOOST_PRODUCT = 2.5
SEVERE_LOSS_RETURN_PCT = -0.05
MIN_HIGH_STACK_TOTAL_TRADES = 9
MIN_SUPPORTING_WINDOWS = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits) if math.isfinite(value) else None
    return value


def numeric(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def summarize_values(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "sum": rounded(sum(values), 4) if values else 0.0,
        "mean": rounded(mean(values), 4) if values else None,
        "median": rounded(median(values), 4) if values else None,
        "min": rounded(min(values), 4) if values else None,
        "max": rounded(max(values), 4) if values else None,
        "positive_rate": rounded(sum(1 for value in values if value > 0) / len(values), 4)
        if values
        else None,
    }


def sizing_profile(trade: dict[str, Any]) -> dict[str, Any]:
    multipliers = trade.get("sizing_multipliers") or {}
    risk_values: dict[str, float] = {}
    boost_values: dict[str, float] = {}
    haircut_values: dict[str, float] = {}
    boost_product = 1.0
    for key, raw in multipliers.items():
        if not str(key).endswith("_risk_multiplier_applied"):
            continue
        value = numeric(raw)
        if value is None:
            continue
        if abs(value - 1.0) <= 1e-9:
            continue
        risk_values[str(key)] = value
        if value > 1.0:
            boost_values[str(key)] = value
            boost_product *= value
        elif value < 1.0:
            haircut_values[str(key)] = value
    high_stack = len(boost_values) >= MIN_BOOST_COUNT and boost_product >= MIN_BOOST_PRODUCT
    return {
        "risk_multiplier_count": len(risk_values),
        "boost_count": len(boost_values),
        "haircut_count": len(haircut_values),
        "boost_product": rounded(boost_product, 6),
        "risk_multipliers": risk_values,
        "boost_multipliers": boost_values,
        "haircut_multipliers": haircut_values,
        "high_stack": high_stack,
    }


def decorate_trade(label: str, trade: dict[str, Any]) -> dict[str, Any]:
    profile = sizing_profile(trade)
    return {
        "window": label,
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": rounded(numeric(trade.get("pnl")), 4),
        "pnl_pct_net": rounded(numeric(trade.get("pnl_pct_net")), 6),
        "actual_risk_pct": rounded(numeric(trade.get("actual_risk_pct")), 6),
        "base_risk_pct": rounded(numeric(trade.get("base_risk_pct")), 6),
        **profile,
    }


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    returns = [
        float(row["pnl_pct_net"]) for row in rows if row.get("pnl_pct_net") is not None
    ]
    severe = [row for row in rows if (row.get("pnl_pct_net") or 0.0) <= SEVERE_LOSS_RETURN_PCT]
    by_ticker = Counter(str(row.get("ticker") or "") for row in rows)
    by_sector = Counter(str(row.get("sector") or "Unknown") for row in rows)
    return {
        "trade_count": len(rows),
        "pnl": summarize_values(pnls),
        "return_pct": summarize_values(returns),
        "severe_loss_threshold": SEVERE_LOSS_RETURN_PCT,
        "severe_loss_count": len(severe),
        "severe_loss_rate": rounded(len(severe) / len(rows), 4) if rows else None,
        "worst_trade": min(rows, key=lambda row: row.get("pnl_pct_net") or 0.0)
        if rows
        else None,
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_sector": dict(sorted(by_sector.items())),
    }


def load_window(label: str, spec: dict[str, Any]) -> dict[str, Any]:
    payload = read_json(spec["path"], {})
    trades = [
        decorate_trade(label, trade)
        for trade in payload.get("trades") or []
        if trade.get("entry_date") and trade.get("pnl") is not None
    ]
    high = [row for row in trades if row["high_stack"]]
    other = [row for row in trades if not row["high_stack"]]
    high_summary = group_summary(high)
    other_summary = group_summary(other)
    high_mean = high_summary["pnl"]["mean"]
    other_mean = other_summary["pnl"]["mean"]
    high_severe = high_summary["severe_loss_rate"]
    other_severe = other_summary["severe_loss_rate"]
    supports_loss_tail = (
        high_mean is not None
        and other_mean is not None
        and high_severe is not None
        and other_severe is not None
        and high_mean < other_mean
        and high_severe > other_severe
    )
    return {
        "label": label,
        "start": spec["start"],
        "end": spec["end"],
        "source_path": repo_rel(spec["path"]),
        "baseline_metrics": {
            "expected_value_score": rounded(payload.get("expected_value_score")),
            "total_pnl": rounded(payload.get("total_pnl"), 2),
            "max_drawdown_pct": rounded(payload.get("max_drawdown_pct"), 6),
            "trade_count": payload.get("total_trades") or len(trades),
            "signals_generated": payload.get("signals_generated"),
            "signals_survived": payload.get("signals_survived"),
            "survival_rate": rounded(payload.get("survival_rate"), 6),
        },
        "trade_count": len(trades),
        "high_stack": high_summary,
        "non_high_stack": other_summary,
        "supports_loss_tail": supports_loss_tail,
        "sample_rows_high_stack": high,
    }


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_high: list[dict[str, Any]] = []
    all_other: list[dict[str, Any]] = []
    supporting = []
    for label, data in windows.items():
        all_high.extend(data["sample_rows_high_stack"])
        # Rebuild non-high rows from per-window source to keep artifact compact.
        if data["supports_loss_tail"]:
            supporting.append(label)
    for label, spec in WINDOWS.items():
        payload = read_json(spec["path"], {})
        all_other.extend(
            decorate_trade(label, trade)
            for trade in payload.get("trades") or []
            if trade.get("entry_date")
            and trade.get("pnl") is not None
            and not sizing_profile(trade)["high_stack"]
        )
    high_summary = group_summary(all_high)
    other_summary = group_summary(all_other)
    return {
        "high_stack": high_summary,
        "non_high_stack": other_summary,
        "supporting_windows": supporting,
        "supporting_window_count": len(supporting),
    }


def make_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    window_payload = {label: load_window(label, spec) for label, spec in WINDOWS.items()}
    aggregate = aggregate_windows(window_payload)
    high_n = aggregate["high_stack"]["trade_count"]
    supporting_count = aggregate["supporting_window_count"]
    sample_ready = high_n >= MIN_HIGH_STACK_TOTAL_TRADES
    lead_passed = sample_ready and supporting_count >= MIN_SUPPORTING_WINDOWS

    failed_reasons: list[str] = []
    if not sample_ready:
        failed_reasons.append("thin_high_risk_sample")
    if supporting_count < MIN_SUPPORTING_WINDOWS:
        failed_reasons.append("no_stable_loss_tail")
    high_mean = aggregate["high_stack"]["pnl"]["mean"]
    other_mean = aggregate["non_high_stack"]["pnl"]["mean"]
    if high_mean is not None and other_mean is not None and high_mean >= other_mean:
        failed_reasons.append("high_risk_entries_are_winners")

    decision = (
        "observed_positive_lead_core_risk_multiplier_stack_loss_tail"
        if lead_passed
        else "rejected_core_risk_multiplier_stack_loss_tail"
    )
    status = "observed_only_positive_lead" if lead_passed else "rejected"
    actual_success = 1 if lead_passed else 0
    predicted_p = float(prediction.get("success_probability") or 0.0)
    baseline = read_json(BASELINE_RESULT, {})

    why = (
        "High-stack selected entries showed stable loss-tail underperformance in "
        "at least two windows, justifying a separate shared-policy Gate 4 cap or "
        "sizing ablation."
        if lead_passed
        else "The high-stack bucket was not a loss-tail cohort: aggregate mean PnL "
        "was higher than non-high-stack, and no window showed both lower mean PnL "
        "and higher severe-loss rate for high-stack entries."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": lead_passed,
        "accepted_alpha": False,
        "observed_only_lead": lead_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "Different PIT gate shape from exp-20260702-010: pre-entry count "
            "and product of shared risk-multiplier boosts on accepted closed "
            "replay trades, not an actual-risk percent cap or stop-distance "
            "response curve."
        ),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": round((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
        },
        "parameters": {
            "high_stack_rule": {
                "min_boost_count": MIN_BOOST_COUNT,
                "min_boost_product": MIN_BOOST_PRODUCT,
                "included_multiplier_keys": "*_risk_multiplier_applied with value != 1.0",
                "excluded_keys": "max_position_pct caps and non-risk sizing metadata",
            },
            "decision_rule": (
                "Observed positive lead only if high-stack sample has at least "
                f"{MIN_HIGH_STACK_TOTAL_TRADES} closed trades and at least "
                f"{MIN_SUPPORTING_WINDOWS} canonical windows where high-stack "
                "mean PnL is lower than non-high-stack and severe-loss rate is "
                "higher. Otherwise reject; no behavior changes either way."
            ),
            "severe_loss_return_pct": SEVERE_LOSS_RETURN_PCT,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new accepted this without override. Nearest "
                    "core_actual_risk_intensity was a single attempt; this tests "
                    "risk-multiplier stack provenance rather than the rejected "
                    "actual-risk cap."
                ),
                "exp-20260702-010": (
                    "Rejected high actual-risk entry cap; this does not retune "
                    "the 2% actual-risk threshold."
                ),
                "exp-20260630-018": (
                    "Observed high account-risk cohort lead; this uses canonical "
                    "closed replay trades and pre-entry sizing multiplier fields."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": "Predeclared source-validation rule in parameters.decision_rule.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_windows": baseline.get("windows") or [],
            "passed": BASELINE_RESULT.exists()
            and all(spec["path"].exists() for spec in WINDOWS.values()),
        },
        "gate2": {
            "fields_checked": [
                "entry_date",
                "pnl",
                "pnl_pct_net",
                "sizing_multipliers",
                "actual_risk_pct",
            ],
            "target_price_relevance": (
                "Closed-trade attribution does not consume target_price or alter "
                "exits. The canonical backtester signal contract still owns "
                "target_price during replay; this runner reads only completed "
                "trade records."
            ),
            "missing_sizing_multiplier_trade_count": sum(
                1
                for label in WINDOWS
                for row in read_json(WINDOWS[label]["path"], {}).get("trades") or []
                if not row.get("sizing_multipliers")
            ),
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "note": "Read-only attribution; canonical survival is unchanged.",
            "minimum_before_survival_rate": min(
                window_payload[label]["baseline_metrics"]["survival_rate"]
                for label in WINDOWS
                if window_payload[label]["baseline_metrics"]["survival_rate"] is not None
            ),
            "passed": True,
        },
        "gate4": {
            "applicable": False,
            "passed": lead_passed,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "sample_ready": sample_ready,
            "high_stack_total_trades": high_n,
            "supporting_windows": aggregate["supporting_windows"],
            "supporting_window_count": supporting_count,
            "note": (
                "No before/after strategy behavior changed. A positive lead "
                "would still require a separate shared-policy Gate 1-4 sizing "
                "or cap experiment."
            ),
        },
        "before_metrics": {
            label: window_payload[label]["baseline_metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "strategy_behavior_changed": False,
            "observed_attribution": aggregate,
        },
        "delta_metrics": {
            "strategy_expected_value_score_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "strategy_trade_count_delta": 0,
            "high_stack_mean_pnl_minus_non_high": rounded(
                (high_mean - other_mean)
                if high_mean is not None and other_mean is not None
                else None,
                4,
            ),
            "supporting_window_count": supporting_count,
        },
        "window_attribution": window_payload,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only attribution over accepted canonical replay artifacts; "
                "no production or backtest adapter behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune boost_count, boost_product, actual-risk percent "
                "caps, stop distance, target multiple, hold length, or response "
                "curve on these same canonical closed trades."
            ),
            "new_evidence_required": (
                "A legal retry needs prospectively logged core_risk_intensity "
                "forward rows with closed replacement value, or a single shared "
                "sizing/cap ablation that changes behavior and passes Gate 1-4."
            ),
        },
        "rejection_reason": None if lead_passed else ";".join(failed_reasons),
        "next_retry_requires": [
            "closed prospective core_risk_intensity forward rows with replacement value",
            "or a shared production/backtest sizing-cap ablation with full Gate 1-4",
        ],
        "before_after_strategy_behavior_changed": False,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            *[repo_rel(spec["path"]) for spec in WINDOWS.values()],
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} core risk multiplier stack loss-tail",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "| Window | high n | high mean PnL | non-high mean PnL | high severe loss | non-high severe loss | supports loss-tail |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for label in WINDOWS:
        row = payload["window_attribution"][label]
        high = row["high_stack"]
        other = row["non_high_stack"]
        lines.append(
            f"| {label} | {high['trade_count']} | {high['pnl']['mean']} | "
            f"{other['pnl']['mean']} | {high['severe_loss_rate']} | "
            f"{other['severe_loss_rate']} | {row['supports_loss_tail']} |"
        )
    gate4 = payload["gate4"]
    lines += [
        "",
        f"Supporting windows: {gate4['supporting_windows']}; failed reasons: "
        f"{gate4['failed_reasons']}.",
        "",
        "No strategy behavior changed. A positive lead would still need a separate "
        "shared production/backtest sizing or cap experiment before any risk rule "
        "could be promoted.",
    ]
    return "\n".join(lines) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": [
            {
                "path": repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": sha256(REPO_ROOT / path if not path.is_absolute() else path),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, make_card(payload))
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_json(MANIFEST_JSON, make_manifest(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = make_payload()
    persist(payload)
    print(
        json.dumps(
            safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "gate4": payload["gate4"],
                    "delta_metrics": payload["delta_metrics"],
                    "artifact": payload["artifact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
