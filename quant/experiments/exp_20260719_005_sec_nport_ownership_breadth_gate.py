"""exp-20260719-005: N-PORT holder-breadth fresh-entry eligibility.

The policy was fixed before outcome measurement.  For each next-open fresh
core candidate, use only Form N-PORT rows whose filing date is strictly before
that action date.  With at least 20 matched continuously reporting fund
series, a negative net holder breadth (bought-from-zero minus sold-to-zero,
normalised by matched series) makes the candidate ineligible.  Flat, positive,
or missing coverage fails open.  Existing positions, add-ons, exits, sizing,
ranking, costs, and live/default orders remain unchanged.

The three canonical windows decide Gate 4 against exp-20260715-010.  The
previously frozen 2026-04-22..2026-07-16 warehouse is a separate recent
holdout, as required by the exp-20260715-009 reopen contract.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
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
import exp_20260715_009_sec_nport_entry_notional_scalar as prior_nport  # noqa: E402
import exp_20260717_006_clean_spy_leader_family_removal_holdout_confirmation as holdout_common  # noqa: E402
import exp_20260717_007_nvd_cve_cluster_entry_gate as gate_common  # noqa: E402
import sec_nport_ownership_breadth_gate as breadth_gate  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260719-005"
PROTOCOL_ID = "sec_nport_holder_breadth_negative_fresh_entry_eligibility_v1"
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
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BACKTEST_DIR = EXP_DIR / "backtests_finalized"
RESUME_BACKTEST_DIRS = (
    BACKTEST_DIR,
)
BEFORE_FILE = EXP_DIR / "before_measurement.json"
AFTER_FILE = EXP_DIR / "after_measurement.json"
ARTIFACT = EXP_DIR / "exp_20260719_005_sec_nport_ownership_breadth_gate.json"

HOLDOUT_SPEC = {
    "label": "holdout_recent",
    "start": holdout_common.HOLDOUT_START,
    "end": holdout_common.HOLDOUT_END,
    "snapshot": None,
    "warehouse": holdout_common.HOLDOUT_DB,
}
ACTIVE_EV = 6.2057
REQUIRED_EV = 6.82627
ACTIVE_PNL = 130_992.36
MIN_MATCHED_SERIES = 20
MIN_SURVIVAL_RATE = 0.05
MIN_FRESH_ENTRY_EXCLUSIONS = 5
MIN_CANONICAL_TRADES = 40

HYPOTHESIS = (
    "SEC N-PORT filing-date PIT independent ownership breadth should identify "
    "weakening institutional sponsorship: with at least 20 matched fund "
    "series, negative net new-holder breadth excludes only a next-open fresh "
    "core candidate and improves the cash-feasible strategy across all three "
    "canonical windows while confirming direction on the frozen recent holdout."
)


def _path_text(path: Path) -> str:
    try:
        return gate1._repo_rel(path)
    except ValueError:
        return str(path.resolve())


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Unexpected frozen Gate-1 input schema")
    if payload.get("behavior_sha256") != gate1._stable_hash(
        payload.get("behavior")
    ):
        raise RuntimeError("Frozen Gate-1 behavior-input hash mismatch")
    return payload


def _canonical_specs() -> list[dict[str, Any]]:
    return [
        {**spec, "warehouse": gate1.WAREHOUSE}
        for spec in gate1.WINDOWS
    ]


def _all_specs() -> list[dict[str, Any]]:
    return [*_canonical_specs(), dict(HOLDOUT_SPEC)]


def _holdout_sessions() -> list[str]:
    conn = sqlite3.connect(
        f"file:{holdout_common.HOLDOUT_DB.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        rows = conn.execute(
            "SELECT date FROM ohlcv WHERE ticker = 'SPY' "
            "AND date >= ? AND date <= ? ORDER BY date",
            (HOLDOUT_SPEC["start"], HOLDOUT_SPEC["end"]),
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


def _all_sessions() -> list[str]:
    sessions = {
        day_text
        for spec in gate1.WINDOWS
        for day_text in gate1._spy_dates(spec)
    }
    sessions.update(_holdout_sessions())
    latest = date.fromisoformat(HOLDOUT_SPEC["end"])
    sessions.update(
        candidate.isoformat()
        for offset in range(1, 16)
        if is_us_equity_session(candidate := latest + timedelta(days=offset))
    )
    return sorted(sessions)


def _source_identity(dataset: Any) -> dict[str, Any]:
    compact = prior_nport._compact_identity()
    return {
        "source": "SEC Form N-PORT public as-filed compact archive",
        "prior_experiment": "exp-20260715-009",
        "compact_identity": compact,
        "holding_count": dataset.holding_count,
        "report_count": dataset.report_count,
        "source_manifest": _path_text(prior_nport.EXP_DIR / "nport_source_manifest.json"),
        "source_manifest_sha256": gate1._file_sha256(
            prior_nport.EXP_DIR / "nport_source_manifest.json"
        ),
        "pit_clock": "filing_date_strictly_before_next_open_action_date",
        "raw_price_dependency": False,
        "license": "official SEC public filing archive; local replay only",
    }


def _build_resolver(
    frozen: Mapping[str, Any],
) -> tuple[Any, Any, list[str], dict[str, Any]]:
    dataset = prior_nport._load_dataset()
    sessions = _all_sessions()
    source_identity = _source_identity(dataset)
    resolver = breadth_gate.NPortOwnershipBreadthEntryResolver(
        base_tickers=frozen["behavior"]["universe"],
        dataset=dataset,
        trading_sessions=sessions,
        source_identity=source_identity,
    )
    return resolver, dataset, sessions, source_identity


def _sanitise_nonfinite(
    value: Any,
    *,
    path: str = "",
    found: list[str] | None = None,
) -> tuple[Any, list[str]]:
    """Make identity hashing JSON-safe without changing measured results."""
    paths = found if found is not None else []
    if isinstance(value, float) and not math.isfinite(value):
        paths.append(path or "<root>")
        return None, paths
    if isinstance(value, Mapping):
        output = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            output[key], paths = _sanitise_nonfinite(
                child, path=child_path, found=paths
            )
        return output, paths
    if isinstance(value, list):
        output = []
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            clean, paths = _sanitise_nonfinite(
                child, path=child_path, found=paths
            )
            output.append(clean)
        return output, paths
    if isinstance(value, tuple):
        clean, paths = _sanitise_nonfinite(
            list(value), path=path, found=paths
        )
        return tuple(clean), paths
    return value, paths


def _safe_result_identity(result: Mapping[str, Any]) -> dict[str, Any]:
    clean, nonfinite_paths = _sanitise_nonfinite(dict(result))
    identity = gate1._result_identity(clean)
    critical = {
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "total_trades",
    }
    critical_paths = sorted(
        path
        for path in nonfinite_paths
        if path.split(".", 1)[0].split("[", 1)[0] in critical
    )
    identity.update(
        {
            "nonfinite_paths_normalised_for_identity_only": sorted(
                nonfinite_paths
            ),
            "critical_nonfinite_paths": critical_paths,
            "critical_metrics_finite": not critical_paths,
        }
    )
    return identity


def _run_window(
    spec: Mapping[str, Any],
    frozen: Mapping[str, Any],
    *,
    resolver: Any | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    config = dict(gate1.RUN_CONFIG)
    config["CASH_LEDGER_ENFORCED"] = True
    universe_metadata = {
        "measurement_protocol": PROTOCOL_ID,
        "source_role": "SEC N-PORT filing-date PIT holder breadth",
        "security_master_survivorship_status": (
            "current frozen roster; this experiment does not repair delistings"
        ),
    }
    if resolver is not None:
        universe_metadata.update(dict(resolver.metadata))
    engine = BacktestEngine(
        list(behavior["universe"]),
        start=str(spec["start"]),
        end=str(spec["end"]),
        config=config,
        ohlcv_warehouse_path=str(spec["warehouse"]),
        ohlcv_warehouse_snapshot_source=spec.get("snapshot"),
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
    effective = _effective_earnings_identity_for_spec(
        engine, spec, behavior["universe"], calendar
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    identity = _safe_result_identity(result)
    identity.update(
        {
            "effective_earnings_inputs_sha256": effective["sha256"],
            "effective_earnings_row_count": effective["row_count"],
            "resolved_config_sha256": gate1._stable_hash(engine.config),
            "universe_membership_sha256": gate1._stable_hash(
                result.get("universe_membership") or {}
            ),
            "window": {
                key: spec.get(key)
                for key in ("label", "start", "end", "snapshot")
            },
        }
    )
    return result, identity


def _persist_result(
    arm: str,
    spec: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, str]:
    path = BACKTEST_DIR / f"{spec['label']}_{arm}_{EXPERIMENT_ID}.json"
    persistable = _persistable_backtest_result(dict(result))
    clean, nonfinite_paths = _sanitise_nonfinite(persistable)
    if nonfinite_paths:
        clean["_nonfinite_fields_normalised_to_null"] = sorted(nonfinite_paths)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if gate1._stable_hash(existing) != gate1._stable_hash(clean):
            raise RuntimeError(
                f"Refusing to replace non-identical finalized arm: {path}"
            )
        return {"path": _path_text(path), "sha256": gate1._file_sha256(path)}
    gate1._atomic_write_json(path, clean)
    return {"path": _path_text(path), "sha256": gate1._file_sha256(path)}


def _load_hash_verified_partial_arm(
    arm: str,
    spec: Mapping[str, Any],
    *,
    resolver: Any | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Reuse a completed finalized arm only after validating its identity."""
    name = f"{spec['label']}_{arm}_{EXPERIMENT_ID}.json"
    path = next(
        (directory / name for directory in RESUME_BACKTEST_DIRS if (directory / name).is_file()),
        None,
    )
    if path is None:
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    expected_period = f"{spec['start']} → {spec['end']}"
    if result.get("error") or result.get("period") != expected_period:
        return None
    audit = result.get("universe_membership") or {}
    if resolver is None:
        if audit.get("mode") not in {None, "static_pool_hypothesis"}:
            return None
    else:
        expected_source_hash = resolver.metadata.get("source_hash")
        daily = audit.get("daily") or []
        if audit.get("mode") != "pit_walk_forward" or not daily:
            return None
        if any(row.get("source_hash") != expected_source_hash for row in daily):
            return None
    identity = _safe_result_identity(result)
    identity["reused_hash_verified_partial_arm"] = _path_text(path)
    return result, identity


