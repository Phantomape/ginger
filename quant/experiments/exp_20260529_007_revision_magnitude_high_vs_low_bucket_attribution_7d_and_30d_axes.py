"""exp-20260529-007: Revision magnitude high-vs-low attribution (7d + 30d axes).

Lane: alpha_discovery.
Change type: read_only_revision_magnitude_attribution.
Single causal variable:
    revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes.

Why this experiment exists
--------------------------
``exp-20260527-002`` ("larger PIT 7d EPS revisions should beat smaller
ones") closed ``observed_only_data_gap`` because the watchlist had only
the 7d magnitude axis populated (55%) and no 30d axis at all.
``exp-20260528-030`` filled ``eps_estimate_delta_30d`` (80.85% on
primary positive rows). This experiment re-runs the magnitude
hypothesis with both axes now available.

Hypothesis
----------
Within positive expectation revision rows, *larger* revisions should
produce higher forward returns than *smaller* revisions. If true, a
high-magnitude bucket should beat a low-magnitude bucket at 5d / 10d.

Method
------
For each magnitude axis (``eps_estimate_delta_7d`` and
``eps_estimate_delta_30d``):

1. Take primary-positive rows with a positive revision on that axis.
2. Split at the median of the positive deltas into ``high_magnitude``
   (strictly above the median) and ``low_magnitude`` (at or below).
3. Compare ``high_magnitude`` vs ``low_magnitude`` at 5d (primary) and
   10d (secondary): avg_return, win_rate, tail loss, concentration.

The split point and bucket members are recorded so the comparison is
fully reproducible.

Gate 4
------
Mirrors ``exp-20260527-002``'s published ``gate_thresholds``. An axis
is "decisive" only when both its high and low buckets meet the
``min_bucket_closed_5d`` floor.

* If at least one decisive axis shows ``high - low`` 5d avg-return lift
  ``>= LIFT_FLOOR`` with concentration limits passed ->
  ``accepted_revision_magnitude_edge``.
* If every decisive axis shows ``high - low`` 5d lift ``<= 0`` ->
  ``rejected_no_revision_magnitude_edge``.
* If no axis is decisive (both axes too thin) ->
  ``observed_only_thin_magnitude_buckets``.

This experiment is strictly read-only: it changes no entries, exits,
ranking, sizing, LLM/news inputs, paper sleeves, or live orders.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-030"
    / "eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260529-007"
    / "revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes.json"
)

EXPERIMENT_ID = "exp-20260529-007"
RULE_VERSION = "revision_magnitude_high_vs_low_attribution_v1"

PUBLISHED_GATE_THRESHOLDS = {
    "max_single_ticker_positive_share": 0.5,
    "max_top5_positive_share": 0.6,
    "min_bucket_closed_10d": 5,
    "min_bucket_closed_5d": 8,
}
LIFT_FLOOR = 0.01  # 1 pp 5d avg return required to call an axis "accepted"

PRIMARY_HORIZON = "5d"
SECONDARY_HORIZON = "10d"

MAGNITUDE_AXES = ("eps_estimate_delta_7d", "eps_estimate_delta_30d")


# ---------------------------------------------------------------------------
# Stats helpers (same protocol as exp-20260528-027/028)
# ---------------------------------------------------------------------------


def _closed_rows(rows: Iterable[dict[str, Any]], horizon: str) -> list[dict[str, Any]]:
    return [
        r
        for r in rows
        if ((r.get("forward_outcomes") or {}).get(horizon) or {}).get("closed")
    ]


def horizon_stats(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    closed = _closed_rows(rows, horizon)
    returns = [
        r["forward_outcomes"][horizon]["return"]
        for r in closed
        if r["forward_outcomes"][horizon].get("return") is not None
    ]
    pnl_pairs = [
        (r, r["forward_outcomes"][horizon].get("pnl_proxy") or 0.0)
        for r in closed
    ]
    positive_pairs = [(r, p) for r, p in pnl_pairs if p > 0]
    positive_total = sum(p for _r, p in positive_pairs)
    top5_positive = sum(
        p for _r, p in sorted(positive_pairs, key=lambda x: x[1], reverse=True)[:5]
    )
    by_ticker_positive: Counter[str] = Counter()
    for r, p in positive_pairs:
        by_ticker_positive[r.get("ticker", "")] += p
    max_single = max(by_ticker_positive.values()) if by_ticker_positive else 0.0
    return {
        "row_count": len(rows),
        "closed_count": len(closed),
        "avg_return": (sum(returns) / len(returns)) if returns else None,
        "win_rate": (
            sum(1 for r in returns if r > 0) / len(returns) if returns else None
        ),
        "tail_loss": min(returns) if returns else None,
        "total_pnl_proxy": sum(p for _r, p in pnl_pairs),
        "positive_pnl_proxy": positive_total,
        "top5_positive_share": (
            top5_positive / positive_total if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            max_single / positive_total if positive_total > 0 else None
        ),
    }


def _diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


# ---------------------------------------------------------------------------
# Axis attribution
# ---------------------------------------------------------------------------


def split_axis(
    rows: list[dict[str, Any]],
    axis: str,
) -> dict[str, Any]:
    """Split primary-positive rows with a positive delta on ``axis`` into
    high / low magnitude buckets at the median of the positive deltas."""
    positive = [
        r
        for r in rows
        if r.get("primary_expectation_positive")
        and r.get(axis) is not None
        and float(r[axis]) > 0
    ]
    deltas = sorted(float(r[axis]) for r in positive)
    if not deltas:
        return {
            "axis": axis,
            "positive_row_count": 0,
            "median_split": None,
            "high_magnitude": [],
            "low_magnitude": [],
        }
    median = statistics.median(deltas)
    high = [r for r in positive if float(r[axis]) > median]
    low = [r for r in positive if float(r[axis]) <= median]
    return {
        "axis": axis,
        "positive_row_count": len(positive),
        "median_split": median,
        "high_magnitude": high,
        "low_magnitude": low,
    }


def axis_attribution(
    rows: list[dict[str, Any]],
    axis: str,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    split = split_axis(rows, axis)
    high = split["high_magnitude"]
    low = split["low_magnitude"]
    high_stats = {
        PRIMARY_HORIZON: horizon_stats(high, PRIMARY_HORIZON),
        SECONDARY_HORIZON: horizon_stats(high, SECONDARY_HORIZON),
    }
    low_stats = {
        PRIMARY_HORIZON: horizon_stats(low, PRIMARY_HORIZON),
        SECONDARY_HORIZON: horizon_stats(low, SECONDARY_HORIZON),
    }

    horizons: dict[str, Any] = {}
    decisive_by_horizon: dict[str, bool] = {}
    concentration_by_horizon: dict[str, bool] = {}
    for horizon, min_key in (
        (PRIMARY_HORIZON, "min_bucket_closed_5d"),
        (SECONDARY_HORIZON, "min_bucket_closed_10d"),
    ):
        hs = high_stats[horizon]
        ls = low_stats[horizon]
        min_required = thresholds[min_key]
        decisive = (
            hs.get("closed_count", 0) >= min_required
            and ls.get("closed_count", 0) >= min_required
        )
        ph_top5 = hs.get("top5_positive_share")
        ph_single = hs.get("max_single_ticker_positive_share")
        conc_ok = bool(
            (ph_top5 is None or ph_top5 <= thresholds["max_top5_positive_share"])
            and (
                ph_single is None
                or ph_single <= thresholds["max_single_ticker_positive_share"]
            )
        )
        horizons[horizon] = {
            "high_avg_return": hs.get("avg_return"),
            "low_avg_return": ls.get("avg_return"),
            "avg_return_lift": _diff(hs.get("avg_return"), ls.get("avg_return")),
            "high_win_rate": hs.get("win_rate"),
            "low_win_rate": ls.get("win_rate"),
            "win_rate_lift": _diff(hs.get("win_rate"), ls.get("win_rate")),
            "high_closed": hs.get("closed_count"),
            "low_closed": ls.get("closed_count"),
        }
        decisive_by_horizon[horizon] = decisive
        concentration_by_horizon[horizon] = conc_ok

    return {
        "axis": axis,
        "positive_row_count": split["positive_row_count"],
        "median_split": split["median_split"],
        "high_magnitude_row_count": len(high),
        "low_magnitude_row_count": len(low),
        "high_magnitude_tickers": sorted({r.get("ticker", "") for r in high}),
        "low_magnitude_tickers": sorted({r.get("ticker", "") for r in low}),
        "high_stats": high_stats,
        "low_stats": low_stats,
        "horizons": horizons,
        "decisive_by_horizon": decisive_by_horizon,
        "concentration_passed_by_horizon": concentration_by_horizon,
    }


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def evaluate_gates(
    axis_results: dict[str, dict[str, Any]],
    rows_total: int,
) -> dict[str, Any]:
    gate1 = {
        "name": "axes_have_positive_revision_rows",
        "passed": all(
            ar.get("positive_row_count", 0) > 0 for ar in axis_results.values()
        ),
        "positive_row_counts": {
            ax: ar.get("positive_row_count", 0) for ax, ar in axis_results.items()
        },
    }
    gate2 = {
        "name": "required_input_fields_present",
        "passed": rows_total > 0,
        "rows_total": rows_total,
    }
    gate3 = {
        "name": "survival_rate_not_affected_read_only_attribution",
        "passed": True,
    }

    per_axis_5d: dict[str, Any] = {}
    any_accepted = False
    decisive_axes = []
    all_decisive_non_positive = True
    for axis, ar in axis_results.items():
        h = ar["horizons"][PRIMARY_HORIZON]
        lift = h.get("avg_return_lift")
        decisive = ar["decisive_by_horizon"][PRIMARY_HORIZON]
        conc_ok = ar["concentration_passed_by_horizon"][PRIMARY_HORIZON]
        accepted = bool(
            decisive and lift is not None and lift >= LIFT_FLOOR and conc_ok
        )
        if accepted:
            any_accepted = True
        if decisive:
            decisive_axes.append(axis)
            if lift is None or lift > 0:
                all_decisive_non_positive = False
        per_axis_5d[axis] = {
            "lift": lift,
            "decisive": decisive,
            "concentration_passed": conc_ok,
            "accepted": accepted,
        }

    if any_accepted:
        status = "accepted_revision_magnitude_edge"
        passed = True
    elif decisive_axes and all_decisive_non_positive:
        status = "rejected_no_revision_magnitude_edge"
        passed = False
    else:
        status = "observed_only_thin_magnitude_buckets"
        passed = False

    gate4 = {
        "name": "revision_magnitude_high_vs_low_5d",
        "passed": passed,
        "status": status,
        "primary_horizon": PRIMARY_HORIZON,
        "lift_floor": LIFT_FLOOR,
        "decisive_axes": decisive_axes,
        "per_axis_5d_diagnostic": per_axis_5d,
        "decision_rule": (
            "An axis is decisive only if both high and low buckets clear "
            "min_bucket_closed_5d=8. If at least one decisive axis shows "
            "high-low 5d lift >= 0.01 with concentration passed -> accepted. "
            "If every decisive axis shows lift <= 0 -> rejected. If no axis "
            "is decisive -> observed_only_thin_magnitude_buckets."
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


def _strip_rows(axis_result: dict[str, Any]) -> dict[str, Any]:
    """Drop the heavy row lists before persisting; keep ticker lists."""
    out = dict(axis_result)
    out.pop("high_stats", None)
    out.pop("low_stats", None)
    return out


def run(
    source: Path = DEFAULT_SOURCE,
    output: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    with source.open("r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    rows = list(artifact.get("enriched_watchlist_rows") or [])

    axis_results: dict[str, dict[str, Any]] = {}
    for axis in MAGNITUDE_AXES:
        axis_results[axis] = axis_attribution(rows, axis, PUBLISHED_GATE_THRESHOLDS)

    gates = evaluate_gates(axis_results, len(rows))
    decision = gates["gate4"]["status"]

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "source_enriched_watchlist_artifact": str(source.relative_to(REPO_ROOT)),
        "row_count": len(rows),
        "magnitude_axes": list(MAGNITUDE_AXES),
        "axis_results": {ax: _strip_rows(ar) for ax, ar in axis_results.items()},
        "gate_thresholds_published_by_exp_20260527_002": PUBLISHED_GATE_THRESHOLDS,
        "lift_floor": LIFT_FLOOR,
        "gates": gates,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.source, args.output)
    summary = {
        "anti_js": result["anti_js"],
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "output": str(args.output.relative_to(REPO_ROOT)),
        "gate4_per_axis_5d": result["gates"]["gate4"]["per_axis_5d_diagnostic"],
        "gate4_decisive_axes": result["gates"]["gate4"]["decisive_axes"],
        "gate4_status": result["gates"]["gate4"]["status"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
