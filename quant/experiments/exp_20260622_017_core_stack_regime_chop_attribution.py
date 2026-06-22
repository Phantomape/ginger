"""exp-20260622-017: core accepted-stack regime-chop attribution (read-only).

Lane: measurement_repair (read-only diagnostic / observed-only).

Question
--------
exp-20260615-019 found that the accepted Fundamental-Growth+RS sleeve and a
rejected deferred-revenue scout both lose specifically in the directionless
`choppy_range` regime (SPY near/below trend AND weak breadth, but NOT stressed)
while staying positive in risk_on and risk_off. That finding promoted the
shared, rule-versioned `quant/regime_chop_state.py` module and motivates a
portfolio-level chop down-tilt (queue #3 in the playbook, the system's clearest
forward bet).

But the chop-sensitivity of the **core accepted stack** itself -- the canonical
~7.89-EV core book (breakout/post-earnings/rank-1 top-up etc.), not a default-off
sleeve -- has never been measured. If the core book also loses in chop, a
portfolio-level chop exposure tilt is broadly motivated; if chop-loss is
specific to the FGRS sleeve, the tilt should stay sleeve-scoped. Without this
measurement the portfolio tilt cannot be credibly proposed or sized.

What this does
--------------
Read-only. For every trade in the canonical core baseline artifact
(`exp-20260602-003`, the current accepted core-stack version) across the three
fixed windows, it recomputes the **entry-day** regime via the shared
`regime_chop_state.regime_chop_from_spy_universe` adapter at full fidelity
(SPY trend/momentum/drawdown/vol + universe breadth above 50d SMA), strictly
point-in-time (only bars dated <= entry_date), and buckets realized trade PnL by
regime label. It reports per-regime mean/median PnL and win rate, the continuous
`Spearman(p_choppy, pnl)` and `Spearman(exposure_scalar, pnl)`, and a
counterfactual estimate of what the shared `exposure_scalar` soft down-tilt
would have done to core PnL on these windows.

It changes NO entry, ranking, sizing, exit, or order behavior and asserts no
Gate-4 acceptance. Any execution use needs a separate Gate 1-4 experiment plus
forward / live-pilot validation, per `regime_chop_state.py` and the playbook.
"""

from __future__ import annotations

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

EXPERIMENT_ID = "exp-20260622-017"
SLUG = "core_stack_regime_chop_attribution"

# Canonical core baseline artifact (current accepted core-stack version).
BASELINE = ROOT / "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json"

