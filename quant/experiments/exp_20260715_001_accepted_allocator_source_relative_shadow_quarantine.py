"""exp-20260715-001: source-relative shadow quarantine for the allocator.

The runner has two deliberately separate phases.

``preflight`` builds every allocator source exactly once per canonical window,
then compares current allocator admission with the source quarantine enabled.
Its JSON/stdout surface contains decision semantics only.  Outcome-bearing
source rows remain in memory until all three viability gates pass; only then
are they frozen atomically behind a last-written contract.  ``full`` is
fail-closed: it requires a passing persisted preflight, rebuilds the same
decisions from frozen inputs, and refuses to calculate performance unless the
decision hash is identical.

Both variants use the accepted execution envelope v2.  Only trades whose
fixed exit date is inside the canonical window are binding.  The active
post-MTM Gate-1 artifacts are read rather than silently rerunning a different
core baseline, while the allocator candidate surface uses the broad warehouse
and the broad sector map.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for _path in (QUANT, EXPERIMENTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
from sharpe_inference import (  # noqa: E402
    build_backtest_sharpe_inference,
    evaluate_deflated_sharpe_trial_panel,
)


EXPERIMENT_ID = "exp-20260715-001"
RULE_VERSION = "source_relative_21_session_underwater_quarantine_dual_hwm_v1"
PROTOCOL_ID = "post_mtm_allocator_same_raw_rows_quarantine_gate4_v1"

ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
SECTOR_MAP = ROOT / "data" / "reference" / "broad_market_sector_map.json"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
INPUT_DIR = OUT_DIR / "inputs"
INPUT_CONTRACT = INPUT_DIR / "contract.json"
PREFLIGHT_OUT = OUT_DIR / "preflight.json"
FULL_OUT = OUT_DIR / "full.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    (label, dict(spec)) for label, spec in framework.WINDOWS.items()
)

MIN_AFFECTED_SETTLED_TOTAL = 20
MIN_AFFECTED_SETTLED_PER_WINDOW = 3
MIN_AFFECTED_SOURCE_FAMILIES = 2
MIN_TRIGGER_COUNT = 1
MIN_ADMISSION_SURVIVAL = 0.05
MIN_AGGREGATE_FULL_SYSTEM_EV_IMPROVEMENT = 0.10
MAX_DRAWDOWN_WORSENING = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

INITIAL_CAPITAL = float(framework.overlay_helper.INITIAL_CAPITAL)
_FILE_HASH_CACHE: dict[tuple[str, int, int], str] = {}
_PREFLIGHT_FORBIDDEN_KEY_FRAGMENTS = (
    "pnl",
    "return",
    "expected_value",
    "drawdown",
    "winner",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_hash(path: Path) -> str:
    stat = path.stat()
    cache_key = (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    cached = _FILE_HASH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _FILE_HASH_CACHE[cache_key] = value
    return value


def _repo_rel(path: Path | str) -> str:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    return str(resolved.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected mapping in {_repo_rel(path)}")
    return payload


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                _json_safe(payload),
                handle,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical_bytes(payload)
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(compressed)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected mapping in {_repo_rel(path)}")
    return payload


def _snapshot_input_path(label: str) -> Path:
    return INPUT_DIR / f"{label}_broad_snapshot.json.gz"


def _source_input_path(label: str) -> Path:
    return INPUT_DIR / f"{label}_raw_source_rows.json.gz"


def _code_identity() -> dict[str, Any]:
    runner_path = Path(__file__).resolve()
    helper_path = Path(allocator.__file__).resolve()
    paths = {
        "runner": runner_path,
        "shared_allocator_helper": helper_path,
        "daily_runner": QUANT / "run.py",
        "rolling_corr_peer_shock_source_helper": (
            QUANT / "rolling_corr_peer_shock_paper_sleeve.py"
        ),
        "industry_relative_laggard_source_helper": (
            QUANT / "industry_relative_laggard_repair_paper_sleeve.py"
        ),
        "macro_relief_leadership_source_helper": (
            QUANT / "macro_relief_leadership_paper_sleeve.py"
        ),
        "constants": QUANT / "constants.py",
        "sharpe_inference": QUANT / "sharpe_inference.py",
        "broad_framework_runner": Path(framework.__file__).resolve(),
        "overlay_helper": Path(framework.overlay_helper.__file__).resolve(),
    }
    return {
        name: {"path": _repo_rel(path), "sha256": _file_hash(path)}
        for name, path in paths.items()
    }


def _policy_bundle() -> dict[str, Any]:
    config = allocator._config({})
    accepted_scalars = allocator._source_notional_scalars(config)
    bundle = {
        "initial_capital": INITIAL_CAPITAL,
        "comparison_configs": {
            "before": {"source_quarantine_enabled": False},
            "after": {"source_quarantine_enabled": True},
        },
        "quarantine_rule_version": RULE_VERSION,
        "canonical_windows": [
            {"label": label, **dict(spec)} for label, spec in WINDOWS.items()
        ],
        "source_priority": [
            {"source_family": source_family, **dict(metadata)}
            for source_family, metadata in allocator.SOURCE_PRIORITY.items()
        ],
        "source_notional_scalars": {
            source_family: float(accepted_scalars.get(source_family, 1.0))
            for source_family in allocator.SOURCE_PRIORITY
        },
        "daily_entry_slots": int(config["daily_entry_slots"]),
        "same_ticker_cooldown_days": int(config["same_ticker_cooldown_days"]),
        "hold_days": int(config["hold_days"]),
        "round_trip_cost_pct": float(config["round_trip_cost_pct"]),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "source_shadow_notional_usd": float(
            config["source_shadow_notional_usd"]
        ),
        "source_quarantine_underwater_sessions": int(
            config["source_quarantine_underwater_sessions"]
        ),
        "source_quarantine_benchmarks": list(
            config["source_quarantine_benchmarks"]
        ),
        "execution_envelope": allocator.EXECUTION_ENVELOPE,
        "code_identity": _code_identity(),
    }
    return {**bundle, "policy_sha256": _stable_hash(bundle)}


def _assert_preflight_nonperformance(payload: Any, path: str = "root") -> None:
    """Fail closed if a performance field leaks into decision preflight."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _PREFLIGHT_FORBIDDEN_KEY_FRAGMENTS):
                raise RuntimeError(f"preflight performance field prohibited at {path}.{key}")
            _assert_preflight_nonperformance(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _assert_preflight_nonperformance(value, f"{path}[{index}]")


def _active_baseline_index() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    summary = _load_json(ACTIVE_BASELINE)
    if summary.get("experiment_id") != "exp-20260712-015":
        raise RuntimeError("active Gate-1 baseline experiment identity changed")
    if summary.get("protocol_id") != "post_mtm_gate1_frozen_inputs_v1":
        raise RuntimeError("active Gate-1 protocol identity changed")
    if summary.get("baseline_role") != "active_post_mtm_gate1_reference":
        raise RuntimeError("active Gate-1 baseline role changed")
    rows = summary.get("windows") or []
    index = {
        str(row.get("label")): row
        for row in rows
        if isinstance(row, dict) and row.get("label")
    }
    if set(index) != set(WINDOWS):
        raise RuntimeError("active Gate-1 canonical windows changed")
    return summary, index


def _load_core_result(
    label: str,
    baseline_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = baseline_index[label]
    path = ROOT / str(record["path"])
    actual_hash = _file_hash(path)
    if actual_hash != str(record.get("artifact_sha256") or ""):
        raise RuntimeError(f"{label}: active raw core artifact hash changed")
    result = _load_json(path)
    exact_checks = {
        "total_pnl": result.get("total_pnl"),
        "expected_value_score": result.get("expected_value_score"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
    }
    for key, value in exact_checks.items():
        if value != record.get(key):
            raise RuntimeError(f"{label}: active raw/summary mismatch for {key}")
    inference = result.get("sharpe_inference") or {}
    if inference.get("return_series_sha256") != record.get(
        "daily_return_series_sha256"
    ):
        raise RuntimeError(f"{label}: active daily-series identity changed")
    return result, {
        "path": _repo_rel(path),
        "sha256": actual_hash,
        "daily_series_sha256": inference.get("return_series_sha256"),
        "trade_rows_sha256": record.get("trade_rows_sha256"),
    }


def _broad_rowset_manifest(
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    digest = hashlib.sha256()
    row_count = 0
    dates: list[str] = []
    for ticker in sorted(snapshot):
        for row in snapshot[ticker]:
            day = str(row.get("Date") or row.get("date") or "")[:10]
            canonical = [
                ticker,
                day,
                row.get("Open", row.get("open")),
                row.get("High", row.get("high")),
                row.get("Low", row.get("low")),
                row.get("Close", row.get("close")),
                row.get("Volume", row.get("volume")),
            ]
            digest.update(_canonical_bytes(canonical))
            digest.update(b"\n")
            row_count += 1
            if day:
                dates.append(day)
    return {
        "ticker_count": len(snapshot),
        "row_count": row_count,
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "rowset_sha256": digest.hexdigest(),
    }


def _source_artifact_manifest(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    references: dict[str, str | None] = {}
    for row in source_rows:
        reference = str(row.get("source_artifact") or "").strip()
        if not reference or reference in references:
            continue
        path = ROOT / reference
        references[reference.replace("\\", "/")] = (
            _file_hash(path) if path.exists() and path.is_file() else None
        )
    manifest = {
        "raw_source_row_count": len(source_rows),
        "raw_source_rows_sha256": _stable_hash(source_rows),
        "referenced_artifacts": [
            {"path": path, "sha256": references[path]}
            for path in sorted(references)
        ],
        "missing_reference_count": sum(
            1 for value in references.values() if value is None
        ),
    }
    manifest["manifest_sha256"] = _stable_hash(manifest)
    return manifest


def _semantic_id(row: dict[str, Any]) -> str:
    notional = float(row.get("paper_notional_usd") or row.get("notional_usd") or 0.0)
    scalar = float(row.get("source_notional_scalar") or 1.0)
    parts = (
        str(row.get("source_family") or "unknown"),
        str(row.get("ticker") or "").upper(),
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("entry_date") or "")[:10],
        str(row.get("exit_date") or "")[:10],
        f"notional={notional:.2f}",
        f"scalar={scalar:.6f}",
    )
    return "|".join(parts)


def _settled_rows(rows: list[dict[str, Any]], end: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("exit_date") or "")[:10]
        and str(row.get("exit_date") or "")[:10] <= end
    ]


def _source_counts(
    ids: set[str], rows_by_id: dict[str, dict[str, Any]]
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(rows_by_id[value].get("source_family") or "unknown")
                for value in ids
            ).items()
        )
    )


def _compact_envelope_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_version": audit.get("rule_version"),
        "input_count": int(audit.get("input_trade_count") or 0),
        "kept_count": int(audit.get("kept_trade_count") or 0),
        "skipped_count": int(audit.get("skipped_trade_count") or 0),
    }


