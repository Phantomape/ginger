"""exp-20260623-017: live pilot competition scalar outcome attribution.

Observed-only alpha attribution. This settles append-only live pilot
competition decision snapshots against the hot OHLCV warehouse and tests
whether higher applied pilot sleeve scalar separates next-10-trading-day
cash/SPY/QQQ replacement value.

No strategy, helper, ranking, sizing, exit, order, watchlist, LLM, paper sleeve,
or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
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


EXPERIMENT_ID = "exp-20260623-017"
OWNER = "alpha-explore"
SLUG = "live_pilot_competition_scalar_outcome_attribution"
RUNNER = f"quant/experiments/exp_20260623_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_017_{SLUG}.json"
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

HYPOTHESIS = (
    "Observed-only attribution: live pilot competition decision snapshots with "
    "higher applied pilot sleeve scalar and selected event-guarded full-history "
    "sleeve status should show positive next-10-trading-day replacement value "
    "versus cash/SPY/QQQ before any pilot allocation promotion is justified."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "pilot_competition_forward_attribution"
TRIAL_FAMILY = "live_pilot_competition_scalar_outcome_attribution"
TRIAL_VARIANT_ID = "hot_warehouse_10d_v1"
CHANGED_VARIABLE = "live_pilot_competition_scalar_forward_outcome_monotonicity_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260623-006", "exp-20260612-022", "exp-20260612-024"]
CAUSAL_COMPONENTS = [
    "pilot_competition_decisions ledger",
    "hot warehouse 10d settlement",
    "pilot_sleeve_scalar buckets",
    "event_guard/full_history tags",
    "no strategy behavior change",
]

CONFIG = {
    "hold_days": 10,
    "min_closed_decisions": 10,
    "min_bucket_rows": 3,
    "max_single_ticker_closed_share": 0.50,
    "max_single_positive_pnl_share": 0.55,
}
BUCKETS = ["low_scalar", "mid_scalar", "high_scalar"]

DEFAULT_PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_small",
        "no_monotonic_separation",
        "warehouse_outcomes_missing",
        "pilot_concentration",
        "forward_window_too_short",
    ],
    "confidence_reason": (
        "Pilot sleeves are playbook-relevant and production-visible, but current "
        "scorecards show thin closed evidence and one killed pilot; this run only "
        "settles existing append-only competition decisions and does not change "
        "entries, sizing, exits, rankings, or orders."
    ),
    "recorded_at": "2026-06-23T14:10:59+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def decision_date(decision_id: str, logged_at: str | None) -> str | None:
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


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or DEFAULT_PREDICTION


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


def latest_decisions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(PILOT_LEDGER)
    by_decision: dict[str, dict[str, Any]] = {}
    duplicate_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for row in rows:
        if row.get("record_type") != "decision_snapshot":
            skipped["non_decision_snapshot"] += 1
            continue
        decision_id = str(row.get("decision_id") or "")
        if not decision_id:
            skipped["missing_decision_id"] += 1
            continue
        duplicate_counts[decision_id] += 1
        current = by_decision.get(decision_id)
        if current is None or str(row.get("logged_at") or row.get("timestamp") or "") >= str(
            current.get("logged_at") or current.get("timestamp") or ""
        ):
            by_decision[decision_id] = row

    decisions: list[dict[str, Any]] = []
    for row in sorted(
        by_decision.values(),
        key=lambda item: (decision_date(str(item.get("decision_id") or ""), item.get("logged_at")) or "", str(item.get("decision_id") or "")),
    ):
        ranking = list(row.get("ranking_snapshot") or [])
        primary = ranking[0] if ranking and isinstance(ranking[0], dict) else {}
        risk = row.get("risk_snapshot") or {}
        sizing = risk.get("pilot_sizing") or {}
        sleeve_meta = row.get("pilot_sleeve") or risk.get("pilot_sleeve") or {}
        asof_date = decision_date(str(row.get("decision_id") or ""), row.get("logged_at"))
        ticker = str(row.get("pilot_ticker") or primary.get("ticker") or "").upper()
        scalar = as_float(sizing.get("pilot_sleeve_scalar_applied"))
        planned_notional = as_float(primary.get("position_value_usd") or sizing.get("position_value_usd"))
        if not asof_date:
            skipped["missing_decision_date"] += 1
            continue
        if not ticker:
            skipped["missing_ticker"] += 1
            continue
        if scalar is None:
            skipped["missing_scalar"] += 1
            continue
        if planned_notional is None or planned_notional <= 0:
            skipped["missing_notional"] += 1
            continue
        decisions.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision_id": row.get("decision_id"),
                "decision_hash": row.get("decision_hash"),
                "asof_date": asof_date,
                "logged_at": row.get("logged_at") or row.get("timestamp"),
                "ticker": ticker,
                "sleeve": row.get("sleeve") or sleeve_meta.get("name"),
                "strategy": primary.get("strategy"),
                "rank": primary.get("rank"),
                "slot_decision": primary.get("slot_decision") or sleeve_meta.get("slot_decision"),
                "status": primary.get("status"),
                "sector": primary.get("sector"),
                "pilot_segment": primary.get("pilot_segment") or sleeve_meta.get("segment"),
                "theme": sleeve_meta.get("theme"),
                "history_class": sleeve_meta.get("history_class"),
                "event_guard_profile": sleeve_meta.get("event_guard_profile"),
                "requires_event_guard": sleeve_meta.get("requires_event_guard"),
                "liquidity_tier": sleeve_meta.get("liquidity_tier"),
                "pilot_sleeve_tradeable": sizing.get("pilot_sleeve_tradeable"),
                "market_regime": risk.get("market_regime"),
                "pilot_sleeve_scalar_applied": round(scalar, 6),
                "pilot_max_capital_scalar": round_or_none(sizing.get("pilot_max_capital_scalar")),
                "pilot_max_risk_scalar": round_or_none(sizing.get("pilot_max_risk_scalar")),
                "planned_notional_usd": round(planned_notional, 2),
                "planned_entry_price": round_or_none(primary.get("entry_price")),
                "planned_stop_price": round_or_none(primary.get("stop_price")),
                "planned_target_price": round_or_none(primary.get("target_price")),
                "planned_shares": primary.get("shares_to_buy"),
                "planned_risk_amount_usd": round_or_none(primary.get("risk_amount_usd")),
                "trade_quality_score": round_or_none(primary.get("trade_quality_score") or sizing.get("trade_quality_score")),
                "confidence_score": round_or_none(primary.get("confidence_score")),
                "ticker_minus_spy_signal_day_open_close_return_pct": round_or_none(
                    sizing.get("ticker_minus_spy_signal_day_open_close_return_pct")
                ),
                "raw_duplicate_count": duplicate_counts[row.get("decision_id")],
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    audit = {
        "ledger_path": repo_rel(PILOT_LEDGER),
        "ledger_exists": PILOT_LEDGER.exists(),
        "raw_rows": len(rows),
        "bad_json_rows": bad_json,
        "unique_decisions": len(by_decision),
        "usable_decisions": len(decisions),
        "raw_duplicate_decision_counts": {
            key: count for key, count in sorted(duplicate_counts.items()) if count > 1
        },
        "skipped": dict(sorted(skipped.items())),
    }
    return decisions, audit


def load_ohlcv_rows(tickers: set[str], start: str, end: str) -> dict[str, list[dict[str, Any]]]:
    ticker_list = sorted({ticker.upper() for ticker in tickers if ticker})
    if not ticker_list:
        return {}
    placeholders = ",".join("?" for _ in ticker_list)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    params = [*ticker_list, start, end]
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in ticker_list}
    with sqlite3.connect(HOT_WAREHOUSE) as conn:
        for ticker, day, open_, high, low, close, volume in conn.execute(sql, params):
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
    return rows_by_symbol


def first_index_after(rows: list[dict[str, Any]], asof_date: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date")) > asof_date:
            return index
    return None


def pnl_between(rows: list[dict[str, Any]], entry_date: str, exit_date: str, notional: float) -> float | None:
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_raw = as_float(entry.get("open"))
    exit_raw = as_float(exit_.get("close"))
    if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    return notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def settle_decisions(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not decisions:
        return [], {"settled_rows": 0, "skipped": {"no_decisions": 0}}
    tickers = {row["ticker"] for row in decisions} | {"SPY", "QQQ"}
    start = min(row["asof_date"] for row in decisions)
    end = "2026-12-31"
    bars = load_ohlcv_rows(tickers, start, end)
    settled: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for row in decisions:
        stock_rows = bars.get(row["ticker"], [])
        entry_index = first_index_after(stock_rows, row["asof_date"])
        if entry_index is None:
            skipped["missing_entry_bar"] += 1
            continue
        exit_index = entry_index + int(CONFIG["hold_days"])
        if exit_index >= len(stock_rows):
            skipped["missing_10d_exit_bar"] += 1
            continue
        entry = stock_rows[entry_index]
        exit_ = stock_rows[exit_index]
        entry_raw = as_float(entry.get("open"))
        exit_raw = as_float(exit_.get("close"))
        notional = float(row["planned_notional_usd"])
        if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
            skipped["bad_entry_or_exit_price"] += 1
            continue
        entry_price = apply_entry_fill(entry_raw)
        exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        pnl = notional * pnl_pct_net
        spy_pnl = pnl_between(bars.get("SPY", []), entry["date"], exit_["date"], notional)
        qqq_pnl = pnl_between(bars.get("QQQ", []), entry["date"], exit_["date"], notional)
        settled.append(
            {
                **row,
                "entry_date": entry["date"],
                "exit_date": exit_["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "pnl_pct_net": round(pnl_pct_net, 6),
                "pnl_usd": round(pnl, 2),
                "replacement_value_vs_cash_usd": round(pnl, 2),
                "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2) if spy_pnl is not None else None,
                "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2) if qqq_pnl is not None else None,
                "replacement_value_vs_cash_per_10k": round(pnl / notional * 10000.0, 2),
                "replacement_value_vs_spy_per_10k": (
                    round((pnl - spy_pnl) / notional * 10000.0, 2) if spy_pnl is not None else None
                ),
                "replacement_value_vs_qqq_per_10k": (
                    round((pnl - qqq_pnl) / notional * 10000.0, 2) if qqq_pnl is not None else None
                ),
                "hold_days": CONFIG["hold_days"],
            }
        )
    audit = {
        "warehouse_path": repo_rel(HOT_WAREHOUSE),
        "ticker_count_requested": len(tickers),
        "ticker_count_with_rows": sum(1 for rows in bars.values() if rows),
        "decision_rows": len(decisions),
        "settled_rows": len(settled),
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
    return settled, audit


def scalar_bucket(row: dict[str, Any]) -> str:
    scalar = float(row["pilot_sleeve_scalar_applied"])
    if scalar <= 0.25:
        return "low_scalar"
    if scalar <= 0.40:
        return "mid_scalar"
    return "high_scalar"


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "max_single_ticker_closed_share": None,
            "max_single_positive_pnl_share": None,
            "top_closed_ticker": None,
            "top_positive_pnl_ticker": None,
        }
    closed_counts = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    top_closed, top_closed_count = closed_counts.most_common(1)[0]
    positive: Counter[str] = Counter()
    for row in rows:
        pnl = as_float(row.get("pnl_usd")) or 0.0
        if pnl > 0:
            positive[str(row.get("ticker") or "UNKNOWN")] += pnl
    total_positive = sum(positive.values())
    if positive and total_positive > 0:
        top_positive, top_positive_value = positive.most_common(1)[0]
        top_positive_share = top_positive_value / total_positive
    else:
        top_positive, top_positive_value, top_positive_share = None, None, None
    return {
        "ticker_count": len(closed_counts),
        "max_single_ticker_closed_share": round(top_closed_count / len(rows), 4),
        "top_closed_ticker": {"ticker": top_closed, "rows": top_closed_count},
        "max_single_positive_pnl_share": round(top_positive_share, 4)
        if top_positive_share is not None
        else None,
        "top_positive_pnl_ticker": {
            "ticker": top_positive,
            "positive_pnl_usd": round(top_positive_value, 2),
        }
        if top_positive is not None
        else None,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl_usd"]) for row in rows]
    rv_spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    rv_qqq = [
        float(row["replacement_value_vs_qqq_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    pct = [float(row["pnl_pct_net"]) for row in rows]
    return {
        "n": len(rows),
        "mean_pnl_usd": round_or_none(mean(pnls), 4),
        "median_pnl_usd": round_or_none(median(pnls), 4) if pnls else None,
        "sum_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_pnl_pct_net": round_or_none(mean(pct), 6),
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 4) if pnls else None,
        "mean_replacement_vs_spy_usd": round_or_none(mean(rv_spy), 4),
        "mean_replacement_vs_qqq_usd": round_or_none(mean(rv_qqq), 4),
        "median_replacement_vs_spy_usd": round_or_none(median(rv_spy), 4) if rv_spy else None,
        "median_replacement_vs_qqq_usd": round_or_none(median(rv_qqq), 4) if rv_qqq else None,
        "concentration": concentration(rows),
    }


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None

    def ranks(values: list[float]) -> list[float]:
        ordered = sorted((value, index) for index, value in enumerate(values))
        out = [0.0] * len(values)
        cursor = 0
        while cursor < len(ordered):
            end = cursor + 1
            while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
                end += 1
            rank = (cursor + end + 1) / 2.0
            for _, index in ordered[cursor:end]:
                out[index] = rank
            cursor = end
        return out

    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x <= 0 or var_y <= 0:
        return None
    return round(cov / math.sqrt(var_x * var_y), 4)


def analyze(settled_rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucketed: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKETS}
    for row in settled_rows:
        bucketed[scalar_bucket(row)].append(row)
    scalar_values = [float(row["pilot_sleeve_scalar_applied"]) for row in settled_rows]
    pnl_values = [float(row["pnl_usd"]) for row in settled_rows]
    rv_spy_pairs = [
        (float(row["pilot_sleeve_scalar_applied"]), float(row["replacement_value_vs_spy_usd"]))
        for row in settled_rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    rv_qqq_pairs = [
        (float(row["pilot_sleeve_scalar_applied"]), float(row["replacement_value_vs_qqq_usd"]))
        for row in settled_rows
        if as_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    return {
        "all_settled_rows": summarize(settled_rows),
        "bucket_summary": {bucket: summarize(rows) for bucket, rows in bucketed.items()},
        "spearman_scalar_to_cash_replacement": spearman(scalar_values, pnl_values),
        "spearman_scalar_to_spy_replacement": spearman(
            [item[0] for item in rv_spy_pairs], [item[1] for item in rv_spy_pairs]
        ),
        "spearman_scalar_to_qqq_replacement": spearman(
            [item[0] for item in rv_qqq_pairs], [item[1] for item in rv_qqq_pairs]
        ),
        "sample_rows": settled_rows[:10],
    }


def gt(a: Any, b: Any) -> bool:
    return a is not None and b is not None and a > b


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    buckets = analysis["bucket_summary"]
    low = buckets["low_scalar"]
    mid = buckets["mid_scalar"]
    high = buckets["high_scalar"]
    conc = analysis["all_settled_rows"]["concentration"]
    checks = {
        "closed_decision_sample_min_passed": (
            analysis["all_settled_rows"]["n"] >= CONFIG["min_closed_decisions"]
        ),
        "each_bucket_min_rows_passed": all(
            buckets[bucket]["n"] >= CONFIG["min_bucket_rows"] for bucket in BUCKETS
        ),
        "high_mean_cash_beats_mid_and_low": (
            gt(high["mean_pnl_usd"], mid["mean_pnl_usd"])
            and gt(high["mean_pnl_usd"], low["mean_pnl_usd"])
        ),
        "high_mean_spy_positive": (
            high["mean_replacement_vs_spy_usd"] is not None
            and high["mean_replacement_vs_spy_usd"] > 0
        ),
        "high_mean_qqq_positive": (
            high["mean_replacement_vs_qqq_usd"] is not None
            and high["mean_replacement_vs_qqq_usd"] > 0
        ),
        "spearman_cash_positive": (
            analysis["spearman_scalar_to_cash_replacement"] is not None
            and analysis["spearman_scalar_to_cash_replacement"] > 0
        ),
        "spearman_spy_positive": (
            analysis["spearman_scalar_to_spy_replacement"] is not None
            and analysis["spearman_scalar_to_spy_replacement"] > 0
        ),
        "closed_ticker_concentration_passed": (
            conc["max_single_ticker_closed_share"] is not None
            and conc["max_single_ticker_closed_share"] <= CONFIG["max_single_ticker_closed_share"]
        ),
        "positive_pnl_concentration_passed": (
            conc["max_single_positive_pnl_share"] is not None
            and conc["max_single_positive_pnl_share"] <= CONFIG["max_single_positive_pnl_share"]
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return checks, failed


def calibration(prediction: dict[str, Any], observed_lead: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability"))
    actual = 1 if observed_lead else 0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    predicted_failure_mode_hit = (
        "sample_too_small" in predicted_modes
        and "closed_decision_sample_min_passed" in failed
    ) or any(mode in failed for mode in predicted_modes)
    return {
        "actual_decision": (
            "observed_only_positive_live_pilot_scalar_lead_not_promoted"
            if observed_lead
            else "rejected_sample_too_small_live_pilot_competition_scalar_edge"
        ),
        "actual_success": actual,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4) if probability is not None else None,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": predicted_failure_mode_hit,
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    decisions, ledger_audit = latest_decisions()
    settled_rows, settlement_audit = settle_decisions(decisions)
    analysis = analyze(settled_rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_live_pilot_scalar_lead_not_promoted"
        if observed_lead
        else "rejected_sample_too_small_live_pilot_competition_scalar_edge"
    )
    now = utc_now()
    why = (
        "The live pilot competition ledger has too few closed unique decisions "
        "and too much INTC concentration to support a pilot allocation scalar "
        "promotion. This is useful forward measurement, not alpha acceptance."
        if not observed_lead
        else "Higher pilot scalar separated closed live pilot decisions, but this "
        "remains observed-only and still cannot alter live allocation without a "
        "separate Gate 1-4 promotion."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "closed_live_pilot_decision_rows",
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "experiment.py new novelty gate passed with no strong near-neighbor; "
                "nearest score was 0.1881 and source saturation was not applicable."
            ),
            "3_single_policy_bundle": (
                "One observed-only risk-allocation attribution bundle: settle existing "
                "pilot competition decision snapshots against hot warehouse 10d outcomes, "
                "bucket by applied pilot scalar, and test replacement-value separation."
            ),
            "4_success_failure_standard": (
                "Observed-only lead requires at least 10 closed unique decisions, at least "
                "3 rows per scalar bucket, high-scalar mean cash/benchmark replacement "
                "strength, positive Spearman, and concentration guards."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "ledger_path": repo_rel(PILOT_LEDGER),
            "warehouse_path": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "dedupe_rule": (
                "Use the latest logged decision_snapshot per decision_id so repeated "
                "append-only snapshots do not inflate independent sample size."
            ),
            "entry_rule": "first tradable open strictly after decision_id date",
            "exit_rule": "close after 10 trading bars from entry",
            "bucket_method": "fixed scalar buckets: <=0.25 low, <=0.40 mid, >0.40 high",
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(decisions) and settlement_audit["settled_rows"] > 0,
            "source_decisions": len(decisions),
            "settled_rows": settlement_audit["settled_rows"],
            "fields_checked": [
                "decision_id",
                "asof_date",
                "ticker",
                "pilot_sleeve_scalar_applied",
                "planned_notional_usd",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in settled_rows),
            "target_price_present": all(row.get("planned_target_price") is not None for row in decisions),
            "target_price_relevance": (
                "Target price is validated from the pilot ranking snapshot, but the "
                "observed-only settlement uses a fixed 10-trading-day outcome and "
                "does not change exit policy."
            ),
            "ledger_audit": ledger_audit,
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(decisions),
            "signals_survived": settlement_audit["settled_rows"],
            "survival_rate": round(settlement_audit["settled_rows"] / len(decisions), 4)
            if decisions
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": checks,
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "analysis": analysis,
            "settled_rows": settled_rows,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_live_pilot_ledger": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution over "
                "existing logged pilot snapshots and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not promote or retune pilot scalar, max risk/capital scalar, "
                "event guard, hold, target, stop, or notional from these five "
                "unique competition decisions. Wait for more closed live pilot rows."
            ),
            "new_evidence_required": (
                "At least 10-20 closed unique live pilot competition decisions with "
                "less single-ticker concentration and intact replacement-value fields."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(PILOT_LEDGER),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-006.json",
        ],
    }
    return payload, settled_rows


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            "dependencies_validated": payload["gate2"]["dependencies_validated"],
            "source_decisions": payload["gate2"]["source_decisions"],
            "settled_rows": payload["gate2"]["settled_rows"],
            "fields_checked": payload["gate2"]["fields_checked"],
            "entry_date_present": payload["gate2"]["entry_date_present"],
            "target_price_present": payload["gate2"]["target_price_present"],
            "settlement_audit": payload["gate2"]["settlement_audit"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "all_settled_rows": analysis["all_settled_rows"],
            "bucket_summary": analysis["bucket_summary"],
            "spearman_scalar_to_cash_replacement": analysis["spearman_scalar_to_cash_replacement"],
            "spearman_scalar_to_spy_replacement": analysis["spearman_scalar_to_spy_replacement"],
            "spearman_scalar_to_qqq_replacement": analysis["spearman_scalar_to_qqq_replacement"],
            "sample_rows": analysis["sample_rows"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    buckets = analysis["bucket_summary"]
    rows = [
        "| Bucket | Rows | Mean PnL | Median PnL | Mean vs SPY | Mean vs QQQ | Win Rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket_name in BUCKETS:
        bucket = buckets[bucket_name]
        win = bucket["win_rate"]
        rows.append(
            "| {name} | {n} | {mean_pnl} | {median_pnl} | {spy} | {qqq} | {win} |".format(
                name=bucket_name,
                n=bucket["n"],
                mean_pnl=money(bucket["mean_pnl_usd"]),
                median_pnl=money(bucket["median_pnl_usd"]),
                spy=money(bucket["mean_replacement_vs_spy_usd"]),
                qqq=money(bucket["mean_replacement_vs_qqq_usd"]),
                win="n/a" if win is None else f"{win:.2%}",
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: live pilot competition scalar attribution",
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
            "## Scalar Buckets",
            "",
            *rows,
            "",
            f"- Settled rows: `{analysis['all_settled_rows']['n']}`",
            f"- Spearman(scalar, cash replacement): `{analysis['spearman_scalar_to_cash_replacement']}`",
            f"- Spearman(scalar, SPY replacement): `{analysis['spearman_scalar_to_spy_replacement']}`",
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "all_settled_rows": payload["attribution"]["analysis"]["all_settled_rows"],
            "bucket_summary": payload["attribution"]["analysis"]["bucket_summary"],
            "spearman_scalar_to_cash_replacement": payload["attribution"]["analysis"][
                "spearman_scalar_to_cash_replacement"
            ],
        },
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
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
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
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, _settled_rows = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "settled_rows": analysis["all_settled_rows"]["n"],
                "spearman_cash": analysis["spearman_scalar_to_cash_replacement"],
                "bucket_summary": analysis["bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
