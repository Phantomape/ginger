"""exp-20260717-007: NVD Initial Analysis CVE-cluster entry gate.

The single decision hypothesis is fixed before outcome measurement: for one
mapped issuer, the third distinct CVE whose NVD Change History transition is
``Initial Analysis`` with an added CPE detail in the same UTC Monday calendar
week activates a five-entry-session exclusion beginning with the next trading
session.  The helper resolver evaluates the *next-open fill session* from each
signal day, so a signal queued immediately before an exclusion cannot leak
through at the excluded open.  Existing positions, exits, ranking, sizing and
costs are unchanged.

The source archive is immutable and replayable.  ``--refresh-source`` fetches
and hashes the official paginated Change History response; ``--source-archive``
replays a previously archived manifest without network access.  With neither
flag, an existing archive is reused and a missing archive is fetched.

This runner deliberately rejects otherwise-positive results if the PIT entry
resolver changes an add-on checkpoint or queued add-on fill.  Such a change
would mix entry admission with lifecycle sizing and break causal attribution.
"""

from __future__ import annotations

import argparse
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

from backtester import (  # noqa: E402
    BacktestEngine,
    _persistable_backtest_result,
)
import nvd_cve_entry_gate as nvd  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402


EXPERIMENT_ID = "exp-20260717-007"
PROTOCOL_ID = "nvd_initial_analysis_cluster3_next_session_5d_v1"
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
SOURCE_DIR = (
    ROOT / "data" / "non_ohlcv" / "nvd_cve_entry_gate" / EXPERIMENT_ID
)
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BACKTEST_DIR = ROOT / "data" / "backtests" / "nvd_cve_entry_gate_20260717"
BEFORE_FILE = EXP_DIR / "before_measurement.json"
AFTER_FILE = EXP_DIR / "after_measurement.json"
ARTIFACT = EXP_DIR / "exp_20260717_007_nvd_cve_cluster_entry_gate.json"

# The previous UTC Monday gives the oldest window enough history to observe a
# partial issuer-week whose third event can activate on its first session.
SOURCE_START = "2024-09-23T00:00:00.000Z"
SOURCE_END = "2026-04-21T23:59:59.999Z"
CLUSTER_THRESHOLD = 3
EXCLUSION_SESSIONS = 5
ACTIVE_EV = 6.2057
REQUIRED_EV = 6.82627  # strict >10% improvement over the active 6.2057 anchor
MIN_SURVIVAL_RATE = 0.05

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


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Unexpected frozen Gate-1 behavior-input schema")
    if payload.get("behavior_sha256") != gate1._stable_hash(
        payload.get("behavior")
    ):
        raise RuntimeError("Frozen Gate-1 behavior-input hash mismatch")
    return payload


def _path_text(path: Path) -> str:
    try:
        return gate1._repo_rel(path)
    except ValueError:
        return str(path.resolve())


def _coerce_manifest_path(value: Any, *, archive_dir: Path) -> Path:
    raw: Any = value
    if isinstance(value, Mapping):
        raw = value.get("manifest_path") or value.get("path")
    if raw is None:
        raise RuntimeError("NVD archive fetch did not return a manifest path")
    path = Path(str(raw))
    if not path.is_absolute():
        candidates = (ROOT / path, archive_dir / path)
        path = next((candidate for candidate in candidates if candidate.exists()), path)
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"NVD archive manifest does not exist: {path}")
    return path


def _discover_manifest(archive_dir: Path) -> Path | None:
    if not archive_dir.exists():
        return None
    preferred = tuple(
        path
        for name in (
            "manifest.json",
            "source_manifest.json",
            "nvd_change_history_manifest.json",
        )
        if (path := archive_dir / name).is_file()
    )
    if len(preferred) == 1:
        return preferred[0].resolve()
    if len(preferred) > 1:
        raise RuntimeError(
            "Multiple preferred NVD manifests found; pass --source-archive"
        )
    matches = sorted(archive_dir.glob("*manifest*.json"))
    if not matches:
        return None
    if len(matches) != 1:
        raise RuntimeError(
            "Multiple NVD manifests found; pass --source-archive explicitly"
        )
    return matches[0].resolve()


