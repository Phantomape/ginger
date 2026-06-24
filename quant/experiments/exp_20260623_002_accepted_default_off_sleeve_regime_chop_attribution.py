"""exp-20260623-002: accepted default-off sleeve regime-chop attribution (read-only).

Lane: measurement_repair (read-only diagnostic / observed-only).

Question
--------
exp-20260615-019 found the accepted Fundamental-Growth+RS sleeve loses
specifically in the directionless `choppy_range` regime (SPY near/below trend
AND weak breadth, but NOT stressed). exp-20260622-017 then showed the **core
accepted stack** does NOT share that chop-loss -- sign reversed and consistent
(pooled Spearman(p_choppy, PnL) = +0.116). The sanctioned next bet (playbook
queue #3) is a chop-scoped SOFT exposure down-tilt, but it must be scoped only
to sleeves with individually-negative chop sensitivity; applying it portfolio-
wide would have cut core PnL by ~12%.

The gap this closes: every OTHER accepted default-off candidate-pool sleeve
(industry_stable_core_flow, narrow_range_compression_breakout,
turn_of_month_liquid_leadership, fiftytwo_week_high_proximity,
distribution_day_absorption_leadership, sbc_burden_improvement,
supplier_financing_debt_relief, revision_surprise_low_extension) has NEVER been
regime-attributed. Without this measurement the chop down-tilt's scope set is
guesswork.

What this does
--------------
Read-only. For every accepted default-off sleeve's per-window replay trades
(`target_trades_by_window` in each acceptance artifact), it recomputes the
**entry-day** regime via the shared
`regime_chop_state.regime_chop_from_spy_universe` adapter at full fidelity
(SPY trend/momentum/drawdown/vol + universe breadth above 50d SMA + index
agreement), strictly point-in-time (only bars dated <= entry_date), and buckets
realized trade PnL by regime label. Per sleeve it reports per-regime mean/median
PnL and win rate, continuous Spearman(p_choppy, pnl) and
Spearman(exposure_scalar, pnl) (per-window + pooled), and a counterfactual
estimate of what the shared `exposure_scalar` soft down-tilt would have done to
that sleeve's PnL on these windows. A cross-sleeve summary ranks every sleeve by
pooled chop sensitivity and partitions them into the chop-down-tilt SCOPE set
(individually chop-negative) versus EXCLUDE set (chop-neutral/positive), placing
the prior FGRS (-0.324) and core (+0.116) reference points on the same scale.

It changes NO entry, ranking, sizing, exit, or order behavior and asserts no
Gate-4 acceptance. Any execution use needs a separate Gate 1-4 experiment plus
forward / live-pilot validation tagged with entry-time regime, per
`regime_chop_state.py` and the playbook -- never a frozen-window re-slice.
"""

from __future__ import annotations

import glob
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

import regime_chop_state as rcs  # noqa: E402

EXPERIMENT_ID = "exp-20260623-002"
SLUG = "accepted_default_off_sleeve_regime_chop_attribution"

# Accepted default-off candidate-pool sleeves: name -> acceptance experiment id.
# Each artifact carries per-window `target_trades_by_window` with entry_date+pnl.
ROSTER = {
    "industry_stable_core_flow": "exp-20260608-008",
    "narrow_range_compression_breakout": "exp-20260608-013",
    "turn_of_month_liquid_leadership": "exp-20260609-027",
    "fiftytwo_week_high_proximity": "exp-20260610-008",
    "distribution_day_absorption_leadership": "exp-20260611-007",
    "sbc_burden_improvement": "exp-20260616-015",
    "supplier_financing_debt_relief": "exp-20260620-009",
    "revision_surprise_low_extension": "exp-20260609-011",
}

# Prior regime-attribution reference points on the SAME pooled-Spearman scale.
PRIOR_REFERENCES = {
    "fundamental_growth_rs (exp-20260615-019/025)": -0.324,
    "core_accepted_stack (exp-20260622-017)": 0.116,
}

# window label -> snapshot OHLCV file (universe + index bars).
WINDOW_SNAPSHOTS = {
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
}

# Scope threshold: a sleeve enters the chop-down-tilt scope set only if its
# pooled chop sensitivity is materially negative on a non-trivial sample.
SCOPE_SPEARMAN_MAX = -0.10
SCOPE_MIN_TRADES = 20

SMA_SHORT = 50
INDEX_TICKERS = ("SPY", "QQQ", "IWM")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict:
    return json.loads(io.open(path, encoding="utf-8").read())


def _ohlcv(snapshot: dict) -> dict:
    if isinstance(snapshot, dict) and "ohlcv" in snapshot:
        return snapshot["ohlcv"]
    return snapshot


def _spy_bars(ohlcv: dict) -> list[dict]:
    bars = [b for b in (ohlcv.get("SPY") or []) if b.get("Date") and b.get("Close") is not None]
    bars.sort(key=lambda b: b["Date"])
    return bars


