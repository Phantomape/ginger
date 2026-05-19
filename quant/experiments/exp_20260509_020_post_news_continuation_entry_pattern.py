"""exp-20260509-020 post-news continuation entry pattern.

Alpha search, shadow-only. This tests a single PEAD-like entry pattern without
touching the production core: after a PIT high-confidence earnings/results
filing event, only buy a fixed-notional satellite if the event trading day
already showed a positive price/volume reaction.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
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
    INITIAL_CAPITAL,
    ROUND_TRIP_COST_PCT,
    _combined_metrics,
    _core_metrics,
    _event_equity_curve,
    _gate4,
    _round,
)


EXPERIMENT_ID = "exp-20260509-020"
STEM = "post_news_continuation_entry_pattern"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260509_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

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
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

EVENT_SUBTYPE = "8k_item_2_02"
EVENT_REACTION_MIN_PCT = 1.0
EVENT_VOLUME_RATIO_MIN = 1.5
EVENT_REACTION_LOOKBACK_DAYS = 20
POST_EVENT_HOLD_TRADING_DAYS = 10
MAX_ACTIVE_POST_NEWS_POSITIONS = 5


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _date_tag(date_value: str) -> str:
    return str(date_value)[:10].replace("-", "")


def _norm_date(value: Any) -> str:
    text = str(value or "")[:10]
    if "-" in text:
        return text
    if len(text) >= 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


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
                    "open": _as_float(row.get("Open")),
                    "close": _as_float(row.get("Close")),
                    "volume": _as_float(row.get("Volume")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda item: item["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _trading_days(prices: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    return [row["date"] for row in prices.get("SPY", []) if start <= row["date"] <= end]


def _events_for_date(date_value: str) -> list[tuple[str, dict[str, Any]]]:
    path = REPO_ROOT / "data" / f"event_snapshot_{_date_tag(date_value)}.json"
    payload = _json_load(path, {})
    events_by_ticker = payload.get("events_by_ticker") if isinstance(payload, dict) else {}
    if not isinstance(events_by_ticker, dict):
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for ticker, events in events_by_ticker.items():
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("event_subtype") != EVENT_SUBTYPE:
                continue
            if event.get("source_confidence") != "high":
                continue
            if not event.get("point_in_time_complete"):
                continue
            out.append((str(ticker).upper(), event))
    return out


def _candidate_from_event(
    ticker: str,
    event: dict[str, Any],
    event_date: str,
    rows: list[dict[str, Any]],
    row_index: int,
) -> dict[str, Any]:
    if row_index < EVENT_REACTION_LOOKBACK_DAYS:
        return {"ticker": ticker, "event_date": event_date, "status": "insufficient_volume_lookback"}
    exit_idx = row_index + POST_EVENT_HOLD_TRADING_DAYS
    entry_idx = row_index + 1
    if exit_idx >= len(rows) or entry_idx >= len(rows):
        return {"ticker": ticker, "event_date": event_date, "status": "missing_forward_price"}

    previous = rows[row_index - 1]
    current = rows[row_index]
    entry = rows[entry_idx]
    exit_row = rows[exit_idx]
    previous_close = previous.get("close")
    current_close = current.get("close")
    entry_open = entry.get("open")
    exit_close = exit_row.get("close")
    if not previous_close or not current_close or not entry_open or not exit_close:
        return {"ticker": ticker, "event_date": event_date, "status": "missing_open_or_close"}

    volume_values = [
        row.get("volume")
        for row in rows[row_index - EVENT_REACTION_LOOKBACK_DAYS : row_index]
        if row.get("volume") is not None
    ]
    if len(volume_values) < EVENT_REACTION_LOOKBACK_DAYS:
        return {"ticker": ticker, "event_date": event_date, "status": "insufficient_volume_lookback"}
    avg_volume = sum(float(value) for value in volume_values) / len(volume_values)
    current_volume = current.get("volume")
    if not current_volume or avg_volume <= 0:
        return {"ticker": ticker, "event_date": event_date, "status": "missing_volume"}

    event_reaction_pct = (float(current_close) / float(previous_close) - 1.0) * 100.0
    volume_ratio = float(current_volume) / avg_volume
    if event_reaction_pct <= EVENT_REACTION_MIN_PCT:
        return {
            "ticker": ticker,
            "event_date": event_date,
            "status": "reaction_not_positive_enough",
            "event_reaction_pct": round(event_reaction_pct, 6),
            "volume_ratio": round(volume_ratio, 6),
        }
    if volume_ratio < EVENT_VOLUME_RATIO_MIN:
        return {
            "ticker": ticker,
            "event_date": event_date,
            "status": "volume_confirmation_missing",
            "event_reaction_pct": round(event_reaction_pct, 6),
            "volume_ratio": round(volume_ratio, 6),
        }

    gross_return = float(exit_close) / float(entry_open) - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    return {
        "ticker": ticker,
        "source": "post_news_continuation_earnings_8k",
        "status": "price_ready",
        "event_date": event_date,
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry_open), 6),
        "exit_close": round(float(exit_close), 6),
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "event_reaction_pct": round(event_reaction_pct, 6),
        "volume_ratio": round(volume_ratio, 6),
        "notional": EVENT_NOTIONAL,
        "shares": EVENT_NOTIONAL / float(entry_open),
        "pnl": round(EVENT_NOTIONAL * net_return, 2),
        "event_subtype": event.get("event_subtype"),
        "event_type": event.get("event_type"),
        "surprise_direction": event.get("surprise_direction"),
        "title": ((event.get("attributes") or {}).get("title")),
        "source_files": event.get("source_files"),
    }


def _build_candidates(
    prices: dict[str, list[dict[str, Any]]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    row_maps = {
        ticker: {row["date"]: idx for idx, row in enumerate(rows)}
        for ticker, rows in prices.items()
    }
    for event_date in _trading_days(prices, start, end):
        for ticker, event in _events_for_date(event_date):
            rows = prices.get(ticker)
            if not rows:
                rejected.append({"ticker": ticker, "event_date": event_date, "status": "missing_price_history"})
                continue
            row_index = row_maps.get(ticker, {}).get(event_date)
            if row_index is None:
                rejected.append({"ticker": ticker, "event_date": event_date, "status": "missing_event_day_price"})
                continue
            candidate = _candidate_from_event(ticker, event, event_date, rows, row_index)
            if candidate.get("status") == "price_ready":
                candidates.append(candidate)
            else:
                rejected.append(candidate)
    return candidates, rejected


def _select_trades(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready = [row for row in candidates if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            row["entry_date"],
            -float(row.get("event_reaction_pct") or 0.0),
            -float(row.get("volume_ratio") or 0.0),
            row["ticker"],
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = str(row["entry_date"])
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if any(trade.get("ticker") == row.get("ticker") for trade in active):
            skipped.append({**row, "skip_reason": "ticker_already_active"})
            continue
        if len(active) >= MAX_ACTIVE_POST_NEWS_POSITIONS:
            skipped.append(
                {
                    **row,
                    "skip_reason": "post_news_capacity_full",
                    "active_tickers": [trade.get("ticker") for trade in active],
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


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    baseline_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    by_window = OrderedDict()
    for label in WINDOWS:
        by_window[label] = {
            "expected_value_score": _round(
                float(after[label].get("expected_value_score") or 0.0)
                - float(before[label].get("expected_value_score") or 0.0),
                4,
            ),
            "sharpe_daily": _round(
                float(after[label].get("sharpe_daily") or 0.0)
                - float(before[label].get("sharpe_daily") or 0.0),
                4,
            ),
            "total_pnl": round(
                float(after[label].get("total_pnl") or 0.0)
                - float(before[label].get("total_pnl") or 0.0),
                2,
            ),
            "total_return_pct": _round(
                float(after[label].get("total_return_pct") or 0.0)
                - float(before[label].get("total_return_pct") or 0.0),
                4,
            ),
            "max_drawdown_pct": _round(
                float(after[label].get("max_drawdown_pct") or 0.0)
                - float(before[label].get("max_drawdown_pct") or 0.0),
                4,
            ),
            "win_rate": _round(
                float(after[label].get("win_rate") or 0.0)
                - float(before[label].get("win_rate") or 0.0),
                4,
            ),
            "trade_count": int(after[label].get("trade_count") or 0)
            - int(before[label].get("trade_count") or 0),
            "survival_rate": _round(
                float(after[label].get("survival_rate") or 0.0)
                - float(before[label].get("survival_rate") or 0.0),
                4,
            ),
        }
    return {
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
            1 for label in WINDOWS if by_window[label]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for label in WINDOWS if by_window[label]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(1 for label in WINDOWS if by_window[label]["total_pnl"] > 0),
        "windows_pnl_regressed": sum(1 for label in WINDOWS if by_window[label]["total_pnl"] < 0),
        "by_window": by_window,
    }


def _candidate_quality(selected: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row.get("status") or row.get("skip_reason") or "unknown") for row in rejected)
    selected_pnl = sum(float(row.get("pnl") or 0.0) for row in selected)
    selected_wins = sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0)
    return {
        "raw_price_ready_candidates": len(selected),
        "rejected_or_unqualified_count": len(rejected),
        "rejection_status_counts": dict(sorted(status_counts.items())),
        "selected_pnl": round(selected_pnl, 2),
        "selected_win_rate": round(selected_wins / len(selected), 4) if selected else None,
        "selected_avg_event_reaction_pct": _round(
            sum(float(row.get("event_reaction_pct") or 0.0) for row in selected) / len(selected)
            if selected
            else None,
            4,
        ),
        "selected_avg_volume_ratio": _round(
            sum(float(row.get("volume_ratio") or 0.0) for row in selected) / len(selected)
            if selected
            else None,
            4,
        ),
        "selected_by_ticker": dict(Counter(row.get("ticker") for row in selected)),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-020 Post-News Continuation Entry Pattern",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Rule",
        "",
        (
            "Shadow PEAD-like satellite: high-confidence `8k_item_2_02` event, "
            f"event-day close-to-close reaction > {EVENT_REACTION_MIN_PCT:.1f}%, "
            f"event-day volume >= {EVENT_VOLUME_RATIO_MIN:.1f}x prior 20-day average, "
            f"enter next open, exit on the {POST_EVENT_HOLD_TRADING_DAYS}th trading day after the event, "
            f"fixed ${EVENT_NOTIONAL:,.0f} notional, max {MAX_ACTIVE_POST_NEWS_POSITIONS} active positions."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Core EV | Variant EV | Delta EV | Core PnL | Variant PnL | Delta PnL | Event trades | Event PnL | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        shadow = payload["shadow_metrics"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} | {wr} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
                trades=shadow["selected_trade_count"],
                epnl=float(shadow["selected_pnl"]),
                wr=shadow["selected_win_rate"],
            )
        )
    agg = payload["delta_metrics"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV sum: {agg['baseline_ev_sum']:.4f} -> {agg['after_ev_sum']:.4f} ({agg['aggregate_ev_delta']:+.4f}, {agg['aggregate_ev_delta_pct']:+.2%})",
            f"- PnL sum: ${agg['baseline_pnl_sum']:,.2f} -> ${agg['after_pnl_sum']:,.2f} ({agg['aggregate_pnl_delta']:+,.2f}, {agg['aggregate_pnl_delta_pct']:+.2%})",
            f"- EV windows improved/regressed: {agg['windows_ev_improved']}/{agg['windows_ev_regressed']}",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "No production orders, shared core policy, sizing, ranking, exits, LLM/news prompt, or live universe changed. A positive retry would need a shared default-off post-news sleeve adapter before any promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXPERIMENT_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXPERIMENT_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "audit_report": _repo_rel(ARTIFACT_MD),
                "decision": payload["decision"],
                "aggregate_delta": payload["delta_metrics"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _json_load(REGISTRY_JSON, {"experiments": []})
    if not isinstance(registry, dict):
        registry = {"experiments": []}
    experiments = registry.setdefault("experiments", [])
    found = False
    for item in experiments:
        if item.get("experiment_id") == EXPERIMENT_ID:
            item.update(
                {
                    "status": payload["status"],
                    "lane": payload["lane"],
                    "owner": "alpha-search",
                    "hypothesis": payload["hypothesis"],
                    "ticket_file": _repo_rel(TICKET_JSON),
                    "updated_at": payload["timestamp"],
                }
            )
            found = True
            break
    if not found:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["lane"],
                "owner": "alpha-search",
                "hypothesis": payload["hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "updated_at": payload["timestamp"],
            }
        )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = _load_price_map()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    shadow_metrics: dict[str, dict[str, Any]] = OrderedDict()
    selected_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    skipped_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()

    for label, window in WINDOWS.items():
        core_result = _load_core_result(window)
        candidates, rejected = _build_candidates(prices, start=window["start"], end=window["end"])
        selected, capacity_skipped = _select_trades(candidates)
        event_curve = _event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(core_result)
        after_metrics[label] = _combined_metrics(core_result, event_curve, selected)
        selected_by_window[label] = selected
        skipped_by_window[label] = rejected + capacity_skipped
        quality = _candidate_quality(selected, rejected + capacity_skipped)
        shadow_metrics[label] = {
            "event_subtype": EVENT_SUBTYPE,
            "raw_candidate_count": len(candidates) + len(rejected),
            "qualified_price_ready_count": len(candidates),
            "selected_trade_count": len(selected),
            "capacity_skipped_count": len(capacity_skipped),
            "selected_pnl": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
            "selected_win_rate": quality["selected_win_rate"],
            "selected_avg_event_reaction_pct": quality["selected_avg_event_reaction_pct"],
            "selected_avg_volume_ratio": quality["selected_avg_volume_ratio"],
            "selected_by_ticker": quality["selected_by_ticker"],
            "rejection_status_counts": quality["rejection_status_counts"],
            "selected_trades": selected,
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(before_metrics[label], after_metrics[label]))
        for label in WINDOWS
    )
    passes_any_gate4 = any(
        any(
            row[key]
            for key in (
                "passes_material_ev",
                "passes_sharpe",
                "passes_drawdown",
                "passes_pnl",
                "passes_trade_count",
            )
        )
        for row in gate4_by_window.values()
    )
    majority_ev_positive = delta["windows_ev_improved"] >= 2 and delta["windows_ev_regressed"] <= 1
    aggregate_material = bool(
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
    )
    passed = bool(majority_ev_positive and aggregate_material and passes_any_gate4)
    decision = "accepted_shadow_lead_needs_shared_adapter" if passed else "rejected_positive_but_immaterial"
    status = "shadow_only" if passed else "rejected"
    decision_rationale = (
        "Accepted only as a shadow lead: the post-news continuation pattern clears materiality and majority-window checks, but production promotion still needs a shared default-off adapter and fresh forward replacement-value evidence."
        if passed
        else (
            "Rejected for production promotion. The PEAD-like post-news continuation pattern was positive in aggregate but did not clear Gate 4 materiality: the late_strong window was effectively flat while aggregate PnL/EV improvement was below the required threshold."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "change_type": "shadow_post_news_continuation_entry_pattern",
        "mechanism_family": "post_news_continuation_candidate_pool_extension",
        "hypothesis": (
            "A PEAD-like post-news continuation entry can add non-overlapping event-driven candidates when earnings/results news is confirmed by same-day price and volume follow-through."
        ),
        "alpha_hypothesis": {
            "category": "entry",
            "statement": (
                "High-confidence 8-K earnings/results events with >1% event-day price reaction and >=1.5x volume should continue over the next 10 trading days."
            ),
            "why_this_now": (
                "LLM soft-ranking and earnings-estimate revision data are still limited, while broad event-bundle/state-surface retunes have recent rejection guardrails. This tests a separate, fully replayable price-confirmed news reaction pattern."
            ),
        },
        "parameters": {
            "event_subtype": EVENT_SUBTYPE,
            "event_reaction_min_pct": EVENT_REACTION_MIN_PCT,
            "event_volume_ratio_min": EVENT_VOLUME_RATIO_MIN,
            "volume_lookback_trading_days": EVENT_REACTION_LOOKBACK_DAYS,
            "entry": "next trading day open after event day",
            "exit": f"close on trading day +{POST_EVENT_HOLD_TRADING_DAYS} from event day",
            "event_notional_usd": EVENT_NOTIONAL,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "max_active_positions": MAX_ACTIVE_POST_NEWS_POSITIONS,
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "add-ons",
                "LLM/news prompts",
                "event bundle source queues",
                "state-surface rules",
                "production order path",
            ],
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
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "recent_guardrails_checked": [
                "exp-20260509-024 rejected broad benchmark gates on event bundle",
                "exp-20260509-025 rejected state-surface self-leadership exception",
                "event bundle source/hold/notional retunes are banned without new evidence",
                "LLM soft-ranking and earnings-estimate revision alpha remain data-limited",
            ],
            "why_not_simple_repeat": (
                "This is not an event-bundle source subset, benchmark gate, state-surface exception, or LLM/news prompt change. It tests an independent PEAD-style price/volume-confirmed entry pattern in shadow mode."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": {
            "passed": passed,
            "gate4_by_window": gate4_by_window,
            "majority_ev_positive": majority_ev_positive,
            "aggregate_material": aggregate_material,
            "passes_any_window_gate4": passes_any_gate4,
            "acceptance_rule": (
                "Require majority-window EV improvement and aggregate EV >10% or aggregate PnL >5%, with at least one Gate 4 criterion, before any shared adapter work."
            ),
        },
        "shadow_metrics": shadow_metrics,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "production_signal_path_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": "This experiment deliberately avoids the current LLM replay coverage bottleneck.",
        },
        "single_causal_variable": "PEAD-like post-news continuation entry pattern",
        "decision_rationale": decision_rationale,
        "rejection_reason": None if passed else decision_rationale,
        "risk_of_change": (
            "The rule may over-select high-volume earnings spikes that already exhausted their move, especially in late strong tapes where core A/B already captures leadership better."
        ),
        "next_action": (
            "Do not promote or retune nearby price/volume thresholds on this same sample. A retry needs forward paper evidence or an orthogonal semantic earnings-quality field."
            if not passed
            else "Implement a shared default-off post-news sleeve adapter and collect forward replacement-value evidence before live/default promotion."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _append_experiment_log(payload)
    _update_ticket(payload)
    _update_registry(payload)
    print(json.dumps(_safe({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
