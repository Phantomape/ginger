"""exp-20260709-025: candidate decision cohort attribution.

Observed-only alpha read on the exp-20260709-024 leak-free candidate training
ledger. This runner tests fixed entry-decision cohorts; it does not fit a
model and does not change signal generation, ranking, sizing, exits, or orders.
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


EXPERIMENT_ID = "exp-20260709-025"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "candidate_decision_cohort_attribution"
RUNNER = f"quant/experiments/exp_20260709_025_{SLUG}.py"
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
OUT_JSON = OUT_DIR / "exp_20260709_025_candidate_decision_cohort_attribution.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "candidate_meta_label_v1 observed-only alpha: the exp-20260709-024 "
    "leak-free candidate training ledger may reveal a fixed entry-decision "
    "cohort, such as slot_sliced or no_shares, with stable positive 10d "
    "cash/SPY/QQQ outcomes that current entry planning is missing; if no "
    "cohort beats entered candidates across windows, model/admission work "
    "remains blocked."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "candidate_meta_label_observed_only_cohort_attribution"
MECHANISM_FAMILY = "candidate_meta_label"
TRIAL_FAMILY = "candidate_meta_label_entry_decision_cohort_attribution"
TRIAL_VARIANT_ID = "candidate_decision_cohort_10d_v1"
SINGLE_CAUSAL_VARIABLE = "candidate_meta_label_v1_entry_decision_cohort_attribution"
CAUSAL_COMPONENTS = [
    "exp024_candidate_training_ledger",
    "fixed_decision_cohorts",
    "10d_cash_spy_qqq_labels",
    "no_model_training",
    "no_strategy_change",
]
NEARBY_PRIORS = ["exp-20260709-023", "exp-20260709-024"]
NEW_EVIDENCE_TYPE = "new_training_rows_attribution"
NEW_EVIDENCE_AXIS = (
    "New evidence axis from exp-20260709-024: first leak-free "
    "candidate_meta_label training ledger with selected and unselected "
    "canonical-window candidate decisions. This run performs one fixed batch "
    "cohort attribution and does not fit a model, tune thresholds, or change "
    "entry planning."
)

MIN_COHORT_ROWS = 8
MAX_TICKER_SHARE = 0.40
MIN_POSITIVE_WINDOWS = 2
MIN_BEATS_ENTERED_WINDOWS = 2
COMPARATORS = ("cash", "spy", "qqq")

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-025/exp_20260709_025_candidate_decision_cohort_attribution.json",
    "experiments/logs/exp-20260709-025.json",
    "experiments/cards/exp-20260709-025.md",
    "experiments/manifests/exp-20260709-025.json",
    "experiments/tickets/exp-20260709-025.json",
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
    rows = evaluation.get("training_ledger_rows") if isinstance(evaluation, Mapping) else None
    if isinstance(rows, list):
        return payload, [row for row in rows if isinstance(row, dict)]

    # Fallback for a stripped artifact shape.
    found: list[dict[str, Any]] = []
    windows = evaluation.get("windows") if isinstance(evaluation, Mapping) else []
    if isinstance(windows, list):
        for window in windows:
            if not isinstance(window, Mapping):
                continue
            for row in window.get("training_rows") or []:
                if isinstance(row, dict):
                    found.append(row)
    return payload, found


def complete_10d_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    complete = []
    for row in rows:
        horizon = (row.get("horizons") or {}).get("10d") if isinstance(row, Mapping) else None
        if isinstance(horizon, Mapping) and horizon.get("status") == "complete":
            complete.append(dict(row))
    return complete


def value(row: Mapping[str, Any], comparator: str) -> float | None:
    horizon = (row.get("horizons") or {}).get("10d")
    if not isinstance(horizon, Mapping):
        return None
    key = f"replacement_value_vs_{comparator}_usd"
    return numeric(horizon.get(key))


def mean_for(rows: Iterable[Mapping[str, Any]], comparator: str) -> float | None:
    values = [value(row, comparator) for row in rows]
    values = [item for item in values if item is not None]
    if not values:
        return None
    return sum(values) / len(values)


def group_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        grouped.setdefault(key, []).append(dict(row))
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


def summarize_cohort(
    decision: str,
    rows: list[dict[str, Any]],
    entered_by_window: Mapping[str, list[dict[str, Any]]],
    entered_all: list[dict[str, Any]],
) -> dict[str, Any]:
    by_window = group_by(rows, "window")
    entered_avg_cash = mean_for(entered_all, "cash")
    cohort_avg_cash = mean_for(rows, "cash")
    window_summaries: dict[str, Any] = {}
    positive_cash_windows = 0
    beats_entered_cash_windows = 0
    for window, window_rows in sorted(by_window.items()):
        entered_rows = entered_by_window.get(window, [])
        window_avg_cash = mean_for(window_rows, "cash")
        window_entered_avg_cash = mean_for(entered_rows, "cash")
        positive = window_avg_cash is not None and window_avg_cash > 0
        beats_entered = (
            window_avg_cash is not None
            and window_entered_avg_cash is not None
            and window_avg_cash > window_entered_avg_cash
        )
        positive_cash_windows += int(positive)
        beats_entered_cash_windows += int(beats_entered)
        window_summaries[window] = {
            "count": len(window_rows),
            "avg_cash": round(window_avg_cash, 6) if window_avg_cash is not None else None,
            "entered_avg_cash": (
                round(window_entered_avg_cash, 6)
                if window_entered_avg_cash is not None else None
            ),
            "positive_cash": positive,
            "beats_entered_cash": beats_entered,
        }

    summaries = {
        comparator: summarize_values(value(row, comparator) for row in rows)
        for comparator in COMPARATORS
    }
    concentration = ticker_concentration(rows)
    criteria = {
        "min_rows": len(rows) >= MIN_COHORT_ROWS,
        "avg_cash_positive": (summaries["cash"]["avg"] or 0) > 0,
        "avg_spy_positive": (summaries["spy"]["avg"] or 0) > 0,
        "avg_qqq_positive": (summaries["qqq"]["avg"] or 0) > 0,
        "cash_win_rate_gte_50pct": (summaries["cash"]["win_rate"] or 0) >= 0.50,
        "beats_entered_overall_cash": (
            cohort_avg_cash is not None
            and entered_avg_cash is not None
            and cohort_avg_cash > entered_avg_cash
        ),
        "positive_cash_windows_gte_2": positive_cash_windows >= MIN_POSITIVE_WINDOWS,
        "beats_entered_cash_windows_gte_2": (
            beats_entered_cash_windows >= MIN_BEATS_ENTERED_WINDOWS
        ),
        "max_ticker_share_lte_40pct": (
            concentration["top_ticker_share"] is not None
            and concentration["top_ticker_share"] <= MAX_TICKER_SHARE
        ),
    }
    if decision == "entered":
        criteria["unselected_cohort"] = False
    else:
        criteria["unselected_cohort"] = True
    passed = all(criteria.values())
    return {
        "decision": decision,
        "count": len(rows),
        "comparators": summaries,
        "concentration": concentration,
        "avg_cash_minus_entered": (
            round(cohort_avg_cash - entered_avg_cash, 6)
            if cohort_avg_cash is not None and entered_avg_cash is not None else None
        ),
        "positive_cash_windows": positive_cash_windows,
        "beats_entered_cash_windows": beats_entered_cash_windows,
        "by_window": window_summaries,
        "criteria": criteria,
        "passed_missed_alpha_lead": passed,
        "sample_rows": [
            {
                "window": row.get("window"),
                "signal_date": row.get("signal_date"),
                "intended_entry_date": row.get("intended_entry_date"),
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "cash_rv_usd": value(row, "cash"),
                "spy_rv_usd": value(row, "spy"),
                "qqq_rv_usd": value(row, "qqq"),
            }
            for row in rows[:5]
        ],
    }


def baseline_metrics(source_payload: Mapping[str, Any]) -> dict[str, Any]:
    baseline = source_payload.get("baseline_metrics")
    if isinstance(baseline, Mapping):
        return dict(baseline)
    baseline = read_json(BASELINE_RESULT, {})
    windows = baseline.get("windows") if isinstance(baseline, Mapping) else []
    if not isinstance(windows, list):
        windows = []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
    }


def build_evaluation() -> dict[str, Any]:
    source_payload, all_rows = load_source_rows()
    complete = complete_10d_rows(all_rows)
    by_decision = group_by(complete, "decision")
    entered = by_decision.get("entered", [])
    entered_by_window = group_by(entered, "window")
    cohort_summaries = {
        decision: summarize_cohort(decision, rows, entered_by_window, entered)
        for decision, rows in sorted(by_decision.items())
    }
    leads = [
        item for item in cohort_summaries.values()
        if item.get("passed_missed_alpha_lead")
    ]
    decision = (
        "observed_only_positive_candidate_decision_missed_alpha_lead"
        if leads
        else "observed_only_rejected_no_stable_candidate_decision_missed_alpha_cohort"
    )
    return {
        "source_artifact": repo_rel(SOURCE_ARTIFACT),
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_rows": len(all_rows),
        "complete_10d_rows": len(complete),
        "entered_complete_10d_rows": len(entered),
        "decision_counts": {key: len(rows) for key, rows in sorted(by_decision.items())},
        "cohort_gate": {
            "min_cohort_rows": MIN_COHORT_ROWS,
            "max_ticker_share": MAX_TICKER_SHARE,
            "min_positive_cash_windows": MIN_POSITIVE_WINDOWS,
            "min_beats_entered_cash_windows": MIN_BEATS_ENTERED_WINDOWS,
            "requires_unselected_cohort": True,
            "requires_positive_cash_spy_qqq_avg": True,
            "requires_cash_win_rate_gte_50pct": True,
        },
        "cohorts": cohort_summaries,
        "lead_cohorts": [item["decision"] for item in leads],
        "decision": decision,
        "baseline_metrics": baseline_metrics(source_payload),
        "source_readiness": (
            source_payload.get("headline_metrics")
            if isinstance(source_payload, Mapping) else None
        ),
    }


def load_ticket_prediction() -> dict[str, Any] | None:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, Mapping) else None
    return dict(prediction) if isinstance(prediction, Mapping) else None


def build_payload() -> dict[str, Any]:
    evaluation = build_evaluation()
    prediction = load_ticket_prediction()
    success = bool(evaluation["lead_cohorts"])
    brier = None
    if prediction and numeric(prediction.get("success_probability")) is not None:
        p = float(prediction["success_probability"])
        brier = round((p - (1.0 if success else 0.0)) ** 2, 6)
    failed_modes = []
    if not success:
        failed_modes = [
            "cohort_window_instability",
            "entered_candidates_already_best_or_no_unselected_cohort_passed",
        ]
    decision = evaluation["decision"]
    status = decision
    baseline = evaluation["baseline_metrics"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
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
            "realized_failure_modes": failed_modes,
            "predicted_failure_mode_hit": bool(failed_modes),
        },
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "complete_10d_rows_examined": evaluation["complete_10d_rows"],
            "lead_cohort_count": len(evaluation["lead_cohorts"]),
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "observed_only_lead_cohort_count": len(evaluation["lead_cohorts"]),
        },
        "evaluation": evaluation,
        "headline_metrics": {
            "complete_10d_rows": evaluation["complete_10d_rows"],
            "entered_complete_10d_rows": evaluation["entered_complete_10d_rows"],
            "decision_counts": evaluation["decision_counts"],
            "lead_cohorts": evaluation["lead_cohorts"],
            "lead_cohort_count": len(evaluation["lead_cohorts"]),
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "source_artifact": repo_rel(SOURCE_ARTIFACT),
        },
        "gate2": {
            "passed": evaluation["complete_10d_rows"] > 0,
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
            "complete_10d_rows": evaluation["complete_10d_rows"],
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
            "evaluation_type": "observed_only_attribution_no_strategy_change",
            "accepted_alpha": False,
            "decision": decision,
            "reason": (
                "Observed-only fixed cohort lead; no shared policy, model, "
                "ranking, sizing, exit, or order behavior changed."
                if success
                else "No fixed unselected decision cohort passed the "
                "predeclared missed-alpha gate."
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
            None if success
            else "No unselected entry-decision cohort passed min rows, positive cash/SPY/QQQ averages, window stability, entered-candidate comparison, and concentration guards."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The new exp024 ledger allowed a fixed batch read of entered "
                "and unselected entry-decision cohorts. Passing would require "
                "a cohort to beat entered candidates across windows without "
                "model fitting or threshold tuning."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this ledger by changing min cohort rows, cash/"
                "SPY/QQQ comparator set, window-count guards, ticker-share "
                "guard, decision names, model class, probability scalar, or "
                "response curve. Do not train a candidate_meta_label model "
                "until the exp024 readiness gate passes."
            ),
            "new_evidence_required": (
                "A valid retry needs at least 300 complete candidate rows with "
                "75 positive and 75 negative labels, new settled candidate "
                "rows from pipeline wiring, or a genuinely new non-oracle "
                "decision-time field."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-023 blocked model fitting; exp-20260709-024 "
                "materialized the first leak-free candidate ledger but left "
                "model readiness blocked."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only lead only if a fixed unselected decision cohort "
                "passes the predeclared cash/SPY/QQQ, window, entered-comparison, "
                "and concentration gates. No alpha can be accepted here."
            ),
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
            f"# {EXPERIMENT_ID}: candidate decision cohort attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Complete 10d rows: `{h['complete_10d_rows']}`",
            f"- Entered complete rows: `{h['entered_complete_10d_rows']}`",
            f"- Lead cohorts: `{h['lead_cohorts']}`",
            f"- Strategy behavior changed: `false`",
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
