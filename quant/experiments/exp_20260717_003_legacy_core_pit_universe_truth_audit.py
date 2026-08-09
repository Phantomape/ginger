"""Audit legacy-core universe look-ahead without claiming historical PIT truth.

The repository only proves two historical entry-membership states: the
13-name watchlist in the first commit and the 43-name base watchlist introduced
on 2026-04-04 (effective next session, 2026-04-06).  Dates before the first
snapshot fail closed and are labelled unidentifiable.  The same runner also
starts the prospective full-membership ledger for the broad paper feed.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtester import BacktestEngine, _persistable_backtest_result  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    DEFAULT_SNAPSHOT_LOG_PATH,
    DEFAULT_STATE_PATH,
)
from broad_market_universe_feed import (  # noqa: E402
    DEFAULT_CLEAN_CUTOFF,
    DEFAULT_MEMBERSHIP_LEDGER_PATH,
    generate_broad_market_paper_universe,
)
from entry_universe_ledger import (  # noqa: E402
    EntryUniverseResolver,
    append_membership_snapshot,
    build_membership_snapshot,
    load_membership_snapshots,
)

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402


EXPERIMENT_ID = "exp-20260717-003"
PROTOCOL_ID = "legacy_core_git_membership_lower_bound_v1"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
FROZEN_INPUTS = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-015"
    / "frozen_behavior_inputs.json"
)
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
HISTORICAL_MEMBERSHIP_LEDGER = EXP_DIR / "git_proven_core_membership.jsonl"
BEFORE_MEASUREMENT = EXP_DIR / "before_measurement.json"
AFTER_MEASUREMENT = EXP_DIR / "after_measurement.json"
SUMMARY = EXP_DIR / "exp_20260717_003_legacy_core_pit_universe_truth_audit.json"

FIRST_COMMIT = "8b0aee2d8454ac18a6df1d99ed5bc12893969771"
QUANT_PIPELINE_COMMIT = "eeec55266089e2c57df71030d84be12d87ebf97a"
EXPANSION_COMMIT = "0bb52d403d5fa771fbec7dc73d2cb5333d9457fa"
FIRST_EFFECTIVE_DATE = "2026-01-23"
QUANT_PIPELINE_EFFECTIVE_DATE = "2026-03-16"
EXPANSION_EFFECTIVE_DATE = "2026-04-06"
MANIFEST_GENERATED_AT = "2026-07-17T05:31:51Z"

FIRST_TICKERS = (
    "NVDA", "META", "AMD", "QQQ", "TSLA", "MCD", "CRDO", "IAU",
    "NFLX", "APP", "GOOG", "COIN", "MU",
)
EXPANDED_TICKERS = (
    "NVDA", "META", "AMD", "CRDO", "APP", "GOOG", "MU",
    "MSFT", "AAPL", "AVGO", "TSM", "PLTR", "DDOG", "NOW", "SNOW",
    "TSLA", "MCD", "AMZN", "BKNG", "NFLX", "DIS", "SPOT",
    "COIN", "V", "MA", "GS", "JPM", "LLY", "NVO", "UNH", "ISRG",
    "XOM", "CVX", "CAT", "DE", "GE", "RTX", "IAU", "GLD", "SLV",
    "QQQ", "SPY", "IWM",
)

IDENTIFIABLE_SLICE = {
    "label": "watchlist_proxy_slice",
    "start": FIRST_EFFECTIVE_DATE,
    "end": "2026-04-21",
    "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
}

QUANT_PIPELINE_SLICE = {
    "label": "quant_pipeline_era_slice",
    "start": QUANT_PIPELINE_EFFECTIVE_DATE,
    "end": "2026-04-21",
    "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
}

HEADLINE_FIELDS = (
    "expected_value_score",
    "total_pnl",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "total_trades",
    "signals_generated",
    "signals_survived",
    "survival_rate",
)


def _git_show(commit: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return completed.stdout


def _literal_assignment(source: str, variable: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise RuntimeError(f"{variable} is not a literal list[str]")
        return [item.upper() for item in value]
    raise RuntimeError(f"Could not find literal assignment {variable}")


def _verify_git_membership_sources() -> dict[str, Any]:
    first = _literal_assignment(
        _git_show(FIRST_COMMIT, "news_collector/filter.py"), "WATCHLIST"
    )
    expanded = _literal_assignment(
        _git_show(EXPANSION_COMMIT, "quant/filter.py"), "_BASE_WATCHLIST"
    )
    quant_filter_source = _git_show(QUANT_PIPELINE_COMMIT, "quant/filter.py")
    quant_data_layer_source = _git_show(
        QUANT_PIPELINE_COMMIT, "quant/data_layer.py"
    )
    quant_run_source = _git_show(QUANT_PIPELINE_COMMIT, "quant/run.py")
    quant_tickers = _literal_assignment(quant_filter_source, "WATCHLIST")
    checks = {
        "first_commit_exact": set(first) == set(FIRST_TICKERS),
        "first_commit_count_13": len(set(first)) == 13,
        "first_quant_pipeline_membership_exact": set(quant_tickers)
        == set(FIRST_TICKERS),
        "first_quant_pipeline_imports_watchlist": (
            "from filter import WATCHLIST" in quant_data_layer_source
        ),
        "first_quant_pipeline_calls_get_universe": (
            "universe        = get_universe()" in quant_run_source
        ),
        "expansion_commit_exact": set(expanded) == set(EXPANDED_TICKERS),
        "expansion_commit_count_43": len(set(expanded)) == 43,
        "first_is_subset_of_expansion": set(first).issubset(expanded),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Git membership source validation failed: {checks}")
    return {
        "checks": checks,
        "snapshots": [
            {
                "effective_as_of": FIRST_EFFECTIVE_DATE,
                "source_commit": FIRST_COMMIT,
                "source_path": "news_collector/filter.py",
                "source_symbol": "WATCHLIST",
                "ticker_count": len(first),
                "tickers": sorted(first),
            },
            {
                "effective_as_of": QUANT_PIPELINE_EFFECTIVE_DATE,
                "source_commit": QUANT_PIPELINE_COMMIT,
                "source_path": "quant/data_layer.py + quant/filter.py + quant/run.py",
                "source_symbol": "get_universe -> WATCHLIST",
                "ticker_count": len(quant_tickers),
                "tickers": sorted(quant_tickers),
                "role": "first_proven_quant_pipeline_entry_universe",
            },
            {
                "effective_as_of": EXPANSION_EFFECTIVE_DATE,
                "source_commit": EXPANSION_COMMIT,
                "source_path": "quant/filter.py",
                "source_symbol": "_BASE_WATCHLIST",
                "ticker_count": len(expanded),
                "tickers": sorted(expanded),
            },
        ],
    }


def _build_historical_membership_resolver() -> tuple[EntryUniverseResolver, dict[str, Any]]:
    source_audit = _verify_git_membership_sources()
    specs = (
        (
            FIRST_EFFECTIVE_DATE,
            FIRST_TICKERS,
            FIRST_COMMIT,
            "news_collector/filter.py",
            "WATCHLIST",
            "2026-01-23T00:10:34-08:00",
        ),
        (
            QUANT_PIPELINE_EFFECTIVE_DATE,
            FIRST_TICKERS,
            QUANT_PIPELINE_COMMIT,
            "quant/data_layer.py+quant/filter.py+quant/run.py",
            "get_universe->WATCHLIST",
            "2026-03-13T20:47:43-07:00",
        ),
        (
            EXPANSION_EFFECTIVE_DATE,
            EXPANDED_TICKERS,
            EXPANSION_COMMIT,
            "quant/filter.py",
            "_BASE_WATCHLIST",
            "2026-04-04T23:28:05-07:00",
        ),
    )
    append_results = []
    for effective, tickers, commit, path, symbol, commit_time in specs:
        snapshot = build_membership_snapshot(
            effective_as_of=effective,
            tickers=tickers,
            source=f"git:{path}:{symbol}",
            source_hash=commit,
            generated_at=MANIFEST_GENERATED_AT,
            provenance={
                "experiment_id": EXPERIMENT_ID,
                "source_commit": commit,
                "source_commit_time": commit_time,
                "source_path": path,
                "source_symbol": symbol,
                "rule_version": PROTOCOL_ID,
                "interpretation": "entry_eligible_from_effective_date",
            },
        )
        append_results.append(
            append_membership_snapshot(HISTORICAL_MEMBERSHIP_LEDGER, snapshot)
        )

    resolver = EntryUniverseResolver.from_path(HISTORICAL_MEMBERSHIP_LEDGER)
    source_audit["ledger"] = {
        "path": gate1._repo_rel(HISTORICAL_MEMBERSHIP_LEDGER),
        "append_results": append_results,
        "metadata": resolver.metadata,
    }
    return resolver, source_audit


def _load_frozen() -> dict[str, Any]:
    frozen = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if frozen.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Unexpected frozen behavior schema")
    if frozen.get("behavior_sha256") != gate1._stable_hash(frozen.get("behavior")):
        raise RuntimeError("Frozen behavior hash mismatch")
    return frozen


def _json_safe_nonfinite(value: Any, *, path: str = "$") -> tuple[Any, list[str]]:
    """Represent diagnostic NaN/Infinity explicitly in strict JSON artifacts.

    Small, one-sided cohorts can legitimately produce an infinite descriptive
    profit factor.  That must not make the audit unpersistable or silently
    turn into non-standard JSON.
    """

    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN", [path]
        return ("Infinity" if value > 0 else "-Infinity"), [path]
    if isinstance(value, dict):
        out = {}
        paths: list[str] = []
        for key, item in value.items():
            safe, found = _json_safe_nonfinite(item, path=f"{path}.{key}")
            out[key] = safe
            paths.extend(found)
        return out, paths
    if isinstance(value, list):
        out = []
        paths: list[str] = []
        for index, item in enumerate(value):
            safe, found = _json_safe_nonfinite(item, path=f"{path}[{index}]")
            out.append(safe)
            paths.extend(found)
        return out, paths
    if isinstance(value, tuple):
        return _json_safe_nonfinite(list(value), path=path)
    return value, []


def _without_runtime_generated_at(value: Any) -> Any:
    """Remove wall-clock-only audit timestamps from a replay identity."""

    if isinstance(value, dict):
        return {
            key: _without_runtime_generated_at(item)
            for key, item in value.items()
            if key != "generated_at"
        }
    if isinstance(value, list):
        return [_without_runtime_generated_at(item) for item in value]
    return value


def _run_window(
    spec: dict[str, str],
    frozen: dict[str, Any],
    *,
    resolver: EntryUniverseResolver | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = gate1._calendar_dates(frozen)
    universe_metadata = {
        "measurement_protocol": PROTOCOL_ID,
        "security_master_survivorship_status": (
            "current_roster_security_master_not_repaired"
        ),
    }
    if resolver is not None:
        universe_metadata.update(resolver.metadata)
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
        universe_mode="pit_walk_forward" if resolver else "static_pool_hypothesis",
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
    result, nonfinite_paths = _json_safe_nonfinite(result)
    identity = gate1._result_identity(result)
    identity.update({
        "effective_earnings_inputs_sha256": effective["sha256"],
        "effective_earnings_row_count": effective["row_count"],
        "resolved_config_sha256": gate1._stable_hash(engine.config),
        "universe_membership_sha256": gate1._stable_hash(
            result.get("universe_membership") or {}
        ),
        "persistable_result_sha256": gate1._stable_hash(
            _persistable_backtest_result(result)
        ),
        "deterministic_persistable_result_sha256": gate1._stable_hash(
            _without_runtime_generated_at(_persistable_backtest_result(result))
        ),
        "window": dict(spec),
        "nonfinite_diagnostic_paths": nonfinite_paths,
    })
    return result, identity


def _run_arm(
    name: str,
    specs: tuple[dict[str, str], ...],
    frozen: dict[str, Any],
    *,
    resolver: EntryUniverseResolver | None,
    passes: int,
) -> list[dict[str, dict[str, Any]]]:
    all_passes = []
    for pass_index in range(1, passes + 1):
        records: dict[str, dict[str, Any]] = {}
        for spec in specs:
            print(
                f"[{name} pass {pass_index}/{passes}] {spec['label']} ...",
                flush=True,
            )
            result, identity = _run_window(spec, frozen, resolver=resolver)
            result_path = (
                EXP_DIR
                / f"replay_{name}_pass{pass_index}_{spec['label']}.json"
            )
            gate1._atomic_write_json(
                result_path, _persistable_backtest_result(result)
            )
            records[spec["label"]] = {
                "result": result,
                "identity": identity,
                "result_path": gate1._repo_rel(result_path),
                "result_file_sha256": gate1._file_sha256(result_path),
            }
        all_passes.append(records)
    return all_passes


def _headline(result: dict[str, Any]) -> dict[str, Any]:
    headline = {key: result.get(key) for key in HEADLINE_FIELDS}
    headline["trade_count"] = headline.pop("total_trades")
    headline["cash_ledger"] = {
        key: (result.get("cash_ledger") or {}).get(key)
        for key in (
            "enforced",
            "min_cash",
            "negative_cash_event_count",
            "cash_conservation_error",
            "cash_conservation_passed",
        )
    }
    return headline


def _static_reference_checks(
    records: dict[str, dict[str, Any]], reference: dict[str, Any]
) -> dict[str, Any]:
    expected = {row["label"]: row for row in reference["windows"]}
    checks: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        result = records[label]["result"]
        identity = records[label]["identity"]
        row = expected[label]
        field_checks = {
            "expected_value_score": result.get("expected_value_score")
            == row.get("expected_value_score"),
            "total_pnl": result.get("total_pnl") == row.get("total_pnl"),
            "trade_count": result.get("total_trades") == row.get("trade_count"),
            "signals_generated": result.get("signals_generated")
            == row.get("signals_generated"),
            "signals_survived": result.get("signals_survived")
            == row.get("signals_survived"),
            "survival_rate": result.get("survival_rate")
            == row.get("survival_rate"),
            "trade_rows_sha256": identity.get("trade_rows_sha256")
            == row.get("trade_rows_sha256"),
            "daily_return_series_sha256": identity.get(
                "daily_return_series_sha256"
            )
            == row.get("daily_return_series_sha256"),
        }
        checks[label] = {**field_checks, "all_pass": all(field_checks.values())}
    checks["all_windows_exact"] = all(
        checks[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    return checks


def _membership_checks(
    result: dict[str, Any], resolver: EntryUniverseResolver
) -> dict[str, Any]:
    audit = result.get("universe_membership") or {}
    generated = audit.get("generated_signals") or []
    survived = audit.get("survived_signals") or []
    entered = audit.get("entered_trades") or []
    trades = result.get("trades") or []
    valid_hashes = {
        row["snapshot_hash"] for row in resolver.metadata["snapshots"]
    }
    trade_pairs = {
        (str(row.get("ticker") or "").upper(), row.get("entry_date"))
        for row in trades
    }
    entered_pairs = {
        (str(row.get("ticker") or "").upper(), row.get("entry_date"))
        for row in entered
    }
    identifiable_days = int(audit.get("identifiable_days") or 0)
    checks = {
        "point_in_time_mode": audit.get("mode") == "pit_walk_forward",
        "data_universe_contains_historical_union": set(resolver.data_tickers).issubset(
            set(audit.get("data_universe") or [])
        ),
        "generated_signal_count_matches": len(generated)
        == int(result.get("signals_generated") or 0),
        "survived_signal_count_matches": len(survived)
        == int(result.get("signals_survived") or 0),
        "generated_signal_provenance_complete": all(
            row.get("snapshot_sha256") in valid_hashes
            and row.get("signal_date") >= FIRST_EFFECTIVE_DATE
            for row in generated
        ),
        "survived_target_price_complete": all(
            isinstance(row.get("target_price"), (int, float))
            and row.get("target_price") > 0
            and row.get("snapshot_sha256") in valid_hashes
            for row in survived
        ),
        "trade_entry_date_complete": all(bool(row.get("entry_date")) for row in trades),
        "every_trade_matches_membership_entry": trade_pairs == entered_pairs,
        "entered_provenance_complete": all(
            row.get("snapshot_sha256") in valid_hashes
            and bool(row.get("entry_date"))
            for row in entered
        ),
        "gate3_status_correct": (
            (audit.get("gate3") or {}).get("status")
            == (
                "measured_on_identifiable_days"
                if identifiable_days
                else "not_applicable_no_identifiable_entry_days"
            )
        ),
        "cash_enforced": (result.get("cash_ledger") or {}).get("enforced") is True,
        "no_negative_cash_events": (
            result.get("cash_ledger") or {}
        ).get("negative_cash_event_count") == 0,
        "cash_conservation": (
            result.get("cash_ledger") or {}
        ).get("cash_conservation_passed") is True,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def _double_replay_checks(
    pass_a: dict[str, dict[str, Any]],
    pass_b: dict[str, dict[str, Any]],
    specs: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for spec in specs:
        label = spec["label"]
        first = pass_a[label]["identity"]
        second = pass_b[label]["identity"]
        row = {
            "behavior_result_sha256": first["behavior_result_sha256"]
            == second["behavior_result_sha256"],
            "trade_rows_sha256": first["trade_rows_sha256"]
            == second["trade_rows_sha256"],
            "daily_return_series_sha256": first["daily_return_series_sha256"]
            == second["daily_return_series_sha256"],
            "universe_membership_sha256": first["universe_membership_sha256"]
            == second["universe_membership_sha256"],
            "deterministic_persistable_result_sha256": first[
                "deterministic_persistable_result_sha256"
            ]
            == second["deterministic_persistable_result_sha256"],
        }
        row["all_pass"] = all(row.values())
        row["raw_persistable_result_sha256_equal_report_only"] = first[
            "persistable_result_sha256"
        ] == second["persistable_result_sha256"]
        row["raw_difference_reason"] = (
            None
            if row["raw_persistable_result_sha256_equal_report_only"]
            else "runtime-generated non-OHLCV audit generated_at timestamps"
        )
        checks[label] = row
    checks["all_windows_exact"] = all(
        checks[spec["label"]]["all_pass"] for spec in specs
    )
    return checks


def _entered_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in (result.get("entry_candidate_events") or [])
        if row.get("decision") == "entered"
    ]


def _identified_slice_comparison(
    static_result: dict[str, Any],
    pit_result: dict[str, Any],
    resolver: EntryUniverseResolver,
    *,
    role: str = "watchlist_proxy_sensitivity",
) -> dict[str, Any]:
    static_headline = _headline(static_result)
    pit_headline = _headline(pit_result)
    leaked_entries = []
    for event in _entered_events(static_result):
        resolution = resolver.resolve(event["date"])
        ticker = str(event.get("ticker") or "").upper()
        if ticker not in set(resolution.get("tickers") or []):
            leaked_entries.append({
                "signal_date": event.get("date"),
                "entry_date": (event.get("details") or {}).get("fill_date"),
                "ticker": ticker,
                "strategy": event.get("strategy"),
                "membership_status": resolution.get("status"),
                "membership_effective_as_of": resolution.get("effective_as_of"),
                "membership_snapshot_hash": resolution.get("snapshot_hash"),
            })

    static_trade_keys = {
        row.get("trade_key") for row in (static_result.get("trades") or [])
    }
    pit_trade_keys = {
        row.get("trade_key") for row in (pit_result.get("trades") or [])
    }
    leaked_entry_pairs = {
        (row.get("ticker"), row.get("entry_date")) for row in leaked_entries
    }
    directly_ineligible_trade_rows = [
        {
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "pnl": row.get("pnl"),
            "exit_reason": row.get("exit_reason"),
        }
        for row in (static_result.get("trades") or [])
        if (row.get("ticker"), row.get("entry_date")) in leaked_entry_pairs
    ]
    directly_ineligible_pnl = round(
        sum(float(row.get("pnl") or 0) for row in directly_ineligible_trade_rows),
        2,
    )
    if role == "quant_pipeline_era_membership_comparison":
        role_note = (
            "Git-proven quant-pipeline membership comparison from the first session "
            "after quant/data_layer.py and quant/run.py existed; all other policy and "
            "measurement inputs locked"
        )
        first_limit = (
            "This is the strongest recoverable trading-universe comparison, but it "
            "covers only 2026-03-16 through 2026-04-21."
        )
    else:
        role_note = (
            "Watchlist-proxy sensitivity from the first repository-visible 13-name "
            "attention list; all other policy and measurement inputs locked"
        )
        first_limit = (
            "The 2026-01-23 through 2026-03-13 portion predates the recoverable quant "
            "pipeline, so its delta is sensitivity evidence, not proven trading leakage."
        )
    return {
        "comparison_role": role_note,
        "static_current_membership": static_headline,
        "git_proven_membership": pit_headline,
        "static_minus_git_proven": {
            "expected_value_score": round(
                float(static_result.get("expected_value_score") or 0)
                - float(pit_result.get("expected_value_score") or 0),
                4,
            ),
            "total_pnl": round(
                float(static_result.get("total_pnl") or 0)
                - float(pit_result.get("total_pnl") or 0),
                2,
            ),
            "trade_count": int(static_result.get("total_trades") or 0)
            - int(pit_result.get("total_trades") or 0),
            "signals_generated": int(static_result.get("signals_generated") or 0)
            - int(pit_result.get("signals_generated") or 0),
        },
        "static_entered_count": len(_entered_events(static_result)),
        "static_entries_ineligible_under_git_manifest_count": len(leaked_entries),
        "static_entries_ineligible_under_git_manifest": leaked_entries,
        "directly_ineligible_static_trades": directly_ineligible_trade_rows,
        "directly_ineligible_static_trade_pnl": directly_ineligible_pnl,
        "directly_ineligible_share_of_static_pnl": (
            round(
                directly_ineligible_pnl / float(static_result.get("total_pnl")),
                4,
            )
            if static_result.get("total_pnl")
            else None
        ),
        "static_only_trade_keys": sorted(static_trade_keys - pit_trade_keys),
        "git_proven_only_trade_keys": sorted(pit_trade_keys - static_trade_keys),
        "interpretation_limits": [
            first_limit,
            "It still uses the current-roster OHLCV security master and therefore remains survivor biased.",
            "Path-dependent capital competition means the delta is a portfolio effect, not the sum of leaked trades.",
        ],
    }


def _audit_preclean_broad_state(clean_cutoff: str) -> dict[str, Any]:
    state = json.loads(Path(DEFAULT_STATE_PATH).read_text(encoding="utf-8"))
    snapshots = []
    snapshot_path = Path(DEFAULT_SNAPSHOT_LOG_PATH)
    if snapshot_path.exists():
        for line in snapshot_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                snapshots.append(json.loads(line))
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    opened = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    snapshot_dates = [
        str(row.get("asof_date") or row.get("as_of") or "")[:10]
        for row in snapshots
        if row.get("asof_date") or row.get("as_of")
    ]
    latest_as_of = max(snapshot_dates, default=None)
    stale_open = [
        row for row in opened
        if latest_as_of and str(row.get("last_seen_date") or "")[:10] < latest_as_of
    ]
    post_feed_closed = [
        row for row in closed
        if str(row.get("created_asof") or row.get("entry_date") or "")[:10]
        >= "2026-06-11"
    ]
    return {
        "snapshot_rows": len(snapshots),
        "unique_snapshot_dates": len(set(snapshot_dates)),
        "latest_snapshot_as_of": latest_as_of,
        "closed_count": len(closed),
        "closed_pnl": round(sum(float(row.get("pnl") or 0) for row in closed), 2),
        "post_2026_06_11_closed_count": len(post_feed_closed),
        "open_count": len(opened),
        "pending_count": len(pending),
        "stale_open_mark_count_before_repair": len(stale_open),
        "stale_open_tickers_before_repair": sorted({row.get("ticker") for row in stale_open}),
        "clean_cutoff": clean_cutoff,
        "clean_settled_rows_at_inception": 0,
        "cohort_rule": (
            "Only entries created on/after clean_cutoff and tied to a persisted "
            "membership snapshot may count as clean forward alpha evidence; pre-cutoff "
            "positions remain markable but belong to the legacy carry cohort."
        ),
    }


def _seed_broad_forward_membership() -> dict[str, Any]:
    seed_path = EXP_DIR / "broad_market_universe_seed_20260717.json"
    payload = generate_broad_market_paper_universe(
        as_of=DEFAULT_CLEAN_CUTOFF,
        out_path=seed_path,
        ledger_path=DEFAULT_MEMBERSHIP_LEDGER_PATH,
        clean_cutoff=DEFAULT_CLEAN_CUTOFF,
        write=True,
    )
    rows = load_membership_snapshots(DEFAULT_MEMBERSHIP_LEDGER_PATH)
    latest = rows[-1] if rows else None
    checks = {
        "ledger_status_appended_or_duplicate": payload.get(
            "membership_ledger_status"
        ) in {"appended", "duplicate"},
        "full_membership_persisted": bool(latest)
        and latest.get("tickers") == payload.get("tickers"),
        "cutoff_exact": bool(latest)
        and latest.get("effective_as_of") == DEFAULT_CLEAN_CUTOFF,
        "membership_hash_exact": bool(latest)
        and latest.get("membership_hash") == payload.get("membership_hash"),
        "broad_population_nontrivial": len(payload.get("tickers") or []) >= 1000,
    }
    checks["all_pass"] = all(checks.values())
    return {
        "checks": checks,
        "seed_feed_path": gate1._repo_rel(seed_path),
        "ledger_path": gate1._repo_rel(Path(DEFAULT_MEMBERSHIP_LEDGER_PATH)),
        "ledger_status": payload.get("membership_ledger_status"),
        "effective_as_of": payload.get("membership_as_of"),
        "ticker_count": len(payload.get("tickers") or []),
        "membership_hash": payload.get("membership_hash"),
        "snapshot_hash": payload.get("membership_snapshot_hash"),
        "ledger_hash": payload.get("membership_ledger_hash"),
        "forward_generation": payload.get("forward_generation"),
    }


def _public_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for label, record in records.items():
        result = record["result"]
        membership = result.get("universe_membership") or {}
        headline = _headline(result)
        interpretation_status = "measured"
        if (
            membership.get("mode") == "pit_walk_forward"
            and int(membership.get("identifiable_days") or 0) == 0
        ):
            for key in (
                "expected_value_score",
                "total_pnl",
                "sharpe_daily",
                "max_drawdown_pct",
                "win_rate",
                "signals_generated",
                "signals_survived",
                "survival_rate",
                "trade_count",
            ):
                headline[key] = None
            interpretation_status = (
                "unidentifiable_pre_membership_history_do_not_aggregate"
            )
        public[label] = {
            "headline": headline,
            "interpretation_status": interpretation_status,
            "identity": record["identity"],
            "result_path": record["result_path"],
            "result_file_sha256": record["result_file_sha256"],
            "universe_membership_summary": {
                key: membership.get(key)
                for key in (
                    "mode",
                    "trading_days",
                    "identifiable_days",
                    "unidentifiable_days",
                    "first_identifiable_date",
                    "min_eligible_count",
                    "max_eligible_count",
                    "snapshot_hashes",
                    "gate3",
                )
            },
        }
    return public


def main() -> int:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    anchor_metrics = {
        "expected_value_score": active["aggregate"]["expected_value_score_sum"],
        "total_pnl": active["aggregate"]["total_pnl_sum"],
        "total_trades": active["aggregate"]["trade_count_sum"],
        "survival_rate": active["aggregate"]["minimum_survival_rate"],
        "max_drawdown_pct": active["aggregate"]["worst_max_drawdown_pct"],
    }
    resolver, source_audit = _build_historical_membership_resolver()
    if not set(resolver.data_tickers).issubset(frozen["behavior"]["universe"]):
        raise RuntimeError("Historical membership contains ticker outside frozen data universe")

    gate1._atomic_write_json(
        BEFORE_MEASUREMENT,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "active_cash_feasible_static_current_membership_anchor",
            **anchor_metrics,
            "source": gate1._repo_rel(ACTIVE_BASELINE),
            "source_sha256": gate1._file_sha256(ACTIVE_BASELINE),
            "aggregate": active["aggregate"],
            "windows": active["windows"],
            "truth_status": (
                "valid regression anchor but not an unbiased alpha estimate: current "
                "membership is carried backward and the magnitude of contamination "
                "is not fully identifiable"
            ),
        },
    )

    static_full = _run_arm(
        "static_current_full",
        tuple(gate1.WINDOWS),
        frozen,
        resolver=None,
        passes=1,
    )[0]
    static_checks = _static_reference_checks(static_full, active)

    pit_full_passes = _run_arm(
        "git_proven_full",
        tuple(gate1.WINDOWS),
        frozen,
        resolver=resolver,
        passes=2,
    )
    pit_full_double = _double_replay_checks(
        pit_full_passes[0], pit_full_passes[1], tuple(gate1.WINDOWS)
    )
    pit_full_membership_checks = {
        label: _membership_checks(record["result"], resolver)
        for label, record in pit_full_passes[0].items()
    }
    pit_full_membership_checks["all_windows_pass"] = all(
        row["all_pass"]
        for label, row in pit_full_membership_checks.items()
        if label != "all_windows_pass"
    )

    slice_static_passes = _run_arm(
        "static_current_identifiable_slice",
        (IDENTIFIABLE_SLICE,),
        frozen,
        resolver=None,
        passes=2,
    )
    slice_pit_passes = _run_arm(
        "git_proven_identifiable_slice",
        (IDENTIFIABLE_SLICE,),
        frozen,
        resolver=resolver,
        passes=2,
    )
    slice_static_double = _double_replay_checks(
        slice_static_passes[0], slice_static_passes[1], (IDENTIFIABLE_SLICE,)
    )
    slice_pit_double = _double_replay_checks(
        slice_pit_passes[0], slice_pit_passes[1], (IDENTIFIABLE_SLICE,)
    )
    slice_pit_membership = _membership_checks(
        slice_pit_passes[0][IDENTIFIABLE_SLICE["label"]]["result"], resolver
    )
    slice_comparison = _identified_slice_comparison(
        slice_static_passes[0][IDENTIFIABLE_SLICE["label"]]["result"],
        slice_pit_passes[0][IDENTIFIABLE_SLICE["label"]]["result"],
        resolver,
        role="watchlist_proxy_sensitivity",
    )

    quant_static_passes = _run_arm(
        "static_current_quant_pipeline_era",
        (QUANT_PIPELINE_SLICE,),
        frozen,
        resolver=None,
        passes=2,
    )
    quant_pit_passes = _run_arm(
        "git_proven_quant_pipeline_era",
        (QUANT_PIPELINE_SLICE,),
        frozen,
        resolver=resolver,
        passes=2,
    )
    quant_static_double = _double_replay_checks(
        quant_static_passes[0], quant_static_passes[1], (QUANT_PIPELINE_SLICE,)
    )
    quant_pit_double = _double_replay_checks(
        quant_pit_passes[0], quant_pit_passes[1], (QUANT_PIPELINE_SLICE,)
    )
    quant_pit_membership = _membership_checks(
        quant_pit_passes[0][QUANT_PIPELINE_SLICE["label"]]["result"], resolver
    )
    quant_pipeline_comparison = _identified_slice_comparison(
        quant_static_passes[0][QUANT_PIPELINE_SLICE["label"]]["result"],
        quant_pit_passes[0][QUANT_PIPELINE_SLICE["label"]]["result"],
        resolver,
        role="quant_pipeline_era_membership_comparison",
    )

    broad_preclean = _audit_preclean_broad_state(DEFAULT_CLEAN_CUTOFF)
    broad_forward = _seed_broad_forward_membership()

    acceptance = {
        "git_membership_sources_exact": all(source_audit["checks"].values()),
        "static_default_bit_exact_to_active_anchor": static_checks[
            "all_windows_exact"
        ],
        "pit_full_double_replay_exact": pit_full_double["all_windows_exact"],
        "pit_full_membership_and_cash_contract": pit_full_membership_checks[
            "all_windows_pass"
        ],
        "watchlist_proxy_static_double_replay_exact": slice_static_double[
            "all_windows_exact"
        ],
        "watchlist_proxy_pit_double_replay_exact": slice_pit_double[
            "all_windows_exact"
        ],
        "watchlist_proxy_membership_and_cash_contract": slice_pit_membership[
            "all_pass"
        ],
        "quant_pipeline_static_double_replay_exact": quant_static_double[
            "all_windows_exact"
        ],
        "quant_pipeline_pit_double_replay_exact": quant_pit_double[
            "all_windows_exact"
        ],
        "quant_pipeline_membership_and_cash_contract": quant_pit_membership[
            "all_pass"
        ],
        "broad_forward_full_membership_started": broad_forward["checks"]["all_pass"],
        "pre_snapshot_windows_not_interpreted_as_zero_return": True,
        "security_master_survivorship_not_claimed_repaired": True,
        "gate1_not_replaced": True,
        "accepted_alpha": False,
        "live_ready": False,
    }
    accepted = all(
        value for key, value in acceptance.items()
        if key not in {"accepted_alpha", "live_ready"}
    )

    payload = {
        "schema": "legacy_core_pit_universe_truth_audit_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": (
            "accepted_measurement_repair" if accepted else "failed_measurement_repair"
        ),
        **anchor_metrics,
        "accepted_alpha": False,
        "live_ready": False,
        "acceptance": acceptance,
        "hypothesis_result": (
            "The 2026-01-23 Git snapshot supports only a watchlist-proxy sensitivity; "
            "strict quant-pipeline entry membership is auditable from 2026-03-16. "
            "Earlier history and the current-roster security master remain "
            "unidentifiable. The clean broad forward membership ledger is active "
            "only in default-off paper measurement."
        ),
        "frozen_identity": {
            "frozen_behavior_path": gate1._repo_rel(FROZEN_INPUTS),
            "frozen_behavior_sha256": frozen["behavior_sha256"],
            "data_universe_count": len(frozen["behavior"]["universe"]),
            "run_config": dict(gate1.RUN_CONFIG),
            "warehouse": gate1._repo_rel(gate1.WAREHOUSE),
        },
        "historical_membership_source_audit": source_audit,
        "static_anchor_checks": static_checks,
        "pit_full_double_replay_checks": pit_full_double,
        "pit_full_membership_checks": pit_full_membership_checks,
        "watchlist_proxy_static_double_replay_checks": slice_static_double,
        "watchlist_proxy_pit_double_replay_checks": slice_pit_double,
        "watchlist_proxy_membership_checks": slice_pit_membership,
        "quant_pipeline_static_double_replay_checks": quant_static_double,
        "quant_pipeline_pit_double_replay_checks": quant_pit_double,
        "quant_pipeline_membership_checks": quant_pit_membership,
        "full_window_static_current_membership": _public_records(static_full),
        "full_window_git_proven_membership": _public_records(pit_full_passes[0]),
        "watchlist_proxy_sensitivity": slice_comparison,
        "quant_pipeline_era_comparison": quant_pipeline_comparison,
        "broad_forward_preclean_audit": broad_preclean,
        "broad_forward_membership": broad_forward,
        "production_impact": {
            "live_orders_changed": False,
            "live_signals_ranking_sizing_exits_changed": False,
            "backtester_default_changed": False,
            "default_off_pit_resolver_available": True,
            "broad_paper_membership_append_only_from_cutoff": True,
            "pre_cutoff_open_and_pending_tickers_continue_to_be_marked": True,
            "gate1_replaced": False,
        },
        "limitations_and_unknowns": [
            "No recoverable entry-membership snapshot exists before 2026-01-23.",
            "The OHLCV warehouse uses a current-roster security master and omits many delisted/acquired names.",
            "The Git manifest is an auditable lower bound, not proof that no other discretionary ticker was considered.",
            "The large January-to-April watchlist-proxy delta partly predates the recoverable quant pipeline and is not proven trading leakage.",
            "Broad forward membership starts with zero settled clean-generation trades; alpha remains unknown until settlement.",
            "The active 6.2057 Gate-1 remains a regression anchor, not an unbiased expected-return estimate.",
        ],
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260717_003_legacy_core_pit_universe_truth_audit.py"
            ),
            "baseline": gate1._repo_rel(ACTIVE_BASELINE),
            "historical_membership_ledger": gate1._repo_rel(
                HISTORICAL_MEMBERSHIP_LEDGER
            ),
        },
    }
    gate1._atomic_write_json(AFTER_MEASUREMENT, payload)
    gate1._atomic_write_json(SUMMARY, payload)
    print(json.dumps({
        "decision": payload["decision"],
        "static_anchor_exact": static_checks["all_windows_exact"],
        "watchlist_proxy_sensitivity": slice_comparison,
        "quant_pipeline_era_comparison": quant_pipeline_comparison,
        "broad_forward_membership": broad_forward,
        "summary": gate1._repo_rel(SUMMARY),
    }, ensure_ascii=False, indent=2))
    if not accepted:
        raise RuntimeError(f"Measurement acceptance failed: {acceptance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
