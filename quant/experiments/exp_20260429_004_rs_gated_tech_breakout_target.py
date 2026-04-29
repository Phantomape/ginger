"""exp-20260429-004: RS-gated Technology breakout target replay.

Alpha search. Prior Technology breakout target widening failed because it
damaged the dominant late_strong window when applied to every Technology
breakout. This runner tests a different causal variable: only widen the target
for Technology breakouts that already show strong relative strength versus SPY.

Production defaults remain unchanged unless the fixed-window replay passes
Gate 4 and a shared production/backtest policy is added.
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

import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260429-004"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_004_rs_gated_tech_breakout_target.json"
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
    ("tech_breakout_rs_5pct_target_5atr", {"min_rs_vs_spy": 0.05, "target_mult": 5.0}),
    ("tech_breakout_rs_5pct_target_6atr", {"min_rs_vs_spy": 0.05, "target_mult": 6.0}),
    ("tech_breakout_rs_10pct_target_6atr", {"min_rs_vs_spy": 0.10, "target_mult": 6.0}),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    cap_eff = result.get("capital_efficiency") or {}
    addon = result.get("addon_attribution") or {}
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
        "addon_executed": addon.get("executed"),
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


def _retarget(sig: dict, target_mult: float) -> dict:
    entry = sig.get("entry_price")
    stop = sig.get("stop_price")
    if not entry or not stop or entry <= stop:
        return sig
    risk_per_share = entry - stop
    atr_proxy = risk_per_share / 1.5
    target = round(entry + target_mult * atr_proxy, 2)
    reward = round(target - entry, 2)
    rr_ratio = round(reward / risk_per_share, 2) if risk_per_share > 0 else None
    return {
        **sig,
        "target_price": target,
        "reward_per_share": reward,
        "risk_reward_ratio": rr_ratio,
        "target_mult_used": target_mult,
        "rs_gated_tech_breakout_target_applied": True,
    }


def _eligible(sig: dict, rule: dict) -> bool:
    if sig.get("strategy") != "breakout_long":
        return False
    ticker = (sig.get("ticker") or "").upper()
    if sig.get("sector") != "Technology" and SECTOR_MAP.get(ticker) != "Technology":
        return False
    conditions = sig.get("conditions_met") or {}
    rs_vs_spy = conditions.get("rs_vs_spy")
    return rs_vs_spy is not None and rs_vs_spy >= rule["min_rs_vs_spy"]


def _run_window(universe: list[str], cfg: dict, rule: dict | None) -> dict:
    original_enrich = risk_engine.enrich_signals
    retargeted = []

    def rs_gated_enrich(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        if not rule:
            return enriched
        out = []
        for sig in enriched:
            if _eligible(sig, rule):
                new_sig = _retarget(sig, rule["target_mult"])
                retargeted.append({
                    "ticker": new_sig.get("ticker"),
                    "strategy": new_sig.get("strategy"),
                    "sector": new_sig.get("sector"),
                    "rs_vs_spy": (new_sig.get("conditions_met") or {}).get("rs_vs_spy"),
                    "old_target_price": sig.get("target_price"),
                    "new_target_price": new_sig.get("target_price"),
                    "target_mult": rule["target_mult"],
                })
                out.append(new_sig)
            else:
                out.append(sig)
        return out

    try:
        risk_engine.enrich_signals = rs_gated_enrich
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
        risk_engine.enrich_signals = original_enrich

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "retargeted_count": len(retargeted),
        "retargeted_signals": retargeted,
    }


def _aggregate(by_window: OrderedDict) -> dict:
    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    return {
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
        "retargeted_count_sum": sum(v["retargeted_count"] for v in by_window.values()),
    }


def run_experiment() -> dict:
    universe = sorted(get_universe())
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, rule in VARIANTS.items():
            result = _run_window(universe, cfg, rule)
            rows.append({
                "window": label,
                "variant": variant,
                "rule": rule,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} retargeted={result['retargeted_count']}"
            )

    baseline_rows = {
        label: next(
            row for row in rows
            if row["window"] == label and row["variant"] == "baseline"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant, rule in VARIANTS.items():
        if rule is None:
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            candidate = next(
                row for row in rows
                if row["window"] == label and row["variant"] == variant
            )
            by_window[label] = {
                "before": before,
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], before),
                "retargeted_count": candidate["retargeted_count"],
            }
        summary[variant] = {
            "rule": rule,
            "by_window": by_window,
            "aggregate": _aggregate(by_window),
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
    accepted = (
        best_agg["windows_improved"] >= 2
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
        "change_type": "rs_gated_exit_target_replay",
        "hypothesis": (
            "Technology breakout target widening may be useful only when the "
            "candidate already shows strong relative strength versus SPY, avoiding "
            "the broad target-width damage seen in exp-20260428-004."
        ),
        "why_tested": (
            "LLM soft ranking remains sample-limited. Recent slot, ETF, gap, and "
            "global ordering experiments were rejected, so this tests a production-"
            "replayable exit alpha using an existing candidate-level context field."
        ),
        "parameters": {
            "single_causal_variable": "RS-gated Technology breakout target width",
            "baseline": "current production target path",
            "tested_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT=0.40",
                "MAX_POSITIONS=5",
                "MAX_PORTFOLIO_HEAT=0.08",
                "same-day sector cap",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
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
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
            "rejected_variants": {
                variant: data["aggregate"]
                for variant, data in summary.items()
                if variant != best_variant
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted only if the best RS-gated target variant improves a "
                "majority of windows without regression and passes a materiality guard."
                if accepted
                else "Rejected because the best RS-gated target variant did not pass multi-window Gate 4."
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
                "LLM soft-ranking data remains insufficient, so this tested a "
                "deterministic candidate-level exit alpha instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_broad_technology_breakout_target_width": True,
            "not_repeating_gap_or_slot_capacity_sweeps": True,
            "mechanism_family": "candidate-context-gated exit target",
        },
        "summary": summary,
        "rows": rows,
        "rejection_reason": None if accepted else (
            "RS-gated Technology breakout target widening did not pass fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby Technology breakout target widths or RS thresholds without a new state/event source.",
            "A valid retry needs orthogonal event context, LLM grading coverage, or forward evidence.",
            "If a target-width variant is ever accepted, implement it in shared production/backtest enrichment before promotion.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "decision": payload["decision"],
        "best_variant": best_variant,
        "aggregate": best_agg,
        "next_retry_requires": payload["next_retry_requires"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_experiment()
    agg = result["delta_metrics"]["aggregate"]
    print(
        f"{result['experiment_id']} {result['decision']} "
        f"best={result['delta_metrics']['best_variant']} "
        f"EV_delta_sum={agg['expected_value_score_delta_sum']} "
        f"PnL_delta={agg['total_pnl_delta_sum']} "
        f"windows={agg['windows_improved']}/{agg['windows_regressed']}"
    )
