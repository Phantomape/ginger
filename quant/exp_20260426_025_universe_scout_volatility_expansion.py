"""exp-20260426-025 low-overlap volatility-expansion universe scout.

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


EXPERIMENT_ID = "exp-20260426-025"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_025_universe_scout_volatility_expansion.json",
)
PRIOR_HIGH_BETA_ARTIFACT = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_019_universe_scout_high_beta_midcap.json",
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
MIN_LOW_OVERLAP_AB_DAY_RATE = 0.04
MIN_ATR_EXPANSION_RATIO = 1.20
MIN_VOLUME_RATIO = 1.30
MIN_DAILY_RANGE_VS_ATR = 1.15
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


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str], Counter]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
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
                point = (ticker, entry_date)
                touchpoints.add(point)
                tickers.add(ticker)
                by_ticker[ticker] += 1

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
    return touchpoints, tickers, by_ticker


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


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_close"] = out["Close"].shift(1)
    ranges = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - out["prev_close"]).abs(),
        (out["Low"] - out["prev_close"]).abs(),
    ], axis=1)
    out["atr14"] = ranges.max(axis=1).rolling(14).mean()
    out["atr14_median60"] = out["atr14"].shift(1).rolling(60).median()
    out["atr_expansion_ratio"] = out["atr14"] / out["atr14_median60"]
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    out["daily_range_vs_atr"] = (out["High"] - out["Low"]) / out["atr14"]
    out["momentum5"] = out["Close"] / out["Close"].shift(5) - 1
    out["momentum10"] = out["Close"] / out["Close"].shift(10) - 1
    out["spy_momentum10"] = spy["Close"] / spy["Close"].shift(10) - 1
    out["high20_prev"] = out["High"].shift(1).rolling(20).max()
    out["high60_prev"] = out["High"].shift(1).rolling(60).max()
    out["ma200"] = out["Close"].rolling(200).mean()
    out["breakout20"] = out["Close"] >= out["high20_prev"]
    out["near_high60"] = out["Close"] >= out["high60_prev"] * 0.97
    out["above200"] = out["Close"] > out["ma200"]
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
        if info["coverage_fraction"] < MIN_COVERAGE_FRACTION:
            rejected["insufficient_coverage"] += 1
            continue
        if (info["median_dollar_volume"] or 0.0) < MIN_MEDIAN_DOLLAR_VOLUME:
            rejected["insufficient_liquidity"] += 1
            continue
        if (info["median_close"] or 0.0) < MIN_CLOSE:
            rejected["low_price"] += 1
            continue
        if (info["ab_touchpoint_day_rate"] or 0.0) > MIN_LOW_OVERLAP_AB_DAY_RATE:
            rejected["prior_ab_overlap_too_high"] += 1
            continue
        selected.append(ticker)
    selected.sort()
    return selected, stats, rejected


def _signal_for_row(ticker: str, row: pd.Series) -> dict | None:
    fields = [
        row.get("atr14"),
        row.get("atr_expansion_ratio"),
        row.get("volume_ratio"),
        row.get("daily_range_vs_atr"),
        row.get("momentum10"),
    ]
    if any(value is None or pd.isna(value) for value in fields):
        return None
    close = float(row["Close"])
    atr_pct = float(row["atr14"]) / close if close else 1.0
    if close <= 0 or atr_pct > 0.09:
        return None

    vol_expands = float(row["atr_expansion_ratio"]) >= MIN_ATR_EXPANSION_RATIO
    volume_confirms = float(row["volume_ratio"]) >= MIN_VOLUME_RATIO
    range_confirms = float(row["daily_range_vs_atr"]) >= MIN_DAILY_RANGE_VS_ATR
    upward_bias = float(row["momentum10"]) > 0 or bool(row.get("breakout20"))
    spy_mom = 0.0 if pd.isna(row.get("spy_momentum10")) else float(row.get("spy_momentum10"))
    rs_positive = float(row["momentum10"]) > spy_mom
    near_high = bool(row.get("near_high60"))
    above200 = bool(row.get("above200"))

    if not (vol_expands and volume_confirms and range_confirms and upward_bias):
        return None

    score = (
        1.0
        + min(float(row["atr_expansion_ratio"]) - MIN_ATR_EXPANSION_RATIO, 1.5) * 0.30
        + min(float(row["volume_ratio"]) - MIN_VOLUME_RATIO, 2.0) * 0.15
        + (0.20 if rs_positive else 0.0)
        + (0.15 if near_high else 0.0)
        + (0.10 if above200 else 0.0)
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "strategy_proxy": "volatility_expansion_long",
        "shadow_score": round(score, 4),
        "close": round(close, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "conditions": {
            "atr_expansion_ratio": round(float(row["atr_expansion_ratio"]), 4),
            "volume_ratio": round(float(row["volume_ratio"]), 4),
            "daily_range_vs_atr": round(float(row["daily_range_vs_atr"]), 4),
            "momentum_10d_pct": round(float(row["momentum10"]), 6),
            "spy_10d_return": round(spy_mom, 6),
            "rs_positive": rs_positive,
            "breakout_20d": bool(row.get("breakout20")),
            "near_high60": near_high,
            "above_200ma": above200,
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


def _evaluate_window(
    label: str,
    cfg: dict,
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_tickers: set[str],
    ab_by_ticker: Counter,
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
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
                "conditions": row["conditions"],
            }
            for row in rows[:30]
        ],
    }


def _prior_high_beta_summary() -> dict | None:
    if not os.path.exists(PRIOR_HIGH_BETA_ARTIFACT):
        return None
    payload = _load_json(PRIOR_HIGH_BETA_ARTIFACT)
    summary = {}
    for window in payload.get("windows") or []:
        label = window["window"]
        fwd10 = window["forward_return_distribution"]["fwd_10d"]
        summary[label] = {
            "shadow_universe_count": window["shadow_universe_count"],
            "shadow_candidate_records": window["shadow_candidate_records"],
            "same_day_ab_overlap_rate": window["same_day_ab_overlap_rate"],
            "outside_production_candidate_count": window["outside_production_candidate_count"],
            "fwd_10d_avg": fwd10["avg"],
            "fwd_10d_win_rate": fwd10["win_rate"],
        }
    return summary


def main() -> int:
    production_universe = _production_universe()
    ab_touchpoints, ab_tickers, ab_by_ticker = _load_existing_ab_touchpoints()
    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            production_universe,
            ab_touchpoints,
            ab_tickers,
            ab_by_ticker,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        print(
            f"[{label}] universe={summary['shadow_universe_count']} "
            f"candidates={summary['shadow_candidate_records']} "
            f"unique={summary['shadow_candidate_unique_tickers']} "
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"outside_prod={summary['outside_production_candidate_count']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "hypothesis": (
            "A low-overlap volatility-expansion shadow universe can identify "
            "OHLCV-replayable candidates with better non-overlap and "
            "forward-return quality than the prior high-beta mid-cap proxy, "
            "without changing production universe or strategy logic."
        ),
        "single_causal_variable": "low-overlap volatility-expansion shadow universe definition",
        "shadow_universe_definition": {
            "source": "existing OHLCV snapshots only; no production universe promotion",
            "filters": {
                "excluded_etf_or_macro_proxies": sorted(ETF_OR_MACRO_PROXIES),
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "max_ab_touchpoint_day_rate": MIN_LOW_OVERLAP_AB_DAY_RATE,
            },
            "shadow_candidate_trigger": (
                "Volatility expansion in shadow mode only: ATR14 at least "
                f"{MIN_ATR_EXPANSION_RATIO}x its prior 60d median, same-day "
                f"volume at least {MIN_VOLUME_RATIO}x prior 20d average, "
                f"range at least {MIN_DAILY_RANGE_VS_ATR}x ATR, plus positive "
                "10d momentum or a 20d breakout."
            ),
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "prior_high_beta_proxy_summary": _prior_high_beta_summary(),
        "survivorship_bias_risk": (
            "High. The repository snapshots contain only the archived ticker set. "
            "This is a low-overlap definition inside available snapshots, not a "
            "survivorship-free historical universe membership test."
        ),
        "outside_production_limitations": [
            "Current OHLCV snapshots contain no tickers outside the archived repository universe.",
            "Outside-production candidate count is therefore expected to be zero unless new OHLCV sources are added.",
            "This scout can rank candidate source quality but cannot justify production promotion by itself.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "A shadow universe must beat scarce-slot alternatives, not merely produce more rows.",
            "A survivorship-aware external candidate source is still needed before production promotion.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
