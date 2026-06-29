"""exp-20260628-015: full-population breakout-without-2x-volume precursor sleeve.

Default-off, read-only forward instrumentation. Detects EVERY production-visible
``above_200ma & breakout_20d & not volume_spike`` precursor event across the
universe -- crucially including events that never become a real ``trend_long``
entry -- and records each with its forward next-open 10d/20d replacement value
and a point-in-time entry-regime bucket.

Why full-population: exp-20260627-006 found 24/39 ACTUAL trend_long trades had a
production-visible breakout-without-2x-volume precursor 1-5 sessions earlier with
a +1.92% median entry-price advantage and +2.46% 10d delta. That statistic is
SELECTION-CONDITIONED on breakouts that eventually became real trades; it cannot
tell us the base rate or false-positive drag of the precursor signal itself. This
sleeve logs the whole precursor population so the entry-latency lead can be
re-tested OUT OF SAMPLE on a de-biased sample before any volume-threshold or
entry-timing change. It also records, for each event, whether a real trend_long
entry followed (the survivorship subset), so the biased and de-biased samples can
be compared directly.

Parity: the precursor condition reproduces ``quant.feature_layer``
``compute_trend_features`` EXACTLY -- 200-bar MA of close, prior-20-day high
excluding today, 20-day average volume excluding today, 2.0x spike threshold --
minus the ``volume_spike`` confirmation. The forward-outcome fill convention
mirrors ``quant.forward_replacement_value``: next-open entry with buy-side entry
slippage, horizon-close exit with sell-side slippage, ``ROUND_TRIP_COST_PCT``
subtracted. This module never creates, ranks, sizes, exits, or orders a position;
``trade_enabled`` is always False and no live/default behavior changes.

late_strong NOTE: exp-20260627-006 showed the late_strong entry-regime bucket has
a NEGATIVE 20d delta (-1.53%). The regime label is recorded on every event so the
loss bucket can be isolated; this sleeve does NOT exclude or tilt on it -- that is
a downstream out-of-sample test, gated on forward-row accrual, not a behavior of
the instrumentation.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Iterable

try:
    from constants import ROUND_TRIP_COST_PCT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from regime_chop_state import (
        RULE_VERSION as REGIME_CHOP_RULE_VERSION,
        regime_chop_from_spy_universe,
    )
except ImportError:  # pragma: no cover - package-style import fallback
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.fill_model import (
        SLIPPAGE_BPS_ENTRY,
        SLIPPAGE_BPS_TARGET,
        apply_slippage,
    )
    from quant.regime_chop_state import (
        RULE_VERSION as REGIME_CHOP_RULE_VERSION,
        regime_chop_from_spy_universe,
    )


RULE_VERSION = "breakout_precursor_paper_sleeve_v1"

# Parity constants -- must mirror feature_layer.compute_trend_features.
MA_200_PERIOD = 200
BREAKOUT_LOOKBACK = 20
VOL_AVG_PERIOD = 20
VOL_SPIKE_MULT = 2.0
# Name-level extension context (mirrors forward_replacement_value exhaustion tag).
ATR_PERIOD = 14
MA_20_PERIOD = 20
HIGH_252_LOOKBACK = 252
# Forward replacement horizons (trading sessions held after the next-open entry).
FORWARD_HORIZONS = (10, 20)
# An event needs at least one full 200-bar MA window of strictly-prior history.
MIN_PRIOR_BARS = MA_200_PERIOD
# How close, in sessions, a real trend_long entry must follow the precursor to be
# counted as the survivorship subset (exp-20260627-006 used a 1-5 session window).
ACTUAL_ENTRY_MATCH_MAX_GAP_SESSIONS = 5

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "replay_only": False,
    "default_off_attribution_only": True,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}


def _f(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_bars(rows: Iterable[Any]) -> list[dict[str, Any]]:
    """Coerce raw OHLCV rows into ascending, validated bar dicts.

    Accepts dicts (case-insensitive ``date/open/high/low/close/volume`` keys) or
    positional ``(date, open, high, low, close, volume)`` tuples. Rows missing a
    date or close are dropped; missing volume is kept as ``None`` (such a bar can
    never satisfy the volume-spike test, so it cannot be falsely emitted, but it
    also blocks a precursor that needs ``avg_vol_20``).
    """
    out: list[dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, dict):
            lower = {str(k).lower(): v for k, v in row.items()}
            date = lower.get("date") or lower.get("d")
            o, h, l, c, v = (
                lower.get("open"),
                lower.get("high"),
                lower.get("low"),
                lower.get("close"),
                lower.get("volume"),
            )
        else:
            seq = list(row)
            seq += [None] * (6 - len(seq))
            date, o, h, l, c, v = seq[:6]
        date = str(date)[:10] if date is not None else ""
        close = _f(c)
        if not date or close is None:
            continue
        high = _f(h)
        low = _f(l)
        out.append(
            {
                "date": date,
                "open": _f(o),
                "high": high if high is not None else close,
                "low": low if low is not None else close,
                "close": close,
                "volume": _f(v),
            }
        )
    out.sort(key=lambda b: b["date"])
    return out


def _precursor_at(bars: list[dict[str, Any]], i: int) -> dict[str, Any] | None:
    """Evaluate the precursor condition at signal index ``i`` using only bars
    dated on/before ``i`` (PIT). Returns the feature snapshot, or ``None`` when
    there is insufficient strictly-prior history.
    """
    if i < MIN_PRIOR_BARS:
        return None
    today = bars[i]
    close = today["close"]

    prev20 = bars[i - BREAKOUT_LOOKBACK:i]
    if len(prev20) < BREAKOUT_LOOKBACK:
        return None
    high_20d = max(b["high"] for b in prev20)
    breakout_20d = close > high_20d

    closes_200 = [b["close"] for b in bars[i - (MA_200_PERIOD - 1):i + 1]]
    if len(closes_200) < MA_200_PERIOD:
        return None
    ma200 = mean(closes_200)
    above_200ma = close > ma200

    vols_20 = [b["volume"] for b in prev20]
    if any(v is None for v in vols_20) or today["volume"] is None:
        return None
    avg_vol_20 = mean(vols_20)
    if avg_vol_20 <= 0:
        return None
    volume_spike_ratio = today["volume"] / avg_vol_20
    volume_spike = volume_spike_ratio > VOL_SPIKE_MULT

    is_precursor = bool(above_200ma and breakout_20d and not volume_spike)
    if not is_precursor:
        return None

    # Name-level extension context (same construction as the exp-022 tag).
    ma20 = mean(b["close"] for b in bars[i - (MA_20_PERIOD - 1):i + 1])
    trs = []
    for j in range(max(1, i - ATR_PERIOD + 1), i + 1):
        h, l, pc = bars[j]["high"], bars[j]["low"], bars[j - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = mean(trs) if trs else None
    high252 = max(b["high"] for b in bars[max(0, i - HIGH_252_LOOKBACK + 1):i + 1])

    momentum_10d_pct = None
    if i >= 10:
        c10 = bars[i - 10]["close"]
        if c10:
            momentum_10d_pct = round(close / c10 - 1.0, 6)

    return {
        "close": round(close, 4),
        "high_20d": round(high_20d, 4),
        "ma200": round(ma200, 4),
        "volume_spike_ratio": round(volume_spike_ratio, 4),
        "extension_atr_mult": (
            round((close - ma20) / atr, 6) if atr and atr > 0 else None
        ),
        "pct_from_20ma": round(close / ma20 - 1.0, 6) if ma20 else None,
        "pct_from_252w_high": (
            round(close / high252 - 1.0, 6) if high252 else None
        ),
        "momentum_10d_pct": momentum_10d_pct,
    }


def _forward_outcome(bars: list[dict[str, Any]], i: int) -> dict[str, Any]:
    """Next-open entry on the session after ``i``; horizon-close exits.

    Returns settlement status and, for each fully-elapsed horizon, the
    cost-and-slippage-adjusted forward net return plus the forward MAE. A horizon
    whose exit bar does not yet exist is recorded as unsettled -- the source of
    the calendar-bound forward-row accrual.
    """
    entry_idx = i + 1
    out: dict[str, Any] = {"entry_idx": entry_idx, "horizons": {}}
    if entry_idx >= len(bars):
        out["status"] = "unsettled_no_entry_bar"
        out["entry_date"] = None
        return out
    entry_bar = bars[entry_idx]
    entry_open = entry_bar["open"]
    if entry_open is None or entry_open <= 0:
        out["status"] = "missing_entry_open"
        out["entry_date"] = entry_bar["date"]
        return out
    entry_fill = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
    out["entry_date"] = entry_bar["date"]
    out["entry_fill"] = round(entry_fill, 4)

    any_settled = False
    for horizon in FORWARD_HORIZONS:
        exit_idx = entry_idx + horizon
        if exit_idx >= len(bars):
            out["horizons"][str(horizon)] = {"status": "unsettled"}
            continue
        exit_bar = bars[exit_idx]
        exit_fill = apply_slippage(exit_bar["close"], SLIPPAGE_BPS_TARGET, "sell")
        net_return = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
        lows = [b["low"] for b in bars[entry_idx:exit_idx + 1] if b["low"] is not None]
        mae = (min(lows) / entry_fill - 1.0) if lows else None
        out["horizons"][str(horizon)] = {
            "status": "settled",
            "exit_date": exit_bar["date"],
            "exit_fill": round(exit_fill, 4),
            "forward_net_return_pct": round(net_return * 100.0, 4),
            "forward_mae_pct": round(mae * 100.0, 4) if mae is not None else None,
        }
        any_settled = True

    out["status"] = "settled" if any_settled else "unsettled_horizon"
    return out


def _regime_label_at(regime_spy_bars, signal_date):
    if not regime_spy_bars:
        return {"regime_label": "unknown", "coverage": "missing_spy_bars"}
    return regime_chop_from_spy_universe(regime_spy_bars, signal_date)


def scan_ticker_precursors(
    ticker: str,
    bars: Iterable[Any],
    *,
    regime_spy_bars=None,
    actual_entry_dates: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Emit one event record for every breakout-without-2x-volume precursor on
    ``ticker``. ``actual_entry_dates`` (the name's real trend_long entry dates)
    marks the survivorship subset on each event.
    """
    norm = normalize_bars(bars)
    actual = sorted({str(d)[:10] for d in (actual_entry_dates or []) if d})
    events: list[dict[str, Any]] = []
    for i in range(MIN_PRIOR_BARS, len(norm)):
        snapshot = _precursor_at(norm, i)
        if snapshot is None:
            continue
        signal_date = norm[i]["date"]
        outcome = _forward_outcome(norm, i)
        regime = _regime_label_at(regime_spy_bars, signal_date)

        matched_entry = None
        match_gap = None
        for entry_date in actual:
            if entry_date < signal_date:
                continue
            # session gap by index within this name's own bar series.
            gap = sum(1 for b in norm[i + 1:] if b["date"] <= entry_date)
            if entry_date >= signal_date and gap <= ACTUAL_ENTRY_MATCH_MAX_GAP_SESSIONS:
                matched_entry = entry_date
                match_gap = gap
                break

        events.append(
            {
                "rule_version": RULE_VERSION,
                "ticker": str(ticker).upper(),
                "signal_date": signal_date,
                "precursor": snapshot,
                "forward": outcome,
                "entry_regime_label": regime.get("regime_label"),
                "entry_regime_status": regime.get("coverage"),
                "entry_regime_rule_version": REGIME_CHOP_RULE_VERSION,
                "entry_regime_p_risk_on_trend": regime.get("p_risk_on_trend"),
                "entry_regime_p_choppy_range": regime.get("p_choppy_range"),
                "entry_regime_p_risk_off_stress": regime.get("p_risk_off_stress"),
                "became_trend_long_entry": matched_entry is not None,
                "matched_actual_entry_date": matched_entry,
                "matched_actual_entry_gap_sessions": match_gap,
            }
        )
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Population vs survivorship-subset forward summary, split by entry regime.

    This is the de-biasing lens: it compares the forward return of the full
    precursor population against the ``became_trend_long_entry`` subset that
    exp-20260627-006 measured, so a base-rate collapse is visible at a glance.
    """

    def _bucket(rows, horizon):
        vals = [
            r["forward"]["horizons"].get(str(horizon), {}).get("forward_net_return_pct")
            for r in rows
        ]
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"n": 0, "mean": None, "median": None}
        vals.sort()
        n = len(vals)
        med = (
            vals[n // 2]
            if n % 2
            else round((vals[n // 2 - 1] + vals[n // 2]) / 2.0, 4)
        )
        return {"n": n, "mean": round(sum(vals) / n, 4), "median": med}

    settled = [e for e in events if e["forward"].get("status") == "settled"]
    subset = [e for e in settled if e["became_trend_long_entry"]]
    by_regime: dict[str, int] = {}
    for e in events:
        label = str(e.get("entry_regime_label") or "unknown")
        by_regime[label] = by_regime.get(label, 0) + 1

    out: dict[str, Any] = {
        "events_total": len(events),
        "events_settled": len(settled),
        "events_became_actual_entry": len(subset),
        "by_entry_regime_label": by_regime,
        "forward_full_population": {},
        "forward_actual_entry_subset": {},
    }
    for horizon in FORWARD_HORIZONS:
        out["forward_full_population"][f"{horizon}d"] = _bucket(settled, horizon)
        out["forward_actual_entry_subset"][f"{horizon}d"] = _bucket(subset, horizon)
    return out
