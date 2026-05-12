"""Replay clustered Form 4 purchases with pre-entry RS confirmation.

This alpha-search experiment keeps the core A/B stack unchanged and changes one
event qualification variable versus the prior clustered Form 4 satellite replay:
a clustered meaningful open-market purchase event must also show positive
one-session relative strength versus SPY before the usable-trade-date entry.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    HOLD_DAYS,
    INITIAL_CAPITAL,
    MAX_EVENT_POSITIONS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _candidate_trade,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_price_map,
    _repo_rel,
    _round,
    _select_event_trades,
    _write_json,
)
from form4_event_queue import (  # noqa: E402
    BASE_MEANINGFUL_PURCHASE_VALUE,
    aggregate_purchase_events,
    load_form4_transaction_rows,
)


EXP_ID = "exp-20260512-017"
STEM = "form4_cluster_preentry_rs"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
COMBINED_FORM4_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _parse_date(value: Any):
    text = _date10(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _load_cluster_events(prices: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], Path | None]:
    path = COMBINED_FORM4_PATH
    if not path.exists():
        return [], None

    rows = load_form4_transaction_rows(path)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if event.get("meaningful_purchase_v1")
    ]

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_ticker[str(event.get("ticker") or "").upper()].append(event)

    cluster_events: list[dict[str, Any]] = []
    for ticker, ticker_events in by_ticker.items():
        ticker_events.sort(key=lambda item: _date10(item.get("usable_trade_date")))
        for idx, event in enumerate(ticker_events):
            current = _parse_date(event.get("usable_trade_date"))
            prior_30 = [
                prior
                for prior in ticker_events[: idx + 1]
                if current
                and _parse_date(prior.get("usable_trade_date"))
                and 0 <= (current - _parse_date(prior.get("usable_trade_date"))).days <= 30
            ]
            owner_count_30 = sum(int(prior.get("owner_count") or 0) for prior in prior_30)
            clustered = (
                len(prior_30) >= 2
                or owner_count_30 >= 2
                or int(event.get("owner_count") or 0) >= 2
            )
            if not clustered:
                continue
            usable = _date10(event.get("usable_trade_date"))
            window = _window_name(usable)
            if not window:
                continue
            status = "event_ready" if ticker in prices else "missing_price_history"
            cluster_events.append(
                {
                    **event,
                    "ticker": ticker,
                    "window": window,
                    "status": status,
                    "cluster_buying_30d": True,
                    "cluster_buying_30d_event_count": len(prior_30),
                    "cluster_buying_30d_owner_count": owner_count_30,
                }
            )
    return sorted(
        cluster_events,
        key=lambda row: (_date10(row.get("usable_trade_date")), str(row.get("ticker") or "")),
    ), path


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") >= target:
            return idx
    return None


def _preentry_rs_annotation(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable = _date10(event.get("usable_trade_date"))
    rows = prices.get(ticker)
    spy_rows = prices.get("SPY")
    if not ticker or not usable:
        return {
            **event,
            "preentry_rs_confirmed": False,
            "preentry_rs_status": "missing_ticker_or_usable_date",
        }
    if not rows or not spy_rows:
        return {
            **event,
            "preentry_rs_confirmed": False,
            "preentry_rs_status": "missing_price_history",
        }

    entry_idx = _first_index_on_or_after(rows, usable)
    spy_entry_idx = _first_index_on_or_after(spy_rows, usable)
    if entry_idx is None or spy_entry_idx is None:
        return {
            **event,
            "preentry_rs_confirmed": False,
            "preentry_rs_status": "missing_entry_anchor",
        }
    if entry_idx < 2 or spy_entry_idx < 2:
        return {
            **event,
            "preentry_rs_confirmed": False,
            "preentry_rs_status": "insufficient_preentry_history",
        }

    base = rows[entry_idx - 2]
    end = rows[entry_idx - 1]
    spy_base = spy_rows[spy_entry_idx - 2]
    spy_end = spy_rows[spy_entry_idx - 1]
    if not base.get("close") or not end.get("close") or not spy_base.get("close") or not spy_end.get("close"):
        return {
            **event,
            "preentry_rs_confirmed": False,
            "preentry_rs_status": "missing_preentry_close",
        }

    ticker_return = float(end["close"]) / float(base["close"]) - 1.0
    spy_return = float(spy_end["close"]) / float(spy_base["close"]) - 1.0
    excess = ticker_return - spy_return
    return {
        **event,
        "preentry_rs_status": "ready",
        "preentry_rs_confirmed": excess > 0.0,
        "preentry_rs_base_date": base["date"],
        "preentry_rs_end_date": end["date"],
        "preentry_1d_return_pct": round(ticker_return * 100.0, 6),
        "preentry_1d_spy_return_pct": round(spy_return * 100.0, 6),
        "preentry_1d_excess_vs_spy_pct": round(excess * 100.0, 6),
    }


def _with_preentry_rs_confirmation(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [_preentry_rs_annotation(event, prices) for event in events]


def _aggregate_delta(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    return {
        "baseline_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "baseline_pnl_sum": round(before_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - before_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            > float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in before
            if float(after[label].get("expected_value_score") or 0.0)
            < float(before[label].get("expected_value_score") or 0.0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            > float(before[label].get("total_pnl") or 0.0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in before
            if float(after[label].get("total_pnl") or 0.0)
            < float(before[label].get("total_pnl") or 0.0)
        ),
    }


def _single_ticker_positive_share(event_details: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in event_details.values():
        for trade in detail.get("selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _gate_result(
    gate4: dict[str, Any],
    aggregate_delta: dict[str, Any],
    event_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    touched = sum(int(row.get("selected_trade_count") or 0) for row in event_details.values())
    single_share = _single_ticker_positive_share(event_details)
    material = (
        aggregate_delta["aggregate_ev_delta_pct"] is not None
        and aggregate_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        aggregate_delta["aggregate_pnl_delta_pct"] is not None
        and aggregate_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    zero_ev_regression = aggregate_delta["windows_ev_regressed"] == 0
    sample_ok = touched >= 8 and (single_share is None or single_share <= 0.50)
    return {
        "passed": bool(material and zero_ev_regression and sample_ok),
        "material_aggregate": bool(material),
        "zero_ev_regression": bool(zero_ev_regression),
        "selected_event_trades": touched,
        "sample_guard_min_trades": 8,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "sample_guard_passed": bool(sample_ok),
        "by_window": gate4,
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Cluster Pre-Entry RS",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Baseline EV | Confirmed EV | Delta EV | Baseline PnL | Confirmed PnL | Event PnL | Trades | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']} | {after['expected_value_score']} | "
            f"{delta['expected_value_score']} | ${before['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{before['trade_count']} -> {after['trade_count']} | "
            f"{before['win_rate']:.2%} -> {after['win_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "```json",
            json.dumps(payload["aggregate_delta"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXP_ID,
        "title": "Form 4 cluster pre-entry RS",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "report": _repo_rel(ARTIFACT_MD),
            "aggregate_delta": payload["aggregate_delta"],
            "decision": payload["decision"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    cluster_events, event_file = _load_cluster_events(prices)
    annotated_events = _with_preentry_rs_confirmation(cluster_events, prices)
    confirmed_events = [
        event
        for event in annotated_events
        if event.get("preentry_rs_status") == "ready" and bool(event.get("preentry_rs_confirmed"))
    ]
    event_candidates = [_candidate_trade(event, prices) for event in confirmed_events]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas: dict[str, dict[str, Any]] = OrderedDict()
    gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
    event_details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = _select_event_trades(
            event_candidates,
            start=window["start"],
            end=window["end"],
        )
        event_curve = _event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = (
            _combined_metrics(result, event_curve, selected)
            if selected
            else dict(before_metrics[label])
        )
        deltas[label] = _delta(before_metrics[label], after_metrics[label])
        gate_by_window[label] = _gate4(before_metrics[label], after_metrics[label])
        scoped_annotated = [
            row
            for row in annotated_events
            if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
        ]
        event_details[label] = {
            "raw_cluster_event_count": len(scoped_annotated),
            "preentry_confirmed_event_count": sum(
                1 for row in scoped_annotated if bool(row.get("preentry_rs_confirmed"))
            ),
            "preentry_rejected_event_count": sum(
                1
                for row in scoped_annotated
                if row.get("preentry_rs_status") == "ready" and not row.get("preentry_rs_confirmed")
            ),
            "preentry_status_counts": dict(
                sorted(
                    {
                        status: sum(
                            1
                            for row in scoped_annotated
                            if row.get("preentry_rs_status") == status
                        )
                        for status in {row.get("preentry_rs_status") for row in scoped_annotated}
                    }.items()
                )
            ),
            "candidate_count": sum(
                1
                for row in event_candidates
                if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "price_ready_count": sum(
                1
                for row in event_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(
                sorted(
                    {
                        reason: sum(1 for row in skipped if row["reason"] == reason)
                        for reason in {row["reason"] for row in skipped}
                    }.items()
                )
            ),
            "selected_trades": selected,
            "skipped_candidates": skipped[:20],
        }

    aggregate_delta = _aggregate_delta(before_metrics, after_metrics)
    gate = _gate_result(gate_by_window, aggregate_delta, event_details)

    if gate["passed"]:
        decision = "accepted_for_default_off_paper_promotion"
        status = "accepted_default_off"
        rationale = (
            "Clustered Form 4 buying with pre-entry relative-strength confirmation cleared "
            "material aggregate lift, zero EV regression, and the pre-registered "
            "sample/concentration guard. Promotion would still require a shared "
            "default-off run/backtest adapter before trade-enabled use."
        )
    elif (
        aggregate_delta["aggregate_ev_delta"] > 0
        and aggregate_delta["aggregate_pnl_delta"] > 0
        and aggregate_delta["windows_ev_regressed"] == 0
    ):
        decision = "rejected_positive_sample_not_material"
        status = "rejected"
        rationale = (
            "Clustered Form 4 buying with pre-entry relative-strength confirmation was "
            "directionally positive, but it did not clear materiality and sample/"
            "concentration guards strongly enough to justify another event sleeve promotion."
        )
    else:
        decision = "rejected"
        status = "rejected"
        rationale = (
            "Pre-entry relative-strength confirmation did not improve enough windows or "
            "introduced EV/PnL regression under the canonical three-window replay."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Clustered PIT-safe Form 4 meaningful open-market purchases whose ticker "
            "outperformed SPY during the last complete session before the usable entry "
            "may be a higher-quality standalone event alpha than raw clustered Form 4 "
            "buying, because price confirmation can separate informed accumulation "
            "from stale insider signals without adding noisy tickers."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_clustered_insider_buy_preentry_rs_event_satellite",
        "single_causal_variable": "positive 1-session ticker excess return versus SPY before clustered Form 4 usable_trade_date",
        "parameters": {
            "base_meaningful_purchase_min_total_value": BASE_MEANINGFUL_PURCHASE_VALUE,
            "cluster_window_calendar_days": 30,
            "cluster_definition": "same ticker has >=2 meaningful event days in 30d, or owner_count_30d >=2, or current event owner_count >=2",
            "preentry_rs_definition": "close-to-close ticker return over the last complete session before entry exceeds SPY close-to-close return over the same relative session",
            "preentry_rs_threshold_excess_vs_spy_pct": "> 0.0",
            "event_notional_usd": 10_000.0,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "fields_checked": [
                "Form 4 ticker",
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 owner_count",
                "ticker OHLCV close before usable_trade_date",
                "SPY OHLCV close before usable_trade_date",
            ],
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM/news replay settings",
                "Form 4 transaction parser",
                "event notional",
                "event holding period",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260504-034": "Prior >=500k Form 4 satellite was positive but immaterial.",
            "exp-20260508-025": "Current shadow audit showed cluster_30d meaningful purchases had stronger 5/10/20d forward returns than broad meaningful purchases.",
            "exp-20260508-028": "Raw clustered Form 4 satellite improved 2/3 windows with zero EV regression, but aggregate EV +3.63% and PnL +2.05% failed materiality.",
            "why_not_simple_repeat": "This does not retune purchase-value thresholds, owner roles, notional, capacity, or hold days; it tests one orthogonal pre-entry price-confirmation discriminator.",
            "mechanism_insight_check": "Avoids LLM-ranking, options, 10-K, gap-cancel, add-on heat, sector-cap, and noisy ticker expansion blocked zones.",
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "deltas": deltas,
        "aggregate_delta": aggregate_delta,
        "gate4": gate,
        "event_details": event_details,
        "decision_rationale": rationale,
        "expected_value_score_delta": {
            label: deltas[label]["expected_value_score"]
            for label in WINDOWS
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains sample-limited; this tests a deterministic PIT-safe SEC event source.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 pre-entry RS queue/paper adapter must be "
                "wired in run.py and replay before any trade-enabled promotion."
            ),
        },
        "data_source": {
            "form4_transactions_path": _repo_rel(event_file) if event_file else None,
            "pit_status": "uses accepted_at/usable_trade_date plus OHLCV closes fully before entry",
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(Path(__file__)),
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": payload["decision"],
        "aggregate_delta": payload["aggregate_delta"],
        "gate4": {
            key: payload["gate4"][key]
            for key in (
                "passed",
                "material_aggregate",
                "zero_ev_regression",
                "selected_event_trades",
                "sample_guard_passed",
                "single_ticker_positive_share",
            )
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
