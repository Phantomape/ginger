"""Replay single-owner Form 4 purchases as a bounded event overlay.

This alpha-search experiment keeps the core A/B stack unchanged and changes one
event qualification variable inside the existing PIT-safe Form 4 forward queue:
only events with exactly one reporting owner are allowed into the standalone
10k-notional event overlay. Prior Form 4 runs found positive but underpowered
results; this tests whether avoiding multi-owner cluster events improves
replacement quality without adding noisy tickers or an LLM dependency.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
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
    _select_event_trades,
    _write_json,
)
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION,
    aggregate_purchase_events,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXP_ID = "exp-20260512-901"
STEM = "form4_single_owner_forward_queue"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _load_forward_events() -> list[dict[str, Any]]:
    if not FORM4_TRANSACTIONS_PATH.exists():
        return []
    rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    out: list[dict[str, Any]] = []
    for event in events:
        usable = _date10(event.get("usable_trade_date"))
        window = _window_name(usable)
        if not window:
            continue
        out.append({**event, "window": window})
    return sorted(out, key=lambda row: (_date10(row.get("usable_trade_date")), str(row.get("ticker") or "")))


def _annotate_status(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    annotated = []
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        status = "event_ready" if ticker in prices else "missing_price_history"
        annotated.append({**event, "ticker": ticker, "status": status})
    return annotated


def _single_owner(event: dict[str, Any]) -> bool:
    return int(event.get("owner_count") or 0) == 1


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    predicate: Callable[[dict[str, Any]], bool],
) -> list[dict[str, Any]]:
    return [_candidate_trade(event, prices) for event in events if predicate(event)]


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    return {
        "before_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "before_pnl_sum": round(before_pnl, 2),
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


def _single_ticker_positive_share(details: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("single_owner_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _gate_result(
    core_delta: dict[str, Any],
    refinement_delta: dict[str, Any],
    core_gate_by_window: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("single_owner_selected_trade_count") or 0) for row in details.values())
    single_share = _single_ticker_positive_share(details)
    material = (
        core_delta["aggregate_ev_delta_pct"] is not None
        and core_delta["aggregate_ev_delta_pct"] > 0.10
    ) or (
        core_delta["aggregate_pnl_delta_pct"] is not None
        and core_delta["aggregate_pnl_delta_pct"] > 0.05
    )
    no_core_ev_regression = core_delta["windows_ev_regressed"] == 0
    improves_raw = (
        refinement_delta["aggregate_ev_delta"] > 0.0
        and refinement_delta["aggregate_pnl_delta"] > 0.0
        and refinement_delta["windows_ev_regressed"] == 0
    )
    sample_ok = selected >= 8 and (single_share is None or single_share <= 0.50)
    return {
        "passed": bool(material and no_core_ev_regression and improves_raw and sample_ok),
        "material_vs_core": bool(material),
        "no_core_ev_regression": bool(no_core_ev_regression),
        "improves_vs_raw_form4": bool(improves_raw),
        "single_owner_selected_event_trades": selected,
        "sample_guard_min_trades": 8,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "sample_guard_passed": bool(sample_ok),
        "by_window_vs_core": core_gate_by_window,
    }


def _position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        return {"passed": False, "reason": "open_positions payload is not a list/object with positions"}
    missing = []
    for idx, position in enumerate(positions):
        if not isinstance(position, dict):
            missing.append({"index": idx, "reason": "not_object"})
            continue
        absent = [
            field
            for field in ("entry_date", "target_price")
            if position.get(field) in (None, "")
        ]
        if absent:
            missing.append({
                "index": idx,
                "ticker": position.get("ticker"),
                "missing_fields": absent,
            })
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
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
        "# Form 4 Single-Owner Forward Queue",
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
        "| Window | Core EV | Raw Form4 EV | Single-owner EV | Delta vs raw | Delta vs core | Core PnL | Single-owner PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["core_baseline_metrics"][label]
        raw = payload["raw_form4_metrics"][label]
        after = payload["after_metrics"][label]
        raw_delta = payload["deltas_vs_raw_form4"][label]
        core_delta = payload["deltas_vs_core"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | {raw['expected_value_score']} | "
            f"{after['expected_value_score']} | {raw_delta['expected_value_score']} | "
            f"{core_delta['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{core['trade_count']} -> {after['trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate vs Raw Form4",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_raw_form4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Aggregate vs Core",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_core"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
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
        "title": "Form 4 single-owner forward queue",
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
            "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
            "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
            "decision": payload["decision"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    events = _annotate_status(_load_forward_events(), prices)
    raw_candidates = _event_candidates(events, prices, lambda event: True)
    single_owner_candidates = _event_candidates(events, prices, _single_owner)

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    core_gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        raw_selected, raw_skipped = _select_event_trades(
            raw_candidates,
            start=window["start"],
            end=window["end"],
        )
        single_selected, single_skipped = _select_event_trades(
            single_owner_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = _event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        single_curve = _event_equity_curve(
            single_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        core_baseline[label] = _core_metrics(result)
        raw_metrics[label] = (
            _combined_metrics(result, raw_curve, raw_selected)
            if raw_selected
            else dict(core_baseline[label])
        )
        after_metrics[label] = (
            _combined_metrics(result, single_curve, single_selected)
            if single_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = _delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = _delta(core_baseline[label], after_metrics[label])
        core_gate_by_window[label] = _gate4(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "single_owner_event_count": sum(1 for row in scoped_events if _single_owner(row)),
            "multi_owner_event_count": sum(1 for row in scoped_events if not _single_owner(row)),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "single_owner_price_ready_count": sum(
                1
                for row in single_owner_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "single_owner_selected_trade_count": len(single_selected),
            "raw_skipped_count": len(raw_skipped),
            "single_owner_skipped_count": len(single_skipped),
            "single_owner_selected_trades": single_selected,
            "raw_selected_trades": raw_selected,
            "single_owner_skipped_candidates": single_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, core_gate_by_window, details)

    if gate["passed"]:
        decision = "accepted_default_off_form4_single_owner_forward_queue"
        status = "accepted_default_off"
        rationale = (
            "Single-owner Form 4 forward-queue events improved the raw Form 4 overlay "
            "and cleared the core materiality/sample/concentration gates. Promotion "
            "would still require a shared default-off run/backtest adapter before any "
            "trade-enabled use."
        )
    elif (
        aggregate_vs_core["aggregate_ev_delta"] > 0
        and aggregate_vs_core["aggregate_pnl_delta"] > 0
        and aggregate_vs_core["windows_ev_regressed"] == 0
    ):
        decision = "rejected_positive_sample_not_material"
        status = "rejected"
        rationale = (
            "Single-owner Form 4 forward-queue events improved the raw Form 4 overlay "
            "and were positive versus core, but the lift did not clear materiality. "
            "Keep Form 4 in forward observation rather than adding another paper "
            "promotion from the frozen sample."
        )
    else:
        decision = "rejected_form4_single_owner_forward_queue"
        status = "rejected"
        rationale = (
            "Single-owner Form 4 forward-queue events failed to improve enough "
            "canonical windows or introduced EV/PnL regression."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 forward-queue events with exactly one reporting owner "
            "may be a cleaner standalone insider-buying alpha than multi-owner "
            "clusters, because a focused open-market purchase can signal individual "
            "conviction while clustered filings may reflect compensation or corporate "
            "governance timing rather than incremental replacement value."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_single_owner_insider_buy_event_satellite",
        "single_causal_variable": "owner_count == 1 qualifier on the existing Form 4 forward queue",
        "gate_questions": {
            "alpha_hypothesis": (
                "Entry/candidate overlay: test a Form 4 event-quality discriminator "
                "using PIT-safe owner_count metadata."
            ),
            "prior_similar_experiments": [
                "exp-20260504-034: raw >=500k Form 4 satellite positive but immaterial.",
                "exp-20260508-028: clustered Form 4 satellite positive but immaterial.",
                "exp-20260512-017: clustered Form 4 + pre-entry RS positive but immaterial.",
            ],
            "single_causal_variable": (
                "Only the Form 4 owner-count qualifier changes; core universe, "
                "entries, exits, ranking, sizing, Form 4 threshold, notional, "
                "capacity, hold days, and LLM/news remain locked."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus raw Form 4 and core, avoid "
                "core EV regression across windows, keep survival above 5%, and pass "
                "materiality/sample/concentration guards."
            ),
            "reproducibility": (
                "This script reruns core, raw Form 4, and single-owner Form 4 overlays "
                "across the three docs/backtesting.md fixed snapshots."
            ),
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "owner_count_required": 1,
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "fields_checked": [
                "Form 4 ticker",
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 owner_count",
                "Form 4 transaction flags",
                "ticker OHLCV open and close",
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
                "Form 4 purchase-value threshold",
                "event notional",
                "event holding period",
                "event capacity",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows",
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_metrics": core_baseline,
        },
        "gate2": _position_field_check(),
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in core_baseline.values()
            ),
            "passed": min(
                float(row.get("survival_rate") or 0.0)
                for row in core_baseline.values()
            ) >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "event_details": details,
        "decision_rationale": rationale,
        "expected_value_score_delta": {
            label: deltas_vs_core[label]["expected_value_score"]
            for label in WINDOWS
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains sample-limited; Form 4 has replayable PIT-safe owner-count metadata.",
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
            "live_slots_changed": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 single-owner queue/paper adapter must be "
                "wired in run.py and replay before any trade-enabled promotion."
            ),
        },
        "data_source": {
            "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
            "pit_status": "uses Form 4 accepted_at/usable_trade_date and fixed OHLCV snapshots",
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
        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
        "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
        "gate4": {
            key: payload["gate4"][key]
            for key in (
                "passed",
                "material_vs_core",
                "no_core_ev_regression",
                "improves_vs_raw_form4",
                "single_owner_selected_event_trades",
                "sample_guard_passed",
                "single_ticker_positive_share",
            )
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
