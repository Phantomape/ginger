"""exp-20260623-011: exit-lifecycle forward advisory outcome attribution.

Observed-only alpha attribution. This runner tests whether production
exit-lifecycle shadow advisory events identify held positions with worse
next-5-trading-day outcomes than rows without advisory events.

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

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260623-011"
SLUG = "exit_lifecycle_forward_advisory_outcome"
RUNNER = f"quant/experiments/exp_20260623_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_011_{SLUG}.json"
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
    "Observed-only attribution: production exit-lifecycle high-urgency and "
    "hard-stop shadow events may identify held positions with worse "
    "next-5-trading-day returns than no-advisory rows, justifying a future "
    "shared exit/risk policy only if separation is monotonic."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_attribution"
TRIAL_FAMILY = "exit_lifecycle_forward_advisory_outcome_attribution"
TRIAL_VARIANT_ID = "high_urgency_hard_stop_next5d_forward_v1"
CHANGED_VARIABLE = "exit_lifecycle_forward_advisory_outcome_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260429-032",
    "exp-20260612-007",
    "exp-20260623-003",
]
NEW_EVIDENCE_TYPE = "forward_production_exit_lifecycle_rows"
NEW_EVIDENCE_AXIS = (
    "New daily production exit-lifecycle shadow rows with closeable forward "
    "OHLCV outcomes; this is not a SIGNAL_TARGET trim replay, target-width "
    "sweep, or fixed-entry oracle regret bucket retry."
)
CAUSAL_COMPONENTS = [
    "production exit lifecycle shadow logs",
    "warehouse OHLCV forward settlement",
    "advisory severity buckets",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-011/exp_20260623_011_exit_lifecycle_forward_advisory_outcome.json",
    "experiments/cards/exp-20260623-011.md",
    "experiments/manifests/exp-20260623-011.json",
    "experiments/tickets/exp-20260623-011.json",
    "experiments/logs/exp-20260623-011.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
CONFIG = {
    "hold_days": 5,
    "min_settled_rows": 100,
    "min_advisory_rows": 20,
    "min_hard_stop_rows": 8,
    "min_dates_advisory_worse": 3,
    "max_single_adverse_pnl_share": 0.50,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_small",
        "no_monotonic_forward_separation",
        "advisory_events_are_loss_state_not_predictive",
        "warehouse_outcomes_missing",
    ],
    "confidence_reason": (
        "This uses actual daily exit-lifecycle shadow rows unavailable in "
        "prior SIGNAL_TARGET replay and fixed-entry oracle experiments; risk "
        "is that advisory events simply label already-losing positions rather "
        "than future avoidable loss."
    ),
    "recorded_at": "2026-06-23T08:04:23+00:00",
}
BUCKETS = ["none", "high_urgency", "hard_stop"]


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


def advisory_bucket(row: dict[str, Any]) -> tuple[str, int, list[str]]:
    event_types = [
        str(event.get("event_type") or "")
        for event in row.get("advisory_events") or []
        if isinstance(event, dict)
    ]
    if "hard_stop_breach" in event_types:
        return "hard_stop", 2, event_types
    if row.get("has_advisory_event") or "high_urgency_advisory" in event_types:
        return "high_urgency", 1, event_types
    return "none", 0, event_types


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
                if not ticker or len(as_of) != 10:
                    skipped.append({"file": repo_rel(path), "line": line_no, "reason": "missing_ticker_or_as_of"})
                    continue
                market_value = as_float(row.get("market_value_usd"))
                if market_value is None or market_value <= 0:
                    skipped.append({"file": repo_rel(path), "line": line_no, "reason": "missing_market_value"})
                    continue
                bucket, severity, event_types = advisory_bucket(row)
                rows.append(
                    {
                        **row,
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "market_value_usd": market_value,
                        "advisory_bucket": bucket,
                        "advisory_severity": severity,
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
        out.append(
            {
                "Date": str(day.date()),
                "Open": open_,
                "Close": close,
            }
        )
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


def return_between(bars: list[dict[str, Any]], entry_date: str, exit_date: str) -> float | None:
    by_date = {row["Date"]: row for row in bars}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_open = as_float(entry.get("Open"))
    exit_close = as_float(exit_.get("Close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    return exit_close / entry_open - 1.0


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
        stock_return = exit_close / entry_open - 1.0
        spy_return = return_between(bars.get("SPY", []), entry["Date"], exit_["Date"])
        qqq_return = return_between(bars.get("QQQ", []), entry["Date"], exit_["Date"])
        notional = float(row["market_value_usd"])
        pnl = notional * stock_return
        spy_pnl = notional * spy_return if spy_return is not None else None
        qqq_pnl = notional * qqq_return if qqq_return is not None else None
        settled.append(
            {
                **row,
                "entry_date": entry["Date"],
                "exit_date": exit_["Date"],
                "entry_open": round(entry_open, 4),
                "exit_close": round(exit_close, 4),
                "forward_5d_return_pct": round(stock_return, 6),
                "forward_5d_pnl_usd": round(pnl, 2),
                "spy_same_window_return_pct": round(spy_return, 6) if spy_return is not None else None,
                "qqq_same_window_return_pct": round(qqq_return, 6) if qqq_return is not None else None,
                "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2) if spy_pnl is not None else None,
                "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2) if qqq_pnl is not None else None,
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
            "entry_start": min((row["entry_date"] for row in settled), default=None),
            "entry_end": max((row["entry_date"] for row in settled), default=None),
            "exit_start": min((row["exit_date"] for row in settled), default=None),
            "exit_end": max((row["exit_date"] for row in settled), default=None),
        },
    }


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = as_float(row.get("forward_5d_pnl_usd"))
        if pnl is not None and pnl < 0:
            by_ticker[row["ticker"]] += -pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "adverse_pnl": 0.0,
            "max_single_adverse_pnl_share": None,
            "adverse_pnl_hhi": None,
            "top_adverse_tickers": [],
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "adverse_pnl": round(total, 2),
        "max_single_adverse_pnl_share": round(max(shares.values()), 6),
        "adverse_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_adverse_tickers": [
            {"ticker": ticker, "adverse_pnl": round(value, 2), "share": round(shares[ticker], 6)}
            for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(row["forward_5d_return_pct"]) for row in rows]
    pnls = [float(row["forward_5d_pnl_usd"]) for row in rows]
    spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    qqq = [
        float(row["replacement_value_vs_qqq_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    return {
        "n": len(rows),
        "mean_forward_5d_return_pct": round_or_none(mean(returns), 6),
        "median_forward_5d_return_pct": median_or_none(returns),
        "mean_forward_5d_pnl_usd": round_or_none(mean(pnls), 2),
        "median_forward_5d_pnl_usd": median_or_none(pnls),
        "total_forward_5d_pnl_usd": round_or_none(sum(pnls), 2) if pnls else 0.0,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6) if returns else None,
        "mean_replacement_value_vs_spy_usd": round_or_none(mean(spy), 2),
        "mean_replacement_value_vs_qqq_usd": round_or_none(mean(qqq), 2),
        "ticker_count": len({row["ticker"] for row in rows}),
        "as_of_dates": sorted({row["as_of_date"] for row in rows}),
        "concentration": concentration(rows),
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        bucket: summarize([row for row in rows if row["advisory_bucket"] == bucket])
        for bucket in BUCKETS
    }


def date_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[row["as_of_date"]].append(row)
    details = []
    worse_count = 0
    comparable_count = 0
    for date_text, group in sorted(by_date.items()):
        none_rows = [row for row in group if row["advisory_severity"] == 0]
        advisory_rows = [row for row in group if row["advisory_severity"] > 0]
        if not none_rows or not advisory_rows:
            continue
        comparable_count += 1
        none_mean = mean([float(row["forward_5d_return_pct"]) for row in none_rows])
        advisory_mean = mean([float(row["forward_5d_return_pct"]) for row in advisory_rows])
        advisory_worse = advisory_mean is not None and none_mean is not None and advisory_mean < none_mean
        if advisory_worse:
            worse_count += 1
        details.append(
            {
                "as_of_date": date_text,
                "none_rows": len(none_rows),
                "advisory_rows": len(advisory_rows),
                "none_mean_return": round_or_none(none_mean, 6),
                "advisory_mean_return": round_or_none(advisory_mean, 6),
                "advisory_worse": advisory_worse,
            }
        )
    return {
        "comparable_dates": comparable_count,
        "advisory_worse_dates": worse_count,
        "details": details,
    }


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    severities = [float(row["advisory_severity"]) for row in rows]
    returns = [float(row["forward_5d_return_pct"]) for row in rows]
    spy_repl = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    spy_severity = [
        float(row["advisory_severity"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    summary = bucket_summary(rows)
    support = date_support(rows)
    none = summary["none"]
    high = summary["high_urgency"]
    hard = summary["hard_stop"]
    checks = {
        "min_settled_rows": CONFIG["min_settled_rows"],
        "settled_rows": len(rows),
        "advisory_rows": sum(1 for row in rows if row["advisory_severity"] > 0),
        "hard_stop_rows": sum(1 for row in rows if row["advisory_bucket"] == "hard_stop"),
        "severity_spearman_return": spearman(severities, returns),
        "severity_spearman_spy_replacement": spearman(spy_severity, spy_repl),
        "high_mean_return_below_none": (
            high["mean_forward_5d_return_pct"] is not None
            and none["mean_forward_5d_return_pct"] is not None
            and high["mean_forward_5d_return_pct"] < none["mean_forward_5d_return_pct"]
        ),
        "high_median_return_below_none": (
            high["median_forward_5d_return_pct"] is not None
            and none["median_forward_5d_return_pct"] is not None
            and high["median_forward_5d_return_pct"] < none["median_forward_5d_return_pct"]
        ),
        "hard_mean_return_below_none": (
            hard["mean_forward_5d_return_pct"] is not None
            and none["mean_forward_5d_return_pct"] is not None
            and hard["mean_forward_5d_return_pct"] < none["mean_forward_5d_return_pct"]
        ),
        "hard_median_return_below_none": (
            hard["median_forward_5d_return_pct"] is not None
            and none["median_forward_5d_return_pct"] is not None
            and hard["median_forward_5d_return_pct"] < none["median_forward_5d_return_pct"]
        ),
        "date_support": support,
        "max_single_adverse_pnl_share": summarize(rows)["concentration"]["max_single_adverse_pnl_share"],
    }
    failed = []
    if checks["settled_rows"] < CONFIG["min_settled_rows"]:
        failed.append("settled_sample_too_small")
    if checks["advisory_rows"] < CONFIG["min_advisory_rows"]:
        failed.append("advisory_sample_too_small")
    if checks["hard_stop_rows"] < CONFIG["min_hard_stop_rows"]:
        failed.append("hard_stop_sample_too_small")
    if checks["severity_spearman_return"] is None or checks["severity_spearman_return"] >= 0:
        failed.append("severity_return_spearman_not_negative")
    if checks["severity_spearman_spy_replacement"] is None or checks["severity_spearman_spy_replacement"] >= 0:
        failed.append("severity_spy_replacement_spearman_not_negative")
    if not checks["high_mean_return_below_none"]:
        failed.append("high_urgency_mean_not_worse_than_none")
    if not checks["high_median_return_below_none"]:
        failed.append("high_urgency_median_not_worse_than_none")
    if not checks["hard_mean_return_below_none"]:
        failed.append("hard_stop_mean_not_worse_than_none")
    if not checks["hard_median_return_below_none"]:
        failed.append("hard_stop_median_not_worse_than_none")
    if support["advisory_worse_dates"] < CONFIG["min_dates_advisory_worse"]:
        failed.append("too_few_dates_with_advisory_worse_than_none")
    share = checks["max_single_adverse_pnl_share"]
    if share is not None and share > CONFIG["max_single_adverse_pnl_share"]:
        failed.append("adverse_pnl_concentration_too_high")
    return {
        "all_settled_rows": summarize(rows),
        "bucket_summary": summary,
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "observed_only_lead": not failed,
        "sample_rows": [
            {
                key: row.get(key)
                for key in (
                    "as_of_date",
                    "ticker",
                    "advisory_bucket",
                    "advisory_severity",
                    "entry_date",
                    "exit_date",
                    "forward_5d_return_pct",
                    "forward_5d_pnl_usd",
                    "replacement_value_vs_spy_usd",
                    "replacement_value_vs_qqq_usd",
                    "unrealized_pnl_pct",
                    "drawdown_from_hwm_pct",
                    "breach_status",
                    "event_types",
                )
            }
            for row in rows[:250]
        ],
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "sample_too_small": {
            "settled_sample_too_small",
            "advisory_sample_too_small",
            "hard_stop_sample_too_small",
        },
        "no_monotonic_forward_separation": {
            "severity_return_spearman_not_negative",
            "severity_spy_replacement_spearman_not_negative",
            "high_urgency_mean_not_worse_than_none",
            "hard_stop_mean_not_worse_than_none",
        },
        "advisory_events_are_loss_state_not_predictive": {
            "high_urgency_median_not_worse_than_none",
            "hard_stop_median_not_worse_than_none",
            "too_few_dates_with_advisory_worse_than_none",
        },
        "warehouse_outcomes_missing": {"settled_sample_too_small"},
    }
    hit_modes = [
        mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)
    ]
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
        "bucket_summary": bucket_summary([]),
        "acceptance_checks": {"settled_rows": 0},
        "failed_reasons": ["settled_sample_too_small"],
        "observed_only_lead": False,
        "sample_rows": [],
    }
    observed_lead = bool(analysis["observed_only_lead"])
    failed = list(analysis["failed_reasons"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_exit_lifecycle_advisory_loss_lead_not_promoted"
        if observed_lead
        else "rejected_no_forward_exit_lifecycle_advisory_edge"
    )
    why = (
        "Exit-lifecycle advisory severity showed negative forward outcome "
        "separation versus no-advisory rows. This remains diagnostic-only "
        "because no shared executable lifecycle policy was tested."
        if observed_lead
        else "Exit-lifecycle advisory rows did not show a robust monotonic "
        "forward loss edge. The shadow log remains useful for observation, but "
        "these high-urgency/hard-stop labels are not enough to justify an "
        "exit or risk rule."
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
                    "This is not a target trim, target-width, trailing-stop, "
                    "MFE/giveback, or fixed-entry oracle retry. It uses new "
                    "daily production exit-lifecycle shadow rows."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: classify production "
                "exit-lifecycle rows by advisory severity and settle next "
                "5-trading-day outcomes from the warehouse."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_dir": repo_rel(SOURCE_DIR),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "config": CONFIG,
            "outcome_definition": (
                "Gross diagnostic return from next trading session open after "
                "as_of_date to the close five trading days later; no order is "
                "scheduled and no execution cost is applied."
            ),
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
                "market_value_usd",
                "advisory_events.event_type",
                "has_advisory_event",
                "forward_5d_return_pct",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
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
                "Outcome is gross diagnostic next-open-to-5d-close path attribution.",
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
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by converting high-urgency, hard-stop, target, "
                "trailing-stop, time-stop, MFE/giveback, or target-width labels "
                "into executable exit rules on the same forward rows. A valid "
                "retry needs materially more closed rows, a predeclared "
                "shared default-off advisory helper, or PIT intratrade path "
                "features available before the advisory event."
            ),
            "new_evidence_required": (
                "More closed production exit-lifecycle rows with next-open "
                "settlement, slot-reuse/winner-collateral accounting, and "
                "a shared default-off advisory lifecycle helper before any "
                "Gate 1-4 exit-policy promotion."
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
            "experiments/logs/exp-20260429-032.json",
            "experiments/logs/exp-20260612-007.json",
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
        "| Advisory Bucket | Rows | Mean Return | Median Return | Mean PnL | Mean vs SPY | Mean vs QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        item = analysis["bucket_summary"][bucket]
        rows.append(
            "| {bucket} | {n} | {mean_ret} | {median_ret} | {mean_pnl} | {spy} | {qqq} |".format(
                bucket=bucket,
                n=item["n"],
                mean_ret=pct(item["mean_forward_5d_return_pct"]),
                median_ret=pct(item["median_forward_5d_return_pct"]),
                mean_pnl=money(item["mean_forward_5d_pnl_usd"]),
                spy=money(item["mean_replacement_value_vs_spy_usd"]),
                qqq=money(item["mean_replacement_value_vs_qqq_usd"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: exit-lifecycle forward advisory outcome",
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
            "- Settled rows: `{}`".format(analysis["all_settled_rows"]["n"]),
            "- Severity Spearman(return): `{}`".format(
                analysis["acceptance_checks"].get("severity_spearman_return")
            ),
            "- Severity Spearman(SPY replacement): `{}`".format(
                analysis["acceptance_checks"].get("severity_spearman_spy_replacement")
            ),
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
                "advisory_rows": checks.get("advisory_rows"),
                "hard_stop_rows": checks.get("hard_stop_rows"),
                "severity_spearman_return": checks.get("severity_spearman_return"),
                "severity_spearman_spy_replacement": checks.get(
                    "severity_spearman_spy_replacement"
                ),
                "bucket_summary": payload["attribution"]["analysis"]["bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
