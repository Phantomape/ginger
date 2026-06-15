"""Regime-tagged scorecard for closed forward / live-pilot paper rows.

This is the out-of-sample accumulation surface for the regime_chop soft-tilt
(exp-20260615-019/025/028). It stamps each closed forward paper-sleeve row (and,
when present, live-pilot ledger rows) with its PRODUCTION-FAITHFUL entry-time
regime: the stress-only `regime_chop` fidelity (SPY trend + momentum + drawdown +
vol), which is exactly what the daily market-state field emits after
exp-20260615-028. It then reports per-regime replacement value and a soft-tilt
counterfactual (exposure-weighted vs equal-weight).

It changes no orders. It is meant to be re-run as rows accumulate; the row-level
tags let a future Gate 1-4 ask whether down-weighting the choppy regime improved
cost-adjusted replacement value out-of-sample. With only a handful of closed rows
today it is observation-only and must NOT drive any sizing decision yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]


def _f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    import math
    return out if math.isfinite(out) else None


def build_scorecard(
    rows: list[dict[str, Any]],
    regime_fn: Callable[[str], dict[str, Any] | None],
    *,
    rv_key: str = "replacement_value_vs_spy_usd",
    min_rows_for_inference: int = 50,
) -> dict[str, Any]:
    """Pure aggregation: tag each row via regime_fn(entry_date) and summarize.

    `regime_fn` returns a dict with at least `regime_label`, `p_choppy_range`,
    and `exposure_scalar`, or None if the date cannot be classified.
    """
    tagged: list[dict[str, Any]] = []
    untagged = 0
    for row in rows:
        entry = str(row.get("entry_date") or row.get("signal_date") or "")[:10]
        regime = regime_fn(entry) if entry else None
        if not regime or regime.get("regime_label") in (None, "unknown"):
            untagged += 1
            continue
        tagged.append({
            "sleeve": row.get("sleeve"),
            "ticker": row.get("ticker"),
            "entry_date": entry,
            "replacement_value_vs_spy_usd": _f(row.get(rv_key)),
            "pnl": _f(row.get("pnl")),
            "regime_label": regime.get("regime_label"),
            "p_choppy_range": _f(regime.get("p_choppy_range")),
            "exposure_scalar": _f(regime.get("exposure_scalar")),
            "regime_fidelity": regime.get("fidelity") or regime.get("coverage"),
        })

    by_regime: dict[str, dict[str, Any]] = {}
    for label in ("risk_on_trend", "choppy_range", "risk_off_stress"):
        bucket = [t for t in tagged if t["regime_label"] == label]
        rvs = [t["replacement_value_vs_spy_usd"] for t in bucket if t["replacement_value_vs_spy_usd"] is not None]
        exps = [t["exposure_scalar"] for t in bucket if t["exposure_scalar"] is not None]
        by_regime[label] = {
            "count": len(bucket),
            "mean_replacement_value_vs_spy_usd": round(sum(rvs) / len(rvs), 2) if rvs else None,
            "mean_exposure_scalar": round(sum(exps) / len(exps), 4) if exps else None,
        }

    rv_rows = [t for t in tagged if t["replacement_value_vs_spy_usd"] is not None and t["exposure_scalar"] is not None]
    equal_mean = sum(t["replacement_value_vs_spy_usd"] for t in rv_rows) / len(rv_rows) if rv_rows else None
    wsum = sum(t["exposure_scalar"] for t in rv_rows)
    exp_weighted_mean = (
        sum(t["exposure_scalar"] * t["replacement_value_vs_spy_usd"] for t in rv_rows) / wsum
        if wsum > 0 else None
    )
    soft_tilt = {
        "note": (
            "OBSERVE-ONLY counterfactual. Down-weights each row's replacement value "
            "by its entry-time exposure_scalar (which softly cuts only the choppy "
            "regime). A higher exposure-weighted mean than the equal-weight mean "
            "means the chop down-tilt would have helped. NOT acceptance evidence."
        ),
        "rv_rows": len(rv_rows),
        "equal_weight_mean_rv_vs_spy_usd": round(equal_mean, 2) if equal_mean is not None else None,
        "exposure_weighted_mean_rv_vs_spy_usd": round(exp_weighted_mean, 2) if exp_weighted_mean is not None else None,
        "tilt_gain_usd": round(exp_weighted_mean - equal_mean, 2) if (equal_mean is not None and exp_weighted_mean is not None) else None,
    }

    return {
        "rule_version": "regime_tagged_scorecard_v1",
        "total_rows": len(rows),
        "tagged_rows": len(tagged),
        "untagged_rows": untagged,
        "tiny_sample_warning": len(tagged) < min_rows_for_inference,
        "min_rows_for_inference": min_rows_for_inference,
        "by_regime": by_regime,
        "soft_tilt_counterfactual": soft_tilt,
        "rows": sorted(tagged, key=lambda t: (t["entry_date"], str(t["sleeve"]), str(t["ticker"]))),
    }


def load_forward_paper_rows(paper_sleeves_dir: Path | str | None = None) -> list[dict[str, Any]]:
    base = Path(paper_sleeves_dir) if paper_sleeves_dir else (REPO_ROOT / "data" / "paper_sleeves")
    rows: list[dict[str, Any]] = []
    for state_path in sorted(base.glob("*/state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        sleeve = state.get("sleeve") or state_path.parent.name
        for row in (state.get("closed_positions") or state.get("closed_outcomes") or []):
            entry = str(row.get("entry_date") or row.get("signal_date") or "")[:10]
            if not entry:
                continue
            rows.append({
                "sleeve": sleeve,
                "ticker": row.get("ticker"),
                "entry_date": entry,
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "pnl": row.get("pnl"),
            })
    return rows


def warehouse_spy_stress_regime_fn(
    db_path: Path | str,
    start: str = "2023-08-29",
    end: str = "2026-12-31",
) -> Callable[[str], dict[str, Any] | None]:
    """Production-faithful (stress-only) regime function from warehouse SPY bars."""
    import regime_chop_state as rc
    from ohlcv_warehouse import load_warehouse_ohlcv_frames

    frames = load_warehouse_ohlcv_frames(db_path, ["SPY"], start, end)
    spy = frames.get("SPY")
    if spy is None or len(spy) == 0:
        return lambda _date: None
    bars = [{"Date": str(idx.date()), "Close": float(r.Close), "High": float(r.High)} for idx, r in spy.iterrows()]

    def _fn(asof: str) -> dict[str, Any] | None:
        feats = rc.spy_features_at(bars, asof)
        if feats is None:
            return None
        out = rc.regime_chop_from_features({
            "trend_pct_from_ma": feats["trend_pct_from_ma"],
            "ret20": feats["ret20"],
            "drawdown_from_high": feats["drawdown_from_high"],
            "vol_ratio": feats["vol_ratio"],
        })
        out["fidelity"] = "stress_only_no_breadth"
        return out

    return _fn
