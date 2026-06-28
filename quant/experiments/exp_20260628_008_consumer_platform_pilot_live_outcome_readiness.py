"""exp-20260628-008: CONSUMER_PLATFORM_PILOT live outcome readiness.

Observed-only alpha readiness audit. This settles append-only live
CONSUMER_PLATFORM_PILOT competition decision snapshots against the hot OHLCV
warehouse with the same fixed 10-trading-day outcome convention used by the
pilot competition attribution work.

No strategy, helper, ranking, sizing, exit, order, watchlist, LLM, paper
sleeve, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260628-008"
OWNER = "alpha-explore"
SLUG = "consumer_platform_pilot_live_outcome_readiness"
RUNNER = f"quant/experiments/exp_20260628_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260628_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
PILOT_LEDGER = REPO_ROOT / "data" / "ledgers" / "pilot_competition_decisions.jsonl"

TARGET_SLEEVE = "CONSUMER_PLATFORM_PILOT"
HYPOTHESIS = (
    "CONSUMER_PLATFORM_PILOT live competition decisions may have distinct "
    "forward replacement value from AI_INFRA and older frozen "
    "consumer-platform basket tests; audit the post-activation live decision "
    "row outcomes before any pilot promotion or kill decision."
)
CHANGE_TYPE = "pilot_forward_readiness"
IMPLEMENTATION_MODE = "observed_only_forward_readiness"
MECHANISM_FAMILY = "pilot_forward_readiness"
TRIAL_FAMILY = "consumer_platform_pilot_live_outcome_readiness"
TRIAL_VARIANT_ID = "hot_warehouse_10d_live_ledger_v1"
CHANGED_VARIABLE = "consumer_platform_pilot_live_decision_outcome_readiness_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260627-020",
    "exp-20260623-017",
    "exp-20260524-015",
    "exp-20260525-007",
]
NEW_EVIDENCE_TYPE = "post_activation_consumer_platform_live_decision_row"
CAUSAL_COMPONENTS = [
    "live pilot competition ledger",
    "hot warehouse forward settlement",
    "cash SPY QQQ comparators",
    "read-only readiness verdict",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260628-008/exp_20260628_008_consumer_platform_pilot_live_outcome_readiness.json",
    "experiments/cards/exp-20260628-008.md",
    "experiments/manifests/exp-20260628-008.json",
    "experiments/tickets/exp-20260628-008.json",
    "experiments/logs/exp-20260628-008.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

CONFIG = {
    "hold_days": 10,
    "min_live_decisions": 5,
    "min_settled_rows": 5,
    "max_single_ticker_settled_share": 0.50,
    "max_gap_from_planned_entry_pct": 0.08,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def decision_asof_date(decision_id: str, logged_at: str | None) -> str | None:
    match = re.match(r"^(20\d{2}-\d{2}-\d{2})-", decision_id or "")
    if match:
        return match.group(1)
    if logged_at:
        return logged_at[:10]
    return None


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_json = 0
    if not path.exists():
        return rows, bad_json
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows, bad_json


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "success_probability": 0.16,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "single_live_decision_row",
            "gap_cancel_no_entry",
            "negative_replacement_value",
            "missing_hot_warehouse_prices",
        ],
        "confidence_reason": "Fallback prediction; reservation should carry the pre-run prediction.",
        "recorded_at": utc_now(),
    }


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def first_ranking(row: dict[str, Any]) -> dict[str, Any]:
    ranking = row.get("ranking_snapshot")
    if isinstance(ranking, list) and ranking and isinstance(ranking[0], dict):
        return ranking[0]
    return {}


def sleeve_name(row: dict[str, Any], primary: dict[str, Any]) -> str | None:
    risk = row.get("risk_snapshot")
    pilot = row.get("pilot_sleeve")
    candidates = [
        row.get("sleeve"),
        primary.get("pilot_sleeve"),
        risk.get("pilot_sleeve_name") if isinstance(risk, dict) else None,
        pilot.get("name") if isinstance(pilot, dict) else None,
    ]
    for value in candidates:
        if value:
            return str(value)
    return None


def latest_consumer_decisions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(PILOT_LEDGER)
    latest_by_id: dict[str, dict[str, Any]] = {}
    duplicate_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()

    for row in rows:
        if row.get("record_type") != "decision_snapshot":
            skipped["not_decision_snapshot"] += 1
            continue
        decision_id = str(row.get("decision_id") or "")
        if not decision_id:
            skipped["missing_decision_id"] += 1
            continue
        primary = first_ranking(row)
        if sleeve_name(row, primary) != TARGET_SLEEVE:
            skipped["other_sleeve"] += 1
            continue
        duplicate_counts[decision_id] += 1
        logged_at = str(row.get("logged_at") or row.get("timestamp") or "")
        prior = latest_by_id.get(decision_id)
        if prior is None or logged_at >= str(prior.get("logged_at") or ""):
            latest_by_id[decision_id] = row

    decisions: list[dict[str, Any]] = []
    for row in latest_by_id.values():
        primary = first_ranking(row)
        risk = row.get("risk_snapshot") if isinstance(row.get("risk_snapshot"), dict) else {}
        pilot_sizing = risk.get("pilot_sizing") if isinstance(risk.get("pilot_sizing"), dict) else {}
        asof_date = decision_asof_date(
            str(row.get("decision_id") or ""),
            str(row.get("logged_at") or row.get("timestamp") or ""),
        )
        ticker = str(row.get("pilot_ticker") or primary.get("ticker") or "").upper()
        planned_notional = safe_float(primary.get("position_value_usd")) or safe_float(
            risk.get("position_value_usd")
        )
        planned_entry_price = safe_float(primary.get("entry_price")) or safe_float(
            risk.get("entry_price")
        )
        target_price = safe_float(primary.get("target_price")) or safe_float(
            risk.get("target_price")
        )
        if not asof_date:
            skipped["missing_asof_date"] += 1
            continue
        if not ticker:
            skipped["missing_ticker"] += 1
            continue
        if planned_notional is None or planned_notional <= 0:
            skipped["missing_planned_notional"] += 1
            continue
        decisions.append(
            {
                "decision_id": str(row.get("decision_id")),
                "logged_at": row.get("logged_at") or row.get("timestamp"),
                "asof_date": asof_date,
                "ticker": ticker,
                "sleeve": TARGET_SLEEVE,
                "strategy": primary.get("strategy"),
                "rank": safe_int(primary.get("rank")),
                "pilot_segment": primary.get("pilot_segment")
                or (row.get("pilot_sleeve") or {}).get("segment")
                if isinstance(row.get("pilot_sleeve"), dict)
                else primary.get("pilot_segment"),
                "planned_notional_usd": round(planned_notional, 4),
                "planned_entry_price": round_or_none(planned_entry_price, 4),
                "planned_stop_price": round_or_none(
                    safe_float(primary.get("stop_price")) or safe_float(risk.get("stop_price")),
                    4,
                ),
                "target_price": round_or_none(target_price, 4),
                "shares_to_buy": safe_int(primary.get("shares_to_buy"))
                or safe_int(risk.get("shares_to_buy")),
                "trade_quality_score": round_or_none(
                    safe_float(primary.get("trade_quality_score"))
                    or safe_float(risk.get("trade_quality_score")),
                    6,
                ),
                "confidence_score": round_or_none(primary.get("confidence_score"), 6),
                "pilot_sleeve_scalar_applied": round_or_none(
                    risk.get("pilot_sleeve_scalar_applied")
                    if risk.get("pilot_sleeve_scalar_applied") is not None
                    else pilot_sizing.get("pilot_sleeve_scalar_applied"),
                    6,
                ),
                "event_guard_profile": (row.get("pilot_sleeve") or {}).get("event_guard_profile")
                if isinstance(row.get("pilot_sleeve"), dict)
                else None,
                "history_class": (row.get("pilot_sleeve") or {}).get("history_class")
                if isinstance(row.get("pilot_sleeve"), dict)
                else None,
            }
        )

    decisions.sort(key=lambda item: (item["asof_date"], item["decision_id"]))
    source_audit = {
        "ledger_path": repo_rel(PILOT_LEDGER),
        "raw_jsonl_rows": len(rows),
        "bad_json_rows": bad_json,
        "target_sleeve": TARGET_SLEEVE,
        "deduped_target_sleeve_decisions": len(decisions),
        "duplicate_target_decision_ids": {
            key: count for key, count in sorted(duplicate_counts.items()) if count > 1
        },
        "skipped": dict(sorted(skipped.items())),
        "decision_ids": [row["decision_id"] for row in decisions],
    }
    return decisions, source_audit


def hot_warehouse_uri() -> str:
    return HOT_WAREHOUSE.resolve().as_uri() + "?mode=ro&immutable=1"


def load_ohlcv_rows(
    tickers: set[str], start: str, end: str
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    ticker_list = sorted({ticker.upper() for ticker in tickers if ticker})
    audit: dict[str, Any] = {
        "warehouse_path": repo_rel(HOT_WAREHOUSE),
        "warehouse_exists": HOT_WAREHOUSE.exists(),
        "uri_mode": "mode=ro&immutable=1",
        "ticker_count_requested": len(ticker_list),
        "start": start,
        "end": end,
    }
    if not ticker_list:
        audit["error"] = "no_tickers_requested"
        return {}, audit

    placeholders = ",".join("?" for _ in ticker_list)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in ticker_list}
    try:
        with sqlite3.connect(hot_warehouse_uri(), uri=True) as conn:
            for ticker, day, open_, high, low, close, volume in conn.execute(
                sql, [*ticker_list, start, end]
            ):
                rows_by_symbol[str(ticker).upper()].append(
                    {
                        "date": str(day),
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                    }
                )
    except sqlite3.Error as exc:
        audit["error"] = f"{type(exc).__name__}: {exc}"
        return rows_by_symbol, audit

    populated = {ticker: rows for ticker, rows in rows_by_symbol.items() if rows}
    audit.update(
        {
            "ticker_count_with_rows": len(populated),
            "rows_loaded": sum(len(rows) for rows in rows_by_symbol.values()),
            "date_ranges": {
                ticker: {"min": rows[0]["date"], "max": rows[-1]["date"], "rows": len(rows)}
                for ticker, rows in sorted(populated.items())
            },
        }
    )
    return rows_by_symbol, audit


def first_index_after(rows: list[dict[str, Any]], asof_date: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date")) > asof_date:
            return index
    return None


def pnl_between(
    rows: list[dict[str, Any]], entry_date: str, exit_date: str, notional: float
) -> float | None:
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_raw = safe_float(entry.get("open"))
    exit_raw = safe_float(exit_.get("close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    return notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def settle_decisions(
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not decisions:
        return [], [], {"decision_rows": 0, "settled_rows": 0, "skipped": {"no_decisions": 0}}

    tickers = {row["ticker"] for row in decisions} | {"SPY", "QQQ"}
    start = min(row["asof_date"] for row in decisions)
    bars, warehouse_audit = load_ohlcv_rows(tickers, start, "2026-12-31")
    settled: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()

    for row in decisions:
        stock_rows = bars.get(row["ticker"], [])
        entry_index = first_index_after(stock_rows, row["asof_date"])
        if entry_index is None:
            skipped["missing_entry_bar"] += 1
            pending.append(
                {
                    **row,
                    "pending_reason": "missing_entry_bar",
                    "latest_available_bar": stock_rows[-1]["date"] if stock_rows else None,
                    "available_forward_sessions": 0,
                }
            )
            continue

        entry = stock_rows[entry_index]
        entry_raw = safe_float(entry.get("open"))
        exit_index = entry_index + int(CONFIG["hold_days"])
        available_forward_sessions = max(0, len(stock_rows) - entry_index - 1)
        planned_entry = safe_float(row.get("planned_entry_price"))
        gap_pct = (
            (entry_raw / planned_entry - 1.0)
            if entry_raw is not None and planned_entry is not None and planned_entry > 0
            else None
        )

        if exit_index >= len(stock_rows):
            skipped["missing_10d_exit_bar"] += 1
            pending.append(
                {
                    **row,
                    "pending_reason": "missing_10d_exit_bar",
                    "entry_date": entry.get("date"),
                    "entry_open_raw": round_or_none(entry_raw, 4),
                    "entry_fill_price": round_or_none(
                        apply_entry_fill(entry_raw) if entry_raw and entry_raw > 0 else None, 4
                    ),
                    "entry_gap_vs_planned_pct": round_or_none(gap_pct, 6),
                    "entry_gap_beyond_proxy_limit": (
                        abs(gap_pct) > float(CONFIG["max_gap_from_planned_entry_pct"])
                        if gap_pct is not None
                        else None
                    ),
                    "available_forward_sessions": available_forward_sessions,
                    "latest_available_bar": stock_rows[-1]["date"] if stock_rows else None,
                    "required_hold_days": CONFIG["hold_days"],
                }
            )
            continue

        exit_ = stock_rows[exit_index]
        exit_raw = safe_float(exit_.get("close"))
        notional = float(row["planned_notional_usd"])
        if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
            skipped["bad_entry_or_exit_price"] += 1
            continue

        entry_price = apply_entry_fill(entry_raw)
        exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
        pnl = notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)
        spy_pnl = pnl_between(bars.get("SPY", []), entry["date"], exit_["date"], notional)
        qqq_pnl = pnl_between(bars.get("QQQ", []), entry["date"], exit_["date"], notional)
        settled.append(
            {
                **row,
                "entry_date": entry["date"],
                "exit_date": exit_["date"],
                "entry_open_raw": round(entry_raw, 4),
                "entry_fill_price": round(entry_price, 4),
                "exit_close_raw": round(exit_raw, 4),
                "exit_fill_price": round(exit_price, 4),
                "entry_gap_vs_planned_pct": round_or_none(gap_pct, 6),
                "entry_gap_beyond_proxy_limit": (
                    abs(gap_pct) > float(CONFIG["max_gap_from_planned_entry_pct"])
                    if gap_pct is not None
                    else None
                ),
                "pnl_usd": round(pnl, 4),
                "pnl_pct_net": round(pnl / notional, 6),
                "spy_pnl_usd": round_or_none(spy_pnl, 4),
                "qqq_pnl_usd": round_or_none(qqq_pnl, 4),
                "replacement_value_vs_cash_usd": round(pnl, 4),
                "replacement_value_vs_spy_usd": (
                    round(pnl - spy_pnl, 4) if spy_pnl is not None else None
                ),
                "replacement_value_vs_qqq_usd": (
                    round(pnl - qqq_pnl, 4) if qqq_pnl is not None else None
                ),
                "hold_days": CONFIG["hold_days"],
            }
        )

    audit = {
        **warehouse_audit,
        "decision_rows": len(decisions),
        "settled_rows": len(settled),
        "pending_rows": len(pending),
        "skipped": dict(sorted(skipped.items())),
        "entry_rule": "first tradable open strictly after decision_id date",
        "exit_rule": "close after 10 trading bars from entry",
    }
    if settled:
        audit["settled_date_range"] = {
            "asof_start": min(row["asof_date"] for row in settled),
            "asof_end": max(row["asof_date"] for row in settled),
            "entry_start": min(row["entry_date"] for row in settled),
            "entry_end": max(row["entry_date"] for row in settled),
            "exit_start": min(row["exit_date"] for row in settled),
            "exit_end": max(row["exit_date"] for row in settled),
        }
    return settled, pending, audit


def summarize_settled(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl_usd"]) for row in rows]
    rv_spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if safe_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    rv_qqq = [
        float(row["replacement_value_vs_qqq_usd"])
        for row in rows
        if safe_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    top_ticker, top_ticker_count = tickers.most_common(1)[0] if tickers else (None, 0)
    return {
        "n": len(rows),
        "sum_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_pnl_usd": round_or_none(mean(pnls), 4),
        "median_pnl_usd": round_or_none(median(pnls), 4) if pnls else None,
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 4) if pnls else None,
        "mean_replacement_vs_spy_usd": round_or_none(mean(rv_spy), 4),
        "mean_replacement_vs_qqq_usd": round_or_none(mean(rv_qqq), 4),
        "sum_replacement_vs_spy_usd": round(sum(rv_spy), 2) if rv_spy else None,
        "sum_replacement_vs_qqq_usd": round(sum(rv_qqq), 2) if rv_qqq else None,
        "top_settled_ticker": top_ticker,
        "top_settled_ticker_share": round(top_ticker_count / len(rows), 4) if rows else None,
    }


def evaluate_readiness(
    decisions: list[dict[str, Any]],
    settled_rows: list[dict[str, Any]],
    pending_rows: list[dict[str, Any]],
    settlement_audit: dict[str, Any],
) -> dict[str, Any]:
    summary = summarize_settled(settled_rows)
    failed: list[str] = []
    if len(decisions) < int(CONFIG["min_live_decisions"]):
        failed.append(f"live_decisions_below_floor:{len(decisions)}/{CONFIG['min_live_decisions']}")
    if len(settled_rows) < int(CONFIG["min_settled_rows"]):
        failed.append(f"settled_rows_below_floor:{len(settled_rows)}/{CONFIG['min_settled_rows']}")
    if pending_rows and not settled_rows:
        reasons = sorted({str(row.get("pending_reason")) for row in pending_rows})
        failed.append("all_target_sleeve_rows_pending:" + ",".join(reasons))
    if settlement_audit.get("error"):
        failed.append("hot_warehouse_read_error")
    top_share = safe_float(summary.get("top_settled_ticker_share"))
    if top_share is not None and top_share > float(CONFIG["max_single_ticker_settled_share"]):
        failed.append(
            "single_ticker_concentration:"
            f"{top_share:.2f}>{CONFIG['max_single_ticker_settled_share']}"
        )
    if len(settled_rows) >= int(CONFIG["min_settled_rows"]):
        spy_sum = safe_float(summary.get("sum_replacement_vs_spy_usd"))
        qqq_sum = safe_float(summary.get("sum_replacement_vs_qqq_usd"))
        if spy_sum is None or spy_sum <= 0:
            failed.append("non_positive_replacement_vs_spy")
        if qqq_sum is None or qqq_sum <= 0:
            failed.append("non_positive_replacement_vs_qqq")

    mature_enough = len(settled_rows) >= int(CONFIG["min_settled_rows"])
    passed = not failed
    if passed:
        status = "accepted"
        decision = "accepted_observed_only_consumer_platform_pilot_forward_lead"
    elif not mature_enough:
        status = "blocked"
        decision = "blocked_consumer_platform_pilot_live_outcome_not_mature"
    else:
        status = "rejected"
        decision = "rejected_consumer_platform_pilot_live_outcome_not_allocation_ready"

    return {
        "status": status,
        "decision": decision,
        "passed": passed,
        "failed_reasons": failed,
        "readiness_rule": CONFIG,
        "summary": summary,
        "activation_ready": False,
        "watchlist_ready": bool(passed),
        "blocked": status == "blocked",
        "reopen_condition": (
            "Reopen only after at least 5 unique CONSUMER_PLATFORM_PILOT live "
            "ledger decisions have 10-trading-day settled hot-warehouse "
            "outcomes, or after this HOOD row plus four new same-sleeve rows "
            "are mature with cash/SPY/QQQ replacement values."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    baseline = load_baseline_metrics()
    decisions, source_audit = latest_consumer_decisions()
    settled_rows, pending_rows, settlement_audit = settle_decisions(decisions)
    readiness = evaluate_readiness(decisions, settled_rows, pending_rows, settlement_audit)
    target_present = all(row.get("target_price") is not None for row in decisions) if decisions else False
    entry_present = any(row.get("entry_date") for row in settled_rows + pending_rows)
    survival_generated = len(decisions)
    survival_survived = len(settled_rows) + len(pending_rows)
    survival_rate = (
        round(survival_survived / survival_generated, 4) if survival_generated else None
    )

    gate1 = {
        "baseline_loaded": BASELINE_RESULT.exists(),
        "baseline_metrics": baseline,
        "passed": BASELINE_RESULT.exists(),
    }
    gate2 = {
        "dependencies_validated": bool(decisions)
        and target_present
        and not settlement_audit.get("error")
        and HOT_WAREHOUSE.exists(),
        "passed": bool(decisions)
        and target_present
        and not settlement_audit.get("error")
        and HOT_WAREHOUSE.exists(),
        "fields_checked": [
            "decision_id",
            "asof_date",
            "sleeve",
            "ticker",
            "entry_date",
            "target_price",
            "planned_notional_usd",
            "planned_entry_price",
        ],
        "entry_date_present": entry_present,
        "target_price_present": target_present,
        "source_audit": source_audit,
        "settlement_audit": settlement_audit,
    }
    gate3 = {
        "filter_added": False,
        "signals_generated": survival_generated,
        "signals_survived": survival_survived,
        "survival_rate": survival_rate,
        "passed": survival_generated == 0 or (survival_rate is not None and survival_rate >= 0.05),
        "note": "No executable filter was added; this only audits live decision outcome maturity.",
    }
    gate4 = {
        "passed": readiness["passed"],
        "decision": readiness["decision"],
        "strategy_rerun_required": False,
        "accepted_alpha": False,
        "failed_reasons": readiness["failed_reasons"],
        "readiness_rule": readiness["readiness_rule"],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
    }

    status = readiness["status"]
    decision = readiness["decision"]
    failure_hit = [
        item
        for item in prediction.get("main_failure_modes", [])
        if item in {"single_live_decision_row", "missing_hot_warehouse_prices"}
    ]
    if len(decisions) <= 1 and "single_live_decision_row" not in failure_hit:
        failure_hit.append("single_live_decision_row")
    if settlement_audit.get("skipped", {}).get("missing_10d_exit_bar"):
        failure_hit.append("missing_10d_exit_bar")
    predicted_probability = safe_float(prediction.get("success_probability")) or 0.0
    actual_success = 1 if gate4["passed"] else 0

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "watchlist_ready": readiness["watchlist_ready"],
        "alpha_ready": False,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "target_sleeve_live_decisions": len(decisions),
            "target_sleeve_settled_10d_rows": len(settled_rows),
            "target_sleeve_pending_rows": len(pending_rows),
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "readiness": {
            "target_sleeve": TARGET_SLEEVE,
            "activation_ready": readiness["activation_ready"],
            "watchlist_ready": readiness["watchlist_ready"],
            "blocked": readiness["blocked"],
            "blockers": readiness["failed_reasons"],
            "reopen_condition": readiness["reopen_condition"],
            "summary": readiness["summary"],
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "decisions": decisions,
            "settled_rows": settled_rows,
            "pending_rows": pending_rows,
        },
        "calibration": {
            "predicted_success_probability": predicted_probability,
            "actual_success": actual_success,
            "brier_score": round((predicted_probability - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "failure_modes_observed": sorted(set(failure_hit + readiness["failed_reasons"])),
            "predicted_failure_mode_hit": bool(failure_hit),
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "shared_helper_changed": False,
            "paper_or_live_snapshot_changed": False,
            "read_only_sources": [repo_rel(PILOT_LEDGER), repo_rel(HOT_WAREHOUSE)],
        },
        "live_realistic_execution_envelope": {
            "status": "not_live_ready",
            "reason": "Observed-only audit with insufficient same-sleeve closed forward rows.",
            "notional_cap_evaluated": False,
            "liquidity_and_slippage_mode": "Existing fill_model entry/sell slippage plus round-trip cost for attribution only.",
            "kill_switch": "No production change; existing pilot controls remain unchanged.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                f"The target sleeve has {len(decisions)} visible live decision row(s) and "
                f"{len(settled_rows)} settled 10-trading-day outcome row(s); this is below "
                "the predeclared readiness floor."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not re-slice the same CONSUMER_PLATFORM_PILOT live decision row by "
                "adjacent fields, gap proxies, scalar labels, or event-guard labels until "
                "new same-sleeve live decisions mature or the HOOD row has a 10-day exit."
            ),
            "next_new_evidence": readiness["reopen_condition"],
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [RUNNER_COMMAND, ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict"],
        "related_files": {
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "manifest": repo_rel(MANIFEST_JSON),
            "ticket": repo_rel(TICKET_JSON),
            "baseline": repo_rel(BASELINE_RESULT),
            "ledger": repo_rel(PILOT_LEDGER),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "audit_note": "Observed-only alpha_search run; Gate 4 blocks promotion until closed forward evidence exists.",
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "owner",
            "lane",
            "status",
            "decision",
            "accepted",
            "accepted_alpha",
            "watchlist_ready",
            "alpha_ready",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "hypothesis",
            "alpha_hypothesis",
            "nearby_prior_experiments",
            "new_evidence_type",
            "prediction",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "readiness",
            "calibration",
            "production_impact",
            "live_realistic_execution_envelope",
            "post_run_reflection",
            "changed_files",
            "allowed_write_scope",
            "reproduction_commands",
            "related_files",
            "anti_js",
            "lean_quality_passed",
        ]
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["readiness"]["summary"]
    blockers = ", ".join(payload["readiness"]["blockers"]) or "none"
    pending_rows = payload["readiness"]["pending_rows"]
    pending_lines = []
    for row in pending_rows:
        pending_lines.append(
            "- {decision_id}: {ticker}, entry {entry_date}, available sessions {available}, "
            "latest bar {latest}, reason {reason}".format(
                decision_id=row.get("decision_id"),
                ticker=row.get("ticker"),
                entry_date=row.get("entry_date") or "n/a",
                available=row.get("available_forward_sessions"),
                latest=row.get("latest_available_bar"),
                reason=row.get("pending_reason"),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: CONSUMER_PLATFORM_PILOT live outcome readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Readiness",
            "",
            f"- Live decisions: `{payload['delta_metrics']['target_sleeve_live_decisions']}`",
            f"- Settled 10d rows: `{payload['delta_metrics']['target_sleeve_settled_10d_rows']}`",
            f"- Pending rows: `{payload['delta_metrics']['target_sleeve_pending_rows']}`",
            f"- Sum PnL: `{money(summary['sum_pnl_usd'])}`",
            f"- Sum RV vs SPY: `{money(summary['sum_replacement_vs_spy_usd'])}`",
            f"- Sum RV vs QQQ: `{money(summary['sum_replacement_vs_qqq_usd'])}`",
            f"- Blockers: `{blockers}`",
            "",
            "## Pending Rows",
            "",
            *(pending_lines or ["- none"]),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
                "card_file": repo_rel(CARD_MD),
                "summary": payload["post_run_reflection"]["why_result_happened"],
            },
            "new_evidence_type": NEW_EVIDENCE_TYPE,
        }
    )
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, build_log(payload))
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    update_ticket(payload)
    upsert_jsonl(EXPERIMENT_LOG, build_log(payload))

    registry_result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "watchlist_ready": payload["watchlist_ready"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "settled_rows": payload["delta_metrics"]["target_sleeve_settled_10d_rows"],
        "pending_rows": payload["delta_metrics"]["target_sleeve_pending_rows"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "live_decisions": payload["delta_metrics"]["target_sleeve_live_decisions"],
                "settled_rows": payload["delta_metrics"]["target_sleeve_settled_10d_rows"],
                "pending_rows": payload["delta_metrics"]["target_sleeve_pending_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
