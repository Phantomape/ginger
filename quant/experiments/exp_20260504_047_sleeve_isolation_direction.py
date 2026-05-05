"""exp-20260504-047 sleeve-isolation alpha direction audit.

This alpha-search experiment tests one causal variable: which executable
strategy sleeves are allowed to compete for production slots. It does not tune
thresholds, add filters, change exits, change sizing constants, touch LLM/news,
or expand the universe.

The goal is not to promote a broad sleeve disablement by default. The goal is to
measure, on the canonical three windows, whether current marginal alpha points
more toward trend lifecycle work or breakout candidate-quality work.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260504-047"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sleeve_isolation_direction.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / "exp-20260504-047_sleeve_isolation_direction.md"
)

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
        (
            "trend_only",
            {
                "enabled_strategies": ("trend_long",),
                "description": "Only trend_long can enter; all other mechanics unchanged.",
            },
        ),
        (
            "breakout_only",
            {
                "enabled_strategies": ("breakout_long",),
                "description": "Only breakout_long can enter; all other mechanics unchanged.",
            },
        ),
    ]
)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item) for item in value]
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _metric(result: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = float(result.get(key))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _round(value: Any, digits: int = 6) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    total_pnl = _metric(result, "total_pnl")
    total_return_pct = _metric(benchmarks, "strategy_total_return_pct")
    sharpe_daily = _metric(result, "sharpe_daily")
    expected_value_score = result.get("expected_value_score")
    if expected_value_score is None:
        expected_value_score = total_return_pct * sharpe_daily
    return {
        "expected_value_score": _round(expected_value_score, 4),
        "sharpe_daily": _round(sharpe_daily, 2),
        "total_pnl": _round(total_pnl, 2),
        "total_return_pct": _round(total_return_pct, 4),
        "max_drawdown_pct": _round(_metric(result, "max_drawdown_pct"), 4),
        "win_rate": _round(_metric(result, "win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(_metric(result, "survival_rate"), 4),
        "vs_spy_pct": _round(_metric(benchmarks, "strategy_vs_spy_pct"), 4),
        "vs_qqq_pct": _round(_metric(benchmarks, "strategy_vs_qqq_pct"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _trade_breakdown(result: dict[str, Any]) -> dict[str, Any]:
    by_strategy: dict[str, dict[str, Any]] = {}
    for trade in result.get("trades", []) or []:
        strategy = trade.get("strategy") or "unknown"
        row = by_strategy.setdefault(
            strategy,
            {"trade_count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0},
        )
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["losses"] += int(pnl <= 0)
        row["total_pnl"] += pnl
    for row in by_strategy.values():
        count = row["trade_count"]
        row["win_rate"] = _round(row["wins"] / count if count else 0.0, 4)
        row["total_pnl"] = _round(row["total_pnl"], 2)
    return by_strategy


def _run_window(window: dict[str, str], enabled_strategies: tuple[str, ...] | None = None) -> dict[str, Any]:
    config = {}
    if enabled_strategies is not None:
        config["ENABLED_STRATEGIES"] = enabled_strategies
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=window["snapshot"],
    ).run()
    return {
        "metrics": _extract_metrics(result),
        "by_strategy": _trade_breakdown(result),
        "entry_reason_counts": result.get("entry_reason_counts") or {},
        "addon_summary": {
            "scheduled": (result.get("addon_attribution") or {}).get("scheduled"),
            "executed": (result.get("addon_attribution") or {}).get("executed"),
            "skipped": (result.get("addon_attribution") or {}).get("skipped"),
        },
    }


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
        "total_pnl": _round(after["total_pnl"] - before["total_pnl"], 2),
        "total_pnl_delta_pct": _round(_pct_delta(before["total_pnl"], after["total_pnl"]), 6),
        "max_drawdown_improvement_pct": _round(
            before["max_drawdown_pct"] - after["max_drawdown_pct"],
            6,
        ),
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
        "passes_material_ev": ev_delta_pct > 0.10,
        "passes_sharpe": delta["sharpe_daily"] > 0.10,
        "passes_drawdown": delta["max_drawdown_improvement_pct"] > 0.01,
        "passes_pnl": pnl_delta_pct > 0.05,
        "passes_trade_count": trade_count_pass,
        "ev_delta_pct": _round(ev_delta_pct, 6),
        "pnl_delta_pct": _round(pnl_delta_pct, 6),
        "sharpe_daily_delta": delta["sharpe_daily"],
        "drawdown_improvement_pct": delta["max_drawdown_improvement_pct"],
        "trade_count_increased_with_win_rate_not_down": trade_count_pass,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(row["metrics"]["expected_value_score"] for row in rows.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum(row["metrics"]["total_pnl"] for row in rows.values()),
            2,
        ),
        "trade_count_sum": int(sum(row["metrics"]["trade_count"] for row in rows.values())),
    }


def _write_report(payload: dict[str, Any]) -> None:
    baseline = payload["before_metrics"]
    variants = payload["variants_summary"]
    lines = [
        "# exp-20260504-047 Sleeve Isolation Direction",
        "",
        "Alpha hypothesis: isolate the executable A/B sleeves to determine whether the next alpha work should prioritize trend lifecycle management or breakout candidate quality.",
        "",
        "No production behavior changed. The experiment used the canonical snapshots from docs/backtesting.md.",
        "",
        "## Baseline",
        "",
        "| Window | EV | PnL | Sharpe daily | Max DD | Win rate | Trades | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in baseline.items():
        m = row["metrics"]
        lines.append(
            f"| {label} | {m['expected_value_score']:.4f} | {m['total_pnl']:.2f} | "
            f"{m['sharpe_daily']:.2f} | {m['max_drawdown_pct']:.4f} | "
            f"{m['win_rate']:.4f} | {m['trade_count']} | {m['survival_rate']:.4f} |"
        )
    lines.extend(["", "## Variant Deltas", ""])
    for variant_name, variant in variants.items():
        lines.extend(
            [
                f"### {variant_name}",
                "",
                "| Window | EV delta | PnL delta | Sharpe delta | DD improvement | Trade delta |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for label, row in variant["by_window"].items():
            d = row["delta"]
            lines.append(
                f"| {label} | {d['expected_value_score']:.4f} | {d['total_pnl']:.2f} | "
                f"{d['sharpe_daily']:.2f} | {d['max_drawdown_improvement_pct']:.4f} | "
                f"{d['trade_count']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "Production impact: experiment-only. A positive future sleeve-routing rule must be implemented through shared production/backtest policy before live use.",
            "",
        ]
    )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    baseline = OrderedDict()
    for label, window in WINDOWS.items():
        baseline[label] = _run_window(window)

    variant_runs: dict[str, OrderedDict[str, Any]] = OrderedDict()
    variants_summary: dict[str, Any] = OrderedDict()
    for variant_name, spec in VARIANTS.items():
        rows: OrderedDict[str, Any] = OrderedDict()
        summary_rows: OrderedDict[str, Any] = OrderedDict()
        for label, window in WINDOWS.items():
            rows[label] = _run_window(window, spec["enabled_strategies"])
            before = baseline[label]["metrics"]
            after = rows[label]["metrics"]
            summary_rows[label] = {
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "gate4": _gate4(before, after),
                "by_strategy": rows[label]["by_strategy"],
                "entry_reason_counts": rows[label]["entry_reason_counts"],
                "addon_summary": rows[label]["addon_summary"],
            }
        variant_runs[variant_name] = rows
        aggregate_before = _aggregate(baseline)
        aggregate_after = _aggregate(rows)
        variants_summary[variant_name] = {
            "description": spec["description"],
            "enabled_strategies": spec["enabled_strategies"],
            "by_window": summary_rows,
            "aggregate": {
                "before": aggregate_before,
                "after": aggregate_after,
                "delta": {
                    "expected_value_score_sum": _round(
                        aggregate_after["expected_value_score_sum"]
                        - aggregate_before["expected_value_score_sum"],
                        4,
                    ),
                    "expected_value_score_delta_pct": _round(
                        _pct_delta(
                            aggregate_before["expected_value_score_sum"],
                            aggregate_after["expected_value_score_sum"],
                        ),
                        6,
                    ),
                    "total_pnl_sum": _round(
                        aggregate_after["total_pnl_sum"] - aggregate_before["total_pnl_sum"],
                        2,
                    ),
                    "total_pnl_delta_pct": _round(
                        _pct_delta(
                            aggregate_before["total_pnl_sum"],
                            aggregate_after["total_pnl_sum"],
                        ),
                        6,
                    ),
                    "trade_count_sum": (
                        aggregate_after["trade_count_sum"]
                        - aggregate_before["trade_count_sum"]
                    ),
                },
            },
            "ev_improved_windows": sum(
                1
                for row in summary_rows.values()
                if row["delta"]["expected_value_score"] > 0
            ),
            "ev_regressed_windows": sum(
                1
                for row in summary_rows.values()
                if row["delta"]["expected_value_score"] < 0
            ),
            "material_gate4_windows": sum(
                1
                for row in summary_rows.values()
                if any(
                    [
                        row["gate4"]["passes_material_ev"],
                        row["gate4"]["passes_sharpe"],
                        row["gate4"]["passes_drawdown"],
                        row["gate4"]["passes_pnl"],
                        row["gate4"]["passes_trade_count"],
                    ]
                )
            ),
        }

    best_variant = max(
        variants_summary,
        key=lambda name: variants_summary[name]["aggregate"]["after"]["expected_value_score_sum"],
    )
    best = variants_summary[best_variant]
    accepted = (
        best["ev_regressed_windows"] == 0
        and best["ev_improved_windows"] >= 2
        and best["material_gate4_windows"] >= 2
    )
    status = "accepted_requires_shared_promotion" if accepted else "rejected"
    decision = "accepted_requires_shared_promotion" if accepted else "rejected"
    decision_rationale = (
        "Accepted for follow-up only: the best sleeve-isolation variant cleared the "
        "multi-window materiality rule. Promotion would require changing shared "
        "ENABLED_STRATEGIES policy and validating run.py/backtester parity."
        if accepted
        else (
            "Rejected for production. Neither broad sleeve isolation improved the "
            "canonical three-window expected-value profile without EV regression. "
            "The useful alpha direction is not disabling a sleeve; it is improving "
            "trend lifecycle and breakout candidate quality inside the current A+B "
            "portfolio."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "a_b_sleeve_meta_allocation",
        "change_type": "strategy_sleeve_isolation_replay",
        "hypothesis": (
            "If one A/B sleeve is diluting the accepted stack, isolating trend_long "
            "or breakout_long should improve the three-window EV profile and point "
            "to a clean alpha optimization direction."
        ),
        "alpha_hypothesis": {
            "category": "meta_allocation / entry sleeve eligibility",
            "entry_exit_ranking_or_allocation": "entry sleeve eligibility",
            "why_this_now": (
                "LLM soft-ranking remains sample-limited; static threshold, ETF, "
                "SEC governance, and nearby add-on cap surfaces are recently blocked. "
                "The playbook explicitly calls for a mid_weak meta-allocation map."
            ),
        },
        "historical_experiment_check": {
            "not_repeating": [
                "not a threshold sweep",
                "not a Technology cofire preference",
                "not global trend-first ordering",
                "not breakout one-slot deferral retuning",
                "not macro ETF candidate expansion",
                "not LLM soft-ranking on sparse samples",
            ],
            "similar_prior_results": {
                "exp-20260427-036": "global trend-first ordering was rejected",
                "exp-20260501-017": "Technology same-ticker cofire trend preference was rejected",
                "exp-20260504-045": "energy ETF pair-confirmed candidate pool was rejected",
            },
            "why_not_simple_repeat": (
                "This run isolates whole executable sleeves to decide alpha direction; "
                "it does not change ordering, state thresholds, or ticker lists."
            ),
        },
        "single_causal_variable": "ENABLED_STRATEGIES sleeve eligibility",
        "parameters": {
            "baseline": ["trend_long", "breakout_long"],
            "tested_variants": {
                name: list(spec["enabled_strategies"])
                for name, spec in VARIANTS.items()
            },
            "locked_variables": [
                "universe",
                "signal thresholds",
                "risk multipliers",
                "candidate ranking",
                "position sizing constants",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": baseline,
        "variants_summary": variants_summary,
        "best_variant": best_variant,
        "after_metrics": {
            label: row["after"] for label, row in best["by_window"].items()
        },
        "expected_value_score_delta": {
            label: row["delta"]["expected_value_score"]
            for label, row in best["by_window"].items()
        },
        "gate4": {
            "rule": (
                "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, PnL >5%, "
                "or trade count rises with win rate not down. Promotion also "
                "requires no EV-regressed window and majority-window support."
            ),
            "best_variant": best_variant,
            "by_window": {label: row["gate4"] for label, row in best["by_window"].items()},
            "material_windows": best["material_gate4_windows"],
            "passes_majority": accepted,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_accepted": (
                "Accepted variant would require shared constants/run/backtester strategy "
                "enablement plus parity tests before live use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking outcome joins remain too sparse.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if accepted else decision_rationale,
        "why_not_other_attractive_points": (
            "SEC governance and Form 4 need forward outcomes; macro ETF expansion "
            "was just rejected; add-on local thresholds/caps are blocked; AI infra "
            "is already a forward pilot rather than a core historical promotion."
        ),
        "risk_of_change": (
            "A broad sleeve disablement would miss valid winners and could reduce "
            "the diversification that currently lets A+B pass all three windows."
        ),
        "next_action": (
            "Do not disable either A/B sleeve. Use the result as direction: optimize "
            "inside the weaker sleeve or lifecycle branch with a richer discriminator."
        ),
        "related_files": [
            "quant/experiments/exp_20260504_047_sleeve_isolation_direction.py",
            "data/experiments/exp-20260504-047/sleeve_isolation_direction.json",
            "docs/experiments/logs/exp-20260504-047.json",
            "docs/experiments/tickets/exp-20260504-047.json",
            "docs/experiments/artifacts/exp-20260504-047_sleeve_isolation_direction.md",
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "lane": "alpha_search",
        "owner": "alpha-search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "single_causal_variable": payload["single_causal_variable"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": decision,
        "best_variant": best_variant,
        "gate4_passed": accepted,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_report(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "aggregate_delta": best["aggregate"]["delta"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "log": str(LOG_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
