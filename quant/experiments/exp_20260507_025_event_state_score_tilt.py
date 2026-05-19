"""exp-20260507-025 event/state-score allocation replay.

Alpha search. The default-off event bundle remains the strongest replay-positive
non-core surface, but recent source pruning, core-pressure, pre-entry momentum,
price-structure, and event/state shared-cap variants did not clear the marginal
gate. This experiment changes one causal variable inside the frozen event
bundle: whether an event trade should receive more or less notional based on the
same point-in-time state-surface score that has been validated as a separate
paper sleeve.

No core entries, ranking, sizing, exits, universe membership, event sources,
event thresholds, holding periods, LLM/news behavior, or production orders are
changed.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _aggregate_delta,
    _combined_metrics,
    _core_metrics,
    _gate4,
    _load_core_result,
    _load_event_trades,
)
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    INITIAL_CAPITAL,
    _close_on_or_before,
    _trading_days,
)


EXP_ID = "exp-20260507-025"
STEM = "event_state_score_tilt"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INDEX_TICKERS = {"SPY", "QQQ", "IWM"}

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Current frozen event bundle; 1.0x notional for all event trades.",
                "positive_score_scalar": 1.0,
                "nonpositive_score_scalar": 1.0,
            },
        ),
        (
            "state_score_pos_125_075",
            {
                "description": "Tilt notional toward events whose ticker has positive PIT state-surface score before entry.",
                "positive_score_scalar": 1.25,
                "nonpositive_score_scalar": 0.75,
            },
        ),
        (
            "state_score_pos_150_050",
            {
                "description": "Stronger version of the same positive state-score tilt.",
                "positive_score_scalar": 1.50,
                "nonpositive_score_scalar": 0.50,
            },
        ),
        (
            "state_score_pos_only",
            {
                "description": "Trade only event rows with positive PIT state-surface score.",
                "positive_score_scalar": 1.0,
                "nonpositive_score_scalar": 0.0,
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> Any:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return round(parsed, digits)


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected snapshot shape: {snapshot_path}")
    return {
        str(ticker).upper(): sorted(rows, key=lambda row: str(row.get("Date") or ""))
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _close(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("Close"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _volume(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("Volume"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _rows_until(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("Date") or "") <= date_str]


def _ret(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) <= lookback:
        return None
    now = _close(hist[-1])
    then = _close(hist[-lookback - 1])
    if not now or not then:
        return None
    return now / then - 1.0


def _pct_from_sma(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    closes = [_close(row) for row in hist[-lookback:]]
    closes = [value for value in closes if value]
    if not now or len(closes) < lookback:
        return None
    avg = sum(closes) / len(closes)
    return now / avg - 1.0 if avg else None


def _volume_ratio(rows: list[dict[str, Any]], date_str: str, lookback: int = 20) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback + 1:
        return None
    now = _volume(hist[-1])
    vols = [_volume(row) for row in hist[-lookback - 1 : -1]]
    vols = [value for value in vols if value]
    if not now or len(vols) < lookback:
        return None
    avg = sum(vols) / len(vols)
    return now / avg if avg else None


def _near_high(rows: list[dict[str, Any]], date_str: str, lookback: int = 60) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    highs = []
    for row in hist[-lookback:]:
        try:
            highs.append(float(row.get("High")))
        except (TypeError, ValueError):
            continue
    if not now or not highs:
        return None
    high = max(highs)
    return now / high if high else None


def _breadth(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    lookback: int,
) -> float | None:
    seen = 0
    above = 0
    for ticker in universe:
        pct = _pct_from_sma(ohlcv.get(ticker.upper()) or [], date_str, lookback)
        if pct is None:
            continue
        seen += 1
        above += int(pct > 0)
    return above / seen if seen else None


def _sector_dispersion(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> float | None:
    values = []
    for ticker in universe:
        value = _ret(ohlcv.get(ticker.upper()) or [], date_str, 20)
        if value is not None:
            values.append(value)
    if len(values) < 2:
        return None
    return statistics.pstdev(values)


def _state_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> dict[str, Any]:
    spy_ret20 = _ret(ohlcv.get("SPY", []), date_str, 20)
    qqq_ret20 = _ret(ohlcv.get("QQQ", []), date_str, 20)
    iwm_ret20 = _ret(ohlcv.get("IWM", []), date_str, 20)
    spy_pct200 = _pct_from_sma(ohlcv.get("SPY", []), date_str, 200)
    qqq_pct200 = _pct_from_sma(ohlcv.get("QQQ", []), date_str, 200)
    breadth50 = _breadth(ohlcv, universe, date_str, 50)
    dispersion20 = _sector_dispersion(ohlcv, universe, date_str)

    pct_values = [value for value in (spy_pct200, qqq_pct200) if value is not None]
    min_index_pct200 = min(pct_values) if pct_values else None
    qqq_minus_iwm = qqq_ret20 - iwm_ret20 if qqq_ret20 is not None and iwm_ret20 is not None else None
    iwm_minus_spy = iwm_ret20 - spy_ret20 if iwm_ret20 is not None and spy_ret20 is not None else None

    if min_index_pct200 is not None and min_index_pct200 < 0:
        state_bucket = "weak_index"
    elif qqq_minus_iwm is not None and qqq_minus_iwm > 0.04:
        state_bucket = "narrow_cap_weight_leadership"
    elif iwm_minus_spy is not None and iwm_minus_spy > 0.02:
        state_bucket = "broad_rotation"
    else:
        state_bucket = "balanced_risk_on"

    if breadth50 is None:
        breadth_bucket = "unknown"
    elif breadth50 >= 0.65:
        breadth_bucket = "broad_breadth"
    elif breadth50 <= 0.45:
        breadth_bucket = "thin_breadth"
    else:
        breadth_bucket = "mixed_breadth"

    if dispersion20 is None:
        dispersion_bucket = "unknown"
    elif dispersion20 >= 0.08:
        dispersion_bucket = "high_sector_dispersion"
    elif dispersion20 <= 0.035:
        dispersion_bucket = "low_sector_dispersion"
    else:
        dispersion_bucket = "mid_sector_dispersion"

    return {
        "state_bucket": state_bucket,
        "breadth_bucket": breadth_bucket,
        "dispersion_bucket": dispersion_bucket,
        "spy_ret20": _round(spy_ret20, 6),
        "qqq_ret20": _round(qqq_ret20, 6),
        "iwm_ret20": _round(iwm_ret20, 6),
        "qqq_minus_iwm_ret20": _round(qqq_minus_iwm, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "min_index_pct_from_200sma": _round(min_index_pct200, 6),
        "universe_breadth_above_50sma": _round(breadth50, 6),
        "sector_ret20_dispersion": _round(dispersion20, 6),
    }


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    clean = [value for value in values.values() if value is not None]
    if len(clean) < 2:
        return {key: 0.0 for key in values}
    mean = statistics.mean(clean)
    stdev = statistics.pstdev(clean) or 1.0
    return {key: (value - mean) / stdev for key, value in values.items()}


def _score_candidates_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    features: dict[str, dict[str, float]] = {}
    for ticker in universe:
        rows = ohlcv.get(ticker.upper()) or []
        if date_str not in {str(row.get("Date") or "") for row in rows}:
            continue
        ret20 = _ret(rows, date_str, 20)
        ret60 = _ret(rows, date_str, 60)
        ret5 = _ret(rows, date_str, 5)
        near_high = _near_high(rows, date_str, 60)
        vol_ratio = _volume_ratio(rows, date_str, 20)
        spy_ret20 = float(state.get("spy_ret20") or 0.0)
        if None in (ret20, ret60, ret5, near_high, vol_ratio):
            continue
        features[ticker.upper()] = {
            "ret20_excess_spy": float(ret20) - spy_ret20,
            "ret60": float(ret60),
            "ret5": float(ret5),
            "near_high_60": float(near_high),
            "volume_ratio_20": float(vol_ratio),
        }
    if not features:
        return []

    z_ret20 = _zscore_map({ticker: row["ret20_excess_spy"] for ticker, row in features.items()})
    z_ret60 = _zscore_map({ticker: row["ret60"] for ticker, row in features.items()})
    z_pause = _zscore_map({ticker: -abs(row["ret5"]) for ticker, row in features.items()})
    z_high = _zscore_map({ticker: row["near_high_60"] for ticker, row in features.items()})
    z_volume = _zscore_map({ticker: row["volume_ratio_20"] for ticker, row in features.items()})

    state_bucket = str(state.get("state_bucket") or "")
    breadth_bucket = str(state.get("breadth_bucket") or "")
    dispersion_bucket = str(state.get("dispersion_bucket") or "")
    candidates = []
    for ticker, values in features.items():
        if state_bucket == "broad_rotation":
            surface = "rotation_breakout_leadership"
            score = (
                0.45 * z_ret20[ticker]
                + 0.25 * z_high[ticker]
                + 0.20 * z_volume[ticker]
                + 0.10 * z_ret60[ticker]
            )
        elif breadth_bucket == "broad_breadth":
            surface = "broad_breadth_trend_persistence"
            score = (
                0.40 * z_ret60[ticker]
                + 0.25 * z_ret20[ticker]
                + 0.20 * z_pause[ticker]
                + 0.15 * z_high[ticker]
            )
        elif dispersion_bucket == "mid_sector_dispersion":
            surface = "mid_dispersion_selective_leadership"
            score = (
                0.35 * z_ret20[ticker]
                + 0.30 * z_ret60[ticker]
                + 0.20 * z_high[ticker]
                + 0.15 * z_volume[ticker]
            )
        else:
            surface = "balanced_state_leadership"
            score = (
                0.35 * z_ret60[ticker]
                + 0.35 * z_ret20[ticker]
                + 0.20 * z_high[ticker]
                + 0.10 * z_pause[ticker]
            )
        candidates.append(
            {
                "date": date_str,
                "ticker": ticker,
                "surface": surface,
                "score": _round(score, 6),
                "state_bucket": state_bucket,
                "breadth_bucket": breadth_bucket,
                "dispersion_bucket": dispersion_bucket,
                "features": {key: _round(value, 6) for key, value in values.items()},
            }
        )
    return sorted(candidates, key=lambda row: (row["score"], row["ticker"]), reverse=True)


def _previous_spy_date(ohlcv: dict[str, list[dict[str, Any]]], entry_date: str) -> str | None:
    previous: str | None = None
    for row in ohlcv.get("SPY", []):
        date_str = str(row.get("Date") or "")[:10]
        if date_str and date_str < entry_date:
            previous = date_str
        if date_str >= entry_date:
            break
    return previous


def _event_decision_date(
    trade: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> str | None:
    entry_date = str(trade.get("entry_date") or "")[:10]
    raw = str(trade.get("usable_trade_date") or trade.get("reaction_date") or "")[:10]
    if raw and entry_date and raw < entry_date:
        return raw
    if entry_date:
        return _previous_spy_date(ohlcv, entry_date)
    return raw or None


def _state_confirmation(
    *,
    trade: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    cache: dict[str, tuple[dict[str, Any], list[dict[str, Any]], dict[str, tuple[int, dict[str, Any]]]]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    decision_date = _event_decision_date(trade, ohlcv)
    if not decision_date:
        return {
            "state_feature_available": False,
            "state_reason": "missing_decision_date",
            "state_score_positive": None,
        }

    if decision_date not in cache:
        state = _state_for_date(ohlcv, universe, decision_date)
        ranked = _score_candidates_for_date(ohlcv, universe, decision_date, state)
        by_ticker = {row["ticker"]: (idx + 1, row) for idx, row in enumerate(ranked)}
        cache[decision_date] = (state, ranked, by_ticker)
    state, ranked, by_ticker = cache[decision_date]
    found = by_ticker.get(ticker)
    if not found:
        return {
            "state_feature_available": False,
            "state_reason": "ticker_not_scored",
            "state_decision_date": decision_date,
            "state_bucket": state.get("state_bucket"),
            "breadth_bucket": state.get("breadth_bucket"),
            "state_score_positive": None,
        }
    rank, row = found
    rank_pct = rank / len(ranked) if ranked else None
    score = float(row.get("score") or 0.0)
    return {
        "state_feature_available": True,
        "state_reason": "scored",
        "state_decision_date": decision_date,
        "state_rank": rank,
        "state_rank_pct": _round(rank_pct, 6),
        "state_score": _round(score, 6),
        "state_score_positive": score > 0.0,
        "state_surface": row.get("surface"),
        "state_bucket": row.get("state_bucket"),
        "breadth_bucket": row.get("breadth_bucket"),
        "dispersion_bucket": row.get("dispersion_bucket"),
        "state_features": row.get("features"),
    }


def _enrich_event_trades(
    by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    enriched: dict[str, list[dict[str, Any]]] = OrderedDict()
    for label, trades in by_window.items():
        ohlcv = _load_ohlcv(REPO_ROOT / WINDOWS[label]["snapshot"])
        universe = sorted(ticker for ticker in ohlcv if ticker.upper() not in INDEX_TICKERS)
        cache: dict[
            str,
            tuple[dict[str, Any], list[dict[str, Any]], dict[str, tuple[int, dict[str, Any]]]],
        ] = {}
        rows = []
        for trade in trades:
            rows.append(
                {
                    **trade,
                    **_state_confirmation(
                        trade=trade,
                        ohlcv=ohlcv,
                        universe=universe,
                        cache=cache,
                    ),
                }
            )
        enriched[label] = rows
    return enriched


def _scalar_for_trade(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    if not trade.get("state_feature_available"):
        return 1.0
    if bool(trade.get("state_score_positive")):
        return float(variant["positive_score_scalar"])
    return float(variant["nonpositive_score_scalar"])


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any] | None:
    scalar = _scalar_for_trade(trade, variant)
    if scalar <= 0.0:
        return None
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_score_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _event_equity_curve(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    days = _trading_days(prices, start, end)
    entries_by_day: dict[str, list[dict[str, Any]]] = {}
    exits_by_day: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        entries_by_day.setdefault(str(trade["entry_date"]), []).append(trade)
        exits_by_day.setdefault(str(trade["exit_date"]), []).append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            cash -= float(trade.get("notional") or EVENT_NOTIONAL)
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        for trade in exiting:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is None:
                continue
            notional = float(trade.get("notional") or EVENT_NOTIONAL)
            cash += float(trade.get("shares") or 0.0) * close - notional * ROUND_TRIP_COST_PCT
        if exiting:
            exit_keys = {
                (trade["ticker"], trade["entry_date"], trade["exit_date"])
                for trade in exiting
            }
            active = [
                trade
                for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"]) not in exit_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += float(trade.get("shares") or 0.0) * close
        equity = cash + market_value
        curve.append(
            {
                "date": day,
                "event_equity": round(equity, 2),
                "event_pnl": round(equity - INITIAL_CAPITAL, 2),
                "active_event_positions": len(active),
            }
        )
    return curve


def _trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    by_source: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        if not trade.get("state_feature_available"):
            bucket = "missing"
        elif trade.get("state_score_positive"):
            bucket = "positive_score"
        else:
            bucket = "nonpositive_score"
        for key, target in ((source, by_source), (bucket, by_bucket)):
            row = target.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "total_pnl": 0.0, "total_notional": 0.0},
            )
            pnl = float(trade.get("pnl") or 0.0)
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["total_pnl"] += pnl
            row["total_notional"] += float(trade.get("notional") or EVENT_NOTIONAL)
    for target in (by_source, by_bucket):
        for row in target.values():
            count = int(row["trade_count"])
            row["win_rate"] = round(row["wins"] / count, 4) if count else None
            row["total_pnl"] = round(float(row["total_pnl"]), 2)
            row["total_notional"] = round(float(row["total_notional"]), 2)
    return {
        "trade_count": len(trades),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "total_notional": round(sum(float(trade.get("notional") or EVENT_NOTIONAL) for trade in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "by_source": by_source,
        "by_state_score_bucket": by_bucket,
        "trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "notional": trade.get("notional"),
                "scalar": trade.get("state_score_scalar"),
                "state_score": trade.get("state_score"),
                "state_score_positive": trade.get("state_score_positive"),
                "state_surface": trade.get("state_surface"),
                "state_decision_date": trade.get("state_decision_date"),
                "state_rank_pct": trade.get("state_rank_pct"),
                "state_feature_available": trade.get("state_feature_available"),
            }
            for trade in trades
        ],
    }


def _coverage(enriched: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    available = [row for row in rows if row.get("state_feature_available")]
    bucket_counts = Counter(
        "positive_score" if row.get("state_score_positive") else "nonpositive_score"
        for row in available
    )
    return {
        "event_trade_count": len(rows),
        "feature_available_count": len(available),
        "feature_available_fraction": round(len(available) / len(rows), 4) if rows else None,
        "bucket_counts": dict(bucket_counts),
        "missing_feature_count": len(rows) - len(available),
        "rule": "event ticker's PIT state-surface score > 0 before event entry",
    }


def _gate_summary(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = _aggregate_delta(before, after)
    by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in by_window.values())
        or any(row["passes_drawdown"] for row in by_window.values())
    )
    passed = delta["windows_ev_improved"] >= 2 and delta["windows_ev_regressed"] == 0 and material
    return {
        "passed": bool(passed),
        "delta": delta,
        "by_window": by_window,
        "rule": (
            "EV first over the three canonical backtesting.md windows; require "
            "majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger."
        ),
    }


def _best_variant_name(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != "full_bundle"]
    return max(
        names,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = _load_event_trades()
    event_trades = _enrich_event_trades(raw_event_trades)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_metrics[label] = _core_metrics(result)
        for name, variant in VARIANTS.items():
            scaled = [
                row
                for row in (
                    _scaled_trade(trade, name, variant)
                    for trade in event_trades[label]
                )
                if row is not None
            ]
            curve = _event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _combined_metrics(result, curve, scaled)
            variant_events[name][label] = _trade_summary(scaled)

    full_metrics = variant_metrics["full_bundle"]
    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    full_gates = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    best_variant = _best_variant_name(full_gates)
    best_gate = full_gates[best_variant]
    accepted = bool(best_gate["passed"] and core_gates[best_variant]["passed"])
    decision = "promising_replay_only_state_score_tilt" if accepted else "rejected"

    if accepted:
        rationale = (
            f"Promising replay-only: {best_variant} beat the full frozen event bundle "
            "and core baseline under the three-window Gate 4 rule. Production use "
            "still requires a shared default-off event paper/live adapter that computes "
            "the same PIT state score before any capital impact."
        )
        rejection_reason = None
        next_action = (
            "Move only this positive state-score tilt into a shared default-off event "
            "paper adapter, then collect forward closed outcomes before live promotion."
        )
    else:
        rationale = (
            f"Rejected: the best state-score variant ({best_variant}) did not beat the "
            "full frozen event bundle with enough stable EV improvement and materiality."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the full event bundle unchanged; do not retry nearby state-score "
            "event tilts without forward replacement-value evidence or a materially "
            "different event-quality discriminator."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_state_score_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Default-off event-bundle trades whose ticker has a positive PIT "
            "state-surface score before entry should receive more notional than "
            "event trades with non-positive state-score confirmation."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking is still data-limited, earnings/C enablement failed, "
                "event source pruning, core-pressure guards, pre-entry relative momentum, "
                "price-structure tilts, state-surface pruning, state/event shared capacity, "
                "and state-surface collision ranking all have recent rejection evidence. "
                "This is a different cross-surface event-quality discriminator."
            ),
        },
        "single_causal_variable": "PIT state-surface score > 0 used only to tilt event notional",
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
            "base_event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "feature_rule": "event ticker state-surface score > 0 on latest PIT decision date before event entry",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "event source definitions",
                "event source thresholds",
                "event holding period",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "historical_experiment_check": {
            "similar_positive_priors": {
                "exp-20260504-049": "Full frozen default-off event bundle improved all three canonical windows.",
                "exp-20260507-016": "State surface satellite improved all three canonical windows as a separate replay-only sleeve.",
                "exp-20260507-018": "Default-off production-visible state-surface paper adapter exists for forward observation only.",
            },
            "nearby_rejected": {
                "exp-20260505-031": "One-day event follow-through delay regressed all windows.",
                "exp-20260507-012": "Event source pruning did not beat the full bundle.",
                "exp-20260507-019": "Event+state shared-capacity combination failed versus event-only.",
                "exp-20260507-020": "FD/Other item-code semantics was positive but immaterial.",
                "exp-20260507-021": "Core-pressure event guard was positive only immaterial versus full bundle.",
                "exp-20260507-022": "5d pre-entry relative-strength tilt was positive only immaterial versus full bundle.",
                "exp-20260507-023": "State-surface scarce-slot core collision ranking failed.",
                "exp-20260507-024": "SMA20/SMA50 price-structure event tilt regressed late_strong versus full bundle.",
            },
            "why_not_simple_repeat": (
                "This does not prune event sources, change event timing, alter source priority, "
                "combine satellite capacity, retune short-horizon relative momentum, or use the "
                "SMA20/SMA50 price-structure proxy. It uses one cross-sectional state-surface score "
                "that is already computed from PIT OHLCV/breadth inputs."
            ),
            "mechanism_insight_conflict": (
                "No conflict with recent do-not-repeat zones: no LLM ranking, no raw earnings/C, "
                "no broad universe growth, no source subset permutation, no core slot/capacity change."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_event_bundle": full_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_full_bundle": full_gates,
        },
        "expected_value_score_delta": {
            "best_variant_vs_full_bundle": {
                label: best_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "best_variant_vs_core": {
                label: core_gates[best_variant]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "best_variant": best_variant,
        "event_selection": variant_events,
        "coverage": {
            "source_coverage": source_coverage,
            "state_score_feature": _coverage(event_trades),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_positive": (
                "A shared default-off event paper/live adapter must compute the same PIT-safe "
                "state-score feature in run.py and backtester before any capital impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking outcome joins remain sparse; this deterministic alpha test "
                "does not weaken or expand LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings re-enable, LLM ranking, event source pruning, FD/Other item-code tweaks, "
            "state-surface pruning/combination/collision ranking, broad universe expansion, and "
            "runner exits all have recent blocker or rejection evidence."
        ),
        "risk_of_change": (
            "A state-score tilt can underweight profitable reversal events and can still overfit "
            "the current frozen event sample; forward paper evidence is required before promotion."
        ),
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-025 Event State-Score Tilt",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with positive PIT state-surface score before entry.",
        "",
        "## Best Variant Vs Full Bundle",
        "",
        "| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    for label in WINDOWS:
        before = payload["before_metrics"]["full_event_bundle"][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=selected["trade_count"],
                epnl=selected["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_full_bundle"].items():
        delta = row["delta"]
        lines.append(
            "| {name} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {passed} |".format(
                name=name,
                ev=delta["aggregate_ev_delta"],
                pnl=delta["aggregate_pnl_delta"],
                wi=delta["windows_ev_improved"],
                wr=delta["windows_ev_regressed"],
                passed=row["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["coverage"]["state_score_feature"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "No production universe, ranking, sizing, exits, LLM, news, or order path changed.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines))


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Event state-score tilt",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_report(payload)

    compact = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "best_variant": payload["best_variant"],
        "coverage": payload["coverage"]["state_score_feature"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_variant_vs_full_bundle": payload["delta_metrics"]["variant_vs_full_bundle"][best]["delta"],
                    "best_variant_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
                    "coverage": payload["coverage"]["state_score_feature"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
