"""exp-20260623-015: exit-lifecycle plus LLM-state confluence attribution.

Observed-only alpha attribution. This runner tests whether same-day agreement
between production exit-lifecycle advisory pressure and LLM decision-log exit
pressure has incremental forward loss information versus either surface alone.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
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

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)


EXPERIMENT_ID = "exp-20260623-015"
SLUG = "exit_lifecycle_llm_confluence_forward_loss"
RUNNER = f"quant/experiments/exp_20260623_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXIT_LIFECYCLE_DIR = REPO_ROOT / "data" / "exit_lifecycle"
LLM_DECISION_DIR = REPO_ROOT / "data" / "daily" / "llm" / "decisions"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Observed-only attribution: rows where production exit-lifecycle advisory "
    "severity and LLM decision-log exit pressure agree should show worse "
    "next-5-trading-day outcomes than single-surface or no-pressure rows, "
    "creating a future shared exit/risk policy lead only if confluence improves "
    "forward loss separation."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_llm_confluence_attribution"
TRIAL_FAMILY = "exit_lifecycle_llm_state_confluence_forward_attribution"
TRIAL_VARIANT_ID = "dual_surface_exit_pressure_next5d_v1"
CHANGED_VARIABLE = "exit_lifecycle_llm_state_confluence_forward_loss_attribution_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-011",
    "exp-20260623-012",
    "exp-20260429-032",
]
NEW_EVIDENCE_TYPE = "cross_surface_forward_production_rows"
NEW_EVIDENCE_AXIS = (
    "New gate shape combining two independently logged production surfaces on "
    "the same ticker/as_of date; not a retune of either exit-lifecycle advisory "
    "labels or LLM position-state labels alone."
)
CAUSAL_COMPONENTS = [
    "production exit-lifecycle shadow logs",
    "daily LLM decision logs",
    "cross-surface confluence buckets",
    "warehouse OHLCV forward settlement",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-015/exp_20260623_015_exit_lifecycle_llm_confluence_forward_loss.json",
    "experiments/cards/exp-20260623-015.md",
    "experiments/manifests/exp-20260623-015.json",
    "experiments/tickets/exp-20260623-015.json",
    "experiments/logs/exp-20260623-015.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

CONFIG = {
    "hold_days": 5,
    "min_joined_rows": 120,
    "min_no_pressure_rows": 80,
    "min_single_surface_rows": 10,
    "min_dual_pressure_rows": 20,
    "min_dates_dual_worse": 3,
    "max_dual_adverse_pnl_share": 0.50,
    "dedupe_key": "ticker,entry_date,exit_date,confluence_bucket",
}
DEFAULT_PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_small",
        "no_confluence_incremental_separation",
        "surfaces_are_same_endogenous_label",
        "warehouse_outcomes_missing",
        "ticker_concentration",
    ],
    "confidence_reason": (
        "Both exp-20260623-011 and exp-20260623-012 produced observed-only "
        "forward loss leads on distinct production surfaces; confluence may "
        "reduce label noise, but overlap/endogeneity and limited closed dates "
        "make this a low-confidence diagnostic, not a promotable exit rule."
    ),
    "recorded_at": "2026-06-23T12:03:20+00:00",
}

LLM_STATE_DEFINITIONS = {
    "HOLD": {"bucket": "hold", "severity": 0},
    "HIGH_REDUCE": {"bucket": "high_reduce", "severity": 1},
    "TARGET_EXIT": {"bucket": "target_exit", "severity": 2},
    "ATR_EXIT": {"bucket": "atr_exit", "severity": 3},
    "CRITICAL_EXIT": {"bucket": "critical_exit", "severity": 4},
}
CONFLUENCE_BUCKETS = [
    "no_pressure",
    "llm_only",
    "lifecycle_only",
    "dual_pressure",
    "single_surface_pressure",
]


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


def lifecycle_severity(row: dict[str, Any]) -> tuple[str, int, list[str]]:
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


def load_lifecycle_rows() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    files = sorted(EXIT_LIFECYCLE_DIR.glob("exit_lifecycle_*.jsonl"))
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
                bucket, severity, event_types = lifecycle_severity(row)
                rows[(as_of, ticker)] = {
                    "as_of_date": as_of,
                    "ticker": ticker,
                    "market_value_usd": market_value,
                    "entry_date_source": row.get("entry_date"),
                    "target_price": row.get("target_price"),
                    "lifecycle_bucket": bucket,
                    "lifecycle_severity": severity,
                    "lifecycle_event_types": event_types,
                    "lifecycle_breach_status": row.get("breach_status"),
                    "unrealized_pnl_pct": row.get("unrealized_pnl_pct"),
                    "drawdown_from_hwm_pct": row.get("drawdown_from_hwm_pct"),
                }
    counter = Counter(row["lifecycle_bucket"] for row in rows.values())
    return rows, {
        "source_dir": repo_rel(EXIT_LIFECYCLE_DIR),
        "files": [repo_rel(path) for path in files],
        "file_count": len(files),
        "rows": len(rows),
        "skipped_rows": skipped,
        "dates": sorted({key[0] for key in rows}),
        "tickers": sorted({key[1] for key in rows}),
        "bucket_counts": dict(sorted(counter.items())),
    }


def parse_log_date(raw: Any, path: Path) -> str | None:
    text = str(raw or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    stem = path.stem.replace("llm_decision_log_", "")
    if len(stem) == 8 and stem.isdigit():
        return f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}"
    return None


def classify_llm_state(raw_state: Any) -> tuple[str, str, int]:
    state = str(raw_state or "").upper().strip() or "UNKNOWN"
    definition = LLM_STATE_DEFINITIONS.get(state)
    if definition is None:
        return state, "other_non_hold", 1
    return state, str(definition["bucket"]), int(definition["severity"])


def load_llm_rows() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    files = sorted(LLM_DECISION_DIR.glob("llm_decision_log_*.json"))
    for path in files:
        payload = read_json(path, {})
        as_of = parse_log_date(payload.get("date") if isinstance(payload, dict) else None, path)
        position_states = payload.get("position_states") if isinstance(payload, dict) else None
        if as_of is None:
            skipped.append({"file": repo_rel(path), "reason": "missing_or_bad_date"})
            continue
        if not isinstance(position_states, dict) or not position_states:
            skipped.append({"file": repo_rel(path), "reason": "missing_position_states"})
            continue
        for raw_ticker, raw_state in sorted(position_states.items()):
            ticker = str(raw_ticker or "").upper().strip()
            if not ticker:
                skipped.append({"file": repo_rel(path), "reason": "missing_ticker"})
                continue
            state, bucket, severity = classify_llm_state(raw_state)
            rows[(as_of, ticker)] = {
                "as_of_date": as_of,
                "ticker": ticker,
                "llm_position_state": state,
                "llm_bucket": bucket,
                "llm_severity": severity,
            }
    state_counts = Counter(row["llm_position_state"] for row in rows.values())
    bucket_counts = Counter(row["llm_bucket"] for row in rows.values())
    return rows, {
        "source_dir": repo_rel(LLM_DECISION_DIR),
        "files": [repo_rel(path) for path in files],
        "file_count": len(files),
        "rows": len(rows),
        "skipped_rows": skipped,
        "dates": sorted({key[0] for key in rows}),
        "tickers": sorted({key[1] for key in rows}),
        "state_counts": dict(sorted(state_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
    }


def confluence_bucket(lifecycle_sev: int, llm_sev: int) -> str:
    if lifecycle_sev > 0 and llm_sev > 0:
        return "dual_pressure"
    if lifecycle_sev > 0:
        return "lifecycle_only"
    if llm_sev > 0:
        return "llm_only"
    return "no_pressure"


def joined_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lifecycle_rows, lifecycle_audit = load_lifecycle_rows()
    llm_rows, llm_audit = load_llm_rows()
    keys = sorted(set(lifecycle_rows) & set(llm_rows))
    rows: list[dict[str, Any]] = []
    for key in keys:
        life = lifecycle_rows[key]
        llm = llm_rows[key]
        bucket = confluence_bucket(life["lifecycle_severity"], llm["llm_severity"])
        rows.append(
            {
                **life,
                **llm,
                "confluence_bucket": bucket,
                "confluence_score": life["lifecycle_severity"] + llm["llm_severity"],
                "surface_disagreement": bucket in {"llm_only", "lifecycle_only"},
            }
        )
    bucket_counts = Counter(row["confluence_bucket"] for row in rows)
    surface_disagreement_rows = sum(1 for row in rows if row["surface_disagreement"])
    return rows, {
        "lifecycle": lifecycle_audit,
        "llm": llm_audit,
        "joined_rows": len(rows),
        "joined_dates": sorted({row["as_of_date"] for row in rows}),
        "joined_tickers": sorted({row["ticker"] for row in rows}),
        "confluence_bucket_counts": dict(sorted(bucket_counts.items())),
        "surface_disagreement_rows": surface_disagreement_rows,
        "surface_agreement_rate": round((len(rows) - surface_disagreement_rows) / len(rows), 6)
        if rows
        else None,
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
        "raw_settled_rows": len(settled),
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


def dedupe_settled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in sorted(
        rows,
        key=lambda item: (item["as_of_date"], item["ticker"], item["confluence_bucket"]),
    ):
        key = (
            row["ticker"],
            row["entry_date"],
            row["exit_date"],
            row["confluence_bucket"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


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
        "as_of_date_count": len({row["as_of_date"] for row in rows}),
        "concentration": concentration(rows),
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        bucket: summarize([row for row in rows if row["confluence_bucket"] == bucket])
        for bucket in CONFLUENCE_BUCKETS
        if bucket != "single_surface_pressure"
    }
    single_surface = [
        row for row in rows if row["confluence_bucket"] in {"llm_only", "lifecycle_only"}
    ]
    summary["single_surface_pressure"] = summarize(single_surface)
    return summary


def date_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[row["as_of_date"]].append(row)
    details = []
    worse_count = 0
    comparable_count = 0
    for date_text, group in sorted(by_date.items()):
        no_rows = [row for row in group if row["confluence_bucket"] == "no_pressure"]
        dual_rows = [row for row in group if row["confluence_bucket"] == "dual_pressure"]
        if not no_rows or not dual_rows:
            continue
        comparable_count += 1
        no_mean = mean([float(row["forward_5d_return_pct"]) for row in no_rows])
        dual_mean = mean([float(row["forward_5d_return_pct"]) for row in dual_rows])
        dual_worse = dual_mean is not None and no_mean is not None and dual_mean < no_mean
        if dual_worse:
            worse_count += 1
        details.append(
            {
                "as_of_date": date_text,
                "no_pressure_rows": len(no_rows),
                "dual_pressure_rows": len(dual_rows),
                "no_pressure_mean_return": round_or_none(no_mean, 6),
                "dual_pressure_mean_return": round_or_none(dual_mean, 6),
                "dual_worse": dual_worse,
            }
        )
    return {
        "comparable_dates": comparable_count,
        "dual_worse_dates": worse_count,
        "details": details,
    }


def sample_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = sorted(
        rows,
        key=lambda row: (
            row["confluence_bucket"] != "dual_pressure",
            row["as_of_date"],
            row["ticker"],
        ),
    )
    return [
        {
            key: row.get(key)
            for key in (
                "as_of_date",
                "ticker",
                "confluence_bucket",
                "confluence_score",
                "lifecycle_bucket",
                "llm_position_state",
                "entry_date",
                "exit_date",
                "market_value_usd",
                "forward_5d_return_pct",
                "forward_5d_pnl_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "unrealized_pnl_pct",
                "drawdown_from_hwm_pct",
            )
        }
        for row in wanted[:250]
    ]


def analyze(settled_rows: list[dict[str, Any]]) -> dict[str, Any]:
    deduped = dedupe_settled_rows(settled_rows)
    summary = bucket_summary(deduped)
    no_rows = [row for row in deduped if row["confluence_bucket"] == "no_pressure"]
    dual_rows = [row for row in deduped if row["confluence_bucket"] == "dual_pressure"]
    single_rows = [
        row for row in deduped if row["confluence_bucket"] in {"llm_only", "lifecycle_only"}
    ]
    returns = [float(row["forward_5d_return_pct"]) for row in deduped]
    scores = [float(row["confluence_score"]) for row in deduped]
    spy_values = [
        float(row["replacement_value_vs_spy_usd"])
        for row in deduped
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    spy_scores = [
        float(row["confluence_score"])
        for row in deduped
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    support = date_support(deduped)
    dual_concentration = concentration(dual_rows)

    checks = {
        "raw_settled_rows": len(settled_rows),
        "deduped_settled_rows": len(deduped),
        "no_pressure_rows": len(no_rows),
        "single_surface_rows": len(single_rows),
        "dual_pressure_rows": len(dual_rows),
        "joined_settled_bucket_counts": dict(Counter(row["confluence_bucket"] for row in deduped)),
        "severity_spearman_return": spearman(scores, returns),
        "severity_spearman_spy_replacement": spearman(spy_scores, spy_values),
        "date_support": support,
        "max_dual_adverse_pnl_share": dual_concentration["max_single_adverse_pnl_share"],
        "dual_mean_return": summary["dual_pressure"]["mean_forward_5d_return_pct"],
        "dual_median_return": summary["dual_pressure"]["median_forward_5d_return_pct"],
        "no_pressure_mean_return": summary["no_pressure"]["mean_forward_5d_return_pct"],
        "no_pressure_median_return": summary["no_pressure"]["median_forward_5d_return_pct"],
        "single_surface_mean_return": summary["single_surface_pressure"]["mean_forward_5d_return_pct"],
        "single_surface_median_return": summary["single_surface_pressure"]["median_forward_5d_return_pct"],
        "dual_concentration": dual_concentration,
    }
    checks.update(
        {
            "joined_sample_min_passed": len(deduped) >= CONFIG["min_joined_rows"],
            "no_pressure_sample_min_passed": len(no_rows) >= CONFIG["min_no_pressure_rows"],
            "single_surface_sample_min_passed": len(single_rows) >= CONFIG["min_single_surface_rows"],
            "dual_pressure_sample_min_passed": len(dual_rows) >= CONFIG["min_dual_pressure_rows"],
            "dual_mean_below_no_pressure": (
                checks["dual_mean_return"] is not None
                and checks["no_pressure_mean_return"] is not None
                and checks["dual_mean_return"] < checks["no_pressure_mean_return"]
            ),
            "dual_median_below_no_pressure": (
                checks["dual_median_return"] is not None
                and checks["no_pressure_median_return"] is not None
                and checks["dual_median_return"] < checks["no_pressure_median_return"]
            ),
            "dual_mean_below_single_surface": (
                checks["dual_mean_return"] is not None
                and checks["single_surface_mean_return"] is not None
                and checks["dual_mean_return"] < checks["single_surface_mean_return"]
            ),
            "dual_median_below_single_surface": (
                checks["dual_median_return"] is not None
                and checks["single_surface_median_return"] is not None
                and checks["dual_median_return"] < checks["single_surface_median_return"]
            ),
            "severity_spearman_return_negative": (
                checks["severity_spearman_return"] is not None
                and checks["severity_spearman_return"] < 0
            ),
            "severity_spearman_spy_replacement_negative": (
                checks["severity_spearman_spy_replacement"] is not None
                and checks["severity_spearman_spy_replacement"] < 0
            ),
            "date_support_passed": support["dual_worse_dates"] >= CONFIG["min_dates_dual_worse"],
            "dual_concentration_passed": (
                checks["max_dual_adverse_pnl_share"] is not None
                and checks["max_dual_adverse_pnl_share"] <= CONFIG["max_dual_adverse_pnl_share"]
            ),
        }
    )
    failures = [
        name
        for name, passed in {
            "joined_sample_too_small": checks["joined_sample_min_passed"],
            "no_pressure_sample_too_small": checks["no_pressure_sample_min_passed"],
            "single_surface_sample_too_small": checks["single_surface_sample_min_passed"],
            "dual_pressure_sample_too_small": checks["dual_pressure_sample_min_passed"],
            "dual_mean_not_below_no_pressure": checks["dual_mean_below_no_pressure"],
            "dual_median_not_below_no_pressure": checks["dual_median_below_no_pressure"],
            "dual_mean_not_below_single_surface": checks["dual_mean_below_single_surface"],
            "dual_median_not_below_single_surface": checks["dual_median_below_single_surface"],
            "severity_return_spearman_not_negative": checks["severity_spearman_return_negative"],
            "severity_spy_replacement_spearman_not_negative": checks[
                "severity_spearman_spy_replacement_negative"
            ],
            "too_few_dates_with_dual_worse_than_no_pressure": checks["date_support_passed"],
            "dual_adverse_concentration_failed": checks["dual_concentration_passed"],
        }.items()
        if not passed
    ]
    return {
        "raw_settled_rows": len(settled_rows),
        "deduped_settled_rows": len(deduped),
        "all_settled_rows": summarize(deduped),
        "bucket_summary": summary,
        "acceptance_checks": checks,
        "failed_reasons": failures,
        "observed_only_lead": not failures,
        "sample_rows": sample_rows(deduped),
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "sample_too_small": {
            "joined_sample_too_small",
            "no_pressure_sample_too_small",
            "single_surface_sample_too_small",
            "dual_pressure_sample_too_small",
        },
        "no_confluence_incremental_separation": {
            "dual_mean_not_below_single_surface",
            "dual_median_not_below_single_surface",
            "severity_return_spearman_not_negative",
            "severity_spy_replacement_spearman_not_negative",
        },
        "surfaces_are_same_endogenous_label": {"single_surface_sample_too_small"},
        "warehouse_outcomes_missing": {"joined_sample_too_small"},
        "ticker_concentration": {"dual_adverse_concentration_failed"},
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
    joined, source_audit = joined_rows()
    settled, settlement_audit = settle_rows(joined)
    analysis = analyze(settled)
    observed_lead = bool(analysis["observed_only_lead"])
    failed = list(analysis["failed_reasons"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_exit_lifecycle_llm_confluence_loss_lead_not_promoted"
        if observed_lead
        else "rejected_no_incremental_exit_lifecycle_llm_confluence_edge"
    )
    why = (
        "Dual-surface exit pressure showed incremental forward loss separation. "
        "This remains diagnostic-only because no shared executable policy was tested."
        if observed_lead
        else "The two production surfaces mostly agree on the same rows, leaving "
        "too little single-surface disagreement to prove incremental confluence "
        "value. The dual-pressure rows can still be monitored, but this does not "
        "justify an exit or risk rule."
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
                    "This does not convert either exit-lifecycle advisory labels "
                    "or LLM position-state labels into exits. It tests whether "
                    "same ticker/date agreement between both logged surfaces adds "
                    "incremental forward-loss information."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: join exit-lifecycle and "
                "LLM decision-log rows by ticker/as_of date, classify confluence "
                "pressure, settle next 5-trading-day outcomes, and test whether "
                "dual pressure is worse than single-surface and no-pressure rows."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "exit_lifecycle_source_dir": repo_rel(EXIT_LIFECYCLE_DIR),
            "llm_decision_source_dir": repo_rel(LLM_DECISION_DIR),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "llm_state_definitions": LLM_STATE_DEFINITIONS,
            "config": CONFIG,
            "outcome_definition": (
                "Gross diagnostic return from next trading session open after "
                "as_of_date to the close five trading days later using exit "
                "lifecycle market value as notional. No order is scheduled and "
                "no execution cost is applied."
            ),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(joined) and bool(settled),
            "fields_checked": [
                "as_of_date",
                "ticker",
                "entry_date",
                "target_price",
                "market_value_usd",
                "advisory_events.event_type",
                "has_advisory_event",
                "position_states",
                "llm_position_state",
                "confluence_bucket",
                "forward_5d_return_pct",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date_source")) for row in joined),
            "target_price_present_count": sum(1 for row in joined if row.get("target_price") is not None),
            "target_price_relevance": (
                "Checked for Gate 2. This attribution does not schedule target exits."
            ),
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["joined_rows"],
            "signals_survived": settlement_audit["raw_settled_rows"],
            "survival_rate": round(settlement_audit["raw_settled_rows"] / source_audit["joined_rows"], 4)
            if source_audit["joined_rows"]
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
                "Forward-only production rows, not canonical fixed-window PIT replay.",
                "No shared helper, adapter, daily execution rule, or exit policy was promoted.",
                "Rows are deduped by ticker, entry date, exit date, and confluence bucket.",
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
            "uses_llm_decision_log": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by converting dual-surface exit pressure, HIGH_REDUCE, "
                "TARGET_EXIT, ATR_EXIT, CRITICAL_EXIT, high-urgency, hard-stop, "
                "target-width, or trailing-stop labels into executable rules on "
                "the same forward rows. A valid retry needs materially more "
                "closed rows with actual single-surface disagreement, PIT "
                "intratrade path features, slot-reuse/winner-collateral accounting, "
                "and a shared default-off advisory helper before Gate 1-4 promotion."
            ),
            "new_evidence_required": (
                "More closed production rows where the LLM and exit-lifecycle "
                "surfaces disagree, or a distinct PIT feature that explains why "
                "dual pressure predicts avoidable future loss rather than merely "
                "duplicating the same current exit label."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(EXIT_LIFECYCLE_DIR),
            repo_rel(LLM_DECISION_DIR),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-011.json",
            "experiments/logs/exp-20260623-012.json",
            "experiments/logs/exp-20260429-032.json",
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
                "lifecycle": {
                    **payload["gate2"]["source_audit"]["lifecycle"],
                    "skipped_rows": payload["gate2"]["source_audit"]["lifecycle"]["skipped_rows"][:20],
                },
                "llm": {
                    **payload["gate2"]["source_audit"]["llm"],
                    "skipped_rows": payload["gate2"]["source_audit"]["llm"]["skipped_rows"][:20],
                },
            },
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "raw_settled_rows": analysis["raw_settled_rows"],
            "deduped_settled_rows": analysis["deduped_settled_rows"],
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
        "| Confluence Bucket | Rows | Mean Return | Median Return | Mean PnL | Mean vs SPY | Mean vs QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in CONFLUENCE_BUCKETS:
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
    checks = analysis["acceptance_checks"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: exit-lifecycle + LLM confluence",
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
            "- Raw settled rows: `{}`".format(checks.get("raw_settled_rows")),
            "- Deduped settled rows: `{}`".format(checks.get("deduped_settled_rows")),
            "- Single-surface rows: `{}`".format(checks.get("single_surface_rows")),
            "- Dual-pressure rows: `{}`".format(checks.get("dual_pressure_rows")),
            "- Severity Spearman(return): `{}`".format(checks.get("severity_spearman_return")),
            "- Severity Spearman(SPY replacement): `{}`".format(
                checks.get("severity_spearman_spy_replacement")
            ),
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
                "raw_settled_rows": checks.get("raw_settled_rows"),
                "deduped_settled_rows": checks.get("deduped_settled_rows"),
                "single_surface_rows": checks.get("single_surface_rows"),
                "dual_pressure_rows": checks.get("dual_pressure_rows"),
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