def _effective_earnings_identity_for_spec(
    engine: Any,
    spec: Mapping[str, Any],
    universe: Sequence[str],
    calendar: Mapping[str, Sequence[date]],
) -> dict[str, Any]:
    if spec.get("snapshot") is not None:
        return gate1._effective_earnings_identity(
            engine, dict(spec), list(universe), dict(calendar)
        )
    rows = []
    for day_text in _holdout_sessions():
        today = datetime.fromisoformat(day_text)
        for ticker in universe:
            rows.append(
                [
                    day_text,
                    ticker,
                    engine._earnings_dict_for(
                        today, list(calendar.get(ticker, [])), ticker
                    ),
                ]
            )
    payload = {
        "schema": "effective_earnings_inputs_v1",
        "window": spec["label"],
        "rows": rows,
    }
    return {"sha256": gate1._stable_hash(payload), "row_count": len(rows)}


def _canonical_gate4(
    windows: Mapping[str, Mapping[str, Any]],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    per_window: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        base = windows[label]["before"]
        candidate = windows[label]["after"]
        trade_floor = max(10, math.floor(0.80 * int(base["trade_count"])))
        row = {
            "ev_non_degrading": candidate["expected_value_score"]
            >= base["expected_value_score"],
            "pnl_non_degrading": candidate["total_pnl"] >= base["total_pnl"],
            "trade_floor": trade_floor,
            "trade_sample_sufficient": candidate["trade_count"] >= trade_floor,
            "survival_gate": candidate["survival_rate"] >= MIN_SURVIVAL_RATE,
        }
        row["all_pass"] = all(
            value for key, value in row.items() if key != "trade_floor"
        )
        per_window[label] = row
    checks = {
        "aggregate_ev_strictly_above_10pct_hurdle": after[
            "expected_value_score_sum"
        ]
        > REQUIRED_EV,
        "aggregate_pnl_strictly_above_anchor": after["total_pnl_sum"]
        > ACTIVE_PNL,
        "aggregate_drawdown_within_one_point": after["worst_max_drawdown_pct"]
        <= before["worst_max_drawdown_pct"] + 0.01,
        "aggregate_trade_sample_sufficient": after["trade_count_sum"]
        >= MIN_CANONICAL_TRADES,
        "aggregate_survival_gate": after["minimum_survival_rate"]
        >= MIN_SURVIVAL_RATE,
        "all_windows_ev_pnl_non_degrading": all(
            row["all_pass"] for row in per_window.values()
        ),
    }
    checks["all_pass"] = all(checks.values())
    return {
        "fixed_hurdle": {
            "active_ev": ACTIVE_EV,
            "required_ev": ">6.82627",
            "active_pnl": ACTIVE_PNL,
            "canonical_trade_floor": MIN_CANONICAL_TRADES,
        },
        "per_window": per_window,
        "checks": checks,
    }


def _holdout_gate(window: Mapping[str, Any]) -> dict[str, Any]:
    before = window["before"]
    after = window["after"]
    checks = {
        "ev_strictly_improves": after["expected_value_score"]
        > before["expected_value_score"],
        "pnl_strictly_improves": after["total_pnl"] > before["total_pnl"],
        "drawdown_within_one_point": after["max_drawdown_pct"]
        <= before["max_drawdown_pct"] + 0.01,
        "survival_gate": after["survival_rate"] >= MIN_SURVIVAL_RATE,
    }
    checks["all_pass"] = all(checks.values())
    return {"checks": checks, "role": "separate_recent_observe_confirmation"}


def _measurement_projection(
    aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    total_pnl = float(aggregate["total_pnl_sum"])
    return {
        "benchmarks": {
            "strategy_total_return_pct": round(total_pnl / 100_000.0, 4)
        },
        "expected_value_score": float(aggregate["expected_value_score_sum"]),
        "expected_value_score_formula": (
            "per-window sum of strategy_total_return_pct * abs(sharpe_daily)"
        ),
        "total_pnl": total_pnl,
        "max_drawdown_pct": float(aggregate["worst_max_drawdown_pct"]),
        "total_trades": int(aggregate["trade_count_sum"]),
        "survival_rate": float(aggregate["minimum_survival_rate"]),
    }


def _candidate_overlap(
    result: Mapping[str, Any],
    resolver: Any,
) -> dict[str, Any]:
    """Attribute the fixed gate against the persisted fresh-entry queue.

    The current backtester persists the candidate loop under
    ``entry_candidate_events``; ``universe_membership.generated_signals`` is
    intentionally empty for these cash-feasible static replays.  Deduplicate
    by ticker and signal date so multiple candidate-loop diagnostics cannot
    inflate the predeclared touch floor.
    """

    hits: dict[tuple[str, str], dict[str, Any]] = {}
    entered_hits: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in list(result.get("entry_candidate_events") or []):
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
        if resolution.get("status") != "resolved" or ticker in eligible:
            continue
        provenance = resolution.get("provenance") or {}
        row = {
            "ticker": ticker,
            "signal_date": signal_day,
            "entry_date": provenance.get("entry_session"),
            "strategy": raw.get("strategy"),
            "sector": raw.get("sector"),
            "before_decision": raw.get("decision"),
            "candidate_rank": raw.get("candidate_rank"),
        }
        key = (ticker, signal_day)
        hits[key] = row
        if raw.get("decision") == "entered":
            entered_hits[key] = row

    generated = sorted(
        hits.values(), key=lambda row: (row["signal_date"], row["ticker"])
    )
    entered = sorted(
        entered_hits.values(),
        key=lambda row: (row["signal_date"], row["ticker"]),
    )
    return {
        "generated_fresh_candidate_exclusions": len(generated),
        "survived_fresh_candidate_exclusions": len(entered),
        "generated_rows": generated,
        "survived_rows": entered,
        "persisted_surface": "entry_candidate_events",
    }


def _daily_parity(
    *,
    resolver: Any,
    dataset: Any,
    sessions: Sequence[str],
    source_identity: Mapping[str, Any],
    base_tickers: Sequence[str],
    candidate_touch: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    signal_days = sorted(
        {
            str(row["signal_date"])
            for record in candidate_touch.values()
            for row in record.get("generated_rows") or []
        }
    )
    checks: list[dict[str, Any]] = []
    base = {str(value).upper() for value in base_tickers}
    for signal_day in signal_days:
        resolution = resolver.resolve(signal_day)
        eligible = {
            str(value).upper() for value in resolution.get("tickers") or []
        }
        expected_excluded = sorted(base - eligible)
        snapshot = breadth_gate.build_daily_ownership_breadth_snapshot(
            dataset,
            as_of=signal_day,
            trading_sessions=sessions,
            candidate_tickers=base_tickers,
            base_tickers=base_tickers,
            source_identity=source_identity,
        )
        actual_excluded = sorted(
            str(value).upper()
            for value in snapshot.get("excluded_tickers_for_next_session") or []
        )
        provenance = resolution.get("provenance") or {}
        parity = {
            "excluded_tickers": expected_excluded == actual_excluded,
            "entry_session": provenance.get("entry_session")
            == snapshot.get("next_trading_session"),
            "source_hash": resolution.get("source_hash")
            == snapshot.get("source_hash"),
            "membership_hash": resolution.get("membership_hash")
            == snapshot.get("membership_hash"),
            "trade_enabled_false": snapshot.get("trade_enabled") is False,
        }
        checks.append(
            {
                "signal_date": signal_day,
                "expected_excluded": expected_excluded,
                "actual_excluded": actual_excluded,
                "checks": parity,
                "all_pass": all(parity.values()),
            }
        )
    return {
        "checked_signal_dates": len(checks),
        "all_pass": bool(checks) and all(row["all_pass"] for row in checks),
        "checks": checks,
    }


def build_artifact() -> dict[str, Any]:
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    active_aggregate = active.get("aggregate") or {}
    if active_aggregate.get("expected_value_score_sum") != ACTIVE_EV:
        raise RuntimeError("Active Gate-1 EV no longer matches the frozen hurdle")
    if active_aggregate.get("total_pnl_sum") != ACTIVE_PNL:
        raise RuntimeError("Active Gate-1 PnL no longer matches the frozen hurdle")

    holdout_manifest = json.loads(
        holdout_common.HOLDOUT_MANIFEST.read_text(encoding="utf-8")
    )
    if holdout_common._holdout_rowset_sha256(holdout_common.HOLDOUT_DB) != (
        holdout_manifest.get("rowset_sha256")
    ):
        raise RuntimeError("Frozen recent holdout rowset hash mismatch")

    resolver, dataset, sessions, source_identity = _build_resolver(frozen)
    specs = _all_specs()
    before_records: dict[str, dict[str, Any]] = {}
    after_records: dict[str, dict[str, Any]] = {}
    for spec in specs:
        label = str(spec["label"])
        cached_before = _load_hash_verified_partial_arm(
            "before", spec, resolver=None
        )
        if cached_before is None:
            print(f"[{label}] before: cash-feasible static anchor ...", flush=True)
            before_result, before_identity = _run_window(
                spec, frozen, resolver=None
            )
        else:
            print(f"[{label}] before: reuse hash-verified finalized arm", flush=True)
            before_result, before_identity = cached_before
        before_records[label] = {
            "result": before_result,
            "identity": before_identity,
            "artifact": _persist_result("before", spec, before_result),
        }
        cached_after = _load_hash_verified_partial_arm(
            "after", spec, resolver=resolver
        )
        if cached_after is None:
            print(f"[{label}] after: N-PORT negative holder-breadth eligibility ...", flush=True)
            after_result, after_identity = _run_window(
                spec, frozen, resolver=resolver
            )
        else:
            print(f"[{label}] after: reuse hash-verified finalized arm", flush=True)
            after_result, after_identity = cached_after
        if after_identity["nonfinite_paths_normalised_for_identity_only"]:
            print(
                f"[{label}] non-finite diagnostic paths normalised for JSON: "
                f"{after_identity['nonfinite_paths_normalised_for_identity_only']}",
                flush=True,
            )
        after_records[label] = {
            "result": after_result,
            "identity": after_identity,
            "artifact": _persist_result("after", spec, after_result),
        }

    canonical_before = {
        spec["label"]: before_records[spec["label"]]
        for spec in gate1.WINDOWS
    }
    gate1_checks = gate_common._static_reference_checks(canonical_before, active)
    windows: dict[str, Any] = {}
    gate2: dict[str, Any] = {}
    gate3: dict[str, Any] = {}
    addon_audit: dict[str, Any] = {}
    candidate_touch: dict[str, Any] = {}
    for spec in specs:
        label = str(spec["label"])
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
            "window": {
                key: spec.get(key)
                for key in ("label", "start", "end", "snapshot")
            },
            "before": before_headline,
            "after": after_headline,
            "delta": gate_common._delta(after_headline, before_headline),
            "before_identity": before_records[label]["identity"],
            "after_identity": after_records[label]["identity"],
            "before_artifact": before_records[label]["artifact"],
            "after_artifact": after_records[label]["artifact"],
        }

    gate2["all_windows_pass"] = all(
        gate2[str(spec["label"])]["all_pass"] for spec in specs
    )
    gate3["all_windows_pass"] = all(
        gate3[str(spec["label"])]["passed"] for spec in specs
    )
    addon_audit["all_windows_clean"] = all(
        addon_audit[str(spec["label"])]["clean"] for spec in specs
    )

    canonical_labels = [spec["label"] for spec in gate1.WINDOWS]
    total_touches = sum(
        candidate_touch[label]["generated_fresh_candidate_exclusions"]
        for label in canonical_labels
    )
    touch_gate = {
        "minimum_aggregate": MIN_FRESH_ENTRY_EXCLUSIONS,
        "aggregate_generated_fresh_candidate_exclusions": total_touches,
        "at_least_five": total_touches >= MIN_FRESH_ENTRY_EXCLUSIONS,
        "at_least_one_each_window": all(
            candidate_touch[label]["generated_fresh_candidate_exclusions"] >= 1
            for label in canonical_labels
        ),
        "holdout_generated_fresh_candidate_exclusions": candidate_touch[
            HOLDOUT_SPEC["label"]
        ]["generated_fresh_candidate_exclusions"],
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
    canonical_gate4 = _canonical_gate4(
        windows, before_aggregate, after_aggregate
    )
    holdout_gate = _holdout_gate(windows[HOLDOUT_SPEC["label"]])
    daily_parity = _daily_parity(
        resolver=resolver,
        dataset=dataset,
        sessions=sessions,
        source_identity=source_identity,
        base_tickers=frozen["behavior"]["universe"],
        candidate_touch=candidate_touch,
    )

    shared_contract = {
        "shared_helper_imported": True,
        "resolver_type": type(resolver).__name__,
        "daily_default_off_snapshot_callable": callable(
            getattr(breadth_gate, "build_daily_ownership_breadth_snapshot", None)
        ),
        "historical_daily_pit_parity": daily_parity,
        "historical_daily_pit_parity_complete": daily_parity["all_pass"],
        "run_adapter_wired": False,
        "run_adapter_evaluated_then_rolled_back": (
            "_persist_sec_nport_ownership_breadth_observer"
        ),
        "daily_adapter_retained_after_rejection": False,
        "trade_enabled": False,
        "live_order_path_enabled": False,
    }
    critical_metric_identity = {
        label: {
            "before": before_records[label]["identity"][
                "critical_metrics_finite"
            ],
            "after": after_records[label]["identity"][
                "critical_metrics_finite"
            ],
            "before_nonfinite_paths": before_records[label]["identity"][
                "nonfinite_paths_normalised_for_identity_only"
            ],
            "after_nonfinite_paths": after_records[label]["identity"][
                "nonfinite_paths_normalised_for_identity_only"
            ],
        }
        for label in windows
    }
    critical_metric_identity["all_critical_metrics_finite"] = all(
        row[arm]
        for label, row in critical_metric_identity.items()
        if label != "all_critical_metrics_finite"
        for arm in ("before", "after")
    )
    source_and_policy_valid = all(
        (
            dataset.holding_count > 0,
            dataset.report_count > 0,
            resolver.metadata.get("policy", {}).get("min_matched_series")
            == MIN_MATCHED_SERIES,
            source_identity["pit_clock"]
            == "filing_date_strictly_before_next_open_action_date",
        )
    )
    measurement_valid = all(
        (
            gate1_checks["all_windows_exact"],
            gate2["all_windows_pass"],
            gate3["all_windows_pass"],
            critical_metric_identity["all_critical_metrics_finite"],
            source_and_policy_valid,
        )
    )
    strict_full_stack_passed = all(
        (
            measurement_valid,
            touch_gate["all_pass"],
            canonical_gate4["checks"]["all_pass"],
            holdout_gate["checks"]["all_pass"],
            addon_audit["all_windows_clean"],
            daily_parity["all_pass"],
            not shared_contract["trade_enabled"],
        )
    )
    if not measurement_valid:
        decision = "blocked_invalid_measurement"
    elif not daily_parity["all_pass"]:
        decision = "blocked_incomplete_full_stack"
    elif not touch_gate["all_pass"]:
        decision = "rejected_insufficient_fresh_entry_overlap"
    elif not addon_audit["all_windows_clean"]:
        decision = "rejected_attribution_contamination"
    elif not canonical_gate4["checks"]["all_pass"]:
        decision = "rejected"
    elif not holdout_gate["checks"]["all_pass"]:
        decision = "rejected_holdout_failed"
    elif strict_full_stack_passed:
        decision = "accepted_default_off"
    else:
        decision = "blocked_incomplete_full_stack"

    artifact = {
        "schema": "sec_nport_ownership_breadth_gate_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "accepted_alpha": decision == "accepted_default_off",
        "live_ready": False,
        "hypothesis": HYPOTHESIS,
        "single_causal_variable": (
            "negative N-PORT net new-holder breadth controls next-open fresh-core "
            "candidate eligibility; missing/flat/positive fails open"
        ),
        "fingerprint_caveat": (
            "Literal entry_admission text is over-matched to core_entry_admission "
            "before N-PORT in the current classifier. True-surface novelty was "
            "checked as sec_form_nport_public_holdings with a new eligibility gate; "
            "nearest exp-20260715-009 score was 0.4695."
        ),
        "measurement_retry_history": {
            "hash_verified_replay_directories": [
                _path_text(path) for path in RESUME_BACKTEST_DIRS
            ],
            "final_directory": _path_text(BACKTEST_DIR),
            "attempt_1": (
                "identity hashing rejected a non-finite diagnostic value"
            ),
            "attempt_2": (
                "strict JSON persistence rejected the same non-finite diagnostic"
            ),
            "attempt_3": (
                "Windows denied atomic replacement of an existing partial file; "
                "partial artifacts were preserved and final output moved to a new directory"
            ),
            "attempt_4": (
                "canonical windows completed; the snapshot-only earnings identity "
                "helper rejected the SQLite holdout before its replay began"
            ),
            "closeout_projection": (
                "completed arms were hash-verified and projected into the standard "
                "experiment.py close metric schema without recomputation"
            ),
            "resume_validation": (
                "period, universe mode, and every daily resolver source hash"
            ),
            "strategy_policy_changed_between_attempts": False,
        },
        "source_contract": source_identity,
        "locked_policy": resolver.metadata.get("policy"),
        "resolver_metadata": dict(resolver.metadata),
        "frozen_behavior_inputs": {
            "path": _path_text(FROZEN_INPUTS),
            "sha256": gate1._file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
        },
        "active_baseline": {
            "path": _path_text(ACTIVE_BASELINE),
            "sha256": gate1._file_sha256(ACTIVE_BASELINE),
            "aggregate": active_aggregate,
        },
        "holdout_contract": {
            "role": "separate_recent_observe_confirmation",
            "warehouse": _path_text(holdout_common.HOLDOUT_DB),
            "manifest": _path_text(holdout_common.HOLDOUT_MANIFEST),
            "manifest_sha256": gate1._file_sha256(
                holdout_common.HOLDOUT_MANIFEST
            ),
            "rowset_sha256": holdout_manifest["rowset_sha256"],
            "window": {
                "start": HOLDOUT_SPEC["start"],
                "end": HOLDOUT_SPEC["end"],
            },
            "canonical_arithmetic_included": False,
        },
        "gates": {
            "gate1_before_exact_reproduction": gate1_checks,
            "gate2_runtime_fields_and_pit_provenance": gate2,
            "gate3_survival": gate3,
            "identity_nonfinite_audit": critical_metric_identity,
            "gate4_canonical_alpha": canonical_gate4,
            "separate_holdout_confirmation": holdout_gate,
            "predeclared_candidate_touch_floor": touch_gate,
        },
        "verdicts": {
            "source_and_policy_valid": source_and_policy_valid,
            "measurement_valid": measurement_valid,
            "candidate_touch_gate_passed": touch_gate["all_pass"],
            "canonical_gate4_passed": canonical_gate4["checks"]["all_pass"],
            "holdout_gate_passed": holdout_gate["checks"]["all_pass"],
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
            "shared_helper_added": True,
            "daily_default_off_observer_added": False,
            "daily_default_off_observer_evaluated_then_rolled_back": True,
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
                "No added notional; an enabled policy could only cancel a fresh "
                "entry and retain cash. The after replay measures downstream cash "
                "and slot displacement."
            ),
            "liquidity_slippage_and_costs": (
                "Unchanged accepted next-open fill, slippage, and round-trip costs."
            ),
            "max_positions_and_exposure": "Existing caps and sector limits unchanged.",
            "order_semantics": (
                "Decision uses filings strictly before the queued next-open action date."
            ),
            "kill_switch": (
                "Missing source, missing next session, fewer than 20 matched series, "
                "or invalid data fails open; observer remains trade_enabled=false."
            ),
            "live_ready": False,
        },
        "known_limitations": [
            "N-PORT ownership is quarterly and may be stale relative to the entry signal.",
            "The frozen current security roster does not repair survivorship.",
            "The compact archive is inherited from exp-20260715-009 and is not a live refresh service.",
            "The same resolver can affect add-on eligibility; any observed contamination rejects the experiment.",
            "Late-window candidate touches may be concentrated in repeated tickers.",
        ],
        "nearby_prior": {
            "exp-20260715-009": (
                "Rejected aggregate-share sign 1.10/0.90 notional scalar; this "
                "experiment uses holder-series breadth and no share sums/scalars."
            ),
            "exp-20260715-010": "Active cash-feasible Gate-1 comparator.",
            "exp-20260717-006": "Frozen recent holdout warehouse harness.",
        },
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260719_005_sec_nport_ownership_breadth_gate.py"
            )
        },
    }

    gate1._atomic_write_json(
        BEFORE_FILE,
        {
            "schema": "exp_20260719_005_before_projection_v1",
            "experiment_id": EXPERIMENT_ID,
            "role": "cash_feasible_static_anchor_plus_separate_holdout",
            **_measurement_projection(before_aggregate),
            "active_source": _path_text(ACTIVE_BASELINE),
            "canonical_aggregate": before_aggregate,
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
            "schema": "exp_20260719_005_after_projection_v1",
            "experiment_id": EXPERIMENT_ID,
            "role": "fixed_sec_nport_holder_breadth_fresh_entry_eligibility",
            "decision": decision,
            "accepted_alpha": decision == "accepted_default_off",
            **_measurement_projection(after_aggregate),
            "canonical_aggregate": after_aggregate,
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
                "holdout": artifact["gates"]["separate_holdout_confirmation"],
                "artifact": _path_text(ARTIFACT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
