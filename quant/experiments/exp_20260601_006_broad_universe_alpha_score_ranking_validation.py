"""exp-20260601-006: Broad 1446-ticker universe validation of the alpha_score
ranking decomposition.

Lane: alpha_discovery.
Change type: read_only_broad_universe_ranking_component_validation.
Single causal variable:
    broad_1446_ticker_universe_alpha_score_quantile_and_component_decomposition.

Why this experiment exists
--------------------------
`exp-20260531-006` (composite quintile ladder) and `exp-20260601-003`
(component decomposition) both concluded the composite `alpha_score`
forward-return edge is essentially `relative_strength` only, with no
incremental non-momentum component. But both ran on the narrow ~52-name
curated watchlist snapshot, which is momentum-homogeneous large-cap names
plus benchmark ETFs. On such a universe, RS dominating and other factors
being collinear is close to expected by construction, so the conclusion
may not generalize.

This experiment re-runs both analyses on the **broad 1446-ticker
all-windows-full-liquid universe** from the
`data/experiments/exp-20260519-030/warehouse_main.sqlite` warehouse — a
heterogeneous cross-section (small/mid caps included) ~28x larger than
the curated snapshot. It loads each qualified ticker's full OHLCV once,
scores the full universe point-in-time on sampled trading days across the
canonical 3 windows, and reuses the exp-20260601-003 quantile +
component-decomposition + RS-double-sort machinery.

This is strictly read-only: it changes no entries, exits, ranking,
sizing, LLM/news inputs, paper sleeves, or live orders. Forward returns
are raw close-to-close (no costs). It is a validation / robustness re-run,
not a promotion.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"), str(REPO_ROOT / "quant" / "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from feature_layer import compute_features  # noqa: E402
from cross_sectional_ranking_surface import build_cross_sectional_ranking_surface  # noqa: E402
from daily_context_archive import (  # noqa: E402
    build_breadth_context,
    build_earnings_estimate_revision_context,
    build_theme_density_context,
)

# Reuse the exact judged machinery from exp-20260601-003 / exp-20260531-006.
from exp_20260601_003_alpha_score_component_decomposition_forward_return import (  # noqa: E402
    COMPONENTS,
    EDGE_FLOOR,
    FORWARD_HORIZONS,
    component_attribution,
    judge as component_judge,
)
from exp_20260531_006_full_universe_alpha_score_quantile_forward_return import (  # noqa: E402
    aggregate as quantile_aggregate,
    judge as quantile_judge,
)

# exp-20260612-017: warehouse relocated to data/warehouse/; resolve via module.
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH as WAREHOUSE  # noqa: E402

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260601-006"
DEFAULT_OUTPUT = EXP_DIR / "broad_universe_alpha_score_ranking_validation.json"

EXPERIMENT_ID = "exp-20260601-006"
RULE_VERSION = "broad_universe_alpha_score_ranking_validation_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

SAMPLE_STEP = 5
MIN_HISTORY = 21


def load_warehouse_frames(db_path: Path = WAREHOUSE) -> dict[str, pd.DataFrame]:
    """Load all-windows-full-liquid tickers' full OHLCV into {ticker: frame}."""
    con = sqlite3.connect(str(db_path))
    tickers = [
        r[0]
        for r in con.execute(
            "select ticker from coverage_summary where all_windows_full_liquid=1"
        ).fetchall()
    ]
    tset = set(tickers)
    df = pd.read_sql_query(
        "select ticker,date,open,high,low,close,volume from ohlcv order by ticker,date",
        con,
    )
    con.close()
    frames: dict[str, pd.DataFrame] = {}
    for ticker, g in df.groupby("ticker"):
        if ticker not in tset:
            continue
        gg = g.copy()
        gg["Date"] = pd.to_datetime(gg["date"])
        gg = gg.set_index("Date").sort_index()
        gg = gg.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        )
        frames[ticker] = gg[["Open", "High", "Low", "Close", "Volume"]]
    return frames


def _sample_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> list[pd.Timestamp]:
    all_dates: set[pd.Timestamp] = set()
    for fr in frames.values():
        all_dates.update(fr.loc[start:end].index)
    ordered = sorted(all_dates)
    if not ordered:
        return []
    buffer = max(FORWARD_HORIZONS)
    eligible = ordered[:-buffer] if len(ordered) > buffer else []
    return eligible[::SAMPLE_STEP]


