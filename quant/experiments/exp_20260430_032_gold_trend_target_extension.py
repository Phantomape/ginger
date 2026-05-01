"""exp-20260430-032 gold trend target extension.

Alpha search. Test one exit/lifecycle variable: GLD/IAU trend targets use
8 ATR instead of the broader Commodity trend default of 7 ATR. Entries,
sizing, ranking, add-ons, slots, LLM/news replay, and non-gold Commodities
targets remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260430-032"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "gold_trend_target_extension.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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

BASELINE_GOLD_TARGET_ATR = 7.0
PROMOTED_GOLD_TARGET_ATR = 8.0


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    gold_trades = [
        trade for trade in result.get("trades", [])
        if trade.get("strategy") == "trend_long"
        and trade.get("ticker") in {"GLD", "IAU"}
    ]
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "gold_trend_trade_count": len(gold_trades),
        "gold_trend_pnl": round(sum(float(t.get("pnl") or 0.0) for t in gold_trades), 2),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_variant(universe: list[str], gold_target_atr: float) -> OrderedDict:
    risk_engine.TREND_GOLD_TARGET_ATR_MULT = gold_target_atr
    rows = OrderedDict()
    for label, cfg in WINDOWS.items():
        result = _run_window(universe, cfg)
        rows[label] = {
            "metrics": _metrics(result),
            "trades": result.get("trades", []),
        }
        m = rows[label]["metrics"]
        print(
            f"[{label}] gold_target={gold_target_atr} "
            f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
            f"SharpeD={m['sharpe_daily']} DD={m['max_drawdown_pct']} "
            f"gold_trades={m['gold_trend_trade_count']}"
        )
    return rows


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS),
        2,
    )
    total_pnl_delta = round(
        sum(deltas[label]["total_pnl"] for label in WINDOWS),
        2,
    )
    ev_base = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(
        sum(deltas[label]["expected_value_score"] for label in WINDOWS),
        6,
    )
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / ev_base, 6) if ev_base else None,
        "baseline_expected_value_score_sum": ev_base,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6)
        if baseline_total_pnl else None,
        "ev_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] > 0
        ),
        "max_drawdown_delta_max": max(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(
            deltas[label]["sharpe_daily"] for label in WINDOWS
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.1:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    original_gold_target = risk_engine.TREND_GOLD_TARGET_ATR_MULT
    try:
        baseline = _run_variant(universe, BASELINE_GOLD_TARGET_ATR)
        promoted = _run_variant(universe, PROMOTED_GOLD_TARGET_ATR)
        aggregate = _aggregate(baseline, promoted)
        accepted = _passes_gate4(aggregate)
        return {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "accepted" if accepted else "rejected",
            "decision": "accepted" if accepted else "rejected",
            "lane": "alpha_search",
            "change_type": "exit_lifecycle_gold_trend_target_width",
            "hypothesis": (
                "Gold ETF trend winners (GLD/IAU) have cleaner continuation "
                "than the broader Commodity sleeve and should use an 8 ATR "
                "target while SLV remains on the accepted 7 ATR Commodity path."
            ),
            "parameters": {
                "single_causal_variable": "GLD/IAU trend_long target width",
                "baseline_gold_target_atr": BASELINE_GOLD_TARGET_ATR,
                "promoted_gold_target_atr": PROMOTED_GOLD_TARGET_ATR,
                "unchanged_commodity_target_atr": BASELINE_GOLD_TARGET_ATR,
                "gold_tickers": ["GLD", "IAU"],
                "locked_variables": [
                    "universe",
                    "signal generation",
                    "entry filters",
                    "candidate ranking",
                    "all sizing constants",
                    "MAX_POSITIONS",
                    "MAX_POSITION_PCT",
                    "MAX_PORTFOLIO_HEAT",
                    "MAX_PER_SECTOR",
                    "gap cancels",
                    "add-ons",
                    "non-gold target widths",
                    "LLM/news replay",
                    "earnings strategy",
                ],
            },
            "date_range": {
                "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
                "secondary": [
                    f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                    f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
                ],
            },
            "market_regime_summary": {
                label: cfg["state_note"] for label, cfg in WINDOWS.items()
            },
            "before_metrics": {
                label: baseline[label]["metrics"] for label in WINDOWS
            },
            "after_metrics": {
                label: promoted[label]["metrics"] for label in WINDOWS
            },
            "delta_metrics": aggregate,
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": False,
                "parity_test_added": True,
                "parity_note": (
                    "Implemented in quant/risk_engine.py and quant/constants.py, "
                    "which are shared by run.py and backtester.py."
                ),
            },
            "llm_metrics": {
                "used_llm": False,
                "blocker_relation": (
                    "LLM soft-ranking remains sample-limited, so this tests a "
                    "deterministic lifecycle alpha that is production-aligned."
                ),
            },
            "history_guardrails": {
                "not_unconditional_commodity_8atr_retry": True,
                "not_commodity_breakout_target_extension": True,
                "not_risk_budget_multiplier_tuning": True,
                "why_not_simple_repeat": (
                    "The rejected 8ATR Commodity trend extension hurt the SLV path. "
                    "This isolates GLD/IAU and leaves SLV on the accepted 7ATR target."
                ),
            },
            "rejection_reason": None if accepted else (
                "Gold-only 8ATR target did not pass fixed-window Gate 4."
            ),
            "next_retry_requires": [
                "Do not extend SLV or all Commodities above 7ATR without new evidence.",
                "Do not continue nearby 8.5/9ATR gold target sweeps without forward sample.",
                "A future retry should use event/news context or a broader precious-metals state map.",
            ],
            "related_files": [
                "quant/constants.py",
                "quant/risk_engine.py",
                "quant/test_quant.py",
                "quant/experiments/exp_20260430_032_gold_trend_target_extension.py",
                "data/experiments/exp-20260430-032/gold_trend_target_extension.json",
                "docs/experiments/logs/exp-20260430-032.json",
                "docs/experiments/tickets/exp-20260430-032.json",
            ],
        }
    finally:
        risk_engine.TREND_GOLD_TARGET_ATR_MULT = original_gold_target


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Gold trend target extension",
        "summary": (
            "GLD/IAU 8ATR target "
            f"Gate4={payload['decision'] == 'accepted'}"
        ),
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "delta_metrics": payload["delta_metrics"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
