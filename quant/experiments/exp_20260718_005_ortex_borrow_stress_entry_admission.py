"""exp-20260718-005: fixed ORTEX borrow-stress core entry admission.

This is the first Gate-1..4 consumption of the authenticated historical ORTEX
``costToBorrowNew`` surface built by exp-20260718-003.  The policy is frozen to
the exp-20260712-013 iBorrowDesk scout before any ORTEX outcome is read:

* stressed when fee >= 1.0%, or when the five-session fee rise is >= 0.25pp
  and availability is <= 70% of its five-session-ago value;
* transition when the immediately prior trading session is not stressed;
  missing prior-session source data resets that state to non-stressed, exactly
  as in the predecessor runner;
* one next-open fresh-entry exclusion, with a ten-session ticker cooldown;
* no threshold, lookback, cooldown, ranking, sizing, exit, or cost retuning.

ORTEX supplies fee but not availability.  The compound availability branch is
therefore explicitly unavailable/false; it is never imputed from CTB.  The
shared helper is default-off.  Historical replay uses it only through an
experiment resolver, and the daily observer merely emits its decision surface.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
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
import ortex_borrow_entry_gate as borrow_gate  # noqa: E402
import ortex_data_sidecar as sidecar  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260718-005"
PROTOCOL_ID = "ortex_exp20260712_013_fixed_stress_entry_admission_v1"
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
SOURCE_ROWS = sidecar.NORMALIZED_ROWS_PATH
SOURCE_FETCH_SUMMARY = (
    ROOT / "data" / "experiments" / "exp-20260718-003" / "ortex_fetch_summary.json"
)
SOURCE_READY_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260718-003"
    / "exp_20260718_003_ortex_borrow_observer_breadth.json"
)
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BACKTEST_DIR = EXP_DIR / "backtests"
BEFORE_FILE = EXP_DIR / "before_measurement.json"
AFTER_FILE = EXP_DIR / "after_measurement.json"
ARTIFACT = EXP_DIR / "exp_20260718_005_ortex_borrow_stress_entry_admission.json"

ACTIVE_EV = 6.2057
REQUIRED_EV = 6.82627
MIN_SURVIVAL_RATE = 0.05
MIN_FRESH_ENTRY_EXCLUSIONS = 5

HYPOTHESIS = (
    "Authenticated PIT ORTEX cost-to-borrow history now covers old_thin. "
    "Applying the unchanged exp-20260712-013 borrow-stress transition policy "
    "as a next-open fresh-core entry-admission exclusion should avoid "
    "crowded-short and lending-stress underperformance and improve the "
    "cash-feasible strategy across all three canonical windows."
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
    sessions = {
        day_text
        for spec in gate1.WINDOWS
        for day_text in gate1._spy_dates(spec)
    }
    latest_end = max(date.fromisoformat(spec["end"]) for spec in gate1.WINDOWS)
    sessions.update(
        candidate.isoformat()
        for offset in range(1, 15)
        if is_us_equity_session(candidate := latest_end + timedelta(days=offset))
    )
    return sorted(sessions)


def _run_window(
    spec: dict[str, str],
    frozen: dict[str, Any],
    *,
    resolver: Any | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    universe_metadata = {
        "measurement_protocol": PROTOCOL_ID,
        "source_role": "authenticated ORTEX PIT costToBorrowNew entry admission",
        "security_master_survivorship_status": (
            "current frozen roster; the gate does not claim delisted-security repair"
        ),
    }
    if resolver is not None:
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
        universe_mode=(
            "pit_walk_forward" if resolver is not None else "static_pool_hypothesis"
        ),
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


def _source_contract() -> dict[str, Any]:
    fetch = json.loads(SOURCE_FETCH_SUMMARY.read_text(encoding="utf-8"))
    ready = json.loads(SOURCE_READY_ARTIFACT.read_text(encoding="utf-8"))
    materialization = fetch.get("materialization") or {}
    credential = sidecar.load_api_key()
    credential_is_private_non_test = bool(
        credential and str(credential).strip().upper() != "TEST"
    )
    return {
        "account_authorization_evidenced": bool(
            credential_is_private_non_test
            and materialization.get("status") == "completed"
            and float(materialization.get("credits_used_total") or 0.0) > 0.0
        ),
        "credential_present": bool(credential),
        "credential_is_private_non_test": credential_is_private_non_test,
        "credential_value_persisted_in_artifact": False,
        "authenticated_credit_metered_fetch": bool(
            float(materialization.get("credits_used_total") or 0.0) > 0.0
            and materialization.get("credits_left_last_reported") is not None
        ),
        "credits_used_total": materialization.get("credits_used_total"),
        "credits_left_last_reported": materialization.get(
            "credits_left_last_reported"
        ),
        "api_key_persisted": materialization.get("api_key_persisted") is True,
        "separate_license_manifest_present": False,
        "permitted_use_or_redistribution_manifest_present": False,
        "authorization_boundary": (
            "Private provider account access and credit-metered historical API "
            "use are evidenced. No repository-auditable redistribution/license "
            "manifest exists; results remain local default-off research."
        ),
        "source_rows_path": _path_text(SOURCE_ROWS),
        "source_rows_sha256": gate1._file_sha256(SOURCE_ROWS),
        "source_ready_artifact": _path_text(SOURCE_READY_ARTIFACT),
        "source_ready_artifact_sha256": gate1._file_sha256(SOURCE_READY_ARTIFACT),
        "source_ready_decision": ready.get("decision"),
        "source_ready_acceptance": ready.get("acceptance"),
    }


def _policy_identity() -> dict[str, Any]:
    expected = {
        "fee_level_stress_pct": 1.0,
        "fee_delta5_stress_pp": 0.25,
        "availability_ratio5_stress": 0.70,
        "lookback_sessions": 5,
        "cooldown_sessions": 10,
    }
    actual = {
        "fee_level_stress_pct": borrow_gate.FEE_LEVEL_STRESS,
        "fee_delta5_stress_pp": borrow_gate.FEE_DELTA5_STRESS,
        "availability_ratio5_stress": borrow_gate.AVAIL_RATIO5_STRESS,
        "lookback_sessions": borrow_gate.LOOKBACK_SESSIONS,
        "cooldown_sessions": borrow_gate.COOLDOWN_SESSIONS,
    }
    checks = {key: actual[key] == value for key, value in expected.items()}
    checks.update(
        {
            "availability_field_present_in_ortex": False,
            "missing_availability_branch_failed_closed": True,
            "entry_semantics": "one exclusion on usable next-open session",
            "transition_semantics": (
                "immediately prior trading session not stressed; a missing "
                "prior-session row resets stressed_prev to false"
            ),
            "threshold_or_response_retuned": False,
        }
    )
    return {
        "predecessor": "exp-20260712-013",
        "rule_version": borrow_gate.RULE_VERSION,
        "expected": expected,
        "actual": actual,
        "checks": checks,
        "exact_numeric_match": all(
            checks[key] for key in expected
        ),
    }


def _build_resolver(
    frozen: Mapping[str, Any],
) -> tuple[Any, dict[str, Any], list[dict[str, Any]], list[str]]:
    rows = sidecar.load_normalised_rows(SOURCE_ROWS)
    sessions = _all_sessions()
    index = borrow_gate.build_ortex_borrow_stress_exclusion_index(
        rows,
        sessions,
    )
    resolver = borrow_gate.OrtexBorrowEntryUniverseResolver(
        base_tickers=frozen["behavior"]["universe"],
        exclusion_index=index,
        trading_sessions=sessions,
        source_rows_sha256=index["source_rows_canonical_hash"],
    )
    return resolver, index, rows, sessions


def _window_for_day(day: str) -> str | None:
    return next(
        (
            spec["label"]
            for spec in gate1.WINDOWS
            if spec["start"] <= day <= spec["end"]
        ),
        None,
    )


def _resolver_exclusions(
    resolver: Any,
    sessions: Sequence[str],
    base_tickers: Sequence[str],
) -> list[dict[str, Any]]:
    base = {str(ticker).upper() for ticker in base_tickers}
    exclusions: list[dict[str, Any]] = []
    for index, signal_day in enumerate(sessions[:-1]):
        resolution = resolver.resolve(signal_day)
        if resolution.get("status") != "resolved":
            continue
        eligible = {str(ticker).upper() for ticker in resolution.get("tickers") or []}
        excluded = sorted(base - eligible)
        if not excluded:
            continue
        provenance = resolution.get("provenance") or {}
        entry_session = str(
            provenance.get("entry_session")
            or resolution.get("entry_session")
            or sessions[index + 1]
        )
        for ticker in excluded:
            exclusions.append(
                {
                    "ticker": ticker,
                    "signal_date": signal_day,
                    "entry_date": entry_session,
                    "window": _window_for_day(entry_session),
                    "source_hash": resolution.get("source_hash"),
                    "snapshot_sha256": resolution.get("snapshot_sha256"),
                    "record_hash": resolution.get("record_hash"),
                }
            )
    return exclusions


def _candidate_overlap(
    result: Mapping[str, Any],
    resolver: Any,
) -> dict[str, Any]:
    membership = result.get("universe_membership") or {}

    def excluded(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        hits: dict[tuple[str, str], dict[str, Any]] = {}
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            signal_day = str(
                raw.get("signal_date") or raw.get("date") or raw.get("as_of") or ""
            )[:10]
            if not ticker or not signal_day:
                continue
            resolution = resolver.resolve(signal_day)
            eligible = {
                str(value).upper() for value in resolution.get("tickers") or []
            }
            if resolution.get("status") == "resolved" and ticker not in eligible:
                provenance = resolution.get("provenance") or {}
                hits[(ticker, signal_day)] = {
                    "ticker": ticker,
                    "signal_date": signal_day,
                    "entry_date": provenance.get("entry_session"),
                    "strategy": raw.get("strategy"),
                    "sector": raw.get("sector"),
                }
        return sorted(hits.values(), key=lambda row: (row["signal_date"], row["ticker"]))

    generated = excluded(list(membership.get("generated_signals") or []))
    survived = excluded(list(membership.get("survived_signals") or []))
    return {
        "generated_fresh_candidate_exclusions": len(generated),
        "survived_fresh_candidate_exclusions": len(survived),
        "generated_rows": generated,
        "survived_rows": survived,
    }


def _daily_parity(
    rows: Sequence[Mapping[str, Any]],
    resolver: Any,
    sessions: Sequence[str],
    base_tickers: Sequence[str],
) -> dict[str, Any]:
    base = {str(ticker).upper() for ticker in base_tickers}
    checks: list[dict[str, Any]] = []
    for signal_day in sessions[:-1]:
        resolution = resolver.resolve(signal_day)
        eligible = {str(ticker).upper() for ticker in resolution.get("tickers") or []}
        resolver_excluded = sorted(base - eligible)
        if not resolver_excluded:
            continue
        snapshot = borrow_gate.build_daily_entry_admission_snapshot(
            rows,
            as_of=signal_day,
            trading_sessions=sessions,
            base_tickers=base_tickers,
        )
        daily_excluded = snapshot.get("excluded_tickers")
        if daily_excluded is None:
            daily_excluded = snapshot.get("excluded_tickers_for_next_session")
        if daily_excluded is None:
            daily_excluded = (snapshot.get("entry_admission") or {}).get(
                "excluded_tickers"
            )
        daily_values = sorted(str(ticker).upper() for ticker in (daily_excluded or []))
        provenance = resolution.get("provenance") or {}
        parity_checks = {
            "excluded_tickers": resolver_excluded == daily_values,
            "source_hash": resolution.get("source_hash")
            == snapshot.get("source_hash"),
            "index_hash": provenance.get("index_hash")
            == snapshot.get("exclusion_index_hash"),
            "resolver_snapshot_hash": resolution.get("snapshot_sha256")
            == snapshot.get("resolver_snapshot_hash"),
            "resolver_record_hash": resolution.get("record_hash")
            == snapshot.get("resolver_record_hash"),
            "membership_hash": resolution.get("membership_hash")
            == snapshot.get("membership_hash"),
            "entry_session": provenance.get("entry_session")
            == snapshot.get("next_trading_session"),
            "trade_enabled_false": snapshot.get("trade_enabled") is False,
        }
        checks.append(
            {
                "signal_date": signal_day,
                "resolver_excluded": resolver_excluded,
                "daily_excluded": daily_values,
                "parity_checks": parity_checks,
                "matches": all(parity_checks.values()),
                "trade_enabled": snapshot.get("trade_enabled"),
            }
        )
    return {
        "checked_exclusion_dates": len(checks),
        "all_exclusion_dates_match": bool(checks) and all(
            row["matches"] and row["trade_enabled"] is False for row in checks
        ),
        "checks": checks,
    }


def _source_density(
    rows: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    blocks = sorted({str(row.get("historical_block") or "unknown") for row in rows})
    by_block: dict[str, Any] = {}
    for block in blocks:
        subset = [row for row in rows if str(row.get("historical_block") or "unknown") == block]
        tickers = {str(row.get("ticker") or "").upper() for row in subset}
        provider_dates = {str(row.get("provider_date") or "")[:10] for row in subset}
        values = [
            float(row["cost_to_borrow_new_pct"])
            for row in subset
            if isinstance(row.get("cost_to_borrow_new_pct"), (int, float))
        ]
        by_block[block] = {
            "rows": len(subset),
            "tickers": len(tickers),
            "provider_dates": len(provider_dates),
            "fee_ge_1pct_rows": sum(value >= 1.0 for value in values),
            "fee_min_pct": min(values) if values else None,
            "fee_max_pct": max(values) if values else None,
        }
    exclusion_by_window = Counter(
        str(row.get("window") or "outside") for row in exclusions
    )
    exclusion_by_ticker = Counter(str(row.get("ticker") or "") for row in exclusions)
    return {
        "rows": len(rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows}),
        "blocks": by_block,
        "resolver_exclusion_count": len(exclusions),
        "resolver_exclusions_by_window": dict(sorted(exclusion_by_window.items())),
        "resolver_exclusions_by_ticker": dict(sorted(exclusion_by_ticker.items())),
        "resolver_exclusions": list(exclusions),
    }


def build_artifact() -> dict[str, Any]:
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    if active.get("aggregate", {}).get("expected_value_score_sum") != ACTIVE_EV:
        raise RuntimeError("Active Gate-1 aggregate EV no longer matches frozen hurdle")

    source_contract = _source_contract()
    policy_identity = _policy_identity()
    resolver, exclusion_index, source_rows, sessions = _build_resolver(frozen)
    source_contract["source_rows_file_sha256"] = source_contract[
        "source_rows_sha256"
    ]
    source_contract["source_rows_canonical_sha256"] = exclusion_index[
        "source_rows_canonical_hash"
    ]
    source_contract["canonical_row_hash_verified"] = (
        exclusion_index["source_rows_sha256"]
        == exclusion_index["source_rows_canonical_hash"]
    )
    source_exclusions = _resolver_exclusions(
        resolver, sessions, frozen["behavior"]["universe"]
    )
    source_density = _source_density(source_rows, source_exclusions)
    daily_parity = _daily_parity(
        source_rows, resolver, sessions, frozen["behavior"]["universe"]
    )

    before_records: dict[str, dict[str, Any]] = {}
    after_records: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] before: active cash-feasible static anchor ...", flush=True)
        before_result, before_identity = _run_window(spec, frozen, resolver=None)
        before_records[label] = {
            "result": before_result,
            "identity": before_identity,
            "artifact": _persist_result("before", spec, before_result),
        }
        print(f"[{label}] after: fixed ORTEX borrow-stress admission ...", flush=True)
        after_result, after_identity = _run_window(spec, frozen, resolver=resolver)
        after_records[label] = {
            "result": after_result,
            "identity": after_identity,
            "artifact": _persist_result("after", spec, after_result),
        }

    gate1_checks = gate_common._static_reference_checks(before_records, active)
    windows: dict[str, Any] = {}
    gate2: dict[str, Any] = {}
    gate3: dict[str, Any] = {}
    addon_audit: dict[str, Any] = {}
    candidate_touch: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before_headline = gate_common._headline(before_records[label]["result"])
        after_headline = gate_common._headline(after_records[label]["result"])
        gate2[label] = gate_common._gate2_checks(
            after_records[label]["result"], resolver
        )
        gate3[label] = {
            "signals_generated": after_headline["signals_generated"],
            "signals_survived": after_headline["signals_survived"],
            "survival_rate": after_headline["survival_rate"],
            "passed": after_headline["survival_rate"] >= MIN_SURVIVAL_RATE,
        }
        addon_audit[label] = gate_common._addon_attribution(
            after_records[label]["result"]
        )
        candidate_touch[label] = _candidate_overlap(
            before_records[label]["result"], resolver
        )
        windows[label] = {
            "window": dict(spec),
            "before": before_headline,
            "after": after_headline,
            "delta": gate_common._delta(after_headline, before_headline),
            "before_identity": before_records[label]["identity"],
            "after_identity": after_records[label]["identity"],
            "before_artifact": before_records[label]["artifact"],
            "after_artifact": after_records[label]["artifact"],
        }
    gate2["all_windows_pass"] = all(
        gate2[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
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
        "aggregate_generated_fresh_candidate_exclusions": total_generated_touches,
        "at_least_five": total_generated_touches >= MIN_FRESH_ENTRY_EXCLUSIONS,
        "at_least_one_each_window": all(
            candidate_touch[spec["label"]]["generated_fresh_candidate_exclusions"]
            >= 1
            for spec in gate1.WINDOWS
        ),
    }
    touch_gate["all_pass"] = touch_gate["at_least_five"] and touch_gate[
        "at_least_one_each_window"
    ]

    before_aggregate = gate_common._aggregate(windows, "before")
    after_aggregate = gate_common._aggregate(windows, "after")
    aggregate_delta = {
        key: round(float(after_aggregate[key]) - float(before_aggregate[key]), 6)
        for key in before_aggregate
        if isinstance(before_aggregate[key], (int, float))
        and isinstance(after_aggregate[key], (int, float))
    }
    gate4 = gate_common._gate4_checks(
        windows, before_aggregate, after_aggregate
    )

    source_and_policy_valid = all(
        (
            source_contract["account_authorization_evidenced"],
            source_contract["source_ready_decision"]
            == "accepted_measurement_repair_ortex_borrow_observer_ready",
            policy_identity["exact_numeric_match"],
            source_density["blocks"].get("old_thin", {}).get("rows", 0) > 0,
        )
    )
    measurement_valid = all(
        (
            gate1_checks["all_windows_exact"],
            gate2["all_windows_pass"],
            gate3["all_windows_pass"],
            source_and_policy_valid,
        )
    )
    shared_contract = {
        "shared_helper_imported": True,
        "resolver_type": type(resolver).__name__,
        "daily_default_off_snapshot_callable": callable(
            getattr(borrow_gate, "build_daily_entry_admission_snapshot", None)
        ),
        "historical_daily_pit_parity": daily_parity,
        "historical_daily_pit_parity_complete": daily_parity[
            "all_exclusion_dates_match"
        ],
        "observer_integration": "ortex_borrow_observer.build_daily_snapshot",
        "trade_enabled": False,
        "live_order_path_enabled": False,
    }
    canonical_gate4_passed = gate4["checks"]["all_pass"]
    strict_full_stack_passed = all(
        (
            measurement_valid,
            touch_gate["all_pass"],
            canonical_gate4_passed,
            addon_audit["all_windows_clean"],
            shared_contract["historical_daily_pit_parity_complete"],
            not shared_contract["trade_enabled"],
        )
    )
    if not measurement_valid:
        decision = "blocked_invalid_measurement"
    elif not shared_contract["historical_daily_pit_parity_complete"]:
        decision = "blocked_incomplete_full_stack"
    elif not touch_gate["all_pass"]:
        decision = "rejected_insufficient_fresh_entry_overlap"
    elif not canonical_gate4_passed:
        decision = "rejected"
    elif not addon_audit["all_windows_clean"]:
        decision = "rejected_attribution_contamination"
    elif strict_full_stack_passed:
        decision = "accepted_default_off"
    else:
        decision = "blocked_incomplete_full_stack"

    artifact = {
        "schema": "ortex_borrow_stress_entry_admission_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "accepted_alpha": decision == "accepted_default_off",
        "live_ready": False,
        "hypothesis": HYPOTHESIS,
        "single_causal_variable": (
            "unchanged exp-20260712-013 borrow-stress transition policy used "
            "as one next-open fresh-core entry-admission exclusion"
        ),
        "source_contract": source_contract,
        "source_density": source_density,
        "locked_policy": policy_identity,
        "exclusion_index": {
            "schema": exclusion_index.get("schema"),
            "rule_version": exclusion_index.get("rule_version"),
            "index_hash": exclusion_index.get("index_hash"),
            "source_rows_sha256": exclusion_index.get("source_rows_sha256"),
            "source_rows_canonical_hash": exclusion_index.get(
                "source_rows_canonical_hash"
            ),
            "source_rows_sha256_supplied": exclusion_index.get(
                "source_rows_sha256_supplied"
            ),
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
            "gate2_runtime_fields_and_pit_provenance": gate2,
            "gate3_survival": gate3,
            "gate4_canonical_alpha": gate4,
            "predeclared_candidate_touch_floor": touch_gate,
        },
        "verdicts": {
            "source_and_policy_valid": source_and_policy_valid,
            "measurement_valid": measurement_valid,
            "candidate_touch_gate_passed": touch_gate["all_pass"],
            "canonical_gate4_passed": canonical_gate4_passed,
            "addon_attribution_clean": addon_audit["all_windows_clean"],
            "strict_full_stack_passed": strict_full_stack_passed,
            "decision": decision,
        },
        "candidate_touch": candidate_touch,
        "addon_attribution": addon_audit,
        "shared_paper_contract": shared_contract,
        "windows": windows,
        "aggregate": {
            "before": before_aggregate,
            "after": after_aggregate,
            "delta": aggregate_delta,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_observer_schema_extended": True,
            "trade_enabled": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "rejected_strategy_behavior_retained": False,
        },
        "live_realistic_execution_envelope": {
            "notional_and_capital": (
                "Unchanged cash-feasible Gate-1 sizing and cash ledger; the "
                "experiment resolver can only cancel a not-yet-filled entry."
            ),
            "liquidity_slippage_and_costs": (
                "Unchanged accepted next-open fill, slippage, and round-trip cost contracts."
            ),
            "portfolio_competition": (
                "An excluded entry retains cash and can change later slot competition; "
                "the full after replay includes that downstream path."
            ),
            "max_positions_and_exposure": "Existing caps and sector constraints unchanged.",
            "order_semantics": (
                "The resolver evaluates whether the queued next-open fill session "
                "is the transition's strict usable session."
            ),
            "kill_switch": (
                "No live adapter exists; observer and helper stay trade_enabled=false."
            ),
            "source_failure": (
                "Hash, schema, or clock failure aborts measurement and cannot affect orders."
            ),
            "license_boundary": source_contract["authorization_boundary"],
            "live_ready": False,
        },
        "known_limitations": [
            "ORTEX supplies CTB-new but no lendable-availability history, so the compound availability branch never fires.",
            "The authenticated historical pull covers three central blocks, not every session in each canonical window; uncovered dates fail open.",
            "The security master is the frozen current roster and does not repair survivorship.",
            "Provider account authorization is evidenced, but a separate redistribution/license manifest is absent.",
            "Any resolver-driven add-on change fails causal attribution.",
            "Acceptance can only be default-off; no live locate/borrow-availability claim is made.",
        ],
        "nearby_prior": {
            "exp-20260712-013": "Frozen observed-only borrow-stress policy and thresholds.",
            "exp-20260718-003": "Authenticated ORTEX PIT breadth and settlement repair.",
            "exp-20260715-010": "Active cash-feasible Gate-1 comparator.",
            "exp-20260718-004": (
                "Concurrent but independent ORTEX+Moomoo pair-spread gate; no files "
                "or decision variables are shared with this entry-admission ticket."
            ),
        },
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260718_005_ortex_borrow_stress_entry_admission.py"
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
            "role": "fixed_ortex_borrow_stress_entry_admission",
            "decision": decision,
            "aggregate": after_aggregate,
            "candidate_touch_gate": touch_gate,
            "windows": {
                label: {
                    "headline": windows[label]["after"],
                    "artifact": windows[label]["after_artifact"],
                    "gate2": gate2[label],
                    "candidate_touch": candidate_touch[label],
                    "addon_attribution": addon_audit[label],
                }
                for label in windows
            },
        },
    )
    gate1._atomic_write_json(ARTIFACT, artifact)
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        raise SystemExit("This fixed-policy runner takes no arguments")
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
    if artifact["decision"] == "accepted_default_off":
        return 0
    if artifact["decision"].startswith("rejected"):
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
