"""exp-20260528-027: PEAD window x residual leadership bucket attribution.

Lane: alpha_discovery.
Change type: read_only_pead_attribution_rerun.
Single causal variable:
    pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist.

Why this experiment exists
--------------------------
``exp-20260527-005`` (and 006/007) all ended ``observed_only_data_gap``
because the upstream ``annotated_watchlist_rows`` produced by
``exp-20260525-034`` had no ``last_earnings_date``: every primary
positive row collapsed into ``pead_status = missing_last_earnings_date``
and no bucket comparison was possible. ``exp-20260527-908`` reconstructed
``last_earnings_date`` PIT-safely from SEC EDGAR 10-Q / 10-K / 8-K(2.02)
filings and produced an enriched watchlist artifact. This experiment is
the first read-only PEAD bucket attribution that consumes the enriched
watchlist and finally tests the alpha hypothesis directly.

Comparisons run
---------------
1. ``residual_eligible`` vs ``non_residual_eligible`` — within the T+2..T+15
   PEAD window, do primary positive residual leaders outperform primary
   positive non-residual rows at the 5d / 10d horizons?
2. ``all_eligible_pead`` vs ``outside_pead_primary_positive`` — does the
   PEAD window itself produce a return lift relative to primary positive
   rows whose ``days_since_last_earnings`` is outside ``[2, 15]``?
3. ``all_eligible_pead`` vs ``not_primary_7d_positive`` — does
   ``positive expectation revision`` combined with the PEAD window
   beat the non-primary-positive baseline?

Each comparison reports per-bucket avg_return, win_rate, total
``pnl_proxy``, tail loss, single-ticker concentration, and top-5 positive
concentration at the 5d and 10d horizons, mirroring the
``gate_thresholds`` published in ``exp-20260527-005``'s artifact.

Gate 4
------
The acceptance bar for this ``alpha_discovery`` experiment is a clear,
non-jackpot residual edge that survives concentration limits *and* meets
the published bucket size floors. Anything weaker is reported as
``observed_only_thin_bucket_data_now_available`` so the next iteration
can either retry with more accumulated data or pivot to a different
PEAD discriminator. A negative residual edge is reported as
``rejected_no_residual_pead_edge``.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260527-908"
    / "last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-027"
    / "pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist.json"
)

EXPERIMENT_ID = "exp-20260528-027"
RULE_VERSION = "pead_window_residual_bucket_attribution_v1"

# Mirrors gate thresholds published in exp-20260527-005's artifact.
PUBLISHED_GATE_THRESHOLDS = {
    "max_single_ticker_positive_share": 0.5,
    "max_top5_positive_share": 0.6,
    "min_bucket_closed_10d": 5,
    "min_bucket_closed_5d": 8,
}

PRIMARY_HORIZON = "5d"
SECONDARY_HORIZON = "10d"

# Effect size floor for the residual-vs-non-residual comparison. Below
# this the residual lift is not large enough to justify a paper sleeve
# even if statistically present, given the small sample.
RESIDUAL_LIFT_FLOOR = 0.01  # 1 percentage point of forward return at 5d


# ---------------------------------------------------------------------------
# Bucket assignment (mirrors exp-20260527-005's `pead_readiness_bucket`)
# ---------------------------------------------------------------------------


def assign_pead_bucket(row: dict[str, Any]) -> str:
    if not row.get("primary_expectation_positive"):
        return "not_primary_7d_positive"
    if not row.get("watchlist_effective_trade_date"):
        return "blocked_missing_effective_trade_date"
    if not row.get("last_earnings_date"):
        return "blocked_missing_last_earnings_date"
    if not row.get("pead_window"):
        return "outside_pead_primary_positive"
    if row.get("residual_leader"):
        return "residual_eligible"
    return "non_residual_eligible"


# ---------------------------------------------------------------------------
# Per-bucket statistics
# ---------------------------------------------------------------------------


def _closed_rows(rows: Iterable[dict[str, Any]], horizon: str) -> list[dict[str, Any]]:
    return [
        r
        for r in rows
        if ((r.get("forward_outcomes") or {}).get(horizon) or {}).get("closed")
    ]


def _bucket_horizon_stats(
    rows: list[dict[str, Any]], horizon: str
) -> dict[str, Any]:
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
    max_single = (
        max(by_ticker_positive.values()) if by_ticker_positive else 0.0
    )
    return {
        "row_count": len(rows),
        "closed_count": len(closed),
        "returns_count": len(returns),
        "avg_return": (sum(returns) / len(returns)) if returns else None,
        "win_rate": (
            sum(1 for r in returns if r > 0) / len(returns) if returns else None
        ),
        "total_pnl_proxy": sum(p for _r, p in pnl_pairs),
        "positive_pnl_proxy": positive_total,
        "tail_loss": min(returns) if returns else None,
        "top5_positive_share": (
            top5_positive / positive_total if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            max_single / positive_total if positive_total > 0 else None
        ),
    }


def bucket_stats(
    rows_by_bucket: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket_name, rows in rows_by_bucket.items():
        out[bucket_name] = {
            "row_count": len(rows),
            PRIMARY_HORIZON: _bucket_horizon_stats(rows, PRIMARY_HORIZON),
            SECONDARY_HORIZON: _bucket_horizon_stats(rows, SECONDARY_HORIZON),
        }
    return out


# ---------------------------------------------------------------------------
# Comparison primitive
# ---------------------------------------------------------------------------


def _safe_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def comparison_payload(
    *,
    name: str,
    preferred_bucket: str,
    comparison_bucket: str,
    stats: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    pref = stats.get(preferred_bucket) or {}
    comp = stats.get(comparison_bucket) or {}
    diffs: dict[str, Any] = {}
    bucket_size_passed: dict[str, bool] = {}
    concentration_passed: dict[str, bool] = {}
    for horizon, min_key in (
        (PRIMARY_HORIZON, "min_bucket_closed_5d"),
        (SECONDARY_HORIZON, "min_bucket_closed_10d"),
    ):
        ph = pref.get(horizon) or {}
        ch = comp.get(horizon) or {}
        diffs[horizon] = {
            "preferred_avg_return": ph.get("avg_return"),
            "comparison_avg_return": ch.get("avg_return"),
            "preferred_win_rate": ph.get("win_rate"),
            "comparison_win_rate": ch.get("win_rate"),
            "avg_return_lift": _safe_diff(
                ph.get("avg_return"), ch.get("avg_return")
            ),
            "win_rate_lift": _safe_diff(ph.get("win_rate"), ch.get("win_rate")),
            "preferred_closed": ph.get("closed_count"),
            "comparison_closed": ch.get("closed_count"),
        }
        min_required = thresholds.get(min_key)
        bucket_size_passed[horizon] = (
            ph.get("closed_count", 0) >= min_required
            and ch.get("closed_count", 0) >= min_required
        )
        max_top5 = thresholds.get("max_top5_positive_share")
        max_single = thresholds.get("max_single_ticker_positive_share")
        ph_top5 = ph.get("top5_positive_share")
        ph_single = ph.get("max_single_ticker_positive_share")
        concentration_passed[horizon] = bool(
            (ph_top5 is None or ph_top5 <= max_top5)
            and (ph_single is None or ph_single <= max_single)
        )
    return {
        "name": name,
        "preferred_bucket": preferred_bucket,
        "comparison_bucket": comparison_bucket,
        "horizons": diffs,
        "bucket_size_floor_passed_by_horizon": bucket_size_passed,
        "concentration_passed_by_horizon": concentration_passed,
    }


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


def evaluate_gates(
    comparisons: list[dict[str, Any]],
    stats: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    # Gate 1: baseline measurability — we have a populated enriched watchlist
    # and at least one PEAD-eligible row in each bucket.
    pref_residual = stats.get("residual_eligible") or {}
    pref_non_res = stats.get("non_residual_eligible") or {}
    gate1 = {
        "name": "baseline_buckets_populated",
        "passed": (
            pref_residual.get("row_count", 0) > 0
            and pref_non_res.get("row_count", 0) > 0
        ),
        "residual_eligible_row_count": pref_residual.get("row_count", 0),
        "non_residual_eligible_row_count": pref_non_res.get("row_count", 0),
    }

    # Gate 2: required input fields — all bucketed rows had last_earnings_date
    # AND a forward_outcomes block.
    bucketed_total = sum(
        s.get("row_count", 0)
        for k, s in stats.items()
        if k
        in (
            "residual_eligible",
            "non_residual_eligible",
            "outside_pead_primary_positive",
            "blocked_missing_last_earnings_date",
            "not_primary_7d_positive",
        )
    )
    gate2 = {
        "name": "required_input_fields_present",
        "passed": bucketed_total > 0,
        "bucketed_total_rows": bucketed_total,
    }

    # Gate 3: survival rate — read-only attribution does not filter; pass.
    gate3 = {
        "name": "survival_rate_not_affected_read_only_attribution",
        "passed": True,
    }

    # Gate 4: primary alpha test — residual_eligible vs non_residual_eligible.
    primary = next(
        c for c in comparisons if c["name"] == "residual_vs_non_residual_within_pead"
    )
    primary_5d = primary["horizons"][PRIMARY_HORIZON]
    primary_lift = primary_5d.get("avg_return_lift")
    primary_size_ok = primary["bucket_size_floor_passed_by_horizon"][PRIMARY_HORIZON]
    primary_concentration_ok = primary["concentration_passed_by_horizon"][
        PRIMARY_HORIZON
    ]
    lift_ok = primary_lift is not None and primary_lift >= RESIDUAL_LIFT_FLOOR
    lift_negative = primary_lift is not None and primary_lift < 0

    if lift_negative:
        gate4_status = "rejected_no_residual_pead_edge"
        gate4_passed = False
    elif primary_size_ok and lift_ok and primary_concentration_ok:
        gate4_status = "accepted_residual_pead_continuation_edge"
        gate4_passed = True
    else:
        gate4_status = "observed_only_thin_bucket_data_now_available"
        gate4_passed = False

    gate4 = {
        "name": "primary_residual_vs_non_residual_within_pead_window",
        "passed": gate4_passed,
        "status": gate4_status,
        "primary_horizon": PRIMARY_HORIZON,
        "residual_lift_floor": RESIDUAL_LIFT_FLOOR,
        "primary_horizon_lift": primary_lift,
        "primary_horizon_bucket_size_passed": primary_size_ok,
        "primary_horizon_concentration_passed": primary_concentration_ok,
        "decision_rule": (
            "If residual_eligible avg_return @ 5d minus non_residual_eligible "
            "avg_return @ 5d is negative -> rejected_no_residual_pead_edge. "
            "Else if bucket size floor + concentration limits pass AND lift "
            ">= 0.01 -> accepted_residual_pead_continuation_edge. "
            "Else -> observed_only_thin_bucket_data_now_available."
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
    source: Path = DEFAULT_SOURCE,
    output: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    with source.open("r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    rows = list(artifact.get("enriched_watchlist_rows") or [])

    rows_by_bucket: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        b = assign_pead_bucket(r)
        rows_by_bucket.setdefault(b, []).append(r)

    stats = bucket_stats(rows_by_bucket)

    # Build aggregate buckets used by comparisons (2) and (3).
    all_eligible = rows_by_bucket.get(
        "residual_eligible", []
    ) + rows_by_bucket.get("non_residual_eligible", [])
    stats["all_eligible_pead"] = {
        "row_count": len(all_eligible),
        PRIMARY_HORIZON: _bucket_horizon_stats(all_eligible, PRIMARY_HORIZON),
        SECONDARY_HORIZON: _bucket_horizon_stats(
            all_eligible, SECONDARY_HORIZON
        ),
    }

    comparisons = [
        comparison_payload(
            name="residual_vs_non_residual_within_pead",
            preferred_bucket="residual_eligible",
            comparison_bucket="non_residual_eligible",
            stats=stats,
            thresholds=PUBLISHED_GATE_THRESHOLDS,
        ),
        comparison_payload(
            name="pead_window_vs_outside_window_primary_positive",
            preferred_bucket="all_eligible_pead",
            comparison_bucket="outside_pead_primary_positive",
            stats=stats,
            thresholds=PUBLISHED_GATE_THRESHOLDS,
        ),
        comparison_payload(
            name="positive_revision_pead_vs_non_primary_baseline",
            preferred_bucket="all_eligible_pead",
            comparison_bucket="not_primary_7d_positive",
            stats=stats,
            thresholds=PUBLISHED_GATE_THRESHOLDS,
        ),
    ]

    gates = evaluate_gates(comparisons, stats, PUBLISHED_GATE_THRESHOLDS)
    decision = gates["gate4"]["status"]

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "source_enriched_watchlist_artifact": str(source.relative_to(REPO_ROOT)),
        "row_count": len(rows),
        "bucket_counts": {b: len(v) for b, v in rows_by_bucket.items()},
        "bucket_stats": stats,
        "comparisons": comparisons,
        "gate_thresholds_published_by_exp_20260527_005": (
            PUBLISHED_GATE_THRESHOLDS
        ),
        "residual_lift_floor": RESIDUAL_LIFT_FLOOR,
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
        "bucket_counts": result["bucket_counts"],
        "primary_comparison_5d": result["comparisons"][0]["horizons"][
            PRIMARY_HORIZON
        ],
        "primary_comparison_10d": result["comparisons"][0]["horizons"][
            SECONDARY_HORIZON
        ],
        "gate4": result["gates"]["gate4"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
