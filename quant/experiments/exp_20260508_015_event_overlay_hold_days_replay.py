"""exp-20260508-015 event overlay hold-days replay.

Alpha search. The default-off event overlay with the non-generic state-surface
add-on is the strongest recent non-core alpha surface, but its lifecycle is
still frozen at the original source-level 10 day hold. This experiment changes
one causal variable only: the fixed event hold horizon.

Core A/B entries, ranking, sizing, exits, LLM/news behavior, event source
definitions, state add-on eligibility, and production orders are unchanged.
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

from experiments.exp_20260504_010_sec_event_sleeve_backtest import (  # noqa: E402
    build_primary_candidates as build_sec_negative_candidates,
)
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    ROUND_TRIP_COST_PCT,
    _load_form4_events,
    _load_price_map,
)
from experiments.exp_20260504_039_sec_governance_procedural_overlay import (  # noqa: E402
    _candidate_events as build_sec_governance_candidates,
)
from experiments.exp_20260507_025_event_state_score_tilt import (  # noqa: E402
    WINDOWS,
    _combined_metrics,
    _core_metrics,
    _coverage,
    _enrich_event_trades,
    _event_equity_curve,
    _gate_summary,
    _load_core_result,
    _repo_rel,
    _safe,
    _trade_summary,
    _write_json,
    _write_text,
)


EXP_ID = "exp-20260508-015"
STEM = "event_overlay_hold_days_replay"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

GENERIC_SURFACE = "balanced_state_leadership"
CURRENT_VARIANT = "hold_10d_current"
SOURCE_ORDER = {
    "sec_governance_procedural": 0,
    "sec_negative_reaction": 1,
    "form4_meaningful_purchase": 2,
}

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "hold_5d",
            {
                "description": "Exit event overlays at the 5 trading-day horizon.",
                "hold_days": 5,
            },
        ),
        (
            CURRENT_VARIANT,
            {
                "description": "Current default-off paper lifecycle: 10 trading-day event hold.",
                "hold_days": 10,
            },
        ),
        (
            "hold_20d",
            {
                "description": "Exit event overlays at the 20 trading-day horizon.",
                "hold_days": 20,
            },
        ),
    ]
)


def _idx_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") >= date_value:
            return idx
    return None


def _row_by_date(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> dict[str, Any] | None:
    for row in prices.get(str(ticker).upper(), []):
        if str(row.get("date") or "") == date_value:
            return row
    return None


def _price_ready_candidate(
    candidate: dict[str, Any],
    *,
    source: str,
    prices: dict[str, list[dict[str, Any]]],
    hold_days: int,
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    if source == "form4_meaningful_purchase":
        entry_anchor = str(candidate.get("usable_trade_date") or "")[:10]
        # Preserve the current Form 4 source semantics: the existing 10d sleeve
        # exits at entry_idx + HOLD_DAYS, unlike the SEC sources' +days-1.
        exit_offset = hold_days
    else:
        entry_anchor = str(candidate.get("entry_date") or candidate.get("usable_trade_date") or "")[:10]
        exit_offset = hold_days - 1

    rows = prices.get(ticker) or []
    if not ticker or not entry_anchor or not rows:
        return {
            **candidate,
            "source": source,
            "hold_days": hold_days,
            "status": "missing_price_history",
        }

    entry_idx = _idx_on_or_after(rows, entry_anchor)
    if entry_idx is None:
        return {
            **candidate,
            "source": source,
            "hold_days": hold_days,
            "status": "missing_entry_price",
        }

    if source == "sec_governance_procedural":
        horizon = (candidate.get("horizons") or {}).get(f"{hold_days}d") or {}
        if horizon and horizon.get("status") != "valid":
            return {
                **candidate,
                "source": source,
                "hold_days": hold_days,
                "status": str(horizon.get("status") or "invalid_horizon"),
            }
        exit_date = str(horizon.get("end_date") or "")[:10]
        exit_row = _row_by_date(prices, ticker, exit_date) if exit_date else None
        if exit_row is None and not exit_date:
            exit_idx = entry_idx + exit_offset
            if exit_idx < len(rows):
                exit_row = rows[exit_idx]
                exit_date = str(exit_row.get("date") or "")[:10]
    else:
        exit_idx = entry_idx + exit_offset
        if exit_idx >= len(rows):
            return {
                **candidate,
                "source": source,
                "hold_days": hold_days,
                "status": "missing_exit_price",
            }
        exit_row = rows[exit_idx]
        exit_date = str(exit_row.get("date") or "")[:10]

    entry_row = rows[entry_idx]
    entry_open = entry_row.get("open")
    exit_close = (exit_row or {}).get("close")
    if not entry_open or not exit_close:
        return {
            **candidate,
            "source": source,
            "hold_days": hold_days,
            "status": "missing_open_or_close",
        }

    entry_open = float(entry_open)
    exit_close = float(exit_close)
    shares = EVENT_NOTIONAL / entry_open
    pnl = shares * exit_close - EVENT_NOTIONAL - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
    gross_return = exit_close / entry_open - 1.0
    net_return = pnl / EVENT_NOTIONAL
    return {
        **candidate,
        "source": source,
        "status": "price_ready",
        "hold_days": hold_days,
        "entry_date": str(entry_row.get("date") or "")[:10],
        "exit_date": exit_date,
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "gross_return_pct": round(gross_return, 6),
        "net_return_pct": round(net_return, 6),
        "notional": EVENT_NOTIONAL,
        "shares": shares,
        "pnl": round(pnl, 2),
    }


def _select_source_trades(
    candidates: list[dict[str, Any]],
    *,
    source: str,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if row.get("status") == "price_ready"
        and start <= str(row.get("entry_date") or "")[:10] <= end
    ]
    skipped = [
        {
            "source": source,
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date") or row.get("usable_trade_date"),
            "hold_days": row.get("hold_days"),
            "reason": row.get("status") or "not_price_ready",
        }
        for row in candidates
        if row.get("status") != "price_ready"
        and start <= str(row.get("entry_date") or row.get("usable_trade_date") or "")[:10] <= end
    ]

    if source == "form4_meaningful_purchase":
        scoped.sort(
            key=lambda row: (
                row["entry_date"],
                -float(row.get("total_purchase_value") or 0.0),
                str(row.get("ticker") or ""),
            )
        )
    elif source == "sec_negative_reaction":
        scoped.sort(
            key=lambda row: (
                row["entry_date"],
                float(row.get("reaction_excess_return") or 0.0),
                str(row.get("ticker") or ""),
            )
        )
    else:
        scoped.sort(
            key=lambda row: (
                row["entry_date"],
                str(row.get("target_cell") or ""),
                float(row.get("reaction_excess_return") or 0.0),
                str(row.get("ticker") or ""),
            )
        )

    selected: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in scoped:
        entry_date = str(row["entry_date"])[:10]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if active:
            skipped.append(
                {
                    "source": source,
                    "ticker": row.get("ticker"),
                    "entry_date": entry_date,
                    "hold_days": row.get("hold_days"),
                    "reason": "source_slot_full",
                    "active_tickers": [trade.get("ticker") for trade in active],
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _load_repriced_event_trades(
    hold_days: int,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
    dict[str, list[dict[str, Any]]],
]:
    prices = _load_price_map()

    form4_events, form4_path = _load_form4_events(prices)
    form4_candidates = [
        _price_ready_candidate(
            event,
            source="form4_meaningful_purchase",
            prices=prices,
            hold_days=hold_days,
        )
        for event in form4_events
    ]

    sec_negative_candidates, sec_negative_prices = build_sec_negative_candidates()
    for ticker, rows in sec_negative_prices.items():
        prices.setdefault(str(ticker).upper(), rows)
    sec_negative_trades = [
        _price_ready_candidate(
            row,
            source="sec_negative_reaction",
            prices=prices,
            hold_days=hold_days,
        )
        for row in sec_negative_candidates
    ]

    governance_candidates, governance_prices, governance_coverage = build_sec_governance_candidates()
    for ticker, rows in governance_prices.items():
        prices.setdefault(str(ticker).upper(), rows)
    governance_trades = [
        _price_ready_candidate(
            row,
            source="sec_governance_procedural",
            prices=prices,
            hold_days=hold_days,
        )
        for row in governance_candidates
    ]

    source_candidates = {
        "form4_meaningful_purchase": form4_candidates,
        "sec_negative_reaction": sec_negative_trades,
        "sec_governance_procedural": governance_trades,
    }
    by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    source_skips: dict[str, list[dict[str, Any]]] = {
        source: [] for source in SOURCE_ORDER
    }
    source_selected_counts: dict[str, int] = {source: 0 for source in SOURCE_ORDER}

    for label, window in WINDOWS.items():
        rows = []
        for source in SOURCE_ORDER:
            selected, skipped = _select_source_trades(
                source_candidates[source],
                source=source,
                start=window["start"],
                end=window["end"],
            )
            rows.extend(selected)
            source_skips[source].extend(skipped)
            source_selected_counts[source] += len(selected)
        rows.sort(
            key=lambda row: (
                row["entry_date"],
                SOURCE_ORDER.get(str(row.get("source") or ""), 99),
                str(row.get("ticker") or ""),
            )
        )
        by_window[label] = rows

    coverage = {
        "hold_days": hold_days,
        "form4_source_path": str(form4_path) if form4_path else None,
        "raw_candidate_counts": {
            source: len(rows) for source, rows in source_candidates.items()
        },
        "price_ready_candidate_counts": {
            source: sum(1 for row in rows if row.get("status") == "price_ready")
            for source, rows in source_candidates.items()
        },
        "selected_trade_counts": source_selected_counts,
        "sec_governance_coverage": governance_coverage,
        "source_skipped_counts": {
            source: len(rows) for source, rows in source_skips.items()
        },
        "source_skipped_reason_counts": {
            source: dict(Counter(str(row.get("reason") or "unknown") for row in rows))
            for source, rows in source_skips.items()
        },
        "source_exit_semantics": {
            "form4_meaningful_purchase": "entry_idx + hold_days, matching current source sleeve",
            "sec_negative_reaction": "entry_idx + hold_days - 1",
            "sec_governance_procedural": "source horizon end_date when available, otherwise entry_idx + hold_days - 1",
        },
    }
    return by_window, coverage, prices


def _eligible_for_state_addon(trade: dict[str, Any]) -> bool:
    return (
        bool(trade.get("state_feature_available"))
        and bool(trade.get("state_score_positive"))
        and str(trade.get("state_surface") or "") != GENERIC_SURFACE
    )


def _with_current_state_addon(trade: dict[str, Any], variant_name: str) -> dict[str, Any]:
    scalar = 2.0 if _eligible_for_state_addon(trade) else 1.0
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_surface_addon_eligible": _eligible_for_state_addon(trade),
        "state_score_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _best_variant_name(gates: dict[str, dict[str, Any]]) -> str:
    return max(
        gates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def _eligible_summary(enriched_by_variant: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    out: dict[str, Any] = OrderedDict()
    for name, by_window in enriched_by_variant.items():
        rows = [trade for trades in by_window.values() for trade in trades]
        eligible = [trade for trade in rows if _eligible_for_state_addon(trade)]
        out[name] = {
            "event_trade_count": len(rows),
            "eligible_trade_count": len(eligible),
            "eligible_fraction": round(len(eligible) / len(rows), 4) if rows else None,
            "eligible_total_pnl_before_scalar": round(
                sum(float(row.get("pnl") or 0.0) for row in eligible),
                2,
            ),
            "eligible_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in eligible}
            ),
        }
    return out


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        core_metrics[label] = _core_metrics(result)

    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_coverage: dict[str, Any] = OrderedDict()
    variant_enriched: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict()

    for name, variant in VARIANTS.items():
        hold_days = int(variant["hold_days"])
        raw_event_trades, coverage, prices = _load_repriced_event_trades(hold_days)
        enriched = _enrich_event_trades(raw_event_trades)
        variant_enriched[name] = enriched
        variant_coverage[name] = coverage
        for label, window in WINDOWS.items():
            scaled = [
                _with_current_state_addon(trade, name)
                for trade in enriched[label]
            ]
            curve = _event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _combined_metrics(
                core_results[label],
                curve,
                scaled,
            )
            variant_events[name][label] = _trade_summary(scaled)

    current_metrics = variant_metrics[CURRENT_VARIANT]
    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    current_gates = OrderedDict(
        (name, _gate_summary(current_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != CURRENT_VARIANT
    )
    best_variant = _best_variant_name(current_gates)
    best_gate = current_gates[best_variant]
    accepted = bool(best_gate["passed"] and core_gates[best_variant]["passed"])

    if accepted:
        decision = "promising_replay_only_hold_day_change"
        rationale = (
            f"Promising replay-only: {best_variant} beat the current 10d event "
            "overlay with the non-generic state add-on across the canonical "
            "three-window Gate 4 rule. Promotion would require changing the "
            "shared default-off event paper adapters, not only a backtest script."
        )
        rejection_reason = None
        next_action = (
            "If promoted, update the shared default-off event paper adapters and "
            "production report fields together, then add parity tests before any live capital."
        )
    else:
        decision = "rejected"
        rationale = (
            f"Rejected: {best_variant} was the best alternate hold horizon, but it "
            "did not beat the current 10d event overlay with enough stable three-window "
            "EV improvement and materiality."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the current 10d event overlay lifecycle; do not retry nearby hold-day "
            "sweeps without new closed forward paper evidence or a different lifecycle signal."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_overlay_hold_day_replay",
        "mechanism_family": "external_event_satellite_overlay_lifecycle",
        "hypothesis": (
            "The current event overlay may be exiting too early or too late; changing "
            "only the fixed hold horizon could improve the event/state add-on sleeve's "
            "expected-value contribution without adding new tickers or filters."
        ),
        "alpha_hypothesis": {
            "category": "exit/lifecycle",
            "entry_exit_ranking_or_allocation": "exit",
            "why_this_now": (
                "LLM soft-ranking, analyst revisions, gap-cancel discriminators, pre-earnings "
                "risk buckets, simple universe baskets, event source pruning, and event state-score "
                "floors are either data-limited or recently rejected. The event overlay remains a "
                "positive surface; lifecycle duration is a distinct untested causal variable."
            ),
        },
        "single_causal_variable": "fixed event overlay hold_days",
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": CURRENT_VARIANT,
            "base_event_notional_usd": EVENT_NOTIONAL,
            "state_surface_addon_scalar": 2.0,
            "state_surface_addon_rule": (
                "score > 0 and state_surface != balanced_state_leadership"
            ),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "event source definitions",
                "event source thresholds",
                "event source priority",
                "per-source max positions",
                "state-surface add-on eligibility",
                "state-surface add-on scalar",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "nearby_positive_priors": {
                "exp-20260504-049": "Default-off event overlay bundle improved all three windows.",
                "exp-20260507-026": "Non-generic positive state-surface add-on improved all three windows versus the full event bundle.",
            },
            "nearby_rejected_or_limited": {
                "exp-20260507-012": "Event source pruning failed; keep source bundle intact.",
                "exp-20260507-019": "Shared event/state capacity failed versus event-only.",
                "exp-20260507-024": "Event price-structure tilt regressed late_strong.",
                "exp-20260508-005": "State score floor tightening rejected; keep score > 0.",
                "exp-20260508-013": "Pre-earnings 8-21 risk buckets rejected.",
                "exp-20260508-014": "Gap-cancel Phase B joint discriminator rejected.",
            },
            "why_not_simple_repeat": (
                "This does not prune sources, retune event thresholds, alter state-score floors, "
                "share capacity with core/state sleeves, or use the rejected gap/pre-earnings families. "
                "It tests only the event overlay lifecycle duration."
            ),
            "mechanism_insight_conflict": (
                "No conflict with current mechanism insights: it avoids LLM sparse joins, analyst "
                "revision zero-touch data, noisy ticker expansion, and recently rejected state/gap variants."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "current_event_overlay": current_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_current_event_overlay": current_gates,
        },
        "expected_value_score_delta": {
            "best_variant_vs_current_event_overlay": {
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
            "by_variant": variant_coverage,
            "state_score_feature_by_variant": {
                name: _coverage(rows) for name, rows in variant_enriched.items()
            },
            "state_surface_addon_eligible_by_variant": _eligible_summary(variant_enriched),
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
                "Hold-day promotion must be implemented in shared default-off event paper adapters "
                "and surfaced by run.py; a backtest-only hold change is not acceptable."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking remains sample-limited; this deterministic lifecycle test does "
                "not weaken or expand LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "10-K candidate expansion is a forward/PIT observation task, estimate revisions have zero "
            "candidate touches, LLM soft-ranking lacks outcome joins, and recent gap/pre-earnings/event "
            "quality variants failed or were only immaterial."
        ),
        "risk_of_change": (
            "A shorter hold can miss delayed event drift; a longer hold can tie up the source slot "
            "and block profitable follow-on events. The selection effect is explicitly replayed here."
        ),
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_event_overlay"][best]
    lines = [
        "# exp-20260508-015 Event Overlay Hold-Days Replay",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests whether the current default-off event overlay plus non-generic state-surface add-on should use a different fixed hold horizon.",
        "",
        "## Best Variant Vs Current 10d Overlay",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"]["current_event_overlay"][label]
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
            "| Variant | EV Sum Vs Current | PnL Delta Vs Current | Windows EV Improved | Windows EV Regressed | Passed |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_current_event_overlay"].items():
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
            json.dumps(
                payload["coverage"]["state_surface_addon_eligible_by_variant"],
                indent=2,
                sort_keys=True,
            ),
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
            "title": "Event overlay hold-days replay",
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
                    "best_variant_vs_current_event_overlay": payload["delta_metrics"][
                        "variant_vs_current_event_overlay"
                    ][best]["delta"],
                    "best_variant_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "production_impact": payload["production_impact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
