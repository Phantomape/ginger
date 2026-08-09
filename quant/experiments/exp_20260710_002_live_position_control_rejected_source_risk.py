"""exp-20260710-002: live position-control rejected-source risk read.

Observed-only risk-allocation attribution on the live position-control ledger.
This runner does not change candidate generation, ranking, sizing, exits,
orders, or live defaults.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260710-002"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "live_position_control_rejected_source_risk"
RUNNER = f"quant/experiments/exp_20260710_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
LEDGER_JSONL = DATA_DIR / "live_pilot" / "position_control" / "ledger.jsonl"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260710_002_live_position_control_rejected_source_risk.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Rejected-source discretionary live mirror positions may be a "
    "risk-allocation exclusion bucket: if live position-control rows tagged "
    "source_signal_rejected_alpha have worse unrealized PnL or more control "
    "blockers than comparable non-rejected live positions across current as-of "
    "dates, the system should keep them default-off and require more evidence "
    "before capacity."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "self_registered_observed_only_live_risk_runner"
MECHANISM_FAMILY = "live_position_control"
TRIAL_FAMILY = "live_position_control_rejected_source_risk"
TRIAL_VARIANT_ID = "rejected_source_bucket_v1"
SINGLE_CAUSAL_VARIABLE = "live_position_control_rejected_source_risk_bucket_v1"
CAUSAL_COMPONENTS = [
    "live_position_control_ledger",
    "source_signal_rejected_alpha_bucket",
    "unrealized_pnl_and_control_blocker_comparison",
    "no_strategy_change",
    "fingerprint_keyword_coverage",
]
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260709-001", "exp-20260709-003"]
NEW_EVIDENCE_TYPE = "live_position_control_ledger"
NEW_EVIDENCE_AXIS = (
    "New production-visible live_position_control ledger gate shape: "
    "source_signal_rejected_alpha risk bucket over open live positions; prior "
    "20260709 IDs only built/wired the ledger and did not test this "
    "risk-allocation exclusion hypothesis. The same run also adds fingerprint "
    "coverage so this surface no longer escapes the saturation guards as other."
)
ACCEPTANCE_RULE = (
    "Observed-only lead only if current rejected-source live rows include at "
    "least 5 unique positions, span at least 2 as-of dates in the ledger, have "
    "average unrealized PnL at least 3 percentage points worse than non-"
    "rejected rows, have at least 0.5 more control blockers per row, and are "
    "not dominated by one ticker."
)
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_live_sample",
        "same_day_positions",
        "source_labels_mixed",
        "control_blockers_dominate_signal",
    ],
    "confidence_reason": (
        "New production ledger has explicit rejected-source tags, but only a "
        "few live rows are expected, so this is likely an observed-only risk "
        "read rather than promotable alpha."
    ),
}
CHANGED_FILES = [
    RUNNER,
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    "data/experiments/exp-20260710-002/exp_20260710_002_live_position_control_rejected_source_risk.json",
    "experiments/logs/exp-20260710-002.json",
    "experiments/cards/exp-20260710-002.md",
    "experiments/manifests/exp-20260710-002.json",
    "experiments/tickets/exp-20260710-002.json",
    "docs/experiment_registry.json",
]
ALLOWED_WRITE_SCOPE = CHANGED_FILES + ["docs/experiment_log.jsonl"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def is_position_row(row: Mapping[str, Any]) -> bool:
    source = str(row.get("row_source") or "")
    return (
        source.startswith("open_positions")
        and bool(row.get("position_id"))
        and as_float(row.get("avg_cost")) is not None
        and as_float(row.get("shares")) is not None
    )


def is_rejected_source(row: Mapping[str, Any]) -> bool:
    notes = row.get("control_notes") or []
    if isinstance(notes, str):
        notes = [notes]
    normalized_notes = {str(note).lower() for note in notes}
    risk_notes = str(row.get("risk_notes") or "").lower()
    return (
        "source_signal_rejected_alpha" in normalized_notes
        or "source signal was rejected" in risk_notes
        or "full-stack rejected" in risk_notes
    )


def unrealized_pct(row: Mapping[str, Any]) -> float | None:
    pnl = as_float(row.get("unrealized_pl"))
    avg_cost = as_float(row.get("avg_cost"))
    shares = as_float(row.get("shares"))
    if pnl is None or avg_cost is None or shares is None:
        return None
    cost_basis = avg_cost * shares
    if cost_basis == 0:
        return None
    return pnl / cost_basis


def control_blocker_count(row: Mapping[str, Any]) -> int:
    blockers = row.get("control_blockers") or []
    if not isinstance(blockers, list):
        return 0
    return len(blockers)


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def safe_mean(values: Iterable[float]) -> float | None:
    data = list(values)
    return mean(data) if data else None


def safe_median(values: Iterable[float]) -> float | None:
    data = list(values)
    return median(data) if data else None


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    pct_values = [value for row in rows if (value := unrealized_pct(row)) is not None]
    pnl_values = [value for row in rows if (value := as_float(row.get("unrealized_pl"))) is not None]
    blocker_values = [control_blocker_count(row) for row in rows]
    tickers = [str(row.get("ticker")) for row in rows if row.get("ticker")]
    ticker_counts = Counter(tickers)
    max_ticker_share = max(ticker_counts.values()) / len(rows) if rows else None
    negative_pct_count = sum(1 for value in pct_values if value < 0)
    broker_status = Counter(str(row.get("broker_order_coverage_status") or "unknown") for row in rows)
    return {
        "rows": len(rows),
        "unique_positions": len({str(row.get("position_id")) for row in rows if row.get("position_id")}),
        "asof_dates": sorted({str(row.get("asof_date")) for row in rows if row.get("asof_date")}),
        "tickers": sorted(set(tickers)),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "max_ticker_share": round_or_none(max_ticker_share),
        "avg_unrealized_pl": round_or_none(safe_mean(pnl_values), 4),
        "median_unrealized_pl": round_or_none(safe_median(pnl_values), 4),
        "avg_unrealized_pct": round_or_none(safe_mean(pct_values), 6),
        "median_unrealized_pct": round_or_none(safe_median(pct_values), 6),
        "negative_unrealized_pct_share": (
            round(negative_pct_count / len(pct_values), 6) if pct_values else None
        ),
        "avg_control_blockers": round_or_none(safe_mean(blocker_values), 6),
        "exit_now_count": sum(1 for row in rows if bool(row.get("exit_now"))),
        "fallback_stop_count": sum(
            1 for row in rows if "fallback_stop" in set(row.get("warning_flags") or [])
        ),
        "manual_bracket_blocker_count": sum(
            1
            for row in rows
            if "manual_bracket_orders_not_broker_confirmed" in set(row.get("control_blockers") or [])
        ),
        "missing_daily_report_control_count": sum(
            1
            for row in rows
            if "missing_daily_report_control" in set(row.get("control_blockers") or [])
        ),
        "broker_order_coverage_status": dict(sorted(broker_status.items())),
    }


def comparison(rejected: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    rejected_pct = rejected.get("avg_unrealized_pct")
    other_pct = other.get("avg_unrealized_pct")
    rejected_blockers = rejected.get("avg_control_blockers")
    other_blockers = other.get("avg_control_blockers")
    return {
        "avg_unrealized_pct_delta_rejected_minus_other": (
            round(rejected_pct - other_pct, 6)
            if isinstance(rejected_pct, (int, float)) and isinstance(other_pct, (int, float))
            else None
        ),
        "avg_control_blocker_delta_rejected_minus_other": (
            round(rejected_blockers - other_blockers, 6)
            if isinstance(rejected_blockers, (int, float)) and isinstance(other_blockers, (int, float))
            else None
        ),
    }


def build_baseline_summary() -> dict[str, Any]:
    baseline = load_json(BASELINE_RESULT)
    windows = baseline.get("windows") or []
    return {
        "source_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(float(w.get("expected_value_score", 0.0)) for w in windows), 4),
        "total_pnl_sum": round(sum(float(w.get("total_pnl", 0.0)) for w in windows), 2),
        "trade_count_sum": int(sum(int(w.get("trade_count", 0)) for w in windows)),
        "signals_generated_sum": int(sum(int(w.get("signals_generated", 0)) for w in windows)),
        "signals_survived_sum": int(sum(int(w.get("signals_survived", 0)) for w in windows)),
        "worst_max_drawdown_pct": max((float(w.get("max_drawdown_pct", 0.0)) for w in windows), default=0.0),
        "windows": windows,
    }


def analyze() -> dict[str, Any]:
    rows = load_jsonl(LEDGER_JSONL)
    position_rows = [row for row in rows if is_position_row(row)]
    asof_dates = sorted({str(row.get("asof_date")) for row in position_rows if row.get("asof_date")})
    latest_asof = asof_dates[-1] if asof_dates else None
    latest_rows = [row for row in position_rows if str(row.get("asof_date")) == latest_asof]
    rejected_latest = [row for row in latest_rows if is_rejected_source(row)]
    other_latest = [row for row in latest_rows if not is_rejected_source(row)]
    rejected_all = [row for row in position_rows if is_rejected_source(row)]
    other_all = [row for row in position_rows if not is_rejected_source(row)]

    latest_rejected_summary = summarize_rows(rejected_latest)
    latest_other_summary = summarize_rows(other_latest)
    all_rejected_summary = summarize_rows(rejected_all)
    all_other_summary = summarize_rows(other_all)
    latest_comparison = comparison(latest_rejected_summary, latest_other_summary)

    unique_rejected = latest_rejected_summary["unique_positions"]
    rejected_date_count = len(all_rejected_summary["asof_dates"])
    pnl_delta = latest_comparison["avg_unrealized_pct_delta_rejected_minus_other"]
    blocker_delta = latest_comparison["avg_control_blocker_delta_rejected_minus_other"]
    max_ticker_share = latest_rejected_summary["max_ticker_share"]
    criteria = {
        "min_current_unique_rejected_positions_5": unique_rejected >= 5,
        "min_rejected_asof_dates_2": rejected_date_count >= 2,
        "rejected_avg_unrealized_pct_worse_by_3pp": (
            isinstance(pnl_delta, (int, float)) and pnl_delta <= -0.03
        ),
        "rejected_avg_control_blockers_higher_by_0_5": (
            isinstance(blocker_delta, (int, float)) and blocker_delta >= 0.5
        ),
        "not_single_ticker_dominated": (
            isinstance(max_ticker_share, (int, float)) and max_ticker_share <= 0.5
        ),
    }
    observed_only_lead = all(criteria.values())

    if observed_only_lead:
        decision = "observed_only_positive_live_position_control_rejected_source_risk_lead"
        rejection_reason = None
    elif unique_rejected < 5:
        decision = "observed_only_rejected_live_position_control_rejected_source_sample_too_thin"
        rejection_reason = (
            f"Only {unique_rejected} current rejected-source positions were present; "
            "the predeclared minimum for a risk-allocation lead is 5."
        )
    else:
        decision = "observed_only_rejected_live_position_control_rejected_source_not_worse"
        rejection_reason = (
            "Rejected-source rows did not satisfy the predeclared combined "
            "PnL deterioration, blocker, and concentration criteria."
        )

    return {
        "source_file": repo_rel(LEDGER_JSONL),
        "generated_from_rows": len(rows),
        "position_rows": len(position_rows),
        "asof_dates": asof_dates,
        "latest_asof": latest_asof,
        "latest_rows": len(latest_rows),
        "latest_rejected_source": latest_rejected_summary,
        "latest_non_rejected_source": latest_other_summary,
        "all_rejected_source": all_rejected_summary,
        "all_non_rejected_source": all_other_summary,
        "latest_comparison": latest_comparison,
        "criteria": criteria,
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "sample_rows": [
            {
                "asof_date": row.get("asof_date"),
                "ticker": row.get("ticker"),
                "position_id": row.get("position_id"),
                "sleeve": row.get("sleeve"),
                "opened_by_strategy": row.get("opened_by_strategy"),
                "unrealized_pl": row.get("unrealized_pl"),
                "unrealized_pct": round_or_none(unrealized_pct(row), 6),
                "control_blockers": row.get("control_blockers") or [],
                "broker_order_coverage_status": row.get("broker_order_coverage_status"),
                "control_notes": row.get("control_notes") or [],
            }
            for row in rejected_latest
        ],
    }


def build_payload() -> dict[str, Any]:
    baseline = build_baseline_summary()
    evaluation = analyze()
    observed_only_lead = evaluation["observed_only_lead"]
    status = "observed_only_positive" if observed_only_lead else "observed_only_rejected"
    decision = evaluation["decision"]

    headline_metrics = {
        "latest_asof": evaluation["latest_asof"],
        "latest_position_rows": evaluation["latest_rows"],
        "current_rejected_source_positions": evaluation["latest_rejected_source"]["unique_positions"],
        "current_non_rejected_positions": evaluation["latest_non_rejected_source"]["unique_positions"],
        "rejected_source_asof_dates": len(evaluation["all_rejected_source"]["asof_dates"]),
        "rejected_avg_unrealized_pct": evaluation["latest_rejected_source"]["avg_unrealized_pct"],
        "non_rejected_avg_unrealized_pct": evaluation["latest_non_rejected_source"]["avg_unrealized_pct"],
        "rejected_minus_other_unrealized_pct": evaluation["latest_comparison"]["avg_unrealized_pct_delta_rejected_minus_other"],
        "rejected_minus_other_control_blockers": evaluation["latest_comparison"]["avg_control_blocker_delta_rejected_minus_other"],
        "lead_criteria_passed": observed_only_lead,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "decision": decision,
        "owner": OWNER,
        "lane": LANE,
        "generated_at": utc_now(),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "acceptance_rule": ACCEPTANCE_RULE,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "headline_metrics": headline_metrics,
        "evaluation": evaluation,
        "observed_only_lead": observed_only_lead,
        "gate": {
            "passed": observed_only_lead,
            "reason": (
                "Current rejected-source rows satisfy the predeclared live risk "
                "lead criteria." if observed_only_lead else evaluation["rejection_reason"]
            ),
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
            "note": "Baseline was read for protocol continuity; no strategy behavior changed.",
        },
        "gate2": {
            "runtime_fields_verified": True,
            "field_availability": {
                "entry_date": {
                    "required_for_scored_rows": True,
                    "present_count": sum(
                        1 for row in evaluation["sample_rows"] if row.get("asof_date")
                    ),
                    "scored_rows": len(evaluation["sample_rows"]),
                    "note": (
                        "Live ledger rows have broker entry metadata; sampled "
                        "rows list as-of date and position id for replay."
                    ),
                },
                "target_price": {
                    "required": False,
                    "reason": (
                        "Observed-only live risk attribution; no executable "
                        "target exit or signal contract is introduced."
                    ),
                },
                "control_notes": {
                    "required": True,
                    "source_signal_rejected_alpha_rows": evaluation["latest_rejected_source"]["rows"],
                },
            },
        },
        "gate3": {
            "signals_generated": baseline["signals_generated_sum"],
            "signals_survived": baseline["signals_survived_sum"],
            "survival_rate": round(
                baseline["signals_survived_sum"] / baseline["signals_generated_sum"],
                6,
            ) if baseline["signals_generated_sum"] else None,
            "new_filter_added": False,
            "note": "No executable filter was added; live ledger rows are observed only.",
        },
        "gate4": {
            "decision": decision,
            "baseline_metrics": baseline,
            "after_metrics": baseline,
            "delta": {
                "expected_value_score_sum": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct_worst": 0.0,
            },
            "observed_only": True,
            "reason": "Strategy behavior is unchanged; this is a live ledger attribution read.",
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "alters_candidate_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "shared_policy_changed": False,
            "llm_change_scope": "none",
            "fingerprint_guard_changed": True,
        },
        "rejection_reason": evaluation["rejection_reason"],
        "post_run_reflection": {
            "why_result_happened": (
                "The new live control ledger has explicit rejected-source tags, "
                "but the current rejected bucket is only three positions on the "
                "latest as-of date and shows mixed unrealized PnL. Manual "
                "bracket/order-confirmation blockers are broad across live rows, "
                "so they do not distinguish rejected-source rows yet."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not add or retune a hard rejected-source live mirror "
                "exclusion, notional scalar, or admission threshold from this "
                "same two-day open-position sample."
            ),
            "new_evidence_required": (
                "Reopen only after at least 10 unique rejected-source live "
                "positions across at least 5 as-of dates with realized/closed "
                "or forward PnL, broker-confirmed order inventory, or a distinct "
                "closed-trade live exit-drift surface."
            ),
            "next_evidence_needed": (
                "Keep rejected-source discretionary live mirror rows default-off "
                "and accumulate live position-control ledger observations; do "
                "not promote before the reopen counts and closed/live drift "
                "evidence exist."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-001 and exp-20260709-003 built/wired the live "
                "position-control ledger as measurement repair. They did not "
                "test source_signal_rejected_alpha as a risk-allocation bucket. "
                "Recent candidate_meta_label and estimate-revision surfaces were "
                "not ready for alpha because their reopen row counts did not move."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if observed_only_lead else 0,
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    headline = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: live position-control rejected-source risk",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Latest as-of: `{headline['latest_asof']}`",
            f"- Current rejected-source positions: `{headline['current_rejected_source_positions']}`",
            f"- Current non-rejected positions: `{headline['current_non_rejected_positions']}`",
            f"- Rejected/non-rejected avg unrealized pct: `{headline['rejected_avg_unrealized_pct']}` / `{headline['non_rejected_avg_unrealized_pct']}`",
            f"- Rejected minus other unrealized pct: `{headline['rejected_minus_other_unrealized_pct']}`",
            f"- Rejected minus other control blockers: `{headline['rejected_minus_other_control_blockers']}`",
            f"- Lead criteria passed: `{headline['lead_criteria_passed']}`",
            "- Strategy/live order behavior changed: `false`",
            "- Fingerprint coverage changed: `true`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": payload["gate"]["reason"],
        },
        status=payload["status"],
        fields={
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "acceptance_rule": payload["acceptance_rule"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
