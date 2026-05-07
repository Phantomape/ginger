"""exp-20260506-015: SPY-leader add-on heat-room replay.

Alpha search. The prior global heat-cap experiment was directionally positive
but below Gate 4. This tests a narrower causal variable: allow extra portfolio
heat only while executing first follow-through add-ons for already accepted
SPY-relative leaders. New entries still see the production 8% heat gate.

The script is replay-only. A passing result must be promoted through a shared
production/backtest policy before it can affect live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-015"
STEM = "spy_leader_addon_heat_room"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

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
        "state_note": "rotation-heavy bull where strategy profits but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("addon_heat_10pct", {"addon_execution_heat_cap": 0.10}),
    ("addon_heat_12pct", {"addon_execution_heat_cap": 0.12}),
])


def _round(value, digits=4):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _addon_stats(result: dict) -> dict:
    addon = result.get("addon_attribution") or {}
    events = addon.get("events") or []
    statuses = Counter(str(event.get("status") or "unknown") for event in events)
    executed = [event for event in events if event.get("status") == "executed"]
    leader_events = [
        event for event in events if bool(event.get("spy_relative_leader_addon_cap"))
    ]
    leader_executed = [
        event for event in leader_events if event.get("status") == "executed"
    ]
    leader_heat_blocked = [
        event for event in leader_events
        if "portfolio_heat_cap" in str(event.get("status") or "")
    ]
    return {
        "scheduled": addon.get("scheduled"),
        "executed": addon.get("executed"),
        "skipped": addon.get("skipped"),
        "checkpoint_rejected": addon.get("checkpoint_rejected"),
        "status_counts": dict(sorted(statuses.items())),
        "executed_shares": sum(int(event.get("addon_shares") or 0) for event in executed),
        "spy_leader_event_count": len(leader_events),
        "spy_leader_executed_count": len(leader_executed),
        "spy_leader_executed_shares": sum(
            int(event.get("addon_shares") or 0) for event in leader_executed
        ),
        "spy_leader_heat_blocked_count": len(leader_heat_blocked),
        "spy_leader_heat_blocked_tickers": sorted({
            str(event.get("ticker") or "").upper()
            for event in leader_heat_blocked
            if event.get("ticker")
        }),
        "sample_events": [
            {
                "ticker": event.get("ticker"),
                "status": event.get("status"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "addon_shares": event.get("addon_shares"),
                "requested_shares": event.get("requested_shares"),
                "spy_relative_leader_addon_cap": event.get("spy_relative_leader_addon_cap"),
                "addon_position_cap": event.get("addon_position_cap"),
            }
            for event in events[:12]
        ],
    }


def _run_window(window: dict, addon_execution_heat_cap: float | None = None) -> dict:
    original_backtester_heat = bt.MAX_PORTFOLIO_HEAT
    if addon_execution_heat_cap is not None:
        bt.MAX_PORTFOLIO_HEAT = addon_execution_heat_cap
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
            include_pilot_sleeve=False,
        )
        return engine.run()
    finally:
        bt.MAX_PORTFOLIO_HEAT = original_backtester_heat


def _delta(before: dict, after: dict) -> dict:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    )
    return {
        key: _round((after.get(key) or 0) - (before.get(key) or 0), 6)
        for key in keys
    }


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0) for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values()
            if row["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values()
            if row["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values()
            if row["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values()
            if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_min": _round(
            min(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "sharpe_daily_delta_min": _round(
            min(row["delta"]["sharpe_daily"] for row in rows.values()),
            6,
        ),
        "sharpe_daily_delta_max": _round(
            max(row["delta"]["sharpe_daily"] for row in rows.values()),
            6,
        ),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "addon_executed_delta_sum": sum(
            (row["after_addon_stats"]["executed"] or 0)
            - (row["before_addon_stats"]["executed"] or 0)
            for row in rows.values()
        ),
        "spy_leader_addon_executed_delta_sum": sum(
            row["after_addon_stats"]["spy_leader_executed_count"]
            - row["before_addon_stats"]["spy_leader_executed_count"]
            for row in rows.values()
        ),
        "spy_leader_heat_blocked_delta_sum": sum(
            row["after_addon_stats"]["spy_leader_heat_blocked_count"]
            - row["before_addon_stats"]["spy_leader_heat_blocked_count"]
            for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict) -> bool:
    materiality = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["total_pnl_delta_pct"] > 0.05
        or aggregate["sharpe_daily_delta_min"] > 0.10
        or aggregate["max_drawdown_delta_min"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    stability = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )
    return bool(materiality and stability)


def _markdown_report(payload: dict) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SPY-leader add-on heat room",
        "",
        f"Decision: {payload['decision']}",
        "",
        "## Best Variant",
        "",
        f"- Best: `{payload['best_variant']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['total_pnl_delta_sum']}`",
        "",
        "## Window Metrics",
        "",
        "| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Add-ons delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {addon_delta} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                pnl_delta=row["delta"]["total_pnl"],
                sharpe_delta=row["delta"]["sharpe_daily"],
                dd_delta=row["delta"]["max_drawdown_pct"],
                addon_delta=(
                    (row["after_addon_stats"]["executed"] or 0)
                    - (row["before_addon_stats"]["executed"] or 0)
                ),
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        payload["rejection_reason"] or payload["acceptance_reason"],
        "",
        "Production impact: replay-only experiment. No live order, ranking, sizing, or entry policy changed.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    baselines = {}
    for label, window in WINDOWS.items():
        raw = _run_window(window)
        baselines[label] = {
            "raw": raw,
            "metrics": _metrics(raw),
            "addon_stats": _addon_stats(raw),
        }

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            raw = _run_window(window, variant["addon_execution_heat_cap"])
            before = baselines[label]["metrics"]
            after = _metrics(raw)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "before_addon_stats": baselines[label]["addon_stats"],
                "after_addon_stats": _addon_stats(raw),
            }
        aggregate = _aggregate(rows)
        variants[name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_passed": _gate4_passed(aggregate),
        }

    ranked = sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )
    best_name, best = ranked[0]
    accepted = best["gate4_passed"]
    decision = "accepted_for_promotion" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "capital_allocation_heat_capacity",
        "mechanism_family": "spy_relative_leader_followthrough_addon_capacity",
        "hypothesis": (
            "If the accepted SPY-relative leader first add-on is still heat-constrained, "
            "a narrow add-on-only heat-room exception should unlock more confirmed-winner "
            "exposure without weakening the production entry heat gate."
        ),
        "alpha_hypothesis": {
            "category": "allocation / lifecycle",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion are sample-limited, while "
                "the playbook's current top unblocked alpha path is add-on materiality "
                "and explicitly asks for narrower cap/heat budget semantics rather than "
                "another add-on threshold sweep."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260502-025": (
                    "Global heat cap 9-12% was positive but below Gate 4; a valid retry "
                    "needed a narrower capacity discriminator."
                ),
                "exp-20260502-022": (
                    "SPY-relative leader first add-on cap at 60% is accepted; this run "
                    "does not change that cap or its trigger."
                ),
                "exp-20260503 second-add-on family": (
                    "Second add-ons remain disqualified; this run only changes heat room "
                    "for the already accepted first add-on."
                ),
            },
            "why_not_simple_repeat": (
                "The tested variable is add-on execution heat room inside BacktestEngine; "
                "entry heat, signal generation, candidate ordering, add-on thresholds, "
                "add-on cap, and exits remain locked."
            ),
        },
        "parameters": {
            "single_causal_variable": "first add-on execution heat cap used by backtester._cap_addon_shares",
            "baseline": {
                "entry_heat_cap": 0.08,
                "addon_execution_heat_cap": 0.08,
            },
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "candidate ordering",
                "entry portfolio heat gate",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "MAX_POSITION_PCT",
                "ADDON_CHECKPOINT_DAYS",
                "ADDON_MIN_UNREALIZED_PCT",
                "ADDON_MIN_RS_VS_SPY",
                "ADDON_FRACTION_OF_ORIGINAL_SHARES",
                "ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT",
                "SECOND_ADDON_ENABLED",
                "exits",
                "LLM/news replay",
                "pilot sleeve",
            ],
            "implementation_note": (
                "Replay monkey-patches only backtester.MAX_PORTFOLIO_HEAT, which is read "
                "by _cap_addon_shares during add-on execution. Entry heat remains supplied "
                "by portfolio_engine.compute_portfolio_heat at the production 8% cap."
            ),
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {label: data["metrics"] for label, data in baselines.items()},
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            **best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Gate 4 requires material EV/PnL/Sharpe/drawdown improvement or more "
                "trades without win-rate decline, plus EV improvement in at least two "
                "canonical windows and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted in a future rerun, implement an explicit shared add-on heat "
                "capacity policy used by both backtester.py and run.py before changing "
                "production behavior."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains production-sample limited, so this run tests a "
                "deterministic lifecycle allocation lever instead of changing LLM duties."
            ),
        },
        "acceptance_reason": (
            "Best variant passed the three-window Gate 4 materiality and stability rules."
            if accepted else None
        ),
        "rejection_reason": (
            None if accepted else
            "The narrower add-on-only heat exception did not clear Gate 4 across the "
            "canonical windows. Treat add-on heat capacity as directionally interesting "
            "but still below production materiality without forward concentration evidence."
        ),
        "next_retry_requires": [
            "Do not retry nearby add-on-only heat caps without forward/paper concentration evidence.",
            "A valid retry needs a new discriminator explaining which leader add-ons deserve extra heat.",
            "Any future promotion must be implemented as shared run/backtester policy, not a backtest-only constant patch.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_015_spy_leader_addon_heat_room.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown_report(payload), encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "title": "SPY-leader add-on heat room",
        "summary": f"Best {best_name}; Gate4={accepted}",
        "best_variant": best_name,
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