def _resolve_source_manifest(args: argparse.Namespace) -> tuple[Path, str]:
    if args.source_archive is not None:
        supplied = args.source_archive.resolve()
        if supplied.is_dir():
            discovered = _discover_manifest(supplied)
            if discovered is None:
                raise FileNotFoundError(
                    f"No manifest found in --source-archive directory: {supplied}"
                )
            return discovered, "explicit_source_archive"
        return _coerce_manifest_path(supplied, archive_dir=supplied.parent), (
            "explicit_source_archive"
        )

    existing = None if args.refresh_source else _discover_manifest(SOURCE_DIR)
    if existing is not None:
        return existing, "reused_default_archive"

    fetched = nvd.fetch_nvd_change_history_archive(
        start=SOURCE_START,
        end=SOURCE_END,
        archive_dir=SOURCE_DIR,
    )
    return _coerce_manifest_path(fetched, archive_dir=SOURCE_DIR), (
        "refreshed_archive" if args.refresh_source else "fetched_missing_archive"
    )


def _manifest_identity(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    file_sha256 = gate1._file_sha256(path)
    declared_payload = payload.get("manifest_payload_sha256")
    return {
        "path": _path_text(path),
        "file_sha256": file_sha256,
        "manifest_sha256": file_sha256,
        "manifest_payload_sha256": declared_payload,
        "schema": payload.get("schema"),
        "query": payload.get("query"),
        "page_count": len(payload.get("pages") or []),
        "total_results": payload.get("total_results"),
        "declares_self_hash": bool(declared_payload),
    }


def _all_sessions() -> list[str]:
    # Include real sessions before old_thin starts.  A cluster triggered in the
    # preceding UTC week may spend some or all of its five-session exclusion
    # on Sep-23..Oct-01; starting the calendar at Oct-02 would incorrectly
    # carry those consumed sessions into the measured window.
    oldest = next(spec for spec in gate1.WINDOWS if spec["label"] == "old_thin")
    buffered_oldest = {
        **oldest,
        "start": SOURCE_START[:10],
    }
    sessions = {
        day_text
        for spec in (*gate1.WINDOWS, buffered_oldest)
        for day_text in gate1._spy_dates(spec)
    }
    # The resolver evaluates the next-open session.  Append a real exchange
    # calendar tail so the final measured signal day remains identifiable and
    # a trigger on that day receives its complete five-session schedule even
    # though the frozen OHLCV window itself ends there.
    latest_end = max(date.fromisoformat(spec["end"]) for spec in gate1.WINDOWS)
    sessions.update(
        candidate.isoformat()
        for offset in range(1, 15)
        if nvd.is_us_equity_session(
            candidate := latest_end + timedelta(days=offset)
        )
    )
    return sorted(sessions)


def _as_mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row
    if hasattr(row, "__dict__"):
        return vars(row)
    return {}


def _field(row: Any, *names: str) -> Any:
    values = _as_mapping(row)
    for name in names:
        if name in values and values[name] is not None:
            return values[name]
    return None


def _source_summary(
    raw_rows: Sequence[Any],
    events: Sequence[Any],
    clusters: Sequence[Any],
    sessions: Sequence[str],
    *,
    evaluation_tickers: Sequence[str],
) -> dict[str, Any]:
    event_tickers = sorted(
        {
            str(value).upper()
            for row in events
            if (value := _field(row, "ticker", "issuer_ticker"))
        }
    )
    event_ids = {
        str(value).upper()
        for row in events
        if (value := _field(row, "cve_id", "cveId", "cve"))
    }
    cluster_tickers = sorted(
        {
            str(value).upper()
            for row in clusters
            if (value := _field(row, "ticker", "issuer_ticker"))
        }
    )
    triggers = sorted(
        str(value)
        for row in clusters
        if (value := _field(
            row,
            "trigger_created",
            "trigger_created_at",
            "trigger_at",
            "created",
        ))
    )
    normalization_checks = {
        "event_name_exact": all(
            _field(row, "event_name") == "Initial Analysis" for row in events
        ),
        "detail_type_exact": all(
            _field(row, "detail_type") == "CPE Configuration" for row in events
        ),
        "detail_action_exact": all(
            _field(row, "detail_action") == "Added" for row in events
        ),
        "published_clock_not_used": all(
            _field(row, "published_clock_used") is False for row in events
        ),
        "reanalysis_not_used": all(
            _field(row, "reanalysis_used") is False for row in events
        ),
    }
    if not all(normalization_checks.values()):
        raise RuntimeError(
            f"NVD normalized event contract drifted: {normalization_checks}"
        )
    evaluation_ticker_set = {
        str(value).strip().upper()
        for value in evaluation_tickers
        if str(value).strip()
    }

    def _density(rows: Sequence[Any], *, start: str, end: str) -> dict[str, Any]:
        ticker_counts = Counter(
            str(ticker).upper()
            for row in rows
            if (ticker := _field(row, "ticker", "issuer_ticker"))
        )
        top_ticker, top_count = (
            ticker_counts.most_common(1)[0] if ticker_counts else (None, 0)
        )
        issuer_week_count = len(rows)
        return {
            "start": start,
            "end": end,
            "issuer_week_count": issuer_week_count,
            "ticker_count": len(ticker_counts),
            "top1_ticker": top_ticker,
            "top1_count": top_count,
            "top1_concentration": round(top_count / issuer_week_count, 6)
            if issuer_week_count
            else None,
            "preflight_thresholds": {
                "issuer_week_count_gte_20": issuer_week_count >= 20,
                "ticker_count_gte_10": len(ticker_counts) >= 10,
                "top1_concentration_lte_30pct": (
                    issuer_week_count > 0
                    and top_count / issuer_week_count <= 0.30
                ),
            },
        }

    density_by_window: dict[str, dict[str, Any]] = {}
    evaluation_universe_density_by_window: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = str(spec["label"])
        start = str(spec["start"])
        end = str(spec["end"])
        window_clusters = [
            row
            for row in clusters
            if start
            <= str(_field(row, "trigger_created", "created") or "")[:10]
            <= end
        ]
        density_by_window[label] = _density(
            window_clusters,
            start=start,
            end=end,
        )
        evaluation_universe_density_by_window[label] = _density(
            [
                row
                for row in window_clusters
                if str(_field(row, "ticker", "issuer_ticker") or "").upper()
                in evaluation_ticker_set
            ],
            start=start,
            end=end,
        )
    return {
        "raw_change_rows": len(raw_rows),
        "normalized_initial_analysis_events": len(events),
        "distinct_cve_ids": len(event_ids),
        "mapped_event_tickers": event_tickers,
        "mapped_event_ticker_count": len(event_tickers),
        "issuer_week_clusters": len(clusters),
        "cluster_tickers": cluster_tickers,
        "cluster_ticker_count": len(cluster_tickers),
        "density_by_window": density_by_window,
        "density_scope": (
            "density_by_window covers every statically mapped vendor ticker; "
            "evaluation_universe_density_by_window is the decision-relevant "
            "intersection with the frozen Gate-4 base universe"
        ),
        "evaluation_universe_ticker_count": len(evaluation_ticker_set),
        "evaluation_universe_density_by_window": (
            evaluation_universe_density_by_window
        ),
        "first_trigger_created": triggers[0] if triggers else None,
        "last_trigger_created": triggers[-1] if triggers else None,
        "trading_session_count": len(sessions),
        "normalization_checks": normalization_checks,
        "cluster_rule": {
            "calendar": "UTC Monday week",
            "change_history_event": "Initial Analysis",
            "detail_type": "CPE Configuration",
            "detail_action": "Added",
            "threshold": CLUSTER_THRESHOLD,
            "deduplication": "distinct CVE ID ordered by (created, cve_id)",
            "trigger": "third distinct CVE created timestamp",
            "activation": "next trading session",
            "exclusion_sessions": EXCLUSION_SESSIONS,
            "normalization_contract": (
                "normalize_nvd_initial_analysis_events admits only exact "
                "Initial Analysis transitions carrying an Added CPE "
                "Configuration detail; other history rows fail closed."
            ),
        },
    }


def _build_resolver(
    frozen: dict[str, Any], manifest_path: Path
) -> tuple[Any, dict[str, Any]]:
    manifest = _manifest_identity(manifest_path)
    # Loading verifies every page hash, pagination contract and manifest
    # self-hash before any event can enter the replay.
    raw_rows = nvd.load_nvd_change_history_archive(manifest_path)
    events = nvd.normalize_nvd_initial_analysis_events(raw_rows)
    clusters = nvd.build_nvd_cve_clusters(events)
    sessions = _all_sessions()
    exclusion_index = nvd.build_nvd_exclusion_index(
        clusters,
        sessions,
        source_manifest_sha256=manifest["manifest_sha256"],
    )
    resolver = nvd.NvdEntryUniverseResolver(
        base_tickers=frozen["behavior"]["universe"],
        exclusion_index=exclusion_index,
        trading_sessions=sessions,
        source_manifest_sha256=manifest["manifest_sha256"],
    )
    metadata = getattr(resolver, "metadata", None)
    if not isinstance(metadata, Mapping):
        raise RuntimeError("NVD resolver metadata must be a mapping")
    return resolver, {
        "manifest": manifest,
        "summary": _source_summary(
            raw_rows,
            events,
            clusters,
            sessions,
            evaluation_tickers=frozen["behavior"]["universe"],
        ),
        "resolver_metadata": dict(metadata),
    }


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
        "source_role": "NVD Change History Initial Analysis added-CPE PIT",
        "security_master_survivorship_status": (
            "current frozen roster; entry gate does not claim delisted-security repair"
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
    spec: dict[str, str],
    result: dict[str, Any],
) -> dict[str, str]:
    path = BACKTEST_DIR / f"{spec['label']}_{arm}_{EXPERIMENT_ID}.json"
    gate1._atomic_write_json(path, _persistable_backtest_result(result))
    return {
        "path": _path_text(path),
        "sha256": gate1._file_sha256(path),
    }


def _headline(result: Mapping[str, Any]) -> dict[str, Any]:
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
    records: Mapping[str, Mapping[str, Any]], active: Mapping[str, Any]
) -> dict[str, Any]:
    expected = {row["label"]: row for row in active["windows"]}
    checks: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        record = records[label]
        result = record["result"]
        identity = record["identity"]
        row = expected[label]
        fields = {
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
            "cash_enforced": (result.get("cash_ledger") or {}).get("enforced")
            is True,
            "cash_conservation": (
                result.get("cash_ledger") or {}
            ).get("cash_conservation_passed")
            is True,
        }
        checks[label] = {**fields, "all_pass": all(fields.values())}
    checks["all_windows_exact"] = all(
        checks[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    return checks


def _gate2_checks(result: Mapping[str, Any], resolver: Any) -> dict[str, Any]:
    audit = result.get("universe_membership") or {}
    generated = audit.get("generated_signals") or []
    survived = audit.get("survived_signals") or []
    entered = audit.get("entered_trades") or []
    trades = result.get("trades") or []
    daily = audit.get("daily") or []
    valid_hashes = {
        row.get("snapshot_sha256") for row in daily if row.get("snapshot_sha256")
    }
    entered_eligible = []
    for row in entered:
        resolution = resolver.resolve(row.get("signal_date"))
        entered_eligible.append(
            str(row.get("ticker") or "").upper()
            in {str(t).upper() for t in resolution.get("tickers") or []}
        )
    checks = {
        "pit_mode": audit.get("mode") == "pit_walk_forward",
        "all_days_identifiable": int(audit.get("unidentifiable_days") or 0) == 0,
        "generated_count_matches": len(generated)
        == int(result.get("signals_generated") or 0),
        "survived_count_matches": len(survived)
        == int(result.get("signals_survived") or 0),
        # Generated-signal rows are intentionally captured before enrichment;
        # signal_date is their date sentinel.  target_price is checked on every
        # survived/enriched signal; entry_date is checked on entered/trade rows.
        "generated_signal_date_complete": all(
            bool(row.get("signal_date")) for row in generated
        ),
        "generated_resolver_provenance_complete": all(
            row.get("snapshot_sha256") in valid_hashes
            and row.get("status") == "resolved"
            for row in generated
        ),
        "survived_target_price_complete": all(
            isinstance(row.get("target_price"), (int, float))
            and math.isfinite(float(row["target_price"]))
            and float(row["target_price"]) > 0
            for row in survived
        ),
        "survived_resolver_provenance_complete": all(
            row.get("snapshot_sha256") in valid_hashes
            and row.get("status") == "resolved"
            for row in survived
        ),
        "trade_entry_date_complete": all(bool(row.get("entry_date")) for row in trades),
        "entered_fill_after_signal": all(
            bool(row.get("signal_date"))
            and bool(row.get("entry_date"))
            and row["entry_date"] > row["signal_date"]
            for row in entered
        ),
        "entered_next_open_was_resolver_eligible": all(entered_eligible),
        "cash_enforced": (result.get("cash_ledger") or {}).get("enforced") is True,
        "no_negative_cash_events": (
            result.get("cash_ledger") or {}
        ).get("negative_cash_event_count")
        == 0,
        "cash_conservation": (
            result.get("cash_ledger") or {}
        ).get("cash_conservation_passed")
        is True,
    }
    checks["all_pass"] = all(checks.values())
    return checks


def _addon_attribution(result: Mapping[str, Any]) -> dict[str, Any]:
    events = (result.get("addon_attribution") or {}).get("events") or []
    contaminated = [
        row
        for row in events
        if row.get("status") == "skipped_entry_universe_ineligible"
    ]
    checkpoint = [row for row in contaminated if row.get("checkpoint_date")]
    queued_fill = [row for row in contaminated if row.get("scheduled_fill_date")]
    return {
        "resolver_changed_addon_count": len(contaminated),
        "checkpoint_rejection_count": len(checkpoint),
        "queued_fill_rejection_count": len(queued_fill),
        "clean": not contaminated,
        "events": contaminated,
        "acceptance_note": (
            "Any resolver-driven add-on checkpoint or queued-fill change fails "
            "causal attribution even if headline EV improves."
        ),
    }


def _delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    return {
        key: (
            round(float(after[key]) - float(before[key]), 6)
            if isinstance(after.get(key), (int, float))
            and isinstance(before.get(key), (int, float))
            else None
        )
        for key in keys
    }


def _aggregate(windows: Mapping[str, Mapping[str, Any]], arm: str) -> dict[str, Any]:
    rows = [windows[spec["label"]][arm] for spec in gate1.WINDOWS]
    return {
        "expected_value_score_sum": round(
            sum(float(row["expected_value_score"]) for row in rows), 4
        ),
        "total_pnl_sum": round(sum(float(row["total_pnl"]) for row in rows), 2),
        "trade_count_sum": sum(int(row["trade_count"]) for row in rows),
        "positive_ev_windows": sum(
            float(row["expected_value_score"]) > 0 for row in rows
        ),
        "minimum_survival_rate": min(float(row["survival_rate"]) for row in rows),
        "worst_max_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in rows
        ),
    }


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
        trade_sample_floor = max(10, math.floor(0.80 * before["trade_count"]))
        row = {
            "ev_non_degrading": after["expected_value_score"]
            >= before["expected_value_score"],
            "pnl_non_degrading": after["total_pnl"] >= before["total_pnl"],
            "drawdown_non_degrading": after["max_drawdown_pct"]
            <= before["max_drawdown_pct"],
            "trade_sample_floor": trade_sample_floor,
            "trade_sample_sufficient": after["trade_count"]
            >= trade_sample_floor,
            "gate3_survival": after["survival_rate"] >= MIN_SURVIVAL_RATE,
        }
        row["all_pass"] = all(
            value for key, value in row.items() if key != "trade_sample_floor"
        )
        per_window[label] = row
    checks = {
        "aggregate_ev_strictly_above_10pct_hurdle": after_aggregate[
            "expected_value_score_sum"
        ]
        > REQUIRED_EV,
        "aggregate_pnl_non_degrading": after_aggregate["total_pnl_sum"]
        >= before_aggregate["total_pnl_sum"],
        "aggregate_drawdown_non_degrading": after_aggregate[
            "worst_max_drawdown_pct"
        ]
        <= before_aggregate["worst_max_drawdown_pct"],
        "aggregate_trade_sample_sufficient": after_aggregate["trade_count_sum"]
        >= 40,
        "aggregate_survival_gate": after_aggregate["minimum_survival_rate"]
        >= MIN_SURVIVAL_RATE,
        "all_windows_non_degrading": all(
            row["all_pass"] for row in per_window.values()
        ),
    }
    checks["all_pass"] = all(checks.values())
    return {
        "fixed_hurdle": {
            "active_gate1_expected_value_score": ACTIVE_EV,
            "required_improvement": ">10%",
            "acceptance_boundary": ">6.82627",
            "aggregate_trade_count_floor": 40,
            "per_window_trade_count_floor": (
                "max(10, floor(80% of that window's before trade count))"
            ),
        },
        "per_window": per_window,
        "checks": checks,
    }


def build_artifact(args: argparse.Namespace) -> dict[str, Any]:
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    if active.get("aggregate", {}).get("expected_value_score_sum") != ACTIVE_EV:
        raise RuntimeError("Active Gate-1 aggregate EV no longer matches frozen hurdle")

    manifest_path, archive_mode = _resolve_source_manifest(args)
    resolver, source = _build_resolver(frozen, manifest_path)

    before_records: dict[str, dict[str, Any]] = {}
    after_records: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] before: active cash-feasible static anchor ...", flush=True)
        before_result, before_identity = _run_window(
            spec, frozen, resolver=None
        )
        before_records[label] = {
            "result": before_result,
            "identity": before_identity,
            "artifact": _persist_result("before", spec, before_result),
        }
        print(f"[{label}] after: NVD cluster entry admission ...", flush=True)
        after_result, after_identity = _run_window(
            spec, frozen, resolver=resolver
        )
        after_records[label] = {
            "result": after_result,
            "identity": after_identity,
            "artifact": _persist_result("after", spec, after_result),
        }

    gate1_checks = _static_reference_checks(before_records, active)
    windows: dict[str, Any] = {}
    gate2: dict[str, Any] = {}
    addon_audit: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before_headline = _headline(before_records[label]["result"])
        after_headline = _headline(after_records[label]["result"])
        gate2[label] = _gate2_checks(after_records[label]["result"], resolver)
        addon_audit[label] = _addon_attribution(after_records[label]["result"])
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
                key: (after_records[label]["result"].get("universe_membership") or {}).get(
                    key
                )
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
    gate2["all_windows_pass"] = all(
        gate2[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    addon_audit["all_windows_clean"] = all(
        addon_audit[spec["label"]]["clean"] for spec in gate1.WINDOWS
    )

    before_aggregate = _aggregate(windows, "before")
    after_aggregate = _aggregate(windows, "after")
    aggregate_delta = {
        key: round(float(after_aggregate[key]) - float(before_aggregate[key]), 6)
        for key in before_aggregate
        if isinstance(before_aggregate[key], (int, float))
        and isinstance(after_aggregate[key], (int, float))
    }
    gate3 = {
        label: {
            "signals_generated": windows[label]["after"]["signals_generated"],
            "signals_survived": windows[label]["after"]["signals_survived"],
            "survival_rate": windows[label]["after"]["survival_rate"],
            "passed": windows[label]["after"]["survival_rate"]
            >= MIN_SURVIVAL_RATE,
        }
        for label in windows
    }
    gate3["all_windows_pass"] = all(
        gate3[spec["label"]]["passed"] for spec in gate1.WINDOWS
    )
    gate4 = _gate4_checks(windows, before_aggregate, after_aggregate)

    shared_contract = {
        "shared_helper_imported": True,
        "resolver_type": type(resolver).__name__,
        "daily_default_off_snapshot_callable": callable(
            getattr(nvd, "persist_daily_nvd_cve_entry_gate_snapshot", None)
        ),
        "historical_daily_pit_parity_complete": False,
        "historical_daily_pit_parity_caveat": (
            "The historical resolver can cancel at a same-day open after a "
            "pre-open trigger, while the date-only daily snapshot emits only "
            "the next configured session. No production parity is claimed."
        ),
        "trade_enabled": False,
        "live_order_path_enabled": False,
    }
    canonical_gate4_passed = gate4["checks"]["all_pass"]
    canonical_full_stack_passed = all(
        (
            gate1_checks["all_windows_exact"],
            gate2["all_windows_pass"],
            gate3["all_windows_pass"],
            canonical_gate4_passed,
            addon_audit["all_windows_clean"],
        )
    )
    strict_full_stack_passed = all(
        (
            canonical_full_stack_passed,
            shared_contract["daily_default_off_snapshot_callable"],
            shared_contract["historical_daily_pit_parity_complete"],
            not shared_contract["trade_enabled"],
        )
    )
    measurement_valid = (
        gate1_checks["all_windows_exact"]
        and gate2["all_windows_pass"]
        and gate3["all_windows_pass"]
    )
    strict_measurement_valid = (
        measurement_valid
        and addon_audit["all_windows_clean"]
        and shared_contract["historical_daily_pit_parity_complete"]
    )
    if not measurement_valid:
        decision = "blocked_invalid_measurement"
    elif not canonical_gate4_passed:
        decision = "rejected"
    elif not addon_audit["all_windows_clean"]:
        decision = "rejected_attribution_contamination"
    elif not strict_full_stack_passed:
        decision = "blocked_incomplete_full_stack"
    else:
        decision = "accepted_default_off"

    artifact = {
        "schema": "nvd_cve_cluster_entry_gate_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "accepted_alpha": decision == "accepted_default_off",
        "live_ready": False,
        "hypothesis": (
            "A point-in-time cluster of at least three distinct CVEs first "
            "mapped to a listed issuer during NVD Initial Analysis predicts "
            "near-term remediation and reputation drag, so excluding that "
            "issuer from new long entries for the next five trading sessions "
            "should improve cash-feasible strategy expected value."
        ),
        "single_causal_variable": (
            "NVD Initial Analysis issuer UTC-Monday-week cluster >=3 activates "
            "a next-session five-trading-session long-entry exclusion"
        ),
        "locked_policy": source["summary"]["cluster_rule"],
        "source_archive_mode": archive_mode,
        "source": source,
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
        },
        "verdicts": {
            "canonical_gate4_passed": canonical_gate4_passed,
            "canonical_full_stack_passed": canonical_full_stack_passed,
            "strict_full_stack_passed": strict_full_stack_passed,
            "measurement_valid": measurement_valid,
            "strict_measurement_valid": strict_measurement_valid,
            "decision": decision,
        },
        "addon_attribution": addon_audit,
        "windows": windows,
        "aggregate": {
            "before": before_aggregate,
            "after": after_aggregate,
            "delta": aggregate_delta,
        },
        "shared_paper_contract": shared_contract,
        "production_impact": {
            "default_off": True,
            "live_or_default_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "add_on_changes_allowed": False,
            "helper_live_claimed": False,
            "rejected_helper_status": (
                "No live or production-alpha claim is permitted after a failed "
                "Gate 4 or attribution check."
            ),
        },
        "live_realistic_execution_envelope": {
            "notional_and_capital": (
                "Unchanged cash-feasible Gate-1 sizing and capital ledger; the "
                "gate can only cancel a not-yet-filled core entry."
            ),
            "liquidity_slippage_and_costs": (
                "Unchanged accepted fill, liquidity-aware slippage, and round-trip "
                "cost contracts."
            ),
            "portfolio_competition": (
                "An excluded entry retains cash and may change later slot competition; "
                "that downstream effect is included in the after replay."
            ),
            "max_positions_and_exposure": (
                "Existing max-position and sector constraints are unchanged."
            ),
            "order_semantics": (
                "Resolver evaluates the signal's next-open fill session; an excluded "
                "fill is cancelled before cash debit or Position construction."
            ),
            "kill_switch": (
                "Keep NVD CVE entry admission trade_enabled=false; any promotion "
                "requires an explicit enable flag and an immediate disable path."
            ),
            "source_failure": (
                "Archive hash, pagination, schema, or PIT validation failure aborts "
                "measurement; default-off daily operation cannot change orders."
            ),
            "live_ready": False,
        },
        "nearby_prior": {
            "exp-20260705-014": (
                "CISA KEV used a much narrower known-exploited subset and did not "
                "test this NVD Initial Analysis cluster source."
            ),
            "exp-20260715-010": "Active cash-feasible Gate-1 comparator.",
        },
        "known_limitations": [
            "The frozen current-roster security master does not recover delisted issuers.",
            (
                "Issuer mapping is a static, fail-closed vendor-to-ticker map, "
                "not an effective-dated ownership history; unmapped CPE vendors "
                "do not enter the gate and the map is not suitable for broader reuse."
            ),
            (
                "All-mapped-vendor density clears the source-level bars, but "
                "density within the frozen 47-name Gate-4 base fails the "
                ">=10-ticker bar in every window and the <=30% top-one bar in "
                "old and late."
            ),
            (
                "Date-only daily snapshot parity is incomplete for pre-open "
                "triggers that the historical fill-time resolver can apply at "
                "the same session open; strict measurement validity is not claimed."
            ),
            (
                "The late window changed one AMZN add-on checkpoint, so only "
                "the mid and old windows have clean entry-only attribution."
            ),
            "Acceptance is default-off only; broker/order-path parity is not claimed.",
        ],
        "reproduction": {
            "refresh_command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260717_007_nvd_cve_cluster_entry_gate.py "
                "--refresh-source"
            ),
            "archive_command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260717_007_nvd_cve_cluster_entry_gate.py "
                f"--source-archive {manifest_path}"
            ),
        },
    }
    gate1._atomic_write_json(
        BEFORE_FILE,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "active_cash_feasible_static_entry_anchor",
            "source": _path_text(ACTIVE_BASELINE),
            "expected_value_score": before_aggregate["expected_value_score_sum"],
            "total_pnl": before_aggregate["total_pnl_sum"],
            "total_trades": before_aggregate["trade_count_sum"],
            "survival_rate": before_aggregate["minimum_survival_rate"],
            "max_drawdown_pct": before_aggregate["worst_max_drawdown_pct"],
            "gate1_identity": gate1_checks,
            "aggregate": before_aggregate,
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
            "role": "nvd_cluster3_next_session_5d_entry_gate",
            "decision": decision,
            "source_manifest": source["manifest"],
            "expected_value_score": after_aggregate["expected_value_score_sum"],
            "total_pnl": after_aggregate["total_pnl_sum"],
            "total_trades": after_aggregate["trade_count_sum"],
            "survival_rate": after_aggregate["minimum_survival_rate"],
            "max_drawdown_pct": after_aggregate["worst_max_drawdown_pct"],
            "aggregate": after_aggregate,
            "windows": {
                label: {
                    "headline": windows[label]["after"],
                    "artifact": windows[label]["after_artifact"],
                    "gate2": gate2[label],
                    "addon_attribution": addon_audit[label],
                }
                for label in windows
            },
        },
    )
    gate1._atomic_write_json(ARTIFACT, artifact)
    return artifact


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--refresh-source",
        action="store_true",
        help="Fetch and archive a fresh verified NVD Change History source bundle.",
    )
    source.add_argument(
        "--source-archive",
        type=Path,
        help="Replay an existing archive manifest (or directory containing it).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    artifact = build_artifact(_parse_args(argv))
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "verdicts": artifact["verdicts"],
                "aggregate": artifact["aggregate"],
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
