"""Reassess recoverable historical strategy evidence under current contracts.

The module is intentionally evaluation-only.  It freezes a complete manifest
of the historical evidence that is still recoverable from the repository,
re-scores stored metrics with the sign-preserving EV helper, and evaluates
every unique, complete, separable three-window target-trade surface against the
cash-feasible Gate-1 core through the capital-neutral Gate 4-P contract.

Closed experiment verdicts are provenance and are never rewritten here.
Historical selection history is known to be incomplete, so a positive
economic result is capped at ``portfolio_forward_watch``.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from quant.convergence import expected_value_score_raw
from quant.evaluator_gates import (
    DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS,
    evaluate_portfolio_contribution_gate,
)
from quant import portfolio_contribution_batch as legacy_pc


REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ("late_strong", "mid_weak", "old_thin")
ACTIVE_BASELINE_SUMMARY = Path(
    "data/backtests/"
    "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
ACTIVE_CORE_ARTIFACTS = {
    "late_strong": Path(
        "data/backtests/cash_feasible_20260715/"
        "late_strong_exp-20260715-010.json"
    ),
    "mid_weak": Path(
        "data/backtests/cash_feasible_20260715/"
        "mid_weak_exp-20260715-010.json"
    ),
    "old_thin": Path(
        "data/backtests/cash_feasible_20260715/"
        "old_thin_exp-20260715-010.json"
    ),
}
DEFAULT_WAREHOUSE = Path("data/warehouse/warehouse_main.sqlite")
PORTFOLIO_CAPITAL_USD = 100_000.0
CANDIDATE_CAPITAL_USD = 10_000.0
CORE_WEIGHT = 0.90
CANDIDATE_WEIGHT = 0.10
DEFAULT_BOOTSTRAP_REPLICATES = 10_000
DEFAULT_BOOTSTRAP_SEED = 2_026_071_611
DEFAULT_BLOCK_LENGTH = 20
CURRENT_SCORE_CONTRACT = "strategy_total_return_pct * abs(sharpe_daily)"
REQUIRED_TRADE_FIELDS = (
    "ticker",
    "entry_date",
    "exit_date",
    "paper_notional_usd",
    "entry_price",
    "exit_price",
)
OPEN_STATUSES = {"proposed", "claimed", "running"}
ALPHA_LANES = {"alpha_search", "alpha_discovery"}


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _repo_rel(path: str | Path) -> str:
    resolved = _repo_path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _read_json(path: str | Path) -> Any:
    resolved = _repo_path(path)
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return json.loads(resolved.read_text(encoding=encoding))
        except UnicodeError:
            continue
    return json.loads(resolved.read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    resolved = _repo_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _repo_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _metric_return(metrics: Mapping[str, Any]) -> float | None:
    for key in ("total_return_pct", "strategy_total_return_pct"):
        value = _finite(metrics.get(key))
        if value is not None:
            return value
    benchmarks = metrics.get("benchmarks")
    if isinstance(benchmarks, Mapping):
        return _finite(benchmarks.get("strategy_total_return_pct"))
    return None


def _rescore_metric_block(metrics: Any) -> dict[str, Any]:
    if not isinstance(metrics, Mapping):
        return {
            "disposition": "missing_metric_block",
            "current_expected_value_score": None,
        }
    strategy_return = _metric_return(metrics)
    sharpe = _finite(metrics.get("sharpe_daily"))
    stored = _finite(metrics.get("expected_value_score"))
    if strategy_return is None or sharpe is None:
        return {
            "disposition": "missing_return_or_sharpe",
            "strategy_total_return_pct": strategy_return,
            "sharpe_daily": sharpe,
            "stored_expected_value_score": stored,
            "current_expected_value_score": None,
        }
    current = expected_value_score_raw(strategy_return, sharpe)
    assert current is not None
    changed = stored is not None and not math.isclose(
        stored, current, rel_tol=0.0, abs_tol=5e-4
    )
    return {
        "disposition": "rescored_changed" if changed else "rescored_unchanged",
        "strategy_total_return_pct": strategy_return,
        "sharpe_daily": sharpe,
        "stored_expected_value_score": stored,
        "current_expected_value_score": current,
        "delta_vs_stored": current - stored if stored is not None else None,
        "legacy_negative_times_negative_pathology": strategy_return < 0.0
        and sharpe < 0.0,
    }


def _contains_active_baseline(value: Any) -> bool:
    target = ACTIVE_BASELINE_SUMMARY.as_posix()
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return target in normalized or "exp-20260715-010" in normalized
    if isinstance(value, Mapping):
        return any(_contains_active_baseline(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_active_baseline(item) for item in value)
    return False


def scan_experiment_logs(
    *, exclude_experiment_ids: Iterable[str] = ()
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    """Give every historical log a deterministic current-contract disposition."""

    excluded = set(exclude_experiment_ids)
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "experiments" / "logs").glob("exp-*.json")):
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rows.append(
                {
                    "path": _repo_rel(path),
                    "source_sha256": _sha256_file(path),
                    "experiment_id": path.stem,
                    "record_disposition": "unreadable_log",
                    "error": type(exc).__name__,
                }
            )
            continue
        if not isinstance(payload, Mapping):
            rows.append(
                {
                    "path": _repo_rel(path),
                    "source_sha256": _sha256_file(path),
                    "experiment_id": path.stem,
                    "record_disposition": "non_object_log",
                }
            )
            continue
        experiment_id = str(payload.get("experiment_id") or path.stem)
        if experiment_id in excluded:
            continue
        status = str(payload.get("status") or "")
        before = _rescore_metric_block(payload.get("before_metrics"))
        after = _rescore_metric_block(payload.get("after_metrics"))
        rescoreable = any(
            row.get("current_expected_value_score") is not None
            for row in (before, after)
        )
        score_changed = any(
            row.get("disposition") == "rescored_changed" for row in (before, after)
        )
        row = {
            "path": _repo_rel(path),
            "source_sha256": _sha256_file(path),
            "experiment_id": experiment_id,
            "status": status or None,
            "closed": status not in OPEN_STATUSES,
            "lane": payload.get("lane") or payload.get("change_type"),
            "decision": payload.get("decision"),
            "before_metrics": before,
            "after_metrics": after,
            "metric_disposition": (
                "current_ev_changed"
                if score_changed
                else "current_ev_recoverable"
                if rescoreable
                else "current_ev_evidence_missing"
            ),
            "comparator_disposition": (
                "active_cash_feasible_comparator_declared"
                if _contains_active_baseline(payload)
                else "legacy_or_unproven_comparator"
            ),
        }
        rows.append(row)
        by_id.setdefault(experiment_id, dict(payload))

    counts = Counter(row["metric_disposition"] for row in rows)
    comparator_counts = Counter(row["comparator_disposition"] for row in rows)
    summary = {
        "log_file_count": len(rows),
        "unique_experiment_id_count": len({row["experiment_id"] for row in rows}),
        "closed_experiment_id_count": len(
            {row["experiment_id"] for row in rows if row.get("closed")}
        ),
        "metric_disposition_counts": dict(sorted(counts.items())),
        "comparator_disposition_counts": dict(sorted(comparator_counts.items())),
        "negative_times_negative_rows": sum(
            bool(side.get("legacy_negative_times_negative_pathology"))
            for row in rows
            for side in (row.get("before_metrics") or {}, row.get("after_metrics") or {})
        ),
    }
    return rows, summary, by_id


def scan_experiment_tickets(
    *, exclude_experiment_ids: Iterable[str] = ()
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    """Freeze the ticket authority surface and expose canonical metadata."""

    excluded = set(exclude_experiment_ids)
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "experiments" / "tickets").glob("*.json")):
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rows.append(
                {
                    "path": _repo_rel(path),
                    "source_sha256": _sha256_file(path),
                    "experiment_id": path.stem,
                    "ticket_disposition": "unreadable_ticket",
                    "error": type(exc).__name__,
                }
            )
            continue
        if not isinstance(payload, Mapping):
            rows.append(
                {
                    "path": _repo_rel(path),
                    "source_sha256": _sha256_file(path),
                    "experiment_id": path.stem,
                    "ticket_disposition": "non_object_ticket",
                }
            )
            continue
        experiment_id = str(payload.get("experiment_id") or path.stem)
        if experiment_id in excluded:
            continue
        result = payload.get("result")
        result_decision = (
            result.get("decision") if isinstance(result, Mapping) else None
        )
        status = str(payload.get("status") or "")
        row = {
            "path": _repo_rel(path),
            "source_sha256": _sha256_file(path),
            "experiment_id": experiment_id,
            "ticket_disposition": "canonical_ticket",
            "status": status or None,
            "closed": status not in OPEN_STATUSES,
            "lane": payload.get("lane"),
            "change_type": payload.get("change_type"),
            "decision": result_decision or payload.get("decision"),
            "trial_family": payload.get("trial_family"),
            "mechanism_family": payload.get("mechanism_family"),
        }
        rows.append(row)
        by_id.setdefault(experiment_id, dict(payload))

    lane_counts = Counter(str(row.get("lane") or "missing") for row in rows)
    status_counts = Counter(str(row.get("status") or "missing") for row in rows)
    summary = {
        "ticket_file_count": len(rows),
        "unique_experiment_id_count": len({row["experiment_id"] for row in rows}),
        "closed_experiment_id_count": len(
            {row["experiment_id"] for row in rows if row.get("closed")}
        ),
        "lane_counts": dict(sorted(lane_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
    }
    return rows, summary, by_id


def _target_surface(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = payload.get("target_trades_by_window")
    return value if isinstance(value, Mapping) else None


def _normalize_target_surface(
    surface: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Normalize replay fields without changing any historical source file.

    Early artifacts sometimes persisted ``shares`` but not
    ``paper_notional_usd``.  That missing notional is exactly recoverable from
    shares times entry price.  A small number of artifacts also mixed
    signal-only observer rows into ``target_trades_by_window``; rows without a
    complete entry/exit contract are excluded and explicitly counted rather
    than being silently treated as zero-PnL trades.
    """

    normalized: dict[str, list[dict[str, Any]]] = {}
    total = 0
    valid = 0
    derived_notional = 0
    unsupported_direction_rows = 0
    direction_values: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    per_window: dict[str, Any] = {}
    for window in WINDOWS:
        raw_rows = surface.get(window)
        if not isinstance(raw_rows, list):
            invalid[f"missing_window:{window}"] += 1
            normalized[window] = []
            per_window[window] = {"source_rows": 0, "replayable_rows": 0}
            continue
        window_rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            total += 1
            if not isinstance(raw, Mapping):
                invalid["non_object_trade"] += 1
                continue
            explicit_directions = [
                str(raw.get(field) or "").strip().lower()
                for field in (
                    "paper_direction",
                    "position_direction",
                    "position_side",
                    "trade_side",
                    "direction",
                    "side",
                )
                if raw.get(field) not in (None, "")
            ]
            for direction in explicit_directions:
                direction_values[direction] += 1
            if any(
                "short" in direction
                or "inverse" in direction
                or direction in {"sell_short", "bearish"}
                for direction in explicit_directions
            ):
                unsupported_direction_rows += 1
            ticker = str(raw.get("ticker") or "").strip().upper()
            entry = legacy_pc._parse_date(raw.get("entry_date"))
            exit_day = legacy_pc._parse_date(raw.get("exit_date"))
            entry_price = _finite(raw.get("entry_price"))
            exit_price = _finite(raw.get("exit_price"))
            notional = _finite(raw.get("paper_notional_usd"))
            notional_was_derived = False
            if notional is None:
                shares = _finite(raw.get("shares"))
                if (
                    shares is not None
                    and shares > 0.0
                    and entry_price is not None
                    and entry_price > 0.0
                ):
                    notional = shares * entry_price
                    notional_was_derived = True
            row_reasons: list[str] = []
            if not ticker:
                row_reasons.append("missing_ticker")
            if entry is None:
                row_reasons.append("missing_entry_date")
            if exit_day is None:
                row_reasons.append("missing_exit_date")
            if entry_price is None or entry_price <= 0.0:
                row_reasons.append("invalid_entry_price")
            if exit_price is None or exit_price <= 0.0:
                row_reasons.append("invalid_exit_price")
            if notional is None or notional <= 0.0:
                row_reasons.append("missing_or_invalid_notional")
            if row_reasons:
                for reason in row_reasons:
                    invalid[reason] += 1
                continue
            assert entry is not None and exit_day is not None
            assert entry_price is not None and exit_price is not None
            assert notional is not None
            row = dict(raw)
            row.update(
                {
                    "ticker": ticker,
                    "entry_date": entry.isoformat(),
                    "exit_date": exit_day.isoformat(),
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "paper_notional_usd": float(notional),
                }
            )
            if notional_was_derived:
                row["paper_notional_derivation"] = "shares * entry_price"
                derived_notional += 1
            window_rows.append(row)
            valid += 1
        normalized[window] = window_rows
        per_window[window] = {
            "source_rows": len(raw_rows),
            "replayable_rows": len(window_rows),
        }
    audit = {
        "source_row_count": total,
        "replayable_row_count": valid,
        "excluded_embedded_row_count": total - valid,
        "derived_paper_notional_count": derived_notional,
        "unsupported_non_long_direction_row_count": unsupported_direction_rows,
        "explicit_direction_values": dict(sorted(direction_values.items())),
        "row_exclusion_reasons": dict(sorted(invalid.items())),
        "windows": per_window,
    }
    return normalized, audit


