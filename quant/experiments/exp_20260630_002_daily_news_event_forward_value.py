"""exp-20260630-002: daily news event forward-value attribution.

Observed-only alpha search. This runner tests whether final daily
clean-trade-news rows with explicit ticker text matches and a fixed positive
event taxonomy show 5d/10d forward replacement value versus cash, SPY, and QQQ.

It changes no entry, exit, ranking, sizing, paper, live, LLM prompt, or news
archive behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-002"
OWNER = "alpha-explore"
SLUG = "daily_news_event_forward_value"
RUNNER = f"quant/experiments/exp_20260630_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_text_sanitation import audit_daily_news_file  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from news_text_sanitizer import annotate_news_item  # noqa: E402
from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402


NEWS_DIR = REPO_ROOT / "data" / "daily" / "news" / "trade"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Daily clean-trade-news explicit-ticker positive event rows may contain "
    "production-visible LLM/news event-scoring alpha if a fixed deterministic "
    "event taxonomy shows closed 5d/10d replacement value versus cash, SPY, "
    "and QQQ without changing trading behavior."
)
CHANGE_TYPE = "llm_event_scoring_forward_attribution"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "daily_clean_trade_news_event_taxonomy_forward_value"
TRIAL_VARIANT_ID = "explicit_ticker_positive_event_v1"
CHANGED_VARIABLE = "daily_clean_trade_news_event_taxonomy_forward_value_v1"
NEW_EVIDENCE_TYPE = "daily_news_sanitized_archive_forward_outcome_rows"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-001",
    "exp-20260428-012",
    "exp-20260502-010",
]
CAUSAL_COMPONENTS = [
    "daily clean-trade-news archive",
    "deterministic event taxonomy",
    "explicit ticker text provenance",
    "5d/10d forward outcome join",
    "cash/SPY/QQQ replacement value",
    "no strategy behavior change",
]

CONFIG = {
    "unit_notional_usd": 4000.0,
    "horizons": [5, 10],
    "min_closed_10d_target_rows": 30,
    "min_target_event_dates": 12,
    "min_mean_10d_return_edge_vs_control": 0.005,
    "min_mean_10d_replacement_vs_spy_usd": 0.0,
    "min_mean_10d_replacement_vs_qqq_usd": 0.0,
    "max_single_ticker_target_share": 0.35,
    "dedupe_key": "news_date,ticker,event_bucket",
}

EVENT_BUCKET_PATTERNS = [
    (
        "earnings_growth",
        [
            r"\bbeats?\b",
            r"\bstrong earnings\b",
            r"\bearnings growth\b",
            r"\brevenue growth\b",
            r"\bsales growth\b",
            r"\bprofit growth\b",
            r"\braises? guidance\b",
            r"\bstrong outlook\b",
        ],
    ),
    (
        "analyst_upgrade",
        [
            r"\bupgrade\b",
            r"\brating upgrade\b",
            r"\braises? (?:price )?target\b",
            r"\boutperform\b",
            r"\bbuy rating\b",
        ],
    ),
    (
        "order_contract_partner",
        [
            r"\border\b",
            r"\bcontract\b",
            r"\bpartnership\b",
            r"\bsupply deal\b",
            r"\bcustomer win\b",
            r"\bdeal with\b",
        ],
    ),
    (
        "capital_return",
        [
            r"\bbuyback\b",
            r"\brepurchase\b",
            r"\bdividend\b",
            r"\bcapital return\b",
        ],
    ),
    (
        "product_catalyst",
        [
            r"\bcatalyst\b",
            r"\bturning point\b",
            r"\blaunch\b",
            r"\bapproval\b",
            r"\bsurges?\b",
            r"\bjumps?\b",
            r"\bsoars?\b",
        ],
    ),
]
NEGATIVE_PATTERNS = [
    r"\bdowngrade\b",
    r"\bsell\b",
    r"\blawsuit\b",
    r"\bpressure\b",
    r"\bfail(?:s|ed|ure)?\b",
    r"\bin the red\b",
    r"\bmiss(?:es|ed)?\b",
    r"\bweak\b",
    r"\bcut(?:s|ting)?\b",
    r"\bprobe\b",
    r"\binvestigation\b",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def news_date_from_path(path: Path) -> str | None:
    match = re.search(r"_(\d{8})\.json$", path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def compiled_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_event(text: str) -> tuple[str | None, list[str]]:
    flags: list[str] = []
    if compiled_any(NEGATIVE_PATTERNS, text):
        flags.append("negative_exclusion")
        return None, flags
    for bucket, patterns in EVENT_BUCKET_PATTERNS:
        if compiled_any(patterns, text):
            return bucket, flags
    return None, flags


def sanitized_text(item: Mapping[str, Any]) -> str:
    fields = (item.get("text_sanitation") or {}).get("fields") or {}
    parts = []
    for field in ("title", "summary", "description"):
        audit = fields.get(field) or {}
        value = audit.get("sanitized_text")
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return (ticket.get("prediction") if isinstance(ticket, dict) else None) or {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "windows": windows,
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def load_news_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    for path in sorted(NEWS_DIR.glob("clean_trade_news_*.json")):
        if path.name.startswith("."):
            continue
        news_date = news_date_from_path(path)
        audit = audit_daily_news_file(path, kind="clean_trade_news", news_date=news_date)
        file_summaries.append(
            {
                "path": repo_rel(path),
                "news_date": news_date,
                "rows": audit.get("rows"),
                "readable": audit.get("readable"),
                "schema_valid": audit.get("schema_valid"),
                "summary": audit.get("summary"),
            }
        )
        raw_items = read_json(path, [])
        if not isinstance(raw_items, list):
            raw_items = []
        for raw_item in raw_items:
            item = annotate_news_item(raw_item)
            ticker_match = ((item.get("text_sanitation") or {}).get("ticker_entity_match") or {})
            if ticker_match.get("status") != "explicit_text_match":
                continue
            text = sanitized_text(item)
            event_bucket, flags = classify_event(text)
            for ticker in ticker_match.get("matched_tickers") or []:
                rows.append(
                    {
                        "news_date": news_date,
                        "ticker": str(ticker).upper(),
                        "source": item.get("source"),
                        "tier": item.get("tier"),
                        "published_at": item.get("published_at"),
                        "title": item.get("title"),
                        "text_hash": (item.get("text_sanitation") or {}).get("post_sanitize_hash"),
                        "ticker_entity_status": ticker_match.get("status"),
                        "event_bucket": event_bucket or "control_non_positive_event",
                        "positive_event": event_bucket is not None,
                        "event_flags": flags,
                    }
                )
    return rows, {
        "news_dir": repo_rel(NEWS_DIR),
        "file_count": len(file_summaries),
        "date_range": {
            "start": min((row["news_date"] for row in file_summaries if row.get("news_date")), default=None),
            "end": max((row["news_date"] for row in file_summaries if row.get("news_date")), default=None),
        },
        "file_summaries": file_summaries,
        "explicit_ticker_rows": len(rows),
        "positive_event_rows_raw": sum(1 for row in rows if row["positive_event"]),
        "bucket_counts_raw": dict(Counter(row["event_bucket"] for row in rows)),
    }


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (item["news_date"] or "", item["ticker"], item["event_bucket"], item.get("published_at") or "")):
        key = (str(row.get("news_date")), str(row.get("ticker")), str(row.get("event_bucket")))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def frame_to_rows(frame: Any) -> list[dict[str, Any]]:
    out = []
    for day, row in frame.iterrows():
        open_ = as_float(row.get("Open"))
        close = as_float(row.get("Close"))
        if open_ is None or close is None:
            continue
        out.append({"date": str(day.date()), "open": open_, "close": close})
    out.sort(key=lambda item: item["date"])
    return out


def load_bars(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tickers = {row["ticker"] for row in rows}
    tickers.update({"SPY", "QQQ"})
    dates = sorted(str(row["news_date"]) for row in rows if row.get("news_date"))
    start = dates[0] if dates else "2026-01-01"
    frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, sorted(tickers), start, "2026-12-31")
    return {ticker: frame_to_rows(frame) for ticker, frame in frames.items()}


def next_index_after(bars: list[dict[str, Any]], date_text: str) -> int | None:
    for index, row in enumerate(bars):
        if row["date"] > date_text:
            return index
    return None


def return_between(bars: list[dict[str, Any]], entry_date: str, exit_date: str) -> float | None:
    by_date = {row["date"]: row for row in bars}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    if entry["open"] <= 0 or exit_["close"] <= 0:
        return None
    return exit_["close"] / entry["open"] - 1.0


def settle_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars = load_bars(rows)
    settled: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    notional = float(CONFIG["unit_notional_usd"])
    max_horizon = max(int(value) for value in CONFIG["horizons"])
    for row in rows:
        ticker_bars = bars.get(row["ticker"])
        if not ticker_bars:
            skipped["missing_ticker_bars"] += 1
            continue
        entry_index = next_index_after(ticker_bars, str(row["news_date"]))
        if entry_index is None:
            skipped["missing_next_session"] += 1
            continue
        entry = ticker_bars[entry_index]
        outcome: dict[str, Any] = {
            **row,
            "entry_date": entry["date"],
            "entry_open": round(entry["open"], 4),
            "target_price": None,
            "unit_notional_usd": notional,
        }
        closed_any = False
        for horizon in CONFIG["horizons"]:
            h = int(horizon)
            exit_index = entry_index + h
            prefix = f"forward_{h}d"
            if exit_index >= len(ticker_bars):
                outcome[f"{prefix}_closed"] = False
                skipped[f"not_yet_{h}d_closed"] += 1
                continue
            exit_ = ticker_bars[exit_index]
            if entry["open"] <= 0 or exit_["close"] <= 0:
                skipped[f"bad_{h}d_price"] += 1
                outcome[f"{prefix}_closed"] = False
                continue
            stock_return = exit_["close"] / entry["open"] - 1.0
            spy_return = return_between(bars.get("SPY", []), entry["date"], exit_["date"])
            qqq_return = return_between(bars.get("QQQ", []), entry["date"], exit_["date"])
            pnl = notional * stock_return
            spy_pnl = notional * spy_return if spy_return is not None else None
            qqq_pnl = notional * qqq_return if qqq_return is not None else None
            outcome.update(
                {
                    f"{prefix}_closed": True,
                    f"{prefix}_exit_date": exit_["date"],
                    f"{prefix}_exit_close": round(exit_["close"], 4),
                    f"{prefix}_return_pct": round(stock_return, 6),
                    f"{prefix}_pnl_usd": round(pnl, 2),
                    f"{prefix}_spy_return_pct": round(spy_return, 6) if spy_return is not None else None,
                    f"{prefix}_qqq_return_pct": round(qqq_return, 6) if qqq_return is not None else None,
                    f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
                    if spy_pnl is not None
                    else None,
                    f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
                    if qqq_pnl is not None
                    else None,
                }
            )
            closed_any = True
        if closed_any or max_horizon == 0:
            settled.append(outcome)
    return settled, {
        "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
        "loaded_tickers": sorted(bars),
        "input_rows": len(rows),
        "settled_rows_any_horizon": len(settled),
        "skipped_reasons": dict(sorted(skipped.items())),
        "date_range": {
            "news_start": min((row["news_date"] for row in rows if row.get("news_date")), default=None),
            "news_end": max((row["news_date"] for row in rows if row.get("news_date")), default=None),
            "entry_start": min((row["entry_date"] for row in settled if row.get("entry_date")), default=None),
            "entry_end": max((row["entry_date"] for row in settled if row.get("entry_date")), default=None),
        },
    }


def rows_closed(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    return [row for row in rows if row.get(f"forward_{horizon}d_closed")]


def summarize(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    prefix = f"forward_{horizon}d"
    closed = rows_closed(rows, horizon)
    returns = [float(row[f"{prefix}_return_pct"]) for row in closed]
    pnls = [float(row[f"{prefix}_pnl_usd"]) for row in closed]
    spy = [
        float(row[f"{prefix}_replacement_value_vs_spy_usd"])
        for row in closed
        if as_float(row.get(f"{prefix}_replacement_value_vs_spy_usd")) is not None
    ]
    qqq = [
        float(row[f"{prefix}_replacement_value_vs_qqq_usd"])
        for row in closed
        if as_float(row.get(f"{prefix}_replacement_value_vs_qqq_usd")) is not None
    ]
    return {
        "n": len(closed),
        "mean_return_pct": round(mean(returns), 6) if returns else None,
        "median_return_pct": round(median_or_none(returns), 6) if returns else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6) if returns else None,
        "mean_pnl_usd": round(mean(pnls), 2) if pnls else None,
        "total_pnl_usd": round(sum(pnls), 2) if pnls else 0.0,
        "mean_replacement_value_vs_spy_usd": round(mean(spy), 2) if spy else None,
        "total_replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "mean_replacement_value_vs_qqq_usd": round(mean(qqq), 2) if qqq else None,
        "total_replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
    }


def single_ticker_share(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    counts = Counter(row["ticker"] for row in rows)
    return round(max(counts.values()) / len(rows), 6)


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [row for row in rows if row["positive_event"]]
    controls = [row for row in rows if not row["positive_event"]]
    target10 = rows_closed(targets, 10)
    control10 = rows_closed(controls, 10)
    target_summary = {str(h): summarize(targets, int(h)) for h in CONFIG["horizons"]}
    control_summary = {str(h): summarize(controls, int(h)) for h in CONFIG["horizons"]}
    bucket_summary: dict[str, dict[str, Any]] = {}
    for bucket in sorted({row["event_bucket"] for row in rows}):
        bucket_rows = [row for row in targets if row["event_bucket"] == bucket]
        if not bucket_rows:
            continue
        bucket_summary[bucket] = {str(h): summarize(bucket_rows, int(h)) for h in CONFIG["horizons"]}

    target10_mean = as_float(target_summary["10"].get("mean_return_pct"))
    control10_mean = as_float(control_summary["10"].get("mean_return_pct"))
    target_edge = (
        round(target10_mean - control10_mean, 6)
        if target10_mean is not None and control10_mean is not None
        else None
    )
    checks = {
        "closed_10d_target_rows": len(target10),
        "closed_10d_control_rows": len(control10),
        "target_event_dates": len({row["news_date"] for row in target10}),
        "target_ticker_count": len({row["ticker"] for row in target10}),
        "target_single_ticker_share": single_ticker_share(target10),
        "mean_10d_return_edge_vs_control": target_edge,
        "target_mean_10d_replacement_vs_spy_usd": target_summary["10"].get(
            "mean_replacement_value_vs_spy_usd"
        ),
        "target_mean_10d_replacement_vs_qqq_usd": target_summary["10"].get(
            "mean_replacement_value_vs_qqq_usd"
        ),
        "canonical_three_window_coverage": False,
    }
    failed = []
    if checks["closed_10d_target_rows"] < CONFIG["min_closed_10d_target_rows"]:
        failed.append("target_closed_10d_sample_too_small")
    if checks["target_event_dates"] < CONFIG["min_target_event_dates"]:
        failed.append("target_event_date_breadth_too_small")
    if target_edge is None or target_edge < CONFIG["min_mean_10d_return_edge_vs_control"]:
        failed.append("mean_10d_return_edge_vs_control_too_low")
    if (
        as_float(checks["target_mean_10d_replacement_vs_spy_usd"]) is None
        or float(checks["target_mean_10d_replacement_vs_spy_usd"])
        <= CONFIG["min_mean_10d_replacement_vs_spy_usd"]
    ):
        failed.append("target_mean_10d_spy_replacement_not_positive")
    if (
        as_float(checks["target_mean_10d_replacement_vs_qqq_usd"]) is None
        or float(checks["target_mean_10d_replacement_vs_qqq_usd"])
        <= CONFIG["min_mean_10d_replacement_vs_qqq_usd"]
    ):
        failed.append("target_mean_10d_qqq_replacement_not_positive")
    if (
        as_float(checks["target_single_ticker_share"]) is None
        or float(checks["target_single_ticker_share"]) > CONFIG["max_single_ticker_target_share"]
    ):
        failed.append("target_single_ticker_concentration_too_high")
    if not checks["canonical_three_window_coverage"]:
        failed.append("coverage_not_canonical_windows")
    observed_positive = bool(
        not set(failed).difference({"coverage_not_canonical_windows"})
        and "coverage_not_canonical_windows" in failed
    )
    return {
        "observed_only_positive_lead": observed_positive,
        "failed_reasons": failed,
        "checks": checks,
        "target_summary": target_summary,
        "control_summary": control_summary,
        "bucket_summary": bucket_summary,
        "sample_rows": target10[:12],
    }


def calibration(prediction: dict[str, Any], observed_positive: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if observed_positive else 0.0
    mode_map = {
        "insufficient_closed_forward_rows": {
            "target_closed_10d_sample_too_small",
            "target_event_date_breadth_too_small",
        },
        "no_event_taxonomy_edge": {
            "mean_10d_return_edge_vs_control_too_low",
            "target_mean_10d_spy_replacement_not_positive",
            "target_mean_10d_qqq_replacement_not_positive",
        },
        "ticker_metadata_only_noise": {"target_single_ticker_concentration_too_high"},
        "missing_ohlcv_settlement": {"target_closed_10d_sample_too_small"},
        "coverage_not_canonical_windows": {"coverage_not_canonical_windows"},
    }
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    hit = [mode for mode in predicted_modes if set(failed) & mode_map.get(mode, set())]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(observed_positive),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    raw_rows, source_audit = load_news_rows()
    deduped_rows = dedupe_rows(raw_rows)
    settled_rows, settlement_audit = settle_rows(deduped_rows)
    analysis = analyze(settled_rows)
    observed_positive = bool(analysis["observed_only_positive_lead"])
    failed = list(analysis["failed_reasons"])
    decision = (
        "observed_only_positive_daily_news_event_forward_lead_not_promoted"
        if observed_positive
        else "rejected_no_daily_news_event_forward_value_edge"
    )
    status = "observed_only_positive_lead" if observed_positive else "rejected"
    why = (
        "The fixed positive-event taxonomy separated forward replacement value on "
        "the current daily news archive, but coverage is current-forward only and "
        "does not span the canonical three windows, so no strategy or helper was "
        "promoted."
        if observed_positive
        else "The fixed positive-event taxonomy did not clear the predeclared "
        "forward edge checks versus explicit-ticker control rows after dedupe and "
        "10d settlement; daily news remains an attribution surface, not a trading "
        "rule."
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
        "observed_only_lead": observed_positive,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new passed with no strong near-neighbor and no saturated-source block.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "boundary": "This uses the sanitized daily news archive and does not retry SEC/companyfacts/OHLCV precursor scan surfaces.",
            },
            "3_single_policy_bundle": "One deterministic event taxonomy plus explicit ticker-text provenance and forward outcome join.",
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "news_dir": repo_rel(NEWS_DIR),
            "warehouse_path": repo_rel(DEFAULT_WAREHOUSE_PATH),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "event_bucket_patterns": EVENT_BUCKET_PATTERNS,
            "negative_patterns": NEGATIVE_PATTERNS,
            "config": CONFIG,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy metrics are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(settled_rows),
            "fields_checked": [
                "news_date",
                "ticker",
                "title",
                "text_sanitation.post_sanitize_hash",
                "ticker_entity_status",
                "event_bucket",
                "entry_date",
                "target_price",
                "forward_5d_return_pct",
                "forward_10d_return_pct",
                "forward_10d_replacement_value_vs_spy_usd",
                "forward_10d_replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in settled_rows),
            "target_price_present_count": sum(1 for row in settled_rows if row.get("target_price")),
            "target_price_relevance": "Not applicable; no target exit is scheduled in this observed-only attribution.",
            "source_audit": {
                **source_audit,
                "file_summaries": source_audit["file_summaries"][:8],
            },
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["explicit_ticker_rows"],
            "signals_survived": len(rows_closed(settled_rows, 10)),
            "survival_rate": round(
                len(rows_closed(settled_rows, 10)) / source_audit["explicit_ticker_rows"], 4
            )
            if source_audit["explicit_ticker_rows"]
            else None,
            "target_candidate_rows_raw": source_audit["positive_event_rows_raw"],
            "target_candidate_rows_deduped": sum(1 for row in deduped_rows if row["positive_event"]),
            "note": "No executable filter was added; this measures a fixed observed-only cohort.",
        },
        "gate4": {
            "observed_only_lead": observed_positive,
            "failed_reasons": failed,
            "checks": analysis["checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Daily news archive coverage starts in 2026 and does not cover all canonical fixed windows.",
                "No shared helper, daily paper sleeve, prompt rule, or live order behavior was promoted.",
                "Event taxonomy is deterministic and not an LLM semantic scorer.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "raw_explicit_ticker_rows": source_audit["explicit_ticker_rows"],
            "raw_positive_event_rows": source_audit["positive_event_rows_raw"],
            "deduped_rows": len(deduped_rows),
            "settled_10d_rows": len(rows_closed(settled_rows, 10)),
        },
        "attribution": {
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "deduped_row_count": len(deduped_rows),
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
            "llm_prompt_changed": False,
            "news_archives_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
        },
        "calibration": calibration(prediction, observed_positive, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping the positive/negative keyword list, tiers, "
                "headline sources, hold days, top-N, notional, or response curve on "
                "the same daily news archive. A valid retry needs either materially "
                "more closed daily news rows, an LLM-scored event label with saved "
                "evidence spans, or canonical-window replay coverage."
            ),
            "new_evidence_required": (
                "A replayable PIT structured event ledger with actor/object/relation/"
                "magnitude/evidence spans and enough closed replacement-value rows, "
                "or historical daily-news coverage spanning the canonical windows."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(NEWS_DIR),
            repo_rel(BASELINE_RESULT),
            "quant/daily_news_text_sanitation.py",
            "quant/news_text_sanitizer.py",
            "experiments/logs/exp-20260630-001.json",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only; no JS tooling invoked."},
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "target_summary": analysis["target_summary"],
            "control_summary": analysis["control_summary"],
            "bucket_summary": analysis["bucket_summary"],
            "checks": analysis["checks"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    target10 = analysis["target_summary"]["10"]
    control10 = analysis["control_summary"]["10"]
    checks = analysis["checks"]
    rows = [
        "| Cohort | 10d rows | Mean return | Mean PnL | Mean vs SPY | Mean vs QQQ | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| positive_event | {n} | {ret} | {pnl} | {spy} | {qqq} | {win} |".format(
            n=target10["n"],
            ret=pct(target10["mean_return_pct"]),
            pnl=money(target10["mean_pnl_usd"]),
            spy=money(target10["mean_replacement_value_vs_spy_usd"]),
            qqq=money(target10["mean_replacement_value_vs_qqq_usd"]),
            win=pct(target10["win_rate"]),
        ),
        "| explicit_ticker_control | {n} | {ret} | {pnl} | {spy} | {qqq} | {win} |".format(
            n=control10["n"],
            ret=pct(control10["mean_return_pct"]),
            pnl=money(control10["mean_pnl_usd"]),
            spy=money(control10["mean_replacement_value_vs_spy_usd"]),
            qqq=money(control10["mean_replacement_value_vs_qqq_usd"]),
            win=pct(control10["win_rate"]),
        ),
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily news event forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production behavior changed: no",
            "- Accepted alpha: no",
            "",
            "## 10d Result",
            "",
            *rows,
            "",
            f"- Mean 10d return edge vs control: `{pct(checks['mean_10d_return_edge_vs_control'])}`",
            f"- Target dates: `{checks['target_event_dates']}`",
            f"- Target single-ticker share: `{pct(checks['target_single_ticker_share'])}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / RUNNER, OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON, REGISTRY_JSON]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
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
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "checks": analysis["checks"],
                "target_10d": analysis["target_summary"]["10"],
                "control_10d": analysis["control_summary"]["10"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
