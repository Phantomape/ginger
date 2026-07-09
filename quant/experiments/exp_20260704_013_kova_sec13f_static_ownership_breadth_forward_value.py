"""exp-20260704-013: Kova SEC13F static ownership breadth forward value.

Observed-only alpha attribution. This evaluates whether the current Kova
SEC13F ownership sidecar adds a distinct sponsorship/crowding discriminator
when joined to Kova RS proxy rows: low-ownership-breadth high-RS names should
outperform crowded high-RS names over the next 10 trading sessions.

No strategy behavior, shared helper, daily adapter, paper order, live order,
ranking, sizing, exit, watchlist, or LLM behavior changes.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260704-013"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_static_ownership_breadth_forward_value"
RUNNER = f"quant/experiments/exp_20260704_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OWNERSHIP_DIR = REPO_ROOT / "data" / "kova" / "institutional"
RS_PROXY_DIR = REPO_ROOT / "data" / "kova" / "rs_proxy"
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260704_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Kova current SEC13F ownership breadth joined to RS proxy rows may identify "
    "low-sponsorship high-RS names with better 10d cash/SPY/QQQ replacement "
    "value than crowded high-RS names, using the latest current ownership "
    "sidecar and settled forward rows only as observed-only attribution."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_kova_sec13f_static_ownership_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_static_ownership_breadth_forward_value"
TRIAL_VARIANT_ID = "low_breadth_high_rs_vs_crowded_high_rs_forward10_v1"
CHANGED_VARIABLE = "kova_sec13f_static_ownership_breadth_forward_value_v1"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEW_EVIDENCE_TYPE = "new_forward_rows"
NEW_EVIDENCE_AXIS = (
    "The Kova current SEC13F ownership sidecar now has broad June 2026 rows that "
    "can be joined to Kova RS proxy and settled with the hot warehouse through "
    "2026-07-02. This is a forward-row attribution read, not an adjacent 13F "
    "active-flow, manager-definition, top-N, hold, notional, or threshold retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260615-009",
    "exp-20260702-015",
    "exp-20260704-011",
]
CAUSAL_COMPONENTS = [
    "Kova SEC13F current ownership sidecar",
    "Kova RS proxy rank fields",
    "cross-sectional holder-count breadth buckets",
    "10d cash/SPY/QQQ replacement-value attribution",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260704-013/exp_20260704_013_kova_sec13f_static_ownership_breadth_forward_value.json",
    "experiments/cards/exp-20260704-013.md",
    "experiments/manifests/exp-20260704-013.json",
    "experiments/tickets/exp-20260704-013.json",
    "experiments/logs/exp-20260704-013.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZON = 10
PROXY_NOTIONAL_USD = 10_000.0
COMPARATORS = ("SPY", "QQQ")
BUCKETS = ("low_breadth_high_rs", "crowded_high_rs", "low_breadth_weak_rs", "other")
MIN_BROAD_SOURCE_ROWS = 500
REQUIRED_SOURCE_FIELDS = [
    "query_asof_date",
    "asof_date",
    "ticker",
    "status",
    "holder_count",
    "position_row_count",
    "total_value_usd",
    "rs_proxy_rank_pct_20d",
    "rs_proxy_rank_pct_120d",
]
ACCEPTANCE_RULE = {
    "horizon": HORIZON,
    "primary_bucket": "low_breadth_high_rs",
    "low_breadth_high_rs": "holder_count_breadth_pct <= 0.35 and rs_proxy_rank_pct_20d >= 0.80",
    "crowded_high_rs": "holder_count_breadth_pct >= 0.80 and rs_proxy_rank_pct_20d >= 0.80",
    "low_breadth_weak_rs": "holder_count_breadth_pct <= 0.35 and rs_proxy_rank_pct_20d <= 0.40",
    "min_primary_rows": 80,
    "min_crowded_rows": 80,
    "min_weak_rows": 80,
    "min_settled_signal_dates": 3,
    "max_primary_single_positive_pnl_share": 0.35,
    "max_primary_positive_pnl_hhi": 0.20,
    "max_primary_median_price_lag_days": 7,
    "required_mean_outperformance": [
        "primary SPY replacement mean > crowded SPY replacement mean",
        "primary QQQ replacement mean > crowded QQQ replacement mean",
        "primary SPY replacement mean > weak SPY replacement mean",
        "primary QQQ replacement mean > weak QQQ replacement mean",
    ],
    "required_median_outperformance": [
        "primary SPY replacement median > crowded SPY replacement median",
        "primary SPY replacement median > weak SPY replacement median",
    ],
}
DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "13f_disclosure_lag",
        "ownership_context_not_alpha",
        "overlap_with_rs_momentum",
        "sample_concentration",
    ],
    "confidence_reason": (
        "13F has mostly failed as direct timing alpha and is delayed ownership "
        "context, but the latest Kova current ownership sidecar plus settled "
        "hot-warehouse forward rows is a new forward evidence axis; this run "
        "only checks whether static sponsorship breadth adds interpretable "
        "replacement-value separation beyond RS."
    ),
}
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "watchlist_changed": False,
    "llm_decision_boundary_changed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "uses_kova_sec13f_sidecar": True,
    "uses_kova_rs_proxy_sidecar": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "parity_note": (
        "Observed-only attribution over existing Kova sidecars and the hot "
        "warehouse. No shared policy/helper or production adapter behavior changed."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    return None if number is None else int(number)


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    return None if number is None else round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile(values: list[float], ratio: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    return clean[lower] + (clean[upper] - clean[lower]) * (position - lower)


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def days_between(a: Any, b: Any) -> int | None:
    first = parse_date(a)
    second = parse_date(b)
    if first is None or second is None:
        return None
    return (first - second).days


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def baseline_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(safe_int(window.get("signals_generated")) or 0 for window in windows)
    survived = sum(safe_int(window.get("signals_survived")) or 0 for window in windows)
    drawdowns = [
        safe_float(window.get("max_drawdown_pct"))
        for window in windows
        if safe_float(window.get("max_drawdown_pct")) is not None
    ]
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "window_count": len(windows),
        "windows": [
            {
                "label": item.get("label"),
                "start": item.get("start"),
                "end": item.get("end"),
                "expected_value_score": round_or_none(item.get("expected_value_score"), 4),
                "total_pnl": round_or_none(item.get("total_pnl"), 2),
                "trade_count": safe_int(item.get("trade_count")),
                "signals_generated": safe_int(item.get("signals_generated")),
                "signals_survived": safe_int(item.get("signals_survived")),
                "survival_rate": round_or_none(item.get("survival_rate"), 6),
            }
            for item in windows
        ],
        "aggregate_expected_value_score": round(
            sum(safe_float(item.get("expected_value_score")) or 0.0 for item in windows), 4
        ),
        "aggregate_total_pnl": round(
            sum(safe_float(item.get("total_pnl")) or 0.0 for item in windows), 2
        ),
        "aggregate_trade_count": sum(safe_int(item.get("trade_count")) or 0 for item in windows),
        "aggregate_signals_generated": generated,
        "aggregate_signals_survived": survived,
        "aggregate_survival_rate": round(survived / generated, 6) if generated else None,
        "worst_max_drawdown_pct": round(max(drawdowns), 4) if drawdowns else None,
    }


def immutable_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro&immutable=1"


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def file_summary(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"file": repo_rel(path), "rows": len(rows), "sha256": sha256_file(path)}


def load_rs_proxy_index() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    paths = sorted(RS_PROXY_DIR.glob("rs_proxy_*.jsonl"))
    index: dict[tuple[str, str], dict[str, Any]] = {}
    file_summaries = []
    raw_count = 0
    usable_count = 0
    for path in paths:
        rows = iter_jsonl(path)
        raw_count += len(rows)
        file_summaries.append(file_summary(path, rows))
        for row in rows:
            ticker = str(row.get("ticker") or "").upper().strip()
            asof = str(row.get("asof_date") or "")[:10]
            if (
                not ticker
                or not asof
                or str(row.get("status") or "").lower() != "ok"
                or safe_float(row.get("rs_proxy_rank_pct_20d")) is None
                or safe_float(row.get("rs_proxy_rank_pct_120d")) is None
            ):
                continue
            usable_count += 1
            index[(ticker, asof)] = row
    return index, {
        "source_dir": repo_rel(RS_PROXY_DIR),
        "source_file_count": len(paths),
        "raw_rows": raw_count,
        "usable_rows": usable_count,
        "index_keys": len(index),
        "source_files": file_summaries,
    }


def source_field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    coverage = {}
    for field in REQUIRED_SOURCE_FIELDS:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        coverage[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "coverage": round(present / total, 6) if total else None,
        }
    return coverage


def rank_pct_by_date(rows: list[dict[str, Any]], field: str, out_field: str) -> None:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row["signal_date"])].append(row)
    for date_rows in by_date.values():
        ordered = sorted(
            [row for row in date_rows if safe_float(row.get(field)) is not None],
            key=lambda row: (float(row[field]), str(row.get("ticker"))),
        )
        denom = max(len(ordered) - 1, 1)
        for index, row in enumerate(ordered):
            row[out_field] = round(index / denom, 6)


def load_joined_source_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rs_index, rs_metadata = load_rs_proxy_index()
    paths = sorted(OWNERSHIP_DIR.glob("sec13f_ownership_*.jsonl"))
    raw_rows: list[dict[str, Any]] = []
    file_summaries = []
    skipped_small_files = []
    duplicate_keys = 0
    joined: dict[tuple[str, str], dict[str, Any]] = {}

    for path in paths:
        rows = iter_jsonl(path)
        raw_rows.extend({**row, "source_file": repo_rel(path)} for row in rows)
        file_summaries.append(file_summary(path, rows))
        if len(rows) < MIN_BROAD_SOURCE_ROWS:
            skipped_small_files.append(repo_rel(path))
            continue
        for row in rows:
            ticker = str(row.get("ticker") or "").upper().strip()
            signal_date = str(row.get("query_asof_date") or row.get("asof_date") or "")[:10]
            holder_count = safe_float(row.get("holder_count"))
            if (
                not ticker
                or not signal_date
                or str(row.get("status") or "").lower() != "ok"
                or holder_count is None
            ):
                continue
            rs = rs_index.get((ticker, signal_date))
            if not rs:
                continue
            cleaned = dict(row)
            cleaned.update(
                {
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "ownership_asof_date": str(row.get("asof_date") or "")[:10],
                    "holder_count": holder_count,
                    "position_row_count": safe_float(row.get("position_row_count")),
                    "total_value_usd": safe_float(row.get("total_value_usd")),
                    "rs_proxy_rank_pct_20d": safe_float(rs.get("rs_proxy_rank_pct_20d")),
                    "rs_proxy_rank_pct_120d": safe_float(rs.get("rs_proxy_rank_pct_120d")),
                    "rs_proxy_asof_price_date": str(rs.get("asof_price_date") or "")[:10],
                    "price_lag_days": days_between(signal_date, rs.get("asof_price_date")),
                    "ownership_source_file": repo_rel(path),
                    "rs_proxy_source_file": rs.get("source_file"),
                }
            )
            key = (ticker, signal_date)
            if key in joined:
                duplicate_keys += 1
            joined[key] = cleaned

    rows = sorted(joined.values(), key=lambda item: (str(item["signal_date"]), str(item["ticker"])))
    rank_pct_by_date(rows, "holder_count", "holder_count_breadth_pct")
    for row in rows:
        row["bucket"] = classify_bucket(row)

    signal_dates = sorted({str(row.get("signal_date")) for row in rows})
    price_lags = [
        int(row["price_lag_days"])
        for row in rows
        if row.get("price_lag_days") is not None
    ]
    metadata = {
        "ownership_source_dir": repo_rel(OWNERSHIP_DIR),
        "ownership_file_count": len(paths),
        "ownership_raw_rows": len(raw_rows),
        "joined_rows": len(rows),
        "duplicate_ticker_signal_rows": duplicate_keys,
        "skipped_small_ownership_files": skipped_small_files,
        "ticker_count": len({str(row.get("ticker")) for row in rows}),
        "signal_date_start": signal_dates[0] if signal_dates else None,
        "signal_date_end": signal_dates[-1] if signal_dates else None,
        "signal_date_count": len(signal_dates),
        "ownership_status_counts": dict(
            sorted(Counter(str(row.get("status") or "missing") for row in raw_rows).items())
        ),
        "bucket_counts": dict(sorted(Counter(str(row.get("bucket")) for row in rows).items())),
        "field_coverage": source_field_coverage(rows),
        "price_lag_days": {
            "n": len(price_lags),
            "mean": round_or_none(mean(price_lags), 4),
            "median": round_or_none(median(price_lags), 4) if price_lags else None,
            "p75": round_or_none(percentile(price_lags, 0.75), 4),
            "max": max(price_lags) if price_lags else None,
        },
        "ownership_source_files": file_summaries,
        "rs_proxy_metadata": rs_metadata,
    }
    return rows, metadata


def classify_bucket(row: dict[str, Any]) -> str:
    breadth = safe_float(row.get("holder_count_breadth_pct"))
    rs20 = safe_float(row.get("rs_proxy_rank_pct_20d"))
    if breadth is None or rs20 is None:
        return "other"
    if breadth <= 0.35 and rs20 >= 0.80:
        return "low_breadth_high_rs"
    if breadth >= 0.80 and rs20 >= 0.80:
        return "crowded_high_rs"
    if breadth <= 0.35 and rs20 <= 0.40:
        return "low_breadth_weak_rs"
    return "other"


def load_hot_prices(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not HOT_WAREHOUSE.exists():
        return {}, {
            "warehouse": repo_rel(HOT_WAREHOUSE),
            "exists": False,
            "immutable_read": False,
            "error": "missing_hot_warehouse",
        }
    requested = sorted({ticker.upper() for ticker in tickers if ticker})
    prices: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    con = sqlite3.connect(immutable_uri(HOT_WAREHOUSE), uri=True)
    try:
        quick = con.execute("pragma quick_check").fetchone()
        warehouse_range = con.execute(
            "select min(date), max(date), count(*), count(distinct ticker) from ohlcv"
        ).fetchone()
        for start in range(0, len(requested), 750):
            chunk = requested[start : start + 750]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, close from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            for ticker, day, open_px, close_px in con.execute(sql, chunk):
                open_f = safe_float(open_px)
                close_f = safe_float(close_px)
                if open_f is None or close_f is None or open_f <= 0 or close_f <= 0:
                    continue
                prices.setdefault(str(ticker).upper(), []).append(
                    {"date": str(day), "open": open_f, "close": close_f}
                )
    finally:
        con.close()

    prices = {ticker: rows for ticker, rows in prices.items() if rows}
    missing = sorted(set(requested) - set(prices))
    date_ranges = {
        ticker: {"start": rows[0]["date"], "end": rows[-1]["date"], "rows": len(rows)}
        for ticker, rows in prices.items()
        if rows
    }
    return prices, {
        "warehouse": repo_rel(HOT_WAREHOUSE),
        "exists": True,
        "immutable_read": True,
        "quick_check": quick[0] if quick else None,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing),
        "missing_requested_ticker_sample": missing[:25],
        "warehouse_min_date": warehouse_range[0] if warehouse_range else None,
        "warehouse_max_date": warehouse_range[1] if warehouse_range else None,
        "warehouse_row_count": warehouse_range[2] if warehouse_range else None,
        "warehouse_ticker_count": warehouse_range[3] if warehouse_range else None,
        "benchmark_ranges": {ticker: date_ranges.get(ticker) for ticker in COMPARATORS},
    }


def net_pnl_from_bars(
    entry_open: float,
    exit_close: float,
    notional: float = PROXY_NOTIONAL_USD,
) -> tuple[float, float, float, float]:
    entry_fill = apply_entry_fill(entry_open, notional=notional)
    exit_fill = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell", notional=notional)
    if entry_fill is None or exit_fill is None or entry_fill <= 0:
        raise ValueError("invalid fill inputs")
    net_return = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = notional * net_return
    return round(entry_fill, 4), round(exit_fill, 4), round(net_return, 8), round(pnl, 2)


def resolve_horizon(
    ticker_rows: list[dict[str, Any]],
    signal_date: str,
    horizon: int,
) -> dict[str, Any]:
    if not ticker_rows:
        return {"status": "missing_ticker_prices"}
    dates = [row["date"] for row in ticker_rows]
    entry_idx = bisect.bisect_right(dates, signal_date)
    if entry_idx >= len(ticker_rows):
        return {"status": "pending_forward_entry"}
    exit_idx = entry_idx + horizon - 1
    if exit_idx >= len(ticker_rows):
        return {
            "status": "pending_forward_exit",
            "entry_date": ticker_rows[entry_idx]["date"],
            "available_forward_sessions": len(ticker_rows) - entry_idx,
        }
    entry = ticker_rows[entry_idx]
    exit_row = ticker_rows[exit_idx]
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except ValueError:
        return {"status": "invalid_price"}
    return {
        "status": "settled",
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry["open"]), 4),
        "exit_close": round(float(exit_row["close"]), 4),
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl": pnl,
    }


def metric_field(comparator: str) -> str:
    return f"replacement_value_{HORIZON}d_vs_{comparator}_usd"


def settle_rows(source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = {str(row.get("ticker")) for row in source_rows} | set(COMPARATORS)
    prices, price_metadata = load_hot_prices(tickers)
    outcomes: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    settled_by_bucket: Counter[str] = Counter()
    settled_by_signal_date: Counter[str] = Counter()

    for row in source_rows:
        ticker = str(row.get("ticker") or "").upper()
        signal_date = str(row.get("signal_date") or "")[:10]
        outcome = resolve_horizon(prices.get(ticker, []), signal_date, HORIZON)
        status = str(outcome.get("status") or "unknown")
        status_counts[status] += 1
        out = dict(row)
        out["forward_10d_status"] = "settled_10d" if status == "settled" else status
        out["planned_entry_date"] = outcome.get("entry_date")
        out["target_price"] = None
        out["target_price_resolution"] = "not_applicable_observed_only_fixed_horizon"
        if status == "settled":
            settled_by_bucket[str(row.get("bucket"))] += 1
            settled_by_signal_date[signal_date] += 1
            out.update(
                {
                    "forward_10d_entry_date": outcome["entry_date"],
                    "forward_10d_exit_date": outcome["exit_date"],
                    "entry_open": outcome["entry_open"],
                    "exit_close": outcome["exit_close"],
                    "entry_fill": outcome["entry_fill"],
                    "exit_fill": outcome["exit_fill"],
                    "forward_10d_net_return": outcome["net_return"],
                    metric_field("cash"): outcome["pnl"],
                }
            )
            for comparator in COMPARATORS:
                comp = resolve_horizon(prices.get(comparator, []), signal_date, HORIZON)
                if comp.get("status") == "settled":
                    out[metric_field(comparator.lower())] = round(
                        float(out[metric_field("cash")]) - float(comp["pnl"]),
                        2,
                    )
        outcomes.append(out)

    settled = [row for row in outcomes if row.get("forward_10d_status") == "settled_10d"]
    return outcomes, {
        "price_metadata": price_metadata,
        "outcome_rows": len(outcomes),
        "settled_rows": len(settled),
        "outcome_status_counts": dict(sorted(status_counts.items())),
        "settled_by_bucket": dict(sorted(settled_by_bucket.items())),
        "settled_by_signal_date": dict(sorted(settled_by_signal_date.items())),
        "settled_signal_date_count": len(settled_by_signal_date),
        "settled_entry_date_range": [
            min((str(row.get("forward_10d_entry_date")) for row in settled), default=None),
            max((str(row.get("forward_10d_entry_date")) for row in settled), default=None),
        ],
        "settled_exit_date_range": [
            min((str(row.get("forward_10d_exit_date")) for row in settled), default=None),
            max((str(row.get("forward_10d_exit_date")) for row in settled), default=None),
        ],
    }


def describe_distribution(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round(mean(clean), 4),
        "median": round(median(clean), 4),
        "p25": round(percentile(clean, 0.25), 4),
        "p75": round(percentile(clean, 0.75), 4),
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None and value > 0:
            by_ticker[str(row.get("ticker"))] += value
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl": 0.0,
            "positive_ticker_count": 0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: pnl / total for ticker, pnl in by_ticker.items()}
    return {
        "positive_pnl": round(total, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 2), "share": round(shares[ticker], 6)}
            for ticker, pnl in by_ticker.most_common(8)
        ],
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if row.get("forward_10d_status") == "settled_10d"]
    price_lags = [
        int(row["price_lag_days"])
        for row in settled
        if row.get("price_lag_days") is not None
    ]
    summary = {
        "n": len(settled),
        "ticker_count": len({str(row.get("ticker")) for row in settled}),
        "signal_date_count": len({str(row.get("signal_date")) for row in settled}),
        "signal_date_start": min((str(row.get("signal_date")) for row in settled), default=None),
        "signal_date_end": max((str(row.get("signal_date")) for row in settled), default=None),
        "entry_date_start": min((str(row.get("forward_10d_entry_date")) for row in settled), default=None),
        "entry_date_end": max((str(row.get("forward_10d_entry_date")) for row in settled), default=None),
        "median_holder_count": round_or_none(
            median([float(row["holder_count"]) for row in settled if row.get("holder_count") is not None]),
            4,
        )
        if settled
        else None,
        "median_holder_breadth_pct": round_or_none(
            median(
                [
                    float(row["holder_count_breadth_pct"])
                    for row in settled
                    if row.get("holder_count_breadth_pct") is not None
                ]
            ),
            4,
        )
        if settled
        else None,
        "median_rs20": round_or_none(
            median(
                [
                    float(row["rs_proxy_rank_pct_20d"])
                    for row in settled
                    if row.get("rs_proxy_rank_pct_20d") is not None
                ]
            ),
            4,
        )
        if settled
        else None,
        "price_lag_days": {
            "n": len(price_lags),
            "mean": round_or_none(mean(price_lags), 4),
            "median": round_or_none(median(price_lags), 4) if price_lags else None,
            "p75": round_or_none(percentile(price_lags, 0.75), 4),
            "max": max(price_lags) if price_lags else None,
        },
        "replacement_metrics": {},
        "cash_positive_concentration": concentration(settled, metric_field("cash")),
        "spy_positive_concentration": concentration(settled, metric_field("spy")),
    }
    for comparator in ("cash", "spy", "qqq"):
        field = metric_field(comparator)
        summary["replacement_metrics"][comparator] = describe_distribution(
            [float(row[field]) for row in settled if safe_float(row.get(field)) is not None]
        )
    return summary


def build_analysis(
    source_rows: list[dict[str, Any]],
    source_metadata: dict[str, Any],
    outcome_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_bucket = {
        bucket: [row for row in outcome_rows if row.get("bucket") == bucket]
        for bucket in BUCKETS
    }
    settled = [row for row in outcome_rows if row.get("forward_10d_status") == "settled_10d"]
    return {
        "source_metadata": source_metadata,
        "sample_settled_rows": [
            {
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date"),
                "bucket": row.get("bucket"),
                "holder_count": row.get("holder_count"),
                "holder_count_breadth_pct": row.get("holder_count_breadth_pct"),
                "rs_proxy_rank_pct_20d": row.get("rs_proxy_rank_pct_20d"),
                "entry_date": row.get("forward_10d_entry_date"),
                "exit_date": row.get("forward_10d_exit_date"),
                "replacement_value_10d_vs_cash_usd": row.get(metric_field("cash")),
                "replacement_value_10d_vs_spy_usd": row.get(metric_field("spy")),
                "replacement_value_10d_vs_qqq_usd": row.get(metric_field("qqq")),
            }
            for row in settled[:20]
        ],
        "settled_summary": {
            "all_settled_summary": summarize_rows(outcome_rows),
            "bucket_summary": {
                bucket: summarize_rows(rows) for bucket, rows in by_bucket.items()
            },
        },
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("forward_10d_status")) for row in outcome_rows).items())
        ),
        "source_rows": len(source_rows),
        "outcome_rows": len(outcome_rows),
        "settled_rows": len(settled),
    }


def value_at(summary: dict[str, Any], bucket: str, comparator: str, stat: str) -> float | None:
    return safe_float(
        summary["bucket_summary"][bucket]["replacement_metrics"][comparator].get(stat)
    )


def metric_text(value: Any) -> str:
    number = safe_float(value)
    return f"{number:.4f}" if number is not None else "unavailable because zero rows settled"


def evaluate_gate4(analysis: dict[str, Any], settlement_metadata: dict[str, Any]) -> dict[str, Any]:
    summary = analysis["settled_summary"]
    bucket = summary["bucket_summary"]
    primary = bucket["low_breadth_high_rs"]
    crowded = bucket["crowded_high_rs"]
    weak = bucket["low_breadth_weak_rs"]
    checks = {
        "strategy_behavior_unchanged": True,
        "hot_warehouse_immutable_read_passed": bool(
            settlement_metadata.get("price_metadata", {}).get("immutable_read")
            and settlement_metadata.get("price_metadata", {}).get("quick_check") == "ok"
        ),
        "primary_sample_min_passed": primary["n"] >= ACCEPTANCE_RULE["min_primary_rows"],
        "crowded_sample_min_passed": crowded["n"] >= ACCEPTANCE_RULE["min_crowded_rows"],
        "weak_sample_min_passed": weak["n"] >= ACCEPTANCE_RULE["min_weak_rows"],
        "settled_signal_dates_min_passed": (
            settlement_metadata.get("settled_signal_date_count", 0)
            >= ACCEPTANCE_RULE["min_settled_signal_dates"]
        ),
        "primary_cash_mean_positive": (
            safe_float(primary["replacement_metrics"]["cash"]["mean"]) or 0.0
        )
        > 0.0,
        "primary_mean_spy_beats_crowded": (
            (value_at(summary, "low_breadth_high_rs", "spy", "mean") or -1e9)
            > (value_at(summary, "crowded_high_rs", "spy", "mean") or 1e9)
        ),
        "primary_mean_qqq_beats_crowded": (
            (value_at(summary, "low_breadth_high_rs", "qqq", "mean") or -1e9)
            > (value_at(summary, "crowded_high_rs", "qqq", "mean") or 1e9)
        ),
        "primary_mean_spy_beats_weak": (
            (value_at(summary, "low_breadth_high_rs", "spy", "mean") or -1e9)
            > (value_at(summary, "low_breadth_weak_rs", "spy", "mean") or 1e9)
        ),
        "primary_mean_qqq_beats_weak": (
            (value_at(summary, "low_breadth_high_rs", "qqq", "mean") or -1e9)
            > (value_at(summary, "low_breadth_weak_rs", "qqq", "mean") or 1e9)
        ),
        "primary_median_spy_beats_crowded": (
            (value_at(summary, "low_breadth_high_rs", "spy", "median") or -1e9)
            > (value_at(summary, "crowded_high_rs", "spy", "median") or 1e9)
        ),
        "primary_median_spy_beats_weak": (
            (value_at(summary, "low_breadth_high_rs", "spy", "median") or -1e9)
            > (value_at(summary, "low_breadth_weak_rs", "spy", "median") or 1e9)
        ),
        "primary_concentration_max_share_passed": (
            (
                safe_float(
                    primary["cash_positive_concentration"].get(
                        "max_single_positive_pnl_share"
                    )
                )
                or 0.0
            )
            <= ACCEPTANCE_RULE["max_primary_single_positive_pnl_share"]
        ),
        "primary_concentration_hhi_passed": (
            (
                safe_float(primary["cash_positive_concentration"].get("positive_pnl_hhi"))
                or 0.0
            )
            <= ACCEPTANCE_RULE["max_primary_positive_pnl_hhi"]
        ),
        "primary_price_lag_guardrail_passed": (
            (safe_float(primary["price_lag_days"].get("median")) or 0.0)
            <= ACCEPTANCE_RULE["max_primary_median_price_lag_days"]
        ),
    }
    failed = [key for key, passed in checks.items() if not passed]
    success = not failed
    decision = (
        "observed_only_positive_kova_sec13f_low_breadth_high_rs_lead"
        if success
        else "observed_only_rejected_no_kova_sec13f_static_ownership_breadth_edge"
    )
    return {
        "decision": decision,
        "observed_only_lead": success,
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
        "lead_limitations": [
            "Forward-only post-snapshot attribution, not canonical fixed-window PIT coverage.",
            "13F disclosures are delayed and can be ownership/crowding context rather than entry timing.",
            "No shared helper, ranker, sizing rule, watchlist, or order behavior was promoted.",
        ],
    }


def calibration(
    prediction: dict[str, Any],
    success: bool,
    failed_reasons: list[str],
) -> dict[str, Any]:
    prob = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1 if success else 0
    return {
        "predicted_success_probability": prob,
        "actual_success": actual,
        "brier_score": round((prob - actual) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes", []),
        "realized_failure_modes": failed_reasons,
        "predicted_failure_mode_hit": any(
            fragment in " ".join(failed_reasons)
            for fragment in ("concentration", "ownership", "sample")
        ),
        "surprise_note": (
            "The fixed Kova SEC13F low-breadth high-RS shape cleared all "
            "observed-only forward checks, but remains only a lead."
            if success
            else "The fixed Kova SEC13F low-breadth high-RS shape did not clear "
            "the preregistered 10d replacement-value, sample, staleness, or "
            "concentration checks."
        ),
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_summary(BASELINE_RESULT)
    source_rows, source_metadata = load_joined_source_rows()
    outcome_rows, settlement_metadata = settle_rows(source_rows)
    analysis = build_analysis(source_rows, source_metadata, outcome_rows)
    gate4 = evaluate_gate4(analysis, settlement_metadata)
    observed_lead = bool(gate4["observed_only_lead"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    primary = analysis["settled_summary"]["bucket_summary"]["low_breadth_high_rs"]
    crowded = analysis["settled_summary"]["bucket_summary"]["crowded_high_rs"]
    weak = analysis["settled_summary"]["bucket_summary"]["low_breadth_weak_rs"]
    why_result = (
        "The low-breadth high-RS bucket produced an interpretable forward lead "
        f"with {primary['n']} settled rows, beating crowded and weak controls on "
        "the preregistered replacement-value checks. This is only a lead because "
        "coverage is current-forward only and no shared helper was promoted."
        if observed_lead
        else (
            "The static SEC13F ownership-breadth interaction did not create a "
            "stable edge beyond RS: low-breadth high-RS settled "
            f"{primary['n']} rows with mean SPY replacement "
            f"{metric_text(primary['replacement_metrics']['spy']['mean'])} versus crowded "
            f"{metric_text(crowded['replacement_metrics']['spy']['mean'])} and weak "
            f"{metric_text(weak['replacement_metrics']['spy']['mean'])}. This keeps 13F "
            "static breadth in attribution/context rather than candidate-pool "
            "selection."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": gate4["decision"],
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
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed without override. Nearest neighbors were "
                    "SEC13F sponsorship/active-flow attribution, but below the "
                    "blocking threshold; source saturation did not apply because "
                    "gate_shape=other."
                ),
                "exp-20260615-009": "Prior 13F low-crowding sponsorship leadership failed; this run uses newer current-forward rows and remains observed-only.",
                "exp-20260702-015": "Historical active-manager 13F flow candidate source failed Gate 4; this run tests static breadth context only.",
                "exp-20260704-011": "Kova RS proxy acceleration was rejected; this run asks whether 13F breadth adds separation beyond high RS.",
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: join current Kova SEC13F "
                "ownership breadth to same-date Kova RS proxy, bucket low-breadth "
                "high-RS versus crowded high-RS and weak controls, and settle 10d "
                "cash/SPY/QQQ replacement value without changing executable policy."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if sample floors pass, low-breadth high-RS "
                "beats crowded high-RS and low-breadth weak-RS on SPY/QQQ mean and "
                "SPY median checks, cash mean is positive, price-lag and concentration "
                "guards pass, immutable warehouse read passes, and strategy behavior "
                "remains unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "ownership_source_dir": repo_rel(OWNERSHIP_DIR),
            "rs_proxy_source_dir": repo_rel(RS_PROXY_DIR),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizon": HORIZON,
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_fill": "next available hot-warehouse session open with buy-side slippage",
            "exit_fill": "10th forward session close with target-side sell slippage",
            "comparators": list(COMPARATORS),
            "bucket_definitions": {
                "low_breadth_high_rs": ACCEPTANCE_RULE["low_breadth_high_rs"],
                "crowded_high_rs": ACCEPTANCE_RULE["crowded_high_rs"],
                "low_breadth_weak_rs": ACCEPTANCE_RULE["low_breadth_weak_rs"],
            },
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(source_rows)
            and source_metadata["field_coverage"]["ticker"]["coverage"] == 1.0
            and source_metadata["field_coverage"]["holder_count"]["coverage"] == 1.0,
            "fields_checked": REQUIRED_SOURCE_FIELDS
            + [
                "entry_date",
                "planned_entry_date",
                "target_price",
                "forward_10d_status",
                "forward_10d_entry_date",
                "forward_10d_exit_date",
                "replacement_value_10d_vs_cash_usd",
                "replacement_value_10d_vs_spy_usd",
                "replacement_value_10d_vs_qqq_usd",
            ],
            "source_field_coverage": source_metadata["field_coverage"],
            "settled_entry_date_rows": settlement_metadata["settled_rows"],
            "target_price_scope": (
                "Not applicable: observed-only fixed-horizon attribution does not "
                "schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_metadata["joined_rows"],
            "signals_survived": settlement_metadata["settled_rows"],
            "survival_rate": round(
                settlement_metadata["settled_rows"] / source_metadata["joined_rows"],
                6,
            )
            if source_metadata["joined_rows"]
            else None,
            "baseline_survival_rate": baseline["aggregate_survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            **gate4,
            "why": (
                "The fixed Kova SEC13F static breadth + RS shape cleared all "
                "observed-only replacement-value checks. It remains a forward "
                "lead only and needs canonical PIT helper work before promotion."
                if observed_lead
                else "The fixed Kova SEC13F static breadth + RS shape failed at "
                "least one preregistered replacement-value, sample, staleness, "
                "or concentration check. Do not promote or retune this shape "
                "without materially new evidence."
            ),
            "baseline_after_identity": True,
            "baseline_expected_value_score": baseline["aggregate_expected_value_score"],
            "after_expected_value_score": baseline["aggregate_expected_value_score"],
            "expected_value_score_delta": 0.0,
            "baseline_total_pnl": baseline["aggregate_total_pnl"],
            "after_total_pnl": baseline["aggregate_total_pnl"],
            "total_pnl_delta": 0.0,
        },
        "analysis": analysis,
        "settlement_metadata": settlement_metadata,
        "production_impact": PRODUCTION_IMPACT,
        "calibration": calibration(prediction, observed_lead, gate4["failed_reasons"]),
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact_file": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "post_run_reflection": {
            "why_result_happened": why_result,
            "forbidden_near_neighbor_retry": (
                "Do not rerun Kova SEC13F static ownership breadth by only "
                "changing holder-count percentile cuts, RS percentile cuts, "
                "hard buckets into weights, the 10d horizon, top-N, notional, "
                "or response curves on these same current rows."
            ),
            "new_evidence_required": (
                "Reopen only with materially more newly settled Kova SEC13F "
                "forward rows across later market windows, materially richer "
                "PIT manager/flow provenance, non-quarterly ownership/flow data, "
                "borrow/options cross-evidence, or canonical fixed-window PIT "
                "coverage through a shared helper."
            ),
            "anti_repeat": (
                "13F static breadth remains context unless it clears forward "
                "replacement-value separation and then reproduces in canonical "
                "PIT helper form; do not retune the same current-row cuts."
            ),
            "next_step": (
                "If positive, the next valid step is a shared default-off helper "
                "with canonical Gate 1-4 and accepted-comparator checks. If "
                "rejected, park static 13F breadth until new forward rows or "
                "richer ownership provenance arrives."
            ),
        },
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "analysis",
        "settlement_metadata",
        "production_impact",
        "calibration",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact_file",
        "log_file",
        "card_file",
        "revision_manifest_file",
        "post_run_reflection",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def table_row(name: str, summary: dict[str, Any]) -> str:
    metrics = summary["replacement_metrics"]
    return (
        f"| `{name}` | {summary['n']} | {summary['ticker_count']} | "
        f"{metrics['cash']['mean']} | {metrics['spy']['mean']} | "
        f"{metrics['qqq']['mean']} | {metrics['spy']['median']} |"
    )


def build_card(payload: dict[str, Any]) -> str:
    bucket = payload["analysis"]["settled_summary"]["bucket_summary"]
    checks = payload["gate4"]["failed_reasons"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F static ownership breadth forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Hypothesis: {HYPOTHESIS}",
            f"- Runner: `{RUNNER_COMMAND}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 10d Forward Results",
            "",
            "| Bucket | Rows | Tickers | Mean vs cash | Mean vs SPY | Mean vs QQQ | Median vs SPY |",
            "|---|---:|---:|---:|---:|---:|---:|",
            table_row("low_breadth_high_rs", bucket["low_breadth_high_rs"]),
            table_row("crowded_high_rs", bucket["crowded_high_rs"]),
            table_row("low_breadth_weak_rs", bucket["low_breadth_weak_rs"]),
            "",
            "## Gate 4",
            "",
            f"- Failed checks: {', '.join(checks) if checks else 'none'}",
            f"- Strategy EV delta: `{payload['gate4']['expected_value_score_delta']}`",
            "- Production impact: no ranking, sizing, exits, paper orders, live orders, watchlist, shared helper, or LLM decision boundary changed.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": utc_now(),
        "status": payload["status"],
        "decision": payload["decision"],
        "files": [
            {"path": repo_rel(path), "exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
    }


def persist_payload(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log_record(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "decision": payload["decision"],
            "status": payload["status"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
            "strategy_delta": payload["gate4"]["before_after_strategy_delta"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> None:
    payload = build_payload()
    persist_payload(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
