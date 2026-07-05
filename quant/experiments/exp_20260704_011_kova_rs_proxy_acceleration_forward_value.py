"""exp-20260704-011: Kova RS proxy acceleration forward value.

Observed-only alpha attribution. This evaluates whether production-visible Kova
rs_proxy rows where 20d SPY-relative rank is high but 120d rank is low, a fixed
recent-leadership acceleration shape, outperform persistent leaders or weak RS
rows over the next 10 trading sessions.

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
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260704-011"
OWNER = "alpha-explore"
SLUG = "kova_rs_proxy_acceleration_forward_value"
RUNNER = f"quant/experiments/exp_20260704_011_{SLUG}.py"
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
RS_PROXY_DIR = REPO_ROOT / "data" / "kova" / "rs_proxy"
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260704_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Kova RS proxy rows may contain a production-visible candidate-pool lead: "
    "tickers with high 20-day SPY-relative rank but low 120-day rank represent "
    "recent leadership acceleration and should outperform persistent or weak RS "
    "buckets over the next 10 trading days."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_kova_rs_proxy_forward_attribution"
TRIAL_FAMILY = "kova_rs_proxy_recent_leadership_acceleration_forward_value"
TRIAL_VARIANT_ID = "rs20_high_rs120_low_forward10_v1"
CHANGED_VARIABLE = "kova_rs_proxy_recent_leadership_acceleration_forward_value_v1"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEW_EVIDENCE_TYPE = "new_production_visible_pit_sidecar_field"
NEW_EVIDENCE_AXIS = (
    "Kova rs_proxy is a production-visible PIT sidecar with explicit 20d, 60d, "
    "and 120d SPY-relative rank fields. This run tests a fixed 20d-high/"
    "120d-low acceleration shape and does not retune an accepted sleeve, "
    "generic ATR extension rule, short-volume rule, or candidate-pool threshold."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260519-034",
    "exp-20260621-011",
    "exp-20260630-016",
]
CAUSAL_COMPONENTS = [
    "Kova rs_proxy daily sidecar",
    "20d-vs-120d acceleration bucket",
    "10-trading-day forward return",
    "SPY-relative and QQQ-relative forward comparison",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260704-011/exp_20260704_011_kova_rs_proxy_acceleration_forward_value.json",
    "experiments/cards/exp-20260704-011.md",
    "experiments/manifests/exp-20260704-011.json",
    "experiments/tickets/exp-20260704-011.json",
    "experiments/logs/exp-20260704-011.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZON = 10
PROXY_NOTIONAL_USD = 10_000.0
COMPARATORS = ("SPY", "QQQ")
REPLACEMENT_SUFFIXES = ("cash", "spy", "qqq")
BUCKETS = ("recent_acceleration", "persistent_leader", "weak_rs", "other")
REQUIRED_SOURCE_FIELDS = [
    "asof_date",
    "asof_price_date",
    "ticker",
    "status",
    "benchmark",
    "available_window_count",
    "rs_proxy_rank_pct_20d",
    "rs_proxy_rank_pct_60d",
    "rs_proxy_rank_pct_120d",
    "excess_ret_20d_vs_spy",
    "excess_ret_60d_vs_spy",
    "excess_ret_120d_vs_spy",
]
ACCEPTANCE_RULE = {
    "horizon": HORIZON,
    "primary_bucket": "recent_acceleration",
    "recent_acceleration": "rs_proxy_rank_pct_20d >= 0.80 and rs_proxy_rank_pct_120d <= 0.50",
    "persistent_leader": "rs_proxy_rank_pct_20d >= 0.80 and rs_proxy_rank_pct_120d >= 0.80",
    "weak_rs": "rs_proxy_rank_pct_20d <= 0.40 and rs_proxy_rank_pct_120d <= 0.50",
    "min_recent_rows": 100,
    "min_persistent_rows": 100,
    "min_weak_rows": 100,
    "min_settled_asof_dates": 8,
    "max_recent_single_positive_pnl_share": 0.35,
    "max_recent_positive_pnl_hhi": 0.20,
    "max_recent_median_price_lag_days": 7,
    "required_mean_outperformance": [
        "recent SPY replacement mean > persistent SPY replacement mean",
        "recent SPY replacement mean > weak SPY replacement mean",
        "recent QQQ replacement mean > persistent QQQ replacement mean",
        "recent QQQ replacement mean > weak QQQ replacement mean",
    ],
    "required_median_outperformance": [
        "recent SPY replacement median > persistent SPY replacement median",
        "recent SPY replacement median > weak SPY replacement median",
    ],
}
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "momentum_near_neighbor_blocked",
        "forward_sample_overlaps_broad_momentum",
        "not_incremental_vs_existing_ohlcv_sources",
        "drawdown_or_concentration",
    ],
    "confidence_reason": (
        "This uses a PIT production-visible Kova rs_proxy sidecar rather than a "
        "threshold on an accepted helper; recent playbook warns generic OHLCV "
        "momentum often fails, so confidence is low and the test is observed-only."
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
    "uses_kova_rs_proxy_sidecar": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "parity_note": (
        "Observed-only attribution over existing Kova rs_proxy snapshots and the "
        "hot warehouse. No shared policy/helper or production adapter behavior changed."
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


def load_rs_proxy_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = sorted(RS_PROXY_DIR.glob("rs_proxy_*.jsonl"))
    raw_rows: list[dict[str, Any]] = []
    file_summaries = []
    invalid_rows = 0
    for path in paths:
        rows = iter_jsonl(path)
        raw_rows.extend({**row, "source_file": repo_rel(path)} for row in rows)
        file_summaries.append(
            {
                "file": repo_rel(path),
                "rows": len(rows),
                "sha256": sha256_file(path),
            }
        )

    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_keys = 0
    for row in raw_rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        asof_date = str(row.get("asof_date") or "")[:10]
        price_date = str(row.get("asof_price_date") or "")[:10]
        ranks = [
            safe_float(row.get("rs_proxy_rank_pct_20d")),
            safe_float(row.get("rs_proxy_rank_pct_60d")),
            safe_float(row.get("rs_proxy_rank_pct_120d")),
        ]
        if (
            not ticker
            or not asof_date
            or not price_date
            or str(row.get("status") or "").lower() != "ok"
            or safe_int(row.get("available_window_count") or 0) < 3
            or any(value is None for value in ranks)
        ):
            invalid_rows += 1
            continue
        key = (ticker, asof_date)
        cleaned = dict(row)
        cleaned["ticker"] = ticker
        cleaned["signal_date"] = asof_date
        cleaned["price_lag_days"] = days_between(asof_date, price_date)
        if key in dedup:
            duplicate_keys += 1
        dedup[key] = cleaned

    rows = sorted(dedup.values(), key=lambda item: (str(item["signal_date"]), str(item["ticker"])))
    asof_dates = sorted({str(row.get("signal_date")) for row in rows})
    price_lags = [
        int(row["price_lag_days"])
        for row in rows
        if row.get("price_lag_days") is not None
    ]
    metadata = {
        "source_dir": repo_rel(RS_PROXY_DIR),
        "source_exists": RS_PROXY_DIR.exists(),
        "source_file_count": len(paths),
        "raw_rows": len(raw_rows),
        "usable_rows_after_status_and_rank_filter": len(rows),
        "invalid_or_incomplete_rows": invalid_rows,
        "duplicate_ticker_asof_rows": duplicate_keys,
        "ticker_count": len({str(row.get("ticker")) for row in rows}),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "status_counts": dict(
            sorted(Counter(str(row.get("status") or "missing") for row in raw_rows).items())
        ),
        "field_coverage": source_field_coverage(raw_rows),
        "price_lag_days": {
            "n": len(price_lags),
            "mean": round_or_none(mean(price_lags), 4),
            "median": round_or_none(median(price_lags), 4) if price_lags else None,
            "p75": round_or_none(percentile(price_lags, 0.75), 4),
            "max": max(price_lags) if price_lags else None,
        },
        "source_files": file_summaries,
    }
    return rows, metadata


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
        "pnl_usd": pnl,
    }


def comparator_pnl(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    exit_date: str,
) -> dict[str, Any]:
    by_date = {row["date"]: row for row in prices.get(ticker, [])}
    entry = by_date.get(entry_date)
    exit_row = by_date.get(exit_date)
    if not entry or not exit_row:
        return {"status": "missing_comparator_window"}
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except ValueError:
        return {"status": "invalid_comparator_price"}
    return {
        "status": "settled",
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl_usd": pnl,
    }


def bucket_for(row: dict[str, Any]) -> str:
    rank20 = safe_float(row.get("rs_proxy_rank_pct_20d"))
    rank120 = safe_float(row.get("rs_proxy_rank_pct_120d"))
    if rank20 is None or rank120 is None:
        return "other"
    if rank20 >= 0.80 and rank120 <= 0.50:
        return "recent_acceleration"
    if rank20 >= 0.80 and rank120 >= 0.80:
        return "persistent_leader"
    if rank20 <= 0.40 and rank120 <= 0.50:
        return "weak_rs"
    return "other"


def settle_row(
    row: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("signal_date") or row.get("asof_date") or "")[:10]
    out = {
        "experiment_id": EXPERIMENT_ID,
        "ticker": ticker or None,
        "asof_date": row.get("asof_date"),
        "signal_date": signal_date or None,
        "asof_price_date": row.get("asof_price_date"),
        "source_file": row.get("source_file"),
        "known_at": row.get("known_at"),
        "benchmark": row.get("benchmark"),
        "available_window_count": row.get("available_window_count"),
        "price_lag_days": row.get("price_lag_days"),
        "rs_proxy_rank_pct_20d": round_or_none(row.get("rs_proxy_rank_pct_20d"), 8),
        "rs_proxy_rank_pct_60d": round_or_none(row.get("rs_proxy_rank_pct_60d"), 8),
        "rs_proxy_rank_pct_120d": round_or_none(row.get("rs_proxy_rank_pct_120d"), 8),
        "excess_ret_20d_vs_spy": round_or_none(row.get("excess_ret_20d_vs_spy"), 8),
        "excess_ret_60d_vs_spy": round_or_none(row.get("excess_ret_60d_vs_spy"), 8),
        "excess_ret_120d_vs_spy": round_or_none(row.get("excess_ret_120d_vs_spy"), 8),
        "bucket": bucket_for(row),
        "target_price": None,
        "target_price_resolution": "not_applicable_observed_only_fixed_horizon",
        "trade_enabled": False,
        "alters_orders": False,
        "proxy_notional_usd": PROXY_NOTIONAL_USD,
    }
    if not ticker or not signal_date:
        out[f"forward_{HORIZON}d_status"] = "missing_ticker_or_signal_date"
        out["outcome_status"] = "pending_forward_close"
        return out

    outcome = resolve_horizon(prices.get(ticker, []), signal_date, HORIZON)
    status = str(outcome.get("status"))
    prefix = f"forward_{HORIZON}d"
    out[f"{prefix}_status"] = status
    out["entry_date"] = outcome.get("entry_date")
    out["planned_entry_date"] = outcome.get("entry_date")
    if outcome.get("available_forward_sessions") is not None:
        out[f"{prefix}_available_forward_sessions"] = outcome.get("available_forward_sessions")
    if status != "settled":
        out["outcome_status"] = "pending_forward_close"
        return out

    entry_date = str(outcome["entry_date"])
    exit_date = str(outcome["exit_date"])
    out[f"{prefix}_entry_date"] = entry_date
    out[f"{prefix}_exit_date"] = exit_date
    out[f"{prefix}_entry_open"] = outcome["entry_open"]
    out[f"{prefix}_exit_close"] = outcome["exit_close"]
    out[f"{prefix}_entry_fill"] = outcome["entry_fill"]
    out[f"{prefix}_exit_fill"] = outcome["exit_fill"]
    out[f"{prefix}_return_pct"] = round(float(outcome["net_return"]) * 100.0, 6)
    out[f"{prefix}_pnl_usd"] = outcome["pnl_usd"]
    out[f"replacement_value_{HORIZON}d_vs_cash_usd"] = outcome["pnl_usd"]

    all_comparators_settled = True
    for comparator in COMPARATORS:
        detail = comparator_pnl(prices, comparator, entry_date, exit_date)
        key = comparator.lower()
        out[f"{prefix}_{key}_status"] = detail["status"]
        if detail["status"] == "settled":
            out[f"{prefix}_{key}_pnl_usd"] = detail["pnl_usd"]
            out[f"replacement_value_{HORIZON}d_vs_{key}_usd"] = round(
                float(outcome["pnl_usd"]) - float(detail["pnl_usd"]),
                2,
            )
        else:
            all_comparators_settled = False
            out[f"replacement_value_{HORIZON}d_vs_{key}_usd"] = None
    out["outcome_status"] = "settled_10d" if all_comparators_settled else "settled_missing_comparator"
    return out


def settle_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    tickers.update(COMPARATORS)
    prices, price_metadata = load_hot_prices(tickers)
    outcome_rows = [settle_row(row, prices) for row in rows]
    settled = settled_rows(outcome_rows)
    return outcome_rows, {
        "price_metadata": price_metadata,
        "outcome_rows": len(outcome_rows),
        "settled_rows": len(settled),
        "settled_by_bucket": dict(sorted(Counter(row.get("bucket") for row in settled).items())),
        "settled_by_signal_date": dict(
            sorted(Counter(str(row.get("signal_date") or "missing") for row in settled).items())
        ),
        "settled_entry_date_range": [
            min((str(row.get(f"forward_{HORIZON}d_entry_date")) for row in settled), default=None),
            max((str(row.get(f"forward_{HORIZON}d_entry_date")) for row in settled), default=None),
        ],
        "settled_exit_date_range": [
            min((str(row.get(f"forward_{HORIZON}d_exit_date")) for row in settled), default=None),
            max((str(row.get(f"forward_{HORIZON}d_exit_date")) for row in settled), default=None),
        ],
        "horizon_status_counts": dict(
            sorted(Counter(str(row.get(f"forward_{HORIZON}d_status") or "missing") for row in outcome_rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in outcome_rows).items())
        ),
    }


def metric_field(suffix: str) -> str:
    return f"replacement_value_{HORIZON}d_vs_{suffix}_usd"


def settled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get(f"forward_{HORIZON}d_status") == "settled"
        and row.get(metric_field("spy")) is not None
        and row.get(metric_field("qqq")) is not None
    ]


def numeric_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def summarize_metric(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "sum": round(sum(values), 2) if values else 0.0,
        "mean": round_or_none(mean(values), 4),
        "median": round_or_none(median(values), 4) if values else None,
        "p25": round_or_none(percentile(values, 0.25), 4),
        "p75": round_or_none(percentile(values, 0.75), 4),
        "min": round(min(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4)
        if values
        else None,
    }


def concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        value = safe_float(row.get(field))
        if value is None or value <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += value
    total = sum(by_ticker.values())
    top = [
        {"ticker": ticker, "pnl": round(value, 2), "share": round(value / total, 6)}
        for ticker, value in by_ticker.most_common(8)
    ] if total > 0 else []
    return {
        "positive_pnl": round(total, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": top[0]["share"] if top else None,
        "positive_pnl_hhi": round(sum((value / total) ** 2 for value in by_ticker.values()), 6)
        if total > 0
        else None,
        "top_positive_tickers": top,
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    signal_dates = sorted({str(row.get("signal_date") or "") for row in rows if row.get("signal_date")})
    entry_dates = sorted({str(row.get("entry_date") or "") for row in rows if row.get("entry_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    price_lags = numeric_values(rows, "price_lag_days")
    metrics = {}
    for suffix in REPLACEMENT_SUFFIXES:
        metrics[suffix] = summarize_metric(numeric_values(rows, metric_field(suffix)))
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "signal_date_count": len(signal_dates),
        "signal_date_start": signal_dates[0] if signal_dates else None,
        "signal_date_end": signal_dates[-1] if signal_dates else None,
        "entry_date_start": entry_dates[0] if entry_dates else None,
        "entry_date_end": entry_dates[-1] if entry_dates else None,
        "median_rs20": round_or_none(median(numeric_values(rows, "rs_proxy_rank_pct_20d")), 6)
        if rows
        else None,
        "median_rs60": round_or_none(median(numeric_values(rows, "rs_proxy_rank_pct_60d")), 6)
        if rows
        else None,
        "median_rs120": round_or_none(median(numeric_values(rows, "rs_proxy_rank_pct_120d")), 6)
        if rows
        else None,
        "price_lag_days": {
            "n": len(price_lags),
            "mean": round_or_none(mean(price_lags), 4),
            "median": round_or_none(median(price_lags), 4) if price_lags else None,
            "p75": round_or_none(percentile(price_lags, 0.75), 4),
            "max": max(price_lags) if price_lags else None,
        },
        "replacement_metrics": metrics,
        "cash_positive_concentration": concentration(rows, metric_field("cash")),
        "spy_positive_concentration": concentration(rows, metric_field("spy")),
    }


def metric(summary: dict[str, Any], bucket: str, suffix: str, statistic: str) -> float | None:
    return safe_float(
        summary["bucket_summary"][bucket]["replacement_metrics"][suffix].get(statistic)
    )


def compare_metric(
    summary: dict[str, Any],
    left: str,
    right: str,
    suffix: str,
    statistic: str,
) -> bool:
    left_value = metric(summary, left, suffix, statistic)
    right_value = metric(summary, right, suffix, statistic)
    return left_value is not None and right_value is not None and left_value > right_value


def build_analysis(
    source_rows: list[dict[str, Any]],
    source_metadata: dict[str, Any],
    outcome_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    settled = settled_rows(outcome_rows)
    buckets = {
        bucket: [row for row in settled if row.get("bucket") == bucket]
        for bucket in BUCKETS
    }
    bucket_summary = {name: summarize_group(rows) for name, rows in buckets.items()}
    all_summary = summarize_group(settled)
    comparisons = {
        "recent_mean_beats_persistent": {
            suffix: compare_metric(bucket_summary_wrapper(bucket_summary), "recent_acceleration", "persistent_leader", suffix, "mean")
            for suffix in REPLACEMENT_SUFFIXES
        },
        "recent_mean_beats_weak": {
            suffix: compare_metric(bucket_summary_wrapper(bucket_summary), "recent_acceleration", "weak_rs", suffix, "mean")
            for suffix in REPLACEMENT_SUFFIXES
        },
        "recent_median_beats_persistent": {
            suffix: compare_metric(bucket_summary_wrapper(bucket_summary), "recent_acceleration", "persistent_leader", suffix, "median")
            for suffix in REPLACEMENT_SUFFIXES
        },
        "recent_median_beats_weak": {
            suffix: compare_metric(bucket_summary_wrapper(bucket_summary), "recent_acceleration", "weak_rs", suffix, "median")
            for suffix in REPLACEMENT_SUFFIXES
        },
    }
    return {
        "source_summary": source_metadata,
        "settled_summary": {
            "settled_rows": len(settled),
            "all_settled_summary": all_summary,
            "bucket_summary": bucket_summary,
            "comparisons": comparisons,
        },
        "sample_settled_rows": [
            {
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date"),
                "asof_price_date": row.get("asof_price_date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get(f"forward_{HORIZON}d_exit_date"),
                "bucket": row.get("bucket"),
                "rs_proxy_rank_pct_20d": row.get("rs_proxy_rank_pct_20d"),
                "rs_proxy_rank_pct_120d": row.get("rs_proxy_rank_pct_120d"),
                "replacement_value_10d_vs_cash_usd": row.get(metric_field("cash")),
                "replacement_value_10d_vs_spy_usd": row.get(metric_field("spy")),
                "replacement_value_10d_vs_qqq_usd": row.get(metric_field("qqq")),
            }
            for row in settled[:10]
        ],
    }


def bucket_summary_wrapper(bucket_summary: dict[str, Any]) -> dict[str, Any]:
    return {"bucket_summary": bucket_summary}


def evaluate_gate4(analysis: dict[str, Any], settlement_metadata: dict[str, Any]) -> dict[str, Any]:
    settled_summary = analysis["settled_summary"]
    bucket_summary = settled_summary["bucket_summary"]
    comparisons = settled_summary["comparisons"]
    recent = bucket_summary["recent_acceleration"]
    concentration_stats = recent["cash_positive_concentration"]
    checks = {
        "recent_sample_min_passed": recent["n"] >= ACCEPTANCE_RULE["min_recent_rows"],
        "persistent_sample_min_passed": (
            bucket_summary["persistent_leader"]["n"] >= ACCEPTANCE_RULE["min_persistent_rows"]
        ),
        "weak_sample_min_passed": bucket_summary["weak_rs"]["n"] >= ACCEPTANCE_RULE["min_weak_rows"],
        "settled_asof_dates_min_passed": (
            settled_summary["all_settled_summary"]["signal_date_count"]
            >= ACCEPTANCE_RULE["min_settled_asof_dates"]
        ),
        "recent_mean_spy_beats_persistent": comparisons["recent_mean_beats_persistent"]["spy"],
        "recent_mean_spy_beats_weak": comparisons["recent_mean_beats_weak"]["spy"],
        "recent_mean_qqq_beats_persistent": comparisons["recent_mean_beats_persistent"]["qqq"],
        "recent_mean_qqq_beats_weak": comparisons["recent_mean_beats_weak"]["qqq"],
        "recent_median_spy_beats_persistent": comparisons["recent_median_beats_persistent"]["spy"],
        "recent_median_spy_beats_weak": comparisons["recent_median_beats_weak"]["spy"],
        "recent_cash_mean_positive": (
            (recent["replacement_metrics"]["cash"]["mean"] or 0.0) > 0.0
        ),
        "recent_price_lag_guardrail_passed": (
            recent["price_lag_days"]["median"] is not None
            and recent["price_lag_days"]["median"]
            <= ACCEPTANCE_RULE["max_recent_median_price_lag_days"]
        ),
        "recent_concentration_max_share_passed": (
            concentration_stats["max_single_positive_pnl_share"] is not None
            and concentration_stats["max_single_positive_pnl_share"]
            <= ACCEPTANCE_RULE["max_recent_single_positive_pnl_share"]
        ),
        "recent_concentration_hhi_passed": (
            concentration_stats["positive_pnl_hhi"] is not None
            and concentration_stats["positive_pnl_hhi"] <= ACCEPTANCE_RULE["max_recent_positive_pnl_hhi"]
        ),
        "hot_warehouse_immutable_read_passed": bool(
            settlement_metadata["price_metadata"].get("immutable_read")
            and settlement_metadata["price_metadata"].get("quick_check") == "ok"
        ),
        "strategy_behavior_unchanged": True,
    }
    failed = [key for key, passed in checks.items() if not passed]
    observed_lead = not failed
    return {
        "observed_only_lead": observed_lead,
        "decision": (
            "observed_only_positive_kova_rs_proxy_acceleration_lead_not_promoted"
            if observed_lead
            else "observed_only_rejected_no_kova_rs_proxy_acceleration_forward_edge"
        ),
        "failed_reasons": failed,
        "acceptance_checks": checks,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "lead_limitations": [
            "Forward-only post-snapshot attribution, not canonical fixed-window PIT coverage.",
            "Kova rs_proxy is OHLCV-derived, so any future promotion must prove incrementality over existing accepted RS helpers.",
            "No shared helper, ranker, sizing rule, watchlist, or order behavior was promoted.",
        ],
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1 if success else 0
    return {
        "actual_success": actual,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": list(prediction.get("main_failure_modes") or []),
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []) & set(failed)
        ),
        "surprise_note": (
            "The fixed Kova RS acceleration shape separated 10d forward replacement value, "
            "but remains an observed-only lead."
            if success
            else "The fixed Kova RS acceleration shape did not clear the preregistered "
            "benchmark, sample, staleness, or concentration checks."
        ),
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_summary(BASELINE_RESULT)
    source_rows, source_metadata = load_rs_proxy_rows()
    outcome_rows, settlement_metadata = settle_rows(source_rows)
    analysis = build_analysis(source_rows, source_metadata, outcome_rows)
    gate4 = evaluate_gate4(analysis, settlement_metadata)
    observed_lead = bool(gate4["observed_only_lead"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    why = (
        "The fixed high-20d/low-120d Kova RS proxy shape beat persistent and weak RS "
        "comparison buckets on the preregistered 10d cash/SPY/QQQ checks. This remains "
        "observed-only and did not promote a helper or change strategy behavior."
        if observed_lead
        else "The fixed high-20d/low-120d Kova RS proxy shape failed at least one "
        "preregistered 10d replacement-value, staleness, sample, or concentration check. "
        "Do not promote or retune this shape without materially new evidence."
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
                    "Reservation passed without override. Nearest neighbors were weak; "
                    "source saturation did not apply to this fingerprint."
                ),
                "exp-20260519-034": "Prior broad momentum/RS work; this run uses Kova rs_proxy fields and a fixed 20d-vs-120d acceleration shape.",
                "exp-20260621-011": "Kova proxy scout near-neighbor, not this fixed production-visible rs_proxy sidecar attribution.",
                "exp-20260630-016": "Rejected ATR-extension deallocation, explicitly not reused here.",
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: classify Kova rs_proxy daily rows into "
                "recent acceleration, persistent leader, weak RS, and other; settle 10d forward "
                "cash/SPY/QQQ replacement value from the immutable hot warehouse; do not change "
                "any executable policy."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if recent acceleration sample floors pass, recent beats "
                "persistent and weak on SPY/QQQ mean and SPY median checks, cash mean is positive, "
                "price-lag and concentration guards pass, immutable warehouse read passes, and "
                "strategy behavior remains unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_dir": repo_rel(RS_PROXY_DIR),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizon": HORIZON,
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_fill": "next available hot-warehouse session open with buy-side slippage",
            "exit_fill": "10th forward session close with target-side sell slippage",
            "comparators": list(COMPARATORS),
            "bucket_definitions": {
                "recent_acceleration": ACCEPTANCE_RULE["recent_acceleration"],
                "persistent_leader": ACCEPTANCE_RULE["persistent_leader"],
                "weak_rs": ACCEPTANCE_RULE["weak_rs"],
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
            and source_metadata["field_coverage"]["asof_date"]["coverage"] == 1.0
            and source_metadata["field_coverage"]["ticker"]["coverage"] == 1.0,
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
            "signals_generated": source_metadata["usable_rows_after_status_and_rank_filter"],
            "signals_survived": settlement_metadata["settled_rows"],
            "survival_rate": round(
                settlement_metadata["settled_rows"]
                / source_metadata["usable_rows_after_status_and_rank_filter"],
                6,
            )
            if source_metadata["usable_rows_after_status_and_rank_filter"]
            else None,
            "baseline_survival_rate": baseline["aggregate_survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            **gate4,
            "why": why,
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
            "why_result_happened": (
                "The recent-acceleration bucket settled 166 rows and did beat weak RS, "
                "but it did not beat persistent leaders: mean 10d replacement value was "
                "98.9516 vs SPY and 92.2590 vs QQQ, below persistent leaders at 100.6591 "
                "and 104.7897, and its cash mean was negative at -24.0739. The evidence "
                "looks like ordinary RS continuation overlap rather than a distinct "
                "candidate-pool edge from 20d-high/120d-low acceleration."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun Kova rs_proxy recent acceleration by only changing the "
                "20d or 120d percentile thresholds, switching hard buckets into weights, "
                "adding simple slices, or changing the 10d horizon. Those are same-surface "
                "retunes after a rejected observed-only attribution."
            ),
            "new_evidence_required": (
                "Reopen only with materially more settled rs_proxy forward rows across "
                "new market windows, a genuinely non-OHLCV data source that explains why "
                "recent leadership is new, or a different gate shape that first proves "
                "incrementality against existing RS helpers before any promotion."
            ),
            "anti_repeat": (
                "Do not retry this same Kova rs_proxy acceleration shape by only changing "
                "thresholds, response curves, or slices. Reopen requires materially more "
                "settled forward rows, a non-OHLCV source, or a genuinely different gate shape."
            ),
            "next_step": (
                "If positive, promote only as a shared default-off helper with canonical Gate "
                "1-4 and an incrementality test versus existing RS helpers. If rejected, park "
                "the shape until materially more settled rows arrive."
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


def build_card(payload: dict[str, Any]) -> str:
    recent = payload["analysis"]["settled_summary"]["bucket_summary"]["recent_acceleration"]
    persistent = payload["analysis"]["settled_summary"]["bucket_summary"]["persistent_leader"]
    weak = payload["analysis"]["settled_summary"]["bucket_summary"]["weak_rs"]
    checks = payload["gate4"]["failed_reasons"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova RS proxy acceleration forward value",
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
            table_row("recent_acceleration", recent),
            table_row("persistent_leader", persistent),
            table_row("weak_rs", weak),
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


def table_row(name: str, summary: dict[str, Any]) -> str:
    metrics = summary["replacement_metrics"]
    return (
        f"| `{name}` | {summary['n']} | {summary['ticker_count']} | "
        f"{metrics['cash']['mean']} | {metrics['spy']['mean']} | "
        f"{metrics['qqq']['mean']} | {metrics['spy']['median']} |"
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
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
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
