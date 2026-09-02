"""Freeze admission artifacts for the V2 SEC CORRESP H5 avoid-long scout."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.alpha_search_contract import (  # noqa: E402
    HypothesisCandidate,
    canonical_hash,
    research_only_production_impact,
)
from quant.alpha_search_engine import (  # noqa: E402
    build_selection_scope_manifest,
    freeze_selection_panel,
)
from quant.alpha_search_history import build_historical_prior_snapshot  # noqa: E402
from quant.alpha_search_registry import EvidenceSurfaceRegistry  # noqa: E402
from quant.v2_sec_8k_universe import (  # noqa: E402
    _parse_company_exchange,
    _parse_daily_index,
)
from scripts.alpha_debate import (  # noqa: E402
    build_promotion_request,
    normalize_ticket_proposal,
)


BUNDLE_DIR = ROOT / (
    "data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z"
)
BUNDLE = BUNDLE_DIR / "bundle.json"
INDEX = BUNDLE_DIR / "form.20260820.idx"
MAPPING = BUNDLE_DIR / "company_tickers_exchange.json"
OUT = ROOT / "data/v2/scouts/sec_correspondence_information_risk_h5_20260902"
PREPARATION_REL = "scripts/prepare_v2_sec_correspondence_scout.py"
TARGET_FORM = "CORRESP"
ACCEPTED_EXCHANGES = {"Nasdaq": "XNAS", "NYSE": "XNYS"}
EXPECTED_SESSION_DATES = [
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
]
ENTRY_AT = "2026-08-21T13:30:00Z"
EXIT_AT = "2026-08-27T20:00:00Z"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to mutate frozen artifact: {path}")
        return
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    row = dict(value)
    row[field] = canonical_hash(row)
    return row


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unknown"


def _utc(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _artifact(bundle: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [row for row in bundle["artifacts"] if row.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one bundle artifact for role {role}")
    row = matches[0]
    path = BUNDLE_DIR / row["filename"]
    if _sha256(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
        raise ValueError(f"bundle artifact identity drifted: {role}")
    return row


def _mapping_payload(
    *, association: dict[str, Any], mapping_sha256: str, known_at: str
) -> dict[str, Any]:
    ticker_slug = _slug(association["ticker"])
    mic = ACCEPTED_EXCHANGES[association["exchange"]]
    payload = {
        "cik": association["cik"],
        "symbol": association["ticker"],
        "exchange": association["exchange"],
        "mic": mic,
        "security_id": f"sec-association-{association['cik']}-{ticker_slug}",
        "listing_id": (
            f"sec-association-{association['cik']}-{ticker_slug}-{mic.lower()}"
        ),
        "mapping_artifact_sha256": mapping_sha256,
        "known_at": known_at,
        "authority": "research_only",
    }
    payload["mapping_sha256"] = canonical_hash(payload)
    payload["mapping_id"] = (
        f"sec-correspondence-map-{association['cik']}-{ticker_slug}-"
        f"{mic.lower()}-{payload['mapping_sha256'][:12]}"
    )
    return payload


def evaluate_avoid_long_h5(
    rows: list[dict[str, Any]],
    *,
    candidate_codes: list[str],
    cost_bps: float,
    expected_session_dates: list[str],
) -> dict[str, Any]:
    """Evaluate the fully frozen cash-replacement policy without doing I/O."""
    if not math.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps must be finite and non-negative")
    if len(expected_session_dates) != 5 or len(set(expected_session_dates)) != 5:
        raise ValueError("H5 evaluation requires five unique expected session dates")
    if expected_session_dates != sorted(expected_session_dates):
        raise ValueError("expected session dates must be strictly chronological")
    if len(set(candidate_codes)) != len(candidate_codes):
        raise ValueError("frozen candidate codes must be unique")
    row_by_code = {str(row.get("code")): row for row in rows}
    if len(row_by_code) != len(rows):
        raise ValueError("evaluation rows must have unique codes")
    if set(row_by_code) != set(candidate_codes):
        raise ValueError("evaluation rows must exactly match the frozen candidate codes")
    cost = cost_bps / 10_000.0
    outcomes: list[dict[str, Any]] = []
    for code in candidate_codes:
        source = row_by_code[code]
        item: dict[str, Any] = {"code": code, "status": source.get("status")}
        if source.get("status") == "usable":
            entry = float(source["entry_open"])
            exit_price = float(source["exit_close"])
            if (
                not math.isfinite(entry)
                or not math.isfinite(exit_price)
                or entry <= 0
                or exit_price <= 0
            ):
                raise ValueError("usable rows require finite positive prices")
            if source.get("session_dates") != expected_session_dates:
                raise ValueError("usable rows must match the exact frozen H5 session dates")
            if source.get("entry_date") != expected_session_dates[0]:
                raise ValueError("usable row entry date must match the first frozen session")
            if source.get("exit_date") != expected_session_dates[-1]:
                raise ValueError("usable row exit date must match the fifth frozen session")
            baseline_net = exit_price / entry - 1.0 - cost
            item.update(
                {
                    "entry_open": entry,
                    "exit_close": exit_price,
                    "baseline_long_after_cost_return": baseline_net,
                    "cash_treatment_return": 0.0,
                    "avoidance_benefit": -baseline_net,
                }
            )
        else:
            item["error"] = source.get("error")
        outcomes.append(item)

    usable = [row for row in outcomes if row["status"] == "usable"]
    benefits = [float(row["avoidance_benefit"]) for row in usable]
    mean_benefit = sum(benefits) / len(benefits) if benefits else None
    median_benefit = median(benefits) if benefits else None
    underperform_share = (
        sum(value > 0 for value in benefits) / len(benefits) if benefits else None
    )
    coverage_pass = len(usable) >= 10
    effect_checks = {
        "mean_avoidance_benefit_positive": mean_benefit is not None
        and mean_benefit > 0,
        "median_avoidance_benefit_positive": median_benefit is not None
        and median_benefit > 0,
        "baseline_underperform_cash_share_gt_half": underperform_share is not None
        and underperform_share > 0.5,
    }
    directional_checks = {
        "usable_security_count_gte_10": coverage_pass,
        **effect_checks,
    }
    directional_pass = coverage_pass and all(effect_checks.values())
    observed_only_lead_eligible = directional_pass and len(usable) >= 30
    if not coverage_pass:
        disposition = "inconclusive_insufficient_sample"
        scientific_classification = "inconclusive_data_coverage"
    elif observed_only_lead_eligible:
        disposition = "positive_replay_lead_not_promoted"
        scientific_classification = "observed_only_positive_lead"
    elif directional_pass:
        disposition = "inconclusive_insufficient_sample"
        scientific_classification = "inconclusive_positive_scout"
    else:
        disposition = "rejected"
        scientific_classification = "falsified_or_indistinguishable"
    return {
        "candidate_count": len(candidate_codes),
        "usable_security_count": len(usable),
        "missing_or_error_count": len(candidate_codes) - len(usable),
        "round_trip_cost_bps": cost_bps,
        "mean_avoidance_benefit": mean_benefit,
        "median_avoidance_benefit": median_benefit,
        "baseline_underperform_cash_share": underperform_share,
        "directional_checks": directional_checks,
        "directional_pass": directional_pass,
        "observed_only_lead_eligible": observed_only_lead_eligible,
        "diagnostic_disposition": disposition,
        "scientific_classification": scientific_classification,
        "candidate_outcomes": outcomes,
    }


def build(*, freeze_at: str, history_cutoff: str, out_dir: Path = OUT) -> dict[str, Any]:
    freeze_time = _utc(freeze_at, field="freeze_at")
    history_cutoff_time = _utc(history_cutoff, field="history_cutoff")
    if history_cutoff_time > freeze_time:
        raise ValueError("history_cutoff cannot be after freeze_at")
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    if bundle.get("daily_index_total_rows") != 4183:
        raise ValueError("origin bundle daily-index population drifted")
    if bundle.get("pit_tier") != "research_pit" or bundle.get("trade_enabled") is not False:
        raise ValueError("origin bundle lost its research-only/default-off boundary")
    index_artifact = _artifact(bundle, "daily_form_index")
    mapping_artifact = _artifact(bundle, "security_mapping")
    access_artifact = _artifact(bundle, "authorization_access")
    reuse_artifact = _artifact(bundle, "authorization_reuse")
    rows = _parse_daily_index(INDEX.read_bytes(), form_date="20260820")
    associations = _parse_company_exchange(MAPPING.read_bytes())
    if len(rows) != 4183 or len(associations) != 10387:
        raise ValueError("frozen SEC source population drifted")
    known_at = max(index_artifact["retrieved_at"], mapping_artifact["retrieved_at"])
    known_time = _utc(known_at, field="source known_at")
    entry_time = _utc(ENTRY_AT, field="entry_at")
    exit_time = _utc(EXIT_AT, field="exit_at")
    if known_time > freeze_time:
        raise ValueError("source known_at cannot be after freeze_at")
    if known_time >= entry_time:
        raise ValueError("source was not known before the frozen next-session entry")
    if entry_time >= exit_time:
        raise ValueError("entry_at must be before exit_at")
    by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for association in associations:
        by_cik[association["cik"]].append(association)

    disposition_rows: list[dict[str, Any]] = []
    mapped_rows: list[dict[str, Any]] = []
    for source in rows:
        source_row_id = (
            f"sec-edgar-{source['accession']}-line-{source['line_number']:06d}"
        )
        row: dict[str, Any] = {
            "source_row_id": source_row_id,
            "source_row_sha256": canonical_hash(source),
            "line_number": source["line_number"],
            "form_type": source["form_type"],
            "company_name": source["company_name"],
            "cik": source["cik"],
            "date_filed": source["date_filed"],
            "filing_path": source["filing_path"],
            "accession": source["accession"],
            "known_at": known_at,
        }
        if source["form_type"] != TARGET_FORM:
            row.update(
                {
                    "disposition": "non_target_form",
                    "reason_code": "form_type_not_correspondence",
                }
            )
        else:
            matches = by_cik.get(source["cik"], [])
            if not matches:
                row.update(
                    {
                        "disposition": "unmapped",
                        "reason_code": "sec_company_exchange_missing",
                    }
                )
            elif len(matches) != 1:
                row.update(
                    {
                        "disposition": "unmapped",
                        "reason_code": "sec_company_exchange_ambiguous",
                    }
                )
            elif matches[0]["exchange"] not in ACCEPTED_EXCHANGES:
                row.update(
                    {
                        "disposition": "excluded",
                        "reason_code": "sec_exchange_unsupported",
                    }
                )
            else:
                mapping = _mapping_payload(
                    association=matches[0],
                    mapping_sha256=mapping_artifact["sha256"],
                    known_at=known_at,
                )
                row.update(
                    {
                        "disposition": "mapped",
                        "reason_code": "exact_cik_single_supported_exchange",
                        "mapping": mapping,
                    }
                )
                mapped_rows.append(row)
        disposition_rows.append(row)

    counts: dict[str, int] = defaultdict(int)
    reason_counts: dict[str, int] = defaultdict(int)
    for row in disposition_rows:
        counts[row["disposition"]] += 1
        reason_counts[row["reason_code"]] += 1
    expected_counts = {
        "excluded": 2,
        "mapped": 20,
        "non_target_form": 4116,
        "unmapped": 45,
    }
    if dict(sorted(counts.items())) != expected_counts:
        raise ValueError(f"CORRESP disposition counts drifted: {dict(counts)}")
    target_rows = [row for row in disposition_rows if row["form_type"] == TARGET_FORM]
    if len(target_rows) != 67:
        raise ValueError("expected exactly 67 CORRESP rows")
    row_ids = [row["source_row_id"] for row in disposition_rows]
    row_hashes = [row["source_row_sha256"] for row in disposition_rows]
    if len(set(row_ids)) != len(rows) or len(set(row_hashes)) != len(rows):
        raise ValueError("daily-index row identities are not unique")

    source_artifacts = {
        _relative(path): _sha256(path)
        for path in (BUNDLE, INDEX, MAPPING, BUNDLE_DIR / access_artifact["filename"], BUNDLE_DIR / reuse_artifact["filename"])
    }
    disposition = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_source_disposition_manifest",
            "scope_id": "sec-edgar-correspondence-public-release-20260820-complete-index",
            "origin_bundle": _relative(BUNDLE),
            "origin_bundle_sha256": _sha256(BUNDLE),
            "origin_bundle_declared_form_type": bundle["form_type"],
            "origin_bundle_scope_reused": False,
            "reused_raw_artifacts_only": True,
            "source_artifact_snapshot_hashes": source_artifacts,
            "authorization_status": "pass_official_sec_public_access_and_reuse_artifacts",
            "target_form_type": TARGET_FORM,
            "target_form_match": "exact_case_sensitive",
            "data_cutoff": known_at,
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "source_reported_row_count": len(rows),
            "target_form_row_count": len(target_rows),
            "disposition_counts": dict(sorted(counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "row_count_conserved": sum(counts.values()) == len(rows),
            "row_ids_unique": True,
            "row_hashes_unique": True,
            "dispositions_mutually_exclusive": True,
            "rows": disposition_rows,
            "external_universe_coverage_status": "unverified",
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "manifest_hash",
    )
    disposition_path = out_dir / "source_disposition_manifest.json"
    _write(disposition_path, disposition)

    candidates_by_listing: dict[str, dict[str, Any]] = {}
    for row in mapped_rows:
        mapping = row["mapping"]
        candidate = candidates_by_listing.setdefault(
            mapping["listing_id"],
            {
                "security_id": mapping["security_id"],
                "listing_id": mapping["listing_id"],
                "symbol": mapping["symbol"],
                "mic": mapping["mic"],
                "mapping_id": mapping["mapping_id"],
                "mapping_sha256": mapping["mapping_sha256"],
                "source_row_ids": [],
                "source_row_hashes": [],
                "admission_status": "admitted",
                "reason": "mapped CORRESP public-release row in the complete frozen index",
            },
        )
        candidate["source_row_ids"].append(row["source_row_id"])
        candidate["source_row_hashes"].append(row["source_row_sha256"])
    candidates = sorted(candidates_by_listing.values(), key=lambda row: row["listing_id"])
    for candidate in candidates:
        candidate["source_row_ids"].sort()
        candidate["source_row_hashes"].sort()
    if len(candidates) != 17:
        raise ValueError("expected 17 deduplicated mapped CORRESP issuers")
    mapped_listing_set = {row["mapping"]["listing_id"] for row in mapped_rows}
    if {row["listing_id"] for row in candidates} != mapped_listing_set:
        raise ValueError("CandidatePool does not equal mapped rows after deduplication")

    candidate_pool = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_candidate_pool",
            "candidate_pool_id": "sec-correspondence-information-risk-h5-20260821",
            "source_disposition_manifest_hash": disposition["manifest_hash"],
            "source_row_count": len(rows),
            "target_form_row_count": len(target_rows),
            "mapped_source_row_count": len(mapped_rows),
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
    candidate_pool_path = out_dir / "candidate_pool.json"
    _write(candidate_pool_path, candidate_pool)

    codes = [f"US.{row['symbol']}" for row in candidates]
    recipe = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_research_market_evaluation_recipe",
            "provider": "moomoo OpenAPI via local authenticated OpenD",
            "opend_endpoint": "127.0.0.1:11111",
            "codes": codes,
            "expected_session_dates": EXPECTED_SESSION_DATES,
            "start_date": "2026-08-21",
            "end_date": "2026-08-27",
            "bar_type": "K_DAY",
            "adjustment": "NONE",
            "session": "RTH",
            "entry_field": "first_session_open",
            "exit_field": "fifth_session_close",
            "horizon_sessions": 5,
            "round_trip_cost_bps": 10.0,
            "baseline": "equal_weight_next_session_open_long_held_h5",
            "treatment": "avoid_long_and_hold_cash",
            "comparators": ["cash"],
            "primary_statistic": "equal_weight_mean_cash_minus_baseline_long_after_cost",
            "minimum_evaluable_security_count": 10,
            "minimum_positive_lead_security_count": 30,
            "acceptance_rule": (
                "directional scout passes iff usable>=10, mean and median avoidance benefit "
                "are positive, and more than half of baseline longs underperform cash; a positive "
                "result with usable<30 remains rejected/inconclusive_insufficient_sample"
            ),
            "falsifier": (
                "with usable>=10, any directional effect predicate fails; usable<10 is "
                "inconclusive_insufficient_sample rather than falsification"
            ),
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
            "order_intent_count": 0,
            "outcomes_accessed_before_freeze": False,
        },
        "recipe_hash",
    )
    recipe_path = out_dir / "market_data_recipe.json"
    _write(recipe_path, recipe)

    decision = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_decision_record",
            "decision_id": "sec-correspondence-h5-avoid-long-all-mapped",
            "candidate_pool_id": candidate_pool["candidate_pool_id"],
            "candidate_pool_hash": candidate_pool["candidate_pool_hash"],
            "policy": "exclude every mapped CORRESP issuer from long admission and hold cash",
            "baseline_policy": "buy every mapped issuer at next-session open and exit H5 close",
            "selection_count": len(candidates),
            "selected_security_ids": [row["security_id"] for row in candidates],
            "signal_known_at": known_at,
            "entry_at": ENTRY_AT,
            "exit_at": EXIT_AT,
            "market_data_recipe_hash": recipe["recipe_hash"],
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "outcome_values_read": False,
            "engine0_policy_invoked": False,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
            "order_intent_count": 0,
        },
        "decision_hash",
    )
    decision_path = out_dir / "decision_record.json"
    _write(decision_path, decision)

    artifact_paths = [BUNDLE, INDEX, MAPPING, disposition_path, candidate_pool_path, recipe_path, decision_path]
    hashes = {_relative(path): _sha256(path) for path in artifact_paths}
    surfaces = {
        "schema_version": 1,
        "surfaces": [
            {
                "surface_id": "fixed_cash_opportunity_cost_comparator_v1",
                "data_source": "fixed_cash_opportunity_cost_comparator",
                "component_sources": ["fixed_cash_opportunity_cost_comparator"],
                "roles": ["market_expectation", "opportunity_cost"],
                "artifacts": [_relative(recipe_path)],
                "artifact_snapshot_hashes": {_relative(recipe_path): hashes[_relative(recipe_path)]},
                "pit_status": "canonical_pit",
                "evidence_grade": "gate_candidate",
                "settled_count": 1,
                "independent_count": 1,
                "candidate_overlap_count": len(candidates),
                "gate_ready": True,
                "expectation_proxy": {"type": "fixed_zero_cash_comparator", "field": "cash_return", "source": "fixed_cash_opportunity_cost_comparator"},
                "saturation_status": "open",
                "reopen_condition": None,
                "source_contract_status": "pass",
                "as_of": freeze_at,
            },
            {
                "surface_id": "v2_sec_edgar_correspondence_public_release_20260820",
                "data_source": "sec_edgar_daily_form_index_correspondence",
                "component_sources": ["sec_edgar_daily_form_index_correspondence"],
                "roles": ["independent_evidence", "candidate_universe", "candidate_pool"],
                "artifacts": [_relative(path) for path in (BUNDLE, INDEX, MAPPING, disposition_path, candidate_pool_path, decision_path)],
                "artifact_snapshot_hashes": {key: value for key, value in hashes.items() if key != _relative(recipe_path)},
                "pit_status": "research_pit",
                "evidence_grade": "lead",
                "settled_count": 0,
                "independent_count": len(candidates),
                "candidate_overlap_count": len(candidates),
                "gate_ready": False,
                "expectation_proxy": None,
                "saturation_status": "open",
                "reopen_condition": "A separately frozen later complete daily index under the unchanged CORRESP avoid-long policy.",
                "source_contract_status": "pass",
                "as_of": known_at,
                "research_pit_basis": (
                    "Official complete SEC daily index and same-freeze association mapping are hash-bound; "
                    "all 4183 rows retain mutually exclusive disposition before outcomes, while vintage and "
                    "market-wide coverage remain unverified."
                ),
                "known_future_leakage": False,
            },
            {
                "surface_id": "moomoo_rth_daily_evaluation_recipe_correspondence_h5",
                "data_source": "moomoo_daily_ohlcv",
                "component_sources": ["moomoo_daily_ohlcv"],
                "roles": ["price_revealed_context"],
                "artifacts": [_relative(recipe_path)],
                "artifact_snapshot_hashes": {_relative(recipe_path): hashes[_relative(recipe_path)]},
                "pit_status": "research_pit",
                "evidence_grade": "lead",
                "settled_count": 0,
                "independent_count": len(candidates),
                "candidate_overlap_count": len(candidates),
                "gate_ready": False,
                "expectation_proxy": None,
                "saturation_status": "open",
                "reopen_condition": "No retry on this date, horizon, cost, or candidate frame.",
                "source_contract_status": "pass",
                "as_of": freeze_at,
                "research_pit_basis": (
                    "Exact codes, session range, adjustment, fields, horizon, costs, and cash comparator "
                    "are frozen before any returned price row is read."
                ),
                "known_future_leakage": False,
            },
        ],
    }
    registry = EvidenceSurfaceRegistry.from_dict(surfaces)
    surfaces = registry.to_dict()
    surface_path = out_dir / "evidence_surfaces.json"
    _write(surface_path, surfaces)
    prior = build_historical_prior_snapshot(
        ROOT / "docs/frozen_families.jsonl",
        history_cutoff=history_cutoff,
        repo_root=ROOT,
    )
    prior_path = out_dir / "prior_fingerprints.json"
    _write(prior_path, prior)

    hypothesis = (
        "Within the complete frozen 2026-08-20 SEC daily index, public release of a CORRESP "
        "staff-comment row identifies disclosure-risk issuers whose next-session-open long exposure "
        "underperforms cash through the fifth regular-session close after 10 bps cost; therefore an "
        "avoid-long cash-replacement rule has positive H5 avoidance benefit."
    )
    raw_candidate = {
        "schema_version": 1,
        "candidate_kind": "expectation_gap",
        "candidate_id": "pending",
        "search_queue": "exploration",
        "title": "V2 SEC CORRESP public-release H5 information-risk exclusion",
        "created_at": freeze_at,
        "created_by": "codex-edge-v2-automation",
        "hypothesis": hypothesis,
        "fingerprint": {
            "data_source": "sec_edgar_daily_form_index_correspondence",
            "component_sources": ["fixed_cash_opportunity_cost_comparator", "moomoo_daily_ohlcv", "sec_edgar_daily_form_index_correspondence"],
            "expectation_proxy": "fixed_zero_cash_comparator",
            "economic_mechanism": "public_staff_correspondence_disclosure_information_risk",
            "decision_surface": "candidate_pool",
            "payoff_shape": "avoid_long_cash_replacement_h5",
            "horizon": "next_regular_open_to_fifth_session_close",
            "execution_dependency": "rth_daily_open_close_with_fixed_cost",
            "portfolio_role": "source_bounded_long_admission_exclusion_scout",
        },
        "surface_ids": sorted(registry.surface_ids),
        "expectation_gap": {
            "market_prior": {"observable": True, "proxy_type": "fixed_zero_cash_comparator", "source": "fixed_cash_opportunity_cost_comparator", "known_at": freeze_at, "value": 0.0},
            "independent_evidence": [{"source": "sec_edgar_daily_form_index_correspondence", "known_at": known_at, "fact": "complete outcome-blind CORRESP public-release disposition"}],
            "our_posterior": {"method": "predeclared_disclosure_risk_avoidance_prior_v1", "calibration_reference": "fast-falsification-scout-20260902", "known_at": freeze_at, "value": 0.005},
            "gap_definition": "predeclared positive cash-minus-baseline-long H5 avoidance benefit",
            "transmission": {"catalyst": "SEC CORRESP row publicly disseminated before the next market open", "affected_tickers": [row["symbol"] for row in candidates], "expected_direction": "baseline long underperforms cash", "half_life": "five regular trading sessions"},
        },
        "why_not_arbitraged": "Comment-letter releases are heterogeneous and delayed, and only a small complete cross-section is available; any exclusion value may be weak or already priced.",
        "falsifier": recipe["falsifier"],
        "baseline": {"policy": recipe["baseline"]},
        "treatment": {"policy": recipe["treatment"], "candidate_pool": _relative(candidate_pool_path), "decision_record": _relative(decision_path)},
        "replacement_value_comparator": "cash over the identical H5 holding interval",
        "expected_horizon": "next_regular_open_to_fifth_session_close",
        "execution_envelope": {"intended_instrument": "cash-equity long admission exclusion for measurement only", "liquidity_dependency": "missing/non-positive/incomplete five-session bars are excluded and counted", "costs_and_carry": "10 bps baseline round-trip cost; cash treatment fixed at zero", "borrow_dependency": "none; no short position", "capacity_constraint": "equal-weight descriptive basket; no deployable-capacity claim", "timing_constraint": "source frozen before 2026-08-21 13:30Z; exit fixed at fifth-session close", "trade_enabled": False},
        "evidence_grade": "lead",
        "next_machine_action": "Reserve, claim, fetch the frozen daily bars once, evaluate, and close.",
        "production_impact": research_only_production_impact(),
        "source_readiness_snapshot": sorted(
            [{"surface_id": row["surface_id"], "snapshot_hash": canonical_hash(row)} for row in surfaces["surfaces"]],
            key=lambda row: row["surface_id"],
        ),
        "prediction": {
            "success_probability": 0.25,
            "main_failure_modes": ["public_release_is_stale", "heterogeneous_letters_cancel", "sample_below_30", "baseline_does_not_underperform_cash"],
            "confidence_reason": "Disclosure scrutiny can delay long-entry recovery, and the complete frame has 17 mapped issuers; however public comment letters may be stale and the sample cannot support promotion, so the scout is more likely to falsify than establish a lead.",
        },
        "reopen_condition": "Do not retune the form/date/H5/cost/mapping or subsets. Reopen only with a separately frozen later complete daily index under the unchanged policy or a distinct causal source.",
    }
    candidate = HypothesisCandidate.with_computed_id(raw_candidate).to_dict()
    scope = build_selection_scope_manifest(
        scope_name="v2-sec-correspondence-information-risk-h5-20260902",
        preregistered_at=freeze_at,
        data_cutoff=freeze_at,
        freeze_at=freeze_at,
        generator_version="v2-sec-correspondence-information-risk-h5-v1",
        candidate_generation_config={
            "outcome_fields_allowed": False,
            "candidate_specific_results_access": False,
            "selection_limit": 1,
            "selection_policy": "select the only complete-frame candidate if D0-D3 pass",
            "fast_falsification_scout": True,
            "primary_horizon_estimated_decision_count": len(candidates),
            "minimum_primary_horizon_decision_count": 10,
            "relaxed_dimensions": ["single_candidate_panel", "sample_below_30_limits_verdict", "cash_only_comparator", "no_engine0_or_market_wide_coverage_required"],
            "non_relaxed_dimensions": ["outcome_blind_freeze", "complete_4183_row_disposition", "hash_bound_inputs", "exact_duplicate_and_contamination_guard", "trade_enabled_false"],
        },
        allowed_surface_ids=list(registry.surface_ids),
        surface_registry_hash=registry.canonical_hash,
        prior_fingerprints=prior,
        queue_budgets={"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=1,
        selection_limit=1,
    )
    scope_path = out_dir / "selection_scope.json"
    _write(scope_path, scope)
    panel = freeze_selection_panel(
        [candidate],
        registry,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
        repo_root=ROOT,
    )
    panel_path = out_dir / "selection_panel.json"
    _write(panel_path, panel)
    if panel["selected_candidate_ids"] != [candidate["candidate_id"]]:
        raise ValueError("candidate did not pass D0-D3: " + json.dumps(panel["preflight_decisions"], ensure_ascii=False))
    proposal = normalize_ticket_proposal(
        {
            "lane": "alpha_search",
            "hypothesis": hypothesis,
            "change_type": "private_replay_scout",
            "single_causal_variable": "sec_correspondence_public_release_h5_avoid_long",
            "causal_components": ["complete 4183-row source disposition", "17-security mapped deduplicated CandidatePool", "cash replacement treatment", "next-open through H5-close horizon", "10 bps baseline round-trip cost", "observed-only ceiling"],
            "mechanism_family": "sec_correspondence_public_release_information_risk",
            "trial_family": "v2_sec_correspondence_public_release_h5_scout",
            "changed_variable": "correspondence_public_release_long_admission_exclusion",
            "prediction": {**raw_candidate["prediction"], "expected_ev_delta": None, "expected_pnl_delta": None},
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
    promotion_path = out_dir / "promotion_request.json"
    _write(promotion_path, promotion)
    report = {
        "schema_version": 1,
        "record_type": "v2_scout_admission_preflight",
        "candidate_id": candidate["candidate_id"],
        "selection_scope_id": panel["selection_scope_id"],
        "preflight": panel["preflight_decisions"][candidate["candidate_id"]],
        "source_row_count": len(rows),
        "target_form_row_count": len(target_rows),
        "mapped_source_row_count": len(mapped_rows),
        "candidate_pool_count": len(candidates),
        "primary_horizon_estimated_decision_count": len(candidates),
        "disposition_counts": dict(sorted(counts.items())),
        "promotion_request": _relative(promotion_path),
        "promotion_hash": promotion["promotion_hash"],
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
    }
    _write(out_dir / "preflight_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-at", required=True)
    parser.add_argument("--history-cutoff", required=True)
    args = parser.parse_args()
    print(json.dumps(build(freeze_at=args.freeze_at, history_cutoff=args.history_cutoff), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
