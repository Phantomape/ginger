"""exp-20260507-021 event/core pressure guard replay.

Alpha search. The default-off external event overlay bundle remains the
strongest replay-positive non-core alpha family, but live promotion is blocked
until forward paper outcomes close. This experiment changes one deterministic
allocation variable inside that family: whether event satellite entries should
stand down when the core A/B book is already active.

No event sources, thresholds, holding periods, notionals, core entries, ranking,
sizing, exits, LLM/news behavior, universe membership, or production orders are
changed.
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


EXP_ID = "exp-20260507-021"
STEM = "event_core_pressure_guard"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "No core pressure guard; current frozen event bundle.",
                "max_core_active": None,
                "same_ticker_guard": False,
            },
        ),
        (
            "no_same_ticker_core_overlap",
            {
                "description": "Skip event entries when the same ticker is already active in the core book.",
                "max_core_active": None,
                "same_ticker_guard": True,
            },
        ),
        (
            "core_active_le_1",
            {
                "description": "Skip event entries when more than one core position is already active.",
                "max_core_active": 1,
                "same_ticker_guard": False,
            },
        ),
        (
            "core_idle_only",
            {
                "description": "Skip event entries unless the core book has zero active positions.",
                "max_core_active": 0,
                "same_ticker_guard": False,
            },
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _ticker(value: Any) -> str:
    return str(value or "").upper()


def _core_active_at(core_trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    entry = _date10(entry_date)
    return [
        trade
        for trade in core_trades
        if _date10(trade.get("entry_date")) <= entry <= _date10(trade.get("exit_date"))
    ]


def _event_pressure_context(
    event_trade: dict[str, Any],
    core_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    active = _core_active_at(core_trades, _date10(event_trade.get("entry_date")))
    event_ticker = _ticker(event_trade.get("ticker"))
    same_ticker = [
        trade
        for trade in active
        if _ticker(trade.get("ticker")) == event_ticker
    ]
    return {
        "core_active_count": len(active),
        "core_active_tickers": sorted(_ticker(trade.get("ticker")) for trade in active),
        "same_ticker_core_active": bool(same_ticker),
    }


def _select_variant_trades(
    event_trades: list[dict[str, Any]],
    core_trades: list[dict[str, Any]],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    max_core_active = variant.get("max_core_active")
    same_ticker_guard = bool(variant.get("same_ticker_guard", False))

    for trade in event_trades:
        context = _event_pressure_context(trade, core_trades)
        reasons: list[str] = []
        if max_core_active is not None and context["core_active_count"] > int(max_core_active):
            reasons.append("core_active_count_above_limit")
        if same_ticker_guard and context["same_ticker_core_active"]:
            reasons.append("same_ticker_core_active")
        enriched = {**trade, "core_pressure_context": context}
        if reasons:
            skipped.append(
                {
                    "ticker": trade.get("ticker"),
                    "source": trade.get("source"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                    "skip_reasons": reasons,
                    **context,
                }
            )
            continue
        selected.append(enriched)
    return selected, skipped


def _metrics_from_trades(
    result: dict[str, Any],
    trades: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    window: dict[str, str],
) -> dict[str, Any]:
    if not trades:
        return _core_metrics(result)
    curve = _event_equity_curve(
        trades,
        prices=prices,
        start=window["start"],
        end=window["end"],
    )
    return _combined_metrics(result, curve, trades)


def _gate_summary(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = _aggregate_delta(before, after)
    by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in by_window.values())
        or any(row["passes_drawdown"] for row in by_window.values())
    )
    passed = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and material
    )
    return {
        "passed": bool(passed),
        "delta": delta,
        "by_window": by_window,
        "rule": (
            "EV first over the three canonical backtesting.md windows; require "
            "majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger."
        ),
    }


def _trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    by_source: dict[str, dict[str, Any]] = {}
    pressure: Counter[str] = Counter()
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        row = by_source.setdefault(source, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
        context = trade.get("core_pressure_context") or {}
        pressure[str(context.get("core_active_count", "unknown"))] += 1
    for row in by_source.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(float(row["total_pnl"]), 2)
    return {
        "trade_count": len(trades),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "source_summary": by_source,
        "core_active_count_distribution": dict(sorted(pressure.items())),
        "trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "core_pressure_context": trade.get("core_pressure_context"),
            }
            for trade in trades
        ],
    }


def _skip_summary(skipped: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "skip_count": len(skipped),
        "skip_reason_counts": dict(Counter(reason for row in skipped for reason in row["skip_reasons"])),
        "skipped_event_pnl": round(sum(float(row.get("pnl") or 0.0) for row in skipped), 2),
        "skipped_winners": sum(1 for row in skipped if float(row.get("pnl") or 0.0) > 0),
        "skipped_trades": skipped,
    }


def _best_guard_name(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != "full_bundle"]
    return max(
        names,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event_trades_by_window, coverage, prices = _load_event_trades()

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    core_trade_counts: dict[str, int] = {}

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_trades = list(result.get("trades") or [])
        core_trade_counts[label] = len(core_trades)
        core_metrics[label] = _core_metrics(result)
        all_events = event_trades_by_window[label]

        for name, variant in VARIANTS.items():
            selected, skipped = _select_variant_trades(all_events, core_trades, variant)
            metrics = _metrics_from_trades(result, selected, prices, window)
            variant_metrics[name][label] = metrics
            variant_events[name][label] = {
                "selected": _trade_summary(selected),
                "skipped": _skip_summary(skipped),
            }
        full_metrics[label] = variant_metrics["full_bundle"][label]

    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    full_gates = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    best_guard = _best_guard_name(full_gates)
    best_gate = full_gates[best_guard]
    accepted = bool(best_gate["passed"] and core_gates[best_guard]["passed"])
    decision = "promising_replay_only_core_pressure_guard" if accepted else "rejected"

    if accepted:
        decision_rationale = (
            f"Promising replay-only: {best_guard} beat the full frozen event bundle "
            "and the core baseline under the three-window Gate 4 rule. It still "
            "requires a shared default-off event adapter that reads core book pressure "
            "before any production use."
        )
        rejection_reason = None
        next_action = (
            "Move only the accepted core-pressure guard into a default-off shared paper "
            "adapter, then collect forward closed event outcomes before live promotion."
        )
    else:
        decision_rationale = (
            f"Rejected: the best guard ({best_guard}) did not beat the full frozen event "
            "bundle with enough stable EV improvement. Core pressure gating removed too "
            "many profitable event entries or failed materiality."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Keep the full default-off event bundle as the stronger replay surface; do not "
            "retry nearby core-pressure guards without forward replacement-value evidence."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_core_pressure_allocation_guard_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "External event satellite entries may have better marginal value when they "
            "are not stacking risk on top of an already-active core A/B book."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation/core-book pressure",
            "why_this_now": (
                "LLM soft-ranking lacks joined outcomes, earnings/C and FD/Other variants "
                "were rejected, event source pruning failed, and the full event bundle is "
                "the strongest remaining replay-positive alpha surface."
            ),
        },
        "single_causal_variable": "core book pressure at event entry",
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
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
                "event source definitions",
                "event thresholds",
                "event notional",
                "event holding period",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "historical_experiment_check": {
            "similar_positive_priors": {
                "exp-20260504-049": "Full default-off event bundle improved all three canonical windows.",
                "exp-20260505-025": "Event bundle remains strongest current direction while forward outcomes accumulate.",
            },
            "nearby_rejected": {
                "exp-20260507-012": "Event source pruning did not beat the full bundle.",
                "exp-20260505-031": "One-day event follow-through delay regressed all windows.",
                "exp-20260507-019": "Combining event/state satellites under shared capacity failed incremental Gate 4.",
                "exp-20260507-020": "FD/Other item 8.01 semantics was positive but immaterial.",
            },
            "why_not_simple_repeat": (
                "This does not prune event sources, alter semantic fields, change timing, or combine "
                "state-surface trades. It tests whether the event bundle's marginal value depends on "
                "observable core book pressure at the event entry date."
            ),
            "mechanism_insight_conflict": (
                "No conflict with the current do-not-repeat list: no LLM ranking, no broad universe "
                "growth, no short/options overlay, no raw earnings/C, no runner exit, and no event source pruning."
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
            "best_guard_vs_full_bundle": {
                label: best_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "best_guard_vs_core": {
                label: core_gates[best_guard]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "event_selection": variant_events,
        "core_trade_counts": core_trade_counts,
        "coverage": coverage,
        "best_guard_variant": best_guard,
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
                "A shared default-off event paper/live adapter must compute core book pressure "
                "from the same open-position state in run.py and backtester before any capital impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking outcome joins remain sparse; this deterministic allocation "
                "experiment avoids weakening or expanding LLM responsibilities."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings raw enablement, LLM ranking, FD/Other semantics, event source pruning, "
            "state-surface pruning/combination, broad universe expansion, and runner exits all "
            "have recent blocker or rejection evidence."
        ),
        "risk_of_change": (
            "A core-pressure guard can miss profitable event trades during strong tapes where "
            "core exposure and event alpha are complementary rather than redundant."
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
        "# exp-20260507-021 Event/Core Pressure Guard",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests whether the default-off event bundle should stand down when the core book is already active.",
        "",
        "## Best Guard Vs Full Bundle",
        "",
        "| Window | Full EV | Guard EV | Delta EV | Full PnL | Guard PnL | Delta PnL | Guard trades | Skipped PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    best = payload["best_guard_variant"]
    gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    for label in WINDOWS:
        before = payload["before_metrics"]["full_event_bundle"][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]["selected"]
        skipped = payload["event_selection"][best][label]["skipped"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${skipped_pnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=selected["trade_count"],
                skipped_pnl=skipped["skipped_event_pnl"],
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
            "title": "Event/core pressure guard",
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
        "best_guard_variant": payload["best_guard_variant"],
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
    best = payload["best_guard_variant"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": payload["decision"],
                    "best_guard_variant": best,
                    "best_guard_vs_full_bundle": payload["delta_metrics"]["variant_vs_full_bundle"][best]["delta"],
                    "best_guard_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
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
