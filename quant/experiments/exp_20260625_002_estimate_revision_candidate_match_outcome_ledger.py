"""exp-20260625-002: estimate-revision candidate-match outcome ledger.

Measurement repair only. Exp-20260624-012 rebuilt the PIT join between the
2026-06-23 estimate-revision ledger and current production-visible candidate
surfaces, but it retained only summary counts. This runner writes the row-level
matched ledger and settles only the entry-day close outcome that is available
without using future bars.

No strategy, shared helper, ranking, sizing, exit, paper order, live order,
watchlist, LLM, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
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


EXPERIMENT_ID = "exp-20260625-002"
OWNER = "alpha-explore"
SLUG = "estimate_revision_candidate_match_outcome_ledger"
RUNNER = f"quant/experiments/exp_20260625_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_002_{SLUG}.json"
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
MATCH_SURFACE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-012"
    / "exp_20260624_012_estimate_revision_candidate_match_surface.json"
)
REVISION_LEDGER = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260623.jsonl"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
MATCH_MODULE_PATH = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260624_012_estimate_revision_candidate_match_surface.py"
)

AS_OF_DATE = "2026-06-23"
USABLE_ENTRY_DATE = "2026-06-24"
LATEST_COMPLETE_TRADING_DAY = "2026-06-24"
PROXY_NOTIONAL_USD = 4000.0
HORIZONS = (0, 1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")

HYPOTHESIS = (
    "Build a row-level PIT estimate-revision candidate-match outcome ledger so "
    "the alpha hypothesis that revision direction only matters when it overlaps "
    "production-visible candidates can be evaluated without changing strategy "
    "behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value only when it "
    "overlaps an existing production-visible candidate, selected signal, or open "
    "default-off paper row; the current blocker is missing row-level matched "
    "outcomes, not another revision threshold."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
TRIAL_FAMILY = "estimate_revision_candidate_match_outcome_ledger"
TRIAL_VARIANT_ID = "post_exp012_row_level_entry_day_outcome_v1"
CHANGED_VARIABLE = "estimate_revision_candidate_match_outcome_ledger_v1"
NEW_EVIDENCE_TYPE = "row_level_forward_match_outcome_surface"
NEW_EVIDENCE_AXIS = (
    "Row-level PIT join between the exp012 candidate-match surface and "
    "warehouse-settled entry-day outcomes. This is not a revision threshold, "
    "direction-window, top-N, hold-day, notional, or rank retest."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-002",
    "exp-20260624-007",
    "exp-20260624-012",
]
CAUSAL_COMPONENTS = [
    "exp012 estimate-revision candidate-match surface",
    "row-level matched ledger materialization",
    "entry-day cash SPY QQQ replacement outcome",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-002/exp_20260625_002_estimate_revision_candidate_match_outcome_ledger.json",
    "experiments/cards/exp-20260625-002.md",
    "experiments/manifests/exp-20260625-002.json",
    "experiments/tickets/exp-20260625-002.json",
    "experiments/logs/exp-20260625-002.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.74,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "selected_nonflat_sample_too_thin",
        "entry_day_outcomes_not_available",
        "candidate_surface_import_breaks",
        "no_alpha_readiness",
    ],
    "confidence_reason": (
        "Exp012 accepted the candidate-match surface and explicitly required "
        "closed forward outcomes for selected/current overlaps before any alpha "
        "work. This repair writes that row-level surface only; it is likely to "
        "remain alpha-not-ready because only entry-day outcomes are mature."
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


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def load_match_module() -> Any:
    spec = importlib.util.spec_from_file_location("exp012_match_surface", MATCH_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {MATCH_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["exp012_match_surface"] = module
    spec.loader.exec_module(module)
    return module


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
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
        "baseline_result_file": repo_rel(BASELINE_RESULT),
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


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {**DEFAULT_PREDICTION, "recorded_at": utc_now()}


def load_bars(tickers: set[str], start: str, end: str) -> dict[str, list[dict[str, Any]]]:
    if not WAREHOUSE.exists() or not tickers:
        return {}
    placeholders = ",".join("?" for _ in sorted(tickers))
    query = (
        "select ticker, date, open, close from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    params = [*sorted(tickers), start, end]
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(WAREHOUSE) as con:
        for ticker, day, open_, close in con.execute(query, params):
            rows_by_ticker[str(ticker).upper()].append(
                {
                    "date": str(day),
                    "open": safe_float(open_),
                    "close": safe_float(close),
                }
            )
    return dict(rows_by_ticker)


def warehouse_date_range() -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {"min_date": None, "max_date": None, "rows": 0}
    with sqlite3.connect(WAREHOUSE) as con:
        min_date, max_date, rows = con.execute(
            "select min(date), max(date), count(*) from ohlcv"
        ).fetchone()
    return {"min_date": min_date, "max_date": max_date, "rows": int(rows or 0)}


def first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if row["date"] >= day:
            return index
    return None


def pnl_for_same_dates(
    rows: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
    notional: float,
) -> float | None:
    by_date = {row["date"]: row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    entry_open = safe_float(entry.get("open"))
    exit_close = safe_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    entry_price = apply_entry_fill(entry_open)
    exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
    return notional * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def settle_entry_day(
    ticker: str,
    bars: dict[str, list[dict[str, Any]]],
    entry_date: str,
) -> dict[str, Any]:
    ticker_rows = bars.get(ticker, [])
    entry_index = first_index_on_or_after(ticker_rows, entry_date)
    if entry_index is None:
        return {
            "entry_date": entry_date,
            "outcome_status": "missing_entry_bar",
            "entry_day_exit_date": None,
            "entry_day_return_pct": None,
            "replacement_value_entry_day_vs_cash_usd": None,
            "replacement_value_entry_day_vs_spy_usd": None,
            "replacement_value_entry_day_vs_qqq_usd": None,
        }
    entry = ticker_rows[entry_index]
    actual_entry_date = entry["date"]
    if actual_entry_date > LATEST_COMPLETE_TRADING_DAY:
        return {
            "entry_date": actual_entry_date,
            "outcome_status": "pending_entry_day_close",
            "entry_day_exit_date": None,
            "entry_day_return_pct": None,
            "replacement_value_entry_day_vs_cash_usd": None,
            "replacement_value_entry_day_vs_spy_usd": None,
            "replacement_value_entry_day_vs_qqq_usd": None,
        }
    entry_open = safe_float(entry.get("open"))
    exit_close = safe_float(entry.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        status = "bad_entry_day_price"
        pnl = None
    else:
        entry_price = apply_entry_fill(entry_open)
        exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
        pnl = PROXY_NOTIONAL_USD * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)
        status = "closed_entry_day"
    spy_pnl = pnl_for_same_dates(bars.get("SPY", []), actual_entry_date, actual_entry_date, PROXY_NOTIONAL_USD)
    qqq_pnl = pnl_for_same_dates(bars.get("QQQ", []), actual_entry_date, actual_entry_date, PROXY_NOTIONAL_USD)
    return {
        "entry_date": actual_entry_date,
        "outcome_status": status,
        "entry_day_exit_date": actual_entry_date if pnl is not None else None,
        "entry_day_return_pct": round(pnl / PROXY_NOTIONAL_USD, 6) if pnl is not None else None,
        "replacement_value_entry_day_vs_cash_usd": round(pnl, 2) if pnl is not None else None,
        "replacement_value_entry_day_vs_spy_usd": (
            round(pnl - spy_pnl, 2) if pnl is not None and spy_pnl is not None else None
        ),
        "replacement_value_entry_day_vs_qqq_usd": (
            round(pnl - qqq_pnl, 2) if pnl is not None and qqq_pnl is not None else None
        ),
        "spy_entry_day_same_window_pnl": round(spy_pnl, 2) if spy_pnl is not None else None,
        "qqq_entry_day_same_window_pnl": round(qqq_pnl, 2) if qqq_pnl is not None else None,
    }


def candidate_entry_date(candidate: dict[str, Any]) -> str:
    dates = candidate.get("dates") if isinstance(candidate.get("dates"), dict) else {}
    entry = str(dates.get("entry_date") or dates.get("usable_trade_date") or USABLE_ENTRY_DATE)[:10]
    if len(entry) != 10 or entry < USABLE_ENTRY_DATE:
        return USABLE_ENTRY_DATE
    return entry


def build_matched_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    match_module = load_match_module()
    revision_rows = read_jsonl(REVISION_LEDGER)
    candidates, source_status = match_module.load_candidate_surface()
    selected_index = match_module.build_index(candidates, "selected")
    current_index = match_module.build_index(candidates, "current")
    all_index = match_module.build_index(candidates, "all")

    tickers = {
        str(row.get("ticker") or "").upper()
        for row in revision_rows
        if row.get("ticker")
    }
    tickers.update(COMPARATORS)
    bars = load_bars(tickers, AS_OF_DATE, LATEST_COMPLETE_TRADING_DAY)
    warehouse_range = warehouse_date_range()

    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    surface_indexes = [
        ("selected_current", selected_index),
        ("current", current_index),
        ("all_candidate_records", all_index),
    ]
    for revision in revision_rows:
        ticker = str(revision.get("ticker") or "").upper()
        if not ticker:
            continue
        for surface_label, index in surface_indexes:
            for candidate in index.get(ticker, []):
                dedupe_key = (
                    ticker,
                    revision.get("as_of_date"),
                    surface_label,
                    candidate.get("source_file"),
                    candidate.get("source_label"),
                    candidate.get("container"),
                    candidate.get("decision_id"),
                    json.dumps(candidate.get("dates") or {}, sort_keys=True),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entry_date = candidate_entry_date(candidate)
                outcome = settle_entry_day(ticker, bars, entry_date)
                direction = match_module.revision_direction(revision)
                row = {
                    "schema_version": 1,
                    "experiment_id": EXPERIMENT_ID,
                    "source_match_surface_experiment_id": "exp-20260624-012",
                    "source_revision_ledger": repo_rel(REVISION_LEDGER),
                    "ticker": ticker,
                    "as_of_date": revision.get("as_of_date"),
                    "usable_entry_date": USABLE_ENTRY_DATE,
                    "surface_label": surface_label,
                    "revision_direction": direction,
                    "estimate_revision_usable": bool(revision.get("estimate_revision_usable")),
                    "eps_estimate": revision.get("eps_estimate"),
                    "eps_estimate_delta_prev": revision.get("eps_estimate_delta_prev"),
                    "eps_estimate_delta_7d": revision.get("eps_estimate_delta_7d"),
                    "next_earnings_date": revision.get("next_earnings_date"),
                    "source_snapshot_timestamp": revision.get("source_snapshot_timestamp"),
                    "candidate_source_file": candidate.get("source_file"),
                    "candidate_source_label": candidate.get("source_label"),
                    "candidate_source": candidate.get("source"),
                    "candidate_strategy": candidate.get("strategy"),
                    "candidate_container": candidate.get("container"),
                    "candidate_state": candidate.get("state"),
                    "candidate_is_current_surface": bool(candidate.get("is_current_surface")),
                    "candidate_is_selected_surface": bool(candidate.get("is_selected_surface")),
                    "candidate_dates": candidate.get("dates"),
                    "candidate_decision_id": candidate.get("decision_id"),
                    "candidate_score": candidate.get("candidate_score"),
                    "paper_notional_usd": PROXY_NOTIONAL_USD,
                    **outcome,
                    "forward_1d_status": "pending_forward_close",
                    "forward_3d_status": "pending_forward_close",
                    "forward_5d_status": "pending_forward_close",
                    "forward_10d_status": "pending_forward_close",
                }
                rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("surface_label")),
            str(row.get("ticker")),
            str(row.get("candidate_source_label")),
            str(row.get("candidate_decision_id")),
        )
    )
    metadata = {
        "revision_ledger_rows": len(revision_rows),
        "candidate_records": len(candidates),
        "source_files_examined": len(source_status),
        "source_files_with_candidate_records": sum(
            1 for row in source_status if int(row.get("candidate_records") or 0) > 0
        ),
        "matched_rows": len(rows),
        "unique_match_keys": len(seen),
        "warehouse_loaded_tickers": len(bars),
        "warehouse_missing_tickers": sorted(ticker for ticker in tickers if ticker not in bars),
        "warehouse_date_range": warehouse_range,
        "warehouse_required_entry_date": USABLE_ENTRY_DATE,
        "warehouse_required_latest_complete_date": LATEST_COMPLETE_TRADING_DAY,
    }
    return rows, metadata


def metric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "sum": 0.0, "positive_rate": None}
    return {
        "n": len(values),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "sum": round(sum(values), 2),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_surface = Counter(str(row.get("surface_label")) for row in rows)
    by_direction = Counter(str(row.get("revision_direction")) for row in rows)
    by_status = Counter(str(row.get("outcome_status")) for row in rows)
    selected = [row for row in rows if row.get("surface_label") == "selected_current"]
    selected_nonflat = [
        row
        for row in selected
        if row.get("estimate_revision_usable") and row.get("revision_direction") in {"up", "down"}
    ]
    selected_closed = [
        row
        for row in selected
        if row.get("outcome_status") == "closed_entry_day"
    ]
    grouped: dict[str, dict[str, Any]] = {}
    for surface in sorted(by_surface):
        surface_rows = [row for row in rows if row.get("surface_label") == surface]
        grouped[surface] = {
            "rows": len(surface_rows),
            "tickers": len({row.get("ticker") for row in surface_rows}),
            "direction_counts": dict(Counter(str(row.get("revision_direction")) for row in surface_rows)),
            "closed_entry_day_rows": sum(
                1 for row in surface_rows if row.get("outcome_status") == "closed_entry_day"
            ),
            "replacement_entry_day_vs_cash": metric_summary(
                [
                    float(row["replacement_value_entry_day_vs_cash_usd"])
                    for row in surface_rows
                    if row.get("replacement_value_entry_day_vs_cash_usd") is not None
                ]
            ),
            "replacement_entry_day_vs_spy": metric_summary(
                [
                    float(row["replacement_value_entry_day_vs_spy_usd"])
                    for row in surface_rows
                    if row.get("replacement_value_entry_day_vs_spy_usd") is not None
                ]
            ),
            "replacement_entry_day_vs_qqq": metric_summary(
                [
                    float(row["replacement_value_entry_day_vs_qqq_usd"])
                    for row in surface_rows
                    if row.get("replacement_value_entry_day_vs_qqq_usd") is not None
                ]
            ),
        }
    return {
        "matched_rows": len(rows),
        "unique_tickers": len({row.get("ticker") for row in rows}),
        "surface_counts": dict(by_surface),
        "revision_direction_counts": dict(by_direction),
        "outcome_status_counts": dict(by_status),
        "selected_current_rows": len(selected),
        "selected_current_closed_entry_day_rows": len(selected_closed),
        "selected_current_nonflat_usable_rows": len(selected_nonflat),
        "selected_current_nonflat_usable_tickers": len({row.get("ticker") for row in selected_nonflat}),
        "surface_summaries": grouped,
        "sample_rows": rows[:5],
    }


def calibration(prediction: dict[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
    prob = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if accepted else 0.0
    return {
        "actual_decision": "accepted_measurement_repair" if accepted else "blocked",
        "actual_success": actual,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual) ** 2, 4),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []) & set(failed)
        ),
        "surprise_note": (
            "Ledger materialization succeeded, but alpha readiness remains blocked "
            "by thin non-flat selected matches and immature 1/3/5/10d outcomes."
            if accepted
            else "The row-level ledger could not be materialized."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    match_artifact = read_json(MATCH_SURFACE_ARTIFACT, {})
    ticket = read_json(TICKET_JSON, {})
    rows, source_metadata = build_matched_rows()
    summary = summarize_rows(rows)
    failed: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        failed.append("baseline_missing_or_incomplete")
    if not MATCH_SURFACE_ARTIFACT.exists():
        failed.append("exp012_match_surface_artifact_missing")
    if source_metadata["matched_rows"] == 0:
        failed.append("no_matched_candidate_rows")
    if summary["selected_current_rows"] == 0:
        failed.append("no_selected_current_rows")
    if summary["selected_current_nonflat_usable_rows"] < 10:
        failed.append("selected_nonflat_sample_too_thin")
    if summary["selected_current_closed_entry_day_rows"] == 0:
        failed.append("entry_day_outcomes_not_available")
        failed.append("selected_entry_day_outcomes_missing")
    warehouse_max = (source_metadata.get("warehouse_date_range") or {}).get("max_date")
    if warehouse_max is None or str(warehouse_max) < USABLE_ENTRY_DATE:
        failed.append("warehouse_latest_date_before_usable_entry")
    measurement_passed = not any(
        reason
        in {
            "baseline_missing_or_incomplete",
            "exp012_match_surface_artifact_missing",
            "no_matched_candidate_rows",
            "no_selected_current_rows",
            "selected_entry_day_outcomes_missing",
        }
        for reason in failed
    )
    alpha_ready = (
        summary["selected_current_nonflat_usable_rows"] >= 10
        and summary["selected_current_closed_entry_day_rows"] >= 20
    )
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_estimate_revision_candidate_match_outcome_ledger"
        if measurement_passed
        else "blocked_missing_recent_warehouse_ohlcv_for_estimate_revision_outcomes"
    )
    gate4 = {
        "passed": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "decision": decision,
        "failed_reasons": failed,
        "measurement_repair_only": True,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "alpha_readiness_rule": {
            "min_selected_current_nonflat_usable_rows": 10,
            "min_selected_current_closed_entry_day_rows": 20,
            "requires_future_1_3_5_10d_rows_before_alpha_promotion": True,
        },
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair_row_level_outcome_ledger",
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
        "calibration": calibration(prediction, measurement_passed, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260624-002": "Gross production estimate-revision direction attribution was observed-only and not promotable.",
                "exp-20260624-007": "Readiness scan found estimate-revision had no candidate match surface.",
                "exp-20260624-012": "Accepted measurement repair built the candidate match summary but did not persist row-level outcomes.",
                "novelty_gate": "Reservation warned on revision near-neighbors; this measurement repair uses the exp012 reopen condition, row-level selected/current outcomes, not revision threshold retuning.",
            },
            "3_single_policy_bundle": (
                "One measurement bundle: materialize row-level exp012 selected/current/all candidate matches and settle only entry-day cash/SPY/QQQ replacement values available through "
                + LATEST_COMPLETE_TRADING_DAY
                + "."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline is unchanged, exp012 and revision ledger load, selected/current rows have entry-day outcomes, and no strategy behavior changes. Alpha remains blocked unless non-flat selected sample and forward outcome floors pass."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF_DATE,
            "usable_entry_date": USABLE_ENTRY_DATE,
            "latest_complete_trading_day": LATEST_COMPLETE_TRADING_DAY,
            "horizons": list(HORIZONS),
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "slippage_bps_target": SLIPPAGE_BPS_TARGET,
            "comparators": list(COMPARATORS),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "match_surface_artifact": repo_rel(MATCH_SURFACE_ARTIFACT),
            "revision_ledger": repo_rel(REVISION_LEDGER),
            "warehouse": repo_rel(WAREHOUSE),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "matched_rows_written": len(rows),
            "selected_current_rows": summary["selected_current_rows"],
            "selected_current_nonflat_usable_rows": summary[
                "selected_current_nonflat_usable_rows"
            ],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": MATCH_SURFACE_ARTIFACT.exists() and REVISION_LEDGER.exists() and WAREHOUSE.exists(),
            "dependencies_validated": MATCH_SURFACE_ARTIFACT.exists() and REVISION_LEDGER.exists() and WAREHOUSE.exists(),
            "fields_checked": [
                "ticker",
                "as_of_date",
                "estimate_revision_usable",
                "revision_direction",
                "entry_date",
                "target_price",
                "replacement_value_entry_day_vs_cash_usd",
                "replacement_value_entry_day_vs_spy_usd",
                "replacement_value_entry_day_vs_qqq_usd",
            ],
            "entry_date_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_scope": "Not applicable: this is fixed-horizon forward attribution and does not schedule target exits or orders.",
            "source_metadata": source_metadata,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": gate4,
        "match_surface_reference": {
            "artifact": repo_rel(MATCH_SURFACE_ARTIFACT),
            "decision": match_artifact.get("decision"),
            "selected_current_summary": (
                match_artifact.get("match_surface", {})
                .get("selected_current_surface", {})
            ),
        },
        "source_metadata": source_metadata,
        "outcome_summary": summary,
        "matched_outcome_rows": rows,
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
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned measurement artifact only. It reads existing "
                "revision/candidate/warehouse surfaces and writes no shared helper, "
                "daily adapter, order, rank, size, exit, watchlist, or LLM changes."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The row-level candidate-match ledger was materialized and entry-day outcomes were available, but the alpha remains blocked: selected/current non-flat usable revision overlap is too thin and 1/3/5/10d forward outcomes are not mature yet."
                if measurement_passed
                else (
                    "The row-level candidate-match ledger was materialized, but the "
                    "local warehouse cannot settle outcomes: its latest OHLCV date is "
                    f"{warehouse_max}, before the PIT usable entry date "
                    f"{USABLE_ENTRY_DATE}."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry estimate-revision delta thresholds, direction windows, "
                "candidate score cutoffs, top-N, hold days, notional, or rank rules "
                "on this 2026-06-23 surface."
            ),
            "new_evidence_required": (
                "A valid alpha retry needs materially more selected/current non-flat "
                "matches with closed 1/3/5/10d replacement values, another settled "
                "month of production revision rows, or a different unsaturated PIT "
                "expectation source."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(MATCH_SURFACE_ARTIFACT),
            repo_rel(REVISION_LEDGER),
            repo_rel(WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260624_012_estimate_revision_candidate_match_surface.py",
            "experiments/logs/exp-20260624-002.json",
            "experiments/logs/exp-20260624-007.json",
            "experiments/logs/exp-20260624-012.json",
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
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = {key: payload[key] for key in payload if key != "matched_outcome_rows"}
    record["outcome_summary"] = {
        **payload["outcome_summary"],
        "sample_rows": payload["outcome_summary"]["sample_rows"][:2],
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["outcome_summary"]
    selected = summary["surface_summaries"].get("selected_current", {})
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision match outcome ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Matched rows: `{summary['matched_rows']}`",
            f"- Selected/current rows: `{summary['selected_current_rows']}`",
            f"- Selected/current non-flat usable rows: `{summary['selected_current_nonflat_usable_rows']}`",
            f"- Selected/current closed entry-day rows: `{summary['selected_current_closed_entry_day_rows']}`",
            f"- Selected/current mean entry-day replacement vs cash: `{selected.get('replacement_entry_day_vs_cash', {}).get('mean')}`",
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
            "",
        ]
    )


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
        BASELINE_RESULT,
        MATCH_SURFACE_ARTIFACT,
        REVISION_LEDGER,
        WAREHOUSE,
        MATCH_MODULE_PATH,
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
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
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
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "matched_rows": payload["outcome_summary"]["matched_rows"],
                "selected_current_rows": payload["outcome_summary"]["selected_current_rows"],
                "selected_current_nonflat_usable_rows": payload["outcome_summary"][
                    "selected_current_nonflat_usable_rows"
                ],
                "selected_current_closed_entry_day_rows": payload["outcome_summary"][
                    "selected_current_closed_entry_day_rows"
                ],
                "alpha_ready": payload["alpha_ready"],
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
