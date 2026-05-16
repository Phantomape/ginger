"""exp-20260516-030: event rotation negative-reaction source tilt.

Alpha search, replay-only. The accepted/default-off event rotation surface was
revalidated at 3.0x paper notional in exp-20260516-028. This experiment keeps
that rotation surface, the event pool, holding period, core stack, LLM/news,
and production orders fixed. It changes one variable only: whether rotation
rows sourced from `sec_negative_reaction` deserve a higher bounded paper
notional than the other rotation-breakout leadership rows.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260516_028_event_rotation_surface_tilt_after_exp020 as exp028


EXPERIMENT_ID = "exp-20260516-030"
EXPERIMENT_SLUG = "event_rotation_negative_source_tilt"
BASELINE_EXPERIMENT_ID = "exp-20260516-028"

REPO_ROOT = exp028.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "current_rotation_surface_300"
TARGET_SOURCE = "sec_negative_reaction"
TARGET_SURFACE = "rotation_breakout_leadership"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": (
                    "Accepted exp028 paper lead: 3.0x for all eligible "
                    "rotation-breakout leadership rows; 2.0x for other "
                    "positive non-generic state surfaces."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_source_scalar": 3.0,
                "rotation_negative_reaction_scalar": 3.0,
            },
        ),
        (
            "negative_reaction_source_325",
            {
                "description": (
                    "3.25x only for sec_negative_reaction rotation rows; "
                    "other eligible rotation rows stay at 3.0x."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_source_scalar": 3.0,
                "rotation_negative_reaction_scalar": 3.25,
            },
        ),
        (
            "negative_reaction_source_350",
            {
                "description": (
                    "3.5x only for sec_negative_reaction rotation rows; "
                    "other eligible rotation rows stay at 3.0x."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_source_scalar": 3.0,
                "rotation_negative_reaction_scalar": 3.5,
            },
        ),
        (
            "negative_reaction_source_400",
            {
                "description": (
                    "4.0x only for sec_negative_reaction rotation rows; "
                    "included to test concentration guard failure."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_source_scalar": 3.0,
                "rotation_negative_reaction_scalar": 4.0,
            },
        ),
    ]
)


def _configure_modules() -> None:
    exp028._configure_modules()


def _parent():
    return exp028.base.prior.parent


def _safe(value: Any) -> Any:
    return _parent()._safe(value)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _parent()._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    _parent()._write_text(path, text)


def _is_target_source_rotation(trade: dict[str, Any]) -> bool:
    parent = _parent()
    return (
        parent._eligible_non_generic_positive(trade)
        and str(trade.get("state_surface") or "") == TARGET_SURFACE
        and str(trade.get("source") or "") == TARGET_SOURCE
    )


def _surface_scalar(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    parent = _parent()
    if not parent._eligible_non_generic_positive(trade):
        return float(variant["default_scalar"])
    if str(trade.get("state_surface") or "") != TARGET_SURFACE:
        return float(variant["eligible_non_rotation_scalar"])
    if str(trade.get("source") or "") == TARGET_SOURCE:
        return float(variant["rotation_negative_reaction_scalar"])
    return float(variant["rotation_other_source_scalar"])


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    scalar = _surface_scalar(trade, variant)
    base_notional = float(trade.get("notional") or _parent().base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "state_surface_scalar": round(scalar, 4),
        "source_tilt_target": _is_target_source_rotation(trade),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _selection_summary(
    raw_by_window: dict[str, list[dict[str, Any]]],
    scaled_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    parent = _parent()
    raw_rows = [trade for trades in raw_by_window.values() for trade in trades]
    scaled_rows = [trade for trades in scaled_by_window.values() for trade in trades]
    target_raw = [trade for trade in raw_rows if _is_target_source_rotation(trade)]
    target_scaled = [trade for trade in scaled_rows if trade.get("source_tilt_target")]
    rotation_scaled = [
        trade
        for trade in scaled_rows
        if parent._eligible_non_generic_positive(trade)
        and str(trade.get("state_surface") or "") == TARGET_SURFACE
    ]

    by_window: dict[str, Any] = OrderedDict()
    for label, rows in raw_by_window.items():
        target = [trade for trade in rows if _is_target_source_rotation(trade)]
        by_window[label] = {
            "trade_count": len(target),
            "wins": sum(1 for trade in target if float(trade.get("pnl") or 0.0) > 0),
            "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in target), 2),
            "tickers": sorted({str(trade.get("ticker") or "") for trade in target}),
        }

    positive_rotation_pnl = [
        float(trade.get("pnl") or 0.0)
        for trade in rotation_scaled
        if float(trade.get("pnl") or 0.0) > 0
    ]
    max_single_rotation_positive_share = None
    if positive_rotation_pnl and sum(positive_rotation_pnl) > 0:
        max_single_rotation_positive_share = (
            max(positive_rotation_pnl) / sum(positive_rotation_pnl)
        )

    return {
        "target_source": TARGET_SOURCE,
        "target_surface": TARGET_SURFACE,
        "target_trade_count": len(target_raw),
        "target_windows_present": sum(1 for row in by_window.values() if row["trade_count"] > 0),
        "target_tickers": sorted({str(trade.get("ticker") or "") for trade in target_raw}),
        "target_wins": sum(1 for trade in target_raw if float(trade.get("pnl") or 0.0) > 0),
        "target_win_rate": _round(
            sum(1 for trade in target_raw if float(trade.get("pnl") or 0.0) > 0)
            / len(target_raw),
            4,
        )
        if target_raw
        else None,
        "target_unscaled_total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in target_raw),
            2,
        ),
        "target_scaled_total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in target_scaled),
            2,
        ),
        "target_by_window": by_window,
        "rotation_surface_scaled_total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in rotation_scaled),
            2,
        ),
        "max_single_rotation_positive_pnl_share": _round(
            max_single_rotation_positive_share,
            4,
        ),
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 3
        and (selection.get("target_windows_present") or 0) >= 2
        and len(selection.get("target_tickers") or []) >= 2
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
            "min_target_source_trades": 3,
            "min_target_windows": 2,
            "min_target_tickers": 2,
            "max_single_rotation_positive_pnl_share": 0.55,
            "actual_target_source_trades": selection.get("target_trade_count"),
            "actual_target_windows": selection.get("target_windows_present"),
            "actual_target_tickers": selection.get("target_tickers"),
            "actual_max_single_rotation_positive_pnl_share": selection.get(
                "max_single_rotation_positive_pnl_share"
            ),
        },
    }


def _choose_best(
    gates: dict[str, dict[str, Any]],
    variant_metrics: dict[str, dict[str, dict[str, Any]]],
) -> str:
    names = [name for name in VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
            variant_metrics[name]["late_strong"]["expected_value_score"],
        ),
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in parent.base.WINDOWS.items():
        result = parent.base._load_core_result(window)
        core_metrics[label] = parent.base._core_metrics(result)
        for name, variant in VARIANTS.items():
            scaled = [_scaled_trade(trade, name, variant) for trade in event_trades[label]]
            curve = parent.base._event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = parent.base._combined_metrics(
                result,
                curve,
                scaled,
            )
            variant_events[name][label] = scaled

    baseline_metrics = variant_metrics[BASELINE_VARIANT]
    selection_by_variant = OrderedDict(
        (
            name,
            _selection_summary(event_trades, variant_events[name]),
        )
        for name in VARIANTS
    )
    gates_vs_baseline = OrderedDict(
        (
            name,
            _gate_vs_baseline(
                baseline_metrics,
                variant_metrics[name],
                selection_by_variant[name],
            ),
        )
        for name in VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline, variant_metrics)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "promising_replay_only_negative_reaction_rotation_source_tilt"
        if accepted
        else "rejected_negative_reaction_rotation_source_tilt"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` did not clear the baseline gate: "
            f"EV delta {best_gate['delta']['aggregate_ev_delta']}, "
            f"PnL delta {best_gate['delta']['aggregate_pnl_delta']}, "
            f"EV improved/regressed {best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_source_quality_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "changed_variable": "sec_negative_reaction_rotation_source_paper_notional_tilt",
        "hypothesis": (
            "Within the default-off event rotation sleeve, rotation-breakout "
            "leadership rows sourced from SEC negative-reaction absorption may "
            "carry stronger replacement quality than governance/procedural "
            "rotation rows and deserve a bounded extra paper-notional tilt."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-source-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "The playbook points away from nearby core scalar retunes and "
                "toward replayable event fields. exp-20260516-028 showed "
                "rotation_breakout_leadership remains the strongest deterministic "
                "default-off event allocation surface after exp020; its source "
                "split is the next production-visible discriminator."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for eligible rotation_breakout_leadership "
            "events whose source is sec_negative_reaction"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment": BASELINE_EXPERIMENT_ID,
            "target_source": TARGET_SOURCE,
            "target_surface": TARGET_SURFACE,
            "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
            "hold_days": parent.base.HOLD_DAYS,
            "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
            "sample_guard": {
                "min_target_source_trades": 3,
                "min_target_windows": 2,
                "min_target_tickers": 2,
                "max_single_rotation_positive_pnl_share": 0.55,
            },
            "anti_js": "No JavaScript was used.",
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
                "other event source scalars",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "default-off event source-quality allocation: "
                "sec_negative_reaction rotation rows may deserve more paper "
                "notional than other rotation rows."
            ),
            "2_history_check": (
                "exp-20260516-028 revalidated the all-source 3.0x rotation "
                "surface after exp020; it reported sec_negative_reaction "
                "rotation at 3/3 wins and $7,122.74 unscaled PnL versus "
                "governance/procedural at 3/4 wins and $1,329.21. No prior run "
                "isolated source-specific tilt inside the exp028 rotation lead."
            ),
            "3_single_causal_variable": (
                "Only the sec_negative_reaction rotation source scalar changes; "
                "all other rotation rows stay at 3.0x and other positive "
                "non-generic event surfaces stay at 2.0x."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "exp028 3.0x rotation lead, require aggregate EV/PnL "
                "improvement, at least two EV-improved windows, no EV-regressed "
                "windows, materiality by the existing event gate, and source "
                "sample/concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_030_event_rotation_negative_source_tilt.py"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": parent.base.WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_metrics": baseline_metrics,
        },
        "gate2": {
            "required_fields": [
                "event trade source",
                "event trade state_surface",
                "state_feature_available",
                "state_score_positive",
                "event entry_date",
                "event exit_date",
                "event pnl",
            ],
            "target_source_trade_count": selection_by_variant[BASELINE_VARIANT][
                "target_trade_count"
            ],
            "target_windows_present": selection_by_variant[BASELINE_VARIANT][
                "target_windows_present"
            ],
            "target_tickers": selection_by_variant[BASELINE_VARIANT]["target_tickers"],
            "passed": selection_by_variant[BASELINE_VARIANT]["target_trade_count"] >= 3,
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "survival_impact": "not applicable to default-off event paper overlay; core signals unchanged",
            "passed": True,
        },
        "gate4": {
            **best_gate,
            "basis": (
                "Three canonical windows, primary comparison against the exp028 "
                "current_rotation_surface_300 event paper lead."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            BASELINE_VARIANT: baseline_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_current_rotation_300": gates_vs_baseline,
        },
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "selection": selection_by_variant,
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
                "Before live/default capital, implement a shared trade-enabled "
                "event adapter used by run.py and backtester.py, add parity tests, "
                "and collect closed forward replacement-value evidence."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited, so this "
                "uses deterministic PIT event source and state-surface fields."
            ),
        },
        "decision_rationale": (
            "Accepted as replay-only event source-quality allocation lead; no "
            "live/default orders change until a shared adapter and forward "
            "replacement outcomes exist."
            if accepted
            else rejection_reason
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Keep as default-off replay evidence only; next valid promotion step "
            "is a shared event adapter plus forward replacement-value evidence."
            if accepted
            else "Do not retry nearby negative-reaction source scalars without new forward event evidence."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM/SEC soft-ranking because fields and attribution remain "
            "insufficient; skipped Space nearby peer-state retunes after zero "
            "incremental EV; skipped core ATR/RS/price-extension/DTE/cap retunes "
            "because recent logs mark them rejected, exhausted, or no-op."
        ),
        "risk_of_change": (
            "The target source has only three historical paper trades, so this "
            "is not a live-capital promotion. The concentration guard checks "
            "that the broader rotation sleeve is not dominated by one winner."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_rotation_300"][best]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Rotation Negative-Reaction Source Tilt",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests one source-quality allocation variable inside the exp028 default-off event rotation paper lead.",
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | Variant EV | Delta EV | Baseline PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _parent().base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=baseline[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=baseline[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )

    sweep_rows = [
        "| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max winner share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["delta_metrics"]["variant_vs_current_rotation_300"].items():
        selection = payload["selection"][name]
        sweep_rows.append(
            "| {name} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                dev=row["delta"]["aggregate_ev_delta"],
                dpnl=row["delta"]["aggregate_pnl_delta"],
                improved=row["delta"]["windows_ev_improved"],
                regressed=row["delta"]["windows_ev_regressed"],
                trades=selection["target_trade_count"],
                windows=selection["target_windows_present"],
                share=selection["max_single_rotation_positive_pnl_share"],
            )
        )

    lines.extend(
        [
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"][best], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay only. Production and default backtest order paths are unchanged. A live/default version requires a shared trade-enabled event adapter, run/backtester parity tests, and closed forward replacement-value evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "gate_questions": payload["gate_questions"],
        "backtest_protocol": payload["backtest_protocol"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": {payload["best_variant"]: payload["after_metrics"][payload["best_variant"]]},
        "delta_metrics": payload["delta_metrics"],
        "best_variant": payload["best_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "selection": payload["selection"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
        "related_files": payload["related_files"],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    _write_json(LOG_JSON, compact)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation negative-reaction source tilt",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_rotation_300"][best]
    print(
        json.dumps(
            _safe(
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
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
