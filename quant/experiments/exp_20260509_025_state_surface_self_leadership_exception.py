"""exp-20260509-025 state-surface self-leadership exception.

Alpha search, replay-only. Tests one exception to the frozen state-surface
benchmark-momentum gate from exp-20260509-014:

    keep the SPY/QQQ 20-day positive momentum gate, but when the broad gate is
    negative, allow a state-surface candidate only if its own 20-day return is
    positive and above max(SPY, QQQ) 20-day return.

This is intended to recover the early-window leaders that exp-20260509-014
missed without sweeping state-surface top-N, hold days, notional, surface
families, event sources, LLM/news, sizing, exits, or live/default adapters.
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

from experiments import exp_20260509_014_state_surface_benchmark_momentum_gate as base  # noqa: E402


EXPERIMENT_ID = "exp-20260509-025"
STEM = "state_surface_self_leadership_exception"
OUT_JSON = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    base.REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXP14_LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / "exp-20260509-014.json"


def _load_exp14_after_metrics() -> dict[str, dict[str, Any]]:
    with EXP14_LOG_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["after_metrics"]


def _gate_state(
    row: dict[str, Any],
    *,
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision_date = str(row.get("decision_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    core_return = base._equity_return(result, decision_date)
    benchmark_returns = {
        ticker_symbol: base._price_return(prices, ticker_symbol, decision_date)
        for ticker_symbol in base.BENCHMARK_TICKERS
    }
    ready_benchmark_returns = [
        value for value in benchmark_returns.values() if value is not None
    ]
    benchmark_return_max = max(ready_benchmark_returns) if ready_benchmark_returns else None
    ticker_return = base._price_return(prices, ticker, decision_date)

    broad_momentum_positive = (
        benchmark_return_max is not None and benchmark_return_max > 0.0
    )
    self_leadership_exception = (
        ticker_return is not None
        and ticker_return > 0.0
        and benchmark_return_max is not None
        and ticker_return > benchmark_return_max
    )
    allowed = bool(
        core_return is not None
        and (broad_momentum_positive or self_leadership_exception)
    )
    if broad_momentum_positive:
        reason = "benchmark_momentum_positive"
    elif self_leadership_exception:
        reason = "self_leadership_exception"
    elif benchmark_return_max is None:
        reason = "benchmark_momentum_unavailable"
    elif ticker_return is None:
        reason = "ticker_momentum_unavailable"
    else:
        reason = "benchmark_momentum_nonpositive_without_self_leadership"

    return {
        "decision_date": decision_date,
        "ticker": ticker,
        "core_trailing_return_20d": round(core_return, 6) if core_return is not None else None,
        "ticker_return_20d": round(ticker_return, 6) if ticker_return is not None else None,
        "benchmark_returns_20d": {
            ticker_symbol: round(value, 6) if value is not None else None
            for ticker_symbol, value in benchmark_returns.items()
        },
        "benchmark_return_max_20d": (
            round(benchmark_return_max, 6) if benchmark_return_max is not None else None
        ),
        "core_warmup_ready": core_return is not None,
        "benchmark_momentum_positive": broad_momentum_positive,
        "self_leadership_exception": self_leadership_exception,
        "allowed": allowed,
        "allowed_reason": reason if allowed else None,
        "blocked_reason": None if allowed else reason,
        "gate_rule": (
            "core_warmup_ready and (max(SPY_20d_return, QQQ_20d_return) > 0 "
            "or (ticker_20d_return > 0 and ticker_20d_return > max(SPY_20d_return, QQQ_20d_return)))"
        ),
    }


def _filter_self_leadership_exception(
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
                "reason": gate["blocked_reason"] or "self_leadership_gate_blocked",
            }
        )
    return kept, skipped


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    exp14_after = _load_exp14_after_metrics()
    vs_exp14 = base._aggregate_delta(exp14_after, payload["after_metrics"])
    exp14_late = vs_exp14["by_window"]["late_strong"]
    material_vs_exp14 = (
        (vs_exp14["aggregate_ev_delta"] or 0.0) > 0.10
        or (vs_exp14["aggregate_pnl_delta_pct"] or 0.0) > 0.05
    )
    max_dd_worsening_vs_exp14 = max(
        float(row.get("max_drawdown_pct") or 0.0)
        for row in vs_exp14["by_window"].values()
    )
    replacement_passed = bool(
        material_vs_exp14
        and vs_exp14["aggregate_ev_delta"] > 0.0
        and vs_exp14["aggregate_pnl_delta"] > 0.0
        and vs_exp14["windows_ev_improved"] >= 2
        and max_dd_worsening_vs_exp14 <= 0.01
        and exp14_late["expected_value_score"] >= -0.05
    )

    payload = dict(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["status"] = "accepted_replay_only" if replacement_passed else "rejected"
    payload["decision"] = payload["status"]
    payload["change_type"] = "replay_only_state_surface_self_leadership_exception"
    payload["mechanism_family"] = "event_state_surface_stack_participation_gate"
    payload["alpha_hypothesis_category"] = "candidate_pool_allocation"
    payload["alpha_hypothesis"] = (
        "State-surface may find early leaders before SPY/QQQ 20-day momentum "
        "turns positive. A candidate-level self-leadership exception may recover "
        "that alpha while preserving the benchmark gate's broad-tape risk control."
    )
    payload["hypothesis"] = (
        "Keep the exp-20260509-014 benchmark-momentum state-surface gate, but "
        "allow blocked candidates whose own 20-day return is positive and above "
        "max(SPY, QQQ) 20-day return."
    )
    payload["single_causal_variable"] = (
        "candidate self-leadership exception to the frozen state-surface "
        "benchmark-momentum gate; all state-surface scoring, source, notional, "
        "hold-day, sizing, exit, LLM/news, and event-state variables remain locked"
    )
    payload["parameters"] = {
        **payload["parameters"],
        "gate": (
            "core_warmup_ready and (max(SPY_20d_return, QQQ_20d_return) > 0 "
            "or (ticker_20d_return > 0 and ticker_20d_return > max(SPY_20d_return, QQQ_20d_return)))"
        ),
        "self_leadership_threshold": "ticker_20d_return > 0 and ticker_20d_return > max_benchmark_20d_return",
        "threshold_reason": (
            "zero is the non-tuned positive-return boundary; relative leadership "
            "requires the candidate to beat the same max benchmark used by the "
            "accepted gate."
        ),
    }
    payload["history_guardrails"] = {
        "checked_experiment_log": True,
        "checked_mechanism_insights": True,
        "not_repeated_failures": [
            "Not a benchmark threshold sweep; the SPY/QQQ zero-line remains unchanged.",
            "Not a core-equity momentum confirmation retry from exp-20260509-015.",
            "Not a state-surface top-N, hold-day, notional, sector, overlap, or surface-subset retry.",
            "Not an event-bundle benchmark gate migration from exp-20260509-024.",
            "Not an LLM, options, Form 4, or estimate-revision experiment while those outcomes are sparse.",
        ],
        "why_this_is_not_a_simple_repeat": (
            "exp-20260509-014 identified missed early-window leaders as the cost "
            "of the benchmark gate. This tests an ex-ante candidate-level "
            "leadership exception to that exact cost, not another gate threshold "
            "or surface composition change."
        ),
    }
    payload["delta_metrics"]["vs_exp_20260509_014_gate"] = vs_exp14
    payload["expected_value_score_delta"] = {
        **payload["expected_value_score_delta"],
        "vs_exp_20260509_014_gate": vs_exp14["aggregate_ev_delta"],
    }
    payload["gate4"] = {
        **payload["gate4"],
        "replacement_passed_vs_exp_20260509_014": replacement_passed,
        "material_vs_exp_20260509_014": material_vs_exp14,
        "max_dd_worsening_vs_exp_20260509_014": round(max_dd_worsening_vs_exp14, 6),
        "primary_acceptance_rule": (
            "Replace exp-20260509-014 only if the exception improves aggregate "
            "EV and PnL materially versus that gate, improves EV in at least "
            "2/3 windows, keeps max drawdown worsening <= 1pp, and does not "
            "materially reintroduce late_strong risk."
        ),
    }
    if replacement_passed:
        payload["decision_rationale"] = (
            "Accepted replay-only: the self-leadership exception improves the "
            "current benchmark-gated state-surface lead with enough three-window "
            "materiality while preserving the late-window risk guard. It remains "
            "default-off until implemented in the shared state-surface adapter "
            "and covered by parity tests."
        )
        payload["rejection_reason"] = None
        payload["next_action"] = (
            "Implement this exact exception in state_surface_sleeve.py as a "
            "default-off paper queue adapter, expose allow/block reasons in "
            "production output, and add parity tests before any live/default use."
        )
    else:
        payload["decision_rationale"] = (
            "Rejected: the self-leadership exception did not beat exp-20260509-014 "
            "with enough marginal EV/PnL materiality, window robustness, and "
            "late-risk preservation."
        )
        payload["rejection_reason"] = payload["decision_rationale"]
        payload["next_action"] = (
            "Do not retry nearby self-leadership exceptions or relative-return "
            "thresholds on the same frozen state-surface sample. Keep the exact "
            "exp-20260509-014 benchmark gate as the current state-surface lead."
        )
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_role_changed": False,
        "why_no_llm_change": (
            "LLM soft-ranking remains sample-limited; this alpha test uses only "
            "fully replayable OHLCV returns available by the decision date."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "promotion_requirement_if_positive": (
            "A positive result must be implemented as shared default-off "
            "state-surface policy consumed by run.py/backtester.py and tested "
            "before it affects paper queue output; live/default orders remain disabled."
        ),
    }
    payload["why_not_other_attractive_points"] = (
        "Skipped LLM soft-ranking, options, estimate revisions, Form 4, event-source "
        "retunes, state-score floors, state-surface parameter sweeps, sector "
        "complement, and core-overlap filters because recent records mark them "
        "data-limited, rejected, or not the marginal bottleneck."
    )
    payload["risk_of_change"] = (
        "A self-leadership exception may re-admit high-beta candidates during "
        "weak benchmark tape and damage the late_strong risk improvement that "
        "made exp-20260509-014 useful."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        "docs/experiment_log.jsonl",
    ]
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-025 State-Surface Self-Leadership Exception",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether candidate-level 20-day self-leadership should make an exception to the state-surface benchmark-momentum gate.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Exp14 Gate EV | Exception EV | vs Exp14 EV | vs Exp14 PnL | vs Exp14 Sharpe | vs Exp14 DD | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    exp14_after = _load_exp14_after_metrics()
    vs_exp14 = payload["delta_metrics"]["vs_exp_20260509_014_gate"]
    for label in base.event_base.WINDOWS:
        after = payload["after_metrics"][label]
        delta = vs_exp14["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {base_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | "
            "${dpnl:+,.2f} | {dsharpe:+.2f} | {ddd:+.2%} | {trades} |".format(
                label=label,
                base_ev=exp14_after[label]["expected_value_score"],
                after_ev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                dpnl=delta["total_pnl"],
                dsharpe=delta["sharpe_daily"],
                ddd=delta["max_drawdown_pct"],
                trades=sleeve["benchmark_momentum_selected_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus exp-20260509-014 gate: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_exp14["aggregate_ev_delta"],
                vs_exp14["aggregate_ev_delta_pct"] or 0.0,
                vs_exp14["aggregate_pnl_delta"],
                vs_exp14["aggregate_pnl_delta_pct"] or 0.0,
                vs_exp14["windows_ev_improved"],
                vs_exp14["windows_ev_regressed"],
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B behavior, event sources, LLM/news behavior, sizing, exits, or adapters changed. A positive version would need shared default-off state_surface_sleeve.py parity before promotion.",
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
    base._filter_benchmark_momentum = _filter_self_leadership_exception
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
                    "vs_exp_20260509_014_gate": payload["delta_metrics"][
                        "vs_exp_20260509_014_gate"
                    ],
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