def _economic_contract_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = 0
    for row in rows:
        entry_date = str(row.get("entry_date") or "")[:10]
        exit_date = str(row.get("exit_date") or "")[:10]
        net_value = (
            row.get("pnl_pct_net")
            if row.get("pnl_pct_net") is not None
            else row.get("net_return_pct")
        )
        numeric_values = (
            row.get("entry_price"),
            row.get("paper_notional_usd"),
            row.get("pnl"),
            net_value,
        )
        numeric_valid = True
        for value in numeric_values:
            try:
                numeric_valid = numeric_valid and math.isfinite(float(value))
            except (TypeError, ValueError):
                numeric_valid = False
        try:
            positive_contract = (
                float(row.get("entry_price")) > 0.0
                and float(row.get("paper_notional_usd")) > 0.0
            )
        except (TypeError, ValueError):
            positive_contract = False
        target_is_na = row.get("target_price") in (None, "")
        outcome_contract_valid = (
            row.get("outcome_contract_rule_version")
            == allocator.OUTCOME_CONTRACT_RULE_VERSION
            and str(row.get("exit_rule") or "").startswith("time_exit_after_")
            and str(row.get("exit_rule") or "").endswith("_trading_days")
            and row.get("exit_rule_status") == "fixed_time_exit"
            and row.get("target_price_required") is False
            and row.get("target_price_status") == allocator.TARGET_PRICE_STATUS
        )
        if not (
            entry_date
            and exit_date
            and entry_date <= exit_date
            and numeric_valid
            and positive_contract
            and target_is_na
            and outcome_contract_valid
        ):
            invalid += 1
    return {
        "contract_valid": invalid == 0,
        "valid_count": len(rows) - invalid,
        "invalid_count": invalid,
        "fixed_time_exit_target_contract": "not_applicable",
    }


def _validate_snapshot_payload(
    payload: dict[str, Any], *, label: str, spec: dict[str, str]
) -> dict[str, Any]:
    if payload.get("schema") != "allocator_quarantine_frozen_broad_snapshot_v1":
        raise RuntimeError(f"{label}: frozen broad snapshot schema mismatch")
    if payload.get("window") != {
        "label": label,
        "start": spec["start"],
        "end": spec["end"],
    }:
        raise RuntimeError(f"{label}: frozen broad snapshot window mismatch")
    snapshot = payload.get("snapshot")
    sector_entries = payload.get("normalized_sector_entries")
    if not isinstance(snapshot, dict) or not isinstance(sector_entries, dict):
        raise RuntimeError(f"{label}: frozen broad snapshot payload incomplete")
    actual = _broad_rowset_manifest(snapshot)
    expected = payload.get("broad_rowset") or {}
    if actual != expected:
        raise RuntimeError(f"{label}: frozen broad rowset identity mismatch")
    if payload.get("normalized_sector_entries_sha256") != _stable_hash(
        sector_entries
    ):
        raise RuntimeError(f"{label}: frozen sector entries identity mismatch")
    return payload


