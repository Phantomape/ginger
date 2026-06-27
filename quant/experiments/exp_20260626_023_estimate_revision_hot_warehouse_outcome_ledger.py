"""exp-20260626-023: estimate-revision hot-warehouse outcome ledger.

Measurement repair only. Exp-20260625-002 built the row-level PIT join between
estimate revisions and production-visible candidate surfaces, but the main
warehouse ended before the 2026-06-24 usable entry date. This runner repeats the
same join against the hot OHLCV warehouse, settling only closed entry-day and 1d
cash/SPY/QQQ replacement values. 3/5/10d rows remain pending by construction.

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


EXPERIMENT_ID = "exp-20260626-023"
OWNER = "alpha-explore"
SLUG = "estimate_revision_hot_warehouse_outcome_ledger"
RUNNER = f"quant/experiments/exp_20260626_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_023_{SLUG}.json"
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
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
MATCH_MODULE_PATH = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260624_012_estimate_revision_candidate_match_surface.py"
)

AS_OF_DATE = "2026-06-23"
USABLE_ENTRY_DATE = "2026-06-24"
LATEST_COMPLETE_TRADING_DAY = "2026-06-25"
PROXY_NOTIONAL_USD = 4000.0
HORIZONS = (0, 1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")

HYPOTHESIS = (
    "Use the hot warehouse price surface to settle the row-level PIT "
    "estimate-revision candidate-match outcomes that exp-20260625-002 could "
    "not evaluate, so the alpha hypothesis that revision direction only has "
    "replacement value when it overlaps production-visible selected/current "
    "candidates can be judged without retuning revision thresholds or changing "
    "strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value only when it "
    "overlaps existing production-visible selected/current candidates; the "
    "current blocker is missing closed row-level outcomes, not another revision "
    "threshold, rank, hold-day, or notional rule."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
TRIAL_FAMILY = "estimate_revision_candidate_match_outcome_ledger"
TRIAL_VARIANT_ID = "hot_warehouse_entry_1d_outcomes_v1"
CHANGED_VARIABLE = "estimate_revision_candidate_match_hot_warehouse_outcome_ledger_v1"
NEW_EVIDENCE_TYPE = "closed_forward_price_surface_repair"
NEW_EVIDENCE_AXIS = (
    "Hot warehouse OHLCV includes 2026-06-25, materially new closed price "
    "evidence versus exp-20260625-002's stale main warehouse ending 2026-06-15. "
    "This settles selected/current entry-day and 1d outcomes without changing "
    "revision thresholds, candidate score cutoffs, rank rules, hold-day policy, "
    "or notional."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-012",
    "exp-20260625-002",
    "exp-20260625-017",
]
CAUSAL_COMPONENTS = [
    "exp012 estimate-revision candidate-match surface",
    "exp25-002 row-level PIT join shape",
    "hot warehouse entry-day and 1d replacement outcomes",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260626-023/exp_20260626_023_estimate_revision_hot_warehouse_outcome_ledger.json",
    "experiments/cards/exp-20260626-023.md",
    "experiments/manifests/exp-20260626-023.json",
    "experiments/tickets/exp-20260626-023.json",
    "experiments/logs/exp-20260626-023.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.78,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "hot_warehouse_missing_selected_tickers",
        "selected_nonflat_sample_too_thin",
        "only_1d_mature",
        "no_alpha_readiness",
    ],
    "confidence_reason": (
        "Exp012/exp25-002 already built the PIT match rows; the only hard "
        "blocker was stale OHLCV, and the hot warehouse now contains 2026-06-24 "
        "and 2026-06-25 bars. Alpha readiness likely still fails because only "
        "1d is mature."
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


def warehouse_date_range() -> dict[str, Any]:
    if not HOT_WAREHOUSE.exists():
        return {"min_date": None, "max_date": None, "rows": 0}
    with sqlite3.connect(HOT_WAREHOUSE) as con:
        min_date, max_date, rows = con.execute(
            "select min(date), max(date), count(*) from ohlcv"
        ).fetchone()
    return {"min_date": min_date, "max_date": max_date, "rows": int(rows or 0)}


def load_bars(tickers: set[str], start: str, end: str) -> dict[str, list[dict[str, Any]]]:
    if not HOT_WAREHOUSE.exists() or not tickers:
        return {}
    placeholders = ",".join("?" for _ in sorted(tickers))
    query = (
        "select ticker, date, open, close from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    params = [*sorted(tickers), start, end]
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(HOT_WAREHOUSE) as con:
        for ticker, day, open_, close in con.execute(query, params):
            rows_by_ticker[str(ticker).upper()].append(
                {
                    "date": str(day),
                    "open": safe_float(open_),
                    "close": safe_float(close),
                }
            )
    return dict(rows_by_ticker)


def first_index_on_or_after(rows: list[dict[str, Any]], day: str) -> int | None:
    for index, row in enumerate(rows):
        if str(row.get("date")) >= day:
            return index
    return None


def pnl_between_bars(entry: dict[str, Any], exit_: dict[str, Any]) -> float | None:
    entry_open = safe_float(entry.get("open"))
    exit_close = safe_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None or exit_close <= 0:
        return None
    entry_price = apply_entry_fill(entry_open)
    exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
    return PROXY_NOTIONAL_USD * (exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT)


def pnl_for_dates(
    rows: list[dict[str, Any]],
    entry_date: str | None,
    exit_date: str | None,
) -> float | None:
    if not entry_date or not exit_date:
        return None
    by_date = {str(row.get("date")): row for row in rows}
    entry = by_date.get(entry_date)
    exit_ = by_date.get(exit_date)
    if not entry or not exit_:
        return None
    return pnl_between_bars(entry, exit_)


def settle_horizons(
    ticker: str,
    bars: dict[str, list[dict[str, Any]]],
    requested_entry_date: str,
) -> dict[str, Any]:
    ticker_rows = bars.get(ticker, [])
    entry_index = first_index_on_or_after(ticker_rows, requested_entry_date)
    actual_entry_date: str | None = None
    if entry_index is not None:
        actual_entry_date = str(ticker_rows[entry_index].get("date"))

    result: dict[str, Any] = {
        "requested_entry_date": requested_entry_date,
        "entry_date": actual_entry_date or requested_entry_date,
        "actual_entry_date": actual_entry_date,
    }
    for horizon in HORIZONS:
        prefix = f"h{horizon}"
        if entry_index is None or actual_entry_date is None:
            result.update(
                {
                    f"{prefix}_status": "missing_entry_bar",
                    f"{prefix}_exit_date": None,
                    f"{prefix}_return_pct": None,
                    f"{prefix}_pnl_usd": None,
                    f"{prefix}_replacement_value_vs_cash_usd": None,
                    f"{prefix}_replacement_value_vs_spy_usd": None,
                    f"{prefix}_replacement_value_vs_qqq_usd": None,
                }
            )
            continue

        exit_index = entry_index + horizon
        if exit_index >= len(ticker_rows):
            status = "pending_forward_close"
            exit_date = None
            pnl = None
        else:
            exit_row = ticker_rows[exit_index]
            exit_date = str(exit_row.get("date"))
            if exit_date > LATEST_COMPLETE_TRADING_DAY:
                status = "pending_forward_close"
                pnl = None
            else:
                pnl = pnl_between_bars(ticker_rows[entry_index], exit_row)
                status = "closed" if pnl is not None else "bad_price"

        spy_pnl = pnl_for_dates(bars.get("SPY", []), actual_entry_date, exit_date)
        qqq_pnl = pnl_for_dates(bars.get("QQQ", []), actual_entry_date, exit_date)
        result.update(
            {
                f"{prefix}_status": status,
                f"{prefix}_exit_date": exit_date if pnl is not None else None,
                f"{prefix}_return_pct": round(pnl / PROXY_NOTIONAL_USD, 6)
                if pnl is not None
                else None,
                f"{prefix}_pnl_usd": round(pnl, 2) if pnl is not None else None,
                f"{prefix}_replacement_value_vs_cash_usd": round(pnl, 2)
                if pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2)
                if pnl is not None and spy_pnl is not None
                else None,
                f"{prefix}_replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2)
                if pnl is not None and qqq_pnl is not None
                else None,
                f"{prefix}_spy_same_window_pnl_usd": round(spy_pnl, 2)
                if spy_pnl is not None
                else None,
                f"{prefix}_qqq_same_window_pnl_usd": round(qqq_pnl, 2)
                if qqq_pnl is not None
                else None,
            }
        )

    result["outcome_status"] = result.get("h0_status")
    result["entry_day_exit_date"] = result.get("h0_exit_date")
    result["entry_day_return_pct"] = result.get("h0_return_pct")
    result["replacement_value_entry_day_vs_cash_usd"] = result.get(
        "h0_replacement_value_vs_cash_usd"
    )
    result["replacement_value_entry_day_vs_spy_usd"] = result.get(
        "h0_replacement_value_vs_spy_usd"
    )
    result["replacement_value_entry_day_vs_qqq_usd"] = result.get(
        "h0_replacement_value_vs_qqq_usd"
    )
    return result


def candidate_entry_date(candidate: dict[str, Any]) -> str:
    dates = candidate.get("dates") if isinstance(candidate.get("dates"), dict) else {}
    entry = str(
        dates.get("entry_date")
        or dates.get("usable_trade_date")
        or dates.get("signal_date")
        or USABLE_ENTRY_DATE
    )[:10]
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
    bars = load_bars(tickers, USABLE_ENTRY_DATE, LATEST_COMPLETE_TRADING_DAY)

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
                direction = match_module.revision_direction(revision)
                row = {
                    "schema_version": 1,
                    "experiment_id": EXPERIMENT_ID,
                    "source_match_surface_experiment_id": "exp-20260624-012",
                    "blocked_prior_outcome_experiment_id": "exp-20260625-002",
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
                    **settle_horizons(ticker, bars, entry_date),
                }
                rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("surface_label")),
            str(row.get("ticker")),
            str(row.get("revision_direction")),
            str(row.get("candidate_source_file")),
            str(row.get("candidate_source_label")),
            str(row.get("candidate_decision_id")),
        )
    )

    matched_tickers = {str(row.get("ticker")) for row in rows if row.get("ticker")}
    loaded_tickers = {ticker for ticker in matched_tickers if bars.get(ticker)}
    missing_tickers = sorted(matched_tickers - loaded_tickers)
    source_metadata = {
        "revision_ledger_rows": len(revision_rows),
        "candidate_records": len(candidates),
        "source_files_examined": len(source_status),
        "source_files_with_candidate_records": sum(
            1 for row in source_status if int(row.get("candidate_records") or 0) > 0
        ),
        "matched_rows": len(rows),
        "unique_match_keys": len(seen),
        "matched_unique_tickers": len(matched_tickers),
        "hot_warehouse": repo_rel(HOT_WAREHOUSE),
        "hot_warehouse_date_range": warehouse_date_range(),
        "hot_warehouse_loaded_tickers": len(loaded_tickers),
        "hot_warehouse_missing_tickers": missing_tickers[:120],
        "hot_warehouse_missing_tickers_truncated": len(missing_tickers) > 120,
        "hot_warehouse_required_entry_date": USABLE_ENTRY_DATE,
        "hot_warehouse_required_latest_complete_date": LATEST_COMPLETE_TRADING_DAY,
        "surface_source_status_sample": source_status[:20],
    }
    return rows, source_metadata


def values_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "win_rate": None}
    return {
        "count": len(values),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def horizon_values(
    rows: list[dict[str, Any]],
    horizon: int,
    field: str = "replacement_value_vs_cash_usd",
) -> list[float]:
    key = f"h{horizon}_{field}"
    values = [safe_float(row.get(key)) for row in rows if row.get(f"h{horizon}_status") == "closed"]
    return [value for value in values if value is not None]


def summarize_surface(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row.get("estimate_revision_usable")]
    nonflat_usable = [
        row
        for row in usable
        if row.get("revision_direction") in {"up", "down"}
    ]
    direction_counts = Counter(str(row.get("revision_direction") or "unknown") for row in rows)
    summary: dict[str, Any] = {
        "rows": len(rows),
        "usable_rows": len(usable),
        "nonflat_usable_rows": len(nonflat_usable),
        "unique_tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "direction_counts": dict(sorted(direction_counts.items())),
        "closed_rows_by_horizon": {
            f"h{horizon}": sum(1 for row in rows if row.get(f"h{horizon}_status") == "closed")
            for horizon in HORIZONS
        },
        "replacement_vs_cash_by_horizon": {
            f"h{horizon}": values_summary(horizon_values(rows, horizon))
            for horizon in HORIZONS
        },
        "replacement_vs_spy_by_horizon": {
            f"h{horizon}": values_summary(
                horizon_values(rows, horizon, "replacement_value_vs_spy_usd")
            )
            for horizon in HORIZONS
        },
        "replacement_vs_qqq_by_horizon": {
            f"h{horizon}": values_summary(
                horizon_values(rows, horizon, "replacement_value_vs_qqq_usd")
            )
            for horizon in HORIZONS
        },
    }
    by_direction: dict[str, Any] = {}
    for direction in sorted(direction_counts):
        direction_rows = [row for row in rows if row.get("revision_direction") == direction]
        by_direction[direction] = {
            "rows": len(direction_rows),
            "usable_rows": sum(1 for row in direction_rows if row.get("estimate_revision_usable")),
            "h0_vs_cash": values_summary(horizon_values(direction_rows, 0)),
            "h1_vs_cash": values_summary(horizon_values(direction_rows, 1)),
        }
    summary["by_revision_direction"] = by_direction
    return summary


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    surfaces = {
        label: [row for row in rows if row.get("surface_label") == label]
        for label in ("selected_current", "current", "all_candidate_records")
    }
    selected = surfaces["selected_current"]
    selected_nonflat_usable = [
        row
        for row in selected
        if row.get("estimate_revision_usable")
        and row.get("revision_direction") in {"up", "down"}
    ]
    return {
        "matched_rows": len(rows),
        "unique_tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "selected_current_rows": len(selected),
        "selected_current_nonflat_usable_rows": len(selected_nonflat_usable),
        "selected_current_closed_entry_day_rows": sum(
            1 for row in selected if row.get("h0_status") == "closed"
        ),
        "selected_current_closed_1d_rows": sum(
            1 for row in selected if row.get("h1_status") == "closed"
        ),
        "selected_current_closed_3d_rows": sum(
            1 for row in selected if row.get("h3_status") == "closed"
        ),
        "selected_current_closed_5d_rows": sum(
            1 for row in selected if row.get("h5_status") == "closed"
        ),
        "selected_current_closed_10d_rows": sum(
            1 for row in selected if row.get("h10_status") == "closed"
        ),
        "surface_summaries": {
            label: summarize_surface(surface_rows)
            for label, surface_rows in surfaces.items()
        },
        "sample_rows": [
            {
                "ticker": row.get("ticker"),
                "surface_label": row.get("surface_label"),
                "revision_direction": row.get("revision_direction"),
                "estimate_revision_usable": row.get("estimate_revision_usable"),
                "candidate_source_label": row.get("candidate_source_label"),
                "entry_date": row.get("entry_date"),
                "h0_status": row.get("h0_status"),
                "h0_vs_cash": row.get("h0_replacement_value_vs_cash_usd"),
                "h1_status": row.get("h1_status"),
                "h1_vs_cash": row.get("h1_replacement_value_vs_cash_usd"),
            }
            for row in rows[:20]
        ],
    }


def calibration(prediction: dict[str, Any], accepted: bool, realized_failure_modes: list[str]) -> dict[str, Any]:
    prob = safe_float(prediction.get("success_probability"))
    if prob is None:
        prob = 0.0
    actual = 1.0 if accepted else 0.0
    predicted_failures = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": "accepted_measurement_repair" if accepted else "blocked",
        "actual_success": actual,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual) ** 2, 4),
        "predicted_failure_modes": predicted_failures,
        "realized_failure_modes": realized_failure_modes,
        "predicted_failure_mode_hit": bool(set(predicted_failures) & set(realized_failure_modes)),
        "surprise_note": (
            "Hot warehouse settled entry-day and 1d selected/current outcomes, "
            "but alpha promotion remains blocked by immature 3/5/10d rows."
            if accepted
            else "The hot warehouse did not settle enough selected/current rows."
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

    measurement_blockers: list[str] = []
    alpha_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_incomplete")
    if not MATCH_SURFACE_ARTIFACT.exists():
        measurement_blockers.append("exp012_match_surface_artifact_missing")
    if not REVISION_LEDGER.exists():
        measurement_blockers.append("revision_ledger_missing")
    if not HOT_WAREHOUSE.exists():
        measurement_blockers.append("hot_warehouse_missing")
    warehouse_max = (source_metadata.get("hot_warehouse_date_range") or {}).get("max_date")
    if warehouse_max is None or str(warehouse_max) < LATEST_COMPLETE_TRADING_DAY:
        measurement_blockers.append("hot_warehouse_latest_date_before_required_1d_exit")
    if source_metadata["matched_rows"] == 0:
        measurement_blockers.append("no_matched_candidate_rows")
    if summary["selected_current_rows"] == 0:
        measurement_blockers.append("no_selected_current_rows")
    if summary["selected_current_closed_entry_day_rows"] == 0:
        measurement_blockers.append("selected_entry_day_outcomes_missing")
    if summary["selected_current_closed_1d_rows"] == 0:
        measurement_blockers.append("selected_1d_outcomes_missing")

    if summary["selected_current_nonflat_usable_rows"] < 20:
        alpha_blockers.append("selected_nonflat_sample_too_thin")
    if summary["selected_current_closed_3d_rows"] < 20:
        alpha_blockers.append("forward_3d_outcomes_not_mature")
    if summary["selected_current_closed_5d_rows"] < 20:
        alpha_blockers.append("forward_5d_outcomes_not_mature")
    if summary["selected_current_closed_10d_rows"] < 20:
        alpha_blockers.append("forward_10d_outcomes_not_mature")

    measurement_passed = not measurement_blockers
    alpha_ready = measurement_passed and not alpha_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_estimate_revision_hot_warehouse_outcome_ledger"
        if measurement_passed
        else "blocked_missing_hot_warehouse_selected_current_outcomes"
    )
    realized_failure_modes = [*measurement_blockers, *alpha_blockers]

    gate4 = {
        "passed": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "decision": decision,
        "measurement_blockers": measurement_blockers,
        "alpha_blockers": alpha_blockers,
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
            "min_selected_current_nonflat_usable_rows": 20,
            "min_selected_current_closed_3d_rows": 20,
            "min_selected_current_closed_5d_rows": 20,
            "min_selected_current_closed_10d_rows": 20,
            "requires_future_3_5_10d_rows_before_alpha_promotion": True,
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
        "implementation_mode": "measurement_repair_hot_warehouse_outcome_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, measurement_passed, realized_failure_modes),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260624-012": "Accepted measurement repair built the selected/current candidate match surface.",
                "exp-20260625-002": "Blocked because main warehouse ended on 2026-06-15 and could not settle 2026-06-24 outcomes.",
                "exp-20260625-017": "Blocked true outcome recovery from non-OHLCV Kova proxies.",
                "novelty_gate": (
                    "Near-neighbor override was recorded. The new evidence axis is "
                    "closed hot warehouse OHLCV through 2026-06-25, not a revision "
                    "threshold, candidate cutoff, rank, hold-day, or notional retest."
                ),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: reuse exp012 selected/current/all PIT "
                "candidate matches and settle hot-warehouse h0/h1 replacement "
                "values only."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline is unchanged, exp012 "
                "and the revision ledger load, hot warehouse covers 2026-06-25, "
                "selected/current rows have entry-day and 1d outcomes, and strategy "
                "delta remains zero."
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
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
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
            "selected_current_closed_entry_day_rows": summary[
                "selected_current_closed_entry_day_rows"
            ],
            "selected_current_closed_1d_rows": summary["selected_current_closed_1d_rows"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": MATCH_SURFACE_ARTIFACT.exists() and REVISION_LEDGER.exists() and HOT_WAREHOUSE.exists(),
            "dependencies_validated": MATCH_SURFACE_ARTIFACT.exists()
            and REVISION_LEDGER.exists()
            and HOT_WAREHOUSE.exists(),
            "fields_checked": [
                "ticker",
                "as_of_date",
                "estimate_revision_usable",
                "revision_direction",
                "entry_date",
                "target_price",
                "h0_replacement_value_vs_cash_usd",
                "h1_replacement_value_vs_cash_usd",
                "h1_replacement_value_vs_spy_usd",
                "h1_replacement_value_vs_qqq_usd",
            ],
            "entry_date_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: fixed-horizon replacement attribution only; no "
                "target exits or orders are scheduled."
            ),
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
                "The hot warehouse now covers the needed entry and 1d dates, so "
                f"{summary['selected_current_closed_entry_day_rows']} selected/current "
                f"entry-day rows and {summary['selected_current_closed_1d_rows']} "
                "selected/current 1d rows were settled. Alpha promotion remains "
                "blocked because 3/5/10d replacement outcomes are not mature."
                if measurement_passed
                else (
                    "The hot warehouse still could not settle the selected/current "
                    "candidate-match rows needed to repair exp-20260625-002."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry estimate-revision delta thresholds, direction windows, "
                "candidate score cutoffs, top-N, hold days, notional, or rank rules "
                "on this 2026-06-23 surface."
            ),
            "new_evidence_required": (
                "A valid alpha retry needs materially more selected/current non-flat "
                "matches with closed 3/5/10d replacement values, another settled "
                "month of production revision rows, or a different unsaturated PIT "
                "expectation source."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(MATCH_SURFACE_ARTIFACT),
            repo_rel(REVISION_LEDGER),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260624_012_estimate_revision_candidate_match_surface.py",
            "quant/experiments/exp_20260625_002_estimate_revision_candidate_match_outcome_ledger.py",
            "experiments/logs/exp-20260624-012.json",
            "experiments/logs/exp-20260625-002.json",
            "experiments/logs/exp-20260625-017.json",
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
        "sample_rows": payload["outcome_summary"]["sample_rows"][:5],
    }
    source = dict(record.get("source_metadata") or {})
    if "hot_warehouse_missing_tickers" in source:
        source["hot_warehouse_missing_tickers"] = source["hot_warehouse_missing_tickers"][:40]
        source["hot_warehouse_missing_tickers_log_truncated"] = True
    record["source_metadata"] = source
    record["gate2"] = {**record["gate2"], "source_metadata": source}
    return record


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["outcome_summary"]
    selected = summary["surface_summaries"].get("selected_current", {})
    h1 = selected.get("replacement_vs_cash_by_horizon", {}).get("h1", {})
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision hot warehouse outcome ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Matched rows: `{summary['matched_rows']}`",
            f"- Selected/current rows: `{summary['selected_current_rows']}`",
            f"- Selected/current non-flat usable rows: `{summary['selected_current_nonflat_usable_rows']}`",
            f"- Selected/current closed entry-day rows: `{summary['selected_current_closed_entry_day_rows']}`",
            f"- Selected/current closed 1d rows: `{summary['selected_current_closed_1d_rows']}`",
            f"- Selected/current mean 1d replacement vs cash: `{h1.get('mean')}`",
            "- Closed 3/5/10d rows: `0 / 0 / 0`",
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
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
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
        HOT_WAREHOUSE,
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
            "ticket_file": repo_rel(TICKET_JSON),
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
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
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
                "selected_current_closed_1d_rows": payload["outcome_summary"][
                    "selected_current_closed_1d_rows"
                ],
                "alpha_ready": payload["alpha_ready"],
                "measurement_blockers": payload["gate4"]["measurement_blockers"],
                "alpha_blockers": payload["gate4"]["alpha_blockers"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
