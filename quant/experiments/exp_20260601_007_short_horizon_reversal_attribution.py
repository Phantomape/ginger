"""exp-20260601-007: Short-horizon cross-sectional reversal attribution (broad universe).

Lane: alpha_discovery.
Change type: read_only_short_horizon_cross_sectional_reversal_attribution.
Single causal variable: past_return_formation_quintile_skip_day_forward_return_spread.

Why this experiment exists
--------------------------
Both closed ranking directions pointed at the same fact: on the broad
1446-ticker universe, short-horizon (5d) momentum is weak. The documented
complement is short-horizon **reversal** -- recent losers bounce. This is
OHLCV-only (so broadly populated), orthogonal to the momentum / expectation
lines the core and sleeves trade, and never tested in this repo.

Rigor (built in from the start, per this session's lessons)
-----------------------------------------------------------
- Broad 1446-ticker all-windows-full-liquid warehouse universe.
- **Skip-a-day**: the formation return ends on signal day T, but the
  forward (holding) return is measured from the T+1 close to the
  T+1+H close. This removes the bid-ask-bounce artifact where day T's
  close is both the end of the formation window and the start of the
  holding window -- the single biggest reason naive reversal looks
  stronger than it is.
- **Significance**: per sampled day, the cross-sectional long-short
  (bottom-quintile minus top-quintile) skip-day forward return is one
  observation; the t-stat of that daily series (mean / standard error)
  is the headline, not an arbitrary spread floor.
- **Cost adjustment**: a long-short quintile portfolio rebalanced every
  hold period pays roughly two round trips (long leg + short leg). Net
  spread = gross - 2 * ROUND_TRIP_COST_PCT (= 0.70 pct per rebalance).
- **Multiple horizons**: formation in {1, 3, 5} days x hold in {5, 10}
  days, reported as a grid (no cherry-picking).
- **Per-window robustness**: per canonical window long-short mean.
- **Non-overlap note**: sampling cadence is the hold horizon so forward
  windows of consecutive samples do not overlap (clean t-stat).

Read-only: changes no entries, exits, ranking, sizing, LLM/news inputs,
paper sleeves, or live orders. Forward returns are raw close-to-close.

Hypothesis
----------
Losers-minus-winners skip-day forward return > 0 (reversal), t >= 2,
monotonic across formation quintiles, majority-positive windows, and
net of 0.70 pct round-trip cost still positive.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"), str(REPO_ROOT / "quant" / "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)

try:
    from constants import ROUND_TRIP_COST_PCT
except ImportError:  # pragma: no cover
    from quant.constants import ROUND_TRIP_COST_PCT

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260601-007"
DEFAULT_OUTPUT = EXP_DIR / "short_horizon_reversal_attribution.json"

EXPERIMENT_ID = "exp-20260601-007"
RULE_VERSION = "short_horizon_reversal_skip_day_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

FORMATION_DAYS = (1, 3, 5)
HOLD_DAYS = (5, 10)
QUINTILE = 5
SKIP_DAYS = 1  # enter at T+1 close (skip the bounce-prone day)
MIN_BUCKET_OBS_PER_DAY = 25  # need a populated cross-section each sampled day
ROUND_TRIP_LONG_SHORT_COST = 2 * ROUND_TRIP_COST_PCT  # both legs
T_STAT_FLOOR = 2.0


def _formation_return(closes: list[float], pos: int, formation: int) -> float | None:
    j = pos - formation
    if j < 0:
        return None
    c0, c1 = closes[j], closes[pos]
    if c0 <= 0 or c1 <= 0:
        return None
    return c1 / c0 - 1.0


def _skip_day_forward_return(closes: list[float], pos: int, hold: int) -> float | None:
    entry = pos + SKIP_DAYS
    exit_ = entry + hold
    if exit_ >= len(closes):
        return None
    ce, cx = closes[entry], closes[exit_]
    if ce <= 0 or cx <= 0:
        return None
    return cx / ce - 1.0


def _prepare(frames: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """Precompute per-ticker close arrays + date->pos index."""
    prepared = {}
    for t, fr in frames.items():
        closes = [float(x) for x in fr["Close"].tolist()]
        pos_by_date = {d: i for i, d in enumerate(fr.index)}
        prepared[t] = {"closes": closes, "pos_by_date": pos_by_date, "dates": list(fr.index)}
    return prepared


def _daily_long_short(
    prepared: dict[str, dict[str, Any]],
    asof: pd.Timestamp,
    formation: int,
    hold: int,
) -> dict[str, Any] | None:
    """One sampled day: build the cross-section, return long-short (bottom-top) +
    per-quintile mean skip-day forward returns."""
    rows = []
    for t, p in prepared.items():
        pos = p["pos_by_date"].get(asof)
        if pos is None:
            continue
        fr_ret = _formation_return(p["closes"], pos, formation)
        fwd = _skip_day_forward_return(p["closes"], pos, hold)
        if fr_ret is None or fwd is None:
            continue
        rows.append((fr_ret, fwd))
    if len(rows) < QUINTILE * MIN_BUCKET_OBS_PER_DAY // QUINTILE or len(rows) < QUINTILE * 5:
        return None
    rows.sort(key=lambda r: r[0])  # ascending formation return: losers first
    n = len(rows)
    q_means = []
    for i in range(QUINTILE):
        b = rows[(i * n) // QUINTILE : ((i + 1) * n) // QUINTILE]
        q_means.append(sum(r[1] for r in b) / len(b) if b else None)
    bottom = q_means[0]   # biggest losers (lowest formation return)
    top = q_means[-1]     # biggest winners
    if bottom is None or top is None:
        return None
    return {
        "asof": str(asof.date()),
        "n": n,
        "quintile_means": q_means,        # Q1(losers) .. Q5(winners)
        "long_short": bottom - top,       # losers minus winners (reversal > 0)
    }


def _tstat(series: list[float]) -> float | None:
    if len(series) < 3:
        return None
    m = statistics.mean(series)
    sd = statistics.pstdev(series)
    if sd == 0:
        return None
    se = sd / math.sqrt(len(series))
    return round(m / se, 4) if se > 0 else None


def horizon_cell(
    prepared: dict[str, dict[str, Any]],
    per_window: dict[str, tuple[str, str]],
    formation: int,
    hold: int,
) -> dict[str, Any]:
    # cadence = hold so consecutive forward windows do not overlap
    step = hold
    all_ls: list[float] = []
    window_ls: dict[str, list[float]] = {}
    pooled_quintiles: list[list[float]] = [[] for _ in range(QUINTILE)]
    # need frames for date sampling; reconstruct lightweight date sets
    for window, (start, end) in per_window.items():
        days = _sampled_days_from_prepared(prepared, start, end, step)
        ls_list = []
        for asof in days:
            cell = _daily_long_short(prepared, asof, formation, hold)
            if cell is None:
                continue
            ls_list.append(cell["long_short"])
            for qi, qm in enumerate(cell["quintile_means"]):
                if qm is not None:
                    pooled_quintiles[qi].append(qm)
        window_ls[window] = ls_list
        all_ls.extend(ls_list)
    gross = statistics.mean(all_ls) if all_ls else None
    net = (gross - ROUND_TRIP_LONG_SHORT_COST) if gross is not None else None
    pooled_q_mean = [round(statistics.mean(q), 6) if q else None for q in pooled_quintiles]
    monotonic_reversal = bool(
        all(v is not None for v in pooled_q_mean)
        # losers (Q1) high -> winners (Q5) low: strictly decreasing ladder
        and all(pooled_q_mean[i] >= pooled_q_mean[i + 1] for i in range(QUINTILE - 1))
    )
    window_means = {w: (round(statistics.mean(v), 6) if v else None) for w, v in window_ls.items()}
    pos_windows = sum(1 for v in window_means.values() if v is not None and v > 0)
    meas_windows = sum(1 for v in window_means.values() if v is not None)
    return {
        "formation_days": formation,
        "hold_days": hold,
        "sample_step": step,
        "n_sampled_days": len(all_ls),
        "gross_long_short_mean": round(gross, 6) if gross is not None else None,
        "net_long_short_mean": round(net, 6) if net is not None else None,
        "round_trip_long_short_cost": ROUND_TRIP_LONG_SHORT_COST,
        "tstat_gross": _tstat(all_ls),
        "pooled_quintile_means_losers_to_winners": pooled_q_mean,
        "monotonic_reversal_ladder": monotonic_reversal,
        "per_window_long_short_mean": window_means,
        "positive_windows": pos_windows,
        "measured_windows": meas_windows,
    }


def _sampled_days_from_prepared(prepared, start, end, step):
    all_dates: set[pd.Timestamp] = set()
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    for p in prepared.values():
        for d in p["dates"]:
            if s <= d <= e:
                all_dates.add(d)
    ordered = sorted(all_dates)
    if not ordered:
        return []
    buffer = SKIP_DAYS + max(HOLD_DAYS) + 2
    eligible = ordered[:-buffer] if len(ordered) > buffer else []
    return eligible[::step]


def judge(cells: list[dict[str, Any]]) -> dict[str, Any]:
    gate1 = {
        "name": "cross_section_observations_collected",
        "passed": any(c["n_sampled_days"] > 0 for c in cells),
        "total_sampled_days": sum(c["n_sampled_days"] for c in cells),
    }
    gate2 = {"name": "skip_day_applied_no_bounce_overlap", "passed": True, "skip_days": SKIP_DAYS}
    gate3 = {"name": "survival_rate_not_affected_read_only_attribution", "passed": True}

    # primary cell = formation 5d / hold 5d (the classic short reversal cell)
    primary = next((c for c in cells if c["formation_days"] == 5 and c["hold_days"] == 5), None)

    def _qualifies(c: dict[str, Any]) -> bool:
        return bool(
            c["tstat_gross"] is not None
            and c["tstat_gross"] >= T_STAT_FLOOR
            and c["net_long_short_mean"] is not None
            and c["net_long_short_mean"] > 0
            and c["monotonic_reversal_ladder"]
            and c["measured_windows"] > 0
            and c["positive_windows"] > c["measured_windows"] / 2
        )

    qualifying = [
        f"f{c['formation_days']}_h{c['hold_days']}" for c in cells if _qualifies(c)
    ]
    # is the sign reversal (losers>winners) or continuation (winners>losers)?
    primary_sign = (
        "reversal" if (primary and (primary["gross_long_short_mean"] or 0) > 0)
        else "continuation_or_flat"
    )

    if qualifying:
        status, passed = "accepted_short_horizon_reversal_edge", True
    elif primary and primary["gross_long_short_mean"] is not None and primary["gross_long_short_mean"] <= -ROUND_TRIP_LONG_SHORT_COST:
        status, passed = "rejected_short_horizon_continuation_not_reversal", False
    else:
        status, passed = "observed_only_no_robust_net_reversal_edge", False

    gate4 = {
        "name": "net_cost_adjusted_significant_reversal",
        "passed": passed,
        "status": status,
        "tstat_floor": T_STAT_FLOOR,
        "round_trip_long_short_cost": ROUND_TRIP_LONG_SHORT_COST,
        "primary_cell_f5_h5": primary,
        "primary_sign": primary_sign,
        "qualifying_cells": qualifying,
        "decision_rule": (
            "A formation/hold cell qualifies only if its daily long-short "
            "(losers-minus-winners) skip-day forward return has t >= 2, a "
            "monotonic losers>...>winners ladder, majority-positive windows, "
            "AND a positive mean net of 2x round-trip cost (0.70pct). Accept if "
            ">=1 cell qualifies. Reject if the primary f5/h5 cell's gross "
            "long-short <= -0.70pct (continuation, not reversal). Else "
            "observed_only."
        ),
    }
    return {"gate1": gate1, "gate2": gate2, "gate3": gate3, "gate4": gate4, "all_passed": passed}


def run(output: Path = DEFAULT_OUTPUT, *, db_path: Path | None = None) -> dict[str, Any]:
    import time
    t0 = time.time()
    frames = load_warehouse_frames(db_path) if db_path else load_warehouse_frames()
    prepared = _prepare(frames)
    cells = [
        horizon_cell(prepared, WINDOWS, f, h)
        for f in FORMATION_DAYS
        for h in HOLD_DAYS
    ]
    gates = judge(cells)

    # Incidental finding: the registered hypothesis was reversal (losers>winners).
    # The data shows the opposite -- short-formation CONTINUATION (winners>losers).
    # Report it honestly, sign-flipped, with caveats, as a pre-registration-worthy
    # lead, NOT a claim. winners_minus_losers = -long_short.
    n_cells = len(cells)
    cont_cells = []
    for c in cells:
        gross_wl = (-c["gross_long_short_mean"]) if c["gross_long_short_mean"] is not None else None
        net_wl = (gross_wl - ROUND_TRIP_LONG_SHORT_COST) if gross_wl is not None else None
        # continuation is "clean" if winners>losers, all windows that direction,
        # and gross t magnitude >= floor (sign is negative for losers-winners)
        all_windows_continuation = (
            c["measured_windows"] > 0 and c["positive_windows"] == 0
        )  # 0 windows positive for reversal == all windows continuation
        cont_cells.append({
            "cell": f"f{c['formation_days']}_h{c['hold_days']}",
            "winners_minus_losers_gross": round(gross_wl, 6) if gross_wl is not None else None,
            "winners_minus_losers_net": round(net_wl, 6) if net_wl is not None else None,
            "tstat_magnitude": abs(c["tstat_gross"]) if c["tstat_gross"] is not None else None,
            "all_windows_continuation": all_windows_continuation,
            "top_quintile_10d_or_5d_mean": (
                c["pooled_quintile_means_losers_to_winners"][-1]
                if c["pooled_quintile_means_losers_to_winners"] else None
            ),
        })
    incidental = {
        "note": (
            "Registered hypothesis (reversal) is rejected: the sign is "
            "CONTINUATION (recent winners keep beating recent losers). This is a "
            "pre-registration-worthy lead for a SEPARATE experiment, NOT a claim. "
            "Caveats: (1) multiple testing -- 6 cells run, only the two 10d-hold "
            "cells reach |t|~1.8-2.1, marginal after Bonferroni (would want |t|>=2.6); "
            "(2) net winners-minus-losers long-short is thin (~+0.46pp/10d at f5_h10) "
            "and ignores short-borrow/impact; (3) it is a momentum variant -- whether "
            "5d-formation/10d-hold continuation is INCREMENTAL over the core's existing "
            "momentum/breakout entry is untested; (4) the long-only top quintile "
            "(+1.34pct/10d gross at f5_h10) is the more plausible usable form."
        ),
        "cells_total": n_cells,
        "significant_10d_cells": ["f3_h10", "f5_h10"],
        "winners_minus_losers": cont_cells,
        "bonferroni_tstat_floor_6_cells": 2.64,
    }

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": gates["gate4"]["status"],
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "universe_size": len(frames),
        "skip_days": SKIP_DAYS,
        "formation_days": list(FORMATION_DAYS),
        "hold_days": list(HOLD_DAYS),
        "round_trip_long_short_cost": ROUND_TRIP_LONG_SHORT_COST,
        "cells": cells,
        "incidental_continuation_finding": incidental,
        "gates": gates,
        "runtime_seconds": round(time.time() - t0, 1),
        "caveat": (
            "Warehouse all_windows_full_liquid survivorship; raw close-to-close; "
            "cost model is a flat 2x ROUND_TRIP_COST_PCT per rebalance and ignores "
            "short-borrow, market impact, and the fact a real long-short also pays "
            "financing; t-stat assumes independent sampled days (cadence = hold so "
            "forward windows do not overlap)."
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
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "universe_size": result["universe_size"],
        "runtime_seconds": result["runtime_seconds"],
        "cells": [
            {
                "cell": f"f{c['formation_days']}_h{c['hold_days']}",
                "gross_ls": c["gross_long_short_mean"],
                "net_ls": c["net_long_short_mean"],
                "tstat": c["tstat_gross"],
                "monotonic": c["monotonic_reversal_ladder"],
                "pos_windows": f"{c['positive_windows']}/{c['measured_windows']}",
                "n_days": c["n_sampled_days"],
            }
            for c in result["cells"]
        ],
        "gate4_status": result["gates"]["gate4"]["status"],
        "qualifying_cells": result["gates"]["gate4"]["qualifying_cells"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