def _breadth_by_date(ohlcv: dict) -> dict[str, float]:
    """Fraction of non-index universe tickers with Close > own 50d SMA, by date."""
    above: dict[str, int] = {}
    total: dict[str, int] = {}
    for ticker, bars in ohlcv.items():
        if ticker in INDEX_TICKERS:
            continue
        rows = [b for b in (bars or []) if b.get("Date") and b.get("Close") is not None]
        rows.sort(key=lambda b: b["Date"])
        closes = [float(b["Close"]) for b in rows]
        dates = [b["Date"][:10] for b in rows]
        run = 0.0
        for i in range(len(closes)):
            run += closes[i]
            if i >= SMA_SHORT:
                run -= closes[i - SMA_SHORT]
            if i >= SMA_SHORT - 1:
                sma = run / SMA_SHORT
                d = dates[i]
                total[d] = total.get(d, 0) + 1
                if closes[i] > sma:
                    above[d] = above.get(d, 0) + 1
    return {d: above.get(d, 0) / total[d] for d in total if total[d] > 0}


def _index_agreement_by_date(ohlcv: dict, lookback: int = 20) -> dict[str, float]:
    """Fraction of {SPY,QQQ,IWM} with positive trailing `lookback`d return, by date."""
    ret_pos: dict[str, int] = {}
    cnt: dict[str, int] = {}
    for tkr in INDEX_TICKERS:
        rows = [b for b in (ohlcv.get(tkr) or []) if b.get("Date") and b.get("Close") is not None]
        rows.sort(key=lambda b: b["Date"])
        closes = [float(b["Close"]) for b in rows]
        dates = [b["Date"][:10] for b in rows]
        for i in range(lookback, len(closes)):
            d = dates[i]
            cnt[d] = cnt.get(d, 0) + 1
            if closes[i - lookback] > 0 and closes[i] / closes[i - lookback] - 1.0 > 0:
                ret_pos[d] = ret_pos.get(d, 0) + 1
    return {d: ret_pos.get(d, 0) / cnt[d] for d in cnt if cnt[d] > 0}


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 4:
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    vy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


def _summ(pnls: list[float]) -> dict:
    if not pnls:
        return {"n": 0, "mean_pnl": None, "median_pnl": None, "win_rate": None, "total_pnl": 0.0}
    s = sorted(pnls)
    n = len(s)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {
        "n": n,
        "mean_pnl": round(sum(pnls) / n, 2),
        "median_pnl": round(median, 2),
        "win_rate": round(sum(1 for p in pnls if p > 0) / n, 4),
        "total_pnl": round(sum(pnls), 2),
    }


def _artifact_path(eid: str) -> Path:
    fs = sorted(glob.glob(str(ROOT / "data/experiments" / eid / "*.json")))
    if not fs:
        raise FileNotFoundError(f"no artifact for {eid}")
    return Path(fs[0])