def _surface_behavior_projection(
    surface: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    return {
        window: [
            {field: row.get(field) for field in REQUIRED_TRADE_FIELDS}
            for row in surface.get(window, [])
        ]
        for window in WINDOWS
    }


def _extract_dated_return_series(value: Any, path: str = "$") -> list[dict[str, Any]]:
    """Find exact dated daily-return arrays without retaining their raw rows."""

    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "return_series" and isinstance(child, list) and child:
                parsed: list[tuple[date, float]] = []
                valid = True
                for item in child:
                    if not isinstance(item, Mapping):
                        valid = False
                        break
                    day = legacy_pc._parse_date(item.get("date"))
                    daily_return = _finite(item.get("return"))
                    if day is None or daily_return is None:
                        valid = False
                        break
                    parsed.append((day, daily_return))
                if valid and parsed:
                    parsed.sort(key=lambda item: item[0])
                    dates = [item[0] for item in parsed]
                    returns = np.asarray([item[1] for item in parsed], dtype=float)
                    found.append(
                        {
                            "json_path": child_path,
                            "row_count": len(parsed),
                            "date_start": dates[0].isoformat(),
                            "date_end": dates[-1].isoformat(),
                            "return_series_sha256": _series_sha256(dates, returns),
                            "current_metrics": _serializable_metrics(
                                current_return_metrics(returns)
                            ),
                        }
                    )
            found.extend(_extract_dated_return_series(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (Mapping, list)):
                found.extend(_extract_dated_return_series(child, f"{path}[{index}]"))
    return found


def _candidate_family(payload: Mapping[str, Any], path: Path) -> str:
    for key in (
        "trial_family",
        "mechanism_family",
        "single_causal_variable",
        "changed_variable",
        "decision",
    ):
        value = payload.get(key)
        if value:
            return str(value)
    return path.stem


def _surface_alias_descriptor(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": row.get("experiment_id"),
        "path": row.get("path"),
        "source_sha256": row.get("source_sha256"),
        "status": row.get("status"),
        "decision": row.get("decision"),
        "family": row.get("family"),
    }


def scan_top_level_artifacts(
    log_by_id: Mapping[str, Mapping[str, Any]],
    ticket_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    exclude_experiment_ids: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Freeze all JSON experiment artifacts and select unique sleeve paths."""

    excluded = set(exclude_experiment_ids)
    ticket_by_id = ticket_by_id or {}
    manifest_rows: list[dict[str, Any]] = []
    provisional: list[dict[str, Any]] = []
    pattern = REPO_ROOT / "data" / "experiments"
    for path in sorted(pattern.glob("exp-*/**/*.json")):
        experiment_dir_id = next(
            (part for part in path.parts if part.startswith("exp-")),
            path.parent.name,
        )
        if experiment_dir_id in excluded:
            continue
        base = {
            "path": _repo_rel(path),
            "source_sha256": _sha256_file(path),
            "experiment_dir_id": experiment_dir_id,
        }
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            manifest_rows.append(
                {
                    **base,
                    "artifact_disposition": "unreadable_json",
                    "error": type(exc).__name__,
                }
            )
            continue
        if not isinstance(payload, Mapping):
            manifest_rows.append(
                {**base, "artifact_disposition": "non_object_json"}
            )
            continue
        experiment_id = experiment_dir_id
        declared_experiment_id = payload.get("experiment_id")
        exact_daily_series = _extract_dated_return_series(payload)
        surface = _target_surface(payload)
        if surface is None:
            manifest_rows.append(
                {
                    **base,
                    "experiment_id": experiment_id,
                    "declared_experiment_id": declared_experiment_id,
                    "exact_daily_series": exact_daily_series,
                    "artifact_disposition": "not_target_trade_surface",
                }
            )
            continue
        complete_windows = all(isinstance(surface.get(window), list) for window in WINDOWS)
        normalized_surface, normalization = _normalize_target_surface(surface)
        total = int(normalization["source_row_count"])
        valid = int(normalization["replayable_row_count"])
        surface_hash = _canonical_hash(
            _surface_behavior_projection(normalized_surface)
        )
        log = log_by_id.get(experiment_id) or {}
        ticket = ticket_by_id.get(experiment_id) or {}
        ticket_result = ticket.get("result")
        ticket_decision = (
            ticket_result.get("decision")
            if isinstance(ticket_result, Mapping)
            else None
        )
        lane = str(ticket.get("lane") or log.get("lane") or "")
        status = ticket.get("status") or log.get("status") or payload.get("status")
        reasons: list[str] = []
        if not complete_windows:
            reasons.append("incomplete_three_window_surface")
        if valid <= 0:
            reasons.append("no_replayable_trade_rows")
        if int(normalization["unsupported_non_long_direction_row_count"]) > 0:
            reasons.append("unsupported_non_long_direction")
        if str(status or "") in OPEN_STATUSES:
            reasons.append("experiment_not_closed")
        if lane and lane not in ALPHA_LANES:
            reasons.append("explicit_non_alpha_lane")
        row = {
            **base,
            "experiment_id": experiment_id,
            "declared_experiment_id": declared_experiment_id,
            "status": status,
            "lane": lane or None,
            "decision": ticket_decision
            or ticket.get("decision")
            or log.get("decision")
            or payload.get("decision"),
            "family": _candidate_family(payload, path),
            "target_trade_count": total,
            "valid_trade_count": valid,
            "trade_normalization": normalization,
            "exact_daily_series": exact_daily_series,
            "complete_three_window_surface": complete_windows,
            "trade_surface_sha256": surface_hash,
            "artifact_disposition": "provisionally_eligible" if not reasons else "excluded",
            "exclusion_reasons": reasons,
        }
        manifest_rows.append(row)
        if not reasons:
            provisional.append(row)

    first_by_surface: dict[str, dict[str, Any]] = {}
    for row in sorted(provisional, key=lambda item: str(item["path"])):
        surface_hash = str(row["trade_surface_sha256"])
        first = first_by_surface.get(surface_hash)
        if first is None:
            first_by_surface[surface_hash] = row
            row["artifact_disposition"] = "eligible_unique_trade_surface"
            row["surface_aliases"] = [_surface_alias_descriptor(row)]
        else:
            row["artifact_disposition"] = "duplicate_trade_surface"
            row["duplicate_of"] = first["path"]
            row["exclusion_reasons"] = ["duplicate_trade_surface"]
            first["surface_aliases"].append(_surface_alias_descriptor(row))

    for row in first_by_surface.values():
        aliases = row.get("surface_aliases") or []
        row["surface_alias_count"] = len(aliases)
        row["surface_alias_statuses"] = sorted(
            {str(alias.get("status") or "missing") for alias in aliases}
        )
        row["surface_alias_decisions"] = sorted(
            {str(alias.get("decision") or "missing") for alias in aliases}
        )

    eligible = [
        row
        for row in manifest_rows
        if row.get("artifact_disposition") == "eligible_unique_trade_surface"
    ]
    counts_by_experiment = Counter(str(row["experiment_id"]) for row in eligible)
    for row in eligible:
        experiment_id = str(row["experiment_id"])
        if counts_by_experiment[experiment_id] == 1:
            row["candidate_id"] = experiment_id
        else:
            stem = Path(str(row["path"])).stem
            row["candidate_id"] = (
                f"{experiment_id}::{stem}::{str(row['trade_surface_sha256'])[:8]}"
            )

    summary = {
        "experiment_json_artifact_count": len(manifest_rows),
        "top_level_json_count": sum(
            len(Path(str(row["path"])).relative_to("data/experiments").parts) == 2
            for row in manifest_rows
        ),
        "target_trade_artifact_count": sum(
            "trade_surface_sha256" in row for row in manifest_rows
        ),
        "eligible_unique_trade_surface_count": len(eligible),
        "eligible_trade_count": sum(int(row["target_trade_count"]) for row in eligible),
        "eligible_replayable_trade_count": sum(
            int(row["valid_trade_count"]) for row in eligible
        ),
        "derived_paper_notional_row_count": sum(
            int((row.get("trade_normalization") or {}).get("derived_paper_notional_count") or 0)
            for row in eligible
        ),
        "excluded_embedded_row_count": sum(
            int((row.get("trade_normalization") or {}).get("excluded_embedded_row_count") or 0)
            for row in eligible
        ),
        "unsupported_non_long_surface_count": sum(
            "unsupported_non_long_direction" in (row.get("exclusion_reasons") or [])
            for row in manifest_rows
        ),
        "eligible_surfaces_with_at_least_20_trades": sum(
            int(row["valid_trade_count"]) >= 20 for row in eligible
        ),
        "artifact_with_exact_daily_series_count": sum(
            bool(row.get("exact_daily_series")) for row in manifest_rows
        ),
        "exact_daily_series_count": sum(
            len(row.get("exact_daily_series") or []) for row in manifest_rows
        ),
        "aliased_behavior_surface_count": sum(
            int(row.get("surface_alias_count") or 0) > 1 for row in eligible
        ),
        "duplicate_alias_artifact_count": sum(
            max(0, int(row.get("surface_alias_count") or 0) - 1)
            for row in eligible
        ),
        "mixed_status_alias_surface_count": sum(
            len(row.get("surface_alias_statuses") or []) > 1 for row in eligible
        ),
        "artifact_disposition_counts": dict(
            sorted(Counter(str(row["artifact_disposition"]) for row in manifest_rows).items())
        ),
    }
    return manifest_rows, eligible, summary


def current_return_metrics(
    returns: Sequence[float] | np.ndarray,
    *,
    capital: float = PORTFOLIO_CAPITAL_USD,
) -> dict[str, float | int]:
    """Full-precision Gate 4-P metrics under the current EV sign contract."""

    values = np.asarray(returns, dtype=float)
    if values.ndim != 1 or not len(values):
        return {
            "days": 0,
            "total_return_fraction": 0.0,
            "total_pnl": 0.0,
            "sharpe_daily": 0.0,
            "expected_value_score": 0.0,
            "max_drawdown_pct": 0.0,
            "expected_shortfall_95": 0.0,
        }
    if np.any(values <= -1.0) or not np.all(np.isfinite(values)):
        raise ValueError("returns must be finite and greater than -100%")
    total_return = float(np.prod(1.0 + values) - 1.0)
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    sharpe = float(np.mean(values) / std * math.sqrt(252.0)) if std > 0 else 0.0
    score = expected_value_score_raw(total_return, sharpe)
    assert score is not None
    equity = np.concatenate(([1.0], np.cumprod(1.0 + values)))
    peaks = np.maximum.accumulate(equity)
    tail_count = max(1, int(math.ceil(0.05 * len(values))))
    worst = np.partition(values, tail_count - 1)[:tail_count]
    return {
        "days": int(len(values)),
        "total_return_fraction": total_return,
        "total_pnl": capital * total_return,
        "sharpe_daily": sharpe,
        "expected_value_score": float(score),
        "max_drawdown_pct": float(np.max((peaks - equity) / peaks)),
        "expected_shortfall_95": max(0.0, -float(np.mean(worst))),
    }


def current_bootstrap_ev(values: np.ndarray) -> np.ndarray:
    """Vectorized full-precision current-contract EV for bootstrap rows."""

    total_return = np.expm1(np.log1p(values).sum(axis=1))
    means = values.mean(axis=1)
    stds = values.std(axis=1, ddof=1)
    sharpes = np.divide(
        means * math.sqrt(252.0),
        stds,
        out=np.zeros_like(means),
        where=stds > 0.0,
    )
    return total_return * np.abs(sharpes)


def _metric_delta(
    after: Mapping[str, Any], before: Mapping[str, Any]
) -> dict[str, float]:
    keys = (
        "total_return_fraction",
        "total_pnl",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "expected_shortfall_95",
    )
    return {key: float(after[key]) - float(before[key]) for key in keys}


def _serializable_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (float, np.floating)):
            result[key] = round(float(value), 12)
        elif isinstance(value, (int, np.integer)):
            result[key] = int(value)
        else:
            result[key] = value
    return result


def _enforce_candidate_window_coverage(
    gate_report: dict[str, Any],
    *,
    candidate_trade_window_count: int,
    minimum: int,
) -> dict[str, Any]:
    """Add the candidate-specific coverage evidence missing from Gate 4-P v1.

    All three portfolio contributions must remain in the gate because an empty
    candidate leg still displaces 10% of core.  That is distinct from whether
    the candidate itself produced funded trades in at least two windows.
    """

    gate_report.setdefault("metrics", {})["candidate_trade_window_count"] = (
        candidate_trade_window_count
    )
    covered = candidate_trade_window_count >= minimum
    gate_report.setdefault("checks", {})["candidate_trade_window_coverage"] = covered
    if covered:
        return gate_report
    blocker = "insufficient_candidate_window_coverage"
    for key in ("measurement_blockers", "evidence_blockers"):
        values = gate_report.setdefault(key, [])
        if blocker not in values:
            values.append(blocker)
    gate_report["passed"] = False
    if not gate_report.get("hard_failures"):
        gate_report["status"] = "watch"
        gate_report["portfolio_verdict"] = "portfolio_forward_watch"
    return gate_report


def _series_sha256(calendar: Sequence[date], values: np.ndarray) -> str:
    return _canonical_hash(
        [
            {"date": day.isoformat(), "return": float(value)}
            for day, value in zip(calendar, values)
        ]
    )


def load_active_core() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[date]],
    dict[str, np.ndarray],
    dict[str, Any],
]:
    summary_path = _repo_path(ACTIVE_BASELINE_SUMMARY)
    summary = _read_json(summary_path)
    if not isinstance(summary, Mapping) or summary.get("experiment_id") != "exp-20260715-010":
        raise ValueError("active baseline summary is not exp-20260715-010")
    core_payloads: dict[str, dict[str, Any]] = {}
    calendars: dict[str, list[date]] = {}
    returns: dict[str, np.ndarray] = {}
    identity_rows: dict[str, Any] = {}
    summary_windows = {
        str(row.get("label")): row
        for row in summary.get("windows") or []
        if isinstance(row, Mapping)
    }
    for window, rel_path in ACTIVE_CORE_ARTIFACTS.items():
        payload = _read_json(rel_path)
        if not isinstance(payload, dict):
            raise ValueError(f"invalid active core artifact: {rel_path}")
        calendar, window_returns = legacy_pc.core_calendar_and_returns(payload)
        cash = payload.get("cash_ledger") or {}
        if (
            cash.get("enforced") is not True
            or int(cash.get("negative_cash_event_count") or 0) != 0
            or cash.get("cash_conservation_passed") is not True
            or abs(float(cash.get("cash_conservation_error") or 0.0)) > 1e-9
        ):
            raise ValueError(f"active core cash identity failed: {window}")
        expected = summary_windows.get(window) or {}
        actual_sha = _sha256_file(rel_path)
        if expected.get("artifact_sha256") and expected.get("artifact_sha256") != actual_sha:
            raise ValueError(f"active core artifact hash mismatch: {window}")
        core_payloads[window] = payload
        calendars[window] = calendar
        returns[window] = window_returns
        identity_rows[window] = {
            "path": rel_path.as_posix(),
            "artifact_sha256": actual_sha,
            "return_series_sha256": _series_sha256(calendar, window_returns),
            "days": len(calendar),
            "cash_ledger": {
                "enforced": True,
                "negative_cash_event_count": 0,
                "cash_conservation_passed": True,
                "cash_conservation_error": float(
                    cash.get("cash_conservation_error") or 0.0
                ),
                "min_cash": cash.get("min_cash"),
            },
        }
    return core_payloads, calendars, returns, {
        "summary_path": ACTIVE_BASELINE_SUMMARY.as_posix(),
        "summary_sha256": _sha256_file(summary_path),
        "experiment_id": summary.get("experiment_id"),
        "protocol_id": summary.get("protocol_id"),
        "windows": identity_rows,
    }


def simultaneous_current_bounds(
    core_returns: Mapping[str, np.ndarray],
    candidate_returns: Mapping[str, Mapping[str, np.ndarray]],
    *,
    replicates: int,
    block_length: int,
    seed: int,
    confidence: float = 0.90,
) -> dict[str, Any]:
    candidate_ids = sorted(candidate_returns)
    if not candidate_ids:
        raise ValueError("candidate panel is empty")
    rng = np.random.default_rng(seed)
    indices_by_window: dict[str, np.ndarray] = {}
    bootstrap_core: dict[str, np.ndarray] = {}
    for window in WINDOWS:
        core = np.asarray(core_returns[window], dtype=float)
        indices = legacy_pc.circular_block_indices(
            len(core),
            replicates=replicates,
            block_length=block_length,
            rng=rng,
        )
        indices_by_window[window] = indices
        bootstrap_core[window] = current_bootstrap_ev(core[indices])

    observed = np.zeros(len(candidate_ids), dtype=float)
    bootstrap = np.zeros((replicates, len(candidate_ids)), dtype=float)
    for column, candidate_id in enumerate(candidate_ids):
        for window in WINDOWS:
            core = np.asarray(core_returns[window], dtype=float)
            candidate = np.asarray(candidate_returns[candidate_id][window], dtype=float)
            combined = CORE_WEIGHT * core + CANDIDATE_WEIGHT * candidate
            observed[column] += float(
                current_return_metrics(combined)["expected_value_score"]
            ) - float(current_return_metrics(core)["expected_value_score"])
            indices = indices_by_window[window]
            bootstrap[:, column] += current_bootstrap_ev(
                combined[indices]
            ) - bootstrap_core[window]

    lower, standard_errors, critical = legacy_pc.max_t_lower_bounds(
        observed,
        bootstrap,
        confidence=confidence,
    )
    return {
        "candidate_ids": candidate_ids,
        "observed_aggregate_ev_delta": observed.tolist(),
        "bootstrap_standard_error": standard_errors.tolist(),
        "simultaneous_lower_bound": lower.tolist(),
        "critical_max_t": critical,
        "confidence": confidence,
        "replicates": replicates,
        "block_length": block_length,
        "seed": seed,
        "score_contract": CURRENT_SCORE_CONTRACT,
    }


def _load_candidate_payloads(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    payloads: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in candidates:
        candidate_id = str(row["candidate_id"])
        payload = _read_json(str(row["path"]))
        if not isinstance(payload, dict):
            raise ValueError(f"candidate payload is not an object: {row['path']}")
        surface = payload.get("target_trades_by_window")
        if not isinstance(surface, dict):
            raise ValueError(f"candidate surface disappeared: {row['path']}")
        if _sha256_file(str(row["path"])) != row["source_sha256"]:
            raise ValueError(f"candidate source hash changed during run: {row['path']}")
        normalized_surface, _ = _normalize_target_surface(surface)
        normalized_hash = _canonical_hash(
            _surface_behavior_projection(normalized_surface)
        )
        if normalized_hash != row["trade_surface_sha256"]:
            raise ValueError(f"candidate behavior surface changed: {row['path']}")
        normalized_payload = dict(payload)
        normalized_payload["target_trades_by_window"] = normalized_surface
        payloads.append(normalized_payload)
        by_id[candidate_id] = normalized_payload
    return payloads, by_id


def _snapshot_from_warehouse(
    *,
    output_dir: Path,
    warehouse_path: str | Path,
    payloads: Sequence[Mapping[str, Any]],
    calendars: Mapping[str, Sequence[date]],
) -> tuple[list[dict[str, Any]], set[tuple[str, date]]]:
    potential_pairs = legacy_pc._required_pairs_for_panel(payloads, calendars)
    ohlcv_rows, missing = legacy_pc.load_exact_ohlcv_rows(
        warehouse_path, potential_pairs
    )
    if missing:
        raise ValueError(f"warehouse is missing {len(missing)} potential OHLCV rows")
    return ohlcv_rows, potential_pairs


def _write_ohlcv_snapshot(
    output_dir: Path,
    *,
    experiment_id: str,
    rows: Sequence[Mapping[str, Any]],
    potential_pairs: set[tuple[str, date]],
    actual_consumed_pairs: set[tuple[str, date]],
) -> dict[str, Any]:
    """Write a deterministic, correctly attributed Gate 4-P rowset."""

    payload = {
        "schema": "ginger.historical_current_contract_ohlcv_rowset.v1",
        "experiment_id": experiment_id,
        "selection_contract": (
            "reproducibility superset of potential fixed-calendar OHLCV rows; "
            "actual_consumed_pair_count reflects cash-funded rows"
        ),
        "potential_requested_pair_count": len(potential_pairs),
        "actual_consumed_pair_count": len(actual_consumed_pairs),
        "unused_superset_pair_count": len(potential_pairs - actual_consumed_pairs),
        "row_count": len(rows),
        "missing_pairs": [],
        "missing_actual_consumed_pairs": [],
        "rows": list(rows),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    snapshot_path = output_dir / "candidate_ohlcv_rowset.json.gz"
    snapshot_path.write_bytes(compressed)
    gzip_sha = _sha256_bytes(compressed)
    canonical_sha = _sha256_bytes(raw)
    sha_path = output_dir / "candidate_ohlcv_rowset.json.gz.sha256"
    sha_path.write_text(f"{gzip_sha}  {snapshot_path.name}\n", encoding="ascii")
    return {
        "path": _repo_rel(snapshot_path),
        "sha256_path": _repo_rel(sha_path),
        "gzip_sha256": gzip_sha,
        "canonical_json_sha256": canonical_sha,
        "selection_contract": payload["selection_contract"],
        "potential_requested_pair_count": len(potential_pairs),
        "actual_consumed_pair_count": len(actual_consumed_pairs),
        "unused_superset_pair_count": len(potential_pairs - actual_consumed_pairs),
        "row_count": len(rows),
        "missing_pair_count": 0,
        "missing_actual_consumed_pair_count": 0,
    }


def _load_ohlcv_snapshot(
    snapshot_path: str | Path,
    *,
    expected_experiment_id: str | None = None,
    expected_gzip_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved = _repo_path(snapshot_path)
    compressed = resolved.read_bytes()
    actual_gzip_sha256 = _sha256_bytes(compressed)
    if actual_gzip_sha256 != expected_gzip_sha256:
        raise ValueError("frozen OHLCV snapshot SHA256 mismatch")
    sidecar = resolved.with_name(f"{resolved.name}.sha256")
    if not sidecar.exists():
        raise ValueError("frozen OHLCV snapshot SHA256 sidecar is missing")
    sidecar_parts = sidecar.read_text(encoding="ascii").strip().split()
    if not sidecar_parts or sidecar_parts[0] != actual_gzip_sha256:
        raise ValueError("frozen OHLCV snapshot SHA256 sidecar mismatch")
    raw = gzip.decompress(compressed)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, Mapping) or not isinstance(payload.get("rows"), list):
        raise ValueError("invalid frozen OHLCV snapshot")
    if expected_experiment_id and payload.get("experiment_id") != expected_experiment_id:
        raise ValueError("frozen OHLCV snapshot experiment identity mismatch")
    rows = [dict(row) for row in payload["rows"] if isinstance(row, Mapping)]
    if len(rows) != len(payload["rows"]):
        raise ValueError("frozen OHLCV snapshot contains non-object rows")
    identity = {
        "path": _repo_rel(resolved),
        "gzip_sha256": actual_gzip_sha256,
        "sha256_path": _repo_rel(sidecar),
        "canonical_json_sha256": _sha256_bytes(raw),
        "row_count": len(rows),
        "potential_requested_pair_count": payload.get(
            "potential_requested_pair_count"
        ),
        "actual_consumed_pair_count": payload.get("actual_consumed_pair_count"),
    }
    return rows, identity


def run_gate4p_panel(
    candidates: Sequence[Mapping[str, Any]],
    *,
    experiment_id: str,
    output_dir: str | Path,
    warehouse_path: str | Path = DEFAULT_WAREHOUSE,
    ohlcv_snapshot_path: str | Path | None = None,
    ohlcv_snapshot_sha256: str | None = None,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    block_length: int = DEFAULT_BLOCK_LENGTH,
) -> dict[str, Any]:
    """Run the fixed Gate 4-P contract on the complete recoverable panel."""

    output = _repo_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    core_payloads, calendars, core_returns, core_identity = load_active_core()
    payloads, payload_by_id = _load_candidate_payloads(candidates)
    potential_pairs = legacy_pc._required_pairs_for_panel(payloads, calendars)
    snapshot_replay_identity: dict[str, Any] | None = None
    if ohlcv_snapshot_path is None:
        ohlcv_rows, warehouse_pairs = _snapshot_from_warehouse(
            output_dir=output,
            warehouse_path=warehouse_path,
            payloads=payloads,
            calendars=calendars,
        )
        if warehouse_pairs != potential_pairs:
            raise AssertionError("warehouse pair selection changed during replay")
    else:
        if not ohlcv_snapshot_sha256:
            raise ValueError("frozen OHLCV replay requires its expected SHA256")
        ohlcv_rows, snapshot_replay_identity = _load_ohlcv_snapshot(
            ohlcv_snapshot_path,
            expected_experiment_id=experiment_id,
            expected_gzip_sha256=ohlcv_snapshot_sha256,
        )
    price_map = legacy_pc._price_map_from_rows(ohlcv_rows)

    allocations: dict[str, dict[str, dict[str, Any]]] = {}
    allocated_payloads: list[dict[str, Any]] = []
    for row in candidates:
        candidate_id = str(row["candidate_id"])
        surface = payload_by_id[candidate_id]["target_trades_by_window"]
        window_allocations = {
            window: legacy_pc.allocate_sleeve_capital(
                surface[window],
                calendars[window],
                sleeve_capital=CANDIDATE_CAPITAL_USD,
                price_map=price_map,
            )
            for window in WINDOWS
        }
        allocations[candidate_id] = window_allocations
        allocated_payloads.append(
            {
                "target_trades_by_window": {
                    window: window_allocations[window]["allocated_rows"]
                    for window in WINDOWS
                }
            }
        )

    actual_pairs = legacy_pc._required_pairs_for_panel(
        allocated_payloads, calendars
    )
    available_pairs = {
        (
            str(row.get("ticker") or "").strip().upper(),
            legacy_pc._parse_date(row.get("date")),
        )
        for row in ohlcv_rows
    }
    available_pairs = {
        (ticker, day)
        for ticker, day in available_pairs
        if ticker and day is not None
    }
    missing_potential = potential_pairs - available_pairs
    if missing_potential:
        raise ValueError(
            f"replay rowset is missing {len(missing_potential)} potential OHLCV rows"
        )
    missing_actual = actual_pairs - available_pairs
    if missing_actual:
        raise ValueError(f"cash-funded paths are missing {len(missing_actual)} OHLCV rows")
    if ohlcv_snapshot_path is None:
        snapshot = _write_ohlcv_snapshot(
            output,
            experiment_id=experiment_id,
            rows=ohlcv_rows,
            potential_pairs=potential_pairs,
            actual_consumed_pairs=actual_pairs,
        )
    else:
        snapshot = {
            **(snapshot_replay_identity or {}),
            "selection_contract": "replayed from frozen exact OHLCV rowset",
            "actual_recomputed_potential_pair_count": len(potential_pairs),
            "actual_recomputed_consumed_pair_count": len(actual_pairs),
            "missing_pair_count": len(potential_pairs - available_pairs),
            "missing_actual_consumed_pair_count": len(missing_actual),
        }

    core_contributions: list[tuple[str, float]] = []
    for window in WINDOWS:
        for trade in core_payloads[window].get("trades") or []:
            if not isinstance(trade, Mapping):
                continue
            ticker = str(trade.get("ticker") or "").strip().upper()
            pnl = _finite(trade.get("pnl"))
            if ticker and pnl is not None:
                core_contributions.append((ticker, pnl))
    core_concentration = legacy_pc._concentration(core_contributions)

    result_rows: list[dict[str, Any]] = []
    return_panel: dict[str, dict[str, np.ndarray]] = {}
    contribution_by_id: dict[str, list[tuple[str, float]]] = {}
    metadata_by_id = {str(row["candidate_id"]): row for row in candidates}
    for candidate_id in sorted(payload_by_id):
        window_results: dict[str, Any] = {}
        window_returns: dict[str, np.ndarray] = {}
        trade_contributions: list[tuple[str, float]] = []
        usable_count = 0
        excluded_count = 0
        unusable_count = 0
        forced_count = 0
        max_reconciliation_error = 0.0
        normal_reconciliation_errors: list[float] = []
        for window in WINDOWS:
            pnl_by_day: defaultdict[date, float] = defaultdict(float)
            window_usable_count = 0
            window_excluded_count = 0
            window_unusable_count = 0
            allocation = allocations[candidate_id][window]
            allocation_excluded = int(allocation["zero_fill_count"]) + int(
                allocation["boundary_excluded_count"]
            )
            allocation_unusable = int(allocation["invalid_count"])
            excluded_count += allocation_excluded
            unusable_count += allocation_unusable
            window_excluded_count += allocation_excluded
            window_unusable_count += allocation_unusable
            missing_mark_count = 0
            for trade in allocation["allocated_rows"]:
                series, diagnostic = legacy_pc.reconstruct_trade_daily_pnl(
                    trade,
                    calendars[window],
                    price_map,
                )
                if diagnostic.get("usable"):
                    usable_count += 1
                    window_usable_count += 1
                    forced_count += int(bool(diagnostic.get("forced_close")))
                    ticker = str(diagnostic["ticker"])
                    net_pnl = float(diagnostic["net_pnl"])
                    trade_contributions.append((ticker, net_pnl))
                    error = diagnostic.get("normal_exit_reconciliation_error")
                    if error is not None:
                        normal_reconciliation_errors.append(float(error))
                        max_reconciliation_error = max(
                            max_reconciliation_error, abs(float(error))
                        )
                    missing_mark_count += len(
                        diagnostic.get("missing_intermediate_closes") or []
                    )
                    for day, value in series.items():
                        pnl_by_day[day] += float(value)
                elif diagnostic.get("excluded"):
                    excluded_count += 1
                    window_excluded_count += 1
                else:
                    unusable_count += 1
                    window_unusable_count += 1

            candidate_returns = legacy_pc.pnl_to_returns(
                pnl_by_day,
                calendars[window],
                initial_capital=CANDIDATE_CAPITAL_USD,
            )
            core = core_returns[window]
            combined = CORE_WEIGHT * core + CANDIDATE_WEIGHT * candidate_returns
            cash = CORE_WEIGHT * core
            core_metrics = current_return_metrics(core)
            candidate_metrics = current_return_metrics(
                candidate_returns, capital=CANDIDATE_CAPITAL_USD
            )
            combined_metrics = current_return_metrics(combined)
            cash_metrics = current_return_metrics(cash)
            allocation_report = {
                key: value
                for key, value in allocation.items()
                if key not in {"allocated_rows", "cash_events", "diagnostics"}
            }
            cash_events = allocation.get("cash_events") or []
            allocation_diagnostics = allocation.get("diagnostics") or []
            ending_equity = CANDIDATE_CAPITAL_USD + sum(pnl_by_day.values())
            ending_cash = _finite(allocation.get("ending_cash_usd"))
            allocation_report.update(
                {
                    "ending_mtm_equity_usd": ending_equity,
                    "mtm_net_pnl_usd": sum(pnl_by_day.values()),
                    "ending_cash_equity_reconciliation_error_usd": (
                        ending_equity - ending_cash
                        if ending_cash is not None
                        else None
                    ),
                    "ending_cash_equity_reconciled": (
                        ending_cash is not None
                        and abs(ending_equity - ending_cash) <= 1e-6
                    ),
                    "cash_event_count": len(cash_events),
                    "cash_events_sha256": _canonical_hash(cash_events),
                    "allocation_diagnostic_count": len(allocation_diagnostics),
                    "allocation_diagnostics_sha256": _canonical_hash(
                        allocation_diagnostics
                    ),
                }
            )
            window_results[window] = {
                "calendar_start": calendars[window][0].isoformat(),
                "calendar_end": calendars[window][-1].isoformat(),
                "calendar_days": len(calendars[window]),
                "source_trade_count": len(surface[window]),
                "usable_trade_count": window_usable_count,
                "excluded_trade_count": window_excluded_count,
                "unusable_trade_count": window_unusable_count,
                "core_metrics": _serializable_metrics(core_metrics),
                "candidate_metrics": _serializable_metrics(candidate_metrics),
                "combined_metrics": _serializable_metrics(combined_metrics),
                "cash_comparator_metrics": _serializable_metrics(cash_metrics),
                "formal_delta_vs_full_core": _serializable_metrics(
                    _metric_delta(combined_metrics, core_metrics)
                ),
                "diagnostic_delta_vs_90_core_10_cash": _serializable_metrics(
                    _metric_delta(combined_metrics, cash_metrics)
                ),
                "core_candidate_daily_return_correlation": legacy_pc._pearson(
                    core, candidate_returns
                ),
                "candidate_return_series_sha256": _series_sha256(
                    calendars[window], candidate_returns
                ),
                "allocation": allocation_report,
                "missing_intermediate_mark_count": missing_mark_count,
            }
            window_returns[window] = candidate_returns

        return_panel[candidate_id] = window_returns
        contribution_by_id[candidate_id] = trade_contributions
        candidate_trade_window_count = sum(
            int(window_results[window]["usable_trade_count"]) > 0
            for window in WINDOWS
        )
        if not all(
            bool(window_results[window]["allocation"].get("cash_nonnegative"))
            for window in WINDOWS
        ):
            raise AssertionError(
                f"cash ledger created leverage for candidate {candidate_id}"
            )
        if not all(
            bool(
                window_results[window]["allocation"].get(
                    "ending_all_positions_settled"
                )
            )
            for window in WINDOWS
        ):
            raise AssertionError(
                f"cash ledger left positions unsettled for candidate {candidate_id}"
            )
        if not all(
            bool(
                window_results[window]["allocation"].get(
                    "ending_cash_equity_reconciled"
                )
            )
            for window in WINDOWS
        ):
            raise AssertionError(
                f"cash/MTM ending equity mismatch for candidate {candidate_id}"
            )
        result_rows.append(
            {
                "candidate_id": candidate_id,
                "experiment_id": metadata_by_id[candidate_id]["experiment_id"],
                "family": metadata_by_id[candidate_id]["family"],
                "source_path": metadata_by_id[candidate_id]["path"],
                "source_sha256": metadata_by_id[candidate_id]["source_sha256"],
                "trade_surface_sha256": metadata_by_id[candidate_id][
                    "trade_surface_sha256"
                ],
                "historical_status": metadata_by_id[candidate_id].get("status"),
                "historical_decision": metadata_by_id[candidate_id].get("decision"),
                "surface_aliases": metadata_by_id[candidate_id].get(
                    "surface_aliases"
                )
                or [],
                "surface_alias_count": int(
                    metadata_by_id[candidate_id].get("surface_alias_count") or 1
                ),
                "partial_surface_recovery": bool(
                    int(
                        (
                            metadata_by_id[candidate_id].get("trade_normalization")
                            or {}
                        ).get("excluded_embedded_row_count")
                        or 0
                    )
                ),
                "source_trade_normalization": metadata_by_id[candidate_id].get(
                    "trade_normalization"
                ),
                "usable_trade_count": usable_count,
                "candidate_trade_window_count": candidate_trade_window_count,
                "excluded_trade_count": excluded_count,
                "unusable_trade_count": unusable_count,
                "forced_close_count": forced_count,
                "max_abs_normal_exit_reconciliation_error_usd": max_reconciliation_error,
                "historical_source_pnl_reconciliation": {
                    "normal_exit_comparison_count": len(
                        normal_reconciliation_errors
                    ),
                    "max_abs_error_usd": max_reconciliation_error,
                    "mean_abs_error_usd": float(
                        np.mean(np.abs(normal_reconciliation_errors))
                    )
                    if normal_reconciliation_errors
                    else 0.0,
                    "mismatch_over_0_011_usd": max_reconciliation_error > 0.011,
                    "measurement_role": (
                        "diagnostic_only; historical source pnl is not reused in "
                        "the current notional/price/cost replay"
                    ),
                },
                "capital_allocation": {
                    "all_windows_cash_nonnegative": True,
                    "all_windows_ending_cash_equity_reconciled": True,
                    "minimum_cash_usd": min(
                        float(window_results[window]["allocation"]["min_cash_usd"])
                        for window in WINDOWS
                    ),
                    "filled_notional_usd": sum(
                        float(
                            window_results[window]["allocation"][
                                "filled_notional_usd"
                            ]
                        )
                        for window in WINDOWS
                    ),
                },
                "windows": window_results,
            }
        )

    inference = simultaneous_current_bounds(
        core_returns,
        return_panel,
        replicates=bootstrap_replicates,
        block_length=block_length,
        seed=bootstrap_seed,
    )
    inference_index = {
        candidate_id: index
        for index, candidate_id in enumerate(inference["candidate_ids"])
    }
    thresholds = replace(
        DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS,
        required_family_count=len(result_rows),
    )
    for row in result_rows:
        candidate_id = str(row["candidate_id"])
        index = inference_index[candidate_id]
        windows = row["windows"]
        aggregate_ev = sum(
            float(windows[window]["formal_delta_vs_full_core"]["expected_value_score"])
            for window in WINDOWS
        )
        aggregate_pnl = sum(
            float(windows[window]["formal_delta_vs_full_core"]["total_pnl"])
            for window in WINDOWS
        )
        diagnostic_ev = sum(
            float(
                windows[window]["diagnostic_delta_vs_90_core_10_cash"][
                    "expected_value_score"
                ]
            )
            for window in WINDOWS
        )
        diagnostic_pnl = sum(
            float(
                windows[window]["diagnostic_delta_vs_90_core_10_cash"]["total_pnl"]
            )
            for window in WINDOWS
        )
        worst_drawdown = max(
            float(windows[window]["formal_delta_vs_full_core"]["max_drawdown_pct"])
            for window in WINDOWS
        )
        es_worsening: list[float] = []
        for window in WINDOWS:
            core_es = float(windows[window]["core_metrics"]["expected_shortfall_95"])
            combined_es = float(
                windows[window]["combined_metrics"]["expected_shortfall_95"]
            )
            if core_es > 0.0:
                es_worsening.append((combined_es - core_es) / core_es)
            elif combined_es <= 0.0:
                es_worsening.append(0.0)
            else:
                es_worsening.append(float("inf"))
        combined_concentration = legacy_pc._concentration(
            [(ticker, CORE_WEIGHT * pnl) for ticker, pnl in core_contributions]
            + contribution_by_id[candidate_id]
        )
        lower_bound = float(inference["simultaneous_lower_bound"][index])
        gate_metrics = {
            "capital_neutral": True,
            "candidate_weight": CANDIDATE_WEIGHT,
            "core_weight": CORE_WEIGHT,
            "portfolio_weight_sum": 1.0,
            "aggregate_ev_delta": aggregate_ev,
            "aggregate_pnl_delta": aggregate_pnl,
            "affected_trade_count": int(row["usable_trade_count"]),
            "affected_window_count": len(WINDOWS),
            "candidate_trade_window_count": int(
                row["candidate_trade_window_count"]
            ),
            "window_contributions": {
                window: {
                    "core_ev": windows[window]["core_metrics"][
                        "expected_value_score"
                    ],
                    "ev_delta": windows[window]["formal_delta_vs_full_core"][
                        "expected_value_score"
                    ],
                    "pnl_delta": windows[window]["formal_delta_vs_full_core"][
                        "total_pnl"
                    ],
                }
                for window in WINDOWS
            },
            "max_drawdown_worse": worst_drawdown,
            "es95_worsening_fraction": max(es_worsening) if es_worsening else None,
            "concentration": combined_concentration,
            "single_ticker_positive_share": combined_concentration[
                "single_ticker_positive_share"
            ],
            "top_5_contribution_pct": combined_concentration[
                "top_5_contribution_pct"
            ],
            "hhi_concentration": combined_concentration["hhi_concentration"],
            "family_batch_complete": True,
            "expected_family_count": len(result_rows),
            "observed_family_count": len(result_rows),
            "selection_panel_complete": False,
            "multiple_testing_passed": lower_bound > 0.0,
            "simultaneous_ev_delta_lower_bound": lower_bound,
        }
        gate = evaluate_portfolio_contribution_gate(
            gate_metrics, thresholds=thresholds
        )
        gate = _enforce_candidate_window_coverage(
            gate,
            candidate_trade_window_count=int(row["candidate_trade_window_count"]),
            minimum=thresholds.min_affected_windows,
        )
        row["aggregate"] = {
            "formal_vs_full_core": {
                "aggregate_ev_delta": aggregate_ev,
                "aggregate_pnl_delta": aggregate_pnl,
                "core_expected_value_score_sum": sum(
                    float(windows[window]["core_metrics"]["expected_value_score"])
                    for window in WINDOWS
                ),
                "combined_expected_value_score_sum": sum(
                    float(
                        windows[window]["combined_metrics"]["expected_value_score"]
                    )
                    for window in WINDOWS
                ),
                "core_total_pnl_sum": sum(
                    float(windows[window]["core_metrics"]["total_pnl"])
                    for window in WINDOWS
                ),
                "combined_total_pnl_sum": sum(
                    float(windows[window]["combined_metrics"]["total_pnl"])
                    for window in WINDOWS
                ),
            },
            "diagnostic_vs_90_core_10_cash": {
                "aggregate_ev_delta": diagnostic_ev,
                "aggregate_pnl_delta": diagnostic_pnl,
            },
            "worst_max_drawdown_worse": worst_drawdown,
            "worst_es95_worsening_fraction": max(es_worsening)
            if es_worsening
            else None,
            "core_concentration_proxy": core_concentration,
            "combined_concentration_proxy": combined_concentration,
            "simultaneous_inference": {
                "observed_aggregate_ev_delta": float(
                    inference["observed_aggregate_ev_delta"][index]
                ),
                "bootstrap_standard_error": float(
                    inference["bootstrap_standard_error"][index]
                ),
                "simultaneous_90pct_lower_bound": lower_bound,
                "multiple_testing_passed": lower_bound > 0.0,
            },
        }
        row["gate_report"] = gate
        row["gate_metrics"] = gate_metrics
        row["strict_verdict"] = gate["portfolio_verdict"]

    result_rows.sort(
        key=lambda row: (
            float(row["aggregate"]["formal_vs_full_core"]["aggregate_ev_delta"]),
            float(row["aggregate"]["formal_vs_full_core"]["aggregate_pnl_delta"]),
        ),
        reverse=True,
    )
    verdict_counts = Counter(str(row["strict_verdict"]) for row in result_rows)
    positive_both = [
        row
        for row in result_rows
        if float(row["aggregate"]["formal_vs_full_core"]["aggregate_ev_delta"])
        > 0.0
        and float(row["aggregate"]["formal_vs_full_core"]["aggregate_pnl_delta"])
        > 0.0
    ]
    forward_watch = [
        row for row in result_rows if row["strict_verdict"] == "portfolio_forward_watch"
    ]
    contract_checks = {
        "candidate_batch_count_matches_manifest": len(result_rows) == len(candidates),
        "bootstrap_replicates_10000": bootstrap_replicates
        == DEFAULT_BOOTSTRAP_REPLICATES,
        "bootstrap_block_length_20": block_length == DEFAULT_BLOCK_LENGTH,
        "bootstrap_confidence_90pct": math.isclose(
            float(inference["confidence"]), 0.90, rel_tol=0.0, abs_tol=1e-12
        ),
        "ohlcv_potential_rows_complete": int(snapshot.get("missing_pair_count") or 0)
        == 0,
        "ohlcv_consumed_rows_complete": int(
            snapshot.get("missing_actual_consumed_pair_count") or 0
        )
        == 0,
        "all_runtime_trades_replayable": all(
            int(row["unusable_trade_count"]) == 0 for row in result_rows
        ),
        "all_candidate_ledgers_cash_nonnegative": all(
            all(
                bool(row["windows"][window]["allocation"]["cash_nonnegative"])
                for window in WINDOWS
            )
            for row in result_rows
        ),
        "all_candidate_positions_settled": all(
            all(
                bool(
                    row["windows"][window]["allocation"][
                        "ending_all_positions_settled"
                    ]
                )
                for window in WINDOWS
            )
            for row in result_rows
        ),
        "all_candidate_cash_mtm_reconciled": all(
            all(
                bool(
                    row["windows"][window]["allocation"][
                        "ending_cash_equity_reconciled"
                    ]
                )
                for window in WINDOWS
            )
            for row in result_rows
        ),
        "active_core_identity_complete": bool(core_identity.get("summary_sha256"))
        and set((core_identity.get("windows") or {}).keys()) == set(WINDOWS)
        and all(
            bool((core_identity["windows"][window] or {}).get("artifact_sha256"))
            and bool(
                (core_identity["windows"][window] or {}).get(
                    "return_series_sha256"
                )
            )
            for window in WINDOWS
        ),
        "candidate_source_hashes_locked": all(
            bool(row.get("source_sha256")) and bool(row.get("trade_surface_sha256"))
            for row in result_rows
        ),
    }
    canonical_measurement_contract_passed = all(contract_checks.values())
    return {
        "schema": "ginger.historical_current_contract_gate4p_panel.v1",
        "generated_at": _utc_now(),
        "evaluation_mode": "portfolio_contribution",
        "score_contract": CURRENT_SCORE_CONTRACT,
        "capital_contract": {
            "core_weight": CORE_WEIGHT,
            "candidate_weight": CANDIDATE_WEIGHT,
            "candidate_initial_cash_usd": CANDIDATE_CAPITAL_USD,
            "portfolio_initial_capital_usd": PORTFOLIO_CAPITAL_USD,
            "one_way_extra_cost_fraction": legacy_pc.ONE_WAY_COST_FRACTION,
            "forced_exit_slippage_fraction": legacy_pc.FORCED_EXIT_SLIPPAGE_FRACTION,
            "capital_neutral": True,
            "no_leverage": True,
        },
        "selection_contract": {
            "recoverable_eligible_alpha_behavior_surface_batch_complete": True,
            "historical_selection_panel_complete": False,
            "paper_acceptance_capped": True,
            "artifact_scope": "data/experiments/exp-*/**/*.json",
            "reason": (
                "The repository manifest is exhaustive for currently recoverable "
                "eligible alpha behavior surfaces, including exact aliases, but "
                "the original adaptive research trial space and untouched holdout "
                "were not preserved."
            ),
        },
        "core_identity": core_identity,
        "ohlcv_snapshot": snapshot,
        "bootstrap": {
            key: inference[key]
            for key in (
                "replicates",
                "block_length",
                "seed",
                "confidence",
                "critical_max_t",
                "score_contract",
            )
        },
        "gate_thresholds": asdict(thresholds),
        "measurement_contract_checks": contract_checks,
        "canonical_measurement_contract_passed": (
            canonical_measurement_contract_passed
        ),
        "candidate_count": len(result_rows),
        "candidate_zero_trade_window_count": sum(
            int(row["candidate_trade_window_count"]) == 0 for row in result_rows
        ),
        "candidate_single_trade_window_count": sum(
            int(row["candidate_trade_window_count"]) == 1 for row in result_rows
        ),
        "candidate_two_trade_window_count": sum(
            int(row["candidate_trade_window_count"]) == 2 for row in result_rows
        ),
        "candidate_three_trade_window_count": sum(
            int(row["candidate_trade_window_count"]) == 3 for row in result_rows
        ),
        "candidate_trade_window_coverage_blocked_count": sum(
            int(row["candidate_trade_window_count"])
            < thresholds.min_affected_windows
            for row in result_rows
        ),
        "partial_surface_recovery_count": sum(
            bool(row.get("partial_surface_recovery")) for row in result_rows
        ),
        "historical_source_pnl_reconciliation_mismatch_candidate_count": sum(
            bool(
                row["historical_source_pnl_reconciliation"][
                    "mismatch_over_0_011_usd"
                ]
            )
            for row in result_rows
        ),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "formal_positive_ev_count": sum(
            float(row["aggregate"]["formal_vs_full_core"]["aggregate_ev_delta"])
            > 0.0
            for row in result_rows
        ),
        "formal_positive_pnl_count": sum(
            float(row["aggregate"]["formal_vs_full_core"]["aggregate_pnl_delta"])
            > 0.0
            for row in result_rows
        ),
        "formal_positive_ev_and_pnl_count": len(positive_both),
        "cash_positive_ev_and_pnl_count": sum(
            float(
                row["aggregate"]["diagnostic_vs_90_core_10_cash"][
                    "aggregate_ev_delta"
                ]
            )
            > 0.0
            and float(
                row["aggregate"]["diagnostic_vs_90_core_10_cash"][
                    "aggregate_pnl_delta"
                ]
            )
            > 0.0
            for row in result_rows
        ),
        "simultaneous_positive_lower_bound_count": sum(
            float(
                row["aggregate"]["simultaneous_inference"][
                    "simultaneous_90pct_lower_bound"
                ]
            )
            > 0.0
            for row in result_rows
        ),
        "portfolio_forward_watch_count": len(forward_watch),
        "forward_watch_candidate_ids": [row["candidate_id"] for row in forward_watch],
        "top_by_formal_ev": [
            {
                "candidate_id": row["candidate_id"],
                "experiment_id": row["experiment_id"],
                "family": row["family"],
                "source_path": row["source_path"],
                "strict_verdict": row["strict_verdict"],
                "formal_vs_full_core": row["aggregate"]["formal_vs_full_core"],
                "diagnostic_vs_90_core_10_cash": row["aggregate"][
                    "diagnostic_vs_90_core_10_cash"
                ],
                "worst_max_drawdown_worse": row["aggregate"][
                    "worst_max_drawdown_worse"
                ],
                "worst_es95_worsening_fraction": row["aggregate"][
                    "worst_es95_worsening_fraction"
                ],
                "simultaneous_90pct_lower_bound": row["aggregate"][
                    "simultaneous_inference"
                ]["simultaneous_90pct_lower_bound"],
            }
            for row in result_rows[:25]
        ],
        "candidates": result_rows,
    }


def run_reassessment(
    *,
    experiment_id: str,
    output_dir: str | Path,
    warehouse_path: str | Path = DEFAULT_WAREHOUSE,
    ohlcv_snapshot_path: str | Path | None = None,
    ohlcv_snapshot_sha256: str | None = None,
    evidence_manifest_path: str | Path | None = None,
    evidence_manifest_sha256: str | None = None,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    block_length: int = DEFAULT_BLOCK_LENGTH,
) -> dict[str, Any]:
    """Freeze manifests, run Gate 4-P, and write the current-contract audit."""

    output = _repo_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    excluded_ids = {experiment_id}
    if ohlcv_snapshot_path is not None and evidence_manifest_path is None:
        raise ValueError(
            "frozen OHLCV replay also requires --evidence-manifest so the "
            "multiple-testing candidate panel cannot drift"
        )
    if evidence_manifest_path is not None and not evidence_manifest_sha256:
        raise ValueError(
            "frozen evidence replay requires --evidence-manifest-sha256"
        )
    if ohlcv_snapshot_path is not None and not ohlcv_snapshot_sha256:
        raise ValueError(
            "frozen OHLCV replay requires --ohlcv-snapshot-sha256"
        )
    if evidence_manifest_path is not None:
        manifest_path = _repo_path(evidence_manifest_path)
        if _sha256_file(manifest_path) != evidence_manifest_sha256:
            raise ValueError("frozen evidence manifest SHA256 mismatch")
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, Mapping):
            raise ValueError("frozen evidence manifest must be a JSON object")
        if manifest.get("schema") != "ginger.historical_current_contract_manifest.v1":
            raise ValueError("unexpected frozen evidence manifest schema")
        if manifest.get("experiment_id") != experiment_id:
            raise ValueError("frozen evidence manifest experiment identity mismatch")
        eligible_raw = manifest.get("eligible_candidates")
        if not isinstance(eligible_raw, list) or not eligible_raw:
            raise ValueError("frozen evidence manifest has no eligible candidate panel")
        eligible = [dict(row) for row in eligible_raw if isinstance(row, Mapping)]
        if len(eligible) != len(eligible_raw):
            raise ValueError("frozen evidence manifest candidate panel is malformed")
        ticket_summary = dict(manifest.get("ticket_summary") or {})
        log_summary = dict(manifest.get("log_summary") or {})
        artifact_summary = dict(manifest.get("artifact_summary") or {})
        if int(artifact_summary.get("eligible_unique_trade_surface_count") or -1) != len(
            eligible
        ):
            raise ValueError("frozen evidence manifest candidate count mismatch")
        manifest_replay = True
    else:
        tickets, ticket_summary, ticket_by_id = scan_experiment_tickets(
            exclude_experiment_ids=excluded_ids
        )
        logs, log_summary, log_by_id = scan_experiment_logs(
            exclude_experiment_ids=excluded_ids
        )
        artifacts, eligible, artifact_summary = scan_top_level_artifacts(
            log_by_id,
            ticket_by_id,
            exclude_experiment_ids=excluded_ids,
        )
        manifest = {
            "schema": "ginger.historical_current_contract_manifest.v1",
            "experiment_id": experiment_id,
            "frozen_at": _utc_now(),
            "score_contract": CURRENT_SCORE_CONTRACT,
            "active_baseline": ACTIVE_BASELINE_SUMMARY.as_posix(),
            "exclusions": {
                "current_experiment_ids": sorted(excluded_ids),
                "artifact_scope": "data/experiments/exp-*/**/*.json",
            },
            "ticket_summary": ticket_summary,
            "log_summary": log_summary,
            "artifact_summary": artifact_summary,
            "tickets": tickets,
            "logs": logs,
            "artifacts": artifacts,
            "eligible_candidates": eligible,
        }
        manifest_path = output / "historical_evidence_manifest.json"
        _write_json(manifest_path, manifest)
        manifest_replay = False
    manifest_sha = _sha256_file(manifest_path)

    panel = run_gate4p_panel(
        eligible,
        experiment_id=experiment_id,
        output_dir=output,
        warehouse_path=warehouse_path,
        ohlcv_snapshot_path=ohlcv_snapshot_path,
        ohlcv_snapshot_sha256=ohlcv_snapshot_sha256,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        block_length=block_length,
    )
    panel["experiment_id"] = experiment_id
    panel["historical_evidence_manifest"] = {
        "path": _repo_rel(manifest_path),
        "sha256": manifest_sha,
        "frozen_replay": manifest_replay,
    }
    panel_path = output / "historical_gate4p_panel.json"
    _write_json(panel_path, panel)

    watch_rows = [
        row for row in panel["candidates"] if row["strict_verdict"] == "portfolio_forward_watch"
    ]
    legacy_rejected_watch: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for row in watch_rows:
        aliases = row.get("surface_aliases") or [
            {
                "experiment_id": row.get("experiment_id"),
                "path": row.get("source_path"),
                "status": row.get("historical_status"),
                "decision": row.get("historical_decision"),
                "family": row.get("family"),
            }
        ]
        rejected_aliases = [
            alias
            for alias in aliases
            if "reject" in str(alias.get("status") or "").lower()
            or "reject" in str(alias.get("decision") or "").lower()
        ]
        if rejected_aliases:
            legacy_rejected_watch.append((row, rejected_aliases))
    measurement_checks = {
        "candidate_count_matches_manifest": panel["candidate_count"]
        == artifact_summary["eligible_unique_trade_surface_count"],
        **panel["measurement_contract_checks"],
    }
    measurement_contract_passed = all(measurement_checks.values())
    summary = {
        "schema": "ginger.historical_current_contract_reassessment_summary.v1",
        "experiment_id": experiment_id,
        "generated_at": _utc_now(),
        "decision": "accepted_measurement_repair"
        if measurement_contract_passed
        else "blocked_noncanonical_or_incomplete_measurement",
        "accepted_alpha": False,
        "production_impact": "none",
        "historical_verdicts_rewritten": False,
        "frozen_evidence_manifest_replay": manifest_replay,
        "score_contract": CURRENT_SCORE_CONTRACT,
        "active_baseline": panel["core_identity"],
        "historical_ticket_summary": ticket_summary,
        "historical_log_summary": log_summary,
        "historical_artifact_summary": artifact_summary,
        "measurement_contract_checks": measurement_checks,
        "measurement_contract_passed": measurement_contract_passed,
        "gate4p_summary": {
            key: panel[key]
            for key in (
                "candidate_count",
                "verdict_counts",
                "formal_positive_ev_count",
                "formal_positive_pnl_count",
                "formal_positive_ev_and_pnl_count",
                "cash_positive_ev_and_pnl_count",
                "simultaneous_positive_lower_bound_count",
                "portfolio_forward_watch_count",
                "forward_watch_candidate_ids",
                "top_by_formal_ev",
                "partial_surface_recovery_count",
                "historical_source_pnl_reconciliation_mismatch_candidate_count",
                "candidate_zero_trade_window_count",
                "candidate_single_trade_window_count",
                "candidate_two_trade_window_count",
                "candidate_three_trade_window_count",
                "candidate_trade_window_coverage_blocked_count",
            )
        },
        "legacy_rejected_forward_watch_count": len(legacy_rejected_watch),
        "legacy_rejected_forward_watch_alias_count": sum(
            len(aliases) for _, aliases in legacy_rejected_watch
        ),
        "legacy_rejected_forward_watch": [
            {
                "candidate_id": row["candidate_id"],
                "experiment_id": row["experiment_id"],
                "family": row["family"],
                "source_path": row["source_path"],
                "rejected_surface_aliases": rejected_aliases,
                "all_surface_aliases": row.get("surface_aliases") or [],
                "formal": row["aggregate"]["formal_vs_full_core"],
                "diagnostic_vs_cash": row["aggregate"][
                    "diagnostic_vs_90_core_10_cash"
                ],
                "risk": {
                    "worst_max_drawdown_worse": row["aggregate"][
                        "worst_max_drawdown_worse"
                    ],
                    "worst_es95_worsening_fraction": row["aggregate"][
                        "worst_es95_worsening_fraction"
                    ],
                },
                "simultaneous": row["aggregate"]["simultaneous_inference"],
            }
            for row, rejected_aliases in legacy_rejected_watch
        ],
        "limitations": [
            "Fixed historical windows were adaptively reused and are not an untouched holdout.",
            "The manifest is exhaustive only for currently recoverable repository artifacts.",
            "The original full adaptive trial/selection history is incomplete, so positive Gate 4-P economics cannot exceed portfolio_forward_watch.",
            "One behavior surface is a partial recovery with embedded signal-only observer rows explicitly excluded; its provenance is flagged on the candidate.",
            "Historical stored pnl is diagnostic only: candidates are rebuilt from normalized notional, entry/exit prices, cash admission, and the current 45bp round-trip cost contract; source-pnl reconciliation mismatches are counted separately.",
            "Historical strategy verdicts remain immutable provenance; this audit creates leads, not retroactive acceptances.",
        ],
        "artifacts": {
            "manifest": {
                "path": _repo_rel(manifest_path),
                "sha256": manifest_sha,
            },
            "panel": {
                "path": _repo_rel(panel_path),
                "sha256": _sha256_file(panel_path),
            },
            "ohlcv_snapshot": panel["ohlcv_snapshot"],
        },
    }
    summary_path = output / "historical_current_contract_reassessment_summary.json"
    _write_json(summary_path, summary)
    summary["artifacts"]["summary"] = {
        "path": _repo_rel(summary_path),
        "sha256": _sha256_file(summary_path),
    }
    return summary


__all__ = [
    "ACTIVE_BASELINE_SUMMARY",
    "ACTIVE_CORE_ARTIFACTS",
    "CURRENT_SCORE_CONTRACT",
    "current_bootstrap_ev",
    "current_return_metrics",
    "run_gate4p_panel",
    "run_reassessment",
    "scan_experiment_logs",
    "scan_experiment_tickets",
    "scan_top_level_artifacts",
    "simultaneous_current_bounds",
]
