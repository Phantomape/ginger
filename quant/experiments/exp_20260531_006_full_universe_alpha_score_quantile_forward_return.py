"""exp-20260531-006: Full-universe composite alpha_score quantile forward-return
attribution.

Lane: alpha_discovery.
Change type: read_only_full_universe_ranking_forward_return_attribution.
Single causal variable: full_universe_pit_alpha_score_quantile_forward_return.

Why this experiment exists
--------------------------
`exp-20260530-022` showed the composite alpha_score cannot be validated on
*filled* core trades (entry rule concentrates fills into the top rank
bucket; no bottom comparison group). Its declared next step was to score
the FULL daily candidate universe (filled and unfilled) and bucket all
(day, ticker) observations by alpha_score quantile against forward returns.
This experiment does exactly that.

Method (read-only PIT)
----------------------
For each canonical window (late_strong / mid_weak / old_thin):
1. Load the window OHLCV snapshot.
2. Sample trading days every ``SAMPLE_STEP`` sessions across the window
   interior (forward buffer so 20d outcomes are observable).
3. For each sampled day, reuse ``entry_day_ranking_attribution._context_for_asof``
   to score the full universe and obtain ``alpha_score`` per ticker.
4. Compute close-to-close forward returns at 5 / 10 / 20 trading days.
5. Pool every (day, ticker) observation, bucket by alpha_score quintile
   and decile, aggregate forward returns per bucket.

Forward returns are raw close-to-close (no costs): this is an attribution
of the ranking surface's cross-sectional predictive power, not a tradeable
PnL. It changes no entries, exits, ranking, sizing, LLM/news inputs, paper
sleeves, or live orders.

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

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260531-006"
DEFAULT_OUTPUT = EXP_DIR / "full_universe_alpha_score_quantile_forward_return.json"

EXPERIMENT_ID = "exp-20260531-006"
RULE_VERSION = "full_universe_alpha_score_quantile_forward_return_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21", "ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak": ("2025-04-23", "2025-10-22", "ohlcv_snapshot_20250423_20251022.json"),
    "old_thin": ("2024-10-02", "2025-04-22", "ohlcv_snapshot_20241002_20250422.json"),
}

SAMPLE_STEP = 5
FORWARD_HORIZONS = (5, 10, 20)
PRIMARY_HORIZON = 5
QUINTILE = 5
DECILE = 10
MIN_BUCKET_OBS = 30
EDGE_FLOOR = 0.005


def _forward_returns(frame: pd.DataFrame, asof_ts: pd.Timestamp) -> dict[int, float]:
    idx = frame.index
    pos = idx.searchsorted(asof_ts)
    if pos >= len(idx) or idx[pos] != asof_ts:
        return {}
    base_close = float(frame["Close"].iloc[pos])
    if base_close <= 0:
        return {}
    out: dict[int, float] = {}
    for h in FORWARD_HORIZONS:
        fpos = pos + h
        if fpos < len(idx):
            fwd_close = float(frame["Close"].iloc[fpos])
            if fwd_close > 0:
                out[h] = fwd_close / base_close - 1.0
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
            alpha = info.get("alpha_score")
            if alpha is None:
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
                    "alpha_score": float(alpha),
                    "forward_returns": fwd,
                }
            )
    return observations


def _quantile_buckets(obs: list[dict[str, Any]], n_buckets: int) -> list[list[dict[str, Any]]]:
    ordered = sorted(obs, key=lambda o: o["alpha_score"])
    total = len(ordered)
    return [
        ordered[(i * total) // n_buckets : ((i + 1) * total) // n_buckets]
        for i in range(n_buckets)
    ]


def _bucket_stats(bucket: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    rets = [o["forward_returns"][horizon] for o in bucket if horizon in o["forward_returns"]]
    if not rets:
        return {"obs": 0, "avg_return": None, "median_return": None, "win_rate": None}
    # top-5 single-observation concentration of the positive return mass
    pos = sorted((r for r in rets if r > 0), reverse=True)
    pos_total = sum(pos)
    top5_share = round(sum(pos[:5]) / pos_total, 4) if pos_total > 0 else None
    return {
        "obs": len(rets),
        "avg_return": round(sum(rets) / len(rets), 6),
        "median_return": round(statistics.median(rets), 6),
        "win_rate": round(sum(1 for r in rets if r > 0) / len(rets), 4),
        "top5_positive_share": top5_share,
        "alpha_score_lo": round(min(o["alpha_score"] for o in bucket), 6),
        "alpha_score_hi": round(max(o["alpha_score"] for o in bucket), 6),
    }


def quantile_attribution(obs: list[dict[str, Any]], n_buckets: int, label: str) -> dict[str, Any]:
    buckets = _quantile_buckets(obs, n_buckets)
    per_bucket = []
    for i, b in enumerate(buckets):
        entry = {"bucket": f"{label}_{i + 1}", "n_obs": len(b)}
        for h in FORWARD_HORIZONS:
            entry[f"h{h}"] = _bucket_stats(b, h)
        per_bucket.append(entry)
    spreads = {}
    monotonic = {}
    for h in FORWARD_HORIZONS:
        avgs = [pb[f"h{h}"]["avg_return"] for pb in per_bucket]
        top, bot = avgs[-1], avgs[0]
        spreads[f"h{h}"] = (
            round(top - bot, 6) if (top is not None and bot is not None) else None
        )
        # strictly increasing avg_return ladder?
        clean = all(a is not None for a in avgs)
        monotonic[f"h{h}"] = bool(
            clean and all(avgs[i + 1] >= avgs[i] for i in range(len(avgs) - 1))
        )
    return {
        "buckets": per_bucket,
        "top_minus_bottom_spread": spreads,
        "monotonic_increasing_ladder": monotonic,
    }


def aggregate(per_window_obs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    pooled: list[dict[str, Any]] = []
    for obs in per_window_obs.values():
        pooled.extend(obs)
    window_spreads_5d = {}
    for w, obs in per_window_obs.items():
        if len(obs) >= QUINTILE * 5:
            q = quantile_attribution(obs, QUINTILE, "q")
            window_spreads_5d[w] = q["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}")
        else:
            window_spreads_5d[w] = None
    return {
        "total_observations": len(pooled),
        "observations_by_window": {w: len(o) for w, o in per_window_obs.items()},
        "pooled_quintile": quantile_attribution(pooled, QUINTILE, "q") if pooled else None,
        "pooled_decile": quantile_attribution(pooled, DECILE, "d") if pooled else None,
        "per_window_5d_top_minus_bottom_spread": window_spreads_5d,
    }


def judge(agg: dict[str, Any]) -> dict[str, Any]:
    pooled_q = agg.get("pooled_quintile")
    gate1 = {
        "name": "full_universe_observations_collected",
        "passed": agg["total_observations"] > 0,
        "total_observations": agg["total_observations"],
    }
    min_bucket = min((b["n_obs"] for b in pooled_q["buckets"]), default=0) if pooled_q else 0
    gate2 = {
        "name": "quantile_buckets_meet_obs_floor",
        "passed": bool(pooled_q) and min_bucket >= MIN_BUCKET_OBS,
        "min_pooled_quintile_obs": min_bucket,
        "floor": MIN_BUCKET_OBS,
    }
    gate3 = {"name": "survival_rate_not_affected_read_only_attribution", "passed": True}

    spread_5d = pooled_q["top_minus_bottom_spread"].get(f"h{PRIMARY_HORIZON}") if pooled_q else None
    monotonic_5d = pooled_q["monotonic_increasing_ladder"].get(f"h{PRIMARY_HORIZON}") if pooled_q else False
    window_spreads = agg["per_window_5d_top_minus_bottom_spread"]
    positive_windows = sum(1 for v in window_spreads.values() if v is not None and v > 0)
    measured_windows = sum(1 for v in window_spreads.values() if v is not None)
    majority_positive = measured_windows > 0 and positive_windows > measured_windows / 2

    if not gate2["passed"]:
        status, passed = "observed_only_insufficient_universe_observations", False
    elif spread_5d is None:
        status, passed = "observed_only_no_quantile_spread_measurable", False
    elif spread_5d >= EDGE_FLOOR and majority_positive and monotonic_5d:
        status, passed = "accepted_full_universe_alpha_score_forward_edge", True
    elif spread_5d >= EDGE_FLOOR and majority_positive:
        status, passed = "observed_only_top_bottom_edge_without_clean_ladder", False
    elif spread_5d <= -EDGE_FLOOR:
        status, passed = "rejected_full_universe_alpha_score_inverted", False
    else:
        status, passed = "observed_only_no_robust_quantile_edge", False

    gate4 = {
        "name": "full_universe_quantile_forward_return_edge",
        "passed": passed,
        "status": status,
        "primary_horizon": PRIMARY_HORIZON,
        "edge_floor": EDGE_FLOOR,
        "pooled_quintile_top_minus_bottom_5d": spread_5d,
        "pooled_quintile_monotonic_ladder_5d": monotonic_5d,
        "per_window_5d_spread": window_spreads,
        "positive_windows": positive_windows,
        "measured_windows": measured_windows,
        "decision_rule": (
            "Accept only if pooled top-quintile minus bottom-quintile 5d "
            "forward return >= 0.005 AND a majority of windows show positive "
            "spread AND the pooled quintile avg-return ladder is monotonic "
            "increasing AND every pooled quintile has >= 30 obs. A top-vs-"
            "bottom edge without a clean ladder is observed_only. Reject if "
            "the pooled 5d spread <= -0.005."
        ),
    }
    return {"gate1": gate1, "gate2": gate2, "gate3": gate3, "gate4": gate4, "all_passed": passed}


def run(output: Path = DEFAULT_OUTPUT, *, snapshot_dir: Path | None = None) -> dict[str, Any]:
    snapshot_dir = snapshot_dir or (REPO_ROOT / "data" / "ohlcv")
    per_window_obs: dict[str, list[dict[str, Any]]] = {}
    for window, (start, end, snap) in WINDOWS.items():
        ohlcv = load_ohlcv_snapshot(str(snapshot_dir / snap))
        per_window_obs[window] = collect_observations(ohlcv, start, end)

    agg = aggregate(per_window_obs)
    gates = judge(agg)
    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": gates["gate4"]["status"],
        "sample_step_trading_days": SAMPLE_STEP,
        "forward_horizons": list(FORWARD_HORIZONS),
        "windows": {w: {"start": s, "end": e} for w, (s, e, _) in WINDOWS.items()},
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
    pooled_q = result["aggregate"].get("pooled_quintile") or {}
    summary = {
        "anti_js": result["anti_js"],
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "total_observations": result["aggregate"]["total_observations"],
        "pooled_quintile_spread": pooled_q.get("top_minus_bottom_spread"),
        "pooled_quintile_monotonic": pooled_q.get("monotonic_increasing_ladder"),
        "per_window_5d_spread": result["gates"]["gate4"]["per_window_5d_spread"],
        "gate4_status": result["gates"]["gate4"]["status"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
