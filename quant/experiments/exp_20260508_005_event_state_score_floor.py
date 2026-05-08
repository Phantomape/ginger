"""exp-20260508-005 event/state-surface score-floor replay.

Alpha search. exp-20260507-026 found that adding notional to event trades with
positive point-in-time state score on named non-generic state surfaces was the
strongest current event-sleeve lead. This follow-up changes one causal
variable: the minimum positive state score required for that add-on. The scalar
is fixed at 2.0x, and the frozen event bundle, core strategy, exits, LLM/news,
candidate pool, and production orders are unchanged.
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


EXP_ID = "exp-20260508-005"
STEM = "event_state_score_floor"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

GENERIC_SURFACE = "balanced_state_leadership"
CURRENT_VARIANT = "current_non_generic_score_gt_0_2x"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Frozen event bundle; 1.0x notional for every event trade.",
                "eligible_scalar": 1.0,
                "score_floor_exclusive": None,
            },
        ),
        (
            CURRENT_VARIANT,
            {
                "description": "Current default-off paper add-on: 2.0x when state_score > 0 on a non-generic state surface.",
                "eligible_scalar": 2.0,
                "score_floor_exclusive": 0.0,
            },
        ),
        (
            "non_generic_score_gt_025_2x",
            {
                "description": "2.0x only when state_score > 0.25 on a non-generic state surface.",
                "eligible_scalar": 2.0,
                "score_floor_exclusive": 0.25,
            },
        ),
        (
            "non_generic_score_gt_050_2x",
            {
                "description": "2.0x only when state_score > 0.50 on a non-generic state surface.",
                "eligible_scalar": 2.0,
                "score_floor_exclusive": 0.50,
            },
        ),
        (
            "non_generic_score_gt_075_2x",
            {
                "description": "2.0x only when state_score > 0.75 on a non-generic state surface.",
                "eligible_scalar": 2.0,
                "score_floor_exclusive": 0.75,
            },
        ),
        (
            "non_generic_score_gt_100_2x",
            {
                "description": "2.0x only when state_score > 1.00 on a non-generic state surface.",
                "eligible_scalar": 2.0,
                "score_floor_exclusive": 1.00,
            },
        ),
    ]
)


def _score(trade: dict[str, Any]) -> float | None:
    try:
        value = float(trade.get("state_score"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _eligible_for_floor(trade: dict[str, Any], floor: float | None) -> bool:
    if floor is None:
        return False
    score = _score(trade)
    return (
        bool(trade.get("state_feature_available"))
        and score is not None
        and score > floor
        and str(trade.get("state_surface") or "") != GENERIC_SURFACE
    )


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any]:
    floor = variant["score_floor_exclusive"]
    eligible = _eligible_for_floor(trade, floor)
    scalar = float(variant["eligible_scalar"]) if eligible else 1.0
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_surface_addon_eligible": eligible,
        "state_score_floor_exclusive": floor,
        "state_score_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _threshold_variants() -> list[str]:
    return [name for name in VARIANTS if name not in {"full_bundle", CURRENT_VARIANT}]


def _best_threshold_variant(
    full_gates: dict[str, dict[str, Any]],
    current_gates: dict[str, dict[str, Any]],
) -> str:
    candidates = [
        name
        for name in _threshold_variants()
        if full_gates[name]["passed"] and current_gates[name]["passed"]
    ]
    if not candidates:
        candidates = _threshold_variants()
    return max(
        candidates,
        key=lambda name: (
            current_gates[name]["delta"]["after_ev_sum"],
            current_gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def _eligible_summary(
    enriched: dict[str, list[dict[str, Any]]],
    floor: float | None,
) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    eligible = [trade for trade in rows if _eligible_for_floor(trade, floor)]
    by_surface: dict[str, dict[str, Any]] = {}
    by_window: dict[str, dict[str, Any]] = {}

    for trade in eligible:
        surface = str(trade.get("state_surface") or "")
        row = by_surface.setdefault(surface, {"trade_count": 0, "total_pnl": 0.0, "scores": []})
        row["trade_count"] += 1
        row["total_pnl"] += float(trade.get("pnl") or 0.0)
        score = _score(trade)
        if score is not None:
            row["scores"].append(score)

    for label, trades in enriched.items():
        win_eligible = [trade for trade in trades if _eligible_for_floor(trade, floor)]
        by_window[label] = {
            "eligible_trade_count": len(win_eligible),
            "eligible_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in win_eligible), 2),
            "eligible_tickers": sorted({str(row.get("ticker") or "") for row in win_eligible}),
        }

    for row in by_surface.values():
        scores = row.pop("scores")
        row["total_pnl"] = round(float(row["total_pnl"]), 2)
        row["min_score"] = round(min(scores), 6) if scores else None
        row["max_score"] = round(max(scores), 6) if scores else None

    return {
        "event_trade_count": len(rows),
        "eligible_trade_count": len(eligible),
        "eligible_fraction": round(len(eligible) / len(rows), 4) if rows else None,
        "eligible_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in eligible), 2),
        "score_floor_exclusive": floor,
        "generic_surface_not_eligible": GENERIC_SURFACE,
        "eligible_surfaces": sorted(by_surface),
        "by_surface": by_surface,
        "by_window": by_window,
        "rule": f"state_feature_available and state_score > {floor} and state_surface != {GENERIC_SURFACE}",
    }


def _gate_delta_by_window(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        label: gate["delta"]["by_window"][label]["expected_value_score"]
        for label in WINDOWS
    }


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
    current_metrics = variant_metrics[CURRENT_VARIANT]
    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    full_gates = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    current_gates = OrderedDict(
        (name, _gate_summary(current_metrics, variant_metrics[name]))
        for name in _threshold_variants()
    )

    best_variant = _best_threshold_variant(full_gates, current_gates)
    best_vs_current = current_gates[best_variant]
    best_vs_full = full_gates[best_variant]
    accepted = bool(best_vs_current["passed"] and best_vs_full["passed"])
    decision = "accepted_default_off_paper_score_floor" if accepted else "rejected"

    if accepted:
        rationale = (
            f"Accepted for default-off paper promotion: {best_variant} beat both the "
            "full frozen event bundle and the current score>0 add-on over the three "
            "canonical windows with no EV regression and a Gate 4 materiality trigger. "
            "No live order sizing should change until forward paper replacement value closes."
        )
        rejection_reason = None
        next_action = (
            "Promote the selected score floor only inside the shared default-off event "
            "paper adapter and add parity coverage; keep live trading unchanged."
        )
    else:
        rationale = (
            f"Rejected: {best_variant} was the best stricter floor but failed to beat "
            "the current score>0 add-on with stable three-window EV improvement and "
            "materiality. The current non-generic positive-score paper rule remains the better lead."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the current score>0 non-generic paper add-on; do not retry nearby "
            "state-score floors without new forward event outcomes."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_state_surface_score_floor_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "The event/state-surface add-on may improve if only stronger positive "
            "state-score rows receive the 2.0x satellite notional, avoiding weak "
            "positive-score event rows while preserving the non-generic surface edge."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "The non-generic positive state-surface add-on is the strongest recent "
                "alpha lead, while LLM soft-ranking, earnings/C, estimate revisions, "
                "SEC filing-shock, Commodity scalar, gap-up, and pre-earnings variants "
                "are data-limited or recently rejected."
            ),
        },
        "single_causal_variable": (
            "Minimum exclusive PIT state_score required for the non-generic 2.0x "
            "event/state-surface add-on"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": CURRENT_VARIANT,
            "secondary_baseline": "full_bundle",
            "generic_surface_not_eligible": GENERIC_SURFACE,
            "base_event_notional_usd": EVENT_NOTIONAL,
            "fixed_eligible_scalar": 2.0,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "event sources",
                "event thresholds",
                "event hold days",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "direct_parent": {
                "exp-20260507-026": (
                    "Non-generic positive state-surface add-on was promising and "
                    "production-visible as default-off paper at score > 0."
                )
            },
            "nearby_rejected": {
                "exp-20260507-025": "Broad positive-vs-nonpositive state-score tilt rejected.",
                "exp-20260508-003": "Commodity near-high 2.0x rejected as immaterial.",
                "exp-20260508-001": "Pre-earnings 22-45 risk reduction rejected.",
                "exp-20260507-908": "Gap-up entry-state risk scalars rejected.",
                "exp-20260507-907": "Platform RS20 leader risk positive but concentrated/rejected.",
            },
            "why_not_simple_repeat": (
                "This is not another scalar sweep, source prune, source combination, "
                "or broad state-score tilt. The scalar is fixed at 2.0x and only the "
                "minimum event-quality score floor changes."
            ),
            "mechanism_insight_conflict": (
                "No conflict: avoids LLM/earnings data-limited branches, avoids "
                "Commodity scalar retesting, and does not expand ticker noise."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_event_bundle": full_metrics,
            "current_score_gt_0_addon": current_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_full_bundle": full_gates,
            "variant_vs_current_score_gt_0": current_gates,
        },
        "expected_value_score_delta": {
            "best_variant_vs_current_score_gt_0": _gate_delta_by_window(best_vs_current),
            "best_variant_vs_full_bundle": _gate_delta_by_window(best_vs_full),
            "best_variant_vs_core": _gate_delta_by_window(core_gates[best_variant]),
        },
        "best_variant": best_variant,
        "event_selection": variant_events,
        "coverage": {
            "source_coverage": source_coverage,
            "state_score_feature": _coverage(event_trades),
            "score_floor_variants": OrderedDict(
                (name, _eligible_summary(event_trades, variant["score_floor_exclusive"]))
                for name, variant in VARIANTS.items()
                if name != "full_bundle"
            ),
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
                "Only a shared default-off event paper adapter may be updated; live "
                "orders still need forward replacement-value evidence."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking remains data-limited; this deterministic allocation "
                "test neither weakens nor expands LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "LLM soft-ranking, C/earnings, estimate revisions, SEC filing shock, "
            "Commodity near-high, gap-up, RS20 platform leader, and pre-earnings "
            "risk experiments are blocked or recently rejected."
        ),
        "risk_of_change": (
            "A stricter floor can miss profitable weak-positive event rows; even if "
            "positive, this remains sparse same-sample event evidence until forward "
            "paper outcomes accumulate."
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
    best = payload["best_variant"]
    current_gate = payload["delta_metrics"]["variant_vs_current_score_gt_0"][best]
    full_gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    lines = [
        "# exp-20260508-005 Event State Score Floor",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search. Tests whether the current non-generic positive state-surface event add-on should require a higher PIT state-score floor.",
        "",
        "## Best Variant Vs Current Score>0 Rule",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL | Eligible trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"]["current_score_gt_0_addon"][label]
        after = payload["after_metrics"][best][label]
        delta = current_gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]
        eligible = payload["coverage"]["score_floor_variants"][best]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {eligible_trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                eligible_trades=eligible["eligible_trade_count"],
                epnl=selected["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary Vs Current",
            "",
            "| Variant | EV Sum Delta | PnL Delta | Windows EV Improved | Windows EV Regressed | Passed |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_current_score_gt_0"].items():
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
            "## Best Variant Vs Full Bundle",
            "",
            "```json",
            json.dumps(full_gate["delta"], indent=2, sort_keys=True),
            "```",
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["coverage"]["score_floor_variants"][best], indent=2, sort_keys=True),
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
            "title": "Event state score floor",
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
        "coverage": payload["coverage"]["score_floor_variants"][payload["best_variant"]],
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
                    "best_variant_vs_current_score_gt_0": payload["delta_metrics"][
                        "variant_vs_current_score_gt_0"
                    ][best]["delta"],
                    "best_variant_vs_full_bundle": payload["delta_metrics"][
                        "variant_vs_full_bundle"
                    ][best]["delta"],
                    "coverage": payload["coverage"]["score_floor_variants"][best],
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
