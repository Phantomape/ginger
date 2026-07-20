from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import clinicaltrials_phase3_results_paper_sleeve as sleeve


def _history_payload(*, sponsor="Eli Lilly and Company", nct="NCT00000001", posted="2025-01-06"):
    return {
        "study": {
            "hasResults": True,
            "protocolSection": {
                "identificationModule": {"nctId": nct},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": sponsor}},
                "designModule": {"phases": ["PHASE3"]},
                "statusModule": {
                    "resultsFirstPostDateStruct": {"date": posted, "type": "ACTUAL"}
                },
            },
            "resultsSection": {"outcomeMeasuresModule": {}},
        },
        "history_version": 7,
        "source_url": f"https://clinicaltrials.gov/api/int/studies/{nct}/history/7",
        "raw_sha256": "a" * 64,
    }


def _bars(closes, start_day=1):
    return [
        {
            "Date": f"2025-01-{idx + start_day:02d}",
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
        }
        for idx, close in enumerate(closes)
    ]


def _semantic_payload(
    *,
    nct="NCT10000001",
    posted="2025-01-03",
    title="Percentage of Responders With Reduction in Pain Score",
    active_value="70",
    control_value="40",
    param_type="Difference in Percentage",
    param_value="-30",
    p_value="&lt;0.001",
    ci_lower=None,
    ci_upper=None,
    control_title="Placebo",
    non_inferiority_type="SUPERIORITY",
):
    analysis = {
        # Deliberately put control first and use a reversed-sign estimate. The
        # semantic direction must come from matched arm measurements.
        "groupIds": ["OG_CONTROL", "OG_ACTIVE"],
        "nonInferiorityType": non_inferiority_type,
        "paramType": param_type,
        "paramValue": param_value,
    }
    if p_value is not None:
        analysis["pValue"] = p_value
    if ci_lower is not None:
        analysis["ciLowerLimit"] = ci_lower
    if ci_upper is not None:
        analysis["ciUpperLimit"] = ci_upper
    if ci_lower is not None or ci_upper is not None:
        analysis["ciNumSides"] = "TWO_SIDED"
        analysis["ciPctValue"] = "95"
    return {
        "study": {
            "hasResults": True,
            "protocolSection": {
                "identificationModule": {"nctId": nct},
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Eli Lilly and Company"}
                },
                "designModule": {"phases": ["PHASE3"]},
                "statusModule": {
                    "resultsFirstPostDateStruct": {
                        "date": posted,
                        "type": "ACTUAL",
                    }
                },
            },
            "resultsSection": {
                "outcomeMeasuresModule": {
                    "outcomeMeasures": [
                        {
                            "type": "PRIMARY",
                            "title": title,
                            "groups": [
                                {"id": "OG_ACTIVE", "title": "Active therapy"},
                                {"id": "OG_CONTROL", "title": control_title},
                            ],
                            "classes": [
                                {
                                    "categories": [
                                        {
                                            "measurements": [
                                                {
                                                    "groupId": "OG_ACTIVE",
                                                    "value": active_value,
                                                },
                                                {
                                                    "groupId": "OG_CONTROL",
                                                    "value": control_value,
                                                },
                                            ]
                                        }
                                    ]
                                }
                            ],
                            "analyses": [analysis],
                        }
                    ]
                }
            },
        }
    }


def _graded_event(payload, *, strength=None):
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    study = payload["study"]
    event = sleeve.normalise_clinicaltrials_result_events(
        [
            {
                **payload,
                "history_version": 1,
                "source_url": "https://clinicaltrials.gov/history/1",
                "raw_sha256": grade["raw_sha256"],
            }
        ]
    )[0]
    event.update(
        {
            "semantic_grade": grade["grade"],
            "semantic_strength": (
                grade["strongest_semantic_strength"]
                if strength is None
                else strength
            ),
            "semantic_rule_version": sleeve.SEMANTIC_RULE_VERSION,
            "semantic_payload_hash_verified": True,
            "semantic_evidence": grade,
        }
    )
    assert study["protocolSection"]["identificationModule"]["nctId"] == event["nct_id"]
    return event


