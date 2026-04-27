"""exp-20260426-060 undercut-and-reclaim universe scout.

Observed-only shadow evaluation. This script does not change the production
universe or shared strategy code.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from statistics import mean, median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from filter import WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260426-060"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_060_universe_scout_undercut_reclaim.json",
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

ETF_OR_MACRO_PROXIES = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0
MIN_COVERAGE_FRACTION = 0.95
UNDERCUT_LOOKBACK_DAYS = 20
MIN_UNDERCUT_PCT = 0.005
MIN_RECLAIM_PCT = 0.0025
MIN_VOLUME_RATIO = 1.10
MIN_PRIOR_5D_PULLBACK_PCT = -0.03
MIN_CLOSE_LOCATION = 0.60
FORWARD_HORIZONS = [1, 5, 10, 20]


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


def _safe_mean(values):
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(mean(clean), 6) if clean else None


def _safe_median(values):
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(median(clean), 6) if clean else None


def _quantiles(values):
    clean = sorted(float(v) for v in values if v is not None and not math.isnan(float(v)))
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
    summary = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [row.get(key) for row in rows if row.get(key) is not None]
        positives = [v for v in values if v > 0]
        summary[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len(positives) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return summary


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


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str], Counter, Counter]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
    by_date: Counter = Counter()
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
            entry_date = trade.get("entry_date")
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, entry_date))
                tickers.add(ticker)
                by_ticker[ticker] += 1
                by_date[entry_date] += 1

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
                by_date[date_key] += 1
    return touchpoints, tickers, by_ticker, by_date


def _ticker_stats(
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
            "ab_touchpoint_day_rate": None,
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    ab_day_rate = ab_by_ticker[ticker] / expected_days if expected_days else 0.0
    return {
        "ticker": ticker,
        "coverage_days": int(len(window)),
        "coverage_fraction": round(len(window) / expected_days, 4) if expected_days else 0.0,
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
        "ab_touchpoint_days_all_archives": int(ab_by_ticker[ticker]),
        "ab_touchpoint_day_rate": round(ab_day_rate, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
    }


def _liquidity_eligible(info: dict) -> bool:
    return (
        info["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and info["median_dollar_volume"] is not None
        and info["median_dollar_volume"] >= MIN_MEDIAN_DOLLAR_VOLUME
        and info["median_close"] is not None
        and info["median_close"] >= MIN_CLOSE
    )


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_close"] = out["Close"].shift(1)
    out["prior_low20"] = out["Low"].shift(1).rolling(UNDERCUT_LOOKBACK_DAYS).min()
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    out["prior_return5"] = out["Close"].shift(1) / out["Close"].shift(6) - 1
    out["return10"] = out["Close"] / out["Close"].shift(10) - 1
    out["spy_return10"] = spy["Close"] / spy["Close"].shift(10) - 1
    day_range = out["High"] - out["Low"]
    out["close_location"] = (out["Close"] - out["Low"]) / day_range.replace(0, pd.NA)
    return out


def _select_shadow_universe(
    frames: dict[str, pd.DataFrame],
    start: str,
    end: str,
    expected_days: int,
    ab_by_ticker: Counter,
) -> tuple[list[str], dict[str, dict], Counter]:
    stats = {
        ticker: _ticker_stats(ticker, df, start, end, expected_days, ab_by_ticker)
        for ticker, df in frames.items()
    }
    selected = []
    rejected = Counter()
    for ticker, info in stats.items():
        if ticker in ETF_OR_MACRO_PROXIES:
            rejected["etf_or_macro_proxy"] += 1
            continue
        if not _liquidity_eligible(info):
            rejected["liquidity_or_coverage"] += 1
            continue
        selected.append(ticker)
    selected.sort()
    return selected, stats, rejected


def _signal_for_row(ticker: str, row: pd.Series) -> dict | None:
    fields = [
        row.get("prior_low20"),
        row.get("volume_ratio"),
        row.get("prior_return5"),
        row.get("close_location"),
        row.get("return10"),
    ]
    if any(value is None or pd.isna(value) for value in fields):
        return None

    prior_low = float(row["prior_low20"])
    low = float(row["Low"])
    close = float(row["Close"])
    open_ = float(row["Open"])
    if prior_low <= 0 or close <= 0:
        return None

    undercut_pct = low / prior_low - 1
    reclaim_pct = close / prior_low - 1
    volume_ratio = float(row["volume_ratio"])
    prior_return5 = float(row["prior_return5"])
    close_location = float(row["close_location"])
    spy_return10 = 0.0 if pd.isna(row.get("spy_return10")) else float(row["spy_return10"])
    rs_10d = float(row["return10"]) - spy_return10

    if undercut_pct > -MIN_UNDERCUT_PCT:
        return None
    if reclaim_pct < MIN_RECLAIM_PCT:
        return None
    if volume_ratio < MIN_VOLUME_RATIO:
        return None
    if prior_return5 > MIN_PRIOR_5D_PULLBACK_PCT:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if close <= open_:
        return None

    score = (
        1.0
        + min(abs(undercut_pct) - MIN_UNDERCUT_PCT, 0.08) * 5.0
        + min(reclaim_pct, 0.06) * 4.0
        + min(volume_ratio - MIN_VOLUME_RATIO, 2.0) * 0.15
        + min(close_location - MIN_CLOSE_LOCATION, 0.40) * 0.30
        + (0.15 if rs_10d > 0 else 0.0)
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "strategy_proxy": "undercut_reclaim_reversal",
        "shadow_score": round(score, 4),
        "close": round(close, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "conditions": {
            "lookback_days": UNDERCUT_LOOKBACK_DAYS,
            "prior_low20": round(prior_low, 4),
            "undercut_pct": round(undercut_pct, 6),
            "reclaim_pct": round(reclaim_pct, 6),
            "volume_ratio": round(volume_ratio, 4),
            "prior_5d_return": round(prior_return5, 6),
            "close_location": round(close_location, 4),
            "return_10d": round(float(row["return10"]), 6),
            "spy_return_10d": round(spy_return10, 6),
            "rs_10d": round(rs_10d, 6),
            "green_day": close > open_,
        },
    }


def _forward_returns(df: pd.DataFrame, date_key: str) -> dict:
    asof = pd.Timestamp(date_key)
    if asof not in df.index:
        hist = df.loc[:asof]
        if hist.empty:
            return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
        idx = df.index.get_loc(hist.index[-1])
    else:
        idx = df.index.get_loc(asof)
    start_close = float(df["Close"].iloc[idx])
    out = {}
    for horizon in FORWARD_HORIZONS:
        target_idx = idx + horizon
        key = f"fwd_{horizon}d"
        if target_idx >= len(df) or start_close <= 0:
            out[key] = None
        else:
            out[key] = round((float(df["Close"].iloc[target_idx]) - start_close) / start_close, 6)
    return out


def _top_by_day(rows: list[dict], limit: int = 1) -> list[dict]:
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["date"], []).append(row)
    selected = []
    for date_key, day_rows in by_day.items():
        ranked = sorted(day_rows, key=lambda item: (-item["shadow_score"], item["ticker"]))
        selected.extend(ranked[:limit])
    return selected


def _scarce_slot_proxy(rows: list[dict], ab_by_date: Counter) -> dict:
    if not rows:
        return {
            "candidate_days": 0,
            "avg_candidates_per_candidate_day": None,
            "ab_candidate_day_overlap_rate": None,
            "top1_by_day_forward_returns": _summarize_returns([]),
        }
    by_date = Counter(row["date"] for row in rows)
    candidate_days = len(by_date)
    ab_overlap_days = sum(1 for date_key in by_date if ab_by_date[date_key] > 0)
    top1 = _top_by_day(rows, 1)
    top2 = _top_by_day(rows, 2)
    return {
        "candidate_days": candidate_days,
        "max_candidates_on_one_day": max(by_date.values()),
        "avg_candidates_per_candidate_day": round(sum(by_date.values()) / candidate_days, 4),
        "ab_candidate_day_overlap_count": ab_overlap_days,
        "ab_candidate_day_overlap_rate": round(ab_overlap_days / candidate_days, 4),
        "days_with_three_or_more_shadow_candidates": sum(1 for count in by_date.values() if count >= 3),
        "top1_by_day_candidate_count": len(top1),
        "top1_by_day_forward_returns": _summarize_returns(top1),
        "top2_by_day_candidate_count": len(top2),
        "top2_by_day_forward_returns": _summarize_returns(top2),
    }


def _evaluate_window(
    label: str,
    cfg: dict,
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_tickers: set[str],
    ab_by_ticker: Counter,
    ab_by_date: Counter,
) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    expected = _expected_days(frames, cfg["start"], cfg["end"])
    shadow_universe, ticker_stats, rejected = _select_shadow_universe(
        frames,
        cfg["start"],
        cfg["end"],
        expected,
        ab_by_ticker,
    )
    rows = []
    spy_features = frames["SPY"]
    for ticker in shadow_universe:
        feature_df = _add_features(frames[ticker], spy_features)
        window = feature_df.loc[pd.Timestamp(cfg["start"]):pd.Timestamp(cfg["end"])]
        for _, row in window.iterrows():
            signal = _signal_for_row(ticker, row)
            if signal is None:
                continue
            signal.update(_forward_returns(frames[ticker], signal["date"]))
            signal["same_day_ab_overlap"] = (ticker, signal["date"]) in ab_touchpoints
            signal["ticker_in_prior_ab_trades_or_signals"] = ticker in ab_tickers
            signal["in_production_universe"] = ticker in production_universe
            signal["universe_stats"] = ticker_stats[ticker]
            rows.append(signal)

    rows.sort(key=lambda item: (-item["shadow_score"], item["date"], item["ticker"]))
    unique_tickers = sorted({row["ticker"] for row in rows})
    non_overlap_rows = [row for row in rows if not row["same_day_ab_overlap"]]
    outside_prod_rows = [row for row in rows if not row["in_production_universe"]]
    same_day_overlap = sum(1 for row in rows if row["same_day_ab_overlap"])
    ticker_history_overlap = sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"])
    by_sector = Counter(row["sector"] for row in rows)
    by_ticker = Counter(row["ticker"] for row in rows)

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": len(metadata.get("tickers") or []),
        "expected_trading_days": expected,
        "shadow_universe_tickers": shadow_universe,
        "shadow_universe_count": len(shadow_universe),
        "selection_rejections": dict(sorted(rejected.items())),
        "shadow_universe_stats": {ticker: ticker_stats[ticker] for ticker in shadow_universe},
        "liquidity_data_coverage": {
            "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_close": MIN_CLOSE,
            "eligible_ticker_count": len(shadow_universe),
            "median_eligible_dollar_volume": _safe_median(
                [ticker_stats[t]["median_dollar_volume"] for t in shadow_universe]
            ),
            "median_eligible_coverage_fraction": _safe_median(
                [ticker_stats[t]["coverage_fraction"] for t in shadow_universe]
            ),
        },
        "shadow_candidate_records": len(rows),
        "shadow_candidate_unique_tickers": len(unique_tickers),
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "top_candidate_tickers": by_ticker.most_common(12),
        "same_day_ab_overlap_count": same_day_overlap,
        "same_day_ab_overlap_rate": round(same_day_overlap / len(rows), 4) if rows else None,
        "ticker_history_ab_overlap_count": ticker_history_overlap,
        "ticker_history_ab_overlap_rate": round(ticker_history_overlap / len(rows), 4) if rows else None,
        "outside_production_candidate_count": len(outside_prod_rows),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_prod_rows}),
        "forward_return_distribution": _summarize_returns(rows),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(non_overlap_rows),
        "scarce_slot_proxy": _scarce_slot_proxy(rows, ab_by_date),
        "sample_candidates": [
            {
                "date": row["date"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "shadow_score": row["shadow_score"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "ticker_in_prior_ab_trades_or_signals": row["ticker_in_prior_ab_trades_or_signals"],
                "in_production_universe": row["in_production_universe"],
                "ab_touchpoint_day_rate": row["universe_stats"]["ab_touchpoint_day_rate"],
                "median_dollar_volume": row["universe_stats"]["median_dollar_volume"],
                "coverage_fraction": row["universe_stats"]["coverage_fraction"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
                "fwd_20d": row["fwd_20d"],
                "conditions": row["conditions"],
            }
            for row in rows[:30]
        ],
    }


def main() -> int:
    production_universe = _production_universe()
    ab_touchpoints, ab_tickers, ab_by_ticker, ab_by_date = _load_existing_ab_touchpoints()
    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            production_universe,
            ab_touchpoints,
            ab_tickers,
            ab_by_ticker,
            ab_by_date,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        scarce = summary["scarce_slot_proxy"]
        print(
            f"[{label}] universe={summary['shadow_universe_count']} "
            f"candidates={summary['shadow_candidate_records']} "
            f"unique={summary['shadow_candidate_unique_tickers']} "
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"candidate_days={scarce['candidate_days']} "
            f"ab_day_overlap={scarce['ab_candidate_day_overlap_rate']} "
            f"outside_prod={summary['outside_production_candidate_count']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "hypothesis": (
            "A liquidity-qualified undercut-and-reclaim reversal shadow source "
            "may surface scarce, replayable candidates with lower A/B same-day "
            "overlap and useful forward returns, distinct from recent "
            "continuation shadow sources and without changing production "
            "universe or strategy logic."
        ),
        "single_causal_variable": (
            "liquidity-qualified undercut-and-reclaim reversal shadow candidate definition"
        ),
        "shadow_candidate_source_definition": {
            "source": "existing OHLCV snapshots only; no production universe promotion",
            "liquidity_filters": {
                "excluded_etf_or_macro_proxies": sorted(ETF_OR_MACRO_PROXIES),
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            },
            "candidate_trigger": {
                "lookback_days": UNDERCUT_LOOKBACK_DAYS,
                "min_undercut_pct_below_prior_low": MIN_UNDERCUT_PCT,
                "min_reclaim_pct_above_prior_low": MIN_RECLAIM_PCT,
                "min_volume_ratio_vs_prior20": MIN_VOLUME_RATIO,
                "max_prior_5d_return": MIN_PRIOR_5D_PULLBACK_PCT,
                "min_close_location_in_daily_range": MIN_CLOSE_LOCATION,
                "requires_green_day": True,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "prior_rejected_or_limited_sources_considered": [
            "high-beta mid-cap and volatility-expansion universe scouts were observed-only and mostly inside the archived universe",
            "earnings-adjacent scout had primary-window snapshot coverage but weak forward returns",
            "pullback reclaim production-path replay was rejected after EV regressed in all windows",
            "inside-day, gap-and-hold, VCP, and sector-leadership continuation shadows were not promotion-ready",
        ],
        "survivorship_bias_risk": (
            "High. The fixed OHLCV snapshots contain only the archived repository "
            "ticker set, so this is a candidate-source audit inside available "
            "data rather than survivorship-free historical universe membership."
        ),
        "noise_risk": (
            "High. Undercut-and-reclaim patterns can be ordinary volatile noise; "
            "forward returns and scarce-slot proxy are descriptive only and do "
            "not justify production integration without replay and external "
            "universe evidence."
        ),
        "outside_production_limitations": [
            "Current OHLCV snapshots contain no tickers outside the archived repository universe.",
            "Outside-production candidate count is therefore expected to be zero unless new OHLCV sources are added.",
            "This scout evaluates one source definition; it does not add tickers to production.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "Observed-only ticket; acceptance protocol does not promote this source.",
            "Any follow-up would require production-path replay with real sizing, slot competition, and exits.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