def main() -> None:
    # Precompute per-window regime context once (snapshots are large).
    win_ctx: dict[str, dict] = {}
    for label, snap_path in WINDOW_SNAPSHOTS.items():
        ohlcv = _ohlcv(_load_json(ROOT / snap_path))
        win_ctx[label] = {
            "spy": _spy_bars(ohlcv),
            "breadth": _breadth_by_date(ohlcv),
            "agree": _index_agreement_by_date(ohlcv),
        }

    sleeves_out: dict[str, dict] = {}
    for sleeve, eid in ROSTER.items():
        art = _load_json(_artifact_path(eid))
        ttw = art.get("target_trades_by_window", {})
        all_rows: list[dict] = []
        per_window: dict[str, dict] = {}
        for label in WINDOW_SNAPSHOTS:
            ctx = win_ctx[label]
            rows = []
            unresolved = 0
            for tr in ttw.get(label, []):
                entry = str(tr.get("entry_date") or "")[:10]
                pnl = tr.get("pnl")
                if not entry or pnl is None:
                    unresolved += 1
                    continue
                reg = rcs.regime_chop_from_spy_universe(
                    ctx["spy"], entry,
                    breadth=ctx["breadth"].get(entry),
                    index_agreement=ctx["agree"].get(entry),
                )
                if reg.get("regime_label") in (None, "unknown"):
                    unresolved += 1
                    continue
                row = {
                    "sleeve": sleeve,
                    "window": label,
                    "ticker": tr.get("ticker"),
                    "entry_date": entry,
                    "pnl": float(pnl),
                    "regime_label": reg.get("regime_label"),
                    "p_choppy": reg.get("p_choppy_range"),
                    "exposure_scalar": reg.get("exposure_scalar"),
                }
                rows.append(row)
                all_rows.append(row)
            by_regime = {
                lbl: _summ([r["pnl"] for r in rows if r["regime_label"] == lbl])
                for lbl in rcs.REGIME_LABELS
            }
            pc = [r for r in rows if r["p_choppy"] is not None]
            per_window[label] = {
                "n_trades": len(rows),
                "unresolved": unresolved,
                "by_regime": by_regime,
                "spearman_pchoppy_pnl": _spearman(
                    [r["p_choppy"] for r in pc], [r["pnl"] for r in pc]
                ),
            }

        pooled_by_regime = {
            lbl: _summ([r["pnl"] for r in all_rows if r["regime_label"] == lbl])
            for lbl in rcs.REGIME_LABELS
        }
        pc = [r for r in all_rows if r["p_choppy"] is not None]
        ex = [r for r in all_rows if r["exposure_scalar"] is not None]
        pooled_spearman = _spearman([r["p_choppy"] for r in pc], [r["pnl"] for r in pc])
        actual_total = round(sum(r["pnl"] for r in all_rows), 2)
        tilted_total = round(
            sum(r["pnl"] * (r["exposure_scalar"] if r["exposure_scalar"] is not None else 1.0)
                for r in all_rows), 2,
        )
        sleeves_out[sleeve] = {
            "experiment_id": eid,
            "n_trades": len(all_rows),
            "pooled_spearman_pchoppy_pnl": pooled_spearman,
            "pooled_spearman_exposure_pnl": _spearman(
                [r["exposure_scalar"] for r in ex], [r["pnl"] for r in ex]
            ),
            "pooled_by_regime": pooled_by_regime,
            "per_window": per_window,
            "counterfactual_soft_tilt": {
                "actual_total_pnl": actual_total,
                "tilted_total_pnl": tilted_total,
                "tilt_delta_pnl": round(tilted_total - actual_total, 2),
            },
        }

    # Cross-sleeve scope partition.
    ranked = sorted(
        sleeves_out.items(),
        key=lambda kv: (kv[1]["pooled_spearman_pchoppy_pnl"] is None,
                        kv[1]["pooled_spearman_pchoppy_pnl"] if kv[1]["pooled_spearman_pchoppy_pnl"] is not None else 0.0),
    )
    scope_set, exclude_set = [], []
    for name, d in ranked:
        sp = d["pooled_spearman_pchoppy_pnl"]
        rec = {
            "sleeve": name,
            "pooled_spearman_pchoppy_pnl": sp,
            "n_trades": d["n_trades"],
            "chop_bucket_mean_pnl": d["pooled_by_regime"]["choppy_range"]["mean_pnl"],
            "chop_bucket_n": d["pooled_by_regime"]["choppy_range"]["n"],
            "counterfactual_tilt_delta_pnl": d["counterfactual_soft_tilt"]["tilt_delta_pnl"],
        }
        if sp is not None and sp <= SCOPE_SPEARMAN_MAX and d["n_trades"] >= SCOPE_MIN_TRADES:
            scope_set.append(rec)
        else:
            exclude_set.append(rec)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "diagnostic_only": True,
        "trade_enabled": False,
        "alters_orders": False,
        "generated_at": _now(),
        "rule_version": rcs.RULE_VERSION,
        "hypothesis": (
            "Chop-regime PnL sensitivity is sleeve-specific; attributing every "
            "accepted default-off sleeve identifies the subset a chop-scoped soft "
            "down-tilt should cover and which it must exclude."
        ),
        "method": {
            "trades_source": "each sleeve acceptance artifact target_trades_by_window (default-off paper replay)",
            "regime_module": "quant/regime_chop_state.py:regime_chop_from_spy_universe",
            "fidelity": "full (SPY trend/momentum/drawdown/vol + universe breadth above 50d SMA + index agreement)",
            "point_in_time": "regime uses only bars dated <= entry_date; breadth/agreement computed within-snapshot",
            "roster": ROSTER,
            "windows": WINDOW_SNAPSHOTS,
            "scope_rule": {
                "spearman_pchoppy_pnl_max": SCOPE_SPEARMAN_MAX,
                "min_trades": SCOPE_MIN_TRADES,
            },
        },
        "prior_reference_pooled_spearman": PRIOR_REFERENCES,
        "sleeves": sleeves_out,
        "scope_partition": {
            "chop_down_tilt_scope_set": scope_set,
            "exclude_set": exclude_set,
            "note": (
                "Scope set = sleeves with pooled Spearman(p_choppy,PnL) <= "
                f"{SCOPE_SPEARMAN_MAX} on >= {SCOPE_MIN_TRADES} trades. This is a "
                "diagnostic scoping surface only; a separate Gate 1-4 plus forward "
                "entry-regime-tagged rows are required before any soft tilt drives capital."
            ),
        },
    }

    out_path = ROOT / f"data/experiments/{EXPERIMENT_ID}/exp_20260623_002_{SLUG}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    summary = {
        "ranked_pooled_spearman_pchoppy_pnl": [
            {
                "sleeve": name,
                "spearman": (round(d["pooled_spearman_pchoppy_pnl"], 4)
                             if d["pooled_spearman_pchoppy_pnl"] is not None else None),
                "n": d["n_trades"],
                "chop_n": d["pooled_by_regime"]["choppy_range"]["n"],
                "chop_mean_pnl": d["pooled_by_regime"]["choppy_range"]["mean_pnl"],
                "tilt_delta_pnl": d["counterfactual_soft_tilt"]["tilt_delta_pnl"],
            }
            for name, d in ranked
        ],
        "scope_set": [r["sleeve"] for r in scope_set],
        "exclude_set": [r["sleeve"] for r in exclude_set],
        "prior_reference_pooled_spearman": PRIOR_REFERENCES,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
