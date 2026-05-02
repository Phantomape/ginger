"""exp-20260502-017 trend SPY-leader non-core fallback replay.

Alpha search. This tests one capital-allocation variable: whether the accepted
plain risk-on SPY-relative leader 2.0x budget should remain broad for
breakouts but fall back for trend_long leaders outside the repeat-positive
trend sectors. This is intentionally sleeve-specific; prior sector-whitelist
tests cut breakout leaders too and damaged the strong window.
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


EXPERIMENT_ID = "exp-20260502-017"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "trend_spy_leader_noncore_fallback.json"
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

CORE_TREND_SECTORS = (
    "Technology",
    "Consumer Discretionary",
    "Communication Services",
    "Financials",
    "Commodities",
)

VARIANTS = OrderedDict([
    ("trend_noncore_else_1_25x", {"fallback_total_multiplier": 1.25}),
    ("trend_noncore_else_1_00x", {"fallback_total_multiplier": 1.00}),
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


def _is_target_signal(sig: dict) -> bool:
    return (
        sig.get("strategy") == "trend_long"
        and sig.get("sector") not in CORE_TREND_SECTORS
        and _is_plain_spy_leader_sizing(sig.get("sizing") or {})
    )


def _make_variant_sizer(original_size_signals, fallback_total_multiplier: float):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not _is_target_signal(sig):
                continue
            sizing = sig.get("sizing") or {}
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
            new_sizing["trend_spy_leader_noncore_fallback"] = fallback_total_multiplier
            sig["sizing"] = new_sizing
        return sized
    return size_signals


def _run_window(window: dict, variant: dict | None = None) -> dict:
    original_size_signals = pe.size_signals
    if variant is not None:
        pe.size_signals = _make_variant_sizer(
            original_size_signals,
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


def _target_trade_attribution(result: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        sizing = trade.get("sizing_multipliers") or {}
        if (
            trade.get("strategy") == "trend_long"
            and trade.get("sector") not in CORE_TREND_SECTORS
            and _is_plain_spy_leader_sizing(sizing)
        ):
            rows.append(trade)
    return {
        "trade_count": len(rows),
        "wins": sum(1 for row in rows if (row.get("pnl") or 0) > 0),
        "losses": sum(1 for row in rows if (row.get("pnl") or 0) <= 0),
        "total_pnl_usd": _round(sum(row.get("pnl") or 0 for row in rows), 2),
        "trades": [
            {
                "ticker": row.get("ticker"),
                "sector": row.get("sector"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": _round(row.get("pnl"), 2),
                "exit_reason": row.get("exit_reason"),
            }
            for row in rows
        ],
        "note": "Observed outcomes only; zero-risk signals do not become trades.",
    }


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    baseline_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    ev_delta = sum(row["delta"]["expected_value_score"] for row in rows.values())
    pnl_delta = sum(row["delta"]["total_pnl"] for row in rows.values())
    return {
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "sharpe_daily_delta_max": _round(max(row["delta"]["sharpe_daily"] for row in rows.values()), 6),
    }


def _gate4_passed(aggregate: dict) -> bool:
    return (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["sharpe_daily_delta_max"] > 0.10
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )


def main() -> int:
    baselines = {}
    for label, window in WINDOWS.items():
        result = _run_window(window)
        baselines[label] = {"raw": result, "metrics": _metrics(result)}

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            after_result = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(after_result)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "target_trade_attribution_before": _target_trade_attribution(
                    baselines[label]["raw"]
                ),
                "target_trade_attribution_after": _target_trade_attribution(after_result),
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
    decision = "accepted" if best["gate4_passed"] and best["aggregate"]["ev_windows_regressed"] == 0 else "rejected"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "alpha_hypothesis": (
            "Current 2.0x SPY-relative leader allocation is stronger in breakouts "
            "than in non-core trend sectors; a sleeve-specific trend fallback may "
            "reduce weak trend-leader leakage without cutting breakout winners."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": "trend_long non-core SPY-relative leader fallback sizing",
        "parameters": {
            "baseline_total_multiplier": 2.0,
            "core_trend_sectors_kept_at_2x": CORE_TREND_SECTORS,
            "tested_variants": VARIANTS,
            "best_variant": best_name,
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "variants": variants,
        "best_variant": best_name,
        "gate4_basis": (
            "Gate4 requires >10% aggregate EV lift, >0.1 Sharpe lift, >1pp "
            "drawdown reduction, >5% PnL lift, or more trades without win-rate "
            "decline; accepted variants also cannot regress EV in any fixed window."
        ),
        "rejection_reason": (
            None if decision == "accepted" else
            "The sleeve-specific fallback did not pass Gate 4 and/or regressed a fixed window."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, add constants and a shared portfolio_engine branch; "
                "run.py already consumes shared portfolio_engine sizing."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this uses existing "
                "deterministic sizing fields instead."
            ),
        },
        "history_guardrails": {
            "not_sector_whitelist_repeat": (
                "Prior sector whitelist cut all SPY leader sleeves. This test is "
                "trend_long-only and preserves breakout leader sizing."
            ),
            "not_global_spy_leader_multiplier_tuning": True,
            "locked_variables": [
                "entries",
                "exits",
                "candidate order",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "add-ons",
                "LLM/news replay",
                "pilot sleeve",
            ],
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "status": decision,
        "decision": decision,
        "title": "Trend SPY-leader non-core fallback",
        "summary": f"Best {best_name} Gate4={best['gate4_passed']}",
        "best_variant": best_name,
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            **best["aggregate"],
        },
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
