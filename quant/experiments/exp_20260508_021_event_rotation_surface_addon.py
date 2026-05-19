"""exp-20260508-021 rotation-surface event add-on scalar replay.

Alpha search, replay-only. The current default-off event state add-on gives
2.0x notional to positive-score non-generic state surfaces. This experiment
changes one causal variable: whether the strongest observed surface,
`rotation_breakout_leadership`, deserves extra satellite notional while all
other event rows and the core A/B stack remain locked.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
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


EXP_ID = "exp-20260508-021"
STEM = "event_rotation_surface_addon"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

GENERIC_SURFACE = "balanced_state_leadership"
TREATMENT_SURFACE = "rotation_breakout_leadership"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Frozen event bundle; no state-surface add-on.",
                "base_eligible_scalar": 1.0,
                "rotation_surface_scalar": 1.0,
            },
        ),
        (
            "current_non_generic_positive_2x",
            {
                "description": "Current default-off lead: 2.0x for all positive non-generic state surfaces.",
                "base_eligible_scalar": 2.0,
                "rotation_surface_scalar": 2.0,
            },
        ),
        (
            "rotation_surface_2_5x",
            {
                "description": "Keep other positive non-generic surfaces at 2.0x; lift rotation_breakout_leadership to 2.5x.",
                "base_eligible_scalar": 2.0,
                "rotation_surface_scalar": 2.5,
            },
        ),
        (
            "rotation_surface_3_0x",
            {
                "description": "Keep other positive non-generic surfaces at 2.0x; lift rotation_breakout_leadership to 3.0x.",
                "base_eligible_scalar": 2.0,
                "rotation_surface_scalar": 3.0,
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _eligible_non_generic(trade: dict[str, Any]) -> bool:
    return (
        bool(trade.get("state_feature_available"))
        and bool(trade.get("state_score_positive"))
        and str(trade.get("state_surface") or "") != GENERIC_SURFACE
    )


def _eligible_rotation_surface(trade: dict[str, Any]) -> bool:
    return _eligible_non_generic(trade) and str(trade.get("state_surface") or "") == TREATMENT_SURFACE


def _scalar_for_trade(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    if not _eligible_non_generic(trade):
        return 1.0
    if _eligible_rotation_surface(trade):
        return float(variant["rotation_surface_scalar"])
    return float(variant["base_eligible_scalar"])


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any]:
    scalar = _scalar_for_trade(trade, variant)
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_surface_addon_eligible": _eligible_non_generic(trade),
        "rotation_surface_addon_eligible": _eligible_rotation_surface(trade),
        "state_score_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _positive_share(values_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in values_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _rotation_delta_meta(
    event_trades: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
    current_variant: dict[str, Any],
) -> dict[str, Any]:
    touched = 0
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label, rows in event_trades.items():
        window_touched = 0
        window_delta = 0.0
        tickers = []
        for trade in rows:
            if not _eligible_rotation_surface(trade):
                continue
            touched += 1
            window_touched += 1
            ticker = str(trade.get("ticker") or "").upper()
            tickers.append(ticker)
            base_pnl = float(trade.get("pnl") or 0.0)
            delta = base_pnl * (
                _scalar_for_trade(trade, variant)
                - _scalar_for_trade(trade, current_variant)
            )
            window_delta += delta
            pnl_delta_by_ticker[ticker] += delta
        by_window[label] = {
            "touched_rotation_surface_trades": window_touched,
            "incremental_pnl_before_portfolio_interaction": _round(window_delta, 2),
            "tickers": tickers,
        }
    values = {ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())}
    return {
        "touched_rotation_surface_trades": touched,
        "pnl_delta_by_ticker_before_portfolio_interaction": values,
        "max_single_ticker_positive_share": _round(_positive_share(pnl_delta_by_ticker), 4),
        "by_window": by_window,
    }


def _eligible_summary(event_trades: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in event_trades.values() for trade in trades]
    non_generic = [trade for trade in rows if _eligible_non_generic(trade)]
    rotation = [trade for trade in rows if _eligible_rotation_surface(trade)]

    by_surface: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "total_pnl": 0.0, "tickers": set()}
    )
    for trade in non_generic:
        surface = str(trade.get("state_surface") or "")
        by_surface[surface]["trade_count"] += 1
        by_surface[surface]["total_pnl"] += float(trade.get("pnl") or 0.0)
        by_surface[surface]["tickers"].add(str(trade.get("ticker") or "").upper())

    return {
        "event_trade_count": len(rows),
        "non_generic_positive_trade_count": len(non_generic),
        "rotation_surface_trade_count": len(rotation),
        "rotation_surface_total_pnl_before_scalar": _round(
            sum(float(row.get("pnl") or 0.0) for row in rotation),
            2,
        ),
        "rotation_surface_tickers": [str(row.get("ticker") or "").upper() for row in rotation],
        "by_surface": {
            surface: {
                "trade_count": data["trade_count"],
                "total_pnl": _round(data["total_pnl"], 2),
                "tickers": sorted(data["tickers"]),
            }
            for surface, data in sorted(by_surface.items())
        },
        "rule": (
            "positive PIT state score and state_surface != balanced_state_leadership; "
            "treatment surface is rotation_breakout_leadership"
        ),
    }


def _best_variant(gates_vs_current: dict[str, dict[str, Any]]) -> str:
    names = [name for name in gates_vs_current if name != "current_non_generic_positive_2x"]
    return max(
        names,
        key=lambda name: (
            gates_vs_current[name]["delta"]["after_ev_sum"],
            gates_vs_current[name]["delta"]["after_pnl_sum"],
        ),
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = _load_event_trades()
    event_trades = _enrich_event_trades(raw_event_trades)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
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
    current_metrics = variant_metrics["current_non_generic_positive_2x"]
    gates_vs_core = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    gates_vs_full = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    gates_vs_current = OrderedDict(
        (name, _gate_summary(current_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    rotation_meta = OrderedDict(
        (
            name,
            _rotation_delta_meta(
                event_trades,
                variant,
                VARIANTS["current_non_generic_positive_2x"],
            ),
        )
        for name, variant in VARIANTS.items()
        if name not in {"full_bundle", "current_non_generic_positive_2x"}
    )

    best_variant = _best_variant(gates_vs_current)
    best_gate = gates_vs_current[best_variant]
    best_meta = rotation_meta[best_variant]
    sample_ok = (
        best_meta["touched_rotation_surface_trades"] >= 8
        and (
            best_meta["max_single_ticker_positive_share"] is None
            or best_meta["max_single_ticker_positive_share"] <= 0.50
        )
    )
    accepted = bool(best_gate["passed"] and sample_ok)
    decision = "accepted_replay_only" if accepted else "rejected"

    if accepted:
        rationale = (
            f"{best_variant} beat the current non-generic positive 2x event add-on "
            "with enough sample breadth. Promotion would still require a shared "
            "default-off adapter and forward paper outcomes."
        )
        rejection_reason = None
    else:
        rejection_reason = (
            f"Best variant `{best_variant}` failed promotion guard: Gate summary "
            f"passed={best_gate['passed']}, touched rotation-surface trades "
            f"{best_meta['touched_rotation_surface_trades']} (<8 required), "
            f"single-ticker positive share "
            f"{best_meta['max_single_ticker_positive_share']} (<=0.50 required)."
        )
        rationale = (
            "Rejected for production: the rotation surface is directionally strong, "
            "but this replay is too sample-thin and concentrated to justify more "
            "same-sample event notional."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_state_surface_scalar_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Within the current default-off non-generic positive state-surface event "
            "add-on, rotation_breakout_leadership may be the highest-quality surface "
            "and may deserve more event satellite notional than the broad 2.0x scalar."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking, earnings/C, RS20, add-on heat, and raw universe "
                "growth are blocked or recently rejected. The event state add-on is "
                "the strongest current external-alpha lead with full three-window "
                "replay coverage."
            ),
        },
        "single_causal_variable": (
            "rotation_breakout_leadership event state-surface notional scalar above "
            "the current non-generic positive 2.0x default-off lead"
        ),
        "parameters": {
            "variants": VARIANTS,
            "current_policy_proxy": "current_non_generic_positive_2x",
            "treatment_surface": TREATMENT_SURFACE,
            "generic_surface_not_eligible": GENERIC_SURFACE,
            "base_event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "gate4_extra_sample_guard": {
                "touched_rotation_surface_trades": ">= 8",
                "single_ticker_positive_share": "<= 50%",
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
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "direct_parent": {
                "exp-20260507-026": (
                    "Non-generic positive state-surface event add-on was the best "
                    "current replay-only event lead."
                ),
                "exp-20260508-005": (
                    "Raising the state-score floor was positive but immaterial "
                    "versus the current score>0 lead; this tests surface-specific "
                    "notional instead of another score threshold."
                ),
            },
            "nearby_rejected_or_blocked": {
                "exp-20260507-012": "Event source pruning did not beat the full bundle.",
                "exp-20260507-022": "Pre-entry relative momentum tilt was positive only immaterial.",
                "exp-20260508-015": "Alternative event hold horizons failed versus current 10d.",
                "exp-20260508-019": "Add-on allocation experiments are parity-blocked.",
                "exp-20260508-020": "Sector-cap quality replacement was rejected.",
            },
            "why_not_simple_repeat": (
                "This is not source pruning, score-floor retuning, hold-day retuning, "
                "or event/core collision ranking. It keeps the current event add-on "
                "lead and tests only whether one named state surface deserves extra "
                "notional."
            ),
            "mechanism_insight_conflict": (
                "No conflict with the RS20, LLM-ranking, earnings/C, broad universe, "
                "gap-cancel, add-on heat, or sector-cap do-not-repeat zones."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_event_bundle": full_metrics,
            "current_non_generic_positive_2x": current_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": gates_vs_core,
            "variant_vs_full_bundle": gates_vs_full,
            "variant_vs_current": gates_vs_current,
            "rotation_surface_delta_meta": rotation_meta,
        },
        "expected_value_score_delta": {
            "best_variant_vs_current": {
                label: best_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "best_variant_vs_full_bundle": {
                label: gates_vs_full[best_variant]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "best_variant": best_variant,
        "event_selection": variant_events,
        "coverage": {
            "source_coverage": source_coverage,
            "state_score_feature": _coverage(event_trades),
            "surface_scalar": _eligible_summary(event_trades),
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
                "LLM soft-ranking outcome joins remain sparse; this deterministic alpha "
                "test does not weaken or expand LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "risk_of_change": (
            "A higher event scalar may overfit four historical surface hits and would "
            "increase exposure to a small ticker set before forward paper evidence exists."
        ),
        "next_action": (
            "Keep current default-off event state add-on; collect forward outcomes for "
            "rotation_breakout_leadership before retrying higher surface scalars."
        ),
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
    current = "current_non_generic_positive_2x"
    lines = [
        "# exp-20260508-021 Event Rotation Surface Add-On",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant Vs Current Event Add-On",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    gate = payload["delta_metrics"]["variant_vs_current"][best]
    for label in WINDOWS:
        before = payload["before_metrics"][current][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary Vs Current",
            "",
            "| Variant | EV Delta | PnL Delta | Windows EV +/- | Gate | Touched | Single ticker share |",
            "|---|---:|---:|---:|---|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_current"].items():
        if name == current:
            continue
        delta = row["delta"]
        meta = payload["delta_metrics"]["rotation_surface_delta_meta"][name]
        lines.append(
            "| {name} | {ev:+.4f} | ${pnl:+,.2f} | {wi}/{wr} | {gate} | {touched} | {share} |".format(
                name=name,
                ev=delta["aggregate_ev_delta"],
                pnl=delta["aggregate_pnl_delta"],
                wi=delta["windows_ev_improved"],
                wr=delta["windows_ev_regressed"],
                gate=row["passed"],
                touched=meta["touched_rotation_surface_trades"],
                share=meta["max_single_ticker_positive_share"],
            )
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["coverage"]["surface_scalar"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.",
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
            "title": "Event rotation surface add-on",
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
                    "best_variant_vs_current": payload["delta_metrics"]["variant_vs_current"][best]["delta"],
                    "rotation_meta": payload["delta_metrics"]["rotation_surface_delta_meta"][best],
                    "coverage": payload["coverage"]["surface_scalar"],
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
