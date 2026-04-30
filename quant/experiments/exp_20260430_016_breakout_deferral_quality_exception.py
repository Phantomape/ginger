"""exp-20260430-016 breakout deferral quality exception.

Alpha search. Tests a narrow exception to the accepted scarce-slot breakout
deferral: allow only high-quality breakout candidates near their highs to
compete for the last slot. This is distinct from disabling deferral or adding
simple index-state caps.
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
import production_parity as pp  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260430-016"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_016_breakout_deferral_quality_exception.json"
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
    ("baseline_deferral", None),
    ("tqs90_near3pct_exception", {"min_tqs": 0.90, "min_pct_from_high": -0.03}),
    ("tqs85_near5pct_exception", {"min_tqs": 0.85, "min_pct_from_high": -0.05}),
])


def _metrics(result: dict) -> dict:
    reasons = result.get("entry_execution_attribution", {}).get("reason_counts") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "entered": reasons.get("entered", 0),
        "slot_sliced": reasons.get("slot_sliced", 0),
        "breakout_deferred": scarce.get("breakout_deferred", 0),
        "gap_cancel": reasons.get("gap_cancel", 0),
        "adverse_gap_down_cancel": reasons.get("adverse_gap_down_cancel", 0),
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


def _quality_exception_plan(original_plan, rule):
    def wrapper(
        signals,
        open_positions,
        market_context=None,
        max_positions=pp.MAX_POSITIONS,
        defer_breakout_when_slots_lte=pp.DEFER_BREAKOUT_WHEN_SLOTS_LTE,
        defer_breakout_max_min_index_pct_from_ma=pp.DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
        active_positions_count=None,
    ):
        if rule is None:
            return original_plan(
                signals,
                open_positions,
                market_context=market_context,
                max_positions=max_positions,
                defer_breakout_when_slots_lte=defer_breakout_when_slots_lte,
                defer_breakout_max_min_index_pct_from_ma=defer_breakout_max_min_index_pct_from_ma,
                active_positions_count=active_positions_count,
            )

        market_context = market_context or {}
        input_signals = list(signals or [])
        active_positions = (
            int(active_positions_count)
            if active_positions_count is not None
            else len(pp._positive_positions(open_positions))
        )
        slots = max(0, max_positions - active_positions)

        planned = list(input_signals)
        deferred_breakouts = []
        min_index_pct_from_ma = None
        state_ok = True
        if defer_breakout_max_min_index_pct_from_ma is not None:
            spy_pct = market_context.get("spy_pct_from_ma")
            qqq_pct = market_context.get("qqq_pct_from_ma")
            if spy_pct is not None and qqq_pct is not None:
                min_index_pct_from_ma = min(spy_pct, qqq_pct)
                state_ok = min_index_pct_from_ma <= defer_breakout_max_min_index_pct_from_ma
            else:
                state_ok = False

        if (
            defer_breakout_when_slots_lte is not None
            and slots <= defer_breakout_when_slots_lte
            and state_ok
        ):
            kept = []
            for sig in planned:
                is_breakout = sig.get("strategy") == "breakout_long"
                tqs = sig.get("trade_quality_score")
                pct_from_high = sig.get("pct_from_52w_high")
                allow_exception = (
                    is_breakout
                    and tqs is not None
                    and pct_from_high is not None
                    and float(tqs) >= rule["min_tqs"]
                    and float(pct_from_high) >= rule["min_pct_from_high"]
                )
                if is_breakout and not allow_exception:
                    deferred_breakouts.append({
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sig.get("sector", "Unknown"),
                        "available_slots": slots,
                        "trade_quality_score": sig.get("trade_quality_score"),
                        "confidence_score": sig.get("confidence_score"),
                        "pct_from_52w_high": sig.get("pct_from_52w_high"),
                        "entry_price": sig.get("entry_price"),
                        "stop_price": sig.get("stop_price"),
                        "target_price": sig.get("target_price"),
                        "min_index_pct_from_ma": min_index_pct_from_ma,
                    })
                else:
                    kept.append(sig)
            planned = kept

        signals_after_deferral = len(planned)
        slot_sliced = planned[slots:] if slots >= 0 else planned
        planned = planned[:slots]

        return planned, {
            "active_positions": active_positions,
            "max_positions": max_positions,
            "available_slots": slots,
            "signals_before_entry_plan": len(input_signals),
            "signals_after_deferral": signals_after_deferral,
            "signals_after_entry_plan": len(planned),
            "deferred_breakout_signals": deferred_breakouts,
            "slot_sliced_signals": slot_sliced,
            "defer_breakout_when_slots_lte": defer_breakout_when_slots_lte,
            "defer_breakout_max_min_index_pct_from_ma": (
                defer_breakout_max_min_index_pct_from_ma
            ),
            "min_index_pct_from_ma": min_index_pct_from_ma,
            "breakout_deferral_quality_exception": rule,
        }

    return wrapper


def _run_window(universe: list[str], cfg: dict, rule: dict | None) -> dict:
    original_pp_plan = pp.plan_entry_candidates
    original_bt_plan = bt.plan_entry_candidates
    patched = _quality_exception_plan(original_pp_plan, rule)
    pp.plan_entry_candidates = patched
    bt.plan_entry_candidates = patched
    try:
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
        pp.plan_entry_candidates = original_pp_plan
        bt.plan_entry_candidates = original_bt_plan

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
        "scarce_slot_attribution": result.get("scarce_slot_attribution"),
    }


def _aggregate(summary: OrderedDict) -> dict:
    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in summary.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in summary.values()), 2)
    return {
        "expected_value_score_delta_sum": round(
            sum(v["delta"]["expected_value_score"] for v in summary.values()),
            6,
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
        "windows_improved": sum(
            1 for v in summary.values() if v["delta"]["expected_value_score"] > 0
        ),
        "windows_regressed": sum(
            1 for v in summary.values() if v["delta"]["expected_value_score"] < 0
        ),
        "max_drawdown_delta_max": max(v["delta"]["max_drawdown_pct"] for v in summary.values()),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in summary.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in summary.values()),
    }


def _build_payload() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, rule in VARIANTS.items():
            result = _run_window(universe, cfg, rule)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "quality_exception_rule": rule,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} deferred={m['breakout_deferred']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_deferral"
        )
        for label in WINDOWS
    }
    summaries = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(
                r for r in rows if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        summaries[variant] = {"by_window": by_window, "aggregate": _aggregate(by_window)}

    best_variant, best_summary = max(
        summaries.items(),
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
        and best_agg["expected_value_score_delta_sum"] > 0.10
        and (
            best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "scarce_slot_breakout_deferral_quality_exception",
        "hypothesis": (
            "The accepted one-slot breakout deferral may be too blunt for "
            "high-quality breakout candidates already close to highs; a narrow "
            "quality exception could improve scarce-slot allocation without "
            "reopening broad breakout noise."
        ),
        "parameters": {
            "single_causal_variable": "quality exception inside scarce-slot breakout deferral",
            "baseline": "defer all breakout_long when available slots <= 1",
            "tested_values": {
                name: rule for name, rule in VARIANTS.items() if rule is not None
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters before scarce-slot planning",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "all sizing multipliers",
                "gap cancels",
                "add-ons",
                "all exits",
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
        },
        "delta_metrics": {
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
        },
        "gate4_basis": (
            "Accepted by fixed-window Gate 4."
            if accepted
            else "Rejected: no breakout deferral quality exception cleared multi-window Gate 4."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "temporary_shared_helper_patch_tested": True,
            "rolled_back_after_rejection": not accepted,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this deterministic "
                "scarce-slot routing alpha was tested instead."
            ),
        },
        "history_guardrails": {
            "not_disable_deferral": True,
            "not_index_state_cap": True,
            "not_sector_priority": True,
            "not_tqs_global_sort": True,
        },
        "rejection_reason": (
            None if accepted
            else "The best quality exception failed expected-value/PnL materiality or window consistency."
        ),
        "do_not_repeat_without_new_evidence": [
            "High-TQS near-high breakout exceptions to one-slot deferral.",
            "Treating fewer deferred breakouts as alpha without executed-trade improvement.",
        ],
        "next_retry_requires": [
            "A new event/news discriminator or candidate replacement audit proving the allowed breakout beats the displaced trade.",
            "A promoted rule must live in production_parity.plan_entry_candidates and be surfaced in both run.py and backtester.py.",
        ],
        "rows": rows,
        "related_files": [
            "quant/experiments/exp_20260430_016_breakout_deferral_quality_exception.py",
            "data/experiments/exp-20260430-016/exp_20260430_016_breakout_deferral_quality_exception.json",
            "docs/experiments/logs/exp-20260430-016.json",
            "docs/experiments/tickets/exp-20260430-016.json",
        ],
    }


def main() -> None:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in payload.items() if k != "rows"}, ensure_ascii=False) + "\n")
    print(f"decision={payload['decision']} best={payload['after_metrics']['best_variant']}")
    print(json.dumps(payload["delta_metrics"]["aggregate"], indent=2))


if __name__ == "__main__":
    main()
