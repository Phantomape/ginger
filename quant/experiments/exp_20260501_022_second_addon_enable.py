"""exp-20260501-022 second follow-through add-on replay.

Alpha search. Test one lifecycle/capital-allocation variable: enable the
already shared second add-on path. The trigger uses the existing constants:
day 5, unrealized >= 5%, RS vs SPY > 0, 15% of original shares, 45% position cap.
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


EXPERIMENT_ID = "exp-20260501-022"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "second_addon_enable.json"
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
    addon_attr = result.get("addon_attribution") or {}
    addon_events = addon_attr.get("events") or []
    second_events = [
        event for event in addon_events
        if event.get("addon_number") == 2
    ]
    executed_second = [
        event for event in second_events
        if event.get("status") == "executed"
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
        "addon_scheduled": addon_attr.get("scheduled"),
        "addon_executed": addon_attr.get("executed"),
        "addon_skipped": addon_attr.get("skipped"),
        "second_addon_events": len(second_events),
        "second_addon_executed": len(executed_second),
        "second_addon_shares": sum(int(e.get("addon_shares") or 0) for e in executed_second),
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


def _run_window(universe: list[str], cfg: dict, second_addon_enabled: bool) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "SECOND_ADDON_ENABLED": second_addon_enabled,
        },
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "addon_attribution": result.get("addon_attribution"),
        "trades": result.get("trades", []),
    }


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "second_addon_executed_delta_sum": sum(d["second_addon_executed"] for d in deltas.values()),
        "second_addon_shares_delta_sum": sum(d["second_addon_shares"] for d in deltas.values()),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    baseline = OrderedDict()
    variant = OrderedDict()
    for label, cfg in WINDOWS.items():
        baseline[label] = _run_window(universe, cfg, False)
        bm = baseline[label]["metrics"]
        print(
            f"[{label} baseline] EV={bm['expected_value_score']} "
            f"PnL={bm['total_pnl']} SharpeD={bm['sharpe_daily']} "
            f"WR={bm['win_rate']} trades={bm['trade_count']} "
            f"addon_exec={bm['addon_executed']}"
        )
        variant[label] = _run_window(universe, cfg, True)
        vm = variant[label]["metrics"]
        print(
            f"[{label} second_addon] EV={vm['expected_value_score']} "
            f"PnL={vm['total_pnl']} SharpeD={vm['sharpe_daily']} "
            f"WR={vm['win_rate']} trades={vm['trade_count']} "
            f"second_exec={vm['second_addon_executed']}"
        )

    aggregate = _aggregate(baseline, variant)
    accepted = _passes_gate4(aggregate)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_second_followthrough_addon",
        "hypothesis": (
            "A position that still clears day-5 +5% unrealized and positive RS vs SPY "
            "after the accepted first add-on may deserve a second small add-on, "
            "improving winner capture without changing entries, exits, or ticker universe."
        ),
        "alpha_hypothesis_category": "capital_allocation_lifecycle",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin; this tests an "
            "existing deterministic shared add-on path instead of waiting on LLM data."
        ),
        "parameters": {
            "single_causal_variable": "SECOND_ADDON_ENABLED",
            "baseline": False,
            "tested_variant": True,
            "second_addon_checkpoint_days": 5,
            "second_addon_min_unrealized_pct": 0.05,
            "second_addon_min_rs_vs_spy": 0.0,
            "second_addon_fraction_of_original_shares": 0.15,
            "second_addon_max_position_pct": 0.45,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all risk sizing rules",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "first add-on trigger and size",
                "all target/stop exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": OrderedDict(
            (label, baseline[label]["metrics"]) for label in WINDOWS
        ),
        "after_metrics": OrderedDict(
            (label, variant[label]["metrics"]) for label in WINDOWS
        ),
        "delta_metrics": aggregate,
        "best_variant": "second_addon_enabled",
        "best_variant_gate4": accepted,
        "gate4_basis": (
            "Accepted only if aggregate EV improves >10%, aggregate PnL improves >5%, "
            "drawdown drops >1pp, or trade count rises with no win-rate regression, "
            "with EV improving in at least two windows and no EV regression."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, flip SECOND_ADDON_ENABLED in quant/constants.py; "
                "backtester.py and production_parity.py already import the same constant."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that data constraint."
            ),
        },
        "history_guardrails": {
            "not_addon_threshold_retry": True,
            "not_addon_cap_retry": True,
            "not_financials_multiplier_retry": True,
            "why_not_simple_repeat": (
                "This does not tune the accepted first add-on threshold or cap; it tests "
                "whether a separate pre-existing day-5 second-add-on path unlocks materiality."
            ),
        },
        "rejection_reason": None if accepted else (
            "Second add-on did not pass fixed-window Gate 4."
        ),
        "next_retry_requires": [] if accepted else [
            "Do not retry nearby second-add-on thresholds without forward or event/news evidence.",
            "A valid retry needs a stronger quality discriminator, not another local add-on parameter sweep.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_022_second_addon_enable.py",
            "data/experiments/exp-20260501-022/second_addon_enable.json",
            "docs/experiments/logs/exp-20260501-022.json",
            "docs/experiments/tickets/exp-20260501-022.json",
        ],
    }


def main() -> None:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "summary": payload["hypothesis"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "aggregate": payload["delta_metrics"],
        "next_action": (
            "Promote SECOND_ADDON_ENABLED through shared constants."
            if payload["best_variant_gate4"]
            else "Do not promote; keep second add-on default-off."
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {LOG_JSON}")
    print(f"Wrote {TICKET_JSON}")
    print(f"decision={payload['decision']}")


if __name__ == "__main__":
    main()
