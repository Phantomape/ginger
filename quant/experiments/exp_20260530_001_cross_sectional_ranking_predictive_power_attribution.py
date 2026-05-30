"""exp-20260530-001: Cross-sectional composite alpha_score rank predictive-power
attribution on canonical filled trades.

Lane: alpha_discovery.
Change type: read_only_cross_sectional_ranking_predictive_power_attribution.
Single causal variable: entry_day_pit_composite_alpha_score_rank_bucket.

Why this experiment exists
--------------------------
The alpha-direction memo's section 9 ("Ranking Score Replacement Test")
was never completed for the *composite* alpha_score. `exp-20260528-007`
only tested whether *adding* the expectation increment improved ranking
(it did not). This experiment tests the composite cross-sectional
alpha_score itself (trend 0.30 / relative_strength 0.25 /
expectation_revision 0.20 / post_earnings_drift 0.10 /
theme_participation 0.10 / breadth_alignment 0.05), rebuilt point-in-time
as of the day before each filled core entry by
`quant/entry_day_ranking_attribution.py`, across the canonical three
windows (late_strong / mid_weak / old_thin).

Hypothesis: top alpha_score-rank buckets out-return bottom buckets
(monotonic), not via a single jackpot trade, with PIT coverage >= 0.95.

What this script does
---------------------
Reads the three per-window `entry_day_ranking_attribution` reports
(produced by the canonical tool), aggregates the rank-bucket and
component-bucket attribution, and judges:

1. PIT coverage (Gate 2-style field readiness);
2. rank-bucket dispersion (can the monotonicity question even be asked?);
3. constant-component count (components carrying zero discriminating
   information within the filled set);
4. monotonicity / inversion on the components that do have dispersion.

Decision logic
--------------
Filled core trades are a selected sample: the entry rule already picks
top-ranked names, so the composite-rank buckets are expected to be
degenerate. The honest outcomes are:

- `observed_only_rank_degenerate_requires_full_universe` when the filled
  trades cannot populate a bottom rank bucket (no comparison group) and
  no dispersed component shows a clean monotonic edge; or
- `accepted_composite_rank_monotonic_edge` if (rare) the filled trades
  do span rank buckets and show top > bottom monotonicity that is not
  jackpot-driven; or
- `rejected_composite_rank_inverted` if dispersed buckets clearly invert.

This experiment is strictly read-only: no entries, exits, ranking,
sizing, LLM/news inputs, paper sleeves, or live orders change.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260530-001"
DEFAULT_OUTPUT = EXP_DIR / "cross_sectional_ranking_predictive_power_attribution.json"

EXPERIMENT_ID = "exp-20260530-001"
RULE_VERSION = "cross_sectional_ranking_predictive_power_attribution_v1"

WINDOWS = ("late_strong", "mid_weak", "old_thin")
RANK_ORDER = ("top_decile", "top_quartile", "upper_mid", "lower_mid", "bottom_quartile")
PIT_COVERAGE_FLOOR = 0.95
# A dispersed component "wins" only if the higher score bucket beats the
# lower by at least this avg_r margin AND is not driven by < this many trades.
MONOTONIC_AVG_R_MARGIN = 0.10
MIN_BUCKET_TRADES = 8


def _attr_path(window: str) -> Path:
    return EXP_DIR / f"ranking_attr_{window}.json"


def _agg_init() -> dict[str, Any]:
    return {"trades": 0, "total_pnl": 0.0, "wins": 0.0, "avg_r_weighted": 0.0}


def _fold(agg: dict[str, Any], bucket: dict[str, Any]) -> None:
    n = int(bucket.get("trades") or 0)
    agg["trades"] += n
    agg["total_pnl"] += float(bucket.get("total_pnl") or 0.0)
    agg["wins"] += float(bucket.get("win_rate") or 0.0) * n
    agg["avg_r_weighted"] += float(bucket.get("avg_r") or 0.0) * n


def _summarize(agg: dict[str, Any]) -> dict[str, Any]:
    n = agg["trades"]
    if not n:
        return {"trades": 0, "avg_pnl": None, "win_rate": None, "avg_r": None}
    return {
        "trades": n,
        "avg_pnl": round(agg["total_pnl"] / n, 2),
        "total_pnl": round(agg["total_pnl"], 2),
        "win_rate": round(agg["wins"] / n, 4),
        "avg_r": round(agg["avg_r_weighted"] / n, 4),
    }


def aggregate(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rank_agg: dict[str, dict[str, Any]] = defaultdict(_agg_init)
    comp_agg: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(_agg_init)
    )
    coverage: dict[str, Any] = {}
    total_trades = 0
    pit_trades = 0

    for window, report in reports.items():
        cov = report.get("coverage", {})
        coverage[window] = {
            "trades_total": cov.get("trades_total"),
            "pit_coverage": cov.get("point_in_time_safe_coverage"),
            "trades_with_alpha_score": cov.get("trades_with_alpha_score"),
            "policy_research_ready": cov.get("policy_research_ready"),
        }
        total_trades += int(cov.get("trades_total") or 0)
        pit_trades += int(cov.get("point_in_time_safe_trades") or 0)

        for bucket in report.get("ranking_bucket_attribution", []) or []:
            _fold(rank_agg[bucket["bucket"]], bucket)

        for comp, blob in (report.get("component_attribution") or {}).items():
            for bucket in (blob or {}).get("buckets", []) or []:
                _fold(comp_agg[comp][bucket["bucket"]], bucket)

    rank_summary = {bk: _summarize(rank_agg[bk]) for bk in rank_agg}
    comp_summary = {
        comp: {bk: _summarize(comp_agg[comp][bk]) for bk in comp_agg[comp]}
        for comp in comp_agg
    }
    overall_pit_coverage = (pit_trades / total_trades) if total_trades else 0.0
    return {
        "coverage_by_window": coverage,
        "total_trades": total_trades,
        "overall_pit_coverage": round(overall_pit_coverage, 4),
        "rank_bucket_summary": rank_summary,
        "component_bucket_summary": comp_summary,
    }


def judge(agg: dict[str, Any]) -> dict[str, Any]:
    rank = agg["rank_bucket_summary"]
    comp = agg["component_bucket_summary"]

    # Rank dispersion: how many distinct rank buckets actually have trades,
    # and is there anything below top_quartile?
    populated_ranks = [bk for bk in RANK_ORDER if rank.get(bk, {}).get("trades")]
    has_bottom_group = any(
        rank.get(bk, {}).get("trades") for bk in RANK_ORDER[2:]
    )  # upper_mid or lower
    rank_degenerate = not has_bottom_group

    # Constant components carry zero discriminating info within the filled set.
    constant_components = sorted(c for c, b in comp.items() if len(b) <= 1)
    dispersed_components = sorted(c for c, b in comp.items() if len(b) > 1)

    # For each dispersed component, is the higher-score bucket monotonically
    # better (avg_r) than the lower, with both buckets above the trade floor?
    component_verdicts: dict[str, Any] = {}
    any_clean_monotonic = False
    any_inversion = False
    score_order = ("high", "mid", "low")
    for c in dispersed_components:
        buckets = comp[c]
        ordered = [b for b in score_order if b in buckets]
        # compare adjacent: higher score should have >= avg_r
        margins = []
        sample_ok = True
        for hi, lo in zip(ordered, ordered[1:]):
            hr = buckets[hi].get("avg_r")
            lr = buckets[lo].get("avg_r")
            if hr is None or lr is None:
                continue
            margins.append(round(hr - lr, 4))
            if (
                buckets[hi].get("trades", 0) < MIN_BUCKET_TRADES
                or buckets[lo].get("trades", 0) < MIN_BUCKET_TRADES
            ):
                sample_ok = False
        clean_monotonic = bool(
            margins and sample_ok and all(m >= MONOTONIC_AVG_R_MARGIN for m in margins)
        )
        # An inversion is only decisive when both buckets clear the trade
        # floor; a tiny-sample inversion is noise, not evidence.
        inverted = bool(
            margins and sample_ok and all(m <= -MONOTONIC_AVG_R_MARGIN for m in margins)
        )
        if clean_monotonic:
            any_clean_monotonic = True
        if inverted:
            any_inversion = True
        component_verdicts[c] = {
            "ordered_buckets": ordered,
            "avg_r_margins_high_minus_low": margins,
            "sample_ok": sample_ok,
            "clean_monotonic": clean_monotonic,
            "inverted": inverted,
        }

    pit_ok = agg["overall_pit_coverage"] >= PIT_COVERAGE_FLOOR

    if not pit_ok:
        status = "observed_only_insufficient_pit_coverage"
        passed = False
    elif rank_degenerate and not any_clean_monotonic:
        status = "observed_only_rank_degenerate_requires_full_universe"
        passed = False
    elif any_clean_monotonic and not any_inversion:
        status = "accepted_composite_rank_monotonic_edge"
        passed = True
    elif any_inversion and not any_clean_monotonic:
        status = "rejected_composite_rank_inverted"
        passed = False
    else:
        status = "observed_only_mixed_no_clean_monotonic_edge"
        passed = False

    return {
        "gate1": {
            "name": "canonical_three_window_trades_available",
            "passed": agg["total_trades"] > 0,
            "total_trades": agg["total_trades"],
        },
        "gate2": {
            "name": "pit_alpha_score_coverage",
            "passed": pit_ok,
            "overall_pit_coverage": agg["overall_pit_coverage"],
            "floor": PIT_COVERAGE_FLOOR,
        },
        "gate3": {
            "name": "survival_rate_not_affected_read_only_attribution",
            "passed": True,
        },
        "gate4": {
            "name": "composite_alpha_score_rank_monotonicity",
            "passed": passed,
            "status": status,
            "rank_degenerate_no_bottom_group": rank_degenerate,
            "populated_rank_buckets": populated_ranks,
            "constant_components_zero_info": constant_components,
            "dispersed_components": dispersed_components,
            "component_verdicts": component_verdicts,
            "decision_rule": (
                "Filled core trades are a selected sample. If the rank "
                "buckets cannot populate a below-top_quartile comparison "
                "group AND no dispersed component shows a clean monotonic "
                "avg_r edge (>= 0.10 margin, both buckets >= 8 trades), the "
                "composite ranking surface cannot be validated on filled "
                "trades -> observed_only_rank_degenerate_requires_full_universe."
            ),
        },
        "all_passed": passed,
    }


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    reports = {}
    for window in WINDOWS:
        path = _attr_path(window)
        with path.open("r", encoding="utf-8") as fh:
            reports[window] = json.load(fh)

    agg = aggregate(reports)
    gates = judge(agg)
    decision = gates["gate4"]["status"]

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": decision,
        "windows": list(WINDOWS),
        "source_attribution_reports": {
            w: str(_attr_path(w).relative_to(REPO_ROOT)) for w in WINDOWS
        },
        "aggregate": agg,
        "gates": gates,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.output)
    summary = {
        "anti_js": result["anti_js"],
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "output": str(args.output.relative_to(REPO_ROOT)),
        "total_trades": result["aggregate"]["total_trades"],
        "overall_pit_coverage": result["aggregate"]["overall_pit_coverage"],
        "rank_bucket_summary": result["aggregate"]["rank_bucket_summary"],
        "constant_components_zero_info": result["gates"]["gate4"][
            "constant_components_zero_info"
        ],
        "gate4_status": result["gates"]["gate4"]["status"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