def _validate_source_payload(
    payload: dict[str, Any],
    *,
    label: str,
    spec: dict[str, str],
    broad_rowset_sha256: str,
    core_sha256: str,
) -> dict[str, Any]:
    if payload.get("schema") != "allocator_quarantine_frozen_raw_source_rows_v1":
        raise RuntimeError(f"{label}: frozen source schema mismatch")
    if payload.get("window") != {
        "label": label,
        "start": spec["start"],
        "end": spec["end"],
    }:
        raise RuntimeError(f"{label}: frozen source window mismatch")
    if payload.get("broad_rowset_sha256") != broad_rowset_sha256:
        raise RuntimeError(f"{label}: frozen source/broad rowset mismatch")
    if payload.get("active_core_sha256") != core_sha256:
        raise RuntimeError(f"{label}: frozen source/core identity mismatch")
    rows = payload.get("source_rows")
    audit = payload.get("source_audit")
    dates = payload.get("trading_dates")
    if not isinstance(rows, list) or not isinstance(audit, dict) or not isinstance(dates, list):
        raise RuntimeError(f"{label}: frozen source payload incomplete")
    source_manifest = payload.get("source_manifest") or {}
    if source_manifest.get("raw_source_row_count") != len(rows):
        raise RuntimeError(f"{label}: frozen source row count mismatch")
    if source_manifest.get("raw_source_rows_sha256") != _stable_hash(rows):
        raise RuntimeError(f"{label}: frozen source rows identity mismatch")
    if payload.get("source_audit_sha256") != _stable_hash(audit):
        raise RuntimeError(f"{label}: frozen source audit identity mismatch")
    if payload.get("source_builder_identity") != _code_identity():
        raise RuntimeError(f"{label}: frozen source builder code identity changed")
    return payload


def _prepare_frozen_inputs(
    *,
    baseline_index: dict[str, dict[str, Any]],
    allow_materialize: bool,
) -> tuple[dict[str, Any], str | None, dict[str, dict[str, Any]]]:
    existing_contract = _load_json(INPUT_CONTRACT) if INPUT_CONTRACT.exists() else None
    current_code = _code_identity()
    active_baseline_sha = _file_hash(ACTIVE_BASELINE)
    if existing_contract is not None:
        if existing_contract.get("schema") != "allocator_quarantine_frozen_inputs_v1":
            raise RuntimeError("frozen input contract schema mismatch")
        if existing_contract.get("code_identity") != current_code:
            raise RuntimeError("frozen input selector/state code identity changed")
        if existing_contract.get("active_baseline_sha256") != active_baseline_sha:
            raise RuntimeError("frozen input active baseline identity changed")
        if existing_contract.get("policy_sha256") != _policy_bundle()["policy_sha256"]:
            raise RuntimeError("frozen input policy identity changed")
    elif not allow_materialize:
        raise RuntimeError("complete frozen input contract is required")

    # An outcome file without the last-written contract is never trusted.  It
    # can only be residue from an interrupted post-viability commit.  Remove
    # such residue before building this run's outcome rows in memory.
    if existing_contract is None:
        for label in WINDOWS:
            _source_input_path(label).unlink(missing_ok=True)

    capture_sector_entries: dict[str, dict[str, Any]] | None = None
    if existing_contract is None and any(
        not _snapshot_input_path(label).exists() for label in WINDOWS
    ):
        if not allow_materialize:
            raise RuntimeError("frozen broad snapshots are incomplete")
        capture_sector_entries = framework._load_sector_entries()
        if not capture_sector_entries:
            raise RuntimeError("broad sector map is empty")

    prepared: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        core_result, core_manifest = _load_core_result(label, baseline_index)
        snapshot_path = _snapshot_input_path(label)
        if snapshot_path.exists():
            snapshot_payload = _validate_snapshot_payload(
                _load_gzip_json(snapshot_path), label=label, spec=spec
            )
        else:
            if existing_contract is not None:
                raise RuntimeError(f"{label}: contracted broad snapshot is missing")
            if not allow_materialize or capture_sector_entries is None:
                raise RuntimeError(f"{label}: frozen broad snapshot is unavailable")
            snapshot = framework._load_window_snapshot(
                cfg=spec,
                eligible_tickers=set(capture_sector_entries),
            )
            rows_by_ticker = allocator.leader._normalise_ohlcv_by_ticker(snapshot)
            normalized_sector_entries = allocator._sector_entries(
                sector_entries=capture_sector_entries,
                candidate_universe=capture_sector_entries,
                rows_by_ticker=rows_by_ticker,
            )
            snapshot_payload = {
                "schema": "allocator_quarantine_frozen_broad_snapshot_v1",
                "window": {
                    "label": label,
                    "start": spec["start"],
                    "end": spec["end"],
                },
                "origin": {
                    "warehouse": _repo_rel(framework.WAREHOUSE),
                    "warehouse_sha256": _file_hash(Path(framework.WAREHOUSE)),
                    "sector_map": _repo_rel(SECTOR_MAP),
                    "sector_map_sha256": _file_hash(SECTOR_MAP),
                },
                "broad_rowset": _broad_rowset_manifest(snapshot),
                "normalized_sector_entries": normalized_sector_entries,
                "normalized_sector_entries_sha256": _stable_hash(
                    normalized_sector_entries
                ),
                "snapshot": snapshot,
            }
            _atomic_write_gzip_json(snapshot_path, snapshot_payload)
            snapshot_payload = _validate_snapshot_payload(
                _load_gzip_json(snapshot_path), label=label, spec=spec
            )

        snapshot = snapshot_payload["snapshot"]
        normalized_sector_entries = snapshot_payload["normalized_sector_entries"]
        broad_manifest = {
            **snapshot_payload["broad_rowset"],
            **snapshot_payload["origin"],
            "frozen_path": _repo_rel(snapshot_path),
            "frozen_sha256": _file_hash(snapshot_path),
        }
        rows_by_ticker = allocator.leader._normalise_ohlcv_by_ticker(snapshot)
        dates = [
            day
            for day in allocator._trading_dates(rows_by_ticker)
            if spec["start"] <= day <= spec["end"]
        ]
        if not dates:
            raise RuntimeError(f"{label}: frozen broad snapshot has no sessions")

        source_path = _source_input_path(label)
        if existing_contract is not None:
            if not source_path.exists():
                raise RuntimeError(f"{label}: contracted raw source rows are missing")
            source_payload = _validate_source_payload(
                _load_gzip_json(source_path),
                label=label,
                spec=spec,
                broad_rowset_sha256=broad_manifest["rowset_sha256"],
                core_sha256=core_manifest["sha256"],
            )
        else:
            core_entries = framework.shadow._baseline_entries(core_result)
            source_rows, source_audit = allocator._build_source_trades(
                rows_by_ticker=rows_by_ticker,
                dates=dates,
                window_label=label,
                window=spec,
                core_entries_by_date=core_entries,
                sector_entries=normalized_sector_entries,
                candidate_universe=normalized_sector_entries,
                calendar_dates=None,
            )
            source_payload = {
                "schema": "allocator_quarantine_frozen_raw_source_rows_v1",
                "window": {
                    "label": label,
                    "start": spec["start"],
                    "end": spec["end"],
                },
                "broad_rowset_sha256": broad_manifest["rowset_sha256"],
                "active_core_sha256": core_manifest["sha256"],
                "source_builder_identity": current_code,
                "trading_dates": dates,
                "source_rows": source_rows,
                "source_audit": source_audit,
                "source_audit_sha256": _stable_hash(source_audit),
                "source_manifest": _source_artifact_manifest(source_rows),
            }

        if list(source_payload["trading_dates"]) != dates:
            raise RuntimeError(f"{label}: frozen source calendar identity mismatch")

        source_manifest = {
            **source_payload["source_manifest"],
            "frozen_path": _repo_rel(source_path),
            "frozen_sha256": (
                _file_hash(source_path) if existing_contract is not None else None
            ),
        }
        prepared[label] = {
            "core_result": core_result,
            "core_manifest": core_manifest,
            "snapshot": snapshot,
            "rows_by_ticker": rows_by_ticker,
            "trading_dates": list(source_payload["trading_dates"]),
            "normalized_sector_entries": normalized_sector_entries,
            "broad_manifest": broad_manifest,
            "source_rows": source_payload["source_rows"],
            "source_audit": source_payload["source_audit"],
            "source_manifest": source_manifest,
            "source_payload": source_payload,
        }

    provisional = {
        "schema": "allocator_quarantine_frozen_inputs_pending_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "active_baseline_sha256": active_baseline_sha,
        "code_identity": current_code,
        "policy_sha256": _policy_bundle()["policy_sha256"],
    }
    if existing_contract is None:
        return provisional, None, prepared

    expected_contract = _frozen_contract_payload(prepared)
    if existing_contract != expected_contract:
        raise RuntimeError("frozen input contract does not match frozen files")
    return existing_contract, _file_hash(INPUT_CONTRACT), prepared


