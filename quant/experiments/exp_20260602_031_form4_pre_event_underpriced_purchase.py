"""Test Form 4 meaningful buys after 20-day underpricing versus SPY.

This replay-only alpha experiment keeps the frozen Form 4 meaningful-purchase
queue intact and tests one additional event-timing qualifier: the ticker's
20-trading-day return before the usable event date must lag SPY.
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
    _candidate_trade,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _repo_rel,
    _round,
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


EXP_ID = "exp-20260602-031"
STEM = "form4_pre_event_underpriced_purchase"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_core_aggregate.json"
RAW_FORM4_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_qualified_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

LOOKBACK_DAYS = 20
RELATIVE_RETURN_MAX = 0.0
MIN_TARGET_TRADES = 8
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.75
MAX_POSITIVE_HHI = 0.60

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


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _lookback_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_date: str,
    *,
    lookback_days: int,
) -> float | None:
    rows = prices.get(ticker.upper())
    if not rows:
        return None
    entry_idx = _first_index_on_or_after(rows, usable_date)
    if entry_idx is None or entry_idx <= lookback_days:
        return None
    end_idx = entry_idx - 1
    start_idx = end_idx - lookback_days
    start_close = rows[start_idx].get("close")
    end_close = rows[end_idx].get("close")
    if not start_close or not end_close:
        return None
    return float(end_close) / float(start_close) - 1.0


def _with_pre_event_surface(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    usable = str(event.get("usable_trade_date") or "")[:10]
    ticker = str(event.get("ticker") or "").upper()
    ticker_ret = _lookback_return(prices, ticker, usable, lookback_days=LOOKBACK_DAYS)
    spy_ret = _lookback_return(prices, "SPY", usable, lookback_days=LOOKBACK_DAYS)
    if ticker_ret is None or spy_ret is None:
        return {
            **event,
            "window": _window_name(usable),
            "pre_event_status": "missing_pre_event_rs20",
        }
    relative = ticker_ret - spy_ret
    return {
        **event,
        "window": _window_name(usable),
        "pre_event_status": "pre_event_ready",
        "pre_event_ret20_pct": round(ticker_ret * 100.0, 6),
        "pre_event_spy_ret20_pct": round(spy_ret * 100.0, 6),
        "pre_event_rs20_vs_spy_pct": round(relative * 100.0, 6),
        "pre_event_underpriced_vs_spy": relative <= RELATIVE_RETURN_MAX,
    }


def _load_forward_events(prices: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    events = [
        _with_pre_event_surface(event, prices)
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    return [
        event
        for event in events
        if event.get("window") is not None
    ]


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
        "aggregate_ev_before": round(before_ev, 4),
        "aggregate_ev_after": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "aggregate_pnl_before": round(before_pnl, 2),
        "aggregate_pnl_after": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - before_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
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
        for trade in detail.get("qualified_selected_trades") or []:
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
    selected = sum(int(row.get("qualified_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("qualified_selected_trade_count") or 0) > 0
    ]
    concentration = _positive_pnl_concentration(details)
    single_share = concentration["single_ticker_positive_share"]
    hhi = concentration["positive_pnl_hhi"]
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
    sample_ok = (
        selected >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and (single_share is None or single_share <= MAX_SINGLE_POSITIVE_SHARE)
        and (hhi is None or hhi <= MAX_POSITIVE_HHI)
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= MAX_DRAWDOWN_WORSE
    failed = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_raw:
        failed.append("does_not_improve_raw_form4_queue")
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
        "passed": bool(improves_core and improves_raw and drawdown_ok and sample_ok),
        "failed_reasons": failed,
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": f"<= {MAX_DRAWDOWN_WORSE}",
        "qualified_selected_event_trades": selected,
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
        "# Form 4 Pre-Event Underpriced Purchase",
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
        "| Window | Core EV | Raw Form4 EV | Qualified EV | Delta vs raw | Delta vs core | Core PnL | Qualified PnL | Event PnL | Trades |",
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
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:49]) + "\n", encoding="utf-8")


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXP_ID,
        "title": "Form 4 pre-event underpriced purchase",
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


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _json_load(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "updated_at": payload["timestamp"],
                    "completed_at": payload["timestamp"],
                    "result": {
                        "decision": payload["decision"],
                        "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                        "log_file": _repo_rel(LOG_JSON),
                        "artifact": _repo_rel(ARTIFACT_MD),
                    },
                }
            )
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    events = _load_forward_events(prices)
    raw_candidates = [_candidate_trade(event, prices) for event in events]
    qualified_events = [
        event
        for event in events
        if event.get("pre_event_status") == "pre_event_ready"
        and bool(event.get("pre_event_underpriced_vs_spy"))
    ]
    qualified_candidates = [_candidate_trade(event, prices) for event in qualified_events]

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
        qualified_selected, qualified_skipped = _select_event_trades(
            qualified_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = _event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        qualified_curve = _event_equity_curve(
            qualified_selected,
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
            _combined_metrics(result, qualified_curve, qualified_selected)
            if qualified_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = _delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = _delta(core_baseline[label], after_metrics[label])
        scoped_events = [
            row
            for row in events
            if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        ]
        scoped_qualified = [
            row
            for row in qualified_events
            if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "pre_event_ready_count": sum(
                1 for row in scoped_events if row.get("pre_event_status") == "pre_event_ready"
            ),
            "qualified_event_count": len(scoped_qualified),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "qualified_price_ready_count": sum(
                1
                for row in qualified_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "qualified_selected_trade_count": len(qualified_selected),
            "raw_skipped_count": len(raw_skipped),
            "qualified_skipped_count": len(qualified_skipped),
            "raw_selected_trades": raw_selected,
            "qualified_selected_trades": qualified_selected,
            "qualified_skipped_candidates": qualified_skipped[:20],
        }

    aggregate_vs_raw = _aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = _aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)

    if gate["passed"]:
        decision = "accepted_research_form4_underpriced_requires_shared_adapter"
        status = "accepted_default_off"
        rationale = (
            "The pre-event underpriced Form 4 slice improved both core and raw Form 4 "
            "metrics without window regressions while passing sample, drawdown, and "
            "concentration gates. It remains default-off until a shared adapter and "
            "parity tests are implemented."
        )
    elif aggregate_vs_core["aggregate_ev_delta"] > 0 and aggregate_vs_core["aggregate_pnl_delta"] > 0:
        decision = "rejected_positive_not_promotable"
        status = "rejected"
        rationale = (
            "The underpriced Form 4 slice was positive versus the core baseline, but "
            "failed replacement value against raw Form 4 or failed one of the window, "
            "sample, drawdown, or concentration guards."
        )
    else:
        decision = "rejected_form4_underpriced_no_stable_alpha"
        status = "rejected"
        rationale = (
            "The underpriced Form 4 slice did not produce positive, stable three-window "
            "EV/PnL evidence versus the core baseline."
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
            "PIT-safe Form 4 meaningful purchase events may have better forward value "
            "when the ticker was underpriced versus SPY over the prior 20 trading days "
            "before the usable event date."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": "form4_pre_event_underpriced_purchase_candidate_pool",
        "trial_variant_id": "form4_pre_event_rs20_vs_spy_lte_0_v1",
        "changed_variable": "form4_pre_event_rs20_underpriced_qualifier_v1",
        "single_causal_variable": (
            "raw PIT-safe Form 4 forward events require pre-event 20d ticker-vs-SPY "
            "relative return <= 0.0"
        ),
        "prediction": {
            "success_probability": 0.16,
            "expected_ev_delta": 0.18,
            "expected_pnl_delta": 3000.0,
            "main_failure_modes": [
                "does_not_beat_raw_form4",
                "sample_too_thin",
                "old_thin_regression",
                "concentration",
                "underpricing_is_mean_reversion_noise",
            ],
            "confidence_reason": (
                "Form4 is free and PIT-safe across the fixed windows, but prior "
                "Form4 qualifiers have often failed raw-queue replacement value."
            ),
            "recorded_at": "2026-06-02T23:10:01+00:00",
            "brier_score": round((0.16 - actual_success) ** 2, 6),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: insider purchases are more informative when "
                "the market has recently underpriced the ticker versus SPY, creating "
                "a contrarian event-timing edge rather than another owner-role filter."
            ),
            "2_history_check": {
                "exp-20260504-034": "Raw Form 4 event satellite was positive but not promoted.",
                "exp-20260512-017": "Prior Form 4 relative-strength confirmation used the opposite chasing direction and failed sample.",
                "exp-20260529-002": "Executive-role Form 4 qualifier positive vs core but not raw and too concentrated.",
                "exp-20260530-003": "Ownership-delta Form 4 qualifier positive vs core but not raw and too small/materiality failed.",
                "exp-20260530-011": "Multi-filer Form 4 forward queue did not create promotable evidence.",
                "exp-20260602-016": "Form4 + FINRA short-pressure consensus did not improve raw Form4 queue.",
            },
            "3_single_causal_variable": (
                "Only the event qualifier changes by adding pre-event 20d relative "
                "underpricing versus SPY; core strategy, Form4 threshold, event notional, "
                "capacity, hold period, LLM/news, ranking, sizing, and exits stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate EV/PnL "
                "versus core and raw Form4, avoid window EV/PnL regressions, and pass "
                "drawdown, survival, target sample, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_031_form4_pre_event_underpriced_purchase.py"
            ),
        },
        "parameters": {
            "form4_queue_name": QUEUE_NAME,
            "form4_rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "lookback_days": LOOKBACK_DAYS,
            "pre_event_rs20_vs_spy_max": RELATIVE_RETURN_MAX,
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "hold_days": HOLD_DAYS,
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
        "why_not_other_alpha": (
            "Skipped LLM soft-ranking because replay attribution remains sparse. "
            "Skipped Companyfacts, post-earnings high-liquidity/scalar retunes, peer "
            "earnings transfer, VBB, VCP, state-surface, and broad OHLCV pattern "
            "retunes per playbook freeze guidance. 13F/options were skipped because "
            "current coverage is not PIT-safe and dense across the three windows."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "This run uses deterministic free SEC Form 4 rows plus fixed OHLCV "
                "snapshots; LLM soft-ranking remains sample-blocked."
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
                "A shared default-off Form 4 underpriced-event paper adapter must be "
                "wired through production and replay with source-row caching and parity "
                "tests before any production report or order behavior can change."
            ),
        },
        "data_sources": {
            "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
            "ohlcv_snapshots": {
                label: window["snapshot"]
                for label, window in WINDOWS.items()
            },
            "pit_status": (
                "Uses Form 4 usable_trade_date and prior trading-day closes inside "
                "fixed OHLCV snapshots; no filing or price lookahead added."
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


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["before_aggregate"])
    _write_json(RAW_FORM4_AGG_JSON, payload["raw_form4_aggregate"])
    _write_json(AFTER_AGG_JSON, payload["after_aggregate"])
    _write_tickets(payload)
    _write_manifest(payload)
    _write_report(payload)
    _append_experiment_log(payload)
    _update_registry(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
