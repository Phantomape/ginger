"""exp-20260510-021: effective risk-slot accounting replay.

Alpha search. This tests a single capital-allocation variable: count occupied
entry capacity by actual risk budget units instead of nominal open positions.
The script leaves production/backtest source files unchanged by importing a
temporary patched BacktestEngine at runtime. Any positive result is replay-only
until the same policy is implemented in shared production/backtest code.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-021"
STEM = "effective_risk_slot_replay"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _patched_backtester_module(temp_dir: Path):
    source_path = QUANT_DIR / "backtester.py"
    source = source_path.read_text(encoding="utf-8")

    old_helper = (
        "        def _core_position_count():\n"
        "            return sum(1 for p in positions if getattr(p, \"sleeve\", \"core\") == \"core\")\n"
    )
    new_helper = old_helper + (
        "\n"
        "        def _core_effective_risk_position_count():\n"
        "            risk_units = 0.0\n"
        "            for p in positions:\n"
        "                if getattr(p, \"sleeve\", \"core\") != \"core\":\n"
        "                    continue\n"
        "                actual = getattr(p, \"actual_risk_pct\", None)\n"
        "                base = getattr(p, \"base_risk_pct\", None)\n"
        "                try:\n"
        "                    actual = float(actual)\n"
        "                    base = float(base)\n"
        "                except (TypeError, ValueError):\n"
        "                    risk_units += 1.0\n"
        "                    continue\n"
        "                if base <= 0:\n"
        "                    risk_units += 1.0\n"
        "                    continue\n"
        "                risk_units += max(0.0, actual / base)\n"
        "            return int(math.ceil(risk_units))\n"
        "\n"
        "        def _core_position_count_for_entry():\n"
        "            if self.config.get(\"EFFECTIVE_RISK_SLOT_ACCOUNTING\"):\n"
        "                return _core_effective_risk_position_count()\n"
        "            return _core_position_count()\n"
    )
    if old_helper not in source:
        raise RuntimeError("Backtester helper patch anchor not found")
    source = source.replace(old_helper, new_helper, 1)

    replacements = {
        '            core_slots_full = _core_position_count() >= self.config["MAX_POSITIONS"]':
            '            core_slots_full = _core_position_count_for_entry() >= self.config["MAX_POSITIONS"]',
        "                active_positions_count=_core_position_count(),":
            "                active_positions_count=_core_position_count_for_entry(),",
    }
    for old, new in replacements.items():
        if old not in source:
            raise RuntimeError(f"Backtester patch anchor not found: {old}")
        source = source.replace(old, new, 1)

    temp_path = temp_dir / "backtester.py"
    temp_path.write_text(source, encoding="utf-8")
    module_name = f"{EXPERIMENT_ID.replace('-', '_')}_patched_backtester"
    spec = importlib.util.spec_from_file_location(module_name, temp_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to build patched backtester module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tail_loss_share(trades: list[dict[str, Any]], n: int = 5) -> float | None:
    losses = sorted(
        [abs(float(t.get("pnl") or 0.0)) for t in trades if float(t.get("pnl") or 0.0) < 0],
        reverse=True,
    )
    if not losses:
        return None
    return round(sum(losses[:n]) / sum(losses), 4)


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    ordered = sorted(trades, key=lambda t: (t.get("exit_date") or "", t.get("entry_date") or ""))
    streak = 0
    worst = 0
    for trade in ordered:
        if float(trade.get("pnl") or 0.0) < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades") or []
    worst_trade_pct = None
    if trades:
        worst_trade_pct = min(float(t.get("pnl_pct_net") or 0.0) for t in trades)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(worst_trade_pct, 4),
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "tail_loss_share": _tail_loss_share(trades),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
    return out


def _run_window(backtester_module, label: str, spec: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    engine = backtester_module.BacktestEngine(
        sorted(get_universe()),
        start=spec["start"],
        end=spec["end"],
        config=config,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    return {
        "label": label,
        "metrics": _metrics(result),
        "entry_execution_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("decision_counts", {}),
        "trades": result.get("trades") or [],
    }


def _aggregate(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum((m.get("expected_value_score") or 0.0) for m in metrics_by_window.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum((m.get("total_pnl") or 0.0) for m in metrics_by_window.values()),
            2,
        ),
        "trade_count_sum": sum(int(m.get("trade_count") or 0) for m in metrics_by_window.values()),
        "min_survival_rate": _round(
            min((m.get("survival_rate") or 0.0) for m in metrics_by_window.values()),
            4,
        ),
        "max_drawdown_pct_max": _round(
            max((m.get("max_drawdown_pct") or 0.0) for m in metrics_by_window.values()),
            4,
        ),
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} Effective Risk-Slot Replay",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- gate4_passed: {payload['gate4']['passed']}",
        f"- aggregate EV delta: {summary['aggregate_delta']['expected_value_score_sum']}",
        f"- aggregate PnL delta: {summary['aggregate_delta']['total_pnl_sum']}",
        f"- windows EV improved: {summary['windows_ev_improved']}",
        f"- windows EV regressed: {summary['windows_ev_regressed']}",
        "",
        "## Three-Window Metrics",
        "",
        "| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Base DD | After DD | Trades | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {bdd:.4f} | {add:.4f} | {trades} | {surv:.4f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=after["trade_count"],
                surv=after["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Replay-only runtime patch; production files are unchanged.",
            "- A positive result still requires shared `production_parity.py` / `run.py` / `backtester.py` implementation and parity tests before live/default use.",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_experiment_log(payload: dict[str, Any]) -> None:
    record = {
        "timestamp": payload["generated_at"],
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "date_range": payload["date_range"],
        "backtest_protocol": "docs/backtesting.md canonical three-window fixed snapshot protocol",
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["summary"]["aggregate_delta"]["expected_value_score_sum"],
        "decision": payload["decision"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }
    with EXPERIMENT_LOG_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{EXPERIMENT_ID}-") as temp_name:
        backtester_module = _patched_backtester_module(Path(temp_name))
        baseline_config = {"EFFECTIVE_RISK_SLOT_ACCOUNTING": False}
        candidate_config = {"EFFECTIVE_RISK_SLOT_ACCOUNTING": True}

        by_window: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            baseline = _run_window(backtester_module, label, spec, baseline_config)
            candidate = _run_window(backtester_module, label, spec, candidate_config)
            by_window[label] = {
                "window": spec,
                "baseline": baseline,
                "candidate": candidate,
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "touched_trade_count_delta": (
                    candidate["metrics"]["trade_count"] - baseline["metrics"]["trade_count"]
                ),
            }

    before_metrics = {label: row["baseline"]["metrics"] for label, row in by_window.items()}
    after_metrics = {label: row["candidate"]["metrics"] for label, row in by_window.items()}
    by_window_delta = {label: row["delta"] for label, row in by_window.items()}
    before_agg = _aggregate(before_metrics)
    after_agg = _aggregate(after_metrics)
    aggregate_delta = _delta(after_agg, before_agg)
    windows_ev_improved = sum(
        1 for item in by_window_delta.values() if item.get("expected_value_score", 0.0) > 0
    )
    windows_ev_regressed = sum(
        1 for item in by_window_delta.values() if item.get("expected_value_score", 0.0) < 0
    )
    windows_pnl_improved = sum(1 for item in by_window_delta.values() if item.get("total_pnl", 0.0) > 0)
    windows_pnl_regressed = sum(1 for item in by_window_delta.values() if item.get("total_pnl", 0.0) < 0)
    max_drawdown_worsening = max(
        item.get("max_drawdown_pct", 0.0) for item in by_window_delta.values()
    )

    gate4_passed = (
        aggregate_delta.get("expected_value_score_sum", 0.0) > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and max_drawdown_worsening <= 0.02
        and after_agg["min_survival_rate"] >= 0.05
    )
    if gate4_passed:
        decision = "promising_replay_only_not_promoted"
        rejection_reason = None
        interpretation = (
            "Effective risk-slot accounting improved the canonical windows, but the "
            "result is not promoted because production does not yet share the same "
            "risk-unit slot calculation."
        )
    else:
        decision = "rejected"
        rejection_reason = (
            "Effective risk-slot accounting did not pass Gate 4: it must improve "
            "aggregate EV, improve at least two windows, avoid any EV-regressed "
            "window, keep drawdown damage within 2 percentage points, and keep "
            "survival above 5%."
        )
        interpretation = (
            "The alpha question was worth testing because nominal slots over-penalize "
            "haircut positions and under-penalize boosted risk leaders. The replay "
            "does not justify replacing the accepted nominal slot policy on the "
            "current frozen windows."
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "capital_allocation_effective_risk_slot_replay",
        "changed_variable": "entry slot occupancy counted by actual_risk_pct/base_risk_pct risk units",
        "mechanism_family": "risk_allocation_capacity_routing",
        "hypothesis": (
            "If nominal open-position slots misprice capacity after accepted sizing "
            "haircuts and boosts, then risk-unit slot accounting should admit or "
            "defer entries more efficiently than the fixed count of open core positions."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "why_this_now": (
                "LLM soft-ranking and filing/surprise alpha remain data-blocked; "
                "event/state/ETF surfaces already need forward paper outcomes; "
                "the latest slot scout specifically called for a risk/exposure "
                "slot replay instead of another MAX_POSITIONS sweep."
            ),
        },
        "history_guardrails": {
            "not_global_max_positions_sweep": True,
            "not_scarce_slot_threshold_retry": True,
            "not_tqs_or_rs_ranking": True,
            "not_event_state_surface_retune": True,
            "not_llm_soft_ranking": True,
        },
        "parameters": {
            "single_causal_variable": "risk-unit slot occupancy",
            "risk_unit_formula": "ceil(sum(max(0, actual_risk_pct / base_risk_pct) for open core positions))",
            "baseline_slot_formula": "count(open core positions)",
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing rules",
                "MAX_POSITIONS numeric value",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "snapshots": {label: spec["snapshot"] for label, spec in WINDOWS.items()},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate": aggregate_delta,
        },
        "summary": {
            "before_aggregate": before_agg,
            "after_aggregate": after_agg,
            "aggregate_delta": aggregate_delta,
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "windows_pnl_improved": windows_pnl_improved,
            "windows_pnl_regressed": windows_pnl_regressed,
            "max_drawdown_worsening": _round(max_drawdown_worsening, 4),
        },
        "by_window": by_window,
        "gate1": {
            "passed": True,
            "baseline_source": "rerun inside this script using docs/backtesting.md three-window snapshots",
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "Position.actual_risk_pct",
                "Position.base_risk_pct",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "runtime_note": (
                "Historical replay positions always persist actual/base risk after sizing. "
                "Production promotion would need shared risk-unit computation from live "
                "open-position cost, stop, and portfolio value."
            ),
        },
        "gate3": {
            "passed": after_agg["min_survival_rate"] >= 0.05,
            "min_survival_rate": after_agg["min_survival_rate"],
        },
        "gate4": {
            "passed": gate4_passed,
            "basis": "canonical three-window before/after replay",
        },
        "rejection_reason": rejection_reason,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "Implement risk-unit slot accounting in shared production/backtest policy "
                "and add parity tests before any live/default orders can use it."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_blocker_bypassed": (
                "LLM soft-ranking was skipped because production-aligned samples remain too thin."
            ),
        },
        "next_evidence_needed": [
            "Do not retry nominal MAX_POSITIONS or scarce-slot threshold sweeps on this sample.",
            "A valid retry needs shared production-visible risk/exposure slot calculation or fresh forward replacement-value evidence.",
        ],
        "interpretation": interpretation,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    TICKET_JSON.write_text(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "lane": "alpha_search",
                "status": decision,
                "claim": "completed",
                "hypothesis": payload["hypothesis"],
                "changed_variable": payload["changed_variable"],
                "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
                "log": str(LOG_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_markdown(payload)
    _append_experiment_log(payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"decision={decision}")


if __name__ == "__main__":
    main()
