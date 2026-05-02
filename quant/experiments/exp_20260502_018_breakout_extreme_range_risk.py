"""exp-20260502-018 breakout extreme-range risk probe.

Alpha search. Test one candidate quality variable: whether breakout_long
signals whose signal-day range is extremely large versus ATR should receive
less risk. This uses an existing production signal field
conditions_met.daily_range_vs_atr and leaves entry, exit, ranking, universe,
LLM, news, and earnings behavior unchanged.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-018"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "breakout_extreme_range_risk.json"
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
    ("range_2_5_atr_0_50x", {"min_daily_range_vs_atr": 2.5, "risk_multiplier": 0.50}),
    ("range_2_5_atr_0_25x", {"min_daily_range_vs_atr": 2.5, "risk_multiplier": 0.25}),
    ("range_3_0_atr_0_50x", {"min_daily_range_vs_atr": 3.0, "risk_multiplier": 0.50}),
])

_state = {"eligible_signals": 0}


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
    touched_trades = 0
    touched_pnl = 0.0
    for trade in result.get("trades", []):
        sizing = trade.get("sizing") or {}
        if "breakout_extreme_range_risk_multiplier_applied" in sizing:
            touched_trades += 1
            touched_pnl += float(trade.get("pnl") or 0.0)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "eligible_signals": _state["eligible_signals"],
        "touched_trades": touched_trades,
        "touched_trade_pnl": round(touched_pnl, 2),
    }


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
        "eligible_signals",
        "touched_trades",
        "touched_trade_pnl",
    )
    return {key: _round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in keys}


def _make_variant_sizer(original_size_signals, min_daily_range_vs_atr: float, risk_multiplier: float):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if sig.get("strategy") != "breakout_long":
                continue
            daily_range_vs_atr = (sig.get("conditions_met") or {}).get("daily_range_vs_atr")
            if daily_range_vs_atr is None or daily_range_vs_atr < min_daily_range_vs_atr:
                continue
            sizing = sig.get("sizing") or {}
            current_risk_pct = sizing.get("risk_pct")
            if current_risk_pct is None or current_risk_pct <= 0:
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            if not entry or not stop or entry <= 0 or stop <= 0 or stop >= entry:
                continue
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=current_risk_pct * risk_multiplier,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["risk_pct_before_breakout_extreme_range"] = current_risk_pct
            new_sizing["breakout_extreme_range_min_daily_range_vs_atr"] = min_daily_range_vs_atr
            new_sizing["breakout_extreme_range_risk_multiplier_applied"] = risk_multiplier
            sig["sizing"] = new_sizing
            _state["eligible_signals"] += 1
        return sized
    return size_signals


def _run_window(universe: list[str], window: dict, variant: dict | None = None) -> dict:
    original_size_signals = pe.size_signals
    _state["eligible_signals"] = 0
    if variant is not None:
        pe.size_signals = _make_variant_sizer(
            original_size_signals,
            variant["min_daily_range_vs_atr"],
            variant["risk_multiplier"],
        )
    try:
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    finally:
        pe.size_signals = original_size_signals
    if "error" in result:
        raise RuntimeError(result["error"])
    return {"metrics": _metrics(result), "trades": result.get("trades", [])}


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    variant_ev = sum(row["after"]["expected_value_score"] for row in rows.values())
    baseline_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    variant_pnl = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_ev_sum": _round(baseline_ev, 4),
        "variant_ev_sum": _round(variant_ev, 4),
        "aggregate_ev_delta": _round(variant_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": _round((variant_ev - baseline_ev) / baseline_ev if baseline_ev else None, 6),
        "baseline_pnl_sum": _round(baseline_pnl, 2),
        "variant_pnl_sum": _round(variant_pnl, 2),
        "aggregate_pnl_delta": _round(variant_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": _round((variant_pnl - baseline_pnl) / baseline_pnl if baseline_pnl else None, 6),
        "windows_ev_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "windows_ev_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "windows_pnl_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "windows_pnl_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "win_rate_delta_min": min(row["delta"]["win_rate"] for row in rows.values()),
        "max_drawdown_delta_max": max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "eligible_signal_count": sum(row["after"]["eligible_signals"] for row in rows.values()),
        "touched_trade_count": sum(row["after"]["touched_trades"] for row in rows.values()),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["windows_ev_improved"] < 2 or aggregate["windows_ev_regressed"] > 0:
        return False
    if aggregate["aggregate_ev_delta_pct"] and aggregate["aggregate_ev_delta_pct"] > 0.10:
        return True
    if aggregate["aggregate_pnl_delta_pct"] and aggregate["aggregate_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    baseline = OrderedDict()
    for label, window in WINDOWS.items():
        baseline[label] = _run_window(universe, window)
        print(f"baseline {label}: {baseline[label]['metrics']}")

    variants = OrderedDict()
    for variant_name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            after = _run_window(universe, window, variant)
            rows[label] = {
                "before": baseline[label]["metrics"],
                "after": after["metrics"],
                "delta": _delta(baseline[label]["metrics"], after["metrics"]),
            }
            print(f"{variant_name} {label}: {rows[label]['after']} delta={rows[label]['delta']}")
        aggregate = _aggregate(rows)
        variants[variant_name] = {
            "parameters": variant,
            "by_window": rows,
            "aggregate": aggregate,
            "gate4_pass": _passes_gate4(aggregate),
        }

    best_variant = max(
        variants,
        key=lambda name: variants[name]["aggregate"]["aggregate_ev_delta"],
    )
    best = variants[best_variant]
    decision = "accepted" if best["gate4_pass"] else "rejected"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "allocation_sizing_probe",
        "hypothesis": (
            "Breakout_long signals with extremely large signal-day range versus ATR may be "
            "late/exhausted entries; reducing only that existing breakout risk sleeve should "
            "improve EV without changing candidate generation."
        ),
        "alpha_hypothesis_category": "entry_quality_sizing",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains blocked by candidate-outcome join sparsity, so this run "
            "tests a deterministic A/B alpha using existing production signal fields."
        ),
        "mechanism_insight_check": {
            "near_repeat": False,
            "notes": (
                "This is not a nearby SPY-relative leader, Technology cofire, add-on, sector ETF, "
                "or commodity cap retry. It tests the independent breakout signal-day extension field."
            ),
        },
        "parameters": {
            "single_causal_variable": "breakout_long signal-day daily_range_vs_atr sizing haircut",
            "screened_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "entry rules",
                "exit rules",
                "candidate ranking",
                "non-breakout signals",
                "breakout signals below threshold",
                "accepted sector/DTE/gap/near-high sizing rules",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
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
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"]
            for label, row in baseline.items()
        },
        "after_metrics": {
            name: {
                label: row["after"]
                for label, row in variant["by_window"].items()
            }
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"]
            for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": best["gate4_pass"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "notes": (
                "Rejected probes are runtime-only. If a future variant passes, implement the sizing "
                "rule in portfolio_engine so backtester and run.py share the same policy."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": None if decision == "accepted" else (
            "Gate 4 failed. The best daily-range haircut did not improve EV in a majority "
            "of the three fixed windows and/or failed the required magnitude thresholds."
        ),
        "next_retry_requires": [] if decision == "accepted" else [
            "Do not retry nearby global breakout daily_range_vs_atr thresholds or simple haircuts.",
            "A valid retry needs a richer discriminator, such as event/news confirmation or hold-path attribution.",
            "Do not promote this into portfolio_engine without a fresh three-window pass.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_018_breakout_extreme_range_risk.py",
            "data/experiments/exp-20260502-018/breakout_extreme_range_risk.json",
            "docs/experiments/logs/exp-20260502-018.json",
            "docs/experiments/tickets/exp-20260502-018.json",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    payload = build_payload()
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(text + "\n", encoding="utf-8")

    log_line = json.dumps(payload, separators=(",", ":"))
    experiment_log = REPO_ROOT / "docs" / "experiment_log.jsonl"
    existing = experiment_log.read_text(encoding="utf-8") if experiment_log.exists() else ""
    if f'"experiment_id":"{EXPERIMENT_ID}"' not in existing and f'"experiment_id": "{EXPERIMENT_ID}"' not in existing:
        with experiment_log.open("a", encoding="utf-8") as fh:
            fh.write(log_line + "\n")

    print(f"{EXPERIMENT_ID} {payload['decision']} best={payload['best_variant']}")
    print(json.dumps(payload["delta_metrics"][payload["best_variant"]], indent=2))
    return 0 if payload["decision"] in {"accepted", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
