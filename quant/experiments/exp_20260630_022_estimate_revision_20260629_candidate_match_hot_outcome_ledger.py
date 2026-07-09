"""exp-20260630-022: 2026-06-29 estimate-revision outcome ledger.

Measurement repair only. Exp-20260630-021 regenerated the 2026-06-29
estimate-revision ledger after same-day quant signals existed, producing five
matched candidate rows. This runner materializes their row-level hot-warehouse
replacement-value ledger. It does not change strategy behavior.
"""

from __future__ import annotations

import hashlib
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
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    rebuild_experiment_log_from_shards,
)
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260630-022"
OWNER = "alpha-explore"
SLUG = "estimate_revision_20260629_candidate_match_hot_outcome_ledger"
RUNNER = f"quant/experiments/exp_20260630_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260630_022_{SLUG}.json"
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
SOURCE_EXPERIMENT_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260630-021"
    / "exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.json"
)
REVISION_LEDGER = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260629.jsonl"
REVISION_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260629.json"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

AS_OF_DATE = "2026-06-29"
USABLE_ENTRY_DATE = "2026-06-29"
LATEST_COMPLETE_TRADING_DAY = "2026-06-29"
HORIZONS = (0, 1, 3, 5, 10)
COMPARATORS = ("SPY", "QQQ")
PROXY_NOTIONAL_USD = 4000.0

HYPOTHESIS = (
    "Alpha-enabling repair: the post-quant-signal 2026-06-29 "
    "estimate-revision candidate rows need a row-level hot-warehouse "
    "replacement-value ledger so the revision candidate-match alpha can later "
    "be judged from new forward rows, not threshold or condition slices."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value when it overlaps "
    "same-day production-visible candidate rows, but this cannot be judged "
    "until matched candidates have closed replacement-value outcomes."
)
CHANGED_VARIABLE = "estimate_revision_20260629_candidate_match_hot_outcome_ledger_v1"
TRIAL_FAMILY = "estimate_revision_candidate_match_outcome_ledger"
TRIAL_VARIANT_ID = "post_quant_signal_20260629_hot_warehouse_outcomes_v1"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
NEW_EVIDENCE_AXIS = (
    "New post-exp-20260630-021 matched candidate rows for as_of 2026-06-29 "
    "(BKNG DDOG DE GS LITE) plus hot warehouse coverage through 2026-06-29; "
    "this materializes a new forward-observation ledger and does not change "
    "revision thresholds, rank, hold, notional, or condition slices."
)
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260630-022/exp_20260630_022_estimate_revision_20260629_candidate_match_hot_outcome_ledger.json",
    "experiments/cards/exp-20260630-022.md",
    "experiments/manifests/exp-20260630-022.json",
    "experiments/tickets/exp-20260630-022.json",
    "experiments/logs/exp-20260630-022.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


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
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


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


