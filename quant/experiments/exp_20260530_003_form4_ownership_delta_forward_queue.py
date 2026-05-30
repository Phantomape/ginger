"""Replay Form 4 ownership-delta purchases as a bounded event overlay.

This experiment keeps the core strategy and the raw Form 4 forward queue fixed.
The single tested variable is whether at least one qualifying open-market buy
in the event increased that insider's reported beneficial holdings by 10% or
more, computed from Form 4 transaction shares divided by shares owned following
the transaction.
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


EXP_ID = "exp-20260530-003"
STEM = "form4_ownership_delta_forward_queue"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

OWNERSHIP_DELTA_FLOOR = 0.10

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
    if math.isnan(number) or math.isinf(number):
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
        payload = _json_load(REPO_ROOT / window["snapshot"], {})
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


def _eligible_purchase_row(row: dict[str, Any]) -> bool:
    value = _float_or_none(row.get("transaction_value")) or 0.0
    return (
        bool(row.get("open_market_purchase_flag"))
        and bool(row.get("pit_safe_flag"))
        and str(row.get("acquired_disposed_code") or "").upper() == "A"
        and not bool(row.get("10b5_1_flag"))
        and not bool(row.get("option_exercise_flag"))
        and bool(row.get("is_officer") or row.get("is_director") or row.get("is_10pct_owner"))
        and value > 0.0
    )


def _ownership_delta_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    by_event: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not _eligible_purchase_row(row):
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable = _date10(row.get("usable_trade_date"))
        shares = _float_or_none(row.get("shares"))
        shares_after = _float_or_none(row.get("shares_owned_following_transaction"))
        if not ticker or not usable or not shares or not shares_after or shares_after <= 0.0:
            continue
        fraction = shares / shares_after
        event = by_event.setdefault(
            (ticker, usable),
            {
                "max_ownership_delta_fraction": 0.0,
                "sum_purchase_shares": 0.0,
                "sum_reported_after_shares": 0.0,
                "ownership_delta_transaction_count": 0,
                "sample_ownership_delta_fractions": [],
            },
        )
        event["max_ownership_delta_fraction"] = max(
            float(event["max_ownership_delta_fraction"]),
            fraction,
        )
        event["sum_purchase_shares"] += shares
        event["sum_reported_after_shares"] += shares_after
        event["ownership_delta_transaction_count"] += 1
        samples = event["sample_ownership_delta_fractions"]
        if len(samples) < 5:
            samples.append(round(fraction, 6))
    for event in by_event.values():
        denom = float(event["sum_reported_after_shares"] or 0.0)
        event["aggregate_ownership_delta_fraction"] = (
            round(float(event["sum_purchase_shares"]) / denom, 6)
            if denom > 0.0
            else None
        )
        event["max_ownership_delta_fraction"] = round(
            float(event["max_ownership_delta_fraction"]),
            6,
        )
        event["sum_purchase_shares"] = round(float(event["sum_purchase_shares"]), 4)
        event["sum_reported_after_shares"] = round(float(event["sum_reported_after_shares"]), 4)
    return by_event


def _load_forward_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not FORM4_TRANSACTIONS_PATH.exists():
        return [], {"source_status": "missing_form4_transactions"}
    rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    ownership = _ownership_delta_index(rows)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    raw_events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    events = []
    for event in raw_events:
        ticker = str(event.get("ticker") or "").upper()
        usable = _date10(event.get("usable_trade_date"))
        window = _window_name(usable)
        if not window:
            continue
        delta = ownership.get((ticker, usable), {})
        max_delta = _float_or_none(delta.get("max_ownership_delta_fraction")) or 0.0
        events.append(
            {
                **event,
                **delta,
                "ticker": ticker,
                "usable_trade_date": usable,
                "window": window,
                "ownership_delta_ge_10pct": max_delta >= OWNERSHIP_DELTA_FLOOR,
            }
        )
    diagnostics = {
        "source_status": "loaded",
        "transaction_rows": len(rows),
        "raw_forward_event_count": len(events),
        "events_with_ownership_delta": sum(
            1 for event in events if event.get("ownership_delta_transaction_count")
        ),
        "ownership_delta_floor": OWNERSHIP_DELTA_FLOOR,
        "ownership_delta_floor_event_count": sum(
            1 for event in events if event.get("ownership_delta_ge_10pct")
        ),
    }
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    ownership_delta_only: bool,
) -> list[dict[str, Any]]:
    return [
        _candidate_trade(event, prices)
        for event in events
        if not ownership_delta_only or event.get("ownership_delta_ge_10pct")
    ]


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
        for trade in detail.get("ownership_delta_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0.0:
        return {
            "single_ticker_positive_share": None,
            "positive_pnl_hhi": None,
            "positive_pnl_by_ticker": {},
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "single_ticker_positive_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(value * value for value in shares.values()), 6),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(by_ticker.items())
        },
    }


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("ownership_delta_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("ownership_delta_selected_trade_count") or 0) > 0
    ]
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
    improves_core = (
        core_delta["aggregate_ev_delta"] > 0.0
        and core_delta["aggregate_pnl_delta"] > 0.0
        and core_delta["windows_ev_regressed"] == 0
        and core_delta["windows_pnl_regressed"] == 0
    )
    improves_raw = (
        raw_delta["aggregate_ev_delta"] > 0.0
        and raw_delta["aggregate_pnl_delta"] > 0.0
        and raw_delta["windows_ev_regressed"] == 0
        and raw_delta["windows_pnl_regressed"] == 0
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= 0.005
    sample_ok = (
        selected >= 8
        and len(target_windows) >= 3
        and (single_share is None or single_share <= 0.50)
        and (hhi is None or hhi <= 0.35)
    )
    failed = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_raw:
        failed.append("does_not_improve_raw_form4_queue")
    if not material:
        failed.append("not_material_vs_core")
    if not drawdown_ok:
        failed.append("drawdown_drift_too_high")
    if selected < 8:
        failed.append("target_sample_too_small")
    if len(target_windows) < 3:
        failed.append("target_window_coverage_too_small")
    if single_share is not None and single_share > 0.50:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > 0.35:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed": bool(material and improves_core and improves_raw and drawdown_ok and sample_ok),
        "failed_reasons": failed,
        "material_vs_core": bool(material),
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": "<= 0.005",
        "ownership_delta_selected_event_trades": selected,
        "target_trade_count_min": 8,
        "target_windows": target_windows,
        "target_window_count_min": 3,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": "<= 0.50",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": "<= 0.35",
        "sample_guard_passed": bool(sample_ok),
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
            missing.append(
                {
                    "index": idx,
                    "ticker": position.get("ticker"),
                    "missing_fields": absent,
                }
            )
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
        "# Form 4 Ownership-Delta Forward Queue",
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
        "| Window | Core EV | Raw Form4 EV | Ownership EV | Delta vs raw | Delta vs core | Core PnL | Ownership PnL | Event PnL | Trades |",
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
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:45]) + "\n", encoding="utf-8")


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "title": "Form 4 ownership-delta forward queue",
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


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = _json_load(MANIFEST_JSON, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "experiment_id": EXP_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "updated_at": payload["timestamp"],
            "result_files": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(ARTIFACT_MD),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    events, source_diagnostics = _load_forward_events()
    raw_candidates = _event_candidates(events, prices, ownership_delta_only=False)
    ownership_candidates = _event_candidates(events, prices, ownership_delta_only=True)

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
        ownership_selected, ownership_skipped = _select_event_trades(
            ownership_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = _event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        ownership_curve = _event_equity_curve(
            ownership_selected,
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
            _combined_metrics(result, ownership_curve, ownership_selected)
            if ownership_selected
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
            "ownership_delta_event_count": sum(
                1 for row in scoped_events if row.get("ownership_delta_ge_10pct")
            ),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "ownership_delta_price_ready_count": sum(
                1
                for row in ownership_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "ownership_delta_selected_trade_count": len(ownership_selected),
            "raw_skipped_count": len(raw_skipped),
            "ownership_delta_skipped_count": len(ownership_skipped),
            "ownership_delta_selected_trades": ownership_selected,
            "raw_selected_trades": raw_selected,
            "ownership_delta_skipped_candidates": ownership_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)

    if gate["passed"]:
        decision = "accepted_default_off_form4_ownership_delta_forward_queue"
        status = "accepted_default_off"
        rationale = (
            "The ownership-delta Form 4 qualifier improved both core and raw Form 4 "
            "overlays while clearing materiality, drawdown, sample, and concentration "
            "gates. A shared default-off adapter would still be required before any "
            "production use."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The ownership-delta Form 4 slice was positive versus core, but it failed "
            "the full Gate 4 standard once raw Form 4 replacement value, materiality, "
            "window stability, sample, and concentration were considered."
        )
    else:
        decision = "rejected_form4_ownership_delta_forward_queue"
        status = "rejected"
        rationale = (
            "The ownership-delta Form 4 slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 meaningful purchases where at least one insider increases "
            "reported beneficial ownership by 10% or more may be a cleaner free SEC "
            "candidate source than the raw meaningful-purchase queue."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "form4_ownership_delta_event_satellite",
        "trial_family": "form4_ownership_delta_event_satellite",
        "trial_variant_id": EXP_ID,
        "changed_variable": "form4_ownership_delta_ge_10pct_forward_queue_v1",
        "single_causal_variable": (
            "max(shares / shares_owned_following_transaction) >= 0.10 on the "
            "existing PIT-safe Form 4 forward queue"
        ),
        "gate_questions": {
            "alpha_hypothesis": (
                "Candidate-pool/entry overlay: use a free SEC ownership-delta "
                "provenance field to filter already meaningful Form 4 purchases."
            ),
            "prior_similar_experiments": [
                "exp-20260504-034: raw >=500k Form 4 satellite positive but not enough for promotion.",
                "exp-20260512-101: multi-owner cluster observed-only and sample-thin.",
                "exp-20260512-017: multi-owner plus pre-entry RS positive but not material.",
                "exp-20260529-002: executive-role quality positive vs core but not raw and too concentrated.",
                "exp-20260529-024: first-buy inactivity positive but failed window/sample/concentration gates.",
            ],
            "single_causal_variable": (
                "Only the ownership-delta qualifier changes; core entries, raw Form 4 "
                "queue threshold, event notional, capacity, hold, LLM/news, and exits stay fixed."
            ),
            "acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form 4, avoid window EV/PnL regressions, pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "reproducibility": (
                "This runner rebuilds the core, raw Form 4, and ownership-delta Form 4 "
                "overlays from fixed snapshots and the local PIT-safe Form 4 transaction file."
            ),
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "ownership_delta_fraction_floor": OWNERSHIP_DELTA_FLOOR,
            "ownership_delta_definition": "transaction shares / shares owned following transaction",
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
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
            "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values()) >= 0.05,
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
        "source_diagnostics": source_diagnostics,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking is not needed here; the tested field is deterministic "
                "and replayable from free SEC Form 4 transaction data."
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
                "A shared default-off Form 4 ownership-delta queue/paper adapter must "
                "be wired through production and replay before any trade-enabled use."
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
    _write_manifest(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "gate4": {
                    key: payload["gate4"][key]
                    for key in (
                        "passed",
                        "material_vs_core",
                        "improves_core_cleanly",
                        "improves_vs_raw_form4",
                        "drawdown_guard_passed",
                        "ownership_delta_selected_event_trades",
                        "sample_guard_passed",
                        "single_ticker_positive_share",
                        "positive_pnl_hhi",
                        "failed_reasons",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
