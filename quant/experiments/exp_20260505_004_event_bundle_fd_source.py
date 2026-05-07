"""exp-20260505-004 event bundle FD/Other source composition replay.

Alpha search. The current strongest replay-only alpha surface is the
default-off external event bundle from exp-20260504-049. This experiment changes
one causal variable: add the already-frozen FD/Other Event negative-reaction
source from exp-20260504-037 as a fourth independent source and measure its
marginal value versus the existing three-source bundle.

No thresholds, holding periods, event notionals, core A/B entries, ranking,
sizing, exits, LLM prompts, news vetoes, or production orders are changed.
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

from experiments.exp_20260504_037_sec_fd_other_event_sleeve import (  # noqa: E402
    _candidate_events as build_fd_candidates,
    _select_trades as select_fd_trades,
)
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
)


EXP_ID = "exp-20260505-004"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "event_bundle_fd_source.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_event_bundle_fd_source.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

FD_SOURCE = "sec_fd_other_event_negative_reaction"
BASELINE_SOURCES = [
    "form4_meaningful_purchase",
    "sec_negative_reaction",
    "sec_governance_procedural",
]
AFTER_SOURCES = [*BASELINE_SOURCES, FD_SOURCE]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


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


def _select_fd_trades_by_window(
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    candidates, fd_prices = build_fd_candidates()
    for ticker, rows in fd_prices.items():
        prices.setdefault(ticker, rows)

    selected_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    skipped_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    for label, window in WINDOWS.items():
        selected, skipped = select_fd_trades(
            candidates,
            prices,
            start=window["start"],
            end=window["end"],
        )
        for trade in selected:
            trade["source"] = FD_SOURCE
        selected_by_window[label] = selected
        skipped_by_window[label] = skipped

    coverage = {
        "fd_candidate_count": len(candidates),
        "fd_candidate_by_window": dict(Counter(str(row.get("window")) for row in candidates)),
        "fd_selected_trade_count": sum(len(rows) for rows in selected_by_window.values()),
        "fd_selected_by_window": {
            label: len(rows) for label, rows in selected_by_window.items()
        },
        "fd_skipped_by_window": {
            label: len(rows) for label, rows in skipped_by_window.items()
        },
        "fd_skipped_reason_counts": {
            label: dict(Counter(str(row.get("reason") or "unknown") for row in rows))
            for label, rows in skipped_by_window.items()
        },
    }
    return selected_by_window, coverage


def _source_summary(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        row = out.setdefault(source, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in out.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(row["total_pnl"], 2)
    return out


def _marginal_gate(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    aggregate_before = {
        "expected_value_score": sum(
            float(before[label].get("expected_value_score") or 0.0) for label in WINDOWS
        ),
        "total_pnl": sum(float(before[label].get("total_pnl") or 0.0) for label in WINDOWS),
    }
    aggregate_after = {
        "expected_value_score": sum(
            float(after[label].get("expected_value_score") or 0.0) for label in WINDOWS
        ),
        "total_pnl": sum(float(after[label].get("total_pnl") or 0.0) for label in WINDOWS),
    }
    ev_delta = aggregate_after["expected_value_score"] - aggregate_before["expected_value_score"]
    pnl_delta = aggregate_after["total_pnl"] - aggregate_before["total_pnl"]
    ev_delta_pct = (
        ev_delta / aggregate_before["expected_value_score"]
        if aggregate_before["expected_value_score"]
        else None
    )
    pnl_delta_pct = (
        pnl_delta / aggregate_before["total_pnl"] if aggregate_before["total_pnl"] else None
    )
    windows_ev_improved = sum(
        1
        for label in WINDOWS
        if (after[label].get("expected_value_score") or 0.0)
        > (before[label].get("expected_value_score") or 0.0)
    )
    windows_ev_regressed = sum(
        1
        for label in WINDOWS
        if (after[label].get("expected_value_score") or 0.0)
        < (before[label].get("expected_value_score") or 0.0)
    )
    trade_count_windows = sum(1 for row in by_window.values() if row["passes_trade_count"])
    return {
        "by_window": by_window,
        "baseline_bundle_ev_sum": round(aggregate_before["expected_value_score"], 4),
        "after_bundle_ev_sum": round(aggregate_after["expected_value_score"], 4),
        "aggregate_ev_delta": round(ev_delta, 4),
        "aggregate_ev_delta_pct": round(ev_delta_pct, 6) if ev_delta_pct is not None else None,
        "baseline_bundle_pnl_sum": round(aggregate_before["total_pnl"], 2),
        "after_bundle_pnl_sum": round(aggregate_after["total_pnl"], 2),
        "aggregate_pnl_delta": round(pnl_delta, 2),
        "aggregate_pnl_delta_pct": round(pnl_delta_pct, 6) if pnl_delta_pct is not None else None,
        "windows_ev_improved": windows_ev_improved,
        "windows_ev_regressed": windows_ev_regressed,
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
        "passes_material_ev": bool(ev_delta_pct is not None and ev_delta_pct > 0.10),
        "passes_pnl": bool(pnl_delta_pct is not None and pnl_delta_pct > 0.05),
        "passes_sharpe_any_window": any(row["passes_sharpe"] for row in by_window.values()),
        "passes_drawdown_any_window": any(row["passes_drawdown"] for row in by_window.values()),
        "passes_trade_count_any_window": any(row["passes_trade_count"] for row in by_window.values()),
        "passes_trade_count_majority_windows": trade_count_windows >= 2,
        "trade_count_gate_windows": trade_count_windows,
        "satellite_source_acceptance_note": (
            "Trade-count lift is diagnostic for a new satellite source; it is not "
            "sufficient by itself because added source capacity mechanically adds trades."
        ),
    }


def build_payload() -> dict[str, Any]:
    base_trades_by_window, base_coverage, prices = _load_event_trades()
    fd_trades_by_window, fd_coverage = _select_fd_trades_by_window(prices)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    current_bundle_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    marginal_delta_by_window: dict[str, dict[str, Any]] = OrderedDict()
    event_overlay: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        base_trades = list(base_trades_by_window[label])
        fd_trades = list(fd_trades_by_window[label])
        after_trades = [*base_trades, *fd_trades]

        current_curve = _event_equity_curve(
            base_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_curve = _event_equity_curve(
            after_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )

        core_metrics[label] = _core_metrics(result)
        current_bundle_metrics[label] = _combined_metrics(result, current_curve, base_trades)
        after_metrics[label] = _combined_metrics(result, after_curve, after_trades)
        marginal_delta_by_window[label] = _metric_delta(
            current_bundle_metrics[label],
            after_metrics[label],
        )
        event_overlay[label] = {
            "current_bundle_trade_count": len(base_trades),
            "fd_trade_count": len(fd_trades),
            "after_trade_count": len(after_trades),
            "current_bundle_event_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in base_trades),
                2,
            ),
            "fd_event_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in fd_trades),
                2,
            ),
            "after_event_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in after_trades),
                2,
            ),
            "source_summary": _source_summary(after_trades),
            "fd_trades": [
                {
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                    "reaction_excess_return": trade.get("reaction_excess_return"),
                }
                for trade in fd_trades
            ],
        }

    current_vs_core_delta = _aggregate_delta(core_metrics, current_bundle_metrics)
    after_vs_core_delta = _aggregate_delta(core_metrics, after_metrics)
    marginal_gate = _marginal_gate(current_bundle_metrics, after_metrics)

    accepted = (
        marginal_gate["windows_ev_improved"] >= 2
        and marginal_gate["windows_ev_regressed"] == 0
        and (
            marginal_gate["passes_material_ev"]
            or marginal_gate["passes_pnl"]
            or marginal_gate["passes_sharpe_any_window"]
            or marginal_gate["passes_drawdown_any_window"]
        )
    )
    sample_positive = (
        marginal_gate["windows_ev_improved"] >= 2
        and marginal_gate["windows_ev_regressed"] == 0
    )
    if accepted:
        decision = "accepted_requires_default_off_forward_parity"
        status = "accepted_requires_followup"
        rationale = (
            "The FD/Other source adds material marginal value to the existing event bundle. "
            "It must remain default-off until a shared production/backtest paper ledger exists."
        )
    elif sample_positive:
        decision = "positive_marginal_sample_not_material"
        status = "rejected"
        rationale = (
            "The FD/Other source improved the event bundle directionally, but the marginal "
            "lift versus the existing three-source bundle did not clear Gate 4 materiality."
        )
    else:
        decision = "rejected_no_stable_marginal_alpha"
        status = "rejected"
        rationale = (
            "The FD/Other source did not improve the existing three-source event bundle "
            "across the canonical windows without regression."
        )

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "mechanism_family": "external_event_satellite_overlay",
        "change_type": "event_bundle_source_composition",
        "hypothesis": (
            "The already-positive FD/Other Event negative-reaction source may add "
            "incremental satellite alpha when bundled with the existing Form 4, SEC "
            "negative-reaction, and SEC governance/procedural event sources."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_event_sleeve",
            "entry_exit_ranking_or_allocation": "satellite entry/allocation",
            "why_this_now": (
                "LLM soft-ranking and fresh SEC earnings shock are data-blocked; macro ETF "
                "expansion and core threshold surfaces are recently rejected; the event "
                "bundle is the strongest remaining alpha surface."
            ),
        },
        "single_causal_variable": (
            "add FD/Other Event negative-reaction as a fourth independent event bundle source"
        ),
        "parameters": {
            "baseline_sources": BASELINE_SOURCES,
            "after_sources": AFTER_SOURCES,
            "fd_source_definition": "fd_or_other_event + negative_excess_le_minus_2pct",
            "event_notional_usd": EVENT_NOTIONAL,
            "per_source_max_positions": 1,
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
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260504-037": "FD/Other source alone was positive but immaterial.",
                "exp-20260504-049": "Three-source event bundle was promising replay-only.",
                "exp-20260504-053": "Three-source bundle paper attribution is production-visible/default-off.",
                "exp-20260504-055": "No overlap for event-confirmed gap-cancel exception.",
            },
            "why_not_simple_repeat": (
                "This is not another FD threshold, notional, holding-period, or capacity run. "
                "It measures one source-composition question: FD marginal value versus the "
                "already-formed event bundle."
            ),
            "mechanism_insight_guardrails": [
                "No event threshold tuning.",
                "No direct live promotion.",
                "No A/B core slot replacement.",
                "No LLM or keyword prompt change.",
            ],
        },
        "core_metrics": core_metrics,
        "before_metrics": current_bundle_metrics,
        "after_metrics": after_metrics,
        "marginal_delta_by_window": marginal_delta_by_window,
        "current_vs_core_delta": current_vs_core_delta,
        "after_vs_core_delta": after_vs_core_delta,
        "marginal_gate": marginal_gate,
        "expected_value_score_delta": {
            label: marginal_delta_by_window[label]["expected_value_score"]
            for label in WINDOWS
        },
        "coverage": {
            "base_bundle": base_coverage,
            "fd_source": fd_coverage,
        },
        "event_overlay": event_overlay,
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
                "A shared default-off FD paper ledger and event-bundle source adapter are "
                "required before production observation or live capital."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "Production-aligned LLM soft-ranking remains sample-limited; this uses "
                "PIT-safe SEC metadata instead."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": None if status != "rejected" else rationale,
        "why_not_other_attractive_points": (
            "LLM soft-ranking lacks outcome joins; filing-shock rows still lack fresh PIT "
            "financial fields; macro ETF and XLE/USO expansion just failed; core A/B "
            "threshold/ranking/capacity surfaces have recent anti-repeat guardrails."
        ),
        "risk_of_change": (
            "Sparse event sources can overstate robustness when combined after the fact; "
            "any accepted result would still need default-off forward paper evidence."
        ),
        "next_action": (
            "Do not add FD to the production-visible bundle unless marginal Gate 4 passes; "
            "if rejected, wait for forward event samples or a materially richer event source."
        ),
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(AUDIT_MD),
            "docs/experiment_log.jsonl",
        ],
    }


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260505-004 Event Bundle FD Source Composition",
        "",
        "Alpha search. Compares the current three-source default-off event bundle with the same bundle plus the frozen FD/Other Event negative-reaction source.",
        "",
        "## Marginal Three-Window Result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | FD trades | FD PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["marginal_delta_by_window"][label]
        overlay = payload["event_overlay"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {trades} | ${fdpnl:,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=overlay["fd_trade_count"],
                fdpnl=overlay["fd_event_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Marginal Gate",
            "",
            "```json",
            json.dumps(payload["marginal_gate"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
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
            "experiment_id": EXP_ID,
            "title": "Event bundle FD source composition",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(AUDIT_MD, build_report(payload))

    compact = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "marginal_gate": payload["marginal_gate"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(compact), sort_keys=True) + "\n")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "marginal_gate": payload["marginal_gate"],
                    "fd_trade_counts": {
                        label: payload["event_overlay"][label]["fd_trade_count"]
                        for label in WINDOWS
                    },
                    "fd_pnl": {
                        label: payload["event_overlay"][label]["fd_event_pnl"]
                        for label in WINDOWS
                    },
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
