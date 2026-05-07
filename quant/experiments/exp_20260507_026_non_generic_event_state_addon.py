"""exp-20260507-026 non-generic event/state-surface add-on replay.

Alpha search. exp-20260507-025 rejected a broad positive-vs-nonpositive
state-score tilt because it underweighted profitable nonpositive-score event
rows and regressed late_strong. This follow-up changes one narrower causal
variable: add satellite notional only when the event ticker has positive
point-in-time state score on a named non-generic state surface. All other event
rows remain unchanged.

This is replay-only. Core ranking, entries, exits, LLM/news, production orders,
and the default backtester/run strategy path are not changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments.exp_20260507_025_event_state_score_tilt import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _combined_metrics,
    _core_metrics,
    _coverage,
    _enrich_event_trades,
    _event_equity_curve,
    _gate_summary,
    _load_core_result,
    _load_event_trades,
    _repo_rel,
    _safe,
    _trade_summary,
    _write_json,
    _write_text,
)


EXP_ID = "exp-20260507-026"
STEM = "non_generic_event_state_addon"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

GENERIC_SURFACE = "balanced_state_leadership"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Current frozen event bundle; no state-surface add-on.",
                "eligible_scalar": 1.0,
            },
        ),
        (
            "non_generic_positive_add_125",
            {
                "description": "1.25x notional only for positive-score events on non-generic state surfaces.",
                "eligible_scalar": 1.25,
            },
        ),
        (
            "non_generic_positive_add_150",
            {
                "description": "1.50x notional only for positive-score events on non-generic state surfaces.",
                "eligible_scalar": 1.50,
            },
        ),
        (
            "non_generic_positive_add_200",
            {
                "description": "2.00x notional cap for positive-score events on non-generic state surfaces.",
                "eligible_scalar": 2.00,
            },
        ),
    ]
)


def _eligible_for_addon(trade: dict[str, Any]) -> bool:
    return (
        bool(trade.get("state_feature_available"))
        and bool(trade.get("state_score_positive"))
        and str(trade.get("state_surface") or "") != GENERIC_SURFACE
    )


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any]:
    scalar = float(variant["eligible_scalar"]) if _eligible_for_addon(trade) else 1.0
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_surface_addon_eligible": _eligible_for_addon(trade),
        "state_score_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _best_passing_variant(
    full_gates: dict[str, dict[str, Any]],
    core_gates: dict[str, dict[str, Any]],
) -> str:
    candidates = [
        name
        for name in VARIANTS
        if name != "full_bundle" and full_gates[name]["passed"] and core_gates[name]["passed"]
    ]
    if candidates:
        return max(
            candidates,
            key=lambda name: (
                full_gates[name]["delta"]["after_ev_sum"],
                full_gates[name]["delta"]["after_pnl_sum"],
            ),
        )
    names = [name for name in VARIANTS if name != "full_bundle"]
    return max(
        names,
        key=lambda name: (
            full_gates[name]["delta"]["after_ev_sum"],
            full_gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def _eligible_summary(enriched: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    eligible = [trade for trade in rows if _eligible_for_addon(trade)]
    return {
        "event_trade_count": len(rows),
        "eligible_trade_count": len(eligible),
        "eligible_fraction": round(len(eligible) / len(rows), 4) if rows else None,
        "eligible_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in eligible), 2),
        "eligible_surfaces": sorted({str(row.get("state_surface") or "") for row in eligible}),
        "rule": "positive PIT state score and state_surface != balanced_state_leadership",
    }


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = _load_event_trades()
    event_trades = _enrich_event_trades(raw_event_trades)

    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        core_metrics[label] = _core_metrics(result)
        for name, variant in VARIANTS.items():
            scaled = [_scaled_trade(trade, name, variant) for trade in event_trades[label]]
            curve = _event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _combined_metrics(result, curve, scaled)
            variant_events[name][label] = _trade_summary(scaled)

    full_metrics = variant_metrics["full_bundle"]
    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    full_gates = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    best_variant = _best_passing_variant(full_gates, core_gates)
    best_gate = full_gates[best_variant]
    accepted = bool(best_gate["passed"] and core_gates[best_variant]["passed"])
    decision = "promising_replay_only_non_generic_event_state_addon" if accepted else "rejected"

    if accepted:
        rationale = (
            f"Promising replay-only: {best_variant} beat the full frozen event bundle "
            "and core baseline across the three canonical windows without EV regression. "
            "Production use still requires a shared default-off adapter that computes the "
            "same PIT state-surface feature before any capital impact."
        )
        rejection_reason = None
        next_action = (
            "Promote only to a shared default-off event paper adapter with parity tests; "
            "collect closed forward replacement-value outcomes before live capital."
        )
    else:
        rationale = (
            f"Rejected: {best_variant} did not beat the full frozen event bundle with "
            "stable enough three-window EV improvement and materiality."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the full event bundle unchanged; do not retry state-surface event "
            "notional add-ons without forward replacement-value evidence."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_state_surface_addon_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Event trades with positive PIT state score on non-generic opportunity "
            "surfaces deserve add-on satellite notional, while generic balanced-state "
            "events and nonpositive-score events should remain at the frozen bundle size."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "exp-20260507-025 rejected broad state-score tilting versus the full event "
                "bundle, but its diagnostics showed that named non-generic state surfaces "
                "were the cleaner confirmation layer. LLM ranking and earnings/C remain "
                "data-limited or recently rejected."
            ),
        },
        "single_causal_variable": (
            "positive PIT state score on a non-generic state surface controls a bounded "
            "event-notional add-on; all other event rows stay at 1.0x"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
            "generic_surface_not_eligible": GENERIC_SURFACE,
            "base_event_notional_usd": EVENT_NOTIONAL,
            "max_tested_scalar": 2.0,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "capital_accounting": "event equity debits each trade's actual notional and cost",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "event source definitions",
                "event source thresholds",
                "event holding period",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "historical_experiment_check": {
            "direct_parent": {
                "exp-20260507-025": (
                    "Broad positive-vs-nonpositive state-score tilt was rejected versus "
                    "the full event bundle after corrected notional accounting."
                )
            },
            "nearby_rejected": {
                "exp-20260507-012": "Event source pruning did not beat the full bundle.",
                "exp-20260507-019": "Event+state shared-capacity combination failed versus event-only.",
                "exp-20260507-021": "Core-pressure event guard was positive only immaterial versus full bundle.",
                "exp-20260507-022": "5d pre-entry relative-strength tilt was positive only immaterial versus full bundle.",
                "exp-20260507-023": "State-surface scarce-slot core collision ranking failed.",
                "exp-20260507-024": "SMA20/SMA50 price-structure event tilt regressed late_strong versus full bundle.",
            },
            "why_not_simple_repeat": (
                "This does not prune sources, delay entries, underweight nonpositive-score events, "
                "change core capacity, or use SMA20/SMA50 price structure. It only adds notional "
                "to positive-score event rows on named non-generic state surfaces."
            ),
            "mechanism_insight_conflict": (
                "No conflict with recent do-not-repeat zones: no LLM ranking, no raw earnings/C, "
                "no broad universe growth, no source subset permutation, no core slot/capacity change."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_event_bundle": full_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_full_bundle": full_gates,
        },
        "expected_value_score_delta": {
            "best_variant_vs_full_bundle": {
                label: best_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "best_variant_vs_core": {
                label: core_gates[best_variant]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "best_variant": best_variant,
        "event_selection": variant_events,
        "coverage": {
            "source_coverage": source_coverage,
            "state_score_feature": _coverage(event_trades),
            "state_surface_addon": _eligible_summary(event_trades),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_positive": (
                "A shared default-off event paper/live adapter must compute the same PIT-safe "
                "state-surface feature in run.py and backtester before any capital impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking outcome joins remain sparse; this deterministic alpha test "
                "does not weaken or expand LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings re-enable, LLM ranking, event source pruning, FD/Other item-code tweaks, "
            "state-surface pruning/combination/collision ranking, broad universe expansion, and "
            "runner exits all have recent blocker or rejection evidence."
        ),
        "risk_of_change": (
            "The selected scalar doubles a small satellite subset and may overfit the frozen "
            "event sample; forward default-off paper evidence is required before promotion."
        ),
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-026 Non-Generic Event State Add-On",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests a bounded event-satellite add-on for positive PIT state-score events on non-generic state surfaces.",
        "",
        "## Best Variant Vs Full Bundle",
        "",
        "| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    for label in WINDOWS:
        before = payload["before_metrics"]["full_event_bundle"][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=selected["trade_count"],
                epnl=selected["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_full_bundle"].items():
        delta = row["delta"]
        lines.append(
            "| {name} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {passed} |".format(
                name=name,
                ev=delta["aggregate_ev_delta"],
                pnl=delta["aggregate_pnl_delta"],
                wi=delta["windows_ev_improved"],
                wr=delta["windows_ev_regressed"],
                passed=row["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["coverage"]["state_surface_addon"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "No production universe, ranking, sizing, exits, LLM, news, or order path changed.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines))


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Non-generic event state add-on",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_report(payload)

    compact = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "best_variant": payload["best_variant"],
        "coverage": payload["coverage"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_variant_vs_full_bundle": payload["delta_metrics"]["variant_vs_full_bundle"][best]["delta"],
                    "best_variant_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
                    "coverage": payload["coverage"]["state_surface_addon"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
