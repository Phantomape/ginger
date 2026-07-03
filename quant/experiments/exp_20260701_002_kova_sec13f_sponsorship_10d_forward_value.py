"""exp-20260701-002: Kova SEC13F sponsorship 10d forward value.

Observed-only alpha attribution. This run reopens the parked Kova SEC13F
sponsorship surface only because the hot warehouse now closes 10d replacement
rows that were unavailable in exp-20260628-002. It keeps the sponsorship score
fixed and does not change ranking, sizing, exits, paper sleeves, live orders,
watchlists, LLM boundaries, or production daily behavior.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
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


EXPERIMENT_ID = "exp-20260701-002"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_sponsorship_10d_forward_value"
RUNNER = f"quant/experiments/exp_20260701_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260701_002_{SLUG}.json"
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
SOURCE_LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-016"
    / "kova_forward_sec13f_sponsorship_ledger.jsonl"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

HYPOTHESIS = (
    "Observed-only alpha hypothesis: Kova rows with stronger PIT SEC13F "
    "sponsorship should continue to separate newly closed 10d cash/SPY/QQQ "
    "replacement value versus weak or missing sponsorship rows, validating "
    "whether the earlier 1d/3d/5d lead survives a longer forward window before "
    "any shared default-off helper is considered."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_forward_sponsorship_attribution"
TRIAL_VARIANT_ID = "hot_warehouse_10d_closed_forward_v1"
CHANGED_VARIABLE = "kova_sec13f_sponsorship_10d_monotonicity_v1"
SINGLE_CAUSAL_VARIABLE = "kova_sec13f_sponsorship_10d_forward_value_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-016",
    "exp-20260624-017",
    "exp-20260624-018",
    "exp-20260628-002",
]
NEW_EVIDENCE_TYPE = "materially_more_closed_forward_rows"
NEW_EVIDENCE_AXIS = (
    "Materially more closed forward evidence: the exp-20260628-002 reopen "
    "condition advanced from 0 settled 10d rows to 2,536 settled 10d rows "
    "after hot warehouse coverage reached 2026-06-30; this reuses the fixed "
    "sponsorship score and does not introduce a same-source field, threshold, "
    "response curve, or saturated scan retry."
)
CAUSAL_COMPONENTS = [
    "newly closed 10d forward rows",
    "fixed PIT SEC13F sponsorship score",
    "cash/SPY/QQQ replacement-value monotonicity",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260701-002/exp_20260701_002_kova_sec13f_sponsorship_10d_forward_value.json",
    "experiments/cards/exp-20260701-002.md",
    "experiments/manifests/exp-20260701-002.json",
    "experiments/tickets/exp-20260701-002.json",
    "experiments/logs/exp-20260701-002.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZON = 10
COMPARATORS = ("SPY", "QQQ")
REPLACEMENT_SUFFIXES = ("cash", "spy", "qqq")
BUCKETS = ["low_sponsorship", "mid_sponsorship", "high_sponsorship"]
PROXY_NOTIONAL_USD = 10_000.0
CONFIG = {
    "horizon": HORIZON,
    "min_settled_rows": 100,
    "min_sponsorship_rows": 500,
    "min_missing_rows": 100,
    "min_asof_dates": 3,
    "max_single_positive_pnl_share": 0.50,
    "positive_pnl_hhi_guardrail": 0.35,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "10d_signal_reverses",
        "qqq_beta_only",
        "mega_cap_concentration",
        "still_too_few_closed_10d_rows",
    ],
    "confidence_reason": (
        "Exp-20260624-018 showed sponsorship separation on 1d/3d/5d, but "
        "exp-20260628-002 parked 10d attribution until the hot warehouse "
        "advanced. A read-only preflight now finds 2,536 10d rows with "
        "SPY/QQQ comparators through 2026-06-30, including 1,969 "
        "sec13f_status=ok rows, which is materially new closed forward evidence."
    ),
}
REQUIRED_SOURCE_FIELDS = [
    "observation_id",
    "asof_date",
    "ticker",
    "sec13f_status",
    "sec13f_holder_count",
    "sec13f_total_value_usd",
    "sec13f_position_row_count",
    "sec13f_source_asof_date",
    "target_price",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def parse_date_key(value: Any) -> str:
    return str(value or "")[:10]


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    drawdowns = [
        float(window.get("max_drawdown_pct"))
        for window in windows
        if window.get("max_drawdown_pct") is not None
    ]
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
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def source_field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    total = len(rows)
    for field in REQUIRED_SOURCE_FIELDS:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        coverage[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "coverage": round(present / total, 6) if total else None,
        }
    return coverage


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    asof_dates = sorted({parse_date_key(row.get("asof_date")) for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    source_asof_violations = 0
    for row in rows:
        source_asof = parse_date_key(row.get("sec13f_source_asof_date"))
        asof = parse_date_key(row.get("asof_date"))
        if source_asof and asof and source_asof > asof:
            source_asof_violations += 1
    return {
        "source_ledger": repo_rel(SOURCE_LEDGER_JSONL),
        "source_exists": SOURCE_LEDGER_JSONL.exists(),
        "source_rows": len(rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "field_coverage": source_field_coverage(rows),
        "sec13f_source_asof_violations": source_asof_violations,
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
    }


def immutable_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro&immutable=1"


def load_hot_prices(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not HOT_WAREHOUSE.exists():
        return {}, {
            "warehouse": repo_rel(HOT_WAREHOUSE),
            "exists": False,
            "immutable_read": False,
            "error": "missing_hot_warehouse",
        }
    requested = sorted({ticker.upper() for ticker in tickers if ticker})
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
                prices[str(ticker).upper()].append(
                    {"date": str(day), "open": open_f, "close": close_f}
                )
    finally:
        con.close()
    date_ranges = {}
    for ticker, rows in prices.items():
        if rows:
            date_ranges[ticker] = {
                "start": rows[0]["date"],
                "end": rows[-1]["date"],
                "rows": len(rows),
            }
    missing_requested = sorted(set(requested) - set(prices))
    return dict(prices), {
        "warehouse": repo_rel(HOT_WAREHOUSE),
        "exists": True,
        "immutable_read": True,
        "quick_check": quick[0] if quick else None,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing_requested),
        "missing_requested_ticker_sample": missing_requested[:25],
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
    asof_date: str,
    horizon: int,
) -> dict[str, Any]:
    if not ticker_rows:
        return {"status": "missing_ticker_prices"}
    dates = [row["date"] for row in ticker_rows]
    entry_idx = bisect.bisect_right(dates, asof_date)
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


def settle_row(
    row: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    asof_date = parse_date_key(row.get("asof_date"))
    out = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "source_experiment_id": "exp-20260624-016",
        "observation_id": row.get("observation_id"),
        "asof_date": asof_date or None,
        "ticker": ticker or None,
        "source": row.get("source"),
        "source_snapshot_file": row.get("source_snapshot_file"),
        "sec13f_status": row.get("sec13f_status"),
        "sec13f_holder_count": row.get("sec13f_holder_count"),
        "sec13f_position_row_count": row.get("sec13f_position_row_count"),
        "sec13f_total_value_usd": row.get("sec13f_total_value_usd"),
        "sec13f_total_shares": row.get("sec13f_total_shares"),
        "sec13f_source_asof_date": row.get("sec13f_source_asof_date"),
        "sec13f_source_file": row.get("sec13f_source_file"),
        "target_price": None,
        "target_price_resolution": "not_applicable_observed_only_time_horizon",
        "trade_enabled": False,
        "alters_orders": False,
        "proxy_notional_usd": PROXY_NOTIONAL_USD,
    }
    if not ticker or not asof_date:
        out[f"forward_{HORIZON}d_status"] = "missing_ticker_or_asof"
        out["outcome_status"] = "pending_forward_close"
        return out

    outcome = resolve_horizon(prices.get(ticker, []), asof_date, HORIZON)
    status = str(outcome.get("status"))
    prefix = f"forward_{HORIZON}d"
    out[f"{prefix}_status"] = status
    if outcome.get("entry_date"):
        out[f"{prefix}_entry_date"] = outcome.get("entry_date")
        out["entry_date"] = outcome.get("entry_date")
        out["planned_entry_date"] = outcome.get("entry_date")
    else:
        out["entry_date"] = None
        out["planned_entry_date"] = None
    if outcome.get("available_forward_sessions") is not None:
        out[f"{prefix}_available_forward_sessions"] = outcome.get("available_forward_sessions")
    if status != "settled":
        out["outcome_status"] = "pending_forward_close"
        return out

    entry_date = str(outcome["entry_date"])
    exit_date = str(outcome["exit_date"])
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
    status_field = f"forward_{HORIZON}d_status"
    settled = [
        row
        for row in outcome_rows
        if row.get(status_field) == "settled"
        and row.get(f"replacement_value_{HORIZON}d_vs_spy_usd") is not None
        and row.get(f"replacement_value_{HORIZON}d_vs_qqq_usd") is not None
    ]
    return outcome_rows, {
        "price_metadata": price_metadata,
        "outcome_rows": len(outcome_rows),
        "settled_rows": len(settled),
        "settled_sec13f_ok_rows": sum(1 for row in settled if row.get("sec13f_status") == "ok"),
        "settled_missing_or_skipped_rows": sum(
            1 for row in settled if row.get("sec13f_status") != "ok"
        ),
        "settled_by_asof_date": dict(
            sorted(Counter(str(row.get("asof_date") or "missing") for row in settled).items())
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
            sorted(Counter(str(row.get(status_field) or "missing") for row in outcome_rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in outcome_rows).items())
        ),
    }


def percentile_rank(value: float, sorted_values: list[float]) -> float | None:
    if not sorted_values:
        return None
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    avg_zero_based_rank = (left + right - 1) / 2.0
    if len(sorted_values) == 1:
        return 1.0
    return avg_zero_based_rank / (len(sorted_values) - 1)


def log_feature(row: dict[str, Any], key: str) -> float | None:
    value = safe_float(row.get(key))
    if value is None or value <= 0:
        return None
    return math.log1p(value)


def add_sponsorship_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    holder_values = []
    total_values = []
    position_values = []
    for row in rows:
        if row.get("sec13f_status") != "ok":
            continue
        holder = log_feature(row, "sec13f_holder_count")
        total = log_feature(row, "sec13f_total_value_usd")
        position = log_feature(row, "sec13f_position_row_count")
        if holder is not None:
            holder_values.append(holder)
        if total is not None:
            total_values.append(total)
        if position is not None:
            position_values.append(position)
    holder_values.sort()
    total_values.sort()
    position_values.sort()

    scored = []
    for row in rows:
        out = dict(row)
        score_parts = []
        holder = log_feature(row, "sec13f_holder_count")
        total = log_feature(row, "sec13f_total_value_usd")
        position = log_feature(row, "sec13f_position_row_count")
        for value, population in (
            (holder, holder_values),
            (total, total_values),
            (position, position_values),
        ):
            if value is None:
                continue
            ranked = percentile_rank(value, population)
            if ranked is not None:
                score_parts.append(ranked)
        score = mean(score_parts)
        out["sec13f_sponsorship_score"] = round_or_none(score, 8)
        out["sec13f_sponsorship_component_count"] = len(score_parts)
        scored.append(out)
    return scored


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


def sponsorship_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("sec13f_status") == "ok"
        and safe_float(row.get("sec13f_sponsorship_score")) is not None
    ]


def assign_buckets(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            safe_float(row.get("sec13f_sponsorship_score")) or -1.0,
            str(row.get("ticker") or ""),
            str(row.get("asof_date") or ""),
        ),
    )
    buckets = {key: [] for key in BUCKETS}
    total = len(ordered)
    if not total:
        return buckets
    for index, row in enumerate(ordered):
        bucket_index = min(2, int(index * 3 / total))
        buckets[BUCKETS[bucket_index]].append(row)
    return buckets


def numeric_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        value = safe_float(row.get(field))
        if value is None or value <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += value
    positive_total = sum(by_ticker.values())
    top = [
        {"ticker": ticker, "pnl": round(value, 2), "share": round(value / positive_total, 6)}
        for ticker, value in by_ticker.most_common(8)
    ] if positive_total > 0 else []
    hhi = sum((value / positive_total) ** 2 for value in by_ticker.values()) if positive_total > 0 else None
    return {
        "positive_pnl": round(positive_total, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": top[0]["share"] if top else None,
        "positive_pnl_hhi": round_or_none(hhi, 6),
        "top_positive_tickers": top,
    }


def summarize_metric(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": round_or_none(mean(values), 4),
        "median": round_or_none(median(values), 4) if values else None,
        "sum": round(sum(values), 2) if values else 0.0,
        "min": round(min(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4)
        if values
        else None,
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score_values = numeric_values(rows, "sec13f_sponsorship_score")
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    metrics = {}
    for suffix in REPLACEMENT_SUFFIXES:
        metrics[f"replacement_value_vs_{suffix}_usd"] = summarize_metric(
            numeric_values(rows, metric_field(suffix))
        )
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "asof_date_count": len(asof_dates),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "score_mean": round_or_none(mean(score_values), 6),
        "score_median": round_or_none(median(score_values), 6) if score_values else None,
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "replacement_metrics": metrics,
        "cash_positive_concentration": concentration(rows, metric_field("cash")),
    }


def _rankdata(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        avg_rank = (cursor + end - 1) / 2.0
        for _, index in ordered[cursor:end]:
            ranks[index] = avg_rank
        cursor = end
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    if x_mean is None or y_mean is None:
        return None
    xdiff = [value - x_mean for value in xs]
    ydiff = [value - y_mean for value in ys]
    denom_x = math.sqrt(sum(value * value for value in xdiff))
    denom_y = math.sqrt(sum(value * value for value in ydiff))
    if denom_x <= 0 or denom_y <= 0:
        return None
    return sum(x * y for x, y in zip(xdiff, ydiff)) / (denom_x * denom_y)


def spearman(rows: list[dict[str, Any]], suffix: str) -> float | None:
    xs = []
    ys = []
    field = metric_field(suffix)
    for row in rows:
        score = safe_float(row.get("sec13f_sponsorship_score"))
        value = safe_float(row.get(field))
        if score is None or value is None:
            continue
        xs.append(score)
        ys.append(value)
    if len(xs) < 3:
        return None
    return round_or_none(pearson(_rankdata(xs), _rankdata(ys)), 6)


def compare_mean(bucket_summary: dict[str, dict[str, Any]], bucket_a: str, bucket_b: str, suffix: str) -> bool:
    a = bucket_summary[bucket_a]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    b = bucket_summary[bucket_b]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    return a is not None and b is not None and a > b


def compare_high_missing(
    high: dict[str, Any],
    missing: dict[str, Any],
    suffix: str,
) -> bool:
    a = high["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    b = missing["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    return a is not None and b is not None and a > b


def build_analysis(source_rows: list[dict[str, Any]], outcome_rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored_all = add_sponsorship_scores(outcome_rows)
    settled = settled_rows(scored_all)
    ok_rows = sponsorship_rows(settled)
    missing_rows = [row for row in settled if row.get("sec13f_status") != "ok"]
    buckets = assign_buckets(ok_rows)
    bucket_summary = {name: summarize_group(bucket_rows) for name, bucket_rows in buckets.items()}
    missing_summary = summarize_group(missing_rows)
    high = bucket_summary["high_sponsorship"]
    support = {
        "high_beats_low_mean": {
            suffix: compare_mean(bucket_summary, "high_sponsorship", "low_sponsorship", suffix)
            for suffix in REPLACEMENT_SUFFIXES
        },
        "high_beats_missing_mean": {
            suffix: compare_high_missing(high, missing_summary, suffix)
            for suffix in REPLACEMENT_SUFFIXES
        },
        "spearman_score_to_replacement": {
            suffix: spearman(ok_rows, suffix) for suffix in REPLACEMENT_SUFFIXES
        },
    }
    return {
        "source_summary": source_summary(source_rows),
        "settled_summary": {
            "settled_rows": len(settled),
            "sponsorship_rows": len(ok_rows),
            "missing_or_skipped_sponsorship_rows": len(missing_rows),
            "all_settled_summary": summarize_group(settled),
            "bucket_summary": bucket_summary,
            "missing_or_skipped_sponsorship_summary": missing_summary,
            **support,
        },
        "score_definition": (
            "sec13f_sponsorship_score = average percentile rank of log1p(holder_count), "
            "log1p(total_value_usd), and log1p(position_row_count) among all "
            "SEC13F-ok Kova source rows. Missing/skipped SEC13F rows are measured "
            "separately and not ranked."
        ),
        "sample_scored_rows": [
            {
                "ticker": row.get("ticker"),
                "asof_date": row.get("asof_date"),
                "sec13f_status": row.get("sec13f_status"),
                "sec13f_sponsorship_score": row.get("sec13f_sponsorship_score"),
                "forward_10d_entry_date": row.get("forward_10d_entry_date"),
                "forward_10d_exit_date": row.get("forward_10d_exit_date"),
                "replacement_value_10d_vs_cash_usd": row.get("replacement_value_10d_vs_cash_usd"),
                "replacement_value_10d_vs_spy_usd": row.get("replacement_value_10d_vs_spy_usd"),
                "replacement_value_10d_vs_qqq_usd": row.get("replacement_value_10d_vs_qqq_usd"),
            }
            for row in scored_all[:5]
        ],
    }


def evaluate_gate4(analysis: dict[str, Any], settlement_metadata: dict[str, Any]) -> dict[str, Any]:
    primary = analysis["settled_summary"]
    high = primary["bucket_summary"]["high_sponsorship"]
    concentration_stats = high["cash_positive_concentration"]
    checks = {
        "settled_10d_sample_min_passed": (
            primary["settled_rows"] >= CONFIG["min_settled_rows"]
        ),
        "sponsorship_sample_min_passed": (
            primary["sponsorship_rows"] >= CONFIG["min_sponsorship_rows"]
        ),
        "missing_sample_min_passed": (
            primary["missing_or_skipped_sponsorship_rows"] >= CONFIG["min_missing_rows"]
        ),
        "asof_dates_min_passed": (
            primary["all_settled_summary"]["asof_date_count"] >= CONFIG["min_asof_dates"]
        ),
        "high_mean_cash_beats_low": primary["high_beats_low_mean"]["cash"],
        "high_mean_spy_beats_low": primary["high_beats_low_mean"]["spy"],
        "high_mean_qqq_beats_low": primary["high_beats_low_mean"]["qqq"],
        "spearman_cash_positive": (
            (primary["spearman_score_to_replacement"]["cash"] or 0.0) > 0.0
        ),
        "spearman_spy_positive": (
            (primary["spearman_score_to_replacement"]["spy"] or 0.0) > 0.0
        ),
        "spearman_qqq_positive": (
            (primary["spearman_score_to_replacement"]["qqq"] or 0.0) > 0.0
        ),
        "high_mean_cash_beats_missing": primary["high_beats_missing_mean"]["cash"],
        "high_mean_spy_beats_missing": primary["high_beats_missing_mean"]["spy"],
        "high_mean_qqq_beats_missing": primary["high_beats_missing_mean"]["qqq"],
        "concentration_max_share_passed": (
            concentration_stats["max_single_positive_pnl_share"] is not None
            and concentration_stats["max_single_positive_pnl_share"]
            <= CONFIG["max_single_positive_pnl_share"]
        ),
        "concentration_hhi_passed": (
            concentration_stats["positive_pnl_hhi"] is not None
            and concentration_stats["positive_pnl_hhi"] <= CONFIG["positive_pnl_hhi_guardrail"]
        ),
        "hot_warehouse_immutable_read_passed": bool(
            settlement_metadata["price_metadata"].get("immutable_read")
            and settlement_metadata["price_metadata"].get("quick_check") == "ok"
        ),
        "strategy_behavior_unchanged": True,
    }
    failed = [key for key, passed in checks.items() if not passed]
    observed_lead = not failed
    decision = (
        "observed_only_positive_kova_sec13f_10d_sponsorship_lead_not_promoted"
        if observed_lead
        else "rejected_no_10d_kova_sec13f_sponsorship_edge"
    )
    return {
        "observed_only_lead": observed_lead,
        "decision": decision,
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
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "No shared helper, daily adapter, ranker, sizing rule, or order behavior was promoted.",
            "A live-ready path would require a shared default-off helper plus canonical Gate 1-4.",
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
            "The fixed SEC13F sponsorship score remained monotonic on newly closed "
            "10d replacement rows, so this is a forward-only positive lead."
            if success
            else "The sponsorship score did not clear the preregistered 10d "
            "monotonic, benchmark, missing-row, or concentration checks."
        ),
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    source_rows = read_jsonl(SOURCE_LEDGER_JSONL)
    outcome_rows, settlement_metadata = settle_rows(source_rows)
    analysis = build_analysis(source_rows, outcome_rows)
    gate4 = evaluate_gate4(analysis, settlement_metadata)
    observed_lead = bool(gate4["observed_only_lead"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    why = (
        "The fixed PIT SEC13F holder/value/position sponsorship score still "
        "separated newly closed 10d Kova rows versus weak and missing sponsorship "
        "across cash, SPY, and QQQ. The result remains forward-only attribution "
        "and did not promote a helper or change strategy behavior."
        if observed_lead
        else "The fixed PIT SEC13F sponsorship score failed at least one "
        "predeclared 10d replacement-value check. The newly closed rows are "
        "useful evidence, but not enough to promote Kova/13F sponsorship."
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
                "exp-20260624-016": (
                    "Accepted PIT Kova SEC13F observation ledger, but outcomes "
                    "were pending by design."
                ),
                "exp-20260624-017": (
                    "Accepted forward outcome settlement through 1d/3d/5d; 10d "
                    "was not mature."
                ),
                "exp-20260624-018": (
                    "Observed-only positive 1d/3d/5d sponsorship lead. This run "
                    "does not retune score fields or thresholds; it tests newly "
                    "closed 10d rows."
                ),
                "exp-20260628-002": (
                    "Parked the same surface until hot warehouse contained enough "
                    "sessions after the 2026-06-15 cohort. A preflight now found "
                    "2,536 settled 10d rows through 2026-06-30."
                ),
                "novelty_gate": (
                    "Reservation passed with novelty override recorded as "
                    "materially_more_forward_rows; source-saturation was not "
                    "applicable and reopen_condition_guard was not blocked."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: settle 10d outcomes from "
                "the fixed exp-20260624-016 Kova SEC13F source ledger, compute the "
                "same PIT sponsorship score, bucket settled SEC13F-ok rows into "
                "tertiles, and evaluate cash/SPY/QQQ replacement value. No "
                "trading policy changes."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if 10d sample floors pass, high "
                "sponsorship beats low on mean cash/SPY/QQQ replacement value, "
                "Spearman score is positive for cash/SPY/QQQ, high beats missing "
                "on mean, concentration guardrails pass, immutable warehouse read "
                "passes, and no production behavior changes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_ledger": repo_rel(SOURCE_LEDGER_JSONL),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizon": HORIZON,
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_fill": "next available hot-warehouse session open with buy-side slippage",
            "exit_fill": "10th forward session close with target-side sell slippage",
            "comparators": list(COMPARATORS),
            "bucket_method": "tertiles on sec13f_sponsorship_score within settled SEC13F-ok rows",
            "config": CONFIG,
            "score_definition": analysis["score_definition"],
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(source_rows)
            and analysis["source_summary"]["duplicate_observation_ids"] == 0
            and analysis["source_summary"]["sec13f_source_asof_violations"] == 0,
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
            "source_field_coverage": analysis["source_summary"]["field_coverage"],
            "settled_entry_date_rows": settlement_metadata["settled_rows"],
            "target_price_scope": (
                "Not applicable: observed-only fixed-horizon attribution does not "
                "schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": analysis["source_summary"]["source_rows"],
            "signals_survived": settlement_metadata["settled_rows"],
            "survival_rate": round(
                settlement_metadata["settled_rows"] / analysis["source_summary"]["source_rows"],
                4,
            )
            if analysis["source_summary"]["source_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "settlement_metadata": settlement_metadata,
        "attribution": analysis,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "shared_helper_promoted": False,
            "uses_kova_forward_snapshots": True,
            "uses_sec13f_forward_context": True,
            "forward_only_not_fixed_window_pit_coverage": True,
            "live_ready": False,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova SEC13F holder_count, total_value_usd, "
                "position_row_count, sponsorship score, RS, Companyfacts, top-N, "
                "hold, cooldown, notional, allocator thresholds, or response "
                "curves on these same 10d rows. This fixed sponsorship 10d "
                "attribution is the result for the newly closed surface."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more closed forward rows beyond "
                "the current 2026-06-13 to 2026-06-15 10d cohort, materially richer "
                "PIT manager/flow provenance, borrow/options cross-evidence, or a "
                "shared default-off helper with canonical fixed-window PIT coverage."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_LEDGER_JSONL),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-016.json",
            "experiments/logs/exp-20260624-017.json",
            "experiments/logs/exp-20260624-018.json",
            "experiments/logs/exp-20260628-002.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    primary = payload["attribution"]["settled_summary"]
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
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "settlement_metadata": payload["settlement_metadata"],
        "attribution": {
            "source_summary": payload["attribution"]["source_summary"],
            "score_definition": payload["attribution"]["score_definition"],
            "horizon": HORIZON,
            "settled_summary": {
                "settled_rows": primary["settled_rows"],
                "sponsorship_rows": primary["sponsorship_rows"],
                "missing_or_skipped_sponsorship_rows": primary[
                    "missing_or_skipped_sponsorship_rows"
                ],
                "bucket_summary": primary["bucket_summary"],
                "missing_or_skipped_sponsorship_summary": primary[
                    "missing_or_skipped_sponsorship_summary"
                ],
                "spearman_score_to_replacement": primary[
                    "spearman_score_to_replacement"
                ],
                "high_beats_low_mean": primary["high_beats_low_mean"],
                "high_beats_missing_mean": primary["high_beats_missing_mean"],
            },
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "artifact": payload["artifact"],
        "log": payload["log"],
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def card_bucket_row(name: str, summary: dict[str, Any]) -> str:
    metrics = summary["replacement_metrics"]
    return "| {name} | {n} | {score} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=summary["n"],
        score=summary["score_median"],
        cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
        spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
        qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
        median_cash=money(metrics["replacement_value_vs_cash_usd"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["attribution"]["settled_summary"]
    rows = [
        "| Bucket | Rows | Median Score | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        rows.append(card_bucket_row(bucket, primary["bucket_summary"][bucket]))
    rows.append(card_bucket_row("missing_or_skipped", primary["missing_or_skipped_sponsorship_summary"]))
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F sponsorship 10d forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            f"- Settled 10d rows: `{primary['settled_rows']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## 10d Buckets",
            "",
            *rows,
            "",
            f"- 10d sponsorship rows: `{primary['sponsorship_rows']}`",
            f"- 10d missing/skipped rows: `{primary['missing_or_skipped_sponsorship_rows']}`",
            f"- Spearman score to cash/SPY/QQQ: `{primary['spearman_score_to_replacement']['cash']}` / `{primary['spearman_score_to_replacement']['spy']}` / `{primary['spearman_score_to_replacement']['qqq']}`",
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
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
        SOURCE_LEDGER_JSONL,
        HOT_WAREHOUSE,
        BASELINE_RESULT,
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
        "settlement_metadata": payload["settlement_metadata"],
        "calibration": payload["calibration"],
        "attribution": log_record["attribution"],
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
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
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
            "changed_files": payload["changed_files"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    primary = payload["attribution"]["settled_summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "settled_10d_rows": primary["settled_rows"],
                "sponsorship_rows": primary["sponsorship_rows"],
                "missing_or_skipped_rows": primary["missing_or_skipped_sponsorship_rows"],
                "spearman": primary["spearman_score_to_replacement"],
                "high_beats_low_mean": primary["high_beats_low_mean"],
                "high_beats_missing_mean": primary["high_beats_missing_mean"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
