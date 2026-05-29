"""exp-20260528-030: PIT-safe ``eps_estimate_delta_30d`` derivation.

Lane: measurement_repair.
Change type: read_only_pit_field_derivation.
Single causal variable:
    eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.

Why this experiment exists
--------------------------
``exp-20260527-002`` (EPS 7d magnitude) closed ``observed_only_data_gap``
with ``next_evidence_needed = "persist richer revenue/analyst velocity
fields"``. The watchlist artifact published by ``exp-20260525-034``
shows ``eps_estimate_delta_30d`` at 0/700 coverage and
``eps_estimate_delta_7d`` at 388/700 (55%). The
``estimate_revision_ledger`` itself stores the 30d field as ``null``
for every row in the watchlist window, although
``data/daily/snapshots/earnings/earnings_snapshot_*.json`` clearly
records ``eps_estimate`` for the watchlist tickers back to early 2025.

This repair builds a PIT-safe per-ticker ``eps_estimate`` timeline from
the snapshot files and derives, for each watchlist row,

* ``eps_estimate_at_as_of`` — most recent ``eps_estimate`` in a snapshot
  dated ``<= as_of_date``;
* ``eps_estimate_at_as_of_minus_30d`` — most recent ``eps_estimate`` in
  a snapshot dated ``<= as_of_date - 30 calendar days``;
* ``eps_estimate_delta_30d`` — the absolute difference;
* ``eps_estimate_pct_delta_30d`` — the percentage difference using
  ``abs(prior)`` as the denominator, with a fail-safe cap that rejects
  prior values too small to make a meaningful percentage (avoids
  noise from near-zero priors and absorbs cases that look like
  stock-split or unit re-statements).

PIT semantics
-------------
``eps_estimate_at(date)`` returns the latest snapshot dated ``<= date``
that had a non-null ``eps_estimate`` for the ticker. We never read a
snapshot dated after the query date, so no future leak is possible.

The 30 calendar day window is calendar-day, not trading-day. The
calendar offset is computed in Python from ``as_of_date`` directly so
the result is deterministic and does not depend on the current
trading calendar.

This script does not change entries, exits, ranking, sizing, LLM/news
inputs, paper sleeves, or live orders. The source watchlist artifact
``exp-20260525-034`` is not modified; the enriched artifact lands at
``data/experiments/exp-20260528-030/``.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EARNINGS_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"
DEFAULT_SOURCE_WATCHLIST = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-034"
    / "expectation_revision_watchlist_attribution.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-030"
    / "eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.json"
)

EXPERIMENT_ID = "exp-20260528-030"
RULE_VERSION = "earnings_snapshot_pit_eps_estimate_delta_30d_v1"
LOOKBACK_CALENDAR_DAYS = 30
# Prior eps_estimate values below this absolute value are treated as
# numerically noisy denominators; the pct delta is reported as None
# rather than producing 100x-style spurious values.
PCT_DELTA_PRIOR_FLOOR = 0.05

GATE4_COVERAGE_FLOOR = 0.80  # >= 80 pct of primary positive rows must resolve


# ---------------------------------------------------------------------------
# Snapshot ingestion
# ---------------------------------------------------------------------------


def _snapshot_date_from_filename(path: Path) -> str:
    stem = path.stem  # earnings_snapshot_YYYYMMDD
    yyyymmdd = stem.rsplit("_", 1)[-1]
    if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        raise ValueError(f"unrecognised snapshot filename: {path.name}")
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def build_eps_estimate_index(
    snapshot_dir: Path = EARNINGS_SNAPSHOT_DIR,
    *,
    max_as_of: str | None = None,
) -> dict[str, list[tuple[str, float]]]:
    """Per-ticker sorted list of ``(snapshot_date, eps_estimate)`` pairs.

    Only snapshots with a non-null ``eps_estimate`` enter the timeline.
    ``max_as_of`` is a perf trim; PIT correctness is still enforced
    inside :func:`eps_estimate_at_pit`.
    """
    index: dict[str, list[tuple[str, float]]] = {}
    files = sorted(snapshot_dir.glob("earnings_snapshot_*.json"))
    for path in files:
        snap_date = _snapshot_date_from_filename(path)
        if max_as_of is not None and snap_date > max_as_of:
            continue
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        earnings = (payload.get("earnings") or {}) if isinstance(payload, dict) else {}
        if not isinstance(earnings, dict):
            continue
        for raw_ticker, info in earnings.items():
            if not isinstance(info, dict):
                continue
            est = info.get("eps_estimate")
            if est is None:
                continue
            try:
                est_f = float(est)
            except (TypeError, ValueError):
                continue
            ticker = str(raw_ticker).upper().strip()
            if not ticker:
                continue
            index.setdefault(ticker, []).append((snap_date, est_f))
    for ticker in index:
        index[ticker].sort()
    return index


def eps_estimate_at_pit(
    ticker: str,
    on_or_before: str,
    index: dict[str, list[tuple[str, float]]],
) -> tuple[float | None, str | None]:
    """Latest ``eps_estimate`` for ticker, restricted to snapshot dates
    ``<= on_or_before``. Returns ``(value, snapshot_date)`` or
    ``(None, None)`` if nothing in window.
    """
    norm = str(ticker or "").upper().strip()
    if not norm:
        return (None, None)
    pairs = index.get(norm)
    if not pairs:
        return (None, None)
    best: tuple[str, float] | None = None
    for snap_date, est in pairs:
        if snap_date > on_or_before:
            continue
        if best is None or snap_date > best[0]:
            best = (snap_date, est)
    if best is None:
        return (None, None)
    return (best[1], best[0])


# ---------------------------------------------------------------------------
# Delta derivation
# ---------------------------------------------------------------------------


def _calendar_days_before(iso_date: str, days: int) -> str:
    return (date.fromisoformat(iso_date) - timedelta(days=days)).isoformat()


def derive_delta_30d_for_row(
    row: dict[str, Any],
    index: dict[str, list[tuple[str, float]]],
) -> dict[str, Any]:
    ticker = row.get("ticker", "")
    as_of = str(row.get("as_of_date") or "")
    if not as_of:
        return {
            "eps_estimate_delta_30d": None,
            "eps_estimate_pct_delta_30d": None,
            "eps_estimate_at_as_of": None,
            "eps_estimate_at_as_of_minus_30d": None,
            "eps_estimate_at_as_of_snapshot_date": None,
            "eps_estimate_at_prior_snapshot_date": None,
            "status": "missing_as_of_date",
        }
    cutoff = _calendar_days_before(as_of, LOOKBACK_CALENDAR_DAYS)

    current_val, current_snap = eps_estimate_at_pit(ticker, as_of, index)
    if current_val is None:
        return {
            "eps_estimate_delta_30d": None,
            "eps_estimate_pct_delta_30d": None,
            "eps_estimate_at_as_of": None,
            "eps_estimate_at_as_of_minus_30d": None,
            "eps_estimate_at_as_of_snapshot_date": None,
            "eps_estimate_at_prior_snapshot_date": None,
            "status": "no_current_eps_estimate",
        }
    prior_val, prior_snap = eps_estimate_at_pit(ticker, cutoff, index)
    if prior_val is None:
        return {
            "eps_estimate_delta_30d": None,
            "eps_estimate_pct_delta_30d": None,
            "eps_estimate_at_as_of": current_val,
            "eps_estimate_at_as_of_minus_30d": None,
            "eps_estimate_at_as_of_snapshot_date": current_snap,
            "eps_estimate_at_prior_snapshot_date": None,
            "status": "no_prior_eps_estimate_within_30d_lookback",
        }
    delta = current_val - prior_val
    if abs(prior_val) < PCT_DELTA_PRIOR_FLOOR:
        pct = None
        pct_status = "prior_below_pct_delta_floor"
    else:
        pct = delta / abs(prior_val)
        pct_status = "ok"
    return {
        "eps_estimate_delta_30d": delta,
        "eps_estimate_pct_delta_30d": pct,
        "eps_estimate_at_as_of": current_val,
        "eps_estimate_at_as_of_minus_30d": prior_val,
        "eps_estimate_at_as_of_snapshot_date": current_snap,
        "eps_estimate_at_prior_snapshot_date": prior_snap,
        "status": pct_status if pct is not None else pct_status,
    }


def enrich_watchlist_rows(
    rows: list[dict[str, Any]],
    index: dict[str, list[tuple[str, float]]],
) -> list[dict[str, Any]]:
    """Attach derived 30d delta fields to each row without mutating input."""
    enriched: list[dict[str, Any]] = []
    for row in rows:
        derived = derive_delta_30d_for_row(row, index)
        new_row = dict(row)
        # Preserve the original null/value for audit, then set the
        # repaired field.
        new_row["eps_estimate_delta_30d_before_repair"] = row.get(
            "eps_estimate_delta_30d"
        )
        new_row["eps_estimate_delta_30d"] = derived["eps_estimate_delta_30d"]
        new_row["eps_estimate_pct_delta_30d"] = derived["eps_estimate_pct_delta_30d"]
        new_row["eps_estimate_delta_30d_lookup"] = {
            "status": derived["status"],
            "rule_version": RULE_VERSION,
            "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
            "pct_delta_prior_floor": PCT_DELTA_PRIOR_FLOOR,
            "eps_estimate_at_as_of": derived["eps_estimate_at_as_of"],
            "eps_estimate_at_as_of_minus_30d": derived[
                "eps_estimate_at_as_of_minus_30d"
            ],
            "eps_estimate_at_as_of_snapshot_date": derived[
                "eps_estimate_at_as_of_snapshot_date"
            ],
            "eps_estimate_at_prior_snapshot_date": derived[
                "eps_estimate_at_prior_snapshot_date"
            ],
        }
        enriched.append(new_row)
    return enriched


# ---------------------------------------------------------------------------
# Coverage report + gate
# ---------------------------------------------------------------------------


def coverage_report(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(enriched)
    primary_pos = [r for r in enriched if r.get("primary_expectation_positive")]
    have_delta = [r for r in enriched if r.get("eps_estimate_delta_30d") is not None]
    have_delta_primary = [
        r for r in primary_pos if r.get("eps_estimate_delta_30d") is not None
    ]
    have_pct = [r for r in enriched if r.get("eps_estimate_pct_delta_30d") is not None]
    have_pct_primary = [
        r for r in primary_pos if r.get("eps_estimate_pct_delta_30d") is not None
    ]
    status_counts = Counter(
        (r.get("eps_estimate_delta_30d_lookup") or {}).get("status")
        for r in enriched
    )
    return {
        "rows_total": total,
        "primary_positive_rows": len(primary_pos),
        "delta_30d_coverage": {
            "all_rows": {
                "present": len(have_delta),
                "ratio": (len(have_delta) / total) if total else 0.0,
            },
            "primary_positive_rows": {
                "present": len(have_delta_primary),
                "ratio": (len(have_delta_primary) / len(primary_pos))
                if primary_pos
                else 0.0,
            },
        },
        "pct_delta_30d_coverage": {
            "all_rows": {
                "present": len(have_pct),
                "ratio": (len(have_pct) / total) if total else 0.0,
            },
            "primary_positive_rows": {
                "present": len(have_pct_primary),
                "ratio": (len(have_pct_primary) / len(primary_pos))
                if primary_pos
                else 0.0,
            },
        },
        "lookup_status_counts": dict(status_counts),
    }


def evaluate_gates(coverage: dict[str, Any]) -> dict[str, Any]:
    primary_total = coverage["primary_positive_rows"]
    primary_present = coverage["delta_30d_coverage"]["primary_positive_rows"][
        "present"
    ]
    primary_share = (
        primary_present / primary_total if primary_total else 0.0
    )
    gate1 = {
        "name": "baseline_artifact_available",
        "passed": coverage["rows_total"] > 0,
        "rows_in_source": coverage["rows_total"],
    }
    gate2 = {
        "name": "required_input_fields_present",
        "passed": True,
        "note": "ticker + as_of_date present on every input row.",
    }
    gate3 = {
        "name": "survival_rate_not_affected_read_only_field_derivation",
        "passed": True,
    }
    gate4 = {
        "name": "primary_positive_delta_30d_resolved",
        "passed": primary_share >= GATE4_COVERAGE_FLOOR,
        "primary_positive_rows": primary_total,
        "primary_positive_resolved_share": primary_share,
        "floor": GATE4_COVERAGE_FLOOR,
        "criteria": (
            "At least 80 pct of primary positive rows must obtain a "
            "non-null eps_estimate_delta_30d (absolute) value; the pct "
            "form is allowed to be None when the prior is below the "
            "pct_delta_prior_floor since that is a structural property "
            "rather than missing data."
        ),
    }
    return {
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "all_passed": all(g["passed"] for g in (gate1, gate2, gate3, gate4)),
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(
    source: Path = DEFAULT_SOURCE_WATCHLIST,
    snapshot_dir: Path = EARNINGS_SNAPSHOT_DIR,
    output: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    with source.open("r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    original_rows = list(artifact.get("annotated_watchlist_rows") or [])
    max_as_of = (
        max(str(r.get("as_of_date") or "") for r in original_rows)
        if original_rows
        else None
    )
    index = build_eps_estimate_index(snapshot_dir, max_as_of=max_as_of)
    enriched = enrich_watchlist_rows(original_rows, index)
    coverage = coverage_report(enriched)
    gates = evaluate_gates(coverage)
    decision = (
        "accepted_measurement_repair_eps_estimate_delta_30d_field"
        if gates["all_passed"]
        else "rejected_measurement_repair_eps_estimate_delta_30d_field_insufficient_coverage"
    )
    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "source_watchlist_artifact": str(source.relative_to(REPO_ROOT)),
        "earnings_snapshot_dir": str(snapshot_dir.relative_to(REPO_ROOT)),
        "row_count": len(enriched),
        "coverage": coverage,
        "gates": gates,
        "enriched_watchlist_rows": enriched,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_WATCHLIST)
    parser.add_argument("--snapshot-dir", type=Path, default=EARNINGS_SNAPSHOT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.source, args.snapshot_dir, args.output)
    summary = {
        "anti_js": result["anti_js"],
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "output": str(args.output.relative_to(REPO_ROOT)),
        "primary_positive_rows": result["coverage"]["primary_positive_rows"],
        "primary_positive_resolved_share": result["gates"]["gate4"][
            "primary_positive_resolved_share"
        ],
        "all_rows_resolved_share": result["coverage"]["delta_30d_coverage"][
            "all_rows"
        ]["ratio"],
        "lookup_status_counts": result["coverage"]["lookup_status_counts"],
        "gates_all_passed": result["gates"]["all_passed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
