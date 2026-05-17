"""Allocation engine for promotion-gated sleeves."""

from evaluator_gates import evaluate_metrics

STATE_SCALAR = {
    "research": 0.0,
    "shadow": 0.0,
    "pilot": 0.35,
    "limited_production": 0.70,
    "core": 1.00,
    "quarantine": 0.0,
    "retired": 0.0,
}


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def quality_score(metrics):
    """Return a survival-adjusted quality score from performance metrics."""
    ev = max(0.0, _float(metrics.get("expected_value_usd")))
    sharpe = max(0.0, _float(metrics.get("sharpe_ratio")))
    avg_r = max(0.0, _float(metrics.get("avg_r_multiple")))
    tail_ratio = max(0.25, _float(metrics.get("r_tail_ratio"), 1.0))
    skew = _float(metrics.get("r_skewness"), 0.0)
    kurt = max(0.0, _float(metrics.get("r_excess_kurtosis"), 0.0))
    top5 = min(1.0, max(0.0, _float(metrics.get("r_top_5_contribution_pct"), 0.0)))
    hhi = min(1.0, max(0.0, _float(metrics.get("r_hhi_concentration"), 0.0)))
    max_dd = max(0.0, _float(metrics.get("max_drawdown_pct"), 0.0))

    base = ev / 100.0 + sharpe * 1.5 + avg_r * 4.0
    penalty = 1.0
    penalty *= min(1.0, tail_ratio)
    penalty *= max(0.20, 1.0 - max(0.0, -skew) * 0.15)
    penalty *= max(0.15, 1.0 - kurt / 20.0)
    penalty *= max(0.20, 1.0 - top5)
    penalty *= max(0.20, 1.0 - hhi)
    penalty *= max(0.10, 1.0 - max_dd * 3.0)
    return round(max(0.0, base * penalty), 4)


def allocate(sleeves, total_weight=1.0, max_weight=0.35):
    """Allocate weights across sleeves after evaluator gates pass.

    sleeves item shape:
      {"name": str, "state": str, "metrics": dict}
    """
    rows = []
    total_score = 0.0

    for sleeve in sleeves or []:
        state = str(sleeve.get("state") or "research")
        metrics = sleeve.get("metrics") or {}
        gate = evaluate_metrics(metrics)
        score = quality_score(metrics)
        effective = score * STATE_SCALAR.get(state, 0.0) if gate.get("passed") else 0.0
        total_score += effective
        rows.append({
            "name": sleeve.get("name"),
            "state": state,
            "quality_score": score,
            "effective_score": round(effective, 4),
            "gate_report": gate,
            "metrics": metrics,
        })

    for row in rows:
        if total_score <= 0 or row["effective_score"] <= 0:
            weight = 0.0
        else:
            weight = total_weight * row["effective_score"] / total_score
        row["capital_weight"] = round(min(max_weight, weight), 4)

    return sorted(rows, key=lambda row: row["capital_weight"], reverse=True)
