"""exp-20260503-046: SPY-relative leader excess-return margin gate.

Alpha search. Test one capital-allocation variable: whether the already
accepted SPY-relative leader sleeve should require a positive 20-day
ticker-vs-SPY excess-return margin before receiving the accepted risk-on
leader sizing, initial cap, and first add-on cap. This uses only
production-visible OHLCV-derived fields and does not change entries, exits,
candidate ranking, LLM/news replay, earnings logic, or the universe.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
import production_parity  # noqa: E402
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-046"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "spy_leader_margin_gate.json"
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

BASE_CONFIG = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
VARIANTS = OrderedDict([
    ("leader_margin_ge_1pct", 0.01),
    ("leader_margin_ge_2pct", 0.02),
    ("leader_margin_ge_3pct", 0.03),
    ("leader_margin_ge_5pct", 0.05),
])


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades") or []
    leader_trades = [
        trade for trade in trades
        if (
            (trade.get("sizing_multipliers") or {})
            .get("spy_relative_leader_risk_on_multiplier_applied", 1.0)
            > 1.0
        )
    ]
    addon_summary = result.get("addon_attribution") or {}
    addon_events = addon_summary.get("events") or []
    executed_addons = [row for row in addon_events if row.get("status") == "executed"]
    first_leader_addons = [
        row for row in executed_addons
        if row.get("addon_number") == 1
        and row.get("spy_relative_leader_addon_cap") is True
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
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "spy_leader_trade_count": len(leader_trades),
        "spy_leader_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in leader_trades),
            2,
        ),
        "addon_scheduled_count": addon_summary.get("scheduled"),
        "addon_executed_count": addon_summary.get("executed"),
        "first_leader_addons_executed": len(first_leader_addons),
        "converged": (result.get("convergence") or {}).get("converged"),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_was_margin_leader(
    pos: dict[str, Any],
    threshold: float,
    ticker_df=None,
    spy_df=None,
    entry_idx=None,
    spy_entry_idx=None,
) -> bool:
    multipliers = pos.get("sizing_multipliers") or {}
    if not multipliers and isinstance(pos.get("sizing"), dict):
        multipliers = pos["sizing"].get("sizing_multipliers") or {}
    if multipliers.get("spy_relative_leader_risk_on_multiplier_applied", 1.0) > 1.0:
        return True

    explicit_rel = _float_or_none(pos.get("ticker_ret20_minus_spy_pct"))
    if explicit_rel is not None:
        return explicit_rel >= threshold
    if pos.get("spy_relative_leader") is True and ticker_df is None:
        return True

    if ticker_df is None or spy_df is None or entry_idx is None or spy_entry_idx is None:
        return False
    if entry_idx < 20 or spy_entry_idx < 20:
        return False
    try:
        ticker_entry = float(ticker_df["Close"].iloc[entry_idx])
        ticker_base = float(ticker_df["Close"].iloc[entry_idx - 20])
        spy_entry = float(spy_df["Close"].iloc[spy_entry_idx])
        spy_base = float(spy_df["Close"].iloc[spy_entry_idx - 20])
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    if ticker_base <= 0 or spy_base <= 0:
        return False
    ticker_ret20 = (ticker_entry - ticker_base) / ticker_base
    spy_ret20 = (spy_entry - spy_base) / spy_base
    return (ticker_ret20 - spy_ret20) >= threshold


@contextmanager
def _spy_leader_margin_patch(threshold: float):
    original_enrich = risk_engine.enrich_signals
    original_backtester_position = backtester.position_was_spy_relative_leader
    original_production_position = production_parity.position_was_spy_relative_leader

    def patched_enrich(signals, features_dict, *args, **kwargs):
        enriched = original_enrich(signals, features_dict, *args, **kwargs)
        for sig in enriched:
            rel_spy_ret20 = _float_or_none(sig.get("ticker_ret20_minus_spy_pct"))
            if rel_spy_ret20 is None:
                continue
            sig["spy_relative_leader_raw"] = sig.get("spy_relative_leader") is True
            sig["spy_relative_leader_margin_threshold"] = threshold
            sig["spy_relative_leader"] = rel_spy_ret20 >= threshold
        return enriched

    def patched_position(pos, ticker_df=None, spy_df=None, entry_idx=None, spy_entry_idx=None):
        return _position_was_margin_leader(
            pos,
            threshold,
            ticker_df=ticker_df,
            spy_df=spy_df,
            entry_idx=entry_idx,
            spy_entry_idx=spy_entry_idx,
        )

    risk_engine.enrich_signals = patched_enrich
    backtester.position_was_spy_relative_leader = patched_position
    production_parity.position_was_spy_relative_leader = patched_position
    try:
        yield
    finally:
        risk_engine.enrich_signals = original_enrich
        backtester.position_was_spy_relative_leader = original_backtester_position
        production_parity.position_was_spy_relative_leader = original_production_position


def _run_window(
    universe: list[str],
    window: dict[str, Any],
    threshold: float | None = None,
) -> dict[str, Any]:
    context = (
        _spy_leader_margin_patch(threshold)
        if threshold is not None
        else nullcontext()
    )
    with context:
        result = BacktestEngine(
            universe=universe,
            start=window["start"],
            end=window["end"],
            config=dict(BASE_CONFIG),
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _run_variant(
    universe: list[str],
    threshold: float | None = None,
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        result = _run_window(universe, window, threshold=threshold)
        metrics = _metrics(result)
        rows[label] = {
            "metrics": metrics,
            "entry_decision_summary": result.get("entry_decision_summary"),
            "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution"),
        }
        variant_label = "baseline" if threshold is None else f"threshold={threshold:.2%}"
        print(
            f"[{label} {variant_label}] EV={metrics['expected_value_score']} "
            f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
            f"DD={metrics['max_drawdown_pct']} WR={metrics['win_rate']} "
            f"trades={metrics['trade_count']} leader_trades={metrics['spy_leader_trade_count']} "
            f"leader_addons={metrics['first_leader_addons_executed']}"
        )
    return rows


def _aggregate(
    before: OrderedDict[str, dict[str, Any]],
    after: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    deltas: OrderedDict[str, dict[str, Any]] = OrderedDict(
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
        sum(
            float(before[label]["metrics"]["expected_value_score"] or 0.0)
            for label in WINDOWS
        ),
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
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6)
        if baseline_ev else None,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_sum": total_pnl_delta,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6)
        if baseline_total_pnl else None,
        "ev_windows_improved": sum(
            1 for label in WINDOWS
            if (deltas[label]["expected_value_score"] or 0.0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS
            if (deltas[label]["expected_value_score"] or 0.0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS
            if (deltas[label]["total_pnl"] or 0.0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for label in WINDOWS
            if (deltas[label]["total_pnl"] or 0.0) < 0
        ),
        "max_drawdown_delta_min": min(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "max_drawdown_delta_max": max(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(deltas[label]["sharpe_daily"] for label in WINDOWS),
        "spy_leader_trade_count_delta_sum": sum(
            deltas[label]["spy_leader_trade_count"] for label in WINDOWS
        ),
        "spy_leader_pnl_delta_sum": round(
            sum(deltas[label]["spy_leader_pnl"] for label in WINDOWS),
            2,
        ),
        "first_leader_addons_delta_sum": sum(
            deltas[label]["first_leader_addons_executed"] for label in WINDOWS
        ),
    }


def _passes_gate4(delta: dict[str, Any]) -> bool:
    if delta["ev_windows_improved"] < 2 or delta["ev_windows_regressed"] > 0:
        return False
    return bool(
        (delta["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (delta["total_pnl_delta_pct"] or 0.0) > 0.05
        or delta["sharpe_daily_delta_max"] > 0.1
        or delta["max_drawdown_delta_min"] < -0.01
        or (
            delta["trade_count_delta_sum"] > 0
            and delta["win_rate_delta_min"] >= 0
        )
    )


def build_payload() -> dict[str, Any]:
    universe = get_universe()
    baseline = _run_variant(universe)
    variants: OrderedDict[str, OrderedDict[str, dict[str, Any]]] = OrderedDict()
    deltas: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for variant_name, threshold in VARIANTS.items():
        rows = _run_variant(universe, threshold=threshold)
        variants[variant_name] = rows
        deltas[variant_name] = _aggregate(baseline, rows)

    best_variant = max(
        deltas,
        key=lambda name: (
            deltas[name]["ev_windows_improved"],
            -deltas[name]["ev_windows_regressed"],
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
        "change_type": "capital_allocation_spy_relative_leader_margin_gate",
        "hypothesis": (
            "The accepted SPY-relative leader sleeve may be too broad at the "
            "margin. Requiring a positive 20-day ticker-vs-SPY excess-return "
            "margin may preserve true leaders while keeping marginal leaders "
            "on ordinary risk/cap treatment."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains production-aligned sample limited, so "
            "this tests a deterministic production-visible allocation alpha."
        ),
        "mechanism_insight_check": {
            "near_repeat": "qualified_new_discriminator",
            "notes": (
                "This does not retry nearby SPY leader multipliers, initial "
                "caps, add-on caps above 60%, target floors, second add-ons, "
                "or global ranking. It tests a new discriminator for the "
                "already accepted SPY-relative leader sleeve."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "minimum 20-day ticker-vs-SPY excess return required for "
                "SPY-relative leader treatment"
            ),
            "old_value": "ticker_ret20_minus_spy_pct > 0.00",
            "tested_values": dict(VARIANTS),
            "locked_variables": [
                "universe",
                "signal generation except spy_relative_leader boolean",
                "entry filters",
                "candidate ranking",
                "all non-SPY-leader sizing rules",
                "SPY-relative leader risk budget value",
                "SPY-relative leader initial position cap value",
                "SPY-relative leader first add-on cap value",
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
            label: cfg["snapshot"]
            for label, cfg in WINDOWS.items()
        },
        "market_regime_summary": {
            label: cfg["state_note"]
            for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"]
            for label in WINDOWS
        },
        "after_metrics": {
            variant: {
                label: variants[variant][label]["metrics"]
                for label in WINDOWS
            }
            for variant in VARIANTS
        },
        "delta_metrics": deltas,
        "best_variant": best_variant,
        "gate4": {
            "passed": gate4_passed,
            "basis": (
                "Accepted by the canonical three-window Gate 4 protocol."
                if gate4_passed else
                "Rejected because no margin threshold cleared the majority-window "
                "stability and materiality bar."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, implement the threshold as a shared constant "
                "used by risk_engine.enrich_signals and "
                "production_parity.position_was_spy_relative_leader, with tests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "This alpha does not rely on LLM data. LLM soft-ranking was "
                "skipped because current replay samples are insufficient for "
                "a production-aligned ranking experiment."
            ),
        },
        "rejection_reason": (
            None if gate4_passed else
            "The leader-margin discriminator did not materially improve the "
            "accepted SPY-relative leader sleeve across the fixed windows."
        ),
        "next_retry_requires": [
            "Do not retry simple SPY-relative leader excess-return thresholds without forward evidence or a different orthogonal discriminator.",
            "A valid retry should use event/news confirmation, volatility-adjusted excess return, or tail-risk evidence rather than another nearby pct margin.",
            "Any positive retry must be implemented in shared production/backtest policy before acceptance.",
        ],
        "related_files": [
            "quant/experiments/exp_20260503_046_spy_leader_margin_gate.py",
            "data/experiments/exp-20260503-046/spy_leader_margin_gate.json",
            "docs/experiments/logs/exp-20260503-046.json",
            "docs/experiments/tickets/exp-20260503-046.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(text + "\n", encoding="utf-8")

    print(
        f"\n{payload['experiment_id']} {payload['status']} "
        f"best={payload['best_variant']} "
        f"aggregate={payload['delta_metrics'][payload['best_variant']]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
