"""exp-20260503-014: non-leader follow-through add-on cap.

Alpha search. Test one lifecycle allocation variable: keep the accepted
SPY-relative leader day-2 add-on path, but disable first follow-through add-ons
for positions that are not SPY-relative leaders by setting the normal add-on
position cap to 0. This does not change entries, exits, candidate ordering,
risk multipliers, leader add-on cap, LLM/news replay, or the universe.
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


EXPERIMENT_ID = "exp-20260503-014"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "nonleader_addon_cap.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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

BASE_CONFIG = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
VARIANTS = OrderedDict([
    ("nonleader_addon_cap_0_00", {"ADDON_MAX_POSITION_PCT": 0.0}),
])


def _metrics(result: dict) -> dict:
    addon_summary = result.get("addon_attribution") or {}
    addon_events = addon_summary.get("events") or []
    executed = [row for row in addon_events if row.get("status") == "executed"]
    leader_exec = [
        row for row in executed
        if row.get("addon_number") == 1 and row.get("spy_relative_leader_addon_cap") is True
    ]
    nonleader_exec = [
        row for row in executed
        if row.get("addon_number") == 1 and row.get("spy_relative_leader_addon_cap") is not True
    ]
    nonleader_rejected_no_room = [
        row for row in addon_events
        if row.get("addon_number") == 1
        and row.get("spy_relative_leader_addon_cap") is not True
        and row.get("status") in {
            "skipped_position_cap",
            "skipped_portfolio_heat_cap",
            "skipped_cap_no_room",
            "skipped_no_cap_room",
        }
    ]
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
        "addon_scheduled_count": addon_summary.get("scheduled"),
        "addon_executed_count": addon_summary.get("executed"),
        "addon_skipped_count": addon_summary.get("skipped"),
        "first_leader_addons_executed": len(leader_exec),
        "first_nonleader_addons_executed": len(nonleader_exec),
        "first_nonleader_addons_rejected_no_room": len(nonleader_rejected_no_room),
        "converged": (result.get("convergence") or {}).get("converged"),
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


def _run_window(universe: list[str], window: dict, config_overrides: dict | None = None) -> dict:
    config = dict(BASE_CONFIG)
    if config_overrides:
        config.update(config_overrides)
    result = BacktestEngine(
        universe=universe,
        start=window["start"],
        end=window["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_variant(universe: list[str], config_overrides: dict | None = None) -> OrderedDict:
    rows = OrderedDict()
    for label, window in WINDOWS.items():
        result = _run_window(universe, window, config_overrides=config_overrides)
        metrics = _metrics(result)
        rows[label] = {"metrics": metrics}
        print(
            f"[{label}] overrides={config_overrides or 'baseline'} "
            f"EV={metrics['expected_value_score']} PnL={metrics['total_pnl']} "
            f"SharpeD={metrics['sharpe_daily']} DD={metrics['max_drawdown_pct']} "
            f"leader_addons={metrics['first_leader_addons_executed']} "
            f"nonleader_addons={metrics['first_nonleader_addons_executed']}"
        )
    return rows


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(float(before[label]["metrics"]["total_pnl"] or 0.0) for label in WINDOWS),
        2,
    )
    total_pnl_delta = round(
        sum(float(deltas[label]["total_pnl"] or 0.0) for label in WINDOWS),
        2,
    )
    baseline_ev = round(
        sum(float(before[label]["metrics"]["expected_value_score"] or 0.0) for label in WINDOWS),
        6,
    )
    ev_delta = round(
        sum(float(deltas[label]["expected_value_score"] or 0.0) for label in WINDOWS),
        6,
    )
    return {
        "by_window": deltas,
        "baseline_expected_value_score_sum": baseline_ev,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_sum": total_pnl_delta,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6)
        if baseline_total_pnl else None,
        "ev_windows_improved": sum(
            1 for label in WINDOWS if (deltas[label]["expected_value_score"] or 0.0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS if (deltas[label]["expected_value_score"] or 0.0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS if (deltas[label]["total_pnl"] or 0.0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for label in WINDOWS if (deltas[label]["total_pnl"] or 0.0) < 0
        ),
        "max_drawdown_delta_max": max(deltas[label]["max_drawdown_pct"] for label in WINDOWS),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(deltas[label]["sharpe_daily"] for label in WINDOWS),
        "nonleader_addons_removed_sum": -sum(
            deltas[label]["first_nonleader_addons_executed"] for label in WINDOWS
        ),
    }


def _passes_gate4(delta: dict) -> bool:
    if delta["ev_windows_improved"] < 2 or delta["ev_windows_regressed"] > 0:
        return False
    return bool(
        (delta["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (delta["total_pnl_delta_pct"] or 0.0) > 0.05
        or delta["sharpe_daily_delta_max"] > 0.1
        or delta["max_drawdown_delta_max"] < -0.01
        or (
            delta["trade_count_delta_sum"] > 0
            and delta["win_rate_delta_min"] >= 0
        )
    )


def build_payload() -> dict:
    universe = get_universe()
    baseline = _run_variant(universe)
    variants = OrderedDict()
    deltas = OrderedDict()
    for variant_name, overrides in VARIANTS.items():
        rows = _run_variant(universe, config_overrides=overrides)
        variants[variant_name] = rows
        deltas[variant_name] = _aggregate(baseline, rows)

    best_variant = max(
        deltas,
        key=lambda name: (
            deltas[name]["expected_value_score_delta_sum"],
            deltas[name]["total_pnl_delta_sum"],
        ),
    )
    gate4_passed = _passes_gate4(deltas[best_variant])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if gate4_passed else "rejected",
        "decision": "accepted" if gate4_passed else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_followthrough_addon_eligibility",
        "hypothesis": (
            "The accepted day-2 follow-through add-on may be creating value "
            "mainly in the SPY-relative leader sleeve; disabling non-leader "
            "first add-ons may improve capital efficiency while preserving the "
            "accepted leader add-on path."
        ),
        "alpha_hypothesis_category": "lifecycle_capital_allocation",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains production-aligned sample limited, so "
            "this uses a deterministic production-visible lifecycle field."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "notes": (
                "This does not retry leader add-on caps above 60%, global "
                "add-on fractions, second add-ons, RS/TQS ranking, target "
                "floors, or ATR trailing exits. It tests whether the non-leader "
                "add-on sleeve should remain enabled at all."
            ),
        },
        "parameters": {
            "single_causal_variable": "ADDON_MAX_POSITION_PCT for non-SPY-relative leaders",
            "old_value": 0.35,
            "tested_values": VARIANTS,
            "leader_addon_cap_locked": 0.60,
            "best_variant": best_variant,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all initial sizing rules",
                "SPY-relative leader risk budget",
                "SPY-relative leader initial position cap",
                "SPY-relative leader first add-on cap",
                "follow-through checkpoint day",
                "follow-through unrealized and RS thresholds",
                "second add-on behavior",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "all target/stop exits",
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
        "snapshots": {
            label: row["snapshot"] for label, row in WINDOWS.items()
        },
        "market_regime_summary": {
            label: row["state_note"] for label, row in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            variant: {label: rows[label]["metrics"] for label in WINDOWS}
            for variant, rows in variants.items()
        },
        "delta_metrics": deltas,
        "best_variant": best_variant,
        "best_variant_gate4": gate4_passed,
        "gate4_passed": gate4_passed,
        "gate4_basis": (
            "Accepted only if the best variant improves EV in at least two "
            "windows without EV regression and passes one standard Gate 4 "
            "materiality criterion."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, promote through constants.py plus parity tests; "
                "both backtester.py and production_parity.py already consume "
                "ADDON_MAX_POSITION_PCT from the shared constant."
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": None if gate4_passed else (
            "Disabling non-leader first add-ons did not clear the three-window Gate 4 bar."
        ),
        "next_retry_requires": [
            "Do not retry generic non-leader add-on disablement without new lifecycle attribution.",
            "A valid retry needs event/news context or a narrower non-leader quality discriminator.",
            "Any positive promotion must keep add-on eligibility shared between production and backtest paths.",
        ],
        "related_files": [
            "quant/experiments/exp_20260503_014_nonleader_addon_cap.py",
            "data/experiments/exp-20260503-014/nonleader_addon_cap.json",
            "experiments/logs/exp-20260503-014.json",
            "experiments/tickets/exp-20260503-014.json",
            "docs/experiment_log.jsonl",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Non-leader add-on cap",
        "summary": payload["hypothesis"],
        "best_variant": payload["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "next_action": (
            "Promote through shared constants and parity tests."
            if payload["gate4_passed"]
            else "Do not promote; keep accepted add-on path unchanged."
        ),
    }, indent=2) + "\n", encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "gate4_passed": payload["gate4_passed"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
