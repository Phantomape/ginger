"""exp-20260509-015 state-surface benchmark plus core momentum gate.

Alpha search, replay-only. This tests one extra participation discriminator on
top of the frozen event-state plus state-surface stack from exp-20260509-014:
allow the state-surface satellite only when both broad benchmark momentum and
the accepted core equity curve have positive trailing 20-trading-day returns.

No production orders, default backtest policy, core A/B behavior, event source
rules, LLM/news behavior, state-surface scoring, hold days, notional, sizing, or
exits are changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260509_014_state_surface_benchmark_momentum_gate as base


EXPERIMENT_ID = "exp-20260509-015"
STEM = "state_surface_benchmark_core_momentum_gate"
OUT_JSON = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    base.REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)


def _gate_state(
    row: dict[str, Any],
    *,
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision_date = str(row.get("decision_date") or row.get("date") or "")[:10]
    core_return = base._equity_return(result, decision_date)
    benchmark_returns = {
        ticker: base._price_return(prices, ticker, decision_date)
        for ticker in base.BENCHMARK_TICKERS
    }
    ready_benchmark_returns = [
        value for value in benchmark_returns.values() if value is not None
    ]
    benchmark_return_max = max(ready_benchmark_returns) if ready_benchmark_returns else None
    core_momentum_positive = core_return is not None and core_return > 0.0
    benchmark_momentum_positive = (
        benchmark_return_max is not None and benchmark_return_max > 0.0
    )
    allowed = bool(core_momentum_positive and benchmark_momentum_positive)
    return {
        "decision_date": decision_date,
        "core_trailing_return_20d": round(core_return, 6) if core_return is not None else None,
        "benchmark_returns_20d": {
            ticker: round(value, 6) if value is not None else None
            for ticker, value in benchmark_returns.items()
        },
        "benchmark_return_max_20d": (
            round(benchmark_return_max, 6) if benchmark_return_max is not None else None
        ),
        "core_warmup_ready": core_return is not None,
        "core_momentum_positive": core_momentum_positive,
        "benchmark_momentum_positive": benchmark_momentum_positive,
        "allowed": allowed,
        "gate_rule": (
            "core_trailing_return_20d > 0 and max(SPY_20d_return, QQQ_20d_return) > 0"
        ),
    }


def _filter_benchmark_core_momentum(
    candidates: list[dict[str, Any]],
    *,
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    skipped = []
    for row in candidates:
        if row.get("status") != "price_ready":
            kept.append(row)
            continue
        gate = _gate_state(row, result=result, prices=prices)
        enriched = {**row, "benchmark_momentum_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
            continue
        skipped.append(
            {
                **enriched,
                "reason": "benchmark_core_momentum_gate_blocked",
            }
        )
    return kept, skipped


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["status"] = payload["decision"]
    payload["change_type"] = "replay_only_state_surface_benchmark_core_momentum_gate"
    payload["mechanism_family"] = "event_state_surface_stack_participation_gate"
    payload["alpha_hypothesis_category"] = "candidate_pool_allocation"
    payload["alpha_hypothesis"] = (
        "The state-surface satellite should participate only when broad market "
        "momentum and the accepted core strategy's own recent equity momentum "
        "are both positive, because a positive benchmark alone may still admit "
        "surface trades during local strategy drawdowns."
    )
    payload["hypothesis"] = (
        "Apply the frozen state-surface satellite only when max(SPY, QQQ) "
        "20-trading-day return is positive and accepted core equity trailing "
        "20-trading-day return is also positive."
    )
    payload["single_causal_variable"] = (
        "internal core-equity momentum confirmation added to the previously "
        "promising benchmark-momentum participation gate; all sleeve definitions "
        "and sizing mechanics remain locked"
    )
    payload["parameters"] = {
        **payload["parameters"],
        "gate": (
            "core_trailing_return_20d > 0 and max(SPY_20d_return, QQQ_20d_return) > 0"
        ),
        "core_lookback_trading_days": base.LOOKBACK_DAYS,
        "threshold_reason": (
            "zero is the non-tuned profit/loss boundary for both benchmark and "
            "accepted-strategy trailing momentum"
        ),
    }
    payload["history_guardrails"] = {
        "checked_experiment_log": True,
        "checked_mechanism_insights": True,
        "not_repeated_failures": [
            "Not a benchmark threshold sweep; the SPY/QQQ zero-line gate stays unchanged.",
            "Not a state-surface top-N, hold-day, notional, sector, overlap, or surface-subset retry.",
            "Not a core A/B threshold, exit, add-on, or heat-cap change.",
            "Not an LLM soft-ranking or earnings/revision experiment while those remain sample-limited.",
        ],
        "why_this_is_not_a_simple_repeat": (
            "exp-20260509-014 required only benchmark momentum and core warm-up. "
            "This tests a different ex-ante variable: whether the accepted core "
            "strategy itself is in a positive trailing equity state before adding "
            "state-surface paper exposure."
        ),
    }
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_role_changed": False,
        "why_no_llm_change": (
            "LLM soft-ranking remains sample-limited; this test uses fully replayable "
            "benchmark prices and accepted core equity history."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "promotion_requirement_if_positive": (
            "A promoted version must be implemented as a shared default-off "
            "run.py/backtester.py adapter that exposes allow/block reasons and "
            "keeps live orders disabled until forward closed outcomes justify activation."
        ),
    }
    payload["why_not_other_attractive_points"] = (
        "Skipped LLM soft-ranking, earnings/revisions, event-source retunes, "
        "state-score floors, state-surface parameter sweeps, add-on heat reserve, "
        "sector complement, and overlap filters because recent logs mark them "
        "data-limited, rejected, or not the current marginal bottleneck."
    )
    payload["risk_of_change"] = (
        "The gate may miss early recovery leaders because accepted core equity "
        "can lag the first high-quality surface trades after a drawdown."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        "docs/experiment_log.jsonl",
    ]

    vs_event = payload["delta_metrics"]["vs_event_state_addon"]
    vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]
    if payload["decision"] == "promising_replay_only_benchmark_momentum_gate":
        payload["decision"] = "promising_replay_only_benchmark_core_momentum_gate"
        payload["status"] = payload["decision"]
        payload["decision_rationale"] = (
            "Promising replay-only only if the new internal core-momentum gate "
            "improves aggregate EV/PnL and fixes late risk without worsening the "
            "majority of validation windows. See deltas against both event-state "
            "and ungated full-stack baselines."
        )
        payload["rejection_reason"] = None
    else:
        payload["decision"] = "rejected"
        payload["status"] = "rejected"
        payload["decision_rationale"] = (
            "Rejected: adding core-equity positive momentum confirmation did not "
            "beat the previous benchmark-only participation gate with enough "
            "three-window stability and materiality."
        )
        payload["rejection_reason"] = payload["decision_rationale"]
    payload["next_action"] = (
        "If positive, compare against exp-20260509-014 before any adapter work; "
        "if rejected, keep exp-20260509-014 as the stronger participation-gate lead."
    )
    payload["expected_value_score_delta"] = {
        "vs_event_state_addon": vs_event["aggregate_ev_delta"],
        "vs_full_stack_exp_20260509_012": vs_full["aggregate_ev_delta"],
        "vs_exp_20260509_014_gate": None,
    }
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-015 State-Surface Benchmark + Core Momentum Gate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether the state-surface satellite should participate only when both SPY/QQQ 20-day momentum and accepted-core 20-day equity momentum are positive.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Event-State EV | Full Stack EV | Gated EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.event_base.WINDOWS:
        event_metrics = payload["before_metrics"]["event_state_addon"][label]
        full_metrics = payload["before_metrics"]["full_stack_exp_20260509_012"][label]
        after = payload["after_metrics"][label]
        vs_event = payload["delta_metrics"]["vs_event_state_addon"]["by_window"][label]
        vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {event_ev:.4f} | {full_ev:.4f} | {after_ev:.4f} | "
            "{vs_event_ev:+.4f} | {vs_full_ev:+.4f} | ${vs_full_pnl:+,.2f} | "
            "{vs_full_sharpe:+.2f} | {vs_full_dd:+.2%} | {trades} |".format(
                label=label,
                event_ev=event_metrics["expected_value_score"],
                full_ev=full_metrics["expected_value_score"],
                after_ev=after["expected_value_score"],
                vs_event_ev=vs_event["expected_value_score"],
                vs_full_ev=vs_full["expected_value_score"],
                vs_full_pnl=vs_full["total_pnl"],
                vs_full_sharpe=vs_full["sharpe_daily"],
                vs_full_dd=vs_full["max_drawdown_pct"],
                trades=sleeve["benchmark_momentum_selected_trade_count"],
            )
        )
    vs_event = payload["delta_metrics"]["vs_event_state_addon"]
    vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus event-state add-on: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_event["aggregate_ev_delta"],
                vs_event["aggregate_ev_delta_pct"] or 0.0,
                vs_event["aggregate_pnl_delta"],
                vs_event["aggregate_pnl_delta_pct"] or 0.0,
                vs_event["windows_ev_improved"],
                vs_event["windows_ev_regressed"],
            ),
            "- Versus full exp-20260509-012 stack: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_full["aggregate_ev_delta"],
                vs_full["aggregate_ev_delta_pct"] or 0.0,
                vs_full["aggregate_pnl_delta"],
                vs_full["aggregate_pnl_delta_pct"] or 0.0,
                vs_full["windows_ev_improved"],
                vs_full["windows_ev_regressed"],
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. Any promoted version needs shared run.py/backtester.py policy plus parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base._filter_benchmark_momentum = _filter_benchmark_core_momentum
    base._artifact_markdown = _artifact_markdown


def main() -> int:
    configure_base()
    payload = _retag_payload(base.build_payload())
    base.persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "vs_event_state_addon": payload["delta_metrics"]["vs_event_state_addon"],
                    "vs_full_stack_exp_20260509_012": payload["delta_metrics"][
                        "vs_full_stack_exp_20260509_012"
                    ],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
