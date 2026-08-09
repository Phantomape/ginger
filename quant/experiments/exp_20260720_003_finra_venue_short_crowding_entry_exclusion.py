"""exp-20260720-003: FINRA venue-plus-short-crowding core entry gate.

The outcome-blind policy is fixed by the claimed ticket.  On each signal day,
the shared helper resolves only revision-safe source rows published strictly
before that day.
For the exact latest ATS/OTC week it computes each common stock's ATS share of
combined venue volume.  It joins the global latest FINRA short-interest release
and excludes the next-session fresh core entry only when all three conditions
hold: ATS share is above the joined cross-sectional median, short interest rose,
and days-to-cover is at or above the joined cross-sectional median.

The rule is fail-open on stale, missing, mismatched, non-common-stock, revised,
or non-point-in-time inputs.  It is installed as a post-qualification entry
admission policy, never as entry-universe membership, so it cannot directly
alter signal generation, survival, add-ons, existing positions, ranking,
sizing, exits, or live/default orders.  This runner measures the fixed rule on
the three canonical cash-feasible windows and persists experiment-scoped
before/after evidence without writing experiment lifecycle state.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtester import BacktestEngine, _persistable_backtest_result  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402
import exp_20260717_007_nvd_cve_cluster_entry_gate as gate_common  # noqa: E402
import finra_venue_short_crowding_entry_gate as finra_gate  # noqa: E402
from entry_universe_ledger import canonical_hash, membership_hash  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260720-003"
PROTOCOL_ID = "finra_ats_otc_x_short_interest_crowding_core_entry_exclusion_v1"
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
FROZEN_INPUTS = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-015"
    / "frozen_behavior_inputs.json"
)
ATS_ROWS = ROOT / "data" / "non_ohlcv" / "finra_ats_weekly" / "rows.jsonl"
ATS_MANIFEST = ROOT / "data" / "non_ohlcv" / "finra_ats_weekly" / "manifest.json"
OTC_ROWS = ROOT / "data" / "non_ohlcv" / "finra_otc_weekly" / "rows.jsonl"
OTC_MANIFEST = ROOT / "data" / "non_ohlcv" / "finra_otc_weekly" / "manifest.json"
SHORT_ROWS = ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "rows.json"
SHORT_SOURCE_FILES = (
    ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "source_files.json"
)
SHORT_RAW_SOURCE_DIR = (
    ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "source_cache"
)
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BACKTEST_DIR = EXP_DIR / "backtests"
BEFORE_FILE = EXP_DIR / "before_measurement.json"
AFTER_FILE = EXP_DIR / "after_measurement.json"
ARTIFACT = (
    EXP_DIR
    / "exp_20260720_003_finra_venue_short_crowding_entry_exclusion.json"
)
MARKDOWN_ARTIFACT = (
    ROOT
    / "experiments"
    / "artifacts"
    / "exp-20260720-003_finra_venue_short_crowding_entry_exclusion.md"
)

ACTIVE_EV = 6.2057
EXPECTED_SOURCE_HASH = (
    "2d0771e246f724db62ad7c412153634690f73f3ec595e6cb341e6bd3282dcd05"
)
EXPECTED_RAW_SOURCE_FILE_COUNT = 46
EXPECTED_NORMALIZED_SHORT_ROW_COUNT = 46_511
EXPECTED_REVISED_SHORT_ROW_COUNT = 152
EXPECTED_FROZEN_CORE_REVISED_ROW_COUNT = 18
EXPECTED_FROZEN_CORE_REVISED_BY_WINDOW = {
    "old_thin": 4,
    "mid_weak": 3,
    "late_strong": 11,
}
MIN_SURVIVAL_RATE = 0.05
MIN_FRESH_ENTRY_EXCLUSIONS = 5
MAX_VENUE_AGE_DAYS = 14
MAX_SHORT_INTEREST_AGE_DAYS = 21

HYPOTHESIS = (
    "Exclude a fresh core trend/breakout entry on its next-session execution "
    "date when the latest strictly prior-day exact-week FINRA ATS/OTC "
    "cross-section has above-median ATS share and the latest strictly "
    "prior-day global FINRA short-interest release has rising short interest "
    "with days-to-cover at or above the contemporaneous joined-universe "
    "median; this joint crowding state should remove fragile dark-volume "
    "demand while preserving uncrowded accumulation."
)


def _path_text(path: Path) -> str:
    try:
        return gate1._repo_rel(path)
    except ValueError:
        return str(path.resolve())


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Unexpected frozen Gate-1 behavior-input schema")
    if payload.get("behavior_sha256") != gate1._stable_hash(payload.get("behavior")):
        raise RuntimeError("Frozen Gate-1 behavior-input hash mismatch")
    return payload


def _all_sessions() -> list[str]:
    earliest_start = min(
        date.fromisoformat(spec["start"]) for spec in gate1.WINDOWS
    )
    latest_end = max(date.fromisoformat(spec["end"]) for spec in gate1.WINDOWS)
    final_day = latest_end + timedelta(days=14)
    sessions: list[str] = []
    candidate = earliest_start
    while candidate <= final_day:
        if is_us_equity_session(candidate):
            sessions.append(candidate.isoformat())
        candidate += timedelta(days=1)
    return sessions


def _run_window(
    spec: dict[str, str],
    frozen: Mapping[str, Any],
    *,
    resolver: Any,
    entry_admission_policy: Any | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(dict(frozen))
    universe_metadata = {
        "measurement_protocol": PROTOCOL_ID,
        "source_role": "PIT FINRA ATS/OTC plus global short-interest entry admission",
        "security_master_survivorship_status": (
            "current frozen roster; the gate does not claim delisted-security repair"
        ),
    }
    universe_metadata.update(dict(resolver.metadata))
    engine = BacktestEngine(
        list(behavior["universe"]),
        start=spec["start"],
        end=spec["end"],
        config=dict(gate1.RUN_CONFIG),
        ohlcv_warehouse_path=str(gate1.WAREHOUSE),
        ohlcv_warehouse_snapshot_source=spec["snapshot"],
        replay_llm=False,
        replay_news=False,
        include_pilot_sleeve=False,
        require_non_ohlcv=False,
        include_entry_candidate_events=True,
        include_oracle_diagnostics=False,
        entry_universe_resolver=resolver,
        entry_admission_policy=entry_admission_policy,
        universe_mode="pit_walk_forward",
        universe_metadata=universe_metadata,
    )
    engine._earnings_snapshots = behavior["earnings_snapshots"]
    engine._download_earnings_calendar = lambda: {
        ticker: list(values) for ticker, values in calendar.items()
    }
    effective = gate1._effective_earnings_identity(
        engine, spec, behavior["universe"], calendar
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    identity = gate1._result_identity(result)
    identity.update(
        {
            "effective_earnings_inputs_sha256": effective["sha256"],
            "effective_earnings_row_count": effective["row_count"],
            "resolved_config_sha256": gate1._stable_hash(engine.config),
            "universe_membership_sha256": gate1._stable_hash(
                result.get("universe_membership") or {}
            ),
            "entry_admission_sha256": (
                gate1._stable_hash(result["entry_admission"])
                if "entry_admission" in result
                else None
            ),
            "entry_admission_enabled": "entry_admission" in result,
            "window": dict(spec),
        }
    )
    return result, identity


def _persist_result(
    arm: str,
    spec: Mapping[str, str],
    result: Mapping[str, Any],
) -> dict[str, str]:
    path = BACKTEST_DIR / f"{spec['label']}_{arm}_{EXPERIMENT_ID}.json"
    gate1._atomic_write_json(path, _persistable_backtest_result(dict(result)))
    return {"path": _path_text(path), "sha256": gate1._file_sha256(path)}


def _source_file_identity() -> dict[str, Any]:
    paths = {
        "ats_rows": ATS_ROWS,
        "ats_manifest": ATS_MANIFEST,
        "otc_rows": OTC_ROWS,
        "otc_manifest": OTC_MANIFEST,
        "short_interest_rows": SHORT_ROWS,
        "short_interest_source_files": SHORT_SOURCE_FILES,
    }
    identities: dict[str, Any] = {
        name: {
            "path": _path_text(path),
            "sha256": gate1._file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }
    raw_paths = sorted(SHORT_RAW_SOURCE_DIR.glob("*.csv"))
    identities["short_interest_raw_csvs"] = {
        path.name: {
            "path": _path_text(path),
            "sha256": gate1._file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in raw_paths
    }
    return identities


def _window_for_day(day_text: str) -> str | None:
    return next(
        (
            spec["label"]
            for spec in gate1.WINDOWS
            if spec["start"] <= day_text <= spec["end"]
        ),
        None,
    )


def _entry_session(
    resolution: Mapping[str, Any],
    sessions: Sequence[str],
    signal_day: str,
) -> str | None:
    provenance = resolution.get("provenance") or {}
    explicit = (
        provenance.get("entry_session")
        or provenance.get("next_trading_session")
        or resolution.get("entry_session")
        or resolution.get("next_trading_session")
    )
    if explicit:
        return str(explicit)[:10]
    try:
        return sessions[sessions.index(signal_day) + 1]
    except (ValueError, IndexError):
        return None


def _excluded_tickers(payload: Mapping[str, Any]) -> list[str]:
    direct = payload.get("excluded_tickers")
    if direct is None:
        direct = payload.get("excluded_tickers_for_next_session")
    if direct is None:
        direct = (payload.get("entry_admission") or {}).get("excluded_tickers")
    return sorted(
        {
            str(ticker).strip().upper()
            for ticker in (direct or [])
            if str(ticker).strip()
        }
    )


def _resolver_exclusions(
    resolver: Any,
    sessions: Sequence[str],
    base_tickers: Sequence[str],
) -> list[dict[str, Any]]:
    base = {str(ticker).strip().upper() for ticker in base_tickers}
    exclusions: list[dict[str, Any]] = []
    for signal_day in sessions[:-1]:
        resolution = resolver.resolve(signal_day)
        if resolution.get("status") != "resolved":
            continue
        eligible = {
            str(ticker).strip().upper()
            for ticker in resolution.get("tickers") or []
        }
        provenance = resolution.get("provenance") or {}
        entry_day = _entry_session(resolution, sessions, signal_day)
        for ticker in sorted(base - eligible):
            state = provenance.get("state") or {}
            exclusions.append(
                {
                    "ticker": ticker,
                    "signal_date": signal_day,
                    "entry_date": entry_day,
                    "window": _window_for_day(entry_day or ""),
                    "source_hash": resolution.get("source_hash"),
                    "snapshot_sha256": resolution.get("snapshot_sha256"),
                    "record_hash": resolution.get("record_hash"),
                    "index_hash": provenance.get("index_hash"),
                    "membership_hash": resolution.get("membership_hash")
                    or provenance.get("membership_hash"),
                    "venue_publication_date": state.get(
                        "venue_publication_date"
                    ),
                    "short_interest_publication_date": state.get(
                        "short_interest_publication_date"
                    ),
                    "venue_age_days": state.get("venue_age_days"),
                    "short_interest_age_days": state.get(
                        "short_interest_age_days"
                    ),
                }
            )
    return exclusions


def _candidate_overlap(
    result: Mapping[str, Any],
    policy: Any,
    sessions: Sequence[str],
) -> dict[str, Any]:
    membership = result.get("universe_membership") or {}

    def excluded_candidates(
        rows: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        hits: dict[tuple[str, str], dict[str, Any]] = {}
        for raw in rows:
            ticker = str(raw.get("ticker") or "").strip().upper()
            signal_day = str(
                raw.get("signal_date") or raw.get("date") or raw.get("as_of") or ""
            )[:10]
            if not ticker or not signal_day:
                continue
            resolution = policy.resolve(signal_day)
            provenance = resolution.get("provenance") or {}
            excluded = {
                str(value).strip().upper()
                for value in provenance.get("excluded_tickers") or []
            }
            if resolution.get("status") == "resolved" and ticker in excluded:
                hits[(ticker, signal_day)] = {
                    "ticker": ticker,
                    "signal_date": signal_day,
                    "entry_date": _entry_session(
                        resolution, sessions, signal_day
                    ),
                    "strategy": raw.get("strategy"),
                    "sector": raw.get("sector"),
                    "target_price_present": isinstance(
                        raw.get("target_price"), (int, float)
                    ),
                }
        return sorted(
            hits.values(), key=lambda row: (row["signal_date"], row["ticker"])
        )

    def eligible_entered_exclusions(
        rows: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        hits: dict[tuple[str, str, str], dict[str, Any]] = {}
        for raw in rows:
            ticker = str(raw.get("ticker") or "").strip().upper()
            signal_day = str(raw.get("signal_date") or "")[:10]
            fill_day = str(raw.get("entry_date") or "")[:10]
            if not ticker or not signal_day or not fill_day:
                continue
            decision = policy.evaluate(
                signal_date=signal_day,
                ticker=ticker,
                fill_date=fill_day,
            )
            if decision.get("admit") is False:
                provenance = decision.get("provenance") or {}
                hits[(ticker, signal_day, fill_day)] = {
                    "ticker": ticker,
                    "signal_date": signal_day,
                    "entry_date": fill_day,
                    "strategy": raw.get("strategy"),
                    "sector": raw.get("sector"),
                    "status": decision.get("status"),
                    "reason": decision.get("reason"),
                    "strict_next_session_match": provenance.get(
                        "strict_next_session_match"
                    ),
                    "source_hash": provenance.get("source_hash"),
                    "index_hash": provenance.get("index_hash"),
                }
        return sorted(
            hits.values(),
            key=lambda row: (
                row["signal_date"],
                row["ticker"],
                row["entry_date"],
            ),
        )

    generated = excluded_candidates(
        list(membership.get("generated_signals") or [])
    )
    survived = excluded_candidates(
        list(membership.get("survived_signals") or [])
    )
    entered = eligible_entered_exclusions(
        list(membership.get("entered_trades") or [])
    )
    return {
        "generated_fresh_candidate_exclusions": len(generated),
        "survived_fresh_candidate_exclusions": len(survived),
        "entered_trade_exclusions": len(entered),
        "eligible_entered_trade_exclusions": len(entered),
        "generated_rows": generated,
        "survived_rows": survived,
        "entered_rows": entered,
    }


def _admission_event_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").strip().upper(),
        str(row.get("signal_date") or "")[:10],
        str(row.get("fill_date") or row.get("entry_date") or "")[:10],
    )


def _entry_admission_audit(
    before_result: Mapping[str, Any],
    after_result: Mapping[str, Any],
    candidate_touch: Mapping[str, Any],
    policy: Any,
) -> dict[str, Any]:
    audit = after_result.get("entry_admission")
    payload = dict(audit) if isinstance(audit, Mapping) else {}
    events = [
        dict(row)
        for row in payload.get("events") or []
        if isinstance(row, Mapping)
    ]
    denied = [row for row in events if row.get("admit") is False]
    admitted = [row for row in events if row.get("admit") is True]
    delayed = [
        row
        for row in events
        if row.get("status") == "admitted_not_strict_next_session"
    ]
    expected_rows = [
        dict(row)
        for row in candidate_touch.get("entered_rows") or []
        if isinstance(row, Mapping)
    ]
    expected_counts = Counter(_admission_event_key(row) for row in expected_rows)
    denied_counts = Counter(_admission_event_key(row) for row in denied)
    missing = list((expected_counts - denied_counts).elements())
    unexpected = list((denied_counts - expected_counts).elements())

    after_survived = (
        (after_result.get("universe_membership") or {}).get("survived_signals")
        or []
    )
    survived_keys = {
        (
            str(row.get("ticker") or "").strip().upper(),
            str(row.get("signal_date") or "")[:10],
        )
        for row in after_survived
    }
    after_survived_exclusion_counts: Counter[tuple[str, str, str]] = Counter()
    for row in after_survived:
        ticker = str(row.get("ticker") or "").strip().upper()
        signal_day = str(row.get("signal_date") or "")[:10]
        if not ticker or not signal_day:
            continue
        resolution = policy.resolve(signal_day)
        provenance = resolution.get("provenance") or {}
        excluded = {
            str(value).strip().upper()
            for value in provenance.get("excluded_tickers") or []
        }
        expected_fill = str(provenance.get("entry_session") or "")[:10]
        if ticker in excluded and expected_fill:
            after_survived_exclusion_counts[
                (ticker, signal_day, expected_fill)
            ] += 1
    denied_not_survived_exclusions = list(
        (denied_counts - after_survived_exclusion_counts).elements()
    )
    computed_status_counts = dict(
        sorted(Counter(str(row.get("status") or "") for row in events).items())
    )
    computed_reason_counts = dict(
        sorted(Counter(str(row.get("reason") or "") for row in events).items())
    )
    notes = [str(value) for value in payload.get("notes") or []]
    checks = {
        "before_policy_disabled": "entry_admission" not in before_result,
        "after_audit_present_and_enabled": bool(payload)
        and payload.get("enabled") is True,
        "policy_metadata_exact": payload.get("policy_metadata")
        == policy.metadata,
        "events_not_truncated": int(payload.get("events_truncated") or 0) == 0,
        "event_count_complete": int(payload.get("evaluated_count") or 0)
        == len(events),
        "admitted_count_matches_events": int(payload.get("admitted_count") or 0)
        == len(admitted),
        "denied_count_matches_events": int(payload.get("denied_count") or 0)
        == len(denied),
        "evaluated_partition_exact": int(payload.get("evaluated_count") or 0)
        == int(payload.get("admitted_count") or 0)
        + int(payload.get("denied_count") or 0),
        "status_counts_match_events": payload.get("status_counts")
        == computed_status_counts,
        "reason_counts_match_events": payload.get("reason_counts")
        == computed_reason_counts,
        "all_events_are_survived_fresh_candidates": all(
            (key[0], key[1]) in survived_keys
            for key in (_admission_event_key(row) for row in events)
        ),
        "denied_events_have_fixed_semantics": all(
            row.get("status") == "denied"
            and row.get("reason")
            == "finra_joint_crowding_strict_next_session"
            and (row.get("provenance") or {}).get(
                "strict_next_session_match"
            )
            is True
            and str(row.get("fill_date") or "")[:10]
            == str(
                (row.get("provenance") or {}).get("entry_session") or ""
            )[:10]
            for row in denied
        ),
        "denied_source_identity_exact": all(
            (row.get("provenance") or {}).get("source_hash")
            == policy.metadata.get("source_hash")
            and (row.get("provenance") or {}).get("index_hash")
            == policy.metadata.get("index_hash")
            for row in denied
        ),
        "every_before_executable_exclusion_was_denied": not missing,
        "every_denial_is_after_full_base_survived_exclusion": not (
            denied_not_survived_exclusions
        ),
        "delayed_fills_explicitly_admitted": all(
            row.get("admit") is True
            and row.get("reason")
            == "actual_fill_date_differs_from_strict_next_session"
            and (row.get("provenance") or {}).get(
                "strict_next_session_match"
            )
            is False
            for row in delayed
        ),
        "no_broad_delayed_fill_cancellation": all(
            row.get("admit") is True
            and row.get("status") == "admitted_not_strict_next_session"
            for row in events
            if str(row.get("fill_date") or "")[:10]
            != str(
                (row.get("provenance") or {}).get("entry_session") or ""
            )[:10]
        ),
        "backtester_notes_exclude_addons": any(
            "add-on" in note.lower() for note in notes
        ),
    }
    return {
        "audit": payload,
        "denied_event_count": len(denied),
        "denied_events": denied,
        "admitted_event_count": len(admitted),
        "delayed_admitted_event_count": len(delayed),
        "delayed_admitted_events": delayed,
        "eligible_entered_touch_count": len(expected_rows),
        "eligible_entered_touch_rows": expected_rows,
        "denied_touch_cross_check": {
            "expected_keys": [list(key) for key in sorted(expected_counts.elements())],
            "actual_keys": [list(key) for key in sorted(denied_counts.elements())],
            "missing_expected_keys": [list(key) for key in sorted(missing)],
            "unexpected_denied_keys": [list(key) for key in sorted(unexpected)],
            "denied_not_after_survived_exclusion_keys": [
                list(key) for key in sorted(denied_not_survived_exclusions)
            ],
            "expected_subset": not missing,
            "denied_subset_of_after_full_base_survived_exclusions": not (
                denied_not_survived_exclusions
            ),
            "extra_denies_are_portfolio_path_dependence": bool(unexpected)
            and not denied_not_survived_exclusions,
            "exact": not missing and not unexpected,
        },
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def _short_revision_audit(
    short_rows: Sequence[Mapping[str, Any]],
    loader_audit: Mapping[str, Any],
    index: Mapping[str, Any],
    sessions: Sequence[str],
    base_tickers: Sequence[str],
) -> dict[str, Any]:
    revised = [
        dict(row)
        for row in short_rows
        if str(row.get("revision_flag") or "").upper() == "R"
    ]
    valid_short, invalid_short = finra_gate._normalise_short_rows(short_rows)
    revised_keys = {
        (
            str(row.get("ticker") or "").strip().upper(),
            str(row.get("settlement_date") or "")[:10],
        )
        for row in revised
    }
    valid_keys = {
        (
            str(row.get("ticker") or "").strip().upper(),
            str(row.get("settlement_date") or "")[:10],
        )
        for row in valid_short
    }
    frozen = {str(ticker).strip().upper() for ticker in base_tickers}
    frozen_revised = [
        row
        for row in revised
        if str(row.get("ticker") or "").strip().upper() in frozen
    ]
    by_window: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        selected_release_dates = {
            str((index.get("state_by_signal_day") or {}).get(day, {}).get(
                "short_interest_usable_trade_date"
            ) or "")[:10]
            for day in sessions
            if spec["start"] <= day <= spec["end"]
        }
        selected_release_dates.discard("")
        rows = [
            row
            for row in frozen_revised
            if str(row.get("usable_trade_date") or "")[:10]
            in selected_release_dates
        ]
        by_window[spec["label"]] = {
            "revised_frozen_core_row_count": len(rows),
            "selected_short_interest_release_dates": sorted(
                selected_release_dates
            ),
            "rows": [
                {
                    key: row.get(key)
                    for key in (
                        "ticker",
                        "settlement_date",
                        "publication_date",
                        "usable_trade_date",
                        "revision_flag",
                        "pit_safe",
                        "as_published_vintage_available",
                    )
                }
                for row in rows
            ],
        }
    counts_by_window = {
        label: row["revised_frozen_core_row_count"]
        for label, row in by_window.items()
    }
    checks = {
        "raw_source_file_count_exact": loader_audit.get(
            "raw_source_file_count"
        )
        == EXPECTED_RAW_SOURCE_FILE_COUNT,
        "normalized_row_count_exact": loader_audit.get(
            "normalized_row_count"
        )
        == EXPECTED_NORMALIZED_SHORT_ROW_COUNT,
        "all_normalized_rows_raw_matched": loader_audit.get(
            "all_normalized_rows_raw_matched"
        )
        is True,
        "matched_row_count_exact": loader_audit.get(
            "matched_normalized_row_count"
        )
        == EXPECTED_NORMALIZED_SHORT_ROW_COUNT,
        "missing_key_count_zero": loader_audit.get(
            "missing_normalized_key_count"
        )
        == 0,
        "revised_row_count_exact": len(revised)
        == EXPECTED_REVISED_SHORT_ROW_COUNT
        == loader_audit.get("revised_normalized_row_count"),
        "all_revised_rows_fail_closed": all(
            row.get("pit_safe") is False
            and row.get("as_published_vintage_available") is False
            for row in revised
        ),
        "revised_rows_absent_from_valid_index_inputs": not (
            revised_keys & valid_keys
        ),
        "normalized_valid_count_matches_index": len(valid_short)
        == int((index.get("valid_row_counts") or {}).get("short_interest") or -1),
        "normalized_invalid_count_matches_index": len(invalid_short)
        == int((index.get("invalid_row_counts") or {}).get("short_interest") or -1),
        "frozen_core_revised_count_exact": len(frozen_revised)
        == EXPECTED_FROZEN_CORE_REVISED_ROW_COUNT,
        "frozen_core_revised_by_window_exact": counts_by_window
        == EXPECTED_FROZEN_CORE_REVISED_BY_WINDOW,
    }
    return {
        **dict(loader_audit),
        "revised_rows_excluded_from_index": len(revised_keys - valid_keys),
        "frozen_core_revised_row_count": len(frozen_revised),
        "frozen_core_revised_counts_by_window": counts_by_window,
        "frozen_core_revised_by_window": by_window,
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def _headline(result: Mapping[str, Any]) -> dict[str, Any]:
    headline = gate_common._headline(result)
    benchmarks = result.get("benchmarks") or {}
    headline["benchmarks"] = {
        key: benchmarks.get(key)
        for key in (
            "spy_buy_hold_return_pct",
            "qqq_buy_hold_return_pct",
            "strategy_total_return_pct",
            "strategy_vs_spy_pct",
            "strategy_vs_qqq_pct",
        )
    }
    return headline


def _delta(
    after: Mapping[str, Any], before: Mapping[str, Any]
) -> dict[str, Any]:
    return gate_common._delta(after, before)


def _aggregate(
    windows: Mapping[str, Mapping[str, Any]], arm: str
) -> dict[str, Any]:
    aggregate = gate_common._aggregate(windows, arm)
    rows = [windows[spec["label"]][arm] for spec in gate1.WINDOWS]
    aggregate["minimum_strategy_vs_spy_pct"] = min(
        float((row.get("benchmarks") or {})["strategy_vs_spy_pct"])
        for row in rows
    )
    aggregate["minimum_strategy_vs_qqq_pct"] = min(
        float((row.get("benchmarks") or {})["strategy_vs_qqq_pct"])
        for row in rows
    )
    return aggregate


def _gate4_checks(
    windows: Mapping[str, Mapping[str, Any]],
    before_aggregate: Mapping[str, Any],
    after_aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    per_window: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before = windows[label]["before"]
        after = windows[label]["after"]
        benchmarks = after.get("benchmarks") or {}
        trade_sample_floor = max(10, math.floor(0.80 * before["trade_count"]))
        row = {
            "ev_non_regressing": after["expected_value_score"]
            >= before["expected_value_score"],
            "pnl_non_regressing": after["total_pnl"] >= before["total_pnl"],
            "drawdown_no_worse_than_plus_0p5pp": after["max_drawdown_pct"]
            <= before["max_drawdown_pct"] + 0.005,
            "trade_sample_floor": trade_sample_floor,
            "trade_sample_sufficient": after["trade_count"] >= trade_sample_floor,
            "gate3_survival": after["survival_rate"] >= MIN_SURVIVAL_RATE,
            "beats_spy_buy_hold": float(benchmarks.get("strategy_vs_spy_pct") or 0.0)
            > 0.0,
            "beats_qqq_buy_hold": float(benchmarks.get("strategy_vs_qqq_pct") or 0.0)
            > 0.0,
        }
        row["all_pass"] = all(
            value for key, value in row.items() if key != "trade_sample_floor"
        )
        per_window[label] = row
    checks = {
        "aggregate_ev_strictly_improves": after_aggregate[
            "expected_value_score_sum"
        ]
        > before_aggregate["expected_value_score_sum"],
        "aggregate_pnl_strictly_improves": after_aggregate["total_pnl_sum"]
        > before_aggregate["total_pnl_sum"],
        "aggregate_drawdown_no_worse_than_plus_0p5pp": after_aggregate[
            "worst_max_drawdown_pct"
        ]
        <= before_aggregate["worst_max_drawdown_pct"] + 0.005,
        "aggregate_trade_sample_sufficient": after_aggregate["trade_count_sum"]
        >= 40,
        "aggregate_survival_gate": after_aggregate["minimum_survival_rate"]
        >= MIN_SURVIVAL_RATE,
        "all_windows_non_regressing_and_benchmark_positive": all(
            row["all_pass"] for row in per_window.values()
        ),
    }
    checks["all_pass"] = all(checks.values())
    return {
        "fixed_hurdle": {
            "active_gate1_expected_value_score": ACTIVE_EV,
            "required_aggregate_ev": "strictly greater than active Gate-1",
            "required_aggregate_pnl": "strictly greater than active Gate-1",
            "per_window_ev_and_pnl": "no regression",
            "drawdown_tolerance_percentage_points": 0.5,
            "aggregate_trade_count_floor": 40,
            "per_window_trade_count_floor": (
                "max(10, floor(80% of that window's before trade count))"
            ),
            "benchmark_rule": "positive strategy_vs_spy_pct and strategy_vs_qqq_pct",
        },
        "per_window": per_window,
        "checks": checks,
    }


def _build_policy(
    frozen: Mapping[str, Any],
    source_identities: Mapping[str, Any],
) -> tuple[
    Any,
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
    dict[str, Any],
]:
    ats_rows = finra_gate.load_jsonl_rows(ATS_ROWS)
    otc_rows = finra_gate.load_jsonl_rows(OTC_ROWS)
    short_rows, revision_audit = (
        finra_gate.load_revision_safe_short_interest_rows(
            SHORT_ROWS, SHORT_RAW_SOURCE_DIR
        )
    )
    sessions = _all_sessions()
    index = finra_gate.build_finra_venue_short_crowding_exclusion_index(
        ats_rows,
        otc_rows,
        short_rows,
        sessions,
        source_identities=source_identities,
    )
    policy = finra_gate.FinraVenueShortCrowdingEntryAdmissionPolicy(
        base_tickers=frozen["behavior"]["universe"],
        exclusion_index=index,
        trading_sessions=sessions,
        source_hash=index["source_hash"],
    )
    if not isinstance(policy.metadata, Mapping):
        raise RuntimeError("FINRA admission-policy metadata must be a mapping")
    return (
        policy,
        index,
        ats_rows,
        otc_rows,
        short_rows,
        sessions,
        revision_audit,
    )


class _FailOpenCandidateAuditResolver:
    """Log the full baseline candidate surface without changing eligibility.

    A static baseline leaves the BacktestEngine universe-membership candidate
    arrays empty.  This resolver returns the identical full base universe on
    every day in both arms while retaining a hash-bound audit record.  The
    FINRA object is installed separately as the after arm's admission policy;
    its diagnostic ``resolve`` output only labels counterfactual candidate
    touches.
    """

    def __init__(self, base_tickers: Sequence[str], source_resolver: Any) -> None:
        self._base = tuple(
            sorted(
                {
                    str(ticker).strip().upper()
                    for ticker in base_tickers
                    if str(ticker).strip()
                }
            )
        )
        self._source_resolver = source_resolver
        metadata = dict(source_resolver.metadata)
        metadata.update(
            {
                "schema": "finra_entry_candidate_fail_open_audit_resolver_v1",
                "audit_only": True,
                "eligibility_policy": "always_full_frozen_base_universe",
                "applies_finra_exclusion": False,
                "base_membership_hash": membership_hash(self._base),
                "trade_enabled": False,
                "strategy_behavior_changed": False,
                "alters_live_orders": False,
            }
        )
        self._metadata = metadata

    @property
    def data_tickers(self) -> frozenset[str]:
        return frozenset(self._base)

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    def resolve(self, as_of: Any) -> dict[str, Any]:
        source = self._source_resolver.resolve(as_of)
        source_provenance = deepcopy(source.get("provenance") or {})
        underlying_excluded = list(source_provenance.get("excluded_tickers") or [])
        provenance = {
            **source_provenance,
            "excluded_tickers": [],
            "audit_underlying_excluded_tickers": underlying_excluded,
            "audit_only": True,
            "eligibility_policy": "always_full_frozen_base_universe",
            "applies_finra_exclusion": False,
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_live_orders": False,
        }
        semantic = {
            "as_of": source.get("as_of"),
            "entry_session": provenance.get("entry_session"),
            "eligible": list(self._base),
            "source_hash": source.get("source_hash"),
            "rule_version": finra_gate.RULE_VERSION,
            "audit_only": True,
        }
        snapshot_hash = canonical_hash(
            {"record_type": "finra_entry_candidate_fail_open_membership", **semantic}
        )
        record_hash = canonical_hash(
            {"record_type": "finra_entry_candidate_fail_open_resolution", **semantic}
        )
        return {
            **source,
            "status": "resolved",
            "snapshot_sha256": snapshot_hash,
            "snapshot_hash": snapshot_hash,
            "record_hash": record_hash,
            "tickers": list(self._base),
            "ticker_count": len(self._base),
            "membership_hash": membership_hash(self._base),
            "reason": "fail_open_candidate_audit_full_base_universe",
            "provenance": provenance,
        }

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of)["tickers"])


def _policy_identity(index: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "source_cutoff": "publication_date_strictly_before_signal_date",
        "venue_join": "exact_ticker_week_start_published_date_tier",
        "short_interest_join": (
            "latest_global_release_then_exact_ticker_presence"
        ),
        "max_venue_age_calendar_days": MAX_VENUE_AGE_DAYS,
        "max_short_interest_age_calendar_days": MAX_SHORT_INTEREST_AGE_DAYS,
        "venue_share_gate": (
            "ats_share_over_ats_plus_otc_strictly_above_joined_median"
        ),
        "short_interest_change_gate": "strictly_positive",
        "days_to_cover_gate": "at_or_above_joined_median",
        "entry_response": "exclude_fresh_core_entry_on_strict_next_session",
        "missing_or_stale_policy": "fail_open",
        "non_common_stock_tickers": sorted(
            finra_gate.NON_COMMON_STOCK_TICKERS
        ),
    }
    actual = dict(index.get("policy") or {})
    field_checks = {key: actual.get(key) == value for key, value in expected.items()}
    checks = {
        **field_checks,
        "rule_version_exact": index.get("rule_version")
        == finra_gate.RULE_VERSION
        == "finra_ats_otc_x_short_interest_crowding_entry_exclusion_v1",
        "measurement_protocol_id_fixed": PROTOCOL_ID
        == "finra_ats_otc_x_short_interest_crowding_core_entry_exclusion_v1",
        "helper_trade_enabled_false": finra_gate.TRADE_ENABLED is False,
        "index_trade_enabled_false": index.get("trade_enabled") is False,
        "index_strategy_behavior_changed_false": index.get(
            "strategy_behavior_changed"
        )
        is False,
        "index_alters_live_orders_false": index.get("alters_live_orders")
        is False,
    }
    return {
        "rule_version": index.get("rule_version"),
        "expected": expected,
        "actual": actual,
        "checks": checks,
        "all_pass": all(checks.values()),
        "threshold_or_response_retuned": False,
    }


def _resolver_pit_audit(
    resolver: Any,
    index: Mapping[str, Any],
    sessions: Sequence[str],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    covered_days = 0
    strict_prior_checks = 0
    for signal_day in sessions[:-1]:
        resolution = resolver.resolve(signal_day)
        provenance = resolution.get("provenance") or {}
        state = provenance.get("state") or {}
        state_status = str(state.get("status") or "missing")
        counts[state_status] += 1
        entry_day = _entry_session(resolution, sessions, signal_day)
        checks: dict[str, bool] = {
            "resolved": resolution.get("status") == "resolved",
            "as_of_exact": str(resolution.get("as_of") or "")[:10]
            == signal_day,
            "strict_next_session": bool(entry_day and entry_day > signal_day),
            "source_hash": resolution.get("source_hash")
            == index.get("source_hash"),
            "source_hashes": provenance.get("source_hashes")
            == index.get("source_hashes"),
            "index_hash": provenance.get("index_hash")
            == index.get("index_hash"),
            "rule_version": provenance.get("rule_version")
            == finra_gate.RULE_VERSION,
            "trade_enabled_false": provenance.get("trade_enabled") is False,
            "alters_live_orders_false": provenance.get("alters_live_orders")
            is False,
        }
        venue_publication = state.get("venue_publication_date")
        short_publication = state.get("short_interest_publication_date")
        if venue_publication is not None or short_publication is not None:
            strict_prior_checks += 1
            checks["venue_publication_strictly_prior"] = bool(
                venue_publication and str(venue_publication)[:10] < signal_day
            )
            checks["short_interest_publication_strictly_prior"] = bool(
                short_publication and str(short_publication)[:10] < signal_day
            )
        if state_status == "covered":
            covered_days += 1
            checks.update(
                {
                    "venue_fresh": int(state.get("venue_age_days") or 0)
                    <= MAX_VENUE_AGE_DAYS,
                    "short_interest_fresh": int(
                        state.get("short_interest_age_days") or 0
                    )
                    <= MAX_SHORT_INTEREST_AGE_DAYS,
                    "venue_median_finite": isinstance(
                        state.get("venue_share_median"), (int, float)
                    )
                    and math.isfinite(float(state["venue_share_median"])),
                    "days_to_cover_median_finite": isinstance(
                        state.get("days_to_cover_median"), (int, float)
                    )
                    and math.isfinite(float(state["days_to_cover_median"])),
                    "joined_population_positive": int(
                        state.get("joined_ticker_count") or 0
                    )
                    > 0,
                }
            )
        if not all(checks.values()):
            failures.append(
                {
                    "signal_date": signal_day,
                    "entry_session": entry_day,
                    "state": state,
                    "failed_checks": [
                        key for key, passed in checks.items() if not passed
                    ],
                }
            )
    return {
        "session_count": max(0, len(sessions) - 1),
        "covered_session_count": covered_days,
        "strict_prior_date_check_count": strict_prior_checks,
        "state_status_counts": dict(sorted(counts.items())),
        "failure_count": len(failures),
        "failures": failures,
        "all_pass": not failures and covered_days > 0 and strict_prior_checks > 0,
    }


def _daily_parity(
    ats_rows: Sequence[Mapping[str, Any]],
    otc_rows: Sequence[Mapping[str, Any]],
    short_rows: Sequence[Mapping[str, Any]],
    resolver: Any,
    exclusion_index: Mapping[str, Any],
    sessions: Sequence[str],
    base_tickers: Sequence[str],
    source_identities: Mapping[str, Any],
) -> dict[str, Any]:
    # The daily builder hashes the complete exclusion index, including every
    # session's source state, coverage set and exclusions.  Exact index-hash
    # equality therefore proves all-session decision parity without rebuilding
    # and sorting the 46k-row short-interest archive once per day.  We also
    # exercise the adapter projection on boundary, status, exclusion and
    # no-exclusion representatives from every canonical window.
    sample_days: set[str] = set()
    states_seen: set[str] = set()
    exclusion_window_seen: set[str] = set()
    no_exclusion_window_seen: set[str] = set()
    for spec in gate1.WINDOWS:
        window_sessions = [
            day for day in sessions[:-1] if spec["start"] <= day <= spec["end"]
        ]
        if window_sessions:
            sample_days.add(window_sessions[0])
            sample_days.add(window_sessions[-1])
    for signal_day in sessions[:-1]:
        resolution = resolver.resolve(signal_day)
        provenance = resolution.get("provenance") or {}
        status = str((provenance.get("state") or {}).get("status") or "missing")
        if status not in states_seen:
            sample_days.add(signal_day)
            states_seen.add(status)
        window = _window_for_day(signal_day)
        excluded = provenance.get("excluded_tickers") or []
        if window and excluded and window not in exclusion_window_seen:
            sample_days.add(signal_day)
            exclusion_window_seen.add(window)
        if (
            window
            and not excluded
            and status == "covered"
            and window not in no_exclusion_window_seen
        ):
            sample_days.add(signal_day)
            no_exclusion_window_seen.add(window)

    checks: list[dict[str, Any]] = []
    index_hash_checks: list[bool] = []
    for signal_day in sorted(sample_days):
        resolution = resolver.resolve(signal_day)
        snapshot = finra_gate.build_daily_entry_admission_snapshot(
            ats_rows,
            otc_rows,
            short_rows,
            as_of=signal_day,
            trading_sessions=sessions,
            base_tickers=base_tickers,
            source_identities=source_identities,
        )
        provenance = resolution.get("provenance") or {}
        index_hash_match = snapshot.get("exclusion_index_hash") == exclusion_index.get(
            "index_hash"
        )
        index_hash_checks.append(index_hash_match)
        parity_checks = {
            "as_of": resolution.get("as_of") == snapshot.get("as_of"),
            "eligible_tickers": sorted(resolution.get("tickers") or [])
            == sorted(snapshot.get("eligible_tickers") or []),
            "excluded_tickers": sorted(
                provenance.get("excluded_tickers") or []
            )
            == _excluded_tickers(snapshot),
            "source_hash": resolution.get("source_hash")
            == snapshot.get("source_hash"),
            "source_hashes": provenance.get("source_hashes")
            == snapshot.get("source_hashes"),
            "source_identities": provenance.get("source_identities")
            == snapshot.get("source_identities")
            == source_identities,
            "index_hash": provenance.get("index_hash")
            == snapshot.get("exclusion_index_hash"),
            "complete_index_hash": index_hash_match,
            "resolver_snapshot_hash": resolution.get("snapshot_sha256")
            == snapshot.get("resolver_snapshot_hash"),
            "resolver_record_hash": resolution.get("record_hash")
            == snapshot.get("resolver_record_hash"),
            "membership_hash": resolution.get("membership_hash")
            == snapshot.get("membership_hash"),
            "entry_session": provenance.get("entry_session")
            == snapshot.get("next_trading_session"),
            "state": provenance.get("state") == snapshot.get("state"),
            "coverage_status": provenance.get("coverage_status")
            == snapshot.get("coverage_status"),
            "trade_enabled_false": snapshot.get("trade_enabled") is False,
            "orders_unchanged": all(
                snapshot.get(key) is False
                for key in (
                    "alters_live_orders",
                    "alters_orders",
                    "alters_signal_generation",
                    "alters_candidate_ranking",
                    "alters_sizing",
                    "alters_exits",
                )
            ),
        }
        checks.append(
            {
                "signal_date": signal_day,
                "resolver_excluded": provenance.get("excluded_tickers") or [],
                "daily_excluded": _excluded_tickers(snapshot),
                "parity_checks": parity_checks,
                "matches": all(parity_checks.values()),
            }
        )
    checked_count = max(0, len(sessions) - 1)
    mismatches = [row for row in checks if not row["matches"]]
    complete_index_hash_parity = bool(index_hash_checks) and all(index_hash_checks)
    return {
        "scope": (
            "complete all-session index-hash equality plus adapter projection "
            "on boundary/status/exclusion/no-exclusion representatives"
        ),
        "indexed_session_count": checked_count,
        "sampled_adapter_session_count": len(checks),
        "sampled_adapter_sessions": sorted(sample_days),
        "complete_index_hash_parity": complete_index_hash_parity,
        "mismatch_count": len(mismatches),
        "checks": checks,
        "mismatches": mismatches,
        "all_sessions_match": checked_count > 0
        and complete_index_hash_parity
        and not mismatches,
    }


def _source_contract(
    ats_rows: Sequence[Mapping[str, Any]],
    otc_rows: Sequence[Mapping[str, Any]],
    short_rows: Sequence[Mapping[str, Any]],
    index: Mapping[str, Any],
    resolver: Any,
    file_identity_before: Mapping[str, Any],
    file_identity_after: Mapping[str, Any],
    pit_audit: Mapping[str, Any],
    revision_audit: Mapping[str, Any],
) -> dict[str, Any]:
    ats_manifest = json.loads(ATS_MANIFEST.read_text(encoding="utf-8"))
    otc_manifest = json.loads(OTC_MANIFEST.read_text(encoding="utf-8"))
    resolver_metadata = resolver.metadata
    ats_tickers = {
        str(row.get("ticker") or "").strip().upper() for row in ats_rows
    }
    otc_tickers = {
        str(row.get("ticker") or "").strip().upper() for row in otc_rows
    }
    short_tickers = {
        str(row.get("ticker") or "").strip().upper() for row in short_rows
    }
    raw_clock_checks = {
        "ats_publication_not_before_week": all(
            str(row.get("published_date") or "")[:10]
            >= str(row.get("week_start_date") or "")[:10]
            for row in ats_rows
        ),
        "otc_publication_not_before_week": all(
            str(row.get("published_date") or "")[:10]
            >= str(row.get("week_start_date") or "")[:10]
            for row in otc_rows
        ),
        "short_publication_after_settlement": all(
            str(row.get("publication_date") or "")[:10]
            > str(row.get("settlement_date") or "")[:10]
            for row in short_rows
            if row.get("publication_date") and row.get("settlement_date")
        ),
        "short_rows_revision_aware_pit_safe": all(
            (
                str(row.get("revision_flag") or "").upper() == "R"
                and row.get("pit_safe") is False
                and row.get("as_published_vintage_available") is False
            )
            or (
                not row.get("revision_flag")
                and row.get("pit_safe") is True
                and row.get("as_published_vintage_available") is True
            )
            for row in short_rows
        ),
    }
    checks = {
        "source_files_stable_during_run": file_identity_before
        == file_identity_after,
        "expected_joint_source_hash": index.get("source_hash")
        == EXPECTED_SOURCE_HASH,
        "resolver_source_hash": resolver_metadata.get("source_hash")
        == index.get("source_hash"),
        "resolver_source_hashes": resolver_metadata.get("source_hashes")
        == index.get("source_hashes"),
        "index_source_identities_exact": index.get("source_identities")
        == file_identity_before,
        "resolver_source_identities_exact": resolver_metadata.get(
            "source_identities"
        )
        == file_identity_before,
        "resolver_index_hash": resolver_metadata.get("index_hash")
        == index.get("index_hash"),
        "all_raw_short_interest_csvs_hash_bound": len(
            file_identity_before.get("short_interest_raw_csvs") or {}
        )
        == EXPECTED_RAW_SOURCE_FILE_COUNT,
        "ats_manifest_row_count": int(ats_manifest.get("row_count") or -1)
        == len(ats_rows),
        "otc_manifest_row_count": int(otc_manifest.get("row_count") or -1)
        == len(otc_rows),
        "ats_manifest_ticker_count": int(
            ats_manifest.get("ticker_count") or -1
        )
        == len(ats_tickers),
        "otc_manifest_ticker_count": int(
            otc_manifest.get("ticker_count") or -1
        )
        == len(otc_tickers),
        "ats_summary_type_exact": ats_manifest.get("summary_type_code")
        == "ATS_W_SMBL",
        "otc_summary_type_exact": otc_manifest.get("summary_type_code")
        == "OTC_W_SMBL",
        "input_counts_match_index": index.get("input_row_counts")
        == {
            "ats": len(ats_rows),
            "otc": len(otc_rows),
            "short_interest": len(short_rows),
        },
        "strict_publication_ordering": pit_audit.get("all_pass") is True,
        "revision_provenance_complete": revision_audit.get("all_pass") is True,
        **raw_clock_checks,
    }
    return {
        "source": "official FINRA weekly ATS + non-ATS plus biweekly short interest",
        "file_identity_before": dict(file_identity_before),
        "file_identity_after": dict(file_identity_after),
        "ats_manifest": ats_manifest,
        "otc_manifest": otc_manifest,
        "raw_row_counts": {
            "ats": len(ats_rows),
            "otc": len(otc_rows),
            "short_interest": len(short_rows),
        },
        "raw_ticker_counts": {
            "ats": len(ats_tickers),
            "otc": len(otc_tickers),
            "short_interest": len(short_tickers),
        },
        "canonical_source_hash": index.get("source_hash"),
        "canonical_source_hashes": index.get("source_hashes"),
        "expected_source_hash": EXPECTED_SOURCE_HASH,
        "index_hash": index.get("index_hash"),
        "trading_sessions_hash": index.get("trading_sessions_hash"),
        "valid_row_counts": index.get("valid_row_counts"),
        "invalid_row_counts": index.get("invalid_row_counts"),
        "unmatched_ats_exact_keys": index.get("unmatched_ats_exact_keys"),
        "join_contract": (
            "ATS and OTC rows join only on exact ticker, week_start_date, "
            "published_date, and tier; unmatched rows are not used."
        ),
        "common_stock_contract": {
            "fail_closed_denylist": sorted(
                finra_gate.NON_COMMON_STOCK_TICKERS
            ),
            "heuristic_asset_class_inference_used": False,
        },
        "pit_audit": dict(pit_audit),
        "short_interest_revision_audit": dict(revision_audit),
        "raw_clock_checks": raw_clock_checks,
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def _source_density(
    index: Mapping[str, Any],
    exclusions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter(
        str((state or {}).get("status") or "missing")
        for state in (index.get("state_by_signal_day") or {}).values()
    )
    by_window = Counter(str(row.get("window") or "outside") for row in exclusions)
    by_ticker = Counter(str(row.get("ticker") or "") for row in exclusions)
    return {
        "input_row_counts": index.get("input_row_counts"),
        "valid_row_counts": index.get("valid_row_counts"),
        "invalid_row_counts": index.get("invalid_row_counts"),
        "unmatched_ats_exact_keys": index.get("unmatched_ats_exact_keys"),
        "state_status_counts": dict(sorted(status_counts.items())),
        "resolver_exclusion_count": len(exclusions),
        "resolver_exclusions_by_window": dict(sorted(by_window.items())),
        "resolver_exclusions_by_ticker": dict(sorted(by_ticker.items())),
        "resolver_exclusions": list(exclusions),
    }


def _zero_price_gate2_preflight(
    frozen: Mapping[str, Any] | None = None,
    *,
    enforce_expected_hash: bool = True,
) -> dict[str, Any]:
    """Build and validate every non-price source/parity contract."""

    frozen_payload = dict(frozen or _load_frozen())
    file_identity_before = _source_file_identity()
    (
        policy,
        exclusion_index,
        ats_rows,
        otc_rows,
        short_rows,
        sessions,
        loader_revision_audit,
    ) = _build_policy(frozen_payload, file_identity_before)
    policy_identity = _policy_identity(exclusion_index)
    pit_audit = _resolver_pit_audit(policy, exclusion_index, sessions)
    revision_audit = _short_revision_audit(
        short_rows,
        loader_revision_audit,
        exclusion_index,
        sessions,
        frozen_payload["behavior"]["universe"],
    )
    daily_parity = _daily_parity(
        ats_rows,
        otc_rows,
        short_rows,
        policy,
        exclusion_index,
        sessions,
        frozen_payload["behavior"]["universe"],
        file_identity_before,
    )
    file_identity_after = _source_file_identity()
    source_contract = _source_contract(
        ats_rows,
        otc_rows,
        short_rows,
        exclusion_index,
        policy,
        file_identity_before,
        file_identity_after,
        pit_audit,
        revision_audit,
    )
    checks = {
        "source_hash_locked": (
            exclusion_index.get("source_hash") == EXPECTED_SOURCE_HASH
            if enforce_expected_hash
            else bool(exclusion_index.get("source_hash"))
        ),
        "source_contract": source_contract.get("all_pass") is True
        if enforce_expected_hash
        else all(
            value
            for key, value in (source_contract.get("checks") or {}).items()
            if key != "expected_joint_source_hash"
        ),
        "policy_identity": policy_identity.get("all_pass") is True,
        "strict_publication_ordering": pit_audit.get("all_pass") is True,
        "revision_provenance": revision_audit.get("all_pass") is True,
        "historical_daily_parity": daily_parity.get("all_sessions_match")
        is True,
    }
    return {
        "policy": policy,
        "exclusion_index": exclusion_index,
        "ats_rows": ats_rows,
        "otc_rows": otc_rows,
        "short_rows": short_rows,
        "sessions": sessions,
        "file_identity_before": file_identity_before,
        "policy_identity": policy_identity,
        "pit_audit": pit_audit,
        "revision_audit": revision_audit,
        "daily_parity": daily_parity,
        "source_contract": source_contract,
        "checks": checks,
        "all_pass": all(checks.values()),
    }


def build_artifact() -> dict[str, Any]:
    """Run Gate 1-4 and persist experiment-scoped evidence only."""

    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    if active.get("aggregate", {}).get("expected_value_score_sum") != ACTIVE_EV:
        raise RuntimeError("Active Gate-1 aggregate EV no longer matches the ticket")

    preflight = _zero_price_gate2_preflight(frozen)
    if not preflight["all_pass"]:
        failed = [
            key for key, passed in preflight["checks"].items() if not passed
        ]
        raise RuntimeError(f"FINRA zero-price Gate-2 preflight failed: {failed}")
    policy = preflight["policy"]
    exclusion_index = preflight["exclusion_index"]
    ats_rows = preflight["ats_rows"]
    otc_rows = preflight["otc_rows"]
    short_rows = preflight["short_rows"]
    sessions = preflight["sessions"]
    file_identity_before = preflight["file_identity_before"]
    policy_identity = preflight["policy_identity"]
    pit_audit = preflight["pit_audit"]
    revision_audit = preflight["revision_audit"]
    daily_parity = preflight["daily_parity"]
    source_contract = preflight["source_contract"]
    before_audit_resolver = _FailOpenCandidateAuditResolver(
        frozen["behavior"]["universe"], policy
    )

    source_exclusions = _resolver_exclusions(
        policy, sessions, frozen["behavior"]["universe"]
    )
    source_density = _source_density(exclusion_index, source_exclusions)
    print("[gate2] zero-price source/revision/daily parity passed", flush=True)

    before_records: dict[str, dict[str, Any]] = {}
    after_records: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] before: active cash-feasible static anchor ...", flush=True)
        before_result, before_identity = _run_window(
            spec,
            frozen,
            resolver=before_audit_resolver,
            entry_admission_policy=None,
        )
        before_records[label] = {
            "result": before_result,
            "identity": before_identity,
            "artifact": _persist_result("before", spec, before_result),
        }
        print(
            f"[{label}] after: fixed FINRA venue/short-crowding admission ...",
            flush=True,
        )
        after_result, after_identity = _run_window(
            spec,
            frozen,
            resolver=before_audit_resolver,
            entry_admission_policy=policy,
        )
        after_records[label] = {
            "result": after_result,
            "identity": after_identity,
            "artifact": _persist_result("after", spec, after_result),
        }

    file_identity_after = _source_file_identity()
    source_contract = _source_contract(
        ats_rows,
        otc_rows,
        short_rows,
        exclusion_index,
        policy,
        file_identity_before,
        file_identity_after,
        pit_audit,
        revision_audit,
    )
    gate1_checks = gate_common._static_reference_checks(before_records, active)
    windows: dict[str, Any] = {}
    gate2: dict[str, Any] = {}
    gate3: dict[str, Any] = {}
    candidate_touch: dict[str, Any] = {}
    entry_admission: dict[str, Any] = {}
    addon_audit: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before_headline = _headline(before_records[label]["result"])
        after_headline = _headline(after_records[label]["result"])
        gate2[label] = gate_common._gate2_checks(
            after_records[label]["result"], before_audit_resolver
        )
        gate3[label] = {
            "signals_generated": after_headline["signals_generated"],
            "signals_survived": after_headline["signals_survived"],
            "survival_rate": after_headline["survival_rate"],
            "passed": after_headline["survival_rate"] >= MIN_SURVIVAL_RATE,
        }
        candidate_touch[label] = _candidate_overlap(
            before_records[label]["result"], policy, sessions
        )
        entry_admission[label] = _entry_admission_audit(
            before_records[label]["result"],
            after_records[label]["result"],
            candidate_touch[label],
            policy,
        )
        gate2[label]["entry_admission_audit"] = entry_admission[label]
        gate2[label]["entry_admission_audit_passed"] = entry_admission[
            label
        ]["all_pass"]
        gate2[label]["generated_signals_directly_filtered"] = False
        gate2[label]["survived_signals_directly_filtered"] = False
        gate2[label]["addons_directly_filtered"] = False
        gate2[label]["base_runtime_pass"] = gate2[label]["all_pass"]
        gate2[label]["all_pass"] = gate2[label]["all_pass"] and entry_admission[
            label
        ]["all_pass"]
        addon_audit[label] = gate_common._addon_attribution(
            after_records[label]["result"]
        )
        windows[label] = {
            "window": dict(spec),
            "before": before_headline,
            "after": after_headline,
            "delta": _delta(after_headline, before_headline),
            "before_identity": before_records[label]["identity"],
            "after_identity": after_records[label]["identity"],
            "before_artifact": before_records[label]["artifact"],
            "after_artifact": after_records[label]["artifact"],
            "universe_membership": {
                key: (
                    after_records[label]["result"].get("universe_membership")
                    or {}
                ).get(key)
                for key in (
                    "mode",
                    "trading_days",
                    "identifiable_days",
                    "unidentifiable_days",
                    "min_eligible_count",
                    "max_eligible_count",
                    "snapshot_hashes",
                    "gate3",
                )
            },
        }
    gate2["source_contract_passed"] = source_contract["all_pass"]
    gate2["policy_identity_passed"] = policy_identity["all_pass"]
    gate2["strict_publication_ordering_passed"] = pit_audit["all_pass"]
    gate2["historical_daily_parity_complete"] = daily_parity[
        "all_sessions_match"
    ]
    gate2["short_interest_revision_provenance"] = revision_audit
    gate2["short_interest_revision_provenance_passed"] = revision_audit[
        "all_pass"
    ]
    gate2["frozen_core_revised_counts_by_window"] = revision_audit[
        "frozen_core_revised_counts_by_window"
    ]
    gate2["entry_admission_audit_and_parity_passed"] = all(
        entry_admission[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    gate2["all_windows_runtime_pass"] = all(
        gate2[spec["label"]]["base_runtime_pass"] for spec in gate1.WINDOWS
    )
    gate2["all_windows_pass"] = all(
        (
            gate2["all_windows_runtime_pass"],
            gate2["source_contract_passed"],
            gate2["policy_identity_passed"],
            gate2["strict_publication_ordering_passed"],
            gate2["historical_daily_parity_complete"],
            gate2["short_interest_revision_provenance_passed"],
        )
    )
    gate2["all_windows_including_admission_pass"] = all(
        (
            gate2["all_windows_pass"],
            gate2["entry_admission_audit_and_parity_passed"],
        )
    )
    gate3["all_windows_pass"] = all(
        gate3[spec["label"]]["passed"] for spec in gate1.WINDOWS
    )
    addon_audit["all_windows_clean"] = all(
        addon_audit[spec["label"]]["clean"] for spec in gate1.WINDOWS
    )

    total_generated_touches = sum(
        candidate_touch[spec["label"]]["generated_fresh_candidate_exclusions"]
        for spec in gate1.WINDOWS
    )
    touch_gate = {
        "minimum_aggregate": MIN_FRESH_ENTRY_EXCLUSIONS,
        "minimum_each_window": 1,
        "aggregate_generated_fresh_candidate_exclusions": total_generated_touches,
        "aggregate_survived_fresh_candidate_exclusions": sum(
            candidate_touch[spec["label"]][
                "survived_fresh_candidate_exclusions"
            ]
            for spec in gate1.WINDOWS
        ),
        "aggregate_entered_trade_exclusions": sum(
            candidate_touch[spec["label"]]["entered_trade_exclusions"]
            for spec in gate1.WINDOWS
        ),
        "generated_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "generated_fresh_candidate_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
        "survived_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "survived_fresh_candidate_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
        "entered_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "entered_trade_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
        "aggregate_floor_passed": total_generated_touches
        >= MIN_FRESH_ENTRY_EXCLUSIONS,
        "each_window_floor_passed": all(
            candidate_touch[spec["label"]][
                "generated_fresh_candidate_exclusions"
            ]
            >= 1
            for spec in gate1.WINDOWS
        ),
    }
    touch_gate["all_pass"] = touch_gate["aggregate_floor_passed"] and touch_gate[
        "each_window_floor_passed"
    ]

    before_aggregate = _aggregate(windows, "before")
    after_aggregate = _aggregate(windows, "after")
    aggregate_delta = {
        key: round(float(after_aggregate[key]) - float(before_aggregate[key]), 6)
        for key in before_aggregate
        if isinstance(before_aggregate[key], (int, float))
        and isinstance(after_aggregate.get(key), (int, float))
    }
    gate4 = _gate4_checks(windows, before_aggregate, after_aggregate)

    shared_contract = {
        "shared_helper_imported": True,
        "helper_module": "quant.finra_venue_short_crowding_entry_gate",
        "rule_version": finra_gate.RULE_VERSION,
        "entry_universe_resolver_type": type(before_audit_resolver).__name__,
        "entry_universe_resolver_same_both_arms": True,
        "entry_universe_resolver_always_full_base": True,
        "entry_admission_policy_type": type(policy).__name__,
        "entry_admission_policy_before": None,
        "entry_admission_policy_after": type(policy).__name__,
        "backtester_adapter_default_off": True,
        "generated_signals_directly_filtered": False,
        "survived_signals_directly_filtered": False,
        "addons_directly_filtered": False,
        "delayed_fill_semantics": "admitted_not_strict_next_session",
        "broad_delayed_fill_cancellation": False,
        "daily_default_off_snapshot_callable": callable(
            getattr(finra_gate, "build_daily_entry_admission_snapshot", None)
        ),
        "historical_daily_pit_parity": daily_parity,
        "historical_daily_pit_parity_complete": daily_parity[
            "all_sessions_match"
        ],
        "entry_admission_audit_and_parity": entry_admission,
        "entry_admission_audit_and_parity_complete": gate2[
            "entry_admission_audit_and_parity_passed"
        ],
        "trade_enabled": finra_gate.TRADE_ENABLED,
        "live_order_path_enabled": False,
    }
    execution_envelope = {
        "notional_and_capital": (
            "Unchanged cash-feasible Gate-1 sizing and settled-cash ledger; "
            "the gate can only cancel a not-yet-filled fresh core entry."
        ),
        "liquidity_slippage_and_costs": (
            "Unchanged accepted next-open liquidity, slippage, and round-trip "
            "cost contracts are included in the after replay."
        ),
        "portfolio_competition": (
            "An excluded fill retains cash and may change later slot and cash "
            "competition; the full after replay includes that downstream path."
        ),
        "max_positions_and_exposure": (
            "Existing max-position, sector, heat, and concentration limits remain unchanged."
        ),
        "order_semantics": (
            "The admission policy uses releases strictly before the signal day "
            "and can deny only the strict next-session fill; delayed fills are "
            "explicitly admitted_not_strict_next_session, not broadly cancelled."
        ),
        "kill_switch": (
            "The shared helper and daily snapshot remain trade_enabled=false; "
            "source/hash/schema failure fails open in observation and cannot place orders."
        ),
        "source_failure": (
            "Missing, stale, mismatched, non-common-stock, or non-PIT source "
            "inputs fail open; runner identity drift aborts Gate 2."
        ),
        "live_ready": False,
    }
    execution_envelope["complete"] = all(
        bool(execution_envelope[key])
        for key in (
            "notional_and_capital",
            "liquidity_slippage_and_costs",
            "portfolio_competition",
            "max_positions_and_exposure",
            "order_semantics",
            "kill_switch",
            "source_failure",
        )
    )

    measurement_valid = all(
        (
            gate1_checks["all_windows_exact"],
            gate2["all_windows_including_admission_pass"],
            gate3["all_windows_pass"],
        )
    )
    canonical_gate4_passed = gate4["checks"]["all_pass"]
    strict_full_stack_passed = all(
        (
            measurement_valid,
            touch_gate["all_pass"],
            canonical_gate4_passed,
            addon_audit["all_windows_clean"],
            shared_contract["historical_daily_pit_parity_complete"],
            shared_contract[
                "entry_admission_audit_and_parity_complete"
            ],
            not shared_contract["trade_enabled"],
            execution_envelope["complete"],
        )
    )
    if (
        not gate1_checks["all_windows_exact"]
        or not gate2["all_windows_including_admission_pass"]
    ):
        decision = "blocked_invalid_measurement"
    elif not gate3["all_windows_pass"]:
        decision = "rejected_survival_floor"
    elif not touch_gate["all_pass"]:
        decision = "rejected_insufficient_fresh_entry_overlap"
    elif not canonical_gate4_passed:
        decision = "rejected"
    elif not addon_audit["all_windows_clean"]:
        decision = "rejected_attribution_contamination"
    elif not execution_envelope["complete"]:
        decision = "blocked_incomplete_execution_envelope"
    elif strict_full_stack_passed:
        decision = "accepted_default_off"
    else:
        decision = "blocked_incomplete_full_stack"

    artifact = {
        "schema": "finra_venue_short_crowding_entry_exclusion_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "accepted_alpha": decision == "accepted_default_off",
        "live_ready": False,
        "hypothesis": HYPOTHESIS,
        "single_causal_variable": (
            "fixed PIT FINRA ATS/OTC x rising-short-interest crowding state "
            "used as one strict-next-session fresh-core entry exclusion"
        ),
        "locked_policy": policy_identity,
        "source_contract": source_contract,
        "source_density": source_density,
        "exclusion_index": {
            key: exclusion_index.get(key)
            for key in (
                "schema",
                "source",
                "source_hash",
                "source_hashes",
                "source_identities",
                "rule_version",
                "index_hash",
                "trading_sessions_hash",
                "input_row_counts",
                "valid_row_counts",
                "invalid_row_counts",
                "unmatched_ats_exact_keys",
            )
        },
        "frozen_behavior_inputs": {
            "path": _path_text(FROZEN_INPUTS),
            "file_sha256": gate1._file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
        },
        "active_baseline": {
            "path": _path_text(ACTIVE_BASELINE),
            "sha256": gate1._file_sha256(ACTIVE_BASELINE),
            "aggregate": active["aggregate"],
        },
        "gates": {
            "gate1_before_exact_reproduction": gate1_checks,
            "gate2_runtime_source_pit_and_parity": gate2,
            "gate3_survival": gate3,
            "gate4_canonical_alpha": gate4,
            "predeclared_candidate_touch_floor": touch_gate,
        },
        "verdicts": {
            "source_contract_valid": source_contract["all_pass"],
            "policy_identity_valid": policy_identity["all_pass"],
            "strict_publication_ordering_valid": pit_audit["all_pass"],
            "historical_daily_parity_complete": daily_parity[
                "all_sessions_match"
            ],
            "short_interest_revision_provenance_valid": revision_audit[
                "all_pass"
            ],
            "entry_admission_audit_and_parity_valid": gate2[
                "entry_admission_audit_and_parity_passed"
            ],
            "measurement_valid": measurement_valid,
            "candidate_touch_gate_passed": touch_gate["all_pass"],
            "canonical_gate4_passed": canonical_gate4_passed,
            "addon_attribution_clean": addon_audit["all_windows_clean"],
            "execution_envelope_complete": execution_envelope["complete"],
            "strict_full_stack_passed": strict_full_stack_passed,
            "decision": decision,
        },
        "candidate_touch": candidate_touch,
        "entry_admission": entry_admission,
        "addon_attribution": addon_audit,
        "shared_paper_contract": shared_contract,
        "windows": windows,
        "aggregate": {
            "before": before_aggregate,
            "after": after_aggregate,
            "delta": aggregate_delta,
        },
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "backtester_adapter_default_off": True,
            "entry_universe_membership_changed": False,
            "generated_or_survived_signals_directly_filtered": False,
            "addons_directly_filtered": False,
            "delayed_fills_broadly_cancelled": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "live_or_default_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "rejected_strategy_behavior_retained": False,
        },
        "live_realistic_execution_envelope": execution_envelope,
        "known_limitations": [
            "The common-stock boundary uses the outcome-blind fixed ticker denylist; it is not a historical security-master repair.",
            "The latest global short-interest release is not ticker-forward-filled when a symbol is absent.",
            "The helper fails open on stale or missing source state, so the gate can only remove positively identified crowding rows.",
            "FINRA revisionFlag=R short-interest rows lack as-published vintages and are fail-closed before index construction; the Gate-2 revision audit exposes their frozen-core counts by window.",
            "An entry exclusion can retain cash and alter later slot competition; the full replay measures that downstream consequence.",
            "The full-base audit resolver is identical in both arms; generated and survived rows are retained for touch measurement and are not directly filtered by FINRA membership.",
            "The admission hook never evaluates add-ons, although denying a fresh entry can indirectly change later portfolio trajectory and add-on opportunities.",
            "A delayed fill is explicitly admitted_not_strict_next_session; the policy does not add a broad delayed-fill cancellation.",
            "Acceptance can only be default-off; no live order adapter is enabled.",
        ],
        "nearby_prior": {
            "exp-20260516-035": "FINRA short-crowding risk haircut, not this gate shape.",
            "exp-20260703-016": "Rejected standalone ATS dark-share candidate pool.",
            "exp-20260706-018": "Rejected standalone OTC internalization candidate pool.",
            "exp-20260718-005": "Rejected ORTEX borrow-stress entry admission template.",
            "exp-20260720-002": "Parked FINRA joint candidate-pool response before outcome replay.",
            "exp-20260715-010": "Active cash-feasible Gate-1 comparator.",
        },
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260720_003_finra_venue_short_crowding_entry_exclusion.py"
            )
        },
    }

    gate1._atomic_write_json(
        BEFORE_FILE,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "active_cash_feasible_static_entry_anchor",
            "source": _path_text(ACTIVE_BASELINE),
            "aggregate": before_aggregate,
            "gate1_identity": gate1_checks,
            "windows": {
                label: {
                    "headline": windows[label]["before"],
                    "artifact": windows[label]["before_artifact"],
                }
                for label in windows
            },
        },
    )
    gate1._atomic_write_json(
        AFTER_FILE,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "fixed_finra_venue_short_crowding_entry_admission",
            "decision": decision,
            "source_hash": exclusion_index.get("source_hash"),
            "short_interest_revision_audit": revision_audit,
            "aggregate": after_aggregate,
            "candidate_touch_gate": touch_gate,
            "gate4": gate4,
            "windows": {
                label: {
                    "headline": windows[label]["after"],
                    "artifact": windows[label]["after_artifact"],
                    "gate2": gate2[label],
                    "gate3": gate3[label],
                    "candidate_touch": candidate_touch[label],
                    "entry_admission": entry_admission[label],
                    "addon_attribution": addon_audit[label],
                }
                for label in windows
            },
        },
    )
    gate1._atomic_write_json(ARTIFACT, artifact)
    return artifact


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(value)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)


def _render_markdown(artifact: Mapping[str, Any]) -> str:
    gates = artifact["gates"]
    lines = [
        f"# {EXPERIMENT_ID}: FINRA venue/short-crowding entry admission",
        "",
        f"- Decision: `{artifact['decision']}`",
        f"- Accepted alpha: `{str(artifact['accepted_alpha']).lower()}`",
        f"- Live ready: `{str(artifact['live_ready']).lower()}`",
        f"- Locked source hash: `{artifact['source_contract']['canonical_source_hash']}`",
        "- Price replay count: one completed three-window before/after run; this report was reclassified from those persisted results without replaying prices.",
        "",
        "## Gate summary",
        "",
        f"- Gate 1 exact baseline: `{str(gates['gate1_before_exact_reproduction']['all_windows_exact']).lower()}`",
        f"- Gate 2 source/PIT/revision/admission: `{str(gates['gate2_runtime_source_pit_and_parity']['all_windows_including_admission_pass']).lower()}`",
        f"- Gate 3 survival: `{str(gates['gate3_survival']['all_windows_pass']).lower()}`",
        f"- Candidate-touch floor: `{str(gates['predeclared_candidate_touch_floor']['all_pass']).lower()}`",
        f"- Gate 4 canonical alpha: `{str(gates['gate4_canonical_alpha']['checks']['all_pass']).lower()}`",
        "",
        "## Results",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Denied | Baseline entered touches |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for spec in gate1.WINDOWS:
        label = spec["label"]
        window = artifact["windows"][label]
        admission = artifact["entry_admission"][label]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:.4f} | "
            "${before_pnl:,.2f} | ${after_pnl:,.2f} | {denied} | {expected} |".format(
                label=label,
                before_ev=window["before"]["expected_value_score"],
                after_ev=window["after"]["expected_value_score"],
                delta_ev=window["delta"]["expected_value_score"],
                before_pnl=window["before"]["total_pnl"],
                after_pnl=window["after"]["total_pnl"],
                denied=admission["denied_event_count"],
                expected=admission["eligible_entered_touch_count"],
            )
        )
    aggregate = artifact["aggregate"]
    lines.extend(
        [
            "",
            "Aggregate EV changed from "
            f"`{aggregate['before']['expected_value_score_sum']:.4f}` to "
            f"`{aggregate['after']['expected_value_score_sum']:.4f}` "
            f"(`{aggregate['delta']['expected_value_score_sum']:+.4f}`). "
            "Aggregate PnL changed from "
            f"`${aggregate['before']['total_pnl_sum']:,.2f}` to "
            f"`${aggregate['after']['total_pnl_sum']:,.2f}` "
            f"(`{aggregate['delta']['total_pnl_sum']:+,.2f}`).",
            "",
            "## Revision-safe source contract",
            "",
            f"- Raw CSV files hash-bound: `{artifact['source_contract']['short_interest_revision_audit']['raw_source_file_count']}`",
            f"- Normalized rows raw-matched: `{artifact['source_contract']['short_interest_revision_audit']['matched_normalized_row_count']}`",
            f"- Revised rows failed closed: `{artifact['source_contract']['short_interest_revision_audit']['revised_rows_excluded_from_index']}`",
            f"- Frozen-universe revised rows by window: `{json.dumps(artifact['source_contract']['short_interest_revision_audit']['frozen_core_revised_counts_by_window'], sort_keys=True)}`",
            "",
            "## Admission attribution",
            "",
            "The full-base fail-open audit resolver is identical in both arms. The before arm has no admission policy; the after arm installs the default-off FINRA policy after qualification and actual fill discovery. Every baseline executable exclusion was denied, and every denial was an excluded survived candidate in the after arm's full-base candidate surface. Additional denials are recorded as cash/slot path dependence. Delayed fills are explicitly admitted as `admitted_not_strict_next_session`; add-ons never pass through the hook.",
            "",
            "Gate 4 rejects the hypothesis because aggregate EV and PnL regressed. No live/default order path changed.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260720_003_finra_venue_short_crowding_entry_exclusion.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260720_003_finra_venue_short_crowding_entry_exclusion.py --reclassify-existing",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _load_verified_cached_backtest(
    path: Path,
    recorded_artifact: Mapping[str, Any],
    recorded_identity: Mapping[str, Any],
    *,
    label: str,
    arm: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Authenticate one cached result before parsing or reclassification."""

    expected_path = _path_text(path)
    recorded_path = str(recorded_artifact.get("path") or "")
    expected_sha256 = str(recorded_artifact.get("sha256") or "").lower()
    if recorded_path != expected_path:
        raise RuntimeError(
            f"{label} {arm} cached artifact path mismatch: "
            f"recorded={recorded_path!r} expected={expected_path!r}"
        )
    if len(expected_sha256) != 64:
        raise RuntimeError(f"{label} {arm} cached artifact SHA256 is missing")
    actual_sha256 = gate1._file_sha256(path).lower()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"{label} {arm} cached artifact SHA256 mismatch: "
            f"recorded={expected_sha256} actual={actual_sha256}"
        )

    result = json.loads(path.read_text(encoding="utf-8"))
    recomputed_identity = gate1._result_identity(result)
    canonical_checks = {
        key: key in recorded_identity and recorded_identity.get(key) == value
        for key, value in recomputed_identity.items()
    }
    failed_identity_keys = [
        key for key, passed in canonical_checks.items() if not passed
    ]
    if failed_identity_keys:
        raise RuntimeError(
            f"{label} {arm} cached result identity mismatch: "
            f"{failed_identity_keys}"
        )
    verification = {
        "path": expected_path,
        "recorded_sha256": expected_sha256,
        "actual_sha256": actual_sha256,
        "file_sha256_match": True,
        "canonical_identity_keys": list(recomputed_identity),
        "canonical_identity_checks": canonical_checks,
        "canonical_identity_sha256": gate1._stable_hash(recomputed_identity),
        "all_canonical_identity_keys_match": all(canonical_checks.values()),
        "all_pass": all(canonical_checks.values()),
    }
    return result, recomputed_identity, verification


