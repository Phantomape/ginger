"""exp-20260510-005 rotation tilt plus benchmark-gated state surface stack.

Alpha search, replay-only. The current event-bundle paper lead is the
rotation_breakout_leadership tilt accepted as a default-off adapter in
exp-20260510-003. This experiment changes one causal variable on top of that
baseline: add the already-frozen benchmark-momentum-gated state-surface
satellite sleeve.

No live orders, default core backtest behavior, event source definitions,
state-surface scoring, LLM/news, sizing, exits, or production trade adapters
are changed.
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

from experiments import exp_20260509_014_state_surface_benchmark_momentum_gate as gate_base  # noqa: E402
from experiments import exp_20260510_001_event_rotation_surface_tilt as rotation_base  # noqa: E402


EXPERIMENT_ID = "exp-20260510-005"
STEM = "rotation_tilt_plus_benchmark_state_surface_stack"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

EVENT_VARIANT = "rotation_surface_add_300"
STATE_SURFACE_GATE = "benchmark_momentum_gate_v1"


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


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _material(delta: dict[str, Any]) -> bool:
    return (
        (delta.get("aggregate_ev_delta_pct") or 0.0) > 0.10
        or (delta.get("aggregate_pnl_delta_pct") or 0.0) > 0.05
    )


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event_base = rotation_base.base
    surface_base = gate_base.surface_base

    raw_event_trades, source_coverage, prices = event_base._load_event_trades()
    enriched_event_trades = event_base._enrich_event_trades(raw_event_trades)
    event_variant = rotation_base.VARIANTS[EVENT_VARIANT]

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    rotation_event_metrics: dict[str, dict[str, Any]] = OrderedDict()
    rotation_full_surface_metrics: dict[str, dict[str, Any]] = OrderedDict()
    rotation_gated_surface_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_gated_surface_trades: list[dict[str, Any]] = []

    for label, window in event_base.WINDOWS.items():
        result = event_base._load_core_result(window)
        core_metrics[label] = event_base._core_metrics(result)
        event_trades = [
            rotation_base._scaled_trade(trade, EVENT_VARIANT, event_variant)
            for trade in enriched_event_trades[label]
        ]
        event_curve = event_base._event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        rotation_event_metrics[label] = event_base._combined_metrics(
            result,
            event_curve,
            event_trades,
        )

        candidates = surface_base._raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        full_selected, full_skipped = surface_base._select_trades(candidates)
        full_stack_trades = event_trades + full_selected
        full_stack_curve = event_base._event_equity_curve(
            full_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        rotation_full_surface_metrics[label] = event_base._combined_metrics(
            result,
            full_stack_curve,
            full_stack_trades,
        )

        gated_candidates, gate_skipped = gate_base._filter_benchmark_momentum(
            candidates,
            result=result,
            prices=prices,
        )
        gated_selected, gated_select_skipped = surface_base._select_trades(gated_candidates)
        gated_stack_trades = event_trades + gated_selected
        gated_stack_curve = event_base._event_equity_curve(
            gated_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        rotation_gated_surface_metrics[label] = event_base._combined_metrics(
            result,
            gated_stack_curve,
            gated_stack_trades,
        )
        all_gated_surface_trades.extend({**trade, "window": label} for trade in gated_selected)

        surface_sleeve[label] = gate_base._surface_sleeve_summary(
            candidates=candidates,
            full_selected=full_selected,
            gated_selected=gated_selected,
            gate_skipped=gate_skipped,
            full_skipped=full_skipped,
            gated_select_skipped=gated_select_skipped,
        )

    vs_core = gate_base._aggregate_delta(core_metrics, rotation_gated_surface_metrics)
    vs_rotation_event = gate_base._aggregate_delta(
        rotation_event_metrics,
        rotation_gated_surface_metrics,
    )
    vs_rotation_full_surface = gate_base._aggregate_delta(
        rotation_full_surface_metrics,
        rotation_gated_surface_metrics,
    )
    concentration = gate_base._single_ticker_positive_share(all_gated_surface_trades)
    concentration_ok = concentration is None or concentration <= 0.50
    drawdown_cap_ok = all(
        float(rotation_gated_surface_metrics[label].get("max_drawdown_pct") or 0.0) <= 0.20
        for label in event_base.WINDOWS
    )
    passed_vs_rotation = (
        vs_rotation_event["windows_ev_improved"] == 3
        and vs_rotation_event["windows_ev_regressed"] == 0
        and _material(vs_rotation_event)
    )
    aggregate_vs_ungated_positive = (
        vs_rotation_full_surface["aggregate_ev_delta"] > 0.0
        and vs_rotation_full_surface["aggregate_pnl_delta"] > 0.0
    )
    passed = bool(
        passed_vs_rotation
        and drawdown_cap_ok
        and concentration_ok
        and vs_core["windows_ev_improved"] == 3
    )

    if passed:
        decision = "promising_replay_only_rotation_plus_benchmark_state_surface_stack"
        decision_rationale = (
            "Promising replay-only: adding the frozen benchmark-gated state-surface "
            "sleeve on top of the current rotation-tilted event bundle improved EV "
            "in all three canonical windows versus the rotation-event baseline and "
            "cleared materiality without breaching drawdown or concentration guards. "
            "It remains default-off/paper because live routing still requires closed "
            "forward replacement-value outcomes and explicit shared trade adapters."
        )
        rejection_reason = None
        next_action = (
            "Keep event rotation tilt plus benchmark-gated state surface as the "
            "strongest current paper stack; collect forward closed outcomes under "
            "the existing default-off adapters before enabling any live/default orders."
        )
    else:
        decision = "rejected"
        decision_rationale = (
            "Rejected: adding the benchmark-gated state-surface sleeve to the "
            "rotation-tilted event baseline did not clear the three-window EV, "
            "materiality, drawdown, and concentration guards."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Do not repeat this stack revalidation without new forward paper outcomes "
            "or a genuinely orthogonal event/state discriminator."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "event_rotation_plus_state_surface_candidate_pool_allocation",
        "hypothesis": (
            "The current rotation-tilted event bundle and the benchmark-gated "
            "state-surface satellite should be additive because the event sleeve "
            "captures event-specific state quality while the state-surface sleeve "
            "adds separate candidate-pool replacement value only in positive "
            "SPY/QQQ tape."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation_candidate_pool_extension",
            "why_this_now": (
                "exp-20260510-003 changed the current event-bundle paper baseline "
                "by accepting the rotation-surface tilt adapter. exp-20260509-014 "
                "tested the benchmark-gated state-surface sleeve only on the prior "
                "event-state baseline, so the current paper stack needs a clean "
                "three-window revalidation before priority decisions."
            ),
        },
        "change_type": "replay_only_paper_stack_revalidation",
        "single_causal_variable": (
            "Include the frozen benchmark-momentum-gated state-surface sleeve on top "
            "of the current rotation-tilted event-bundle paper baseline."
        ),
        "parameters": {
            "event_variant": EVENT_VARIANT,
            "event_rotation_surface": rotation_base.ROTATION_SURFACE,
            "event_rotation_scalar": rotation_base.VARIANTS[EVENT_VARIANT][
                "rotation_surface_scalar"
            ],
            "event_non_rotation_eligible_scalar": rotation_base.VARIANTS[EVENT_VARIANT][
                "eligible_non_rotation_scalar"
            ],
            "state_surface_gate": STATE_SURFACE_GATE,
            "state_surface_gate_rule": (
                "core_warmup_ready and max(SPY_20d_return, QQQ_20d_return) > 0"
            ),
            "locked_variables": [
                "core A/B signal generation",
                "event source definitions",
                "event hold days",
                "event base notional",
                "state-surface scoring",
                "state-surface top-N",
                "state-surface hold days",
                "state-surface notional",
                "LLM/news replay",
                "sizing",
                "exits",
                "production order routing",
            ],
        },
        "history_guardrails": {
            "similar_prior_experiments": {
                "exp-20260509-014": (
                    "Benchmark-gated state-surface sleeve was promising on the "
                    "pre-rotation event-state add-on baseline."
                ),
                "exp-20260510-001": (
                    "Rotation-surface event tilt improved the event paper lead and "
                    "changed the correct marginal baseline."
                ),
                "exp-20260510-003": (
                    "Rotation-surface tilt was moved into the shared default-off "
                    "production-visible adapter without live/default orders."
                ),
            },
            "why_not_repeat": (
                "This is not a top-N, hold-day, notional, source, score-floor, or "
                "benchmark-threshold retune. It uses the exact frozen adapters to "
                "re-evaluate the new current paper stack."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in event_base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in event_base.WINDOWS.items()
        },
        "before_metrics": {
            "core": core_metrics,
            "rotation_event_baseline": rotation_event_metrics,
            "rotation_plus_ungated_state_surface_context": rotation_full_surface_metrics,
        },
        "after_metrics": rotation_gated_surface_metrics,
        "delta_metrics": {
            "vs_core": vs_core,
            "vs_rotation_event_baseline": vs_rotation_event,
            "vs_rotation_plus_ungated_state_surface_context": vs_rotation_full_surface,
        },
        "expected_value_score_delta": {
            "vs_core": vs_core["aggregate_ev_delta"],
            "vs_rotation_event_baseline": vs_rotation_event["aggregate_ev_delta"],
            "vs_rotation_plus_ungated_state_surface_context": vs_rotation_full_surface[
                "aggregate_ev_delta"
            ],
        },
        "gate4": {
            "passed": passed,
            "passed_vs_rotation_event_baseline": passed_vs_rotation,
            "aggregate_vs_ungated_context_positive": aggregate_vs_ungated_positive,
            "drawdown_cap_ok": drawdown_cap_ok,
            "concentration_ok": concentration_ok,
            "single_ticker_positive_share": concentration,
            "rule": (
                "Primary read is versus the current rotation-event paper baseline: "
                "require 3/3 EV improvement, zero EV regression, material aggregate "
                "EV or PnL lift, max drawdown <= 20%, and single-ticker positive "
                "Pnl share <= 50%. Ungated state-surface stack is context, not the "
                "promotion baseline."
            ),
        },
        "coverage": {
            "event_source_coverage": source_coverage,
            "event_trade_count": sum(
                int(event_base._trade_summary(enriched_event_trades[label])["trade_count"])
                for label in event_base.WINDOWS
            ),
            "gated_state_surface_selected_trade_count": sum(
                int(surface_sleeve[label]["benchmark_momentum_selected_trade_count"])
                for label in event_base.WINDOWS
            ),
            "gated_state_surface_selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in all_gated_surface_trades),
                2,
            ),
        },
        "surface_sleeve": surface_sleeve,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking remains production-aligned sample limited; this "
                "test uses replayable event/state/OHLCV paper sleeves."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_orders": False,
            "parity_note": (
                "Both sleeves already have shared default-off production-visible "
                "paper adapters. This run does not enable live/default order routing."
            ),
            "promotion_requirement_if_positive": (
                "A trade-enabled version still needs closed forward paper outcomes, "
                "explicit shared run.py/backtester.py trade adapters, and parity tests."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": next_action,
        "risk_of_change": (
            "Paper stack results may overstate live capacity because event and "
            "state-surface sleeves are not yet trade-enabled and forward closed "
            "replacement-value evidence is still sparse."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking, options, short-pressure, Form 4 thresholding, "
            "PEAD retunes, breakout add-on caps, source pruning, and benchmark "
            "threshold sweeps because recent logs mark them data-limited, rejected, "
            "or already represented by the frozen current adapters."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260510-005 Rotation Tilt Plus Benchmark State Surface Stack",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Single variable: add the frozen benchmark-gated state-surface sleeve on top of the current rotation-tilted event-bundle paper baseline.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Core EV | Rotation Event EV | Rotation+Gated Surface EV | vs Rotation EV | vs Rotation PnL | vs Rotation Sharpe | vs Rotation DD | Gated Surface Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in rotation_base.base.WINDOWS:
        core = payload["before_metrics"]["core"][label]
        before = payload["before_metrics"]["rotation_event_baseline"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["vs_rotation_event_baseline"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {core_ev:.4f} | {before_ev:.4f} | {after_ev:.4f} | "
            "{delta_ev:+.4f} | ${delta_pnl:+,.2f} | {delta_sharpe:+.2f} | "
            "{delta_dd:+.2%} | {trades} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta["expected_value_score"],
                delta_pnl=delta["total_pnl"],
                delta_sharpe=delta["sharpe_daily"],
                delta_dd=delta["max_drawdown_pct"],
                trades=sleeve["benchmark_momentum_selected_trade_count"],
            )
        )
    vs_core = payload["delta_metrics"]["vs_core"]
    vs_rotation = payload["delta_metrics"]["vs_rotation_event_baseline"]
    vs_ungated = payload["delta_metrics"]["vs_rotation_plus_ungated_state_surface_context"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus core: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}).".format(
                vs_core["aggregate_ev_delta"],
                vs_core["aggregate_ev_delta_pct"] or 0.0,
                vs_core["aggregate_pnl_delta"],
                vs_core["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- Versus rotation-event baseline: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_rotation["aggregate_ev_delta"],
                vs_rotation["aggregate_ev_delta_pct"] or 0.0,
                vs_rotation["aggregate_pnl_delta"],
                vs_rotation["aggregate_pnl_delta_pct"] or 0.0,
                vs_rotation["windows_ev_improved"],
                vs_rotation["windows_ev_regressed"],
            ),
            "- Versus ungated rotation+state-surface context: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_ungated["aggregate_ev_delta"],
                vs_ungated["aggregate_ev_delta_pct"] or 0.0,
                vs_ungated["aggregate_pnl_delta"],
                vs_ungated["aggregate_pnl_delta_pct"] or 0.0,
                vs_ungated["windows_ev_improved"],
                vs_ungated["windows_ev_regressed"],
            ),
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. Both sleeves are already default-off paper adapters, and this experiment does not enable live/default orders. Any trade-enabled version still needs closed forward outcomes plus shared run/backtester trade adapters and parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Rotation tilt plus benchmark state surface stack",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    compact = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
    }
    _append_jsonl_dedup(EXPERIMENT_LOG, compact)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "vs_core": payload["delta_metrics"]["vs_core"],
                    "vs_rotation_event_baseline": payload["delta_metrics"][
                        "vs_rotation_event_baseline"
                    ],
                    "vs_rotation_plus_ungated_state_surface_context": payload[
                        "delta_metrics"
                    ]["vs_rotation_plus_ungated_state_surface_context"],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
