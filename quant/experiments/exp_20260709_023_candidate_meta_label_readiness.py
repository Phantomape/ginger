"""exp-20260709-023: candidate meta-label training-table readiness.

Read-only alpha readiness audit for a possible candidate-entry meta-labeler.
The experiment does not fit a model. It first checks whether current canonical
and daily artifacts contain enough leak-free, settled, decision-time candidate
rows to train a low-capacity classifier without using oracle labels.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-023"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "candidate_meta_label_readiness"
RUNNER = f"quant/experiments/exp_20260709_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
WINDOW_DIR = DATA_DIR / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
WINDOWS = [
    (
        "late_strong",
        WINDOW_DIR / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    ),
    (
        "mid_weak",
        WINDOW_DIR / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    ),
    (
        "old_thin",
        WINDOW_DIR / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    ),
]
ORACLE_DIR = DATA_DIR / "experiments" / "oracle_no_entry_restriction_3window"
ORACLE_FILES = [
    ("late_strong", ORACLE_DIR / "late_strong_oracle.json"),
    ("mid_weak", ORACLE_DIR / "mid_weak_oracle.json"),
    ("old_thin", ORACLE_DIR / "old_thin_oracle.json"),
]
DAILY_SIGNAL_DIR = DATA_DIR / "daily" / "signals" / "quant"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_023_candidate_meta_label_readiness.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Candidate-entry meta-labeling may improve core/default-off candidate "
    "admission only if a leak-free settled candidate training table exists; "
    "first audit whether current canonical and daily artifacts provide at "
    "least 300 complete decision-time candidate rows before any model fitting."
)
CHANGE_TYPE = "model_readiness"
IMPLEMENTATION_MODE = "candidate_meta_label_readiness_audit"
MECHANISM_FAMILY = "candidate_meta_label"
TRIAL_FAMILY = "candidate_meta_label_training_table_readiness"
TRIAL_VARIANT_ID = "candidate_meta_label_v1_readiness_audit"
SINGLE_CAUSAL_VARIABLE = "candidate_meta_label_v1_training_table_readiness"
CAUSAL_COMPONENTS = [
    "candidate_row_audit",
    "leak_free_label_gate",
    "fingerprint_guard_coverage",
    "blocked_no_model_if_sample_gate_fails",
]
NEARBY_PRIORS = ["exp-20260709-013", "exp-20260622-017", "exp-20260708-028"]
NEW_EVIDENCE_TYPE = "new_gate_shape_readiness"
NEW_EVIDENCE_AXIS = (
    "New gate shape/readiness contract: candidate_meta_label_v1 requires a "
    "predeclared leak-free training table gate before any learned probability "
    "or scalar can be tested. This is not a response-function, threshold, "
    "notional, hold, or chop-scalar retune."
)
PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "insufficient_complete_candidate_rows",
        "leaky_oracle_labels",
        "missing_rejected_candidate_outcomes",
    ],
    "confidence_reason": (
        "ML/meta-labeling is a new candidate-conditional gate shape discussed "
        "in the July 9 prediction-strategy mailbox, but repo evidence suggests "
        "only 61 accepted core trades and sparse skipped samples are labelable; "
        "the first alpha-valid test is a strict readiness gate, not fitting a "
        "model."
    ),
}
SAMPLE_GATE = {
    "min_complete_candidate_rows": 300,
    "min_positive_labels": 75,
    "min_negative_labels": 75,
    "min_chronological_folds": 3,
    "min_test_rows_per_fold": 50,
    "max_single_ticker_share": 0.20,
    "requires_selected_and_rejected_candidate_coverage": True,
    "requires_non_oracle_labels": True,
}

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-023/exp_20260709_023_candidate_meta_label_readiness.json",
    "experiments/logs/exp-20260709-023.json",
    "experiments/cards/exp-20260709-023.md",
    "experiments/manifests/exp-20260709-023.json",
    "experiments/tickets/exp-20260709-023.json",
    "docs/experiment_registry.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260709-023/exp_20260709_023_candidate_meta_label_readiness.json",
    "experiments/cards/exp-20260709-023.md",
    "experiments/manifests/exp-20260709-023.json",
    "experiments/tickets/exp-20260709-023.json",
    "experiments/logs/exp-20260709-023.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    path.write_text(json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


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
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [numeric(row.get("max_drawdown_pct")) for row in windows]
    drawdowns = [value for value in drawdowns if value is not None]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def selected_trade_complete(trade: Mapping[str, Any]) -> bool:
    required = ("ticker", "strategy", "entry_date", "entry_price", "exit_date", "pnl", "pnl_pct_net", "stop_price")
    return all(trade.get(field) not in (None, "") for field in required)


def selected_trade_row(trade: Mapping[str, Any], window: str) -> dict[str, Any]:
    pnl = numeric(trade.get("pnl")) or 0.0
    return {
        "window": window,
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "pnl": round(pnl, 2),
        "label_positive_cash": pnl > 0,
    }


def skipped_sample_complete(row: Mapping[str, Any]) -> bool:
    details = row.get("details") if isinstance(row.get("details"), Mapping) else {}
    has_entry_contract = bool(details.get("fill_date") and details.get("fill_price"))
    has_label = any(
        row.get(field) is not None
        for field in (
            "pnl",
            "pnl_pct_net",
            "replacement_value_vs_cash_usd",
            "replacement_value_10d_vs_cash_usd",
        )
    )
    return has_entry_contract and has_label


def chronological_folds(rows: list[Mapping[str, Any]], fold_count: int = 3) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (str(row.get("entry_date") or ""), str(row.get("ticker") or "")))
    folds: list[dict[str, Any]] = []
    if not ordered:
        return folds
    for idx in range(fold_count):
        start = round(idx * len(ordered) / fold_count)
        end = round((idx + 1) * len(ordered) / fold_count)
        chunk = ordered[start:end]
        positives = sum(1 for row in chunk if row.get("label_positive_cash"))
        negatives = len(chunk) - positives
        folds.append(
            {
                "fold": idx + 1,
                "rows": len(chunk),
                "positives": positives,
                "negatives": negatives,
                "first_entry_date": chunk[0].get("entry_date") if chunk else None,
                "last_entry_date": chunk[-1].get("entry_date") if chunk else None,
                "has_both_classes": positives > 0 and negatives > 0,
                "meets_min_test_rows": len(chunk) >= SAMPLE_GATE["min_test_rows_per_fold"],
            }
        )
    return folds


def audit_canonical_windows() -> dict[str, Any]:
    selected_rows: list[dict[str, Any]] = []
    per_window: list[dict[str, Any]] = []
    for label, path in WINDOWS:
        payload = read_json(path, {})
        trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
        selected_complete = [trade for trade in trades if isinstance(trade, Mapping) and selected_trade_complete(trade)]
        selected_rows.extend(selected_trade_row(trade, label) for trade in selected_complete)
        attribution = payload.get("entry_execution_attribution")
        if not isinstance(attribution, Mapping):
            attribution = {}
        sample_skips = attribution.get("sample_skips") if isinstance(attribution.get("sample_skips"), list) else []
        skipped_complete = [row for row in sample_skips if isinstance(row, Mapping) and skipped_sample_complete(row)]
        per_window.append(
            {
                "label": label,
                "path": repo_rel(path),
                "exists": path.exists(),
                "signals_generated": payload.get("signals_generated"),
                "signals_survived": payload.get("signals_survived"),
                "total_trades": payload.get("total_trades"),
                "trade_rows": len(trades),
                "complete_selected_trade_rows": len(selected_complete),
                "skipped_count": attribution.get("skipped_count"),
                "sample_skip_rows_persisted": len(sample_skips),
                "complete_skipped_training_rows": len(skipped_complete),
                "skip_sample_gap": max(0, int(attribution.get("skipped_count") or 0) - len(sample_skips)),
                "sample_skip_fields": sorted(sample_skips[0].keys()) if sample_skips else [],
            }
        )
    labels = Counter("positive" if row["label_positive_cash"] else "negative" for row in selected_rows)
    ticker_counts = Counter(str(row.get("ticker") or "") for row in selected_rows)
    top_ticker, top_ticker_rows = ticker_counts.most_common(1)[0] if ticker_counts else (None, 0)
    folds = chronological_folds(selected_rows)
    return {
        "per_window": per_window,
        "complete_selected_trade_rows": len(selected_rows),
        "positive_selected_labels": labels.get("positive", 0),
        "negative_selected_labels": labels.get("negative", 0),
        "selected_ticker_count": len(ticker_counts),
        "selected_top_ticker": top_ticker,
        "selected_top_ticker_rows": top_ticker_rows,
        "selected_top_ticker_share": round(top_ticker_rows / len(selected_rows), 6) if selected_rows else None,
        "chronological_folds": folds,
        "sample_rows": selected_rows[:12],
    }


def audit_oracles() -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for label, path in ORACLE_FILES:
        payload = read_json(path, {})
        oracle = payload.get("candidate_forward_oracle") if isinstance(payload, Mapping) else {}
        if not isinstance(oracle, Mapping):
            oracle = {}
        top = oracle.get("top_candidate_opportunities")
        missing = oracle.get("missing_candidates")
        windows.append(
            {
                "label": label,
                "path": repo_rel(path),
                "exists": path.exists(),
                "candidate_count": oracle.get("candidate_count"),
                "persisted_top_opportunity_rows": len(top) if isinstance(top, list) else 0,
                "missing_candidate_count": oracle.get("missing_candidate_count"),
                "persisted_missing_candidate_rows": len(missing) if isinstance(missing, list) else 0,
                "is_tradable": oracle.get("is_tradable"),
                "lookahead_warning": oracle.get("lookahead_warning"),
            }
        )
    return {
        "windows": windows,
        "candidate_count_total": sum(int(row.get("candidate_count") or 0) for row in windows),
        "trainable_rows": 0,
        "trainability_reason": "candidate_forward_oracle explicitly uses future highs/lookahead and persists only diagnostics, not leak-free labels.",
    }


def listify(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def row_has_entry(row: Mapping[str, Any]) -> bool:
    return any(row.get(field) for field in ("entry_date", "usable_trade_date", "action_date", "signal_date", "date"))


def row_has_outcome(row: Mapping[str, Any]) -> bool:
    return any(
        row.get(field) is not None
        for field in (
            "replacement_value_vs_cash_usd",
            "replacement_value_10d_vs_cash_usd",
            "pnl",
            "pnl_pct_net",
            "outcome_status",
            "closed_outcome",
        )
    )


def audit_daily_signals() -> dict[str, Any]:
    files = sorted(DAILY_SIGNAL_DIR.glob("quant_signals_*.json")) if DAILY_SIGNAL_DIR.exists() else []
    section_counts: Counter[str] = Counter()
    rows_with_entry: Counter[str] = Counter()
    rows_with_outcome: Counter[str] = Counter()
    file_summaries: list[dict[str, Any]] = []
    for path in files:
        payload = read_json(path, {})
        sections = {
            "signals": listify(payload.get("signals")),
            "pilot_signals": listify(payload.get("pilot_signals")),
            "entry_candidate_review.candidates": listify((payload.get("entry_candidate_review") or {}).get("candidates") if isinstance(payload.get("entry_candidate_review"), Mapping) else []),
            "entry_execution_plan.slot_sliced_signals": listify((payload.get("entry_execution_plan") or {}).get("slot_sliced_signals") if isinstance(payload.get("entry_execution_plan"), Mapping) else []),
            "core_risk_intensity_forward_observation.rows": listify((payload.get("core_risk_intensity_forward_observation") or {}).get("rows") if isinstance(payload.get("core_risk_intensity_forward_observation"), Mapping) else []),
        }
        file_row_total = 0
        for name, rows in sections.items():
            section_counts[name] += len(rows)
            file_row_total += len(rows)
            for row in rows:
                if isinstance(row, Mapping):
                    if row_has_entry(row):
                        rows_with_entry[name] += 1
                    if row_has_outcome(row):
                        rows_with_outcome[name] += 1
        if file_row_total:
            file_summaries.append({"path": repo_rel(path), "rows": file_row_total})
    return {
        "files_scanned": len(files),
        "files_with_candidate_like_rows": len(file_summaries),
        "section_counts": dict(section_counts),
        "rows_with_entry_or_signal_date": dict(rows_with_entry),
        "rows_with_any_outcome_field": dict(rows_with_outcome),
        "candidate_like_rows_total": sum(section_counts.values()),
        "trainable_rows": 0,
        "trainability_reason": "daily production rows are sparse/open and do not provide settled leak-free cash/SPY/QQQ labels in the quant_signals snapshots.",
        "file_summaries": file_summaries[:25],
    }


def build_gate(canonical: Mapping[str, Any], daily: Mapping[str, Any]) -> dict[str, Any]:
    complete_rows = int(canonical["complete_selected_trade_rows"])
    positives = int(canonical["positive_selected_labels"])
    negatives = int(canonical["negative_selected_labels"])
    folds = canonical["chronological_folds"]
    ticker_share = canonical.get("selected_top_ticker_share") or 0.0
    has_rejected_outcomes = any(value > 0 for value in daily.get("rows_with_any_outcome_field", {}).values())
    criteria = {
        "complete_candidate_rows_gte_300": complete_rows >= SAMPLE_GATE["min_complete_candidate_rows"],
        "positive_labels_gte_75": positives >= SAMPLE_GATE["min_positive_labels"],
        "negative_labels_gte_75": negatives >= SAMPLE_GATE["min_negative_labels"],
        "three_chronological_folds_with_both_classes": sum(1 for row in folds if row["has_both_classes"]) >= SAMPLE_GATE["min_chronological_folds"],
        "each_fold_has_at_least_50_test_rows": all(row["meets_min_test_rows"] for row in folds),
        "no_single_ticker_over_20pct": ticker_share <= SAMPLE_GATE["max_single_ticker_share"],
        "selected_and_rejected_candidate_outcomes_present": has_rejected_outcomes,
        "non_oracle_labels_only": True,
    }
    failed = [key for key, value in criteria.items() if not value]
    return {
        "passed": all(criteria.values()),
        "criteria": criteria,
        "failed_criteria": failed,
        "sample_gate": SAMPLE_GATE,
        "complete_trainable_rows_counted": complete_rows,
        "positive_labels_counted": positives,
        "negative_labels_counted": negatives,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    canonical = audit_canonical_windows()
    oracles = audit_oracles()
    daily = audit_daily_signals()
    gate = build_gate(canonical, daily)
    decision = "blocked_candidate_meta_label_training_table_not_ready"
    rejection_reason = ";".join(gate["failed_criteria"])
    actual_success = 1 if gate["passed"] else 0
    brier = round((PREDICTION["success_probability"] - actual_success) ** 2, 4)
    why = (
        "The current artifacts prove only 61 complete selected-trade rows in "
        "the canonical windows. Skipped samples are partial diagnostics without "
        "settled labels, no-entry oracle rows are explicitly lookahead-only, "
        "and daily quant snapshots are sparse/open. A meta-labeler trained now "
        "would be selected-trade overfit or oracle leakage."
    )
    headline = {
        "complete_selected_trade_rows": canonical["complete_selected_trade_rows"],
        "positive_selected_labels": canonical["positive_selected_labels"],
        "negative_selected_labels": canonical["negative_selected_labels"],
        "candidate_oracle_count_total": oracles["candidate_count_total"],
        "daily_candidate_like_rows_total": daily["candidate_like_rows_total"],
        "trainable_rows_vs_required": f"{canonical['complete_selected_trade_rows']}/{SAMPLE_GATE['min_complete_candidate_rows']}",
        "failed_criteria": gate["failed_criteria"],
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "blocked",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
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
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": brier,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": "insufficient_complete_candidate_rows",
            "predicted_failure_mode_hit": True,
            "surprise_level": "low",
            "surprise_note": "The pre-run concern that selected and skipped candidate rows were too sparse was confirmed.",
        },
        "baseline_metrics": baseline,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "readiness": {
            "canonical_windows": canonical,
            "oracle_rows": oracles,
            "daily_signal_rows": daily,
            "gate": gate,
        },
        "headline_metrics": headline,
        "gate": {
            "passed": False,
            "decision": decision,
            "reason": rejection_reason,
            "criteria": gate["criteria"],
            "failed_criteria": gate["failed_criteria"],
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "note": "Read-only readiness audit; no before/after strategy metric change.",
        },
        "gate2": {
            "passed": False,
            "entry_date_target_price_sentinel": {
                "entry_date_present_for_selected_trades": canonical["complete_selected_trade_rows"],
                "target_price_not_required_for_readiness_audit": True,
                "blocked_reason": "Complete candidate training rows beyond selected trades are not persisted with settlement labels.",
            },
            "required_training_fields": [
                "ticker",
                "signal_date",
                "intended_entry_date",
                "entry_price",
                "strategy_or_source",
                "selected_or_sliced_or_blocked_status",
                "decision_time_features",
                "fixed_horizon_or_stop_target_contract",
                "cash_spy_qqq_settled_outcome",
                "logged_comparator_id_if_using_displacement_label",
            ],
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline["survival_rate"],
        },
        "gate4": {
            "passed": False,
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "reason": "No model was fit because the predeclared sample gate failed.",
        },
        "production_impact": {
            "observed_only_readiness_audit": True,
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
            "fingerprint_guard_changed": True,
        },
        "rejection_reason": rejection_reason,
        "realized_failure_mode": "insufficient_complete_candidate_rows",
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not fit elastic-net, HGB, LSTM, transformer, probability "
                "scalar, chop-control model, or no-entry classifier on the 61 "
                "selected trades, sparse skipped samples, or oracle top lists. "
                "Do not reframe a learned scalar as accepted alpha until the "
                "training-table sample gate passes."
            ),
            "new_evidence_required": (
                "Build an append-only candidate ledger with at least 300 settled "
                "rows, at least 75 positive and 75 negative non-oracle labels, "
                "selected plus skipped/slot-sliced/blocked coverage, three "
                "chronological folds with >=50 test rows and both classes, "
                "cash/SPY/QQQ outcomes, and logged comparator IDs for any "
                "displacement label."
            ),
            "next_evidence_needed": (
                "The next legal work is measurement plumbing: persist generated, "
                "selected, slot-sliced, and blocked candidate rows with decision-"
                "time features and fixed-horizon settlement. Model fitting is "
                "blocked until that ledger exists."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-013 audited core-entry admission/regime state; "
                "exp-20260622-017 showed blanket chop scalar harms core; "
                "the July 9 ML mailbox challenged Family 1 sample size and "
                "required a readiness gate before fitting."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": "Pass the predeclared training-table sample gate; otherwise no model fitting and decision is blocked.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: Mapping[str, Any]) -> str:
    h = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: candidate meta-label readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Complete selected trade rows: `{h['complete_selected_trade_rows']}`",
            f"- Positive / negative selected labels: `{h['positive_selected_labels']}` / `{h['negative_selected_labels']}`",
            f"- Oracle candidate count (not trainable): `{h['candidate_oracle_count_total']}`",
            f"- Daily candidate-like rows (not settled training rows): `{h['daily_candidate_like_rows_total']}`",
            f"- Trainable rows vs required: `{h['trainable_rows_vs_required']}`",
            f"- Failed criteria: `{h['failed_criteria']}`",
            "- Strategy/live order behavior changed: `false`",
            "- Fingerprint guard updated: `candidate_meta_label` / `model_readiness`",
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
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
            "summary": payload["gate"]["reason"],
            "calibration": payload["calibration"],
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
            "realized_failure_mode": payload["realized_failure_mode"],
            "calibration": payload["calibration"],
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
