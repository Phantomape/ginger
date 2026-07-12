"""Freeze and verify the post-MTM three-window Gate-1 baseline.

The runner intentionally changes no strategy policy.  It captures the two
otherwise mutable behavior inputs (the current universe and yfinance earnings
calendar), freezes the earnings-snapshot map, and then replays all canonical
windows twice.  The baseline is published only when source/data fingerprints
remain stable and both replay identities are exactly equal.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from backtester import (  # noqa: E402
    BacktestEngine,
    CANCEL_GAP_PCT,
    DEFAULT_CONFIG,
    _persistable_backtest_result,
)
from data_layer import get_universe  # noqa: E402
from earnings_assets import is_non_earnings_asset  # noqa: E402
from fill_model import (  # noqa: E402
    IMPACT_BPS,
    LIQUID_REF_ADV_USD,
    MAX_LEG_BPS,
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_STOP,
    SLIPPAGE_BPS_TARGET,
)
from ohlcv_warehouse import snapshot_source_key  # noqa: E402
from operator_input_paths import open_positions_path  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


EXPERIMENT_ID = "exp-20260712-015"
PROTOCOL_ID = "post_mtm_gate1_frozen_inputs_v1"
WAREHOUSE = ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
OLD_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
FROZEN_INPUTS = EXP_DIR / "frozen_behavior_inputs.json"
SOURCE_IDENTITY = EXP_DIR / "source_identity.json"
SOURCE_BUNDLE = EXP_DIR / "source_bundle.zip"
BEFORE_MEASUREMENT = EXP_DIR / "before_measurement.json"
AFTER_MEASUREMENT = EXP_DIR / "after_measurement.json"
REPLAY_IDENTITY = EXP_DIR / "double_replay_identity.json"
BASELINE_DIR = ROOT / "data" / "backtests" / "post_mtm_20260712"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

RUN_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
    "ATR_STOP_DAILY_RECOMPUTE": False,
    "ATR_STOP_TRIGGER_ON_CLOSE": False,
    "ATR_STOP_EXIT_NEXT_OPEN": False,
}

WINDOWS = (
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
)

RESULT_METRICS = (
    "period",
    "trading_days",
    "total_trades",
    "wins",
    "losses",
    "win_rate",
    "total_pnl",
    "sharpe",
    "sharpe_daily",
    "max_drawdown_pct",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "expected_value_score",
    "by_strategy",
    "benchmarks",
)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _source_paths() -> list[Path]:
    paths: list[Path] = []
    for path in QUANT.rglob("*.py"):
        rel_parts = path.relative_to(QUANT).parts
        if "__pycache__" in rel_parts:
            continue
        if "experiments" in rel_parts and path.resolve() != Path(__file__).resolve():
            continue
        if path.name.startswith("test_"):
            continue
        paths.append(path)
    for name in ("requirements.txt", "pyproject.toml"):
        path = ROOT / name
        if path.exists():
            paths.append(path)
    return sorted(set(paths), key=lambda path: _repo_rel(path))


def _source_manifest() -> dict[str, Any]:
    files = {
        _repo_rel(path): {"sha256": _file_sha256(path), "bytes": path.stat().st_size}
        for path in _source_paths()
    }
    source_tree_sha256 = _stable_hash(files)
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all", "--", "quant")
    return {
        "schema": "post_mtm_source_identity_v1",
        "git_head": _git_text("rev-parse", "HEAD"),
        "git_branch": _git_text("rev-parse", "--abbrev-ref", "HEAD"),
        "git_quant_status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
        "git_quant_status_line_count": len(status.splitlines()) if status else 0,
        "git_worktree_clean_for_quant": not bool(status),
        "source_tree_sha256": source_tree_sha256,
        "file_count": len(files),
        "files": files,
    }


def _write_source_bundle(manifest: dict[str, Any]) -> dict[str, Any]:
    SOURCE_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{SOURCE_BUNDLE.name}.", suffix=".tmp", dir=SOURCE_BUNDLE.parent
    )
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path in _source_paths():
                info = zipfile.ZipInfo(_repo_rel(path), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes())
            info = zipfile.ZipInfo("SOURCE_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, _json_bytes(manifest) + b"\n")
        os.replace(tmp_name, SOURCE_BUNDLE)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return {
        "path": _repo_rel(SOURCE_BUNDLE),
        "sha256": _file_sha256(SOURCE_BUNDLE),
        "bytes": SOURCE_BUNDLE.stat().st_size,
        "recovery_contract": (
            "The normalized bundle contains every non-test, non-experiment quant Python "
            "source file plus this runner, including untracked MTM/inference sources."
        ),
    }


def _dependency_identity() -> dict[str, Any]:
    packages = {}
    for name in ("numpy", "pandas", "scipy", "yfinance"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    payload = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }
    return {**payload, "sha256": _stable_hash(payload)}


def _cost_contract(resolved_config: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "initial_capital": resolved_config["INITIAL_CAPITAL"],
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "slippage_bps_entry": SLIPPAGE_BPS_ENTRY,
        "slippage_bps_stop": SLIPPAGE_BPS_STOP,
        "slippage_bps_target": SLIPPAGE_BPS_TARGET,
        "liquidity_aware_slippage": resolved_config["LIQUIDITY_AWARE_SLIPPAGE"],
        "liquid_ref_adv_usd": LIQUID_REF_ADV_USD,
        "impact_bps": IMPACT_BPS,
        "max_leg_bps": MAX_LEG_BPS,
        "upside_gap_cancel_pct": CANCEL_GAP_PCT,
        "adverse_gap_cancel_pct": resolved_config["ADVERSE_GAP_CANCEL_PCT"],
        "final_liquidation": "last_close_target_slippage_then_round_trip_cost",
    }
    return {**payload, "sha256": _stable_hash(payload)}


def _serialize_calendar(calendar: dict[str, Any]) -> dict[str, list[str]]:
    return {
        str(ticker): sorted({str(value)[:10] for value in (values or [])})
        for ticker, values in sorted(calendar.items())
    }


def _capture_frozen_inputs() -> dict[str, Any]:
    universe = list(get_universe())
    probe = BacktestEngine(
        universe,
        start=WINDOWS[0]["start"],
        end=WINDOWS[0]["end"],
        config=RUN_CONFIG,
        ohlcv_warehouse_path=str(WAREHOUSE),
        ohlcv_warehouse_snapshot_source=WINDOWS[0]["snapshot"],
        replay_llm=False,
        replay_news=False,
        include_pilot_sleeve=False,
        require_non_ohlcv=False,
        include_oracle_diagnostics=False,
    )
    calendar = _serialize_calendar(probe._download_earnings_calendar())
    max_snapshot_key = max(spec["end"].replace("-", "") for spec in WINDOWS)
    earnings_snapshots = {
        key: value
        for key, value in sorted(probe._earnings_snapshots.items())
        if key <= max_snapshot_key
    }
    behavior = {
        "universe": universe,
        "earnings_calendar": calendar,
        "earnings_snapshots": earnings_snapshots,
    }
    backtest_universe = list(probe._backtest_data_universe())
    eligible = [ticker for ticker in backtest_universe if not is_non_earnings_asset(ticker)]
    populated = [ticker for ticker in eligible if calendar.get(ticker)]
    path = open_positions_path()
    provenance = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "calendar_provider": "yfinance.Ticker.get_earnings_dates(limit=20)",
        "open_positions_path": _repo_rel(path) if path.exists() else str(path),
        "open_positions_sha256": _file_sha256(path) if path.exists() else None,
        "eligible_earnings_tickers": len(eligible),
        "populated_earnings_tickers": len(populated),
        "calendar_coverage_fraction": len(populated) / len(eligible) if eligible else 1.0,
        "earnings_snapshot_count": len(earnings_snapshots),
    }
    payload = {
        "schema": "post_mtm_frozen_behavior_inputs_v1",
        "experiment_id": EXPERIMENT_ID,
        "behavior": behavior,
        "behavior_sha256": _stable_hash(behavior),
        "provenance": provenance,
    }
    _atomic_write_json(FROZEN_INPUTS, payload)
    return payload


def _load_or_capture_frozen_inputs(refresh: bool) -> dict[str, Any]:
    if refresh or not FROZEN_INPUTS.exists():
        payload = _capture_frozen_inputs()
    else:
        payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Frozen behavior input schema is missing or incompatible")
    if payload.get("behavior_sha256") != _stable_hash(payload.get("behavior")):
        raise RuntimeError("Frozen behavior input content does not match its declared hash")
    return payload


def _calendar_dates(payload: dict[str, Any]) -> dict[str, list[date]]:
    return {
        ticker: [date.fromisoformat(value) for value in values]
        for ticker, values in payload["behavior"]["earnings_calendar"].items()
    }


def _warehouse_rowset(spec: dict[str, str], universe: list[str]) -> dict[str, Any]:
    requested = sorted(set(universe + ["SPY", "QQQ"]))
    lookback = int({**DEFAULT_CONFIG, **RUN_CONFIG}["LOOKBACK_CALENDAR_DAYS"])
    query_start = (date.fromisoformat(spec["start"]) - timedelta(days=lookback)).isoformat()
    query_end = (date.fromisoformat(spec["end"]) + timedelta(days=5)).isoformat()
    source = snapshot_source_key(spec["snapshot"])
    placeholders = ",".join("?" for _ in requested)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv_snapshot_versions
        WHERE snapshot_source = ?
          AND ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    with sqlite3.connect(WAREHOUSE, timeout=30.0) as conn:
        rows = [list(row) for row in conn.execute(sql, [source, *requested, query_start, query_end])]
    present = sorted({str(row[0]) for row in rows})
    behavior_payload = {
        "schema": "warehouse_snapshot_behavior_rows_v1",
        "table": "ohlcv_snapshot_versions",
        "snapshot_source": source,
        "requested_tickers": requested,
        "query_start": query_start,
        "query_end": query_end,
        "columns": ["ticker", "date", "open", "high", "low", "close", "volume"],
        "rows": rows,
    }
    return {
        "snapshot_source": source,
        "snapshot_file": spec["snapshot"],
        "snapshot_file_sha256": _file_sha256(ROOT / spec["snapshot"]),
        "warehouse_rowset_sha256": _stable_hash(behavior_payload),
        "row_count": len(rows),
        "ticker_count": len(present),
        "date_min": min((str(row[1]) for row in rows), default=None),
        "date_max": max((str(row[1]) for row in rows), default=None),
        "missing_tickers": sorted(set(requested) - set(present)),
        "query_start": query_start,
        "query_end": query_end,
    }


def _input_stage(frozen: dict[str, Any]) -> dict[str, Any]:
    behavior = frozen["behavior"]
    resolved_config = {**DEFAULT_CONFIG, **RUN_CONFIG}
    windows = {
        spec["label"]: _warehouse_rowset(spec, behavior["universe"])
        for spec in WINDOWS
    }
    payload = {
        "frozen_behavior_sha256": frozen["behavior_sha256"],
        "frozen_behavior_file_sha256": _file_sha256(FROZEN_INPUTS),
        "universe_sha256": _stable_hash(behavior["universe"]),
        "resolved_config_sha256": _stable_hash(resolved_config),
        "cost_contract_sha256": _cost_contract(resolved_config)["sha256"],
        "warehouse_windows": windows,
    }
    return {**payload, "input_stage_sha256": _stable_hash(payload)}


def _spy_dates(spec: dict[str, str]) -> list[str]:
    source = snapshot_source_key(spec["snapshot"])
    with sqlite3.connect(WAREHOUSE, timeout=30.0) as conn:
        return [
            str(row[0])
            for row in conn.execute(
                """
                SELECT date FROM ohlcv_snapshot_versions
                WHERE snapshot_source = ? AND ticker = 'SPY'
                  AND date >= ? AND date <= ? ORDER BY date
                """,
                (source, spec["start"], spec["end"]),
            )
        ]


def _effective_earnings_identity(
    engine: BacktestEngine,
    spec: dict[str, str],
    universe: list[str],
    calendar: dict[str, list[date]],
) -> dict[str, Any]:
    rows = []
    for day_text in _spy_dates(spec):
        today = datetime.fromisoformat(day_text)
        for ticker in universe:
            rows.append(
                [
                    day_text,
                    ticker,
                    engine._earnings_dict_for(today, calendar.get(ticker, []), ticker),
                ]
            )
    payload = {
        "schema": "effective_earnings_inputs_v1",
        "window": spec["label"],
        "rows": rows,
    }
    return {"sha256": _stable_hash(payload), "row_count": len(rows)}


def _result_identity(result: dict[str, Any]) -> dict[str, Any]:
    metrics = {key: result.get(key) for key in RESULT_METRICS}
    trades = result.get("trades") or []
    inference = result.get("sharpe_inference") or {}
    psr = inference.get("psr") or {}
    dsr = inference.get("dsr") or {}
    return_series = inference.get("return_series") or []
    recomputed_return_series_sha256 = _stable_hash(
        {"schema": "dated_periodic_return_series_v1", "rows": return_series}
    )
    inference_contract_passed = (
        int(inference.get("schema_version") or 0) >= 1
        and inference.get("status") == "computable"
        and psr.get("status") == "computable"
        and dsr.get("status") == "not_computable"
        and bool(inference.get("return_series_sha256"))
        and inference.get("return_series_sha256")
        == recomputed_return_series_sha256
        and inference.get("sample_count") == result.get("trading_days", 0) - 1
        and len(return_series) == inference.get("sample_count")
    )
    identity = {
        "result_metrics_sha256": _stable_hash(metrics),
        "trade_rows_sha256": _stable_hash(trades),
        "trade_multiset_sha256": _stable_hash(sorted(_stable_hash(row) for row in trades)),
        "daily_return_series_sha256": inference.get("return_series_sha256"),
        "daily_return_series_sha256_recomputed": recomputed_return_series_sha256,
        "metrics": metrics,
        "trade_count": len(trades),
        "sharpe_inference_contract_passed": inference_contract_passed,
        "sharpe_inference_schema_version": inference.get("schema_version"),
        "psr_status": psr.get("status"),
        "psr_probability": psr.get("probability"),
        "dsr_status": dsr.get("status"),
    }
    identity["behavior_result_sha256"] = _stable_hash(
        {
            "result_metrics_sha256": identity["result_metrics_sha256"],
            "trade_rows_sha256": identity["trade_rows_sha256"],
            "daily_return_series_sha256": identity["daily_return_series_sha256"],
        }
    )
    return identity


def _run_window(
    spec: dict[str, str], frozen: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = _calendar_dates(frozen)
    engine = BacktestEngine(
        list(behavior["universe"]),
        start=spec["start"],
        end=spec["end"],
        config=RUN_CONFIG,
        ohlcv_warehouse_path=str(WAREHOUSE),
        ohlcv_warehouse_snapshot_source=spec["snapshot"],
        replay_llm=False,
        replay_news=False,
        include_pilot_sleeve=False,
        require_non_ohlcv=False,
        include_oracle_diagnostics=False,
    )
    engine._earnings_snapshots = behavior["earnings_snapshots"]
    engine._download_earnings_calendar = lambda: {
        ticker: list(values) for ticker, values in calendar.items()
    }
    effective = _effective_earnings_identity(
        engine, spec, behavior["universe"], calendar
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    identity = _result_identity(result)
    identity["effective_earnings_inputs_sha256"] = effective["sha256"]
    identity["effective_earnings_row_count"] = effective["row_count"]
    identity["resolved_config_sha256"] = _stable_hash(engine.config)
    identity["window"] = {
        "label": spec["label"],
        "start": spec["start"],
        "end": spec["end"],
        "snapshot": spec["snapshot"],
    }
    return result, identity


def _run_pass(name: str, frozen: dict[str, Any]) -> dict[str, Any]:
    records = {}
    for spec in WINDOWS:
        result, identity = _run_window(spec, frozen)
        result_path = EXP_DIR / f"replay_{name}_{spec['label']}.json"
        _atomic_write_json(result_path, _persistable_backtest_result(result))
        records[spec["label"]] = {
            "identity": identity,
            "result_path": _repo_rel(result_path),
            "result_file_sha256": _file_sha256(result_path),
            "result": result,
        }
    return records


def _window_identity_for_compare(record: dict[str, Any]) -> dict[str, Any]:
    return record["identity"]


def _write_before_measurement() -> None:
    old = json.loads(OLD_BASELINE.read_text(encoding="utf-8"))
    _atomic_write_json(
        BEFORE_MEASUREMENT,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "pre_mtm_archived_baseline",
            "source": _repo_rel(OLD_BASELINE),
            "source_sha256": _file_sha256(OLD_BASELINE),
            "cross_protocol_comparison_allowed": False,
            "reason": (
                "The archived Sharpe, EV, and drawdown were measured before the daily "
                "mark-to-market/final-liquidation repair."
            ),
            "archived_summary": old,
        },
    )


def _assert_republish_allowed(
    source_identity: dict[str, Any],
    *,
    refresh_inputs: bool,
    replace_baseline: bool,
) -> None:
    """Keep this experiment's published baseline immutable by default."""
    if replace_baseline:
        ticket = json.loads(TICKET.read_text(encoding="utf-8-sig"))
        if ticket.get("status") not in {"proposed", "claimed", "running"}:
            raise RuntimeError(
                "--replace-baseline is disabled after experiment closeout; reserve a "
                "new experiment instead"
            )
        return
    if not BASELINE_SUMMARY.exists():
        return
    existing = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    existing_source = (existing.get("source_identity") or {}).get(
        "source_tree_sha256"
    )
    if existing_source != source_identity["source_tree_sha256"]:
        raise RuntimeError(
            "Refusing to overwrite the published baseline with a different source "
            "tree. Reserve a new experiment; --replace-baseline is only for the "
            "still-open construction of exp-20260712-015."
        )
    if refresh_inputs:
        raise RuntimeError(
            "Refusing to refresh behavior inputs under an existing baseline identity. "
            "Reserve a new experiment for a new input capture."
        )
    if not FROZEN_INPUTS.exists():
        raise RuntimeError("Published baseline is missing its frozen input artifact")
    frozen = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    existing_behavior = (existing.get("frozen_behavior_inputs") or {}).get(
        "behavior_sha256"
    )
    if frozen.get("behavior_sha256") != existing_behavior:
        raise RuntimeError(
            "Refusing to overwrite the published baseline with different frozen inputs"
        )


