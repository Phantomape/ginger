"""Slot-capacity replacement-value audit for Form 4 queue candidates.

This experiment is shadow-only. It does not change the Form 4 queue rule,
production entries, rankings, sizing, exits, or the core universe. It measures
whether historical Form 4 queue candidates would have had positive replacement
value after accounting for occupied MAX_POSITIONS slots and same-day accepted
core alternatives.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from constants import MAX_POSITIONS  # noqa: E402


EXP_ID = "exp-20260504-006"
SOURCE_REPLAY = DATA_DIR / "experiments" / "exp-20260504-005" / "form4_historical_forward_queue_replay.json"
ACCEPTED_TRADES = DATA_DIR / "experiments" / "current_accepted_trades_20260502_alpha_search.json"
ORACLE_DIR = DATA_DIR / "experiments" / "oracle_standard_3window_20260501_220042"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_slot_capacity_replacement_value.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
REGISTRY_JSON = DOCS_DIR / "experiment_registry.json"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_slot_capacity_replacement_value_20260504.md"

SNAPSHOT_FILES = [
    DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260501_with_pilot.json",
]
ORACLE_FILES = {
    "old_thin": ORACLE_DIR / "old_thin_entry_skip_oracle.json",
    "mid_weak": ORACLE_DIR / "mid_weak_entry_skip_oracle.json",
    "late_strong": ORACLE_DIR / "late_strong_entry_skip_oracle.json",
}
WINDOW_ORDER = ("old_thin", "mid_weak", "late_strong")
PRIMARY_HORIZON = "10"


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _load_price_map(snapshot_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in snapshot_paths:
        payload = _load_json(path, {})
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


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _forward_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    horizon: int,
) -> dict[str, Any] | None:
    rows = prices.get(str(ticker).upper())
    spy_rows = prices.get("SPY")
    qqq_rows = prices.get("QQQ")
    if not rows or not spy_rows or not qqq_rows:
        return None
    start_idx = _first_index_on_or_after(rows, entry_date)
    spy_start_idx = _first_index_on_or_after(spy_rows, entry_date)
    qqq_start_idx = _first_index_on_or_after(qqq_rows, entry_date)
    if start_idx is None or spy_start_idx is None or qqq_start_idx is None:
        return None
    exit_idx = start_idx + horizon
    spy_exit_idx = spy_start_idx + horizon
    qqq_exit_idx = qqq_start_idx + horizon
    if exit_idx >= len(rows) or spy_exit_idx >= len(spy_rows) or qqq_exit_idx >= len(qqq_rows):
        return None
    entry = rows[start_idx]
    exit_row = rows[exit_idx]
    spy_entry = spy_rows[spy_start_idx]
    spy_exit = spy_rows[spy_exit_idx]
    qqq_entry = qqq_rows[qqq_start_idx]
    qqq_exit = qqq_rows[qqq_exit_idx]
    if (
        not entry["open"]
        or not exit_row["close"]
        or not spy_entry["open"]
        or not spy_exit["close"]
        or not qqq_entry["open"]
        or not qqq_exit["close"]
    ):
        return None
    ret = exit_row["close"] / entry["open"] - 1.0
    spy_ret = spy_exit["close"] / spy_entry["open"] - 1.0
    qqq_ret = qqq_exit["close"] / qqq_entry["open"] - 1.0
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "return_pct": round(ret * 100.0, 4),
        "spy_return_pct": round(spy_ret * 100.0, 4),
        "qqq_return_pct": round(qqq_ret * 100.0, 4),
        "excess_vs_spy_pct": round((ret - spy_ret) * 100.0, 4),
        "excess_vs_qqq_pct": round((ret - qqq_ret) * 100.0, 4),
    }


def _flatten_accepted_trades(path: Path) -> list[dict[str, Any]]:
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
    return sorted(rows, key=lambda row: (row.get("entry_date") or "", row.get("ticker") or ""))


def _load_top_skipped_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, path in ORACLE_FILES.items():
        payload = _load_json(path, {})
        oracle = payload.get("entry_skip_oracle", {}) if isinstance(payload, dict) else {}
        for row in oracle.get("top_skipped_opportunities") or []:
            if isinstance(row, dict):
                rows.append({**row, "window": window})
    return sorted(rows, key=lambda row: (row.get("entry_date") or row.get("date") or "", row.get("ticker") or ""))


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _active_before_entry(trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    active = []
    for trade in trades:
        trade_entry = _date(trade.get("entry_date"))
        trade_exit = _date(trade.get("exit_date"))
        if not trade_entry or not trade_exit:
            continue
        if trade_entry < entry_date <= trade_exit:
            active.append(trade)
    return active


def _same_day_entries(trades: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    return [trade for trade in trades if _date(trade.get("entry_date")) == entry_date]


def _same_day_skipped(skipped_rows: list[dict[str, Any]], entry_date: str) -> list[dict[str, Any]]:
    return [
        row for row in skipped_rows
        if _date(row.get("entry_date") or row.get("date")) == entry_date
    ]


def _accepted_alt_payload(
    trade: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = _date(trade.get("entry_date"))
    outcome = _forward_return(prices, ticker, entry_date, int(PRIMARY_HORIZON)) if ticker and entry_date else None
    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "window": trade.get("window"),
        "entry_date": entry_date,
        "exit_date": trade.get("exit_date"),
        "final_trade_pnl_pct_net": (
            round(float(trade["pnl_pct_net"]) * 100.0, 4)
            if trade.get("pnl_pct_net") is not None
            else None
        ),
        "primary_horizon_outcome": outcome,
    }


def _skipped_alt_payload(row: dict[str, Any]) -> dict[str, Any]:
    max_forward = _float_or_none(row.get("max_forward_return_pct"))
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "strategy": row.get("strategy"),
        "window": row.get("window"),
        "decision": row.get("decision"),
        "entry_date": _date(row.get("entry_date") or row.get("date")),
        "available_slots_at_entry_loop": row.get("available_slots_at_entry_loop"),
        "max_forward_return_pct_upper_bound": (
            round(max_forward * 100.0, 4) if max_forward is not None else None
        ),
        "note": "oracle upper bound, not tradable replacement evidence",
    }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def _win_rate(values: list[float]) -> float | None:
    return round(sum(1 for value in values if value > 0.0) / len(values), 4) if values else None


def _capacity_state(slots_before_core: int, slots_after_core: int, same_day_count: int) -> str:
    if slots_after_core > 0:
        return "spare_slot_after_core_entries"
    if slots_before_core > 0 and same_day_count > 0:
        return "same_day_core_filled_last_slot"
    if slots_before_core <= 0:
        return "full_before_core_entries"
    return "unknown_capacity_state"


def _replacement_snapshot(
    candidate: dict[str, Any],
    *,
    accepted_trades: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entry_date = _date(candidate.get("entry_date"))
    if not entry_date:
        return {
            "ticker": candidate.get("ticker"),
            "usable_trade_date": candidate.get("usable_trade_date"),
            "window": candidate.get("window"),
            "status": "missing_price_history_no_slot_value",
            "primary_horizon_trading_days": int(PRIMARY_HORIZON),
        }

    candidate_outcome = (candidate.get("outcomes") or {}).get(PRIMARY_HORIZON)
    active = _active_before_entry(accepted_trades, entry_date)
    same_day = _same_day_entries(accepted_trades, entry_date)
    skipped = _same_day_skipped(skipped_rows, entry_date)
    slots_before_core = max(0, MAX_POSITIONS - len(active))
    slots_after_core = max(0, MAX_POSITIONS - len(active) - len(same_day))
    accepted_alts = [_accepted_alt_payload(trade, prices) for trade in same_day]
    skipped_alts = [_skipped_alt_payload(row) for row in skipped]

    candidate_spy_excess = (
        _float_or_none(candidate_outcome.get("excess_vs_spy_pct"))
        if isinstance(candidate_outcome, dict)
        else None
    )
    candidate_return = (
        _float_or_none(candidate_outcome.get("return_pct"))
        if isinstance(candidate_outcome, dict)
        else None
    )
    accepted_spy_excess = [
        alt["primary_horizon_outcome"]["excess_vs_spy_pct"]
        for alt in accepted_alts
        if alt.get("primary_horizon_outcome")
        and alt["primary_horizon_outcome"].get("excess_vs_spy_pct") is not None
    ]
    accepted_returns = [
        alt["primary_horizon_outcome"]["return_pct"]
        for alt in accepted_alts
        if alt.get("primary_horizon_outcome")
        and alt["primary_horizon_outcome"].get("return_pct") is not None
    ]
    skipped_upper_bounds = [
        alt["max_forward_return_pct_upper_bound"]
        for alt in skipped_alts
        if alt.get("max_forward_return_pct_upper_bound") is not None
    ]

    replacement = {
        "vs_cash_return_pct": candidate_return,
        "vs_spy_excess_pct": candidate_spy_excess,
        "vs_same_day_accepted_avg_spy_excess_pct": None,
        "vs_same_day_accepted_weakest_spy_excess_pct": None,
        "vs_same_day_accepted_best_spy_excess_pct": None,
        "vs_same_day_accepted_avg_return_pct": None,
        "vs_top_skipped_best_upper_bound_return_pct": None,
    }
    if candidate_spy_excess is not None and accepted_spy_excess:
        replacement["vs_same_day_accepted_avg_spy_excess_pct"] = round(
            candidate_spy_excess - (sum(accepted_spy_excess) / len(accepted_spy_excess)),
            6,
        )
        replacement["vs_same_day_accepted_weakest_spy_excess_pct"] = round(
            candidate_spy_excess - min(accepted_spy_excess),
            6,
        )
        replacement["vs_same_day_accepted_best_spy_excess_pct"] = round(
            candidate_spy_excess - max(accepted_spy_excess),
            6,
        )
    if candidate_return is not None and accepted_returns:
        replacement["vs_same_day_accepted_avg_return_pct"] = round(
            candidate_return - (sum(accepted_returns) / len(accepted_returns)),
            6,
        )
    if candidate_return is not None and skipped_upper_bounds:
        replacement["vs_top_skipped_best_upper_bound_return_pct"] = round(
            candidate_return - max(skipped_upper_bounds),
            6,
        )

    return {
        "ticker": candidate.get("ticker"),
        "usable_trade_date": candidate.get("usable_trade_date"),
        "entry_date": entry_date,
        "window": candidate.get("window"),
        "total_purchase_value": candidate.get("total_purchase_value"),
        "owner_count": candidate.get("owner_count"),
        "sample_owner_names": candidate.get("sample_owner_names"),
        "status": "closed_primary_outcome" if candidate_outcome else "missing_primary_outcome",
        "primary_horizon_trading_days": int(PRIMARY_HORIZON),
        "capacity": {
            "max_positions": MAX_POSITIONS,
            "active_positions_before_entry": len(active),
            "same_day_accepted_entries": len(same_day),
            "slots_before_core_entries": slots_before_core,
            "slots_after_core_entries": slots_after_core,
            "capacity_state": _capacity_state(slots_before_core, slots_after_core, len(same_day)),
            "active_tickers_before_entry": sorted({str(trade.get("ticker") or "").upper() for trade in active}),
        },
        "candidate_primary_outcome": candidate_outcome,
        "same_day_accepted_alternatives": accepted_alts,
        "same_day_top_skipped_oracle_alternatives": skipped_alts,
        "replacement_value": replacement,
    }


def _summarize_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in snapshots if row.get("status") == "closed_primary_outcome"]
    priced = [row for row in snapshots if row.get("entry_date")]
    states = Counter(
        ((row.get("capacity") or {}).get("capacity_state") or row.get("status"))
        for row in snapshots
    )
    same_day_conflicts = [
        row for row in closed
        if (row.get("capacity") or {}).get("same_day_accepted_entries", 0) > 0
    ]
    candidate_returns = [
        row["candidate_primary_outcome"]["return_pct"]
        for row in closed
        if row.get("candidate_primary_outcome")
        and row["candidate_primary_outcome"].get("return_pct") is not None
    ]
    candidate_spy_excess = [
        row["candidate_primary_outcome"]["excess_vs_spy_pct"]
        for row in closed
        if row.get("candidate_primary_outcome")
        and row["candidate_primary_outcome"].get("excess_vs_spy_pct") is not None
    ]
    vs_accepted_avg = [
        row["replacement_value"]["vs_same_day_accepted_avg_spy_excess_pct"]
        for row in same_day_conflicts
        if row.get("replacement_value", {}).get("vs_same_day_accepted_avg_spy_excess_pct") is not None
    ]
    vs_accepted_weakest = [
        row["replacement_value"]["vs_same_day_accepted_weakest_spy_excess_pct"]
        for row in same_day_conflicts
        if row.get("replacement_value", {}).get("vs_same_day_accepted_weakest_spy_excess_pct") is not None
    ]
    vs_skipped_upper = [
        row["replacement_value"]["vs_top_skipped_best_upper_bound_return_pct"]
        for row in closed
        if row.get("replacement_value", {}).get("vs_top_skipped_best_upper_bound_return_pct") is not None
    ]
    return {
        "candidate_count": len(snapshots),
        "priced_candidate_count": len(priced),
        "closed_primary_count": len(closed),
        "missing_price_history_count": sum(1 for row in snapshots if row.get("status") == "missing_price_history_no_slot_value"),
        "capacity_state_counts": dict(sorted(states.items())),
        "same_day_accepted_conflict_count": len(same_day_conflicts),
        "same_day_top_skipped_conflict_count": sum(
            1 for row in snapshots
            if row.get("same_day_top_skipped_oracle_alternatives")
        ),
        "candidate_10d": {
            "avg_return_pct": _mean(candidate_returns),
            "median_return_pct": _median(candidate_returns),
            "win_rate": _win_rate(candidate_returns),
            "avg_excess_vs_spy_pct": _mean(candidate_spy_excess),
            "median_excess_vs_spy_pct": _median(candidate_spy_excess),
            "excess_win_rate": _win_rate(candidate_spy_excess),
        },
        "replacement_vs_same_day_accepted": {
            "comparison_count": len(vs_accepted_avg),
            "avg_vs_accepted_avg_spy_excess_pct": _mean(vs_accepted_avg),
            "median_vs_accepted_avg_spy_excess_pct": _median(vs_accepted_avg),
            "positive_vs_accepted_avg_rate": _win_rate(vs_accepted_avg),
            "avg_vs_accepted_weakest_spy_excess_pct": _mean(vs_accepted_weakest),
            "positive_vs_accepted_weakest_rate": _win_rate(vs_accepted_weakest),
        },
        "replacement_vs_top_skipped_oracle_upper_bound": {
            "comparison_count": len(vs_skipped_upper),
            "avg_vs_best_upper_bound_return_pct": _mean(vs_skipped_upper),
            "positive_rate": _win_rate(vs_skipped_upper),
            "warning": "Uses top-skipped oracle max forward return; upper-bound only and not production evidence.",
        },
    }


def _by_window(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        window: _summarize_snapshots([row for row in snapshots if row.get("window") == window])
        for window in WINDOW_ORDER
    }


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update({
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "decision": payload["decision"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "candidate_count": payload["slot_capacity_metrics"]["aggregate"]["candidate_count"],
            "same_day_accepted_conflict_count": payload["slot_capacity_metrics"]["aggregate"]["same_day_accepted_conflict_count"],
            "next_action": payload["next_action"],
        },
    })
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update({
                "status": payload["status"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "result": {
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                    "reason": payload["decision_rationale"],
                },
            })
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _write_report(payload: dict[str, Any]) -> None:
    aggregate = payload["slot_capacity_metrics"]["aggregate"]
    lines = [
        "# Form 4 Slot Capacity Replacement Value",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Read",
        "",
        payload["decision_rationale"],
        "",
        "## Aggregate",
        "",
        f"- candidate_count: `{aggregate['candidate_count']}`",
        f"- priced_candidate_count: `{aggregate['priced_candidate_count']}`",
        f"- closed_primary_count: `{aggregate['closed_primary_count']}`",
        f"- same_day_accepted_conflict_count: `{aggregate['same_day_accepted_conflict_count']}`",
        f"- same_day_top_skipped_conflict_count: `{aggregate['same_day_top_skipped_conflict_count']}`",
        f"- capacity_state_counts: `{aggregate['capacity_state_counts']}`",
        "",
        "## Primary 10d Candidate Outcome",
        "",
        f"- avg_return_pct: `{_fmt(aggregate['candidate_10d']['avg_return_pct'])}`",
        f"- avg_excess_vs_spy_pct: `{_fmt(aggregate['candidate_10d']['avg_excess_vs_spy_pct'])}`",
        f"- excess_win_rate: `{_fmt(aggregate['candidate_10d']['excess_win_rate'])}`",
        "",
        "## Replacement Value",
        "",
        f"- same-day accepted comparison_count: `{aggregate['replacement_vs_same_day_accepted']['comparison_count']}`",
        f"- avg_vs_accepted_avg_spy_excess_pct: `{_fmt(aggregate['replacement_vs_same_day_accepted']['avg_vs_accepted_avg_spy_excess_pct'])}`",
        f"- positive_vs_accepted_avg_rate: `{_fmt(aggregate['replacement_vs_same_day_accepted']['positive_vs_accepted_avg_rate'])}`",
        f"- top-skipped upper-bound comparison_count: `{aggregate['replacement_vs_top_skipped_oracle_upper_bound']['comparison_count']}`",
        f"- avg_vs_best_upper_bound_return_pct: `{_fmt(aggregate['replacement_vs_top_skipped_oracle_upper_bound']['avg_vs_best_upper_bound_return_pct'])}`",
        "",
        "## By Window",
        "",
        "| Window | Candidates | Closed 10d | Same-day accepted conflicts | Avg 10d SPY excess | Avg replacement vs accepted avg |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOW_ORDER:
        row = payload["slot_capacity_metrics"]["by_window"][window]
        lines.append(
            f"| {window} | {row['candidate_count']} | {row['closed_primary_count']} | "
            f"{row['same_day_accepted_conflict_count']} | "
            f"{_fmt(row['candidate_10d']['avg_excess_vs_spy_pct'])} | "
            f"{_fmt(row['replacement_vs_same_day_accepted']['avg_vs_accepted_avg_spy_excess_pct'])} |"
        )
    lines.extend([
        "",
        "## Caveats",
        "",
        "- Same-day accepted alternatives are tradable proxies; top-skipped rows are oracle upper bounds and biased.",
        "- Existing full candidate signal history is not available, so this is not a full candidate-rank replay.",
        "- No production rule, sizing, or queue definition changed.",
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    source = _load_json(SOURCE_REPLAY, {})
    candidates = (source.get("shadow_or_replay_metrics") or {}).get("sample_candidates") or []
    accepted_trades = _flatten_accepted_trades(ACCEPTED_TRADES)
    skipped_rows = _load_top_skipped_rows()
    prices = _load_price_map(SNAPSHOT_FILES)
    snapshots = [
        _replacement_snapshot(
            candidate,
            accepted_trades=accepted_trades,
            skipped_rows=skipped_rows,
            prices=prices,
        )
        for candidate in candidates
    ]
    aggregate = _summarize_snapshots(snapshots)
    replacement_count = aggregate["replacement_vs_same_day_accepted"]["comparison_count"]
    avg_replacement = aggregate["replacement_vs_same_day_accepted"]["avg_vs_accepted_avg_spy_excess_pct"]
    if replacement_count >= 5 and avg_replacement and avg_replacement > 0:
        decision = "default_off_candidate_needs_full_rank_replay"
    else:
        decision = "shadow_only_capacity_inconclusive"
    rationale = (
        "Form 4 queue candidates still look positive as standalone 10d events, but "
        "capacity-aware replacement evidence is too thin for promotion. Only "
        f"{replacement_count} candidates have same-day accepted-trade alternatives "
        "for tradable slot comparison, so the slot value cannot yet be treated as "
        "stable alpha."
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "form4_slot_capacity_replacement_value_shadow",
        "hypothesis": (
            "Portfolio-capacity-aware replacement-value snapshots can show whether "
            "Form 4 forward queue candidates would have added value after accounting "
            "for occupied MAX_POSITIONS slots and same-day accepted alternatives."
        ),
        "non_ohlcv_data_source": "SEC Form 4 PIT-safe transaction rows, via exp-20260504-005 queue replay",
        "single_causal_variable": "Form 4 queue slot-capacity replacement value",
        "historical_experiment_check": {
            "source_experiment": "exp-20260504-005",
            "prior_findings": {
                "exp-20260504-005": "17 historical queue candidates; positive 10d returns but slot value not portfolio-capacity-aware",
                "exp-20260503-048": "accepted-trade overlay sparse",
                "exp-20260503-049": "top skipped overlap zero",
                "exp-20260503-053": "owner role discriminator rejected",
            },
            "why_this_is_not_repeat": (
                "This does not change Form 4 qualification. It only values the "
                "already-frozen queue candidates against occupied slots and same-day alternatives."
            ),
        },
        "baseline_metrics": source.get("baseline_metrics"),
        "after_metrics": source.get("after_metrics"),
        "expected_value_score_delta": source.get("expected_value_score_delta"),
        "data_availability": {
            **(source.get("data_availability") or {}),
            "source_replay": _repo_rel(SOURCE_REPLAY),
            "accepted_trades_file": _repo_rel(ACCEPTED_TRADES),
            "top_skipped_oracle_files": {
                window: _repo_rel(path) for window, path in ORACLE_FILES.items()
            },
            "pit_status": (
                "Form 4 candidates are PIT-safe by usable_trade_date. Accepted-trade replacement "
                "comparisons are shadow replay proxies; top-skipped comparisons are oracle-biased."
            ),
        },
        "slot_capacity_metrics": {
            "primary_horizon_trading_days": int(PRIMARY_HORIZON),
            "max_positions": MAX_POSITIONS,
            "aggregate": aggregate,
            "by_window": _by_window(snapshots),
            "snapshots": snapshots,
        },
        "candidate_overlap_and_slot_value": {
            "overlap_with_existing_signals": (
                (source.get("shadow_or_replay_metrics") or {}).get("overlap_with_existing_signals")
            ),
            "capacity_aware_replacement_summary": aggregate["replacement_vs_same_day_accepted"],
            "top_skipped_upper_bound_summary": aggregate["replacement_vs_top_skipped_oracle_upper_bound"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "shadow_slot_capacity_audit_only_no_strategy_change",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_shadow_slot_audit",
        },
        "decision_rationale": rationale,
        "next_action": (
            "Do not promote Form 4 entries yet. The next useful step is to capture "
            "full same-day candidate-rank snapshots from the production/backtest entry loop, "
            "so Form 4 can be compared against all rankable A/B candidates rather than only "
            "accepted trades and top-skipped oracle rows."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _update_ticket(payload)
    _update_registry(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["slot_capacity_metrics"]["aggregate"]
    compact = {
        "experiment_id": EXP_ID,
        "decision": payload["decision"],
        "candidate_count": aggregate["candidate_count"],
        "closed_primary_count": aggregate["closed_primary_count"],
        "capacity_state_counts": aggregate["capacity_state_counts"],
        "same_day_accepted_conflict_count": aggregate["same_day_accepted_conflict_count"],
        "replacement_vs_same_day_accepted": aggregate["replacement_vs_same_day_accepted"],
        "output": _repo_rel(OUT_JSON),
        "audit": _repo_rel(AUDIT_MD),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
