"""Replay executive-role Form 4 purchases as a bounded event overlay.

This alpha-search experiment keeps the core A/B stack unchanged and changes one
event qualification variable inside the existing PIT-safe Form 4 forward queue:
only events with a CEO, CFO, or president title are allowed into the standalone
10k-notional event overlay. The goal is to test whether a free SEC role-quality
field improves candidate-pool replacement value without adding noisy tickers or
an LLM dependency.
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
    _candidate_trade,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
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


EXP_ID = "exp-20260529-002"
STEM = "form4_exec_role_quality_forward_queue"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in WINDOWS.values():
        path = REPO_ROOT / window["snapshot"]
        payload = _json_load(path, {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


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


def _exec_role_quality(event: dict[str, Any]) -> bool:
    return bool(event.get("any_ceo_cfo_or_president"))


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
    max_drawdown_drift = max(
        float(after[label].get("max_drawdown_pct") or 0.0)
        - float(before[label].get("max_drawdown_pct") or 0.0)
        for label in before
    )
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
        "max_drawdown_drift": round(max_drawdown_drift, 6),
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("exec_role_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "single_ticker_positive_share": None,
            "positive_pnl_hhi": None,
            "positive_pnl_by_ticker": {},
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    hhi = sum(value * value for value in shares.values())
    return {
        "single_ticker_positive_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(hhi, 6),
        "positive_pnl_by_ticker": {ticker: round(value, 2) for ticker, value in sorted(by_ticker.items())},
    }


def _gate_result(
    core_delta: dict[str, Any],
    refinement_delta: dict[str, Any],
    core_gate_by_window: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("exec_role_selected_trade_count") or 0) for row in details.values())
    concentration = _positive_pnl_concentration(details)
    single_share = concentration["single_ticker_positive_share"]
    hhi = concentration["positive_pnl_hhi"]
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
    drawdown_ok = core_delta["max_drawdown_drift"] <= 0.005
    sample_ok = (
        selected >= 8
        and (single_share is None or single_share <= 0.50)
        and (hhi is None or hhi <= 0.35)
    )
    return {
        "passed": bool(material and no_core_ev_regression and improves_raw and drawdown_ok and sample_ok),
        "material_vs_core": bool(material),
        "no_core_ev_regression": bool(no_core_ev_regression),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": "<= 0.005",
        "exec_role_selected_event_trades": selected,
        "sample_guard_min_trades": 8,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": "<= 0.35",
        "sample_guard_passed": bool(sample_ok),
        "by_window_vs_core": core_gate_by_window,
        "positive_pnl_by_ticker": concentration["positive_pnl_by_ticker"],
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
        "# Form 4 Executive-Role Forward Queue",
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
        "| Window | Core EV | Raw Form4 EV | Exec-role EV | Delta vs raw | Delta vs core | Core PnL | Exec-role PnL | Event PnL | Trades |",
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
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "title": "Form 4 executive-role forward queue",
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


def _write_tickets(payload: dict[str, Any]) -> None:
    ticket = _ticket(payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    events = _annotate_status(_load_forward_events(), prices)
    raw_candidates = _event_candidates(events, prices, lambda event: True)
    exec_role_candidates = _event_candidates(events, prices, _exec_role_quality)

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
        exec_selected, exec_skipped = _select_event_trades(
            exec_role_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = _event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        exec_curve = _event_equity_curve(
            exec_selected,
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
            _combined_metrics(result, exec_curve, exec_selected)
            if exec_selected
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
            "exec_role_event_count": sum(1 for row in scoped_events if _exec_role_quality(row)),
            "non_exec_role_event_count": sum(1 for row in scoped_events if not _exec_role_quality(row)),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "exec_role_price_ready_count": sum(
                1
                for row in exec_role_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "exec_role_selected_trade_count": len(exec_selected),
            "raw_skipped_count": len(raw_skipped),
            "exec_role_skipped_count": len(exec_skipped),
            "exec_role_selected_trades": exec_selected,
            "raw_selected_trades": raw_selected,
            "exec_role_skipped_candidates": exec_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, core_gate_by_window, details)

    if gate["passed"]:
        decision = "accepted_default_off_form4_exec_role_forward_queue"
        status = "accepted_default_off"
        rationale = (
            "Executive-role Form 4 forward-queue events improved the raw Form 4 overlay "
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
            "Executive-role Form 4 events were positive versus core, but the result "
            "did not clear all materiality, raw-queue improvement, drawdown, sample, "
            "and concentration gates. Keep Form 4 role quality in forward observation "
            "rather than promoting another frozen-window paper rule."
        )
    else:
        decision = "rejected_form4_exec_role_forward_queue"
        status = "rejected"
        rationale = (
            "Executive-role Form 4 forward-queue events failed to improve enough "
            "canonical windows or introduced EV/PnL regression versus core or raw Form 4."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 forward-queue events with a CEO, CFO, or president title "
            "may be a cleaner standalone insider-buying alpha than the raw meaningful "
            "purchase queue, because senior operating executives should have stronger "
            "information content than broad insider-role metadata."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_role_quality_event_satellite",
        "trial_family": "form4_role_quality_event_satellite",
        "trial_variant_id": EXP_ID,
        "changed_variable": "form4_exec_role_quality_forward_queue_v1",
        "single_causal_variable": (
            "any_ceo_cfo_or_president qualifier on the existing Form 4 forward queue"
        ),
        "gate_questions": {
            "alpha_hypothesis": (
                "Entry/candidate overlay: test a free SEC Form 4 role-quality discriminator "
                "using PIT-safe executive-title metadata."
            ),
            "prior_similar_experiments": [
                "exp-20260504-034: raw >=500k Form 4 satellite positive but immaterial.",
                "exp-20260512-901: single-owner Form 4 positive but not material.",
                "exp-20260512-108: single-owner + pre-entry RS failed to improve enough.",
                "exp-20260512-101: multi-owner cluster remained underpowered.",
            ],
            "single_causal_variable": (
                "Only the executive-role qualifier changes; core universe, entries, exits, "
                "ranking, sizing, Form 4 threshold, notional, capacity, hold days, and "
                "LLM/news remain locked."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus raw Form 4 and core, avoid core EV "
                "regression across windows, keep survival above 5%, and pass drawdown, "
                "materiality, sample, and concentration guards."
            ),
            "reproducibility": (
                "This script reruns core, raw Form 4, and executive-role Form 4 overlays "
                "across the three docs/backtesting.md fixed snapshots."
            ),
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "required_role_field": "any_ceo_cfo_or_president == true",
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "fields_checked": [
                "Form 4 ticker",
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 any_ceo_cfo_or_president",
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
            "why_not_llm": (
                "LLM soft-ranking remains sample-limited; Form 4 has replayable PIT-safe "
                "executive-role metadata from a free SEC source."
            ),
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
                "A shared default-off Form 4 executive-role queue/paper adapter must be "
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
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(Path(__file__)),
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_tickets(payload)
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
                "drawdown_guard_passed",
                "exec_role_selected_event_trades",
                "sample_guard_passed",
                "single_ticker_positive_share",
                "positive_pnl_hhi",
            )
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
