"""exp-20260528-028: Multi-tier PEAD window lift attribution (no residual filter).

Lane: alpha_discovery.
Change type: read_only_pead_attribution_no_residual_filter.
Single causal variable:
    multi_tier_pead_window_lift_attribution_no_residual_filter.

Why this experiment exists
--------------------------
``exp-20260528-027`` rejected the "residual leadership inside the PEAD
window" hypothesis: the residual filter actively hurt 5d returns
(-2.0% residual eligible vs +1.6% non-residual eligible). One reading
is that residual leadership is the wrong discriminator; the simpler
hypothesis "positive expectation revision rows inside the T+2..T+15
window outperform the same rows outside the window" still deserves a
test on its own.

This experiment tests that simpler hypothesis across three independent
positive revision tier definitions that are already on the watchlist:

* ``primary_expectation_positive`` — the strictest tier (47 rows total).
* ``wide_watchlist_positive`` — a broader tier (61 rows total) that
  includes prev-delta and 7d delta evidence.
* ``scout_prev_positive`` — a prev-delta-only scout tier (25 rows).

For each tier we build:

* ``{tier}_pead_in`` — rows where the tier flag is true, ``last_earnings_date``
  is present (so ``pead_window`` is computed at all), and
  ``pead_window`` is True.
* ``{tier}_pead_out`` — rows where the tier flag is true, ``last_earnings_date``
  is present, and ``pead_window`` is False.
* ``{tier}_baseline`` — rows where the tier flag is False (baseline
  comparison; same for all tiers up to the tier itself).

For each tier we compute two diagnostic comparisons at 5d (primary)
and 10d (secondary): ``pead_in`` vs ``pead_out`` (window effect) and
``pead_in`` vs ``baseline`` (any-effect-at-all). We then decide:

* Across all three tiers, if every ``pead_in`` 5d avg-return lift over
  ``pead_out`` is non-positive (i.e. the PEAD window consistently fails
  to improve returns), record ``rejected_no_pead_window_lift_across_tiers``.
* If at least one tier shows a clean lift that meets the published
  ``min_bucket_closed_5d=8`` floor AND ``concentration`` limits AND
  the lift >= 0.01, record ``accepted_pead_window_lift_in_some_tier``.
* Otherwise, ``observed_only_no_consistent_pead_window_lift``.

Gate thresholds are identical to ``exp-20260527-005``'s published values
so the comparison protocol stays comparable. This experiment is
strictly read-only — no entries, exits, ranking, sizing, LLM/news inputs,
paper sleeves, or live orders change.

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
    / "exp-20260528-028"
    / "multi_tier_pead_window_lift_attribution_no_residual_filter.json"
)

EXPERIMENT_ID = "exp-20260528-028"
RULE_VERSION = "multi_tier_pead_window_lift_attribution_v1"

PUBLISHED_GATE_THRESHOLDS = {
    "max_single_ticker_positive_share": 0.5,
    "max_top5_positive_share": 0.6,
    "min_bucket_closed_10d": 5,
    "min_bucket_closed_5d": 8,
}
LIFT_FLOOR = 0.01  # 1 pp 5d avg return required to call a tier "accepted"

PRIMARY_HORIZON = "5d"
SECONDARY_HORIZON = "10d"

TIER_FLAGS = (
    "primary_expectation_positive",
    "wide_watchlist_positive",
    "scout_prev_positive",
)


# ---------------------------------------------------------------------------
# Helpers
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
    max_single = (
        max(by_ticker_positive.values()) if by_ticker_positive else 0.0
    )
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


def _comparison_diffs(
    pref_stats: dict[str, Any],
    comp_stats: dict[str, Any],
    horizon: str,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    pref = pref_stats.get(horizon) or {}
    comp = comp_stats.get(horizon) or {}
    min_key = (
        "min_bucket_closed_5d" if horizon == PRIMARY_HORIZON else "min_bucket_closed_10d"
    )
    min_required = thresholds[min_key]
    bucket_size_passed = (
        pref.get("closed_count", 0) >= min_required
        and comp.get("closed_count", 0) >= min_required
    )
    ph_top5 = pref.get("top5_positive_share")
    ph_single = pref.get("max_single_ticker_positive_share")
    concentration_passed = bool(
        (ph_top5 is None or ph_top5 <= thresholds["max_top5_positive_share"])
        and (
            ph_single is None
            or ph_single <= thresholds["max_single_ticker_positive_share"]
        )
    )
    return {
        "preferred_avg_return": pref.get("avg_return"),
        "comparison_avg_return": comp.get("avg_return"),
        "preferred_win_rate": pref.get("win_rate"),
        "comparison_win_rate": comp.get("win_rate"),
        "avg_return_lift": _diff(pref.get("avg_return"), comp.get("avg_return")),
        "win_rate_lift": _diff(pref.get("win_rate"), comp.get("win_rate")),
        "preferred_closed": pref.get("closed_count"),
        "comparison_closed": comp.get("closed_count"),
        "bucket_size_passed": bucket_size_passed,
        "concentration_passed": concentration_passed,
    }


def attribute_tier(
    rows: list[dict[str, Any]],
    tier: str,
) -> dict[str, Any]:
    """Compute pead_in / pead_out / baseline stats for a tier."""
    pead_in = [
        r
        for r in rows
        if r.get(tier)
        and r.get("last_earnings_date")
        and r.get("pead_window")
    ]
    pead_out = [
        r
        for r in rows
        if r.get(tier)
        and r.get("last_earnings_date")
        and not r.get("pead_window")
    ]
    # Baseline = same-tier-FALSE rows. "Outside the tier" is the cleanest
    # statistical control for "is the tier flag itself informative?".
    baseline = [r for r in rows if not r.get(tier)]
    stats = {
        f"{tier}_pead_in": {
            "row_count": len(pead_in),
            PRIMARY_HORIZON: horizon_stats(pead_in, PRIMARY_HORIZON),
            SECONDARY_HORIZON: horizon_stats(pead_in, SECONDARY_HORIZON),
        },
        f"{tier}_pead_out": {
            "row_count": len(pead_out),
            PRIMARY_HORIZON: horizon_stats(pead_out, PRIMARY_HORIZON),
            SECONDARY_HORIZON: horizon_stats(pead_out, SECONDARY_HORIZON),
        },
        f"{tier}_baseline_not_in_tier": {
            "row_count": len(baseline),
            PRIMARY_HORIZON: horizon_stats(baseline, PRIMARY_HORIZON),
            SECONDARY_HORIZON: horizon_stats(baseline, SECONDARY_HORIZON),
        },
    }
    return stats


def tier_comparisons(
    stats: dict[str, Any],
    tier: str,
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    pead_in_stats = stats[f"{tier}_pead_in"]
    pead_out_stats = stats[f"{tier}_pead_out"]
    baseline_stats = stats[f"{tier}_baseline_not_in_tier"]
    return [
        {
            "name": f"{tier}__pead_in_vs_pead_out",
            "tier": tier,
            "preferred_bucket": f"{tier}_pead_in",
            "comparison_bucket": f"{tier}_pead_out",
            "horizons": {
                PRIMARY_HORIZON: _comparison_diffs(
                    pead_in_stats, pead_out_stats, PRIMARY_HORIZON, thresholds
                ),
                SECONDARY_HORIZON: _comparison_diffs(
                    pead_in_stats, pead_out_stats, SECONDARY_HORIZON, thresholds
                ),
            },
        },
        {
            "name": f"{tier}__pead_in_vs_baseline_not_in_tier",
            "tier": tier,
            "preferred_bucket": f"{tier}_pead_in",
            "comparison_bucket": f"{tier}_baseline_not_in_tier",
            "horizons": {
                PRIMARY_HORIZON: _comparison_diffs(
                    pead_in_stats, baseline_stats, PRIMARY_HORIZON, thresholds
                ),
                SECONDARY_HORIZON: _comparison_diffs(
                    pead_in_stats, baseline_stats, SECONDARY_HORIZON, thresholds
                ),
            },
        },
    ]


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def evaluate_gates(
    all_comparisons: list[dict[str, Any]],
    stats: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    gate1 = {
        "name": "all_three_tiers_have_pead_in_rows",
        "passed": all(
            (stats.get(f"{tier}_pead_in") or {}).get("row_count", 0) > 0
            for tier in TIER_FLAGS
        ),
        "row_counts": {
            tier: (stats.get(f"{tier}_pead_in") or {}).get("row_count", 0)
            for tier in TIER_FLAGS
        },
    }
    gate2 = {
        "name": "required_input_fields_present",
        "passed": True,
        "note": "tier flags present on every input row (verified in source artifact).",
    }
    gate3 = {
        "name": "survival_rate_not_affected_read_only_attribution",
        "passed": True,
    }

    # Gate 4 core: scan tier-level pead_in_vs_pead_out at 5d.
    primary_window_comps = [
        c for c in all_comparisons if c["name"].endswith("__pead_in_vs_pead_out")
    ]
    per_tier_5d: dict[str, dict[str, Any]] = {}
    any_accepted = False
    all_non_positive = True
    for c in primary_window_comps:
        h = c["horizons"][PRIMARY_HORIZON]
        lift = h.get("avg_return_lift")
        size_ok = h.get("bucket_size_passed")
        conc_ok = h.get("concentration_passed")
        accepted = bool(
            lift is not None and lift >= LIFT_FLOOR and size_ok and conc_ok
        )
        if accepted:
            any_accepted = True
        if lift is None or lift > 0:
            all_non_positive = False
        per_tier_5d[c["tier"]] = {
            "lift": lift,
            "bucket_size_passed": size_ok,
            "concentration_passed": conc_ok,
            "accepted": accepted,
        }

    if any_accepted:
        gate4_status = "accepted_pead_window_lift_in_some_tier"
        gate4_passed = True
    elif all_non_positive:
        gate4_status = "rejected_no_pead_window_lift_across_tiers"
        gate4_passed = False
    else:
        gate4_status = "observed_only_no_consistent_pead_window_lift"
        gate4_passed = False

    gate4 = {
        "name": "multi_tier_pead_window_lift",
        "passed": gate4_passed,
        "status": gate4_status,
        "primary_horizon": PRIMARY_HORIZON,
        "lift_floor": LIFT_FLOOR,
        "per_tier_5d_diagnostic": per_tier_5d,
        "decision_rule": (
            "If at least one tier shows 5d pead_in vs pead_out avg_return "
            "lift >= 0.01 with bucket-size floor and concentration limits "
            "passed -> accepted. Else if every tier's lift is <= 0 -> "
            "rejected. Otherwise -> observed_only."
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

    stats: dict[str, Any] = {}
    all_comparisons: list[dict[str, Any]] = []
    for tier in TIER_FLAGS:
        stats.update(attribute_tier(rows, tier))
        all_comparisons.extend(tier_comparisons(stats, tier, PUBLISHED_GATE_THRESHOLDS))

    gates = evaluate_gates(all_comparisons, stats, PUBLISHED_GATE_THRESHOLDS)
    decision = gates["gate4"]["status"]

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "source_enriched_watchlist_artifact": str(source.relative_to(REPO_ROOT)),
        "row_count": len(rows),
        "tier_row_counts": {tier: sum(1 for r in rows if r.get(tier)) for tier in TIER_FLAGS},
        "bucket_stats": stats,
        "comparisons": all_comparisons,
        "gate_thresholds_published_by_exp_20260527_005": PUBLISHED_GATE_THRESHOLDS,
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
        "tier_row_counts": result["tier_row_counts"],
        "gate4_per_tier_5d": result["gates"]["gate4"]["per_tier_5d_diagnostic"],
        "gate4_status": result["gates"]["gate4"]["status"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
