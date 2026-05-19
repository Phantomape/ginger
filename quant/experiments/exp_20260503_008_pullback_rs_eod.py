"""Cross-sectional EOD pullback-in-uptrend alpha research.

Observed-only experiment. It reads existing point-in-time OHLCV snapshots and
does not change production signal, risk, universe, or backtester behavior.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260503-008"
STRATEGY_NAME = "pullback_rs_eod"
RUN_TS = datetime.now(timezone.utc)
RUN_STAMP = RUN_TS.strftime("%Y%m%d_%H%M")

WINDOWS = OrderedDict([
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
])

HORIZONS = [5, 10, 20, 60]
COSTS_BPS = [0, 35, 70]
MIN_HISTORY_DAYS = 80
MIN_CLOSE = 5.0
MIN_ADV20 = 20_000_000
EXCLUDED_SECTORS = {"ETF", "Commodities"}
EXCLUDED_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV", "GDX", "USO", "UUP", "XLE", "XLP", "XLU", "XLV", "IEF", "TLT"}
VARIANTS = OrderedDict([
    ("pullback_rs_60_5", "z_ret_60d_minus_z_ret_5d"),
    ("momentum_60", "z_ret_60d"),
    ("reversal_5", "negative_z_ret_5d"),
])

EXP_DIR = os.path.join(REPO_ROOT, "experiments", "research", STRATEGY_NAME)
LOG_DIR = os.path.join(REPO_ROOT, "experiments", "research", STRATEGY_NAME, "logs")
DATA_EXP_DIR = os.path.join(REPO_ROOT, "data", "experiments", EXPERIMENT_ID)
DOC_LOG = os.path.join(REPO_ROOT, "docs", "experiment_log.jsonl")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_frames(snapshot_path: str) -> tuple[dict[str, pd.DataFrame], dict]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    frames: dict[str, pd.DataFrame] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        sector = SECTOR_MAP.get(ticker.upper(), "Unknown")
        if ticker.upper() in EXCLUDED_TICKERS or sector in EXCLUDED_SECTORS:
            continue
        df = pd.DataFrame(rows)
        if df.empty or not {"Date", "Close", "Volume"}.issubset(df.columns):
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
        frames[ticker.upper()] = df.dropna(subset=["Close", "Volume"])
    return frames, payload.get("metadata") or {}


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(mean(clean), 6) if clean else None


def _max_drawdown(returns: list[float], horizon: int) -> float | None:
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret in returns:
        # Forward returns overlap because the portfolio is re-ranked daily.
        # Use a per-day equivalent return as a drawdown proxy instead of
        # compounding each full horizon label as if it were a daily P&L.
        daily_ret = (1.0 + ret) ** (1.0 / horizon) - 1.0 if ret > -1.0 else -1.0
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, equity / peak - 1.0)
    return round(max_dd, 6)


def _bucket_rows(day: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = day.sort_values("score", ascending=False)
    n = len(ranked)
    k = max(1, int(math.ceil(n * 0.10)))
    return ranked.head(k), ranked.tail(k)


def _spearman_by_date(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    rows = []
    fwd_col = f"fwd_{horizon}d"
    for date, day in panel.groupby("date"):
        clean = day[["score", fwd_col]].dropna()
        if len(clean) < 5:
            continue
        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "rank_ic": round(float(clean["score"].corr(clean[fwd_col], method="spearman")), 6),
            "n": int(len(clean)),
        })
    return pd.DataFrame(rows)


def _coverage(frames: dict[str, pd.DataFrame], start: str, end: str) -> dict:
    rows = []
    for ticker, df in frames.items():
        window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
        if window.empty:
            continue
        adv20 = (window["Close"] * window["Volume"]).rolling(20).mean()
        rows.append({
            "ticker": ticker,
            "days": int(len(window)),
            "median_close": round(float(window["Close"].median()), 4),
            "median_adv20": round(float(adv20.median()), 2) if not adv20.dropna().empty else None,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
        })
    return {
        "ticker_count": len(rows),
        "sectors": dict(Counter(row["sector"] for row in rows)),
        "liquid_count": sum(
            1 for row in rows
            if row["days"] >= MIN_HISTORY_DAYS
            and row["median_close"] >= MIN_CLOSE
            and (row["median_adv20"] or 0) >= MIN_ADV20
        ),
    }


def _build_panel(frames: dict[str, pd.DataFrame], start: str, end: str, variant: str) -> pd.DataFrame:
    records = []
    for ticker, df in frames.items():
        work = df.copy()
        work["ret_5d"] = work["Close"].pct_change(5)
        work["ret_20d"] = work["Close"].pct_change(20)
        work["ret_60d"] = work["Close"].pct_change(60)
        work["adv20"] = (work["Close"] * work["Volume"]).rolling(20).mean()
        work["vol20"] = work["Close"].pct_change().rolling(20).std()
        for horizon in HORIZONS:
            work[f"fwd_{horizon}d"] = work["Close"].shift(-horizon) / work["Close"] - 1.0
        window = work.loc[pd.Timestamp(start):pd.Timestamp(end)].copy()
        window = window[
            (window["Close"] >= MIN_CLOSE)
            & (window["adv20"] >= MIN_ADV20)
            & window["ret_5d"].notna()
            & window["ret_60d"].notna()
        ]
        if window.empty:
            continue
        for date, row in window.iterrows():
            rec = {
                "date": date,
                "ticker": ticker,
                "sector": SECTOR_MAP.get(ticker, "Unknown"),
                "close": float(row["Close"]),
                "adv20": float(row["adv20"]),
                "ret_5d": float(row["ret_5d"]),
                "ret_20d": float(row["ret_20d"]),
                "ret_60d": float(row["ret_60d"]),
                "vol20": float(row["vol20"]) if not pd.isna(row["vol20"]) else None,
            }
            for horizon in HORIZONS:
                value = row.get(f"fwd_{horizon}d")
                rec[f"fwd_{horizon}d"] = float(value) if not pd.isna(value) else None
            records.append(rec)
    panel = pd.DataFrame(records)
    if panel.empty:
        return panel
    scored = []
    for _, day in panel.groupby("date"):
        day = day.copy()
        if len(day) < 10:
            continue
        z60 = (day["ret_60d"] - day["ret_60d"].mean()) / day["ret_60d"].std(ddof=0)
        z5 = (day["ret_5d"] - day["ret_5d"].mean()) / day["ret_5d"].std(ddof=0)
        if variant == "pullback_rs_60_5":
            day["score"] = z60 - z5
        elif variant == "momentum_60":
            day["score"] = z60
        elif variant == "reversal_5":
            day["score"] = -z5
        else:
            raise ValueError(f"Unknown variant: {variant}")
        day = day.replace([math.inf, -math.inf], pd.NA).dropna(subset=["score"])
        scored.append(day)
    return pd.concat(scored, ignore_index=True) if scored else pd.DataFrame()


def _evaluate_panel(panel: pd.DataFrame, window_name: str, variant: str, cost_bps: int) -> tuple[list[dict], pd.DataFrame]:
    rows = []
    rank_ic_frames = []
    cost = cost_bps / 10_000.0
    for horizon in HORIZONS:
        fwd_col = f"fwd_{horizon}d"
        rank_ic = _spearman_by_date(panel, horizon)
        if not rank_ic.empty:
            rank_ic["window"] = window_name
            rank_ic["variant"] = variant
            rank_ic["horizon"] = horizon
            rank_ic_frames.append(rank_ic)

        top_rets = []
        bottom_rets = []
        spreads = []
        hit_values = []
        top_holdings_by_day = []
        sector_counter: Counter = Counter()
        top_size = []
        all_size = []
        top_liq = []
        all_liq = []
        score_size_pairs = []
        score_liq_pairs = []

        for _, day in panel.groupby("date"):
            clean = day.dropna(subset=["score", fwd_col])
            if len(clean) < 10:
                continue
            top, bottom = _bucket_rows(clean)
            top_ret = float(top[fwd_col].mean()) - cost
            bottom_ret = float(bottom[fwd_col].mean()) - cost
            top_rets.append(top_ret)
            bottom_rets.append(bottom_ret)
            spreads.append(top_ret - bottom_ret)
            hit_values.append(1.0 if top_ret > bottom_ret else 0.0)
            top_holdings_by_day.append(set(top["ticker"]))
            sector_counter.update(top["sector"].tolist())
            top_size.extend(top["close"].astype(float).tolist())
            all_size.extend(clean["close"].astype(float).tolist())
            top_liq.extend(top["adv20"].astype(float).tolist())
            all_liq.extend(clean["adv20"].astype(float).tolist())
            for item in clean[["score", "close", "adv20"]].itertuples(index=False):
                score_size_pairs.append((float(item.score), math.log(float(item.close))))
                score_liq_pairs.append((float(item.score), math.log(float(item.adv20))))

        turnover_values = []
        for prev, cur in zip(top_holdings_by_day, top_holdings_by_day[1:]):
            if cur:
                turnover_values.append(1.0 - len(prev & cur) / len(cur))

        def _corr(pairs: list[tuple[float, float]]) -> float | None:
            if len(pairs) < 5:
                return None
            df = pd.DataFrame(pairs, columns=["score", "x"])
            return round(float(df["score"].corr(df["x"], method="spearman")), 6)

        sector_total = sum(sector_counter.values())
        rows.append({
            "window": window_name,
            "variant": variant,
            "horizon": horizon,
            "cost_bps": cost_bps,
            "rank_ic_mean": _safe_mean(rank_ic["rank_ic"].tolist()) if not rank_ic.empty else None,
            "rank_ic_positive_rate": round(float((rank_ic["rank_ic"] > 0).mean()), 6) if not rank_ic.empty else None,
            "rank_ic_dates": int(len(rank_ic)),
            "top_bucket_return_mean": _safe_mean(top_rets),
            "bottom_bucket_return_mean": _safe_mean(bottom_rets),
            "top_bottom_spread_mean": _safe_mean(spreads),
            "top_bottom_hit_rate": _safe_mean(hit_values),
            "top_bucket_max_drawdown": _max_drawdown(top_rets, horizon),
            "spread_max_drawdown": _max_drawdown(spreads, horizon),
            "turnover_mean": _safe_mean(turnover_values),
            "sector_exposure_top": json.dumps(
                {k: round(v / sector_total, 4) for k, v in sector_counter.most_common()},
                sort_keys=True,
            ) if sector_total else "{}",
            "top_avg_close": _safe_mean(top_size),
            "universe_avg_close": _safe_mean(all_size),
            "top_avg_adv20": _safe_mean(top_liq),
            "universe_avg_adv20": _safe_mean(all_liq),
            "score_size_spearman": _corr(score_size_pairs),
            "score_liquidity_spearman": _corr(score_liq_pairs),
            "observations": int(panel[fwd_col].notna().sum()),
        })
    rank_ic_by_date = pd.concat(rank_ic_frames, ignore_index=True) if rank_ic_frames else pd.DataFrame()
    return rows, rank_ic_by_date


def _write_config() -> None:
    os.makedirs(EXP_DIR, exist_ok=True)
    lines = [
        f"experiment_id: {EXPERIMENT_ID}",
        f"strategy_name: {STRATEGY_NAME}",
        "hypothesis: >",
        "  Stocks with strong 60-day cross-sectional momentum but weak recent 5-day",
        "  returns may show better 5/10/20/60-day relative forward returns than",
        "  pure momentum or pure reversal in an EOD rebalance setting.",
        "data:",
        "  source: existing repo OHLCV snapshots",
        "  fields: [Date, Close, Volume]",
        "  point_in_time: features use only rows at or before signal date; forward returns use later closes only as labels",
        "universe:",
        "  scope: current snapshot equities with ETF and commodity proxies excluded",
        f"  min_close: {MIN_CLOSE}",
        f"  min_adv20: {MIN_ADV20}",
        "  survivorship_bias_note: current repo snapshots are not a historical all-US membership archive",
        "variants:",
    ]
    for name, desc in VARIANTS.items():
        lines.append(f"  {name}: {desc}")
    lines.extend([
        f"horizons: {HORIZONS}",
        f"transaction_cost_bps: {COSTS_BPS}",
        "split:",
    ])
    for name, cfg in WINDOWS.items():
        lines.append(f"  {name}: {cfg['start']} -> {cfg['end']}")
    with open(os.path.join(EXP_DIR, "config.yaml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    os.makedirs(EXP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DATA_EXP_DIR, exist_ok=True)
    _write_config()

    result_rows: list[dict] = []
    all_rank_ic: list[pd.DataFrame] = []
    coverage_by_window = {}
    metadata_by_window = {}

    for window_name, cfg in WINDOWS.items():
        frames, metadata = _load_frames(cfg["snapshot"])
        coverage_by_window[window_name] = _coverage(frames, cfg["start"], cfg["end"])
        metadata_by_window[window_name] = {
            "snapshot": cfg["snapshot"],
            "metadata_ticker_count": metadata.get("ticker_count"),
            "state_note": cfg["state_note"],
        }
        for variant in VARIANTS:
            panel = _build_panel(frames, cfg["start"], cfg["end"], variant)
            if panel.empty:
                continue
            for cost_bps in COSTS_BPS:
                rows, rank_ic = _evaluate_panel(panel, window_name, variant, cost_bps)
                result_rows.extend(rows)
                if cost_bps == 35 and not rank_ic.empty:
                    all_rank_ic.append(rank_ic)

    results_path = os.path.join(EXP_DIR, "results.csv")
    _write_csv(results_path, result_rows)

    rank_ic_path = os.path.join(EXP_DIR, "rank_ic_by_date.csv")
    if all_rank_ic:
        pd.concat(all_rank_ic, ignore_index=True).to_csv(rank_ic_path, index=False)

    result_df = pd.DataFrame(result_rows)
    primary = result_df[
        (result_df["variant"] == "pullback_rs_60_5")
        & (result_df["cost_bps"] == 35)
        & (result_df["horizon"].isin([5, 10, 20, 60]))
    ].copy()
    variant_summary = (
        result_df[result_df["cost_bps"] == 35]
        .groupby(["variant", "horizon"], as_index=False)
        .agg({
            "rank_ic_mean": "mean",
            "top_bottom_spread_mean": "mean",
            "top_bucket_return_mean": "mean",
            "turnover_mean": "mean",
            "top_bottom_hit_rate": "mean",
        })
    )
    best = variant_summary.sort_values(
        ["top_bottom_spread_mean", "rank_ic_mean"],
        ascending=[False, False],
    ).head(8)

    decision = "rejected"
    rejection_reason = (
        "Observed-only result: primary pullback_rs_60_5 did not show stable positive "
        "rank IC and spread across all horizons/windows after 35 bps costs."
    )
    if not primary.empty:
        grouped = primary.groupby("horizon").agg({
            "rank_ic_mean": "mean",
            "top_bottom_spread_mean": "mean",
            "top_bucket_return_mean": "mean",
        })
        stable = (
            (grouped["rank_ic_mean"] > 0).sum() >= 3
            and (grouped["top_bottom_spread_mean"] > 0).sum() >= 3
        )
        if stable:
            decision = "observed_promising_not_promoted"
            rejection_reason = (
                "Primary variant is directionally promising, but this is a standalone "
                "cross-sectional study with survivorship-biased current snapshots and no "
                "production slot-aware integration yet."
            )

    notes_path = os.path.join(EXP_DIR, "notes.md")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(f"# {STRATEGY_NAME}\n\n")
        f.write("## Hypothesis\n")
        f.write("Rank liquid US equities higher when 60-day cross-sectional momentum remains strong but the last 5 trading days have pulled back.\n\n")
        f.write("## Data Fields\n")
        f.write("- `Date`, `Close`, `Volume` from existing OHLCV snapshots\n")
        f.write("- Derived features: `ret_5d`, `ret_20d`, `ret_60d`, `adv20`, `vol20`\n")
        f.write("- Labels: forward close-to-close returns at 5/10/20/60 trading days\n\n")
        f.write("## Guardrails\n")
        f.write("- Point-in-time features use only data available through the signal date.\n")
        f.write("- Forward returns are labels only, never inputs.\n")
        f.write("- Current repo snapshots are current-universe biased; no promotion from this artifact alone.\n")
        f.write("- No production rules, thresholds, LLM prompts, or risk policy changed.\n\n")
        f.write("## Decision\n")
        f.write(f"`{decision}` - {rejection_reason}\n\n")
        f.write("## Best 35 bps rows\n")
        f.write(best.to_markdown(index=False))
        f.write("\n")

    log_path = os.path.join(LOG_DIR, f"{RUN_STAMP}_{STRATEGY_NAME}.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# {RUN_STAMP} {STRATEGY_NAME}\n\n")
        f.write(f"- experiment_id: `{EXPERIMENT_ID}`\n")
        f.write("- lane: `alpha_search`\n")
        f.write("- category: `cross_sectional_ranking`\n")
        f.write(f"- decision: `{decision}`\n")
        f.write(f"- run_time_utc: `{RUN_TS.isoformat()}`\n\n")
        f.write("## Alpha Hypothesis\n")
        f.write("Strong 60-day relative strength combined with a short 5-day pullback can rank better than pure momentum or pure reversal for EOD 5/10/20/60-day holding horizons.\n\n")
        f.write("## Mechanism Insight Check\n")
        f.write("This does not retry rejected low-TQS breakout, Financials target-width, semicap watchlist, or SEC/earnings sparse-archive variants. It is a standalone OHLCV cross-sectional ranking probe.\n\n")
        f.write("## Outputs\n")
        f.write(f"- `{results_path}`\n")
        f.write(f"- `{rank_ic_path}`\n")
        f.write(f"- `{notes_path}`\n")
        f.write(f"- `{os.path.join(EXP_DIR, 'config.yaml')}`\n\n")
        f.write("## Coverage\n")
        f.write(json.dumps(coverage_by_window, indent=2, sort_keys=True))
        f.write("\n\n## Result Summary at 35 bps\n")
        f.write(best.to_markdown(index=False))
        f.write("\n\n## Decision Rationale\n")
        f.write(rejection_reason + "\n")

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": RUN_TS.isoformat(),
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "cross_sectional_ranking_research",
        "hypothesis": "60-day relative strength with a 5-day pullback may improve EOD cross-sectional forward returns versus pure momentum or pure reversal.",
        "parameters": {
            "single_causal_variable": "ranking formula",
            "variants": dict(VARIANTS),
            "horizons": HORIZONS,
            "transaction_cost_bps": COSTS_BPS,
            "min_close": MIN_CLOSE,
            "min_adv20": MIN_ADV20,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "locked_variables": [
                "production signal generation",
                "production filters",
                "risk engine",
                "backtester trading logic",
                "LLM/news replay",
                "production universe",
            ],
        },
        "date_range": {name: {"start": cfg["start"], "end": cfg["end"]} for name, cfg in WINDOWS.items()},
        "market_regime_summary": {name: cfg["state_note"] for name, cfg in WINDOWS.items()},
        "coverage": coverage_by_window,
        "result_files": {
            "research_log": log_path,
            "config": os.path.join(EXP_DIR, "config.yaml"),
            "results": results_path,
            "rank_ic_by_date": rank_ic_path,
            "notes": notes_path,
        },
        "summary_35bps": best.to_dict(orient="records"),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Use a point-in-time historical constituent universe before promotion.",
            "If promising rows persist, test a slot-aware overlay against accepted A/B candidates rather than changing production entries directly.",
            "Do not promote pure OHLCV ranks without sector and liquidity neutrality checks remaining acceptable.",
        ],
    }
    artifact_path = os.path.join(DATA_EXP_DIR, f"{EXPERIMENT_ID}_{STRATEGY_NAME}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)

    with open(DOC_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(artifact, sort_keys=True) + "\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "results": results_path,
        "notes": notes_path,
        "research_log": log_path,
        "artifact": artifact_path,
    }, indent=2))


if __name__ == "__main__":
    main()