def _frozen_contract_payload(prepared: dict[str, dict[str, Any]]) -> dict[str, Any]:
    contract_windows: dict[str, Any] = {}
    for label, context in prepared.items():
        snapshot_path = _snapshot_input_path(label)
        source_path = _source_input_path(label)
        if not snapshot_path.exists() or not source_path.exists():
            raise RuntimeError(f"{label}: cannot commit incomplete frozen inputs")
        source_payload = context["source_payload"]
        broad_manifest = context["broad_manifest"]
        source_manifest = source_payload["source_manifest"]
        contract_windows[label] = {
            "window": source_payload["window"],
            "active_core": context["core_manifest"],
            "broad_snapshot": {
                "path": _repo_rel(snapshot_path),
                "sha256": _file_hash(snapshot_path),
                "rowset_sha256": broad_manifest["rowset_sha256"],
                "origin": {
                    "warehouse": broad_manifest["warehouse"],
                    "warehouse_sha256": broad_manifest["warehouse_sha256"],
                    "sector_map": broad_manifest["sector_map"],
                    "sector_map_sha256": broad_manifest["sector_map_sha256"],
                },
            },
            "raw_source_rows": {
                "path": _repo_rel(source_path),
                "sha256": _file_hash(source_path),
                "row_count": len(source_payload["source_rows"]),
                "rows_sha256": source_manifest["raw_source_rows_sha256"],
                "manifest_sha256": source_manifest["manifest_sha256"],
                "audit_sha256": source_payload["source_audit_sha256"],
            },
            "normalized_sector_entries_sha256": _stable_hash(
                context["normalized_sector_entries"]
            ),
        }
    warehouse_origins = {
        row["broad_snapshot"]["origin"]["warehouse_sha256"]
        for row in contract_windows.values()
    }
    sector_origins = {
        row["broad_snapshot"]["origin"]["sector_map_sha256"]
        for row in contract_windows.values()
    }
    if len(warehouse_origins) != 1 or len(sector_origins) != 1:
        raise RuntimeError("frozen windows do not share one origin data identity")
    return {
        "schema": "allocator_quarantine_frozen_inputs_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "active_baseline": _repo_rel(ACTIVE_BASELINE),
        "active_baseline_sha256": _file_hash(ACTIVE_BASELINE),
        "code_identity": _code_identity(),
        "policy_sha256": _policy_bundle()["policy_sha256"],
        "windows": contract_windows,
    }


