"""exp-20260508-001: pre-earnings 22-45 day risk replay.

Alpha search, replay-only. The entry-state oracle shows a modestly positive
candidate pocket 22-45 calendar days before earnings, but prior DTE experiments
warn against adding narrow earnings-distance rules without multi-window proof.

This experiment tests one causal variable: whether already-entered A/B trades
tagged `pre_earnings_22_45` deserve a bounded cap-aware risk boost. It does not
change signal generation, candidate ranking, entries, exits, add-ons, universe,
LLM/news behavior, or production orders. Any positive result would still require
a shared run.py/backtester.py risk policy plus parity tests before promotion.
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


EXPERIMENT_ID = "exp-20260508-001"
STEM = "pre_earnings_22_45_risk_replay"
SOURCE_EXPERIMENTS = ("exp-20260507-032", "exp-20260507-033")
TREATMENT_TAG = "pre_earnings_22_45"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = (
    REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS = OrderedDict(
    [
        ("pre_earnings_22_45_1_25x_cap_aware", {"risk_multiplier": 1.25}),
        ("pre_earnings_22_45_1_50x_cap_aware", {"risk_multiplier": 1.50}),
        ("pre_earnings_22_45_2_00x_cap_aware", {"risk_multiplier": 2.00}),
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


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Pre-Earnings 22-45 Risk Replay",
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
        "| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
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
            "| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |",
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
            "## Rejection Reason",
            "",
            payload["rejection_reason"] or "None",
            "",
            "## Production Impact",
            "",
            "Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.",
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
    decision = "accepted_replay_only" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if decision == "rejected":
        rejection_reason = (
            f"Best variant `{best_variant}` failed Gate 4: EV delta "
            f"{best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), PnL delta "
            f"{best['total_pnl_delta_sum']} ({best['total_pnl_delta_pct']}), "
            f"windows improved/regressed {best['windows_ev_improved']}/"
            f"{best['windows_ev_regressed']}, changed trades "
            f"{best['changed_treatment_trades']} of {best['touched_treatment_trades']} "
            f"touched, max DD worsening {best['max_drawdown_worsening_max']}, "
            f"single ticker positive share {best['max_single_ticker_positive_share']}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Accepted A/B trades 22-45 calendar days before the next earnings "
            "date may represent a stable pre-event continuation pocket that "
            "deserves modest cap-aware add-on risk, unlike the already-rejected "
            "far-earnings broad add-on and older narrow DTE overfit pockets."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "cap_aware_entry_state_risk_replay",
        "mechanism_family": "pre_earnings_entry_state_lifecycle_allocation",
        "single_causal_variable": "pre_earnings_22_45_entry_state_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in base.WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "nearby_rejected": {
                "exp-20260421-023": (
                    "Broad <=2/3/4/5 day pre-earnings entry guard sweep was "
                    "rejected; this test uses a different 22-45 day oracle state "
                    "and only resizes already-entered trades."
                ),
                "exp-20260505-016": (
                    "Residual Financials/Healthcare breakout DTE zero-risk failed; "
                    "this is not a zero-risk retry and is not sector-specific."
                ),
                "exp-20260507-033": (
                    "Far-from-earnings add-on was positive but failed Gate 4 on "
                    "mid_weak regression and old_thin drawdown; this tests a "
                    "different earnings-distance bucket."
                ),
            },
            "mechanism_insight_conflict": (
                "No conflict with the current LLM soft-ranking, C-sleeve, event "
                "source pruning, state-surface, pilot-slot, or raw universe "
                "expansion do-not-repeat zones. The DTE-overfit risk is explicit "
                "and handled by Gate 4 plus no-promotion-on-failure."
            ),
            "why_not_simple_repeat": (
                "This is an entry-state oracle replay for an untested 22-45 day "
                "bucket, not another narrow sector/DTE pocket, not a C-sleeve "
                "enablement, and not a threshold sweep."
            ),
        },
        "parameters": {
            "treatment_tag": TREATMENT_TAG,
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
            "gate4": {
                "expected_value_score_delta_pct": "> 10%",
                "total_pnl_delta_pct": "> 5%",
                "windows_ev_improved": ">= 2 of 3",
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
            "passed": bool(best["proxy_gate4_passed"]),
            "basis": (
                "Replay-only cap-aware resize of baseline entered trades. "
                "Promotion would require shared run.py/backtester.py risk policy."
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
            "blocker_relation": (
                "LLM/news replay is locked out of this deterministic entry-state replay."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby pre_earnings_22_45 risk scalars on this same sample.",
            "A valid retry needs forward entry-state outcomes or an orthogonal event/news quality discriminator.",
            "Any promotion must move the rule into a shared risk policy consumed by run.py and backtester.py with parity tests.",
        ],
        "risk_of_change": (
            "May overweight a shallow pre-event sample and add another DTE-shaped "
            "complexity layer; the old_thin regression is the key collateral risk."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse.",
            "earnings_c_sleeve": "Revalidated after snapshot repair and regressed all three windows.",
            "event_bundle_tuning": "Event/state add-on is already default-off for forward evidence; more same-sample tuning risks overfit.",
            "pilot_pool": "Pilot pool was just expanded and slot-ranked; no closed forward outcomes exist yet.",
            "sma20_reclaim": "Read-only precheck showed negative EV and only seven touched entered trades.",
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
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": payload["alpha_hypothesis_category"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "single_causal_variable": payload["single_causal_variable"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "proxy_before_metrics": payload["proxy_before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": rejection_reason,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "risk_of_change": payload["risk_of_change"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Pre-earnings 22-45 risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "expected_value_score_delta_pct": best["expected_value_score_delta_pct"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "total_pnl_delta_pct": best["total_pnl_delta_pct"],
        "windows_ev_improved": best["windows_ev_improved"],
        "windows_ev_regressed": best["windows_ev_regressed"],
        "next_action": (
            "Do not promote; avoid nearby pre-earnings 22-45 risk scalars without new evidence."
            if decision == "rejected"
            else "Promote only after shared policy and parity tests."
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
