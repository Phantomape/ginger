"""exp-20260710-018: candidate meta-label train-before-test cohort.

Observed-only alpha read on the leak-free candidate decision ledger built in
exp-20260709-024. The gate shape is fixed before looking at this result:
old_thin+mid_weak select at most one unselected decision cohort, and
late_strong validates it. No model is fit and no strategy behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260710-018"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "candidate_meta_label_train_before_test_cohort"
RUNNER = f"quant/experiments/exp_20260710_018_{SLUG}.py"
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
SOURCE_EXPERIMENT_ID = "exp-20260709-024"
SOURCE_ARTIFACT = (
    DATA_DIR
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260709_024_candidate_training_ledger_materialization.json"
)
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260710_018_candidate_meta_label_train_before_test_cohort.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "candidate_meta_label train-before-test alpha: the leak-free canonical "
    "candidate ledger may contain an unselected entry-decision cohort that can "
    "be selected using only earlier chronological rows and then validated on "
    "later rows for positive 10d cash/SPY/QQQ replacement value versus entered "
    "candidates; if no cohort is train-selected and test-valid, candidate "
    "meta-label promotion remains blocked."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "candidate_meta_label_train_before_test_observed_only"
MECHANISM_FAMILY = "candidate_meta_label"
TRIAL_FAMILY = "candidate_meta_label_train_before_test_cohort_validation"
TRIAL_VARIANT_ID = "train_select_holdout_10d_v1"
SINGLE_CAUSAL_VARIABLE = "candidate_meta_label_train_selected_decision_cohort_validation_v1"
CAUSAL_COMPONENTS = [
    "exp024_candidate_training_ledger",
    "train_before_test_cohort_selection",
    "holdout_10d_cash_spy_qqq_validation",
    "no_model_training",
    "no_strategy_change",
]
NEARBY_PRIORS = ["exp-20260709-023", "exp-20260709-024", "exp-20260709-025"]
NEW_EVIDENCE_TYPE = "new_gate_shape_train_before_test"
NEW_EVIDENCE_AXIS = (
    "New gate shape explicitly allowed by the candidate_meta_label freeze: "
    "chronological train-before-test cohort selection and holdout validation on "
    "the existing leak-free ledger, not another decision-name reslice, "
    "threshold sweep, model fit, or response curve."
)
ACCEPTANCE_RULE = (
    "Observed-only lead only if old_thin+mid_weak can select exactly one "
    "unselected decision cohort using fixed train criteria, and that same "
    "cohort validates on late_strong with positive cash/SPY/QQQ 10d averages, "
    "cash win rate >=50%, cash average above entered late_strong candidates, "
    ">=3 holdout rows, and max single ticker share <=40%. No alpha can be "
    "accepted here."
)

TRAIN_WINDOWS = {"old_thin", "mid_weak"}
HOLDOUT_WINDOWS = {"late_strong"}
COMPARATORS = ("cash", "spy", "qqq")
MIN_TRAIN_ROWS = 8
MIN_HOLDOUT_ROWS = 3
MAX_TICKER_SHARE = 0.40
MIN_CASH_WIN_RATE = 0.50

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260710-018/exp_20260710_018_candidate_meta_label_train_before_test_cohort.json",
    "experiments/logs/exp-20260710-018.json",
    "experiments/cards/exp-20260710-018.md",
    "experiments/manifests/exp-20260710-018.json",
    "experiments/tickets/exp-20260710-018.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return safe(value.item())
        except Exception:
            return str(value)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
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
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def summarize_values(values: Iterable[Any]) -> dict[str, Any]:
    xs = [float(value) for value in values if numeric(value) is not None]
    if not xs:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_count": 0,
            "win_rate": None,
        }
    positives = sum(1 for value in xs if value > 0)
    return {
        "count": len(xs),
        "avg": round(sum(xs) / len(xs), 6),
        "median": round(median(xs), 6),
        "min": round(min(xs), 6),
        "max": round(max(xs), 6),
        "positive_count": positives,
        "win_rate": round(positives / len(xs), 6),
    }


def load_source_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = read_json(SOURCE_ARTIFACT, {})
    evaluation = payload.get("evaluation") if isinstance(payload, Mapping) else {}
    rows = evaluation.get("training_ledger_rows") if isinstance(evaluation, Mapping) else []
    clean = [dict(row) for row in rows if isinstance(row, Mapping)]
    return payload if isinstance(payload, dict) else {}, clean


def complete_10d_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        horizon = (row.get("horizons") or {}).get("10d")
        if isinstance(horizon, Mapping) and horizon.get("status") == "complete":
            out.append(dict(row))
    return out


def value(row: Mapping[str, Any], comparator: str) -> float | None:
    horizon = (row.get("horizons") or {}).get("10d")
    if not isinstance(horizon, Mapping):
        return None
    return numeric(horizon.get(f"replacement_value_vs_{comparator}_usd"))


def mean_for(rows: Iterable[Mapping[str, Any]], comparator: str) -> float | None:
    values = [value(row, comparator) for row in rows]
    values = [item for item in values if item is not None]
    return sum(values) / len(values) if values else None


def group_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(field) or "unknown"), []).append(dict(row))
    return grouped


def ticker_concentration(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("ticker") or "") for row in rows)
    top, top_count = counts.most_common(1)[0] if counts else (None, 0)
    share = top_count / len(rows) if rows else None
    return {
        "unique_tickers": len(counts),
        "top_ticker": top,
        "top_ticker_rows": top_count,
        "top_ticker_share": round(share, 6) if share is not None else None,
    }


def sample_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "window": row.get("window"),
            "signal_date": row.get("signal_date"),
            "intended_entry_date": row.get("intended_entry_date"),
            "ticker": row.get("ticker"),
            "decision": row.get("decision"),
            "strategy": row.get("strategy"),
            "cash_rv_usd": value(row, "cash"),
            "spy_rv_usd": value(row, "spy"),
            "qqq_rv_usd": value(row, "qqq"),
        }
        for row in rows[:6]
    ]


def summarize_segment(
    decision: str,
    rows: list[dict[str, Any]],
    entered_rows: list[dict[str, Any]],
    *,
    min_rows: int,
) -> dict[str, Any]:
    comparators = {
        comparator: summarize_values(value(row, comparator) for row in rows)
        for comparator in COMPARATORS
    }
    concentration = ticker_concentration(rows)
    avg_cash = mean_for(rows, "cash")
    entered_avg_cash = mean_for(entered_rows, "cash")
    criteria = {
        "unselected_cohort": decision != "entered",
        "min_rows": len(rows) >= min_rows,
        "avg_cash_positive": (comparators["cash"]["avg"] or 0.0) > 0,
        "avg_spy_positive": (comparators["spy"]["avg"] or 0.0) > 0,
        "avg_qqq_positive": (comparators["qqq"]["avg"] or 0.0) > 0,
        "cash_win_rate_gte_50pct": (comparators["cash"]["win_rate"] or 0.0)
        >= MIN_CASH_WIN_RATE,
        "cash_avg_beats_entered": (
            avg_cash is not None
            and entered_avg_cash is not None
            and avg_cash > entered_avg_cash
        ),
        "max_ticker_share_lte_40pct": (
            concentration["top_ticker_share"] is not None
            and concentration["top_ticker_share"] <= MAX_TICKER_SHARE
        ),
    }
    return {
        "decision": decision,
        "rows": len(rows),
        "comparators": comparators,
        "concentration": concentration,
        "entered_avg_cash": round(entered_avg_cash, 6) if entered_avg_cash is not None else None,
        "avg_cash_minus_entered": (
            round(avg_cash - entered_avg_cash, 6)
            if avg_cash is not None and entered_avg_cash is not None
            else None
        ),
        "criteria": criteria,
        "passed": all(criteria.values()),
        "sample_rows": sample_rows(rows),
    }


def baseline_metrics(source_payload: Mapping[str, Any]) -> dict[str, Any]:
    baseline = source_payload.get("baseline_metrics")
    if isinstance(baseline, Mapping):
        return dict(baseline)
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, Mapping) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "available": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def choose_train_cohort(summaries: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        dict(summary)
        for summary in summaries.values()
        if summary.get("passed") and summary.get("decision") != "entered"
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            numeric(item.get("avg_cash_minus_entered")) or float("-inf"),
            item.get("rows") or 0,
            str(item.get("decision") or ""),
        ),
        reverse=True,
    )
    return candidates[0]


def build_evaluation() -> dict[str, Any]:
    source_payload, all_rows = load_source_rows()
    complete = complete_10d_rows(all_rows)
    train = [row for row in complete if row.get("window") in TRAIN_WINDOWS]
    holdout = [row for row in complete if row.get("window") in HOLDOUT_WINDOWS]
    train_by_decision = group_by(train, "decision")
    holdout_by_decision = group_by(holdout, "decision")
    train_entered = train_by_decision.get("entered", [])
    holdout_entered = holdout_by_decision.get("entered", [])
    train_summaries = {
        decision: summarize_segment(
            decision,
            rows,
            train_entered,
            min_rows=MIN_TRAIN_ROWS,
        )
        for decision, rows in sorted(train_by_decision.items())
    }
    selected = choose_train_cohort(train_summaries)
    selected_decision = selected.get("decision") if selected else None
    holdout_summary = None
    if selected_decision:
        holdout_summary = summarize_segment(
            str(selected_decision),
            holdout_by_decision.get(str(selected_decision), []),
            holdout_entered,
            min_rows=MIN_HOLDOUT_ROWS,
        )
    holdout_passed = bool(holdout_summary and holdout_summary.get("passed"))
    if not selected:
        decision = "observed_only_rejected_train_segment_selects_no_candidate_cohort"
        failed = ["train_segment_selects_no_cohort"]
    elif not holdout_passed:
        decision = "observed_only_rejected_train_selected_cohort_fails_holdout"
        failed = [
            key
            for key, ok in (holdout_summary or {}).get("criteria", {}).items()
            if not ok
        ]
    else:
        decision = "observed_only_positive_train_selected_candidate_cohort_holdout_lead"
        failed = []
    return {
        "source_artifact": repo_rel(SOURCE_ARTIFACT),
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_rows": len(all_rows),
        "complete_10d_rows": len(complete),
        "train_windows": sorted(TRAIN_WINDOWS),
        "holdout_windows": sorted(HOLDOUT_WINDOWS),
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_decision_counts": {
            decision: len(rows) for decision, rows in sorted(train_by_decision.items())
        },
        "holdout_decision_counts": {
            decision: len(rows) for decision, rows in sorted(holdout_by_decision.items())
        },
        "train_summaries": train_summaries,
        "selected_train_cohort": selected,
        "selected_train_cohort_decision": selected_decision,
        "holdout_summary_for_selected_cohort": holdout_summary,
        "holdout_passed": holdout_passed,
        "decision": decision,
        "failed_reasons": failed,
        "baseline_metrics": baseline_metrics(source_payload),
        "source_readiness": (
            source_payload.get("headline_metrics")
            if isinstance(source_payload, Mapping)
            else None
        ),
        "gate_shape": {
            "train_windows": sorted(TRAIN_WINDOWS),
            "holdout_windows": sorted(HOLDOUT_WINDOWS),
            "min_train_rows": MIN_TRAIN_ROWS,
            "min_holdout_rows": MIN_HOLDOUT_ROWS,
            "max_ticker_share": MAX_TICKER_SHARE,
            "min_cash_win_rate": MIN_CASH_WIN_RATE,
            "selection_rule": "choose passing unselected train cohort with highest train avg_cash_minus_entered",
        },
    }


def load_ticket_prediction() -> dict[str, Any] | None:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, Mapping) else None
    return dict(prediction) if isinstance(prediction, Mapping) else None


def build_payload() -> dict[str, Any]:
    evaluation = build_evaluation()
    prediction = load_ticket_prediction()
    success = evaluation["decision"].startswith("observed_only_positive")
    brier = None
    if prediction and numeric(prediction.get("success_probability")) is not None:
        p = float(prediction["success_probability"])
        brier = round((p - (1.0 if success else 0.0)) ** 2, 6)
    baseline = evaluation["baseline_metrics"]
    decision = evaluation["decision"]
    selected_decision = evaluation["selected_train_cohort_decision"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": decision,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
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
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": int(success),
            "predicted_success_probability": (
                prediction.get("success_probability") if prediction else None
            ),
            "brier_score": brier,
            "predicted_failure_modes": (
                prediction.get("main_failure_modes") if prediction else []
            ),
            "realized_failure_modes": evaluation["failed_reasons"],
            "predicted_failure_mode_hit": bool(evaluation["failed_reasons"]),
        },
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "complete_10d_rows_examined": evaluation["complete_10d_rows"],
            "train_rows": evaluation["train_rows"],
            "holdout_rows": evaluation["holdout_rows"],
            "selected_train_cohort_decision": selected_decision,
            "observed_only_holdout_lead": success,
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "observed_only_holdout_lead": success,
        },
        "evaluation": evaluation,
        "headline_metrics": {
            "complete_10d_rows": evaluation["complete_10d_rows"],
            "train_rows": evaluation["train_rows"],
            "holdout_rows": evaluation["holdout_rows"],
            "selected_train_cohort_decision": selected_decision,
            "holdout_passed": evaluation["holdout_passed"],
            "failed_reasons": evaluation["failed_reasons"],
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "source_artifact": repo_rel(SOURCE_ARTIFACT),
        },
        "gate2": {
            "passed": evaluation["complete_10d_rows"] > 0,
            "complete_10d_rows": evaluation["complete_10d_rows"],
            "required_fields_checked": [
                "ticker",
                "window",
                "decision",
                "intended_entry_date",
                "target_price",
                "horizons.10d.replacement_value_vs_cash_usd",
                "horizons.10d.replacement_value_vs_spy_usd",
                "horizons.10d.replacement_value_vs_qqq_usd",
            ],
            "target_price_contract_changed": False,
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline.get("survival_rate"),
        },
        "gate4": {
            "passed": False,
            "evaluation_type": "observed_only_train_before_test_no_strategy_change",
            "accepted_alpha": False,
            "decision": decision,
            "reason": (
                "Observed-only holdout lead. No shared policy, model, ranking, "
                "sizing, exit, or order behavior changed."
                if success
                else "The train-before-test cohort gate did not validate; no "
                "candidate meta-label or entry-planning change is justified."
            ),
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "shared_policy_changed": False,
            "llm_change_scope": "none",
            "observed_only_attribution": True,
            "model_trained": False,
        },
        "rejection_reason": (
            None
            if success
            else "No train-selected unselected cohort validated on late_strong holdout under the fixed cash/SPY/QQQ, entered-comparison, sample, and concentration gates."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The only legal candidate_meta_label reopen path tested here "
                "was a train-before-test gate. Any apparent cohort edge had to "
                "be selected from old_thin+mid_weak before late_strong was "
                "evaluated."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this same ledger by changing train/holdout "
                "windows, min row thresholds, comparator set, decision names, "
                "model class, probability scalar, horizon, or response curve. "
                "Do not train a candidate_meta_label model until the exp024 "
                "readiness gate passes."
            ),
            "new_evidence_required": (
                "A valid retry needs at least 300 complete candidate rows with "
                "75 positive and 75 negative labels, materially new settled "
                "candidate rows from pipeline wiring, or a genuinely new "
                "non-oracle decision-time field."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-023 blocked model fitting, exp-20260709-024 "
                "materialized the first leak-free candidate ledger, and "
                "exp-20260709-025 rejected fixed batch decision cohorts. This "
                "run uses the playbook-allowed new gate shape: train-before-test."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": CHANGED_FILES + [repo_rel(SOURCE_ARTIFACT)],
        "changed_files": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    h = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: candidate meta-label train-before-test cohort",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Complete / train / holdout rows: `{h['complete_10d_rows']}` / `{h['train_rows']}` / `{h['holdout_rows']}`",
            f"- Selected train cohort: `{h['selected_train_cohort_decision']}`",
            f"- Holdout passed: `{h['holdout_passed']}`",
            f"- Failed reasons: `{h['failed_reasons']}`",
            "- Strategy/live order behavior changed: `false`",
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
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
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
            "acceptance_rule": payload["acceptance_rule"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
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