def _score_universe_asof(frames: dict[str, pd.DataFrame], asof_ts: pd.Timestamp) -> dict[str, dict[str, Any]]:
    """Score the full universe PIT as of asof_ts: {ticker: {alpha_score, components}}."""
    feats: dict[str, Any] = {}
    for ticker, fr in frames.items():
        sl = fr.loc[:asof_ts]
        if len(sl) < MIN_HISTORY:
            continue
        row = compute_features(ticker, sl, {})
        if row:
            feats[ticker] = row
    if not feats:
        return {}
    bc = build_breadth_context(feats)
    td = build_theme_density_context(feats)
    ec = build_earnings_estimate_revision_context(feats)
    surf = build_cross_sectional_ranking_surface(
        feats, breadth_context=bc, theme_density_context=td, expectation_context=ec
    )
    out: dict[str, dict[str, Any]] = {}
    for row in surf.get("rows") or []:
        t = str(row.get("ticker") or "").upper()
        if t:
            out[t] = {"alpha_score": row.get("alpha_score"), "components": row.get("components")}
    return out


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


def collect_observations(frames: dict[str, pd.DataFrame], start: str, end: str) -> list[dict[str, Any]]:
    obs: list[dict[str, Any]] = []
    for asof_ts in _sample_days(frames, start, end):
        scored = _score_universe_asof(frames, asof_ts)
        asof_str = str(asof_ts.date())
        for ticker, info in scored.items():
            comps = info.get("components")
            alpha = info.get("alpha_score")
            if alpha is None or not isinstance(comps, dict):
                continue
            fwd = _forward_returns(frames[ticker], asof_ts)
            if not fwd:
                continue
            obs.append(
                {
                    "asof_date": asof_str,
                    "ticker": ticker,
                    "alpha_score": float(alpha),
                    "components": {c: comps.get(c) for c in COMPONENTS},
                    "forward_returns": fwd,
                }
            )
    return obs


def run(output: Path = DEFAULT_OUTPUT, *, db_path: Path = WAREHOUSE) -> dict[str, Any]:
    t0 = time.time()
    frames = load_warehouse_frames(db_path)
    per_window: dict[str, list[dict[str, Any]]] = {}
    for window, (start, end) in WINDOWS.items():
        per_window[window] = collect_observations(frames, start, end)
    pooled = [o for obs in per_window.values() for o in obs]

    # 1) composite quintile ladder (exp-20260531-006 machinery)
    quantile_agg = quantile_aggregate(per_window)
    quantile_gates = quantile_judge(quantile_agg)

    # 2) per-component RS-controlled decomposition (exp-20260601-003 machinery)
    attr = component_attribution(pooled, per_window)
    component_gates = component_judge(attr, len(pooled))

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "universe_size": len(frames),
        "sample_step_trading_days": SAMPLE_STEP,
        "total_observations": len(pooled),
        "observations_by_window": {w: len(o) for w, o in per_window.items()},
        "composite_quantile": {
            "decision": quantile_gates["gate4"]["status"],
            "aggregate": quantile_agg,
            "gates": quantile_gates,
        },
        "component_decomposition": {
            "decision": component_gates["gate4"]["status"],
            "component_attribution": attr,
            "gates": component_gates,
        },
        "decision": (
            f"composite:{quantile_gates['gate4']['status']}|"
            f"components:{component_gates['gate4']['status']}"
        ),
        "runtime_seconds": round(time.time() - t0, 1),
        "caveat": (
            "Broad universe is the exp-20260519-030 warehouse all-windows-full-"
            "liquid set; survivorship is limited to liquidity coverage, not "
            "delisting-free. expectation_revision / post_earnings_drift / theme "
            "inputs are unpopulated for non-curated tickers and will be constant "
            "or near-constant by data availability, not by being tested-and-weak."
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
    cq = result["composite_quantile"]
    cd = result["component_decomposition"]
    pooled_q = cq["aggregate"].get("pooled_quintile") or {}
    summary = {
        "experiment_id": result["experiment_id"],
        "universe_size": result["universe_size"],
        "total_observations": result["total_observations"],
        "runtime_seconds": result["runtime_seconds"],
        "composite_decision": cq["decision"],
        "composite_quintile_spread": pooled_q.get("top_minus_bottom_spread"),
        "composite_monotonic": pooled_q.get("monotonic_increasing_ladder"),
        "component_decision": cd["decision"],
        "component_5d_spread": {
            c: cd["component_attribution"][c]["pooled_spread_by_horizon"]["h5"]["top_minus_bottom"]
            for c in COMPONENTS
        },
        "residual_5d_vs_rs": {
            c: cd["component_attribution"][c].get("residual_5d_spread_vs_rs") for c in COMPONENTS
        },
        "near_constant": cd["gates"]["gate4"]["near_constant_components"],
        "non_momentum_incremental_edges": cd["gates"]["gate4"]["non_momentum_components_with_edge"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
