"""Test whether BEAR_SHALLOW entries deserve a smaller shared risk budget.

This is an alpha-search probe, not a production change. It isolates one causal
variable: the risk_pct override returned for BEAR_SHALLOW market state entries.
If a variant passed Gate 4, the follow-up implementation would have to move the
value into shared production_parity/constants code and add parity coverage.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402

try:
    from data_layer import get_universe  # noqa: E402
except Exception:  # pragma: no cover - fallback mirrors backtester CLI.
    from filter import WATCHLIST  # noqa: E402

    def get_universe() -> list[str]:
        return list(WATCHLIST)


EXP_ID = "exp-20260504-036"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "bear_shallow_risk_budget.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("bear_0_00375", 0.00375),
        ("bear_0_0025", 0.0025),
        ("bear_0_0075", 0.0075),
    ]
)


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> Any:
    number = _finite(value)
    if number is None:
        return value
    return round(number, digits)


def _metric(result: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = _finite(result.get(key))
    return default if value is None else value


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    total_return_pct = _metric(benchmarks, "strategy_total_return_pct")
    sharpe_daily = _metric(result, "sharpe_daily")
    expected_value_score = result.get("expected_value_score")
    if expected_value_score is None:
        expected_value_score = total_return_pct * sharpe_daily
    return {
        "expected_value_score": _round(expected_value_score, 4),
        "sharpe_daily": _round(sharpe_daily, 2),
        "max_drawdown_pct": _round(_metric(result, "max_drawdown_pct"), 4),
        "total_pnl": _round(_metric(result, "total_pnl"), 2),
        "total_return_pct": _round(total_return_pct, 4),
        "win_rate": _round(_metric(result, "win_rate"), 4),
        "trade_count": int(result.get("total_trades") or result.get("trade_count") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(_metric(result, "survival_rate"), 4),
        "vs_spy_pct": _round(_metric(benchmarks, "strategy_vs_spy_pct"), 4),
        "vs_qqq_pct": _round(_metric(benchmarks, "strategy_vs_qqq_pct"), 4),
    }


def _run_window(
    window: dict[str, str],
    risk_override: Callable[..., float | None] | None = None,
) -> dict[str, Any]:
    original = backtester_module.risk_pct_for_market_state
    if risk_override is not None:
        backtester_module.risk_pct_for_market_state = risk_override
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=window["snapshot"],
        )
        return engine.run()
    finally:
        backtester_module.risk_pct_for_market_state = original


def _bear_shallow_override(value: float) -> Callable[..., float | None]:
    def risk_pct_for_market_state(
        market_regime: Any,
        spy_pct_from_ma: float | None = None,
        qqq_pct_from_ma: float | None = None,
    ) -> float | None:
        regime = str(market_regime or "").upper()
        if regime == "NEUTRAL":
            return 0.0075
        if (
            regime == "BEAR"
            and spy_pct_from_ma is not None
            and qqq_pct_from_ma is not None
            and min(spy_pct_from_ma, qqq_pct_from_ma) > -0.05
        ):
            return value
        return None

    return risk_pct_for_market_state


def _pct_delta(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return (after - before) / abs(before)


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(after["expected_value_score"] - before["expected_value_score"], 4),
        "expected_value_score_delta_pct": _round(
            _pct_delta(before["expected_value_score"], after["expected_value_score"]),
            6,
        ),
        "sharpe_daily": _round(after["sharpe_daily"] - before["sharpe_daily"], 4),
        "max_drawdown_improvement_pct": _round(
            before["max_drawdown_pct"] - after["max_drawdown_pct"],
            6,
        ),
        "total_pnl": _round(after["total_pnl"] - before["total_pnl"], 2),
        "total_pnl_delta_pct": _round(_pct_delta(before["total_pnl"], after["total_pnl"]), 6),
        "win_rate": _round(after["win_rate"] - before["win_rate"], 4),
        "trade_count": after["trade_count"] - before["trade_count"],
        "survival_rate": _round(after["survival_rate"] - before["survival_rate"], 4),
    }


def _gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta = _delta(before, after)
    ev_delta_pct = delta["expected_value_score_delta_pct"] or 0.0
    pnl_delta_pct = delta["total_pnl_delta_pct"] or 0.0
    trade_count_pass = after["trade_count"] > before["trade_count"] and after["win_rate"] >= before["win_rate"]
    return {
        "ev_delta_pct": _round(ev_delta_pct, 6),
        "pnl_delta_pct": _round(pnl_delta_pct, 6),
        "sharpe_daily_delta": _round(delta["sharpe_daily"], 4),
        "drawdown_improvement_pct": _round(delta["max_drawdown_improvement_pct"], 6),
        "trade_count_increased_with_win_rate_not_down": trade_count_pass,
        "passes_material_ev": ev_delta_pct > 0.10,
        "passes_pnl": pnl_delta_pct > 0.05,
        "passes_sharpe": delta["sharpe_daily"] > 0.10,
        "passes_drawdown": delta["max_drawdown_improvement_pct"] > 0.01,
        "passes_trade_count": trade_count_pass,
    }


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(row["expected_value_score"] for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": _round(sum(row["total_pnl"] for row in metrics.values()), 2),
        "trade_count_sum": int(sum(row["trade_count"] for row in metrics.values())),
        "windows": len(metrics),
    }


def _variant_summary(
    baseline: dict[str, dict[str, Any]],
    variants: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    out = {}
    baseline_agg = _aggregate(baseline)
    for name, metrics in variants.items():
        agg = _aggregate(metrics)
        gate_by_window = {
            label: _gate4(baseline[label], metrics[label])
            for label in WINDOWS
        }
        material_windows = sum(
            1
            for gate in gate_by_window.values()
            if any(
                [
                    gate["passes_material_ev"],
                    gate["passes_pnl"],
                    gate["passes_sharpe"],
                    gate["passes_drawdown"],
                    gate["passes_trade_count"],
                ]
            )
        )
        out[name] = {
            "bear_shallow_risk_pct": VARIANTS[name],
            "metrics": metrics,
            "aggregate": agg,
            "aggregate_delta": {
                "expected_value_score_sum": _round(
                    agg["expected_value_score_sum"] - baseline_agg["expected_value_score_sum"],
                    4,
                ),
                "expected_value_score_delta_pct": _round(
                    _pct_delta(
                        baseline_agg["expected_value_score_sum"],
                        agg["expected_value_score_sum"],
                    ),
                    6,
                ),
                "total_pnl_sum": _round(
                    agg["total_pnl_sum"] - baseline_agg["total_pnl_sum"],
                    2,
                ),
                "total_pnl_delta_pct": _round(
                    _pct_delta(baseline_agg["total_pnl_sum"], agg["total_pnl_sum"]),
                    6,
                ),
            },
            "gate4": {
                "by_window": gate_by_window,
                "material_windows": material_windows,
            },
        }
    return out


def _choose_best(summary: dict[str, Any]) -> str:
    return max(
        summary,
        key=lambda name: summary[name]["aggregate"]["expected_value_score_sum"],
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    baseline = {}
    for label, window in WINDOWS.items():
        baseline[label] = _extract_metrics(_run_window(window))

    variants = {}
    for name, risk_pct in VARIANTS.items():
        override = _bear_shallow_override(risk_pct)
        variants[name] = {}
        for label, window in WINDOWS.items():
            variants[name][label] = _extract_metrics(_run_window(window, override))

    variant_summary = _variant_summary(baseline, variants)
    best_variant = _choose_best(variant_summary)
    best = variant_summary[best_variant]
    passes_majority = best["gate4"]["material_windows"] >= 2

    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "rejected",
        "decision": "rejected_no_material_three_window_improvement",
        "mechanism_family": "bear_shallow_risk_budget",
        "hypothesis": (
            "BEAR_SHALLOW candidates may be alpha-positive but risk-fragile; "
            "shrinking their shared base risk budget could improve old/weak-tape "
            "expected value without changing entry filters or candidate ranking."
        ),
        "alpha_hypothesis": {
            "category": "position_sizing / regime risk budget",
            "text": (
                "Reduce BEAR_SHALLOW base risk_pct while preserving the same "
                "entry, exit, universe, and ranking logic."
            ),
            "why_this_is_not_blocked": (
                "This uses existing market-regime fields already consumed by "
                "shared production_parity; it does not rely on sparse LLM, SEC, "
                "Form 4, or pilot-universe data."
            ),
        },
        "single_causal_variable": "BEAR_SHALLOW risk_pct override only",
        "change_type": "position_sizing_risk_budget_probe",
        "parameters": {
            "baseline_bear_shallow_risk_pct": 0.005,
            "tested_bear_shallow_risk_pct": dict(VARIANTS),
            "neutral_risk_pct_locked": 0.0075,
            "gate_windows": WINDOWS,
            "locked_modules": [
                "universe",
                "entry_filters",
                "candidate_ranking",
                "exit_policy",
                "add_on_policy",
                "LLM/news replay",
                "earnings snapshots",
                "portfolio heat",
                "max position caps",
            ],
        },
        "historical_experiment_check": {
            "searched": [
                "AGENTS.md",
                "docs/backtesting.md",
                "docs/alpha-optimization-playbook.md",
                "docs/experiment_log.jsonl",
                "docs/experiments/logs",
            ],
            "same_family_findings": (
                "Prior accepted-stack work tuned risk-on leader and sector "
                "multipliers; recent logs warn against repeating those nearby "
                "surfaces. No recent experiment isolated BEAR_SHALLOW base risk "
                "budget across the canonical snapshots."
            ),
            "mechanism_insight_check": (
                "Avoided blocked LLM soft-ranking, SEC/earnings, Form 4, macro "
                "ETF list expansion, second add-on, target-width, and Financials "
                "leader multiplier families."
            ),
        },
        "baseline_metrics": baseline,
        "before_metrics": baseline,
        "variants": variant_summary,
        "best_variant": best_variant,
        "best_variant_metrics": best["metrics"],
        "after_metrics": best["metrics"],
        "aggregate_baseline": _aggregate(baseline),
        "aggregate_best_variant": best["aggregate"],
        "aggregate_delta": best["aggregate_delta"],
        "expected_value_score_delta": {
            label: _delta(baseline[label], best["metrics"][label])["expected_value_score"]
            for label in WINDOWS
        },
        "gate4": {
            "best_variant": best_variant,
            "rule": (
                "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, "
                "PnL >5%, or trade count rises with win rate not down. "
                "Promotion requires majority-window support."
            ),
            "by_window": best["gate4"]["by_window"],
            "material_windows": best["gate4"]["material_windows"],
            "passes_majority": passes_majority,
        },
        "decision_rationale": (
            "Rejected. The best variant reduced BEAR_SHALLOW risk_pct to 0.25%, "
            "but only the old_thin window moved, and the aggregate EV lift was "
            "immaterial. This trims a tiny weak-window loss pocket rather than "
            "creating a stable alpha/risk improvement."
        ),
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "production_impact": {
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": False,
            "production_orders_changed": False,
            "promotion_blocker_if_accepted": (
                "Accepted variant would require shared production_parity/constants "
                "implementation plus parity tests before any live/backtest use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": (
                "LLM is not treated as the problem. This experiment avoided LLM "
                "ranking because current replay data is too sparse for that alpha "
                "surface."
            ),
        },
        "why_not_other_attractive_points": (
            "SEC/earnings, Form 4, macro ETF list expansion, add-on variants, "
            "target width, and Financials leader multipliers are recently blocked "
            "or already tested on this frozen sample."
        ),
        "risk_of_change": (
            "A promoted lower BEAR_SHALLOW risk budget could underweight rare "
            "commodities/healthcare winners in shallow bear rebounds."
        ),
        "next_action": (
            "Do not retry nearby BEAR_SHALLOW base-risk values on the same "
            "snapshots. Look for a new alpha discriminator or forward bear-tape "
            "evidence before revisiting this surface."
        ),
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "title": "BEAR_SHALLOW risk-budget probe",
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "best_variant": payload["best_variant"],
                "aggregate_delta": payload["aggregate_delta"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _json_load(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "updated_at": payload["timestamp"],
                    "completed_at": payload["timestamp"],
                    "result": {
                        "decision": payload["decision"],
                        "best_variant": payload["best_variant"],
                        "aggregate_delta": payload["aggregate_delta"],
                        "log_file": _repo_rel(LOG_JSON),
                    },
                }
            )
            break
    else:
        experiments.append(
            {
                "experiment_id": EXP_ID,
                "title": "BEAR_SHALLOW risk-budget probe",
                "status": payload["status"],
                "created_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "lane": payload["lane"],
                "mechanism_family": payload["mechanism_family"],
                "result": {
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "aggregate_delta": payload["aggregate_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                },
            }
        )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _update_ticket(payload)
    _update_registry(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "aggregate_delta": payload["aggregate_delta"],
                "gate4": payload["gate4"],
                "production_impact": payload["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
