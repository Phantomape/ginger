"""exp-20260430-001 event-sensitive liquidity-filtered universe scout.

Observed-only shadow evaluation. This script does not change production
universe membership, shared strategy code, candidate ordering, or sizing.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean, median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from filter import WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260430-001"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260430_001_event_sensitive_liquidity_filtered_universe.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

FORWARD_HORIZONS = [1, 5, 10, 20]
TOP_PER_DAY = 5

MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 50_000_000
MIN_CLOSE = 8.0

EVENT_MIN_ABS_MOVE = 0.05
EVENT_MIN_VOLUME_RATIO = 1.80
EVENT_MIN_RANGE_VS_ATR = 1.25
EVENT_MAX_ATR_PCT = 0.12
ENTRY_MIN_CLOSE_LOCATION = 0.55
ENTRY_MIN_RS_VS_SPY_5D = 0.0
ENTRY_MAX_GAP_FROM_EVENT_CLOSE = 0.08


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_frames(snapshot_path: str) -> tuple[dict[str, pd.DataFrame], dict]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames, payload.get("metadata") or {}


def _expected_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is None:
        return 0
    return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))


def _clean(values):
    return [float(v) for v in values if v is not None and not math.isnan(float(v))]


def _safe_mean(values):
    clean = _clean(values)
    return round(mean(clean), 6) if clean else None


def _safe_median(values):
    clean = _clean(values)
    return round(median(clean), 6) if clean else None


def _quantiles(values):
    clean = sorted(_clean(values))
    if not clean:
        return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}

    def pick(q: float) -> float:
        return round(clean[int(round((len(clean) - 1) * q))], 6)

    return {
        "p10": pick(0.10),
        "p25": pick(0.25),
        "p50": pick(0.50),
        "p75": pick(0.75),
        "p90": pick(0.90),
    }


def _summarize_returns(rows: list[dict]) -> dict:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [row.get(key) for row in rows if row.get(key) is not None]
        positives = [v for v in values if v > 0]
        out[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len(positives) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return out


def _date_key_from_path(path: str) -> str | None:
    stem = os.path.basename(path).split(".")[0]
    raw = stem.split("_")[-1]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _production_universe() -> set[str]:
    universe = {ticker.upper() for ticker in WATCHLIST}
    positions_path = os.path.join(REPO_ROOT, "data", "open_positions.json")
    if os.path.exists(positions_path):
        try:
            payload = _load_json(positions_path)
            for pos in payload.get("positions") or []:
                ticker = pos.get("ticker")
                if ticker:
                    universe.add(str(ticker).upper())
        except Exception:
            pass
    return universe


def _load_existing_ab_context() -> tuple[set[tuple[str, str]], set[str], Counter, set[str]]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
    active_days: set[str] = set()
    data_dir = os.path.join(REPO_ROOT, "data")

    for name in os.listdir(data_dir):
        if not name.startswith("backtest_results_") or not name.endswith(".json"):
            continue
        try:
            payload = _load_json(os.path.join(data_dir, name))
        except Exception:
            continue
        for trade in payload.get("trades") or []:
            if trade.get("strategy") not in {"trend_long", "breakout_long"}:
                continue
            ticker = trade.get("ticker")
            entry_date = str(trade.get("entry_date") or "")[:10]
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, entry_date))
                tickers.add(ticker)
                by_ticker[ticker] += 1
                active_days.add(entry_date)

    for name in os.listdir(data_dir):
        if not (name.startswith("quant_signals_") or name.startswith("trend_signals_")):
            continue
        if not name.endswith(".json"):
            continue
        date_key = _date_key_from_path(name)
        if not date_key:
            continue
        try:
            payload = _load_json(os.path.join(data_dir, name))
        except Exception:
            continue
        signals = payload.get("signals") if isinstance(payload, dict) else payload
        if isinstance(signals, dict):
            signals = signals.values()
        for sig in signals or []:
            if not isinstance(sig, dict):
                continue
            if sig.get("strategy") not in {"trend_long", "breakout_long"}:
                continue
            ticker = sig.get("ticker")
            if ticker:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, date_key))
                tickers.add(ticker)
                by_ticker[ticker] += 1
                active_days.add(date_key)
    return touchpoints, tickers, by_ticker, active_days


def _ticker_liquidity(
    ticker: str,
    df: pd.DataFrame,
    start: str,
    end: str,
    expected_days: int,
    ab_by_ticker: Counter,
) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "ticker": ticker,
            "coverage_days": 0,
            "coverage_fraction": 0.0,
            "median_dollar_volume": None,
            "median_close": None,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    return {
        "ticker": ticker,
        "coverage_days": int(len(window)),
        "coverage_fraction": round(len(window) / expected_days, 4) if expected_days else 0.0,
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "ab_touchpoint_days_all_archives": int(ab_by_ticker[ticker]),
    }


def _passes_liquidity(info: dict) -> bool:
    return (
        info["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and (info.get("median_dollar_volume") or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
        and (info.get("median_close") or 0.0) >= MIN_CLOSE
    )


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_close"] = out["Close"].shift(1)
    ranges = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - out["prev_close"]).abs(),
        (out["Low"] - out["prev_close"]).abs(),
    ], axis=1)
    out["atr14"] = ranges.max(axis=1).rolling(14).mean()
    out["atr_pct"] = out["atr14"] / out["Close"]
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    out["range_vs_atr"] = (out["High"] - out["Low"]) / out["atr14"]
    out["ret1"] = out["Close"] / out["prev_close"] - 1
    out["ret5"] = out["Close"] / out["Close"].shift(5) - 1
    out["spy_ret5"] = spy["Close"] / spy["Close"].shift(5) - 1
    day_range = (out["High"] - out["Low"]).replace(0, pd.NA)
    out["close_location"] = (out["Close"] - out["Low"]) / day_range
    out["event_midpoint_prev"] = ((out["High"] + out["Low"]) / 2).shift(1)
    out["event_close_prev"] = out["Close"].shift(1)
    out["event_ret1_prev"] = out["ret1"].shift(1)
    out["event_volume_ratio_prev"] = out["volume_ratio"].shift(1)
    out["event_range_vs_atr_prev"] = out["range_vs_atr"].shift(1)
    out["event_atr_pct_prev"] = out["atr_pct"].shift(1)
    out["entry_gap_from_event_close"] = out["Open"] / out["event_close_prev"] - 1
    return out


def _forward_returns(df: pd.DataFrame, date_key: str) -> dict:
    asof = pd.Timestamp(date_key)
    if asof not in df.index:
        hist = df.loc[:asof]
        if hist.empty:
            return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
        asof = hist.index[-1]
    idx = df.index.get_loc(asof)
    entry = float(df.iloc[idx]["Close"])
    out = {}
    for horizon in FORWARD_HORIZONS:
        fwd_idx = idx + horizon
        key = f"fwd_{horizon}d"
        if fwd_idx >= len(df) or entry <= 0:
            out[key] = None
        else:
            out[key] = round(float(df.iloc[fwd_idx]["Close"]) / entry - 1, 6)
    return out


def _candidate(ticker: str, row: pd.Series) -> dict | None:
    required = [
        row.get("event_ret1_prev"),
        row.get("event_volume_ratio_prev"),
        row.get("event_range_vs_atr_prev"),
        row.get("event_atr_pct_prev"),
        row.get("event_midpoint_prev"),
        row.get("event_close_prev"),
        row.get("entry_gap_from_event_close"),
        row.get("close_location"),
        row.get("ret5"),
        row.get("spy_ret5"),
    ]
    if any(value is None or pd.isna(value) for value in required):
        return None

    event_move = float(row["event_ret1_prev"])
    if abs(event_move) < EVENT_MIN_ABS_MOVE:
        return None
    if float(row["event_volume_ratio_prev"]) < EVENT_MIN_VOLUME_RATIO:
        return None
    if float(row["event_range_vs_atr_prev"]) < EVENT_MIN_RANGE_VS_ATR:
        return None
    if float(row["event_atr_pct_prev"]) > EVENT_MAX_ATR_PCT:
        return None
    if float(row["Close"]) < float(row["event_midpoint_prev"]):
        return None
    if abs(float(row["entry_gap_from_event_close"])) > ENTRY_MAX_GAP_FROM_EVENT_CLOSE:
        return None
    if float(row["close_location"]) < ENTRY_MIN_CLOSE_LOCATION:
        return None

    rs5 = float(row["ret5"]) - float(row["spy_ret5"])
    if rs5 < ENTRY_MIN_RS_VS_SPY_5D:
        return None

    event_direction = "positive_event_hold" if event_move > 0 else "negative_event_recovery_hold"
    score = (
        1.0
        + min(abs(event_move) - EVENT_MIN_ABS_MOVE, 0.15) * 3.0
        + min(float(row["event_volume_ratio_prev"]) - EVENT_MIN_VOLUME_RATIO, 4.0) * 0.10
        + min(float(row["event_range_vs_atr_prev"]) - EVENT_MIN_RANGE_VS_ATR, 2.0) * 0.10
        + min(max(rs5, 0.0), 0.12) * 2.0
        + min(float(row["close_location"]) - ENTRY_MIN_CLOSE_LOCATION, 0.45) * 0.20
        + (0.10 if event_move < 0 else 0.0)
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "shadow_score": round(score, 4),
        "shadow_event_proxy": event_direction,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "close": round(float(row["Close"]), 4),
        "conditions": {
            "prior_event_return": round(event_move, 6),
            "prior_event_volume_ratio": round(float(row["event_volume_ratio_prev"]), 4),
            "prior_event_range_vs_atr": round(float(row["event_range_vs_atr_prev"]), 4),
            "prior_event_atr_pct": round(float(row["event_atr_pct_prev"]), 6),
            "entry_close_vs_event_midpoint": round(float(row["Close"]) / float(row["event_midpoint_prev"]) - 1, 6),
            "entry_gap_from_event_close": round(float(row["entry_gap_from_event_close"]), 6),
            "entry_close_location": round(float(row["close_location"]), 4),
            "entry_5d_return": round(float(row["ret5"]), 6),
            "entry_spy_5d_return": round(float(row["spy_ret5"]), 6),
            "entry_rs5_vs_spy": round(rs5, 6),
        },
    }


def _scarce_slot_proxy(rows: list[dict], ab_active_days: set[str]) -> dict:
    by_day: OrderedDict[str, list[dict]] = OrderedDict()
    for row in sorted(rows, key=lambda r: (r["date"], -r["shadow_score"], r["ticker"])):
        by_day.setdefault(row["date"], []).append(row)
    top_rows = []
    for day_rows in by_day.values():
        top_rows.extend(day_rows[:TOP_PER_DAY])
    ab_days = {day for day in by_day if day in ab_active_days}
    return {
        "candidate_days": len(by_day),
        "ab_active_day_count": len(ab_days),
        "ab_active_day_rate": round(len(ab_days) / len(by_day), 4) if by_day else None,
        "top_per_day_limit": TOP_PER_DAY,
        "top_per_day_candidate_count": len(top_rows),
        "top_per_day_forward_returns": _summarize_returns(top_rows),
        "all_candidate_forward_returns": _summarize_returns(rows),
        "note": "Top-per-day returns are only a scarce-slot proxy; no fills, stops, sizing, or slot-aware replay ran.",
    }


def _audit_window(name: str, cfg: dict, production_universe: set[str], ab_context: tuple) -> dict:
    ab_touchpoints, ab_tickers, ab_by_ticker, ab_active_days = ab_context
    frames, metadata = _load_frames(cfg["snapshot"])
    start = cfg["start"]
    end = cfg["end"]
    expected_days = _expected_days(frames, start, end)
    spy = frames["SPY"]

    liquidity = {}
    liquid_tickers = []
    rejections = Counter()
    for ticker, df in frames.items():
        if ticker in EXCLUDED_TICKERS:
            rejections["excluded_etf_or_macro_proxy"] += 1
            continue
        info = _ticker_liquidity(ticker, df, start, end, expected_days, ab_by_ticker)
        liquidity[ticker] = info
        if _passes_liquidity(info):
            liquid_tickers.append(ticker)
        else:
            rejections["failed_liquidity_or_coverage"] += 1

    candidates = []
    for ticker in sorted(liquid_tickers):
        featured = _add_features(frames[ticker], spy)
        window = featured.loc[pd.Timestamp(start):pd.Timestamp(end)]
        for _, row in window.iterrows():
            signal = _candidate(ticker, row)
            if signal is None:
                continue
            signal.update(_forward_returns(frames[ticker], signal["date"]))
            signal["same_day_ab_overlap"] = (ticker, signal["date"]) in ab_touchpoints
            signal["ticker_in_prior_ab_trades_or_signals"] = ticker in ab_tickers
            signal["in_production_universe"] = ticker in production_universe
            signal["median_dollar_volume"] = liquidity[ticker]["median_dollar_volume"]
            signal["coverage_fraction"] = liquidity[ticker]["coverage_fraction"]
            candidates.append(signal)

    candidates = sorted(candidates, key=lambda r: (r["date"], -r["shadow_score"], r["ticker"]))
    same_day_overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    ticker_history_overlap = [row for row in candidates if row["ticker_in_prior_ab_trades_or_signals"]]
    outside_prod = [row for row in candidates if not row["in_production_universe"]]
    by_sector = Counter(row["sector"] for row in candidates)
    by_proxy = Counter(row["shadow_event_proxy"] for row in candidates)

    return {
        "window": name,
        "start": start,
        "end": end,
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": metadata.get("ticker_count"),
        "expected_trading_days": expected_days,
        "liquid_shadow_universe_count": len(liquid_tickers),
        "selection_rejections": dict(sorted(rejections.items())),
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "candidate_tickers": sorted({row["ticker"] for row in candidates}),
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "candidate_count_by_event_proxy": dict(sorted(by_proxy.items())),
        "candidate_median_dollar_volume": _safe_median([row["median_dollar_volume"] for row in candidates]),
        "coverage_fraction_min": min((row["coverage_fraction"] for row in candidates), default=None),
        "same_day_ab_overlap_count": len(same_day_overlap),
        "same_day_ab_overlap_rate": round(len(same_day_overlap) / len(candidates), 4) if candidates else None,
        "ticker_history_ab_overlap_count": len(ticker_history_overlap),
        "ticker_history_ab_overlap_rate": round(len(ticker_history_overlap) / len(candidates), 4) if candidates else None,
        "outside_production_candidate_count": len(outside_prod),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_prod}),
        "forward_return_distribution": _summarize_returns(candidates),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(
            [row for row in candidates if not row["same_day_ab_overlap"]]
        ),
        "scarce_slot_proxy": _scarce_slot_proxy(candidates, ab_active_days),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "sample_candidates": candidates[:40],
    }


def _weighted_forward(windows: list[dict]) -> dict:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        count = sum((w["forward_return_distribution"][key]["count"] or 0) for w in windows)
        avg_num = 0.0
        win_num = 0.0
        for window in windows:
            stats = window["forward_return_distribution"][key]
            n = stats["count"] or 0
            if n and stats["avg"] is not None:
                avg_num += n * stats["avg"]
            if n and stats["win_rate"] is not None:
                win_num += n * stats["win_rate"]
        out[key] = {
            "count": count,
            "weighted_avg": round(avg_num / count, 6) if count else None,
            "weighted_win_rate": round(win_num / count, 4) if count else None,
            "note": "Weighted from per-window summary metrics; quantiles remain in window sections.",
        }
    return out


def _promotion_evidence(windows: list[dict]) -> dict:
    fwd10_positive = 0
    fwd20_positive = 0
    top10_positive = 0
    for window in windows:
        fwd10 = window["forward_return_distribution"]["fwd_10d"]["avg"]
        fwd20 = window["forward_return_distribution"]["fwd_20d"]["avg"]
        top10 = window["scarce_slot_proxy"]["top_per_day_forward_returns"]["fwd_10d"]["avg"]
        fwd10_positive += int(fwd10 is not None and fwd10 > 0)
        fwd20_positive += int(fwd20 is not None and fwd20 > 0)
        top10_positive += int(top10 is not None and top10 > 0)
    return {
        "forward_10d_positive_windows": fwd10_positive,
        "forward_20d_positive_windows": fwd20_positive,
        "scarce_slot_top5_10d_positive_windows": top10_positive,
        "promotion_ready": fwd10_positive == 3 and top10_positive == 3,
        "rule": "Promotion would require all three windows positive on 10d forward and top-5-per-day 10d proxy, then a separate slot-aware replay ticket.",
    }


def main() -> None:
    production_universe = _production_universe()
    ab_context = _load_existing_ab_context()
    windows = [
        _audit_window(name, cfg, production_universe, ab_context)
        for name, cfg in WINDOWS.items()
    ]

    total_candidates = sum(window["candidate_count"] for window in windows)
    total_overlap = sum(window["same_day_ab_overlap_count"] for window in windows)
    total_outside = sum(window["outside_production_candidate_count"] for window in windows)
    promotion = _promotion_evidence(windows)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": "一个流动性过滤后的事件敏感 universe 可以在当前 trend/breakout 覆盖之外产生非重叠高质量候选。",
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "single_causal_variable": "event-sensitive liquidity-filtered universe",
        "alpha_hypothesis": {
            "category": "universe_scout",
            "statement": "A high-volume event shock followed by next-day hold/continuation can identify event-sensitive candidates with better scarce-slot quality than raw event-day candidates.",
            "why_this_is_not_a_repeat": "Prior OHLCV event scout measured raw event-day repricing. This run measures the post-event hold day as the candidate source, so the independent variable is the universe definition, not a threshold sweep or ETF addition.",
            "why_not_production_now": "This is shadow measurement only; production promotion would require a separate ticket and slot-aware backtest.",
        },
        "shadow_universe_definition": {
            "name": "post-event hold continuation liquid universe",
            "source": "fixed OHLCV snapshots only; no production universe promotion",
            "liquidity_filters": {
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "excluded_tickers": sorted(EXCLUDED_TICKERS),
            },
            "event_day_trigger": {
                "prior_abs_close_to_close_return_gte": EVENT_MIN_ABS_MOVE,
                "prior_volume_ratio_gte": EVENT_MIN_VOLUME_RATIO,
                "prior_range_vs_atr_gte": EVENT_MIN_RANGE_VS_ATR,
                "prior_atr_pct_lte": EVENT_MAX_ATR_PCT,
            },
            "entry_day_hold_trigger": {
                "close_above_prior_event_midpoint": True,
                "abs_open_gap_from_prior_event_close_lte": ENTRY_MAX_GAP_FROM_EVENT_CLOSE,
                "close_location_gte": ENTRY_MIN_CLOSE_LOCATION,
                "five_day_relative_strength_vs_spy_gte": ENTRY_MIN_RS_VS_SPY_5D,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "historical_constraints_checked": {
            "recent_rejections_avoided": [
                "exp-20260430-005 defensive ETF universe expansion",
                "exp-20260430-008 sector/commodity ETF universe expansion",
            ],
            "not_repeated_without_new_evidence": "No ETF additions were tested; no production universe file was modified; raw event-day scout was changed to post-event hold-day measurement.",
        },
        "bias_risks": [
            "Fixed OHLCV snapshots contain only archived repository tickers, so true outside-production discovery is structurally capped.",
            "Snapshot membership is survivorship-biased and not a historical constituent universe.",
            "The event proxy does not know actual news, earnings, guidance, or LLM semantic event quality.",
            "Forward returns are candidate marks, not fills, sizing, stops, news vetos, or scarce-slot portfolio simulation.",
        ],
        "production_promotion": False,
        "promotion_evidence": promotion,
        "promotion_follow_up": (
            "Create a separate promotion ticket only if an external survivorship-aware "
            "source can supply non-production candidates and a slot-aware replay shows "
            "that these candidates improve EV without displacing stronger A/B trades."
        ),
        "ab_context": {
            "ab_touchpoint_count": len(ab_context[0]),
            "ab_ticker_count": len(ab_context[1]),
            "ab_active_day_count": len(ab_context[3]),
            "ab_by_ticker_top10": dict(ab_context[2].most_common(10)),
        },
        "aggregate": {
            "candidate_count": total_candidates,
            "unique_tickers": sorted({ticker for window in windows for ticker in window["candidate_tickers"]}),
            "same_day_ab_overlap_rate_weighted": round(total_overlap / total_candidates, 4) if total_candidates else None,
            "outside_production_candidate_count": total_outside,
            "sample_based_forward_returns": _weighted_forward(windows),
        },
        "windows": windows,
        "decision": {
            "status": "observed_only",
            "promotion_ready": bool(promotion["promotion_ready"] and total_outside > 0),
            "reason": "Shadow audit only; useful mechanism evidence is possible, but current snapshots do not prove external universe expansion value.",
            "do_not_repeat": [
                "Do not add defensive or sector ETFs as simple universe expansion.",
                "Do not treat higher candidate count as alpha without slot opportunity-cost evidence.",
                "Do not rerun raw event-day OHLCV scout without a new event-quality or slot-quality discriminator.",
            ],
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=False)
        f.write("\n")

    print(json.dumps({
        "artifact": OUT_JSON,
        "candidate_count": total_candidates,
        "same_day_ab_overlap_rate_weighted": artifact["aggregate"]["same_day_ab_overlap_rate_weighted"],
        "outside_production_candidate_count": total_outside,
        "weighted_forward_returns": artifact["aggregate"]["sample_based_forward_returns"],
        "promotion_evidence": promotion,
        "decision": artifact["decision"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