def _assert_existing_context_matches(
    input_identity: dict[str, Any],
    dependencies: dict[str, Any],
    *,
    replace_baseline: bool,
) -> None:
    if replace_baseline or not BASELINE_SUMMARY.exists():
        return
    existing = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    if (existing.get("input_identity") or {}).get("input_stage_sha256") != input_identity.get(
        "input_stage_sha256"
    ):
        raise RuntimeError(
            "Refusing to overwrite the published baseline after warehouse/config/cost "
            "input identity changed"
        )
    if (existing.get("dependency_identity") or {}).get("sha256") != dependencies.get(
        "sha256"
    ):
        raise RuntimeError(
            "Refusing to overwrite the published baseline after dependency identity changed"
        )


def _assert_existing_results_match(
    pass_b: dict[str, Any], *, replace_baseline: bool
) -> None:
    if replace_baseline or not BASELINE_SUMMARY.exists():
        return
    existing = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    for row in existing.get("windows") or []:
        label = row.get("label")
        manifest_path = row.get("manifest_path")
        if label not in pass_b or not manifest_path:
            raise RuntimeError("Published baseline is missing a comparable window manifest")
        manifest = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
        if manifest.get("result_identity") != pass_b[label]["identity"]:
            raise RuntimeError(
                f"Refusing to overwrite {label}: replay result identity changed"
            )


