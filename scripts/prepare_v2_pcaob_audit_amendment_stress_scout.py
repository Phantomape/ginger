"""Freeze outcome-blind admission inputs for the PCAOB amendment-stress scout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import zipfile
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
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
from scripts.alpha_debate import (  # noqa: E402
    build_promotion_request,
    normalize_ticket_proposal,
)


MEMBER = "FirmFilings.csv"
AUDIT_REPORT_TYPE = (
    "Issuer, other than Employee Benefit Plan or Investment Company"
)
OFFICIAL_ARCHIVE_SHA256 = (
    "0f51a6b213da6dff8087d41a251545a5280143429492233d0ee798f00e4d1396"
)
OFFICIAL_FRAME_ROWS = 942
WINDOW_START = date(2023, 9, 1)
WINDOW_END = date(2026, 6, 1)
HORIZON_SESSIONS = 5
STRESS_MIN_COUNT = 3
NEGATIVE_CONTROL_COUNT = 1
ROUND_TRIP_COST_BPS = 10.0
EXPECTED_STRESS_DECISIONS = 48
EXPECTED_CONTROL_DECISIONS = 29
SPY_SECURITY_ID = "US.SPY"
DEFAULT_MANIFEST = ROOT / "data/non_ohlcv/pcaob_form_ap/source_manifest.json"
DEFAULT_ARCHIVE = ROOT / (
    "data/non_ohlcv/pcaob_form_ap/source/FirmFilings_20260716.zip"
)
DEFAULT_OUT = ROOT / "data/v2/scouts/pcaob_audit_amendment_stress_h5_20260901"
CALENDAR_SQL = (
    "SELECT rowid, ticker, date FROM ohlcv "
    "WHERE ticker=? ORDER BY date, rowid"
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    row = dict(value)
    row[field] = canonical_hash(row)
    return row


def _parse_date(value: str, field: str) -> date:
    text = str(value).strip()
    for pattern in (
        "%Y-%m-%d",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise ValueError(f"invalid {field}: {value!r}")


def _load_source_frame(
    manifest_path: Path, archive_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    archive_sha = _sha256(archive_path)
    if archive_sha != manifest.get("archive_sha256"):
        raise ValueError("PCAOB archive hash does not match its source manifest")
    if archive_path.stat().st_size != manifest.get("archive_bytes"):
        raise ValueError("PCAOB archive byte count does not match its source manifest")
    entries = manifest.get("zip_entries") or []
    if (
        len(entries) != 1
        or entries[0].get("name") != MEMBER
        or int(entries[0].get("uncompressed_bytes") or 0) <= 0
    ):
        raise ValueError("unexpected PCAOB ZIP member contract")
    if archive_sha == OFFICIAL_ARCHIVE_SHA256 and entries[0].get(
        "uncompressed_bytes"
    ) != 93094798:
        raise ValueError("official PCAOB member byte contract drifted")

    required = {
        "Form Filing ID",
        "Amendment Audit Report",
        "Audit Report Type",
        "Filing Date",
    }
    frame: list[dict[str, Any]] = []
    source_rows = 0
    with zipfile.ZipFile(archive_path) as zipped:
        info = zipped.getinfo(MEMBER)
        if info.file_size != entries[0]["uncompressed_bytes"]:
            raise ValueError("PCAOB member byte count drifted")
        with zipped.open(MEMBER) as raw:
            reader = csv.DictReader(
                (line.decode("utf-8-sig") for line in raw)
            )
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError("PCAOB member is missing required columns")
            for source_rows, source in enumerate(reader, start=1):
                if str(source["Amendment Audit Report"]).strip().lower() != "true":
                    continue
                if str(source["Audit Report Type"]).strip() != AUDIT_REPORT_TYPE:
                    continue
                filing_id = str(source["Form Filing ID"]).strip()
                filing_date = _parse_date(source["Filing Date"], "Filing Date")
                identity = {
                    "form_filing_id": filing_id,
                    "amendment_audit_report": "true",
                    "audit_report_type": AUDIT_REPORT_TYPE,
                    "filing_date": filing_date.isoformat(),
                }
                frame.append(
                    {
                        "source_row_id": f"pcaob-form-ap:{filing_id}",
                        "source_row_sha256": canonical_hash(identity),
                        **identity,
                    }
                )

    ids = [row["source_row_id"] for row in frame]
    hashes = [row["source_row_sha256"] for row in frame]
    if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
        raise ValueError("PCAOB frame row identities are not unique")
    if archive_sha == OFFICIAL_ARCHIVE_SHA256 and len(frame) != OFFICIAL_FRAME_ROWS:
        raise ValueError("official PCAOB amendment frame is not the frozen 942 rows")
    report = {
        "archive_sha256": archive_sha,
        "archive_bytes": archive_path.stat().st_size,
        "member": MEMBER,
        "member_bytes": info.file_size,
        "upstream_source_row_count": source_rows,
        "frame_row_count": len(frame),
        "filter_excluded_row_count": source_rows - len(frame),
    }
    return manifest, frame, report


def _load_spy_calendar(warehouse_path: Path) -> tuple[list[date], dict[str, Any]]:
    if not warehouse_path.is_file():
        raise ValueError("explicit outcome warehouse does not exist")
    uri = f"file:{warehouse_path.resolve().as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(CALENDAR_SQL, ("SPY",)).fetchall()
    finally:
        connection.close()
    if not rows:
        raise ValueError("SPY calendar preflight returned no rows")
    if any(str(ticker) != "SPY" for _, ticker, _ in rows):
        raise ValueError("SPY calendar query returned a foreign ticker")
    sessions = [_parse_date(value, "ohlcv.date") for _, _, value in rows]
    if sessions != sorted(sessions) or len(sessions) != len(set(sessions)):
        raise ValueError("SPY calendar dates must be sorted and unique")
    calendar_rows = [
        {
            "row_identity": canonical_hash(
                {"rowid": int(rowid), "ticker": str(ticker), "date": str(value)}
            ),
            "ticker": str(ticker),
            "date": str(value),
        }
        for rowid, ticker, value in rows
    ]
    return sessions, {
        "warehouse_sha256": _sha256(warehouse_path),
        "warehouse_bytes": warehouse_path.stat().st_size,
        "table": "ohlcv",
        "ticker": "SPY",
        "calendar_row_count": len(calendar_rows),
        "calendar_rows": calendar_rows,
        "outcome_columns_read": [],
        "outcome_values_read": False,
        "query_contract": "rowid/ticker/date only",
    }


def _decision_panel(
    frame: list[dict[str, Any]], sessions: list[date]
) -> list[dict[str, Any]]:
    by_week: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in frame:
        filing_date = _parse_date(row["filing_date"], "filing_date")
        week_start = filing_date - timedelta(days=filing_date.weekday())
        by_week[week_start].append(row)

    panel: list[dict[str, Any]] = []
    for week_start, week_rows in sorted(by_week.items()):
        target = week_start + timedelta(days=8)  # next-week Tuesday
        entry_index = bisect_left(sessions, target)
        entry = sessions[entry_index] if entry_index < len(sessions) else None
        exit_index = entry_index + HORIZON_SESSIONS - 1
        exit_session = sessions[exit_index] if exit_index < len(sessions) else None
        count = len(week_rows)
        if entry is None or exit_session is None:
            cohort = "not_reachable"
        elif not (WINDOW_START <= entry <= WINDOW_END):
            cohort = "outside_window"
        elif count >= STRESS_MIN_COUNT:
            cohort = "amendment_stress"
        elif count == NEGATIVE_CONTROL_COUNT:
            cohort = "count_one_negative_control"
        else:
            cohort = "count_two_neutral"
        panel.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "amendment_filing_count": count,
                "cohort": cohort,
                "source_row_ids": sorted(row["source_row_id"] for row in week_rows),
                "entry_session_date": entry.isoformat() if entry else None,
                "exit_session_date": exit_session.isoformat() if exit_session else None,
            }
        )
    return panel


def build(
    *,
    freeze_at: str,
    history_cutoff: str,
    warehouse_path: Path,
    source_manifest_path: Path = DEFAULT_MANIFEST,
    archive_path: Path = DEFAULT_ARCHIVE,
    output_dir: Path = DEFAULT_OUT,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    manifest, frame, source_report = _load_source_frame(
        source_manifest_path, archive_path
    )
    sessions, calendar = _load_spy_calendar(warehouse_path)
    panel = _decision_panel(frame, sessions)
    counts = Counter(row["cohort"] for row in panel)
    if source_report["archive_sha256"] == OFFICIAL_ARCHIVE_SHA256:
        if counts["amendment_stress"] != EXPECTED_STRESS_DECISIONS:
            raise ValueError("official PCAOB stress decision count drifted")
        if counts["count_one_negative_control"] != EXPECTED_CONTROL_DECISIONS:
            raise ValueError("official PCAOB negative-control decision count drifted")

    output_dir.mkdir(parents=True, exist_ok=True)
    mapped_rows = [
        {
            **row,
            "published_at": row["filing_date"],
            "known_at_contract": "Filing Date plus one PCAOB daily-update cycle",
            "disposition": "mapped",
            "reason_code": "mapped_to_market_sensor",
            "reason": "complete audit-report-amendment frame maps to aggregate SPY stress sensor",
            "security_mapping": {
                "security_id": SPY_SECURITY_ID,
                "listing_id": SPY_SECURITY_ID,
                "mapping_type": "aggregate_market_sensor_not_issuer_mapping",
            },
        }
        for row in frame
    ]
    disposition = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_source_disposition_manifest",
            "scope_id": "pcaob-form-ap-audit-report-amendments-complete-frame",
            "source_manifest": _relative(source_manifest_path, repo_root),
            "source_manifest_sha256": _sha256(source_manifest_path),
            "source_archive": _relative(archive_path, repo_root),
            "source_archive_sha256": source_report["archive_sha256"],
            "source_member": MEMBER,
            "source_filter": {
                "amendment_audit_report": "true",
                "audit_report_type": AUDIT_REPORT_TYPE,
                "forbidden_field": "Latest Form AP Filing",
            },
            "upstream_source_row_count": source_report["upstream_source_row_count"],
            "source_reported_row_count": len(mapped_rows),
            "disposition_counts": {
                "mapped": len(mapped_rows),
                "excluded": 0,
                "unmapped": 0,
            },
            "row_count_conserved": True,
            "row_ids_unique": True,
            "row_hashes_unique": True,
            "dispositions_mutually_exclusive": True,
            "rows": mapped_rows,
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "manifest_hash",
    )
    disposition_path = output_dir / "source_disposition_manifest.json"
    _write(disposition_path, disposition)

    candidate_pool = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_candidate_pool",
            "candidate_pool_id": "pcaob-audit-amendment-stress-spy-h5",
            "source_disposition_manifest_hash": disposition["manifest_hash"],
            "source_row_count": len(mapped_rows),
            "mapped_source_row_count": len(mapped_rows),
            "candidate_count": 1,
            "candidate_security_set_equals_mapped_deduplicated_set": True,
            "candidates": [
                {
                    "security_id": SPY_SECURITY_ID,
                    "listing_id": SPY_SECURITY_ID,
                    "symbol": "SPY",
                    "mic": "ARCX",
                    "admission_status": "admitted",
                    "mapping_type": "aggregate_market_sensor_not_issuer_mapping",
                    "reason": "SPY is the frozen market-stress measurement target",
                }
            ],
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "candidate_pool_hash",
    )
    pool_path = output_dir / "candidate_pool.json"
    _write(pool_path, candidate_pool)

    calendar_artifact = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_outcome_blind_warehouse_calendar_preflight",
            **calendar,
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
            "horizon_sessions": HORIZON_SESSIONS,
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "calendar_hash",
    )
    calendar_path = output_dir / "warehouse_calendar_preflight.json"
    _write(calendar_path, calendar_artifact)

    decision = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_experiment_local_decision_record",
            "decision_id": "pcaob-audit-amendment-stress-spy-h5-v1",
            "candidate_pool_id": candidate_pool["candidate_pool_id"],
            "candidate_pool_hash": candidate_pool["candidate_pool_hash"],
            "aggregation": "complete Monday-Sunday PCAOB filing weeks",
            "known_at_rule": (
                "after week-end plus one daily-update cycle; enter no earlier than "
                "the first SPY session on or after next-week Tuesday"
            ),
            "stress_rule": f"weekly amendment filing count >= {STRESS_MIN_COUNT}",
            "negative_control_rule": (
                f"weekly amendment filing count == {NEGATIVE_CONTROL_COUNT}"
            ),
            "neutral_rule": "weekly amendment filing count == 2",
            "entry_field": "open",
            "exit_field": "close",
            "horizon_sessions": HORIZON_SESSIONS,
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
            "stress_decision_count": counts["amendment_stress"],
            "negative_control_decision_count": counts[
                "count_one_negative_control"
            ],
            "weekly_panel": panel,
            "frozen_at": freeze_at,
            "outcome_blind": True,
            "outcome_values_read": False,
            "engine0_policy_invoked": False,
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "decision_hash",
    )
    decision_path = output_dir / "decision_record.json"
    _write(decision_path, decision)

    recipe = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_research_market_evaluation_recipe",
            "warehouse_identity": {
                "sha256": calendar["warehouse_sha256"],
                "bytes": calendar["warehouse_bytes"],
            },
            "table": "ohlcv",
            "ticker": "SPY",
            "entry_field": "open",
            "exit_field": "close",
            "session": "RTH",
            "horizon_sessions": HORIZON_SESSIONS,
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
            "baseline": "SPY open-to-H5-close return",
            "treatment": "hold cash instead of SPY during amendment-stress decisions",
            "replacement_value_comparator": "SPY",
            "negative_control": "otherwise identical count-one filing weeks",
            "primary_statistic": (
                "mean cash-after-cost minus SPY open-to-H5-close return"
            ),
            "minimum_evaluable_stress_decisions": 30,
            "acceptance_rule": (
                "diagnostic observed-only lead iff evaluable stress N>=30, stress "
                "mean cash-after-cost minus SPY return is positive, and that mean "
                "edge exceeds the identical count-one negative-control mean edge"
            ),
            "falsifier": (
                "stress N<30 is inconclusive_insufficient_sample; otherwise reject "
                "if either primary comparison is non-positive"
            ),
            "report_only_diagnostics": ["median_edge", "positive_edge_share"],
            "forbidden_post_outcome_changes": [
                "stress count threshold",
                "H5 horizon",
                "evaluation window",
                "round-trip cost",
            ],
            "frozen_at": freeze_at,
            "outcomes_accessed_before_freeze": False,
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "recipe_hash",
    )
    recipe_path = output_dir / "evaluation_recipe.json"
    _write(recipe_path, recipe)

    baseline = _self_hash(
        {
            "schema_version": 1,
            "record_type": "v2_outcome_free_baseline_measurement",
            "baseline": "SPY open-to-H5-close return",
            "treatment": "cash after 10 bps switching cost",
            "stress_decision_count": counts["amendment_stress"],
            "negative_control_decision_count": counts[
                "count_one_negative_control"
            ],
            "outcome_metrics": None,
            "outcome_values_read": False,
            "frozen_at": freeze_at,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "trade_enabled": False,
        },
        "baseline_hash",
    )
    baseline_path = output_dir / "baseline_measurement.json"
    _write(baseline_path, baseline)

    artifact_paths = [
        source_manifest_path,
        archive_path,
        disposition_path,
        pool_path,
        calendar_path,
        decision_path,
        recipe_path,
        baseline_path,
    ]
    hashes = {_relative(path, repo_root): _sha256(path) for path in artifact_paths}
    source_surface = {
        "surface_id": "pcaob_form_ap_audit_amendment_frame_20260716",
        "data_source": "pcaob_form_ap",
        "component_sources": ["pcaob_form_ap"],
        "roles": ["independent_evidence", "candidate_pool", "regime_filter"],
        "artifacts": [
            _relative(source_manifest_path, repo_root),
            _relative(archive_path, repo_root),
            _relative(disposition_path, repo_root),
            _relative(pool_path, repo_root),
            _relative(decision_path, repo_root),
        ],
        "artifact_snapshot_hashes": {
            _relative(path, repo_root): hashes[_relative(path, repo_root)]
            for path in (
                source_manifest_path,
                archive_path,
                disposition_path,
                pool_path,
                decision_path,
            )
        },
        "pit_status": "research_pit",
        "evidence_grade": "lead",
        "settled_count": 0,
        "independent_count": len(frame),
        "candidate_overlap_count": 1,
        "gate_ready": False,
        "expectation_proxy": None,
        "saturation_status": "open",
        "reopen_condition": (
            "Reopen only with an as-published PCAOB vintage or prospectively "
            "frozen later filing rows, never by retuning count/H5/window/cost."
        ),
        "source_contract_status": "pass",
        "as_of": manifest["fetched_at"],
        "research_pit_basis": (
            "Official public Form AP filing records use Filing Date plus one daily-update "
            "cycle and a strictly later open; the exact local archive is hash-bound, while "
            "historical vintages and revision history remain unverified."
        ),
        "known_future_leakage": False,
    }
    market_surface = {
        "surface_id": "spy_date_only_calendar_and_h5_recipe_20260901",
        "data_source": "local_ohlcv_warehouse",
        "component_sources": ["local_ohlcv_warehouse"],
        "roles": [
            "market_expectation",
            "price_revealed_context",
            "evaluation_clock",
        ],
        "artifacts": [
            _relative(calendar_path, repo_root),
            _relative(recipe_path, repo_root),
            _relative(baseline_path, repo_root),
        ],
        "artifact_snapshot_hashes": {
            _relative(path, repo_root): hashes[_relative(path, repo_root)]
            for path in (calendar_path, recipe_path, baseline_path)
        },
        "pit_status": "research_pit",
        "evidence_grade": "lead",
        "settled_count": 0,
        "independent_count": counts["amendment_stress"],
        "candidate_overlap_count": 1,
        "gate_ready": False,
        "expectation_proxy": {
            "type": "price_revealed",
            "field": "predeclared_zero_cash_minus_spy_edge_prior",
            "source": "local_ohlcv_warehouse",
        },
        "saturation_status": "open",
        "reopen_condition": "No retry on the same frozen dates or alternate H5/cost.",
        "source_contract_status": "pass",
        "as_of": freeze_at,
        "research_pit_basis": (
            "Only SPY rowid/ticker/date were read before freeze; exact open/close values "
            "remain inaccessible until claim and are hash-bound at evaluation."
        ),
        "known_future_leakage": False,
    }
    registry = EvidenceSurfaceRegistry.from_dict(
        {"schema_version": 1, "surfaces": [source_surface, market_surface]}
    )
    surfaces = registry.to_dict()
    surface_path = output_dir / "evidence_surfaces.json"
    _write(surface_path, surfaces)

    prior = build_historical_prior_snapshot(
        repo_root / "docs/frozen_families.jsonl",
        history_cutoff=history_cutoff,
        repo_root=repo_root,
    )
    prior_path = output_dir / "prior_fingerprints.json"
    _write(prior_path, prior)

    hypothesis = (
        "Weeks with at least three PCAOB Form AP audit-report amendments identify "
        "transient aggregate market stress, so replacing SPY with cash from the first "
        "eligible next-week Tuesday open through the fifth session close yields positive "
        "mean after-cost edge and exceeds otherwise identical count-one filing weeks."
    )
    raw_candidate: dict[str, Any] = {
        "schema_version": 1,
        "candidate_kind": "expectation_gap",
        "candidate_id": "pending",
        "search_queue": "exploration",
        "title": "PCAOB audit-report amendment stress cash switch",
        "created_at": freeze_at,
        "created_by": "codex-edge-v2-fast-falsification-scout",
        "hypothesis": hypothesis,
        "fingerprint": {
            "data_source": "pcaob_form_ap",
            "component_sources": ["pcaob_form_ap", "local_ohlcv_warehouse"],
            "expectation_proxy": "price_revealed",
            "economic_mechanism": "aggregate_audit_amendment_market_stress",
            "decision_surface": "regime_filter",
            "payoff_shape": "cash_replacement_during_stress_h5",
            "horizon": "next_week_tuesday_open_to_fifth_session_close",
            "execution_dependency": "spy_rth_open_close_fixed_cost",
            "portfolio_role": "aggregate_market_risk_off_scout",
        },
        "surface_ids": list(registry.surface_ids),
        "expectation_gap": {
            "market_prior": {
                "observable": True,
                "proxy_type": "price_revealed",
                "source": "local_ohlcv_warehouse",
                "known_at": freeze_at,
                "value": 0.0,
            },
            "independent_evidence": [
                {
                    "source": "pcaob_form_ap",
                    "known_at": manifest["fetched_at"],
                    "fact": "complete audit-report amendment filing frame",
                }
            ],
            "our_posterior": {
                "method": "predeclared_weekly_amendment_count_stress_prior_v1",
                "calibration_reference": "outcome-blind fast falsification",
                "known_at": freeze_at,
                "value": 0.0001,
            },
            "gap_definition": "positive cash-minus-SPY H5 edge in stress weeks",
            "transmission": {
                "catalyst": "clustered audit-report amendment filings",
                "affected_tickers": ["SPY"],
                "expected_direction": "cash outperforms SPY after switching cost",
                "half_life": "five regular sessions",
            },
        },
        "why_not_arbitraged": (
            "The audit amendment aggregate is obscure, slow-moving, and may be too weak "
            "or too stale to survive a conservative weekly clock and switching cost."
        ),
        "falsifier": recipe["falsifier"],
        "baseline": {"policy": "hold SPY over the frozen H5 window"},
        "treatment": {
            "policy": "hold cash during count>=3 amendment-stress weeks",
            "candidate_pool": _relative(pool_path, repo_root),
            "decision_record": _relative(decision_path, repo_root),
        },
        "replacement_value_comparator": "SPY over identical entry/exit sessions",
        "expected_horizon": "next_week_tuesday_open_to_fifth_session_close",
        "execution_envelope": {
            "intended_instrument": "SPY/cash measurement only",
            "liquidity_dependency": "SPY regular-session daily bars",
            "costs_and_carry": "10 bps switch cost; no cash yield credit",
            "borrow_dependency": "none",
            "capacity_constraint": "diagnostic only; no deployable-capacity claim",
            "timing_constraint": "first SPY session on/after next-week Tuesday",
            "trade_enabled": False,
        },
        "evidence_grade": "lead",
        "next_machine_action": "Reserve, claim, evaluate frozen SPY windows once, and close.",
        "production_impact": research_only_production_impact(),
        "source_readiness_snapshot": [
            {"surface_id": row["surface_id"], "snapshot_hash": canonical_hash(row)}
            for row in surfaces["surfaces"]
        ],
        "prediction": {
            "success_probability": 0.25,
            "main_failure_modes": [
                "amendment_timing_not_systemic",
                "spy_already_prices_stress",
                "count_one_control_matches_or_beats_stress",
                "warehouse_identity_drift",
            ],
            "confidence_reason": (
                "Clustered audit amendments plausibly proxy stress, but the aggregate link "
                "to SPY is indirect and the conservative clock likely removes most signal."
            ),
        },
        "reopen_condition": (
            "Do not retune threshold, H5, window, or cost after outcome access. Reopen "
            "only with an as-published PCAOB vintage or prospectively frozen new rows."
        ),
    }
    raw_candidate["source_readiness_snapshot"].sort(
        key=lambda row: row["surface_id"]
    )
    candidate = HypothesisCandidate.with_computed_id(raw_candidate).to_dict()

    scope = build_selection_scope_manifest(
        scope_name="v2-pcaob-audit-amendment-stress-h5-20260901",
        preregistered_at=freeze_at,
        data_cutoff=freeze_at,
        freeze_at=freeze_at,
        generator_version="v2-pcaob-audit-amendment-stress-h5-v1",
        candidate_generation_config={
            "outcome_fields_allowed": False,
            "candidate_specific_results_access": False,
            "selection_limit": 1,
            "selection_policy": "select the sole frozen candidate if D0-D3 pass",
            "fast_falsification_scout": True,
            "non_relaxed_dimensions": [
                "outcome_blind_freeze",
                "complete_source_frame_disposition",
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
    scope_path = output_dir / "selection_scope.json"
    _write(scope_path, scope)
    selection = freeze_selection_panel(
        [candidate],
        registry,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
        repo_root=repo_root,
    )
    panel_path = output_dir / "selection_panel.json"
    _write(panel_path, selection)
    if selection["selected_candidate_ids"] != [candidate["candidate_id"]]:
        raise ValueError(
            "candidate did not pass D0-D3: "
            + json.dumps(selection["preflight_decisions"], ensure_ascii=False)
        )

    proposal = normalize_ticket_proposal(
        {
            "lane": "alpha_search",
            "hypothesis": hypothesis,
            "change_type": "private_replay_scout",
            "single_causal_variable": "pcaob_amendment_count_gte3_cash_switch_h5",
            "causal_components": [
                "complete 942-row audit-report amendment frame",
                "Monday-Sunday count>=3 stress gate",
                "next-week Tuesday-or-later entry",
                "SPY H5 replacement comparator",
                "10 bps switching cost",
                "count-one negative control",
                "observed-only ceiling",
            ],
            "mechanism_family": "aggregate_audit_amendment_market_stress",
            "trial_family": "v2_pcaob_amendment_stress_h5_scout",
            "changed_variable": "weekly_audit_report_amendment_count_gte3",
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
        repo_root=repo_root,
    )
    promotion_path = output_dir / "promotion_request.json"
    _write(promotion_path, promotion)

    report = {
        "schema_version": 1,
        "record_type": "v2_scout_admission_preflight",
        "candidate_id": candidate["candidate_id"],
        "selection_scope_id": selection["selection_scope_id"],
        "preflight": selection["preflight_decisions"][candidate["candidate_id"]],
        "source_row_count": len(frame),
        "stress_decision_count": counts["amendment_stress"],
        "negative_control_decision_count": counts[
            "count_one_negative_control"
        ],
        "promotion_request": _relative(promotion_path, repo_root),
        "promotion_hash": promotion["promotion_hash"],
        "outcome_values_read": False,
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
    }
    report_path = output_dir / "preflight_report.json"
    _write(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-at", required=True)
    parser.add_argument("--history-cutoff", required=True)
    parser.add_argument("--warehouse-path", type=Path, required=True)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--archive-path", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                freeze_at=args.freeze_at,
                history_cutoff=args.history_cutoff,
                warehouse_path=args.warehouse_path,
                source_manifest_path=args.source_manifest_path,
                archive_path=args.archive_path,
                output_dir=args.output_dir,
            ),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
