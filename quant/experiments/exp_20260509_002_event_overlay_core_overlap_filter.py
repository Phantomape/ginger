"""exp-20260509-002 event overlay core-overlap filter replay.

Alpha search, replay-only. The frozen external event bundle is currently the
cleanest non-core alpha surface, but recent playbook guidance rejects another
source/notional/holding-period/capacity sweep. This experiment changes one
causal variable instead: whether event overlay candidates should be filtered by
their overlap with already-accepted A/B core exposure.

Core A/B entries, ranking, sizing, exits, scarce-slot routing, add-ons,
universe, LLM/news behavior, event source composition, event hold period, and
event notional are locked.
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


EXPERIMENT_ID = "exp-20260509-002"
STEM = "event_overlay_core_overlap_filter"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

CORE_STRATEGIES = {"trend_long", "breakout_long"}

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Current frozen three-source event overlay bundle.",
                "exclude_same_day_core_entry": False,
                "exclude_window_core_ticker": False,
            },
        ),
        (
            "no_same_day_core_entry",
            {
                "description": "Drop event rows when any A/B core trade enters on the same day.",
                "exclude_same_day_core_entry": True,
                "exclude_window_core_ticker": False,
            },
        ),
        (
            "no_window_core_ticker",
            {
                "description": "Drop event rows whose ticker is already traded by A/B in the same window.",
                "exclude_same_day_core_entry": False,
                "exclude_window_core_ticker": True,
            },
        ),
        (
            "non_overlap_both",
            {
                "description": "Keep only event rows with no same-day core entry and no same-window core ticker.",
                "exclude_same_day_core_entry": True,
                "exclude_window_core_ticker": True,
            },
        ),
    ]
)


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


def _core_context(result: dict[str, Any]) -> dict[str, Any]:
    trades = [
        trade
        for trade in result.get("trades") or []
        if trade.get("strategy") in CORE_STRATEGIES
        and trade.get("entry_date")
        and trade.get("ticker")
    ]
    entry_dates = {str(trade.get("entry_date") or "")[:10] for trade in trades}
    tickers = {str(trade.get("ticker") or "").upper() for trade in trades}
    return {
        "entry_dates": entry_dates,
        "tickers": tickers,
        "trade_count": len(trades),
    }


def _event_key(trade: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(trade.get("source") or "unknown"),
        str(trade.get("ticker") or "").upper(),
        str(trade.get("entry_date") or "")[:10],
    )


def _filter_events(
    trades: list[dict[str, Any]],
    context: dict[str, Any],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    entry_dates = set(context["entry_dates"])
    tickers = set(context["tickers"])
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")[:10]
        reasons: list[str] = []
        if variant["exclude_same_day_core_entry"] and entry_date in entry_dates:
            reasons.append("same_day_core_entry")
        if variant["exclude_window_core_ticker"] and ticker in tickers:
            reasons.append("same_window_core_ticker")
        if reasons:
            dropped.append({**trade, "core_overlap_drop_reasons": reasons})
        else:
            kept.append(trade)
    return kept, dropped


def _event_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(str(trade.get("source") or "unknown") for trade in trades)
    ticker_counts = Counter(str(trade.get("ticker") or "").upper() for trade in trades)
    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in trades)
    positive_by_ticker: dict[str, float] = {}
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl > 0:
            ticker = str(trade.get("ticker") or "").upper()
            positive_by_ticker[ticker] = positive_by_ticker.get(ticker, 0.0) + pnl
    positive_total = sum(positive_by_ticker.values())
    max_positive_share = (
        max(positive_by_ticker.values()) / positive_total
        if positive_total > 0
        else None
    )
    return {
        "event_trade_count": len(trades),
        "event_pnl": _round(total_pnl, 2),
        "event_win_rate": _round(
            sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0) / len(trades),
            4,
        )
        if trades
        else None,
        "source_counts": dict(sorted(source_counts.items())),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "max_single_ticker_positive_share": _round(max_positive_share, 4),
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


def _dropped_summary(dropped: list[dict[str, Any]]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    for trade in dropped:
        for reason in trade.get("core_overlap_drop_reasons") or []:
            reason_counts[str(reason)] += 1
    return {
        "dropped_count": len(dropped),
        "dropped_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in dropped), 2),
        "reason_counts": dict(sorted(reason_counts.items())),
        "dropped_events": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "drop_reasons": trade.get("core_overlap_drop_reasons"),
            }
            for trade in dropped
        ],
    }


def _variant_delta_vs_full(
    full_metrics: dict[str, dict[str, Any]],
    variant_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = _aggregate_delta(full_metrics, variant_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(full_metrics[label], variant_metrics[label]))
        for label in WINDOWS
    )
    passed = (
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
        "gate4_by_window": gate4_by_window,
        "passed": bool(passed),
        "rule": (
            "Incremental promotion requires majority-window EV improvement, no EV "
            "regression versus the full frozen bundle, and one Gate 4 materiality trigger."
        ),
    }


def _best_variant(gates_vs_full: dict[str, dict[str, Any]]) -> str:
    candidates = [name for name in gates_vs_full if name != "full_bundle"]
    return max(
        candidates,
        key=lambda name: (
            float(gates_vs_full[name]["delta"].get("after_ev_sum") or 0.0),
            float(gates_vs_full[name]["delta"].get("after_pnl_sum") or 0.0),
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Event Overlay Core-Overlap Filter",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| Window | Core EV | Full bundle EV | Full bundle PnL | Full event trades |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["core_metrics"][label]
        full = payload["variant_metrics"]["full_bundle"][label]
        event = payload["variant_event_summary"]["full_bundle"][label]
        lines.append(
            "| {label} | {core_ev} | {full_ev} | {full_pnl} | {trades} |".format(
                label=label,
                core_ev=core.get("expected_value_score"),
                full_ev=full.get("expected_value_score"),
                full_pnl=full.get("total_pnl"),
                trades=event.get("event_trade_count"),
            )
        )

    lines.extend(
        [
            "",
            "## Variant Comparison Versus Full Bundle",
            "",
            "| Variant | EV sum | EV delta | PnL delta | Windows improved/regressed | Gate | Event trades | Event PnL |",
            "|---|---:|---:|---:|---:|---|---:|---:|",
        ]
    )
    for name in payload["variants"]:
        if name == "full_bundle":
            summary = payload["core_delta"][name]
            delta = summary["delta"]
            gate = "core-baseline"
            ev_delta = delta["aggregate_ev_delta"]
            pnl_delta = delta["aggregate_pnl_delta"]
            improved = delta["windows_ev_improved"]
            regressed = delta["windows_ev_regressed"]
        else:
            summary = payload["incremental_gate_vs_full"][name]
            delta = summary["delta"]
            gate = "PASS" if summary["passed"] else "FAIL"
            ev_delta = delta["aggregate_ev_delta"]
            pnl_delta = delta["aggregate_pnl_delta"]
            improved = delta["windows_ev_improved"]
            regressed = delta["windows_ev_regressed"]
        event_totals = payload["variant_event_totals"][name]
        lines.append(
            "| {name} | {ev_sum} | {ev_delta} | {pnl_delta} | {imp}/{reg} | {gate} | {trades} | {event_pnl} |".format(
                name=name,
                ev_sum=delta["after_ev_sum"],
                ev_delta=ev_delta,
                pnl_delta=pnl_delta,
                imp=improved,
                reg=regressed,
                gate=gate,
                trades=event_totals["event_trade_count"],
                event_pnl=event_totals["event_pnl"],
            )
        )

    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. The default production and backtest order paths are unchanged. Any future positive version would require a shared event-candidate policy and run/backtester parity tests before capital impact.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = _load_event_trades()

    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_contexts: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_event_summary: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_drop_summary: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        core_contexts[label] = _core_context(result)
        core_metrics[label] = _core_metrics(result)
        for name, variant in VARIANTS.items():
            kept, dropped = _filter_events(
                raw_event_trades[label],
                core_contexts[label],
                variant,
            )
            curve = _event_equity_curve(
                kept,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _combined_metrics(result, curve, kept)
            variant_event_summary[name][label] = _event_summary(kept)
            variant_drop_summary[name][label] = _dropped_summary(dropped)

    core_delta = OrderedDict(
        (name, {"delta": _aggregate_delta(core_metrics, variant_metrics[name])})
        for name in VARIANTS
    )
    full_metrics = variant_metrics["full_bundle"]
    incremental_gate_vs_full = OrderedDict(
        (name, _variant_delta_vs_full(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    best = _best_variant(incremental_gate_vs_full)
    accepted = bool(incremental_gate_vs_full[best]["passed"])
    if accepted:
        decision = "promising_replay_only_core_overlap_filter"
        decision_rationale = (
            f"Promising replay-only: {best} beat the full frozen event bundle "
            "with the pre-registered three-window incremental Gate 4 standard. "
            "It is not promoted to production here; promotion requires a shared "
            "event-candidate policy and parity tests."
        )
        rejection_reason = None
        next_action = (
            "Design a shared default-off event-candidate adapter that computes "
            "core-overlap state before order generation, then rerun parity tests."
        )
    else:
        decision = "rejected_incremental_filter"
        decision_rationale = (
            f"Rejected as an incremental filter. The best overlap-filtered variant "
            f"({best}) did not beat the full frozen event bundle with enough "
            "three-window stability and materiality. The full event bundle remains "
            "the better candidate-pool surface."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Keep the full frozen event bundle for forward paper observation; do "
            "not prune event rows by core-overlap state without new forward "
            "replacement-value evidence."
        )

    variant_event_totals = OrderedDict()
    for name in VARIANTS:
        rows = list(variant_event_summary[name].values())
        ticker_positive: dict[str, float] = {}
        for label in WINDOWS:
            for trade in variant_event_summary[name][label]["event_trades"]:
                pnl = float(trade.get("pnl") or 0.0)
                if pnl > 0:
                    ticker = str(trade.get("ticker") or "").upper()
                    ticker_positive[ticker] = ticker_positive.get(ticker, 0.0) + pnl
        positive_total = sum(ticker_positive.values())
        variant_event_totals[name] = {
            "event_trade_count": sum(int(row["event_trade_count"]) for row in rows),
            "event_pnl": _round(sum(float(row["event_pnl"] or 0.0) for row in rows), 2),
            "max_single_ticker_positive_share": _round(
                max(ticker_positive.values()) / positive_total if positive_total > 0 else None,
                4,
            ),
        }

    hypothesis = (
        "If the event overlay's alpha is truly independent candidate-pool alpha, "
        "then filtering out event rows that overlap same-day or same-window core "
        "A/B exposure should preserve or improve the frozen bundle's replacement "
        "value without source/notional/holding-period tuning."
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_candidate_pool_overlap_filter_replay",
        "mechanism_family": "external_event_candidate_pool_quality",
        "hypothesis": hypothesis,
        "alpha_hypothesis": {
            "category": "candidate_pool/event_overlay",
            "entry_exit_ranking_or_allocation": "candidate_pool",
            "why_this_now": (
                "LLM soft-ranking is still sample-limited, simple universe growth "
                "is banned without scarce-slot evidence, and recent event-bundle "
                "source/notional/holding-period sweeps are no-go zones. This tests "
                "whether event candidates add independent alpha rather than duplicate "
                "core A/B exposure."
            ),
        },
        "single_causal_variable": (
            "event candidate eligibility by overlap with accepted A/B core exposure"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
            "event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "event source composition",
                "event notional",
                "event hold period",
                "core universe",
                "core signal generation",
                "candidate ranking",
                "core position sizing",
                "core exits",
                "scarce-slot routing",
                "add-ons",
                "LLM/news replay",
                "production order path",
            ],
            "gate4": {
                "primary_objective": "expected_value_score vs full frozen event bundle",
                "aggregate_expected_value_score_delta_pct": "> 10%",
                "aggregate_total_pnl_delta_pct": "> 5%",
                "daily_sharpe_delta": "> 0.1 in any canonical window",
                "drawdown_delta": "> 1pp improvement in any canonical window",
                "robustness": "EV improves in >=2 windows and regresses in 0 versus full bundle",
            },
        },
        "variants": VARIANTS,
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec.get("state_note") for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": {
            "avoided_recent_no_go_zones": [
                "LLM soft-ranking replay remains sample-limited",
                "gap-cancel joint discriminators were rejected",
                "event source pruning was rejected",
                "event notional, capacity, and hold-period sweeps are discouraged",
                "broad universe expansion is banned without scarce-slot quality evidence",
            ],
            "why_not_simple_repeat": (
                "This does not alter source composition, notional, capacity, hold "
                "period, event thresholds, or core candidate ranking. It tests the "
                "orthogonal question of whether event rows duplicate or diversify "
                "accepted core exposure."
            ),
        },
        "core_metrics": core_metrics,
        "variant_metrics": variant_metrics,
        "core_delta": core_delta,
        "incremental_gate_vs_full": incremental_gate_vs_full,
        "best_variant": best,
        "variant_event_summary": variant_event_summary,
        "variant_drop_summary": variant_drop_summary,
        "variant_event_totals": variant_event_totals,
        "source_coverage": source_coverage,
        "expected_value_score_delta": (
            incremental_gate_vs_full[best]["delta"]["aggregate_ev_delta"]
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking and event grading remain data-limited; this run "
                "uses deterministic replayable event/core overlap fields."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": next_action,
        "risk_of_change": (
            "Filtering overlap can remove useful event rows that confirm the same "
            "winners already present in A/B; this may reduce event-bundle convexity."
        ),
        "next_retry_requires": [
            "Do not retry nearby same-day/same-window overlap filters on the same sample.",
            "A valid retry needs forward paper replacement-value outcomes or a materially richer event-quality field.",
            "Any positive promotion must be implemented in shared run/backtester event-candidate policy with parity tests.",
        ],
        "related_files": [
            str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
    }
    return payload


def main() -> int:
    payload = build_payload()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Event overlay core-overlap filter",
        "status": payload["decision"],
        "decision": payload["decision"],
        "summary": payload["decision_rationale"],
        "created_at": payload["timestamp"],
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "next_action": payload["next_action"],
    }
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["variant_metrics"]["full_bundle"],
        "after_metrics": payload["variant_metrics"][payload["best_variant"]],
        "core_metrics": payload["core_metrics"],
        "delta_metrics": payload["incremental_gate_vs_full"][payload["best_variant"]],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
        "next_retry_requires": payload["next_retry_requires"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "best_incremental_delta": payload["incremental_gate_vs_full"][
                    payload["best_variant"]
                ]["delta"],
                "core_delta_full_bundle": payload["core_delta"]["full_bundle"]["delta"],
                "artifact": str(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
