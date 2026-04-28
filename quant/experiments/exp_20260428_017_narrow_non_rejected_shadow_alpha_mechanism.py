"""exp-20260428-017: earnings-proximity A/B candidate shadow audit.

This runner is observed-only. It does not change production strategy behavior,
and it does not attempt to repair or promote the C earnings strategy. The single
causal variable being audited is whether existing A/B candidates have useful
quality separation when a same-day earnings snapshot says they are close to an
earnings event with positive prior surprise context.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-017"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_017_narrow_non_rejected_shadow_alpha_mechanism.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

FORWARD_HORIZONS = [1, 5, 10, 20]
NEAR_EARNINGS_MAX_DAYS = 10


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
    }


def _load_frames(snapshot: str) -> dict[str, pd.DataFrame]:
    payload = _load_json(REPO_ROOT / snapshot)
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames


def _forward_returns(frames: dict[str, pd.DataFrame], ticker: str, asof: str) -> dict:
    df = frames.get(str(ticker).upper())
    out = {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    if df is None or df.empty:
        return out
    asof_ts = pd.Timestamp(asof[:10])
    hist = df.loc[:asof_ts]
    if hist.empty:
        return out
    idx = df.index.get_loc(hist.index[-1])
    base = float(df["Close"].iloc[idx])
    if base <= 0:
        return out
    for horizon in FORWARD_HORIZONS:
        end_idx = idx + horizon
        if end_idx < len(df):
            out[f"fwd_{horizon}d"] = round(float(df["Close"].iloc[end_idx]) / base - 1.0, 6)
    return out


def _snapshot_for_date(asof: str) -> tuple[dict | None, str | None]:
    yyyymmdd = asof[:10].replace("-", "")
    path = REPO_ROOT / "data" / f"earnings_snapshot_{yyyymmdd}.json"
    if not path.exists():
        return None, None
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return None, None
    return payload.get("earnings") or {}, path.name


def _earnings_context(ticker: str, asof: str) -> dict:
    earnings, source = _snapshot_for_date(asof)
    if earnings is None:
        return {
            "earnings_snapshot_source": None,
            "earnings_context_available": False,
            "days_to_earnings": None,
            "avg_historical_surprise_pct": None,
            "earnings_shadow_bucket": "no_snapshot",
        }
    item = earnings.get(str(ticker).upper())
    if not isinstance(item, dict):
        return {
            "earnings_snapshot_source": source,
            "earnings_context_available": False,
            "days_to_earnings": None,
            "avg_historical_surprise_pct": None,
            "earnings_shadow_bucket": "ticker_missing_from_snapshot",
        }
    dte = item.get("days_to_earnings")
    surprise = item.get("avg_historical_surprise_pct")
    near = dte is not None and 0 <= float(dte) <= NEAR_EARNINGS_MAX_DAYS
    positive_surprise = surprise is not None and float(surprise) > 0
    if near and positive_surprise:
        bucket = "near_earnings_positive_surprise"
    elif near:
        bucket = "near_earnings_nonpositive_or_unknown_surprise"
    else:
        bucket = "not_near_earnings"
    return {
        "earnings_snapshot_source": source,
        "earnings_context_available": True,
        "days_to_earnings": dte,
        "avg_historical_surprise_pct": surprise,
        "earnings_shadow_bucket": bucket,
    }


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(mean(clean), 6) if clean else None


def _safe_median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(median(clean), 6) if clean else None


def _summarize(rows: list[dict]) -> dict:
    out = {
        "candidate_count": len(rows),
        "unique_tickers": len({r["ticker"] for r in rows}),
        "by_strategy": dict(Counter(r["strategy"] for r in rows)),
        "by_source": dict(Counter(r["source"] for r in rows)),
        "by_earnings_bucket": dict(Counter(r["earnings_shadow_bucket"] for r in rows)),
        "earnings_context_coverage": (
            round(sum(1 for r in rows if r["earnings_context_available"]) / len(rows), 4)
            if rows else 0.0
        ),
        "realized_count": sum(1 for r in rows if r["source"] == "executed_ab_trade"),
        "realized_pnl_sum": round(sum(float(r.get("realized_pnl") or 0.0) for r in rows), 2),
        "realized_win_rate": None,
    }
    realized = [float(r["realized_pnl"]) for r in rows if r["source"] == "executed_ab_trade"]
    if realized:
        out["realized_win_rate"] = round(sum(1 for v in realized if v > 0) / len(realized), 4)
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [r.get(key) for r in rows if r.get(key) is not None]
        out[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": (
                round(sum(1 for v in values if float(v) > 0) / len(values), 4)
                if values else None
            ),
        }
    return out


def _collect_window(label: str, cfg: dict, universe: list[str]) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])

    frames = _load_frames(cfg["snapshot"])
    rows = []

    for trade in result.get("trades") or []:
        strategy = trade.get("strategy")
        if strategy not in {"trend_long", "breakout_long"}:
            continue
        asof = trade.get("entry_date")
        ticker = str(trade.get("ticker") or "").upper()
        row = {
            "window": label,
            "source": "executed_ab_trade",
            "ticker": ticker,
            "strategy": strategy,
            "sector": trade.get("sector"),
            "asof": asof,
            "realized_pnl": trade.get("pnl"),
            "realized_pnl_pct_net": trade.get("pnl_pct_net"),
            "entry_price": trade.get("entry_price"),
            "exit_reason": trade.get("exit_reason"),
        }
        row.update(_earnings_context(ticker, asof))
        row.update(_forward_returns(frames, ticker, asof))
        rows.append(row)

    for event in (result.get("scarce_slot_attribution") or {}).get("deferred_events") or []:
        asof = event.get("date")
        ticker = str(event.get("ticker") or "").upper()
        row = {
            "window": label,
            "source": "scarce_slot_deferred_breakout",
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "sector": event.get("sector"),
            "asof": asof,
            "realized_pnl": None,
            "realized_pnl_pct_net": None,
            "entry_price": event.get("entry_price"),
            "exit_reason": None,
            "trade_quality_score": event.get("trade_quality_score"),
            "confidence_score": event.get("confidence_score"),
        }
        row.update(_earnings_context(ticker, asof))
        row.update(_forward_returns(frames, ticker, asof))
        rows.append(row)

    by_bucket = OrderedDict()
    for bucket in sorted({r["earnings_shadow_bucket"] for r in rows}):
        by_bucket[bucket] = _summarize([r for r in rows if r["earnings_shadow_bucket"] == bucket])

    executed = [r for r in rows if r["source"] == "executed_ab_trade"]
    deferred = [r for r in rows if r["source"] == "scarce_slot_deferred_breakout"]
    near_positive = [r for r in rows if r["earnings_shadow_bucket"] == "near_earnings_positive_surprise"]

    return {
        "window": label,
        "config": cfg,
        "baseline_metrics": _metrics(result),
        "candidate_count": len(rows),
        "existing_ab_overlap_count": len(executed),
        "scarce_slot_deferred_count": len(deferred),
        "earnings_context_available_count": sum(1 for r in rows if r["earnings_context_available"]),
        "near_positive_count": len(near_positive),
        "overall_summary": _summarize(rows),
        "executed_ab_summary": _summarize(executed),
        "scarce_slot_summary": _summarize(deferred),
        "by_earnings_bucket": by_bucket,
        "rows": rows,
    }


def run_experiment() -> dict:
    universe = get_universe()
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        print(f"Running {label} {cfg['start']} -> {cfg['end']}")
        windows[label] = _collect_window(label, cfg, universe)
        print(
            f"  candidates={windows[label]['candidate_count']} "
            f"earnings_ctx={windows[label]['earnings_context_available_count']} "
            f"near_positive={windows[label]['near_positive_count']}"
        )

    aggregate_rows = []
    for payload in windows.values():
        aggregate_rows.extend(payload["rows"])

    aggregate = {
        "candidate_count": len(aggregate_rows),
        "existing_ab_overlap_count": sum(
            1 for r in aggregate_rows if r["source"] == "executed_ab_trade"
        ),
        "scarce_slot_deferred_count": sum(
            1 for r in aggregate_rows if r["source"] == "scarce_slot_deferred_breakout"
        ),
        "earnings_context_available_count": sum(
            1 for r in aggregate_rows if r["earnings_context_available"]
        ),
        "near_positive_count": sum(
            1 for r in aggregate_rows
            if r["earnings_shadow_bucket"] == "near_earnings_positive_surprise"
        ),
        "overall_summary": _summarize(aggregate_rows),
        "by_earnings_bucket": OrderedDict(
            (bucket, _summarize([
                r for r in aggregate_rows if r["earnings_shadow_bucket"] == bucket
            ]))
            for bucket in sorted({r["earnings_shadow_bucket"] for r in aggregate_rows})
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_discovery",
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "earnings-proximity context for existing A/B candidates",
        "hypothesis": (
            "Existing trend/breakout candidates close to earnings with positive "
            "historical surprise context may have different forward quality or "
            "scarce-slot opportunity cost."
        ),
        "history_guardrails": {
            "not_c_strategy_single_field_repair": True,
            "not_ohlcv_only_entry_family": True,
            "not_addon_threshold_or_cap_tuning": True,
            "not_global_tqs_ranking": True,
            "not_simple_scarce_slot_explainer": True,
            "production_strategy_changed": False,
        },
        "parameters": {
            "near_earnings_max_trading_days": NEAR_EARNINGS_MAX_DAYS,
            "positive_surprise_definition": "avg_historical_surprise_pct > 0",
            "audited_sources": ["executed_ab_trade", "scarce_slot_deferred_breakout"],
            "locked_variables": [
                "signal generation",
                "entry/exit rules",
                "risk sizing",
                "add-on rules",
                "scarce-slot routing",
                "LLM/news replay",
                "earnings_event_long strategy",
            ],
        },
        "windows": windows,
        "aggregate": aggregate,
        "decision_basis": (
            "Observed-only unless the audited subset has enough cross-window "
            "coverage and quality separation to justify a later production-path "
            "ranking experiment."
        ),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_experiment()
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
