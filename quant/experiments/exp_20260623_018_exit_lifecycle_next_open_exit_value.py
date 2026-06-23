"""exp-20260623-018: exit-lifecycle next-open exit value attribution.

Observed-only alpha attribution. This runner tests the execution-envelope
question left open by prior exit-lifecycle forward-loss diagnostics: whether
high-pressure production shadow rows would have benefited from a next-open
diagnostic sell versus continuing to hold for five trading days.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
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
from fill_model import (  # noqa: E402
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_TARGET,
    apply_slippage,
)
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260623-018"
SLUG = "exit_lifecycle_next_open_exit_value"
RUNNER = f"quant/experiments/exp_20260623_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SOURCE_DIR = REPO_ROOT / "data" / "exit_lifecycle"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Observed-only exit/risk attribution: production exit-lifecycle "
    "high-pressure rows are only actionable if a next-open diagnostic early "
    "exit avoids the subsequent 5-trading-day holding loss and preserves "
    "positive cash/SPY/QQQ replacement value after sell-side execution "
    "assumptions."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_execution_value_attribution"
TRIAL_FAMILY = "exit_lifecycle_next_open_exit_value_attribution"
TRIAL_VARIANT_ID = "next_open_exit_vs_5d_hold_cash_spy_qqq_v1"
CHANGED_VARIABLE = "exit_lifecycle_next_open_exit_replacement_value_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-011",
    "exp-20260623-016",
    "exp-20260623-015",
    "exp-20260623-012",
    "exp-20260623-003",
]
NEW_EVIDENCE_TYPE = "forward_production_exit_lifecycle_rows_with_execution_envelope"
NEW_EVIDENCE_AXIS = (
    "Next-open executable sell value and released-cash/SPY/QQQ replacement "
    "value versus continuing to hold the exact production position. This is "
    "not a severity, target, stop, target-width, LLM-state, or above-cost "
    "threshold retry."
)
CAUSAL_COMPONENTS = [
    "production exit-lifecycle shadow logs",
    "next-open sell execution envelope",
    "hold-vs-cash-SPY-QQQ replacement value",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-018/exp_20260623_018_exit_lifecycle_next_open_exit_value.json",
    "experiments/cards/exp-20260623-018.md",
    "experiments/manifests/exp-20260623-018.json",
    "experiments/tickets/exp-20260623-018.json",
    "experiments/logs/exp-20260623-018.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
CONFIG = {
    "hold_days": 5,
    "min_settled_rows": 100,
    "min_pressure_rows": 20,
    "min_comparable_dates": 6,
    "min_pressure_better_dates": 4,
    "max_single_positive_cash_value_share": 0.50,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_small",
        "ticker_concentration",
        "no_cash_replacement_edge",
        "no_benchmark_replacement_edge",
        "current_loss_endogeneity",
    ],
    "confidence_reason": (
        "Recent production exit-lifecycle and LLM state rows showed forward "
        "loss separation, but confluence and above-cost checks exposed "
        "overlap/concentration; this run tests the missing execution-envelope "
        "question rather than retuning exit labels."
    ),
    "recorded_at": "2026-06-23T15:03:17+00:00",
}
BUCKETS = ["no_pressure", "high_urgency", "hard_stop"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def median_or_none(values: list[float]) -> float | None:
    return round(float(median(values)), 6) if values else None


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        avg_rank = (start + 1 + end) / 2.0
        for rank_index in range(start, end):
            out[order[rank_index]] = avg_rank
        start = end
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in rx))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(numerator / (den_x * den_y), 6)


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


def pressure_bucket(row: dict[str, Any]) -> tuple[str, int, list[str]]:
    event_types = [
        str(event.get("event_type") or "")
        for event in row.get("advisory_events") or []
        if isinstance(event, dict)
    ]
    if "hard_stop_breach" in event_types:
        return "hard_stop", 2, event_types
    if row.get("has_advisory_event") or "high_urgency_advisory" in event_types:
        return "high_urgency", 1, event_types
    return "no_pressure", 0, event_types


def load_exit_lifecycle_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    files = sorted(SOURCE_DIR.glob("exit_lifecycle_*.jsonl"))
    skipped = []
    for path in files:
        with path.open(encoding="utf-8-sig") as handle:
            for line_no, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                row = json.loads(raw)
                ticker = str(row.get("ticker") or "").upper()
                as_of = str(row.get("as_of_date") or "")[:10]
                shares = as_float(row.get("shares"))
                market_value = as_float(row.get("market_value_usd"))
                if not ticker or len(as_of) != 10:
                    skipped.append({"file": repo_rel(path), "line": line_no, "reason": "missing_ticker_or_as_of"})
                    continue
                if shares is None or shares <= 0:
                    skipped.append({"file": repo_rel(path), "line": line_no, "reason": "missing_shares"})
                    continue
                if market_value is None or market_value <= 0:
                    skipped.append({"file": repo_rel(path), "line": line_no, "reason": "missing_market_value"})
                    continue
                bucket, severity, event_types = pressure_bucket(row)
                rows.append(
                    {
                        **row,
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "shares": shares,
                        "market_value_usd": market_value,
                        "pressure_bucket": bucket,
                        "pressure_severity": severity,
                        "event_types": event_types,
                    }
                )
    return rows, {
        "files": [repo_rel(path) for path in files],
        "file_count": len(files),
        "source_rows": len(rows),
        "skipped_rows": skipped,
        "dates": sorted({row["as_of_date"] for row in rows}),
        "tickers": sorted({row["ticker"] for row in rows}),
    }


def frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    out = []
    for day, row in frame.iterrows():
        open_ = as_float(row.get("Open"))
        close = as_float(row.get("Close"))
        if open_ is None or close is None:
            continue
        out.append({"Date": str(day.date()), "Open": open_, "Close": close})
    out.sort(key=lambda item: item["Date"])
    return out


def load_bars(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tickers = {row["ticker"] for row in rows}
    tickers.update({"SPY", "QQQ"})
    dates = sorted({row["as_of_date"] for row in rows})
    start = dates[0] if dates else "2026-01-01"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, "2026-12-31")
    return {ticker: frame_to_rows(frame) for ticker, frame in frames.items()}


def next_index_after(bars: list[dict[str, Any]], date_text: str) -> int | None:
    for index, row in enumerate(bars):
        if row["Date"] > date_text:
            return index
    return None


def net_sell_value(raw_price: float, shares: float) -> tuple[float, float]:
    sell_price = apply_slippage(raw_price, SLIPPAGE_BPS_TARGET, "sell")
    value = sell_price * shares
    return sell_price, value - value * ROUND_TRIP_COST_PCT


def etf_replacement_return(
    bars: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
) -> float | None:
    by_date = {row["Date"]: row for row in bars}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_open = as_float(entry.get("Open"))
    exit_close = as_float(exit_.get("Close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    entry_fill = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
    exit_fill = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
    return exit_fill / entry_fill - 1.0 - ROUND_TRIP_COST_PCT


def settle_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars = load_bars(rows)
    settled: list[dict[str, Any]] = []
    skipped: dict[str, int] = defaultdict(int)
    for row in rows:
        ticker_bars = bars.get(row["ticker"])
        if not ticker_bars:
            skipped["missing_ticker_bars"] += 1
            continue
        entry_index = next_index_after(ticker_bars, row["as_of_date"])
        if entry_index is None:
            skipped["missing_next_session"] += 1
            continue
        exit_index = entry_index + int(CONFIG["hold_days"])
        if exit_index >= len(ticker_bars):
            skipped["not_yet_5d_closed"] += 1
            continue
        entry = ticker_bars[entry_index]
        exit_ = ticker_bars[exit_index]
        entry_open = as_float(entry.get("Open"))
        exit_close = as_float(exit_.get("Close"))
        if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
            skipped["bad_entry_or_exit_price"] += 1
            continue
        shares = float(row["shares"])
        early_exit_price, early_exit_cash = net_sell_value(entry_open, shares)
        delayed_exit_price, delayed_exit_cash = net_sell_value(exit_close, shares)
        cash_value = early_exit_cash - delayed_exit_cash
        stock_hold_return = exit_close / entry_open - 1.0
        spy_return = etf_replacement_return(bars.get("SPY", []), entry["Date"], exit_["Date"])
        qqq_return = etf_replacement_return(bars.get("QQQ", []), entry["Date"], exit_["Date"])
        spy_value = early_exit_cash * (1.0 + spy_return) - delayed_exit_cash if spy_return is not None else None
        qqq_value = early_exit_cash * (1.0 + qqq_return) - delayed_exit_cash if qqq_return is not None else None
        settled.append(
            {
                **row,
                "next_open_exit_date": entry["Date"],
                "comparison_exit_date": exit_["Date"],
                "next_open_raw": round(entry_open, 4),
                "comparison_exit_raw_close": round(exit_close, 4),
                "next_open_exit_price_net": round(early_exit_price, 4),
                "delayed_exit_price_net": round(delayed_exit_price, 4),
                "next_open_exit_cash_usd": round(early_exit_cash, 2),
                "delayed_5d_exit_cash_usd": round(delayed_exit_cash, 2),
                "cash_replacement_value_vs_hold_usd": round(cash_value, 2),
                "stock_hold_5d_return_pct": round(stock_hold_return, 6),
                "spy_replacement_return_pct": round(spy_return, 6) if spy_return is not None else None,
                "qqq_replacement_return_pct": round(qqq_return, 6) if qqq_return is not None else None,
                "spy_replacement_value_vs_hold_usd": round(spy_value, 2) if spy_value is not None else None,
                "qqq_replacement_value_vs_hold_usd": round(qqq_value, 2) if qqq_value is not None else None,
            }
        )
    return settled, {
        "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
        "loaded_tickers": sorted(bars),
        "settled_rows": len(settled),
        "skipped_reasons": dict(sorted(skipped.items())),
        "settled_date_range": {
            "as_of_start": min((row["as_of_date"] for row in settled), default=None),
            "as_of_end": max((row["as_of_date"] for row in settled), default=None),
            "entry_start": min((row["next_open_exit_date"] for row in settled), default=None),
            "entry_end": max((row["next_open_exit_date"] for row in settled), default=None),
            "exit_start": min((row["comparison_exit_date"] for row in settled), default=None),
            "exit_end": max((row["comparison_exit_date"] for row in settled), default=None),
        },
    }


def positive_value_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get("cash_replacement_value_vs_hold_usd"))
        if value is not None and value > 0:
            by_ticker[row["ticker"]] += value
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_cash_value_usd": 0.0,
            "max_single_positive_cash_value_share": None,
            "positive_cash_value_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "positive_cash_value_usd": round(total, 2),
        "max_single_positive_cash_value_share": round(max(shares.values()), 6),
        "positive_cash_value_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "positive_value": round(value, 2), "share": round(shares[ticker], 6)}
            for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cash = [float(row["cash_replacement_value_vs_hold_usd"]) for row in rows]
    spy = [
        float(row["spy_replacement_value_vs_hold_usd"])
        for row in rows
        if as_float(row.get("spy_replacement_value_vs_hold_usd")) is not None
    ]
    qqq = [
        float(row["qqq_replacement_value_vs_hold_usd"])
        for row in rows
        if as_float(row.get("qqq_replacement_value_vs_hold_usd")) is not None
    ]
    hold_returns = [float(row["stock_hold_5d_return_pct"]) for row in rows]
    return {
        "n": len(rows),
        "mean_cash_value_vs_hold_usd": round_or_none(mean(cash), 2),
        "median_cash_value_vs_hold_usd": median_or_none(cash),
        "total_cash_value_vs_hold_usd": round_or_none(sum(cash), 2) if cash else 0.0,
        "positive_cash_value_rate": round(sum(1 for value in cash if value > 0) / len(cash), 6) if cash else None,
        "mean_spy_value_vs_hold_usd": round_or_none(mean(spy), 2),
        "median_spy_value_vs_hold_usd": median_or_none(spy),
        "mean_qqq_value_vs_hold_usd": round_or_none(mean(qqq), 2),
        "median_qqq_value_vs_hold_usd": median_or_none(qqq),
        "mean_stock_hold_5d_return_pct": round_or_none(mean(hold_returns), 6),
        "median_stock_hold_5d_return_pct": median_or_none(hold_returns),
        "ticker_count": len({row["ticker"] for row in rows}),
        "as_of_dates": sorted({row["as_of_date"] for row in rows}),
        "positive_value_concentration": positive_value_concentration(rows),
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {bucket: summarize([row for row in rows if row["pressure_bucket"] == bucket]) for bucket in BUCKETS}


def date_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[row["as_of_date"]].append(row)
    details = []
    better_count = 0
    comparable_count = 0
    for date_text, group in sorted(by_date.items()):
        pressure = [row for row in group if row["pressure_severity"] > 0]
        no_pressure = [row for row in group if row["pressure_severity"] == 0]
        if not pressure or not no_pressure:
            continue
        comparable_count += 1
        pressure_mean = mean([float(row["cash_replacement_value_vs_hold_usd"]) for row in pressure])
        no_pressure_mean = mean([float(row["cash_replacement_value_vs_hold_usd"]) for row in no_pressure])
        pressure_better = (
            pressure_mean is not None
            and no_pressure_mean is not None
            and pressure_mean > no_pressure_mean
        )
        if pressure_better:
            better_count += 1
        details.append(
            {
                "as_of_date": date_text,
                "pressure_rows": len(pressure),
                "no_pressure_rows": len(no_pressure),
                "pressure_mean_cash_value": round_or_none(pressure_mean, 2),
                "no_pressure_mean_cash_value": round_or_none(no_pressure_mean, 2),
                "pressure_better": pressure_better,
            }
        )
    return {
        "comparable_dates": comparable_count,
        "pressure_better_dates": better_count,
        "details": details,
    }


def sample_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            -float(row.get("cash_replacement_value_vs_hold_usd") or 0.0),
            row["as_of_date"],
            row["ticker"],
        ),
    )
    fields = (
        "as_of_date",
        "ticker",
        "pressure_bucket",
        "pressure_severity",
        "shares",
        "market_value_usd",
        "unrealized_pnl_pct",
        "drawdown_from_hwm_pct",
        "next_open_exit_date",
        "comparison_exit_date",
        "next_open_exit_cash_usd",
        "delayed_5d_exit_cash_usd",
        "cash_replacement_value_vs_hold_usd",
        "spy_replacement_value_vs_hold_usd",
        "qqq_replacement_value_vs_hold_usd",
        "stock_hold_5d_return_pct",
        "event_types",
    )
    return [{field: row.get(field) for field in fields} for row in ordered[:250]]


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pressure_rows = [row for row in rows if row["pressure_severity"] > 0]
    no_pressure_rows = [row for row in rows if row["pressure_severity"] == 0]
    cash_values = [float(row["cash_replacement_value_vs_hold_usd"]) for row in rows]
    spy_values = [
        float(row["spy_replacement_value_vs_hold_usd"])
        for row in rows
        if as_float(row.get("spy_replacement_value_vs_hold_usd")) is not None
    ]
    qqq_values = [
        float(row["qqq_replacement_value_vs_hold_usd"])
        for row in rows
        if as_float(row.get("qqq_replacement_value_vs_hold_usd")) is not None
    ]
    severities = [float(row["pressure_severity"]) for row in rows]
    cash_spearman = spearman(severities, cash_values)
    spy_spearman = spearman(
        [float(row["pressure_severity"]) for row in rows if as_float(row.get("spy_replacement_value_vs_hold_usd")) is not None],
        spy_values,
    )
    qqq_spearman = spearman(
        [float(row["pressure_severity"]) for row in rows if as_float(row.get("qqq_replacement_value_vs_hold_usd")) is not None],
        qqq_values,
    )
    buckets = bucket_summary(rows)
    pressure_summary = summarize(pressure_rows)
    no_pressure_summary = summarize(no_pressure_rows)
    support = date_support(rows)
    concentration = positive_value_concentration(pressure_rows)
    checks = {
        "settled_rows": len(rows),
        "pressure_rows": len(pressure_rows),
        "no_pressure_rows": len(no_pressure_rows),
        "pressure_mean_cash_positive": (pressure_summary["mean_cash_value_vs_hold_usd"] or 0.0) > 0,
        "pressure_median_cash_positive": (pressure_summary["median_cash_value_vs_hold_usd"] or 0.0) > 0,
        "pressure_mean_spy_positive": (pressure_summary["mean_spy_value_vs_hold_usd"] or 0.0) > 0,
        "pressure_mean_qqq_positive": (pressure_summary["mean_qqq_value_vs_hold_usd"] or 0.0) > 0,
        "pressure_mean_cash_beats_no_pressure": (
            pressure_summary["mean_cash_value_vs_hold_usd"] is not None
            and no_pressure_summary["mean_cash_value_vs_hold_usd"] is not None
            and pressure_summary["mean_cash_value_vs_hold_usd"] > no_pressure_summary["mean_cash_value_vs_hold_usd"]
        ),
        "severity_cash_spearman": cash_spearman,
        "severity_spy_spearman": spy_spearman,
        "severity_qqq_spearman": qqq_spearman,
        "date_support": support,
        "pressure_positive_value_concentration": concentration,
    }
    failed = []
    if len(rows) < int(CONFIG["min_settled_rows"]):
        failed.append("settled_sample_too_small")
    if len(pressure_rows) < int(CONFIG["min_pressure_rows"]):
        failed.append("pressure_sample_too_small")
    if not checks["pressure_mean_cash_positive"]:
        failed.append("pressure_mean_cash_value_not_positive")
    if not checks["pressure_median_cash_positive"]:
        failed.append("pressure_median_cash_value_not_positive")
    if not checks["pressure_mean_spy_positive"]:
        failed.append("pressure_mean_spy_value_not_positive")
    if not checks["pressure_mean_qqq_positive"]:
        failed.append("pressure_mean_qqq_value_not_positive")
    if not checks["pressure_mean_cash_beats_no_pressure"]:
        failed.append("pressure_cash_value_not_above_no_pressure")
    if cash_spearman is None or cash_spearman <= 0:
        failed.append("severity_cash_value_spearman_not_positive")
    if spy_spearman is None or spy_spearman <= 0:
        failed.append("severity_spy_value_spearman_not_positive")
    if qqq_spearman is None or qqq_spearman <= 0:
        failed.append("severity_qqq_value_spearman_not_positive")
    if support["comparable_dates"] < int(CONFIG["min_comparable_dates"]):
        failed.append("comparable_dates_too_small")
    if support["pressure_better_dates"] < int(CONFIG["min_pressure_better_dates"]):
        failed.append("too_few_dates_pressure_better_than_no_pressure")
    max_share = concentration["max_single_positive_cash_value_share"]
    if max_share is None or max_share > float(CONFIG["max_single_positive_cash_value_share"]):
        failed.append("pressure_positive_cash_value_concentration_too_high")
    return {
        "all_settled_rows": summarize(rows),
        "pressure_rows": pressure_summary,
        "no_pressure_rows": no_pressure_summary,
        "bucket_summary": buckets,
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "observed_only_lead": not failed,
        "sample_rows": sample_rows(rows),
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "sample_too_small": {"settled_sample_too_small", "pressure_sample_too_small"},
        "ticker_concentration": {"pressure_positive_cash_value_concentration_too_high"},
        "no_cash_replacement_edge": {
            "pressure_mean_cash_value_not_positive",
            "pressure_median_cash_value_not_positive",
            "pressure_cash_value_not_above_no_pressure",
            "severity_cash_value_spearman_not_positive",
        },
        "no_benchmark_replacement_edge": {
            "pressure_mean_spy_value_not_positive",
            "pressure_mean_qqq_value_not_positive",
            "severity_spy_value_spearman_not_positive",
            "severity_qqq_value_spearman_not_positive",
        },
        "current_loss_endogeneity": {"too_few_dates_pressure_better_than_no_pressure"},
    }
    hit_modes = [mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit_modes,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    source_rows, source_audit = load_exit_lifecycle_rows()
    settled_rows, settlement_audit = settle_rows(source_rows)
    analysis = analyze(settled_rows) if settled_rows else {
        "all_settled_rows": summarize([]),
        "pressure_rows": summarize([]),
        "no_pressure_rows": summarize([]),
        "bucket_summary": bucket_summary([]),
        "acceptance_checks": {"settled_rows": 0, "pressure_rows": 0},
        "failed_reasons": ["settled_sample_too_small"],
        "observed_only_lead": False,
        "sample_rows": [],
    }
    observed_lead = bool(analysis["observed_only_lead"])
    failed = list(analysis["failed_reasons"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_exit_lifecycle_next_open_exit_value_lead_not_promoted"
        if observed_lead
        else "rejected_no_next_open_exit_replacement_value_edge"
    )
    if observed_lead:
        why = (
            "High-pressure exit-lifecycle rows retained positive next-open "
            "exit value versus five-day hold and benchmarks. This is still "
            "only a lead because no shared executable lifecycle policy was "
            "tested."
        )
    else:
        why = (
            "High-pressure exit-lifecycle rows did not clear the execution "
            "value screen strongly enough. The prior forward-loss separation "
            "does not yet justify an exit or risk rule after next-open "
            "execution and released-cash replacement accounting."
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
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
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted this as no strong near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "This does not convert advisory labels into exits. It "
                    "tests the missing next-open execution and replacement "
                    "value envelope for existing production shadow rows."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: classify production "
                "exit-lifecycle rows by pressure, then compare next-open "
                "diagnostic exit cash/SPY/QQQ value against continuing to "
                "hold the same shares for five trading days."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_dir": repo_rel(SOURCE_DIR),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "config": CONFIG,
            "execution_model": {
                "early_exit": (
                    "next available open after as_of_date with target-side "
                    "sell slippage and ROUND_TRIP_COST_PCT"
                ),
                "delayed_hold_comparator": (
                    "same shares sold at close after five trading days with "
                    "target-side sell slippage and ROUND_TRIP_COST_PCT"
                ),
                "replacement_comparators": (
                    "cash keeps early-exit proceeds; SPY/QQQ buy same next "
                    "open with entry slippage, sell five-day close with "
                    "target-side slippage, and subtract ROUND_TRIP_COST_PCT"
                ),
            },
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(source_rows) and bool(settled_rows),
            "fields_checked": [
                "as_of_date",
                "ticker",
                "entry_date",
                "target_price",
                "shares",
                "market_value_usd",
                "advisory_events.event_type",
                "has_advisory_event",
                "next_open_exit_cash_usd",
                "delayed_5d_exit_cash_usd",
                "cash_replacement_value_vs_hold_usd",
                "spy_replacement_value_vs_hold_usd",
                "qqq_replacement_value_vs_hold_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in source_rows),
            "target_price_present_count": sum(1 for row in source_rows if row.get("target_price") is not None),
            "target_price_relevance": (
                "Checked for Gate 2. It is not consumed by this attribution "
                "and no target exit is scheduled."
            ),
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["source_rows"],
            "signals_survived": settlement_audit["settled_rows"],
            "survival_rate": round(settlement_audit["settled_rows"] / source_audit["source_rows"], 4)
            if source_audit["source_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": analysis["acceptance_checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Forward-only daily production rows, not canonical fixed-window PIT replay.",
                "No shared helper, adapter, daily execution rule, or exit policy was promoted.",
                "Outcome is diagnostic next-open exit value versus a five-day hold comparator.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "analysis": analysis,
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
            "uses_exit_lifecycle_shadow_log": True,
            "live_realistic_execution_envelope": (
                "Partially evaluated as an observed-only diagnostic envelope "
                "for next-open sell value and cash/SPY/QQQ replacement. This "
                "is not live-ready because no shared policy or fixed-window "
                "strategy replay exists."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by converting high-urgency, hard-stop, target, "
                "trailing-stop, time-stop, MFE/giveback, target-width, "
                "above-cost, or LLM state labels into executable rules on "
                "these same forward rows. A valid retry needs materially more "
                "closed rows, slot-reuse/winner-collateral accounting, or a "
                "predeclared shared default-off advisory helper."
            ),
            "new_evidence_required": (
                "More closed production exit-lifecycle rows plus explicit "
                "slot-reuse/winner-collateral accounting and a shared "
                "default-off advisory lifecycle helper before any Gate 1-4 "
                "exit-policy promotion."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_DIR),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-011.json",
            "experiments/logs/exp-20260623-016.json",
            "experiments/logs/exp-20260623-015.json",
            "experiments/logs/exp-20260623-012.json",
            "experiments/logs/exp-20260623-003.json",
        ],
    }


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
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            **payload["gate2"],
            "source_audit": {
                **payload["gate2"]["source_audit"],
                "skipped_rows": payload["gate2"]["source_audit"]["skipped_rows"][:20],
            },
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "all_settled_rows": analysis["all_settled_rows"],
            "pressure_rows": analysis["pressure_rows"],
            "no_pressure_rows": analysis["no_pressure_rows"],
            "bucket_summary": analysis["bucket_summary"],
            "acceptance_checks": analysis["acceptance_checks"],
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


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    rows = [
        "| Pressure Bucket | Rows | Mean Cash Value | Median Cash Value | Mean vs SPY | Mean vs QQQ | Mean Hold Return |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        item = analysis["bucket_summary"][bucket]
        rows.append(
            "| {bucket} | {n} | {cash} | {med_cash} | {spy} | {qqq} | {ret} |".format(
                bucket=bucket,
                n=item["n"],
                cash=money(item["mean_cash_value_vs_hold_usd"]),
                med_cash=money(item["median_cash_value_vs_hold_usd"]),
                spy=money(item["mean_spy_value_vs_hold_usd"]),
                qqq=money(item["mean_qqq_value_vs_hold_usd"]),
                ret=pct(item["mean_stock_hold_5d_return_pct"]),
            )
        )
    checks = analysis["acceptance_checks"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: exit-lifecycle next-open exit value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Result",
            "",
            *rows,
            "",
            "- Settled rows: `{}`".format(checks.get("settled_rows")),
            "- Pressure rows: `{}`".format(checks.get("pressure_rows")),
            "- Severity Spearman(cash value): `{}`".format(checks.get("severity_cash_spearman")),
            "- Severity Spearman(SPY value): `{}`".format(checks.get("severity_spy_spearman")),
            "- Severity Spearman(QQQ value): `{}`".format(checks.get("severity_qqq_spearman")),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
            "new_evidence_axis": payload["new_evidence_axis"],
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
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    checks = payload["gate4"]["acceptance_checks"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "settled_rows": checks.get("settled_rows"),
                "pressure_rows": checks.get("pressure_rows"),
                "severity_cash_spearman": checks.get("severity_cash_spearman"),
                "severity_spy_spearman": checks.get("severity_spy_spearman"),
                "severity_qqq_spearman": checks.get("severity_qqq_spearman"),
                "pressure_rows_summary": payload["attribution"]["analysis"]["pressure_rows"],
                "no_pressure_rows_summary": payload["attribution"]["analysis"]["no_pressure_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
