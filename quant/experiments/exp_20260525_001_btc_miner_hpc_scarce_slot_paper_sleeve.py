"""exp-20260525-001: BTC miner/HPC scarce-slot paper sleeve scout.

Alpha search on one causal variable: route production-governed BTC miner/HPC
specialist candidates that the replay already deferred for scarce core slots
into an additive, default-off paper sleeve instead of letting them compete for
core slots. Core entries, ranking, sizing, exits, filters, LLM/news, and live
orders stay fixed.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260523_009_ai_power_datacenter_core_pool as base  # noqa: E402
import risk_engine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260525-001"
STEM = "btc_miner_hpc_scarce_slot_paper_sleeve"
TRIAL_FAMILY = "governed_btc_miner_hpc_scarce_slot_paper_sleeve"
CHANGED_VARIABLE = "btc_miner_hpc_scarce_slot_no_displacement_paper_routing"
TARGET_THEME = "btc_miner_hpc"
SOURCE_UNIVERSE_STATE = REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260523.json"
SOURCE_OHLCV_EXPERIMENT_ID = base.SOURCE_OHLCV_EXPERIMENT_ID

TARGET_SECTOR_MAP = {
    "CIFR": "Financials",
    "CORZ": "Financials",
    "IREN": "Financials",
    "MARA": "Financials",
    "RIOT": "Financials",
    "WULF": "Financials",
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
WINDOWS = base.WINDOWS
CANONICAL_WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

PAPER_NOTIONAL_USD = 2_500.0
ROUND_TRIP_COST_PCT = 0.0035
MAX_HOLD_DAYS = 20
MIN_TARGET_TRADES = 4
MIN_TARGET_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "open_positions.json missing"}
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = payload if isinstance(payload, list) else payload.get("positions", [])
    missing: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"index": index, "ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "checked_positions": len(rows or []),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _target_universe() -> dict[str, Any]:
    state = _load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}

    for ticker, record in sorted(records.items()):
        if not isinstance(record, dict):
            continue
        symbol = str(ticker).upper()
        reasons: list[str] = []
        if record.get("theme") != TARGET_THEME:
            reasons.append("not_target_theme")
        if record.get("status") != "specialist":
            reasons.append("not_specialist_status")
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if record.get("liquidity_tier") not in {"ok", "watch"}:
            reasons.append("liquidity_not_ok_or_watch")
        if symbol in core:
            reasons.append("already_core")

        if reasons:
            if record.get("theme") == TARGET_THEME:
                excluded[symbol] = reasons
            continue

        selected.append(symbol)
        selected_records[symbol] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "liquidity_tier",
                "history_class",
                "first_trade_allowed_as_of",
                "max_capital_scalar",
                "max_risk_scalar",
                "requires_event_guard",
                "event_guard_profile",
                "pilot_sleeve",
                "competes_for_core_slots",
                "source",
                "source_reason",
                "notes",
            )
        }
        selected_records[symbol]["sector_patch"] = TARGET_SECTOR_MAP.get(symbol, "Unknown")

    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "records.theme == btc_miner_hpc, status == specialist, history_class "
            "full_history, liquidity_tier in {ok, watch}, and not already core"
        ),
        "why_this_cohort_is_not_noise": (
            "The target set is the governed specialist BTC miner/HPC cohort from "
            "the universe state. The replay only observes candidates already "
            "found by the existing engine and deferred by scarce core slots."
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_related_records": excluded,
    }


def _snapshot_coverage_for_windows(
    target_tickers: list[str],
    windows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    passed = True
    for label, spec in windows.items():
        snapshot_path = REPO_ROOT / spec["snapshot"]
        payload = _load_json(snapshot_path)
        ohlcv = payload.get("ohlcv") or payload
        ticker_rows = {ticker: len(ohlcv.get(ticker) or []) for ticker in target_tickers}
        missing = [ticker for ticker, count in ticker_rows.items() if count <= 0]
        if missing:
            passed = False
        coverage[label] = {
            "snapshot": spec["snapshot"],
            "ticker_row_counts": ticker_rows,
            "missing_tickers": missing,
        }
    return {"passed": passed, "by_window": coverage}


def _snapshot_coverage(target_tickers: list[str]) -> dict[str, Any]:
    return _snapshot_coverage_for_windows(target_tickers, WINDOWS)


@contextmanager
def _target_sector_patch(target_tickers: list[str]):
    original = {ticker: risk_engine.SECTOR_MAP.get(ticker) for ticker in target_tickers}
    for ticker in target_tickers:
        risk_engine.SECTOR_MAP[ticker] = TARGET_SECTOR_MAP.get(ticker, "Unknown")
    try:
        yield
    finally:
        for ticker, value in original.items():
            if value is None:
                risk_engine.SECTOR_MAP.pop(ticker, None)
            else:
                risk_engine.SECTOR_MAP[ticker] = value


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _snapshot_rows_by_ticker(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(REPO_ROOT / snapshot_path)
    ohlcv = payload.get("ohlcv") or payload
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        normalized = []
        for row in rows or []:
            normalized.append(
                {
                    "date": str(_row_value(row, "date")),
                    "open": _float_or_none(_row_value(row, "open")),
                    "high": _float_or_none(_row_value(row, "high")),
                    "low": _float_or_none(_row_value(row, "low")),
                    "close": _float_or_none(_row_value(row, "close")),
                }
            )
        rows_by_ticker[str(ticker).upper()] = sorted(
            [row for row in normalized if row["date"] and row["open"] is not None],
            key=lambda row: row["date"],
        )
    return rows_by_ticker


def _scarce_slot_events(
    expanded_result: dict[str, Any],
    target_tickers: set[str],
) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    rows: list[dict[str, Any]] = []
    for event in (expanded_result.get("scarce_slot_attribution") or {}).get(
        "deferred_events"
    ) or []:
        if not isinstance(event, dict):
            continue
        ticker = str(event.get("ticker") or "").upper()
        if ticker not in target_tickers:
            continue
        key = (
            ticker,
            event.get("date"),
            event.get("strategy"),
            event.get("entry_price"),
            event.get("stop_price"),
            event.get("target_price"),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(event))
    return sorted(rows, key=lambda row: (str(row.get("date") or ""), str(row.get("ticker") or "")))


def _next_entry_index(rows: list[dict[str, Any]], signal_date: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date") or "") > signal_date:
            return index
    return None


def _simulate_scarce_event(
    event: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = str(event.get("ticker") or "").upper()
    signal_date = str(event.get("date") or "")
    rows = rows_by_ticker.get(ticker) or []
    if not rows:
        return None, "missing_ohlcv_rows"
    entry_index = _next_entry_index(rows, signal_date)
    if entry_index is None:
        return None, "missing_next_trading_day"

    stop_price = _float_or_none(event.get("stop_price"))
    target_price = _float_or_none(event.get("target_price"))
    fill_price = _float_or_none(rows[entry_index].get("open"))
    if fill_price is None or fill_price <= 0:
        return None, "invalid_next_open"
    if stop_price is None or target_price is None:
        return None, "missing_stop_or_target"
    if stop_price <= 0 or target_price <= 0 or stop_price >= fill_price or target_price <= fill_price:
        return None, "invalid_stop_target_after_fill"

    shares = int(PAPER_NOTIONAL_USD // fill_price)
    if shares <= 0:
        return None, "notional_too_small"

    exit_row = rows[-1]
    exit_reason = "window_end"
    for offset, row in enumerate(rows[entry_index:], start=0):
        high = _float_or_none(row.get("high"))
        low = _float_or_none(row.get("low"))
        close = _float_or_none(row.get("close"))
        if high is None or low is None or close is None:
            continue
        exit_row = row
        if low <= stop_price:
            exit_price = stop_price
            exit_reason = "stop"
            break
        if high >= target_price:
            exit_price = target_price
            exit_reason = "target"
            break
        if offset >= MAX_HOLD_DAYS:
            exit_price = close
            exit_reason = "max_hold"
            break
    else:
        exit_price = _float_or_none(exit_row.get("close")) or fill_price

    gross_pnl = (exit_price - fill_price) * shares
    cost = fill_price * shares * ROUND_TRIP_COST_PCT
    pnl = gross_pnl - cost
    pnl_pct_net = (exit_price - fill_price) / fill_price - ROUND_TRIP_COST_PCT
    return (
        {
            "ticker": ticker,
            "sector": TARGET_SECTOR_MAP.get(ticker, "Financials"),
            "strategy": event.get("strategy"),
            "source": "scarce_slot_deferred_event",
            "signal_date": signal_date,
            "entry_date": rows[entry_index]["date"],
            "exit_date": exit_row["date"],
            "exit_reason": exit_reason,
            "signal_entry_price": _round(event.get("entry_price"), 4),
            "entry_price": _round(fill_price, 4),
            "stop_price": _round(stop_price, 4),
            "target_price": _round(target_price, 4),
            "exit_price": _round(exit_price, 4),
            "shares": shares,
            "notional": _round(fill_price * shares, 2),
            "pnl": _round(pnl, 2),
            "pnl_pct_net": _round(pnl_pct_net, 6),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
            "candidate_rank": event.get("candidate_rank"),
            "capital_scalar": event.get("capital_scalar"),
        },
        None,
    )


def _simulate_scarce_sleeve(
    events: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    simulated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active_until_by_ticker: dict[str, str] = {}

    for event in events:
        trade, reason = _simulate_scarce_event(event, rows_by_ticker)
        ticker = str(event.get("ticker") or "").upper()
        if trade is None:
            skipped.append(
                {
                    "ticker": ticker,
                    "date": event.get("date"),
                    "strategy": event.get("strategy"),
                    "reason": reason,
                }
            )
            continue
        prior_exit = active_until_by_ticker.get(ticker)
        if prior_exit is not None and str(trade["entry_date"]) <= prior_exit:
            skipped.append(
                {
                    "ticker": ticker,
                    "date": event.get("date"),
                    "strategy": event.get("strategy"),
                    "reason": "same_ticker_overlap",
                    "prior_exit_date": prior_exit,
                }
            )
            continue
        simulated.append(trade)
        active_until_by_ticker[ticker] = str(trade["exit_date"])

    return {
        "candidate_event_count": len(events),
        "simulated_trade_count": len(simulated),
        "skipped_event_count": len(skipped),
        "skip_reasons": dict(Counter(row["reason"] for row in skipped)),
        "skipped_events_sample": skipped[:20],
        "trades": simulated,
    }


def _overlay_from_target_trades(
    before_result: dict[str, Any],
    target_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in target_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "strategy": trade.get("strategy"),
                "pnl": _round(pnl, 2),
                "source": "btc_miner_hpc_scarce_slot_no_displacement_paper",
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())},
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    target_universe = _target_universe()
    target_tickers = target_universe["target_tickers"]
    if not target_tickers:
        raise RuntimeError("No target tickers selected from universe state")
    coverage = _snapshot_coverage(target_tickers)
    canonical_coverage = _snapshot_coverage_for_windows(target_tickers, CANONICAL_WINDOWS)
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    base_universe = sorted(get_universe())
    expanded_universe = sorted(set(base_universe) | set(target_tickers))
    target_set = set(target_tickers)

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    candidate_events_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    simulation_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    expanded_core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    with _target_sector_patch(target_tickers):
        for label, spec in WINDOWS.items():
            print(f"[{label}] baseline core universe")
            before_result = base._run_window(label, base_universe)
            print(f"[{label}] expanded universe for scarce-slot discovery")
            expanded_result = base._run_window(label, expanded_universe)
            rows_by_ticker = _snapshot_rows_by_ticker(spec["snapshot"])
            scarce_events = _scarce_slot_events(expanded_result, target_set)
            simulation = _simulate_scarce_sleeve(scarce_events, rows_by_ticker)
            target_trades = simulation["trades"]
            overlay = _overlay_from_target_trades(before_result, target_trades)
            before = overlay_helper._metrics(before_result)
            after = overlay_helper._metrics_with_overlay(before_result, overlay)
            delta = overlay_helper._delta(after, before)

            before_metrics[label] = before
            after_metrics[label] = after
            target_trades_by_window[label] = target_trades
            candidate_events_by_window[label] = scarce_events
            simulation_by_window[label] = {
                key: value for key, value in simulation.items() if key != "trades"
            }
            expanded_core_metrics[label] = base._metrics(expanded_result)
            window_rows[label] = {
                "before": before,
                "after": after,
                "delta": delta,
                "overlay_total_pnl": overlay["overlay_total_pnl"],
                "overlay_day_count": overlay["overlay_day_count"],
                "overlay_days": overlay["overlay_days"],
                "target_trade_count": len(target_trades),
                "candidate_event_count": len(scarce_events),
            }

    aggregate = _aggregate(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    decision = (
        "promising_replay_only_btc_miner_hpc_scarce_slot_paper_sleeve"
        if gate4_passed
        else "rejected_btc_miner_hpc_scarce_slot_paper_sleeve"
    )
    rejection_reason = None
    if not gate4_passed:
        failed = []
        if aggregate["expected_value_score_delta_sum"] <= 0:
            failed.append("aggregate_ev_not_positive")
        if aggregate["total_pnl_delta_sum"] <= 0:
            failed.append("aggregate_pnl_not_positive")
        if aggregate["windows_ev_improved"] < MIN_EV_IMPROVED_WINDOWS:
            failed.append("too_few_ev_improved_windows")
        if aggregate["windows_ev_regressed"]:
            failed.append("window_ev_regression")
        if aggregate["windows_pnl_regressed"]:
            failed.append("window_pnl_regression")
        if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
            failed.append("target_sample_too_small")
        if len(target_windows) < MIN_TARGET_WINDOWS:
            failed.append("target_window_coverage_too_small")
        if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
            failed.append("drawdown_drift_too_high")
        if min_survival < 0.05:
            failed.append("survival_rate_below_gate")
        if not concentration_passed:
            failed.append("target_concentration_failed")
        rejection_reason = "; ".join(failed)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The governed BTC miner/HPC specialist cohort may have high-convexity "
            "replacement value when the existing engine already finds breakouts, "
            "but raw core admission failed because the candidates were skipped or "
            "deferred by slot/capital constraints. Routing scarce-slot deferred "
            "events into a small no-displacement paper sleeve tests that edge "
            "without changing core production behavior."
        ),
        "change_type": "candidate_pool_no_displacement_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260501-008",
            "exp-20260519-011",
            "exp-20260523-010",
            "exp-20260524-033",
            "exp-20260524-035",
            "exp-20260524-036",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "scarce_slot_deferred_candidate_no_displacement_replay",
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md three-window replay using exp-20260519-029 "
                "observation-universe OHLCV snapshots; candidate events are "
                "scarce-slot deferred events from the expanded replay, then "
                "simulated as additive default-off paper on top of baseline core "
                "equity without displacing core trades."
            ),
            "canonical_snapshot_target_coverage": canonical_coverage,
            "snapshot_coverage_note": (
                "The standard date windows are preserved. Target discovery uses "
                "the existing exp-20260519-029 observation-universe snapshots "
                "because canonical core snapshots do not reliably contain all "
                "governed BTC miner/HPC specialist tickers."
            ),
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_theme": TARGET_THEME,
            "target_sector_map": TARGET_SECTOR_MAP,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
            "event_source": "scarce_slot_attribution.deferred_events",
            "paper_sleeve_routing": "additive_no_core_displacement",
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "max_hold_days": MAX_HOLD_DAYS,
            "entry_model": "next_trading_day_open_after_deferred_signal_date",
            "exit_model": "stop_first_then_target_then_max_hold_or_window_end",
            "same_ticker_overlap_rule": "skip_additional_events_until_prior_paper_trade_exits",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "target cohort definition",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: BTC miner/HPC specialist "
                "scarce-slot deferred events may have standalone replacement value "
                "as a no-displacement paper sleeve."
            ),
            "2_history_check": {
                "exp-20260523-010": (
                    "Raw BTC miner/HPC core-pool admission was rejected with "
                    "zero entered target trades; target signals were mostly "
                    "deferred or skipped rather than safely admitted."
                ),
                "exp-20260519-011": (
                    "Broad governed non-core expansion was positive in aggregate "
                    "but rejected because broad variants regressed windows and "
                    "failed replacement-value gates."
                ),
                "exp-20260524-035": (
                    "AI optical no-displacement paper was positive in all three "
                    "windows but rejected by concentration; this BTC version "
                    "uses scarce-slot deferred events rather than entered target "
                    "trades."
                ),
                "exp-20260524-036": (
                    "Broad-market production-feed pool added too much correlated "
                    "noise and failed window/materiality/concentration gates."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows, positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV/PnL-regressed window, "
                ">=4 target paper trades across >=2 windows, drawdown drift <=0.5pp, "
                "survival >=5%, and target concentration within guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260525_001_btc_miner_hpc_scarce_slot_paper_sleeve.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": {
                "observation_snapshot_target_coverage": coverage,
                "canonical_snapshot_target_coverage": canonical_coverage,
                "note": (
                    "The replay preserves the standard date windows and uses "
                    "observation-universe snapshots for target OHLCV coverage."
                ),
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme/status/liquidity_tier/history_class",
                "target OHLCV rows in all three exp-20260519-029 snapshots",
                "scarce_slot_attribution.deferred_events date/ticker/entry_price/stop_price/target_price",
                "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or core entry rule was added. The target cohort "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_improved_min": MIN_EV_IMPROVED_WINDOWS,
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "candidate_events_by_window": candidate_events_by_window,
        "simulation_by_window": simulation_by_window,
        "expanded_core_metrics": expanded_core_metrics,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result is a research lead only. Promotion requires a "
                "shared default-off BTC miner/HPC paper adapter, daily report "
                "exposure, forward replacement-value ledger, and parity tests "
                "before any live/default behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains "
            "sparse; skipped another raw BTC core-pool admission because the "
            "prior run had zero entered target trades; skipped state-surface, "
            "event scalar, and broad-market retunes due recent anti-repeat gates. "
            "This uses a governed specialist free-data cohort and changes only "
            "capital routing for candidates the engine already discovered."
        ),
        "interpretation": (
            "The BTC miner/HPC scarce-slot paper sleeve has replay replacement "
            "value, but no production/shared policy was promoted. Treat it as a "
            "forward-watch sleeve lead only."
            if gate4_passed
            else (
                "The BTC miner/HPC scarce-slot paper sleeve did not clear Gate 4; "
                "do not promote this specialist cohort without broader forward "
                "evidence or a stronger free-data regime/catalyst field."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Build forward default-off BTC miner/HPC paper replacement-value rows "
            "or add a free BTC/power-regime catalyst field before promotion."
            if gate4_passed
            else (
                "Use a materially new free-data BTC/power-regime context field "
                "or forward paper ledger before retrying BTC miner/HPC."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Candidate events | Paper trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=len(payload["candidate_events_by_window"][label]),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} BTC Miner/HPC Scarce-Slot Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route governed BTC miner/HPC scarce-slot deferred events into an additive default-off paper sleeve instead of core slot competition.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            f"- snapshot_note: {payload['backtest_protocol']['snapshot_coverage_note']}",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Simulation",
            "",
            "```json",
            json.dumps(payload["simulation_by_window"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "BTC miner/HPC scarce-slot paper sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "simulation_by_window": payload["simulation_by_window"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
