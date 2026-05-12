"""Observed-only accepted-stack oracle loss taxonomy for exp-20260511-102.

This script does not alter strategy behavior. It reruns the accepted stack over
the fixed snapshots, classifies losing trades ex post, and estimates oracle
loss saved versus winner collateral for future pre-registered alpha tests.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260511-102"
SLUG = "accepted_stack_oracle_loss_taxonomy"

ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


OUT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260511_102_accepted_stack_oracle_loss_taxonomy.json"
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
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    return _round(value)


def _load_snapshot_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("ohlcv", raw)


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


def _trade_rows(
    trade: dict[str, Any], rows_by_ticker: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows_by_ticker.get(str(trade.get("ticker")), [])
        if str(trade.get("entry_date")) <= str(row.get("Date")) <= str(trade.get("exit_date"))
    ]


def _ret(price: float | None, entry: float) -> float | None:
    if price is None or entry == 0:
        return None
    return price / entry - 1.0


def _path_stats(trade: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    entry = float(trade.get("entry_price") or 0.0)
    highs = [float(r["High"]) for r in rows if r.get("High") is not None]
    lows = [float(r["Low"]) for r in rows if r.get("Low") is not None]
    closes = [float(r["Close"]) for r in rows if r.get("Close") is not None]
    first3 = rows[:3]
    first5 = rows[:5]
    first3_highs = [float(r["High"]) for r in first3 if r.get("High") is not None]
    first3_lows = [float(r["Low"]) for r in first3 if r.get("Low") is not None]
    first3_closes = [
        float(r["Close"]) for r in first3 if r.get("Close") is not None
    ]
    first5_closes = [
        float(r["Close"]) for r in first5 if r.get("Close") is not None
    ]

    worst_gap: float | None = None
    prev_close: float | None = None
    for row in rows:
        if prev_close and row.get("Open") is not None:
            gap = float(row["Open"]) / prev_close - 1.0
            worst_gap = gap if worst_gap is None else min(worst_gap, gap)
        if row.get("Close") is not None:
            prev_close = float(row["Close"])

    mfe = _ret(max(highs), entry) if highs else None
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    return {
        "path_rows": len(rows),
        "holding_trading_days": len(rows),
        "mfe_pct": mfe,
        "mae_pct": _ret(min(lows), entry) if lows else None,
        "first3_mfe_pct": _ret(max(first3_highs), entry) if first3_highs else None,
        "first3_mae_pct": _ret(min(first3_lows), entry) if first3_lows else None,
        "first3_close_return_pct": _ret(first3_closes[-1], entry)
        if first3_closes
        else None,
        "first5_close_return_pct": _ret(first5_closes[-1], entry)
        if first5_closes
        else None,
        "max_close_return_pct": _ret(max(closes), entry) if closes else None,
        "min_close_return_pct": _ret(min(closes), entry) if closes else None,
        "worst_overnight_gap_pct": worst_gap,
        "giveback_from_mfe_pct": (mfe - pnl_pct) if mfe is not None else None,
    }


def _base_trade(
    window: str, trade: dict[str, Any], rows_by_ticker: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    rows = _trade_rows(trade, rows_by_ticker)
    out = {
        "window": window,
        "trade_key": trade.get("trade_key"),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector") or "Unknown",
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "stop_price": trade.get("stop_price"),
        "target_mult_used": trade.get("target_mult_used"),
        "shares": trade.get("shares"),
        "pnl": float(trade.get("pnl") or 0.0),
        "pnl_pct_net": float(trade.get("pnl_pct_net") or 0.0),
        "exit_reason": trade.get("exit_reason"),
        "addon_count": int(trade.get("addon_count") or 0),
        "actual_risk_pct": trade.get("actual_risk_pct"),
        "initial_risk_pct": trade.get("initial_risk_pct"),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": trade.get("regime_exit_score"),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
    }
    out.update(_path_stats(trade, rows))
    return out


def _add_cluster_context(trades: list[dict[str, Any]]) -> None:
    by_day_sector: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_window_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_day_sector[
            (trade["window"], str(trade["entry_date"]), str(trade["sector"]))
        ].append(trade)
        by_window_day[(trade["window"], str(trade["entry_date"]))].append(trade)

    for group in by_day_sector.values():
        loss_count = sum(1 for t in group if t["pnl"] < 0)
        pnl = sum(t["pnl"] for t in group)
        for trade in group:
            trade["same_day_sector_entry_count"] = len(group)
            trade["same_day_sector_loss_count"] = loss_count
            trade["same_day_sector_group_pnl"] = pnl

    for group in by_window_day.values():
        winners = [t for t in group if t["pnl"] > 0]
        winner_pnl = sum(t["pnl"] for t in winners)
        for trade in group:
            trade["same_day_winner_count"] = len(winners)
            trade["same_day_winner_pnl"] = winner_pnl


def _label_trade(trade: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    mfe = trade.get("mfe_pct")
    first3_mfe = trade.get("first3_mfe_pct")
    first3_close = trade.get("first3_close_return_pct")
    first3_mae = trade.get("first3_mae_pct")
    gap = trade.get("worst_overnight_gap_pct")
    giveback = trade.get("giveback_from_mfe_pct")
    sizing = trade.get("sizing_multipliers") or {}

    if trade.get("exit_reason") == "stop" and mfe is not None and mfe < 0.01:
        labels.append("oracle_low_mfe_stopout")
    if (
        first3_mae is not None
        and first3_mfe is not None
        and first3_mae <= -0.03
        and first3_mfe < 0.02
    ):
        labels.append("early_adverse_no_reclaim")
    if (
        first3_close is not None
        and first3_mfe is not None
        and first3_close <= 0
        and first3_mfe < 0.02
    ):
        labels.append("weak_initial_follow_through")
    if mfe is not None and mfe >= 0.03 and trade["pnl"] < 0:
        labels.append("oracle_winner_to_loser_giveback")
    if giveback is not None and giveback >= 0.05 and trade["pnl"] < 0:
        labels.append("large_mfe_giveback")
    if gap is not None and gap <= -0.03:
        labels.append("overnight_gap_damage")
    if int(trade.get("addon_count") or 0) > 0:
        labels.append("addon_exposed")
    if float(trade.get("actual_risk_pct") or 0.0) >= 0.02:
        labels.append("risk_amplified_2pct_plus")
    if "rs20_entry_state_risk_multiplier_applied" in sizing:
        labels.append("rs20_leader_sized")
    if int(trade.get("same_day_sector_entry_count") or 0) >= 2:
        labels.append("same_day_sector_cluster")
    if int(trade.get("same_day_sector_loss_count") or 0) >= 2:
        labels.append("same_day_sector_loss_cluster")
    if trade.get("regime_exit_bucket") == "risk_on":
        labels.append("risk_on_entry")
    if not labels:
        labels.append("unclassified_oracle")
    return labels


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winners = [r for r in rows if r["pnl"] > 0]
    losers = [r for r in rows if r["pnl"] < 0]
    pnl = sum(r["pnl"] for r in rows)
    return {
        "count": len(rows),
        "winner_count": len(winners),
        "loser_count": len(losers),
        "win_rate": _round(len(winners) / len(rows), 4) if rows else None,
        "total_pnl": _round(pnl, 2),
        "avg_pnl": _round(pnl / len(rows), 2) if rows else None,
        "loss_abs": _round(sum(abs(r["pnl"]) for r in losers), 2),
        "winner_pnl": _round(sum(r["pnl"] for r in winners), 2),
        "worst_pnl": _round(min((r["pnl"] for r in rows), default=0.0), 2),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "Unknown")].append(row)
    return {
        name: _summary(items)
        for name, items in sorted(
            grouped.items(), key=lambda item: sum(x["pnl"] for x in item[1])
        )
    }


def _replacement_context(trade: dict[str, Any], trades: list[dict[str, Any]]) -> dict[str, Any]:
    same_window = [t for t in trades if t["window"] == trade["window"] and t is not trade]
    same_day_winners = [
        t
        for t in same_window
        if t["entry_date"] == trade["entry_date"] and t["pnl"] > 0
    ]
    same_sector_winners = [
        t
        for t in same_day_winners
        if t.get("sector") == trade.get("sector")
    ]
    all_window_winners = [t for t in same_window if t["pnl"] > 0]
    median_winner = median([t["pnl"] for t in all_window_winners]) if all_window_winners else None
    loss_abs = abs(trade["pnl"]) if trade["pnl"] < 0 else 0.0
    return {
        "same_day_winner_count": len(same_day_winners),
        "same_day_winner_pnl": _round(sum(t["pnl"] for t in same_day_winners), 2),
        "same_day_same_sector_winner_count": len(same_sector_winners),
        "same_day_same_sector_winner_pnl": _round(
            sum(t["pnl"] for t in same_sector_winners), 2
        ),
        "window_median_winner_pnl": _round(median_winner, 2)
        if median_winner is not None
        else None,
        "median_winners_needed_to_replace_loss": _round(loss_abs / median_winner, 3)
        if median_winner and median_winner > 0
        else None,
    }


def _label_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_loss_abs = sum(abs(r["pnl"]) for r in rows if r["pnl"] < 0)
    labels = sorted({label for row in rows for label in row["oracle_labels"]})
    out: dict[str, Any] = {}
    for label in labels:
        exposed = [r for r in rows if label in r["oracle_labels"]]
        bad = [r for r in exposed if r["pnl"] < 0]
        good = [r for r in exposed if r["pnl"] > 0]
        bad_loss_abs = sum(abs(r["pnl"]) for r in bad)
        collateral_pnl = sum(r["pnl"] for r in good)
        same_day_replacement_pnl = sum(
            r.get("replacement_context", {}).get("same_day_winner_pnl") or 0.0
            for r in bad
        )
        out[label] = {
            "exposed": _summary(exposed),
            "bad_slice": _summary(bad),
            "good_trade_collateral_if_naive_filter": _summary(good),
            "oracle_loss_saved_if_only_bad_trades_removed": _round(bad_loss_abs, 2),
            "tail_loss_share_of_all_losses": _round(bad_loss_abs / total_loss_abs, 4)
            if total_loss_abs
            else None,
            "naive_filter_net_after_collateral": _round(bad_loss_abs - collateral_pnl, 2),
            "collateral_to_bad_loss_abs_ratio": _round(collateral_pnl / bad_loss_abs, 4)
            if bad_loss_abs
            else None,
            "same_day_replacement_winner_pnl_available": _round(
                same_day_replacement_pnl, 2
            ),
            "by_strategy": _group(exposed, "strategy"),
            "by_sector": _group(exposed, "sector"),
            "worst_bad_examples": [
                {
                    "window": r["window"],
                    "ticker": r["ticker"],
                    "strategy": r["strategy"],
                    "sector": r["sector"],
                    "entry_date": r["entry_date"],
                    "exit_date": r["exit_date"],
                    "pnl": _round(r["pnl"], 2),
                    "pnl_pct_net": _round(r["pnl_pct_net"], 6),
                    "mfe_pct": _round(r.get("mfe_pct")),
                    "mae_pct": _round(r.get("mae_pct")),
                    "same_day_winner_pnl": r.get("replacement_context", {}).get(
                        "same_day_winner_pnl"
                    ),
                }
                for r in sorted(bad, key=lambda x: x["pnl"])[:8]
            ],
        }
    return out


def _tail_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    losers = sorted([r for r in rows if r["pnl"] < 0], key=lambda r: r["pnl"])
    loss_abs = sum(abs(r["pnl"]) for r in losers)
    tail = losers[: min(5, len(losers))]
    return {
        "loser_count": len(losers),
        "total_loss_abs": _round(loss_abs, 2),
        "tail_n": len(tail),
        "tail_loss_abs": _round(sum(abs(r["pnl"]) for r in tail), 2),
        "tail_loss_share": _round(sum(abs(r["pnl"]) for r in tail) / loss_abs, 4)
        if loss_abs
        else None,
        "worst_trades": [
            {
                "window": r["window"],
                "ticker": r["ticker"],
                "strategy": r["strategy"],
                "sector": r["sector"],
                "entry_date": r["entry_date"],
                "exit_date": r["exit_date"],
                "pnl": _round(r["pnl"], 2),
                "pnl_pct_net": _round(r["pnl_pct_net"], 6),
                "exit_reason": r["exit_reason"],
                "oracle_labels": r["oracle_labels"],
            }
            for r in tail
        ],
    }


def _run_window(label: str, spec: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
    if result.get("error"):
        raise RuntimeError(f"{label} backtest failed: {result['error']}")
    trades = [_base_trade(label, t, rows_by_ticker) for t in result.get("trades", [])]
    return result, trades


def build_artifact() -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    by_window: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        result, trades = _run_window(label, spec)
        all_trades.extend(trades)
        by_window[label] = {
            "window": spec,
            "metrics": _metric_block(result),
            "trades": trades,
        }

    _add_cluster_context(all_trades)
    for trade in all_trades:
        trade["oracle_labels"] = _label_trade(trade)
        trade["replacement_context"] = _replacement_context(trade, all_trades)

    for label in by_window:
        trades = by_window[label]["trades"]
        by_window[label]["trade_summary"] = _summary(trades)
        by_window[label]["bad_trade_summary"] = _summary([t for t in trades if t["pnl"] < 0])
        by_window[label]["tail_summary"] = _tail_summary(trades)
        by_window[label]["oracle_taxonomy"] = _label_summary(trades)

    aggregate_metrics = {
        "expected_value_score_sum": _round(
            sum(w["metrics"]["expected_value_score"] for w in by_window.values()), 4
        ),
        "total_pnl_sum": _round(sum(w["metrics"]["total_pnl"] for w in by_window.values()), 2),
        "trade_count_sum": sum(int(w["metrics"]["trade_count"] or 0) for w in by_window.values()),
        "signals_generated_sum": sum(
            int(w["metrics"]["signals_generated"] or 0) for w in by_window.values()
        ),
        "signals_survived_sum": sum(
            int(w["metrics"]["signals_survived"] or 0) for w in by_window.values()
        ),
        "max_drawdown_pct_max": _round(
            max(w["metrics"]["max_drawdown_pct"] for w in by_window.values()), 4
        ),
    }
    aggregate_metrics["survival_rate"] = _round(
        aggregate_metrics["signals_survived_sum"]
        / aggregate_metrics["signals_generated_sum"],
        4,
    )

    bad_trades = [t for t in all_trades if t["pnl"] < 0]
    cluster_overlaps = Counter(
        ",".join(sorted(t["oracle_labels"])) for t in bad_trades
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "loss_attribution",
        "status": "observed_only",
        "classification": "accepted-stack oracle/replacement-value loss taxonomy",
        "hypothesis": (
            "Accepted-stack bad trades may cluster into reproducible "
            "oracle/replacement-value failure families that explain repeated "
            "tail loss without adding filters."
        ),
        "single_causal_variable": "accepted-stack oracle loss taxonomy",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            "strategy_logic_changed": False,
        },
        "expected_value_score": aggregate_metrics["expected_value_score_sum"],
        "total_pnl": aggregate_metrics["total_pnl_sum"],
        "max_drawdown_pct": aggregate_metrics["max_drawdown_pct_max"],
        "survival_rate": aggregate_metrics["survival_rate"],
        "win_rate": _round(
            sum(1 for t in all_trades if t["pnl"] > 0) / len(all_trades), 4
        ),
        "total_trades": len(all_trades),
        "historical_constraints_checked": [
            "exp-20260507-903 and exp-20260509-021 already found hold-quality labels; this refresh adds oracle/replacement-value collateral framing on the accepted stack.",
            "exp-20260511-006 rejected blunt same-day same-sector risk_on follower haircut.",
            "exp-20260511-010 found quality-conditioned sector follower risk was underpowered, not promotable.",
            "exp-20260511-013 rejected all-core same-sector TQS follower haircut.",
            "No filter, sizing change, threshold, ranking rule, LLM boundary change, or production adapter is introduced here.",
        ],
        "aggregate": {
            "metrics": aggregate_metrics,
            "trade_summary": _summary(all_trades),
            "bad_trade_summary": _summary(bad_trades),
            "tail_summary": _tail_summary(all_trades),
            "oracle_taxonomy": _label_summary(all_trades),
            "bad_trade_pnl_by_strategy": _group(bad_trades, "strategy"),
            "bad_trade_pnl_by_sector": _group(bad_trades, "sector"),
            "bad_trade_pnl_by_ticker": _group(bad_trades, "ticker"),
            "cluster_overlap_counts": dict(cluster_overlaps.most_common()),
        },
        "by_window": by_window,
        "bad_trades": sorted(
            bad_trades, key=lambda t: (t["pnl"], t["window"], str(t["entry_date"]))
        ),
        "future_test_candidates": [
            {
                "candidate": "event/news-conditioned low-MFE stopout triage",
                "why": "Low-MFE stopouts have high oracle loss-saved purity, but historical path-only exits were rejected; a valid retry needs an ex-ante event/news or state label.",
            },
            {
                "candidate": "sector-cluster quality forward attribution",
                "why": "Same-day sector clustering recurs, but simple follower haircuts were rejected; only forward cluster-quality evidence or a new orthogonal discriminator should reopen it.",
            },
            {
                "candidate": "replacement-value ranking audit for bad-trade entry days",
                "why": "For loss days with same-day winners, future work should compare frozen candidate alternatives before changing ranking or filters.",
            },
        ],
        "decision": "observed_only",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
    }


def main() -> None:
    artifact = build_artifact()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(_safe(artifact), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    top = {
        "artifact": str(OUT_PATH.relative_to(ROOT)),
        "metrics": artifact["aggregate"]["metrics"],
        "bad_trade_summary": artifact["aggregate"]["bad_trade_summary"],
        "top_oracle_labels": {
            label: {
                "bad_count": row["bad_slice"]["count"],
                "loss_abs": row["bad_slice"]["loss_abs"],
                "collateral_pnl": row["good_trade_collateral_if_naive_filter"][
                    "winner_pnl"
                ],
                "naive_filter_net_after_collateral": row[
                    "naive_filter_net_after_collateral"
                ],
            }
            for label, row in sorted(
                artifact["aggregate"]["oracle_taxonomy"].items(),
                key=lambda item: item[1]["oracle_loss_saved_if_only_bad_trades_removed"],
                reverse=True,
            )[:8]
        },
    }
    print(json.dumps(_safe(top), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