def test_exact_fixed_sponsor_map_and_version_contract():
    assert len(sleeve.SPONSOR_TO_TICKER) == 12
    rows = sleeve.normalise_clinicaltrials_result_events([_history_payload()])
    assert rows[0]["ticker"] == "LLY"
    assert rows[0]["history_version"] == "7"
    assert rows[0]["raw_sha256"] == "a" * 64
    unknown = _history_payload(sponsor="Unregistered Sponsor", nct="NCT00000002")
    assert sleeve.normalise_clinicaltrials_result_events([unknown]) == []


def test_unversioned_historical_row_fails_closed():
    row = _history_payload()
    row.pop("history_version")
    assert sleeve.normalise_clinicaltrials_result_events([row]) == []


def test_estimated_first_post_date_fails_closed():
    row = _history_payload()
    row["study"]["protocolSection"]["statusModule"]["resultsFirstPostDateStruct"]["type"] = "ESTIMATED"
    assert sleeve.normalise_clinicaltrials_result_events([row]) == []


def test_history_change_parser_uses_public_result_module_only():
    payload = {
        "changes": [
            {"version": 40, "moduleLabels": ["Outcome Measures"]},
            {
                "version": 41,
                "moduleLabels": ["Outcome Measures (Results)"],
                "reviewNotPassed": True,
            },
            {"version": 42, "moduleLabels": ["Outcome Measures (Results)"]},
        ]
    }
    assert sleeve._history_versions(payload) == [40, 41, 42]
    assert sleeve._public_result_version_candidates(payload) == [42]


def test_price_confirmation_top1_and_replay_cost_contract():
    events = sleeve.normalise_clinicaltrials_result_events(
        [
            _history_payload(nct="NCT00000001", posted="2025-01-03"),
            _history_payload(sponsor="Novo Nordisk A/S", nct="NCT00000002", posted="2025-01-03"),
        ]
    )
    # Jan 3 issuer return: LLY +2%, NVO +1%, SPY flat -> LLY top1.
    ohlcv = {
        "SPY": _bars([100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]),
        "LLY": _bars([100, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]),
        "NVO": _bars([100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]),
    }
    replay = sleeve.replay_clinicaltrials_phase3_results_paper_trades(
        events=events, ohlcv_by_ticker=ohlcv, start="2025-01-01", end="2025-01-16"
    )
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    assert trade["ticker"] == "LLY"
    assert trade["entry_date"] == "2025-01-04"
    assert trade["exit_date"] == "2025-01-14"
    expected = 4000 * (113 / 102.8 - 1 - 0.0035)
    assert trade["pnl"] == pytest.approx(expected, abs=0.01)
    assert trade["target_price"] > trade["entry_price"]
    assert trade["trade_enabled"] is False


def test_daily_old_discovery_is_seed_only_and_default_off():
    snapshot, observations = sleeve.prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="20260713",
        existing_observations=[],
        fetched_events=[
            {
                "nct_id": "NCT00000003",
                "ticker": "MRK",
                "results_first_post_date": "2026-07-01",
            }
        ],
    )
    assert observations[0]["first_seen_date"] == "2026-07-13"
    assert snapshot["candidate_count"] == 0
    assert snapshot["seed_only_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_signal_generation"] is False
    assert snapshot["alters_candidate_ranking"] is False


def test_today_first_seen_can_only_be_pending_not_traded():
    snapshot, _ = sleeve.prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="2026-07-13",
        existing_observations=[],
        fetched_events=[
                {
                    "nct_id": "NCT00000004",
                    "ticker": "REGN",
                    "results_first_post_date": "2026-07-13",
                    "history_version": "12",
                    "source_url": "https://clinicaltrials.gov/api/int/studies/NCT00000004/history/12",
                    "raw_sha256": "b" * 64,
                }
        ],
    )
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_confirmation_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["settled_count"] == 0
    assert snapshot["trade_enabled"] is False


def test_as_of_accepts_daily_yyyymmdd_contract():
    snapshot = sleeve.build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date="20260713", observations=[]
    )
    assert snapshot["as_of_date"] == "2026-07-13"


