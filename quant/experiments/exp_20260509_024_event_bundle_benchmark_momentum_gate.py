"""exp-20260509-024 event bundle benchmark momentum gate.

Alpha search, replay-only. Tests whether the frozen default-off event bundle
should participate only when broad benchmark momentum is positive.

Single causal variable:
    For event-bundle overlay trades only, require max(SPY, QQQ) trailing
    20-trading-day return before entry > 0.

This does not change production orders, core A/B entries, ranking, sizing,
exits, LLM/news behavior, event-source thresholds, or live/default adapters.
If accepted later, the gate must be implemented in a shared production/backtest
event policy with parity tests before it can affect live behavior.
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


EXPERIMENT_ID = "exp-20260509-024"
STEM = "event_bundle_benchmark_momentum_gate"
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

LOOKBACK_DAYS = 20
BENCHMARK_TICKERS = ("SPY", "QQQ")


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


def _last_index_before(rows: list[dict[str, Any]], date_value: str) -> int | None:
    idx = None
    for row_idx, row in enumerate(rows):
        row_date = str(row.get("date") or "")[:10]
        if row_date and row_date < date_value:
            idx = row_idx
        elif row_date >= date_value:
            break
    return idx


def _price_return_before_entry(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    lookback: int = LOOKBACK_DAYS,
) -> float | None:
    rows = prices.get(ticker) or []
    idx = _last_index_before(rows, entry_date)
    if idx is None or idx - lookback < 0:
        return None
    start = rows[idx - lookback].get("close")
    end = rows[idx].get("close")
    if not start or not end:
        return None
    return float(end) / float(start) - 1.0


def _gate_state(
    trade: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date") or "")[:10]
    benchmark_returns = {
        ticker: _price_return_before_entry(prices, ticker, entry_date)
        for ticker in BENCHMARK_TICKERS
    }
    ready_returns = [value for value in benchmark_returns.values() if value is not None]
    benchmark_return_max = max(ready_returns) if ready_returns else None
    allowed = benchmark_return_max is not None and benchmark_return_max > 0.0
    return {
        "entry_date": entry_date,
        "lookback_days": LOOKBACK_DAYS,
        "benchmark_returns_20d_before_entry": {
            ticker: _round(value, 6) if value is not None else None
            for ticker, value in benchmark_returns.items()
        },
        "benchmark_return_max_20d_before_entry": (
            _round(benchmark_return_max, 6) if benchmark_return_max is not None else None
        ),
        "benchmark_momentum_ready": benchmark_return_max is not None,
        "benchmark_momentum_positive": bool(
            benchmark_return_max is not None and benchmark_return_max > 0.0
        ),
        "allowed": allowed,
    }


def _filter_event_trades(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    skipped = []
    for trade in trades:
        gate = _gate_state(trade, prices=prices)
        enriched = {**trade, "benchmark_momentum_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
        else:
            skipped.append({**enriched, "reason": "benchmark_momentum_gate_blocked"})
    return kept, skipped


def _event_summary(trades: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in trades)
    skipped_pnl = sum(float(trade.get("pnl") or 0.0) for trade in skipped)
    return {
        "event_trade_count": len(trades),
        "event_pnl": _round(total_pnl, 2),
        "event_win_rate": _round(
            sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0) / len(trades)
            if trades
            else None,
            4,
        ),
        "blocked_trade_count": len(skipped),
        "blocked_pnl": _round(skipped_pnl, 2),
        "blocked_win_rate": _round(
            sum(1 for trade in skipped if float(trade.get("pnl") or 0.0) > 0) / len(skipped)
            if skipped
            else None,
            4,
        ),
        "source_summary": _source_summary(trades),
        "blocked_source_summary": _source_summary(skipped),
        "event_trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "benchmark_momentum_gate": trade.get("benchmark_momentum_gate"),
            }
            for trade in trades
        ],
        "blocked_trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "benchmark_momentum_gate": trade.get("benchmark_momentum_gate"),
                "reason": trade.get("reason"),
            }
            for trade in skipped
        ],
    }


def _build_artifact(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-024 Event Bundle Benchmark Momentum Gate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Core+Event EV | Gated EV | Delta EV | Core+Event PnL | Gated PnL | Delta PnL | Kept / blocked trades | Blocked PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["full_event_metrics"][label]
        after = payload["gated_event_metrics"][label]
        delta = payload["delta_vs_full_event"]["by_window"][label]
        event = payload["gated_event_overlay"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {kept}/{blocked} | ${blocked_pnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                kept=event["event_trade_count"],
                blocked=event["blocked_trade_count"],
                blocked_pnl=event["blocked_pnl"],
            )
        )

    delta = payload["delta_vs_full_event"]
    core_delta = payload["delta_vs_core_gated"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus full event bundle EV: {:.4f} -> {:.4f} ({:+.4f}, {:+.2%})".format(
                delta["baseline_ev_sum"],
                delta["after_ev_sum"],
                delta["aggregate_ev_delta"],
                delta["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- Versus full event bundle PnL: ${:,.2f} -> ${:,.2f} ({:+,.2f}, {:+.2%})".format(
                delta["baseline_pnl_sum"],
                delta["after_pnl_sum"],
                delta["aggregate_pnl_delta"],
                delta["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- Gated event bundle versus core EV delta: {:+.4f}".format(
                core_delta["aggregate_ev_delta"]
            ),
            "- Gated event bundle versus core PnL delta: ${:+,.2f}".format(
                core_delta["aggregate_pnl_delta"]
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. No live/default order path, core A/B behavior, event-source threshold, ranking, sizing, exits, or LLM/news behavior changed. A promoted version requires a shared run.py/backtester.py event policy and parity test.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event_trades_by_window, coverage, prices = _load_event_trades()

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_event_metrics: dict[str, dict[str, Any]] = OrderedDict()
    gated_event_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_event_overlay: dict[str, dict[str, Any]] = OrderedDict()
    gated_event_overlay: dict[str, dict[str, Any]] = OrderedDict()
    gate4_vs_full_by_window: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        core_result = _load_core_result(window)
        event_trades = event_trades_by_window[label]
        gated_trades, blocked_trades = _filter_event_trades(event_trades, prices=prices)

        full_curve = _event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        gated_curve = _event_equity_curve(
            gated_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )

        core_metrics[label] = _core_metrics(core_result)
        full_event_metrics[label] = _combined_metrics(core_result, full_curve, event_trades)
        gated_event_metrics[label] = _combined_metrics(core_result, gated_curve, gated_trades)
        full_event_overlay[label] = _event_summary(event_trades, [])
        gated_event_overlay[label] = _event_summary(gated_trades, blocked_trades)
        gate4_vs_full_by_window[label] = _gate4(
            full_event_metrics[label],
            gated_event_metrics[label],
        )

    delta_vs_full = _aggregate_delta(full_event_metrics, gated_event_metrics)
    delta_vs_core_full = _aggregate_delta(core_metrics, full_event_metrics)
    delta_vs_core_gated = _aggregate_delta(core_metrics, gated_event_metrics)

    passed_vs_full = (
        delta_vs_full["windows_ev_improved"] >= 2
        and delta_vs_full["windows_ev_regressed"] == 0
        and (
            (
                delta_vs_full["aggregate_ev_delta_pct"] is not None
                and delta_vs_full["aggregate_ev_delta_pct"] > 0.10
            )
            or (
                delta_vs_full["aggregate_pnl_delta_pct"] is not None
                and delta_vs_full["aggregate_pnl_delta_pct"] > 0.05
            )
            or any(row["passes_sharpe"] for row in gate4_vs_full_by_window.values())
            or any(row["passes_drawdown"] for row in gate4_vs_full_by_window.values())
        )
    )
    remains_positive_vs_core = (
        delta_vs_core_gated["windows_ev_improved"] >= 2
        and delta_vs_core_gated["aggregate_ev_delta"] > 0
        and delta_vs_core_gated["aggregate_pnl_delta"] > 0
    )
    accepted = bool(passed_vs_full and remains_positive_vs_core)
    decision = "accepted_direction_paper_only" if accepted else "rejected"
    if accepted:
        decision_rationale = (
            "Accepted as a paper-only event-bundle allocation lead: the benchmark "
            "momentum gate improves the frozen full event bundle in the required "
            "three-window check and remains positive versus core. It is not a live "
            "or default promotion until implemented in a shared event policy with "
            "run/backtester parity tests and forward closed-outcome attribution."
        )
    else:
        decision_rationale = (
            "Rejected: the broad benchmark momentum participation gate did not improve "
            "the frozen full event bundle with enough three-window robustness and/or "
            "did not preserve the required positive edge versus core."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "candidate_pool_allocation_gate",
        "mechanism_family": "external_event_candidate_pool",
        "hypothesis": (
            "The frozen event overlay bundle may be higher quality when broad benchmark "
            "momentum is positive before entry; filtering event overlay trades by "
            "max(SPY, QQQ) 20-day return > 0 may remove weak-tape event losses without "
            "changing core A/B behavior."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_allocation",
            "entry_exit_ranking_or_allocation": "satellite allocation",
            "why_this_now": (
                "LLM soft-ranking, Form 4, options, post-news continuation, and raw "
                "universe expansion remain sparse, rejected, or forward-only. The event "
                "bundle is the strongest recent replay alpha lead, and this tests one "
                "orthogonal OHLCV state qualifier instead of retuning event sources."
            ),
        },
        "historical_experiment_check": {
            "similar_failures_checked": [
                "exp-20260507-022 event pre-entry relative-momentum notional tilt rejected",
                "exp-20260509-014 state-surface benchmark momentum gate accepted as replay-only lead",
                "exp-20260509-015 benchmark+core gate rejected for adding a second filter",
            ],
            "why_not_simple_repeat": (
                "This is not a source, threshold, or notional retune. It applies the "
                "already-useful broad benchmark participation concept to the separate "
                "event-bundle sleeve using a single zero-line gate."
            ),
            "mechanism_insight_conflict": (
                "No conflict found: it avoids LLM ranking, earnings/revisions, event "
                "source pruning, Form 4 cluster retunes, options overlays, and raw ticker expansion."
            ),
        },
        "parameters": {
            "benchmark_tickers": list(BENCHMARK_TICKERS),
            "lookback_days": LOOKBACK_DAYS,
            "gate": "max(SPY_20d_return_before_entry, QQQ_20d_return_before_entry) > 0",
            "event_sources_unchanged": True,
            "event_notional_unchanged": True,
            "hold_days_unchanged": True,
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window.get("state_note") for label, window in WINDOWS.items()
        },
        "core_metrics": core_metrics,
        "full_event_metrics": full_event_metrics,
        "gated_event_metrics": gated_event_metrics,
        "delta_vs_full_event": delta_vs_full,
        "delta_vs_core_full_event": delta_vs_core_full,
        "delta_vs_core_gated": delta_vs_core_gated,
        "gate4_vs_full_by_window": gate4_vs_full_by_window,
        "coverage": coverage,
        "full_event_overlay": full_event_overlay,
        "gated_event_overlay": gated_event_overlay,
        "expected_value_score_delta": delta_vs_full["aggregate_ev_delta"],
        "single_causal_variable": (
            "benchmark-momentum participation gate on the frozen event-bundle overlay"
        ),
        "decision_rationale": decision_rationale,
        "risk_of_change": (
            "May block event-driven winners that work despite weak broad indexes; "
            "promotion would need forward closed-outcome replacement attribution."
        ),
        "llm_metrics": {
            "llm_behavior_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking outcome joins remain too sparse; this alpha test uses "
                "fully replayable benchmark OHLCV and frozen event candidates."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "note": (
                "Replay-only experiment. A positive version needs shared event policy "
                "and run/backtester parity before affecting live/default behavior."
            ),
        },
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking, options, Form 4 cluster promotion, post-news "
            "continuation, 10-K/universe expansion, core ranking, and source pruning "
            "because recent records mark them data-limited, rejected, forward-only, "
            "or too close to no-repeat zones."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
    }


def main() -> int:
    payload = build_payload()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "single_causal_variable": payload["single_causal_variable"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "allowed_scope": payload["related_files"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _build_artifact(payload))
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "delta_vs_full_event": payload["delta_vs_full_event"],
        "delta_vs_core_gated": payload["delta_vs_core_gated"],
    }), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
