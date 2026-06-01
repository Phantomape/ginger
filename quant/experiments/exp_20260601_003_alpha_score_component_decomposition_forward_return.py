"""exp-20260601-003: alpha_score component-decomposition forward-return attribution.

Lane: alpha_discovery.
Change type: read_only_alpha_score_component_decomposition_forward_return.
Single causal variable: per_component_score_quantile_forward_return_spread.

Why this experiment exists
--------------------------
`exp-20260531-006` found a real but top-quantile-concentrated, non-monotonic
forward-return edge for the composite `alpha_score` on the full daily
universe (pooled Q5-Q1 5d +0.56pp, growing with horizon, not jackpot).
Its open question, and the playbook's explicit next step, is whether that
edge is just the momentum components (trend 0.30 + relative_strength 0.25)
the core entry rule already trades on, or whether the other four
components (expectation_revision, post_earnings_drift, theme_participation,
breadth_alignment) carry *independent* cross-sectional signal.

This experiment re-collects the same full-universe (day, ticker)
observations across the canonical 3 windows, but keeps each observation's
six component scores, then buckets the pooled observations by EACH
component's score quantile and measures the 5/10/20-day forward-return
top-minus-bottom spread per component. It also reports each component's
cross-sectional dispersion so constant / near-constant components (which
carry zero ordering information) are flagged.

This is a univariate decomposition: it isolates each component's marginal
quantile spread. It does not attempt a multivariate regression (component
collinearity is reported as a caveat, not resolved). It is strictly
read-only and changes no entries, exits, ranking, sizing, LLM/news inputs,
paper sleeves, or live orders. Forward returns are raw close-to-close (no
costs).

Judgment
--------
- ``accepted_incremental_component_edge`` if at least one of the four
  non-momentum components (expectation_revision / post_earnings_drift /
  theme_participation / breadth_alignment) shows a 5d top-minus-bottom
  spread >= ``EDGE_FLOOR`` with adequate dispersion and majority-positive
  windows — evidence alpha_score carries signal beyond core momentum.
- ``observed_only_momentum_only_edge`` if only trend / relative_strength
  show a spread (alpha_score adds nothing over the core momentum logic).
- ``observed_only_no_component_edge`` if no component shows a spread.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
_QUANT_DIR = str(REPO_ROOT / "quant")
if _QUANT_DIR not in sys.path:
    sys.path.insert(0, _QUANT_DIR)

from entry_day_ranking_attribution import (  # noqa: E402
    _context_for_asof,
    load_ohlcv_snapshot,
)

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260601-003"
DEFAULT_OUTPUT = EXP_DIR / "alpha_score_component_decomposition_forward_return.json"

EXPERIMENT_ID = "exp-20260601-003"
RULE_VERSION = "alpha_score_component_decomposition_forward_return_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21", "ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak": ("2025-04-23", "2025-10-22", "ohlcv_snapshot_20250423_20251022.json"),
    "old_thin": ("2024-10-02", "2025-04-22", "ohlcv_snapshot_20241002_20250422.json"),
}

COMPONENTS = (
    "trend",
    "relative_strength",
    "expectation_revision",
    "post_earnings_drift",
    "theme_participation",
    "breadth_alignment",
)
MOMENTUM_COMPONENTS = ("trend", "relative_strength")
NON_MOMENTUM_COMPONENTS = (
    "expectation_revision",
    "post_earnings_drift",
    "theme_participation",
    "breadth_alignment",
)

SAMPLE_STEP = 5
FORWARD_HORIZONS = (5, 10, 20)
PRIMARY_HORIZON = 5
QUINTILE = 5
MIN_BUCKET_OBS = 30
EDGE_FLOOR = 0.005
MIN_DISTINCT_VALUES = 5  # below this a component is treated as near-constant


def _forward_returns(frame: pd.DataFrame, asof_ts: pd.Timestamp) -> dict[int, float]:
    idx = frame.index
    pos = idx.searchsorted(asof_ts)
    if pos >= len(idx) or idx[pos] != asof_ts:
        return {}
    base = float(frame["Close"].iloc[pos])
    if base <= 0:
        return {}
    out: dict[int, float] = {}
    for h in FORWARD_HORIZONS:
        fpos = pos + h
        if fpos < len(idx):
            fwd = float(frame["Close"].iloc[fpos])
            if fwd > 0:
                out[h] = fwd / base - 1.0
    return out


def _sample_trading_days(ohlcv: dict[str, pd.DataFrame], start: str, end: str) -> list[pd.Timestamp]:
    all_dates: set[pd.Timestamp] = set()
    for frame in ohlcv.values():
        all_dates.update(frame.loc[start:end].index)
    ordered = sorted(all_dates)
    if not ordered:
        return []
    buffer = max(FORWARD_HORIZONS)
    eligible = ordered[:-buffer] if len(ordered) > buffer else []
    return eligible[::SAMPLE_STEP]


def collect_observations(ohlcv: dict[str, pd.DataFrame], start: str, end: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for asof_ts in _sample_trading_days(ohlcv, start, end):
        context = _context_for_asof(ohlcv, asof_ts)
        rank_map = context.get("rank_map") or {}
        for ticker, info in rank_map.items():
            components = info.get("alpha_score_components")
            if not isinstance(components, dict):
                continue
            frame = ohlcv.get(ticker)
            if frame is None:
                continue
            fwd = _forward_returns(frame, asof_ts)
            if not fwd:
                continue
            observations.append(
                {
                    "asof_date": context["asof_date"],
                    "ticker": ticker,
                    "alpha_score": info.get("alpha_score"),
                    "components": {c: components.get(c) for c in COMPONENTS},
                    "forward_returns": fwd,
                }
            )
    return observations


def _component_dispersion(obs: list[dict[str, Any]], component: str) -> dict[str, Any]:
    vals = [o["components"].get(component) for o in obs if o["components"].get(component) is not None]
    if not vals:
        return {
            "n": 0, "distinct": 0, "std": None, "min": None, "max": None,
            "near_constant": True, "within_day_variance_share": None,
            "cross_sectional": False,
        }
    distinct = len(set(round(v, 4) for v in vals))
    std = round(statistics.pstdev(vals), 6) if len(vals) > 1 else 0.0

    # Decompose total variance into within-day (cross-sectional) vs across-day
    # (market-timing) components. A genuine stock-selection signal varies a lot
    # WITHIN a day across tickers; a market/breadth-regime value is nearly the
    # same for all tickers on a day and only changes across days, so its
    # quantile spread is a market-timing (beta) confound, not cross-sectional
    # alpha (AGENTS.md Section 11).
    by_day: dict[str, list[float]] = {}
    for o in obs:
        v = o["components"].get(component)
        if v is not None:
            by_day.setdefault(o["asof_date"], []).append(v)
    day_means = []
    within_vars = []
    for day_vals in by_day.values():
        if not day_vals:
            continue
        day_means.append(sum(day_vals) / len(day_vals))
        if len(day_vals) > 1:
            within_vars.append(statistics.pvariance(day_vals))
    across_var = statistics.pvariance(day_means) if len(day_means) > 1 else 0.0
    within_var = (sum(within_vars) / len(within_vars)) if within_vars else 0.0
    denom = within_var + across_var
    within_share = round(within_var / denom, 4) if denom > 0 else None

    return {
        "n": len(vals),
        "distinct": distinct,
        "std": std,
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "near_constant": distinct < MIN_DISTINCT_VALUES,
        "within_day_variance": round(within_var, 8),
        "across_day_variance": round(across_var, 8),
        "within_day_variance_share": within_share,
        # cross-sectional only if its variation is majority within-day
        "cross_sectional": bool(within_share is not None and within_share >= 0.5),
    }


def _quantile_spread(obs: list[dict[str, Any]], component: str, horizon: int) -> dict[str, Any]:
    scored = [o for o in obs if o["components"].get(component) is not None and horizon in o["forward_returns"]]
    ordered = sorted(scored, key=lambda o: o["components"][component])
    total = len(ordered)
    if total < QUINTILE * MIN_BUCKET_OBS // QUINTILE:
        pass
    bottom = ordered[: total // QUINTILE]
    top = ordered[total - total // QUINTILE :]

    def _avg(group):
        rets = [o["forward_returns"][horizon] for o in group]
        return (sum(rets) / len(rets)) if rets else None

    top_avg, bot_avg = _avg(top), _avg(bottom)
    return {
        "top_obs": len(top),
        "bottom_obs": len(bottom),
        "top_avg_return": round(top_avg, 6) if top_avg is not None else None,
        "bottom_avg_return": round(bot_avg, 6) if bot_avg is not None else None,
        "top_minus_bottom": (
            round(top_avg - bot_avg, 6) if (top_avg is not None and bot_avg is not None) else None
        ),
    }


def _conditional_spread_vs_rs(obs: list[dict[str, Any]], component: str, horizon: int) -> float | None:
    """Component 5d top-minus-bottom spread CONDITIONAL on relative_strength.

    Double-sort: split observations into RS quintiles, then within each RS
    band compute the component's top-vs-bottom forward-return spread, and
    average across bands. If the component's edge is collinear with RS, this
    residual spread collapses toward zero. If it survives, the component
    carries signal independent of core momentum.
    """
    rs_scored = [o for o in obs if o["components"].get("relative_strength") is not None]
    rs_ordered = sorted(rs_scored, key=lambda o: o["components"]["relative_strength"])
    total = len(rs_ordered)
    if total < QUINTILE * MIN_BUCKET_OBS:
        return None
    band_spreads = []
    for i in range(QUINTILE):
        band = rs_ordered[(i * total) // QUINTILE : ((i + 1) * total) // QUINTILE]
        sp = _quantile_spread(band, component, horizon)
        if sp["top_minus_bottom"] is not None and sp["top_obs"] >= 5 and sp["bottom_obs"] >= 5:
            band_spreads.append(sp["top_minus_bottom"])
    if not band_spreads:
        return None
    return round(sum(band_spreads) / len(band_spreads), 6)


def component_attribution(pooled: list[dict[str, Any]], per_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in COMPONENTS:
        disp = _component_dispersion(pooled, c)
        horizons = {f"h{h}": _quantile_spread(pooled, c, h) for h in FORWARD_HORIZONS}
        window_5d = {}
        for w, obs in per_window.items():
            sp = _quantile_spread(obs, c, PRIMARY_HORIZON)
            window_5d[w] = sp["top_minus_bottom"]
        positive_windows = sum(1 for v in window_5d.values() if v is not None and v > 0)
        measured = sum(1 for v in window_5d.values() if v is not None)
        # residual 5d spread after controlling for relative_strength (skip RS itself)
        residual_vs_rs = (
            None if c == "relative_strength" else _conditional_spread_vs_rs(pooled, c, PRIMARY_HORIZON)
        )
        out[c] = {
            "dispersion": disp,
            "pooled_spread_by_horizon": horizons,
            "per_window_5d_spread": window_5d,
            "positive_windows": positive_windows,
            "measured_windows": measured,
            "residual_5d_spread_vs_rs": residual_vs_rs,
            "is_momentum_component": c in MOMENTUM_COMPONENTS,
        }
    return out


def judge(attr: dict[str, Any], total_obs: int) -> dict[str, Any]:
    gate1 = {"name": "observations_collected", "passed": total_obs > 0, "total_observations": total_obs}

    def _clean_edge(c: str) -> bool:
        node = attr[c]
        disp = node["dispersion"]
        sp5 = node["pooled_spread_by_horizon"]["h5"]["top_minus_bottom"]
        return bool(
            not disp["near_constant"]
            # a market-timing (mostly across-day) component is a beta confound,
            # not cross-sectional alpha -> require within-day-dominant variation
            and disp["cross_sectional"]
            and disp["n"] >= MIN_BUCKET_OBS
            and sp5 is not None
            and sp5 >= EDGE_FLOOR
            and node["measured_windows"] > 0
            and node["positive_windows"] > node["measured_windows"] / 2
        )

    def _survives_rs_control(c: str) -> bool:
        # a non-momentum component is only incremental if its edge survives
        # double-sorting within relative_strength bands (not collinear with RS)
        resid = attr[c].get("residual_5d_spread_vs_rs")
        return bool(resid is not None and resid >= EDGE_FLOOR)

    momentum_edges = [c for c in MOMENTUM_COMPONENTS if _clean_edge(c)]
    non_momentum_univariate_edges = [c for c in NON_MOMENTUM_COMPONENTS if _clean_edge(c)]
    # incremental == clean univariate edge AND survives RS control
    non_momentum_edges = [c for c in non_momentum_univariate_edges if _survives_rs_control(c)]
    momentum_collinear = [c for c in non_momentum_univariate_edges if c not in non_momentum_edges]
    near_constant = [c for c in COMPONENTS if attr[c]["dispersion"]["near_constant"]]
    # components whose 5d spread clears the floor but are NOT cross-sectional
    # (market-timing / beta confounds) — reported, not credited.
    timing_confounds = [
        c
        for c in COMPONENTS
        if not attr[c]["dispersion"]["near_constant"]
        and not attr[c]["dispersion"]["cross_sectional"]
        and (attr[c]["pooled_spread_by_horizon"]["h5"]["top_minus_bottom"] or 0) >= EDGE_FLOOR
    ]

    gate2 = {
        "name": "components_have_dispersion",
        "passed": len(near_constant) < len(COMPONENTS),
        "near_constant_components": near_constant,
    }
    gate3 = {"name": "survival_rate_not_affected_read_only_attribution", "passed": True}

    if non_momentum_edges:
        status, passed = "accepted_incremental_component_edge", True
    elif momentum_edges:
        status, passed = "observed_only_momentum_only_edge", False
    else:
        status, passed = "observed_only_no_component_edge", False

    gate4 = {
        "name": "incremental_non_momentum_component_edge",
        "passed": passed,
        "status": status,
        "edge_floor": EDGE_FLOOR,
        "momentum_components_with_edge": momentum_edges,
        "non_momentum_components_with_edge": non_momentum_edges,
        "non_momentum_univariate_edges": non_momentum_univariate_edges,
        "momentum_collinear_components": momentum_collinear,
        "near_constant_components": near_constant,
        "market_timing_confound_components": timing_confounds,
        "decision_rule": (
            "A non-momentum component is incremental only if (a) its pooled 5d "
            "top-minus-bottom quintile spread >= 0.005, (b) within-day-dominant "
            "variation (selects stocks, not market timing), (c) majority-positive "
            "windows, AND (d) the spread SURVIVES double-sorting within "
            "relative_strength quintile bands (residual_5d_spread_vs_rs >= 0.005), "
            "proving it is not collinear with core momentum. Accept if >=1 "
            "non-momentum component qualifies. If only trend/RS or RS-collinear "
            "components qualify, alpha_score adds nothing over core momentum -> "
            "observed_only_momentum_only_edge. If none -> observed_only_no_"
            "component_edge."
        ),
    }
    return {"gate1": gate1, "gate2": gate2, "gate3": gate3, "gate4": gate4, "all_passed": passed}


def run(output: Path = DEFAULT_OUTPUT, *, snapshot_dir: Path | None = None) -> dict[str, Any]:
    snapshot_dir = snapshot_dir or (REPO_ROOT / "data" / "ohlcv")
    per_window: dict[str, list[dict[str, Any]]] = {}
    for window, (start, end, snap) in WINDOWS.items():
        ohlcv = load_ohlcv_snapshot(str(snapshot_dir / snap))
        per_window[window] = collect_observations(ohlcv, start, end)
    pooled = [o for obs in per_window.values() for o in obs]

    attr = component_attribution(pooled, per_window)
    gates = judge(attr, len(pooled))
    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": gates["gate4"]["status"],
        "sample_step_trading_days": SAMPLE_STEP,
        "forward_horizons": list(FORWARD_HORIZONS),
        "total_observations": len(pooled),
        "observations_by_window": {w: len(o) for w, o in per_window.items()},
        "component_attribution": attr,
        "gates": gates,
        "caveat": (
            "Univariate per-component quantile spreads do not control for "
            "component collinearity (e.g. trend and relative_strength both "
            "load on momentum). A component showing a spread may share it with "
            "another; this isolates marginal univariate signal, not "
            "independent contribution."
        ),
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
        "total_observations": result["total_observations"],
        "component_5d_spread": {
            c: result["component_attribution"][c]["pooled_spread_by_horizon"]["h5"]["top_minus_bottom"]
            for c in COMPONENTS
        },
        "within_day_share": {
            c: result["component_attribution"][c]["dispersion"]["within_day_variance_share"]
            for c in COMPONENTS
        },
        "residual_5d_vs_rs": {
            c: result["component_attribution"][c]["residual_5d_spread_vs_rs"]
            for c in COMPONENTS
        },
        "near_constant": result["gates"]["gate4"]["near_constant_components"],
        "momentum_edges": result["gates"]["gate4"]["momentum_components_with_edge"],
        "non_momentum_univariate_edges": result["gates"]["gate4"]["non_momentum_univariate_edges"],
        "momentum_collinear": result["gates"]["gate4"]["momentum_collinear_components"],
        "non_momentum_incremental_edges": result["gates"]["gate4"]["non_momentum_components_with_edge"],
        "gate4_status": result["gates"]["gate4"]["status"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