def _publish_baseline(
    pass_b: dict[str, Any],
    source_identity: dict[str, Any],
    source_bundle: dict[str, Any],
    input_identity: dict[str, Any],
    frozen: dict[str, Any],
    dependencies: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved_config = {**DEFAULT_CONFIG, **RUN_CONFIG}
    cost = _cost_contract(resolved_config)
    rows = []
    for spec in WINDOWS:
        label = spec["label"]
        record = pass_b[label]
        target = BASELINE_DIR / f"{label}_{EXPERIMENT_ID}.json"
        manifest_target = BASELINE_DIR / f"{label}_{EXPERIMENT_ID}_manifest.json"
        _atomic_write_json(target, _persistable_backtest_result(record["result"]))
        artifact = {
            "schema": "post_mtm_gate1_window_baseline_v1",
            "experiment_id": EXPERIMENT_ID,
            "protocol_id": PROTOCOL_ID,
            "baseline_role": "active_post_mtm_gate1_reference",
            "window": record["identity"]["window"],
            "source_tree_sha256": source_identity["source_tree_sha256"],
            "source_bundle_sha256": source_bundle["sha256"],
            "frozen_behavior_sha256": frozen["behavior_sha256"],
            "input_stage_sha256": input_identity["input_stage_sha256"],
            "warehouse": input_identity["warehouse_windows"][label],
            "resolved_config": resolved_config,
            "resolved_config_sha256": _stable_hash(resolved_config),
            "cost_contract": cost,
            "dependency_identity": dependencies,
            "result_identity": record["identity"],
            "result_path": _repo_rel(target),
            "result_artifact_sha256": _file_sha256(target),
        }
        artifact["baseline_manifest_sha256"] = _stable_hash(
            {
                "schema": "canonical_baseline_manifest_v1",
                "result_metrics_sha256": record["identity"]["result_metrics_sha256"],
                "trade_rows_sha256": record["identity"]["trade_rows_sha256"],
                "daily_return_series_sha256": record["identity"]["daily_return_series_sha256"],
                "warehouse_rowset_sha256": input_identity["warehouse_windows"][label][
                    "warehouse_rowset_sha256"
                ],
                "universe_sha256": input_identity["universe_sha256"],
                "config_sha256": input_identity["resolved_config_sha256"],
                "effective_earnings_inputs_sha256": record["identity"][
                    "effective_earnings_inputs_sha256"
                ],
                "source_tree_sha256": source_identity["source_tree_sha256"],
                "source_bundle_sha256": source_bundle["sha256"],
            }
        )
        _atomic_write_json(manifest_target, artifact)
        metrics = record["identity"]["metrics"]
        inference = record["result"].get("sharpe_inference") or {}
        rows.append(
            {
                "label": label,
                "start": spec["start"],
                "end": spec["end"],
                "path": _repo_rel(target),
                "artifact_sha256": _file_sha256(target),
                "manifest_path": _repo_rel(manifest_target),
                "manifest_sha256": _file_sha256(manifest_target),
                "baseline_manifest_sha256": artifact["baseline_manifest_sha256"],
                "source": spec["snapshot"],
                "expected_value_score": metrics["expected_value_score"],
                "sharpe_daily": metrics["sharpe_daily"],
                "sharpe_daily_full_precision": inference.get("annualized_sharpe"),
                "total_pnl": metrics["total_pnl"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "win_rate": metrics["win_rate"],
                "trade_count": metrics["total_trades"],
                "signals_generated": metrics["signals_generated"],
                "signals_survived": metrics["signals_survived"],
                "survival_rate": metrics["survival_rate"],
                "psr_probability": record["identity"]["psr_probability"],
                "dsr_status": record["identity"]["dsr_status"],
                "trade_rows_sha256": record["identity"]["trade_rows_sha256"],
                "daily_return_series_sha256": record["identity"][
                    "daily_return_series_sha256"
                ],
            }
        )
    aggregate = {
        "expected_value_score_sum": sum(row["expected_value_score"] for row in rows),
        "total_pnl_sum": round(sum(row["total_pnl"] for row in rows), 2),
        "trade_count_sum": sum(row["trade_count"] for row in rows),
        "positive_ev_windows": sum(row["expected_value_score"] > 0 for row in rows),
        "minimum_survival_rate": min(row["survival_rate"] for row in rows),
        "worst_max_drawdown_pct": max(row["max_drawdown_pct"] for row in rows),
    }
    return rows, aggregate


def build_artifact(
    *, refresh_inputs: bool = False, replace_baseline: bool = False
) -> dict[str, Any]:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    source_pre = _source_manifest()
    _assert_republish_allowed(
        source_pre,
        refresh_inputs=refresh_inputs,
        replace_baseline=replace_baseline,
    )
    source_bundle = _write_source_bundle(source_pre)
    _atomic_write_json(
        SOURCE_IDENTITY,
        {**source_pre, "source_bundle": source_bundle},
    )
    frozen = _load_or_capture_frozen_inputs(refresh_inputs)
    capture_coverage = frozen["provenance"].get("calendar_coverage_fraction", 0.0)
    source_after_capture = _source_manifest()
    input_pre = _input_stage(frozen)
    dependencies = _dependency_identity()
    _assert_existing_context_matches(
        input_pre, dependencies, replace_baseline=replace_baseline
    )
    pass_a = _run_pass("a", frozen)
    source_after_a = _source_manifest()
    input_after_a = _input_stage(frozen)
    pass_b = _run_pass("b", frozen)
    source_after_b = _source_manifest()
    input_after_b = _input_stage(frozen)
    _assert_existing_results_match(pass_b, replace_baseline=replace_baseline)

    source_stage_hashes = [
        stage["source_tree_sha256"]
        for stage in (source_pre, source_after_capture, source_after_a, source_after_b)
    ]
    input_stage_hashes = [
        stage["input_stage_sha256"]
        for stage in (input_pre, input_after_a, input_after_b)
    ]
    source_stable = len(set(source_stage_hashes)) == 1
    input_stable = len(set(input_stage_hashes)) == 1
    per_window_equal = {
        spec["label"]: _window_identity_for_compare(pass_a[spec["label"]])
        == _window_identity_for_compare(pass_b[spec["label"]])
        for spec in WINDOWS
    }
    inference_passed = all(
        pass_b[spec["label"]]["identity"]["sharpe_inference_contract_passed"]
        for spec in WINDOWS
    )
    calendar_capture_passed = capture_coverage >= 0.75
    accepted = (
        source_stable
        and input_stable
        and all(per_window_equal.values())
        and inference_passed
        and calendar_capture_passed
        and source_bundle["sha256"] == _file_sha256(SOURCE_BUNDLE)
    )

    rows: list[dict[str, Any]] = []
    aggregate: dict[str, Any] = {}
    if accepted:
        rows, aggregate = _publish_baseline(
            pass_b,
            source_pre,
            source_bundle,
            input_pre,
            frozen,
            dependencies,
        )

    replay_identity = {
        "schema": "post_mtm_double_replay_identity_v1",
        "experiment_id": EXPERIMENT_ID,
        "source_stage_hashes": source_stage_hashes,
        "input_stage_hashes": input_stage_hashes,
        "source_stable": source_stable,
        "input_stable": input_stable,
        "per_window_exact_identity": per_window_equal,
        "pass_a": {label: row["identity"] for label, row in pass_a.items()},
        "pass_b": {label: row["identity"] for label, row in pass_b.items()},
    }
    _atomic_write_json(REPLAY_IDENTITY, replay_identity)
    _write_before_measurement()
    artifact = {
        "schema": "post_mtm_gate1_baseline_summary_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "accepted_measurement_repair" if accepted else "blocked",
        "protocol_id": PROTOCOL_ID,
        "warehouse": _repo_rel(WAREHOUSE),
        "baseline_role": (
            "active_post_mtm_gate1_reference" if accepted else "provisional_diagnostic"
        ),
        "clean_release_ready": False,
        "clean_release_blocker": (
            "The exact behavior source is recoverable from the source bundle but is "
            "not yet represented by a clean committed Git tree."
        ),
        "not_the_repaired_20260604_champion": True,
        "old_baseline_role": "pre_mtm_archived",
        "old_baseline": _repo_rel(OLD_BASELINE),
        "cross_protocol_ev_sharpe_drawdown_comparison_allowed": False,
        "strategy_or_order_behavior_changed": False,
        "source_identity": {
            "git_head": source_pre["git_head"],
            "git_branch": source_pre["git_branch"],
            "git_worktree_clean_for_quant": source_pre["git_worktree_clean_for_quant"],
            "source_tree_sha256": source_pre["source_tree_sha256"],
            "source_stage_hashes": source_stage_hashes,
            "source_stable": source_stable,
            "source_bundle": source_bundle,
        },
        "input_identity": input_pre,
        "input_stage_hashes": input_stage_hashes,
        "input_stable": input_stable,
        "frozen_behavior_inputs": {
            "path": _repo_rel(FROZEN_INPUTS),
            "file_sha256": _file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
            "universe": frozen["behavior"]["universe"],
            "universe_count": len(frozen["behavior"]["universe"]),
            "universe_sha256": _stable_hash(frozen["behavior"]["universe"]),
            "calendar_coverage_fraction": capture_coverage,
            "calendar_capture_passed": calendar_capture_passed,
            "earnings_calendar_sha256": _stable_hash(
                frozen["behavior"]["earnings_calendar"]
            ),
            "earnings_snapshots_sha256": _stable_hash(
                frozen["behavior"]["earnings_snapshots"]
            ),
        },
        "resolved_config": {**DEFAULT_CONFIG, **RUN_CONFIG},
        "resolved_config_sha256": _stable_hash({**DEFAULT_CONFIG, **RUN_CONFIG}),
        "cost_contract": _cost_contract({**DEFAULT_CONFIG, **RUN_CONFIG}),
        "dependency_identity": dependencies,
        "double_replay": {
            "identity_artifact": _repo_rel(REPLAY_IDENTITY),
            "per_window_exact_identity": per_window_equal,
            "all_exact": all(per_window_equal.values()),
            "sharpe_inference_contract_passed": inference_passed,
        },
        "windows": rows,
        "aggregate": aggregate,
        "production_impact": (
            "Measurement artifact only: no entry, exit, ranking, sizing, risk, "
            "candidate, or order path changed."
        ),
        "known_limitations": [
            "The source identity is a recoverable source bundle over a dirty working tree, not a clean release commit.",
            "The captured yfinance earnings calendar is frozen and reproducible but remains the current protocol's historical PIT caveat.",
            "DSR remains not_computable for each single baseline window because a selection trial panel is not supplied.",
        ],
        "alpha_hypothesis_deferred": (
            "After this comparison anchor is frozen, evaluate a genuinely new alpha "
            "hypothesis against it rather than further retuning the DSR threshold."
        ),
    }
    _atomic_write_json(AFTER_MEASUREMENT, artifact)
    if accepted:
        _atomic_write_json(BASELINE_SUMMARY, artifact)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-inputs",
        action="store_true",
        help="Recapture universe/calendar/snapshots instead of reusing the frozen input file.",
    )
    parser.add_argument(
        "--replace-baseline",
        action="store_true",
        help=(
            "Allow replacement only while constructing this still-open experiment. "
            "After closeout, reserve a new experiment instead."
        ),
    )
    args = parser.parse_args()
    artifact = build_artifact(
        refresh_inputs=args.refresh_inputs,
        replace_baseline=args.replace_baseline,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "baseline_summary": (
                    _repo_rel(BASELINE_SUMMARY)
                    if artifact["decision"] == "accepted_measurement_repair"
                    else None
                ),
                "source_stable": artifact["source_identity"]["source_stable"],
                "input_stable": artifact["input_stable"],
                "double_replay_exact": artifact["double_replay"]["all_exact"],
                "calendar_coverage_fraction": artifact["frozen_behavior_inputs"][
                    "calendar_coverage_fraction"
                ],
                "aggregate": artifact["aggregate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if artifact["decision"] == "accepted_measurement_repair" else 2


if __name__ == "__main__":
    raise SystemExit(main())