def test_semantic_grader_uses_measurements_and_high_polarity_precedence():
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(
        _semantic_payload()
    )
    assert grade["grade"] == "positive"
    assert grade["positive_analysis_count"] == 1
    evidence = grade["evidence"][0]
    assert evidence["polarity"] == "favorable_high"
    assert "pain score" in evidence["polarity_matches"]["favorable_low"]
    assert evidence["estimate"]["value"] == -30
    assert evidence["p_value"]["decoded"] == "<0.001"
    assert evidence["measurement_direction_audit"]["active_value"] == 70
    assert evidence["measurement_direction_audit"]["control_value"] == 40
    assert evidence["direction"] == "positive"


def test_semantic_grader_negative_dominates_and_nonsignificant_is_neutral():
    negative = sleeve.grade_clinicaltrials_primary_endpoint_semantics(
        _semantic_payload(active_value="20", control_value="40")
    )
    assert negative["grade"] == "negative"
    assert negative["negative_analysis_count"] == 1

    neutral = sleeve.grade_clinicaltrials_primary_endpoint_semantics(
        _semantic_payload(p_value="= 0.20")
    )
    assert neutral["grade"] == "neutral"
    assert neutral["neutral_analysis_count"] == 1


def test_semantic_grader_fails_closed_without_unique_arm_measurements():
    payload = _semantic_payload()
    measurements = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]["classes"][0]["categories"][0]["measurements"]
    measurements.append({"groupId": "OG_ACTIVE", "value": "71"})
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "abstain"
    assert grade["evidence"][0]["reason"] == "arm_measurement_not_exactly_one_unique_numeric_value"


def test_semantic_grader_fails_closed_on_raw_event_counts_without_exposure_alignment():
    payload = _semantic_payload(
        title="Number of Progression Events",
        active_value="20",
        control_value="30",
    )
    outcome = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]
    outcome["unitOfMeasure"] = "Events"
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "abstain"
    assert grade["evidence"][0]["reason"] == "count_outcome_denominator_alignment_unproven"


def test_vaccine_efficacy_ci_requires_two_sided_95pct_metadata():
    payload = _semantic_payload(
        title="Vaccine Efficacy Against Infection",
        active_value="90",
        control_value="20",
        param_type="Vaccine Efficacy",
        param_value="70",
        p_value=None,
        ci_lower="50",
        ci_upper="85",
    )
    analysis = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]["analyses"][0]
    analysis["ciPctValue"] = "90"
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "abstain"
    assert grade["evidence"][0]["reason"] == "vaccine_efficacy_ci_not_two_sided_95pct"


def test_hr_ci_fallback_and_time_to_resolution_direction():
    payload = _semantic_payload(
        title="Time to Resolution of Symptoms",
        active_value="5",
        control_value="10",
        param_type="Hazard Ratio (HR)",
        param_value="1.5",
        p_value=None,
        ci_lower="1.1",
        ci_upper="2.0",
        control_title="Investigator's Choice",
    )
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "positive"
    evidence = grade["evidence"][0]
    assert evidence["statistic_family"] == "hazard_ratio"
    assert evidence["special_rule"] == "time_to_alleviation_recovery_resolution_hr_gt_1"
    assert evidence["arm_contract"]["control_group"]["control_tokens"]
    assert evidence["measurement_direction_audit"]["favorable_relation"] == "active_lt_control"


def test_hr_ci_fallback_requires_two_sided_95pct_metadata():
    payload = _semantic_payload(
        title="Overall Survival",
        active_value="12",
        control_value="10",
        param_type="Hazard Ratio (HR)",
        param_value="0.7",
        p_value=None,
        ci_lower="0.5",
        ci_upper="0.9",
    )
    analysis = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]["analyses"][0]
    analysis.pop("ciNumSides")
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "abstain"
    assert grade["evidence"][0]["reason"] == "hazard_ratio_ci_not_two_sided_95pct"


def test_wilcoxon_difference_is_not_misclassified_as_cox():
    payload = _semantic_payload(
        title="Change in KCCQ Clinical Summary Score",
        active_value="20",
        control_value="12",
        param_type="Median Difference (Net)",
        param_value="8",
        p_value="&lt;0.01",
    )
    analysis = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]["analyses"][0]
    analysis["statisticalMethod"] = "Stratified Wilcoxon"
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "positive"
    assert grade["evidence"][0]["statistic_family"] == "polarity_difference"


