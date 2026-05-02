"""exp-20260502-015 SPY-relative leader absolute-momentum floor replay.

Alpha search. This tests one capital-allocation variable: whether otherwise
unmodified risk-on SPY-relative leaders should keep the accepted 2.0x risk
budget only when their own 20-day return is also positive/strong. This is not
another SPY-relative lookback, breadth confirmation, sector confirmation, or
wide-stop retry; the added discriminator is candidate absolute 20-day momentum.
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


EXPERIMENT_ID = "exp-20260502-015"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "spy_leader_absolute_momentum_floor.json"
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
    ("positive_20d_else_1_25x", {"min_ticker_ret20": 0.00, "fallback_total_multiplier": 1.25}),
    ("positive_20d_else_1_50x", {"min_ticker_ret20": 0.00, "fallback_total_multiplier": 1.50}),
    ("five_pct_20d_else_1_25x", {"min_ticker_ret20": 0.05, "fallback_total_multiplier": 1.25}),
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
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _is_plain_spy_leader_sizing(sizing: dict) -> bool:
    if not sizing:
        return False
    return (
        sizing.get("risk_on_unmodified_risk_multiplier_applied") == 2.0
        and sizing.get("spy_relative_leader_risk_on_multiplier_applied") == 2.0
    )


def _ticker_ret20(sig: dict) -> float | None:
    ticker_minus_spy = sig.get("ticker_ret20_minus_spy_pct")
    spy_ret20 = sig.get("spy_ret20_pct")
    if isinstance(ticker_minus_spy, (int, float)) and isinstance(spy_ret20, (int, float)):
        return ticker_minus_spy + spy_ret20
    return None


def _make_variant_sizer(original_size_signals, min_ticker_ret20: float, fallback_total_multiplier: float):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if not _is_plain_spy_leader_sizing(sizing):
                continue
            ticker_ret20 = _ticker_ret20(sig)
            if ticker_ret20 is None or ticker_ret20 >= min_ticker_ret20:
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            base_risk_pct = sizing.get("base_risk_pct")
            if not entry or not stop or base_risk_pct is None:
                continue
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=base_risk_pct * fallback_total_multiplier,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["base_risk_pct"] = base_risk_pct
            new_sizing["risk_on_unmodified_risk_multiplier_applied"] = fallback_total_multiplier
            new_sizing["spy_relative_leader_risk_on_multiplier_applied"] = fallback_total_multiplier
            new_sizing["spy_leader_absolute_momentum_floor"] = min_ticker_ret20
            new_sizing["spy_leader_ticker_ret20_pct"] = round(ticker_ret20, 4)
            sig["sizing"] = new_sizing
        return sized
    return size_signals


def _run_window(window: dict, variant: dict | None = None) -> dict:
    original_size_signals = pe.size_signals
    if variant is not None:
        pe.size_signals = _make_variant_sizer(
            original_size_signals,
            variant["min_ticker_ret20"],
            variant["fallback_total_multiplier"],
        )
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
    finally:
        pe.size_signals = original_size_signals
    return result


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
    )
    return {key: _round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in keys}


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
        "win_rate_delta_min": min(row["delta"]["win_rate"] for row in rows.values()),
        "max_drawdown_delta_max": max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baselines = {}
    for label, window in WINDOWS.items():
        result = _run_window(window)
        baseline_path = OUT_DIR / f"baseline_{label}.json"
        baseline_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        baselines[label] = _metrics(result)

    variants = {}
    for variant_name, variant in VARIANTS.items():
        rows = {}
        for label, window in WINDOWS.items():
            result = _run_window(window, variant)
            after = _metrics(result)
            rows[label] = {
                "window": window,
                "before": baselines[label],
                "after": after,
                "delta": _delta(baselines[label], after),
                "resized_trade_attribution": (
                    result.get("sizing_rule_trade_attribution") or {}
                ).get("spy_relative_leader_risk_on_multiplier_applied"),
            }
        aggregate = _aggregate(rows)
        aggregate["gate4_pass"] = (
            aggregate["aggregate_ev_delta_pct"] > 0.10
            or aggregate["aggregate_pnl_delta_pct"] > 0.05
            or any(row["delta"]["sharpe_daily"] > 0.1 for row in rows.values())
            or any(row["delta"]["max_drawdown_pct"] < -0.01 for row in rows.values())
        )
        variants[variant_name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
        }

    best_name, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["gate4_pass"],
            item[1]["aggregate"]["aggregate_ev_delta"],
            item[1]["aggregate"]["aggregate_pnl_delta"],
        ),
    )
    accepted = (
        best["aggregate"]["gate4_pass"]
        and best["aggregate"]["windows_ev_improved"] >= 2
        and best["aggregate"]["windows_ev_regressed"] == 0
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "alpha_hypothesis": (
            "Otherwise-unmodified risk-on SPY-relative leaders may be lower "
            "quality when their own 20-day return is weak; preserving the 2.0x "
            "budget only for absolute-momentum leaders could improve capital "
            "efficiency without changing entries."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": "SPY-relative leader absolute 20-day momentum floor",
        "parameters": {
            "baseline_total_multiplier": 2.0,
            "tested_variants": VARIANTS,
            "best_variant": best_name,
        },
        "date_range": {
            label: f"{row['start']} -> {row['end']}"
            for label, row in WINDOWS.items()
        },
        "snapshots": {label: row["snapshot"] for label, row in WINDOWS.items()},
        "market_regime_summary": {
            label: row["state_note"] for label, row in WINDOWS.items()
        },
        "variants": variants,
        "best_variant": best_name,
        "best_variant_gate4": best["aggregate"]["gate4_pass"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "default_behavior_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Production-aligned LLM outcome joins remain too sparse; this "
                "tests deterministic candidate momentum context instead."
            ),
        },
        "history_guardrails": {
            "not_plain_spy_leader_multiplier_retry": (
                "The baseline 2.0x multiplier is unchanged for leaders that "
                "clear the absolute-momentum floor; only weak-absolute-momentum "
                "leaders are tested for fallback sizing."
            ),
            "not_spy_relative_lookback_retry": True,
            "not_breadth_or_sector_confirmation_retry": True,
            "not_wide_stop_retry": True,
        },
        "gate4_basis": (
            "Promotion requires Gate 4 materiality and EV improvement in at least "
            "2/3 windows with no EV-regressed window."
        ),
        "rejection_reason": None if accepted else (
            "No tested absolute-momentum floor for SPY-relative leaders passed "
            "the multi-window Gate 4 robustness bar."
        ),
        "next_retry_requires": [
            "Do not retry nearby absolute 20-day return floors without forward evidence.",
            "A valid retry needs event/news/lifecycle context that separates weak-absolute leaders from temporary index-relative dislocations.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    TICKET_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": best_name,
        "aggregate": best["aggregate"],
    }, indent=2))


if __name__ == "__main__":
    main()
