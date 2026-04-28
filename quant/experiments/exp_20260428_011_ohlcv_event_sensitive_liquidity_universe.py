"""exp-20260428-011 OHLCV event-sensitive liquidity-filtered universe scout.

Observed-only shadow evaluation. This script does not change the production
universe or shared strategy code.
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


EXPERIMENT_ID = "exp-20260428-011"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260428_011_ohlcv_event_sensitive_liquidity_universe.json",
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
MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0

MIN_ABS_EVENT_MOVE = 0.04
MIN_VOLUME_RATIO = 1.75
MIN_RANGE_VS_ATR = 1.20
MIN_CLOSE_LOCATION = 0.60
MAX_ATR_PCT = 0.10


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


def _load_existing_ab_context() -> tuple[set[tuple[str, str]], set[str], Counter, set[str]]:
    touchpoints: set[tuple[str, str]] = set()
    active_days: set[str] = set()
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
            entry_date = str(trade.get("entry_date") or "")[:10]
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, entry_date))
                active_days.add(entry_date)
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
                active_days.add(date_key)
                tickers.add(ticker)
                by_ticker[ticker] += 1
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
        "ab_touchpoint_days_all_archives": int(ab_by_ticker[ticker]),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
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
    out["close_to_close"] = out["Close"] / out["prev_close"] - 1
    intraday_range = (out["High"] - out["Low"]).replace(0, pd.NA)
    out["close_location"] = (out["Close"] - out["Low"]) / intraday_range
    out["momentum5"] = out["Close"] / out["Close"].shift(5) - 1
    out["momentum10"] = out["Close"] / out["Close"].shift(10) - 1
    out["spy_momentum10"] = spy["Close"] / spy["Close"].shift(10) - 1
    out["high20_prev"] = out["High"].shift(1).rolling(20).max()
    out["breakout20"] = out["Close"] >= out["high20_prev"]
    return out


def _event_signal(ticker: str, row: pd.Series) -> dict | None:
    required = [
        row.get("atr14"),
        row.get("atr_pct"),
        row.get("volume_ratio"),
        row.get("range_vs_atr"),
        row.get("close_to_close"),
        row.get("close_location"),
        row.get("momentum5"),
    ]
    if any(value is None or pd.isna(value) for value in required):
        return None
    if float(row["atr_pct"]) > MAX_ATR_PCT:
        return None

    event_move = float(row["close_to_close"])
    event_like = (
        abs(event_move) >= MIN_ABS_EVENT_MOVE
        and float(row["volume_ratio"]) >= MIN_VOLUME_RATIO
        and float(row["range_vs_atr"]) >= MIN_RANGE_VS_ATR
    )
    constructive_close = float(row["close_location"]) >= MIN_CLOSE_LOCATION
    follow_through_bias = float(row["momentum5"]) > 0 or bool(row.get("breakout20"))
    if not (event_like and constructive_close and follow_through_bias):
        return None

    spy_mom = 0.0 if pd.isna(row.get("spy_momentum10")) else float(row.get("spy_momentum10"))
    rs_positive = float(row.get("momentum10") or 0.0) > spy_mom
    shock_direction = "positive_repricing" if event_move > 0 else "constructive_recovery"
    score = (
        1.0
        + min(abs(event_move) - MIN_ABS_EVENT_MOVE, 0.12) * 4.0
        + min(float(row["volume_ratio"]) - MIN_VOLUME_RATIO, 3.0) * 0.12
        + min(float(row["range_vs_atr"]) - MIN_RANGE_VS_ATR, 2.0) * 0.10
        + (0.15 if rs_positive else 0.0)
        + (0.10 if bool(row.get("breakout20")) else 0.0)
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "shadow_score": round(score, 4),
        "shadow_event_proxy": shock_direction,
        "close": round(float(row["Close"]), 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "conditions": {
            "close_to_close_return": round(event_move, 6),
            "volume_ratio": round(float(row["volume_ratio"]), 4),
            "range_vs_atr": round(float(row["range_vs_atr"]), 4),
            "close_location": round(float(row["close_location"]), 4),
            "momentum_5d": round(float(row["momentum5"]), 6),
            "momentum_10d": round(float(row.get("momentum10") or 0.0), 6),
            "spy_10d_return": round(spy_mom, 6),
            "rs_positive": bool(rs_positive),
            "breakout_20d": bool(row.get("breakout20")),
            "atr_pct": round(float(row["atr_pct"]), 6),
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


def _scarce_slot_proxy(rows: list[dict], ab_active_days: set[str]) -> dict:
    candidate_days = sorted({row["date"] for row in rows})
    ab_activity_rows = [row for row in rows if row["date"] in ab_active_days]
    top_rows = []
    for day in candidate_days:
        day_rows = sorted(
            [row for row in rows if row["date"] == day],
            key=lambda item: (-item["shadow_score"], item["ticker"]),
        )
        top_rows.extend(day_rows[:5])
    return {
        "candidate_days": len(candidate_days),
        "ab_active_day_count": len({row["date"] for row in ab_activity_rows}),
        "ab_active_day_rate": (
            round(len({row["date"] for row in ab_activity_rows}) / len(candidate_days), 4)
            if candidate_days else None
        ),
        "same_ticker_same_day_overlap_count": sum(1 for row in rows if row["same_day_ab_overlap"]),
        "same_ticker_same_day_overlap_rate": (
            round(sum(1 for row in rows if row["same_day_ab_overlap"]) / len(rows), 4)
            if rows else None
        ),
        "top5_per_day_candidate_count": len(top_rows),
        "top5_per_day_fwd_10d": _summarize_returns(top_rows)["fwd_10d"],
        "all_candidate_fwd_10d": _summarize_returns(rows)["fwd_10d"],
        "scarce_slot_quality_note": (
            "Top-5-per-day forward returns are a scarce-slot proxy only; "
            "no portfolio sizing, fills, stops, or production slot replay ran."
        ),
    }


def _evaluate_window(
    label: str,
    cfg: dict,
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_tickers: set[str],
    ab_by_ticker: Counter,
    ab_active_days: set[str],
) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    expected = _expected_days(frames, cfg["start"], cfg["end"])
    spy = frames["SPY"]
    liquidity = {
        ticker: _ticker_liquidity(ticker, df, cfg["start"], cfg["end"], expected, ab_by_ticker)
        for ticker, df in frames.items()
    }
    selected = []
    rejected = Counter()
    for ticker, info in liquidity.items():
        if ticker in EXCLUDED_TICKERS:
            rejected["excluded_etf_or_macro_proxy"] += 1
            continue
        if not _passes_liquidity(info):
            rejected["failed_liquidity_or_coverage"] += 1
            continue
        selected.append(ticker)

    rows = []
    for ticker in sorted(selected):
        features = _add_features(frames[ticker], spy)
        window = features.loc[pd.Timestamp(cfg["start"]):pd.Timestamp(cfg["end"])]
        for _, row in window.iterrows():
            signal = _event_signal(ticker, row)
            if signal is None:
                continue
            signal.update(_forward_returns(frames[ticker], signal["date"]))
            signal["same_day_ab_overlap"] = (ticker, signal["date"]) in ab_touchpoints
            signal["ticker_in_prior_ab_trades_or_signals"] = ticker in ab_tickers
            signal["in_production_universe"] = ticker in production_universe
            signal["liquidity"] = liquidity[ticker]
            rows.append(signal)

    rows.sort(key=lambda item: (item["date"], -item["shadow_score"], item["ticker"]))
    unique_tickers = sorted({row["ticker"] for row in rows})
    outside_prod_rows = [row for row in rows if not row["in_production_universe"]]
    same_day_overlap_count = sum(1 for row in rows if row["same_day_ab_overlap"])
    ticker_history_overlap_count = sum(
        1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"]
    )
    by_sector = Counter(row["sector"] for row in rows)
    by_proxy = Counter(row["shadow_event_proxy"] for row in rows)
    dollar_volume_values = [row["liquidity"]["median_dollar_volume"] for row in rows]

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": len(metadata.get("tickers") or []),
        "expected_trading_days": expected,
        "liquid_shadow_universe_count": len(selected),
        "selection_rejections": dict(sorted(rejected.items())),
        "candidate_count": len(rows),
        "candidate_unique_tickers": len(unique_tickers),
        "candidate_tickers": unique_tickers,
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "candidate_count_by_event_proxy": dict(sorted(by_proxy.items())),
        "candidate_median_dollar_volume": _safe_median(dollar_volume_values),
        "same_day_ab_overlap_count": same_day_overlap_count,
        "same_day_ab_overlap_rate": round(same_day_overlap_count / len(rows), 4) if rows else None,
        "ticker_history_ab_overlap_count": ticker_history_overlap_count,
        "ticker_history_ab_overlap_rate": (
            round(ticker_history_overlap_count / len(rows), 4) if rows else None
        ),
        "outside_production_candidate_count": len(outside_prod_rows),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_prod_rows}),
        "forward_return_distribution": _summarize_returns(rows),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(
            [row for row in rows if not row["same_day_ab_overlap"]]
        ),
        "scarce_slot_proxy": _scarce_slot_proxy(rows, ab_active_days),
        "top_candidate_tickers": Counter(row["ticker"] for row in rows).most_common(12),
        "sample_candidates": [
            {
                "date": row["date"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "shadow_score": row["shadow_score"],
                "event_proxy": row["shadow_event_proxy"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "ticker_in_prior_ab_trades_or_signals": row["ticker_in_prior_ab_trades_or_signals"],
                "in_production_universe": row["in_production_universe"],
                "median_dollar_volume": row["liquidity"]["median_dollar_volume"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
                "fwd_20d": row["fwd_20d"],
                "conditions": row["conditions"],
            }
            for row in sorted(rows, key=lambda item: (-item["shadow_score"], item["date"]))[:40]
        ],
    }


def _aggregate(windows: list[dict]) -> dict:
    total_candidates = sum(w["candidate_count"] for w in windows)
    weighted_fwd = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        count = 0
        weighted_sum = 0.0
        win_sum = 0.0
        for w in windows:
            stats = w["forward_return_distribution"][key]
            stat_count = stats["count"] or 0
            if not stat_count or stats["avg"] is None:
                continue
            count += stat_count
            weighted_sum += stats["avg"] * stat_count
            if stats["win_rate"] is not None:
                win_sum += stats["win_rate"] * stat_count
        weighted_fwd[key] = {
            "count": count,
            "weighted_avg": round(weighted_sum / count, 6) if count else None,
            "weighted_win_rate": round(win_sum / count, 4) if count else None,
            "note": "Weighted from per-window summary metrics; quantiles remain in window sections.",
        }
    return {
        "candidate_count": total_candidates,
        "unique_tickers": sorted({ticker for w in windows for ticker in w["candidate_tickers"]}),
        "same_day_ab_overlap_rate_weighted": (
            round(
                sum(w["same_day_ab_overlap_count"] for w in windows) / total_candidates,
                4,
            )
            if total_candidates else None
        ),
        "outside_production_candidate_count": sum(
            w["outside_production_candidate_count"] for w in windows
        ),
        "sample_based_forward_returns": weighted_fwd,
    }


def main() -> int:
    production_universe = _production_universe()
    ab_touchpoints, ab_tickers, ab_by_ticker, ab_active_days = _load_existing_ab_context()
    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            production_universe,
            ab_touchpoints,
            ab_tickers,
            ab_by_ticker,
            ab_active_days,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        scarce = summary["scarce_slot_proxy"]["top5_per_day_fwd_10d"]
        print(
            f"[{label}] liquid={summary['liquid_shadow_universe_count']} "
            f"candidates={summary['candidate_count']} "
            f"unique={summary['candidate_unique_tickers']} "
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"outside_prod={summary['outside_production_candidate_count']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']} "
            f"top5_fwd10_avg={scarce['avg']}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "An OHLCV-event-sensitive liquidity-filtered shadow universe can "
            "produce replayable, low-overlap candidates across all fixed windows, "
            "avoiding the archived-news coverage gap in prior event scouts."
        ),
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "single_causal_variable": "OHLCV event-sensitive liquidity-filtered universe",
        "alpha_hypothesis": {
            "category": "universe_scout",
            "statement": (
                "Large price/volume repricing days can proxy event sensitivity when "
                "historical news archives are sparse, then reveal whether a broader "
                "event universe is worth sourcing externally."
            ),
            "why_not_production_now": (
                "This is a candidate-source audit. It has no survivorship-free external "
                "constituent history and no production slot-aware replay."
            ),
        },
        "shadow_universe_definition": {
            "source": "fixed OHLCV snapshots only; no production universe promotion",
            "liquidity_filters": {
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "excluded_tickers": sorted(EXCLUDED_TICKERS),
            },
            "event_proxy_trigger": {
                "abs_close_to_close_return_gte": MIN_ABS_EVENT_MOVE,
                "volume_ratio_gte": MIN_VOLUME_RATIO,
                "range_vs_atr_gte": MIN_RANGE_VS_ATR,
                "close_location_gte": MIN_CLOSE_LOCATION,
                "follow_through_bias": "5d momentum > 0 or 20d breakout",
                "max_atr_pct": MAX_ATR_PCT,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "bias_risks": [
            "Fixed OHLCV snapshots contain only archived repository tickers; outside-production discovery is structurally capped.",
            "The OHLCV event proxy does not know real news, earnings, guidance, or LLM semantic event quality.",
            "Forward returns are candidate-level marks, not fills, sizing, stops, or scarce-slot portfolio simulation.",
            "Thresholds are fixed for shadow measurement only and were not swept or promoted.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was allowed or attempted.",
            "Outside-production candidate count is expected to be zero with current snapshots.",
            "Promotion would require a separate ticket with external constituent/OHLCV coverage and Gate 4 replay.",
        ],
        "ab_context": {
            "ab_touchpoint_count": len(ab_touchpoints),
            "ab_ticker_count": len(ab_tickers),
            "ab_active_day_count": len(ab_active_days),
            "ab_by_ticker_top10": dict(ab_by_ticker.most_common(10)),
        },
        "aggregate": _aggregate(windows),
        "windows": windows,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