# window label -> (after-result trade artifact, snapshot OHLCV file)
WINDOWS = {
    "late_strong": (
        "data/experiments/exp-20260602-003/late_strong_after.json",
        "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    ),
    "mid_weak": (
        "data/experiments/exp-20260602-003/mid_weak_after.json",
        "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    ),
    "old_thin": (
        "data/experiments/exp-20260602-003/old_thin_after.json",
        "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    ),
}

SMA_SHORT = 50
INDEX_TICKERS = ("SPY", "QQQ", "IWM")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict:
    return json.loads(io.open(path, encoding="utf-8").read())


def _ohlcv(snapshot: dict) -> dict:
    # snapshot files wrap bars under "ohlcv"; tolerate a flat dict too.
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


def main() -> None:
    baseline = _load_json(BASELINE)
    out_windows: dict[str, dict] = {}
    all_rows: list[dict] = []

    for label, (trade_path, snap_path) in WINDOWS.items():
        result = _load_json(ROOT / trade_path)
        ohlcv = _ohlcv(_load_json(ROOT / snap_path))
        spy = _spy_bars(ohlcv)
        breadth = _breadth_by_date(ohlcv)
        agree = _index_agreement_by_date(ohlcv)

        rows = []
        unresolved = 0
        for tr in result.get("trades", []):
            entry = str(tr.get("entry_date") or "")[:10]
            pnl = tr.get("pnl")
            if not entry or pnl is None:
                unresolved += 1
                continue
            reg = rcs.regime_chop_from_spy_universe(
                spy, entry, breadth=breadth.get(entry), index_agreement=agree.get(entry)
            )
            if reg.get("regime_label") in (None, "unknown"):
                unresolved += 1
                continue
            row = {
                "window": label,
                "ticker": tr.get("ticker"),
                "entry_date": entry,
                "pnl": float(pnl),
                "regime_label": reg.get("regime_label"),
                "p_choppy": reg.get("p_choppy_range"),
                "exposure_scalar": reg.get("exposure_scalar"),
                "bull_score": reg.get("bull_score"),
                "risk_off_score": reg.get("risk_off_score"),
                "stress_confident": reg.get("stress_confident"),
            }
            rows.append(row)
            all_rows.append(row)

        by_regime = {}
        for lbl in rcs.REGIME_LABELS:
            by_regime[lbl] = _summ([r["pnl"] for r in rows if r["regime_label"] == lbl])
        pc = [r for r in rows if r["p_choppy"] is not None]
        ex = [r for r in rows if r["exposure_scalar"] is not None]
        out_windows[label] = {
            "n_trades": len(rows),
            "unresolved": unresolved,
            "by_regime": by_regime,
            "spearman_pchoppy_pnl": _spearman([r["p_choppy"] for r in pc], [r["pnl"] for r in pc]),
            "spearman_exposure_pnl": _spearman([r["exposure_scalar"] for r in ex], [r["pnl"] for r in ex]),
        }

    # Pooled across windows.
    pooled_by_regime = {
        lbl: _summ([r["pnl"] for r in all_rows if r["regime_label"] == lbl]) for lbl in rcs.REGIME_LABELS
    }
    pc = [r for r in all_rows if r["p_choppy"] is not None]
    ex = [r for r in all_rows if r["exposure_scalar"] is not None]

    # Counterfactual: apply the shared exposure_scalar soft down-tilt to each
    # trade's realized PnL (scaling notional). This is a diagnostic estimate of
    # the tilt's directional effect, NOT a Gate-4 acceptance claim.
    actual_total = round(sum(r["pnl"] for r in all_rows), 2)
    tilted_total = round(sum(r["pnl"] * (r["exposure_scalar"] if r["exposure_scalar"] is not None else 1.0) for r in all_rows), 2)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "diagnostic_only": True,
        "trade_enabled": False,
        "alters_orders": False,
        "generated_at": _now(),
        "rule_version": rcs.RULE_VERSION,
        "hypothesis": (
            "The core accepted stack's chop-regime sensitivity is unmeasured; "
            "exp-20260615-019 only attributed the FGRS sleeve plus one scout."
        ),
        "method": {
            "trades_source": "data/experiments/exp-20260602-003 per-window after.json (canonical accepted core stack)",
            "regime_module": "quant/regime_chop_state.py:regime_chop_from_spy_universe",
            "fidelity": "full (SPY trend/momentum/drawdown/vol + universe breadth above 50d SMA + index agreement)",
            "point_in_time": "regime uses only bars dated <= entry_date; breadth/agreement computed within-snapshot",
            "windows": {k: {"trades": v[0], "snapshot": v[1]} for k, v in WINDOWS.items()},
        },
        "baseline_aggregate_ev": baseline.get("aggregate", {}).get("after", {}).get("expected_value_score"),
        "per_window": out_windows,
        "pooled": {
            "n_trades": len(all_rows),
            "by_regime": pooled_by_regime,
            "spearman_pchoppy_pnl": _spearman([r["p_choppy"] for r in pc], [r["pnl"] for r in pc]),
            "spearman_exposure_pnl": _spearman([r["exposure_scalar"] for r in ex], [r["pnl"] for r in ex]),
        },
        "counterfactual_soft_tilt": {
            "note": "diagnostic estimate only; scales each trade PnL by its entry-day exposure_scalar",
            "actual_core_total_pnl": actual_total,
            "tilted_core_total_pnl": tilted_total,
            "tilt_delta_pnl": round(tilted_total - actual_total, 2),
        },
        "trades": all_rows,
    }

    out_path = ROOT / f"data/experiments/{EXPERIMENT_ID}/exp_20260622_017_{SLUG}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(json.dumps({
        "pooled_n": len(all_rows),
        "pooled_by_regime": {k: {"n": v["n"], "mean_pnl": v["mean_pnl"], "win_rate": v["win_rate"]} for k, v in pooled_by_regime.items()},
        "spearman_pchoppy_pnl": artifact["pooled"]["spearman_pchoppy_pnl"],
        "spearman_exposure_pnl": artifact["pooled"]["spearman_exposure_pnl"],
        "counterfactual": artifact["counterfactual_soft_tilt"],
    }, indent=2))


if __name__ == "__main__":
    main()
