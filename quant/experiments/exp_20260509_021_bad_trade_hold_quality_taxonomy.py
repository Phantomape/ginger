"""Observed-only hold-quality taxonomy for exp-20260509-021.

This script does not alter strategy behavior. It runs the accepted backtest
path through the three fixed snapshots, enriches closed trades with path
statistics, and writes a machine-readable bad-trade taxonomy artifact.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402


EXPERIMENT_ID = "exp-20260509-021"
OUT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260509_021_bad_trade_hold_quality_taxonomy.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, digits)
    return value


def _metric_block(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _load_snapshot_rows(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return data.get("ohlcv", {})


def _trade_path_stats(
    trade: dict[str, Any], rows_by_ticker: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    ticker = trade["ticker"]
    entry = trade["entry_date"]
    exit_ = trade["exit_date"]
    entry_price = float(trade["entry_price"])
    rows = [
        r
        for r in rows_by_ticker.get(ticker, [])
        if entry <= str(r.get("Date")) <= exit_
    ]
    if not rows:
        return {
            "path_rows": 0,
            "mfe_pct": None,
            "mae_pct": None,
            "first3_mfe_pct": None,
            "first3_mae_pct": None,
            "first3_close_return_pct": None,
            "max_close_return_pct": None,
            "min_close_return_pct": None,
            "holding_trading_days": None,
        }

    highs = [float(r["High"]) for r in rows if r.get("High") is not None]
    lows = [float(r["Low"]) for r in rows if r.get("Low") is not None]
    closes = [float(r["Close"]) for r in rows if r.get("Close") is not None]
    first3 = rows[: min(3, len(rows))]
    first3_highs = [float(r["High"]) for r in first3 if r.get("High") is not None]
    first3_lows = [float(r["Low"]) for r in first3 if r.get("Low") is not None]
    first3_closes = [
        float(r["Close"]) for r in first3 if r.get("Close") is not None
    ]

    def ret(price: float | None) -> float | None:
        return None if price is None else (price / entry_price) - 1.0

    return {
        "path_rows": len(rows),
        "mfe_pct": ret(max(highs) if highs else None),
        "mae_pct": ret(min(lows) if lows else None),
        "first3_mfe_pct": ret(max(first3_highs) if first3_highs else None),
        "first3_mae_pct": ret(min(first3_lows) if first3_lows else None),
        "first3_close_return_pct": ret(first3_closes[-1] if first3_closes else None),
        "max_close_return_pct": ret(max(closes) if closes else None),
        "min_close_return_pct": ret(min(closes) if closes else None),
        "holding_trading_days": len(rows),
    }


def _enrich_trade(
    window: str, trade: dict[str, Any], rows_by_ticker: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    path = _trade_path_stats(trade, rows_by_ticker)
    enriched = {
        "window": window,
        "trade_key": trade.get("trade_key"),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "stop_price": trade.get("stop_price"),
        "shares": trade.get("shares"),
        "pnl": float(trade.get("pnl") or 0.0),
        "pnl_pct_net": float(trade.get("pnl_pct_net") or 0.0),
        "exit_reason": trade.get("exit_reason"),
        "addon_count": int(trade.get("addon_count") or 0),
        "actual_risk_pct": trade.get("actual_risk_pct"),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": trade.get("regime_exit_score"),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
    }
    enriched.update(path)
    return {k: _round(v) for k, v in enriched.items()}


def _cluster_predicates() -> dict[str, Callable[[dict[str, Any]], bool]]:
    return {
        "low_mfe_stopout": lambda t: (
            t["exit_reason"] == "stop"
            and t.get("mfe_pct") is not None
            and t["mfe_pct"] < 0.01
        ),
        "early_adverse_no_reclaim": lambda t: (
            t.get("first3_mae_pct") is not None
            and t.get("first3_mfe_pct") is not None
            and t["first3_mae_pct"] <= -0.03
            and t["first3_mfe_pct"] < 0.02
        ),
        "weak_follow_through": lambda t: (
            t.get("first3_close_return_pct") is not None
            and t.get("first3_mfe_pct") is not None
            and t["first3_close_return_pct"] <= 0.0
            and t["first3_mfe_pct"] < 0.02
        ),
        "gain_then_failed_hold": lambda t: (
            t.get("mfe_pct") is not None and t["mfe_pct"] >= 0.03
        ),
        "addon_loss": lambda t: t.get("addon_count", 0) > 0,
        "rs20_sized_loss": lambda t: (
            "rs20_entry_state_risk_multiplier_applied"
            in (t.get("sizing_multipliers") or {})
        ),
    }


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = sum(t["pnl"] for t in trades)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] < 0]
    return {
        "count": len(trades),
        "winner_count": len(winners),
        "loser_count": len(losers),
        "win_rate": _round(len(winners) / len(trades), 4) if trades else None,
        "total_pnl": _round(pnl, 2),
        "avg_pnl": _round(pnl / len(trades), 2) if trades else None,
        "avg_pnl_pct_net": _round(
            sum(t["pnl_pct_net"] for t in trades) / len(trades), 6
        )
        if trades
        else None,
        "worst_pnl": _round(min((t["pnl"] for t in trades), default=0.0), 2),
        "worst_pnl_pct_net": _round(
            min((t["pnl_pct_net"] for t in trades), default=0.0), 6
        ),
    }


def _group_pnl(trades: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(key) or "UNKNOWN")].append(trade)
    return {
        name: _summarize_trades(rows)
        for name, rows in sorted(
            grouped.items(), key=lambda item: sum(t["pnl"] for t in item[1])
        )
    }


def _sizing_rule_loss_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        for rule in (trade.get("sizing_multipliers") or {}).keys():
            grouped[rule].append(trade)
    return {
        rule: _summarize_trades(rows)
        for rule, rows in sorted(
            grouped.items(), key=lambda item: sum(t["pnl"] for t in item[1])
        )
    }


def _tail_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    losers = sorted([t for t in trades if t["pnl"] < 0], key=lambda t: t["pnl"])
    loss_abs = sum(abs(t["pnl"]) for t in losers)
    tail_n = min(5, len(losers))
    tail = losers[:tail_n]
    return {
        "loser_count": len(losers),
        "total_loss_abs": _round(loss_abs, 2),
        "tail_n": tail_n,
        "tail_loss_abs": _round(sum(abs(t["pnl"]) for t in tail), 2),
        "tail_loss_share_of_losses": _round(
            sum(abs(t["pnl"]) for t in tail) / loss_abs, 4
        )
        if loss_abs
        else None,
        "worst_trades": [
            {
                "window": t["window"],
                "ticker": t["ticker"],
                "strategy": t["strategy"],
                "sector": t["sector"],
                "entry_date": t["entry_date"],
                "exit_date": t["exit_date"],
                "pnl": _round(t["pnl"], 2),
                "pnl_pct_net": _round(t["pnl_pct_net"], 6),
                "exit_reason": t["exit_reason"],
                "mfe_pct": _round(t.get("mfe_pct")),
                "mae_pct": _round(t.get("mae_pct")),
                "first3_close_return_pct": _round(
                    t.get("first3_close_return_pct")
                ),
                "addon_count": t.get("addon_count"),
                "sizing_rules": sorted((t.get("sizing_multipliers") or {}).keys()),
            }
            for t in tail
        ],
    }


def _cluster_summary(
    trades: list[dict[str, Any]], predicates: dict[str, Callable[[dict[str, Any]], bool]]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, pred in predicates.items():
        exposed = [t for t in trades if pred(t)]
        bad = [t for t in exposed if t["pnl"] < 0]
        good = [t for t in exposed if t["pnl"] > 0]
        out[name] = {
            "definition": {
                "low_mfe_stopout": "exit_reason == stop and full-trade MFE < 1%",
                "early_adverse_no_reclaim": "first 3 trading days MAE <= -3% and first 3 day MFE < 2%",
                "weak_follow_through": "first 3 trading day close return <= 0 and first 3 day MFE < 2%",
                "gain_then_failed_hold": "full-trade MFE >= 3%; bad slice is trades that still closed negative",
                "addon_loss": "trade had addon_count > 0; bad slice is trades that closed negative",
                "rs20_sized_loss": "trade had rs20_entry_state sizing tag; bad slice is trades that closed negative",
            }[name],
            "all_exposed": _summarize_trades(exposed),
            "bad_trade_slice": _summarize_trades(bad),
            "good_trade_collateral_if_filtered": _summarize_trades(good),
            "by_strategy": _group_pnl(exposed, "strategy"),
            "by_sector": _group_pnl(exposed, "sector"),
            "bad_trade_examples": [
                {
                    "window": t["window"],
                    "ticker": t["ticker"],
                    "entry_date": t["entry_date"],
                    "exit_date": t["exit_date"],
                    "pnl": _round(t["pnl"], 2),
                    "pnl_pct_net": _round(t["pnl_pct_net"], 6),
                    "mfe_pct": _round(t.get("mfe_pct")),
                    "mae_pct": _round(t.get("mae_pct")),
                    "first3_close_return_pct": _round(
                        t.get("first3_close_return_pct")
                    ),
                }
                for t in sorted(bad, key=lambda x: x["pnl"])[:10]
            ],
        }
    return out


def _run_window(label: str, spec: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from data_layer import get_universe

    snapshot = ROOT / spec["snapshot"]
    rows_by_ticker = _load_snapshot_rows(snapshot)
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(snapshot),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label} backtest failed: {result['error']}")
    trades = [
        _enrich_trade(label, trade, rows_by_ticker)
        for trade in result.get("trades", [])
    ]
    return result, trades


def main() -> None:
    all_trades: list[dict[str, Any]] = []
    by_window: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        result, trades = _run_window(label, spec)
        all_trades.extend(trades)
        by_window[label] = {
            "window": spec,
            "metrics": _metric_block(result),
            "trade_summary": _summarize_trades(trades),
            "tail_summary": _tail_summary(trades),
            "clusters": _cluster_summary(trades, _cluster_predicates()),
        }

    losers = [t for t in all_trades if t["pnl"] < 0]
    aggregate_trade_summary = _summarize_trades(all_trades)
    aggregate_signals_generated = sum(
        int(w["metrics"]["signals_generated"] or 0) for w in by_window.values()
    )
    aggregate_signals_survived = sum(
        int(w["metrics"]["signals_survived"] or 0) for w in by_window.values()
    )
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "loss_attribution",
        "status": "observed_only",
        "expected_value_score": _round(
            sum(w["metrics"]["expected_value_score"] for w in by_window.values()), 4
        ),
        "total_pnl": _round(sum(w["metrics"]["total_pnl"] for w in by_window.values()), 2),
        "total_trades": len(all_trades),
        "win_rate": aggregate_trade_summary["win_rate"],
        "max_drawdown_pct": _round(
            max(w["metrics"]["max_drawdown_pct"] for w in by_window.values()), 4
        ),
        "survival_rate": _round(
            aggregate_signals_survived / aggregate_signals_generated, 4
        )
        if aggregate_signals_generated
        else None,
        "hypothesis": (
            "Recent bad trades cluster in reproducible hold-quality or "
            "follow-through failure families."
        ),
        "single_causal_variable": "bad trade hold-quality taxonomy",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backtest_protocol": (
            "Observed-only rerun of BacktestEngine.run over the three "
            "docs/backtesting.md fixed windows with canonical OHLCV snapshots; "
            "no strategy logic, filters, thresholds, or production files changed."
        ),
        "accepted_artifact_context": {
            "latest_full_trade_level_artifact": "data/backtest_results_20260510.json",
            "latest_accepted_metric_artifact": (
                "data/experiments/exp-20260510-015/trip_sector_taxonomy.json"
            ),
            "note": (
                "This script recomputes trade-level records from the current "
                "working tree and fixed snapshots because the latest accepted "
                "three-window metric artifact does not store every closed trade."
            ),
        },
        "historical_rejected_constraints": [
            "Low-MFE stopout replay was rejected in exp-20260426-053.",
            "Early-adverse/no-reclaim exit replay was rejected in exp-20260508-035.",
            "Near-target giveback and overnight-gap audits showed high winner collateral.",
            "This artifact is diagnostic only and must not be treated as a filter.",
        ],
        "aggregate": {
            "metrics": {
                "expected_value_score_sum": artifact_ev
                if (artifact_ev := _round(
                    sum(w["metrics"]["expected_value_score"] for w in by_window.values()),
                    4,
                ))
                is not None
                else None,
                "total_pnl_sum": _round(sum(w["metrics"]["total_pnl"] for w in by_window.values()), 2),
                "trade_count_sum": sum(
                    int(w["metrics"]["trade_count"] or 0)
                    for w in by_window.values()
                ),
                "signals_generated_sum": aggregate_signals_generated,
                "signals_survived_sum": aggregate_signals_survived,
            },
            "trade_summary": aggregate_trade_summary,
            "bad_trade_summary": _summarize_trades(losers),
            "tail_summary": _tail_summary(all_trades),
            "clusters": _cluster_summary(all_trades, _cluster_predicates()),
            "bad_trade_pnl_by_strategy": _group_pnl(losers, "strategy"),
            "bad_trade_pnl_by_sector": _group_pnl(losers, "sector"),
            "bad_trade_pnl_by_ticker": _group_pnl(losers, "ticker"),
            "bad_trade_pnl_by_sizing_rule": _sizing_rule_loss_summary(losers),
            "cluster_overlap_counts": {
                ",".join(sorted(names)) if names else "unclustered": count
                for names, count in Counter(
                    tuple(
                        name
                        for name, pred in _cluster_predicates().items()
                        if pred(t)
                    )
                    for t in losers
                ).items()
            },
        },
        "by_window": by_window,
        "all_bad_trades": sorted(losers, key=lambda t: (t["window"], t["pnl"])),
        "future_test_candidates": [
            {
                "candidate": "event/news-conditioned early adverse triage",
                "reason": (
                    "Price-path-only early adverse exits have rejected history; "
                    "a future test needs an orthogonal event/news/state label."
                ),
            },
            {
                "candidate": "hold-quality attribution in ranking rather than hard filter",
                "reason": (
                    "Several weak-follow-through signatures also touch winners, "
                    "so collateral should be measured before any executable rule."
                ),
            },
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(artifact["aggregate"], indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
