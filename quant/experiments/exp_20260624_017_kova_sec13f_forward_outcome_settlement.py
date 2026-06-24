"""exp-20260624-017: Kova SEC13F forward outcome settlement.

Measurement repair for exp-20260624-016. The previous run created PIT-safe
Kova + SEC13F observation rows, but left every forward outcome pending. This
runner adds experiment-owned next-open outcome fields versus cash, SPY, and
QQQ so later work can test a predeclared sponsorship hypothesis after rows
close.

No strategy, helper, ranking, sizing, exits, paper fills, live orders,
watchlist, LLM, or production daily behavior changes in this experiment.
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


EXPERIMENT_ID = "exp-20260624-017"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_forward_outcome_settlement"
RUNNER = f"quant/experiments/exp_20260624_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_017_{SLUG}.json"
OUTCOME_LEDGER_JSONL = DATA_DIR / "kova_sec13f_forward_outcome_settlement_ledger.jsonl"
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
    "Repair the Kova plus SEC13F forward observation blocker by settling "
    "exp-20260624-016 rows into PIT-safe next-open forward outcome fields "
    "versus cash, SPY, and QQQ without changing ranking, sizing, exits, "
    "paper fills, or live orders."
)
ALPHA_HYPOTHESIS = (
    "Institutional sponsorship may become an orthogonal Kova evidence axis only "
    "after Kova forward rows have closed cash/SPY/QQQ replacement outcomes; "
    "this run repairs the missing outcome surface and does not test any 13F "
    "threshold."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "kova_multisource_forward_observation"
TRIAL_FAMILY = "kova_sec13f_forward_outcome_settlement"
TRIAL_VARIANT_ID = "post_exp016_hot_warehouse_partial_forward_v1"
CHANGED_VARIABLE = "kova_sec13f_forward_outcome_settlement_ledger_v1"
NEW_EVIDENCE_TYPE = "forward_replacement_outcome_settlement_fields"
NEW_EVIDENCE_AXIS = (
    "Closed or partially closeable exp-20260624-016 Kova SEC13F observation rows "
    "settled with hot warehouse next-open outcomes versus cash, SPY, and QQQ; "
    "not a 13F holder-count, value, RS, Companyfacts, top-N, hold, cooldown, "
    "or notional threshold retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-014",
    "exp-20260624-015",
    "exp-20260624-016",
]
CAUSAL_COMPONENTS = [
    "exp-20260624-016 Kova SEC13F observation ledger",
    "hot warehouse next-open outcome settlement",
    "cash SPY QQQ replacement-value fields",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-017/exp_20260624_017_kova_sec13f_forward_outcome_settlement.json",
    "data/experiments/exp-20260624-017/kova_sec13f_forward_outcome_settlement_ledger.jsonl",
    "experiments/cards/exp-20260624-017.md",
    "experiments/manifests/exp-20260624-017.json",
    "experiments/tickets/exp-20260624-017.json",
    "experiments/logs/exp-20260624-017.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZONS = (1, 3, 5, 10)
PROXY_NOTIONAL_USD = 10_000.0
MIN_SETTLED_1D_ROWS = 100
MIN_SETTLED_3D_ROWS = 100
MIN_SETTLED_5D_ROWS = 100
COMPARATORS = ("SPY", "QQQ")
REQUIRED_SOURCE_FIELDS = [
    "observation_id",
    "asof_date",
    "ticker",
    "sec13f_status",
    "sec13f_source_asof_date",
    "outcome_status",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.68,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "hot_warehouse_missing_recent_benchmark_rows",
        "too_few_settled_5d_rows",
        "source_ledger_missing_required_fields",
        "duplicate_observation_ids",
    ],
    "confidence_reason": (
        "exp-20260624-016 produced PIT-valid SEC13F holder/value rows from "
        "2026-06-13 onward, and the hot warehouse has recent SPY/QQQ rows "
        "through 2026-06-23. This is a measurement repair only: it should "
        "create partial 1d/3d/5d outcome rows, but it does not test or promote "
        "Kova/13F thresholds."
    ),
}


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


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


def parse_date_key(value: Any) -> str:
    return str(value or "")[:10]


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
                raise ValueError(f"{path}:{line_no}: invalid jsonl") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def summarize_baseline(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    windows = payload.get("windows") if isinstance(payload, dict) else None
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(path),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
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


def load_source_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_jsonl(SOURCE_LEDGER_JSONL)
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    duplicate_ids = len(ids) - len(set(ids))
    asof_dates = sorted({parse_date_key(row.get("asof_date")) for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    source_asof_violations = 0
    for row in rows:
        source_asof = parse_date_key(row.get("sec13f_source_asof_date"))
        asof = parse_date_key(row.get("asof_date"))
        if source_asof and asof and source_asof > asof:
            source_asof_violations += 1
    metadata = {
        "source_ledger": repo_rel(SOURCE_LEDGER_JSONL),
        "source_ledger_exists": SOURCE_LEDGER_JSONL.exists(),
        "source_rows": len(rows),
        "duplicate_observation_ids": duplicate_ids,
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "sec13f_source_asof_violations": source_asof_violations,
        "source_field_coverage": source_field_coverage(rows),
        "source_outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "source_sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
    }
    return rows, metadata


def load_hot_prices(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not HOT_WAREHOUSE.exists():
        return {}, {
            "warehouse": repo_rel(HOT_WAREHOUSE),
            "exists": False,
            "price_ticker_count": 0,
            "error": "missing_hot_warehouse",
        }
    requested = sorted({ticker.upper() for ticker in tickers if ticker})
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    con = sqlite3.connect(HOT_WAREHOUSE)
    try:
        for start in range(0, len(requested), 750):
            chunk = requested[start : start + 750]
            if not chunk:
                continue
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
        date_ranges = {}
        for ticker, rows in prices.items():
            if rows:
                date_ranges[ticker] = {
                    "start": rows[0]["date"],
                    "end": rows[-1]["date"],
                    "rows": len(rows),
                }
        try:
            warehouse_range = con.execute("select min(date), max(date), count(*) from ohlcv").fetchone()
        except sqlite3.DatabaseError:
            warehouse_range = None
    finally:
        con.close()
    missing_requested = sorted(set(requested) - set(prices))
    metadata = {
        "warehouse": repo_rel(HOT_WAREHOUSE),
        "exists": True,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing_requested),
        "missing_requested_ticker_sample": missing_requested[:25],
        "warehouse_min_date": warehouse_range[0] if warehouse_range else None,
        "warehouse_max_date": warehouse_range[1] if warehouse_range else None,
        "warehouse_row_count": warehouse_range[2] if warehouse_range else None,
        "benchmark_ranges": {ticker: date_ranges.get(ticker) for ticker in COMPARATORS},
    }
    return dict(prices), metadata


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
        "entry_open": round(float(entry["open"]), 4),
        "exit_close": round(float(exit_row["close"]), 4),
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
    out: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "source_experiment_id": "exp-20260624-016",
        "rule_version": CHANGED_VARIABLE,
        "source_rule_version": row.get("rule_version"),
        "observation_id": row.get("observation_id"),
        "asof_date": asof_date or None,
        "ticker": ticker or None,
        "source": row.get("source"),
        "source_snapshot_file": row.get("source_snapshot_file"),
        "rs_proxy_status": row.get("rs_proxy_status"),
        "rs_proxy_rank_pct_20d": round_or_none(row.get("rs_proxy_rank_pct_20d")),
        "rs_proxy_rank_pct_60d": round_or_none(row.get("rs_proxy_rank_pct_60d")),
        "rs_proxy_rank_pct_120d": round_or_none(row.get("rs_proxy_rank_pct_120d")),
        "companyfacts_growth_row_count": row.get("companyfacts_growth_row_count"),
        "companyfacts_selected_ok_component_count": row.get(
            "companyfacts_selected_ok_component_count"
        ),
        "companyfacts_selected_positive_yoy_count": row.get(
            "companyfacts_selected_positive_yoy_count"
        ),
        "sec13f_status": row.get("sec13f_status"),
        "sec13f_holder_count": row.get("sec13f_holder_count"),
        "sec13f_position_row_count": row.get("sec13f_position_row_count"),
        "sec13f_total_value_usd": row.get("sec13f_total_value_usd"),
        "sec13f_total_shares": row.get("sec13f_total_shares"),
        "sec13f_source_asof_date": row.get("sec13f_source_asof_date"),
        "sec13f_source_file": row.get("sec13f_source_file"),
        "quality_flags": list(row.get("quality_flags") or []),
        "trade_enabled": False,
        "alters_orders": False,
        "proxy_notional_usd": PROXY_NOTIONAL_USD,
    }
    if not ticker or not asof_date:
        out["outcome_status"] = "missing_ticker_or_asof"
        return out

    settled_horizons: list[int] = []
    horizon_statuses: dict[str, str] = {}
    first_entry_date = None
    for horizon in HORIZONS:
        prefix = f"forward_{horizon}d"
        outcome = resolve_horizon(prices.get(ticker, []), asof_date, horizon)
        status = str(outcome.get("status"))
        horizon_statuses[str(horizon)] = status
        out[f"{prefix}_status"] = status
        if outcome.get("entry_date") and first_entry_date is None:
            first_entry_date = outcome.get("entry_date")
        if status != "settled":
            if outcome.get("entry_date"):
                out[f"{prefix}_entry_date"] = outcome.get("entry_date")
            if outcome.get("available_forward_sessions") is not None:
                out[f"{prefix}_available_forward_sessions"] = outcome.get(
                    "available_forward_sessions"
                )
            continue

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
        out[f"replacement_value_{horizon}d_vs_cash_usd"] = outcome["pnl_usd"]

        all_comparators_settled = True
        for comparator in COMPARATORS:
            detail = comparator_pnl(prices, comparator, entry_date, exit_date)
            detail_key = comparator.lower()
            out[f"{prefix}_{detail_key}_status"] = detail["status"]
            if detail["status"] == "settled":
                out[f"{prefix}_{detail_key}_pnl_usd"] = detail["pnl_usd"]
                out[f"replacement_value_{horizon}d_vs_{detail_key}_usd"] = round(
                    float(outcome["pnl_usd"]) - float(detail["pnl_usd"]),
                    2,
                )
            else:
                all_comparators_settled = False
                out[f"replacement_value_{horizon}d_vs_{detail_key}_usd"] = None
        if all_comparators_settled:
            settled_horizons.append(horizon)

    out["planned_entry_date"] = first_entry_date
    out["entry_date"] = first_entry_date
    out["target_price"] = None
    out["target_price_resolution"] = "not_applicable_observed_only_time_horizon"
    out["settled_horizons"] = settled_horizons
    out["horizon_statuses"] = horizon_statuses
    out["outcome_status"] = "settled_partial" if settled_horizons else "pending_forward_close"
    if 5 in settled_horizons:
        out["forward_5d_return_pct"] = out.get("forward_5d_return_pct")
        out["replacement_value_vs_cash_usd"] = out.get("replacement_value_5d_vs_cash_usd")
        out["replacement_value_vs_spy_usd"] = out.get("replacement_value_5d_vs_spy_usd")
        out["replacement_value_vs_qqq_usd"] = out.get("replacement_value_5d_vs_qqq_usd")
    else:
        out["forward_5d_return_pct"] = None
        out["replacement_value_vs_cash_usd"] = None
        out["replacement_value_vs_spy_usd"] = None
        out["replacement_value_vs_qqq_usd"] = None
    out["forward_10d_return_pct"] = out.get("forward_10d_return_pct")
    return out


def settle_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    tickers.update(COMPARATORS)
    prices, price_metadata = load_hot_prices(tickers)
    outcome_rows = [settle_row(row, prices) for row in rows]

    horizon_counts = {}
    horizon_status_counts = {}
    for horizon in HORIZONS:
        prefix = f"forward_{horizon}d"
        status_field = f"{prefix}_status"
        settled = [
            row
            for row in outcome_rows
            if row.get(status_field) == "settled"
            and row.get(f"replacement_value_{horizon}d_vs_spy_usd") is not None
            and row.get(f"replacement_value_{horizon}d_vs_qqq_usd") is not None
        ]
        horizon_counts[str(horizon)] = len(settled)
        horizon_status_counts[str(horizon)] = dict(
            sorted(Counter(str(row.get(status_field) or "missing") for row in outcome_rows).items())
        )
    metadata = {
        "price_metadata": price_metadata,
        "outcome_rows": len(outcome_rows),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in outcome_rows).items())
        ),
        "horizon_settled_counts": horizon_counts,
        "horizon_status_counts": horizon_status_counts,
    }
    return outcome_rows, metadata


def distribution(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round(sum(clean) / len(clean), 4),
        "median": round(median(clean), 4),
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def top_counts(values: list[Any], limit: int = 20) -> list[dict[str, Any]]:
    counts = Counter(str(value) for value in values if value not in (None, ""))
    total = sum(counts.values())
    return [
        {"key": key, "n": count, "share": round(count / total, 6) if total else None}
        for key, count in counts.most_common(limit)
    ]


def summarize_outcomes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    asof_dates = sorted({str(row.get("asof_date")) for row in rows if row.get("asof_date")})
    tickers = [str(row.get("ticker") or "") for row in rows if row.get("ticker")]
    horizon_summaries = {}
    for horizon in HORIZONS:
        rv_fields = {
            "cash": f"replacement_value_{horizon}d_vs_cash_usd",
            "spy": f"replacement_value_{horizon}d_vs_spy_usd",
            "qqq": f"replacement_value_{horizon}d_vs_qqq_usd",
        }
        settled = [
            row
            for row in rows
            if row.get(f"forward_{horizon}d_status") == "settled"
            and row.get(rv_fields["spy"]) is not None
            and row.get(rv_fields["qqq"]) is not None
        ]
        horizon_summaries[str(horizon)] = {
            "settled_rows": len(settled),
            "distinct_tickers": len({row.get("ticker") for row in settled}),
            "asof_date_count": len({row.get("asof_date") for row in settled}),
            "entry_date_count": len({row.get(f"forward_{horizon}d_entry_date") for row in settled}),
            "exit_date_count": len({row.get(f"forward_{horizon}d_exit_date") for row in settled}),
            "rows_by_asof_date": top_counts([row.get("asof_date") for row in settled], 15),
            "rows_by_sec13f_status": top_counts([row.get("sec13f_status") for row in settled], 10),
            "rows_by_rs_proxy_status": top_counts([row.get("rs_proxy_status") for row in settled], 10),
            "replacement_value_vs_cash_usd": distribution(
                [row.get(rv_fields["cash"]) for row in settled if row.get(rv_fields["cash"]) is not None]
            ),
            "replacement_value_vs_spy_usd": distribution(
                [row.get(rv_fields["spy"]) for row in settled if row.get(rv_fields["spy"]) is not None]
            ),
            "replacement_value_vs_qqq_usd": distribution(
                [row.get(rv_fields["qqq"]) for row in settled if row.get(rv_fields["qqq"]) is not None]
            ),
        }
    return {
        "outcome_rows": len(rows),
        "ticker_count": len(set(tickers)),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "horizons": horizon_summaries,
        "sample_rows": rows[:5],
    }


def evaluate_gate4(
    source_metadata: dict[str, Any],
    settlement_metadata: dict[str, Any],
    outcome_summary: dict[str, Any],
) -> dict[str, Any]:
    price_metadata = settlement_metadata["price_metadata"]
    horizon_counts = settlement_metadata["horizon_settled_counts"]
    checks = {
        "source_ledger_loaded": source_metadata["source_rows"] > 0,
        "outcome_rows_equal_source_rows": (
            settlement_metadata["outcome_rows"] == source_metadata["source_rows"]
        ),
        "duplicate_observation_ids_zero": source_metadata["duplicate_observation_ids"] == 0,
        "source_sec13f_asof_valid": source_metadata["sec13f_source_asof_violations"] == 0,
        "hot_warehouse_exists": bool(price_metadata.get("exists")),
        "spy_benchmark_available": bool((price_metadata.get("benchmark_ranges") or {}).get("SPY")),
        "qqq_benchmark_available": bool((price_metadata.get("benchmark_ranges") or {}).get("QQQ")),
        "settled_1d_floor_met": int(horizon_counts.get("1") or 0) >= MIN_SETTLED_1D_ROWS,
        "settled_3d_floor_met": int(horizon_counts.get("3") or 0) >= MIN_SETTLED_3D_ROWS,
        "settled_5d_floor_met": int(horizon_counts.get("5") or 0) >= MIN_SETTLED_5D_ROWS,
        "strategy_behavior_unchanged": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    decision = (
        "accepted_measurement_repair_kova_sec13f_forward_outcome_settled"
        if not failed
        else "blocked_kova_sec13f_forward_outcome_settlement"
    )
    return {
        "passed": not failed,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_checks": checks,
        "measurement_repair": True,
        "alpha_ready": False,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "outcome_summary": {
            "horizon_settled_counts": horizon_counts,
            "outcome_status_counts": outcome_summary["outcome_status_counts"],
        },
        "lead_limitations": [
            "Measurement repair only; not a Kova/13F rank or threshold test.",
            "10d rows are expected to remain pending until enough future sessions exist.",
            "Any alpha promotion still requires a predeclared attribution or shared helper.",
        ],
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    prob = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1 if success else 0
    predicted_failures = list(prediction.get("main_failure_modes") or [])
    return {
        "actual_success": actual,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual) ** 2, 6),
        "predicted_failure_modes": predicted_failures,
        "failure_modes_observed": failed,
        "predicted_failure_mode_hit": any(mode in failed for mode in predicted_failures),
        "surprise_note": (
            "The hot warehouse supplied enough partial forward sessions to settle "
            "1d/3d/5d rows while 10d remains pending, matching the measurement-repair "
            "expectation."
            if success
            else "The outcome settlement surface did not meet the predeclared measurement floor."
        ),
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = summarize_baseline(BASELINE_RESULT)
    source_rows, source_metadata = load_source_rows()
    outcome_rows, settlement_metadata = settle_rows(source_rows)
    outcome_summary = summarize_outcomes(outcome_rows)
    gate4 = evaluate_gate4(source_metadata, settlement_metadata, outcome_summary)
    success = bool(gate4["passed"])
    status = "accepted_measurement_repair" if success else "blocked"
    decision = str(gate4["decision"])
    failed = list(gate4["failed_reasons"])
    scope_correction = {
        "corrected_before_runner_execution": True,
        "added_outcome_ledger_to_allowed_write_scope": True,
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": success,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, success, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260623-014": (
                    "Rejected pre-exp013 Kova RS/growth monotonicity. This run "
                    "does not retest RS/growth thresholds or score buckets."
                ),
                "exp-20260624-015": (
                    "Accepted local PIT SEC13F holdings fallback; this run uses "
                    "that repaired context from exp-20260624-016."
                ),
                "exp-20260624-016": (
                    "Accepted Kova SEC13F observation ledger but all rows remained "
                    "pending_forward_close. This run repairs that outcome blocker."
                ),
                "novelty_gate": (
                    "Reservation passed without override. Nearest 13F/Kova matches "
                    "were below the blocking threshold and this is measurement repair, "
                    "not a candidate-pool scan."
                ),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: settle exp-20260624-016 rows against the "
                "hot warehouse using next session open and 1/3/5/10-session close "
                "horizons, recording cash/SPY/QQQ replacement-value fields."
            ),
            "4_acceptance_standard": (
                "Accept as measurement repair only if source ledger rows load, "
                "duplicate IDs are zero, SEC13F source_asof remains PIT-valid, SPY/QQQ "
                "benchmarks exist, 1d/3d/5d settlement floors pass, and core strategy "
                "metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_ledger": repo_rel(SOURCE_LEDGER_JSONL),
            "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizons": list(HORIZONS),
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry_fill": "next available hot-warehouse session open with buy-side slippage",
            "exit_fill": "horizon exit session close with target-side sell slippage",
            "comparators": list(COMPARATORS),
            "min_settled_1d_rows": MIN_SETTLED_1D_ROWS,
            "min_settled_3d_rows": MIN_SETTLED_3D_ROWS,
            "min_settled_5d_rows": MIN_SETTLED_5D_ROWS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "passed": BASELINE_RESULT.exists(),
        },
        "gate2": {
            "dependencies_validated": success,
            "fields_checked": REQUIRED_SOURCE_FIELDS
            + [
                "planned_entry_date",
                "entry_date",
                "target_price",
                "forward_5d_return_pct",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "source_field_coverage": source_metadata["source_field_coverage"],
            "outcome_rows": outcome_summary["outcome_rows"],
            "planned_entry_date_rows": sum(1 for row in outcome_rows if row.get("planned_entry_date")),
            "entry_date_rows": sum(1 for row in outcome_rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: Kova observations are not executable candidates "
                "and this measurement repair uses fixed forward horizons, not "
                "target-price exits."
            ),
            "failed_reasons": failed,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "passed": baseline["survival_rate"] is not None and baseline["survival_rate"] >= 0.05,
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "outcome_rows_written": len(outcome_rows),
            "settled_1d_rows": settlement_metadata["horizon_settled_counts"].get("1"),
            "settled_3d_rows": settlement_metadata["horizon_settled_counts"].get("3"),
            "settled_5d_rows": settlement_metadata["horizon_settled_counts"].get("5"),
            "settled_10d_rows": settlement_metadata["horizon_settled_counts"].get("10"),
        },
        "source_metadata": source_metadata,
        "settlement_metadata": settlement_metadata,
        "outcome_summary": outcome_summary,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "replay_only": False,
            "live_ready": False,
            "parity_note": (
                "This experiment writes an experiment-owned outcome ledger only. "
                "It reads exp-20260624-016 and the hot OHLCV warehouse without "
                "modifying daily Kova snapshots, paper sleeve state, backtester, "
                "run.py, or any execution path."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-20260624-016 ledger had PIT-valid SEC13F rows but no "
                "forward outcome fields. The hot warehouse now supplies enough "
                "recent sessions to settle partial 1d/3d/5d cash/SPY/QQQ replacement "
                "values, while 10d remains pending as expected."
                if success
                else "The Kova SEC13F outcome surface could not meet the measurement "
                "floor; the failed checks show which data dependency is still missing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair to retune Kova 13F holder_count, total_value, "
                "RS, Companyfacts, top-N, hold, cooldown, notional, or allocator "
                "thresholds. This run only creates outcome fields."
            ),
            "new_evidence_required": (
                "Next alpha work must wait for enough closed 10d replacement-value "
                "rows or predeclare a separate observed-only sponsorship attribution. "
                "Promotion still requires a shared default-off helper and canonical "
                "Gate 1-4 evidence."
            ),
        },
        "scope_correction": scope_correction,
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_LEDGER_JSONL),
            repo_rel(OUTCOME_LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-016.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(OUTCOME_LEDGER_JSONL),
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
        "lean_quality_passed": success,
        "artifact": repo_rel(OUT_JSON),
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
    }
    return payload, outcome_rows


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
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
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "source_metadata": payload["source_metadata"],
        "settlement_metadata": payload["settlement_metadata"],
        "outcome_summary": {
            "outcome_rows": payload["outcome_summary"]["outcome_rows"],
            "ticker_count": payload["outcome_summary"]["ticker_count"],
            "asof_date_start": payload["outcome_summary"]["asof_date_start"],
            "asof_date_end": payload["outcome_summary"]["asof_date_end"],
            "asof_date_count": payload["outcome_summary"]["asof_date_count"],
            "outcome_status_counts": payload["outcome_summary"]["outcome_status_counts"],
            "horizons": payload["outcome_summary"]["horizons"],
            "sample_rows": payload["outcome_summary"]["sample_rows"][:2],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "scope_correction": payload["scope_correction"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "outcome_ledger": payload["outcome_ledger"],
        "log": payload["log"],
    }


def build_card(payload: dict[str, Any]) -> str:
    counts = payload["settlement_metadata"]["horizon_settled_counts"]
    horizons = payload["outcome_summary"]["horizons"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F forward outcome settlement",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Source rows: `{payload['source_metadata']['source_rows']}`",
            f"- Outcome rows: `{payload['outcome_summary']['outcome_rows']}`",
            f"- Settled 1d / 3d / 5d / 10d rows: `{counts.get('1')}` / `{counts.get('3')}` / `{counts.get('5')}` / `{counts.get('10')}`",
            f"- 5d mean replacement vs cash/SPY/QQQ: `{horizons['5']['replacement_value_vs_cash_usd']['mean']}` / `{horizons['5']['replacement_value_vs_spy_usd']['mean']}` / `{horizons['5']['replacement_value_vs_qqq_usd']['mean']}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
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
        OUTCOME_LEDGER_JSONL,
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
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], outcome_rows: list[dict[str, Any]]) -> None:
    write_jsonl(OUTCOME_LEDGER_JSONL, outcome_rows)
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "settlement_metadata": payload["settlement_metadata"],
        "outcome_summary": log_record["outcome_summary"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
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
            "outcome_ledger": repo_rel(OUTCOME_LEDGER_JSONL),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "scope_correction": payload["scope_correction"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, outcome_rows = build_payload()
    persist(payload, outcome_rows)
    counts = payload["settlement_metadata"]["horizon_settled_counts"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "source_rows": payload["source_metadata"]["source_rows"],
                "outcome_rows": payload["outcome_summary"]["outcome_rows"],
                "settled_1d_rows": counts.get("1"),
                "settled_3d_rows": counts.get("3"),
                "settled_5d_rows": counts.get("5"),
                "settled_10d_rows": counts.get("10"),
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
                "outcome_ledger": payload["outcome_ledger"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
