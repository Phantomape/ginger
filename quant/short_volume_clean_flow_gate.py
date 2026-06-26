"""Shared clean-flow quality gate from moomoo daily short-volume activity.

The gate is intentionally narrow: keep candidates unless a point-in-time
per-ticker ``short_volume_ratio`` percentile is formed and sits in the toxic
highest quintile. Missing coverage is annotated but not used as a filter.

No orders, live ranking, sizing, exits, or existing paper state are changed by
this module. Callers decide whether to apply the gate.
"""

from __future__ import annotations

import bisect
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from data_paths import DATA_ROOT
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_paths import DATA_ROOT


RULE_VERSION = "short_volume_clean_flow_gate_v1"
DEFAULT_SHORT_VOLUME_ROWS = (
    DATA_ROOT / "non_ohlcv" / "moomoo_daily_short_volume_broad" / "rows.jsonl"
)
DEFAULT_MIN_TRAILING_OBS = 30
DEFAULT_QUINTILES = 5
DEFAULT_TOXIC_QUINTILE_INDEX = 4


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _ticker(value: Any) -> str:
    return str(value or "").replace("US.", "").upper()


def load_short_volume_ratio_history(
    path: Path | str = DEFAULT_SHORT_VOLUME_ROWS,
) -> tuple[dict[str, list[tuple[str, float]]], dict[str, Any]]:
    """Load ``ticker -> [(activity_date, short_volume_ratio)]`` from JSONL."""

    source = Path(path)
    by_ticker: dict[str, list[tuple[str, float]]] = defaultdict(list)
    raw_rows = 0
    usable_rows = 0
    if source.exists():
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            raw_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = _ticker(row.get("ticker"))
            activity_date = _date10(row.get("activity_date"))
            ratio = _float_or_none(row.get("short_volume_ratio"))
            if not ticker or not activity_date or ratio is None:
                continue
            by_ticker[ticker].append((activity_date, ratio))
            usable_rows += 1
    for ticker in by_ticker:
        by_ticker[ticker].sort()
    audit = {
        "source_artifact": str(source),
        "raw_rows": raw_rows,
        "usable_rows": usable_rows,
        "distinct_tickers": len(by_ticker),
        "activity_date_min": min(
            (rows[0][0] for rows in by_ticker.values() if rows), default=None
        ),
        "activity_date_max": max(
            (rows[-1][0] for rows in by_ticker.values() if rows), default=None
        ),
        "rule_version": RULE_VERSION,
    }
    return dict(by_ticker), audit


def build_short_volume_percentile_index(
    history: dict[str, list[tuple[str, float]]],
    *,
    min_trailing_obs: int = DEFAULT_MIN_TRAILING_OBS,
) -> dict[str, tuple[list[str], list[float | None]]]:
    """Build expanding percentiles using only prior observations per ticker."""

    index: dict[str, tuple[list[str], list[float | None]]] = {}
    for ticker, rows in history.items():
        dates: list[str] = []
        percentiles: list[float | None] = []
        trailing: list[float] = []
        for activity_date, ratio in sorted(rows):
            dates.append(activity_date)
            if len(trailing) >= min_trailing_obs:
                percentiles.append(sum(1 for item in trailing if item < ratio) / len(trailing))
            else:
                percentiles.append(None)
            trailing.append(ratio)
        index[_ticker(ticker)] = (dates, percentiles)
    return index


def percentile_asof(
    index: dict[str, tuple[list[str], list[float | None]]],
    ticker: str,
    cutoff_date: str,
    *,
    include_cutoff: bool,
) -> tuple[float | None, str | None]:
    """Return the latest formed percentile before or on ``cutoff_date``."""

    ticker_u = _ticker(ticker)
    cutoff = _date10(cutoff_date)
    if not ticker_u or not cutoff or ticker_u not in index:
        return None, None
    dates, percentiles = index[ticker_u]
    if not dates:
        return None, None
    pos = (
        bisect.bisect_right(dates, cutoff) - 1
        if include_cutoff
        else bisect.bisect_left(dates, cutoff) - 1
    )
    while pos >= 0:
        percentile = percentiles[pos]
        if percentile is not None:
            return percentile, dates[pos]
        pos -= 1
    return None, None


