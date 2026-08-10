import json

from quant.experiment_history import (
    build_history_report,
    decision_bucket,
    serialize_history_report,
)


def test_decision_bucket_is_shared_neutral_history_fact():
    assert decision_bucket({"decision": "accepted_alpha", "status": "completed"}) == "accepted"
    assert decision_bucket({"accepted": True, "decision": "rejected"}) == "accepted"
    assert decision_bucket({"decision": "observed_only_positive_replay_lead"}) == "lead"
    assert decision_bucket({"decision": "blocked_source_contract"}) == "blocked"
    assert decision_bucket({"decision": "observed_only"}) == "rejected"


def test_history_report_handles_legacy_string_metric_buckets(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    rows = [
        {
            "experiment_id": "exp-20990101-001",
            "decision": "accepted",
            "change_type": "risk_allocation",
            "delta_metrics": {"expected_value_score": 0.2, "total_pnl": 1000.0},
            "after_metrics": {"trade_count": 12},
            "production_impact": {
                "shared_policy_changed": True,
                "run_adapter_changed": True,
            },
        },
        {
            "experiment_id": "exp-20990101-002",
            "decision": "rejected",
            "change_type": "new_strategy_shadow",
            "before_metrics": "see experiments/logs/exp-20990101-002.json",
            "after_metrics": "see experiments/logs/exp-20990101-002.json",
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    assert report["schema_version"] == 1
    assert report["read_only"] is True
    assert report["purpose"] == "experiment_history_and_anti_repeat_only"
    assert report["records_loaded"] == 2
    assert report["data_quality_warnings"]["non_dict_metric_buckets"]["count"] == 2
    assert report["record_counts"]["strategy_iteration_records"] == 2
    assert report["trial_accounting"]["records_counted"] == 2


def test_history_report_has_no_winner_priority_or_recommendation_surface(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-003",
                "decision": "accepted",
                "change_type": "risk_scalar_or_topup",
                "delta_metrics": {"expected_value_score": 0.5},
                "after_metrics": {"trade_count": 10},
            }
        ),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    forbidden = {
        "priority_formula",
        "research_priorities",
        "strategy_research_priorities",
        "measurement_repair_priorities",
        "recommendations",
        "top_experiments",
        "worst_experiments",
    }
    assert forbidden.isdisjoint(report)


def test_history_report_serialization_is_portable_json(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-099",
                "decision": "accepted",
                "change_type": "risk_scalar_or_topup",
                "delta_metrics": {"expected_value_score": 0.5},
                "after_metrics": {"trade_count": 10},
            }
        ),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)
    text = serialize_history_report(report)

    assert text.isascii()
    assert json.loads(text) == report


