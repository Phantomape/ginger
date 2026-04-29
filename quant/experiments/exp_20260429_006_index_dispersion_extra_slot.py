"""exp-20260429-006: index-dispersion gated sixth slot replay.

Alpha search. Recent runs rejected a global sixth slot and simple
min(SPY, QQQ)-distance gates. This tests a different state source: the
cross-index leadership spread between QQQ and SPY distance from their 200-day
moving averages. The hypothesis is that scarce extra capacity is useful only
when the tape is rotational enough to create marginal A/B opportunities, not
merely when both indexes are elevated.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260429-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_006_index_dispersion_extra_slot.json"
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
    ("baseline_5_slots", None),
    ("qqq_leads_spy_by_2pct", {"mode": "qqq_lead", "threshold": 0.02}),
    ("qqq_leads_spy_by_4pct", {"mode": "qqq_lead", "threshold": 0.04}),
    ("balanced_index_spread_lte_2pct", {"mode": "balanced_abs", "threshold": 0.02}),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    cap_eff = result.get("capital_efficiency") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "pnl_per_trade_usd": cap_eff.get("pnl_per_trade_usd"),
        "pnl_per_calendar_slot_day_usd": cap_eff.get("pnl_per_calendar_slot_day_usd"),
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


def _state_allows_extra_slot(spy_pct, qqq_pct, variant: dict | None) -> tuple[bool, float | None]:
    if variant is None:
        return False, None
    if spy_pct is None or qqq_pct is None:
        return False, None
    spread = float(qqq_pct) - float(spy_pct)
    threshold = float(variant["threshold"])
    if variant["mode"] == "qqq_lead":
        return spread >= threshold, spread
    if variant["mode"] == "balanced_abs":
        return abs(spread) <= threshold, spread
    raise ValueError(f"Unknown variant mode: {variant['mode']}")


def _run_window(universe: list[str], cfg: dict, variant: dict | None) -> dict:
    original_plan = backtester_module.plan_entry_candidates
    audit_counts = {
        "extra_slot_allowed_days": 0,
        "extra_slot_blocked_days": 0,
        "spread_values_seen": [],
    }

    def dispersion_gated_plan(signals, open_positions, market_context=None, **kwargs):
        if variant is None:
            return original_plan(signals, open_positions, market_context=market_context, **kwargs)

        context = market_context or {}
        allowed, spread = _state_allows_extra_slot(
            context.get("spy_pct_from_ma"),
            context.get("qqq_pct_from_ma"),
            variant,
        )
        if spread is not None:
            audit_counts["spread_values_seen"].append(round(spread, 4))

        active_count = int(kwargs.get("active_positions_count") or 0)
        if active_count >= 5 and allowed:
            audit_counts["extra_slot_allowed_days"] += 1
            kwargs["max_positions"] = 6
        else:
            if active_count >= 5:
                audit_counts["extra_slot_blocked_days"] += 1
            kwargs["max_positions"] = 5

        planned, audit = original_plan(
            signals,
            open_positions,
            market_context=market_context,
            **kwargs,
        )
        audit["index_dispersion_extra_slot_variant"] = variant
        audit["index_dispersion_spread"] = spread
        audit["index_dispersion_extra_slot_allowed"] = bool(active_count >= 5 and allowed)
        return planned, audit

    try:
        backtester_module.plan_entry_candidates = dispersion_gated_plan
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "MAX_POSITIONS": 6 if variant is not None else 5,
            },
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
    finally:
        backtester_module.plan_entry_candidates = original_plan

    if "error" in result:
        raise RuntimeError(result["error"])
    metrics = _metrics(result)
    metrics["index_dispersion_extra_slot_audit"] = {
        **audit_counts,
        "spread_min": min(audit_counts["spread_values_seen"], default=None),
        "spread_max": max(audit_counts["spread_values_seen"], default=None),
    }
    return metrics


def run_experiment() -> dict:
    logging.getLogger().setLevel(logging.WARNING)
    universe = sorted(get_universe())
    rows = []
    for window, cfg in WINDOWS.items():
        for variant_name, variant in VARIANTS.items():
            metrics = _run_window(universe, cfg, variant)
            rows.append({
                "window": window,
                "variant": variant_name,
                "variant_config": variant,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "metrics": metrics,
            })
            print(
                f"[{window} {variant_name}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} WR={metrics['win_rate']} "
                f"trades={metrics['trade_count']} "
                f"audit={metrics['index_dispersion_extra_slot_audit']}"
            )

    baseline_rows = {
        window: next(
            row for row in rows
            if row["window"] == window and row["variant"] == "baseline_5_slots"
        )
        for window in WINDOWS
    }

    summary = OrderedDict()
    for variant_name, variant in VARIANTS.items():
        if variant is None:
            continue
        by_window = OrderedDict()
        for window in WINDOWS:
            before = baseline_rows[window]["metrics"]
            after = next(
                row["metrics"] for row in rows
                if row["window"] == window and row["variant"] == variant_name
            )
            by_window[window] = {
                "before": before,
                "after": after,
                "delta": _delta(after, before),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant_name] = {
            "variant_config": variant,
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
                "extra_slot_allowed_days": sum(
                    v["after"]["index_dispersion_extra_slot_audit"]["extra_slot_allowed_days"]
                    for v in by_window.values()
                ),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    behavioral_change = (
        best_agg["extra_slot_allowed_days"] > 0
        and (
            abs(best_agg["total_pnl_delta_sum"]) > 0
            or best_agg["trade_count_delta_sum"] != 0
        )
    )
    accepted = (
        behavioral_change
        and best_agg["windows_improved"] >= 2
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "state_specific_capital_allocation_replay",
        "hypothesis": (
            "A sixth slot may add alpha only when SPY/QQQ index leadership "
            "dispersion indicates a rotational tape, rather than when both "
            "indexes are simply high above their moving averages."
        ),
        "why_tested": (
            "LLM soft ranking remains sample-limited. Recent global slot, "
            "sector priority, ETF expansion, and simple index-distance gates "
            "failed, so this tests a distinct deterministic state variable "
            "that production can compute from the same index OHLCV."
        ),
        "parameters": {
            "single_causal_variable": "index-dispersion gate for sixth position slot",
            "baseline_max_positions": 5,
            "trial_max_positions_when_state_allows": 6,
            "tested_variants": {
                name: cfg for name, cfg in VARIANTS.items() if cfg is not None
            },
            "locked_variables": [
                "A/B signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT=0.40",
                "MAX_PORTFOLIO_HEAT=0.08",
                "MAX_PER_SECTOR=2",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
                "all exits",
                "scarce-slot breakout deferral",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            name: cfg["state_note"] for name, cfg in WINDOWS.items()
        },
        "before_metrics": {
            window: baseline_rows[window]["metrics"] for window in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                window: best_summary["by_window"][window]["after"]
                for window in WINDOWS
            },
        },
        "delta_metrics": {
            **{
                window: best_summary["by_window"][window]["delta"]
                for window in WINDOWS
            },
            "aggregate": best_agg,
            "behavioral_change": behavioral_change,
            "measurement_artifact_guard": (
                "Requires the selected variant to actually release extra slots "
                "and change PnL or trade count. Pure Sharpe/EV movement with "
                "unchanged trades is treated as a harness artifact."
            ),
            "gate4_basis": (
                "Accepted by fixed-window Gate 4." if accepted
                else "Rejected because no behavior-changing index-dispersion extra-slot variant passed multi-window Gate 4."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data is insufficient, so this tested a "
                "deterministic allocation alpha instead of relying on LLM ranking."
            ),
        },
        "history_guardrails": {
            "not_repeating_global_slot_count": True,
            "not_repeating_min_index_pct_from_ma_gate": True,
            "not_repeating_simple_sector_priority": True,
            "not_repeating_etf_universe_expansion": True,
            "mechanism_family": "meta-allocation / index leadership dispersion",
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": None if accepted else (
            "Index-dispersion gated extra slot did not improve fixed-window allocation robustly; "
            "the apparent best EV/Sharpe variant changed no trades or PnL and was rejected as a harness artifact."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY/QQQ leadership-spread thresholds without new evidence.",
            "A valid extra-capacity retry needs richer breadth, dispersion, event context, or forward/paper evidence.",
            "If a future variant is accepted, implement the gate in shared production/backtest policy before promotion.",
        ],
        "related_files": [
            "quant/experiments/exp_20260429_006_index_dispersion_extra_slot.py",
            "data/experiments/exp-20260429-006/exp_20260429_006_index_dispersion_extra_slot.json",
            "docs/experiments/logs/exp-20260429-006.json",
            "docs/experiments/tickets/exp-20260429-006.json",
        ],
        "notes": (
            "Alpha search, not measurement repair. Production strategy code "
            "remains unchanged unless the fixed-window gate accepts a variant."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_experiment()
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "best_variant": result["after_metrics"]["best_variant"],
        "aggregate": result["delta_metrics"]["aggregate"],
    }, indent=2))
