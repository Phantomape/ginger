"""exp-20260426-031 earnings-adjacent shadow universe scout.

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


EXPERIMENT_ID = "exp-20260426-031"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_031_universe_scout_earnings_adjacent.json",
)
PRIOR_VOL_EXPANSION_ARTIFACT = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_025_universe_scout_volatility_expansion.json",
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
EARNINGS_DTE_MIN = 0
EARNINGS_DTE_MAX = 7
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


def _snapshot_date_key(name: str) -> str | None:
    raw = name.removeprefix("earnings_snapshot_").removesuffix(".json")
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
                touchpoints.add((ticker, entry_date))
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


def _liquidity_eligible(stats: dict) -> bool:
    return (
        stats["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and stats["median_dollar_volume"] is not None
        and stats["median_dollar_volume"] >= MIN_MEDIAN_DOLLAR_VOLUME
        and stats["median_close"] is not None
        and stats["median_close"] >= MIN_CLOSE
    )


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


def _earnings_snapshots(start: str, end: str) -> list[tuple[str, dict]]:
    data_dir = os.path.join(REPO_ROOT, "data")
    rows = []
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith("earnings_snapshot_") or not name.endswith(".json"):
            continue
        date_key = _snapshot_date_key(name)
        if date_key is None or date_key < start or date_key > end:
            continue
        try:
            rows.append((date_key, _load_json(os.path.join(data_dir, name))))
        except Exception:
            continue
    return rows


def _score_candidate(dte: int, avg_surprise: float | None, stats: dict) -> float:
    surprise_component = 0.0 if avg_surprise is None else max(min(avg_surprise, 40.0), -20.0) / 40.0
    proximity_component = (EARNINGS_DTE_MAX - dte + 1) / (EARNINGS_DTE_MAX + 1)
    liquidity_component = min(stats["median_dollar_volume"] / 250_000_000, 1.0)
    return round(0.45 * proximity_component + 0.35 * surprise_component + 0.20 * liquidity_component, 6)


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
    ticker_stats = {
        ticker: _ticker_stats(ticker, df, cfg["start"], cfg["end"], expected, ab_by_ticker)
        for ticker, df in frames.items()
        if ticker not in ETF_OR_MACRO_PROXIES
    }
    eligible_tickers = {
        ticker for ticker, stats in ticker_stats.items()
        if _liquidity_eligible(stats)
    }
    snapshots = _earnings_snapshots(cfg["start"], cfg["end"])
    rows = []
    raw_earnings_records = 0
    rejected = Counter()
    dte_counts = Counter()
    for date_key, snapshot in snapshots:
        earnings = snapshot.get("earnings") or {}
        for raw_ticker, info in earnings.items():
            ticker = str(raw_ticker).upper()
            raw_earnings_records += 1
            if ticker in ETF_OR_MACRO_PROXIES:
                rejected["etf_or_macro_proxy"] += 1
                continue
            if ticker not in frames:
                rejected["missing_ohlcv"] += 1
                continue
            if ticker not in eligible_tickers:
                rejected["failed_liquidity_or_coverage"] += 1
                continue
            dte = info.get("days_to_earnings")
            if dte is None:
                rejected["missing_days_to_earnings"] += 1
                continue
            dte = int(dte)
            if dte < EARNINGS_DTE_MIN or dte > EARNINGS_DTE_MAX:
                rejected["outside_dte_window"] += 1
                continue
            avg_surprise = info.get("avg_historical_surprise_pct")
            history = info.get("historical_surprise_pct")
            has_surprise_history = bool(history)
            stats = ticker_stats[ticker]
            dte_counts[dte] += 1
            row = {
                "date": date_key,
                "ticker": ticker,
                "sector": stats["sector"],
                "days_to_earnings": dte,
                "eps_estimate_present": info.get("eps_estimate") is not None,
                "eps_actual_last_present": info.get("eps_actual_last") is not None,
                "has_surprise_history": has_surprise_history,
                "avg_historical_surprise_pct": avg_surprise,
                "positive_avg_surprise": avg_surprise is not None and avg_surprise > 0,
                "shadow_score": _score_candidate(dte, avg_surprise, stats),
                "same_day_ab_overlap": (ticker, date_key) in ab_touchpoints,
                "ticker_in_prior_ab_trades_or_signals": ticker in ab_tickers,
                "in_production_universe": ticker in production_universe,
                "universe_stats": stats,
            }
            row.update(_forward_returns(frames[ticker], date_key))
            rows.append(row)

    rows.sort(key=lambda item: (-item["shadow_score"], item["date"], item["ticker"]))
    unique_tickers = sorted({row["ticker"] for row in rows})
    non_overlap_rows = [row for row in rows if not row["same_day_ab_overlap"]]
    outside_prod_rows = [row for row in rows if not row["in_production_universe"]]
    same_day_overlap = sum(1 for row in rows if row["same_day_ab_overlap"])
    ticker_history_overlap = sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"])
    by_sector = Counter(row["sector"] for row in rows)
    by_ticker = Counter(row["ticker"] for row in rows)
    coverage_fields = {
        "eps_estimate_present_rate": round(
            sum(1 for row in rows if row["eps_estimate_present"]) / len(rows), 4
        ) if rows else None,
        "eps_actual_last_present_rate": round(
            sum(1 for row in rows if row["eps_actual_last_present"]) / len(rows), 4
        ) if rows else None,
        "surprise_history_present_rate": round(
            sum(1 for row in rows if row["has_surprise_history"]) / len(rows), 4
        ) if rows else None,
        "positive_avg_surprise_rate": round(
            sum(1 for row in rows if row["positive_avg_surprise"]) / len(rows), 4
        ) if rows else None,
    }

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": len(metadata.get("tickers") or []),
        "expected_trading_days": expected,
        "earnings_snapshot_days": len(snapshots),
        "raw_earnings_records": raw_earnings_records,
        "liquidity_eligible_tickers": sorted(eligible_tickers),
        "liquidity_eligible_ticker_count": len(eligible_tickers),
        "shadow_universe_tickers": unique_tickers,
        "shadow_universe_count": len(unique_tickers),
        "selection_rejections": dict(sorted(rejected.items())),
        "dte_candidate_counts": {str(k): v for k, v in sorted(dte_counts.items())},
        "shadow_universe_stats": {ticker: ticker_stats[ticker] for ticker in unique_tickers},
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
        "earnings_field_coverage": coverage_fields,
        "forward_return_distribution": _summarize_returns(rows),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(non_overlap_rows),
        "sample_candidates": [
            {
                "date": row["date"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "days_to_earnings": row["days_to_earnings"],
                "shadow_score": row["shadow_score"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "ticker_in_prior_ab_trades_or_signals": row["ticker_in_prior_ab_trades_or_signals"],
                "in_production_universe": row["in_production_universe"],
                "avg_historical_surprise_pct": row["avg_historical_surprise_pct"],
                "positive_avg_surprise": row["positive_avg_surprise"],
                "ab_touchpoint_day_rate": row["universe_stats"]["ab_touchpoint_day_rate"],
                "median_dollar_volume": row["universe_stats"]["median_dollar_volume"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
            }
            for row in rows[:30]
        ],
    }


def _prior_vol_expansion_summary() -> dict | None:
    if not os.path.exists(PRIOR_VOL_EXPANSION_ARTIFACT):
        return None
    payload = _load_json(PRIOR_VOL_EXPANSION_ARTIFACT)
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
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"outside_prod={summary['outside_production_candidate_count']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "hypothesis": (
            "A liquidity-filtered earnings-adjacent shadow universe may surface "
            "event-sensitive candidates with lower A/B overlap and better "
            "forward-return quality than the rejected volatility-expansion "
            "shadow universe, without changing production universe or strategy logic."
        ),
        "single_causal_variable": "earnings-adjacent liquidity-filtered shadow universe definition",
        "shadow_universe_definition": {
            "source": (
                "existing earnings_snapshot_YYYYMMDD.json files joined to fixed "
                "OHLCV snapshots; no production universe promotion"
            ),
            "filters": {
                "excluded_etf_or_macro_proxies": sorted(ETF_OR_MACRO_PROXIES),
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "days_to_earnings_min": EARNINGS_DTE_MIN,
                "days_to_earnings_max": EARNINGS_DTE_MAX,
            },
            "shadow_candidate_trigger": (
                "Any liquidity-qualified ticker with replayable OHLCV and archived "
                f"earnings snapshot days_to_earnings in [{EARNINGS_DTE_MIN}, "
                f"{EARNINGS_DTE_MAX}]. Surprise history is measured and scored, "
                "not used as a hard promotion rule."
            ),
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "prior_volatility_expansion_summary": _prior_vol_expansion_summary(),
        "survivorship_bias_risk": (
            "High. The fixed OHLCV snapshots and earnings snapshots contain only "
            "the archived repository ticker set. This evaluates an earnings-adjacent "
            "candidate source inside available data, not survivorship-free historical "
            "universe membership."
        ),
        "outside_production_limitations": [
            "Current OHLCV snapshots contain no tickers outside the archived repository universe.",
            "Outside-production candidate count is therefore expected to be zero unless new OHLCV sources are added.",
            "This scout can evaluate source quality and overlap but cannot justify production promotion by itself.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "A shadow universe must improve scarce-slot candidate quality, not merely increase candidate count.",
            "A survivorship-aware external earnings universe source is still needed before promotion.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
