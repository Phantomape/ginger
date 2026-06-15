"""exp-20260615-019: PIT regime-state classifier + conditional attribution.

Measurement-repair / diagnostic. It builds the measurement surface that lets us
ask "is a strategy's edge regime-conditional?" WITHOUT re-slicing the three
canonical windows, which is the thing the deferred-revenue scout
(exp-20260615-017) and the broader partial-window-improvement question exposed.

Two read-only deliverables:

1. A mechanical, point-in-time regime classifier. For an as-of date it uses only
   free index OHLCV (SPY/QQQ/IWM) and universe breadth observable on or before
   that date, and emits a probability vector over
   {risk_on_trend, choppy_range, risk_off_stress} plus a scalar risk_off_score
   and bull_score. The constants are CONVENTIONAL market-structure thresholds
   (200d MA, 252d high, ~8% drawdown, ~1.3x vol elevation); they are NOT
   optimized against the trade outcomes below, so the attribution is leak-free.

2. Conditional attribution: each accepted-sleeve replay trade and each
   exp-20260615-017 deferred-revenue paper trade is tagged with the regime at
   its signal date, and we report per-regime trade count, mean PnL, win rate,
   and a separation metric. The 31 closed forward paper-sleeve rows are tagged
   observe-only (too few for inference, reported for completeness).

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402

EXPERIMENT_ID = "exp-20260615-019"
STEM = "pit_regime_state_attribution"
CHANGED_VARIABLE = "pit_regime_state_classifier_and_conditional_attribution_surface"
RULE_VERSION = "pit_regime_state_classifier_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

# Canonical windows -> snapshot file (docs/backtesting.md).
WINDOWS = OrderedDict(
    [
        ("late_strong", ("2025-10-23", "2026-04-21", "data/ohlcv/ohlcv_snapshot_20251023_20260421.json")),
        ("mid_weak", ("2025-04-23", "2025-10-22", "data/ohlcv/ohlcv_snapshot_20250423_20251022.json")),
        ("old_thin", ("2024-10-02", "2025-04-22", "data/ohlcv/ohlcv_snapshot_20241002_20250422.json")),
    ]
)

# Accepted-sleeve replay trade sets to attribute (read directly from artifacts).
FGRS_SOURCE_ARTIFACT = REPO_ROOT / "data" / "experiments" / "exp-20260528-017" / "fundamental_growth_rs_low_liability_support.json"
DEFERRED_REVENUE_ARTIFACT = REPO_ROOT / "data" / "experiments" / "exp-20260615-017" / "exp_20260615_017_deferred_revenue_demand_acceleration.json"
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"

INDEX_TICKERS = ("SPY", "QQQ", "IWM")
REGIME_LABELS = ("risk_on_trend", "choppy_range", "risk_off_stress")

# Conventional, NOT-optimized structural constants.
SMA_LONG = 200
SMA_SHORT = 50
HIGH_LOOKBACK = 252
RET_LOOKBACK = 20
VOL_LOOKBACK = 20
VOL_MEDIAN_LOOKBACK = 100
DD_REF = 0.08            # ~8% drawdown reference
VOL_RATIO_REF = 1.30     # ~30% above own median realized vol
MIN_BARS_FOR_REGIME = 150


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return round(out, digits) if math.isfinite(out) else None


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# PIT regime classifier
# --------------------------------------------------------------------------- #
def _series(ohlcv: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    bars = ohlcv.get(ticker) or []
    rows = [b for b in bars if b.get("Date") and b.get("Close") is not None]
    rows.sort(key=lambda b: str(b["Date"])[:10])
    return rows


class RegimeModel:
    """Per-window PIT regime model precomputed over one snapshot's index bars."""

    def __init__(self, ohlcv: dict[str, Any]) -> None:
        spy = _series(ohlcv, "SPY")
        self.dates = [str(b["Date"])[:10] for b in spy]
        self.closes = [float(b["Close"]) for b in spy]
        self.highs = [float(b.get("High") or b["Close"]) for b in spy]
        self._date_to_idx = {d: i for i, d in enumerate(self.dates)}
        # cross-index 20d return sign agreement, aligned to SPY dates by date.
        self._idx_ret20 = {}
        for tkr in INDEX_TICKERS:
            s = _series(ohlcv, tkr)
            self._idx_ret20[tkr] = self._ret20_by_date(s)
        self._breadth = self._build_breadth(ohlcv)
        # precompute feature/affinity arrays at every SPY date (trailing, PIT).
        self._regime_cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _ret20_by_date(rows: list[dict[str, Any]]) -> dict[str, float]:
        out: dict[str, float] = {}
        closes = [float(b["Close"]) for b in rows]
        dates = [str(b["Date"])[:10] for b in rows]
        for i in range(len(rows)):
            if i >= RET_LOOKBACK and closes[i - RET_LOOKBACK] > 0:
                out[dates[i]] = closes[i] / closes[i - RET_LOOKBACK] - 1.0
        return out

    def _build_breadth(self, ohlcv: dict[str, Any]) -> dict[str, float]:
        """frac of non-index universe tickers with close > own 50d SMA, by date."""
        above: Counter[str] = Counter()
        total: Counter[str] = Counter()
        for ticker, bars in ohlcv.items():
            if ticker in INDEX_TICKERS:
                continue
            rows = _series(ohlcv, ticker)
            closes = [float(b["Close"]) for b in rows]
            dates = [str(b["Date"])[:10] for b in rows]
            run = 0.0
            for i in range(len(rows)):
                run += closes[i]
                if i >= SMA_SHORT:
                    run -= closes[i - SMA_SHORT]
                if i >= SMA_SHORT - 1:
                    sma = run / SMA_SHORT
                    total[dates[i]] += 1
                    if closes[i] > sma:
                        above[dates[i]] += 1
        return {d: above[d] / total[d] for d in total if total[d] > 0}

    def _features_at_idx(self, i: int) -> dict[str, Any] | None:
        if i < MIN_BARS_FOR_REGIME:
            return None
        close = self.closes[i]
        n_long = min(SMA_LONG, i + 1)
        sma_long = sum(self.closes[i - n_long + 1 : i + 1]) / n_long
        n_short = min(SMA_SHORT, i + 1)
        sma_short = sum(self.closes[i - n_short + 1 : i + 1]) / n_short
        t = close / sma_long - 1.0 if sma_long > 0 else 0.0
        mom = close / self.closes[i - RET_LOOKBACK] - 1.0 if i >= RET_LOOKBACK and self.closes[i - RET_LOOKBACK] > 0 else 0.0
        hi_window = self.highs[max(0, i - HIGH_LOOKBACK + 1) : i + 1]
        hi = max(hi_window) if hi_window else close
        dd = close / hi - 1.0 if hi > 0 else 0.0  # <= 0
        rets = []
        for j in range(max(1, i - VOL_LOOKBACK + 1), i + 1):
            if self.closes[j - 1] > 0:
                rets.append(self.closes[j] / self.closes[j - 1] - 1.0)
        vol20 = statistics.pstdev(rets) if len(rets) > 1 else 0.0
        med_vols = []
        for k in range(max(VOL_LOOKBACK, i - VOL_MEDIAN_LOOKBACK + 1), i + 1):
            sub = []
            for j in range(k - VOL_LOOKBACK + 1, k + 1):
                if j >= 1 and self.closes[j - 1] > 0:
                    sub.append(self.closes[j] / self.closes[j - 1] - 1.0)
            if len(sub) > 1:
                med_vols.append(statistics.pstdev(sub))
        med_vol = statistics.median(med_vols) if med_vols else vol20
        vr = vol20 / med_vol if med_vol > 0 else 1.0
        date = self.dates[i]
        agree = [tkr for tkr in INDEX_TICKERS if self._idx_ret20.get(tkr, {}).get(date, 0.0) > 0]
        idx_agree = len(agree) / len(INDEX_TICKERS)
        breadth = self._breadth.get(date, 0.5)
        return {
            "spy_trend_vs_sma200": _round(t, 6),
            "spy_ret20": _round(mom, 6),
            "spy_drawdown_from_252d_high": _round(dd, 6),
            "spy_vol20": _round(vol20, 6),
            "spy_vol_ratio_vs_100d_median": _round(vr, 6),
            "index_ret20_agreement_frac": _round(idx_agree, 6),
            "universe_breadth_above_sma50": _round(breadth, 6),
        }

    @staticmethod
    def _classify_features(f: dict[str, Any]) -> dict[str, Any]:
        t = float(f["spy_trend_vs_sma200"])
        mom = float(f["spy_ret20"])
        dd = float(f["spy_drawdown_from_252d_high"])
        vr = float(f["spy_vol_ratio_vs_100d_median"])
        idx_agree = float(f["index_ret20_agreement_frac"])
        breadth = float(f["universe_breadth_above_sma50"])
        trend_feature = _sigmoid(10.0 * t + 6.0 * mom)
        bull = 0.5 * trend_feature + 0.3 * breadth + 0.2 * idx_agree
        stress = _sigmoid(14.0 * (-dd - DD_REF) + 2.5 * (vr - VOL_RATIO_REF))
        aff_off = stress
        aff_on = bull * (1.0 - stress)
        aff_chop = (1.0 - bull) * (1.0 - stress)
        s = aff_on + aff_chop + aff_off
        if s <= 0:
            p_on = p_chop = p_off = 1.0 / 3.0
        else:
            p_on, p_chop, p_off = aff_on / s, aff_chop / s, aff_off / s
        probs = {"risk_on_trend": p_on, "choppy_range": p_chop, "risk_off_stress": p_off}
        label = max(probs, key=probs.get)
        return {
            "regime_label": label,
            "p_risk_on_trend": _round(p_on, 6),
            "p_choppy_range": _round(p_chop, 6),
            "p_risk_off_stress": _round(p_off, 6),
            "risk_off_score": _round(p_off, 6),
            "bull_score": _round(bull, 6),
        }

    def classify(self, asof: str) -> dict[str, Any]:
        asof = str(asof)[:10]
        if asof in self._regime_cache:
            return self._regime_cache[asof]
        i = self._date_to_idx.get(asof)
        if i is None:
            # use the latest SPY date <= asof
            i = None
            for j, d in enumerate(self.dates):
                if d <= asof:
                    i = j
                else:
                    break
        if i is None:
            out = {"regime_label": "unknown", "coverage": "no_index_bar_on_or_before_asof"}
            self._regime_cache[asof] = out
            return out
        f = self._features_at_idx(i)
        if f is None:
            out = {"regime_label": "unknown", "coverage": "insufficient_lookback"}
            self._regime_cache[asof] = out
            return out
        out = {**self._classify_features(f), "features": f, "coverage": "ok", "asof_index_date": self.dates[i]}
        self._regime_cache[asof] = out
        return out


