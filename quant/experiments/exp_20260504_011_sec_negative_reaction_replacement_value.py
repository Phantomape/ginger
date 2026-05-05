"""exp-20260504-011 SEC negative-reaction replacement-value audit.

This is an alpha-search measurement step after exp-20260504-010.  It keeps the
SEC packet frozen and asks whether the event sleeve would beat same-day A/B
accepted alternatives or occupied-slot alternatives.  It does not change
production entries, ranking, sizing, exits, or the core backtester.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from constants import MAX_POSITIONS, ROUND_TRIP_COST_PCT  # noqa: E402
from experiments.exp_20260504_008_sec_negative_reaction_absorption import (  # noqa: E402
    BASELINE_METRICS,
    WINDOWS,
)
from experiments.exp_20260504_010_sec_event_sleeve_backtest import (  # noqa: E402
    build_primary_candidates,
)


EXPERIMENT_ID = "exp-20260504-011"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_negative_reaction_replacement_value.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "sec_negative_reaction_replacement_value_20260504.md"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"

ACCEPTED_TRADES = DATA_DIR / "experiments" / "current_accepted_trades_20260502_alpha_search.json"
ORACLE_DIR = DATA_DIR / "experiments" / "oracle_standard_3window_20260501_220042"
ORACLE_FILES = {
    "old_thin": ORACLE_DIR / "old_thin_entry_skip_oracle.json",
    "mid_weak": ORACLE_DIR / "mid_weak_entry_skip_oracle.json",
    "late_strong": ORACLE_DIR / "late_strong_entry_skip_oracle.json",
}

PRIMARY_HORIZON = 10
WINDOW_ORDER = ("old_thin", "mid_weak", "late_strong")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe(value) for value in payload]
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _row_by_date(price_map: dict[str, list[dict[str, Any]]], ticker: str, date_value: str) -> dict[str, Any] | None:
    for row in price_map.get(str(ticker).upper(), []):
        if row["date"] == date_value:
            return row
    return None


def _return_between(
    price_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    round_trip_cost_pct: float,
) -> dict[str, Any] | None:
    start = _row_by_date(price_map, ticker, start_date)
    end = _row_by_date(price_map, ticker, end_date)
    spy_start = _row_by_date(price_map, "SPY", start_date)
    spy_end = _row_by_date(price_map, "SPY", end_date)
    if not start or not end or not spy_start or not spy_end:
        return None
    entry = start.get("open")
    exit_price = end.get("close")
    spy_entry = spy_start.get("open")
    spy_exit = spy_end.get("close")
    if not entry or not exit_price or not spy_entry or not spy_exit:
        return None
    gross = exit_price / entry - 1.0
    net = (exit_price / entry) * (1.0 - round_trip_cost_pct) - 1.0
    spy = spy_exit / spy_entry - 1.0
    return {
        "entry_date": start["date"],
        "exit_date": end["date"],
        "gross_return_pct": _round(gross * 100.0, 4),
        "net_return_pct": _round(net * 100.0, 4),
        "spy_return_pct": _round(spy * 100.0, 4),
        "net_excess_vs_spy_pct": _round((net - spy) * 100.0, 4),
    }


def forward_return(
    price_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    horizon_days: int = PRIMARY_HORIZON,
    *,
    round_trip_cost_pct: float = ROUND_TRIP_COST_PCT,
) -> dict[str, Any] | None:
    rows = price_map.get(str(ticker).upper())
    if not rows:
        return None
    start_idx = _idx_on_or_after(rows, entry_date)
    if start_idx is None:
        return None
    exit_idx = start_idx + horizon_days - 1
    if exit_idx >= len(rows):
        return None
    start = rows[start_idx]["date"]
    end = rows[exit_idx]["date"]
    return _return_between(
        price_map,
        ticker,
        start,
        end,
        round_trip_cost_pct=round_trip_cost_pct,
    )


def _flatten_accepted_trades(path: Path = ACCEPTED_TRADES) -> list[dict[str, Any]]:
    payload = _load_json(path, {})
    rows: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return rows
    for window, window_payload in payload.items():
        if not isinstance(window_payload, dict):
            continue
        for trade in window_payload.get("trades") or []:
            if isinstance(trade, dict):
                rows.append({**trade, "window": window})
    return sorted(rows, key=lambda row: (_date(row.get("entry_date")), str(row.get("ticker") or "")))


def _load_top_skipped_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, path in ORACLE_FILES.items():
        payload = _load_json(path, {})
        oracle = payload.get("entry_skip_oracle", {}) if isinstance(payload, dict) else {}
        for row in oracle.get("top_skipped_opportunities") or []:
            if isinstance(row, dict):
                rows.append({**row, "window": window})
    return sorted(rows, key=lambda row: (_date(row.get("entry_date") or row.get("date")), str(row.get("ticker") or "")))


def _active_before_entry(trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    active = []
    for trade in trades:
        trade_entry = _date(trade.get("entry_date"))
        trade_exit = _date(trade.get("exit_date"))
        if trade_entry and trade_exit and trade_entry < entry_date <= trade_exit:
            active.append(trade)
    return active


def _same_day_entries(trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    return [trade for trade in trades if _date(trade.get("entry_date")) == entry_date]


def _same_day_skipped(skipped_rows: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    return [row for row in skipped_rows if _date(row.get("entry_date") or row.get("date")) == entry_date]


def _accepted_alt(trade: dict[str, Any], price_map: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = _date(trade.get("entry_date"))
    outcome = forward_return(price_map, ticker, entry_date) if ticker and entry_date else None
    pnl_pct = trade.get("pnl_pct_net")
    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "window": trade.get("window"),
        "entry_date": entry_date,
        "exit_date": trade.get("exit_date"),
        "final_trade_pnl_pct_net": _round(float(pnl_pct) * 100.0, 4) if pnl_pct is not None else None,
        "primary_horizon_outcome": outcome,
    }


def _active_alt(trade: dict[str, Any], event_entry_date: str, price_map: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    trade_exit = _date(trade.get("exit_date"))
    outcome = None
    if ticker and trade_exit and event_entry_date <= trade_exit:
        outcome = _return_between(
            price_map,
            ticker,
            event_entry_date,
            trade_exit,
            round_trip_cost_pct=0.0,
        )
    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "window": trade.get("window"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "remaining_holding_proxy": outcome,
    }


def _skipped_alt(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("max_forward_return_pct")
    max_forward = float(value) * 100.0 if value is not None else None
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "strategy": row.get("strategy"),
        "window": row.get("window"),
        "decision": row.get("decision"),
        "entry_date": _date(row.get("entry_date") or row.get("date")),
        "available_slots_at_entry_loop": row.get("available_slots_at_entry_loop"),
        "max_forward_return_pct_upper_bound": _round(max_forward, 4),
        "note": "oracle upper bound, not tradable replacement evidence",
    }


def _capacity_state(slots_before_core: int, slots_after_core: int, same_day_count: int) -> str:
    if slots_after_core > 0:
        return "spare_slot_after_core_entries"
    if slots_before_core > 0 and same_day_count > 0:
        return "same_day_core_filled_last_slot"
    if slots_before_core <= 0:
        return "full_before_core_entries"
    return "unknown_capacity_state"


def _diff(candidate_value: float | None, alternatives: list[float], mode: str) -> float | None:
    if candidate_value is None or not alternatives:
        return None
    if mode == "avg":
        benchmark = sum(alternatives) / len(alternatives)
    elif mode == "weakest":
        benchmark = min(alternatives)
    elif mode == "best":
        benchmark = max(alternatives)
    else:
        raise ValueError(mode)
    return _round(candidate_value - benchmark, 6)


def replacement_snapshot(
    candidate: dict[str, Any],
    *,
    accepted_trades: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    price_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entry_date = _date(candidate.get("entry_date"))
    ticker = str(candidate.get("ticker") or "").upper()
    candidate_outcome = forward_return(price_map, ticker, entry_date) if ticker and entry_date else None
    active = _active_before_entry(accepted_trades, entry_date)
    same_day = _same_day_entries(accepted_trades, entry_date)
    skipped = _same_day_skipped(skipped_rows, entry_date)
    slots_before_core = max(0, MAX_POSITIONS - len(active))
    slots_after_core = max(0, MAX_POSITIONS - len(active) - len(same_day))

    accepted_alts = [_accepted_alt(trade, price_map) for trade in same_day]
    active_alts = [_active_alt(trade, entry_date, price_map) for trade in active]
    skipped_alts = [_skipped_alt(row) for row in skipped]

    candidate_excess = candidate_outcome.get("net_excess_vs_spy_pct") if candidate_outcome else None
    candidate_net = candidate_outcome.get("net_return_pct") if candidate_outcome else None
    accepted_excess = [
        alt["primary_horizon_outcome"]["net_excess_vs_spy_pct"]
        for alt in accepted_alts
        if alt.get("primary_horizon_outcome")
        and alt["primary_horizon_outcome"].get("net_excess_vs_spy_pct") is not None
    ]
    active_excess = [
        alt["remaining_holding_proxy"]["net_excess_vs_spy_pct"]
        for alt in active_alts
        if alt.get("remaining_holding_proxy")
        and alt["remaining_holding_proxy"].get("net_excess_vs_spy_pct") is not None
    ]
    skipped_upper = [
        alt["max_forward_return_pct_upper_bound"]
        for alt in skipped_alts
        if alt.get("max_forward_return_pct_upper_bound") is not None
    ]

    return {
        **candidate,
        "status": "closed_primary_outcome" if candidate_outcome else "missing_primary_outcome",
        "primary_horizon_trading_days": PRIMARY_HORIZON,
        "candidate_primary_outcome": candidate_outcome,
        "capacity": {
            "max_positions": MAX_POSITIONS,
            "active_positions_before_entry": len(active),
            "same_day_accepted_entries": len(same_day),
            "slots_before_core_entries": slots_before_core,
            "slots_after_core_entries": slots_after_core,
            "capacity_state": _capacity_state(slots_before_core, slots_after_core, len(same_day)),
            "active_tickers_before_entry": sorted({str(trade.get("ticker") or "").upper() for trade in active}),
        },
        "same_day_accepted_alternatives": accepted_alts,
        "active_slot_alternatives": active_alts,
        "same_day_top_skipped_oracle_alternatives": skipped_alts,
        "replacement_value": {
            "vs_cash_net_return_pct": candidate_net,
            "vs_spy_net_excess_pct": candidate_excess,
            "vs_same_day_accepted_avg_spy_excess_pct": _diff(candidate_excess, accepted_excess, "avg"),
            "vs_same_day_accepted_weakest_spy_excess_pct": _diff(candidate_excess, accepted_excess, "weakest"),
            "vs_same_day_accepted_best_spy_excess_pct": _diff(candidate_excess, accepted_excess, "best"),
            "vs_active_slot_avg_spy_excess_pct": _diff(candidate_excess, active_excess, "avg"),
            "vs_active_slot_weakest_spy_excess_pct": _diff(candidate_excess, active_excess, "weakest"),
            "vs_active_slot_best_spy_excess_pct": _diff(candidate_excess, active_excess, "best"),
            "vs_top_skipped_best_upper_bound_return_pct": (
                _round(candidate_net - max(skipped_upper), 6)
                if candidate_net is not None and skipped_upper
                else None
            ),
        },
    }


def _mean(values: list[float]) -> float | None:
    return _round(sum(values) / len(values), 6) if values else None


def _median(values: list[float]) -> float | None:
    return _round(statistics.median(values), 6) if values else None


def _win_rate(values: list[float]) -> float | None:
    return _round(sum(1 for value in values if value > 0.0) / len(values), 4) if values else None


def _collect(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = (row.get("replacement_value") or {}).get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _summarize_values(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "avg": _mean(values),
        "median": _median(values),
        "positive_rate": _win_rate(values),
        "min": _round(min(values), 6) if values else None,
        "max": _round(max(values), 6) if values else None,
    }


def summarize_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in snapshots if row.get("status") == "closed_primary_outcome"]
    candidate_returns = [
        row["candidate_primary_outcome"]["net_return_pct"]
        for row in closed
        if row.get("candidate_primary_outcome")
        and row["candidate_primary_outcome"].get("net_return_pct") is not None
    ]
    candidate_excess = [
        row["candidate_primary_outcome"]["net_excess_vs_spy_pct"]
        for row in closed
        if row.get("candidate_primary_outcome")
        and row["candidate_primary_outcome"].get("net_excess_vs_spy_pct") is not None
    ]
    return {
        "candidate_count": len(snapshots),
        "closed_primary_count": len(closed),
        "capacity_state_counts": dict(Counter((row.get("capacity") or {}).get("capacity_state") for row in snapshots)),
        "same_day_accepted_conflict_count": sum(
            1 for row in snapshots if (row.get("capacity") or {}).get("same_day_accepted_entries", 0) > 0
        ),
        "active_slot_full_count": sum(
            1 for row in snapshots if (row.get("capacity") or {}).get("slots_before_core_entries", 0) == 0
        ),
        "same_day_top_skipped_conflict_count": sum(
            1 for row in snapshots if row.get("same_day_top_skipped_oracle_alternatives")
        ),
        "candidate_10d": {
            "avg_net_return_pct": _mean(candidate_returns),
            "median_net_return_pct": _median(candidate_returns),
            "net_win_rate": _win_rate(candidate_returns),
            "avg_net_excess_vs_spy_pct": _mean(candidate_excess),
            "median_net_excess_vs_spy_pct": _median(candidate_excess),
            "excess_win_rate": _win_rate(candidate_excess),
        },
        "replacement_vs_same_day_accepted": {
            "avg_spy_excess": _summarize_values(_collect(snapshots, "vs_same_day_accepted_avg_spy_excess_pct")),
            "weakest_spy_excess": _summarize_values(_collect(snapshots, "vs_same_day_accepted_weakest_spy_excess_pct")),
            "best_spy_excess": _summarize_values(_collect(snapshots, "vs_same_day_accepted_best_spy_excess_pct")),
        },
        "replacement_vs_active_slots": {
            "avg_spy_excess": _summarize_values(_collect(snapshots, "vs_active_slot_avg_spy_excess_pct")),
            "weakest_spy_excess": _summarize_values(_collect(snapshots, "vs_active_slot_weakest_spy_excess_pct")),
            "best_spy_excess": _summarize_values(_collect(snapshots, "vs_active_slot_best_spy_excess_pct")),
        },
        "replacement_vs_top_skipped_oracle_upper_bound": {
            **_summarize_values(_collect(snapshots, "vs_top_skipped_best_upper_bound_return_pct")),
            "warning": "Uses top-skipped oracle max forward return; upper-bound only and not production evidence.",
        },
    }


def _by_window(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (window, summarize_snapshots([row for row in snapshots if row.get("window") == window]))
        for window in WINDOW_ORDER
    )


def build_payload() -> dict[str, Any]:
    candidates, price_map = build_primary_candidates()
    accepted_trades = _flatten_accepted_trades()
    skipped_rows = _load_top_skipped_rows()
    snapshots = [
        replacement_snapshot(
            candidate,
            accepted_trades=accepted_trades,
            skipped_rows=skipped_rows,
            price_map=price_map,
        )
        for candidate in candidates
    ]
    aggregate = summarize_snapshots(snapshots)
    active_avg = aggregate["replacement_vs_active_slots"]["avg_spy_excess"]
    accepted_avg = aggregate["replacement_vs_same_day_accepted"]["avg_spy_excess"]
    if (
        (active_avg["count"] or 0) >= 8
        and (active_avg["avg"] or 0.0) > 0.0
        and (accepted_avg["count"] or 0) >= 3
        and (accepted_avg["avg"] or 0.0) > 0.0
    ):
        status = "replacement_promising_not_promoted"
        rationale = (
            "The frozen SEC negative-language + negative-reaction packet has positive "
            "replacement value versus both active-slot and same-day accepted A/B proxies, "
            "but it remains shadow-only until a shared production/backtest event queue exists."
        )
    else:
        status = "replacement_inconclusive_not_promoted"
        rationale = (
            "The frozen SEC packet remains standalone-positive, but replacement evidence is "
            "not yet strong enough across same-day A/B alternatives to promote a core entry "
            "or ranking rule."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "hypothesis": (
            "The SEC negative-language + negative first-reaction packet should show positive "
            "10-trading-day replacement value versus same-day A/B accepted candidates or occupied "
            "A/B slots before it deserves any default-off production queue."
        ),
        "alpha_hypothesis": {
            "category": "event_source_slot_allocation",
            "entry_or_ranking": "entry_source_and_slot_allocation",
            "text": (
                "Recoverable-pressure SEC 8-K Item 2.02 events may be worth a scarce slot if their "
                "post-reaction drift beats same-day A/B opportunities."
            ),
        },
        "change_type": "non_ohlcv_event_replacement_value_shadow",
        "single_causal_variable": "SEC negative-language negative-reaction packet replacement-value measurement",
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-007": "positive filing text failed; negative language was shadow-positive",
                "exp-20260504-008": "negative_language + reaction_excess_return < 0 was positive across all three windows",
                "exp-20260504-010": "frozen packet survived standalone event-sleeve replay after costs and capacity",
            },
            "why_this_is_not_repeat": (
                "This does not tune keywords or reaction thresholds. It freezes the exp-010 packet "
                "and changes only the alpha question to scarce-slot replacement value."
            ),
            "mechanism_insight_check": (
                "Recent playbook says the valid next step is replacement-value replay versus same-day "
                "A/B candidates before any default-off queue or production promotion."
            ),
        },
        "parameters": {
            "packet_rule": "8-K Item 2.02 AND language_bucket == negative_language AND reaction_excess_return < 0",
            "packet_source": "exp-20260504-010 build_primary_candidates()",
            "primary_horizon_trading_days": PRIMARY_HORIZON,
            "candidate_outcome": "entry open to 10th trading-day close, round-trip cost applied",
            "same_day_accepted_proxy": "same-day accepted A/B trades, same 10-trading-day net outcome",
            "active_slot_proxy": "positions open before event entry, remaining return from event entry open to actual exit close, no new entry cost",
            "top_skipped_proxy": "same-day entry-skip oracle max forward return, upper-bound only",
            "locked_variables": [
                "keyword phrase list",
                "reaction threshold at < 0",
                "core A/B ranking",
                "core A/B sizing",
                "core A/B exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": 0.0,
        "replacement_value_metrics": {
            "aggregate": aggregate,
            "by_window": _by_window(snapshots),
            "snapshots": snapshots,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "shadow_replacement_value_only_no_core_strategy_logic_changed",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_shadow_replacement_value",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": rationale,
        "next_retry_requires": [
            "Do not tune keywords or nearby reaction thresholds around this result.",
            "If replacement value is positive, add a default-off production-visible SEC event queue using shared packet policy.",
            "Do not let the packet consume core A/B slots until queue samples have forward replacement-value attribution.",
        ],
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(REPORT_MD),
            "quant/experiments/exp_20260504_010_sec_event_sleeve_backtest.py",
            _repo_rel(ACCEPTED_TRADES),
            *[_repo_rel(path) for path in ORACLE_FILES.values()],
        ],
    }
    return _safe(payload)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def build_report(payload: dict[str, Any]) -> str:
    aggregate = payload["replacement_value_metrics"]["aggregate"]
    candidate = aggregate["candidate_10d"]
    accepted = aggregate["replacement_vs_same_day_accepted"]["avg_spy_excess"]
    active = aggregate["replacement_vs_active_slots"]["avg_spy_excess"]
    lines = [
        "# SEC Negative-Reaction Replacement Value",
        "",
        f"Experiment: `{EXPERIMENT_ID}`",
        f"Status: `{payload['status']}`",
        "",
        "## Headline",
        "",
        payload["decision_rationale"],
        "",
        "## Aggregate",
        "",
        f"- Candidates: `{aggregate['candidate_count']}`",
        f"- Closed primary outcomes: `{aggregate['closed_primary_count']}`",
        f"- Same-day accepted conflicts: `{aggregate['same_day_accepted_conflict_count']}`",
        f"- Full-before-core active-slot cases: `{aggregate['active_slot_full_count']}`",
        f"- Capacity states: `{aggregate['capacity_state_counts']}`",
        "",
        "## Candidate 10d Outcome",
        "",
        f"- Avg net return: `{_fmt_pct(candidate['avg_net_return_pct'])}`",
        f"- Avg net excess vs SPY: `{_fmt_pct(candidate['avg_net_excess_vs_spy_pct'])}`",
        f"- Excess win rate: `{_fmt_pct((candidate['excess_win_rate'] or 0) * 100 if candidate['excess_win_rate'] is not None else None)}`",
        "",
        "## Replacement Proxies",
        "",
        f"- Vs same-day accepted avg: count `{accepted['count']}`, avg `{_fmt_pct(accepted['avg'])}`, positive rate `{_fmt_pct((accepted['positive_rate'] or 0) * 100 if accepted['positive_rate'] is not None else None)}`",
        f"- Vs active-slot avg: count `{active['count']}`, avg `{_fmt_pct(active['avg'])}`, positive rate `{_fmt_pct((active['positive_rate'] or 0) * 100 if active['positive_rate'] is not None else None)}`",
        "",
        "## By Window",
        "",
        "| Window | Candidates | Avg 10d net excess vs SPY | Vs accepted avg | Vs active-slot avg |",
        "|---|---:|---:|---:|---:|",
    ]
    for window, row in payload["replacement_value_metrics"]["by_window"].items():
        lines.append(
            f"| {window} | {row['candidate_count']} | "
            f"{_fmt_pct(row['candidate_10d']['avg_net_excess_vs_spy_pct'])} | "
            f"{_fmt_pct(row['replacement_vs_same_day_accepted']['avg_spy_excess']['avg'])} | "
            f"{_fmt_pct(row['replacement_vs_active_slots']['avg_spy_excess']['avg'])} |"
        )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- This is shadow-only and does not change entries, ranking, sizing, exits, or production orders.",
            "- Active-slot replacement is a proxy based on accepted trade remaining returns, not a full portfolio counterfactual.",
            "- Top-skipped rows are oracle upper bounds and are not production evidence.",
            "- The packet rule is frozen from exp-20260504-010; keyword and reaction-threshold tuning are out of scope.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload["replacement_value_metrics"]
    return {
        key: value
        for key, value in payload.items()
        if key not in {"replacement_value_metrics"}
    } | {
        "replacement_value_metrics": {
            "aggregate": metrics["aggregate"],
            "by_window": metrics["by_window"],
        }
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "title": "SEC negative-reaction replacement value",
            "summary": payload["decision_rationale"],
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(REPORT_MD),
            "production_impact": payload["production_impact"],
            "next_retry_requires": payload["next_retry_requires"],
        },
    )
    _write_text(REPORT_MD, build_report(payload))

    existing_lines = (
        EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if EXPERIMENT_LOG.exists()
        else []
    )
    kept_lines = [
        line
        for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
        and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(_compact_log(payload), ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["replacement_value_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "candidate_count": aggregate["candidate_count"],
                "closed_primary_count": aggregate["closed_primary_count"],
                "candidate_10d": aggregate["candidate_10d"],
                "replacement_vs_same_day_accepted": aggregate["replacement_vs_same_day_accepted"],
                "replacement_vs_active_slots": aggregate["replacement_vs_active_slots"],
                "output": _repo_rel(OUT_JSON),
                "report": _repo_rel(REPORT_MD),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
