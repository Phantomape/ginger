"""Longitudinal ranking validation engine.

Goal:
- validate whether continuous ranking surfaces contain durable predictive value
- measure monotonicity of future returns vs alpha-score deciles
- extract evidence instead of adding more features

This module is read-only and attribution-only.
"""

from __future__ import annotations


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bucket_from_rank(rank_pct):
    if rank_pct is None:
        return "unknown"
    if rank_pct <= 0.10:
        return "top_decile"
    if rank_pct <= 0.20:
        return "top_quintile"
    if rank_pct <= 0.50:
        return "upper_half"
    if rank_pct <= 0.80:
        return "lower_half"
    return "bottom_quintile"


def _summarize(rows):
    pnl_values = []
    win_count = 0
    for row in rows:
        pnl = _float(row.get("pnl"), None)
        if pnl is None:
            pnl = _float(row.get("profit_loss"), None)
        if pnl is None:
            continue
        pnl_values.append(pnl)
        if pnl > 0:
            win_count += 1

    n = len(pnl_values)
    return {
        "trades": n,
        "win_rate": round(win_count / n, 4) if n else None,
        "total_pnl": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl": round(sum(pnl_values) / n, 2) if n else None,
        "best_trade": round(max(pnl_values), 2) if pnl_values else None,
        "worst_trade": round(min(pnl_values), 2) if pnl_values else None,
    }


def validate_ranking_monotonicity(trades):
    buckets = {}

    for trade in trades:
        bucket = _bucket_from_rank(trade.get("alpha_score_rank_pct"))
        buckets.setdefault(bucket, []).append(trade)

    ordered = [
        "top_decile",
        "top_quintile",
        "upper_half",
        "lower_half",
        "bottom_quintile",
        "unknown",
    ]

    rows = []
    for bucket in ordered:
        if bucket not in buckets:
            continue
        rows.append({
            "bucket": bucket,
            **_summarize(buckets[bucket]),
        })

    monotonic = True
    previous = None
    for row in rows:
        avg_pnl = row.get("avg_pnl")
        if avg_pnl is None:
            continue
        if previous is not None and avg_pnl > previous:
            monotonic = False
        previous = avg_pnl

    return {
        "bucket_results": rows,
        "monotonicity_detected": monotonic,
    }


def extract_component_predictive_value(trades):
    component_stats = {}

    for trade in trades:
        pnl = _float(trade.get("pnl"), None)
        if pnl is None:
            pnl = _float(trade.get("profit_loss"), None)
        if pnl is None:
            continue

        components = trade.get("alpha_score_components") or {}

        for component, value in components.items():
            value = _float(value, None)
            if value is None:
                continue

            if value >= 0.75:
                bucket = "elite"
            elif value >= 0.60:
                bucket = "strong"
            elif value >= 0.40:
                bucket = "neutral"
            else:
                bucket = "weak"

            component_stats.setdefault(component, {}).setdefault(bucket, []).append(pnl)

    out = {}
    for component, buckets in component_stats.items():
        out[component] = {}
        for bucket, pnl_values in buckets.items():
            out[component][bucket] = {
                "trades": len(pnl_values),
                "avg_pnl": round(sum(pnl_values) / len(pnl_values), 2),
                "total_pnl": round(sum(pnl_values), 2),
            }

    return out


def build_longitudinal_validation_report(
    *,
    ranking_attribution_report,
):
    """Validate whether ranking alpha is durable and monotonic."""

    trades = ranking_attribution_report.get("annotated_trades") or []

    monotonicity = validate_ranking_monotonicity(trades)

    predictive_components = extract_component_predictive_value(trades)

    evidence = []

    if monotonicity.get("monotonicity_detected"):
        evidence.append(
            "higher-ranked buckets show monotonic future PnL ordering"
        )

    top_decile = next(
        (
            row for row in monotonicity.get("bucket_results", [])
            if row.get("bucket") == "top_decile"
        ),
        None,
    )

    bottom_quintile = next(
        (
            row for row in monotonicity.get("bucket_results", [])
            if row.get("bucket") == "bottom_quintile"
        ),
        None,
    )

    if top_decile and bottom_quintile:
        top_avg = _float(top_decile.get("avg_pnl"), 0.0)
        bottom_avg = _float(bottom_quintile.get("avg_pnl"), 0.0)
        if top_avg > bottom_avg:
            evidence.append(
                "top-ranked names outperform bottom-ranked names"
            )

    return {
        "schema_version": 1,
        "read_only": True,
        "ranking_monotonicity": monotonicity,
        "component_predictive_value": predictive_components,
        "evidence_summary": evidence,
        "notes": [
            "Evidence extraction layer for continuous ranking.",
            "The purpose is to validate whether ranking surfaces contain durable predictive information.",
            "Do not add more features until existing surfaces demonstrate stable evidence.",
        ],
    }
