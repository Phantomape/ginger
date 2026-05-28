import json

from quant.meta_research_engine import build_meta_report


def test_meta_report_handles_legacy_string_metric_buckets(tmp_path):
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

    report = build_meta_report(tmp_path)

    assert report["schema_version"] == 5
    assert report["read_only"] is True
    assert report["records_loaded"] == 2
    assert report["data_quality_warnings"]["non_dict_metric_buckets"]["count"] == 2
    assert "chinese_explanation" in report
    assert "不是交易信号" in report["chinese_explanation"]["一句话"]
    assert report["record_counts"]["strategy_iteration_records"] == 2
    assert report["research_priorities"][0]["summary_zh"]
    assert report["trial_accounting"]["records_counted"] == 2


def test_meta_report_chinese_explanation_translates_priority_fields(tmp_path):
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

    report = build_meta_report(tmp_path)

    explanation = report["chinese_explanation"]
    assert "priority" in explanation["字段说明"]
    assert explanation["当前前五策略研究方向"]
    assert explanation["当前前五策略研究方向"][0]["family_zh"]


def test_meta_report_separates_strategy_from_measurement_priorities(tmp_path):
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

    report = build_meta_report(tmp_path)

    assert report["record_counts"]["strategy_iteration_records"] == 1
    assert report["record_counts"]["measurement_repair_records"] == 1
    assert report["strategy_research_priorities"]
    assert report["strategy_research_priorities"][0]["evidence_summary"]["sum_ev_delta"] == 0.5
    assert report["measurement_repair_priorities"]


def test_meta_report_builds_trial_accounting_with_multiple_testing_bucket(tmp_path):
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

    report = build_meta_report(tmp_path)

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


def test_meta_report_trial_accounting_dedupes_log_copies(tmp_path):
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

    report = build_meta_report(tmp_path)

    assert report["records_loaded"] == 2
    assert report["trial_accounting"]["records_counted"] == 1
    assert report["trial_accounting"]["groups"][0]["experiments"] == 1


def test_meta_report_builds_prediction_calibration(tmp_path):
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

    report = build_meta_report(tmp_path)

    calibration = report["prediction_calibration"]
    assert calibration["records_counted"] == 3
    assert calibration["records_with_prediction"] == 2
    assert calibration["records_missing_prediction"] == 1
    assert calibration["direction_counts"]["overconfident"] == 1
    assert calibration["direction_counts"]["underconfident"] == 1
    assert calibration["by_family"][0]["family"] == "core_allocation"
    assert calibration["by_family"][0]["actual_accept_rate"] == 0.5
