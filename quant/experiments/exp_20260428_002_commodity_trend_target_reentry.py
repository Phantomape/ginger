"""exp-20260428-002: Commodity trend target-exit re-entry replay.

Hypothesis:
    The accepted `trend_long | Commodities` wider target captures the first leg
    of a convex move, but target exits may still leave follow-through alpha on
    the table. Re-enter the same ticker after a Commodity trend target exit and
    let the existing production sizing, slot, stop, target, add-on, and scarce
    slot rules decide whether it is worth taking.

This runner is experiment-only. It monkeypatches signal generation in-process
after deriving target-exit dates from the baseline run and does not change
production strategy defaults.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import signal_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260428-002"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_002_commodity_trend_target_reentry.json"

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

BASELINE_CONFIG = {"REGIME_AWARE_EXIT": True}


def _load_snapshot(path: str) -> dict:
    with (REPO_ROOT / path).open("r", encoding="utf-8") as f:
        return json.load(f)["ohlcv"]


def _spy_close_to_date(snapshot_path: str) -> dict[float, str]:
    snapshot = _load_snapshot(snapshot_path)
    out = {}
    for row in snapshot.get("SPY", []):
        close = row.get("Close")
        date = row.get("Date")
        if isinstance(close, (int, float)) and date:
            out[round(float(close), 6)] = str(date)
    return out


def _next_date_map(snapshot_path: str) -> dict[str, str]:
    snapshot = _load_snapshot(snapshot_path)
    dates = [str(row["Date"]) for row in snapshot.get("SPY", []) if row.get("Date")]
    return {
        date: dates[idx + 1]
        for idx, date in enumerate(dates[:-1])
    }


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    addon = result.get("addon_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "addon_executed": addon.get("executed", 0),
    }


def _run_window(universe: list[str], cfg: dict, reentry_map=None, close_to_date=None) -> dict:
    with _commodity_target_reentry_patch(reentry_map or {}, close_to_date or {}):
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config=BASELINE_CONFIG,
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )
        result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _target_exit_reentry_map(baseline_result: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for trade in baseline_result.get("trades", []):
        if (
            trade.get("exit_reason") == "target"
            and trade.get("strategy") == "trend_long"
            and trade.get("sector") == "Commodities"
        ):
            exit_date = trade.get("exit_date")
            if exit_date:
                out[exit_date].append({
                    "ticker": trade.get("ticker"),
                    "source_entry_date": trade.get("entry_date"),
                    "source_exit_date": exit_date,
                    "source_pnl": trade.get("pnl"),
                    "source_return_pct": trade.get("return_pct"),
                })
    return dict(out)


@contextmanager
def _commodity_target_reentry_patch(
    reentry_map: dict[str, list[dict]],
    close_to_date: dict[float, str],
):
    original_generate = signal_engine.generate_signals

    def generate_with_reentries(features_dict, *args, **kwargs):
        signals = list(original_generate(features_dict, *args, **kwargs))
        if not reentry_map:
            return signals
        market_context = kwargs.get("market_context") or {}
        current_date = market_context.get("current_date")
        date_key = None
        if current_date is not None:
            date_key = str(current_date.date()) if hasattr(current_date, "date") else str(current_date)
        if date_key is None:
            spy_features = (features_dict or {}).get("SPY") or {}
            spy_close = spy_features.get("close")
            if isinstance(spy_close, (int, float)):
                date_key = close_to_date.get(round(float(spy_close), 6))
        if date_key is None:
            return signals
        for source in reentry_map.get(date_key, []):
            ticker = source.get("ticker")
            features = (features_dict or {}).get(ticker) or {}
            close = features.get("close")
            atr = features.get("atr")
            if not ticker or not close or not atr:
                continue
            signals.append({
                "ticker": ticker,
                "strategy": "trend_long",
                "entry_price": round(close, 2),
                "stop_price": round(close - ATR_STOP_MULT * atr, 2),
                "confidence_score": 1.0,
                "entry_note": (
                    "Commodity trend target-exit re-entry candidate; "
                    "experiment-only replay signal."
                ),
                "conditions_met": {
                    "source": "commodity_trend_target_reentry",
                    "source_entry_date": source.get("source_entry_date"),
                    "source_exit_date": source.get("source_exit_date"),
                    "source_pnl": source.get("source_pnl"),
                },
            })
        return signals

    signal_engine.generate_signals = generate_with_reentries
    try:
        yield
    finally:
        signal_engine.generate_signals = original_generate


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _trade_key(trade: dict) -> tuple:
    return (
        trade.get("ticker"),
        trade.get("entry_date"),
        trade.get("exit_date"),
        trade.get("strategy"),
    )


def _reentry_trades(
    candidate_result: dict,
    baseline_result: dict,
    reentry_tickers_by_fill_date: dict[str, set[str]],
) -> list[dict]:
    baseline_keys = {_trade_key(trade) for trade in baseline_result.get("trades", [])}
    rows = []
    for trade in candidate_result.get("trades", []):
        ticker = trade.get("ticker")
        entry_date = trade.get("entry_date")
        if (
            ticker in reentry_tickers_by_fill_date.get(entry_date, set())
            and _trade_key(trade) not in baseline_keys
        ):
            rows.append({
                "ticker": ticker,
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": trade.get("pnl"),
                "return_pct": trade.get("return_pct"),
                "shares": trade.get("shares"),
                "addon_count": trade.get("addon_count"),
            })
    return rows


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        close_to_date = _spy_close_to_date(cfg["snapshot"])
        next_dates = _next_date_map(cfg["snapshot"])
        baseline_result = _run_window(universe, cfg)
        reentry_map = _target_exit_reentry_map(baseline_result)
        candidate_result = _run_window(
            universe,
            cfg,
            reentry_map=reentry_map,
            close_to_date=close_to_date,
        )
        before = _metrics(baseline_result)
        after = _metrics(candidate_result)
        reentry_tickers_by_fill_date = {
            next_dates.get(date): {item["ticker"] for item in items}
            for date, items in reentry_map.items()
            if next_dates.get(date)
        }
        reentry_trades = _reentry_trades(
            candidate_result,
            baseline_result,
            reentry_tickers_by_fill_date,
        )
        row = {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": _delta(after, before),
            "scheduled_reentry_signal_count": sum(len(v) for v in reentry_map.values()),
            "scheduled_reentry_dates": sorted(reentry_map),
            "candidate_reentry_trade_count": len(reentry_trades),
            "candidate_reentry_pnl": round(sum(float(t.get("pnl") or 0.0) for t in reentry_trades), 2),
            "candidate_reentry_trades": reentry_trades,
        }
        print(
            f"[{label}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} | PnL {before['total_pnl']} -> "
            f"{after['total_pnl']} | scheduled={row['scheduled_reentry_signal_count']}"
        )
        rows.append(row)

    ev_delta_sum = round(sum(row["delta_metrics"]["expected_value_score"] for row in rows), 6)
    pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
    summary = {
        "expected_value_score_delta_sum": ev_delta_sum,
        "total_pnl_delta_sum": pnl_delta_sum,
        "windows_improved": sum(
            1 for row in rows if row["delta_metrics"]["expected_value_score"] > 0
        ),
        "windows_regressed": sum(
            1 for row in rows if row["delta_metrics"]["expected_value_score"] < 0
        ),
        "max_drawdown_delta_max": max(
            row["delta_metrics"]["max_drawdown_pct"] for row in rows
        ),
        "scheduled_reentry_signal_count": sum(
            row["scheduled_reentry_signal_count"] for row in rows
        ),
        "candidate_reentry_trade_count": sum(
            row["candidate_reentry_trade_count"] for row in rows
        ),
        "candidate_reentry_pnl": round(
            sum(row["candidate_reentry_pnl"] for row in rows),
            2,
        ),
    }
    accepted = (
        summary["windows_improved"] >= 2
        and summary["windows_regressed"] == 0
        and (
            ev_delta_sum > 0.10
            or pnl_delta_sum > 0.05 * sum(row["before_metrics"]["total_pnl"] for row in rows)
            or any(row["delta_metrics"]["sharpe_daily"] > 0.1 for row in rows)
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_default_off_research_harness" if accepted else "rejected",
        "decision": "accepted_default_off_research_harness" if accepted else "rejected",
        "hypothesis": (
            "Commodity trend target exits may still contain continuation alpha; "
            "re-entering the same ticker after a target exit can improve lifecycle "
            "EV without changing entry rules, LLM/news, target widths, or sizing."
        ),
        "change_type": "alpha_search_lifecycle_reentry_shadow",
        "parameters": {
            "single_causal_variable": "trend_long Commodities target-exit re-entry",
            "baseline_config": BASELINE_CONFIG,
            "candidate_rule": {
                "source_exit_reason": "target",
                "source_strategy": "trend_long",
                "source_sector": "Commodities",
                "signal_date": "source exit_date",
                "fill": "existing next-trading-day entry model",
                "risk_and_exit": "existing trend_long Commodity risk enrichment",
            },
            "locked_variables": [
                "normal entries",
                "target widths",
                "position sizing",
                "day-2 follow-through add-on trigger",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "prior_related_results": [
            {
                "experiment_id": "exp-20260425-031",
                "decision": "accepted",
                "reason": "Commodity trend wider targets carried useful convexity.",
            },
            {
                "experiment_id": "exp-20260425-034",
                "decision": "audit_only",
                "reason": "Post-target Commodity trend continuation was positive in late/mid samples.",
            },
        ],
        "windows": WINDOWS,
        "results": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "No Gate 4 condition passed across the fixed three-window comparison."
        ),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "lifecycle alpha was tested instead."
            ),
        },
        "strategy_behavior_changed": False,
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
