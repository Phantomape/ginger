import datetime
import json
import sys
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from create_experiment_ticket import (  # noqa: E402
    classify_routine_materialization,
    classify_saturated_source_axis,
    evaluate_observed_only_streak_guard,
    evaluate_reopen_condition_guard,
    evaluate_routine_materialization_guard,
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


def test_surface_match_ignores_generic_default_off_sleeve_tokens():
    # "default-off paper sleeve" phrasing appears in nearly every sleeve ticket;
    # it must not map an unrelated ETF-rebound ticket to a parked FTD/FINRA
    # observer surface.
    assert not surface_matches_text(
        "SEC FTD + FINRA default-off observer",
        (
            "Deep index drawdown episode ETF rebound; next-open entry, fixed "
            "5-day hold, default-off paper ETF sleeve"
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


def test_novelty_check_flags_unclassified_data_source(capsys):
    from create_experiment_ticket import _novelty_check

    args = _args(
        hypothesis="brand new exotic population nobody has keywords for yet",
        single_causal_variable="exotic_population_probe",
        changed_variable="exotic_population_probe",
        trial_family="exotic_population_probe",
        mechanism_family="exotic_population_probe",
        file_slug="exotic_population_probe",
        lane="alpha_search",
        change_type="candidate_pool_full_stack",
        novelty_override=False,
        saturated_source_override=False,
        observed_only_override=False,
        routine_materialization_override=False,
        enforce_novelty=False,
        no_enforce_novelty=True,  # warn-only: this test is about the coverage flag
    )
    out = _novelty_check(args)
    assert out is not None
    assert out["fingerprint"]["data_source"] == "other"
    assert out["data_source_unclassified"] is True
    assert "invisible to the saturation" in capsys.readouterr().err


def _write_logs(root, payloads):
    log_dir = root / "experiments" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for payload in payloads:
        path = log_dir / f"{payload['experiment_id']}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")


_KOVA_OBSERVED_LOGS = [
    {
        "experiment_id": "exp-20260704-011",
        "status": "observed_only_rejected",
        "hypothesis": "Kova RS proxy rows recent acceleration forward attribution",
        "change_type": "candidate_pool_observed_attribution",
    },
    {
        "experiment_id": "exp-20260704-013",
        "status": "observed_only_rejected",
        "hypothesis": "Kova current SEC13F ownership breadth joined to RS proxy rows",
        "change_type": "observed_only_forward_attribution",
    },
    {
        "experiment_id": "exp-20260705-008",
        "status": "observed_only_rejected",
        "hypothesis": "Kova SEC13F active-manager active-flow forward separation",
        "change_type": "observed_only_attribution",
    },
]


def test_observed_only_streak_guard_blocks_fourth_probe_on_same_population(tmp_path):
    _write_logs(tmp_path, _KOVA_OBSERVED_LOGS)

    verdict = evaluate_observed_only_streak_guard(
        _args(
            hypothesis="Kova rows: options open-interest join for 10d forward separation",
            change_type="candidate_pool_observed_attribution",
        ),
        "kova_snapshot",
        repo_root=tmp_path,
    )

    assert verdict["applicable"] is True
    assert verdict["streak"] == 3
    assert verdict["blocked"] is True


def test_observed_only_streak_guard_accepts_valid_axis_override(tmp_path):
    _write_logs(tmp_path, _KOVA_OBSERVED_LOGS)

    verdict = evaluate_observed_only_streak_guard(
        _args(
            hypothesis="Kova rows observed-only probe after new settlements",
            change_type="candidate_pool_observed_attribution",
            observed_only_override=True,
            new_evidence_axis="materially more closed forward rows since the last probe",
        ),
        "kova_snapshot",
        repo_root=tmp_path,
    )

    assert verdict["blocked"] is False
    assert verdict["override_accepted"] is True


def test_observed_only_streak_guard_resets_on_non_observed_close(tmp_path):
    _write_logs(
        tmp_path,
        _KOVA_OBSERVED_LOGS
        + [
            {
                "experiment_id": "exp-20260705-020",
                "status": "accepted",
                "hypothesis": "Kova snapshot daily wiring into run.py",
                "change_type": "measurement_repair",
            }
        ],
    )

    verdict = evaluate_observed_only_streak_guard(
        _args(
            hypothesis="Kova rows observed-only probe",
            change_type="candidate_pool_observed_attribution",
        ),
        "kova_snapshot",
        repo_root=tmp_path,
    )

    assert verdict["streak"] == 0
    assert verdict["blocked"] is False


def test_observed_only_streak_guard_ignores_non_observed_proposal(tmp_path):
    _write_logs(tmp_path, _KOVA_OBSERVED_LOGS)

    verdict = evaluate_observed_only_streak_guard(
        _args(
            hypothesis="Kova snapshot shared default-off paper sleeve full-stack Gate 1-4",
            change_type="candidate_pool_full_stack",
        ),
        "kova_snapshot",
        repo_root=tmp_path,
    )

    assert verdict["applicable"] is False
    assert verdict["blocked"] is False


def test_classify_routine_materialization_shapes():
    routine = classify_routine_materialization(
        "Enrich newly closed forward rows with cash/SPY/QQQ replacement values"
    )
    assert routine["routine"] is True
    assert routine["fault_recovery"] is False
    assert routine["pipeline_wiring"] is False

    wiring = classify_routine_materialization(
        "Wire the forward-row replacement enrichment into run.py daily pipeline"
    )
    assert wiring["pipeline_wiring"] is True

    fault = classify_routine_materialization(
        "Recover orphan temp files and re-materialize the observer forward snapshot"
    )
    assert fault["fault_recovery"] is True


_ROUTINE_ENRICHMENT_LOGS = [
    {
        "experiment_id": "exp-20260704-020",
        "status": "accepted",
        "hypothesis": "Enrich newly closed supplier-financing forward rows with replacement values",
        "change_type": "identity_or_measurement_repair",
    },
    {
        "experiment_id": "exp-20260704-021",
        "status": "accepted_measurement_repair",
        "hypothesis": "Enrich newly closed allocator/source-consensus forward rows with replacement values",
        "change_type": "identity_or_measurement_repair",
    },
    {
        "experiment_id": "exp-20260704-023",
        "status": "accepted_measurement_repair",
        "hypothesis": "Materialize estimate-revision overlap forward replacement outcome refresh",
        "change_type": "identity_or_measurement_repair",
    },
]


def test_routine_materialization_guard_blocks_after_cross_surface_budget(tmp_path):
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis="Enrich newly closed narrow-range forward rows with replacement values",
            change_type="identity_or_measurement_repair",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 7, 5),
    )

    assert verdict["applicable"] is True
    assert verdict["recent_cross_surface_count"] == 3
    assert verdict["blocked"] is True


