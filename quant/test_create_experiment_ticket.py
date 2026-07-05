import json
import sys
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from create_experiment_ticket import (  # noqa: E402
    classify_saturated_source_axis,
    evaluate_reopen_condition_guard,
    reopen_condition_numeric_checks,
    surface_matches_text,
)


def test_saturated_source_axis_rejects_same_source_new_field_only():
    verdict = classify_saturated_source_axis(
        "same data source, same gate shape, new XBRL field never scanned before"
    )

    assert verdict["valid"] is False
    assert verdict["invalid_same_source_field_only"] is True
    assert verdict["categories"] == []


def test_saturated_source_axis_accepts_new_data_source():
    verdict = classify_saturated_source_axis(
        "new data source: PIT borrow fee and utilization sidecar"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["new_data_source"]


def test_saturated_source_axis_accepts_new_gate_shape():
    verdict = classify_saturated_source_axis(
        "new gate shape: shared forward default-off helper instead of candidate scan"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["new_gate_shape"]


def test_saturated_source_axis_accepts_more_forward_rows():
    verdict = classify_saturated_source_axis(
        "materially more closed forward rows with settled replacement value"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["materially_more_forward_rows"]


def _write_log(root, payload):
    log_dir = root / "experiments" / "logs"
    log_dir.mkdir(parents=True)
    path = log_dir / f"{payload['experiment_id']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _args(**overrides):
    base = {
        "lane": "alpha_search",
        "hypothesis": "Form4 sale-overhang risk scalar on accepted entries",
        "single_causal_variable": "form4_sale_overhang_notional_haircut",
        "changed_variable": "form4_sale_overhang_notional_haircut",
        "trial_family": "form4_sale_overhang_risk_response",
        "trial_variant_id": "v1",
        "mechanism_family": "form4_sale_overhang_forward_context",
        "file_slug": "form4_sale_overhang_risk_response",
        "new_evidence_axis": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_surface_match_handles_form4_aliases():
    assert surface_matches_text(
        "Form4 sale/10b5/officer overhang",
        "Form 4 officer sale overhang notional haircut",
    )


def test_surface_match_ignores_negated_sec_ftd_finra_alias():
    assert not surface_matches_text(
        "SEC FTD + FINRA default-off observer",
        (
            "supplier financing debt relief forward rows; this is not SEC FTD/FINRA, "
            "not a new FINRA observer, and not a response-function retune"
        ),
    )


def test_surface_match_still_matches_positive_sec_ftd_finra_alias():
    assert surface_matches_text(
        "SEC FTD + FINRA default-off observer",
        "SEC FTD FINRA true trigger rows with replacement-value maturity",
    )


def test_reopen_guard_does_not_block_negated_sec_ftd_finra_surface(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-sec-ftd",
            "reopen_condition": {
                "surface": "SEC FTD + FINRA default-off observer",
                "current_counts": {
                    "closed_sec_ftd_finra_true_trigger_rows": 0,
                    "single_ticker_positive_share": None,
                    "top5_positive_share": None,
                },
                "required_to_reopen": {
                    "closed_sec_ftd_finra_true_trigger_rows_min": 20,
                    "single_ticker_positive_share_max": 0.4,
                    "top5_positive_share_max": 0.7,
                },
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(
        _args(
            hypothesis="supplier financing debt relief new closed forward rows",
            single_causal_variable="supplier_financing_debt_relief_new_closed_rows",
            changed_variable="supplier_financing_debt_relief_new_closed_rows",
            trial_family="supplier_financing_debt_relief_forward_closed_row_readiness",
            trial_variant_id="supplier_financing_debt_relief_new_closed_rows_v1",
            mechanism_family="observed_only_forward_closed_row_readiness",
            file_slug="supplier_financing_debt_relief_new_closed_rows",
            new_evidence_axis=(
                "materially more closed forward rows for supplier financing debt relief; "
                "this is not SEC FTD/FINRA and not a response-function retune"
            ),
        ),
        repo_root=tmp_path,
    )

    assert verdict["blocked"] is False
    assert verdict["matched_conditions"] == []


def test_reopen_guard_still_blocks_positive_sec_ftd_finra_surface(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-sec-ftd-positive",
            "reopen_condition": {
                "surface": "SEC FTD + FINRA default-off observer",
                "current_counts": {
                    "closed_sec_ftd_finra_true_trigger_rows": 0,
                    "single_ticker_positive_share": None,
                    "top5_positive_share": None,
                },
                "required_to_reopen": {
                    "closed_sec_ftd_finra_true_trigger_rows_min": 20,
                    "single_ticker_positive_share_max": 0.4,
                    "top5_positive_share_max": 0.7,
                },
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(
        _args(
            hypothesis="SEC FTD FINRA forward true-trigger maturity audit",
            single_causal_variable="sec_ftd_finra_forward_true_trigger_rows",
            changed_variable="sec_ftd_finra_forward_true_trigger_rows",
            trial_family="sec_ftd_finra_forward_readiness",
            trial_variant_id="sec_ftd_finra_forward_readiness_v1",
            mechanism_family="sec_ftd_finra_forward_context",
            file_slug="sec_ftd_finra_forward_readiness",
        ),
        repo_root=tmp_path,
    )

    assert verdict["blocked"] is True
    assert verdict["matched_conditions"][0]["experiment_id"] == "exp-test-sec-ftd-positive"


def test_reopen_numeric_checks_map_min_to_long_current_key():
    condition = {
        "current_counts": {
            "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
            "high_sale_overhang_forward_rows": 0,
            "single_ticker_closed_row_share": None,
        },
        "required_to_reopen": {
            "closed_forward_rows_min": 25,
            "high_sale_overhang_forward_rows_min": 8,
            "single_ticker_share_max": 0.4,
        },
    }

    checks = reopen_condition_numeric_checks(condition)

    assert checks[0]["current_key"] == "closed_forward_rows_with_cash_spy_qqq_replacement_value"
    assert checks[0]["passed"] is False
    assert checks[1]["current_key"] == "high_sale_overhang_forward_rows"
    assert checks[1]["passed"] is False
    assert checks[2]["current_key"] == "single_ticker_closed_row_share"
    assert checks[2]["passed"] is False


def test_reopen_guard_blocks_parked_surface_without_progress(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-001",
            "reopen_condition": {
                "surface": "Form4 sale/10b5/officer overhang",
                "status": "shared_forward_logging_open_not_alpha_ready",
                "blocking_reason": "closed_forward_replacement_rows_not_materialized",
                "current_counts": {
                    "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
                    "high_sale_overhang_forward_rows": 0,
                    "single_ticker_closed_row_share": None,
                },
                "required_to_reopen": {
                    "closed_forward_rows_min": 25,
                    "high_sale_overhang_forward_rows_min": 8,
                    "single_ticker_share_max": 0.4,
                },
                "reopen_rule": "Do not reserve a Form4 response until rows close.",
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(_args(), repo_root=tmp_path)

    assert verdict["applicable"] is True
    assert verdict["blocked"] is True
    assert verdict["matched_conditions"][0]["experiment_id"] == "exp-test-001"


def test_reopen_guard_allows_new_data_source_axis(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-002",
            "reopen_condition": {
                "surface": "Form4 sale/10b5/officer overhang",
                "current_counts": {
                    "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
                },
                "required_to_reopen": {"closed_forward_rows_min": 25},
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(
        _args(new_evidence_axis="new data source: PIT broker locate feed"),
        repo_root=tmp_path,
    )

    assert verdict["blocked"] is False
    assert verdict["override_accepted"] is True


def test_reopen_guard_allows_satisfied_counts(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-003",
            "reopen_condition": {
                "surface": "Form144 planned-sale/float",
                "current_counts": {
                    "cached_primary_documents": 2,
                    "machine_parseable_ratio_rows": 3,
                    "closed_forward_rows_with_cash_spy_qqq_replacement_value": 27,
                    "high_planned_sale_float_bucket_rows": 9,
                    "single_ticker_closed_row_share": 0.32,
                },
                "required_to_reopen": {
                    "cached_primary_documents_min": 1,
                    "machine_parseable_ratio_rows_min": 1,
                    "closed_forward_rows_min": 25,
                    "high_planned_sale_float_bucket_rows_min": 8,
                    "single_ticker_closed_row_share_max": 0.4,
                },
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(
        _args(
            hypothesis="Form144 planned sale float ranking response",
            single_causal_variable="form144_planned_sale_float_response",
            changed_variable="form144_planned_sale_float_response",
            trial_family="form144_planned_sale_float_response",
            mechanism_family="form144_planned_sale_float_context",
            file_slug="form144_planned_sale_float_response",
        ),
        repo_root=tmp_path,
    )

    assert verdict["blocked"] is False
    assert verdict["matched_conditions"][0]["checks_satisfied"] is True


def test_reopen_guard_ignores_measurement_lane(tmp_path):
    _write_log(
        tmp_path,
        {
            "experiment_id": "exp-test-004",
            "reopen_condition": {
                "surface": "Form4 sale/10b5/officer overhang",
                "current_counts": {"closed_forward_rows_with_cash_spy_qqq_replacement_value": 0},
                "required_to_reopen": {"closed_forward_rows_min": 25},
            },
        },
    )

    verdict = evaluate_reopen_condition_guard(
        _args(lane="measurement_repair"),
        repo_root=tmp_path,
    )

    assert verdict["applicable"] is False
    assert verdict["blocked"] is False