def _persist_viable_source_inputs(
    prepared: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    if INPUT_CONTRACT.exists():
        raise RuntimeError("refusing to overwrite an existing frozen input contract")
    try:
        for label, context in prepared.items():
            _atomic_write_gzip_json(
                _source_input_path(label), context["source_payload"]
            )
        contract = _frozen_contract_payload(prepared)
        _atomic_write_json(INPUT_CONTRACT, contract)
        return contract, _file_hash(INPUT_CONTRACT)
    except BaseException:
        INPUT_CONTRACT.unlink(missing_ok=True)
        for label in WINDOWS:
            _source_input_path(label).unlink(missing_ok=True)
        raise


def _build_window_decisions(
    *,
    label: str,
    spec: dict[str, str],
    frozen: dict[str, Any],
    input_contract_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    core_result = frozen["core_result"]
    core_manifest = frozen["core_manifest"]
    snapshot = frozen["snapshot"]
    broad_manifest = frozen["broad_manifest"]
    rows_by_ticker = frozen["rows_by_ticker"]
    dates = frozen["trading_dates"]
    source_rows = frozen["source_rows"]
    source_audit = frozen["source_audit"]
    source_manifest = frozen["source_manifest"]
    health_by_date, quarantine_audit = (
        allocator.build_historical_source_relative_shadow_quarantine_health(
            source_rows=source_rows,
            trading_dates=dates,
            ohlcv_by_ticker=rows_by_ticker,
            benchmark_ohlcv_by_ticker={
                benchmark: rows_by_ticker.get(benchmark, [])
                for benchmark in allocator.SOURCE_QUARANTINE_BENCHMARKS
            },
            config={"source_quarantine_enabled": True},
        )
    )

    before_selected, before_rejected, before_priority = (
        allocator.select_accepted_helper_source_priority_rows(
            source_rows=source_rows,
            trading_dates=dates,
            config={"source_quarantine_enabled": False},
            create_trades=True,
        )
    )
    after_selected, after_rejected, after_priority = (
        allocator.select_accepted_helper_source_priority_rows(
            source_rows=source_rows,
            trading_dates=dates,
            config={"source_quarantine_enabled": True},
            create_trades=True,
            source_health_by_date=health_by_date,
        )
    )
    before_kept, before_envelope_skips, before_envelope = (
        allocator.apply_execution_envelope_to_trades(before_selected)
    )
    after_kept, after_envelope_skips, after_envelope = (
        allocator.apply_execution_envelope_to_trades(after_selected)
    )
    economic_contract = {
        "before_selected": _economic_contract_audit(before_selected),
        "after_selected": _economic_contract_audit(after_selected),
        "before_kept": _economic_contract_audit(before_kept),
        "after_kept": _economic_contract_audit(after_kept),
        "envelope_missing_date_skip_count": int(
            (before_envelope.get("skip_reasons") or {}).get(
                "missing_entry_or_exit_date", 0
            )
        )
        + int(
            (after_envelope.get("skip_reasons") or {}).get(
                "missing_entry_or_exit_date", 0
            )
        ),
    }
    before_settled = _settled_rows(before_kept, spec["end"])
    after_settled = _settled_rows(after_kept, spec["end"])

    before_by_id = {_semantic_id(row): row for row in before_settled}
    after_by_id = {_semantic_id(row): row for row in after_settled}
    if len(before_by_id) != len(before_settled):
        raise RuntimeError(f"{label}: duplicate current decision semantics")
    if len(after_by_id) != len(after_settled):
        raise RuntimeError(f"{label}: duplicate quarantine decision semantics")
    before_ids = set(before_by_id)
    after_ids = set(after_by_id)
    blocked_ids = before_ids - after_ids
    fallback_ids = after_ids - before_ids
    changed_ids = blocked_ids | fallback_ids
    union_rows = {**before_by_id, **after_by_id}

    direct_quarantine_ids = {
        _semantic_id(row)
        for row in after_rejected
        if row.get("filter_reason") == "source_relative_shadow_quarantine"
    }
    unavailable_filter_ids = {
        _semantic_id(row)
        for row in after_rejected
        if row.get("filter_reason") == "source_quarantine_unavailable"
    }
    trigger_counts = {
        str(key): int(value)
        for key, value in (quarantine_audit.get("trigger_counts") or {}).items()
    }
    recovery_counts = {
        str(key): int(value)
        for key, value in (quarantine_audit.get("recovery_counts") or {}).items()
    }
    unavailable_counts = {
        str(key): int(value)
        for key, value in (
            quarantine_audit.get("unavailable_session_counts") or {}
        ).items()
    }
    survival = (
        len(after_settled) / len(before_settled) if before_settled else 0.0
    )

    policy_bundle = _policy_bundle()
    decision_manifest = {
        "protocol_id": PROTOCOL_ID,
        "window": {"label": label, "start": spec["start"], "end": spec["end"]},
        "active_core_sha256": core_manifest["sha256"],
        "broad_rowset_sha256": broad_manifest["rowset_sha256"],
        "source_artifact_manifest_sha256": source_manifest["manifest_sha256"],
        "policy_bundle": policy_bundle,
        "before_semantic_ids": sorted(before_ids),
        "after_semantic_ids": sorted(after_ids),
    }
    decision_hash = _stable_hash(decision_manifest)

    compact = {
        "window": {"label": label, "start": spec["start"], "end": spec["end"]},
        "input_manifest": {
            "frozen_contract": (
                {
                    "path": _repo_rel(INPUT_CONTRACT),
                    "sha256": input_contract_sha256,
                }
                if input_contract_sha256 is not None
                else None
            ),
            "active_core": core_manifest,
            "broad_rowset": broad_manifest,
            "source_artifacts": source_manifest,
        },
        "decision_semantics": {
            "before_ids": sorted(before_ids),
            "after_ids": sorted(after_ids),
            "decision_hash": decision_hash,
        },
        "settled_counts": {
            "before": len(before_settled),
            "after": len(after_settled),
        },
        "difference": {
            "blocked_ids": sorted(blocked_ids),
            "fallback_ids": sorted(fallback_ids),
            "symmetric_ids": sorted(changed_ids),
            "blocked_count": len(blocked_ids),
            "fallback_count": len(fallback_ids),
            "symmetric_count": len(changed_ids),
            "blocked_by_source": _source_counts(blocked_ids, before_by_id),
            "fallback_by_source": _source_counts(fallback_ids, after_by_id),
            "affected_by_source": _source_counts(changed_ids, union_rows),
        },
        "quarantine": {
            "trigger_counts": dict(sorted(trigger_counts.items())),
            "recovery_counts": dict(sorted(recovery_counts.items())),
            "unavailable_session_counts": dict(sorted(unavailable_counts.items())),
            "direct_quarantine_candidate_count": len(direct_quarantine_ids),
            "unavailable_filter_candidate_count": len(unavailable_filter_ids),
            "quarantined_session_counts": dict(
                sorted(
                    {
                        str(key): int(value)
                        for key, value in (
                            quarantine_audit.get("quarantined_session_counts") or {}
                        ).items()
                    }.items()
                )
            ),
        },
        "admission_survival": round(survival, 8),
        "candidate_counts": {
            "raw_source_rows": len(source_rows),
            "before_selected": len(before_selected),
            "after_selected": len(after_selected),
            "before_rejected": len(before_rejected),
            "after_rejected": len(after_rejected),
            "source_trade_counts": dict(source_audit.get("source_trade_counts") or {}),
            "before_selected_by_source": dict(
                before_priority.get("selected_source_counts") or {}
            ),
            "after_selected_by_source": dict(
                after_priority.get("selected_source_counts") or {}
            ),
        },
        "execution_envelope": {
            "before": _compact_envelope_audit(before_envelope),
            "after": _compact_envelope_audit(after_envelope),
            "before_skip_count": len(before_envelope_skips),
            "after_skip_count": len(after_envelope_skips),
        },
        "economic_contract": economic_contract,
    }
    internal = {
        "label": label,
        "spec": spec,
        "core_result": core_result,
        "snapshot": snapshot,
        "broad_manifest": broad_manifest,
        "trading_dates": dates,
        "before_settled": before_settled,
        "after_settled": after_settled,
        "decision_hash": decision_hash,
    }
    return compact, internal


def build_preflight(
    *, allow_materialize: bool = True
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    summary, baseline_index = _active_baseline_index()
    frozen_contract, contract_sha256, frozen_inputs = _prepare_frozen_inputs(
        baseline_index=baseline_index,
        allow_materialize=allow_materialize,
    )
    windows: list[dict[str, Any]] = []
    internal: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        print(f"PREFLIGHT_START {label}", file=sys.stderr, flush=True)
        compact, context = _build_window_decisions(
            label=label,
            spec=spec,
            frozen=frozen_inputs[label],
            input_contract_sha256=contract_sha256,
        )
        windows.append(compact)
        internal[label] = context
        print(
            "PREFLIGHT_DONE "
            f"{label} before={compact['settled_counts']['before']} "
            f"after={compact['settled_counts']['after']} "
            f"affected={compact['difference']['symmetric_count']}",
            file=sys.stderr,
            flush=True,
        )

    affected_total = sum(row["difference"]["symmetric_count"] for row in windows)
    affected_families = sorted(
        {
            source
            for row in windows
            for source in row["difference"]["affected_by_source"]
        }
    )
    trigger_total = sum(
        sum(row["quarantine"]["trigger_counts"].values()) for row in windows
    )
    recovery_total = sum(
        sum(row["quarantine"]["recovery_counts"].values()) for row in windows
    )
    unavailable_total = sum(
        sum(row["quarantine"]["unavailable_session_counts"].values())
        + int(row["quarantine"]["unavailable_filter_candidate_count"])
        + int(
            row["input_manifest"]["source_artifacts"].get(
                "missing_reference_count", 0
            )
        )
        for row in windows
    )
    economic_contract_invalid_total = sum(
        sum(
            int(audit["invalid_count"])
            for audit in row["economic_contract"].values()
            if isinstance(audit, dict) and "invalid_count" in audit
        )
        + int(row["economic_contract"]["envelope_missing_date_skip_count"])
        for row in windows
    )
    survival_floor = min(row["admission_survival"] for row in windows)
    failed: list[str] = []
    if affected_total < MIN_AFFECTED_SETTLED_TOTAL:
        failed.append("affected_settled_total_below_threshold")
    for row in windows:
        if row["difference"]["symmetric_count"] < MIN_AFFECTED_SETTLED_PER_WINDOW:
            failed.append(
                "affected_settled_window_below_threshold:"
                + row["window"]["label"]
            )
    if len(affected_families) < MIN_AFFECTED_SOURCE_FAMILIES:
        failed.append("affected_source_family_count_below_threshold")
    if trigger_total < MIN_TRIGGER_COUNT:
        failed.append("quarantine_never_triggered")
    if survival_floor < MIN_ADMISSION_SURVIVAL:
        failed.append("admission_survival_below_threshold")
    if unavailable_total:
        failed.append("benchmark_or_state_gap_present")
    if economic_contract_invalid_total:
        failed.append("economic_contract_invalid")

    window_hashes = {
        row["window"]["label"]: row["decision_semantics"]["decision_hash"]
        for row in windows
    }
    decision_hash = _stable_hash(
        {
            "protocol_id": PROTOCOL_ID,
            "active_baseline_sha256": _file_hash(ACTIVE_BASELINE),
            "window_hashes": window_hashes,
        }
    )
    payload = {
        "schema": "allocator_quarantine_decision_preflight_v1",
        "experiment_id": EXPERIMENT_ID,
        "phase": "preflight",
        "rule_version": RULE_VERSION,
        "protocol_id": PROTOCOL_ID,
        "performance_fields_prohibited": True,
        "input_manifest": {
            "active_baseline": _repo_rel(ACTIVE_BASELINE),
            "active_baseline_sha256": _file_hash(ACTIVE_BASELINE),
            "active_baseline_protocol": summary.get("protocol_id"),
            "active_baseline_clean_release_ready": bool(
                summary.get("clean_release_ready")
            ),
            "active_baseline_release_caveat": summary.get("clean_release_blocker"),
            "frozen_contract": (
                _repo_rel(INPUT_CONTRACT) if contract_sha256 is not None else None
            ),
            "frozen_contract_sha256": contract_sha256,
            "code_identity": frozen_contract["code_identity"],
            "origin_warehouse": _repo_rel(framework.WAREHOUSE),
            "origin_sector_map": _repo_rel(SECTOR_MAP),
        },
        "policy": {
            "policy_sha256": _policy_bundle()["policy_sha256"],
            "source_shadow_notional_usd": allocator.SOURCE_SHADOW_NOTIONAL_USD,
            "underwater_sessions": allocator.SOURCE_QUARANTINE_UNDERWATER_SESSIONS,
            "benchmarks": list(allocator.SOURCE_QUARANTINE_BENCHMARKS),
            "execution_envelope_rule_version": allocator.EXECUTION_ENVELOPE[
                "rule_version"
            ],
            "execution_envelope_sha256": _stable_hash(allocator.EXECUTION_ENVELOPE),
        },
        "decision_hash": decision_hash,
        "window_decision_hashes": window_hashes,
        "windows": windows,
        "aggregate": {
            "affected_settled_count": affected_total,
            "affected_source_families": affected_families,
            "affected_source_family_count": len(affected_families),
            "trigger_count": trigger_total,
            "recovery_count": recovery_total,
            "unavailable_count": unavailable_total,
            "economic_contract_invalid_count": economic_contract_invalid_total,
            "admission_survival_floor": survival_floor,
        },
        "thresholds": {
            "min_affected_settled_total": MIN_AFFECTED_SETTLED_TOTAL,
            "min_affected_settled_per_window": MIN_AFFECTED_SETTLED_PER_WINDOW,
            "min_affected_source_families": MIN_AFFECTED_SOURCE_FAMILIES,
            "min_trigger_count": MIN_TRIGGER_COUNT,
            "min_admission_survival": MIN_ADMISSION_SURVIVAL,
            "require_zero_unavailable": True,
        },
        "passed": not failed,
        "failed_reasons": failed,
        "full_phase_authorized": not failed,
    }
    if payload["passed"] and contract_sha256 is None:
        provisional_decision_hash = payload["decision_hash"]
        try:
            _persist_viable_source_inputs(frozen_inputs)
            verified, verified_internal = build_preflight(allow_materialize=False)
            if verified.get("passed") is not True:
                raise RuntimeError("persisted preflight no longer passes")
            if verified.get("decision_hash") != provisional_decision_hash:
                raise RuntimeError("persisted preflight decision hash changed")
            verified["frozen_persistence_verified"] = True
            return verified, verified_internal
        except BaseException:
            INPUT_CONTRACT.unlink(missing_ok=True)
            for label in WINDOWS:
                _source_input_path(label).unlink(missing_ok=True)
            raise
    if contract_sha256 is None:
        if INPUT_CONTRACT.exists() or any(
            _source_input_path(label).exists() for label in WINDOWS
        ):
            raise RuntimeError("non-viable preflight persisted forbidden outcome inputs")
        payload["frozen_persistence_verified"] = False
    else:
        payload["frozen_persistence_verified"] = True
    return payload, internal


def _core_curve(
    result: dict[str, Any], trading_dates: list[str], label: str
) -> list[tuple[str, float]]:
    inference = result.get("sharpe_inference") or {}
    returns = list(inference.get("return_series") or [])
    dates = [day for day in trading_dates if WINDOWS[label]["start"] <= day <= WINDOWS[label]["end"]]
    if len(dates) != len(returns) + 1:
        raise RuntimeError(f"{label}: core daily-series/calendar length mismatch")
    curve = [(dates[0], INITIAL_CAPITAL)]
    equity = INITIAL_CAPITAL
    for expected_date, row in zip(dates[1:], returns):
        if str(row.get("date") or "")[:10] != expected_date:
            raise RuntimeError(f"{label}: core daily-series date mismatch")
        equity *= 1.0 + float(row["return"])
        curve.append((expected_date, equity))
    expected_terminal = INITIAL_CAPITAL + float(result.get("total_pnl") or 0.0)
    if abs(curve[-1][1] - expected_terminal) > 0.05:
        raise RuntimeError(f"{label}: core daily-series terminal identity mismatch")
    # The persisted periodic series is full precision while public total PnL is
    # cents-rounded.  Pin only the terminal cent to the active artifact so the
    # combined curve and the published Gate-1 PnL share an exact cash identity.
    curve[-1] = (curve[-1][0], expected_terminal)
    return curve


def _combined_curve(
    *,
    core_curve: list[tuple[str, float]],
    trades: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, float]]:
    close_by_ticker_date: dict[str, dict[str, float]] = {}
    curve_dates = [day for day, _ in core_curve]
    for ticker in {str(row.get("ticker") or "").upper() for row in trades}:
        exact = {
            str(bar.get("Date") or bar.get("date") or "")[:10]: float(
                bar.get("Close", bar.get("close"))
            )
            for bar in snapshot.get(ticker, [])
            if bar.get("Close", bar.get("close")) is not None
        }
        carried: dict[str, float] = {}
        last_close: float | None = None
        for day in curve_dates:
            if day in exact:
                last_close = exact[day]
            if last_close is not None:
                carried[day] = last_close
        close_by_ticker_date[ticker] = carried
    curve: list[tuple[str, float]] = []
    for day, core_equity in core_curve:
        contribution = 0.0
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if day < entry_date:
                continue
            if day >= exit_date:
                contribution += float(trade.get("pnl") or 0.0)
                continue
            ticker = str(trade.get("ticker") or "").upper()
            close = close_by_ticker_date.get(ticker, {}).get(day)
            entry_price = float(trade.get("entry_price") or 0.0)
            notional = float(trade.get("paper_notional_usd") or 0.0)
            if close is None:
                raise RuntimeError(f"missing daily mark for {ticker} on {day}")
            if entry_price <= 0.0 or notional <= 0.0:
                raise RuntimeError("invalid allocator MTM trade contract")
            contribution += notional * (close / entry_price - 1.0)
            contribution -= notional * float(allocator.ROUND_TRIP_COST_PCT) / 2.0
        curve.append((day, float(core_equity) + contribution))
    return curve


def _curve_metrics(curve: list[tuple[str, float]], trade_count: int) -> dict[str, Any]:
    inference = build_backtest_sharpe_inference(curve)
    if inference.get("status") != "computable":
        raise RuntimeError(f"daily Sharpe inference unavailable: {inference}")
    total = curve[-1][1] - INITIAL_CAPITAL
    strategy_return = total / INITIAL_CAPITAL
    sharpe = float(inference["annualized_sharpe"])
    peak = curve[0][1]
    max_drawdown = 0.0
    for _, equity in curve:
        peak = max(peak, equity)
        if peak > 0.0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    # Keep the repository's canonical public Gate-4 score convention: the
    # displayed four-decimal strategy return times the displayed two-decimal
    # daily Sharpe.  Full-precision inference remains attached for PSR/DSR.
    strategy_return_public = round(strategy_return, 4)
    sharpe_public = round(sharpe, 2)
    return {
        "expected_value_score": round(strategy_return_public * sharpe_public, 4),
        "total_pnl": round(total, 2),
        "strategy_total_return_pct": strategy_return_public,
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe,
        "max_drawdown_pct": round(max_drawdown, 4),
        "trade_count": trade_count,
        "sharpe_inference": inference,
    }


def _assert_core_metric_identity(
    *, label: str, result: dict[str, Any], rebuilt: dict[str, Any]
) -> dict[str, Any]:
    inference = result.get("sharpe_inference") or {}
    benchmarks = result.get("benchmarks") or {}
    checks = {
        "expected_value_score": (
            float(rebuilt["expected_value_score"]),
            float(result.get("expected_value_score")),
            1e-12,
        ),
        "sharpe_daily_display": (
            float(rebuilt["sharpe_daily"]),
            float(result.get("sharpe_daily")),
            1e-12,
        ),
        "sharpe_daily_full_precision": (
            float(rebuilt["sharpe_daily_full_precision"]),
            float(inference.get("annualized_sharpe")),
            1e-6,
        ),
        "max_drawdown_pct": (
            float(rebuilt["max_drawdown_pct"]),
            float(result.get("max_drawdown_pct")),
            1e-12,
        ),
        "strategy_total_return_pct": (
            float(rebuilt["strategy_total_return_pct"]),
            float(benchmarks.get("strategy_total_return_pct")),
            1e-12,
        ),
        "total_pnl": (
            float(rebuilt["total_pnl"]),
            float(result.get("total_pnl")),
            0.005,
        ),
    }
    failed = [
        name
        for name, (actual, expected, tolerance) in checks.items()
        if abs(actual - expected) > tolerance
    ]
    if failed:
        raise RuntimeError(
            f"{label}: rebuilt core metric identity failed: {','.join(failed)}"
        )
    return {
        "passed": True,
        "checks": {
            name: {"passed": True, "absolute_tolerance": tolerance}
            for name, (_, _, tolerance) in checks.items()
        },
    }


def _positive_concentration(trades: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: Counter[str] = Counter()
    for row in trades:
        value = float(row.get("pnl") or 0.0)
        if value > 0.0:
            positive_by_ticker[str(row.get("ticker") or "unknown").upper()] += value
    total = sum(positive_by_ticker.values())
    shares = {
        ticker: value / total for ticker, value in positive_by_ticker.items()
    } if total > 0.0 else {}
    return {
        "positive_total_pnl": total,
        "positive_ticker_count": len(shares),
        "single_name_share": max(shares.values()) if shares else None,
        "hhi": sum(value * value for value in shares.values()) if shares else None,
        "shares": dict(sorted(shares.items())),
    }


def _dsr_panel(
    *,
    label: str,
    window_index: int,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    expected_return_dates: list[str],
    frozen_snapshot: dict[str, Any],
) -> dict[str, Any]:
    common = {
        "attempted": True,
        "selection_scope": "exp-20260715-001_fixed_before_after_pair",
        "window": label,
        "frequency": "daily",
        "return_basis": "combined_core_allocator_equity_return",
        "risk_free_assumption": "zero",
        "protocol": PROTOCOL_ID,
        "data": {
            "frozen_contract": _repo_rel(INPUT_CONTRACT),
            "frozen_contract_sha256": _file_hash(INPUT_CONTRACT),
            "frozen_snapshot": frozen_snapshot["frozen_path"],
            "frozen_snapshot_sha256": frozen_snapshot["frozen_sha256"],
            "broad_rowset_sha256": frozen_snapshot["rowset_sha256"],
        },
        "cost": "accepted_allocator_cost_contract_and_execution_envelope_v2",
    }
    trials = []
    for config_id, payload_key, enabled, metrics in (
        ("current", "before", False, before_metrics),
        ("quarantine", "after", True, after_metrics),
    ):
        inference = metrics["sharpe_inference"]
        trials.append(
            {
                **common,
                "config_id": config_id,
                "config": {
                    "source_quarantine_enabled": enabled,
                    "rule_version": RULE_VERSION,
                },
                "return_series": inference["return_series"],
                "return_series_sha256": inference["return_series_sha256"],
                "return_series_source": (
                    _repo_rel(FULL_OUT)
                    + f"#/windows/{window_index}/{payload_key}/sharpe_inference/return_series"
                ),
            }
        )
    for trial in trials:
        actual_dates = [row["date"] for row in trial["return_series"]]
        if actual_dates != expected_return_dates:
            raise RuntimeError(f"{label}: DSR return dates do not match frozen calendar")
    return evaluate_deflated_sharpe_trial_panel(
        trials,
        selected_config_id="quarantine",
        expected_attempt_count=2,
        selection_pool_complete=True,
        expected_return_dates=expected_return_dates,
    )


def build_full(
    preflight: dict[str, Any], contexts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_after_trades: list[dict[str, Any]] = []
    for window_index, (label, context) in enumerate(contexts.items()):
        core_curve = _core_curve(
            context["core_result"], context["trading_dates"], label
        )
        core_metrics = _curve_metrics(
            core_curve, int(context["core_result"].get("total_trades") or 0)
        )
        core_identity = _assert_core_metric_identity(
            label=label,
            result=context["core_result"],
            rebuilt=core_metrics,
        )
        before_curve = _combined_curve(
            core_curve=core_curve,
            trades=context["before_settled"],
            snapshot=context["snapshot"],
        )
        after_curve = _combined_curve(
            core_curve=core_curve,
            trades=context["after_settled"],
            snapshot=context["snapshot"],
        )
        before_metrics = _curve_metrics(
            before_curve,
            int(context["core_result"].get("total_trades") or 0)
            + len(context["before_settled"]),
        )
        after_metrics = _curve_metrics(
            after_curve,
            int(context["core_result"].get("total_trades") or 0)
            + len(context["after_settled"]),
        )
        rows.append(
            {
                "label": label,
                "window": context["spec"],
                "decision_hash": context["decision_hash"],
                "core_identity": core_identity,
                "core": core_metrics,
                "before": before_metrics,
                "after": after_metrics,
                "delta_after_vs_before": {
                    "expected_value_score": after_metrics["expected_value_score"]
                    - before_metrics["expected_value_score"],
                    "total_pnl": after_metrics["total_pnl"]
                    - before_metrics["total_pnl"],
                    "max_drawdown_pct": after_metrics["max_drawdown_pct"]
                    - before_metrics["max_drawdown_pct"],
                },
                "after_vs_core": {
                    "expected_value_score": after_metrics["expected_value_score"]
                    - core_metrics["expected_value_score"],
                    "total_pnl": after_metrics["total_pnl"]
                    - core_metrics["total_pnl"],
                },
                "before_vs_core": {
                    "expected_value_score": before_metrics["expected_value_score"]
                    - core_metrics["expected_value_score"],
                    "total_pnl": before_metrics["total_pnl"]
                    - core_metrics["total_pnl"],
                },
                "dsr_gate5": _dsr_panel(
                    label=label,
                    window_index=window_index,
                    before_metrics=before_metrics,
                    after_metrics=after_metrics,
                    expected_return_dates=context["trading_dates"][1:],
                    frozen_snapshot=context["broad_manifest"],
                ),
            }
        )
        all_after_trades.extend(context["after_settled"])

    before_allocator_ev = sum(
        row["before_vs_core"]["expected_value_score"] for row in rows
    )
    after_allocator_ev = sum(
        row["after_vs_core"]["expected_value_score"] for row in rows
    )
    before_system_ev = sum(row["before"]["expected_value_score"] for row in rows)
    after_system_ev = sum(row["after"]["expected_value_score"] for row in rows)
    ev_improvement = (
        after_system_ev / before_system_ev - 1.0
        if before_system_ev > 0.0
        else None
    )
    incremental_pnl = sum(
        row["delta_after_vs_before"]["total_pnl"] for row in rows
    )
    improved_windows = [
        row["label"]
        for row in rows
        if row["delta_after_vs_before"]["expected_value_score"] > 0.0
        and row["delta_after_vs_before"]["total_pnl"] > 0.0
    ]
    concentration = _positive_concentration(all_after_trades)
    failed: list[str] = []
    if ev_improvement is None or ev_improvement <= MIN_AGGREGATE_FULL_SYSTEM_EV_IMPROVEMENT:
        failed.append("aggregate_full_system_ev_improvement_not_above_10pct")
    if incremental_pnl <= 0.0:
        failed.append("incremental_pnl_not_positive")
    if len(improved_windows) < 2:
        failed.append("fewer_than_two_windows_improved")
    for row in rows:
        label = row["label"]
        if row["delta_after_vs_before"]["expected_value_score"] < 0.0:
            failed.append(f"window_ev_regression:{label}")
        if row["delta_after_vs_before"]["total_pnl"] < 0.0:
            failed.append(f"window_pnl_regression:{label}")
        if row["delta_after_vs_before"]["max_drawdown_pct"] > MAX_DRAWDOWN_WORSENING:
            failed.append(f"window_drawdown_worsening:{label}")
        if row["after_vs_core"]["expected_value_score"] <= 0.0:
            failed.append(f"after_ev_not_positive_vs_core:{label}")
        if row["after_vs_core"]["total_pnl"] <= 0.0:
            failed.append(f"after_pnl_not_positive_vs_core:{label}")
    if concentration["single_name_share"] is None or concentration[
        "single_name_share"
    ] > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("positive_single_name_concentration_failed")
    if concentration["hhi"] is None or concentration["hhi"] > MAX_POSITIVE_HHI:
        failed.append("positive_hhi_failed")

    return {
        "schema": "allocator_quarantine_post_mtm_full_v1",
        "experiment_id": EXPERIMENT_ID,
        "phase": "full",
        "rule_version": RULE_VERSION,
        "protocol_id": PROTOCOL_ID,
        "preflight_decision_hash": preflight["decision_hash"],
        "preflight_reproduced": True,
        "frozen_input_contract": {
            "path": _repo_rel(INPUT_CONTRACT),
            "sha256": _file_hash(INPUT_CONTRACT),
        },
        "policy_bundle": _policy_bundle(),
        "binding_exit_rule": "exit_date_lte_canonical_window_end",
        "execution_envelope": allocator.EXECUTION_ENVELOPE,
        "windows": rows,
        "aggregate": {
            "before_full_system_ev": before_system_ev,
            "after_full_system_ev": after_system_ev,
            "full_system_ev_improvement_fraction": ev_improvement,
            "before_allocator_ev": before_allocator_ev,
            "after_allocator_ev": after_allocator_ev,
            "allocator_incremental_ev_delta": after_allocator_ev - before_allocator_ev,
            "incremental_pnl": incremental_pnl,
            "improved_windows": improved_windows,
            "positive_pnl_concentration": concentration,
        },
        "gate4": {
            "passed": not failed,
            "failed_reasons": failed,
            "thresholds": {
                "aggregate_full_system_ev_improvement_strictly_above": MIN_AGGREGATE_FULL_SYSTEM_EV_IMPROVEMENT,
                "incremental_pnl_strictly_positive": True,
                "min_improved_windows": 2,
                "no_window_ev_or_pnl_regression": True,
                "max_drawdown_worsening": MAX_DRAWDOWN_WORSENING,
                "after_positive_vs_core_every_window": True,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate5": {
            "role": "live_eligibility_only_not_gate4_acceptance",
            "selection_risk": "high",
            "live_eligible": False,
            "live_ineligible_reason": "historical_allocator_selection_panel_incomplete",
            "allocator_cell_prior_trials": 21,
            "allocator_cell_prior_accepts": 1,
            "panel": "complete_fixed_two_configuration_before_after_pair_per_window",
            "note": (
                "DSR describes the declared two-configuration selection panel only; "
                "the wider historical allocator search is not falsely claimed as a "
                "complete panel. A Gate-4 pass remains default-off, not live-ready."
            ),
        },
    }


def _run_preflight() -> int:
    payload, _ = build_preflight(allow_materialize=True)
    _assert_preflight_nonperformance(payload)
    _atomic_write_json(PREFLIGHT_OUT, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 2


def _run_full() -> int:
    if not PREFLIGHT_OUT.exists():
        raise RuntimeError("persisted preflight is required before full phase")
    persisted = _load_json(PREFLIGHT_OUT)
    if persisted.get("passed") is not True:
        raise RuntimeError("persisted preflight did not pass; full phase is forbidden")
    rebuilt, contexts = build_preflight(allow_materialize=False)
    _assert_preflight_nonperformance(rebuilt)
    if rebuilt.get("passed") is not True:
        raise RuntimeError("rebuilt preflight no longer passes; full phase is forbidden")
    if rebuilt.get("decision_hash") != persisted.get("decision_hash"):
        raise RuntimeError("preflight decision hash did not reproduce")
    payload = build_full(rebuilt, contexts)
    _atomic_write_json(FULL_OUT, payload)
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["gate4"]["passed"] else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("preflight", "full"), required=True)
    args = parser.parse_args()
    if args.phase == "preflight":
        return _run_preflight()
    return _run_full()


if __name__ == "__main__":
    raise SystemExit(main())