def test_count_outcome_without_denominator_alignment_abstains():
    payload = _semantic_payload()
    outcome = payload["study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]
    outcome["paramType"] = "COUNT_OF_PARTICIPANTS"
    outcome["unitOfMeasure"] = "Participants"
    grade = sleeve.grade_clinicaltrials_primary_endpoint_semantics(payload)
    assert grade["grade"] == "abstain"
    assert grade["evidence"][0]["reason"] == "count_outcome_denominator_alignment_unproven"


def test_semantic_archive_enrichment_requires_exact_raw_hash(tmp_path):
    payload = _semantic_payload(nct="NCT10000009")
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "NCT10000009_v3.json"
    path.write_bytes(raw)
    event = {
        "nct_id": "NCT10000009",
        "ticker": "LLY",
        "results_first_post_date": "2025-01-03",
        "history_version": "3",
        "source_url": "https://clinicaltrials.gov/history/3",
        "raw_sha256": sha,
    }
    enriched = sleeve.enrich_clinicaltrials_events_with_primary_endpoint_semantics(
        [event], history_dir=tmp_path
    )
    assert enriched[0]["semantic_grade"] == "positive"
    assert enriched[0]["semantic_payload_hash_verified"] is True
    assert enriched[0]["semantic_provenance"]["raw_sha256"] == sha

    with pytest.raises(RuntimeError, match="hash mismatch"):
        sleeve.enrich_clinicaltrials_events_with_primary_endpoint_semantics(
            [{**event, "raw_sha256": "0" * 64}], history_dir=tmp_path
        )


def test_semantic_replay_and_daily_snapshot_share_rank_and_strict_entry_clock():
    first = _graded_event(
        _semantic_payload(nct="NCT10000011", posted="2025-01-03"),
        strength=4.0,
    )
    second = _graded_event(
        _semantic_payload(nct="NCT10000012", posted="2025-01-03"),
        strength=2.0,
    )
    bars = {
        "SPY": _bars([100] * 16),
        "LLY": _bars([100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]),
    }
    replay = sleeve.replay_clinicaltrials_phase3_endpoint_semantic_paper_trades(
        events=[second, first],
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-16",
    )
    assert len(replay["trades"]) == 1
    assert replay["trades"][0]["nct_id"] == "NCT10000011"
    assert replay["trades"][0]["signal_date"] == "2025-01-03"
    assert replay["trades"][0]["entry_date"] == "2025-01-04"
    assert replay["trades"][0]["target_price"] > replay["trades"][0]["entry_price"]
    assert replay["trades"][0]["trade_enabled"] is False

    snapshot = sleeve.build_clinicaltrials_phase3_endpoint_semantic_snapshot(
        as_of_date="2025-01-03",
        observations=[
            {**second, "first_seen_date": "2025-01-03"},
            {**first, "first_seen_date": "2025-01-03"},
        ],
    )
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["nct_id"] == replay["trades"][0]["nct_id"]
    assert snapshot["parity_contract"]["semantic_grade_parity"] is True
    assert snapshot["parity_contract"]["candidate_lifecycle_parity"] is False
    assert snapshot["parity_contract"]["same_day_price_confirmation"] is False
    assert snapshot["trade_enabled"] is False


def test_semantic_daily_old_first_seen_is_seed_only():
    event = _graded_event(
        _semantic_payload(nct="NCT10000013", posted="2025-01-01")
    )
    snapshot = sleeve.build_clinicaltrials_phase3_endpoint_semantic_snapshot(
        as_of_date="2025-01-03",
        observations=[{**event, "first_seen_date": "2025-01-03"}],
    )
    assert snapshot["candidate_count"] == 0
    assert snapshot["seed_only_count"] == 1


def test_semantic_replay_does_not_force_liquidate_before_tenth_session():
    event = _graded_event(
        _semantic_payload(nct="NCT10000014", posted="2025-01-03")
    )
    bars = {
        "SPY": _bars([100] * 16),
        "LLY": _bars([100 + index for index in range(16)]),
    }
    replay = sleeve.replay_clinicaltrials_phase3_endpoint_semantic_paper_trades(
        events=[event],
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-10",
    )
    assert replay["trades"] == []
    assert len(replay["unsettled"]) == 1
    assert replay["unsettled"][0]["unsettled_reason"] == "scheduled_10_session_exit_outside_window"