def test_routine_materialization_guard_allows_pipeline_wiring_ticket(tmp_path):
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis=(
                "Wire forward-row replacement enrichment into run.py settlement "
                "pipeline so newly closed rows enrich automatically"
            ),
            change_type="measurement_repair",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 7, 5),
    )

    assert verdict["applicable"] is False
    assert verdict["blocked"] is False


def test_routine_materialization_guard_allows_fault_recovery(tmp_path):
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis="Recover orphan temp files and re-append the contaminated observer forward snapshot",
            change_type="measurement_repair",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 7, 5),
    )

    assert verdict["applicable"] is False
    assert verdict["blocked"] is False


def test_routine_materialization_guard_window_expires(tmp_path):
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis="Enrich newly closed narrow-range forward rows with replacement values",
            change_type="identity_or_measurement_repair",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 8, 1),
    )

    assert verdict["applicable"] is True
    assert verdict["recent_cross_surface_count"] == 0
    assert verdict["blocked"] is False


def test_routine_materialization_guard_same_surface_budget_persists(tmp_path):
    _write_logs(
        tmp_path,
        [
            {
                "experiment_id": "exp-20260704-020",
                "status": "accepted_measurement_repair",
                "hypothesis": "Enrich newly closed supplier-financing forward rows with replacement values",
                "change_type": "identity_or_measurement_repair",
            },
            {
                "experiment_id": "exp-20260705-020",
                "status": "accepted_measurement_repair",
                "hypothesis": "Refresh supplier financing forward ledger replacement values",
                "change_type": "identity_or_measurement_repair",
            },
            {
                "experiment_id": "exp-20260706-020",
                "status": "accepted_measurement_repair",
                "hypothesis": "Materialize supplier-financing settled forward outcomes",
                "change_type": "identity_or_measurement_repair",
            },
        ],
    )

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis="Enrich newly closed supplier-financing forward rows with replacement values",
            change_type="identity_or_measurement_repair",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 8, 1),
    )

    assert verdict["applicable"] is True
    assert verdict["recent_cross_surface_count"] == 0
    assert verdict["per_source_count"] == 3
    assert verdict["blocked"] is True


def test_routine_materialization_guard_ignores_alpha_full_stack_ticket(tmp_path):
    # An alpha-lane full-stack hypothesis mentioning "backfill" and "forward"
    # is testing a hypothesis, not appending ledger rows; it must not trip the
    # routine-materialization budget (live false positive, 2026-07-05).
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="alpha_search",
            hypothesis=(
                "Deep index drawdown episodes predict positive 5-day forward "
                "ETF rebound; pre-2023 index history backfill as new evidence"
            ),
            change_type="candidate_pool_full_stack",
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 7, 5),
    )

    assert verdict["applicable"] is False
    assert verdict["blocked"] is False


def test_routine_materialization_guard_override(tmp_path):
    _write_logs(tmp_path, _ROUTINE_ENRICHMENT_LOGS)

    verdict = evaluate_routine_materialization_guard(
        _args(
            lane="measurement_repair",
            hypothesis="Enrich newly closed narrow-range forward rows with replacement values",
            change_type="identity_or_measurement_repair",
            routine_materialization_override=True,
        ),
        repo_root=tmp_path,
        today=datetime.date(2026, 7, 5),
    )

    assert verdict["blocked"] is False
    assert verdict["override_accepted"] is True
