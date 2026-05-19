"""exp-20260504-049 default-off event overlay bundle replay.

Alpha search. The core A/B stack is already saturated and recent LLM/news,
macro ETF, AI infra, Form 4, and SEC queue experiments leave one clean question:
do the frozen default-off external event queues deserve satellite capital as a
bundle, without competing for core A/B slots?

This script changes one causal variable in replay only: add independent $10k
event overlays for the already-frozen Form 4 meaningful-purchase queue, SEC
negative-reaction queue, and SEC governance/procedural queue. It does not tune
thresholds, add tickers, alter core entries, alter ranking, alter sizing, alter
exits, touch LLM/news, or change production defaults.
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

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260503_051_sec_filing_reaction_drift import (  # noqa: E402
    _load_snapshot,
)
from experiments.exp_20260504_010_sec_event_sleeve_backtest import (  # noqa: E402
    build_primary_candidates as build_sec_negative_candidates,
)
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    _candidate_trade as form4_candidate_trade,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_form4_events,
    _load_price_map,
    _select_event_trades as select_form4_trades,
)
from experiments.exp_20260504_039_sec_governance_procedural_overlay import (  # noqa: E402
    _candidate_events as build_sec_governance_candidates,
    _select_trades as select_governance_trades,
)


EXP_ID = "exp-20260504-049"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "default_off_event_overlay_bundle.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / "exp-20260504-049_default_off_event_overlay_bundle.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20260421.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

# Correct the old_thin snapshot path explicitly after OrderedDict construction.
WINDOWS["old_thin"]["snapshot"] = "data/ohlcv_snapshot_20241002_20250422.json"

SOURCE_ORDER = {
    "sec_governance_procedural": 0,
    "sec_negative_reaction": 1,
    "form4_meaningful_purchase": 2,
}


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


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _idx_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") >= date_value:
            return idx
    return None


def _sec_negative_trade(candidate: dict[str, Any], prices: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    entry_date = str(candidate.get("entry_date") or "")[:10]
    rows = prices.get(ticker) or []
    entry_idx = _idx_on_or_after(rows, entry_date)
    if entry_idx is None:
        return {**candidate, "status": "missing_entry_price"}
    exit_idx = entry_idx + HOLD_DAYS - 1
    if exit_idx >= len(rows):
        return {**candidate, "status": "missing_exit_price"}
    entry = rows[entry_idx]
    exit_row = rows[exit_idx]
    entry_open = entry.get("open")
    exit_close = exit_row.get("close")
    if not entry_open or not exit_close:
        return {**candidate, "status": "missing_open_or_close"}
    shares = EVENT_NOTIONAL / float(entry_open)
    pnl = shares * float(exit_close) - EVENT_NOTIONAL - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
    return {
        **candidate,
        "source": "sec_negative_reaction",
        "status": "price_ready",
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry_open), 4),
        "exit_close": round(float(exit_close), 4),
        "shares": shares,
        "notional": EVENT_NOTIONAL,
        "pnl": round(pnl, 2),
        "net_return_pct": round(pnl / EVENT_NOTIONAL, 6),
    }


def _select_sec_negative_trades(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if row.get("status") == "price_ready"
        and start <= str(row.get("entry_date") or "")[:10] <= end
    ]
    scoped.sort(
        key=lambda row: (
            row["entry_date"],
            float(row.get("reaction_excess_return") or 0.0),
            row["ticker"],
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in scoped:
        entry_date = str(row["entry_date"])[:10]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= 1:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "entry_date": entry_date,
                    "reason": "source_slot_full",
                    "source": "sec_negative_reaction",
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _load_core_result(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _load_event_trades() -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
    dict[str, list[dict[str, Any]]],
]:
    prices = _load_price_map()

    form4_events, form4_path = _load_form4_events(prices)
    form4_candidates = []
    for event in form4_events:
        trade = form4_candidate_trade(event, prices)
        if trade.get("status") == "price_ready":
            trade["source"] = "form4_meaningful_purchase"
            form4_candidates.append(trade)

    sec_negative_candidates, sec_negative_prices = build_sec_negative_candidates()
    # The SEC negative runner returns a merged price map with the same schema.
    for ticker, rows in sec_negative_prices.items():
        prices.setdefault(ticker, rows)
    sec_negative_trades = [
        trade
        for trade in (_sec_negative_trade(row, prices) for row in sec_negative_candidates)
        if trade.get("status") == "price_ready"
    ]

    governance_candidates, governance_prices, governance_coverage = build_sec_governance_candidates()
    for ticker, rows in governance_prices.items():
        prices.setdefault(ticker, rows)

    by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    source_skips: dict[str, list[dict[str, Any]]] = {
        "form4_meaningful_purchase": [],
        "sec_negative_reaction": [],
        "sec_governance_procedural": [],
    }
    for label, window in WINDOWS.items():
        form4_selected, form4_skipped = select_form4_trades(
            form4_candidates,
            start=window["start"],
            end=window["end"],
        )
        negative_selected, negative_skipped = _select_sec_negative_trades(
            sec_negative_trades,
            start=window["start"],
            end=window["end"],
        )
        governance_selected, governance_skipped = select_governance_trades(
            governance_candidates,
            prices,
            start=window["start"],
            end=window["end"],
        )
        for trade in governance_selected:
            trade["source"] = "sec_governance_procedural"

        source_skips["form4_meaningful_purchase"].extend(form4_skipped)
        source_skips["sec_negative_reaction"].extend(negative_skipped)
        source_skips["sec_governance_procedural"].extend(governance_skipped)

        rows = [*governance_selected, *negative_selected, *form4_selected]
        rows.sort(
            key=lambda row: (
                row["entry_date"],
                SOURCE_ORDER.get(row.get("source"), 99),
                row.get("ticker", ""),
            )
        )
        by_window[label] = rows

    coverage = {
        "form4_source_path": str(form4_path) if form4_path else None,
        "form4_price_ready_candidates": len(form4_candidates),
        "sec_negative_price_ready_candidates": len(sec_negative_trades),
        "sec_governance_coverage": governance_coverage,
        "source_skipped_counts": {
            source: len(rows) for source, rows in source_skips.items()
        },
        "source_skipped_reason_counts": {
            source: dict(Counter(str(row.get("reason") or row.get("status") or "unknown") for row in rows))
            for source, rows in source_skips.items()
        },
    }
    return by_window, coverage, prices


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1 for label in WINDOWS
            if (after[label].get("expected_value_score") or 0) > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1 for label in WINDOWS
            if (after[label].get("expected_value_score") or 0) < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1 for label in WINDOWS
            if (after[label].get("total_pnl") or 0) > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1 for label in WINDOWS
            if (after[label].get("total_pnl") or 0) < (before[label].get("total_pnl") or 0)
        ),
    }


def _source_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        row = out.setdefault(source, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in out.values():
        count = row["trade_count"]
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(row["total_pnl"], 2)
    return out


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260504-049 Default-Off Event Overlay Bundle",
        "",
        "Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.",
        "",
        "## Three-window result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        source = payload["event_overlay"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {trades} | ${epnl:,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=source["event_trade_count"],
                epnl=source["event_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Source contribution",
            "",
            "```json",
            json.dumps(payload["source_contribution"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines))


def main() -> int:
    event_trades_by_window, coverage, prices = _load_event_trades()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    per_window: dict[str, dict[str, Any]] = OrderedDict()
    source_contribution: dict[str, Any] = OrderedDict()
    core_results: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        event_trades = event_trades_by_window[label]
        event_curve = _event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = _combined_metrics(result, event_curve, event_trades)
        source_summary = _source_summary(event_trades)
        source_contribution[label] = source_summary
        per_window[label] = {
            "event_trade_count": len(event_trades),
            "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in event_trades), 2),
            "source_summary": source_summary,
            "event_trades": [
                {
                    "source": trade.get("source"),
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                }
                for trade in event_trades
            ],
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(before_metrics[label], after_metrics[label]))
        for label in WINDOWS
    )
    passed_without_regression = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and (
            (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
            or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
            or any(row["passes_sharpe"] for row in gate4_by_window.values())
            or any(row["passes_drawdown"] for row in gate4_by_window.values())
        )
    )
    decision = "promising_replay_only" if passed_without_regression else "rejected"
    decision_rationale = (
        "Promising replay-only: the frozen event overlay bundle improved the majority of windows without EV regression. "
        "It is not promoted to production orders here; a shared trade-enabled adapter and forward paper outcomes are required before live capital."
        if passed_without_regression
        else "Rejected: the frozen event overlay bundle did not clear the three-window Gate 4 standard without EV regression and materiality."
    )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "default_off_event_overlay_bundle_replay",
        "mechanism_family": "external_event_satellite_overlay",
        "hypothesis": (
            "Frozen default-off external event queues may have enough combined satellite alpha "
            "to merit future capital without consuming core A/B slots."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_event_sleeve",
            "entry_exit_ranking_or_allocation": "satellite entry/allocation",
            "why_this_now": (
                "LLM soft-ranking, macro ETFs, core ranking, slot, and simple lifecycle surfaces are recently blocked or rejected; "
                "the strongest remaining positive evidence is external event queues."
            ),
        },
        "single_causal_variable": "independent 10k satellite overlay for already-frozen default-off event queues",
        "parameters": {
            "event_sources": [
                "form4_meaningful_purchase",
                "sec_negative_reaction",
                "sec_governance_procedural",
            ],
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
            "similar_experiments": {
                "exp-20260504-010": "SEC negative-reaction standalone event sleeve positive but concentrated; no direct core promotion.",
                "exp-20260504-012": "SEC negative-reaction default-off queue exists for forward observation.",
                "exp-20260504-034": "Form 4 satellite overlay positive in all windows but below materiality.",
                "exp-20260504-039": "SEC governance/procedural overlay passed but required default-off forward ledger.",
                "exp-20260504-044": "SEC governance/procedural queue and paper ledger added observe-only.",
                "exp-20260504-048": "No fresh SEC/earnings evidence; do not rerun same-sample event threshold tuning.",
            },
            "why_not_simple_repeat": (
                "This does not retune any event threshold or promote a single source. "
                "It tests one capital-allocation question: whether frozen default-off event queues add enough satellite value as a bundle."
            ),
            "mechanism_insight_guardrails": [
                "No keyword phrase tuning.",
                "No reaction-threshold sweep.",
                "No Form 4 purchase-value or owner-role sweep.",
                "No core-slot replacement or A/B ranking change.",
                "No production order change without shared adapter and parity tests.",
            ],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": {
            "by_window": gate4_by_window,
            "passes_without_ev_regression": passed_without_regression,
            "rule": "EV first; use the three canonical backtesting.md windows; no production promotion from replay-only event bundle evidence.",
        },
        "event_overlay": per_window,
        "source_contribution": source_contribution,
        "coverage": coverage,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
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
                "A trade-enabled shared event adapter plus forward paper/replacement-value outcomes are required before live capital."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking and filing-grade outcomes remain sample-limited; this tests non-LLM frozen event queues instead.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if passed_without_regression else decision_rationale,
        "why_not_other_attractive_points": (
            "LLM ranking lacks outcome joins, macro ETFs and XLE/USO pair confirmation were just rejected, "
            "AI infra is already a bounded pilot awaiting forward outcomes, and core A/B threshold/ranking/slot surfaces are saturated by recent failures."
        ),
        "risk_of_change": (
            "The replay bundles several sparse event families and can overstate robustness if treated as live-capital proof; "
            "forward observation and a shared adapter are required before promotion."
        ),
        "next_action": (
            "If this is positive, build a single shared default-off event-sleeve paper ledger before considering live capital; "
            "if negative, keep event sources observe-only and wait for forward samples."
        ),
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
            "title": "Default-off event overlay bundle replay",
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
        "change_type": "default_off_event_overlay_bundle_replay",
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": delta,
        "production_impact": payload["production_impact"],
        "decision_rationale": decision_rationale,
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(compact), sort_keys=True) + "\n")

    print(json.dumps(_safe({
        "experiment_id": EXP_ID,
        "decision": decision,
        "delta_metrics": delta,
        "event_trades": {
            label: per_window[label]["event_trade_count"] for label in WINDOWS
        },
    }), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
