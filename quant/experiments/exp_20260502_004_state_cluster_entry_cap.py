"""exp-20260502-004 state-conditioned clustered-entry cap replay.

Alpha search. Test one capital-allocation/lifecycle variable: when broad index
state is weak, cap same-day new core entries to avoid clustered adverse entry
dates. This is not a global MAX_POSITIONS sweep and not a direct stop/no-add-on
filter; it changes only same-day entry cluster exposure under a replayable
market-state condition.
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

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-004"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "state_cluster_entry_cap.json"
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

VARIANTS = OrderedDict([
    ("baseline", None),
    ("cap2_when_min_index_below_0", {"threshold": 0.0, "cap": 2}),
    ("cap2_when_min_index_below_2pct", {"threshold": 0.02, "cap": 2}),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
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
        "entry_reason_counts": entry.get("reason_counts", {}),
        "by_strategy": result.get("by_strategy", {}),
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


def _cluster_rows(trades: list[dict]) -> list[dict]:
    by_entry = OrderedDict()
    for trade in sorted(trades, key=lambda row: (row.get("entry_date") or "", row.get("ticker") or "")):
        by_entry.setdefault(trade.get("entry_date"), []).append(trade)
    rows = []
    for entry_date, items in by_entry.items():
        if not entry_date or len(items) < 2:
            continue
        pnl = round(sum(float(row.get("pnl") or 0.0) for row in items), 2)
        rows.append({
            "entry_date": entry_date,
            "trade_count": len(items),
            "pnl": pnl,
            "loss_count": sum(1 for row in items if float(row.get("pnl") or 0.0) < 0),
            "win_count": sum(1 for row in items if float(row.get("pnl") or 0.0) > 0),
            "tickers": [row.get("ticker") for row in items],
            "strategies": [row.get("strategy") for row in items],
        })
    return rows


def _make_cluster_cap_planner(original, threshold: float, cap: int, audit: list[dict]):
    def _planner(
        signals,
        open_positions,
        market_context=None,
        max_positions=None,
        defer_breakout_when_slots_lte=None,
        defer_breakout_max_min_index_pct_from_ma=None,
        active_positions_count=None,
    ):
        planned, entry_plan = original(
            signals,
            open_positions,
            market_context=market_context,
            max_positions=max_positions,
            defer_breakout_when_slots_lte=defer_breakout_when_slots_lte,
            defer_breakout_max_min_index_pct_from_ma=defer_breakout_max_min_index_pct_from_ma,
            active_positions_count=active_positions_count,
        )
        context = market_context or {}
        spy_pct = context.get("spy_pct_from_ma")
        qqq_pct = context.get("qqq_pct_from_ma")
        min_index = None
        if isinstance(spy_pct, (int, float)) and isinstance(qqq_pct, (int, float)):
            min_index = min(spy_pct, qqq_pct)
        if min_index is None or min_index > threshold or len(planned) <= cap:
            return planned, entry_plan

        capped = list(planned[:cap])
        newly_deferred = list(planned[cap:])
        entry_plan = dict(entry_plan)
        entry_plan["slot_sliced_signals"] = list(entry_plan.get("slot_sliced_signals") or [])
        entry_plan["slot_sliced_signals"].extend(newly_deferred)
        entry_plan["signals_after_entry_plan"] = len(capped)
        entry_plan["state_cluster_entry_cap"] = {
            "threshold": threshold,
            "cap": cap,
            "min_index_pct_from_ma": min_index,
            "deferred_count": len(newly_deferred),
        }
        audit.append({
            "threshold": threshold,
            "cap": cap,
            "min_index_pct_from_ma": round(min_index, 6),
            "signals_before_cap": len(planned),
            "signals_after_cap": len(capped),
            "deferred_tickers": [sig.get("ticker") for sig in newly_deferred],
        })
        return capped, entry_plan

    return _planner


def _run_window(universe: list[str], cfg: dict, variant_cfg: dict | None) -> dict:
    original = bt.plan_entry_candidates
    audit = []
    try:
        if variant_cfg:
            bt.plan_entry_candidates = _make_cluster_cap_planner(
                original,
                threshold=variant_cfg["threshold"],
                cap=variant_cfg["cap"],
                audit=audit,
            )
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
    finally:
        bt.plan_entry_candidates = original
    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "cluster_rows": _cluster_rows(result.get("trades", [])),
        "cap_audit": audit,
    }


def _aggregate(baseline: OrderedDict, variant: OrderedDict) -> dict:
    by_window = OrderedDict()
    for label in WINDOWS:
        by_window[label] = {
            "before": baseline[label]["metrics"],
            "after": variant[label]["metrics"],
            "delta": _delta(variant[label]["metrics"], baseline[label]["metrics"]),
            "before_clusters": baseline[label]["cluster_rows"],
            "after_clusters": variant[label]["cluster_rows"],
            "cap_audit": variant[label]["cap_audit"],
        }
    baseline_pnl = round(sum(row["before"]["total_pnl"] for row in by_window.values()), 2)
    pnl_delta = round(sum(row["delta"]["total_pnl"] for row in by_window.values()), 2)
    baseline_ev = round(sum(row["before"]["expected_value_score"] for row in by_window.values()), 6)
    ev_delta = round(sum(row["delta"]["expected_value_score"] for row in by_window.values()), 6)
    return {
        "by_window": by_window,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": pnl_delta,
        "baseline_total_pnl_sum": baseline_pnl,
        "total_pnl_delta_pct": round(pnl_delta / baseline_pnl, 6) if baseline_pnl else None,
        "ev_windows_improved": sum(1 for row in by_window.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in by_window.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in by_window.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in by_window.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": max(row["delta"]["max_drawdown_pct"] for row in by_window.values()),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in by_window.values()),
        "win_rate_delta_min": min(row["delta"]["win_rate"] for row in by_window.values()),
        "sharpe_daily_delta_max": max(row["delta"]["sharpe_daily"] for row in by_window.values()),
        "cap_trigger_count": sum(len(row["cap_audit"]) for row in by_window.values()),
    }


def _passes_gate4(agg: dict) -> bool:
    if agg["ev_windows_improved"] < 2 or agg["ev_windows_regressed"] > 0:
        return False
    if agg["expected_value_score_delta_pct"] and agg["expected_value_score_delta_pct"] > 0.10:
        return True
    if agg["total_pnl_delta_pct"] and agg["total_pnl_delta_pct"] > 0.05:
        return True
    if agg["sharpe_daily_delta_max"] > 0.10:
        return True
    if agg["max_drawdown_delta_max"] < -0.01:
        return True
    if agg["trade_count_delta_sum"] > 0 and agg["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = sorted(get_universe())
    rows = OrderedDict()
    for variant_name, variant_cfg in VARIANTS.items():
        rows[variant_name] = OrderedDict()
        for label, cfg in WINDOWS.items():
            result = _run_window(universe, cfg, variant_cfg)
            rows[variant_name][label] = result
            metrics = result["metrics"]
            print(
                f"[{label} {variant_name}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} WR={metrics['win_rate']} "
                f"trades={metrics['trade_count']} cap_hits={len(result['cap_audit'])}"
            )

    summaries = OrderedDict()
    for variant_name in VARIANTS:
        if variant_name == "baseline":
            continue
        summaries[variant_name] = _aggregate(rows["baseline"], rows[variant_name])

    best_variant, best_agg = max(
        summaries.items(),
        key=lambda item: (
            item[1]["ev_windows_improved"],
            -item[1]["ev_windows_regressed"],
            item[1]["expected_value_score_delta_sum"],
            item[1]["total_pnl_delta_sum"],
        ),
    )
    accepted = _passes_gate4(best_agg)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "state_conditioned_entry_cluster_cap",
        "hypothesis": (
            "When broad index state is weak, same-day clusters of new entries may "
            "increase correlated adverse-entry risk; capping only those clustered "
            "entry days may improve EV without changing universe, signal generation, "
            "risk sizing, exits, or LLM/news behavior."
        ),
        "alpha_hypothesis_category": "capital_allocation_entry_lifecycle",
        "parameters": {
            "single_causal_variable": "state-conditioned same-day core entry cap",
            "baseline": "no same-day entry cap beyond MAX_POSITIONS / sector cap",
            "tested_variants": {
                "cap2_when_min_index_below_0": {
                    "min(spy_pct_from_ma, qqq_pct_from_ma)": "<= 0.0",
                    "max_same_day_new_entries": 2,
                },
                "cap2_when_min_index_below_2pct": {
                    "min(spy_pct_from_ma, qqq_pct_from_ma)": "<= 0.02",
                    "max_same_day_new_entries": 2,
                },
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters before planning",
                "candidate ranking order",
                "all risk sizing rules",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
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
            (label, rows["baseline"][label]["metrics"]) for label in WINDOWS
        ),
        "after_metrics": {
            "best_variant": best_variant,
            **OrderedDict(
                (label, summaries[best_variant]["by_window"][label]["after"])
                for label in WINDOWS
            ),
        },
        "delta_metrics": {
            "best_variant": best_variant,
            **summaries[best_variant],
            "all_variants": summaries,
        },
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
                "If accepted, move the cap into production_parity.plan_entry_candidates "
                "and expose constants so run.py/backtester.py share the same behavior."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this tests deterministic "
                "entry lifecycle allocation instead of waiting on LLM data."
            ),
        },
        "history_guardrails": {
            "not_global_max_positions_retry": True,
            "not_sector_cap_retry": True,
            "not_addon_threshold_retry": True,
            "not_direct_bad_trade_filter": True,
            "why_not_simple_repeat": (
                "Prior global slot-count and sector-cap sweeps changed broad capacity. "
                "This tests a state-conditioned same-day cluster cap based on an "
                "observed adverse-entry family."
            ),
        },
        "rejection_reason": None if accepted else (
            "No state-conditioned entry-cluster cap passed fixed-window Gate 4."
        ),
        "next_retry_requires": [] if accepted else [
            "Do not promote same-day entry-cluster caps from the 2026-01-06 loss cluster.",
            "A valid retry needs forward evidence or an orthogonal event/news discriminator.",
            "Do not repeat nearby 2-entry caps with only a small min-index threshold change.",
        ],
        "rows": rows,
        "related_files": [
            "quant/experiments/exp_20260502_004_state_cluster_entry_cap.py",
            "data/experiments/exp-20260502-004/state_cluster_entry_cap.json",
            "docs/experiments/logs/exp-20260502-004.json",
            "docs/experiments/tickets/exp-20260502-004.json",
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
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "State-conditioned entry cluster cap",
        "summary": payload["hypothesis"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "aggregate": {
            key: value
            for key, value in payload["delta_metrics"].items()
            if key != "by_window" and key != "all_variants"
        },
        "next_action": (
            "Promote through shared production_parity helper."
            if payload["best_variant_gate4"]
            else "Do not promote; keep current entry planning."
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
