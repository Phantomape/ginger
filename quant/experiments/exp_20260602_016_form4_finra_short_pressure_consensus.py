"""Replay a Form 4 + FINRA short-pressure consensus event sleeve.

This alpha-search experiment keeps the core strategy and the raw PIT-safe
Form 4 forward queue fixed. The single tested variable is whether raw Form 4
meaningful-purchase events only retain replacement value when the same ticker
also has a high latest-published FINRA short-pressure score.

No production orders, watchlists, shared policy modules, ranking, sizing, LLM
paths, or exits are changed. This is a default-off replay only.
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
    _repo_rel,
    _select_event_trades,
    _write_json,
)
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION as FORM4_RULE_VERSION,
    aggregate_purchase_events,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXP_ID = "exp-20260602-016"
STEM = "form4_finra_short_pressure_consensus"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
RAW_FORM4_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
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
FINRA_ROWS_PATH = (
    REPO_ROOT / "data" / "experiments" / "exp-20260530-005" / "finra_short_interest_rows.json"
)

FINRA_SHORT_PRESSURE_FLOOR = 0.70
MIN_TARGET_TRADES = 8
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

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


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


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


def _percentiles(values: list[float | None]) -> list[float | None]:
    present = sorted(value for value in values if value is not None and math.isfinite(value))
    if not present:
        return [None for _ in values]
    if len(present) == 1:
        return [0.5 if value is not None else None for value in values]
    out: list[float | None] = []
    denom = len(present) - 1
    for value in values:
        if value is None or not math.isfinite(value):
            out.append(None)
            continue
        below_or_equal = sum(1 for other in present if other <= value)
        out.append(round((below_or_equal - 1) / denom, 6))
    return out


def _load_finra_rows() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    rows = _json_load(FINRA_ROWS_PATH, [])
    if not isinstance(rows, list):
        return {}, {
            "source_status": "invalid_finra_rows_artifact",
            "source_path": _repo_rel(FINRA_ROWS_PATH),
        }
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        publication = _date10(row.get("publication_date"))
        if not ticker or not publication:
            continue
        by_ticker[ticker].append(row)
    for ticker_rows in by_ticker.values():
        ticker_rows.sort(key=lambda row: (_date10(row.get("publication_date")), _date10(row.get("settlement_date"))))
    return dict(by_ticker), {
        "source_status": "loaded",
        "source_path": _repo_rel(FINRA_ROWS_PATH),
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "pit_status": "uses FINRA publication_date/usable_trade_date rows generated by exp-20260530-005",
    }


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if _date10(row.get("publication_date")) <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


def _same_day_finra_scores(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for ticker in sorted(rows_by_ticker):
        row = _latest_finra_row(rows_by_ticker, ticker, signal_date)
        if row is None:
            continue
        records.append(
            {
                "ticker": ticker,
                "row": row,
                "days_to_cover": _float_or_none(row.get("days_to_cover")),
                "short_interest_change_pct": _float_or_none(
                    row.get("short_interest_change_pct")
                ),
            }
        )
    crowding_scores = _percentiles([record["days_to_cover"] for record in records])
    change_scores = _percentiles(
        [record["short_interest_change_pct"] for record in records]
    )
    out: dict[str, dict[str, Any]] = {}
    for record, crowding, change in zip(records, crowding_scores, change_scores):
        crowding_for_score = 0.0 if crowding is None else crowding
        change_for_score = 0.0 if change is None else change
        score = round(0.70 * crowding_for_score + 0.30 * change_for_score, 6)
        out[record["ticker"]] = {
            "finra_row": record["row"],
            "short_crowding_score": crowding,
            "short_change_score": change,
            "finra_short_pressure_score": score,
            "same_day_finra_covered_count": len(records),
            "score_weights": {
                "days_to_cover_percentile": 0.70,
                "short_interest_change_pct_percentile": 0.30,
            },
        }
    return out


def _load_forward_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not FORM4_TRANSACTIONS_PATH.exists():
        return [], {"source_status": "missing_form4_transactions"}
    rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    rows_by_ticker, finra_diagnostics = _load_finra_rows()
    score_cache: dict[str, dict[str, dict[str, Any]]] = {}
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    raw_events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    events = []
    missing_finra = 0
    qualifying_finra = 0
    for event in raw_events:
        ticker = str(event.get("ticker") or "").upper()
        usable = _date10(event.get("usable_trade_date"))
        window = _window_name(usable)
        if not ticker or not usable or not window:
            continue
        if usable not in score_cache:
            score_cache[usable] = _same_day_finra_scores(rows_by_ticker, usable)
        score = score_cache[usable].get(ticker)
        if score is None:
            missing_finra += 1
            events.append(
                {
                    **event,
                    "ticker": ticker,
                    "usable_trade_date": usable,
                    "window": window,
                    "finra_short_pressure_score": None,
                    "finra_consensus_ge_070": False,
                    "finra_qualification_reason": "missing_published_finra_row",
                }
            )
            continue
        finra_row = score["finra_row"]
        passed = score["finra_short_pressure_score"] >= FINRA_SHORT_PRESSURE_FLOOR
        qualifying_finra += int(passed)
        events.append(
            {
                **event,
                "ticker": ticker,
                "usable_trade_date": usable,
                "window": window,
                "finra_consensus_ge_070": passed,
                "finra_qualification_reason": (
                    "score_ge_floor" if passed else "score_below_floor"
                ),
                "finra_short_pressure_score": score["finra_short_pressure_score"],
                "finra_short_crowding_score": score["short_crowding_score"],
                "finra_short_change_score": score["short_change_score"],
                "same_day_finra_covered_count": score["same_day_finra_covered_count"],
                "finra_settlement_date": finra_row.get("settlement_date"),
                "finra_publication_date": finra_row.get("publication_date"),
                "finra_publication_date_method": finra_row.get(
                    "publication_date_method"
                ),
                "finra_days_to_cover": finra_row.get("days_to_cover"),
                "finra_short_interest": finra_row.get("short_interest"),
                "finra_previous_short_interest": finra_row.get(
                    "previous_short_interest"
                ),
                "finra_short_interest_change_pct": finra_row.get(
                    "short_interest_change_pct"
                ),
                "finra_source_url": finra_row.get("source_url"),
                "known_at": (
                    "after_form4_usable_trade_date_with_latest_published_finra_"
                    "row_on_or_before_event_date"
                ),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    diagnostics = {
        "form4_source_status": "loaded",
        "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
        "transaction_rows": len(rows),
        "raw_forward_event_count": len(events),
        "events_missing_published_finra": missing_finra,
        "finra_consensus_floor": FINRA_SHORT_PRESSURE_FLOOR,
        "finra_consensus_event_count": qualifying_finra,
        "finra": finra_diagnostics,
    }
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _event_candidates(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    finra_consensus_only: bool,
) -> list[dict[str, Any]]:
    return [
        _candidate_trade(event, prices)
        for event in events
        if not finra_consensus_only or event.get("finra_consensus_ge_070")
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


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
        "windows": metrics,
    }


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("finra_consensus_selected_trades") or []:
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
    selected = sum(int(row.get("finra_consensus_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("finra_consensus_selected_trade_count") or 0) > 0
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
    drawdown_ok = core_delta["max_drawdown_drift"] <= MAX_DRAWDOWN_WORSE
    sample_ok = (
        selected >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and (single_share is None or single_share <= MAX_SINGLE_POSITIVE_SHARE)
        and (hhi is None or hhi <= MAX_POSITIVE_HHI)
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
    if selected < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if single_share is not None and single_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed": bool(material and improves_core and improves_raw and drawdown_ok and sample_ok),
        "failed_reasons": failed,
        "material_vs_core": bool(material),
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": "<= 0.005",
        "finra_consensus_selected_event_trades": selected,
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": f"<= {MAX_SINGLE_POSITIVE_SHARE}",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": f"<= {MAX_POSITIVE_HHI}",
        "sample_guard_passed": bool(sample_ok),
        "positive_pnl_by_ticker": concentration["positive_pnl_by_ticker"],
    }


def _position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "operator_inputs/open_positions.json missing"}
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    groups: list[tuple[str, list[Any]]] = []
    if isinstance(payload, dict):
        for key in ("positions", "observations", "open_positions"):
            value = payload.get(key)
            if isinstance(value, list):
                groups.append((key, value))
    elif isinstance(payload, list):
        groups.append(("root", payload))
    if not groups:
        return {"passed": False, "reason": "open_positions payload has no checked lists"}
    missing = []
    checked = 0
    for group_name, positions in groups:
        for idx, position in enumerate(positions):
            checked += 1
            if not isinstance(position, dict):
                missing.append({"group": group_name, "index": idx, "reason": "not_object"})
                continue
            absent = [
                field
                for field in ("entry_date", "target_price")
                if position.get(field) in (None, "")
            ]
            if absent:
                missing.append(
                    {
                        "group": group_name,
                        "index": idx,
                        "ticker": position.get("ticker"),
                        "missing_fields": absent,
                    }
                )
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "checked_groups": [name for name, _ in groups],
        "checked_item_count": checked,
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
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 + FINRA Short-Pressure Consensus",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate Questions",
        "",
        "```json",
        json.dumps(payload["gate_questions"], indent=2, sort_keys=True),
        "```",
        "",
        "## Three-Window Results",
        "",
        "| Window | Core EV | Raw Form4 EV | FINRA Consensus EV | Delta vs raw | Delta vs core | Core PnL | Consensus PnL | Event PnL | Trades |",
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
    CARD_MD.write_text("\n".join(lines[:49]) + "\n", encoding="utf-8")


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "title": "Form 4 + FINRA short-pressure consensus",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
            "raw_form4_aggregate": _repo_rel(RAW_FORM4_AGG_JSON),
            "after_aggregate": _repo_rel(AFTER_AGG_JSON),
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
                _repo_rel(BEFORE_AGG_JSON),
                _repo_rel(RAW_FORM4_AGG_JSON),
                _repo_rel(AFTER_AGG_JSON),
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
    raw_candidates = _event_candidates(events, prices, finra_consensus_only=False)
    finra_candidates = _event_candidates(events, prices, finra_consensus_only=True)

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
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
        finra_selected, finra_skipped = _select_event_trades(
            finra_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = _event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        finra_curve = _event_equity_curve(
            finra_selected,
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
            _combined_metrics(result, finra_curve, finra_selected)
            if finra_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = _delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = _delta(core_baseline[label], after_metrics[label])

        scoped_events = [
            row
            for row in events
            if window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "finra_consensus_event_count": sum(
                1 for row in scoped_events if row.get("finra_consensus_ge_070")
            ),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "finra_consensus_price_ready_count": sum(
                1
                for row in finra_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= _date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "finra_consensus_selected_trade_count": len(finra_selected),
            "raw_skipped_count": len(raw_skipped),
            "finra_consensus_skipped_count": len(finra_skipped),
            "raw_selected_trades": raw_selected,
            "finra_consensus_selected_trades": finra_selected,
            "finra_consensus_skipped_candidates": finra_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)

    if gate["passed"]:
        decision = "accepted_research_form4_finra_consensus_requires_shared_adapter"
        status = "accepted_default_off"
        rationale = (
            "The FINRA-qualified Form 4 consensus improved both core and raw Form 4 "
            "metrics while passing sample, window, drawdown, and concentration gates. "
            "No production path was changed; a shared default-off adapter and parity "
            "tests are still required before any production report or order impact."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The FINRA-qualified Form 4 slice was positive versus core, but it failed "
            "the stricter Gate 4 standard against raw Form 4 replacement value, "
            "materiality, window stability, sample, or concentration."
        )
    else:
        decision = "rejected_form4_finra_short_pressure_consensus"
        status = "rejected"
        rationale = (
            "The FINRA-qualified Form 4 slice did not produce positive, stable "
            "three-window EV/PnL evidence versus the core baseline."
        )

    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values())
    actual_success = 1 if gate["passed"] else 0
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Raw PIT-safe Form 4 meaningful-purchase events may have cleaner forward "
            "replacement value when confirmed by the same ticker's latest published "
            "FINRA short-pressure context."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": "form4_finra_short_pressure_consensus_event_satellite",
        "trial_variant_id": "form4_finra_short_pressure_score_ge_070_v1",
        "changed_variable": "form4_finra_short_pressure_consensus_v1",
        "single_causal_variable": (
            "raw PIT-safe Form 4 forward events require latest published FINRA "
            "short-pressure score >= 0.70 on or before usable trade date"
        ),
        "prediction": {
            "success_probability": 0.18,
            "expected_ev_delta": 0.20,
            "expected_pnl_delta": 3500.0,
            "main_failure_modes": [
                "sample_too_thin",
                "does_not_beat_raw_form4",
                "late_strong_regression",
                "concentration",
                "finra_publication_lag_false_positive",
            ],
            "confidence_reason": (
                "Form 4 and FINRA are both free PIT sources, but prior Form 4 "
                "qualifiers were sample-thin and prior FINRA candidates often needed "
                "confirmation."
            ),
            "recorded_at": "2026-06-02T11:09:12+00:00",
            "brier_score": round((0.18 - actual_success) ** 2, 6),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / entry: meaningful insider buys can be stronger "
                "when paired with high published short-pressure because the trade "
                "has both insider information and potential squeeze/covering demand."
            ),
            "2_history_check": {
                "exp-20260504-034": "raw Form 4 event satellite positive but not enough for promotion.",
                "exp-20260529-002": "executive-role Form 4 qualifier positive vs core but not raw and too concentrated.",
                "exp-20260530-003": "ownership-delta Form 4 qualifier positive vs core but not raw and too small/materiality failed.",
                "exp-20260530-011": "multi-filer Form 4 forward queue did not create promotable evidence.",
                "exp-20260529-017": "FINRA short-pressure breakout default-off candidate pool tested FINRA alone.",
                "exp-20260530-005": "FINRA + IWM confirmation candidate pool accepted as default-off paper source.",
                "exp-20260530-010": "FINRA shared adapter is claimed; this run does not touch it.",
            },
            "3_single_causal_variable": (
                "Only the Form 4 event qualifier changes by adding a FINRA score floor; "
                "core entries, raw Form 4 threshold, event notional, capacity, hold, "
                "LLM/news, ranking, sizing, and exits stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate "
                "EV/PnL versus core and raw Form 4, avoid window EV/PnL regressions, "
                "pass drawdown, survival, target sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_016_form4_finra_short_pressure_consensus.py"
            ),
        },
        "parameters": {
            "form4_queue_name": QUEUE_NAME,
            "form4_rule_version": FORM4_RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "finra_short_pressure_floor": FINRA_SHORT_PRESSURE_FLOOR,
            "finra_score_definition": {
                "days_to_cover_percentile_weight": 0.70,
                "short_interest_change_pct_percentile_weight": 0.30,
                "same_day_universe": "tickers with latest published FINRA row on or before the event date",
            },
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
                "Form 4 parser",
                "Form 4 purchase-value threshold",
                "event notional",
                "event holding period",
                "event capacity",
                "FINRA source rows",
                "production orders",
                "production watchlists",
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
            "min_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
        },
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "before_aggregate": _aggregate_metrics(core_baseline),
        "raw_form4_aggregate": _aggregate_metrics(raw_metrics),
        "after_aggregate": _aggregate_metrics(after_metrics),
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "gate4": gate,
        "event_details": details,
        "decision_rationale": rationale,
        "source_diagnostics": source_diagnostics,
        "why_not_other_alpha": (
            "Skipped LLM soft-ranking because replay attribution remains sparse. "
            "Skipped Companyfacts, VBB, VCP, state-surface, SEC 8-K, and OHLCV "
            "pattern retunes per playbook freeze guidance. 13F was skipped because "
            "coverage is sparse across the three canonical windows."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "The tested field is deterministic and replayable from free SEC "
                "Form 4 plus FINRA short-interest data."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 + FINRA paper adapter must be wired "
                "through production and replay with source-row caching and parity "
                "tests before any production report or order behavior can change."
            ),
        },
        "data_sources": {
            "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
            "finra_rows_path": _repo_rel(FINRA_ROWS_PATH),
            "pit_status": (
                "uses Form 4 usable_trade_date plus latest FINRA publication_date "
                "on or before the same event date"
            ),
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(RAW_FORM4_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(Path(__file__)),
        ],
    }
    return payload


def _write_aggregate_files(payload: dict[str, Any]) -> None:
    _write_json(BEFORE_AGG_JSON, payload["before_aggregate"])
    _write_json(RAW_FORM4_AGG_JSON, payload["raw_form4_aggregate"])
    _write_json(AFTER_AGG_JSON, payload["after_aggregate"])


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_aggregate_files(payload)
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
                        "finra_consensus_selected_event_trades",
                        "target_windows",
                        "failed_reasons",
                    )
                },
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
