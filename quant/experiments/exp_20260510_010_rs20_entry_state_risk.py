"""exp-20260510-010: broad RS20 entry-state risk replay.

Alpha search, replay-only. The accepted entry-state oracle showed that
`rs20_leader` is the broadest populated positive pre-entry tag across all three
canonical windows. This experiment asks whether already-entered A/B trades
with that tag deserve cap-aware extra risk.

No production orders, signal generation, ranking, exits, add-ons, universe, or
LLM/news behavior changes here. A positive promotion would need a shared
run.py/backtester.py risk policy and parity tests.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

import exp_20260507_033_far_earnings_entry_state_risk as base  # noqa: E402


EXPERIMENT_ID = "exp-20260510-010"
STEM = "rs20_entry_state_risk"
TREATMENT_TAG = "rs20_leader"
SOURCE_EXPERIMENTS = (
    "exp-20260507-032",
    "exp-20260507-907",
    "exp-20260508-008",
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
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS = OrderedDict(
    [
        ("rs20_1_10x_cap_aware", {"risk_multiplier": 1.10}),
        ("rs20_1_25x_cap_aware", {"risk_multiplier": 1.25}),
        ("rs20_1_50x_cap_aware", {"risk_multiplier": 1.50}),
    ]
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get(
                    "expected_value_score"
                )
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl")
                or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _directional_gate(best: dict[str, Any]) -> bool:
    return (
        (best.get("total_pnl_delta_pct") or 0.0) > 0.05
        and (best.get("expected_value_score_delta_sum") or 0.0) > 0.0
        and best.get("windows_ev_improved") == 3
        and best.get("windows_ev_regressed") == 0
        and (best.get("max_drawdown_worsening_max") or 0.0) <= 0.01
        and (best.get("touched_treatment_trades") or 0) >= 8
        and (best.get("changed_treatment_trades") or 0) >= 3
        and (
            best.get("max_single_ticker_positive_share") is None
            or best.get("max_single_ticker_positive_share") <= 0.50
        )
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["aggregate"][payload["best_variant"]]
    lines = [
        f"# {EXPERIMENT_ID} RS20 Entry-State Risk Replay",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        "| {ev} | {pnl} | {trades} |".format(
            ev=payload["official_baseline_metrics"]["expected_value_score_sum"],
            pnl=payload["official_baseline_metrics"]["total_pnl_sum"],
            trades=payload["official_baseline_metrics"]["trade_count_sum"],
        ),
        "",
        "## Aggregate Replay",
        "",
        "| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Strong gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in payload["aggregate"].items():
        lines.append(
            "| {name} | {ev} | {ev_pct} | {pnl} | {pnl_pct} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                ev_pct=metrics["expected_value_score_delta_pct"],
                pnl=metrics["total_pnl_delta_sum"],
                pnl_pct=metrics["total_pnl_delta_pct"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_treatment_trades"],
                changed=metrics["changed_treatment_trades"],
                dd=metrics["max_drawdown_worsening_max"],
                share=metrics["max_single_ticker_positive_share"],
                gate="PASS" if metrics["proxy_gate4_passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Window Deltas",
            "",
            "| Variant | Window | EV delta | PnL delta | SharpeD delta | DD delta |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in payload["aggregate"].items():
        for window, delta in metrics["by_window_delta"].items():
            lines.append(
                "| {name} | {window} | {ev} | {pnl} | {sharpe} | {dd} |".format(
                    name=name,
                    window=window,
                    ev=delta["expected_value_score"],
                    pnl=delta["total_pnl"],
                    sharpe=delta["sharpe_daily"],
                    dd=delta["max_drawdown_pct"],
                )
            )
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Best Variant Summary",
            "",
            f"- EV delta: `{best['expected_value_score_delta_sum']}` (`{best['expected_value_score_delta_pct']}` proxy basis)",
            f"- PnL delta: `${best['total_pnl_delta_sum']}` (`{best['total_pnl_delta_pct']}`)",
            f"- Touched / changed trades: `{best['touched_treatment_trades']}` / `{best['changed_treatment_trades']}`",
            f"- Single ticker positive share: `{best['max_single_ticker_positive_share']}`",
            "",
            "## Production Impact",
            "",
            "Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed. Any promotion must implement the risk rule in shared production/backtest policy with parity tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    original_tag = base.TREATMENT_TAG
    original_variants = base.VARIANTS
    base.TREATMENT_TAG = TREATMENT_TAG
    base.VARIANTS = VARIANTS
    try:
        by_window = OrderedDict(
            (name, base._replay_window(name, spec))
            for name, spec in base.WINDOWS.items()
        )
        aggregate = base._aggregate(by_window)
    finally:
        base.TREATMENT_TAG = original_tag
        base.VARIANTS = original_variants

    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    directional_gate_passed = _directional_gate(best)
    strong_gate_passed = bool(best.get("proxy_gate4_passed"))
    decision = (
        "accepted_replay_only"
        if strong_gate_passed
        else (
            "promising_replay_only_not_promoted"
            if directional_gate_passed
            else "rejected"
        )
    )
    if strong_gate_passed:
        decision_rationale = (
            "Strong replay gate passed, but live/default promotion still requires "
            "a shared risk policy and run/backtester parity tests."
        )
    elif directional_gate_passed:
        decision_rationale = (
            "Promising replay-only: EV improved in all three canonical windows, "
            "aggregate PnL cleared +5%, drawdown and concentration stayed inside "
            "guards, but the EV delta missed the >10% strong gate. Do not promote "
            "to production without a shared policy and additional evidence."
        )
    else:
        decision_rationale = (
            "Rejected: the best variant did not clear the directional replay "
            "guards strongly enough to justify any policy work."
        )
    rejection_reason = None if directional_gate_passed else decision_rationale

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Accepted A/B trades whose signal-date entry-state oracle tags them "
            "as `rs20_leader` may deserve cap-aware extra risk because a 20-day "
            "ticker-vs-SPY excess return of at least 5pp identifies broad "
            "continuation leadership without adding noisy tickers or LLM input."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "cap_aware_entry_state_risk_replay",
        "mechanism_family": "rs20_entry_state_lifecycle_allocation",
        "single_causal_variable": "rs20_leader_entry_state_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in base.WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260507-032": (
                "Entry-state oracle found `rs20_leader` had 110 candidates, 51 "
                "entered rows, positive 20d forward return, and all three windows."
            ),
            "exp-20260507-907": (
                "Platform-only RS20 risk replay was positive but failed on APP "
                "concentration. This test broadens away from the platform basket "
                "rather than retuning platform thresholds."
            ),
            "exp-20260508-008": (
                "Platform RS20/no-gap remains forward-watch only because missed "
                "candidate sample size is too small. This experiment uses already "
                "entered core A/B trades instead."
            ),
            "why_not_simple_repeat": (
                "This is not a platform RS20 threshold retry, same-day refill, "
                "missed-candidate sleeve, ETF retune, add-on budget, or LLM rule."
            ),
        },
        "parameters": {
            "treatment_tag": TREATMENT_TAG,
            "treatment_definition": "stock 20d return minus SPY 20d return >= 5 percentage points on signal date",
            "variants": VARIANTS,
            "position_cap_policy": {
                "default_initial_cap": base.MAX_POSITION_PCT,
                "spy_relative_leader_cap": base.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT,
                "entry_equity_source": "baseline proxy daily equity at entry date",
                "if_cap_has_no_headroom": "leave baseline shares unchanged",
            },
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
                "earnings_event_long enablement",
            ],
            "strong_gate4": {
                "expected_value_score_delta_pct": "> 10%",
                "total_pnl_delta_pct": "> 5%",
                "windows_ev_improved": ">= 2 of 3",
                "windows_ev_regressed": "0",
                "max_drawdown_worsening": "<= 1pp",
                "touched_treatment_trades": ">= 8",
                "changed_treatment_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
            "directional_gate": {
                "total_pnl_delta_pct": "> 5%",
                "windows_ev_improved": "3 of 3",
                "windows_ev_regressed": "0",
                "max_drawdown_worsening": "<= 1pp",
                "touched_treatment_trades": ">= 8",
                "changed_treatment_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "before_metrics": {
            name: window["official_baseline_metrics"]
            for name, window in by_window.items()
        },
        "proxy_before_metrics": {
            name: window["proxy_before_metrics"] for name, window in by_window.items()
        },
        "after_metrics": {
            variant: {
                name: by_window[name]["variant_results"][variant]["metrics"]
                for name in by_window
            }
            for variant in VARIANTS
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": {
            "strong_gate_passed": strong_gate_passed,
            "directional_gate_passed": directional_gate_passed,
            "basis": (
                "Replay-only cap-aware resize of baseline entered trades across "
                "the three canonical backtesting.md windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is locked out of this deterministic entry-state replay.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not promote from replay-only evidence; implement a shared production/backtest risk policy first if this is retried.",
            "Do not retry nearby RS20 scalar sweeps on the same sample without forward evidence or a materially different risk semantic.",
            "A live/default version must expose the rs20 leader field in production signals and add parity tests.",
        ],
        "risk_of_change": (
            "The replay increases exposure to a broad momentum-leadership cohort. "
            "It may stack with existing accepted sizing pockets if promoted naively, "
            "so any future implementation must define non-stacking semantics."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse.",
            "sec_earnings_filing_shock": "Directional surprise/guidance fields are still missing.",
            "event_state_surface": "Current event/state surfaces are already default-off and need forward outcomes, not another threshold sweep.",
            "low_deployment_etf_overlay": "Already moved to a default-off paper adapter; same-sample ETF retunes are explicitly deferred.",
            "addon_budget": "Breakout and trend add-on upper bounds were just rejected as immaterial.",
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }
    log_record = {
        key: payload[key]
        for key in (
            "experiment_id",
            "timestamp",
            "lane",
            "status",
            "decision",
            "hypothesis",
            "alpha_hypothesis_category",
            "change_type",
            "mechanism_family",
            "single_causal_variable",
            "date_range",
            "market_regime_summary",
            "historical_experiment_check",
            "parameters",
            "before_metrics",
            "proxy_before_metrics",
            "after_metrics",
            "delta_metrics",
            "best_variant",
            "expected_value_score_delta",
            "gate4",
            "production_impact",
            "llm_metrics",
            "decision_rationale",
            "rejection_reason",
            "next_retry_requires",
            "risk_of_change",
            "why_not_other_attractive_points",
            "related_files",
        )
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "RS20 entry-state risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "expected_value_score_delta_pct": best["expected_value_score_delta_pct"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "total_pnl_delta_pct": best["total_pnl_delta_pct"],
        "windows_ev_improved": best["windows_ev_improved"],
        "windows_ev_regressed": best["windows_ev_regressed"],
        "next_action": (
            "Treat as replay-only lead; do not promote without shared policy and parity tests."
            if directional_gate_passed
            else "Do not retry nearby RS20 scalars without new evidence."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