def quintile(
    percentile: float,
    *,
    quintiles: int = DEFAULT_QUINTILES,
) -> int:
    return min(quintiles - 1, int(percentile * quintiles))


def annotate_candidate(
    row: dict[str, Any],
    index: dict[str, tuple[list[str], list[float | None]]],
    *,
    quintiles: int = DEFAULT_QUINTILES,
    toxic_quintile_index: int = DEFAULT_TOXIC_QUINTILE_INDEX,
) -> dict[str, Any]:
    """Attach clean-flow gate fields to a candidate row."""

    ticker = _ticker(row.get("ticker") or row.get("symbol"))
    entry_date = _date10(row.get("entry_date"))
    signal_date = _date10(row.get("signal_date") or row.get("date") or row.get("as_of"))
    if entry_date:
        percentile, activity_date = percentile_asof(
            index,
            ticker,
            entry_date,
            include_cutoff=False,
        )
        cutoff_basis = "entry_date_strictly_prior_activity"
    elif signal_date:
        percentile, activity_date = percentile_asof(
            index,
            ticker,
            signal_date,
            include_cutoff=True,
        )
        cutoff_basis = "signal_date_activity_available_after_close"
    else:
        percentile, activity_date = None, None
        cutoff_basis = "missing_candidate_date"

    if percentile is None:
        q = None
        passed = True
        reason = "missing_short_volume_percentile_kept"
    else:
        q = quintile(percentile, quintiles=quintiles)
        passed = q < toxic_quintile_index
        reason = "clean_flow_pass" if passed else "toxic_short_volume_quintile"

    out = dict(row)
    out.update(
        {
            "clean_flow_gate_rule_version": RULE_VERSION,
            "clean_flow_gate_passed": passed,
            "clean_flow_gate_reason": reason,
            "short_volume_ratio_percentile": (
                round(percentile, 6) if percentile is not None else None
            ),
            "short_volume_ratio_quintile": q,
            "short_volume_ratio_activity_date": activity_date,
            "short_volume_ratio_cutoff_basis": cutoff_basis,
        }
    )
    return out


def apply_clean_flow_gate(
    rows: list[dict[str, Any]],
    index: dict[str, tuple[list[str], list[float | None]]],
    *,
    quintiles: int = DEFAULT_QUINTILES,
    toxic_quintile_index: int = DEFAULT_TOXIC_QUINTILE_INDEX,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return ``(kept, rejected, audit)`` for the fixed clean-flow gate."""

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    quintile_counts: Counter[str] = Counter()
    for row in rows:
        annotated = annotate_candidate(
            row,
            index,
            quintiles=quintiles,
            toxic_quintile_index=toxic_quintile_index,
        )
        reason = str(annotated["clean_flow_gate_reason"])
        reason_counts[reason] += 1
        q = annotated.get("short_volume_ratio_quintile")
        quintile_counts["missing" if q is None else f"Q{int(q) + 1}"] += 1
        if annotated["clean_flow_gate_passed"]:
            kept.append(annotated)
        else:
            rejected.append(annotated)
    audit = {
        "rule_version": RULE_VERSION,
        "input_count": len(rows),
        "kept_count": len(kept),
        "rejected_count": len(rejected),
        "reason_counts": dict(reason_counts),
        "quintile_counts": dict(quintile_counts),
        "quintiles": quintiles,
        "toxic_quintile_index": toxic_quintile_index,
        "toxic_quintile_label": f"Q{toxic_quintile_index + 1}",
        "missing_percentile_kept": True,
    }
    return kept, rejected, audit