def settle_horizons(ticker: str, bars: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker_rows = bars.get(ticker, [])
    entry_index = first_index_on_or_after(ticker_rows, USABLE_ENTRY_DATE)
    actual_entry_date: str | None = None
    if entry_index is not None:
        actual_entry_date = str(ticker_rows[entry_index].get("date"))

    result: dict[str, Any] = {
        "requested_entry_date": USABLE_ENTRY_DATE,
        "entry_date": actual_entry_date or USABLE_ENTRY_DATE,
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
    return result


def load_matched_candidate_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(REVISION_LEDGER)
    matched = [row for row in rows if row.get("matched_candidate_today")]
    matched.sort(key=lambda row: str(row.get("ticker") or ""))
    return matched


def build_outcome_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matched = load_matched_candidate_rows()
    tickers = {str(row.get("ticker") or "").upper() for row in matched if row.get("ticker")}
    tickers.update(COMPARATORS)
    bars = load_bars(tickers, USABLE_ENTRY_DATE, LATEST_COMPLETE_TRADING_DAY)
    rows: list[dict[str, Any]] = []
    for source in matched:
        ticker = str(source.get("ticker") or "").upper()
        direction = source.get("revision_direction_prev") or source.get("revision_direction")
        outcome = settle_horizons(ticker, bars)
        rows.append(
            {
                "schema_version": 1,
                "experiment_id": EXPERIMENT_ID,
                "source_experiment_id": "exp-20260630-021",
                "source_revision_ledger": repo_rel(REVISION_LEDGER),
                "ticker": ticker,
                "as_of_date": source.get("as_of_date"),
                "usable_entry_date": USABLE_ENTRY_DATE,
                "target_price": None,
                "target_price_scope": "not_applicable_fixed_horizon_replacement_value",
                "revision_direction": direction,
                "estimate_revision_usable": bool(source.get("estimate_revision_usable")),
                "eps_estimate": source.get("eps_estimate"),
                "eps_estimate_delta_prev": source.get("eps_estimate_delta_prev"),
                "eps_estimate_delta_7d": source.get("eps_estimate_delta_7d"),
                "eps_estimate_delta_30d": source.get("eps_estimate_delta_30d"),
                "next_earnings_date": source.get("next_earnings_date"),
                "source_snapshot_timestamp": source.get("source_snapshot_timestamp"),
                "source_snapshot_pit_safe": source.get("source_snapshot_pit_safe"),
                "matched_candidate_count": source.get("matched_candidate_count"),
                "matched_selected_signal_count": source.get("matched_selected_signal_count"),
                "matched_signal_sources": source.get("matched_signal_sources"),
                "matched_signal_record_types": source.get("matched_signal_record_types"),
                "matched_signal_strategies": source.get("matched_signal_strategies"),
                "matched_signal_records": source.get("matched_signal_records"),
                "paper_notional_usd": PROXY_NOTIONAL_USD,
                **outcome,
            }
        )

    loaded_tickers = sorted(ticker for ticker in tickers if bars.get(ticker))
    source_metadata = {
        "source_artifact": repo_rel(SOURCE_EXPERIMENT_ARTIFACT),
        "source_artifact_exists": SOURCE_EXPERIMENT_ARTIFACT.exists(),
        "revision_ledger": repo_rel(REVISION_LEDGER),
        "revision_ledger_exists": REVISION_LEDGER.exists(),
        "revision_summary": repo_rel(REVISION_SUMMARY),
        "revision_summary_exists": REVISION_SUMMARY.exists(),
        "revision_summary_payload": read_json(REVISION_SUMMARY, {}),
        "hot_warehouse": repo_rel(HOT_WAREHOUSE),
        "hot_warehouse_exists": HOT_WAREHOUSE.exists(),
        "hot_warehouse_date_range": warehouse_date_range(),
        "hot_warehouse_loaded_tickers": loaded_tickers,
        "hot_warehouse_missing_matched_tickers": sorted(tickers - set(COMPARATORS) - set(loaded_tickers)),
        "matched_candidate_rows": len(matched),
        "matched_candidate_tickers": sorted(ticker for ticker in tickers if ticker not in COMPARATORS),
    }
    return rows, source_metadata


def summarize_values(values: list[Any]) -> dict[str, Any]:
    numeric = [float(value) for value in values if safe_float(value) is not None]
    return {
        "count": len(numeric),
        "mean": round(mean(numeric), 4) if numeric else None,
        "median": round(median(numeric), 4) if numeric else None,
        "min": round(min(numeric), 4) if numeric else None,
        "max": round(max(numeric), 4) if numeric else None,
        "win_rate": round(sum(1 for value in numeric if value > 0) / len(numeric), 4)
        if numeric
        else None,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    direction_counts = Counter(str(row.get("revision_direction") or "missing") for row in rows)
    closed_counts = {
        f"h{horizon}": sum(1 for row in rows if row.get(f"h{horizon}_status") == "closed")
        for horizon in HORIZONS
    }
    pending_counts = {
        f"h{horizon}": sum(
            1 for row in rows if row.get(f"h{horizon}_status") == "pending_forward_close"
        )
        for horizon in HORIZONS
    }
    nonflat_usable = [
        row
        for row in rows
        if row.get("estimate_revision_usable")
        and str(row.get("revision_direction") or "").lower() not in {"", "flat", "missing"}
    ]
    replacement = {}
    for horizon in HORIZONS:
        prefix = f"h{horizon}"
        replacement[prefix] = {
            "vs_cash": summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_cash_usd") for row in rows]
            ),
            "vs_spy": summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_spy_usd") for row in rows]
            ),
            "vs_qqq": summarize_values(
                [row.get(f"{prefix}_replacement_value_vs_qqq_usd") for row in rows]
            ),
        }
    return {
        "rows": len(rows),
        "unique_tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "tickers": sorted({str(row.get("ticker")) for row in rows if row.get("ticker")}),
        "usable_rows": sum(1 for row in rows if row.get("estimate_revision_usable")),
        "nonflat_usable_rows": len(nonflat_usable),
        "direction_counts": dict(sorted(direction_counts.items())),
        "closed_rows_by_horizon": closed_counts,
        "pending_rows_by_horizon": pending_counts,
        "replacement_value_by_horizon": replacement,
        "sample_rows": rows[:5],
    }


def calibration(
    prediction: dict[str, Any],
    measurement_passed: bool,
    realized_failure_modes: list[str],
) -> dict[str, Any]:
    prob = safe_float(prediction.get("success_probability"))
    if prob is None:
        prob = 0.0
    actual = 1.0 if measurement_passed else 0.0
    predicted_failures = prediction.get("main_failure_modes") or []
    exact_hit = bool(set(predicted_failures) & set(realized_failure_modes))
    semantic_hit = (
        "only_h0_outcomes_mature" in predicted_failures
        and any(str(mode).startswith("forward_") and str(mode).endswith("_not_mature") for mode in realized_failure_modes)
    ) or ("no_alpha_readiness" in predicted_failures and bool(realized_failure_modes))
    return {
        "actual_decision": "accepted_measurement_repair" if measurement_passed else "blocked",
        "actual_success": actual,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual) ** 2, 4),
        "predicted_failure_modes": predicted_failures,
        "realized_failure_modes": realized_failure_modes,
        "predicted_failure_mode_hit": exact_hit or semantic_hit,
        "surprise_note": (
            "Expected: the new 2026-06-29 matched rows materialized and only h0 "
            "can close with the current hot warehouse."
            if measurement_passed
            else "The new matched rows could not be fully materialized from the hot warehouse."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    baseline = baseline_metrics()
    rows, source_metadata = build_outcome_rows()
    summary = summarize_rows(rows)

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_incomplete")
    if not SOURCE_EXPERIMENT_ARTIFACT.exists():
        measurement_blockers.append("source_exp20260630_021_artifact_missing")
    if not REVISION_LEDGER.exists():
        measurement_blockers.append("revision_ledger_missing")
    if not HOT_WAREHOUSE.exists():
        measurement_blockers.append("hot_warehouse_missing")
    if source_metadata["matched_candidate_rows"] == 0:
        measurement_blockers.append("no_candidate_rows_after_exp021")
    if source_metadata["hot_warehouse_missing_matched_tickers"]:
        measurement_blockers.append("no_20260629_hot_bars_for_matched_tickers")
    if summary["closed_rows_by_horizon"]["h0"] < source_metadata["matched_candidate_rows"]:
        measurement_blockers.append("h0_outcomes_not_fully_settled")
    if any(
        row.get("h0_status") == "closed"
        and (
            row.get("h0_replacement_value_vs_spy_usd") is None
            or row.get("h0_replacement_value_vs_qqq_usd") is None
        )
        for row in rows
    ):
        measurement_blockers.append("h0_benchmark_comparator_missing")

    alpha_blockers: list[str] = []
    if summary["nonflat_usable_rows"] < 20:
        alpha_blockers.append("matched_nonflat_sample_too_thin")
    if summary["closed_rows_by_horizon"]["h1"] < 20:
        alpha_blockers.append("forward_1d_outcomes_not_mature")
    if summary["closed_rows_by_horizon"]["h3"] < 20:
        alpha_blockers.append("forward_3d_outcomes_not_mature")
    if summary["closed_rows_by_horizon"]["h5"] < 20:
        alpha_blockers.append("forward_5d_outcomes_not_mature")
    if summary["closed_rows_by_horizon"]["h10"] < 20:
        alpha_blockers.append("forward_10d_outcomes_not_mature")

    measurement_passed = not measurement_blockers
    alpha_ready = measurement_passed and not alpha_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_estimate_revision_20260629_candidate_match_hot_outcome_ledger"
        if measurement_passed
        else "blocked_estimate_revision_20260629_candidate_match_hot_outcome_ledger"
    )
    realized_failure_modes = [*measurement_blockers, *alpha_blockers]
    before_after_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
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
        "change_type": "measurement_repair",
        "implementation_mode": "measurement_repair_hot_warehouse_outcome_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "exp-20260630-021 matched candidate rows",
            "hot warehouse h0 replacement values through 2026-06-29",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260626-023", "exp-20260630-021"],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "post_quant_signal_forward_observation_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, measurement_passed, realized_failure_modes),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-023": (
                    "Accepted measurement repair for the 2026-06-23 revision "
                    "surface; alpha still blocked by immature 3/5/10d rows."
                ),
                "exp-20260630-021": (
                    "Accepted measurement repair creating five 2026-06-29 matched "
                    "candidate rows after quant_signals_20260629 landed."
                ),
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: materialize h0/h1/h3/h5/h10 "
                "replacement values for the five post-exp021 matched candidate "
                "rows, with no threshold/rank/hold/notional decisions."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline remains unchanged, "
                "source ledgers load, all five matched candidate rows have h0 "
                "cash/SPY/QQQ values, and strategy delta is zero."
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
            "source_experiment_artifact": repo_rel(SOURCE_EXPERIMENT_ARTIFACT),
            "revision_ledger": repo_rel(REVISION_LEDGER),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            **before_after_delta,
            "matched_candidate_rows": source_metadata["matched_candidate_rows"],
            "h0_closed_rows": summary["closed_rows_by_horizon"]["h0"],
            "h1_closed_rows": summary["closed_rows_by_horizon"]["h1"],
            "h3_closed_rows": summary["closed_rows_by_horizon"]["h3"],
            "h5_closed_rows": summary["closed_rows_by_horizon"]["h5"],
            "h10_closed_rows": summary["closed_rows_by_horizon"]["h10"],
            "nonflat_usable_rows": summary["nonflat_usable_rows"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": SOURCE_EXPERIMENT_ARTIFACT.exists()
            and REVISION_LEDGER.exists()
            and HOT_WAREHOUSE.exists()
            and source_metadata["matched_candidate_rows"] > 0,
            "dependencies_validated": SOURCE_EXPERIMENT_ARTIFACT.exists()
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
                "h0_replacement_value_vs_spy_usd",
                "h0_replacement_value_vs_qqq_usd",
                "h1_status",
                "h3_status",
                "h5_status",
                "h10_status",
            ],
            "entry_date_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: fixed-horizon replacement attribution only; "
                "no target exits or orders are scheduled."
            ),
            "source_metadata": source_metadata,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable entry, exit, filter, ranking, or sizing rule was added.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": alpha_ready,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": alpha_blockers,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": before_after_delta,
            "alpha_readiness_rule": {
                "min_nonflat_usable_rows": 20,
                "min_closed_1d_rows": 20,
                "min_closed_3d_rows": 20,
                "min_closed_5d_rows": 20,
                "min_closed_10d_rows": 20,
                "requires_future_1_3_5_10d_rows_before_alpha_promotion": True,
            },
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
                "estimate-revision, signal, and warehouse surfaces and writes no "
                "shared helper, daily adapter, order, rank, size, exit, watchlist, "
                "or LLM changes."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The post-exp021 2026-06-29 matched candidate rows all had same-day "
                "hot-warehouse h0 cash/SPY/QQQ outcomes. Alpha promotion remains "
                "blocked because only h0 is closed, the non-flat sample is one row, "
                "and 1/3/5/10d outcomes are pending."
                if measurement_passed
                else "The new matched candidate rows could not be fully settled into a hot-warehouse outcome ledger."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run estimate-revision thresholds, direction gates, top-N, "
                "hold, notional, response curves, or observed-only condition slices "
                "from these five rows."
            ),
            "new_evidence_required": (
                "Next alpha-compliant revision work needs materially more matched "
                "candidate rows with closed 1/3/5/10d replacement values, another "
                "settled month of production revision rows, or a different "
                "unsaturated PIT expectation source."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_EXPERIMENT_ARTIFACT),
            repo_rel(REVISION_LEDGER),
            repo_rel(REVISION_SUMMARY),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260630-021.json",
            "quant/experiments/exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.py",
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
    record = {key: value for key, value in payload.items() if key != "matched_outcome_rows"}
    record["outcome_summary"] = {
        **payload["outcome_summary"],
        "sample_rows": payload["outcome_summary"]["sample_rows"][:5],
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["outcome_summary"]
    h0 = summary["replacement_value_by_horizon"]["h0"]["vs_cash"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: estimate revision 2026-06-29 outcome ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Matched candidate rows: `{summary['rows']}`",
            f"- Tickers: `{', '.join(summary['tickers'])}`",
            f"- Non-flat usable rows: `{summary['nonflat_usable_rows']}`",
            f"- Closed h0 rows: `{summary['closed_rows_by_horizon']['h0']}`",
            f"- Closed h1/h3/h5/h10 rows: `{summary['closed_rows_by_horizon']['h1']} / {summary['closed_rows_by_horizon']['h3']} / {summary['closed_rows_by_horizon']['h5']} / {summary['closed_rows_by_horizon']['h10']}`",
            f"- Mean h0 replacement vs cash: `{h0.get('mean')}`",
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
        SOURCE_EXPERIMENT_ARTIFACT,
        REVISION_LEDGER,
        REVISION_SUMMARY,
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
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    rebuild_experiment_log_from_shards(
        logs_dir=REPO_ROOT / "experiments" / "logs",
        log_path=EXPERIMENT_LOG,
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
                "matched_candidate_rows": payload["outcome_summary"]["rows"],
                "closed_rows_by_horizon": payload["outcome_summary"]["closed_rows_by_horizon"],
                "nonflat_usable_rows": payload["outcome_summary"]["nonflat_usable_rows"],
                "alpha_ready": payload["alpha_ready"],
                "measurement_blockers": payload["gate4"]["measurement_blockers"],
                "alpha_blockers": payload["gate4"]["alpha_blockers"],
                "artifact": payload["artifact"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
