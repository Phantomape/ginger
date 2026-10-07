"""Freeze admission artifacts for the first V2 SEC 8-K event-drift scout."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.alpha_search_contract import (
    HypothesisCandidate,
    canonical_hash,
    research_only_production_impact,
)
from quant.alpha_search_engine import build_selection_scope_manifest, freeze_selection_panel
from quant.alpha_search_history import build_historical_prior_snapshot
from quant.alpha_search_registry import EvidenceSurfaceRegistry
from scripts.alpha_debate import build_promotion_request, normalize_ticket_proposal


MATERIALIZATION = ROOT / (
    "data/v2/universe/sec_edgar_8k/20260820/"
    "20260821T125627Z/materialization.json"
)
BUNDLE = ROOT / (
    "data/v2/source_bundles/sec_edgar_8k/20260820/"
    "20260821T125627Z/bundle.json"
)
OUT = ROOT / "data/v2/scouts/sec_8k_event_drift_h1_20260821"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _self_hash(value: dict, field: str) -> dict:
    row = dict(value)
    row[field] = canonical_hash(row)
    return row


def build(*, freeze_at: str, history_cutoff: str) -> dict:
    materialization = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    boundary = materialization["boundary"]
    if boundary != {
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "authority": "research_only",
        "trade_enabled": False,
    }:
        raise ValueError("unexpected materialization boundary")

    coverage = materialization["coverage_snapshot"]
    rows = coverage["rows"]
    counts = coverage["disposition_counts"]
    if len(rows) != 219 or sum(counts.values()) != len(rows):
        raise ValueError("coverage population is not the frozen 219-row frame")
    if counts != {"excluded": 12, "mapped": 116, "unmapped": 91}:
        raise ValueError("coverage disposition counts drifted")
    row_ids = [row["source_row_id"] for row in rows]
    row_hashes = [row["source_row_sha256"] for row in rows]
    if len(set(row_ids)) != len(rows) or len(set(row_hashes)) != len(rows):
        raise ValueError("coverage row identities are not unique")

    memberships = materialization["universe_manifest"]["memberships"]
    if len(memberships) != 111:
        raise ValueError("expected 111 deduplicated active memberships")
    symbols = sorted({row["symbol"] for row in memberships})
    if len(symbols) != 111:
        raise ValueError("membership symbols are not unique")

    disposition = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_source_disposition_manifest",
            "scope_id": "sec-edgar-exact-8k-20260820-complete-daily-index",
            "source_materialization": _relative(MATERIALIZATION),
            "source_materialization_sha256": _sha256(MATERIALIZATION),
            "input_bundle_id": materialization["input_bundle_id"],
            "input_bundle_sha256": materialization["input_bundle_sha256"],
            "data_cutoff": materialization["universe_manifest"]["data_cutoff"],
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "source_reported_row_count": len(rows),
            "disposition_counts": counts,
            "row_count_conserved": True,
            "row_ids_unique": True,
            "row_hashes_unique": True,
            "dispositions_mutually_exclusive": True,
            "rows": rows,
            "external_universe_coverage_status": "unverified",
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "manifest_hash",
    )
    disposition_path = OUT / "source_disposition_manifest.json"
    _write(disposition_path, disposition)

    candidates = [
        {
            "security_id": row["security_id"],
            "listing_id": row["listing_id"],
            "symbol": row["symbol"],
            "mic": row["mic"],
            "mapping_id": row["mapping_id"],
            "mapping_sha256": row["mapping_sha256"],
            "membership_event_id": row["latest_event_id"],
            "membership_event_hash": row["latest_event_hash"],
            "admission_status": "admitted",
            "reason": "mapped exact-case 8-K row in the complete frozen source frame",
        }
        for row in sorted(memberships, key=lambda item: (item["symbol"], item["listing_id"]))
    ]
    candidate_pool = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_candidate_pool",
            "candidate_pool_id": "sec-8k-event-drift-h1-20260821",
            "source_disposition_manifest_hash": disposition["manifest_hash"],
            "source_row_count": 219,
            "mapped_source_row_count": 116,
            "candidate_count": len(candidates),
            "candidate_security_set_equals_mapped_deduplicated_set": True,
            "candidates": candidates,
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "external_universe_coverage_status": "unverified",
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "candidate_pool_hash",
    )
    candidate_pool_path = OUT / "candidate_pool.json"
    _write(candidate_pool_path, candidate_pool)

    market_recipe = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_research_market_evaluation_recipe",
            "provider": "moomoo OpenAPI via local authenticated OpenD",
            "sdk_version": "10.07.6708",
            "opend_endpoint": "127.0.0.1:11111",
            "quota_check_at": "2026-08-22T01:55:43Z",
            "historical_kline_quota_used": 5,
            "historical_kline_quota_remaining": 295,
            "codes": [f"US.{symbol}" for symbol in symbols] + ["US.SPY", "US.QQQ"],
            "bar_date": "2026-08-21",
            "bar_type": "K_DAY",
            "adjustment": "NONE",
            "session": "RTH",
            "entry_field": "open",
            "exit_field": "close",
            "round_trip_cost_bps": 10.0,
            "primary_statistic": "equal_weight_mean_open_to_close_return_after_cost",
            "comparators": ["cash", "SPY", "QQQ"],
            "minimum_usable_security_count": 60,
            "acceptance_rule": (
                "diagnostic observed-only lead iff usable securities >=60, mean and median "
                "after-cost return are positive, positive-name share >0.5, and equal-weight "
                "mean excess return versus both SPY and QQQ is positive"
            ),
            "falsifier": "any acceptance predicate fails",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
            "outcomes_accessed_before_freeze": False,
        },
        "recipe_hash",
    )
    market_recipe_path = OUT / "market_data_recipe.json"
    _write(market_recipe_path, market_recipe)

    decision = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_decision_record",
            "decision_id": "sec-8k-event-drift-h1-equal-weight-all-mapped",
            "candidate_pool_id": candidate_pool["candidate_pool_id"],
            "candidate_pool_hash": candidate_pool["candidate_pool_hash"],
            "policy": "select every mapped deduplicated security at equal weight",
            "selection_count": len(candidates),
            "selected_security_ids": [row["security_id"] for row in candidates],
            "signal_known_at": materialization["universe_manifest"]["data_cutoff"],
            "entry_at": "2026-08-21T13:30:00Z",
            "exit_at": "2026-08-21T20:00:00Z",
            "market_data_recipe_hash": market_recipe["recipe_hash"],
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "engine0_policy_invoked": False,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "decision_hash",
    )
    decision_path = OUT / "decision_record.json"
    _write(decision_path, decision)

    artifact_paths = [
        MATERIALIZATION,
        BUNDLE,
        disposition_path,
        candidate_pool_path,
        decision_path,
        market_recipe_path,
    ]
    hashes = {_relative(path): _sha256(path) for path in artifact_paths}
    materialization_known_at = materialization["universe_manifest"]["data_cutoff"]
    surfaces = {
        "schema_version": 1,
        "surfaces": [
            {
                "surface_id": "fixed_zero_excess_prior_v1",
                "data_source": "fixed_zero_excess_prior",
                "component_sources": ["fixed_zero_excess_prior"],
                "roles": ["market_expectation", "opportunity_cost"],
                "artifacts": [_relative(market_recipe_path)],
                "artifact_snapshot_hashes": {
                    _relative(market_recipe_path): hashes[_relative(market_recipe_path)]
                },
                "pit_status": "canonical_pit",
                "evidence_grade": "gate_candidate",
                "settled_count": 1,
                "independent_count": 1,
                "candidate_overlap_count": 111,
                "gate_ready": True,
                "expectation_proxy": {
                    "type": "price_revealed",
                    "field": "predeclared_zero_excess_return_prior",
                    "source": "fixed_zero_excess_prior",
                },
                "saturation_status": "open",
                "reopen_condition": None,
                "source_contract_status": "pass",
                "as_of": freeze_at,
            },
            {
                "surface_id": "v2_sec_edgar_8k_daily_index_20260820",
                "data_source": "v2_sec_edgar_8k_daily_index",
                "component_sources": ["v2_sec_edgar_8k_daily_index"],
                "roles": ["independent_evidence", "candidate_universe", "candidate_pool"],
                "artifacts": [
                    _relative(MATERIALIZATION),
                    _relative(BUNDLE),
                    _relative(disposition_path),
                    _relative(candidate_pool_path),
                    _relative(decision_path),
                ],
                "artifact_snapshot_hashes": {
                    key: value
                    for key, value in hashes.items()
                    if key != _relative(market_recipe_path)
                },
                "pit_status": "research_pit",
                "evidence_grade": "lead",
                "settled_count": 0,
                "independent_count": 219,
                "candidate_overlap_count": 111,
                "gate_ready": False,
                "expectation_proxy": None,
                "saturation_status": "open",
                "reopen_condition": (
                    "Reopen beyond H1 only with additional prospectively frozen complete SEC "
                    "daily-index frames under the unchanged all-mapped equal-weight policy."
                ),
                "source_contract_status": "pass",
                "as_of": materialization_known_at,
                "research_pit_basis": (
                    "Official complete prior-day SEC index, same-fetch association mapping, "
                    "row-level known_at, and full mapped/unmapped/excluded disposition are hash-bound; "
                    "the frame remains source-bounded and market coverage is unverified."
                ),
                "known_future_leakage": False,
            },
            {
                "surface_id": "moomoo_rth_daily_evaluation_recipe_20260821",
                "data_source": "moomoo_daily_ohlcv",
                "component_sources": ["moomoo_daily_ohlcv"],
                "roles": ["price_revealed_context"],
                "artifacts": [_relative(market_recipe_path)],
                "artifact_snapshot_hashes": {
                    _relative(market_recipe_path): hashes[_relative(market_recipe_path)]
                },
                "pit_status": "research_pit",
                "evidence_grade": "lead",
                "settled_count": 0,
                "independent_count": 113,
                "candidate_overlap_count": 111,
                "gate_ready": False,
                "expectation_proxy": None,
                "saturation_status": "open",
                "reopen_condition": "No retry on the same date or alternate adjustment mode.",
                "source_contract_status": "pass",
                "as_of": freeze_at,
                "research_pit_basis": (
                    "Exact code/date/session/adjustment query is frozen before any price row is read; "
                    "returned bytes are hash-bound at run time and are evaluation outputs only."
                ),
                "known_future_leakage": False,
            },
        ],
    }
    registry = EvidenceSurfaceRegistry.from_dict(surfaces)
    surfaces = registry.to_dict()
    surface_path = OUT / "evidence_surfaces.json"
    _write(surface_path, surfaces)

    prior = build_historical_prior_snapshot(
        ROOT / "docs/frozen_families.jsonl",
        history_cutoff=history_cutoff,
        repo_root=ROOT,
    )
    prior_path = OUT / "prior_fingerprints.json"
    _write(prior_path, prior)

    hypothesis = (
        "Within the complete frozen 2026-08-20 SEC exact-8-K source frame, an equal-weight "
        "basket of every mapped issuer bought at the 2026-08-21 regular-session open and "
        "sold at that session close has positive after-cost return and positive excess return "
        "versus SPY and QQQ because heterogeneous material-event filings are underreacted to "
        "between the prior close and the next regular session."
    )
    raw_candidate = {
        "schema_version": 1,
        "candidate_kind": "expectation_gap",
        "candidate_id": "pending",
        "search_queue": "exploration",
        "title": "V2 complete SEC 8-K source-frame next-session drift",
        "created_at": freeze_at,
        "created_by": "codex-user-directed-experiment-first",
        "hypothesis": hypothesis,
        "fingerprint": {
            "data_source": "v2_sec_edgar_8k_daily_index",
            "component_sources": [
                "fixed_zero_excess_prior",
                "moomoo_daily_ohlcv",
                "v2_sec_edgar_8k_daily_index",
            ],
            "expectation_proxy": "price_revealed",
            "economic_mechanism": "complete_material_event_frame_next_session_underreaction",
            "decision_surface": "candidate_pool",
            "payoff_shape": "equal_weight_one_session_event_drift",
            "horizon": "next_regular_open_to_same_session_close",
            "execution_dependency": "rth_daily_open_close_with_fixed_cost",
            "portfolio_role": "orthogonal_source_bounded_event_scout",
        },
        "surface_ids": [
            "fixed_zero_excess_prior_v1",
            "v2_sec_edgar_8k_daily_index_20260820",
            "moomoo_rth_daily_evaluation_recipe_20260821",
        ],
        "expectation_gap": {
            "market_prior": {
                "observable": True,
                "proxy_type": "price_revealed",
                "source": "fixed_zero_excess_prior",
                "known_at": freeze_at,
                "value": 0.0,
            },
            "independent_evidence": [
                {
                    "source": "v2_sec_edgar_8k_daily_index",
                    "known_at": materialization_known_at,
                    "fact": "complete exact-8-K prior-day source population",
                }
            ],
            "our_posterior": {
                "method": "predeclared_material_event_underreaction_prior_v1",
                "calibration_reference": "user-directed-loose-bounded-scout-20260821",
                "known_at": freeze_at,
                "value": 0.001,
            },
            "gap_definition": "predeclared positive H1 basket drift versus a zero-excess prior",
            "transmission": {
                "catalyst": "complete prior-day exact-8-K filing population known before market open",
                "affected_tickers": symbols,
                "expected_direction": "positive equal-weight open-to-close basket return",
                "half_life": "one regular trading session",
            },
        },
        "why_not_arbitraged": (
            "The source frame mixes event types, mapping is source-bounded, and the test pays "
            "costs across a broad one-day basket; any edge is expected to be weak and transient."
        ),
        "falsifier": market_recipe["falsifier"],
        "baseline": {"policy": "cash; SPY and QQQ are secondary same-session comparators"},
        "treatment": {
            "policy": "equal weight every one of the 111 mapped deduplicated SEC 8-K issuers",
            "candidate_pool": _relative(candidate_pool_path),
            "decision_record": _relative(decision_path),
        },
        "replacement_value_comparator": "cash, SPY, and QQQ over the identical RTH session",
        "expected_horizon": "next_regular_open_to_same_session_close",
        "execution_envelope": {
            "intended_instrument": "cash equities for measurement only",
            "liquidity_dependency": "none; missing or zero bars are excluded and counted",
            "costs_and_carry": "10 bps round-trip cost, no financing credit",
            "borrow_dependency": "none; long-only diagnostic",
            "capacity_constraint": "equal-weight descriptive basket; no deployable-capacity claim",
            "timing_constraint": "source known before 2026-08-21 13:30Z; RTH open-to-close",
            "trade_enabled": False,
        },
        "evidence_grade": "lead",
        "next_machine_action": "Reserve, claim, fetch frozen moomoo bars, run once, and close.",
        "production_impact": research_only_production_impact(),
        "source_readiness_snapshot": [
            {
                "surface_id": row["surface_id"],
                "snapshot_hash": canonical_hash(row),
            }
            for row in surfaces["surfaces"]
        ],
        "prediction": {
            "success_probability": 0.2,
            "main_failure_modes": [
                "mixed_event_sign_cancels",
                "same_day_reversal",
                "benchmark_not_beaten",
                "missing_price_rows",
            ],
            "confidence_reason": (
                "Material-event underreaction is plausible and the complete frame has 111 mapped "
                "issuers, but the event signs are intentionally unclassified and only one cross-section "
                "is consumed, so a positive all-name basket is unlikely."
            ),
        },
        "reopen_condition": (
            "Do not retune this date, costs, weighting, session, or event subset. Reopen only with "
            "additional prospectively frozen complete daily-index frames under the same policy."
        ),
    }
    raw_candidate["source_readiness_snapshot"].sort(key=lambda row: row["surface_id"])
    candidate = HypothesisCandidate.with_computed_id(raw_candidate).to_dict()

    scope = build_selection_scope_manifest(
        scope_name="v2-sec-8k-event-drift-h1-20260821",
        preregistered_at=freeze_at,
        data_cutoff=freeze_at,
        freeze_at=freeze_at,
        generator_version="v2-sec-8k-event-drift-h1-v1",
        candidate_generation_config={
            "outcome_fields_allowed": False,
            "candidate_specific_results_access": False,
            "selection_limit": 1,
            "selection_policy": "select the only complete-frame candidate if D0-D3 pass",
            "relaxed_user_directed_scout": True,
            "relaxed_dimensions": [
                "one_cross_section_allowed",
                "weak_zero_excess_prior_allowed",
                "no_engine0_or_market_wide_coverage_required",
            ],
            "non_relaxed_dimensions": [
                "outcome_blind_freeze",
                "complete_source_disposition",
                "hash_bound_inputs",
                "trade_enabled_false",
            ],
        },
        allowed_surface_ids=list(registry.surface_ids),
        surface_registry_hash=registry.canonical_hash,
        prior_fingerprints=prior,
        queue_budgets={"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=1,
        selection_limit=1,
    )
    scope_path = OUT / "selection_scope.json"
    _write(scope_path, scope)
    panel = freeze_selection_panel(
        [candidate],
        registry,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
        repo_root=ROOT,
    )
    panel_path = OUT / "selection_panel.json"
    _write(panel_path, panel)
    if panel["selected_candidate_ids"] != [candidate["candidate_id"]]:
        raise ValueError(
            "candidate did not pass D0-D3: "
            + json.dumps(panel["preflight_decisions"], ensure_ascii=False)
        )

    proposal = normalize_ticket_proposal(
        {
            "lane": "alpha_search",
            "hypothesis": hypothesis,
            "change_type": "private_replay_scout",
            "single_causal_variable": "all_mapped_sec_8k_h1_equal_weight_drift",
            "causal_components": [
                "complete 219-row source disposition",
                "111-security mapped deduplicated candidate pool",
                "equal-weight all-candidate treatment",
                "2026-08-21 RTH open-to-close horizon",
                "10 bps round-trip cost",
                "cash/SPY/QQQ comparators",
                "observed-only ceiling",
            ],
            "mechanism_family": "complete_sec_8k_frame_next_session_underreaction",
            "trial_family": "v2_sec_8k_complete_frame_h1_scout",
            "changed_variable": "presence_in_complete_prior_day_exact_8k_frame",
            "prediction": {
                **raw_candidate["prediction"],
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
            },
        }
    )
    promotion = build_promotion_request(
        panel_path=panel_path,
        scope_manifest_path=scope_path,
        surface_registry_path=surface_path,
        prior_fingerprints_path=prior_path,
        proposal=proposal,
        repo_root=ROOT,
    )
    promotion_path = OUT / "promotion_request.json"
    _write(promotion_path, promotion)

    report = {
        "schema_version": 1,
        "record_type": "v2_scout_admission_preflight",
        "candidate_id": candidate["candidate_id"],
        "selection_scope_id": panel["selection_scope_id"],
        "preflight": panel["preflight_decisions"][candidate["candidate_id"]],
        "candidate_pool_count": len(candidates),
        "source_row_count": len(rows),
        "disposition_counts": counts,
        "promotion_request": _relative(promotion_path),
        "promotion_hash": promotion["promotion_hash"],
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
    }
    report_path = OUT / "preflight_report.json"
    _write(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-at", required=True)
    parser.add_argument("--history-cutoff", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(freeze_at=args.freeze_at, history_cutoff=args.history_cutoff),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
