"""exp-20260623-014: Kova closed-forward RS/growth attribution.

Observed-only alpha attribution. This settles closeable pre-exp013 Kova
forward snapshots against the hot OHLCV warehouse, then tests whether a fixed
RS plus filed-date fundamental-growth alignment score separates next-10-trading
day replacement value.

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
from datetime import date, datetime, timezone
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


EXPERIMENT_ID = "exp-20260623-014"
OWNER = "alpha-explore"
SLUG = "kova_closed_forward_rs_growth_alignment"
RUNNER = f"quant/experiments/exp_20260623_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_014_{SLUG}.json"
CLOSED_ROWS_JSONL = DATA_DIR / "kova_closed_forward_rs_growth_alignment_rows.jsonl"
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
KOVA_ROOT = REPO_ROOT / "data" / "kova"
SNAPSHOT_DIR = KOVA_ROOT / "snapshots"
RS_DIR = KOVA_ROOT / "rs_proxy"
FUNDAMENTALS_DIR = KOVA_ROOT / "fundamentals"

SOURCE_START = "2026-05-26"
SOURCE_END = "2026-06-12"
SELECTED_FUNDAMENTAL_COMPONENTS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps_diluted",
)

HYPOTHESIS = (
    "Observed-only attribution: Kova forward observations with aligned RS "
    "strength and filed-date fundamental growth breadth should show better "
    "next-10-trading-day cash/SPY/QQQ replacement value than weak-alignment "
    "rows, creating a future shared default-off Kova candidate-pool lead "
    "without changing strategy behavior."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_closed_forward_rs_growth_alignment_attribution"
TRIAL_VARIANT_ID = "pre_exp013_hot_warehouse_10d_v1"
CHANGED_VARIABLE = "kova_closed_forward_rs_growth_alignment_monotonicity_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260622-005", "exp-20260623-013"]
NEW_EVIDENCE_AXIS = (
    "New closed forward replacement-value rows from pre-exp013 Kova snapshots "
    "settled against data/warehouse/warehouse_main_hot.sqlite; not a "
    "canonical-window Companyfacts, 13F, RS, top-N, hold, cooldown, notional, "
    "or threshold sweep."
)
CAUSAL_COMPONENTS = [
    "pre-exp013 Kova snapshot normalization",
    "hot-warehouse 10d outcome settlement",
    "RS plus fundamental-growth alignment tertiles",
    "replacement value versus cash SPY QQQ",
    "no strategy behavior change",
]

CONFIG = {
    "hold_days": 10,
    "paper_notional_usd": 4000.0,
    "min_settled_rows": 30,
    "min_quality_rows": 30,
    "max_single_positive_pnl_share": 0.50,
    "positive_pnl_hhi_guardrail": 0.35,
    "quality_min_selected_components": 2,
    "quality_min_available_windows": 3,
}
BUCKETS = ["low_alignment", "mid_alignment", "high_alignment"]

DEFAULT_PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "sample_too_small",
        "no_monotonic_separation",
        "mega_cap_concentration",
        "forward_window_too_short",
        "companyfacts_overlap",
    ],
    "confidence_reason": (
        "Kova now has production-visible forward snapshots and exp-20260623-013 "
        "created the normalized surface, but prior Companyfacts/RS families are "
        "heavily explored and these are forward-only rows. The genuinely new "
        "evidence is closed replacement-value outcomes from the pre-exp013 Kova "
        "snapshots via the hot warehouse, so confidence is low and this cannot "
        "promote strategy behavior."
    ),
    "recorded_at": "2026-06-23T11:05:22+00:00",
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


def stable_id(parts: list[Any]) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:24]


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


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


def date_from_filename(path: Path) -> str | None:
    match = re.search(r"(20\d{6})", path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def source_file_for(directory: Path, stem: str, asof_date: str) -> Path:
    return directory / f"{stem}_{asof_date.replace('-', '')}.jsonl"


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


def rows_by_ticker(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    out: dict[str, dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        status = str(row.get("status") or row.get("growth_status") or "unknown")
        status_counts[status] += 1
        out[ticker] = row
    return out, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
    }


def summarize_companyfacts(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    ticker_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "companyfacts_growth_row_count": 0,
            "companyfacts_growth_ok_raw_rows": 0,
            "latest_component_asof": {},
            "latest_component_yoy_growth": {},
        }
    )
    status_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        canonical = str(row.get("canonical") or "")
        status = str(row.get("growth_status") or "unknown")
        status_counts[status] += 1
        stats = ticker_stats[ticker]
        stats["companyfacts_growth_row_count"] += 1
        if status == "ok":
            stats["companyfacts_growth_ok_raw_rows"] += 1
        if canonical not in SELECTED_FUNDAMENTAL_COMPONENTS or status != "ok":
            continue
        yoy = round_or_none(row.get("yoy_growth"), 6)
        if yoy is None:
            continue
        asof_date = str(row.get("asof_date") or "")[:10]
        prev_asof = str(stats["latest_component_asof"].get(canonical) or "")
        if not prev_asof or asof_date >= prev_asof:
            stats["latest_component_asof"][canonical] = asof_date
            stats["latest_component_yoy_growth"][canonical] = yoy

    compact: dict[str, dict[str, Any]] = {}
    for ticker, stats in ticker_stats.items():
        growth = dict(sorted(stats["latest_component_yoy_growth"].items()))
        compact[ticker] = {
            "companyfacts_growth_row_count": stats["companyfacts_growth_row_count"],
            "companyfacts_growth_ok_raw_rows": stats["companyfacts_growth_ok_raw_rows"],
            "companyfacts_selected_ok_component_count": len(growth),
            "companyfacts_selected_positive_yoy_count": sum(
                1 for value in growth.values() if value is not None and value > 0
            ),
            "companyfacts_latest_component_yoy_growth": growth,
            "companyfacts_latest_component_asof": dict(
                sorted(stats["latest_component_asof"].items())
            ),
        }
    return compact, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
    }


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


def snapshot_files() -> list[Path]:
    files = []
    for path in sorted(SNAPSHOT_DIR.glob("kova_data_snapshot_*.json")):
        asof_date = date_from_filename(path)
        if asof_date and SOURCE_START <= asof_date <= SOURCE_END:
            files.append(path)
    return files


def build_observations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "source_start": SOURCE_START,
        "source_end": SOURCE_END,
        "snapshot_files": [],
        "rs_proxy": [],
        "companyfacts_growth": [],
    }
    for snapshot_path in snapshot_files():
        snapshot = read_json(snapshot_path, {})
        asof_date = str(snapshot.get("asof_date") or date_from_filename(snapshot_path) or "")[:10]
        if not asof_date:
            continue
        rs_path = source_file_for(RS_DIR, "rs_proxy", asof_date)
        fundamentals_path = source_file_for(FUNDAMENTALS_DIR, "companyfacts_growth", asof_date)
        rs_by_ticker, rs_audit = rows_by_ticker(rs_path)
        fundamentals_by_ticker, fundamentals_audit = summarize_companyfacts(fundamentals_path)
        snapshot_tickers = sorted({str(t).upper() for t in snapshot.get("tickers") or [] if str(t).strip()})

        audit["snapshot_files"].append(
            {
                "path": repo_rel(snapshot_path),
                "asof_date": asof_date,
                "ticker_count": len(snapshot_tickers),
                "status": snapshot.get("status"),
                "schema_version": snapshot.get("schema_version"),
            }
        )
        audit["rs_proxy"].append(rs_audit)
        audit["companyfacts_growth"].append(fundamentals_audit)

        for ticker in snapshot_tickers:
            rs_row = rs_by_ticker.get(ticker) or {}
            fundamentals = fundamentals_by_ticker.get(ticker) or {}
            ok_count = int(fundamentals.get("companyfacts_selected_ok_component_count") or 0)
            positive_count = int(fundamentals.get("companyfacts_selected_positive_yoy_count") or 0)
            rs_values = [
                as_float(rs_row.get("rs_proxy_rank_pct_20d")),
                as_float(rs_row.get("rs_proxy_rank_pct_60d")),
                as_float(rs_row.get("rs_proxy_rank_pct_120d")),
            ]
            rs_values = [value for value in rs_values if value is not None]
            rs_alignment_score = mean(rs_values)
            growth_breadth_score = positive_count / ok_count if ok_count else None
            if rs_alignment_score is not None and growth_breadth_score is not None:
                alignment_score = (rs_alignment_score + growth_breadth_score) / 2.0
            else:
                alignment_score = None
            quality_flags = []
            if rs_row.get("status") != "ok":
                quality_flags.append("rs_proxy_not_ok")
            if int(rs_row.get("available_window_count") or 0) < CONFIG["quality_min_available_windows"]:
                quality_flags.append("insufficient_rs_windows")
            if ok_count < CONFIG["quality_min_selected_components"]:
                quality_flags.append("too_few_companyfacts_growth_components")
            if alignment_score is None:
                quality_flags.append("missing_alignment_score")

            observations.append(
                {
                    "schema_version": 1,
                    "experiment_id": EXPERIMENT_ID,
                    "rule_version": CHANGED_VARIABLE,
                    "observation_id": stable_id([CHANGED_VARIABLE, asof_date, ticker]),
                    "source": "kova_pre_exp013_forward_snapshot",
                    "asof_date": asof_date,
                    "ticker": ticker,
                    "source_snapshot_file": repo_rel(snapshot_path),
                    "rs_proxy_source_file": repo_rel(rs_path),
                    "companyfacts_growth_source_file": repo_rel(fundamentals_path),
                    "rs_proxy_status": rs_row.get("status"),
                    "available_window_count": rs_row.get("available_window_count"),
                    "rs_proxy_rank_pct_20d": round_or_none(rs_row.get("rs_proxy_rank_pct_20d")),
                    "rs_proxy_rank_pct_60d": round_or_none(rs_row.get("rs_proxy_rank_pct_60d")),
                    "rs_proxy_rank_pct_120d": round_or_none(rs_row.get("rs_proxy_rank_pct_120d")),
                    "excess_ret_20d_vs_spy": round_or_none(rs_row.get("excess_ret_20d_vs_spy")),
                    "excess_ret_60d_vs_spy": round_or_none(rs_row.get("excess_ret_60d_vs_spy")),
                    "excess_ret_120d_vs_spy": round_or_none(rs_row.get("excess_ret_120d_vs_spy")),
                    "companyfacts_growth_row_count": fundamentals.get("companyfacts_growth_row_count", 0),
                    "companyfacts_growth_ok_raw_rows": fundamentals.get(
                        "companyfacts_growth_ok_raw_rows", 0
                    ),
                    "companyfacts_selected_ok_component_count": ok_count,
                    "companyfacts_selected_positive_yoy_count": positive_count,
                    "companyfacts_latest_component_yoy_growth": fundamentals.get(
                        "companyfacts_latest_component_yoy_growth", {}
                    ),
                    "companyfacts_latest_component_asof": fundamentals.get(
                        "companyfacts_latest_component_asof", {}
                    ),
                    "rs_alignment_score": round_or_none(rs_alignment_score),
                    "growth_breadth_score": round_or_none(growth_breadth_score),
                    "kova_alignment_score": round_or_none(alignment_score),
                    "quality_flags": quality_flags,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
    return observations, audit


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
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0.0),
                }
            )
    return {ticker: rows for ticker, rows in rows_by_symbol.items() if rows}


def first_index_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if row["date"] > day:
            return index
    return None


def pnl_between(rows: list[dict[str, Any]], entry_date: str, exit_date: str, notional: float) -> float | None:
    by_date = {row["date"]: row for row in rows}
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


def asof_week(asof_date: str) -> str:
    iso = date.fromisoformat(asof_date).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def settle_observations(observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = {row["ticker"] for row in observations}
    tickers.update({"SPY", "QQQ"})
    bars = load_ohlcv_rows(tickers, SOURCE_START, "2026-06-22")
    skipped: Counter[str] = Counter()
    settled: list[dict[str, Any]] = []
    notional = float(CONFIG["paper_notional_usd"])
    for row in observations:
        ticker = row["ticker"]
        stock_rows = bars.get(ticker)
        if not stock_rows:
            skipped["missing_ticker_ohlcv"] += 1
            continue
        entry_index = first_index_after(stock_rows, row["asof_date"])
        if entry_index is None:
            skipped["missing_entry_bar"] += 1
            continue
        exit_index = entry_index + int(CONFIG["hold_days"])
        if exit_index >= len(stock_rows):
            skipped["not_yet_10d_closed"] += 1
            continue
        entry = stock_rows[entry_index]
        exit_ = stock_rows[exit_index]
        entry_raw = as_float(entry.get("open"))
        exit_raw = as_float(exit_.get("close"))
        if entry_raw is None or entry_raw <= 0 or exit_raw is None or exit_raw <= 0:
            skipped["bad_entry_or_exit_price"] += 1
            continue
        entry_price = apply_entry_fill(entry_raw)
        exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        pnl = notional * pnl_pct_net
        spy_pnl = pnl_between(bars.get("SPY", []), entry["date"], exit_["date"], notional)
        qqq_pnl = pnl_between(bars.get("QQQ", []), entry["date"], exit_["date"], notional)
        quality_pass = not row["quality_flags"]
        settled.append(
            {
                **row,
                "entry_date": entry["date"],
                "exit_date": exit_["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "forward_10d_return_pct": round(pnl_pct_net, 6),
                "pnl": round(pnl, 2),
                "replacement_value_vs_cash_usd": round(pnl, 2),
                "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2) if spy_pnl is not None else None,
                "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2) if qqq_pnl is not None else None,
                "spy_same_window_pnl": round(spy_pnl, 2) if spy_pnl is not None else None,
                "qqq_same_window_pnl": round(qqq_pnl, 2) if qqq_pnl is not None else None,
                "paper_notional_usd": notional,
                "outcome_status": "closed_10d_forward",
                "asof_week": asof_week(row["asof_date"]),
                "quality_pass": quality_pass,
            }
        )
    audit = {
        "source_observations": len(observations),
        "settled_rows": len(settled),
        "skipped_reasons": dict(sorted(skipped.items())),
        "loaded_ohlcv_tickers": len(bars),
        "warehouse_path": repo_rel(HOT_WAREHOUSE),
        "hold_days": CONFIG["hold_days"],
        "entry_rule": "first tradable open strictly after Kova asof_date",
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


def assign_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [
        dict(row)
        for row in rows
        if row.get("quality_pass") and as_float(row.get("kova_alignment_score")) is not None
    ]
    scored.sort(key=lambda item: (item["kova_alignment_score"], item["asof_date"], item["ticker"]))
    n = len(scored)
    for rank, row in enumerate(scored):
        if rank < n / 3:
            bucket = "low_alignment"
        elif rank < 2 * n / 3:
            bucket = "mid_alignment"
        else:
            bucket = "high_alignment"
        row["kova_alignment_bucket"] = bucket
    return scored


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


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = as_float(row.get("pnl"))
        if pnl is not None and pnl > 0:
            by_ticker[str(row.get("ticker"))] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl": 0.0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: pnl / total for ticker, pnl in by_ticker.items()}
    return {
        "positive_pnl": round(total, 2),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 2), "share": round(shares[ticker], 6)}
            for ticker, pnl in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if as_float(row.get("pnl")) is not None]
    repl_spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    repl_qqq = [
        float(row["replacement_value_vs_qqq_usd"])
        for row in rows
        if as_float(row.get("replacement_value_vs_qqq_usd")) is not None
    ]
    scores = [
        float(row["kova_alignment_score"])
        for row in rows
        if as_float(row.get("kova_alignment_score")) is not None
    ]
    return {
        "n": len(rows),
        "mean_pnl": round_or_none(mean(pnls), 4),
        "median_pnl": round_or_none(median(pnls), 4) if pnls else None,
        "total_pnl": round_or_none(sum(pnls), 2) if pnls else 0.0,
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 6) if pnls else None,
        "mean_replacement_vs_spy": round_or_none(mean(repl_spy), 4),
        "mean_replacement_vs_qqq": round_or_none(mean(repl_qqq), 4),
        "median_replacement_vs_spy": round_or_none(median(repl_spy), 4) if repl_spy else None,
        "median_replacement_vs_qqq": round_or_none(median(repl_qqq), 4) if repl_qqq else None,
        "mean_alignment_score": round_or_none(mean(scores), 6),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "asof_weeks": sorted({str(row.get("asof_week")) for row in rows}),
        "concentration": concentration(rows),
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        bucket: summarize_rows([row for row in rows if row.get("kova_alignment_bucket") == bucket])
        for bucket in BUCKETS
    }


def week_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    weeks = sorted({str(row.get("asof_week")) for row in rows})
    for week in weeks:
        week_rows = [row for row in rows if row.get("asof_week") == week]
        buckets = bucket_summary(week_rows)
        high = buckets["high_alignment"]
        low = buckets["low_alignment"]
        out[week] = {
            "rows": len(week_rows),
            "bucket_summary": buckets,
            "high_beats_low_mean_pnl": (
                high["mean_pnl"] is not None
                and low["mean_pnl"] is not None
                and high["mean_pnl"] > low["mean_pnl"]
            ),
            "high_positive_mean_pnl": high["mean_pnl"] is not None and high["mean_pnl"] > 0,
        }
    return out


def analyze(settled_rows: list[dict[str, Any]]) -> dict[str, Any]:
    quality_rows = assign_buckets(settled_rows)
    scores = [float(row["kova_alignment_score"]) for row in quality_rows]
    cash = [float(row["replacement_value_vs_cash_usd"]) for row in quality_rows]
    spy = [
        float(row["replacement_value_vs_spy_usd"])
        for row in quality_rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    spy_scores = [
        float(row["kova_alignment_score"])
        for row in quality_rows
        if as_float(row.get("replacement_value_vs_spy_usd")) is not None
    ]
    weeks = week_summary(quality_rows)
    return {
        "all_settled_rows": summarize_rows(settled_rows),
        "quality_rows": summarize_rows(quality_rows),
        "quality_bucket_summary": bucket_summary(quality_rows),
        "quality_week_summary": weeks,
        "quality_week_count": len(weeks),
        "quality_week_high_beats_low_count": sum(
            1 for item in weeks.values() if item["high_beats_low_mean_pnl"]
        ),
        "quality_week_high_positive_count": sum(
            1 for item in weeks.values() if item["high_positive_mean_pnl"]
        ),
        "spearman_score_to_cash_replacement": spearman(scores, cash),
        "spearman_score_to_spy_replacement": spearman(spy_scores, spy),
        "sample_rows": quality_rows[:10],
    }


def gt(a: Any, b: Any) -> bool:
    return a is not None and b is not None and a > b


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    buckets = analysis["quality_bucket_summary"]
    low = buckets["low_alignment"]
    mid = buckets["mid_alignment"]
    high = buckets["high_alignment"]
    conc = analysis["quality_rows"]["concentration"]
    max_share = conc.get("max_single_positive_pnl_share")
    hhi = conc.get("positive_pnl_hhi")
    checks = {
        "settled_sample_min_passed": analysis["all_settled_rows"]["n"] >= CONFIG["min_settled_rows"],
        "quality_sample_min_passed": analysis["quality_rows"]["n"] >= CONFIG["min_quality_rows"],
        "high_mean_cash_beats_low": gt(high["mean_pnl"], low["mean_pnl"]),
        "high_median_cash_beats_low": gt(high["median_pnl"], low["median_pnl"]),
        "high_mean_spy_beats_low": gt(high["mean_replacement_vs_spy"], low["mean_replacement_vs_spy"]),
        "high_mean_qqq_beats_low": gt(high["mean_replacement_vs_qqq"], low["mean_replacement_vs_qqq"]),
        "mean_cash_monotonic_high_mid_low": (
            gt(high["mean_pnl"], mid["mean_pnl"]) and gt(mid["mean_pnl"], low["mean_pnl"])
        ),
        "median_cash_monotonic_high_mid_low": (
            gt(high["median_pnl"], mid["median_pnl"]) and gt(mid["median_pnl"], low["median_pnl"])
        ),
        "spearman_cash_positive": (
            analysis["spearman_score_to_cash_replacement"] is not None
            and analysis["spearman_score_to_cash_replacement"] > 0
        ),
        "spearman_spy_positive": (
            analysis["spearman_score_to_spy_replacement"] is not None
            and analysis["spearman_score_to_spy_replacement"] > 0
        ),
        "concentration_passed": (
            max_share is not None
            and max_share <= CONFIG["max_single_positive_pnl_share"]
            and hhi is not None
            and hhi <= CONFIG["positive_pnl_hhi_guardrail"]
        ),
        "at_least_two_weeks_high_beats_low": (
            analysis["quality_week_high_beats_low_count"] >= 2
        ),
        "at_least_two_weeks_high_positive": (
            analysis["quality_week_high_positive_count"] >= 2
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return checks, failed


def calibration(prediction: dict[str, Any], observed_lead: bool, failed: list[str]) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability"))
    actual = 1 if observed_lead else 0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    monotonic_failed = any(
        token in reason
        for reason in failed
        for token in ("monotonic", "spearman", "high_mean", "high_median")
    )
    predicted_failure_mode_hit = any(mode in failed for mode in predicted_modes) or (
        "no_monotonic_separation" in predicted_modes and monotonic_failed
    )
    return {
        "actual_decision": (
            "observed_only_positive_kova_rs_growth_alignment_lead_not_promoted"
            if observed_lead
            else "rejected_no_monotonic_kova_rs_growth_alignment_edge"
        ),
        "actual_success": actual,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4) if probability is not None else None,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": predicted_failure_mode_hit,
        "surprise_note": (
            "The closed forward Kova rows produced a clean observed-only lead, "
            "which is above the low-confidence prior but still not promotable."
            if observed_lead
            else "Closed forward Kova rows did not show robust monotonic "
            "replacement-value separation; this matches the low-confidence prior."
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    observations, source_audit = build_observations()
    settled_rows, settlement_audit = settle_observations(observations)
    analysis = analyze(settled_rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_kova_rs_growth_alignment_lead_not_promoted"
        if observed_lead
        else "rejected_no_monotonic_kova_rs_growth_alignment_edge"
    )
    now = utc_now()
    why = (
        "The fixed Kova RS/growth alignment score separated closed forward "
        "replacement-value rows, but this remains forward-only observation and "
        "does not promote a helper or strategy behavior."
        if observed_lead
        else "The pre-exp013 closed Kova rows did not show enough monotonic "
        "cash/SPY/QQQ replacement-value separation. The surface remains useful "
        "for forward maturation, not for threshold or rank promotion."
    )
    return {
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
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_forward_replacement_value_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260622-005": (
                    "Blocked Kova multi-source alpha because fixed-window PIT coverage, "
                    "shared helper, and closed forward replacement rows were missing."
                ),
                "exp-20260623-013": (
                    "Accepted measurement repair created a broad Kova observation ledger "
                    "but left rows pending and prohibited threshold tests until rows close."
                ),
                "novelty_gate": (
                    "Reservation warned on adjacent OHLCV relation families; override "
                    "was recorded because this uses new closed forward replacement-value "
                    "rows from pre-exp013 Kova snapshots, not frozen-window retuning."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: build pre-exp013 Kova observations, "
                "settle next-open 10-trading-day outcomes in the hot warehouse, score "
                "RS/growth alignment, bucket into tertiles, and test cash/SPY/QQQ "
                "replacement-value monotonicity. No trading policy changes."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if settled and quality samples are >=30, high "
                "alignment beats low on mean and median cash PnL plus mean SPY/QQQ "
                "replacement value, cash mean/median are high>mid>low, Spearman is "
                "positive, concentration passes, and at least two as-of week cohorts "
                "support high>low."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_start": SOURCE_START,
            "source_end": SOURCE_END,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(HOT_WAREHOUSE),
            "closed_rows_jsonl": repo_rel(CLOSED_ROWS_JSONL),
            "selected_fundamental_components": list(SELECTED_FUNDAMENTAL_COMPONENTS),
            "config": CONFIG,
            "score_definition": (
                "kova_alignment_score = average(mean(rs_proxy_rank_pct_20d, "
                "rs_proxy_rank_pct_60d, rs_proxy_rank_pct_120d), "
                "positive_selected_fundamental_components / selected_ok_components)"
            ),
            "bucket_method": "tertiles on kova_alignment_score within closed quality rows",
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(observations) and settlement_audit["settled_rows"] > 0,
            "source_observations": len(observations),
            "settled_rows": settlement_audit["settled_rows"],
            "quality_rows": analysis["quality_rows"]["n"],
            "fields_checked": [
                "asof_date",
                "ticker",
                "rs_proxy_rank_pct_20d",
                "rs_proxy_rank_pct_60d",
                "rs_proxy_rank_pct_120d",
                "companyfacts_selected_ok_component_count",
                "companyfacts_selected_positive_yoy_count",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in settled_rows),
            "target_price_relevance": (
                "Not applicable: this is observed-only 10-trading-day outcome "
                "attribution and does not schedule target exits or orders."
            ),
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(observations),
            "signals_survived": settlement_audit["settled_rows"],
            "survival_rate": round(settlement_audit["settled_rows"] / len(observations), 4)
            if observations
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
            "lead_limitations": [
                "Forward-only observations, not canonical fixed-window PIT Kova coverage.",
                "No shared helper or daily adapter promoted.",
                "The broad post-2026-06-13 Kova universe has not yet closed 10d outcomes.",
            ],
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
            "closed_rows_jsonl": repo_rel(CLOSED_ROWS_JSONL),
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
            "uses_kova_forward_snapshots": True,
            "forward_only_not_fixed_window_pit_coverage": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova RS rank, Companyfacts growth breadth, 13F, "
                "intraday, top-N, hold, cooldown, or notional thresholds on the "
                "same pre-exp013 forward rows. The fixed alignment screen is the "
                "attribution result."
            ),
            "new_evidence_required": (
                "A valid Kova retry needs the broad 2026-06-13+ Kova rows closed "
                "with replacement value, a shared default-off observer with fixed "
                "candidate semantics, or materially different PIT fields such as "
                "actual intraday flow or non-skipped 13F provenance."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(CLOSED_ROWS_JSONL),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260622-005.json",
            "experiments/logs/exp-20260623-013.json",
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
            "dependencies_validated": payload["gate2"]["dependencies_validated"],
            "source_observations": payload["gate2"]["source_observations"],
            "settled_rows": payload["gate2"]["settled_rows"],
            "quality_rows": payload["gate2"]["quality_rows"],
            "fields_checked": payload["gate2"]["fields_checked"],
            "entry_date_present": payload["gate2"]["entry_date_present"],
            "target_price_relevance": payload["gate2"]["target_price_relevance"],
            "settlement_audit": payload["gate2"]["settlement_audit"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "all_settled_rows": analysis["all_settled_rows"],
            "quality_rows": analysis["quality_rows"],
            "quality_bucket_summary": analysis["quality_bucket_summary"],
            "quality_week_count": analysis["quality_week_count"],
            "quality_week_high_beats_low_count": analysis["quality_week_high_beats_low_count"],
            "spearman_score_to_cash_replacement": analysis["spearman_score_to_cash_replacement"],
            "spearman_score_to_spy_replacement": analysis["spearman_score_to_spy_replacement"],
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
    buckets = analysis["quality_bucket_summary"]
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
                mean_pnl=money(bucket["mean_pnl"]),
                median_pnl=money(bucket["median_pnl"]),
                spy=money(bucket["mean_replacement_vs_spy"]),
                qqq=money(bucket["mean_replacement_vs_qqq"]),
                win="n/a" if win is None else f"{win:.2%}",
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova closed-forward RS/growth alignment",
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
            "## Quality Buckets",
            "",
            *rows,
            "",
            f"- Settled rows: `{analysis['all_settled_rows']['n']}`",
            f"- Quality rows: `{analysis['quality_rows']['n']}`",
            f"- Spearman(score, cash replacement): `{analysis['spearman_score_to_cash_replacement']}`",
            f"- Spearman(score, SPY replacement): `{analysis['spearman_score_to_spy_replacement']}`",
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
        CLOSED_ROWS_JSONL,
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
        "closed_rows_jsonl": repo_rel(CLOSED_ROWS_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], settled_rows: list[dict[str, Any]]) -> None:
    write_jsonl(CLOSED_ROWS_JSONL, settled_rows)
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
        "closed_rows_jsonl": repo_rel(CLOSED_ROWS_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "all_settled_rows": payload["attribution"]["analysis"]["all_settled_rows"],
            "quality_rows": payload["attribution"]["analysis"]["quality_rows"],
            "quality_bucket_summary": payload["attribution"]["analysis"]["quality_bucket_summary"],
            "spearman_score_to_cash_replacement": payload["attribution"]["analysis"][
                "spearman_score_to_cash_replacement"
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
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    observations, _source_audit = build_observations()
    settled_rows, _settlement_audit = settle_observations(observations)
    payload = build_payload()
    persist(payload, settled_rows)
    analysis = payload["attribution"]["analysis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "settled_rows": analysis["all_settled_rows"]["n"],
                "quality_rows": analysis["quality_rows"]["n"],
                "spearman_cash": analysis["spearman_score_to_cash_replacement"],
                "bucket_summary": analysis["quality_bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
