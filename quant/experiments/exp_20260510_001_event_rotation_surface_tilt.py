"""exp-20260510-001 event rotation-surface tilt replay.

Alpha search, replay-only. The current strongest paper alpha is the frozen
event bundle plus a 2.0x notional add-on for positive PIT scores on
non-generic state surfaces. This experiment changes one causal variable inside
that already-accepted paper lead: whether the `rotation_breakout_leadership`
surface deserves a higher bounded paper notional than the other eligible
non-generic event surfaces.

No production orders, default backtest behavior, core A/B ranking, sizing,
exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_026_non_generic_event_state_addon as base  # noqa: E402


EXPERIMENT_ID = "exp-20260510-001"
STEM = "event_rotation_surface_tilt"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

ROTATION_SURFACE = "rotation_breakout_leadership"
CURRENT_LEAD_VARIANT = "current_non_generic_positive_add_200"
GENERIC_SURFACE = base.GENERIC_SURFACE

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Frozen event bundle; no non-generic state-surface add-on.",
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 1.0,
                "rotation_surface_scalar": 1.0,
            },
        ),
        (
            CURRENT_LEAD_VARIANT,
            {
                "description": "Current paper lead: 2.0x for all positive non-generic state-surface events.",
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_surface_scalar": 2.0,
            },
        ),
        (
            "rotation_surface_add_250",
            {
                "description": "2.5x only for eligible rotation-breakout surface events; other eligible surfaces stay 2.0x.",
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_surface_scalar": 2.5,
            },
        ),
        (
            "rotation_surface_add_300",
            {
                "description": "3.0x only for eligible rotation-breakout surface events; other eligible surfaces stay 2.0x.",
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_surface_scalar": 3.0,
            },
        ),
    ]
)


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _eligible_non_generic_positive(trade: dict[str, Any]) -> bool:
    return (
        bool(trade.get("state_feature_available"))
        and bool(trade.get("state_score_positive"))
        and str(trade.get("state_surface") or "") != GENERIC_SURFACE
    )


def _surface_scalar(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    if not _eligible_non_generic_positive(trade):
        return float(variant["default_scalar"])
    if str(trade.get("state_surface") or "") == ROTATION_SURFACE:
        return float(variant["rotation_surface_scalar"])
    return float(variant["eligible_non_rotation_scalar"])


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    scalar = _surface_scalar(trade, variant)
    base_notional = float(trade.get("notional") or base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    surface = str(trade.get("state_surface") or "")
    return {
        **trade,
        "variant": variant_name,
        "state_surface_tilt_eligible": _eligible_non_generic_positive(trade),
        "rotation_surface_tilt_eligible": (
            _eligible_non_generic_positive(trade) and surface == ROTATION_SURFACE
        ),
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _selection_summary(enriched: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    eligible = [trade for trade in rows if _eligible_non_generic_positive(trade)]
    rotation = [
        trade
        for trade in eligible
        if str(trade.get("state_surface") or "") == ROTATION_SURFACE
    ]
    by_window: dict[str, Any] = OrderedDict()
    by_source: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "wins": 0, "total_pnl": 0.0}
    )
    for label, trades in enriched.items():
        selected = [
            trade
            for trade in trades
            if _eligible_non_generic_positive(trade)
            and str(trade.get("state_surface") or "") == ROTATION_SURFACE
        ]
        by_window[label] = {
            "trade_count": len(selected),
            "wins": sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0),
            "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
            "tickers": sorted({str(trade.get("ticker") or "") for trade in selected}),
        }
        for trade in selected:
            source = str(trade.get("source") or "unknown")
            row = by_source[source]
            row["trade_count"] += 1
            row["wins"] += 1 if float(trade.get("pnl") or 0.0) > 0 else 0
            row["total_pnl"] += float(trade.get("pnl") or 0.0)

    source_out = {
        source: {
            "trade_count": row["trade_count"],
            "wins": row["wins"],
            "win_rate": _round(row["wins"] / row["trade_count"], 4)
            if row["trade_count"]
            else None,
            "total_pnl": _round(row["total_pnl"], 2),
        }
        for source, row in sorted(by_source.items())
    }
    positive_pnl = [float(trade.get("pnl") or 0.0) for trade in rotation if float(trade.get("pnl") or 0.0) > 0]
    max_single_positive_share = None
    if positive_pnl and sum(positive_pnl) > 0:
        max_single_positive_share = max(positive_pnl) / sum(positive_pnl)
    return {
        "event_trade_count": len(rows),
        "non_generic_positive_trade_count": len(eligible),
        "rotation_surface_trade_count": len(rotation),
        "rotation_surface_wins": sum(1 for trade in rotation if float(trade.get("pnl") or 0.0) > 0),
        "rotation_surface_win_rate": _round(
            sum(1 for trade in rotation if float(trade.get("pnl") or 0.0) > 0) / len(rotation),
            4,
        )
        if rotation
        else None,
        "rotation_surface_total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in rotation),
            2,
        ),
        "rotation_surface_windows_present": sum(
            1 for row in by_window.values() if row["trade_count"] > 0
        ),
        "rotation_surface_by_window": by_window,
        "rotation_surface_by_source": source_out,
        "max_single_rotation_positive_pnl_share": _round(max_single_positive_share, 4),
    }


def _variant_event_summary(
    scaled_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_window: dict[str, Any] = OrderedDict()
    total_pnl = 0.0
    trades = 0
    wins = 0
    scalars: Counter[str] = Counter()
    for label, rows in scaled_by_window.items():
        window_pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
        window_wins = sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0)
        for row in rows:
            scalars[str(row.get("state_surface_scalar"))] += 1
        trades += len(rows)
        wins += window_wins
        total_pnl += window_pnl
        by_window[label] = {
            "event_trade_count": len(rows),
            "event_pnl": _round(window_pnl, 2),
            "event_win_rate": _round(window_wins / len(rows), 4) if rows else None,
        }
    return {
        "event_trade_count": trades,
        "event_pnl": _round(total_pnl, 2),
        "event_win_rate": _round(wins / trades, 4) if trades else None,
        "scalar_counts": dict(sorted(scalars.items())),
        "by_window": by_window,
    }


def _gate_vs_current(
    current_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = base._gate_summary(current_metrics, after_metrics)
    sample_ok = (
        (selection.get("rotation_surface_trade_count") or 0) >= 6
        and (selection.get("rotation_surface_windows_present") or 0) >= 2
        and (
            selection.get("max_single_rotation_positive_pnl_share") is None
            or selection["max_single_rotation_positive_pnl_share"] <= 0.55
        )
    )
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "passed": bool(gate["passed"] and sample_ok),
        "sample_guard": {
            "min_rotation_surface_trades": 6,
            "min_windows_present": 2,
            "max_single_positive_pnl_share": 0.55,
            "actual_rotation_surface_trades": selection.get("rotation_surface_trade_count"),
            "actual_windows_present": selection.get("rotation_surface_windows_present"),
            "actual_max_single_positive_pnl_share": selection.get(
                "max_single_rotation_positive_pnl_share"
            ),
        },
    }


def _choose_best(
    gates_vs_current: dict[str, dict[str, Any]],
    variant_metrics: dict[str, dict[str, dict[str, Any]]],
) -> str:
    names = [name for name in VARIANTS if name not in ("full_bundle", CURRENT_LEAD_VARIANT)]
    passed = [name for name in names if gates_vs_current[name]["passed"]]
    candidates = passed or names
    return max(
        candidates,
        key=lambda name: (
            gates_vs_current[name]["delta"]["after_ev_sum"],
            gates_vs_current[name]["delta"]["after_pnl_sum"],
            variant_metrics[name]["late_strong"]["expected_value_score"],
        ),
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = base._load_event_trades()
    event_trades = base._enrich_event_trades(raw_event_trades)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in base.WINDOWS.items():
        result = base._load_core_result(window)
        core_metrics[label] = base._core_metrics(result)
        for name, variant in VARIANTS.items():
            scaled = [_scaled_trade(trade, name, variant) for trade in event_trades[label]]
            curve = base._event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = base._combined_metrics(result, curve, scaled)
            variant_events.setdefault(name, OrderedDict())[label] = scaled

    event_summaries = OrderedDict(
        (name, _variant_event_summary(rows_by_window))
        for name, rows_by_window in variant_events.items()
    )
    selection = _selection_summary(event_trades)
    current_metrics = variant_metrics[CURRENT_LEAD_VARIANT]
    core_gates = OrderedDict(
        (name, base._gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    full_gates = OrderedDict(
        (name, base._gate_summary(variant_metrics["full_bundle"], variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    gates_vs_current = OrderedDict(
        (
            name,
            _gate_vs_current(current_metrics, variant_metrics[name], selection),
        )
        for name in VARIANTS
        if name not in ("full_bundle", CURRENT_LEAD_VARIANT)
    )
    best_variant = _choose_best(gates_vs_current, variant_metrics)
    best_gate = gates_vs_current[best_variant]
    accepted = bool(best_gate["passed"] and core_gates[best_variant]["passed"])
    decision = "promising_replay_only_rotation_surface_tilt" if accepted else "rejected"
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` did not clear the current-lead gate: "
            f"EV delta {best_gate['delta']['aggregate_ev_delta']}, "
            f"PnL delta {best_gate['delta']['aggregate_pnl_delta']}, "
            f"EV improved/regressed {best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}."
        )

    platform_pre_earnings_probe = {
        "hypothesis": (
            "Platform-pool candidates in the pre_earnings_0_7 tag may deserve a "
            "candidate-level replay, but historical candidate-event touches are too sparse."
        ),
        "historical_candidate_touches": {
            "late_strong": 0,
            "mid_weak": 0,
            "old_thin": 1,
        },
        "decision": "deferred_for_insufficient_replay_sample",
        "why_not_now": (
            "Only one frozen three-window candidate row matched pre_earnings_0_7, "
            "so promoting or even rejecting a rule would be sample overfit."
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_surface_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Inside the strongest current event-bundle paper alpha, rotation-breakout "
            "leadership events may carry better event quality than other positive "
            "non-generic state-surface rows and therefore deserve a bounded extra "
            "paper-notional tilt."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking and platform pre-earnings candidate timing are "
                "sample-limited, while exp-20260509-006/007 identify the event bundle "
                "and non-generic positive state-surface add-on as the strongest "
                "current alpha family."
            ),
        },
        "single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": CURRENT_LEAD_VARIANT,
            "rotation_surface": ROTATION_SURFACE,
            "base_event_notional_usd": base.EVENT_NOTIONAL,
            "hold_days": base.HOLD_DAYS,
            "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
            "sample_guard": {
                "min_rotation_surface_trades": 6,
                "min_windows_present": 2,
                "max_single_positive_pnl_share": 0.55,
            },
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
            label: f"{window['start']} -> {window['end']}"
            for label, window in base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260509-006": (
                "Accepted the frozen event bundle as the strongest paper-only "
                "candidate-pool extension versus current core."
            ),
            "exp-20260509-007": (
                "Accepted 2.0x add-on for positive PIT scores on non-generic "
                "event state surfaces as current event allocation lead."
            ),
            "exp-20260509-024": (
                "Rejected broad benchmark-momentum gate on the event bundle; this "
                "run uses event-specific state surface structure instead."
            ),
            "exp-20260509-025": (
                "Rejected state-surface self-leadership exception; this run does "
                "not rescue benchmark-gated candidates."
            ),
            "platform_pre_earnings_probe": platform_pre_earnings_probe,
            "mechanism_insight_conflict": (
                "No conflict: this is not LLM ranking, nearby PEAD price/volume "
                "thresholding, event source pruning, broad benchmark gating, or "
                "core A/B threshold tuning."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_bundle": variant_metrics["full_bundle"],
            CURRENT_LEAD_VARIANT: current_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_full_bundle": full_gates,
            "variant_vs_current_lead": gates_vs_current,
        },
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "selection": selection,
        "event_overlay": event_summaries,
        "source_coverage": source_coverage,
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
            "promotion_blocker_if_positive": (
                "Before live/default capital, implement the event overlay as a "
                "shared trade-enabled adapter used by run.py and backtester.py, "
                "with parity tests and closed forward replacement-value evidence."
            ),
        },
        "gate4": {
            "passed": bool(accepted),
            "basis": (
                "Three canonical backtesting.md windows. Primary comparison is "
                "against the current non-generic positive 2.0x event add-on, not "
                "only against core."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this event-structure "
                "alpha uses replayable PIT state fields instead."
            ),
        },
        "decision_rationale": (
            "Accepted as replay-only event allocation lead refinement; no live "
            "orders change until a shared adapter and forward outcomes exist."
            if accepted
            else rejection_reason
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not promote to live/default orders from this replay alone; if "
            "accepted, first build a shared default-off event adapter and collect "
            "closed forward replacement-value evidence."
            if accepted
            else "Do not retry nearby rotation-surface notional scalars without new forward event evidence."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM ranking and platform pre-earnings candidate timing due "
            "to insufficient production-aligned samples; skipped PEAD threshold "
            "retunes, event benchmark gates, source pruning, and core A/B sizing "
            "retunes because recent logs rejected or warned against nearby variants."
        ),
        "risk_of_change": (
            "A higher rotation-surface scalar may over-concentrate a small event "
            "subset; sample guard requires multi-window coverage and limits "
            "single-trade contribution, but live promotion still needs forward evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Rotation-Surface Tilt",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search. Tests whether `rotation_breakout_leadership` event rows deserve a higher bounded paper notional than the current 2.0x non-generic positive event-surface add-on.",
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    current = payload["before_metrics"][CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]
    for label in base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {cev:.4f} | {aev:.4f} | {dev:+.4f} | ${cpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                cev=current[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                cpnl=current[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV delta vs current lead: {:+.4f} ({:+.2%})".format(
                gate["delta"]["aggregate_ev_delta"],
                gate["delta"]["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL delta vs current lead: ${:+,.2f} ({:+.2%})".format(
                gate["delta"]["aggregate_pnl_delta"],
                gate["delta"]["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                gate["delta"]["windows_ev_improved"],
                gate["delta"]["windows_ev_regressed"],
            ),
            "- Sample guard passed: `{}`".format(gate["sample_guard_passed"]),
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"] or "",
            "",
            "## Production Impact",
            "",
            "Replay only. Production and default backtest order paths are unchanged. A positive live-capital version would need a shared trade-enabled event adapter, run/backtester parity tests, and forward paper replacement-value evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface tilt",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))


def main() -> None:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_variant": best,
                "ev_delta_vs_current": gate["delta"]["aggregate_ev_delta"],
                "pnl_delta_vs_current": gate["delta"]["aggregate_pnl_delta"],
                "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
