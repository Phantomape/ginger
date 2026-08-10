"""Canonical, read-only experiment history utilities.

This module loads and deduplicates experiment records, calculates immutable
trial counts, and derives anti-repeat/freeze evidence.  It deliberately does
not rank historical winners or recommend what the alpha search should try next.

It is read-only: no trading logic, backtest logic, production policy, or search
priority changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]

METRIC_BUCKETS = (
    "after_metrics",
    "candidate_metrics",
    "delta_metrics",
    "deltas",
    "before_metrics",
    "baseline_metrics",
)

DELTA_ALIASES = {
    "expected_value_score": (
        "expected_value_score",
        "expected_value_score_delta",
        "aggregate_ev_delta",
        "ev_delta",
    ),
    "total_pnl": ("total_pnl", "total_pnl_delta", "aggregate_pnl_delta", "pnl_delta"),
    "pnl": ("pnl", "pnl_delta", "total_pnl_delta", "aggregate_pnl_delta"),
    "max_drawdown_pct": ("max_drawdown_pct", "max_drawdown_pct_delta"),
    "survival_rate": ("survival_rate", "survival_rate_delta"),
    "trade_count": ("trade_count", "trade_count_delta", "trades_delta"),
    "trades": ("trades", "trades_delta", "trade_count_delta"),
}

TRIAL_METADATA_KEYS = (
    "mechanism_family",
    "trial_family",
    "trial_variant_id",
    "changed_variable",
    "prior_trial_count",
    "nearby_prior_experiments",
    "multiple_testing_risk_bucket",
    "new_evidence_type",
)

MEASUREMENT_REPAIR_TOKENS = (
    "measurement",
    "instrumentation",
    "logging",
    "documentation",
    "data_audit",
    "data audit",
    "coverage",
    "parity",
    "known_bias",
    "process",
    "replay_fix",
    "data_gap",
    "oracle_diagnostics",
    "observed_only",
    "diagnostic",
    "data_collection",
    "triage",
)

STRATEGY_ITERATION_TOKENS = (
    "alpha",
    "entry",
    "exit",
    "ranking",
    "rank",
    "slot",
    "queue",
    "allocation",
    "risk",
    "llm",
    "event",
    "sleeve",
    "candidate_pool",
    "universe",
    "target",
    "notional",
    "shadow",
)


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"_parse_error": True, "raw": line[:500]})
    return rows


def load_experiment_logs(root=DEFAULT_ROOT):
    """Load experiment records from JSONL and per-experiment JSON logs."""
    root = Path(root)
    records = []

    jsonl_path = root / "docs" / "experiment_log.jsonl"
    for row in _read_jsonl(jsonl_path):
        row.setdefault("_source", str(jsonl_path))
        records.append(row)

    log_dirs = [
        root / "experiments" / "logs",
        root / "docs" / "experiments" / "logs",
    ]
    for logs_dir in log_dirs:
        if not logs_dir.exists():
            continue
        for path in sorted(logs_dir.glob("*.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                row.setdefault("_source", str(path))
                records.append(row)

    return records


def _decision(record):
    return str(record.get("decision") or record.get("status") or "unknown").lower()


def decision_bucket(record):
    """Return the one neutral outcome bucket used by every history consumer.

    Historical records mix boolean flags, status values and richer decision
    strings.  Keeping this precedence in one place prevents the frozen-family
    counters from disagreeing with trial accounting about whether a row was
    accepted.  The bucket is an audit fact; it is never a winner score.
    """

    if record.get("accepted") is True or record.get("accepted_alpha") is True:
        return "accepted"
    status = str(record.get("status") or "").strip().lower()
    decision = str(record.get("decision") or "").strip().lower()
    if (
        status in {"accepted", "accept", "promoted"}
        or decision in {"accepted", "accept", "promoted"}
        or status.startswith(("accepted_", "accept_", "promoted_"))
        or decision.startswith(("accepted_", "accept_", "promoted_"))
    ):
        return "accepted"
    if "positive_replay_lead" in decision:
        return "lead"
    if status.startswith("block") or "blocked" in decision:
        return "blocked"
    return "rejected"


def _record_text(record):
    return " ".join(
        str(record.get(k, ""))
        for k in [
            "experiment_id",
            "hypothesis",
            "change_summary",
            "change_type",
            "component",
            "notes",
            "lane",
            "decision",
            "status",
        ]
    ).lower()


def _is_accepted_decision(record):
    return decision_bucket(record) == "accepted"


def _is_rejected_decision(record):
    return decision_bucket(record) == "rejected"


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _change_type(record):
    value = record.get("change_type") or record.get("category") or "unknown"
    return str(value).lower().replace(" ", "_")


def _component(record):
    return str(record.get("component") or record.get("primary_component") or "unknown")


def _normalize_label(value, default="unknown"):
    text = str(value or "").strip()
    if not text:
        return default
    return "_".join(text.lower().replace("-", "_").split())


def _mechanism_family(record):
    return _normalize_label(
        record.get("mechanism_family")
        or record.get("trial_family")
        or classify_research_family(record)
    )


def _trial_family(record):
    return _normalize_label(
        record.get("trial_family")
        or record.get("mechanism_family")
        or classify_research_family(record)
    )


def _changed_variable(record):
    direct = record.get("changed_variable") or record.get("single_causal_variable")
    if direct:
        return _normalize_label(direct)

    parameters = _as_dict(record.get("parameters"))
    if len(parameters) == 1:
        return _normalize_label(next(iter(parameters)))

    return _normalize_label(_change_type(record))


def _trial_variant_id(record):
    return str(record.get("trial_variant_id") or _experiment_id(record))


def _new_evidence_type(record):
    return _normalize_label(record.get("new_evidence_type"), default="not_declared")


def _declared_prior_trial_count(record):
    return int(max(0, _float(record.get("prior_trial_count"), 0.0)))


def _nearby_prior_experiment_count(record):
    value = record.get("nearby_prior_experiments")
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str) and value.strip():
        return len([part for part in value.split(",") if part.strip()])
    return 0


def _dedupe_records_by_experiment_id(records):
    """Keep one record per experiment id for trial counting.

    load_experiment_logs intentionally loads both JSONL and per-experiment logs.
    Trial accounting should count research attempts, not storage copies.
    """
    by_id = {}
    for record in records:
        experiment_id = _experiment_id(record)
        current = by_id.get(experiment_id)
        if current is None:
            by_id[experiment_id] = record
            continue
        if len(json.dumps(record, sort_keys=True, default=str)) > len(
            json.dumps(current, sort_keys=True, default=str)
        ):
            by_id[experiment_id] = record
    return list(by_id.values())


def _delta(record, key):
    delta = _as_dict(record.get("delta_metrics"))
    if not delta:
        delta = _as_dict(record.get("deltas"))
    for alias in DELTA_ALIASES.get(key, (key,)):
        if alias in delta:
            return _float(delta.get(alias), 0.0)
        if alias in record:
            return _float(record.get(alias), 0.0)

    before = _as_dict(record.get("before_metrics"))
    if not before:
        before = _as_dict(record.get("baseline_metrics"))
    after = _as_dict(record.get("after_metrics"))
    if not after:
        after = _as_dict(record.get("candidate_metrics"))
    if key in before or key in after:
        return _float(after.get(key), 0.0) - _float(before.get(key), 0.0)
    return 0.0


def _metric(record, bucket, key):
    values = _as_dict(record.get(bucket))
    return _float(values.get(key), None)


def _experiment_id(record):
    return str(record.get("experiment_id") or record.get("id") or Path(record.get("_source", "unknown")).stem)


def _sample_count(record):
    for bucket in ("after_metrics", "candidate_metrics", "delta_metrics", "before_metrics"):
        value = _metric(record, bucket, "trade_count")
        if value is not None:
            return value
        value = _metric(record, bucket, "trades")
        if value is not None:
            return value
    return None


def _production_impact(record):
    impact = record.get("production_impact") or {}
    return impact if isinstance(impact, dict) else {}


def is_measurement_repair_record(record):
    return any(token in _record_text(record) for token in MEASUREMENT_REPAIR_TOKENS)


def is_strategy_iteration_record(record):
    text = _record_text(record)
    if is_measurement_repair_record(record):
        return False
    lane = str(record.get("lane") or "").lower()
    if "alpha" in lane or "universe_scout" in lane:
        return True
    return any(token in text for token in STRATEGY_ITERATION_TOKENS)


def build_data_quality_warnings(records):
    metric_type_issues = []
    for record in records:
        for bucket in METRIC_BUCKETS:
            if bucket not in record:
                continue
            value = record.get(bucket)
            if value is None or isinstance(value, dict):
                continue
            metric_type_issues.append({
                "experiment_id": _experiment_id(record),
                "bucket": bucket,
                "actual_type": type(value).__name__,
                "value_preview": str(value)[:160],
                "source": record.get("_source"),
            })

    return {
        "non_dict_metric_buckets": {
            "count": len(metric_type_issues),
            "examples": metric_type_issues[:10],
            "meaning_zh": (
                "部分旧实验日志把 metrics 字段写成了字符串引用，而不是指标字典。"
                "meta report 会把这些字段当作缺失值处理，并在这里列出样例。"
            ),
        }
    }


def classify_research_family(record):
    """Infer a durable research family from log metadata and text."""
    text = _record_text(record)

    if "cap" in text or "position_cap" in text:
        return "position_cap_or_cap_release"
    if "topup" in text or "top-up" in text or "risk_scalar" in text or "risk_budget" in text:
        return "risk_scalar_or_topup"
    if "slot" in text or "ranking" in text or "priority" in text:
        return "slot_or_ranking"
    if "filter" in text or "gate" in text or "guard" in text:
        return "filter_or_gate"
    if "exit" in text or "target" in text or "trailing" in text or "time_stop" in text:
        return "exit_policy"
    if "llm" in text or "prompt" in text or "news" in text or "event" in text:
        return "event_or_llm"
    if "space" in text or "pilot" in text or "sleeve" in text:
        return "pilot_or_sleeve"
    if "ticker" in text or "tsm" in text or "isrg" in text:
        return "ticker_specific"
    return _change_type(record)


def build_freeze_candidates(records):
    """Find repeatedly rejected research families without winner scoring.

    Freeze status is an anti-repeat fact.  It depends only on deduplicated trial
    outcomes and never on a score that could become a search-priority signal.
    """
    grouped = defaultdict(list)
    for record in _dedupe_records_by_experiment_id(records):
        grouped[_trial_family(record)].append(record)

    candidates = []
    for family, rows in sorted(grouped.items()):
        accepted = sum(1 for row in rows if _is_accepted_decision(row))
        accept_rate = accepted / len(rows) if rows else 0.0
        if len(rows) >= 3 and accept_rate <= 0.2:
            candidates.append({
                "scope": "family",
                "name": family,
                "reason": "low_accept_rate",
                "accept_rate": round(accept_rate, 4),
                "experiments": len(rows),
            })
    return sorted(candidates, key=lambda row: (-row["experiments"], row["name"]))


def _multiple_testing_risk_bucket(trial_count, accepted_count, new_evidence_types):
    declared_new_evidence = {
        item for item in new_evidence_types if item and item != "not_declared"
    }
    accept_rate = accepted_count / trial_count if trial_count else 0.0
    if trial_count >= 20:
        return "high"
    if trial_count >= 10 and not declared_new_evidence:
        return "high"
    if trial_count >= 8:
        return "moderate"
    if trial_count >= 5 and accept_rate <= 0.2:
        return "moderate"
    if trial_count >= 3:
        return "low"
    return "minimal"


def _trial_retry_guidance(trial_count, accepted_count, risk_bucket, new_evidence_types):
    declared_new_evidence = {
        item for item in new_evidence_types if item and item != "not_declared"
    }
    accept_rate = accepted_count / trial_count if trial_count else 0.0
    if risk_bucket == "high":
        return "freeze_nearby_retries_until_new_forward_or_field_evidence"
    if risk_bucket == "moderate" and not declared_new_evidence:
        return "require_new_evidence_type_before_more_parameter_search"
    if trial_count >= 5 and accept_rate <= 0.2:
        return "allow_only_materially_different_discriminator"
    return "allow_with_standard_gate4_and_trial_disclosure"


def build_trial_accounting(records):
    """Summarize research degrees of freedom by trial family and variable.

    This is an audit surface, not strategy logic. It helps agents understand how
    much nearby search has already happened before they run another experiment.
    """
    strategy_records = _dedupe_records_by_experiment_id(
        [r for r in records if is_strategy_iteration_record(r)]
    )
    groups = defaultdict(list)
    for record in strategy_records:
        groups[(_trial_family(record), _changed_variable(record))].append(record)

    group_rows = []
    for (trial_family, changed_variable), rows in groups.items():
        accepted = [r for r in rows if _is_accepted_decision(r)]
        rejected = [r for r in rows if _is_rejected_decision(r)]
        ev_deltas = [_delta(r, "expected_value_score") for r in rows]
        pnl_deltas = [_delta(r, "total_pnl") or _delta(r, "pnl") for r in rows]
        new_evidence_types = sorted({_new_evidence_type(r) for r in rows})
        declared_prior_trial_count = max(
            [_declared_prior_trial_count(r) for r in rows] or [0]
        )
        nearby_prior_experiment_count = sum(
            _nearby_prior_experiment_count(r) for r in rows
        )
        effective_trial_count = max(
            len(rows),
            declared_prior_trial_count + 1,
            nearby_prior_experiment_count + len(rows),
        )
        risk_bucket = _multiple_testing_risk_bucket(
            effective_trial_count,
            len(accepted),
            new_evidence_types,
        )
        most_recent_failure = None
        if rejected:
            failure = rejected[-1]
            most_recent_failure = {
                "experiment_id": _experiment_id(failure),
                "decision": _decision(failure),
                "rejection_reason": str(
                    failure.get("rejection_reason")
                    or failure.get("next_evidence_needed")
                    or failure.get("next_retry_requires")
                    or ""
                )[:500],
            }

        group_rows.append({
            "trial_family": trial_family,
            "changed_variable": changed_variable,
            "mechanism_families": sorted({_mechanism_family(r) for r in rows}),
            "experiments": len(rows),
            "effective_trial_count": effective_trial_count,
            "accepted": len(accepted),
            "rejected": len(rejected),
            "accept_rate": round(len(accepted) / len(rows), 4) if rows else 0.0,
            "sum_ev_delta": round(sum(ev_deltas), 4),
            "sum_pnl_delta": round(sum(pnl_deltas), 2),
            "multiple_testing_risk_bucket": risk_bucket,
            "new_evidence_types": new_evidence_types,
            "declared_prior_trial_count_max": declared_prior_trial_count,
            "nearby_prior_experiment_count": nearby_prior_experiment_count,
            "recent_experiments": [_experiment_id(r) for r in rows[-5:]],
            "most_recent_failure": most_recent_failure,
            "retry_guidance": _trial_retry_guidance(
                effective_trial_count,
                len(accepted),
                risk_bucket,
                new_evidence_types,
            ),
        })

    risk_rank = {"high": 0, "moderate": 1, "low": 2, "minimal": 3}
    group_rows = sorted(
        group_rows,
        key=lambda row: (
            risk_rank.get(row["multiple_testing_risk_bucket"], 9),
            -row["effective_trial_count"],
            row["trial_family"],
            row["changed_variable"],
        ),
    )

    missing_counts = {key: 0 for key in TRIAL_METADATA_KEYS}
    for record in strategy_records:
        for key in TRIAL_METADATA_KEYS:
            if key not in record:
                missing_counts[key] += 1

    return {
        "read_only": True,
        "records_counted": len(strategy_records),
        "group_count": len(group_rows),
        "grouping": "trial_family + changed_variable",
        "missing_metadata_counts": missing_counts,
        "high_risk_groups": [
            row for row in group_rows
            if row["multiple_testing_risk_bucket"] == "high"
        ],
        "groups": group_rows,
        "notes": [
            "Trial accounting counts research attempts, not storage copies.",
            "The bucket is a multiple-testing risk warning, not a trading signal.",
            "High-risk groups need new forward evidence, a new production-visible field, or a materially different discriminator before another nearby retry.",
        ],
    }


def _prediction(record):
    value = record.get("prediction")
    return value if isinstance(value, dict) else {}


def _calibration(record):
    value = record.get("calibration")
    return value if isinstance(value, dict) else {}


def _prediction_probability(record):
    prediction = _prediction(record)
    calibration = _calibration(record)
    value = prediction.get("success_probability")
    if value is None:
        value = calibration.get("predicted_success_probability")
    return _float(value, None)


def _actual_success(record):
    decision = _decision(record)
    if _is_accepted_decision(record):
        return 1
    if _is_rejected_decision(record):
        return 0
    if decision == "rolled_back":
        return 0
    return None


def _calibration_direction(probability, actual_success):
    if probability is None or actual_success is None:
        return "not_scored"
    predicted_success = probability >= 0.5
    if predicted_success and not actual_success:
        return "overconfident"
    if not predicted_success and actual_success:
        return "underconfident"
    return "directionally_calibrated"


def build_prediction_calibration(records):
    """Summarize pre-run prediction quality.

    This is a meta-learning audit surface only. It must never be used directly
    as a trading signal, ranking feature, or sizing scalar.
    """
    final_records = _dedupe_records_by_experiment_id([
        r for r in records if _actual_success(r) is not None
    ])
    scored = []
    missing_prediction = []
    for record in final_records:
        probability = _prediction_probability(record)
        actual_success = _actual_success(record)
        if probability is None:
            missing_prediction.append(_experiment_id(record))
            continue
        brier = (probability - actual_success) ** 2
        prediction = _prediction(record)
        calibration = _calibration(record)
        scored.append({
            "experiment_id": _experiment_id(record),
            "family": _mechanism_family(record),
            "trial_family": _trial_family(record),
            "success_probability": round(probability, 4),
            "actual_success": actual_success,
            "decision": _decision(record),
            "brier_score": round(brier, 6),
            "calibration_direction": _calibration_direction(probability, actual_success),
            "expected_ev_delta": (
                prediction.get("expected_ev_delta")
                if prediction.get("expected_ev_delta") is not None
                else calibration.get("expected_ev_delta")
            ),
            "actual_ev_delta": _delta(record, "expected_value_score"),
            "expected_pnl_delta": (
                prediction.get("expected_pnl_delta")
                if prediction.get("expected_pnl_delta") is not None
                else calibration.get("expected_pnl_delta")
            ),
            "actual_pnl_delta": _delta(record, "total_pnl") or _delta(record, "pnl"),
        })

    by_family = defaultdict(list)
    for row in scored:
        by_family[row["family"]].append(row)

    family_rows = []
    for family, rows in by_family.items():
        actual_successes = [row["actual_success"] for row in rows]
        family_rows.append({
            "family": family,
            "experiments": len(rows),
            "avg_predicted_success_probability": round(
                sum(row["success_probability"] for row in rows) / len(rows),
                4,
            ),
            "actual_accept_rate": round(sum(actual_successes) / len(rows), 4),
            "avg_brier_score": round(
                sum(row["brier_score"] for row in rows) / len(rows),
                6,
            ),
            "overconfident": sum(
                1 for row in rows if row["calibration_direction"] == "overconfident"
            ),
            "underconfident": sum(
                1 for row in rows if row["calibration_direction"] == "underconfident"
            ),
            "recent_examples": [row["experiment_id"] for row in rows[-5:]],
        })
    family_rows = sorted(
        family_rows,
        key=lambda row: (row["avg_brier_score"], -row["experiments"], row["family"]),
    )

    avg_brier = (
        sum(row["brier_score"] for row in scored) / len(scored)
        if scored else None
    )
    return {
        "read_only": True,
        "records_counted": len(final_records),
        "records_with_prediction": len(scored),
        "records_missing_prediction": len(missing_prediction),
        "prediction_coverage": round(len(scored) / len(final_records), 4)
        if final_records else 0.0,
        "avg_brier_score": round(avg_brier, 6) if avg_brier is not None else None,
        "direction_counts": {
            "overconfident": sum(
                1 for row in scored if row["calibration_direction"] == "overconfident"
            ),
            "underconfident": sum(
                1 for row in scored if row["calibration_direction"] == "underconfident"
            ),
            "directionally_calibrated": sum(
                1 for row in scored
                if row["calibration_direction"] == "directionally_calibrated"
            ),
        },
        "by_family": family_rows,
        "worst_brier_examples": sorted(
            scored,
            key=lambda row: row["brier_score"],
            reverse=True,
        )[:10],
        "missing_prediction_examples": missing_prediction[:20],
        "notes": [
            "Brier score compares pre-run success_probability with accepted/rejected outcomes.",
            "Observed-only rows are excluded because they intentionally make no strategy success claim.",
            "Prediction calibration is for meta-learning and research process quality only.",
        ],
    }


def build_history_report(root=DEFAULT_ROOT):
    """Build a neutral history report for audit and anti-repeat consumers.

    The schema intentionally contains no research-priority, winner-ranking, or
    next-strategy recommendation fields.  Alpha generation must come from the
    synthesis/search contract, while this report only says what was attempted
    and which near-neighbor lanes require genuinely new evidence.
    """
    records = [r for r in load_experiment_logs(root) if not r.get("_parse_error")]
    strategy_records = [r for r in records if is_strategy_iteration_record(r)]
    measurement_records = [r for r in records if is_measurement_repair_record(r)]

    return {
        "schema_version": 1,
        "read_only": True,
        "purpose": "experiment_history_and_anti_repeat_only",
        "records_loaded": len(records),
        "record_counts": {
            "strategy_iteration_records": len(strategy_records),
            "measurement_repair_records": len(measurement_records),
        },
        "data_quality_warnings": build_data_quality_warnings(records),
        "trial_accounting": build_trial_accounting(records),
        "prediction_calibration": build_prediction_calibration(records),
        "freeze_candidates": build_freeze_candidates(records),
        "notes": [
            "This report preserves history, deduplication, trial accounting, and anti-repeat facts.",
            "It intentionally does not rank historical winners or recommend the next strategy family.",
        ],
    }


def serialize_history_report(report):
    """Return portable JSON for artifacts consumed by mixed tooling."""
    return json.dumps(report, indent=2, ensure_ascii=True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = build_history_report(args.root)
    text = serialize_history_report(report)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text)


if __name__ == "__main__":
    main()
