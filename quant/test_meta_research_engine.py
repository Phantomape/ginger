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

    assert report["schema_version"] == 3
    assert report["read_only"] is True
    assert report["records_loaded"] == 2
    assert report["data_quality_warnings"]["non_dict_metric_buckets"]["count"] == 2
    assert "chinese_explanation" in report
    assert "不是交易信号" in report["chinese_explanation"]["一句话"]
    assert report["record_counts"]["strategy_iteration_records"] == 2
    assert report["research_priorities"][0]["summary_zh"]


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
