"""Forward observation ledger for core risk-intensity attribution.

The ledger is read-only research infrastructure. It records already-sized daily
entry candidates so observed forward outcomes can later test whether the
exp-20260622-019/020 risk-intensity lead survives out of sample.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RULE_VERSION = "core_risk_intensity_forward_observation_v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "core_risk_intensity_forward_observation"
    / "snapshots.jsonl"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _rounded(value: float | None, digits: int = 8) -> float | None:
    return round(value, digits) if value is not None else None


def _sizing(signal: dict[str, Any]) -> dict[str, Any]:
    sizing = signal.get("sizing")
    return sizing if isinstance(sizing, dict) else {}


def _risk_multiplier_items(sizing: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in sizing.items():
        if not str(key).endswith("_risk_multiplier_applied"):
            continue
        numeric = _as_float(value)
        if numeric is None:
            continue
        out[str(key)] = numeric
    return out


def _non_neutral_risk_multiplier_items(sizing: dict[str, Any]) -> dict[str, float]:
    return {
        key: value
        for key, value in _risk_multiplier_items(sizing).items()
        if abs(value - 1.0) > 1e-12
    }


def _signal_signature(signal: dict[str, Any]) -> tuple[Any, ...]:
    sizing = _sizing(signal)
    return (
        str(signal.get("ticker") or ""),
        str(signal.get("strategy") or signal.get("signal_type") or ""),
        _rounded(_as_float(signal.get("entry_price") or sizing.get("entry_price")), 4),
        _rounded(_as_float(signal.get("stop_price") or sizing.get("stop_price")), 4),
        _rounded(_as_float(sizing.get("base_risk_pct")), 8),
        _rounded(_as_float(sizing.get("risk_pct") or sizing.get("actual_risk_pct")), 8),
    )


def _signature_set(signals: list[dict[str, Any]] | None) -> set[tuple[Any, ...]]:
    return {_signal_signature(signal) for signal in signals or []}


def _status_sets(
    selected_signals: list[dict[str, Any]] | None,
    entry_execution_plan: dict[str, Any] | None,
) -> dict[str, set[tuple[Any, ...]]]:
    plan = entry_execution_plan or {}
    return {
        "selected": _signature_set(selected_signals),
        "slot_sliced": _signature_set(plan.get("slot_sliced_signals") or []),
        "deferred_breakout": _signature_set(plan.get("deferred_breakout_signals") or []),
    }


def _candidate_status(
    signal: dict[str, Any],
    status_sets: dict[str, set[tuple[Any, ...]]],
) -> str:
    signature = _signal_signature(signal)
    if signature in status_sets["selected"]:
        return "selected"
    if signature in status_sets["slot_sliced"]:
        return "slot_sliced"
    if signature in status_sets["deferred_breakout"]:
        return "deferred_breakout"
    return "observed_sized_candidate"


def _observation_id(row: dict[str, Any]) -> str:
    raw = "|".join(
        str(row.get(key) or "")
        for key in (
            "as_of",
            "ticker",
            "strategy",
            "candidate_status",
            "entry_price",
            "stop_price",
            "base_risk_pct",
            "actual_risk_pct",
            "risk_intensity",
        )
    )
    return hashlib.sha256(f"{RULE_VERSION}|{raw}".encode("utf-8")).hexdigest()[:24]


def _row_from_signal(
    signal: dict[str, Any],
    *,
    as_of: str,
    candidate_status: str,
) -> tuple[dict[str, Any] | None, str | None]:
    sizing = _sizing(signal)
    base_risk_pct = _as_float(sizing.get("base_risk_pct"))
    actual_risk_pct = _as_float(sizing.get("risk_pct") or sizing.get("actual_risk_pct"))
    if base_risk_pct is None or base_risk_pct <= 0:
        return None, "missing_or_nonpositive_base_risk_pct"
    if actual_risk_pct is None or actual_risk_pct <= 0:
        return None, "missing_or_nonpositive_actual_risk_pct"

    all_multipliers = _risk_multiplier_items(sizing)
    non_neutral = _non_neutral_risk_multiplier_items(sizing)
    entry_price = _as_float(signal.get("entry_price") or sizing.get("entry_price"))
    stop_price = _as_float(signal.get("stop_price") or sizing.get("stop_price"))
    target_price = _as_float(signal.get("target_price") or sizing.get("target_price"))
    risk_intensity = actual_risk_pct / base_risk_pct
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "as_of": as_of,
        "generated_at": utc_now(),
        "trade_enabled": False,
        "ticker": signal.get("ticker"),
        "strategy": signal.get("strategy") or signal.get("signal_type"),
        "sector": signal.get("sector"),
        "candidate_status": candidate_status,
        "entry_price": _rounded(entry_price, 4),
        "stop_price": _rounded(stop_price, 4),
        "target_price": _rounded(target_price, 4),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "position_value_usd": _rounded(_as_float(sizing.get("position_value_usd")), 2),
        "base_risk_pct": _rounded(base_risk_pct, 8),
        "actual_risk_pct": _rounded(actual_risk_pct, 8),
        "risk_intensity": _rounded(risk_intensity, 8),
        "risk_amount_usd": _rounded(_as_float(sizing.get("risk_amount_usd")), 2),
        "risk_multiplier_count": len(non_neutral),
        "risk_multiplier_keys": sorted(non_neutral),
        "risk_multipliers": non_neutral,
        "all_risk_multipliers": all_multipliers,
        "source": "quant.run.sized_entry_candidates",
    }
    row["observation_id"] = _observation_id(row)
    return row, None


def _attach_daily_rank_fields(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            -(rows[index].get("risk_intensity") or 0.0),
            str(rows[index].get("ticker") or ""),
            str(rows[index].get("strategy") or ""),
            str(rows[index].get("observation_id") or ""),
        ),
    )
    total = len(ordered)
    if total == 0:
        return
    for rank_index, row_index in enumerate(ordered, start=1):
        row = rows[row_index]
        row["risk_intensity_rank_desc"] = rank_index
        row["risk_intensity_candidate_count"] = total
        row["risk_intensity_percentile_desc"] = round(rank_index / total, 6)
        if total == 1:
            row["risk_intensity_daily_bucket"] = "only"
        elif rank_index <= math.ceil(total / 3):
            row["risk_intensity_daily_bucket"] = "high"
        elif rank_index > math.ceil(2 * total / 3):
            row["risk_intensity_daily_bucket"] = "low"
        else:
            row["risk_intensity_daily_bucket"] = "mid"


def build_core_risk_intensity_observation_snapshot(
    *,
    as_of: str,
    advisory_signals: list[dict[str, Any]] | None,
    selected_signals: list[dict[str, Any]] | None = None,
    entry_execution_plan: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only daily risk-intensity observation snapshot."""
    status_sets = _status_sets(selected_signals, entry_execution_plan)
    rows: list[dict[str, Any]] = []
    skip_reasons: dict[str, int] = {}
    for signal in advisory_signals or []:
        row, skip_reason = _row_from_signal(
            signal,
            as_of=as_of,
            candidate_status=_candidate_status(signal, status_sets),
        )
        if row is None:
            skip_reasons[skip_reason or "unknown"] = skip_reasons.get(skip_reason or "unknown", 0) + 1
            continue
        rows.append(row)
    _attach_daily_rank_fields(rows)
    selected_count = sum(1 for row in rows if row["candidate_status"] == "selected")
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "as_of": as_of,
        "generated_at": utc_now(),
        "trade_enabled": False,
        "candidate_count": len(rows),
        "selected_count": selected_count,
        "skipped_count": sum(skip_reasons.values()),
        "skip_reasons": skip_reasons,
        "rows": rows,
        "metadata": metadata or {},
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "daily_snapshot_exposed": True,
            "append_only_forward_observation": True,
        },
    }


def _existing_observation_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        observation_id = row.get("observation_id")
        if observation_id:
            ids.add(str(observation_id))
    return ids


def append_core_risk_intensity_observation_snapshot(
    snapshot: dict[str, Any],
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Append new observation rows to the forward ledger without duplicates."""
    path = Path(ledger_path) if ledger_path is not None else DEFAULT_LEDGER_PATH
    rows = list(snapshot.get("rows") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = _existing_observation_ids(path)
    new_rows = [
        row for row in rows if str(row.get("observation_id") or "") not in existing_ids
    ]
    if new_rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return {
        "ledger_path": str(path),
        "rows_seen": len(rows),
        "rows_written": len(new_rows),
        "rows_skipped_duplicate": len(rows) - len(new_rows),
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
    }
