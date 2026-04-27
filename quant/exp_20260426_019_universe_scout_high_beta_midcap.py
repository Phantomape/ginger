"""exp-20260426-021 high-beta mid-cap shadow universe scout.

Observed-only evaluation. This script does not change the production universe
or shared strategy code.
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


EXPERIMENT_ID = "exp-20260426-021"
OUT_JSON = os.path.join(
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

# Explicitly record the proxy nature of "mid-cap": the repo snapshots do not
# include historical market-cap data, so this basket uses a deterministic
# non-mega-cap/event-sensitive proxy list plus measured beta/liquidity gates.
MIDCAP_PROXY_TICKERS = {
    "APP", "COIN", "CRDO", "DDOG", "PLTR", "SNOW", "SPOT", "TRIP",
}

MIN_BETA_VS_SPY = 1.25
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0
MIN_COVERAGE_FRACTION = 0.95
MIN_BETA_OBSERVATIONS = 60
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
        df = df.set_index("Date").sort_index()
        frames[ticker.upper()] = df
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
        idx = int(round((len(clean) - 1) * q))
        return round(clean[idx], 6)

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


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str]]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
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
    return touchpoints, tickers


def _ticker_stats(
    ticker: str,
    df: pd.DataFrame,
    spy: pd.DataFrame,
    start: str,
    end: str,
    expected_days: int,
) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "ticker": ticker,
            "coverage_days": 0,
            "coverage_fraction": 0.0,
            "median_dollar_volume": None,
            "median_close": None,
            "beta_vs_spy": None,
            "beta_observations": 0,
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    returns = df["Close"].astype(float).pct_change()
    spy_returns = spy["Close"].astype(float).pct_change()
    aligned = pd.concat([returns, spy_returns], axis=1, join="inner").dropna()
    aligned = aligned.loc[:pd.Timestamp(end)]
    beta = None
    if len(aligned) >= MIN_BETA_OBSERVATIONS and aligned.iloc[:, 1].var() > 0:
        beta = aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / aligned.iloc[:, 1].var()
    coverage_fraction = len(window) / expected_days if expected_days else 0.0
    return {
        "ticker": ticker,
        "coverage_days": int(len(window)),
        "coverage_fraction": round(coverage_fraction, 4),
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
        "beta_vs_spy": round(float(beta), 4) if beta is not None else None,
        "beta_observations": int(len(aligned)),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
    }


def _select_shadow_universe(
    frames: dict[str, pd.DataFrame],
    start: str,
    end: str,
    expected_days: int,
) -> tuple[list[str], dict[str, dict], Counter]:
    spy = frames["SPY"]
    stats = {
        ticker: _ticker_stats(ticker, df, spy, start, end, expected_days)
        for ticker, df in frames.items()
    }
    selected = []
    rejected = Counter()
    for ticker, info in stats.items():
        if ticker in ETF_OR_MACRO_PROXIES:
            rejected["etf_or_macro_proxy"] += 1
            continue
        if ticker not in MIDCAP_PROXY_TICKERS:
            rejected["not_midcap_proxy_list"] += 1
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
        if info["beta_vs_spy"] is None or info["beta_vs_spy"] < MIN_BETA_VS_SPY:
            rejected["beta_below_threshold"] += 1
            continue
        selected.append(ticker)
    selected.sort()
    return selected, stats, rejected


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_close"] = out["Close"].shift(1)
    ranges = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - out["prev_close"]).abs(),
        (out["Low"] - out["prev_close"]).abs(),
    ], axis=1)
    out["atr14"] = ranges.max(axis=1).rolling(14).mean()
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    out["high20_prev"] = out["High"].shift(1).rolling(20).max()
    out["high252_prev"] = out["High"].shift(1).rolling(252).max()
    out["ma200"] = out["Close"].rolling(200).mean()
    out["momentum10"] = out["Close"] / out["Close"].shift(10) - 1
    out["spy_momentum10"] = spy["Close"] / spy["Close"].shift(10) - 1
    out["breakout20"] = out["Close"] >= out["high20_prev"]
    out["above200"] = out["Close"] > out["ma200"]
    out["daily_range_vs_atr"] = (out["High"] - out["Low"]) / out["atr14"]
    out["pct_from_52w_high"] = out["Close"] / out["high252_prev"] - 1
    return out


def _confidence(checks: list[tuple[bool, float]]) -> float:
    denom = sum(weight for _, weight in checks)
    if denom <= 0:
        return 0.0
    numer = sum(weight for ok, weight in checks if ok)
    return round(numer / denom, 4)


def _signal_for_row(ticker: str, row: pd.Series) -> dict | None:
    close = float(row["Close"])
    atr = row.get("atr14")
    if not close or pd.isna(atr) or atr <= 0 or atr / close > 0.07:
        return None
    if row.get("momentum10") is None or pd.isna(row.get("momentum10")):
        return None
    if float(row.get("momentum10")) < 0:
        return None

    breakout = bool(row.get("breakout20"))
    above200 = bool(row.get("above200"))
    vol_ratio = row.get("volume_ratio")
    range_vs_atr = row.get("daily_range_vs_atr")
    pct_from_high = row.get("pct_from_52w_high")
    near_high = bool(not pd.isna(pct_from_high) and pct_from_high > -0.05)
    spy_mom = 0.0 if pd.isna(row.get("spy_momentum10")) else float(row.get("spy_momentum10"))
    rs_strong = bool(float(row.get("momentum10")) > spy_mom * 1.2)

    candidates = []
    if above200 and breakout and not pd.isna(vol_ratio) and float(vol_ratio) > 2.0:
        confidence = _confidence([
            (above200, 1.0),
            (breakout, 1.0),
            (True, 1.0),
            (rs_strong, 0.40),
            (near_high, 0.40),
        ])
        candidates.append(("trend_long", confidence))

    if (
        breakout
        and not pd.isna(vol_ratio)
        and not pd.isna(range_vs_atr)
        and float(range_vs_atr) > 1.5
        and float(vol_ratio) > 1.5
    ):
        above200_bonus = above200
        confidence = _confidence([
            (True, 1.0),
            (breakout, 1.0),
            (True, 1.0),
            (rs_strong, 0.25),
            (near_high, 0.25),
            (above200_bonus, 0.25),
        ])
        candidates.append(("breakout_long", confidence))

    if not candidates:
        return None
    strategy, confidence = sorted(candidates, key=lambda item: item[1], reverse=True)[0]
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "strategy": strategy,
        "confidence_score": confidence,
        "close": round(close, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "conditions": {
            "above_200ma": above200,
            "breakout_20d": breakout,
            "volume_ratio": round(float(vol_ratio), 4) if not pd.isna(vol_ratio) else None,
            "daily_range_vs_atr": round(float(range_vs_atr), 4) if not pd.isna(range_vs_atr) else None,
            "momentum_10d_pct": round(float(row.get("momentum10")), 6),
            "spy_10d_return": round(spy_mom, 6),
            "pct_from_52w_high": round(float(pct_from_high), 6) if not pd.isna(pct_from_high) else None,
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
) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    expected = _expected_days(frames, cfg["start"], cfg["end"])
    shadow_universe, ticker_stats, rejected = _select_shadow_universe(
        frames,
        cfg["start"],
        cfg["end"],
        expected,
    )
    spy_features = frames["SPY"]
    rows = []
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

    rows.sort(key=lambda item: (item["date"], item["ticker"], item["strategy"]))
    unique_tickers = sorted({row["ticker"] for row in rows})
    non_overlap_rows = [row for row in rows if not row["same_day_ab_overlap"]]
    outside_prod_rows = [row for row in rows if not row["in_production_universe"]]
    same_day_overlap = sum(1 for row in rows if row["same_day_ab_overlap"])
    ticker_history_overlap = sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"])
    by_strategy = Counter(row["strategy"] for row in rows)
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
        "candidate_count_by_strategy": dict(sorted(by_strategy.items())),
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
                "strategy": row["strategy"],
                "sector": row["sector"],
                "confidence_score": row["confidence_score"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "ticker_in_prior_ab_trades_or_signals": row["ticker_in_prior_ab_trades_or_signals"],
                "in_production_universe": row["in_production_universe"],
                "beta_vs_spy": row["universe_stats"]["beta_vs_spy"],
                "median_dollar_volume": row["universe_stats"]["median_dollar_volume"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
            }
            for row in rows[:30]
        ],
    }


def main() -> int:
    production_universe = _production_universe()
    ab_touchpoints, ab_tickers = _load_existing_ab_touchpoints()
    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            production_universe,
            ab_touchpoints,
            ab_tickers,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        print(
            f"[{label}] universe={summary['shadow_universe_count']} "
            f"candidates={summary['shadow_candidate_records']} "
            f"unique={summary['shadow_candidate_unique_tickers']} "
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "hypothesis": (
            "A liquidity-filtered high-beta mid-cap shadow universe can provide "
            "non-overlapping OHLCV-replayable candidates outside the current "
            "accepted A/B universe without relying on sparse archived news coverage."
        ),
        "single_causal_variable": "liquidity-filtered high-beta mid-cap shadow universe definition",
        "shadow_universe_definition": {
            "source": "existing OHLCV snapshots only; no production universe promotion",
            "midcap_proxy_tickers": sorted(MIDCAP_PROXY_TICKERS),
            "excluded_etf_or_macro_proxies": sorted(ETF_OR_MACRO_PROXIES),
            "filters": {
                "min_beta_vs_spy": MIN_BETA_VS_SPY,
                "min_beta_observations": MIN_BETA_OBSERVATIONS,
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            },
            "shadow_candidate_trigger": (
                "A/B-like OHLCV technical triggers in shadow mode only: "
                "trend_long style 200MA+20d breakout+2.0x volume, or "
                "breakout_long style 1.5 ATR range+20d breakout+1.5x volume."
            ),
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "survivorship_bias_risk": (
            "High. The repository snapshots contain only the already archived ticker set, "
            "and no historical market-cap snapshots are available. The 'mid-cap' label is "
            "therefore a deterministic proxy list evaluated with measured beta/liquidity, "
            "not a survivorship-free historical index membership test."
        ),
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "A shadow universe must show scarce-slot candidate quality, not merely more candidates.",
            "The current snapshots do not provide a survivorship-free historical mid-cap source.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