# --------------------------------------------------------------------------- #
# Trade loading
# --------------------------------------------------------------------------- #
def _load_window_trades(artifact: Path, pnl_keys: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(artifact.read_text(encoding="utf-8"))
    by_window = data.get("target_trades_by_window") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for label in WINDOWS:
        rows = by_window.get(label) or []
        clean: list[dict[str, Any]] = []
        for row in rows:
            signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
            pnl = None
            for key in pnl_keys:
                v = row.get(key)
                if v is not None:
                    try:
                        pnl = float(v)
                        break
                    except (TypeError, ValueError):
                        continue
            if not signal_date or pnl is None:
                continue
            clean.append({"signal_date": signal_date, "ticker": row.get("ticker"), "pnl": pnl})
        out[label] = clean
    return out


def _load_forward_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state_path in sorted(PAPER_SLEEVES_DIR.glob("*/state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        sleeve = state.get("sleeve") or state_path.parent.name
        closed = state.get("closed_positions") or state.get("closed_outcomes") or []
        for row in closed:
            entry = str(row.get("entry_date") or row.get("signal_date") or "")[:10]
            rv = row.get("replacement_value_vs_spy_usd")
            if not entry:
                continue
            rows.append(
                {
                    "sleeve": sleeve,
                    "entry_date": entry,
                    "ticker": row.get("ticker"),
                    "replacement_value_vs_spy_usd": rv,
                    "pnl": row.get("pnl"),
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# Attribution
# --------------------------------------------------------------------------- #
def _attribute(trades_by_window: dict[str, list[dict[str, Any]]], models: dict[str, RegimeModel]) -> dict[str, Any]:
    per_regime_all: dict[str, list[float]] = defaultdict(list)
    per_regime_by_window: dict[str, dict[str, list[float]]] = {label: defaultdict(list) for label in WINDOWS}
    risk_off_score_pnl: list[tuple[float, float]] = []
    unknown = 0
    total = 0
    for label, trades in trades_by_window.items():
        model = models[label]
        for tr in trades:
            total += 1
            regime = model.classify(tr["signal_date"])
            rl = regime.get("regime_label", "unknown")
            if rl == "unknown":
                unknown += 1
                continue
            per_regime_all[rl].append(tr["pnl"])
            per_regime_by_window[label][rl].append(tr["pnl"])
            if regime.get("risk_off_score") is not None:
                risk_off_score_pnl.append((float(regime["risk_off_score"]), tr["pnl"]))

    def _summ(pnls: list[float]) -> dict[str, Any]:
        if not pnls:
            return {"count": 0, "total_pnl": 0.0, "mean_pnl": None, "win_rate": None}
        wins = sum(1 for p in pnls if p > 0)
        return {
            "count": len(pnls),
            "total_pnl": _round(sum(pnls), 2),
            "mean_pnl": _round(sum(pnls) / len(pnls), 2),
            "win_rate": _round(wins / len(pnls), 4),
        }

    overall = {rl: _summ(per_regime_all.get(rl, [])) for rl in REGIME_LABELS}
    by_window = {
        label: {rl: _summ(per_regime_by_window[label].get(rl, [])) for rl in REGIME_LABELS}
        for label in WINDOWS
    }
    # risk_off_score terciles
    terciles = {"low": [], "mid": [], "high": []}
    if risk_off_score_pnl:
        scores = sorted(s for s, _ in risk_off_score_pnl)
        n = len(scores)
        q1 = scores[n // 3]
        q2 = scores[(2 * n) // 3]
        for s, p in risk_off_score_pnl:
            if s <= q1:
                terciles["low"].append(p)
            elif s <= q2:
                terciles["mid"].append(p)
            else:
                terciles["high"].append(p)
    tercile_summary = {k: _summ(v) for k, v in terciles.items()}
    # separation: spread in mean_pnl across regimes that have >= 5 trades.
    means = [overall[rl]["mean_pnl"] for rl in REGIME_LABELS if overall[rl]["count"] >= 5 and overall[rl]["mean_pnl"] is not None]
    separation = _round(max(means) - min(means), 2) if len(means) >= 2 else None
    # Spearman rank corr between risk_off_score and pnl.
    spearman = _spearman([s for s, _ in risk_off_score_pnl], [p for _, p in risk_off_score_pnl])
    return {
        "total_trades": total,
        "unknown_regime_trades": unknown,
        "overall_by_regime": overall,
        "by_window_by_regime": by_window,
        "risk_off_score_tercile_summary": tercile_summary,
        "mean_pnl_separation_across_regimes_usd": separation,
        "spearman_risk_off_score_vs_pnl": spearman,
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 8:
        return None

    def _ranks(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda k: vals[k])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if dx == 0 or dy == 0:
        return None
    return _round(num / (dx * dy), 4)


def _attribute_forward(rows: list[dict[str, Any]], models: dict[str, RegimeModel]) -> dict[str, Any]:
    # forward rows can post-date all snapshots; use whichever window model covers
    # the entry date, else the latest (late_strong) model as best available.
    by_regime: dict[str, list[float]] = defaultdict(list)
    tagged = 0
    for row in rows:
        entry = row["entry_date"]
        regime = None
        for label, (start, end, _path) in WINDOWS.items():
            if start <= entry <= end:
                regime = models[label].classify(entry)
                break
        if regime is None:
            regime = models["late_strong"].classify(entry)
        rl = regime.get("regime_label", "unknown")
        rv = row.get("replacement_value_vs_spy_usd")
        if rl != "unknown" and rv is not None:
            try:
                by_regime[rl].append(float(rv))
                tagged += 1
            except (TypeError, ValueError):
                pass

    def _summ(vals: list[float]) -> dict[str, Any]:
        if not vals:
            return {"count": 0, "mean_replacement_value_vs_spy_usd": None}
        return {"count": len(vals), "mean_replacement_value_vs_spy_usd": _round(sum(vals) / len(vals), 2)}

    return {
        "note": "OBSERVE-ONLY. Only %d forward rows had a usable regime tag; far too few for inference." % tagged,
        "forward_rows_total": len(rows),
        "forward_rows_tagged": tagged,
        "by_regime_replacement_value_vs_spy": {rl: _summ(by_regime.get(rl, [])) for rl in REGIME_LABELS},
    }


# --------------------------------------------------------------------------- #
# Build + persist
# --------------------------------------------------------------------------- #
def _regime_day_distribution(models: dict[str, RegimeModel]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_window: dict[str, dict[str, int]] = {}
    for label, (start, end, _path) in WINDOWS.items():
        model = models[label]
        wc: Counter[str] = Counter()
        for d in model.dates:
            if start <= d <= end:
                wc[model.classify(d).get("regime_label", "unknown")] += 1
        by_window[label] = dict(wc)
        counts.update(wc)
    return {"all_windows": dict(counts), "by_window": by_window}


def _build_payload() -> dict[str, Any]:
    models: dict[str, RegimeModel] = {}
    for label, (_s, _e, path) in WINDOWS.items():
        ohlcv = json.loads((REPO_ROOT / path).read_text(encoding="utf-8")).get("ohlcv") or {}
        models[label] = RegimeModel(ohlcv)

    fgrs = _load_window_trades(FGRS_SOURCE_ARTIFACT, ("pnl_without_low_liability_support", "pnl"))
    deferred = _load_window_trades(DEFERRED_REVENUE_ARTIFACT, ("pnl", "paper_pnl"))
    forward_rows = _load_forward_rows()

    fgrs_attr = _attribute(fgrs, models)
    deferred_attr = _attribute(deferred, models)
    forward_attr = _attribute_forward(forward_rows, models)
    regime_days = _regime_day_distribution(models)

    findings = _findings(fgrs_attr, deferred_attr, regime_days)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "measurement_repair_pit_regime_classifier_and_attribution_surface_built",
        "accepted": False,
        "accepted_alpha": False,
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "pit_regime_state_classifier_diagnostic",
        "rule_version": RULE_VERSION,
        "hypothesis": (
            "A mechanical PIT regime classifier plus conditional attribution of "
            "accepted-sleeve replay trades is the measurement surface needed to "
            "test whether a strategy's edge is regime-conditional without "
            "re-slicing the three canonical windows."
        ),
        "leakage_discipline": (
            "Regime constants (200d MA, 252d high, ~8% drawdown reference, ~1.3x "
            "vol-elevation reference, 50d-SMA breadth) are conventional market "
            "structure thresholds set by hand, NOT optimized against the trade "
            "PnL attributed below. The classifier reads only index OHLCV and "
            "breadth observable on or before the as-of date."
        ),
        "regime_classifier": {
            "rule_version": RULE_VERSION,
            "labels": list(REGIME_LABELS),
            "outputs": ["p_risk_on_trend", "p_choppy_range", "p_risk_off_stress", "risk_off_score", "bull_score"],
            "inputs": ["SPY/QQQ/IWM OHLCV", "universe breadth above 50d SMA"],
            "constants": {
                "sma_long": SMA_LONG,
                "sma_short": SMA_SHORT,
                "high_lookback": HIGH_LOOKBACK,
                "ret_lookback": RET_LOOKBACK,
                "vol_lookback": VOL_LOOKBACK,
                "vol_median_lookback": VOL_MEDIAN_LOOKBACK,
                "drawdown_ref": DD_REF,
                "vol_ratio_ref": VOL_RATIO_REF,
                "min_bars_for_regime": MIN_BARS_FOR_REGIME,
            },
        },
        "regime_day_distribution": regime_days,
        "attribution": {
            "fundamental_growth_rs_low_liability": {
                "trade_source": _repo_rel(FGRS_SOURCE_ARTIFACT),
                **fgrs_attr,
            },
            "deferred_revenue_demand_acceleration_exp017": {
                "trade_source": _repo_rel(DEFERRED_REVENUE_ARTIFACT),
                **deferred_attr,
            },
            "forward_paper_sleeve_rows_observe_only": forward_attr,
        },
        "findings": findings,
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
            "uses_llm": False,
            "parity_note": (
                "Diagnostic field-building only. Promoting this regime classifier "
                "to any execution role (per-strategy gate or portfolio-level "
                "capital tilt) requires a separate shared default-off helper, a "
                "daily replayable regime artifact, a parity test, and Gate 1-4 "
                "plus forward state-tagged replacement-value rows."
            ),
        },
        "next_evidence_needed": (
            "If a sleeve shows stable cross-window regime separation here, the "
            "next step is a shared default-off regime artifact + portfolio-level "
            "soft capital tilt (monotonic in risk_off_score, few parameters), "
            "validated on forward state-tagged replacement-value rows, NOT a hard "
            "per-window on/off gate. exp-20260614-010 already showed a hard "
            "frozen-window breadth filter regresses all three windows."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _findings(fgrs_attr: dict[str, Any], deferred_attr: dict[str, Any], regime_days: dict[str, Any]) -> dict[str, Any]:
    return {
        "regime_classifier_built": True,
        "fgrs_mean_pnl_separation_usd": fgrs_attr["mean_pnl_separation_across_regimes_usd"],
        "fgrs_spearman_risk_off_vs_pnl": fgrs_attr["spearman_risk_off_score_vs_pnl"],
        "deferred_mean_pnl_separation_usd": deferred_attr["mean_pnl_separation_across_regimes_usd"],
        "deferred_spearman_risk_off_vs_pnl": deferred_attr["spearman_risk_off_score_vs_pnl"],
        "regime_day_counts_all_windows": regime_days["all_windows"],
        "interpretation": (
            "Read overall_by_regime and by_window_by_regime: a sleeve is a regime "
            "tilt candidate only if mean PnL ordering across regimes is consistent "
            "in sign across all three windows AND the per-regime trade count is "
            "non-trivial. A single-window separation is not evidence."
        ),
    }


def _build_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} PIT Regime-State Classifier + Attribution",
        "",
        f"Status: `{payload['status']}`  Lane: `measurement_repair`",
        "",
        "## What was built",
        "",
        "A mechanical, point-in-time regime classifier (probability over "
        "`risk_on_trend / choppy_range / risk_off_stress`, plus `risk_off_score` "
        "and `bull_score`) from free index OHLCV + breadth, and read-only "
        "conditional attribution of accepted-sleeve replay trades by entry-day "
        "regime. Zero execution change.",
        "",
        "## Regime day distribution (all windows)",
        "",
        "```",
        json.dumps(payload["regime_day_distribution"]["all_windows"], indent=2, sort_keys=True),
        "```",
        "",
        "## Fundamental Growth + RS — overall by regime",
        "",
        "| regime | trades | total PnL | mean PnL | win rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for rl in REGIME_LABELS:
        s = payload["attribution"]["fundamental_growth_rs_low_liability"]["overall_by_regime"][rl]
        lines.append(f"| {rl} | {s['count']} | {s['total_pnl']} | {s['mean_pnl']} | {s['win_rate']} |")
    lines += [
        "",
        f"- mean-PnL separation across regimes: `{payload['findings']['fgrs_mean_pnl_separation_usd']}` USD",
        f"- Spearman(risk_off_score, PnL): `{payload['findings']['fgrs_spearman_risk_off_vs_pnl']}`",
        "",
        "## Deferred-revenue (exp-20260615-017) — overall by regime",
        "",
        "| regime | trades | total PnL | mean PnL | win rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for rl in REGIME_LABELS:
        s = payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]["overall_by_regime"][rl]
        lines.append(f"| {rl} | {s['count']} | {s['total_pnl']} | {s['mean_pnl']} | {s['win_rate']} |")
    lines += [
        "",
        f"- mean-PnL separation across regimes: `{payload['findings']['deferred_mean_pnl_separation_usd']}` USD",
        f"- Spearman(risk_off_score, PnL): `{payload['findings']['deferred_spearman_risk_off_vs_pnl']}`",
        "",
        "## Leakage discipline",
        "",
        payload["leakage_discipline"],
        "",
        "## Next evidence",
        "",
        payload["next_evidence_needed"],
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "findings": payload["findings"],
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    experiment_registry.append_log_entry(EXPERIMENT_LOG, _build_log_record(payload))
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "findings": payload["findings"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "summary": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "findings": payload["findings"],
        "fgrs_overall": payload["attribution"]["fundamental_growth_rs_low_liability"]["overall_by_regime"],
        "deferred_overall": payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]["overall_by_regime"],
        "regime_days": payload["regime_day_distribution"]["all_windows"],
    }, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