def test_history_report_separates_strategy_from_measurement_counts(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    rows = [
        {
            "experiment_id": "exp-20990101-004",
            "lane": "measurement_repair",
            "decision": "accepted_measurement_repair",
            "change_type": "measurement_repair",
            "delta_metrics": {"expected_value_score_delta": 0.0},
        },
        {
            "experiment_id": "exp-20990101-005",
            "lane": "alpha_search",
            "decision": "accepted_default_off_state_surface_rank_queue_alignment_notional",
            "change_type": "default_off_paper_allocation",
            "delta_metrics": {
                "aggregate_ev_delta": 0.5,
                "aggregate_pnl_delta": 10000.0,
            },
            "after_metrics": {"trade_count": 12},
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    assert report["record_counts"]["strategy_iteration_records"] == 1
    assert report["record_counts"]["measurement_repair_records"] == 1
    assert "strategy_research_priorities" not in report
    assert "measurement_repair_priorities" not in report


def test_history_report_builds_trial_accounting_and_freeze_facts(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    rows = []
    for i in range(10):
        rows.append(
            {
                "experiment_id": f"exp-20990102-{i:03d}",
                "lane": "alpha_search",
                "decision": "rejected" if i < 9 else "accepted",
                "change_type": "default_off_paper_allocation",
                "mechanism_family": "state_surface_concentration",
                "trial_family": "state_surface_queue_quality",
                "trial_variant_id": f"queue_quality_{i}",
                "changed_variable": "state_surface_queue_quality_scalar",
                "prior_trial_count": i,
                "nearby_prior_experiments": [
                    f"exp-20990101-{j:03d}" for j in range(i)
                ],
                "new_evidence_type": "not_declared",
                "delta_metrics": {
                    "expected_value_score": 0.1 if i == 9 else -0.01,
                    "total_pnl": 100.0 if i == 9 else -10.0,
                },
                "after_metrics": {"trade_count": 12},
            }
        )
    log_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    accounting = report["trial_accounting"]
    assert accounting["grouping"] == "trial_family + changed_variable"
    assert accounting["missing_metadata_counts"]["trial_family"] == 0
    group = accounting["groups"][0]
    assert group["trial_family"] == "state_surface_queue_quality"
    assert group["changed_variable"] == "state_surface_queue_quality_scalar"
    assert group["experiments"] == 10
    assert group["accepted"] == 1
    assert group["multiple_testing_risk_bucket"] == "high"
    assert group["retry_guidance"] == "freeze_nearby_retries_until_new_forward_or_field_evidence"
    assert group["most_recent_failure"]["experiment_id"] == "exp-20990102-008"
    assert report["freeze_candidates"] == [
        {
            "scope": "family",
            "name": "state_surface_queue_quality",
            "reason": "low_accept_rate",
            "accept_rate": 0.1,
            "experiments": 10,
        }
    ]


def test_history_report_trial_accounting_dedupes_log_copies(tmp_path):
    docs_dir = tmp_path / "docs"
    logs_dir = tmp_path / "experiments" / "logs"
    docs_dir.mkdir()
    logs_dir.mkdir(parents=True)
    row = {
        "experiment_id": "exp-20990103-001",
        "lane": "alpha_search",
        "decision": "accepted",
        "change_type": "risk_scalar_or_topup",
        "trial_family": "core_allocation",
        "changed_variable": "core_rank1_topup",
        "delta_metrics": {"expected_value_score": 0.2},
        "after_metrics": {"trade_count": 10},
    }
    (docs_dir / "experiment_log.jsonl").write_text(
        json.dumps(row),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990103-001.json").write_text(
        json.dumps({**row, "notes": "larger copy"}),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    assert report["records_loaded"] == 2
    assert report["trial_accounting"]["records_counted"] == 1
    assert report["trial_accounting"]["groups"][0]["experiments"] == 1


def test_history_report_builds_prediction_calibration(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    log_path = docs_dir / "experiment_log.jsonl"
    rows = [
        {
            "experiment_id": "exp-20990104-001",
            "lane": "alpha_search",
            "decision": "accepted",
            "change_type": "risk_scalar_or_topup",
            "mechanism_family": "core_allocation",
            "prediction": {
                "success_probability": 0.25,
                "expected_ev_delta": 0.02,
            },
            "delta_metrics": {"expected_value_score": 0.2},
            "after_metrics": {"trade_count": 10},
        },
        {
            "experiment_id": "exp-20990104-002",
            "lane": "alpha_search",
            "decision": "rejected",
            "change_type": "risk_scalar_or_topup",
            "mechanism_family": "core_allocation",
            "prediction": {
                "success_probability": 0.8,
                "expected_ev_delta": 0.2,
            },
            "delta_metrics": {"expected_value_score": -0.1},
            "after_metrics": {"trade_count": 10},
        },
        {
            "experiment_id": "exp-20990104-003",
            "lane": "alpha_search",
            "decision": "rejected",
            "change_type": "filter_or_gate",
            "delta_metrics": {"expected_value_score": -0.01},
            "after_metrics": {"trade_count": 10},
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    report = build_history_report(tmp_path)

    calibration = report["prediction_calibration"]
    assert calibration["records_counted"] == 3
    assert calibration["records_with_prediction"] == 2
    assert calibration["records_missing_prediction"] == 1
    assert calibration["direction_counts"]["overconfident"] == 1
    assert calibration["direction_counts"]["underconfident"] == 1
    assert calibration["by_family"][0]["family"] == "core_allocation"
    assert calibration["by_family"][0]["actual_accept_rate"] == 0.5
