"""exp-20260507-012 event-bundle source-pruning replay.

Alpha search. The strongest current non-core alpha surface is the default-off
external event overlay bundle from exp-20260504-049. This experiment changes one
causal variable inside that surface: source composition. It asks whether pruning
one or more frozen event sources improves the replay-only event bundle versus
the full three-source bundle.

No thresholds, holding periods, notionals, core A/B entries, ranking, sizing,
exits, LLM prompts, news vetoes, production orders, or candidate universe
membership are changed.
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

from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _aggregate_delta,
    _combined_metrics,
    _core_metrics,
    _event_equity_curve,
    _gate4,
    _load_core_result,
    _load_event_trades,
    _source_summary,
)


EXP_ID = "exp-20260507-012"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "event_bundle_source_pruning.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_event_bundle_source_pruning.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

FULL_SOURCES = (
    "form4_meaningful_purchase",
    "sec_negative_reaction",
    "sec_governance_procedural",
)

SOURCE_VARIANTS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    [
        ("full_bundle", FULL_SOURCES),
        ("sec_negative_only", ("sec_negative_reaction",)),
        ("sec_governance_only", ("sec_governance_procedural",)),
        ("form4_only", ("form4_meaningful_purchase",)),
        (
            "sec_negative_plus_governance",
            ("sec_negative_reaction", "sec_governance_procedural"),
        ),
        (
            "sec_negative_plus_form4",
            ("sec_negative_reaction", "form4_meaningful_purchase"),
        ),
        (
            "governance_plus_form4",
            ("sec_governance_procedural", "form4_meaningful_purchase"),
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _metric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    )
    return {
        key: _round((after.get(key) or 0.0) - (before.get(key) or 0.0), 6)
        for key in keys
    }


def _aggregate_metric_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _metric_delta(before[label], after[label])) for label in WINDOWS)
    before_ev = sum(float(before[label].get("expected_value_score") or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label].get("expected_value_score") or 0.0) for label in WINDOWS)
    before_pnl = sum(float(before[label].get("total_pnl") or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label].get("total_pnl") or 0.0) for label in WINDOWS)
    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    return {
        "by_window": by_window,
        "before_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(ev_delta, 4),
        "aggregate_ev_delta_pct": round(ev_delta / before_ev, 6) if before_ev else None,
        "before_pnl_sum": round(before_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(pnl_delta, 2),
        "aggregate_pnl_delta_pct": round(pnl_delta / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0.0)
            > (before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0.0)
            < (before[label].get("expected_value_score") or 0.0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0.0)
            > (before[label].get("total_pnl") or 0.0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0.0)
            < (before[label].get("total_pnl") or 0.0)
        ),
    }


def _passes_materiality(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = _aggregate_metric_delta(before, after)
    gate4_by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    passes = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and (
            (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
            or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
            or any(row["passes_sharpe"] for row in gate4_by_window.values())
            or any(row["passes_drawdown"] for row in gate4_by_window.values())
        )
    )
    return {
        "delta": delta,
        "by_window": gate4_by_window,
        "passed": bool(passes),
        "rule": (
            "EV first across the three canonical backtesting.md windows; no EV "
            "regression, majority-window improvement, plus one Gate 4 materiality trigger."
        ),
    }


def _event_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "event_trade_count": len(trades),
        "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "source_summary": _source_summary(trades),
        "event_trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
            for trade in trades
        ],
    }


def _variant_metrics(
    result: dict[str, Any],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    if not event_trades:
        return _core_metrics(result)
    return _combined_metrics(result, event_curve, event_trades)


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-012 Event-Bundle Source Pruning",
        "",
        "Replay-only alpha search. This tests whether source pruning improves the already promising default-off event bundle.",
        "",
        "## Variant Summary",
        "",
        "| Variant | Sources | EV Sum | EV Delta vs Core | PnL Delta vs Core | Event Trades | Decision Note |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for name, row in payload["variant_summary"].items():
        lines.append(
            "| {name} | {sources} | {ev:.4f} | {dev:.4f} | ${dpnl:,.2f} | {trades} | {note} |".format(
                name=name,
                sources=", ".join(row["sources"]),
                ev=row["core_comparison"]["after_ev_sum"],
                dev=row["core_comparison"]["aggregate_ev_delta"],
                dpnl=row["core_comparison"]["aggregate_pnl_delta"],
                trades=row["event_trade_count_sum"],
                note=row["note"],
            )
        )
    lines.extend(
        [
            "",
            "## Full Bundle vs Best Pruned",
            "",
            "```json",
            json.dumps(payload["best_pruned_vs_full"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines))


def main() -> int:
    event_trades_by_window, coverage, prices = _load_event_trades()

    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in SOURCE_VARIANTS
    )
    variant_windows: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in SOURCE_VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        core_metrics[label] = _core_metrics(result)
        all_trades = event_trades_by_window[label]
        for name, sources in SOURCE_VARIANTS.items():
            allowed = set(sources)
            trades = [trade for trade in all_trades if str(trade.get("source") or "") in allowed]
            curve = _event_equity_curve(
                trades,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _variant_metrics(result, curve, trades)
            variant_windows[name][label] = _event_summary(trades)

    core_comparisons: dict[str, dict[str, Any]] = OrderedDict()
    variant_summary: dict[str, dict[str, Any]] = OrderedDict()
    for name, sources in SOURCE_VARIANTS.items():
        comparison = _aggregate_delta(core_metrics, variant_metrics[name])
        gate = _passes_materiality(core_metrics, variant_metrics[name])
        event_trade_count_sum = sum(
            int(variant_windows[name][label]["event_trade_count"]) for label in WINDOWS
        )
        core_comparisons[name] = {
            "gate4": gate,
            "delta": comparison,
        }
        variant_summary[name] = {
            "sources": list(sources),
            "event_trade_count_sum": event_trade_count_sum,
            "core_comparison": comparison,
            "note": "passes_core_gate" if gate["passed"] else "does_not_clear_core_gate",
        }

    pruned_names = [name for name in SOURCE_VARIANTS if name != "full_bundle"]
    best_pruned_name = max(
        pruned_names,
        key=lambda name: core_comparisons[name]["delta"]["after_ev_sum"],
    )
    full_metrics = variant_metrics["full_bundle"]
    best_pruned_metrics = variant_metrics[best_pruned_name]
    best_pruned_vs_full = _passes_materiality(full_metrics, best_pruned_metrics)
    best_pruned_vs_full["variant"] = best_pruned_name
    best_pruned_vs_full["sources"] = list(SOURCE_VARIANTS[best_pruned_name])

    pruned_beats_full = bool(best_pruned_vs_full["passed"])
    decision = "promising_replay_only_pruned_source_set" if pruned_beats_full else "rejected"
    if pruned_beats_full:
        decision_rationale = (
            f"Promising replay-only: {best_pruned_name} beat the full frozen event bundle "
            "under the same three-window Gate 4 rule. It still requires shared default-off "
            "paper/live adapter work before any capital impact."
        )
        rejection_reason = None
        next_action = (
            "Move the pruned source set into the default-off event paper bundle config, "
            "then collect forward closed outcomes before live promotion."
        )
    else:
        decision_rationale = (
            f"Rejected: the best pruned source set ({best_pruned_name}) did not beat the full "
            "three-source frozen event bundle across the canonical windows. Source pruning "
            "adds selection complexity without improving the current strongest event alpha surface."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Keep the full default-off event bundle as the stronger replay-only surface; "
            "future event work should add new forward evidence or a genuinely new event-quality field, not source pruning."
        )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_bundle_source_composition_replay",
        "mechanism_family": "external_event_satellite_overlay",
        "hypothesis": (
            "The full frozen event overlay bundle may contain weaker sparse sources; pruning "
            "to the best source subset could improve satellite expected value without adding "
            "new tickers or thresholds."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation/source quality",
            "why_this_now": (
                "Raw earnings/C re-enable was rejected, LLM soft-ranking remains sample-limited, "
                "and the event bundle is the strongest current replay-only alpha surface."
            ),
        },
        "single_causal_variable": "event overlay source composition",
        "parameters": {
            "source_variants": {name: list(sources) for name, sources in SOURCE_VARIANTS.items()},
            "baseline_for_pruning_decision": "full_bundle",
            "event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM prompt and replay",
                "news veto",
                "event queue thresholds",
                "event notional",
                "event holding period",
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
        "history_guardrails": {
            "similar_prior_results": {
                "exp-20260504-049": "Full three-source default-off event bundle was promising replay-only.",
                "exp-20260505-004": "Adding FD/Other as a fourth source was rejected; this test only prunes original frozen sources.",
                "exp-20260505-031": "One-day event follow-through delay was rejected; this leaves timing unchanged.",
                "exp-20260506-030": "Slot replacement replay was sparse; this avoids same-day slot substitution claims.",
                "exp-20260507-011": "Raw earnings/C re-enable was rejected after P-ERN coverage improved.",
            },
            "why_not_simple_repeat": (
                "This does not add a source, retune source thresholds, delay entries, change exits, "
                "or touch core slots. It tests whether the existing positive bundle should be narrower."
            ),
            "mechanism_insight_conflict": (
                "No conflict: avoids LLM sample-limited ranking, raw C sleeve, short-pressure, options, "
                "broad universe growth, protective exits, and breadth/dispersion retuning."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_bundle": full_metrics,
        },
        "after_metrics": {
            "variants": variant_metrics,
            "best_pruned": {
                "name": best_pruned_name,
                "metrics": best_pruned_metrics,
            },
        },
        "variant_event_overlay": variant_windows,
        "coverage": coverage,
        "variant_summary": variant_summary,
        "core_comparisons": core_comparisons,
        "best_pruned_vs_full": best_pruned_vs_full,
        "expected_value_score_delta": {
            "best_pruned_vs_full": {
                label: best_pruned_vs_full["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "full_bundle_vs_core": {
                label: core_comparisons["full_bundle"]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
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
            "alters_orders": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_positive": (
                "Accepted source pruning would still need a shared default-off event paper/live adapter "
                "and forward closed outcomes before any order impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_not_llm": (
                "LLM soft-ranking data is still sample-limited; this tests a deterministic event-source "
                "allocation hypothesis instead of changing LLM responsibility."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings raw enablement is newly rejected, LLM ranking lacks enough joined outcomes, "
            "broad universe expansion risks adding noisy tickers, and recent threshold/exit/risk surfaces are saturated by no-go evidence."
        ),
        "risk_of_change": (
            "A pruned event source set could overfit sparse historical event rows and miss profitable "
            "event families that help only in one market state."
        ),
        "next_action": next_action,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(AUDIT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "docs/experiment_log.jsonl",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Event-bundle source pruning",
            "status": decision,
            "decision": decision,
            "summary": decision_rationale,
            "created_at": timestamp,
            "related_log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        },
    )
    _write_report(payload)

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
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
        "best_pruned_vs_full": best_pruned_vs_full,
        "core_comparisons": core_comparisons,
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "related_files": payload["related_files"],
    }
    compact_line = json.dumps(_safe(compact), sort_keys=True)
    if EXPERIMENT_LOG.exists():
        existing = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        existing = [
            line
            for line in existing
            if f'"experiment_id": "{EXP_ID}"' not in line
            and f'"experiment_id":"{EXP_ID}"' not in line
        ]
    else:
        existing = []
    EXPERIMENT_LOG.write_text("\n".join([*existing, compact_line]) + "\n", encoding="utf-8")

    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": decision,
                    "best_pruned_variant": best_pruned_name,
                    "best_pruned_vs_full": best_pruned_vs_full["delta"],
                    "full_bundle_vs_core": core_comparisons["full_bundle"]["delta"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