def _reclassify_existing() -> dict[str, Any]:
    """Reclassify the persisted single replay without invoking BacktestEngine."""

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    preflight = _zero_price_gate2_preflight(frozen)
    if not preflight["all_pass"]:
        failed = [key for key, passed in preflight["checks"].items() if not passed]
        raise RuntimeError(
            f"FINRA zero-price reclassification preflight failed: {failed}"
        )
    policy = preflight["policy"]
    sessions = preflight["sessions"]
    audit_resolver = _FailOpenCandidateAuditResolver(
        frozen["behavior"]["universe"], policy
    )
    before_results: dict[str, Any] = {}
    after_results: dict[str, Any] = {}
    records: dict[str, Any] = {}
    windows: dict[str, Any] = {}
    gate2: dict[str, Any] = {}
    gate3: dict[str, Any] = {}
    candidate_touch: dict[str, Any] = {}
    entry_admission: dict[str, Any] = {}
    addon_audit: dict[str, Any] = {}
    cache_verification: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before_path = BACKTEST_DIR / f"{label}_before_{EXPERIMENT_ID}.json"
        after_path = BACKTEST_DIR / f"{label}_after_{EXPERIMENT_ID}.json"
        prior_window = artifact["windows"][label]
        before, before_identity, before_verification = (
            _load_verified_cached_backtest(
                before_path,
                prior_window["before_artifact"],
                prior_window["before_identity"],
                label=label,
                arm="before",
            )
        )
        after, after_identity, after_verification = (
            _load_verified_cached_backtest(
                after_path,
                prior_window["after_artifact"],
                prior_window["after_identity"],
                label=label,
                arm="after",
            )
        )
        cache_verification[label] = {
            "before": before_verification,
            "after": after_verification,
            "all_pass": before_verification["all_pass"]
            and after_verification["all_pass"],
        }
        before_results[label] = before
        after_results[label] = after
        records[label] = {
            "result": before,
            "identity": before_identity,
        }
        before_headline = _headline(before)
        after_headline = _headline(after)
        candidate_touch[label] = _candidate_overlap(before, policy, sessions)
        entry_admission[label] = _entry_admission_audit(
            before, after, candidate_touch[label], policy
        )
        gate2[label] = gate_common._gate2_checks(after, audit_resolver)
        gate2[label]["entry_admission_audit"] = entry_admission[label]
        gate2[label]["entry_admission_audit_passed"] = entry_admission[label][
            "all_pass"
        ]
        gate2[label]["generated_signals_directly_filtered"] = False
        gate2[label]["survived_signals_directly_filtered"] = False
        gate2[label]["addons_directly_filtered"] = False
        gate2[label]["base_runtime_pass"] = gate2[label]["all_pass"]
        gate2[label]["all_pass"] = gate2[label]["base_runtime_pass"] and (
            entry_admission[label]["all_pass"]
        )
        gate3[label] = {
            "signals_generated": after_headline["signals_generated"],
            "signals_survived": after_headline["signals_survived"],
            "survival_rate": after_headline["survival_rate"],
            "passed": after_headline["survival_rate"] >= MIN_SURVIVAL_RATE,
        }
        addon_audit[label] = gate_common._addon_attribution(after)
        windows[label] = {
            **prior_window,
            "before": before_headline,
            "after": after_headline,
            "delta": _delta(after_headline, before_headline),
            "before_identity": {
                **prior_window["before_identity"],
                **before_identity,
            },
            "after_identity": {
                **prior_window["after_identity"],
                **after_identity,
            },
        }

    cache_verification["all_windows_pass"] = all(
        cache_verification[spec["label"]]["all_pass"]
        for spec in gate1.WINDOWS
    )

    gate1_checks = gate_common._static_reference_checks(records, active)
    gate2.update(
        {
            "source_contract_passed": preflight["source_contract"]["all_pass"],
            "policy_identity_passed": preflight["policy_identity"]["all_pass"],
            "strict_publication_ordering_passed": preflight["pit_audit"]["all_pass"],
            "historical_daily_parity_complete": preflight["daily_parity"][
                "all_sessions_match"
            ],
            "short_interest_revision_provenance": preflight["revision_audit"],
            "short_interest_revision_provenance_passed": preflight[
                "revision_audit"
            ]["all_pass"],
            "frozen_core_revised_counts_by_window": preflight["revision_audit"][
                "frozen_core_revised_counts_by_window"
            ],
        }
    )
    gate2["entry_admission_audit_and_parity_passed"] = all(
        entry_admission[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    gate2["all_windows_runtime_pass"] = all(
        gate2[spec["label"]]["base_runtime_pass"] for spec in gate1.WINDOWS
    )
    gate2["all_windows_pass"] = all(
        (
            gate2["all_windows_runtime_pass"],
            gate2["source_contract_passed"],
            gate2["policy_identity_passed"],
            gate2["strict_publication_ordering_passed"],
            gate2["historical_daily_parity_complete"],
            gate2["short_interest_revision_provenance_passed"],
        )
    )
    gate2["all_windows_including_admission_pass"] = (
        gate2["all_windows_pass"]
        and gate2["entry_admission_audit_and_parity_passed"]
    )
    gate2["cached_replay_artifacts_verified"] = cache_verification[
        "all_windows_pass"
    ]
    gate2["cached_replay_artifact_verification"] = cache_verification
    gate3["all_windows_pass"] = all(
        gate3[spec["label"]]["passed"] for spec in gate1.WINDOWS
    )
    addon_audit["all_windows_clean"] = all(
        addon_audit[spec["label"]]["clean"] for spec in gate1.WINDOWS
    )
    total_generated = sum(
        candidate_touch[spec["label"]]["generated_fresh_candidate_exclusions"]
        for spec in gate1.WINDOWS
    )
    touch_gate = {
        "minimum_aggregate": MIN_FRESH_ENTRY_EXCLUSIONS,
        "minimum_each_window": 1,
        "aggregate_generated_fresh_candidate_exclusions": total_generated,
        "aggregate_survived_fresh_candidate_exclusions": sum(
            candidate_touch[spec["label"]]["survived_fresh_candidate_exclusions"]
            for spec in gate1.WINDOWS
        ),
        "aggregate_entered_trade_exclusions": sum(
            candidate_touch[spec["label"]]["entered_trade_exclusions"]
            for spec in gate1.WINDOWS
        ),
        "generated_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "generated_fresh_candidate_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
        "survived_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "survived_fresh_candidate_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
        "entered_by_window": {
            spec["label"]: candidate_touch[spec["label"]][
                "entered_trade_exclusions"
            ]
            for spec in gate1.WINDOWS
        },
    }
    touch_gate["aggregate_floor_passed"] = (
        total_generated >= MIN_FRESH_ENTRY_EXCLUSIONS
    )
    touch_gate["each_window_floor_passed"] = all(
        candidate_touch[spec["label"]]["generated_fresh_candidate_exclusions"]
        >= 1
        for spec in gate1.WINDOWS
    )
    touch_gate["all_pass"] = (
        touch_gate["aggregate_floor_passed"]
        and touch_gate["each_window_floor_passed"]
    )
    before_aggregate = _aggregate(windows, "before")
    after_aggregate = _aggregate(windows, "after")
    aggregate_delta = {
        key: round(float(after_aggregate[key]) - float(before_aggregate[key]), 6)
        for key in before_aggregate
        if isinstance(before_aggregate[key], (int, float))
        and isinstance(after_aggregate.get(key), (int, float))
    }
    gate4 = _gate4_checks(windows, before_aggregate, after_aggregate)
    measurement_valid = all(
        (
            cache_verification["all_windows_pass"],
            gate1_checks["all_windows_exact"],
            gate2["all_windows_including_admission_pass"],
            gate3["all_windows_pass"],
        )
    )
    if (
        not cache_verification["all_windows_pass"]
        or not gate1_checks["all_windows_exact"]
        or not gate2["all_windows_including_admission_pass"]
    ):
        decision = "blocked_invalid_measurement"
    elif not gate3["all_windows_pass"]:
        decision = "rejected_survival_floor"
    elif not touch_gate["all_pass"]:
        decision = "rejected_insufficient_fresh_entry_overlap"
    elif not gate4["checks"]["all_pass"]:
        decision = "rejected"
    elif not addon_audit["all_windows_clean"]:
        decision = "rejected_attribution_contamination"
    else:
        decision = "accepted_default_off"
    strict_full_stack_passed = (
        decision == "accepted_default_off"
        and artifact["live_realistic_execution_envelope"]["complete"]
        and not artifact["shared_paper_contract"]["trade_enabled"]
    )
    artifact.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "accepted_alpha": decision == "accepted_default_off",
            "candidate_touch": candidate_touch,
            "entry_admission": entry_admission,
            "addon_attribution": addon_audit,
            "reclassification_cache_verification": cache_verification,
            "windows": windows,
            "aggregate": {
                "before": before_aggregate,
                "after": after_aggregate,
                "delta": aggregate_delta,
            },
        }
    )
    artifact["gates"] = {
        "gate1_before_exact_reproduction": gate1_checks,
        "gate2_runtime_source_pit_and_parity": gate2,
        "gate3_survival": gate3,
        "gate4_canonical_alpha": gate4,
        "predeclared_candidate_touch_floor": touch_gate,
    }
    artifact["source_contract"] = preflight["source_contract"]
    artifact["shared_paper_contract"][
        "entry_admission_audit_and_parity"
    ] = entry_admission
    artifact["shared_paper_contract"][
        "entry_admission_audit_and_parity_complete"
    ] = gate2["entry_admission_audit_and_parity_passed"]
    artifact["verdicts"].update(
        {
            "source_contract_valid": preflight["source_contract"]["all_pass"],
            "policy_identity_valid": preflight["policy_identity"]["all_pass"],
            "strict_publication_ordering_valid": preflight["pit_audit"]["all_pass"],
            "historical_daily_parity_complete": preflight["daily_parity"][
                "all_sessions_match"
            ],
            "short_interest_revision_provenance_valid": preflight[
                "revision_audit"
            ]["all_pass"],
            "entry_admission_audit_and_parity_valid": gate2[
                "entry_admission_audit_and_parity_passed"
            ],
            "cached_replay_artifacts_verified": cache_verification[
                "all_windows_pass"
            ],
            "measurement_valid": measurement_valid,
            "candidate_touch_gate_passed": touch_gate["all_pass"],
            "canonical_gate4_passed": gate4["checks"]["all_pass"],
            "addon_attribution_clean": addon_audit["all_windows_clean"],
            "strict_full_stack_passed": strict_full_stack_passed,
            "decision": decision,
        }
    )
    after_measurement = json.loads(AFTER_FILE.read_text(encoding="utf-8"))
    after_measurement.update(
        {
            "decision": decision,
            "aggregate": after_aggregate,
            "candidate_touch_gate": touch_gate,
            "gate4": gate4,
            "short_interest_revision_audit": preflight["revision_audit"],
            "cached_replay_artifact_verification": cache_verification,
        }
    )
    for spec in gate1.WINDOWS:
        label = spec["label"]
        after_measurement["windows"][label].update(
            {
                "headline": windows[label]["after"],
                "gate2": gate2[label],
                "gate3": gate3[label],
                "candidate_touch": candidate_touch[label],
                "entry_admission": entry_admission[label],
                "addon_attribution": addon_audit[label],
            }
        )
    gate1._atomic_write_json(AFTER_FILE, after_measurement)
    gate1._atomic_write_json(ARTIFACT, artifact)
    _atomic_write_text(MARKDOWN_ARTIFACT, _render_markdown(artifact))
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or [])
    if args == ["--reclassify-existing"]:
        artifact = _reclassify_existing()
    elif args:
        raise SystemExit(
            "This fixed-policy runner accepts only --reclassify-existing"
        )
    else:
        artifact = build_artifact()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "verdicts": artifact["verdicts"],
                "aggregate": artifact["aggregate"],
                "candidate_touch": artifact["gates"][
                    "predeclared_candidate_touch_floor"
                ],
                "artifact": _path_text(ARTIFACT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if artifact.get("decision") == "accepted_default_off":
        return 0
    if str(artifact.get("decision") or "").startswith("rejected"):
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
