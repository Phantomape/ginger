"""exp-20260430-030 first add-on quality gate audit.

Alpha search, audit-only. Test whether the accepted day-2 follow-through
add-on is leaking capital into positions that the sizing layer had already
de-risked. This does not promote a strategy rule; it measures whether a
production-feasible discriminator is worth a full shared-policy replay.
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


EXPERIMENT_ID = "exp-20260430-030"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "first_addon_quality_gate_audit.json"
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
        "addon_scheduled": addon.get("scheduled_count"),
        "addon_executed": addon.get("executed_count"),
    }


def _addon_contribution(trade: dict) -> float:
    """Approximate PnL contribution of executed add-on shares.

    The backtester stores aggregate trade PnL after average-cost adjustment, so
    this is an audit approximation only. It is deliberately not acceptance
    evidence for a strategy rule.
    """
    addon_shares = int(trade.get("addon_shares") or 0)
    addon_cost = float(trade.get("addon_cost") or 0.0)
    exit_price = trade.get("exit_price")
    if addon_shares <= 0 or not addon_cost or exit_price is None:
        return 0.0
    avg_addon_fill = addon_cost / addon_shares
    return addon_shares * (float(exit_price) - avg_addon_fill)


def _risk_was_haircut(trade: dict) -> bool:
    base = trade.get("base_risk_pct")
    actual = trade.get("actual_risk_pct")
    if isinstance(base, (int, float)) and isinstance(actual, (int, float)):
        return actual < (base * 0.999)
    multipliers = trade.get("sizing_multipliers") or {}
    return any(isinstance(v, (int, float)) and v < 1.0 for v in multipliers.values())


def _screen_rows(window: str, trades: list[dict]) -> list[dict]:
    rows = []
    for trade in trades:
        if not (trade.get("addon_shares") or 0):
            continue
        addon_pnl = _addon_contribution(trade)
        row = {
            "window": window,
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "trade_pnl": trade.get("pnl"),
            "addon_shares": trade.get("addon_shares"),
            "addon_cost": trade.get("addon_cost"),
            "approx_addon_pnl": round(addon_pnl, 2),
            "approx_pnl_delta_if_removed": round(-addon_pnl, 2),
            "base_risk_pct": trade.get("base_risk_pct"),
            "actual_risk_pct": trade.get("actual_risk_pct"),
            "risk_was_haircut": _risk_was_haircut(trade),
            "sizing_multipliers": trade.get("sizing_multipliers") or {},
            "regime_exit_bucket": trade.get("regime_exit_bucket"),
            "regime_exit_score": trade.get("regime_exit_score"),
        }
        rows.append(row)
    return rows


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


def _aggregate(metrics_by_window: dict, addon_rows: list[dict]) -> dict:
    baseline_total_pnl = round(
        sum(m["total_pnl"] for m in metrics_by_window.values()),
        2,
    )
    haircut_rows = [r for r in addon_rows if r["risk_was_haircut"]]
    all_removed_delta = round(
        sum(r["approx_pnl_delta_if_removed"] for r in addon_rows),
        2,
    )
    haircut_removed_delta = round(
        sum(r["approx_pnl_delta_if_removed"] for r in haircut_rows),
        2,
    )
    by_window = OrderedDict()
    for label in WINDOWS:
        window_rows = [r for r in addon_rows if r["window"] == label]
        window_haircut = [r for r in window_rows if r["risk_was_haircut"]]
        by_window[label] = {
            "addon_trade_count": len(window_rows),
            "haircut_addon_trade_count": len(window_haircut),
            "approx_remove_all_addon_delta": round(
                sum(r["approx_pnl_delta_if_removed"] for r in window_rows),
                2,
            ),
            "approx_remove_haircut_addon_delta": round(
                sum(r["approx_pnl_delta_if_removed"] for r in window_haircut),
                2,
            ),
        }
    return {
        "baseline_total_pnl_sum": baseline_total_pnl,
        "addon_trade_count": len(addon_rows),
        "haircut_addon_trade_count": len(haircut_rows),
        "approx_remove_all_addon_delta": all_removed_delta,
        "approx_remove_all_addon_delta_pct": (
            round(all_removed_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
        "approx_remove_haircut_addon_delta": haircut_removed_delta,
        "approx_remove_haircut_addon_delta_pct": (
            round(haircut_removed_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
        "by_window": by_window,
    }


def build_payload() -> dict:
    universe = get_universe()
    rows = []
    metrics_by_window = OrderedDict()
    addon_rows = []
    for label, cfg in WINDOWS.items():
        result = _run_window(universe, cfg)
        metrics = _metrics(result)
        metrics_by_window[label] = metrics
        window_addons = _screen_rows(label, result.get("trades", []))
        addon_rows.extend(window_addons)
        rows.append({
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "metrics": metrics,
            "addon_rows": window_addons,
        })
        print(
            f"[{label}] EV={metrics['expected_value_score']} "
            f"PnL={metrics['total_pnl']} add-ons={len(window_addons)} "
            f"haircut_addons={sum(1 for r in window_addons if r['risk_was_haircut'])}"
        )

    aggregate = _aggregate(metrics_by_window, addon_rows)
    material = (
        aggregate["approx_remove_haircut_addon_delta_pct"] is not None
        and aggregate["approx_remove_haircut_addon_delta_pct"] > 0.05
        and sum(
            1 for v in aggregate["by_window"].values()
            if v["approx_remove_haircut_addon_delta"] > 0
        ) >= 2
    )
    status = "candidate_for_full_replay" if material else "rejected_audit"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": status,
        "lane": "alpha_search",
        "change_type": "lifecycle_addon_quality_audit",
        "hypothesis": (
            "The day-2 follow-through add-on may leak capital when it adds to "
            "positions that the shared sizing layer had already de-risked."
        ),
        "parameters": {
            "single_causal_variable": (
                "screen first add-ons by whether initial sizing was haircut"
            ),
            "screen_only": True,
            "approximation": (
                "Remove only the estimated add-on share PnL from closed trades; "
                "does not replay changed equity, heat, exits, or freed slots."
            ),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "initial sizing",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "first add-on trigger/fraction/cap",
                "second add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": (
                f"{WINDOWS['late_strong']['start']} -> "
                f"{WINDOWS['late_strong']['end']}"
            ),
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": metrics_by_window,
        "after_metrics": {
            "screened_approximation_only": aggregate,
        },
        "delta_metrics": {
            "aggregate": aggregate,
            "gate4_basis": (
                "Promote to full shared-policy replay only if the haircut-add-on "
                "screen is positive in at least two windows and approximates >5% "
                "aggregate PnL improvement."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "A positive full replay would need shared production_parity "
                "eligibility plus persisted initial sizing metadata."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data remains thin, so this tests deterministic "
                "lifecycle allocation using existing backtest fields."
            ),
        },
        "history_guardrails": {
            "not_addon_cap_tuning": True,
            "not_addon_fraction_tuning": True,
            "not_second_addon_retry": True,
            "why_not_simple_repeat": (
                "This asks whether already-de-risked positions should receive "
                "any first add-on; it does not change add-on size or timing."
            ),
        },
        "addon_rows": addon_rows,
        "rows": rows,
        "rejection_reason": (
            None if material else
            "The haircut-add-on leak is too small/sparse for a full shared-policy replay."
        ),
        "next_retry_requires": [
            "Do not implement a first-add-on haircut gate from this audit alone.",
            "A valid retry needs full backtester replay plus production metadata for initial sizing multipliers.",
            "If event/news context becomes available, use it as a stronger add-on quality discriminator.",
        ],
        "related_files": [
            "quant/experiments/exp_20260430_030_addon_quality_gate_audit.py",
            "data/experiments/exp-20260430-030/first_addon_quality_gate_audit.json",
            "docs/experiments/logs/exp-20260430-030.json",
            "docs/experiments/tickets/exp-20260430-030.json",
        ],
    }


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
        "title": "First add-on quality gate audit",
        "summary": payload["delta_metrics"]["gate4_basis"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
